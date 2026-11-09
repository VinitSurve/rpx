# Security Policy

The RPX project takes the security of its code and its users seriously. As a local-first repository analysis tool designed to inspect source code and detect technical debt and secrets, ensuring our own security and privacy guarantees is paramount.

---

## Supported Versions

Only the latest active minor release receives active security patches.

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

---

## Reporting a Vulnerability

If you believe you have found a security vulnerability in RPX, please **do not open a public issue or discuss it in public forums**.

Instead, please report vulnerabilities privately using **GitHub Private Vulnerability Reporting**:

> **[Report a Security Advisory on GitHub](https://github.com/VinitSurve/rpx/security/advisories/new)**

If private vulnerability reporting is unavailable, contact the project maintainer via their GitHub profile or security advisory system.

### What to Include in Your Report

To help us triage and resolve the issue quickly, please provide:

1. **Description**: A clear description of the vulnerability.
2. **Impact**: An explanation of the potential severity and attack scenario.
3. **Reproduction Steps**: Step-by-step instructions or a minimal reproducible example.
4. **Environment**: RPX version, Python version, OS platform, and relevant terminal/shell configuration.
5. **Mitigation / Suggested Fix**: If you have identified a potential fix or workaround.

---

## Response Process & Timeline

- **Acknowledgment**: We aim to acknowledge receipt of your vulnerability report within **48 hours**.
- **Assessment**: We will evaluate the report, verify the impact, and communicate findings within **5 business days**.
- **Fix & Release**: Once confirmed, a fix will be developed in a private security fork, reviewed, and published in a patched patch release (e.g., `v1.0.1` or `v1.1.1`).
- **Public Disclosure**: A security advisory will be published simultaneously with the patch, giving credit to the reporter (unless anonymity is requested).

---

## RPX Core Security Guarantees

1. **Local-First & Offline**: RPX does not send project code, filenames, or metrics to external servers. All scanning and analytical calculations occur entirely on your local machine.
2. **Safe Read-Only Operations**: Standard scanning commands operate in read-only mode on the inspected filesystem and Git repository.
3. **Automated Secret Redaction**: RPX includes built-in pattern heuristics to detect potential secrets (API tokens, private keys, passwords) and automatically redacts them in terminal dashboards, HTML reports, and AI context exports.
4. **No Telemetry**: RPX collects zero usage statistics, telemetry, or behavioral tracking.

