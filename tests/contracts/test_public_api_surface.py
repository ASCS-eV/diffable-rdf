"""Runtime-inspection contracts for the public API.

A library's annotations are not only read by a type checker. Pydantic,
FastAPI, `typer`, `attrs`, `beartype` and every documentation generator call
`typing.get_type_hints`, which evaluates annotations at runtime.
"""

from __future__ import annotations

import json
import subprocess
import sys
import typing
from collections.abc import Set as AbstractSet

import pytest

import diffable_rdf
from diffable_rdf import deterministic_json


PUBLIC_NAMES = sorted(name for name in diffable_rdf.__all__ if name != "__version__")


def test_the_documented_surface_is_what_the_module_exports() -> None:
    """`__all__` is the contract; nothing may drift out of it silently."""
    assert PUBLIC_NAMES == [
        "canonicalize_rdf_graph",
        "deterministic_json",
        "deterministic_turtle",
        "well_known_prefix_map",
        "wl_blank_node_labels",
        "wl_relabel_quads",
    ]
    for name in PUBLIC_NAMES:
        assert callable(getattr(diffable_rdf, name)), name


@pytest.mark.parametrize("name", PUBLIC_NAMES)
def test_every_public_annotation_resolves_at_runtime(name: str) -> None:
    """Each public callable has resolvable runtime annotations."""
    function = getattr(diffable_rdf, name)

    hints = typing.get_type_hints(function)

    assert hints, f"{name} has no resolvable annotations"
    assert "return" in hints, f"{name} does not annotate its return type"


def test_the_turtle_entry_point_names_the_graph_type_it_takes() -> None:
    """The resolved hint has to be the real class, not a placeholder."""
    import rdflib

    assert typing.get_type_hints(diffable_rdf.deterministic_turtle)["graph"] is rdflib.Graph


def test_the_preserved_keys_argument_admits_any_set() -> None:
    """The key collection annotation accepts the standard set abstractions."""
    hints = typing.get_type_hints(deterministic_json)

    assert hints["preserve_list_order_keys"] == AbstractSet[str] | None

    document = {"custom": [3, 1, 2], "other": [3, 1, 2]}
    expected = {"custom": [3, 1, 2], "other": [1, 2, 3]}
    for keys in ({"custom"}, frozenset({"custom"}), {"custom": 0}.keys()):
        rendered = deterministic_json(document, preserve_list_order_keys=keys)
        assert json.loads(rendered) == expected, keys


def test_both_dependencies_are_loaded_before_any_public_call_can_be_made() -> None:
    """Importing the package loads both required RDF dependencies."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import diffable_rdf, sys; print('pyoxigraph' in sys.modules, 'rdflib' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.split() == ["True", "True"], result.stdout


def test_the_version_has_a_changelog_section() -> None:
    """The current package version has the leading changelog section."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert f"## [{diffable_rdf.__version__}]" in changelog, (
        f"CHANGELOG.md has no section for the current version "
        f"{diffable_rdf.__version__}"
    )
    headings = [line for line in changelog.splitlines() if line.startswith("## [")]
    assert headings[0].startswith(f"## [{diffable_rdf.__version__}]"), (
        f"the newest changelog section is {headings[0]!r}, not the current version"
    )
