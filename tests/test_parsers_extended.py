"""Extended tests for ecosystem parsers (Java, PHP, Ruby, .NET, Dart, Swift, Lockfiles)."""

from pathlib import Path

from rpx.parsers.go import parse_go_sum
from rpx.parsers.java import parse_gradle_file, parse_pom_xml
from rpx.parsers.javascript import (
    inspect_node_modules,
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
)
from rpx.parsers.rust import parse_cargo_lock


def test_java_parsers(tmp_path: Path):
    # Maven pom.xml
    pom = tmp_path / "pom.xml"
    pom.write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        "  <dependencies>\n"
        "    <dependency>\n"
        "      <groupId>org.springframework.boot</groupId>\n"
        "      <artifactId>spring-boot-starter-web</artifactId>\n"
        "      <version>3.1.0</version>\n"
        "    </dependency>\n"
        "    <dependency>\n"
        "      <groupId>org.junit.jupiter</groupId>\n"
        "      <artifactId>junit-jupiter</artifactId>\n"
        "      <version>5.9.3</version>\n"
        "      <scope>test</scope>\n"
        "    </dependency>\n"
        "  </dependencies>\n"
        "</project>\n",
        encoding="utf-8",
    )
    direct, test = parse_pom_xml(pom)
    assert len(direct) == 1
    assert "spring-boot-starter-web" in direct[0].name
    assert len(test) == 1
    assert "junit-jupiter" in test[0].name

    # Gradle
    gradle = tmp_path / "build.gradle"
    gradle.write_text(
        "dependencies {\n"
        '    implementation "com.google.guava:guava:31.1-jre"\n'
        '    testImplementation "junit:junit:4.13.2"\n'
        "}\n",
        encoding="utf-8",
    )
    g_direct, g_test = parse_gradle_file(gradle)
    assert len(g_direct) == 1
    assert "guava" in g_direct[0].name
    assert len(g_test) == 1


