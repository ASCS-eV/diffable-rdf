"""Semantic ordering contracts for deterministic JSON-LD output."""

from __future__ import annotations

import json
import urllib.request

import pytest
from rdflib import Graph
from rdflib.compare import isomorphic

from diffable_rdf import deterministic_json


def _graph(document: object) -> Graph:
    return Graph().parse(data=json.dumps(document), format="json-ld")


def _lookup(document: object, path: list[str]) -> object:
    value = document
    for step in path:
        assert isinstance(value, dict)
        value = value[step]
    return value


def _assert_rdf_equivalent(document: object) -> dict[str, object]:
    rendered = deterministic_json(document)
    result = json.loads(rendered)
    assert isomorphic(_graph(document), Graph().parse(data=rendered, format="json-ld"))
    assert isinstance(result, dict)
    return result


@pytest.mark.parametrize(
    ("document", "path"),
    [
        (
            {
                "@id": "http://example.com/s",
                "http://example.com/p": [{"@value": [2, 1], "@type": "@json"}],
            },
            ("http://example.com/p", 0, "@value"),
        ),
        (
            {
                "@id": "http://example.com/s",
                "http://example.com/p": [
                    {"@value": {"outer": [[2, 1], [4, 3]]}, "@type": "@json"}
                ],
            },
            ("http://example.com/p", 0, "@value", "outer"),
        ),
        (
            {
                "@context": {
                    "payload": {"@id": "http://example.com/p", "@type": "@json"}
                },
                "@id": "http://example.com/s",
                "payload": {"outer": [[2, 1], [4, 3]]},
            },
            ("payload", "outer"),
        ),
        (
            {
                "@context": {
                    "kind": "@type",
                    "literal": "@value",
                    "p": "http://example.com/p",
                },
                "@id": "http://example.com/s",
                "p": [{"literal": [2, 1], "kind": "@json"}],
            },
            ("p", 0, "literal"),
        ),
    ],
)
def test_json_literal_arrays_preserve_rdf_meaning(document, path):
    result: object = _assert_rdf_equivalent(document)
    for component in path:
        result = result[component]  # type: ignore[index]
    if path[-1] == "outer":
        assert result == [[2, 1], [4, 3]]
    else:
        assert result == [2, 1]


def test_context_defined_list_preserves_rdf_meaning():
    document = {
        "@context": {"items": {"@id": "http://example.com/items", "@container": "@list"}},
        "@id": "http://example.com/s",
        "items": ["z", "a"],
    }
    result = _assert_rdf_equivalent(document)
    assert result["items"] == ["z", "a"]


def test_explicit_list_preserves_rdf_meaning():
    document = {
        "@context": {"p": "http://example.com/p"},
        "@id": "http://example.com/s",
        "p": {"@list": ["z", "a"]},
    }
    result = _assert_rdf_equivalent(document)
    assert result["p"]["@list"] == ["z", "a"]  # type: ignore[index]


@pytest.mark.parametrize("definition", ["@list", {"@id": "@list"}])
def test_list_keyword_alias_preserves_rdf_meaning(definition):
    document = {
        "@context": {"items": definition, "p": "http://example.com/p"},
        "@id": "http://example.com/s",
        "p": {"items": ["z", "a"]},
    }
    result = _assert_rdf_equivalent(document)
    assert result["p"]["items"] == ["z", "a"]  # type: ignore[index]


def test_context_overrides_are_applied_in_order():
    list_last = {
        "@context": [
            {"items": "http://example.com/items"},
            {"items": {"@id": "http://example.com/items", "@container": "@list"}},
        ],
        "items": ["z", "a"],
    }
    set_last = {
        "@context": [
            {"items": {"@id": "http://example.com/items", "@container": "@list"}},
            {"items": "http://example.com/items"},
        ],
        "items": ["z", "a"],
    }

    assert _assert_rdf_equivalent(list_last)["items"] == ["z", "a"]
    assert _assert_rdf_equivalent(set_last)["items"] == ["a", "z"]


def test_local_context_is_inherited_and_null_resets_it():
    document = {
        "@context": {"items": {"@id": "http://example.com/items", "@container": "@list"}},
        "nested": {"items": ["z", "a"]},
        "reset": {"@context": None, "items": ["z", "a"]},
    }

    result = json.loads(deterministic_json(document))
    assert result["nested"]["items"] == ["z", "a"]
    assert result["reset"]["items"] == ["a", "z"]


def test_remote_context_is_never_loaded_and_fails_safe(monkeypatch):
    def unexpected_urlopen(*args, **kwargs):
        raise AssertionError("deterministic_json must not load remote contexts")

    monkeypatch.setattr(urllib.request, "urlopen", unexpected_urlopen)
    document = {
        "@context": "https://example.invalid/context.jsonld",
        "possiblyOrdered": ["z", "a"],
        "possibleJsonPayload": {
            "@context": None,
            "nested": [[2, 1], [4, 3]],
        },
    }

    result = json.loads(deterministic_json(document))
    assert result["possiblyOrdered"] == ["z", "a"]
    assert result["possibleJsonPayload"]["nested"] == [[2, 1], [4, 3]]


