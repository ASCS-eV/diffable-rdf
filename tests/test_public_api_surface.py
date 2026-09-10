"""The public surface must hold up to the ways callers actually inspect it.

A library's annotations are not only read by a type checker. Pydantic,
FastAPI, `typer`, `attrs`, `beartype` and every documentation generator call
`typing.get_type_hints`, which evaluates the annotations at runtime -- and an
annotation that only exists under `TYPE_CHECKING` raises `NameError` there.
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
    """`deterministic_turtle` raised NameError: RdfGraph.

    Its `graph` parameter was annotated with a name imported only under
    `TYPE_CHECKING`, for a dependency this package requires unconditionally.
    """
    function = getattr(diffable_rdf, name)

    hints = typing.get_type_hints(function)

    assert hints, f"{name} has no resolvable annotations"
    assert "return" in hints, f"{name} does not annotate its return type"


def test_the_turtle_entry_point_names_the_graph_type_it_takes() -> None:
    """The resolved hint has to be the real class, not a placeholder."""
    import rdflib

    assert typing.get_type_hints(diffable_rdf.deterministic_turtle)["graph"] is rdflib.Graph


def test_the_preserved_keys_argument_admits_any_set() -> None:
    """The annotation was `frozenset[str]`, narrower than the documented contract.

    The documentation invites `preserve_list_order_keys={"custom"}`, which a
    type checker rejected against `frozenset[str]`, and every caller that
    passed a plain set was reporting an error it could not fix without a cast.
    """
    hints = typing.get_type_hints(deterministic_json)

    assert hints["preserve_list_order_keys"] == AbstractSet[str] | None

    document = {"custom": [3, 1, 2], "other": [3, 1, 2]}
    expected = {"custom": [3, 1, 2], "other": [1, 2, 3]}
    for keys in ({"custom"}, frozenset({"custom"}), {"custom": 0}.keys()):
        rendered = deterministic_json(document, preserve_list_order_keys=keys)
        assert json.loads(rendered) == expected, keys


def test_both_dependencies_are_loaded_before_any_public_call_can_be_made() -> None:
    """A dead `except ImportError` around pyoxigraph's import claimed otherwise.

    `deterministic_turtle` caught `ImportError` from importing pyoxigraph and
    re-raised advice to install it. Both are declared, non-optional
    dependencies, and importing this package imports both -- so the branch
    could not run for any installation able to reach it, while suggesting to
    the reader that the dependency was optional.

    Checked in a fresh interpreter: in this one, pytest has imported
    everything already, which would make the assertion vacuous.
    """
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
    """A release must not be able to ship without saying what is in it.

    The publish workflow checks the same two things against the release tag,
    but only at release time. Checking here means a version bump without its
    changelog entry, or an entry without the bump, fails on the pull request
    that introduced it.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert f"## [{diffable_rdf.__version__}]" in changelog, (
        f"CHANGELOG.md has no section for the current version "
        f"{diffable_rdf.__version__}"
    )
    headings = [line for line in changelog.splitlines() if line.startswith("## [")]
    assert headings[0].startswith(f"## [{diffable_rdf.__version__}]"), (
        f"the newest changelog section is {headings[0]!r}, not the current version"
    )
