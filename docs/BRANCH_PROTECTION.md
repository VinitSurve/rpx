# GitHub Branch Protection & Repository Security Configuration

This guide provides the exact configuration required to protect the `main` branch and secure the repository at [https://github.com/VinitSurve/rpx](https://github.com/VinitSurve/rpx).

---

## 1. Branch Protection Rules for `main`

Navigate to **Settings -> Branches -> Add branch protection rule**:

1. **Branch name pattern**: `main`
2. **Protect matching branches**:
   - [x] **Require a pull request before merging**
     - Require approvals: `1` (or leave unchecked if you are the sole maintainer self-merging approved PRs).
     - [x] Dismiss stale pull request approvals when new commits are pushed.
   - [x] **Require status checks to pass before merging**
     - [x] Require branches to be up to date before merging.
     - Search and select the following status check jobs from the CI workflow:
       - `Test (ubuntu-latest, Py 3.11)`
       - `Test (ubuntu-latest, Py 3.12)`
       - `Test (ubuntu-latest, Py 3.13)`
       - `Test (macos-latest, Py 3.11)`
       - `Test (windows-latest, Py 3.11)`
       - `Package Validation & Security Audit`
       - `CodeQL Analysis (Python)`
   - [x] **Require conversation resolution before merging**
   - [x] **Require linear history** (optional, recommended for clean git logs)
   - [x] **Do not allow bypassing the above settings** (or allow administrators if you need emergency override)
   - [x] **Block force pushes** (applies to everyone)
   - [x] **Do not allow deletions**

Click **Create** or **Save changes**.

---

## 2. GitHub Code Security & Analysis

Navigate to **Settings -> Code security and analysis**:

- **Private vulnerability reporting**: Click **Enable** (allows security researchers to report vulnerabilities privately via advisory).
- **Dependency graph**: **Enable** (required for Dependabot).
- **Dependabot alerts**: **Enable**.
- **Dependabot security updates**: **Enable**.
- **Secret scanning**: **Enable** (alerts if secrets or tokens are ever detected in git commits).
- **Push protection**: **Enable** (blocks git pushes containing known secret patterns before they reach GitHub).

---

## 3. PyPI Trusted Publishing (OIDC) Setup

RPX uses PyPI Trusted Publishing (no long-lived API tokens required).

1. Log into your account on [https://pypi.org/](https://pypi.org/).
2. Navigate to **Publishing** -> **Add a publisher**:
   - **Publisher type**: GitHub
   - **PyPI Project Name**: `rpx`
   - **Owner**: `VinitSurve`
   - **Repository name**: `rpx`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`
3. Click **Add publisher**.
4. When you push a git tag matching `v*` (e.g., `git tag v1.0.0 && git push origin v1.0.0`), the `.github/workflows/release.yml` workflow will automatically authenticate with PyPI via OIDC and publish the package safely.

