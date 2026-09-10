"""Requirement catalogs connect scoped contracts to real collected evidence."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


_ROOT = Path(__file__).resolve().parents[2]
_STANDARDS = _ROOT / "docs/standards"
_SELECTOR = "tests/contracts/test_example.py::test_value"


@pytest.fixture(scope="session")
def requirement_checker():
    spec = importlib.util.spec_from_file_location("_test_requirement_checker", _ROOT / "scripts/check_requirements.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def collected_evidence(requirement_checker, pytestconfig):
    """One lazy child collection per session, independent of function-scoped fixtures."""
    target = pytestconfig._diffable_rdf_package_target
    return requirement_checker.collect_evidence(target.mode, target.origin)


@pytest.fixture
def catalog_case(tmp_path: Path):
    """A complete tiny profile makes each schema mutation's purpose explicit."""
    reference_root = tmp_path / "standards"
    reference_root.mkdir()
    (reference_root / "example.txt").write_text("4.  Objects\n\nNames are strings.\n", encoding="utf-8")
    references = {
        "references": [
            {
                "id": "EXAMPLE",
                "media_type": "text/html",
                "path": "example.html",
                "anchors": [
                    {"id": "required", "section": "1 Required", "normative": True},
                    {"id": "overview", "section": "2 Overview", "normative": False},
                ],
            },
            {"id": "RFCEXAMPLE", "media_type": "text/plain", "path": "example.txt", "anchors": []},
        ]
    }
    collection = {
        "nodeids": [_SELECTOR + "[one]", _SELECTOR + "[two]", _SELECTOR + "_other"],
        "exports": ["example"],
        "aliases": {"ttl": "Turtle"},
        "owners": {"diffable_rdf.example:example": "src/diffable_rdf/example.py"},
    }
    catalog = {
        "schema_version": 1,
        "features": [
            {"id": "example", "kind": "callable", "description": "Example function", "export": "example"},
            {"id": "format.turtle", "kind": "format", "description": "Turtle", "aliases": ["ttl"], "backend": "Turtle"},
        ],
        "requirements": [
            {
                "id": "EXAMPLE-VALUE",
                "description": "Values retain identity.",
                "features": ["example", "format.turtle"],
                "category": "normative",
                "clauses": [{"reference": "EXAMPLE", "section": "1 Required", "anchor": "required", "normative": True}],
                "owners": [
                    {"role": "local", "target": "diffable_rdf.example:example", "path": "src/diffable_rdf/example.py"}
                ],
                "status": "supported",
                "reason": None,
                "evidence": {"positive": [_SELECTOR]},
                "not_applicable": {
                    "negative": "The value transformation has no rejection obligation.",
                    "boundary": "Only the stated value examples are claimed.",
                    "property": "No separate randomized property is claimed.",
                    "subprocess": "No process state is involved.",
                    "end-to-end": "This row isolates one value contract.",
                },
            }
        ],
    }
    return catalog, references, collection, reference_root


def test_complete_catalog_matches_collected_evidence_and_current_table(requirement_checker, collected_evidence) -> None:
    references = requirement_checker.checked_references()
    catalog = requirement_checker.read_catalog(_STANDARDS / "requirements.json")
    result = requirement_checker.validate_requirements(catalog, references, collected_evidence, _STANDARDS)

    assert result["supported"] > 0
    assert result["excluded"] > 0
    assert result["unique_matches"] <= result["collected"]
    assert result["evidence_links"] >= result["unique_matches"]
    assert len(collected_evidence["exports"]) == 6
    assert len(collected_evidence["aliases"]) == 15
    expected = requirement_checker.render_coverage(catalog, references, result)
    requirement_checker.check_coverage(_STANDARDS / "coverage.md", expected)


def test_catalog_counts_function_families_without_similarly_named_tests(requirement_checker, catalog_case) -> None:
    result = requirement_checker.validate_requirements(*catalog_case)

    assert result["unique_matches"] == 2
    assert result["evidence_links"] == 2
    assert result["matches"]["EXAMPLE-VALUE"][_SELECTOR] == [_SELECTOR + "[one]", _SELECTOR + "[two]"]


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        pytest.param(_SELECTOR, [_SELECTOR + "[one]", _SELECTOR + "[two]"], id="function-family"),
        pytest.param(_SELECTOR + "[one]", [_SELECTOR + "[one]"], id="exact-parameter"),
        pytest.param(_SELECTOR + "_other", [_SELECTOR + "_other"], id="unparametrized-function"),
    ],
)
def test_selectors_resolve_exact_functions_and_parameters(
    requirement_checker, catalog_case, selector, expected
) -> None:
    assert requirement_checker.match_selector(selector, catalog_case[2]["nodeids"]) == expected


