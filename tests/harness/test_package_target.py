"""Test execution target and child-process isolation coverage."""

from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

import diffable_rdf


def test_parent_and_child_import_the_same_verified_origin(package_under_test, python_runner) -> None:
    """Both process levels resolve the package selected for this run."""
    child = python_runner(
        "import diffable_rdf; print(diffable_rdf.__file__)",
        capture_output=True,
        text=True,
        check=True,
    )

    assert Path(diffable_rdf.__file__).resolve() == package_under_test.origin
    assert Path(child.stdout.strip()).resolve() == package_under_test.origin


def test_source_mode_uses_this_checkout(package_under_test) -> None:
    """Source mode identifies the current worktree rather than an installation."""
    if package_under_test.mode != "source":
        pytest.skip("this assertion applies only to source mode")

    expected = Path(__file__).resolve().parents[2] / "src" / "diffable_rdf" / "__init__.py"
    assert package_under_test.origin == expected.resolve()


def test_child_preserves_an_explicit_hash_seed(python_runner) -> None:
    """Hash-sensitive process tests use the selected interpreter seed."""
    outputs = {
        seed: python_runner(
            "print(hash('diffable-rdf selected hash seed'))",
            env={"PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for seed in ("937", "938", "939")
    }
    repeated = python_runner(
        "print(hash('diffable-rdf selected hash seed'))",
        env={"PYTHONHASHSEED": "937"},
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert outputs["937"] == repeated
    assert len(set(outputs.values())) == len(outputs)


def test_child_provenance_check_does_not_import_the_package_early(python_runner) -> None:
    """The runner can validate its target before code sets process limits."""
    result = python_runner(
        "import sys; print('diffable_rdf' in sys.modules)",
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_child_code_keeps_future_imports_and_assertions(python_runner) -> None:
    """The runner executes user code as a separate module with assertions active."""
    result = python_runner(
        (
            "from __future__ import annotations\n"
            "if not __debug__:\n"
            "    raise SystemExit('optimization is active')\n"
            "print('ok')"
        ),
        env={"PYTHONOPTIMIZE": "2"},
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "ok"


def test_child_ignores_caller_pythonpath_and_target_overrides(
    package_under_test,
    monkeypatch: pytest.MonkeyPatch,
    python_runner,
    tmp_path: Path,
) -> None:
    """Caller environment values cannot redirect the selected child package."""
    decoy = tmp_path / "decoy"
    package = decoy / "diffable_rdf"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("raise RuntimeError('decoy package loaded')\n", encoding="utf-8")
    monkeypatch.chdir(decoy)
    result = python_runner(
        (
            "import os, diffable_rdf\n"
            "print(os.getcwd())\n"
            "print(os.environ.get('PYTEST_ADDOPTS'))\n"
            "print(diffable_rdf.__file__)"
        ),
        env={
            "PYTHONPATH": str(decoy),
            "PYTEST_ADDOPTS": "--package-under-test=installed",
        },
        capture_output=True,
        text=True,
        check=True,
    )

    child_cwd, pytest_options, child_origin = result.stdout.splitlines()
    assert Path(child_cwd).resolve() == (tmp_path / "child").resolve()
    assert not Path(child_cwd).resolve().is_relative_to(decoy.resolve())
    assert pytest_options == "None"
    assert Path(child_origin).resolve() == package_under_test.origin


def test_installed_mode_rejects_the_source_backed_distribution(package_under_test, python_runner) -> None:
    """Installed mode fails closed when an import resolves to this source tree."""
    if package_under_test.mode != "source":
        pytest.skip("the source target is needed to exercise this rejection")

    root = Path(__file__).resolve().parents[2]
    script = textwrap.dedent(
        """
        import pytest
        import sys
        raise SystemExit(pytest.main([
            "--package-under-test=installed",
            "--collect-only",
            "-q",
            "-c",
            sys.argv[1],
            sys.argv[2],
        ]))
        """
    )
    result = python_runner(
        script,
        str(root / "pyproject.toml"),
        str(Path(__file__).resolve()),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "installed mode" in result.stderr


def test_installed_mode_requires_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Installed mode rejects an import with no distribution metadata."""
    import conftest
    import importlib.metadata

    def missing_distribution(_name: str):
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(conftest.importlib.metadata, "distribution", missing_distribution)
    with pytest.raises(pytest.UsageError, match="requires an installed"):
        conftest._installed_origin()


def test_installed_mode_requires_recorded_package_origin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Installed mode rejects a package origin absent from distribution records."""
    import conftest

    class Distribution:
        files = [Path("diffable_rdf/__init__.py")]

        def locate_file(self, _file: Path) -> Path:
            return tmp_path / "other" / "diffable_rdf" / "__init__.py"

        def read_text(self, _name: str) -> None:
            return None

    monkeypatch.setattr(conftest.importlib.metadata, "distribution", lambda _name: Distribution())
    with pytest.raises(pytest.UsageError, match="not owned"):
        conftest._installed_origin()


def test_installed_mode_rejects_compact_editable_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Installed mode rejects editable metadata regardless of JSON whitespace."""
    import conftest

    package_origin = Path(diffable_rdf.__file__).resolve()

    class Distribution:
        files = [Path("diffable_rdf/__init__.py")]

        def locate_file(self, _file: Path) -> Path:
            return package_origin

        def read_text(self, _name: str) -> str:
            return '{"dir_info":{"editable":true}}'

    monkeypatch.setattr(conftest.importlib.metadata, "distribution", lambda _name: Distribution())
    monkeypatch.setattr(conftest, "_SOURCE_ROOT", package_origin.parents[2] / "not-the-source-root")
    with pytest.raises(pytest.UsageError, match="wheel installation"):
        conftest._installed_origin()
