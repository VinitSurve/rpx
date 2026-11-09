"""Go module manifest and checksum parser."""

from __future__ import annotations

from pathlib import Path

from rpx.models import DependencyInfo


def parse_go_mod(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse go.mod for required modules."""
    direct_deps: list[DependencyInfo] = []
    indirect_deps: list[DependencyInfo] = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            in_require = False
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith("//"):
                    continue

                if line_str == "require (":
                    in_require = True
                    continue
                elif in_require and line_str == ")":
                    in_require = False
                    continue

                if in_require or line_str.startswith("require "):
                    req_content = (
                        line_str[8:].strip() if line_str.startswith("require ") else line_str
                    )
                    is_indirect = "// indirect" in req_content
                    clean_content = req_content.replace("// indirect", "").strip()

                    parts = clean_content.split()
                    if len(parts) >= 1:
                        mod_name = parts[0]
                        version = parts[1] if len(parts) > 1 else ""
                        dep = DependencyInfo(
                            name=mod_name,
                            constraint=version,
                            dep_type="indirect" if is_indirect else "direct",
                            ecosystem="go",
                        )
                        if is_indirect:
                            indirect_deps.append(dep)
                        else:
                            direct_deps.append(dep)
    except (OSError, UnicodeDecodeError):
        pass

    return direct_deps, indirect_deps


def parse_go_sum(path: Path) -> list[DependencyInfo]:
    """Parse go.sum for recorded module checksum entries."""
    locked: list[DependencyInfo] = []
    seen = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    mod_name = parts[0]
                    mod_ver = parts[1].split("/")[0]  # strip /go.mod
                    key = (mod_name, mod_ver)
                    if key not in seen:
                        seen.add(key)
                        locked.append(
                            DependencyInfo(
                                name=mod_name,
                                resolved_version=mod_ver,
                                dep_type="locked",
                                ecosystem="go",
                            )
                        )
    except (OSError, UnicodeDecodeError):
        pass

    return locked