def test_php_parsers(tmp_path: Path):
    # Composer.json
    composer = tmp_path / "composer.json"
    composer.write_text(
        "{\n"
        '  "require": {\n'
        '    "php": "^8.1",\n'
        '    "monolog/monolog": "^3.0"\n'
        "  },\n"
        '  "require-dev": {\n'
        '    "phpunit/phpunit": "^10.0"\n'
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    direct, dev = parse_composer_json(composer)
    assert len(direct) == 1
    assert direct[0].name == "monolog/monolog"
    assert len(dev) == 1
    assert dev[0].name == "phpunit/phpunit"

    # Composer.lock
    lock = tmp_path / "composer.lock"
    lock.write_text(
        "{\n"
        '  "packages": [\n'
        '    {"name": "monolog/monolog", "version": "3.4.0"}\n'
        "  ],\n"
        '  "packages-dev": [\n'
        '    {"name": "phpunit/phpunit", "version": "10.2.0"}\n'
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    locked = parse_composer_lock(lock)
    assert len(locked) == 2

    # Composer vendor inspection
    vendor_dir = tmp_path / "vendor" / "psr" / "log"
    vendor_dir.mkdir(parents=True)
    installed = inspect_composer_vendor(tmp_path)
    assert len(installed) == 1
    assert installed[0].name == "psr/log"


def test_ruby_parsers(tmp_path: Path):
    # Gemfile
    gemfile = tmp_path / "Gemfile"
    gemfile.write_text(
        'source "https://rubygems.org"\n'
        'gem "rails", "~> 7.0"\n'
        "group :development, :test do\n"
        '  gem "rspec-rails", "~> 6.0"\n'
        "end\n",
        encoding="utf-8",
    )
    direct, dev = parse_gemfile(gemfile)
    assert len(direct) == 1
    assert direct[0].name == "rails"
    assert len(dev) == 1
    assert dev[0].name == "rspec-rails"

    # Gemfile.lock
    lock = tmp_path / "Gemfile.lock"
    lock.write_text(
        "GEM\n  remote: https://rubygems.org/\n  specs:\n    rails (7.0.4)\n    rake (13.0.6)\n",
        encoding="utf-8",
    )
    locked = parse_gemfile_lock(lock)
    assert len(locked) == 2
    assert locked[0].name == "rails"


def test_dotnet_dart_swift_parsers(tmp_path: Path):
    # .NET csproj
    csproj = tmp_path / "app.csproj"
    csproj.write_text(
        '<Project Sdk="Microsoft.NET.Sdk">\n'
        "  <ItemGroup>\n"
        '    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />\n'
        "  </ItemGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    dotnet_deps = parse_csproj(csproj)
    assert len(dotnet_deps) == 1
    assert dotnet_deps[0].name == "Newtonsoft.Json"

    # Dart pubspec.yaml
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "name: flutter_demo\n"
        "dependencies:\n"
        "  flutter:\n"
        "    sdk: flutter\n"
        "  http: ^1.1.0\n"
        "dev_dependencies:\n"
        "  flutter_test:\n"
        "    sdk: flutter\n"
        "  lints: ^2.0.0\n",
        encoding="utf-8",
    )
    d_direct, d_dev = parse_pubspec_yaml(pubspec)
    assert len(d_direct) == 1
    assert d_direct[0].name == "http"
    assert len(d_dev) == 2
    assert any(d.name == "flutter_test" for d in d_dev)
    assert any(d.name == "lints" for d in d_dev)

    # Swift Package.resolved
    swift_resolved = tmp_path / "Package.resolved"
    swift_resolved.write_text(
        "{\n"
        '  "pins": [\n'
        "    {\n"
        '      "identity": "alamofire",\n'
        '      "state": {"version": "5.6.4"}\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    swift_deps = parse_swift_resolved(swift_resolved)
    assert len(swift_deps) == 1
    assert swift_deps[0].name == "alamofire"


def test_js_lockfiles_and_node_modules(tmp_path: Path):
    # package-lock.json v2/v3
    pkg_lock = tmp_path / "package-lock.json"
    pkg_lock.write_text(
        "{\n"
        '  "name": "app",\n'
        '  "packages": {\n'
        '    "": {},\n'
        '    "node_modules/lodash": {"version": "4.17.21"},\n'
        '    "node_modules/@types/node": {"version": "20.0.0"}\n'
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    locked_npm = parse_package_lock_json(pkg_lock)
    assert len(locked_npm) == 2

    # yarn.lock
    yarn_lock = tmp_path / "yarn.lock"
    yarn_lock.write_text(
        "# THIS IS AN AUTOGENERATED FILE\n"
        '"lodash@^4.17.21":\n'
        '  version "4.17.21"\n'
        "\n"
        '"@types/node@^20.0.0":\n'
        '  version "20.0.0"\n',
        encoding="utf-8",
    )
    locked_yarn = parse_yarn_lock(yarn_lock)
    assert len(locked_yarn) == 2
    assert locked_yarn[0].name == "lodash"
    assert locked_yarn[1].name == "@types/node"

    # pnpm-lock.yaml
    pnpm_lock = tmp_path / "pnpm-lock.yaml"
    pnpm_lock.write_text(
        'lockfileVersion: "6.0"\n'
        "packages:\n"
        "  /lodash@4.17.21:\n"
        "    resolution: {integrity: sha512-...}\n",
        encoding="utf-8",
    )
    locked_pnpm = parse_pnpm_lock(pnpm_lock)
    assert len(locked_pnpm) == 1

    # node_modules
    nm = tmp_path / "node_modules"
    (nm / "lodash").mkdir(parents=True)
    (nm / "@babel" / "core").mkdir(parents=True)
    installed = inspect_node_modules(tmp_path)
    assert len(installed) == 2
    assert any(i.name == "lodash" for i in installed)
    assert any(i.name == "@babel/core" for i in installed)


def test_python_lockfiles_and_venv(tmp_path: Path):
    # poetry.lock / uv.lock
    poetry_lock = tmp_path / "poetry.lock"
    poetry_lock.write_text(
        "[[package]]\n"
        'name = "requests"\n'
        'version = "2.31.0"\n'
        "\n"
        "[[package]]\n"
        'name = "urllib3"\n'
        'version = "2.0.4"\n',
        encoding="utf-8",
    )
    locked_poetry = parse_poetry_or_uv_lock(poetry_lock)
    assert len(locked_poetry) == 2
    assert locked_poetry[0].name == "requests"

    # Pipfile & Pipfile.lock
    pipfile = tmp_path / "Pipfile"
    pipfile.write_text(
        '[packages]\nrequests = "*"\n\n[dev-packages]\nblack = ">=23.0"\n',
        encoding="utf-8",
    )
    pf_direct, pf_dev = parse_pipfile(pipfile)
    assert len(pf_direct) == 1
    assert len(pf_dev) == 1

    pipfile_lock = tmp_path / "Pipfile.lock"
    pipfile_lock.write_text(
        "{\n"
        '  "default": {\n'
        '    "requests": {"version": "==2.31.0"}\n'
        "  },\n"
        '  "develop": {\n'
        '    "black": {"version": "==23.7.0"}\n'
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    locked_pipfile = parse_pipfile_lock(pipfile_lock)
    assert len(locked_pipfile) == 2

    # Virtual environment
    venv_dir = tmp_path / ".venv" / "lib" / "python3.11" / "site-packages"
    (venv_dir / "requests-2.31.0.dist-info").mkdir(parents=True)
    installed_venv = inspect_python_virtualenv(tmp_path)
    assert len(installed_venv) == 1
    assert installed_venv[0].name == "requests"


def test_cargo_and_go_lock(tmp_path: Path):
    # Cargo.lock
    cargo_lock = tmp_path / "Cargo.lock"
    cargo_lock.write_text(
        '[[package]]\nname = "tokio"\nversion = "1.32.0"\n',
        encoding="utf-8",
    )
    locked_cargo = parse_cargo_lock(cargo_lock)
    assert len(locked_cargo) == 1

    # go.sum
    go_sum = tmp_path / "go.sum"
    go_sum.write_text(
        "github.com/gin-gonic/gin v1.9.1 h1:xyz...\n"
        "github.com/gin-gonic/gin v1.9.1/go.mod h1:abc...\n",
        encoding="utf-8",
    )
    locked_go = parse_go_sum(go_sum)
    assert len(locked_go) == 1
    assert locked_go[0].name == "github.com/gin-gonic/gin"
