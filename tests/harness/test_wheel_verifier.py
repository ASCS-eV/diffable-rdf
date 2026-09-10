"""Boundary coverage for the publication wheel verifier input checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest


_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test_wheel.py"


@pytest.fixture(scope="module")
def wheel_verifier():
    """Load the standalone verifier without importing it as a package module."""
    spec = importlib.util.spec_from_file_location("wheel_verifier", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_wheel(
    path: Path,
    *,
    metadata: tuple[str, ...] = ("Name: diffable-rdf", "Version: 1.2.3"),
    files: tuple[str, ...] = ("diffable_rdf/__init__.py", "diffable_rdf/py.typed"),
    record: bool = True,
    extra_metadata: bool = False,
) -> Path:
    """Create a minimal archive for archive-boundary verification only."""
    with zipfile.ZipFile(path, "w") as archive:
        if metadata:
            archive.writestr("diffable_rdf-1.2.3.dist-info/METADATA", "\n".join(metadata) + "\n")
        if extra_metadata:
            archive.writestr("other-1.2.3.dist-info/METADATA", "Name: diffable-rdf\nVersion: 1.2.3\n")
        if record:
            archive.writestr("diffable_rdf-1.2.3.dist-info/RECORD", "")
        for file_name in files:
            archive.writestr(file_name, "")
    return path


@pytest.mark.parametrize(
    ("name", "build", "message"),
    [
        ("absent", lambda path: path, "does not exist"),
        ("wrong-extension", lambda path: _write_wheel(path.with_suffix(".zip")), "must end in .whl"),
        ("bad-zip", lambda path: (path.write_text("not a zip", encoding="utf-8"), path)[1], "not a valid zip"),
        ("absent-metadata", lambda path: _write_wheel(path, metadata=()), "exactly one"),
        ("ambiguous-metadata", lambda path: _write_wheel(path, extra_metadata=True), "exactly one"),
        ("missing-record", lambda path: _write_wheel(path, record=False), "must contain RECORD"),
        ("missing-name", lambda path: _write_wheel(path, metadata=("Version: 1.2.3",)), "metadata must identify"),
        (
            "missing-version",
            lambda path: _write_wheel(path, metadata=("Name: diffable-rdf",)),
            "metadata must identify",
        ),
        (
            "wrong-name",
            lambda path: _write_wheel(path, metadata=("Name: another-distribution", "Version: 1.2.3")),
            "metadata must identify",
        ),
        (
            "missing-module",
            lambda path: _write_wheel(path, files=("diffable_rdf/py.typed",)),
            "diffable_rdf/__init__.py",
        ),
        (
            "missing-marker",
            lambda path: _write_wheel(path, files=("diffable_rdf/__init__.py",)),
            "diffable_rdf/py.typed",
        ),
    ],
)
def test_inspect_wheel_rejects_invalid_archives(wheel_verifier, tmp_path: Path, name, build, message: str) -> None:
    """Invalid archive identities and package contents fail before any installation."""
    wheel = build(tmp_path / f"{name}.whl")
    with pytest.raises(wheel_verifier.WheelVerificationError, match=message):
        wheel_verifier.inspect_wheel(wheel)


def test_inspect_wheel_returns_the_archive_identity(wheel_verifier, tmp_path: Path) -> None:
    """A valid archive yields its declared distribution identity and digest."""
    wheel = _write_wheel(tmp_path / "valid.whl")
    contents = wheel_verifier.inspect_wheel(wheel)
    assert contents.name == "diffable-rdf"
    assert contents.version == "1.2.3"
    assert contents.digest == wheel_verifier._digest(wheel)


def test_cli_requires_one_explicit_wheel_path(
    wheel_verifier,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command line rejects ambiguous selection before any installation."""
    wheel = tmp_path / "candidate.whl"
    with pytest.raises(SystemExit) as error:
        wheel_verifier.main([str(wheel), str(wheel)])
    assert error.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_installed_suite_ignores_pytest_controls_and_retains_hash_seed(
    wheel_verifier,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Inherited pytest controls cannot replace execution of the installed suite."""
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    monkeypatch.setenv("PYTEST_PLUGINS", "unexpected_plugin")
    monkeypatch.setenv("PYTHONHASHSEED", "937")
    calls: list[tuple[tuple[str, ...], Path | None, dict[str, str] | None]] = []

    def record(command, *, cwd=None, env=None) -> None:
        calls.append((tuple(command), cwd, env))

    monkeypatch.setattr(wheel_verifier, "_run", record)
    python = tmp_path / "python"
    neutral_directory = tmp_path / "neutral"
    wheel_verifier.run_installed_suite(python, neutral_directory)

    command, cwd, environment = calls.pop()
    assert command[:5] == (str(python), "-I", "-m", "pytest", "-q")
    assert "--package-under-test=installed" in command
    assert cwd == neutral_directory
    assert environment is not None
    assert "PYTEST_ADDOPTS" not in environment
    assert "PYTEST_PLUGINS" not in environment
    assert environment["PYTHONHASHSEED"] == "937"


def test_run_propagates_a_child_command_failure(wheel_verifier, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed environment, installer, or test command is never converted to success."""
    monkeypatch.setattr(wheel_verifier.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=73))
    with pytest.raises(wheel_verifier.subprocess.CalledProcessError) as error:
        wheel_verifier._run(["failed-command"])
    assert error.value.returncode == 73


