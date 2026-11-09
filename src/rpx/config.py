"""Configuration management, TOML loading, validation, and template generation for RPX."""

from __future__ import annotations

import hashlib
import json
import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rpx.exceptions import ConfigError

DEFAULT_HEALTH_WEIGHTS: dict[str, int] = {
    "Maintainability": 12,
    "Testing": 15,
    "Documentation": 12,
    "Dependency Management": 10,
    "Configuration": 10,
    "Code Complexity": 12,
    "Project Structure": 9,
    "CI/CD Readiness": 10,
    "Repository Hygiene": 10,
}

DEFAULT_CONFIG_TEMPLATE = """# RPX (Repository Project Explorer) Configuration File
# Place this file as .rpx.toml or rpx.toml in your project root,
# or globally at ~/.config/rpx/config.toml

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

# Enable incremental file cache
use_cache = true

# Enable local security heuristics scan
security_enabled = true

# Optional AI provider preference ("auto", "groq", "gemini")
ai_provider = "auto"
ai_model = ""

[rpx.complexity]
low_max = 5
medium_max = 10
high_max = 20
max_function_lines = 60
max_class_lines = 300
max_file_lines = 500
max_nesting_depth = 4
max_parameters = 6

[rpx.health_weights]
"Maintainability" = 12
"Testing" = 15
"Documentation" = 12
"Dependency Management" = 10
"Configuration" = 10
"Code Complexity" = 12
"Project Structure" = 9
"CI/CD Readiness" = 10
"Repository Hygiene" = 10
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
    use_cache: bool = True
    cache_dir: str | None = None
    security_enabled: bool = True
    security_exclude_paths: list[str] = field(default_factory=list)
    ai_provider: str = "auto"
    ai_model: str = ""
    default_export_format: str = "json"

    # Complexity thresholds
    complexity_low_max: int = 5
    complexity_medium_max: int = 10
    complexity_high_max: int = 20
    max_function_lines: int = 60
    max_class_lines: int = 300
    max_file_lines: int = 500
    max_nesting_depth: int = 4
    max_parameters: int = 6

    # Health weights (sum to 100 by default)
    health_weights: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_HEALTH_WEIGHTS))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def signature(self) -> str:
        """Deterministic hash of analysis-affecting config fields for cache invalidation."""
        payload = {
            "exclude": sorted(self.exclude),
            "include_ignored": self.include_ignored,
            "no_deps": self.no_deps,
            "security_enabled": self.security_enabled,
            "complexity_low_max": self.complexity_low_max,
            "complexity_medium_max": self.complexity_medium_max,
            "complexity_high_max": self.complexity_high_max,
            "max_function_lines": self.max_function_lines,
            "max_class_lines": self.max_class_lines,
            "max_file_lines": self.max_file_lines,
            "max_nesting_depth": self.max_nesting_depth,
            "max_parameters": self.max_parameters,
            "health_weights": self.health_weights,
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]


def get_global_config_path() -> Path:
    """Return the path to the global RPX configuration file."""
    env_dir = os.environ.get("RPX_CONFIG_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve() / "config.toml"
    return Path.home() / ".config" / "rpx" / "config.toml"


def get_data_dir() -> Path:
    """Return the local data directory for RPX caches and snapshots."""
    env_dir = os.environ.get("RPX_DATA_DIR")
    if env_dir:
        base = Path(env_dir).expanduser().resolve()
    else:
        base = Path.home() / ".cache" / "rpx"
    base.mkdir(parents=True, exist_ok=True)
    return base


def find_config_file(project_root: Path) -> Path | None:
    """Search for .rpx.toml or rpx.toml in the project root."""
    for filename in (".rpx.toml", "rpx.toml"):
        p = project_root / filename
        if p.is_file():
            return p
    return None


def get_config_paths(project_root: Path) -> dict[str, str | None]:
    """Return resolved paths for global, project, and pyproject configuration files."""
    global_path = get_global_config_path()
    project_cfg = find_config_file(project_root)
    pyproject = project_root / "pyproject.toml"
    has_pyproject_rpx = False
    if pyproject.is_file():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            if isinstance(data.get("tool", {}).get("rpx"), dict):
                has_pyproject_rpx = True
        except Exception:
            pass

    return {
        "global_config": str(global_path)
        if global_path.is_file()
        else f"{global_path} (not found)",
        "project_config": str(project_cfg) if project_cfg else None,
        "pyproject_config": str(pyproject) if has_pyproject_rpx else None,
        "data_dir": str(get_data_dir()),
    }


def load_config(project_root: Path) -> RPXConfig:
    """Load configuration merging global config and project-level config."""
    cfg = RPXConfig()

    # 1. Global config if present
    global_path = get_global_config_path()
    if global_path.is_file():
        try:
            with open(global_path, "rb") as f:
                gdata = tomllib.load(f)
            g_sec = gdata.get("rpx", gdata)
            if isinstance(g_sec, dict):
                _populate_config(cfg, g_sec)
        except Exception:
            pass

    # 2. Project-level config (.rpx.toml / rpx.toml or pyproject.toml)
    config_file = find_config_file(project_root)
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
        cfg.ranking_limit = max(1, data["ranking_limit"])
    if "max_depth" in data and isinstance(data["max_depth"], int):
        cfg.max_depth = max(1, data["max_depth"])
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
    if "use_cache" in data and isinstance(data["use_cache"], bool):
        cfg.use_cache = data["use_cache"]
    if "cache_dir" in data and isinstance(data["cache_dir"], str):
        cfg.cache_dir = data["cache_dir"]
    if "security_enabled" in data and isinstance(data["security_enabled"], bool):
        cfg.security_enabled = data["security_enabled"]
    if "security_exclude_paths" in data and isinstance(data["security_exclude_paths"], list):
        cfg.security_exclude_paths = [str(x) for x in data["security_exclude_paths"]]
    if "ai_provider" in data and isinstance(data["ai_provider"], str):
        cfg.ai_provider = data["ai_provider"]
    if "ai_model" in data and isinstance(data["ai_model"], str):
        cfg.ai_model = data["ai_model"]
    if "default_export_format" in data and isinstance(data["default_export_format"], str):
        cfg.default_export_format = data["default_export_format"]

    # Nested [rpx.complexity]
    comp = data.get("complexity")
    if isinstance(comp, dict):
        if isinstance(comp.get("low_max"), int):
            cfg.complexity_low_max = comp["low_max"]
        if isinstance(comp.get("medium_max"), int):
            cfg.complexity_medium_max = comp["medium_max"]
        if isinstance(comp.get("high_max"), int):
            cfg.complexity_high_max = comp["high_max"]
        if isinstance(comp.get("max_function_lines"), int):
            cfg.max_function_lines = comp["max_function_lines"]
        if isinstance(comp.get("max_class_lines"), int):
            cfg.max_class_lines = comp["max_class_lines"]
        if isinstance(comp.get("max_file_lines"), int):
            cfg.max_file_lines = comp["max_file_lines"]
        if isinstance(comp.get("max_nesting_depth"), int):
            cfg.max_nesting_depth = comp["max_nesting_depth"]
        if isinstance(comp.get("max_parameters"), int):
            cfg.max_parameters = comp["max_parameters"]

    # Nested [rpx.health_weights]
    hw = data.get("health_weights")
    if isinstance(hw, dict):
        for k, v in hw.items():
            if isinstance(v, int) and v >= 0:
                cfg.health_weights[str(k)] = v


def check_config(project_root: Path) -> tuple[bool, list[str], RPXConfig]:
    """Validate configuration files in project_root and return (is_valid, messages, config)."""
    messages: list[str] = []
    is_valid = True

    global_path = get_global_config_path()
    if global_path.is_file():
        try:
            with open(global_path, "rb") as f:
                tomllib.load(f)
            messages.append(f"Global config valid: {global_path}")
        except Exception as e:
            is_valid = False
            messages.append(f"Global config invalid ({global_path}): {e}")

    project_cfg = find_config_file(project_root)
    if project_cfg:
        try:
            with open(project_cfg, "rb") as f:
                tomllib.load(f)
            messages.append(f"Project config valid: {project_cfg}")
        except Exception as e:
            is_valid = False
            messages.append(f"Project config invalid ({project_cfg}): {e}")
    else:
        pyproject = project_root / "pyproject.toml"
        if pyproject.is_file():
            try:
                with open(pyproject, "rb") as f:
                    pdata = tomllib.load(f)
                if "rpx" in pdata.get("tool", {}):
                    messages.append(f"Found valid [tool.rpx] in {pyproject}")
                else:
                    messages.append("No dedicated .rpx.toml found (using defaults)")
            except Exception as e:
                is_valid = False
                messages.append(f"pyproject.toml invalid: {e}")
        else:
            messages.append("No project config file found (using defaults)")

    try:
        cfg = load_config(project_root)
        if cfg.complexity_low_max >= cfg.complexity_medium_max:
            is_valid = False
            messages.append("complexity.low_max must be less than complexity.medium_max")
        if cfg.complexity_medium_max >= cfg.complexity_high_max:
            is_valid = False
            messages.append("complexity.medium_max must be less than complexity.high_max")
        total_weight = sum(cfg.health_weights.values())
        if total_weight <= 0:
            is_valid = False
            messages.append("health_weights sum must be positive")
    except ConfigError as e:
        is_valid = False
        messages.append(str(e))
        cfg = RPXConfig()

    return is_valid, messages, cfg


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
