"""Local security hygiene and risk indicator scanner with mandatory secret redaction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from rpx.config import RPXConfig
from rpx.models import (
    DependencyAnalysis,
    FileRecord,
    SecurityAnalysis,
    SecurityFinding,
)

# Safe template env filenames that are NOT security findings
_SAFE_ENV_NAMES = {
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.dist",
    ".env.defaults",
    ".env.schema",
}

# Sensitive file extensions and names
_SENSITIVE_FILENAMES = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials.json",
    "service-account.json",
    ".htpasswd",
    ".netrc",
    ".npmrc",
    ".pypirc",
}
_SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".keystore", ".jks"}

# Secret detection regexes: (rule_id, severity, description, regex)
_SECRET_PATTERNS: list[tuple[str, str, str, re.Pattern[str]]] = [
    (
        "SEC001",
        "high",
        "Potential AWS Access Key ID",
        re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"),
    ),
    (
        "SEC002",
        "high",
        "Potential GitHub Personal Access Token",
        re.compile(
            r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{22,255})\b"
        ),
    ),
    (
        "SEC003",
        "high",
        "Potential Private Key Material",
        re.compile(r"(-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----)"),
    ),
    (
        "SEC004",
        "high",
        "Potential OpenAI / Anthropic / AI API Key",
        re.compile(r"\b(sk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,})\b"),
    ),
    (
        "SEC005",
        "high",
        "Potential Google Cloud / Firebase API Key",
        re.compile(r"\b(AIza[0-9A-Za-z\-_]{35})\b"),
    ),
    (
        "SEC006",
        "high",
        "Potential Slack Token",
        re.compile(r"\b(xox[baprs]-[0-9A-Za-z\-]{10,})\b"),
    ),
    (
        "SEC007",
        "high",
        "Potential Stripe Live Key",
        re.compile(r"\b((?:sk|rk)_live_[0-9a-zA-Z]{16,})\b"),
    ),
    (
        "SEC008",
        "medium",
        "Potential Hardcoded Secret / Password Assignment",
        re.compile(
            r"""(?i)\b(?:api_key|apikey|secret_key|client_secret|access_token|auth_token|password|passwd|db_pass)\s*[:=]\s*['"]([A-Za-z0-9_\-!@#$%^&*+=]{12,})['"]"""
        ),
    ),
]

# Placeholder values to ignore in generic secret matching
_PLACEHOLDER_VALUES = {
    "changeme",
    "your_api_key_here",
    "your-api-key-here",
    "replace_me",
    "placeholder",
    "example_secret",
    "dummy_secret_value",
    "none",
    "null",
    "undefined",
    "************",
    "xxxxxxxxxxxx",
}

# Security anti-patterns and suspicious configurations
_ANTIPATTERN_RULES: list[tuple[str, str, str, str, re.Pattern[str], set[str] | None, str]] = [
    (
        "SEC101",
        "anti_pattern",
        "medium",
        "Use of eval() or exec() enables arbitrary code execution if fed untrusted input",
        re.compile(r"\b(?:eval|exec)\s*\("),
        {"Python", "JavaScript", "TypeScript", "JSX", "TSX", "PHP"},
        "Replace eval()/exec() with safe parsers (e.g. ast.literal_eval or JSON.parse).",
    ),
    (
        "SEC102",
        "anti_pattern",
        "high",
        "Subprocess invocation with shell=True can lead to command injection",
        re.compile(
            r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\s*\([^)]*shell\s*=\s*True"
        ),
        {"Python"},
        "Pass command arguments as a list and set shell=False.",
    ),
    (
        "SEC103",
        "anti_pattern",
        "medium",
        "Deserialization with pickle.loads/load is unsafe on untrusted data",
        re.compile(r"\bpickle\.loads?\s*\("),
        {"Python"},
        "Use JSON or a schema-validated format for untrusted payloads.",
    ),
    (
        "SEC104",
        "anti_pattern",
        "medium",
        "Unsafe YAML loading without SafeLoader",
        re.compile(r"\byaml\.load\s*\([^)]*(?!Loader\s*=\s*(?:yaml\.)?SafeLoader)"),
        {"Python"},
        "Use yaml.safe_load() instead of yaml.load().",
    ),
    (
        "SEC105",
        "anti_pattern",
        "medium",
        "Direct DOM HTML injection (innerHTML / dangerouslySetInnerHTML)",
        re.compile(r"\b(?:dangerouslySetInnerHTML|\.innerHTML\s*=)"),
        {"JavaScript", "TypeScript", "JSX", "TSX"},
        "Sanitize HTML content or use textContent / safe rendering APIs.",
    ),
    (
        "SEC201",
        "suspicious_config",
        "low",
        "TLS/SSL certificate verification explicitly disabled (verify=False)",
        re.compile(r"\bverify\s*=\s*False\b"),
        {"Python"},
        "Keep TLS verification enabled in production requests.",
    ),
    (
        "SEC202",
        "suspicious_config",
        "low",
        "Service bound to all interfaces (0.0.0.0)",
        re.compile(r"""['"]0\.0\.0\.0['"]"""),
        None,
        "Bind to 127.0.0.1 for local services or configure explicit host bindings via environment variables.",
    ),
]


