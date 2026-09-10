#!/usr/bin/env python3
"""Install one wheel in a fresh environment and test that installed artifact."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence
import zipfile


_DISTRIBUTION_NAME = "diffable-rdf"
_PACKAGE_NAME = "diffable_rdf"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class WheelContents:
    """The distribution identity and required files declared by a wheel."""

    name: str
    version: str
    digest: str


class WheelVerificationError(RuntimeError):
    """A wheel cannot be verified as the artifact selected for publication."""


def _digest(path: Path) -> str:
    """Return the SHA-256 digest for one file."""
    hasher = hashlib.sha256()
    with path.open("rb") as wheel_file:
        for chunk in iter(lambda: wheel_file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def inspect_wheel(path: Path) -> WheelContents:
    """Read the identity and required package files from one wheel archive."""
    if not path.is_file():
        raise WheelVerificationError(f"wheel does not exist: {path}")
    if path.suffix != ".whl":
        raise WheelVerificationError(f"wheel path must end in .whl: {path}")

    try:
        with zipfile.ZipFile(path) as archive:
            archive_names = archive.namelist()
            names = set(archive_names)
            metadata_files = [name for name in archive_names if name.endswith(".dist-info/METADATA")]
            if len(metadata_files) != 1:
                raise WheelVerificationError("wheel must contain exactly one .dist-info/METADATA file")
            metadata_file = metadata_files[0]
            record_file = metadata_file.removesuffix("METADATA") + "RECORD"
            if record_file not in names:
                raise WheelVerificationError("wheel must contain RECORD metadata for its package files")
            metadata = BytesParser(policy=default).parsebytes(archive.read(metadata_file))
    except zipfile.BadZipFile as error:
        raise WheelVerificationError(f"wheel is not a valid zip archive: {path}") from error

    name = metadata.get("Name")
    version = metadata.get("Version")
    if name != _DISTRIBUTION_NAME or not version:
        raise WheelVerificationError(
            f"wheel metadata must identify {_DISTRIBUTION_NAME!r} with a version, got name={name!r} version={version!r}"
        )
    required = {f"{_PACKAGE_NAME}/__init__.py", f"{_PACKAGE_NAME}/py.typed"}
    missing = sorted(required - names)
    if missing:
        raise WheelVerificationError("wheel is missing required package files: " + ", ".join(missing))
    return WheelContents(name=name, version=version, digest=_digest(path))


def _environment_python(environment: Path) -> Path:
    """Return the Python executable created by uv on this platform."""
    relative_path = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return environment / relative_path


def _run(command: Sequence[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """Run one command and preserve its non-zero result for the caller."""
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command)


def _verify_installation(python: Path, wheel: WheelContents) -> str:
    """Confirm that imports and metadata resolve to the freshly installed wheel."""
    program = (
        "import importlib.metadata\n"
        "import importlib.resources\n"
        "from pathlib import Path\n"
        "import diffable_rdf\n"
        f"distribution = importlib.metadata.distribution({wheel.name!r})\n"
        f"expected_version = {wheel.version!r}\n"
        f"expected_name = {wheel.name!r}\n"
        "if distribution.metadata['Name'] != expected_name:\n"
        "    raise SystemExit(\n"
        "        'installed distribution name ' + repr(distribution.metadata['Name'])\n"
        "        + ' does not match wheel ' + repr(expected_name)\n"
        "    )\n"
        "if distribution.version != expected_version:\n"
        "    raise SystemExit(\n"
        "        f'installed version {distribution.version!r} does not match wheel {expected_version!r}'\n"
        "    )\n"
        "if diffable_rdf.__version__ != expected_version:\n"
        "    raise SystemExit(\n"
        "        f'public version {diffable_rdf.__version__!r} does not match wheel {expected_version!r}'\n"
        "    )\n"
        "origin = Path(diffable_rdf.__file__).resolve()\n"
        "recorded = next(\n"
        "    (file for file in distribution.files or () if file.as_posix() == 'diffable_rdf/__init__.py'),\n"
        "    None,\n"
        ")\n"
        "if recorded is None or origin != Path(distribution.locate_file(recorded)).resolve():\n"
        "    raise SystemExit('installed package origin is not owned by distribution metadata')\n"
        "marker = importlib.resources.files('diffable_rdf') / 'py.typed'\n"
        "if not marker.is_file():\n"
        "    raise SystemExit('installed wheel is missing diffable_rdf/py.typed')\n"
        "print(origin)\n"
    )
    result = subprocess.run([str(python), "-I", "-c", program], check=False, capture_output=True, text=True)
    if result.returncode:
        raise WheelVerificationError(result.stderr.strip() or "installed wheel provenance verification failed")
    return result.stdout.strip()


def _pytest_environment() -> dict[str, str]:
    """Remove pytest controls while preserving ordinary child-process settings."""
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    return environment


def run_installed_suite(python: Path, neutral_directory: Path) -> None:
    """Run the repository suite through the installed target from a neutral directory."""
    _run(
        [
            str(python),
            "-I",
            "-m",
            "pytest",
            "-q",
            "--package-under-test=installed",
            "-c",
            str(_PROJECT_ROOT / "pyproject.toml"),
            str(_PROJECT_ROOT / "tests"),
        ],
        cwd=neutral_directory,
        env=_pytest_environment(),
    )


def verify_wheel(path: Path) -> None:
    """Install and test one immutable wheel from a neutral temporary directory."""
    wheel_path = path.resolve()
    wheel = inspect_wheel(wheel_path)
    uv = shutil.which("uv")
    if uv is None:
        raise WheelVerificationError("uv is required to create the isolated wheel test environment")

    with tempfile.TemporaryDirectory(prefix="diffable-rdf-wheel-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        environment = temporary_root / "environment"
        neutral_directory = temporary_root / "work"
        neutral_directory.mkdir()
        _run([uv, "venv", "--python", sys.executable, str(environment)])
        python = _environment_python(environment)
        _run([uv, "pip", "install", "--python", str(python), str(wheel_path), "pytest>=8.0"])
        origin = _verify_installation(python, wheel)
        if Path(origin).is_relative_to(_PROJECT_ROOT.resolve()):
            raise WheelVerificationError(f"installed package origin points into the checkout: {origin}")
        print(f"wheel sha256: {wheel.digest}")
        print(f"installed package origin: {origin}")
        run_installed_suite(python, neutral_directory)

    final_digest = _digest(wheel_path)
    if final_digest != wheel.digest:
        raise WheelVerificationError(
            f"wheel changed while it was tested: expected sha256 {wheel.digest}, got {final_digest}"
        )
    print(f"verified upload wheel sha256: {final_digest}")


def main(arguments: Sequence[str] | None = None) -> int:
    """Parse one explicit wheel path and return a command-line status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path, help="the one wheel file to install and test")
    parsed = parser.parse_args(arguments)
    try:
        verify_wheel(parsed.wheel)
    except WheelVerificationError as error:
        print(f"wheel verification failed: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"wheel verification command failed with exit code {error.returncode}: {error.cmd}", file=sys.stderr)
        return error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
