"""The rdflib Turtle serializer hooks this package depends on.

``diffable_rdf.turtle`` extends rdflib's compact Turtle serializer, overrides
some of its methods and reads two of its members. rdflib calls a method by its
name, and rdflib 8 renamed them from camelCase to snake_case without aliases.
An override under a name rdflib no longer calls is skipped without an error,
and the output silently loses the order or layout the override imposes. These
tests name the hook when the installed rdflib stops providing it.
"""

from __future__ import annotations

import pytest

from diffable_rdf import turtle

_BASE = turtle._CompactTurtleSerializer


def _name_rdflib_uses(names: tuple[str, ...]) -> str:
    """The first of ``names`` that the installed rdflib's serializer defines."""
    present = [name for name in names if hasattr(_BASE, name)]
    assert present, (
        f"{_BASE.__module__}.{_BASE.__qualname__} defines none of {names}. "
        "rdflib renamed or removed a serializer hook diffable_rdf.turtle depends on."
    )
    return present[0]


@pytest.mark.parametrize(
    ("serializer", "names"),
    [
        (turtle._LiteralPreservingTurtleSerializer, ("sort_properties", "sortProperties")),
        (turtle._LiteralPreservingTurtleSerializer, ("preprocess",)),
        (turtle._LiteralPreservingTurtleSerializer, ("label",)),
        (turtle._NoCollectionTurtleSerializer, ("is_valid_list", "isValidList")),
    ],
)
def test_each_override_is_under_the_name_rdflib_calls(serializer: type, names: tuple[str, ...]) -> None:
    name = _name_rdflib_uses(names)
    assert getattr(serializer, name) is not getattr(_BASE, name), (
        f"{serializer.__name__} does not override {name}, which is the name the installed rdflib calls"
    )


@pytest.mark.parametrize(
    "names",
    [("preprocess_triple", "preprocessTriple"), ("predicate_order", "predicateOrder")],
)
def test_each_member_this_package_reads_exists(names: tuple[str, ...]) -> None:
    _name_rdflib_uses(names)
