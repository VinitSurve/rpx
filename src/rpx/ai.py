"""Optional AI-assisted repository intelligence with pluggable credential and LLM provider adapters."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from rpx.analyzers.security import redact_all_secrets_in_text
from rpx.exceptions import AIProviderError
from rpx.models import ScanResult
from rpx.reporters.context_report import generate_context_markdown


class CredentialProvider(ABC):
    """Abstract interface for retrieving API credentials without hardcoding secrets."""

    @abstractmethod
    def get_api_key(self, provider_name: str) -> str | None:
        """Retrieve an API key for `provider_name` ('groq' or 'gemini'), or None if unavailable."""


class EnvCredentialProvider(CredentialProvider):
    """Retrieves API keys from standard environment variables."""

    ENV_MAP: dict[str, tuple[str, ...]] = {
        "groq": ("GROQ_API_KEY", "RPX_GROQ_API_KEY"),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "RPX_GEMINI_API_KEY"),
    }

    def get_api_key(self, provider_name: str) -> str | None:
        for env_var in self.ENV_MAP.get(provider_name.lower(), ()):
            val = os.environ.get(env_var, "").strip()
            if val:
                return val
        return None


class KeypoolCredentialProvider(CredentialProvider):
    """Extensible adapter for future `keypool` CLI secret manager integration.

    Does NOT assume `keypool` is installed. If `keypool` is not on PATH, returns None
    immediately without failing. When `keypool` is available in the future, it queries
    `keypool get <provider> --quiet` with a short timeout.
    """

    def __init__(self, enabled: bool = False):
        # Disabled by default unless RPX_USE_KEYPOOL=1 or explicitly enabled
        self.enabled = enabled or os.environ.get("RPX_USE_KEYPOOL") == "1"

    def is_available(self) -> bool:
        return self.enabled and shutil.which("keypool") is not None

    def get_api_key(self, provider_name: str) -> str | None:
        if not self.is_available():
            return None
        try:
            proc = subprocess.run(
                ["keypool", "get", provider_name.lower(), "--quiet"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            pass
        return None


class CompositeCredentialProvider(CredentialProvider):
    """Chains multiple CredentialProviders in priority order (Env -> Keypool)."""

    def __init__(self, providers: list[CredentialProvider] | None = None):
        self.providers = providers or [
            EnvCredentialProvider(),
            KeypoolCredentialProvider(),
        ]

    def get_api_key(self, provider_name: str) -> str | None:
        for p in self.providers:
            key = p.get_api_key(provider_name)
            if key:
                return key
        return None


class AIProvider(ABC):
    """Abstract base class for LLM repository intelligence providers."""

    name: str = "base"

    @abstractmethod
    def generate_insights(self, sanitized_context: str, focus: str = "architecture") -> str:
        """Generate architectural, onboarding, or refactoring insights from sanitized context."""


class GroqProvider(AIProvider):
    """Groq API adapter using standard library HTTPS client."""

    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model or "llama-3.3-70b-versatile"

    def generate_insights(self, sanitized_context: str, focus: str = "architecture") -> str:
        safe_payload_text = redact_all_secrets_in_text(sanitized_context)
        prompt = _build_system_prompt(focus)
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": safe_payload_text},
                ],
                "temperature": 0.2,
                "max_tokens": 1024,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "RPX-CLI/1.0.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return str(data["choices"][0]["message"]["content"]).strip()
        except (urllib.error.URLError, KeyError, ValueError) as e:
            raise AIProviderError(f"Groq API request failed: {e}") from e


class GeminiProvider(AIProvider):
    """Google Gemini API adapter using standard library HTTPS client."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model or "gemini-2.5-flash"

    def generate_insights(self, sanitized_context: str, focus: str = "architecture") -> str:
        safe_payload_text = redact_all_secrets_in_text(sanitized_context)
        prompt = _build_system_prompt(focus)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        body = json.dumps(
            {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{prompt}\n\n{safe_payload_text}"},
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "RPX-CLI/1.0.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return str(parts[0].get("text", "")).strip()
                raise AIProviderError("Empty response from Gemini API")
        except (urllib.error.URLError, KeyError, ValueError) as e:
            raise AIProviderError(f"Gemini API request failed: {e}") from e


def _build_system_prompt(focus: str) -> str:
    return (
        "You are a principal software architect reviewing a sanitized RPX repository summary. "
        f"Focus on: {focus}. Provide concise, actionable markdown bullet points covering: "
        "(1) Architecture & Module Structure Assessment, (2) Key Technical Debt & Complexity Priorities, "
        "(3) Onboarding Guide for New Engineers, and (4) Concrete Refactoring Recommendations."
    )


def generate_local_heuristic_summary(result: ScanResult, focus: str = "architecture") -> str:
    """Deterministic, 100% offline architectural & onboarding synthesis when no AI key is configured."""
    fp = result.fingerprint
    graph = result.graph
    comp = result.complexity
    debt = result.debt
    health = result.health

    lines = [
        f"### Offline Architectural & Engineering Synthesis ({result.metadata.name})",
        f"*Focus: {focus} • Mode: Local Deterministic Synthesis (No external API call)*",
        "",
        "#### 1. Architecture & Technology Overview",
        f"- **Stack**: {', '.join(fp.primary_languages or ['General'])} "
        f"({', '.join(fp.frameworks) if fp.frameworks else 'Standard library / CLI'})",
        f"- **Module Graph**: {graph.total_modules} internal modules connected by {graph.total_internal_edges} import edges across {len(graph.inferred_layers)} inferred layers (`{', '.join(sorted(graph.inferred_layers.keys())) or 'core'}`).",
        f"- **Entry Points**: {', '.join(f'`{e}`' for e in graph.entry_points[:5]) or 'Standard package root'}",
        f"- **Central Hubs**: {', '.join(f'`{m}`' for m in graph.central_hub_modules[:5]) or 'Distributed module graph'}",
        "",
        "#### 2. Refactoring & Technical Debt Priorities",
    ]

    if comp.high_complexity_functions:
        top_fn = comp.high_complexity_functions[0]
        lines.append(
            f"- **Complexity Hotspot**: Refactor `{top_fn.name}` in `{top_fn.file_path}:{top_fn.start_line}` "
            f"(Cyclomatic Complexity = {top_fn.cyclomatic_complexity}, {top_fn.line_count} lines)."
        )
    else:
        lines.append(
            f"- **Complexity Health**: All {comp.total_functions} analyzed functions are within healthy cyclomatic complexity bounds (avg {comp.avg_function_complexity:.2f})."
        )

    if graph.cycles:
        lines.append(
            f"- **Circular Imports**: Break {len(graph.cycles)} circular dependency cycle(s), starting with `{' -> '.join(graph.cycles[0])}`."
        )
    if debt.total_items > 0:
        lines.append(
            f"- **Debt Backlog**: {debt.total_items} tracked items (High: {debt.by_severity.get('high', 0)}, Medium: {debt.by_severity.get('medium', 0)}, Low: {debt.by_severity.get('low', 0)})."
        )

    lines.append("")
    lines.append("#### 3. Developer Onboarding & Recommended Next Steps")
    if health.recommendations:
        for rec in health.recommendations[:5]:
            lines.append(f"- {rec}")
    else:
        lines.append(
            "- Repository health score is strong. Maintain test coverage and lockfile hygiene."
        )

    lines.append("")
    lines.append(
        "> **Tip**: To enable live LLM synthesis via Groq or Google Gemini, set `GROQ_API_KEY` or `GEMINI_API_KEY` in your environment and run `rpx ai`."
    )
    return "\n".join(lines)


def run_ai_insights(
    result: ScanResult,
    provider_pref: str = "auto",
    model: str = "",
    focus: str = "architecture",
    offline: bool = False,
    cred_provider: CredentialProvider | None = None,
) -> tuple[str, str]:
    """Generate repository insights using an AI provider or fall back gracefully to local synthesis.

    Returns (provider_used, markdown_response).
    """
    if offline:
        return "local-offline", generate_local_heuristic_summary(result, focus=focus)

    creds = cred_provider or CompositeCredentialProvider()
    sanitized_ctx = redact_all_secrets_in_text(generate_context_markdown(result, max_chars=12000))

    pref = provider_pref.lower().strip() or "auto"
    candidates: list[str] = ["groq", "gemini"] if pref == "auto" else [pref]

    for cand in candidates:
        api_key = creds.get_api_key(cand)
        if not api_key:
            continue
        try:
            if cand == "groq":
                prov: AIProvider = GroqProvider(
                    api_key=api_key, model=model or "llama-3.3-70b-versatile"
                )
            elif cand == "gemini":
                prov = GeminiProvider(api_key=api_key, model=model or "gemini-2.5-flash")
            else:
                continue
            response = prov.generate_insights(sanitized_ctx, focus=focus)
            return prov.name, response
        except AIProviderError:
            if pref != "auto":
                raise
            continue

    return "local-fallback", generate_local_heuristic_summary(result, focus=focus)
