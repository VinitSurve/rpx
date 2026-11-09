# Homebrew Tap Setup Guide for RPX

This guide explains how to set up and maintain a dedicated Homebrew tap for RPX under `VinitSurve/homebrew-tap`.

---

## 1. Create the Tap Repository

1. On GitHub, create a new public repository named `homebrew-tap` under your account (`VinitSurve/homebrew-tap`).
2. Clone the repository locally:

```bash
git clone https://github.com/VinitSurve/homebrew-tap.git
cd homebrew-tap
mkdir Formula
```

---

## 2. Generate Formula for a Release

When a new version of RPX is released to PyPI or GitHub Releases:

1. Obtain the release source tarball SHA-256 checksum:

```bash
curl -sL https://github.com/VinitSurve/rpx/archive/refs/tags/v1.0.0.tar.gz | sha256sum
# or from PyPI source distribution:
curl -sL https://files.pythonhosted.org/packages/source/r/rpx/rpx-1.0.0.tar.gz | sha256sum
```

2. Generate or update `Formula/rpx.rb` using `homebrew-pypi-poet` or the template in `packaging/homebrew/rpx.rb.template`:

```bash
pip install homebrew-pypi-poet
poet rpx > Formula/rpx.rb
```

3. Commit and push the formula to `VinitSurve/homebrew-tap`:

```bash
git add Formula/rpx.rb
git commit -m "feat(rpx): release v1.0.0"
git push origin main
```

---

## 3. User Installation

Once the tap repository is published, users can install RPX with:

```bash
brew tap VinitSurve/tap
brew install rpx
```

And test it with:

```bash
brew test rpx
```

