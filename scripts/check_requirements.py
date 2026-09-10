#!/usr/bin/env python3
"""Check scoped requirements against pinned clauses and collected pytest evidence."""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Sequence


_ROOT = Path(__file__).resolve().parents[1]
_CATALOG = _ROOT / "docs/standards/requirements.json"
_REFERENCES = _ROOT / "docs/standards/manifest.json"
_COVERAGE = _ROOT / "docs/standards/coverage.md"
DIMENSIONS = ("positive", "negative", "boundary", "property", "subprocess", "end-to-end")


class RequirementValidationError(ValueError):
    """A requirement, implementation target or evidence selector is inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RequirementValidationError(message)


def _fields(value: Any, expected: set[str], label: str) -> None:
    _require(isinstance(value, dict) and set(value) == expected, f"{label}: fields differ from schema")


def _text(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()) and "\n" not in value, f"{label}: expected nonempty text")
    return value


def _enum(value: Any, choices: set[str], label: str) -> str:
    _text(value, label)
    _require(value in choices, f"unknown {label}: {value}")
    return value


def _strings(value: Any, label: str, *, empty: bool = False) -> list[str]:
    _require(isinstance(value, list) and (empty or bool(value)), f"{label}: expected nonempty list")
    for item in value:
        _text(item, label)
    _require(len(value) == len(set(value)), f"{label}: duplicate values")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_catalog(path: Path) -> dict[str, Any]:
    """Read JSON without accepting duplicate keys or invalid text."""
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RequirementValidationError(f"cannot read requirement catalog: {error}") from error


def checked_references(path: Path = _REFERENCES) -> dict[str, Any]:
    """Verify the original document catalog before using its clause inventory."""
    spec = importlib.util.spec_from_file_location("_requirement_references", _ROOT / "scripts/check_standards.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.check_catalog(path)
    except module.ReferenceValidationError as error:
        raise RequirementValidationError(f"reference catalog: {error}") from error


class _Collection:
    """Record evidence after pytest selects its package target and collects tests."""

    def __init__(self, output: Path) -> None:
        self.output = output

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        if exitstatus != 0:
            return
        import diffable_rdf
        from diffable_rdf.canonicalize import _FORMAT_MAP

        target = session.config._diffable_rdf_package_target
        package_root = target.origin.parent
        owners = {}
        for name, module in tuple(sys.modules.items()):
            if name != "diffable_rdf" and not name.startswith("diffable_rdf."):
                continue
            for symbol, value in vars(module).items():
                if not inspect.isfunction(value) or not value.__module__.startswith("diffable_rdf."):
                    continue
                filename = inspect.getsourcefile(value)
                if filename is not None and Path(filename).resolve().is_relative_to(package_root):
                    owners[f"{name}:{symbol}"] = (
                        "src/diffable_rdf/" + Path(filename).resolve().relative_to(package_root).as_posix()
                    )
        exports = [name for name in diffable_rdf.__all__ if name != "__version__"]
        _require(all(callable(getattr(diffable_rdf, name)) for name in exports), "public exports must be callable")
        snapshot = {
            "nodeids": sorted(item.nodeid for item in session.items),
            "exports": sorted(exports),
            "aliases": {name: str(value) for name, value in sorted(_FORMAT_MAP.items())},
            "owners": owners,
            "mode": target.mode,
            "origin": str(target.origin),
        }
        self.output.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")


def collect_evidence(mode: str = "source", expected_origin: Path | None = None) -> dict[str, Any]:
    """Collect once in a neutral isolated interpreter; no test body is executed."""
    _require(mode in {"source", "installed"}, f"unknown package mode: {mode}")
    environment = os.environ.copy()
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "COVERAGE_PROCESS_START"):
        environment.pop(name, None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    with tempfile.TemporaryDirectory(prefix="diffable-rdf-evidence-") as directory:
        output = Path(directory) / "collection.json"
        command = [
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            "--collect-output",
            str(output),
            "--package-under-test",
            mode,
        ]
        try:
            result = subprocess.run(
                command,
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RequirementValidationError(f"pytest collection could not finish: {error}") from error
        _require(result.returncode == 0, f"pytest collection failed:\n{result.stdout}\n{result.stderr}")
        snapshot = read_catalog(output)
    _require(snapshot["mode"] == mode, "collection package mode differs from the selected target")
    if expected_origin is not None:
        _require(Path(snapshot["origin"]).resolve() == expected_origin.resolve(), "collection package origin differs")
    return snapshot


def match_selector(selector: str, nodeids: list[str]) -> list[str]:
    """Resolve an exact nodeid or a single function's parametrized family."""
    _text(selector, "selector")
    function, separator, parameters = selector.partition("[")
    _require(
        re.fullmatch(r"tests/(?:[A-Za-z0-9_]+/)*test_[A-Za-z0-9_]+\.py::(?:Test\w+::)?test_\w+", function) is not None
        and (not separator or (parameters.endswith("]") and bool(parameters[:-1]))),
        f"invalid function selector: {selector}",
    )
    if separator:
        matches = [node for node in nodeids if node == selector]
    else:
        matches = [node for node in nodeids if node == selector or node.startswith(selector + "[")]
        _require(not (selector in matches and len(matches) > 1), f"ambiguous function selector: {selector}")
    _require(bool(matches), f"selector collected no tests: {selector}")
    return matches