@pytest.mark.parametrize(
    "selector",
    [
        pytest.param("tests/contracts/test_example.py", id="module-only"),
        pytest.param(_SELECTOR + "*", id="function-glob"),
        pytest.param("test_value", id="substring"),
        pytest.param("../" + _SELECTOR, id="parent-path"),
        pytest.param(_SELECTOR.replace("/", "\\"), id="platform-separator"),
        pytest.param(_SELECTOR + "[one", id="unclosed-parameter"),
        pytest.param(_SELECTOR + "[]", id="empty-parameter"),
        pytest.param(_SELECTOR + "[missing]", id="absent-parameter"),
        pytest.param(_SELECTOR + "_removed", id="absent-function"),
    ],
)
def test_selectors_reject_non_evidence(requirement_checker, catalog_case, selector) -> None:
    with pytest.raises(requirement_checker.RequirementValidationError, match="selector"):
        requirement_checker.match_selector(selector, catalog_case[2]["nodeids"])


def test_mixed_bare_and_parametrized_function_is_ambiguous(requirement_checker) -> None:
    with pytest.raises(requirement_checker.RequirementValidationError, match="ambiguous"):
        requirement_checker.match_selector(_SELECTOR, [_SELECTOR, _SELECTOR + "[one]"])


@pytest.mark.parametrize(
    ("location", "field", "value", "message"),
    [
        pytest.param("catalog", "schema_version", True, "schema_version", id="boolean-version"),
        pytest.param("catalog", "schema_version", 2, "schema_version", id="unknown-version"),
        pytest.param("catalog", "extra", True, "fields", id="unknown-catalog-field"),
        pytest.param("catalog", "features", [], "features", id="missing-features"),
        pytest.param("catalog", "requirements", [], "requirements", id="missing-requirements"),
        pytest.param("callable", "kind", "unknown", "kind", id="unknown-feature-kind"),
        pytest.param("callable", "kind", [], "kind", id="nonstring-feature-kind"),
        pytest.param("callable", "export", "renamed", "exports", id="stale-export"),
        pytest.param("callable", "id", "", "feature ID", id="empty-feature-id"),
        pytest.param("format", "aliases", ["removed"], "format mapping", id="stale-alias"),
        pytest.param("format", "aliases", ["ttl", "ttl"], "duplicate", id="duplicate-alias"),
        pytest.param("format", "backend", "TriG", "format mapping", id="incorrect-backend"),
        pytest.param("row", "id", "", "requirement ID", id="empty-requirement-id"),
        pytest.param("row", "id", "unstable name", "requirement ID", id="invalid-requirement-id"),
        pytest.param("row", "description", "", "text", id="empty-description"),
        pytest.param("row", "features", ["unknown"], "unknown feature", id="unknown-feature"),
        pytest.param("row", "category", "conformant", "category", id="unknown-category"),
        pytest.param("row", "category", {}, "category", id="nonstring-category"),
        pytest.param("row", "status", "partial", "status", id="unknown-status"),
        pytest.param("row", "status", [], "status", id="nonstring-status"),
        pytest.param("row", "reason", "Excluded", "supported requirement", id="contradictory-supported-reason"),
        pytest.param("row", "evidence", {}, "no evidence", id="absent-evidence"),
        pytest.param("row", "owners", [], "owners", id="absent-owner"),
        pytest.param("row", "clauses", [], "normative support", id="absent-normative-support"),
        pytest.param("row", "not_applicable", {}, "dimension", id="missing-dimension"),
        pytest.param("clause", "reference", "UNKNOWN", "unknown reference", id="unknown-specification"),
        pytest.param("clause", "anchor", "absent", "unverified clause", id="unknown-anchor"),
        pytest.param("clause", "section", "2 Wrong", "unverified clause", id="incorrect-section"),
        pytest.param("clause", "normative", False, "normative status", id="incorrect-normative-status"),
        pytest.param("clause", "normative", 1, "boolean", id="nonboolean-normative-status"),
        pytest.param("owner", "target", "diffable_rdf.example:removed", "missing implementation", id="removed-owner"),
        pytest.param("owner", "path", "src/diffable_rdf/other.py", "owner path", id="incorrect-owner-path"),
        pytest.param("owner", "role", "parser", "role", id="unknown-owner-role"),
        pytest.param("owner", "role", {}, "role", id="nonstring-owner-role"),
        pytest.param("evidence", "positive", [], "nonempty list", id="empty-selector-list"),
        pytest.param("evidence", "positive", [_SELECTOR, _SELECTOR], "duplicate", id="duplicate-selector"),
        pytest.param("evidence", "mutation", [_SELECTOR], "dimension", id="unknown-evidence-dimension"),
        pytest.param("evidence", "negative", [_SELECTOR], "contradictory", id="excluded-evidence-dimension"),
        pytest.param("applicability", "boundary", "", "applicability reason", id="empty-dimension-reason"),
    ],
)
def test_catalog_rejects_inconsistent_fields(
    requirement_checker,
    catalog_case,
    location,
    field,
    value,
    message,
) -> None:
    catalog, references, collection, root = catalog_case
    row = catalog["requirements"][0]
    objects = {
        "catalog": catalog,
        "callable": catalog["features"][0],
        "format": catalog["features"][1],
        "row": row,
        "clause": row["clauses"][0],
        "owner": row["owners"][0],
        "evidence": row["evidence"],
        "applicability": row["not_applicable"],
    }
    objects[location][field] = value

    with pytest.raises(requirement_checker.RequirementValidationError, match=message):
        requirement_checker.validate_requirements(catalog, references, collection, root)


