"""JSON-LD ordering contracts for ``@graph``, ``@set``, and nested lists.

``@graph`` and ``@set`` arrays are unordered under JSON-LD 1.1. Nested
``@list`` and locally declared list containers retain their element order.
"""

from __future__ import annotations

import json

import pytest
from rdflib import Graph
from rdflib.compare import isomorphic

from diffable_rdf import deterministic_json

EX = "http://example.org/"


def _sorted_document(document: object, **kwargs: object) -> object:
    return json.loads(deterministic_json(document, **kwargs))


@pytest.mark.parametrize("container", ["@graph", "@set"])
def test_unordered_containers_are_sorted(container: str) -> None:
    """The whole point: equal data, one output, whatever order it was built in."""
    forward = {container: [{"@id": f"{EX}z"}, {"@id": f"{EX}a"}]}
    reverse = {container: [{"@id": f"{EX}a"}, {"@id": f"{EX}z"}]}

    assert deterministic_json(forward) == deterministic_json(reverse)
    assert _sorted_document(forward)[container] == [{"@id": f"{EX}a"}, {"@id": f"{EX}z"}]


@pytest.mark.parametrize("container", ["@graph", "@set"])
def test_sorting_an_unordered_container_does_not_change_the_rdf(container: str) -> None:
    """Sorting is only safe because the order carried no meaning -- prove that."""
    document = {
        "@context": {"label": f"{EX}label"},
        container: [
            {"@id": f"{EX}z", "label": "zeta"},
            {"@id": f"{EX}a", "label": "alpha", f"{EX}typed": {"@value": "7", "@type": f"{EX}Int"}},
        ],
    }
    before = Graph().parse(data=json.dumps(document), format="json-ld")
    after = Graph().parse(data=deterministic_json(document), format="json-ld")

    assert isomorphic(before, after)
    assert len(before) == len(after) > 0


def test_a_list_nested_in_a_graph_array_keeps_its_order() -> None:
    """An ordered list retains its element order inside an unordered array."""
    document = {
        "@graph": [
            {"@id": f"{EX}s", f"{EX}items": {"@list": ["zeta", "alpha", "mu"]}},
            {"@id": f"{EX}a"},
        ]
    }
    result = _sorted_document(document)

    # The @graph array itself was reordered...
    assert [node["@id"] for node in result["@graph"]] == [f"{EX}a", f"{EX}s"]
    # ...but the @list inside it was not.
    listed = next(n for n in result["@graph"] if n["@id"] == f"{EX}s")
    assert listed[f"{EX}items"]["@list"] == ["zeta", "alpha", "mu"]


def test_a_container_list_term_nested_in_a_set_array_keeps_its_order() -> None:
    """Ordering declared by a local context survives inside an unordered array."""
    document = {
        "@context": {"items": {"@id": f"{EX}items", "@container": "@list"}},
        "@set": [{"@id": f"{EX}s", "items": ["zeta", "alpha"]}],
    }
    result = _sorted_document(document)

    assert result["@set"][0]["items"] == ["zeta", "alpha"]
    assert isomorphic(
        Graph().parse(data=json.dumps(document), format="json-ld"),
        Graph().parse(data=deterministic_json(document), format="json-ld"),
    )


def test_an_aliased_list_nested_in_a_graph_array_keeps_its_order() -> None:
    """Aliases are resolved through the keyword logic, not the parent-key list."""
    document = {
        "@context": {"ordered": "@list", "items": f"{EX}items"},
        "@graph": [{"@id": f"{EX}s", "items": {"ordered": ["zeta", "alpha"]}}],
    }
    result = _sorted_document(document)

    assert result["@graph"][0]["items"]["ordered"] == ["zeta", "alpha"]


def test_an_aliased_graph_array_is_sorted_like_its_keyword() -> None:
    """An alias of an unordered keyword must not be protected either."""
    document = {
        "@context": {"nodes": "@graph"},
        "nodes": [{"@id": f"{EX}z"}, {"@id": f"{EX}a"}],
    }
    assert _sorted_document(document)["nodes"] == [{"@id": f"{EX}a"}, {"@id": f"{EX}z"}]


def test_context_arrays_are_still_never_reordered() -> None:
    """``@context`` order decides which definition wins; it is not ours to touch."""
    document = {
        "@context": [{"label": f"{EX}first"}, {"label": f"{EX}second"}],
        "@id": f"{EX}s",
        "label": "v",
    }
    result = _sorted_document(document)

    assert result["@context"] == [{"label": f"{EX}first"}, {"label": f"{EX}second"}]
    assert isomorphic(
        Graph().parse(data=json.dumps(document), format="json-ld"),
        Graph().parse(data=deterministic_json(document), format="json-ld"),
    )


def test_a_context_inside_a_graph_element_is_still_applied() -> None:
    """Sorting the array must not stop a nested context from being read."""
    document = {
        "@graph": [
            {
                "@context": {"items": {"@id": f"{EX}items", "@container": "@list"}},
                "@id": f"{EX}s",
                "items": ["zeta", "alpha"],
            }
        ]
    }
    assert _sorted_document(document)["@graph"][0]["items"] == ["zeta", "alpha"]


def test_imports_stays_protected_by_default_and_is_droppable() -> None:
    """``imports`` is a local convenience, not a keyword: the caller owns it."""
    document = {"imports": ["zeta", "alpha"]}

    assert _sorted_document(document)["imports"] == ["zeta", "alpha"]
    dropped = _sorted_document(document, preserve_list_order_keys=frozenset({"other"}))
    assert dropped["imports"] == ["alpha", "zeta"]


def test_a_custom_key_set_replaces_the_default_but_not_the_keyword_rules() -> None:
    """Pinned because it is the one part of the contract easiest to get wrong."""
    document = {"@list": ["zeta", "alpha"], "keep": ["zeta", "alpha"], "sort": ["zeta", "alpha"]}
    result = _sorted_document(document, preserve_list_order_keys=frozenset({"keep"}))

    assert result["@list"] == ["zeta", "alpha"], "@list is a keyword, always ordered"
    assert result["keep"] == ["zeta", "alpha"], "the caller's key is honoured"
    assert result["sort"] == ["alpha", "zeta"], "everything else sorts"
