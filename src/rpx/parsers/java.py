"""Java and JVM build file parsers (Maven pom.xml and Gradle)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from rpx.models import DependencyInfo


def parse_pom_xml(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse Maven pom.xml for declared dependencies."""
    direct_deps: list[DependencyInfo] = []
    test_deps: list[DependencyInfo] = []

    try:
        tree = ET.parse(path)
        root = tree.getroot()

        # Remove namespace prefix if present
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        dependencies = root.find(f"{ns}dependencies")
        if dependencies is not None:
            for dep in dependencies.findall(f"{ns}dependency"):
                group_id = dep.find(f"{ns}groupId")
                artifact_id = dep.find(f"{ns}artifactId")
                version = dep.find(f"{ns}version")
                scope = dep.find(f"{ns}scope")

                if artifact_id is not None and artifact_id.text:
                    name = (
                        f"{group_id.text}:{artifact_id.text}"
                        if (group_id is not None and group_id.text)
                        else artifact_id.text
                    )
                    ver = version.text if version is not None and version.text else ""
                    is_test = scope is not None and scope.text == "test"

                    dep_info = DependencyInfo(
                        name=name,
                        constraint=ver,
                        dep_type="test" if is_test else "direct",
                        ecosystem="maven",
                    )
                    if is_test:
                        test_deps.append(dep_info)
                    else:
                        direct_deps.append(dep_info)
    except (ET.ParseError, OSError):
        pass

    return direct_deps, test_deps


def parse_gradle_file(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse Gradle build file (Groovy or Kotlin DSL) for dependency declarations."""
    direct_deps: list[DependencyInfo] = []
    test_deps: list[DependencyInfo] = []

    pattern = re.compile(
        r"""(implementation|api|compileOnly|runtimeOnly|testImplementation|testCompileOnly)\s*[\('"]([^'")]+)""",
        re.MULTILINE,
    )

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        for match in pattern.finditer(content):
            config_type = match.group(1).lower()
            spec = match.group(2).strip()
            is_test = "test" in config_type

            parts = spec.split(":")
            name = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else spec
            version = parts[2] if len(parts) >= 3 else ""

            dep = DependencyInfo(
                name=name,
                constraint=version,
                dep_type="test" if is_test else "direct",
                ecosystem="gradle",
            )
            if is_test:
                test_deps.append(dep)
            else:
                direct_deps.append(dep)
    except (OSError, UnicodeDecodeError):
        pass

    return direct_deps, test_deps
