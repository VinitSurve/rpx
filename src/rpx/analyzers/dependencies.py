"""Multi-ecosystem dependency orchestrator and manifest analyzer."""

from __future__ import annotations

from pathlib import Path

from rpx.models import DependencyAnalysis
from rpx.parsers.go import parse_go_mod, parse_go_sum
from rpx.parsers.java import parse_gradle_file, parse_pom_xml
from rpx.parsers.javascript import (
    inspect_node_modules,
    parse_package_json,
    parse_package_lock_json,
    parse_pnpm_lock,
    parse_yarn_lock,
)
from rpx.parsers.other import (
    parse_csproj,
    parse_gemfile,
    parse_gemfile_lock,
    parse_pubspec_yaml,
    parse_swift_resolved,
)
from rpx.parsers.php import (
    inspect_composer_vendor,
    parse_composer_json,
    parse_composer_lock,
)
from rpx.parsers.python import (
    inspect_python_virtualenv,
    parse_pipfile,
    parse_pipfile_lock,
    parse_poetry_or_uv_lock,
    parse_pyproject_toml,
    parse_requirements_txt,
)
from rpx.parsers.rust import parse_cargo_lock, parse_cargo_toml


def analyze_dependencies(project_root: Path) -> DependencyAnalysis:
    """Analyze all declared, locked, and installed dependencies across ecosystems."""
    analysis = DependencyAnalysis()

    # 1. JavaScript / TypeScript
    pkg_json = project_root / "package.json"
    if pkg_json.is_file():
        analysis.ecosystems.append("JavaScript/TypeScript")
        analysis.manifest_files.append("package.json")
        direct, dev = parse_package_json(pkg_json)
        analysis.declared_dependencies.extend(direct)
        analysis.declared_dependencies.extend(dev)

    # JS Lockfiles
    pkg_lock = project_root / "package-lock.json"
    if pkg_lock.is_file():
        analysis.lock_files.append("package-lock.json")
        analysis.locked_dependencies.extend(parse_package_lock_json(pkg_lock))

    yarn_lock = project_root / "yarn.lock"
    if yarn_lock.is_file():
        analysis.lock_files.append("yarn.lock")
        analysis.locked_dependencies.extend(parse_yarn_lock(yarn_lock))

    pnpm_lock = project_root / "pnpm-lock.yaml"
    if pnpm_lock.is_file():
        analysis.lock_files.append("pnpm-lock.yaml")
        analysis.locked_dependencies.extend(parse_pnpm_lock(pnpm_lock))

    bun_lock = project_root / "bun.lock"
    bun_lockb = project_root / "bun.lockb"
    if bun_lock.is_file() or bun_lockb.is_file():
        lock_name = "bun.lock" if bun_lock.is_file() else "bun.lockb"
        analysis.lock_files.append(lock_name)

    # JS Installed packages
    js_installed = inspect_node_modules(project_root)
    if js_installed:
        analysis.installed_dependencies.extend(js_installed)

    # 2. Python
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        p_direct, p_dev = parse_pyproject_toml(pyproject)
        if p_direct or p_dev:
            if "Python" not in analysis.ecosystems:
                analysis.ecosystems.append("Python")
            analysis.manifest_files.append("pyproject.toml")
            analysis.declared_dependencies.extend(p_direct)
            analysis.declared_dependencies.extend(p_dev)

    for req_name in ("requirements.txt", "requirements-dev.txt"):
        req_path = project_root / req_name
        if req_path.is_file():
            if "Python" not in analysis.ecosystems:
                analysis.ecosystems.append("Python")
            analysis.manifest_files.append(req_name)
            analysis.declared_dependencies.extend(
                parse_requirements_txt(req_path, is_dev=("dev" in req_name))
            )

    pipfile = project_root / "Pipfile"
    if pipfile.is_file():
        if "Python" not in analysis.ecosystems:
            analysis.ecosystems.append("Python")
        analysis.manifest_files.append("Pipfile")
        p_direct, p_dev = parse_pipfile(pipfile)
        analysis.declared_dependencies.extend(p_direct)
        analysis.declared_dependencies.extend(p_dev)

    # Python Lockfiles
    for py_lock in ("poetry.lock", "uv.lock"):
        p_lock_path = project_root / py_lock
        if p_lock_path.is_file():
            analysis.lock_files.append(py_lock)
            analysis.locked_dependencies.extend(parse_poetry_or_uv_lock(p_lock_path))

    pipfile_lock = project_root / "Pipfile.lock"
    if pipfile_lock.is_file():
        analysis.lock_files.append("Pipfile.lock")
        analysis.locked_dependencies.extend(parse_pipfile_lock(pipfile_lock))

    # Python Installed packages in local virtualenv
    py_installed = inspect_python_virtualenv(project_root)
    if py_installed:
        analysis.installed_dependencies.extend(py_installed)

    # 3. Rust
    cargo_toml = project_root / "Cargo.toml"
    if cargo_toml.is_file():
        analysis.ecosystems.append("Rust")
        analysis.manifest_files.append("Cargo.toml")
        r_direct, r_dev = parse_cargo_toml(cargo_toml)
        analysis.declared_dependencies.extend(r_direct)
        analysis.declared_dependencies.extend(r_dev)

    cargo_lock = project_root / "Cargo.lock"
    if cargo_lock.is_file():
        analysis.lock_files.append("Cargo.lock")
        analysis.locked_dependencies.extend(parse_cargo_lock(cargo_lock))

    # 4. Go
    go_mod = project_root / "go.mod"
    if go_mod.is_file():
        analysis.ecosystems.append("Go")
        analysis.manifest_files.append("go.mod")
        g_direct, g_indirect = parse_go_mod(go_mod)
        analysis.declared_dependencies.extend(g_direct)
        analysis.declared_dependencies.extend(g_indirect)

    go_sum = project_root / "go.sum"
    if go_sum.is_file():
        analysis.lock_files.append("go.sum")
        analysis.locked_dependencies.extend(parse_go_sum(go_sum))

    # 5. PHP
    composer_json = project_root / "composer.json"
    if composer_json.is_file():
        analysis.ecosystems.append("PHP")
        analysis.manifest_files.append("composer.json")
        c_direct, c_dev = parse_composer_json(composer_json)
        analysis.declared_dependencies.extend(c_direct)
        analysis.declared_dependencies.extend(c_dev)

    composer_lock = project_root / "composer.lock"
    if composer_lock.is_file():
        analysis.lock_files.append("composer.lock")
        analysis.locked_dependencies.extend(parse_composer_lock(composer_lock))

    php_installed = inspect_composer_vendor(project_root)
    if php_installed:
        analysis.installed_dependencies.extend(php_installed)

    # 6. Ruby
    gemfile = project_root / "Gemfile"
    if gemfile.is_file():
        analysis.ecosystems.append("Ruby")
        analysis.manifest_files.append("Gemfile")
        rb_direct, rb_dev = parse_gemfile(gemfile)
        analysis.declared_dependencies.extend(rb_direct)
        analysis.declared_dependencies.extend(rb_dev)

    gemfile_lock = project_root / "Gemfile.lock"
    if gemfile_lock.is_file():
        analysis.lock_files.append("Gemfile.lock")
        analysis.locked_dependencies.extend(parse_gemfile_lock(gemfile_lock))

    # 7. Java / Kotlin
    pom_xml = project_root / "pom.xml"
    if pom_xml.is_file():
        analysis.ecosystems.append("Java/Maven")
        analysis.manifest_files.append("pom.xml")
        j_direct, j_test = parse_pom_xml(pom_xml)
        analysis.declared_dependencies.extend(j_direct)
        analysis.declared_dependencies.extend(j_test)

    for gradle_file in ("build.gradle", "build.gradle.kts"):
        g_file_path = project_root / gradle_file
        if g_file_path.is_file():
            if "Java/Gradle" not in analysis.ecosystems:
                analysis.ecosystems.append("Java/Gradle")
            analysis.manifest_files.append(gradle_file)
            g_direct, g_test = parse_gradle_file(g_file_path)
            analysis.declared_dependencies.extend(g_direct)
            analysis.declared_dependencies.extend(g_test)

    # 8. .NET
    for csproj in project_root.glob("*.csproj"):
        analysis.ecosystems.append(".NET")
        analysis.manifest_files.append(csproj.name)
        analysis.declared_dependencies.extend(parse_csproj(csproj))

    # 9. Dart / Flutter
    pubspec = project_root / "pubspec.yaml"
    if pubspec.is_file():
        analysis.ecosystems.append("Dart/Flutter")
        analysis.manifest_files.append("pubspec.yaml")
        d_direct, d_dev = parse_pubspec_yaml(pubspec)
        analysis.declared_dependencies.extend(d_direct)
        analysis.declared_dependencies.extend(d_dev)

    # 10. Swift
    swift_resolved = project_root / "Package.resolved"
    if swift_resolved.is_file():
        analysis.ecosystems.append("Swift")
        analysis.lock_files.append("Package.resolved")
        analysis.locked_dependencies.extend(parse_swift_resolved(swift_resolved))

    # Counts
    analysis.direct_dependencies_count = sum(
        1 for d in analysis.declared_dependencies if d.dep_type in ("direct", "build")
    )
    analysis.dev_dependencies_count = sum(
        1 for d in analysis.declared_dependencies if d.dep_type in ("dev", "test")
    )

    if analysis.locked_dependencies:
        analysis.transitive_dependencies_count = len(analysis.locked_dependencies)
    if analysis.installed_dependencies:
        analysis.installed_dependencies_count = len(analysis.installed_dependencies)

    # Check for missing dependencies (declared direct dependencies not in locked or installed)
    if analysis.lock_files or analysis.installed_dependencies:
        known_names = {d.name.lower() for d in analysis.locked_dependencies} | {
            d.name.lower() for d in analysis.installed_dependencies
        }
        for d in analysis.declared_dependencies:
            if d.dep_type == "direct" and d.name.lower() not in known_names:
                analysis.missing_dependencies.append(d.name)
        analysis.missing_dependencies_count = len(analysis.missing_dependencies)
        if analysis.missing_dependencies:
            analysis.completeness_status = (
                f"{len(analysis.missing_dependencies)} Unresolved/Missing"
            )
        else:
            analysis.completeness_status = "Complete & Resolved"
    elif analysis.declared_dependencies:
        analysis.completeness_status = "Manifest only (no lockfile)"
    else:
        analysis.completeness_status = "No dependencies declared"

    return analysis
