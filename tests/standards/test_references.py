"""Reference catalog integrity across identity, content and path boundaries."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


_ROOT = Path(__file__).resolve().parents[2]
_CATALOG = _ROOT / "docs" / "standards" / "manifest.json"


@pytest.fixture(scope="module")
def reference_checker():
    """Load the dependency-free reference checker by its explicit source path."""
    spec = importlib.util.spec_from_file_location("standards_checker", _ROOT / "scripts" / "check_standards.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def catalog_copy(tmp_path: Path):
    """Provide isolated catalog data and original asset bytes for boundary tests."""
    root = tmp_path / "standards"
    shutil.copytree(_CATALOG.parent, root)
    path = root / "manifest.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, catalog: dict) -> None:
    path.write_text(json.dumps(catalog), encoding="utf-8")


def test_original_catalog_verifies_without_modifying_assets(reference_checker) -> None:
    """The committed inventory verifies with every byte and modification time intact."""
    files = [_CATALOG, *(_CATALOG.parent / "references").iterdir()]
    before = {path: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) for path in files}
    catalog = reference_checker.check_catalog(_CATALOG)
    assert len(catalog["references"]) == 14
    assert len(catalog["licenses"]) == 7
    assert before == {path: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) for path in files}


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda c: c.update(schema_version=2), "schema_version"),
        (lambda c: c.update(schema_version=True), "schema_version"),
        (lambda c: c.update(unknown=True), "catalog fields"),
        (lambda c: c.update(references={}), "references must be"),
        (lambda c: c["references"].pop(), "reference inventory"),
        (lambda c: c["references"][0].update(id="UNKNOWN"), "reference inventory"),
        (lambda c: c["references"].append(copy.deepcopy(c["references"][0])), "duplicate asset ID"),
        (lambda c: c["references"][0].update(sha256="0" * 64), "digest mismatch"),
        (lambda c: c["references"][0].update(sha256="not-a-digest"), "sha256"),
        (lambda c: c["references"][0].update(title="An unrelated title"), "title absent"),
        (lambda c: c["references"][0].update(edition="31 December 2099"), "edition absent"),
        (lambda c: c["references"][0].update(status="Draft Only"), "status absent"),
        (lambda c: c["references"][0].pop("notice"), "asset fields"),
        (lambda c: c["references"][0].update(notice=""), "nonempty string"),
        (lambda c: c["references"][0].update(retrieved_at="2026-13-01"), "valid date"),
        (lambda c: c["references"][0].update(publication_date="yesterday"), "ISO date"),
        (lambda c: c["references"][0].update(source_url="file:///tmp/spec"), "HTTPS URL"),
        (lambda c: c["references"][0].update(source_url="https://["), "HTTPS URL"),
        (lambda c: c["references"][0].update(media_type="application/octet-stream"), "media_type"),
        (lambda c: c["references"][0].update(license_ids=["UNKNOWN"]), "unknown license ID"),
        (lambda c: c["references"][0].update(license_ids=[]), "must not be empty"),
        (lambda c: c["references"][0]["anchors"][0].update(id="absent-clause"), "missing HTML anchor"),
        (lambda c: c["references"][0]["anchors"][0].update(normative="yes"), "must be a boolean"),
        (lambda c: c["licenses"][0].update(sha256="0" * 64), "digest mismatch"),
    ],
)
def test_catalog_rejects_invalid_metadata(reference_checker, catalog_copy, mutation, message: str) -> None:
    """Identity, schema, provenance and clause failures reject the whole catalog."""
    path, catalog = catalog_copy
    mutation(catalog)
    _save(path, catalog)
    with pytest.raises(reference_checker.ReferenceValidationError, match=message):
        reference_checker.check_catalog(path)


@pytest.mark.parametrize("field", ["source_url", "resolved_url"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("https://a b/", id="hostname-space"),
        pytest.param("https://:80/a", id="missing-hostname"),
        pytest.param("https://www.w3.org:bad/a", id="nonnumeric-port"),
        pytest.param("https://www.w3.org:65536/a", id="port-out-of-range"),
        pytest.param("https://www.w3.org:-1/a", id="negative-port"),
        pytest.param("https://www.w3.org/null\x00", id="nul"),
        pytest.param("https://www.w3.org/tab\t", id="tab"),
        pytest.param("https://www.w3.org/line\n", id="line-feed"),
        pytest.param("https://www.w3.org/line\r", id="carriage-return"),
        pytest.param("https://www.w3.org/delete\x7f", id="delete-control"),
        pytest.param("https://www.w3.org/control\x80", id="extended-control"),
        pytest.param("https://www.w3.org/space\u00a0", id="unicode-space"),
    ],
)
def test_catalog_rejects_malformed_urls(reference_checker, catalog_copy, field: str, value: str) -> None:
    """Both provenance URLs require unambiguous HTTPS hostnames, ports and characters."""
    path, catalog = catalog_copy
    catalog["references"][0][field] = value
    _save(path, catalog)
    with pytest.raises(reference_checker.ReferenceValidationError, match=f"{field} must be an HTTPS URL"):
        reference_checker.check_catalog(path)


@pytest.mark.parametrize("asset_group", ["references", "licenses"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_catalog_rejects_damaged_assets(reference_checker, catalog_copy, asset_group: str, damage: str) -> None:
    """Original standards and license files have the same existence and digest requirements."""
    path, catalog = catalog_copy
    asset = path.parent / catalog[asset_group][0]["path"]
    if damage == "missing":
        asset.unlink()
    else:
        asset.write_bytes(asset.read_bytes() + b"\nchanged\n")
    with pytest.raises(reference_checker.ReferenceValidationError, match="missing asset|digest mismatch"):
        reference_checker.check_catalog(path)


@pytest.mark.parametrize("value", ["/tmp/spec.html", "../spec.html", "references/../spec.html", "references//spec.html",
                                  "references/./spec.html", "C:/spec.html", "references\\spec.html", "other/spec.html"])
def test_catalog_rejects_unsafe_paths(reference_checker, catalog_copy, value: str) -> None:
    """Asset paths are portable, unambiguous and contained in the reference directory."""
    path, catalog = catalog_copy
    catalog["references"][0]["path"] = value
    _save(path, catalog)
    with pytest.raises(reference_checker.ReferenceValidationError, match="unsafe asset path"):
        reference_checker.check_catalog(path)


def test_catalog_rejects_duplicate_paths(reference_checker, catalog_copy) -> None:
    """Different IDs cannot claim the same original asset."""
    path, catalog = catalog_copy
    duplicate = copy.deepcopy(catalog["references"][0])
    duplicate["id"] = "ADDITIONAL"
    catalog["references"].append(duplicate)
    _save(path, catalog)
    with pytest.raises(reference_checker.ReferenceValidationError, match="duplicate asset path"):
        reference_checker.check_catalog(path)


def test_catalog_rejects_symlink_escape(reference_checker, catalog_copy, tmp_path: Path) -> None:
    """A path inside the catalog must not resolve to a file outside it."""
    path, catalog = catalog_copy
    asset = path.parent / catalog["references"][0]["path"]
    outside = tmp_path / "external.html"
    asset.rename(outside)
    try:
        asset.symlink_to(outside)
    except OSError:
        pytest.skip("symbolic links are not available to this test process")
    with pytest.raises(reference_checker.ReferenceValidationError, match="escapes references"):
        reference_checker.check_catalog(path)


def test_catalog_rejects_duplicate_json_keys(reference_checker, tmp_path: Path) -> None:
    """Ambiguous JSON object keys fail before any asset lookup."""
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
    with pytest.raises(reference_checker.ReferenceValidationError, match="duplicate JSON key"):
        reference_checker.check_catalog(path)


def test_html_anchor_extraction_supports_ids_and_named_anchors(reference_checker) -> None:
    """Fragment lookup supports HTML identifiers and legacy named anchors."""
    assert reference_checker.html_anchors('<section id="terms"><a name="syntax"></a></section>') == {"terms", "syntax"}


def test_checker_cli_runs_without_site_packages(tmp_path: Path) -> None:
    """The standalone checker runs from a neutral directory using only the standard library."""
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(_ROOT / "scripts" / "check_standards.py")],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "verified 14 standards and 7 license/notice assets offline" in result.stdout


def test_checker_cli_reports_invalid_catalog(reference_checker, tmp_path: Path, capsys) -> None:
    """Invalid input produces a failing exit status with a readable diagnostic."""
    assert reference_checker.main(["--manifest", str(tmp_path / "missing.json")]) == 1
    assert "standards verification failed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("references/null\x00.html", id="nul"),
        pytest.param("references/line\n.html", id="line-feed"),
        pytest.param("references/control\x80.html", id="extended-control"),
        pytest.param('references/quote".html', id="quote"),
        pytest.param("references/angle<.html", id="angle-bracket"),
        pytest.param("references/pipe|.html", id="pipe"),
        pytest.param("references/glob*.html", id="asterisk"),
        pytest.param("references/query?.html", id="question-mark"),
    ],
)
def test_checker_cli_rejects_invalid_path_characters(catalog_copy, value: str, tmp_path: Path) -> None:
    """Invalid portable path characters produce a clean failing command-line result."""
    path, catalog = catalog_copy
    catalog["references"][0]["path"] = value
    _save(path, catalog)
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(_ROOT / "scripts" / "check_standards.py"), "--manifest", str(path)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "standards verification failed: unsafe asset path" in result.stdout
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("operation", ["resolve", "is_file", "read_bytes"])
@pytest.mark.parametrize("error_type", [OSError, ValueError])
def test_checker_cli_reports_asset_access_failures(
    reference_checker, catalog_copy, monkeypatch: pytest.MonkeyPatch, capsys, operation: str, error_type,
) -> None:
    """Filesystem failures are reported through the same command-line error contract."""
    path, _ = catalog_copy

    def fail(*args, **kwargs):
        raise error_type("asset access failed")

    monkeypatch.setattr(Path, operation, fail)
    assert reference_checker.main(["--manifest", str(path)]) == 1
    assert "standards verification failed: cannot" in capsys.readouterr().out


def test_checker_cli_reports_resolution_loops(reference_checker, catalog_copy, monkeypatch: pytest.MonkeyPatch, capsys):
    """A filesystem resolution loop has the same failure status as other inaccessible paths."""
    path, _ = catalog_copy

    def fail(*args, **kwargs):
        raise RuntimeError("symbolic link loop")

    monkeypatch.setattr(Path, "resolve", fail)
    assert reference_checker.main(["--manifest", str(path)]) == 1
    assert "standards verification failed: cannot resolve asset path" in capsys.readouterr().out