@pytest.mark.parametrize("group", ["features", "requirements"])
def test_catalog_rejects_duplicate_identities(requirement_checker, catalog_case, group) -> None:
    catalog_case[0][group].append(copy.deepcopy(catalog_case[0][group][0]))

    with pytest.raises(requirement_checker.RequirementValidationError, match="duplicate.*ID"):
        requirement_checker.validate_requirements(*catalog_case)


@pytest.mark.parametrize("field", ["id", "description", "features", "owners", "status", "evidence"])
def test_catalog_rejects_missing_requirement_fields(requirement_checker, catalog_case, field) -> None:
    catalog_case[0]["requirements"][0].pop(field)

    with pytest.raises(requirement_checker.RequirementValidationError, match="fields"):
        requirement_checker.validate_requirements(*catalog_case)


def test_normative_requirement_cannot_rely_only_on_informative_context(requirement_checker, catalog_case) -> None:
    catalog_case[0]["requirements"][0]["clauses"] = [
        {"reference": "EXAMPLE", "section": "2 Overview", "anchor": "overview", "normative": False},
    ]

    with pytest.raises(requirement_checker.RequirementValidationError, match="normative support"):
        requirement_checker.validate_requirements(*catalog_case)


@pytest.mark.parametrize("section", ["4 Objects", "4 Missing", "40 Objects", "Objects"])
def test_rfc_section_must_match_a_complete_numbered_heading(requirement_checker, catalog_case, section) -> None:
    catalog_case[0]["requirements"][0]["clauses"] = [
        {"reference": "RFCEXAMPLE", "section": section, "anchor": None, "normative": True},
    ]

    if section == "4 Objects":
        assert requirement_checker.validate_requirements(*catalog_case)["supported"] == 1
    else:
        with pytest.raises(requirement_checker.RequirementValidationError, match="RFC section"):
            requirement_checker.validate_requirements(*catalog_case)


def test_out_of_profile_rows_require_reasons_and_no_evidence(requirement_checker, catalog_case) -> None:
    excluded = copy.deepcopy(catalog_case[0]["requirements"][0])
    excluded.update(
        id="EXAMPLE-EXCLUDED",
        status="out-of-profile",
        reason="No processor API is exposed.",
        evidence={},
        not_applicable={},
    )
    catalog_case[0]["requirements"].append(excluded)
    assert requirement_checker.validate_requirements(*catalog_case)["excluded"] == 1

    excluded["evidence"] = {"positive": [_SELECTOR]}
    with pytest.raises(requirement_checker.RequirementValidationError, match="excluded requirement has evidence"):
        requirement_checker.validate_requirements(*catalog_case)
    excluded["evidence"] = {}
    excluded["reason"] = ""
    with pytest.raises(requirement_checker.RequirementValidationError, match="exclusion reason"):
        requirement_checker.validate_requirements(*catalog_case)


def test_each_feature_needs_supported_evidence(requirement_checker, catalog_case) -> None:
    catalog_case[0]["requirements"][0]["features"] = ["example"]

    with pytest.raises(requirement_checker.RequirementValidationError, match="features lack supported evidence"):
        requirement_checker.validate_requirements(*catalog_case)