def _reference(clause: Any, references: dict[str, Any], reference_root: Path) -> None:
    _fields(clause, {"reference", "section", "anchor", "normative"}, "clause")
    identity = _text(clause["reference"], "reference ID")
    _require(identity in references, f"unknown reference ID: {identity}")
    reference = references[identity]
    section = _text(clause["section"], "section")
    _require(type(clause["normative"]) is bool, "clause normative must be a boolean")
    if reference["media_type"] == "text/html":
        anchor = _text(clause["anchor"], "anchor")
        expected = {"id": anchor, "section": section, "normative": clause["normative"]}
        _require(expected in reference["anchors"], f"unverified clause or normative status: {identity}#{anchor}")
    else:
        _require(
            clause["anchor"] is None and clause["normative"], "RFC clauses require a numbered normative text section"
        )
        number, _, title = section.partition(" ")
        _require(re.fullmatch(r"\d+(?:\.\d+)*", number) is not None and bool(title), "invalid RFC section")
        text = (reference_root / reference["path"]).read_text(encoding="utf-8")
        pattern = rf"^{re.escape(number)}\. +{re.escape(title)}[ \t]*$"
        _require(re.search(pattern, text, re.MULTILINE) is not None, f"missing RFC section: {identity} {section}")


def validate_requirements(
    catalog: Any,
    references: dict[str, Any],
    collection: dict[str, Any],
    reference_root: Path,
) -> dict[str, Any]:
    """Validate declarative requirements against verified references and actual collection."""
    _fields(catalog, {"schema_version", "features", "requirements"}, "requirement catalog")
    _require(type(catalog["schema_version"]) is int and catalog["schema_version"] == 1, "unsupported schema_version")
    nodeids = _strings(collection["nodeids"], "collected nodeids")
    exports = _strings(collection["exports"], "collected exports")
    features = catalog["features"]
    _require(isinstance(features, list) and bool(features), "features must be a nonempty list")
    feature_ids: set[str] = set()
    actual_exports: list[str] = []
    actual_aliases: dict[str, str] = {}
    for feature in features:
        _require(isinstance(feature, dict), "feature must be an object")
        kind = _enum(feature.get("kind"), {"callable", "format"}, "feature kind")
        fields = {"id", "kind", "description"} | ({"export"} if kind == "callable" else {"aliases", "backend"})
        _fields(feature, fields, "feature")
        identity = _text(feature["id"], "feature ID")
        _require(re.fullmatch(r"[a-z][a-z0-9_.-]*", identity) is not None, f"invalid feature ID: {identity}")
        _require(identity not in feature_ids, f"duplicate feature ID: {identity}")
        feature_ids.add(identity)
        _text(feature["description"], identity)
        if kind == "callable":
            actual_exports.append(_text(feature["export"], "export"))
        else:
            backend = _text(feature["backend"], "backend")
            for alias in _strings(feature["aliases"], "aliases"):
                _require(alias not in actual_aliases, f"duplicate format alias: {alias}")
                actual_aliases[alias] = backend
    _require(sorted(actual_exports) == sorted(exports), "feature inventory differs from collected public exports")
    _require(actual_aliases == collection["aliases"], "feature inventory differs from collected format mapping")

    reference_map = {item["id"]: item for item in references["references"]}
    rows = catalog["requirements"]
    _require(isinstance(rows, list) and bool(rows), "requirements must be a nonempty list")
    identities: set[str] = set()
    supported_features: set[str] = set()
    matched: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        _fields(
            row,
            {
                "id",
                "description",
                "features",
                "category",
                "clauses",
                "owners",
                "status",
                "reason",
                "evidence",
                "not_applicable",
            },
            "requirement",
        )
        identity = _text(row["id"], "requirement ID")
        _require(
            re.fullmatch(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+", identity) is not None, f"invalid requirement ID: {identity}"
        )
        _require(identity not in identities, f"duplicate requirement ID: {identity}")
        identities.add(identity)
        _text(row["description"], identity)
        row_features = set(_strings(row["features"], identity + " features"))
        _require(row_features <= feature_ids, f"{identity}: unknown feature ID: {sorted(row_features - feature_ids)}")
        _enum(row["category"], {"normative", "policy", "extension"}, identity + " category")
        _require(isinstance(row["clauses"], list), f"{identity}: clauses must be a list")
        for clause in row["clauses"]:
            _reference(clause, reference_map, reference_root)
        if row["category"] == "normative":
            _require(any(clause["normative"] for clause in row["clauses"]), f"{identity}: normative support is absent")
        _require(
            isinstance(row["owners"], list) and bool(row["owners"]), f"{identity}: implementation owners are absent"
        )
        seen_owners: set[str] = set()
        for owner in row["owners"]:
            _fields(owner, {"role", "target", "path"}, identity + " owner")
            _enum(owner["role"], {"local", "dependency", "boundary"}, identity + " owner role")
            target = _text(owner["target"], "owner target")
            _require(target not in seen_owners, f"{identity}: duplicate owner target")
            seen_owners.add(target)
            _require(target in collection["owners"], f"{identity}: missing implementation owner: {target}")
            _require(collection["owners"][target] == owner["path"], f"{identity}: incorrect implementation owner path")
        _enum(row["status"], {"supported", "out-of-profile"}, identity + " status")
        _require(isinstance(row["evidence"], dict), f"{identity}: evidence must be an object")
        _require(isinstance(row["not_applicable"], dict), f"{identity}: not_applicable must be an object")
        matched[identity] = {}
        if row["status"] == "out-of-profile":
            _text(row["reason"], identity + " exclusion reason")
            _require(
                not row["evidence"] and not row["not_applicable"], f"{identity}: excluded requirement has evidence"
            )
            continue
        _require(row["reason"] is None, f"{identity}: supported requirement has an exclusion reason")
        _require(bool(row["evidence"]), f"{identity}: supported requirement has no evidence")
        covered_dimensions = set(row["evidence"])
        excluded_dimensions = set(row["not_applicable"])
        _require(not covered_dimensions & excluded_dimensions, f"{identity}: contradictory evidence applicability")
        _require(
            covered_dimensions | excluded_dimensions == set(DIMENSIONS), f"{identity}: invalid or missing dimension"
        )
        for dimension, reason in row["not_applicable"].items():
            _text(reason, identity + " " + dimension + " applicability reason")
        for dimension, selectors in row["evidence"].items():
            for selector in _strings(selectors, identity + " " + dimension + " selectors"):
                matched[identity][selector] = match_selector(selector, nodeids)
        supported_features.update(row_features)
    _require(
        supported_features == feature_ids,
        f"features lack supported evidence: {sorted(feature_ids - supported_features)}",
    )
    return {
        "matches": matched,
        "collected": len(nodeids),
        "supported": sum(row["status"] == "supported" for row in rows),
        "excluded": sum(row["status"] == "out-of-profile" for row in rows),
        "unique_matches": len({node for evidence in matched.values() for nodes in evidence.values() for node in nodes}),
        "evidence_links": sum(len(nodes) for evidence in matched.values() for nodes in evidence.values()),
    }


def render_coverage(catalog: dict[str, Any], references: dict[str, Any], result: dict[str, Any]) -> str:
    """Render portable coverage evidence without claiming test execution or full conformance."""
    reference_map = {item["id"]: item for item in references["references"]}
    lines = [
        "# Scoped requirement evidence",
        "",
        "Generated from [requirements.json](requirements.json) by `python scripts/check_requirements.py --render`.",
        "The default command checks this table without modifying it.",
        "",
        f"{result['supported']} supported requirements; {result['excluded']} explicit profile exclusions; "
        f"{result['unique_matches']} distinct collected tests; {result['evidence_links']} requirement-to-test links.",
        "",
        "Counts describe collected evidence, not executed or passing tests. One test can support several rows.",
        "This is not a percentage of all clauses in the copied specifications or a complete Cartesian test matrix.",
        "Source and installed targets collect the same behavioral evidence; platform/resource and source-only",
        "harness skips are reported by pytest when executing the suite, not hidden by collection counts.",
        "",
        "## Feature inventory",
        "",
        "| Feature | Contract | Export or format aliases |",
        "| --- | --- | --- |",
    ]
    for feature in catalog["features"]:
        names = [feature["export"]] if feature["kind"] == "callable" else feature["aliases"]
        lines.append(
            f"| `{feature['id']}` | {feature['description']} | " + ", ".join(f"`{name}`" for name in names) + " |"
        )
    lines.extend(
        [
            "",
            "## Requirement map",
            "",
            "| Requirement | Category / status | Concrete behavior | Tests |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in catalog["requirements"]:
        count = len({node for nodes in result["matches"][row["id"]].values() for node in nodes})
        lines.append(
            f"| [{row['id']}](#{row['id'].lower()}) | {row['category']} / {row['status']} | "
            f"{row['description']} | {count} |"
        )
    for row in catalog["requirements"]:
        lines.extend(
            [
                "",
                f"### {row['id']}",
                "",
                row["description"],
                "",
                "Features: " + ", ".join(f"`{feature}`" for feature in row["features"]) + ".",
                "",
            ]
        )
        if row["clauses"]:
            clauses = []
            for clause in row["clauses"]:
                path = reference_map[clause["reference"]]["path"]
                fragment = "#" + clause["anchor"] if clause["anchor"] is not None else ""
                label = f"{clause['reference']} §{clause['section']}"
                status = "normative" if clause["normative"] else "informative context"
                clauses.append(f"[{label}]({path}{fragment}) ({status})")
            lines.extend(["References: " + "; ".join(clauses) + ".", ""])
        else:
            lines.extend(["Project contract; no normative standard algorithm is claimed.", ""])
        for owner in row["owners"]:
            lines.append(f"- {owner['role']}: [`{owner['target']}`](../../{owner['path']}).")
        lines.append("")
        if row["status"] == "out-of-profile":
            lines.append("Outside this API profile: " + row["reason"])
            continue
        lines.extend(["| Dimension | Collected evidence or applicability |", "| --- | --- |"])
        for dimension in DIMENSIONS:
            if dimension in row["not_applicable"]:
                evidence = "Not applicable: " + row["not_applicable"][dimension]
            else:
                evidence = "<br>".join(
                    f"`{selector}` ({len(result['matches'][row['id']][selector])})"
                    for selector in row["evidence"][dimension]
                )
            lines.append(f"| {dimension} | {evidence} |")
    return "\n".join(lines).rstrip() + "\n"


def check_coverage(path: Path, expected: str) -> None:
    """Reject a missing or stale generated report without rewriting it."""
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RequirementValidationError(f"cannot read coverage table: {error}") from error
    _require(actual == expected, "stale coverage table; run python scripts/check_requirements.py --render")


def main(arguments: Sequence[str] | None = None) -> int:
    """Check references and actual test evidence offline, optionally rendering the table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=_CATALOG)
    parser.add_argument("--references", type=Path, default=_REFERENCES)
    parser.add_argument("--coverage", type=Path, default=_COVERAGE)
    parser.add_argument("--package-under-test", choices=("source", "installed"), default="source")
    parser.add_argument("--render", action="store_true", help="explicitly update the generated coverage table")
    parser.add_argument("--collect-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(arguments)
    if args.collect_output is not None:
        import pytest

        return int(
            pytest.main(
                [
                    "--collect-only",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "-o",
                    "addopts=",
                    "--package-under-test=" + args.package_under_test,
                    "-c",
                    str(_ROOT / "pyproject.toml"),
                    str(_ROOT / "tests"),
                ],
                plugins=[_Collection(args.collect_output)],
            )
        )
    try:
        references = checked_references(args.references)
        catalog = read_catalog(args.catalog)
        collection = collect_evidence(args.package_under_test)
        result = validate_requirements(catalog, references, collection, args.references.parent)
        rendered = render_coverage(catalog, references, result)
        if args.render:
            args.coverage.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            check_coverage(args.coverage, rendered)
    except (RequirementValidationError, OSError) as error:
        print(f"requirements verification failed: {error}")
        return 1
    print(
        f"verified {result['supported']} supported requirements and {result['excluded']} profile exclusions; "
        f"{result['unique_matches']} distinct collected tests, {result['evidence_links']} requirement-to-test links "
        f"({args.package_under_test}; collection only)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
