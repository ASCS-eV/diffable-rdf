"""Select and verify the package target used by the test suite."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SOURCE_ROOT = _PROJECT_ROOT / "src"
_PACKAGE_INIT = _SOURCE_ROOT / "diffable_rdf" / "__init__.py"
_PACKAGE_NAME = "diffable-rdf"


@dataclass(frozen=True)
class PackageTarget:
    """The package implementation selected for this test session."""

    mode: str
    origin: Path


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the package target selector before test collection."""
    parser.addoption(
        "--package-under-test",
        action="store",
        choices=("source", "installed"),
        default="source",
        help="test the checkout source tree or an installed wheel (default: source)",
    )


def _package_origin() -> Path:
    """Return the import target without importing the package itself."""
    spec = importlib.util.find_spec("diffable_rdf")
    if spec is None or spec.origin is None:
        raise pytest.UsageError("diffable_rdf is not importable for the selected package target")
    return Path(spec.origin).resolve()


def _installed_origin() -> Path:
    """Verify that the import target belongs to a non-editable distribution."""
    try:
        distribution = importlib.metadata.distribution(_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError as error:
        raise pytest.UsageError("installed mode requires an installed diffable-rdf distribution") from error

    origin = _package_origin()
    package_file = "diffable_rdf/__init__.py"
    files = distribution.files
    record_file = next((file for file in files or () if file.as_posix() == package_file), None)
    if record_file is None:
        raise pytest.UsageError("installed mode requires distribution metadata for diffable_rdf/__init__.py")
    metadata_origin = Path(distribution.locate_file(record_file)).resolve()
    if origin != metadata_origin:
        raise pytest.UsageError(
            "installed mode imported diffable_rdf from a location not owned by its distribution metadata"
        )
    if origin.is_relative_to(_SOURCE_ROOT.resolve()):
        raise pytest.UsageError("installed mode cannot use the checkout source tree or an editable installation")
    direct_url = distribution.read_text("direct_url.json")
    if direct_url:
        try:
            editable = bool(json.loads(direct_url).get("dir_info", {}).get("editable"))
        except json.JSONDecodeError as error:
            raise pytest.UsageError("installed mode requires valid direct_url distribution metadata") from error
        if editable:
            raise pytest.UsageError("installed mode requires a wheel installation, not an editable installation")
    return origin


def pytest_configure(config: pytest.Config) -> None:
    """Choose the import target before pytest imports test modules."""
    imported = [name for name in sys.modules if name == "diffable_rdf" or name.startswith("diffable_rdf.")]
    if imported:
        raise pytest.UsageError("diffable_rdf was imported before package target selection: " + ", ".join(imported))

    mode = config.getoption("package_under_test")
    if mode == "source":
        source_root = str(_SOURCE_ROOT)
        if source_root not in sys.path:
            sys.path.insert(0, source_root)
        else:
            sys.path.remove(source_root)
            sys.path.insert(0, source_root)
        origin = _package_origin()
        expected = _PACKAGE_INIT.resolve()
        if origin != expected:
            raise pytest.UsageError(f"source mode imported {origin}, expected checkout source {expected}")
    else:
        origin = _installed_origin()

    config._diffable_rdf_package_target = PackageTarget(mode=mode, origin=origin)  # type: ignore[attr-defined]


def pytest_report_header(config: pytest.Config) -> str:
    """Display the selected package target in pytest's normal header."""
    target: PackageTarget = config._diffable_rdf_package_target  # type: ignore[attr-defined]
    return f"package under test: {target.mode} ({target.origin})"


@pytest.fixture
def package_under_test(pytestconfig: pytest.Config) -> PackageTarget:
    """Expose the verified parent-process package target to tests."""
    return pytestconfig._diffable_rdf_package_target  # type: ignore[attr-defined]


@pytest.fixture
def python_runner(package_under_test: PackageTarget, tmp_path: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Run child Python code from a neutral directory against the selected target."""
    child_directory = tmp_path / "child"
    child_directory.mkdir()
    expected_origin = str(package_under_test.origin)
    prelude = (
        "import importlib.util\n"
        "from pathlib import Path\n"
        "import sys\n"
        "_spec = importlib.util.find_spec('diffable_rdf')\n"
        "if _spec is None or _spec.origin is None:\n"
        "    raise SystemExit('diffable_rdf is not importable in child process')\n"
        f"_expected = Path({expected_origin!r}).resolve()\n"
        "_actual = Path(_spec.origin).resolve()\n"
        "if _actual != _expected:\n"
        "    raise SystemExit(f'diffable_rdf child origin {_actual} does not match selected target {_expected}')\n"
    )

    def run(
        code: str,
        *arguments: str,
        env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        child_env = os.environ.copy()
        if env is not None:
            child_env.update(env)
        for name in (
            "PYTHONBREAKPOINT",
            "PYTHONDEBUG",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONHOME",
            "PYTHONINSPECT",
            "PYTHONIOENCODING",
            "PYTHONOPTIMIZE",
            "PYTHONPATH",
            "PYTHONPYCACHEPREFIX",
            "PYTHONSAFEPATH",
            "PYTHONSTARTUP",
            "PYTHONUNBUFFERED",
            "PYTHONUSERBASE",
            "PYTHONUTF8",
            "PYTHONWARNINGS",
            "PYTEST_ADDOPTS",
        ):
            child_env.pop(name, None)
        if package_under_test.mode == "source":
            child_env["PYTHONPATH"] = str(_SOURCE_ROOT)
        child_code = prelude + "\nexec(compile(" + repr(code) + ", '<test child>', 'exec'))\n"
        command = [sys.executable, "-s", "-c", child_code, *arguments]
        return subprocess.run(command, cwd=child_directory, env=child_env, **kwargs)

    return run