def test_scoped_context_fails_safe_for_the_document():
    document = {
        "@context": {
            "nested": {
                "@id": "http://example.com/nested",
                "@context": "https://example.invalid/scoped.jsonld",
            }
        },
        "nested": {"possiblyOrdered": ["z", "a"]},
        "ordinary": ["z", "a"],
    }

    result = json.loads(deterministic_json(document))
    assert result["nested"]["possiblyOrdered"] == ["z", "a"]
    assert result["ordinary"] == ["z", "a"]


def test_type_scoped_context_fails_safe_and_preserves_rdf_meaning():
    document = {
        "@context": {
            "Thing": {
                "@id": "http://example.com/Thing",
                "@context": {
                    "items": {"@id": "http://example.com/items", "@container": "@list"}
                },
            },
            "items": "http://example.com/items",
        },
        "@id": "http://example.com/s",
        "@type": "Thing",
        "items": ["z", "a"],
    }

    result = _assert_rdf_equivalent(document)
    assert result["items"] == ["z", "a"]


@pytest.mark.parametrize(("directive", "value"), [("@propagate", False), ("@protected", True)])
def test_unsupported_context_directive_fails_safe(directive, value):
    document = {
        "@context": {directive: value, "items": "http://example.com/items"},
        "items": ["z", "a"],
    }

    result = json.loads(deterministic_json(document))
    assert result["items"] == ["z", "a"]


def test_context_free_json_still_sorts_lists_and_does_not_mutate_input():
    document = {"payload": {"values": [3, 1, 2]}, "custom": ["z", "a"]}
    original = json.loads(json.dumps(document))

    result = json.loads(deterministic_json(document, preserve_list_order_keys=frozenset({"custom"})))

    assert result["payload"]["values"] == [1, 2, 3]
    assert result["custom"] == ["z", "a"]
    assert document == original


@pytest.mark.parametrize(
    ("document", "path"),
    [
        pytest.param(
            {
                "@context": {"payload": {"@id": "http://ex/payload", "@type": "jsn"}, "jsn": "@json"},
                "@id": "http://ex/s",
                "payload": [3, 1, 2],
            },
            ["payload"],
            id="type-json-through-an-alias-declared-later",
        ),
        pytest.param(
            {
                "@context": {"steps": "lst", "lst": "@list"},
                "@id": "http://ex/s",
                "http://ex/p": {"steps": ["c", "a", "b"]},
            },
            ["http://ex/p", "steps"],
            id="list-alias-declared-later",
        ),
        pytest.param(
            {
                "@context": {"steps": {"@id": "lst"}, "lst": "@list"},
                "@id": "http://ex/s",
                "http://ex/p": {"steps": ["c", "a", "b"]},
            },
            ["http://ex/p", "steps"],
            id="list-alias-declared-later-via-id",
        ),
    ],
)
def test_a_term_definition_may_reference_an_alias_declared_after_it(document, path):
    """Key order inside a ``@context`` object carries no meaning.

    Create Term Definition (JSON-LD 1.1 API §4.2.2) keeps a ``defined`` map and
    resolves a referenced term recursively, so a definition may name an alias
    that appears later in the same object. Local resolution therefore reaches
    a stable result before deciding whether an array carries order.
    """
    result = _assert_rdf_equivalent(document)

    assert _lookup(result, path) == _lookup(document, path), "an ordered array was reordered"


@pytest.mark.parametrize(
    ("document", "path"),
    [
        pytest.param(
            {"@id": "http://ex/s", "http://ex/p": {"@list": [["b", "a"], "c"]}},
            ["http://ex/p", "@list"],
            id="array-inside-an-explicit-list",
        ),
        pytest.param(
            {
                "@context": {"l": {"@id": "http://ex/l", "@container": "@list"}},
                "@id": "http://ex/s",
                "l": [["b", "a"], ["c"]],
            },
            ["l"],
            id="array-inside-a-list-container",
        ),
    ],
)
def test_an_array_nested_in_an_ordered_array_keeps_its_order(document, path):
    """An array inside an ordered array is ordered too.

    A list is *the* ordered container (JSON-LD 1.1 §4.3.1), and a nested array
    expands to a nested list rather than to a fresh unordered value -- so its
    order reaches the RDF as ``rdf:first``/``rdf:rest`` structure just the same.
    Nested arrays inherit the enclosing ordered-list semantics.
    """
    result = _assert_rdf_equivalent(document)

    assert _lookup(result, path) == _lookup(document, path)


def test_a_shadowing_definition_in_a_nested_context_array_keeps_its_order():
    """``@context`` arrays are processed in order and each entry overrides the last.

    The inner array's order determines which definition of ``x`` applies.
    """
    document = {
        "@context": [
            {"x": "http://ex/first"},
            [{"x": "http://ex/z-loser"}, {"x": "http://ex/a-winner"}],
        ],
        "@id": "http://ex/s",
        "x": "v",
    }

    result = _assert_rdf_equivalent(document)

    assert result["@context"] == document["@context"]
    assert "http://ex/a-winner" in json.dumps(_graph(document).serialize(format="nt"))


def test_a_dict_inside_an_ordered_array_still_starts_a_sortable_node_object():
    """A dict inside an ordered array begins a sortable JSON-LD node object."""
    document = {"@id": "http://ex/s", "http://ex/p": {"@list": [{"http://ex/q": [3, 1, 2]}]}}

    result = _assert_rdf_equivalent(document)

    assert result["http://ex/p"]["@list"][0]["http://ex/q"] == [1, 2, 3]