def redact_secret(secret_value: str) -> str:
    """Mandatory secret redaction helper. Never returns raw secret text."""
    val = secret_value.strip()
    if not val:
        return "[REDACTED]"
    if "PRIVATE KEY" in val:
        return "-----BEGIN [REDACTED PRIVATE KEY]-----"
    if len(val) <= 8:
        return "***REDACTED***"
    return f"{val[:4]}...***REDACTED***...{val[-2:]}"


def redact_line_snippet(line: str, secret_value: str) -> str:
    """Replace any occurrence of secret_value inside a line snippet with its redacted form."""
    redacted = redact_secret(secret_value)
    safe_line = line.replace(secret_value, redacted).strip()
    return safe_line[:120]


def redact_all_secrets_in_text(text: str) -> str:
    """Scan arbitrary text and redact all matching secret patterns before external export/AI calls."""
    result = text
    for _, _, _, pattern in _SECRET_PATTERNS:

        def _repl(match: re.Match[str]) -> str:
            full = match.group(0)
            target = match.group(1) if match.lastindex else full
            return full.replace(target, redact_secret(target))

        result = pattern.sub(_repl, result)
    return result


def analyze_security(
    project_root: Path,
    files: Sequence[FileRecord],
    dep_analysis: DependencyAnalysis | None,
    config: RPXConfig,
) -> SecurityAnalysis:
    """Run local security heuristics and secret hygiene checks across the repository."""
    if not config.security_enabled:
        return SecurityAnalysis()

    findings: list[SecurityFinding] = []
    committed_env_files: list[str] = []
    sensitive_files: list[str] = []

    excluded_prefixes = tuple(config.security_exclude_paths)

    for f in files:
        rel_path = f.relative_path
        if excluded_prefixes and rel_path.startswith(excluded_prefixes):
            continue

        name_lower = f.name.lower()

        # 1. Check for committed .env files
        if name_lower == ".env" or (
            name_lower.startswith(".env.") and name_lower not in _SAFE_ENV_NAMES
        ):
            committed_env_files.append(rel_path)
            findings.append(
                SecurityFinding(
                    category="sensitive_file",
                    severity="high",
                    file_path=rel_path,
                    line_number=None,
                    rule_id="SEC010",
                    message=f"Environment file '{rel_path}' is present in repository workspace",
                    redacted_snippet=f"File: {rel_path} (contents not displayed for security)",
                    recommendation="Add .env* to .gitignore and store only .env.example in version control.",
                )
            )
            continue

        # 2. Check for sensitive key/credential files
        if name_lower in _SENSITIVE_FILENAMES or f.extension.lower() in _SENSITIVE_EXTENSIONS:
            sensitive_files.append(rel_path)
            findings.append(
                SecurityFinding(
                    category="sensitive_file",
                    severity="high",
                    file_path=rel_path,
                    line_number=None,
                    rule_id="SEC011",
                    message=f"Sensitive credential or key file detected: '{rel_path}'",
                    redacted_snippet=f"File: {rel_path}",
                    recommendation="Remove private keys and credential files from the repository and rotate affected credentials.",
                )
            )
            continue

        if f.is_binary:
            continue

        is_test_file = "test" in rel_path.lower() or rel_path.startswith("tests/")

        # Read text file for pattern scanning
        full_path = project_root / rel_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()
        for line_idx, line in enumerate(lines, start=1):
            if len(line) > 1000:
                continue

            # Skip regex pattern definitions inside security scanners themselves
            if "re.compile(" in line or "_SECRET_PATTERNS" in line:
                continue

            # Check hardcoded secret patterns
            for rule_id, sev, desc, pattern in _SECRET_PATTERNS:
                m = pattern.search(line)
                if m:
                    secret_val = m.group(1) if m.lastindex else m.group(0)
                    if secret_val.lower() in _PLACEHOLDER_VALUES:
                        continue
                    findings.append(
                        SecurityFinding(
                            category="potential_secret",
                            severity="medium" if is_test_file else sev,
                            file_path=rel_path,
                            line_number=line_idx,
                            rule_id=rule_id,
                            message=f"{desc} detected (redacted)",
                            redacted_snippet=redact_line_snippet(line, secret_val),
                            recommendation="Move secrets to environment variables or a secret manager and rotate exposed keys.",
                        )
                    )

            # Check security anti-patterns & suspicious config (skip in test files)
            if not is_test_file and f.is_source:
                stripped = line.strip()
                if stripped.startswith(("#", "//", "/*", "*")):
                    continue
                for (
                    rule_id,
                    cat,
                    sev,
                    msg,
                    pattern,
                    allowed_langs,
                    rec,
                ) in _ANTIPATTERN_RULES:
                    if allowed_langs is None or f.language in allowed_langs:
                        if pattern.search(line):
                            findings.append(
                                SecurityFinding(
                                    category=cat,
                                    severity=sev,
                                    file_path=rel_path,
                                    line_number=line_idx,
                                    rule_id=rule_id,
                                    message=msg,
                                    redacted_snippet=stripped[:120],
                                    recommendation=rec,
                                )
                            )

    # 3. Check unsafe dependency declarations
    if dep_analysis:
        for dep in dep_analysis.dependencies:
            spec = dep.version_spec.strip()
            if spec in ("*", "latest"):
                findings.append(
                    SecurityFinding(
                        category="unsafe_dependency",
                        severity="low",
                        file_path=dep.source_file,
                        line_number=None,
                        rule_id="SEC301",
                        message=f"Dependency '{dep.name}' uses wildcard/unbounded version '{spec}'",
                        redacted_snippet=f"{dep.name} = {spec}",
                        recommendation="Pin dependencies to explicit version ranges and commit a lockfile.",
                    )
                )
            elif "http://" in spec.lower():
                findings.append(
                    SecurityFinding(
                        category="unsafe_dependency",
                        severity="high",
                        file_path=dep.source_file,
                        line_number=None,
                        rule_id="SEC302",
                        message=f"Dependency '{dep.name}' is fetched over unencrypted HTTP",
                        redacted_snippet=f"{dep.name} @ {spec}",
                        recommendation="Use HTTPS or a verified package registry.",
                    )
                )

    sev_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(
        key=lambda x: (
            sev_order.get(x.severity, 3),
            x.file_path,
            x.line_number or 0,
        )
    )

    by_severity: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    by_category: dict[str, int] = {}
    for item in findings:
        by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
        by_category[item.category] = by_category.get(item.category, 0) + 1

    return SecurityAnalysis(
        total_findings=len(findings),
        by_severity=by_severity,
        by_category=by_category,
        committed_env_files=committed_env_files,
        sensitive_files=sensitive_files,
        findings=findings,
    )