@pytest.mark.parametrize("change", ["added-export", "added-alias", "missing-owner", "duplicate-nodeid"])
def test_actual_collection_drift_invalidates_the_catalog(requirement_checker, catalog_case, change) -> None:
    collection = catalog_case[2]
    if change == "added-export":
        collection["exports"].append("new_function")
    elif change == "added-alias":
        collection["aliases"]["turtle"] = "Turtle"
    elif change == "missing-owner":
        collection["owners"].clear()
    else:
        collection["nodeids"].append(collection["nodeids"][0])

    with pytest.raises(requirement_checker.RequirementValidationError):
        requirement_checker.validate_requirements(*catalog_case)


@pytest.mark.parametrize("change", ["removed", "renamed"])
def test_removing_or_renaming_real_referenced_tests_breaks_the_gate(
    requirement_checker,
    collected_evidence,
    change,
) -> None:
    references = requirement_checker.checked_references()
    catalog = requirement_checker.read_catalog(_STANDARDS / "requirements.json")
    snapshot = copy.deepcopy(collected_evidence)
    selector = catalog["requirements"][0]["evidence"]["positive"][0]
    matched = set(requirement_checker.match_selector(selector, snapshot["nodeids"]))
    snapshot["nodeids"] = [node for node in snapshot["nodeids"] if node not in matched]
    if change == "renamed":
        snapshot["nodeids"].extend(node + "_renamed" for node in matched)

    with pytest.raises(requirement_checker.RequirementValidationError, match="collected no tests"):
        requirement_checker.validate_requirements(catalog, references, snapshot, _STANDARDS)


def test_table_rendering_is_deterministic_and_stale_output_is_rejected(
    requirement_checker, catalog_case, tmp_path
) -> None:
    catalog, references, _, _ = catalog_case
    result = requirement_checker.validate_requirements(*catalog_case)
    rendered = requirement_checker.render_coverage(catalog, references, result)
    assert requirement_checker.render_coverage(catalog, references, result) == rendered
    assert "2 distinct collected tests" in rendered
    assert "not executed or passing tests" in rendered

    table = tmp_path / "coverage.md"
    table.write_text(rendered, encoding="utf-8")
    requirement_checker.check_coverage(table, rendered)
    table.write_text(rendered + "extra\n", encoding="utf-8")
    with pytest.raises(requirement_checker.RequirementValidationError, match="stale coverage table"):
        requirement_checker.check_coverage(table, rendered)
    assert table.read_text(encoding="utf-8") == rendered + "extra\n"


@pytest.mark.parametrize("content", ['{"schema_version":1,"schema_version":2}', "{", "[]"])
def test_cli_reports_invalid_catalogs(
    requirement_checker, tmp_path, monkeypatch, capsys, content
) -> None:
    catalog = tmp_path / "requirements.json"
    catalog.write_text(content, encoding="utf-8")
    monkeypatch.setattr(requirement_checker, "collect_evidence", lambda mode: {})

    assert requirement_checker.main(["--catalog", str(catalog)]) == 1
    assert "requirements verification failed" in capsys.readouterr().out


def test_reference_integrity_is_checked_before_requirements(requirement_checker, tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(requirement_checker.RequirementValidationError, match="reference catalog"):
        requirement_checker.checked_references(manifest)


def test_collector_sanitizes_pytest_settings_and_verifies_origin(requirement_checker, tmp_path, monkeypatch) -> None:
    expected = tmp_path / "package/__init__.py"
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only --ignore=tests")
    monkeypatch.setenv("PYTEST_PLUGINS", "unavailable_plugin")
    monkeypatch.setenv("PYTHONPATH", "/unrelated/source")
    calls = []

    def collect(command, **options):
        calls.append((command, options))
        assert command[:2] == [sys.executable, "-I"]
        assert "PYTEST_ADDOPTS" not in options["env"]
        assert "PYTEST_PLUGINS" not in options["env"]
        assert options["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        assert not Path(options["cwd"]).is_relative_to(_ROOT)
        output = Path(command[command.index("--collect-output") + 1])
        output.write_text(json.dumps({"mode": "installed", "origin": str(expected)}), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(requirement_checker.subprocess, "run", collect)
    assert requirement_checker.collect_evidence("installed", expected)["origin"] == str(expected)
    assert len(calls) == 1
    with pytest.raises(requirement_checker.RequirementValidationError, match="origin differs"):
        requirement_checker.collect_evidence("installed", tmp_path / "other/__init__.py")


def test_collector_propagates_collection_failure(requirement_checker, monkeypatch) -> None:
    monkeypatch.setattr(
        requirement_checker.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "collection failed", "invalid package target"),
    )

    with pytest.raises(requirement_checker.RequirementValidationError, match="pytest collection failed"):
        requirement_checker.collect_evidence()
