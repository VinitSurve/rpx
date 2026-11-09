"""Configuration management, TOML loading, and template generation for RPX."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rpx.exceptions import ConfigError

DEFAULT_CONFIG_TEMPLATE = """# RPX (Repository Project Explorer) Configuration File
# Place this file as .rpx.toml or rpx.toml in your project root.

[rpx]
# Maximum number of items in rankings (e.g. largest files, longest files)
ranking_limit = 10

# Maximum directory tree nesting depth
max_depth = 3

# Additional directories or files to exclude from analysis
exclude = [
    "vendor",
    "docs/_build",
    "*.log"
]

# Include directories normally ignored by default or .gitignore (Warning: increases scan time)
include_ignored = false

# Disable Git analytics even if Git is available
no_git = false

# Disable dependency manifest parsing
no_deps = false

# Disable colored terminal output
no_color = false
"""


@dataclass
class RPXConfig:
    """RPX User configuration settings."""

    ranking_limit: int = 10
    max_depth: int = 3
    exclude: list[str] = field(default_factory=list)
    include_ignored: bool = False
    no_git: bool = False
    no_deps: bool = False
    no_color: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def find_config_file(project_root: Path) -> Path | None:
    """Search for .rpx.toml or rpx.toml in the project root."""
    for filename in (".rpx.toml", "rpx.toml"):
        p = project_root / filename
        if p.is_file():
            return p
    return None


def load_config(project_root: Path) -> RPXConfig:
    """Load configuration from .rpx.toml, rpx.toml, or pyproject.toml."""
    config_file = find_config_file(project_root)
    cfg = RPXConfig()

    if config_file:
        try:
            with open(config_file, "rb") as f:
                data = tomllib.load(f)
            rpx_sec = data.get("rpx", data)
            if isinstance(rpx_sec, dict):
                _populate_config(cfg, rpx_sec)
        except Exception as e:
            raise ConfigError(f"Error reading configuration file {config_file}: {e}") from e
    else:
        # Check pyproject.toml [tool.rpx]
        pyproject = project_root / "pyproject.toml"
        if pyproject.is_file():
            try:
                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                tool_rpx = data.get("tool", {}).get("rpx")
                if isinstance(tool_rpx, dict):
                    _populate_config(cfg, tool_rpx)
            except Exception:
                pass

    return cfg


def _populate_config(cfg: RPXConfig, data: dict[str, Any]) -> None:
    """Helper to populate RPXConfig fields from dict."""
    if "ranking_limit" in data and isinstance(data["ranking_limit"], int):
        cfg.ranking_limit = data["ranking_limit"]
    if "max_depth" in data and isinstance(data["max_depth"], int):
        cfg.max_depth = data["max_depth"]
    if "exclude" in data and isinstance(data["exclude"], list):
        cfg.exclude = [str(x) for x in data["exclude"]]
    if "include_ignored" in data and isinstance(data["include_ignored"], bool):
        cfg.include_ignored = data["include_ignored"]
    if "no_git" in data and isinstance(data["no_git"], bool):
        cfg.no_git = data["no_git"]
    if "no_deps" in data and isinstance(data["no_deps"], bool):
        cfg.no_deps = data["no_deps"]
    if "no_color" in data and isinstance(data["no_color"], bool):
        cfg.no_color = data["no_color"]


def init_config(destination_dir: Path, force: bool = False) -> Path:
    """Create a default .rpx.toml configuration file in destination_dir."""
    target_file = destination_dir / ".rpx.toml"
    if target_file.exists() and not force:
        raise ConfigError(
            f"Configuration file already exists: {target_file}. Use --force to overwrite."
        )

    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_CONFIG_TEMPLATE)
    except OSError as e:
        raise ConfigError(f"Failed to create configuration file: {e}") from e

    return target_file