def test_verify_wheel_orders_install_provenance_suite_and_digest(
    wheel_verifier,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The successful sequence tests one artifact before its final digest is accepted."""
    wheel_path = tmp_path / "artifact.whl"
    wheel_path.write_bytes(b"artifact")
    contents = wheel_verifier.WheelContents("diffable-rdf", "1.2.3", "before")
    events: list[str] = []

    monkeypatch.setattr(wheel_verifier, "inspect_wheel", lambda path: contents)
    monkeypatch.setattr(wheel_verifier.shutil, "which", lambda name: "uv")
    monkeypatch.setattr(wheel_verifier, "_digest", lambda path: events.append("final-digest") or "before")

    def run(command, *, cwd=None, env=None) -> None:
        events.append("create-environment" if command[1] == "venv" else "install")

    monkeypatch.setattr(wheel_verifier, "_run", run)
    def provenance(python, wheel) -> str:
        events.append("provenance")
        return "/tmp/site-packages/diffable_rdf/__init__.py"

    monkeypatch.setattr(wheel_verifier, "_verify_installation", provenance)
    monkeypatch.setattr(wheel_verifier, "run_installed_suite", lambda python, cwd: events.append("suite"))
    wheel_verifier.verify_wheel(wheel_path)

    assert events == ["create-environment", "install", "provenance", "suite", "final-digest"]


def test_verify_wheel_rejects_bytes_changed_after_the_suite(
    wheel_verifier,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A final digest mismatch prevents an artifact different from the tested bytes."""
    wheel_path = tmp_path / "artifact.whl"
    wheel_path.write_bytes(b"artifact")
    contents = wheel_verifier.WheelContents("diffable-rdf", "1.2.3", "before")
    monkeypatch.setattr(wheel_verifier, "inspect_wheel", lambda path: contents)
    monkeypatch.setattr(wheel_verifier.shutil, "which", lambda name: "uv")
    monkeypatch.setattr(wheel_verifier, "_digest", lambda path: "after")
    monkeypatch.setattr(wheel_verifier, "_run", lambda command, **kwargs: None)
    monkeypatch.setattr(
        wheel_verifier,
        "_verify_installation",
        lambda python, wheel: "/tmp/site-packages/diffable_rdf/__init__.py",
    )
    monkeypatch.setattr(wheel_verifier, "run_installed_suite", lambda python, cwd: None)

    with pytest.raises(wheel_verifier.WheelVerificationError, match="wheel changed while it was tested"):
        wheel_verifier.verify_wheel(wheel_path)


def test_verify_wheel_requires_uv_before_creating_an_environment(
    wheel_verifier,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The verifier fails clearly when it cannot create the required isolated environment."""
    wheel_path = tmp_path / "artifact.whl"
    wheel_path.write_bytes(b"artifact")
    contents = wheel_verifier.WheelContents("diffable-rdf", "1.2.3", "x")
    monkeypatch.setattr(wheel_verifier, "inspect_wheel", lambda path: contents)
    monkeypatch.setattr(wheel_verifier.shutil, "which", lambda name: None)
    with pytest.raises(wheel_verifier.WheelVerificationError, match="uv is required"):
        wheel_verifier.verify_wheel(wheel_path)
