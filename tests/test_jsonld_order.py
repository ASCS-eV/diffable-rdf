"""Semantic ordering regressions for deterministic JSON-LD output."""

from __future__ import annotations

import json
import urllib.request

import pytest
from rdflib import Graph
from rdflib.compare import isomorphic

from diffable_rdf import deterministic_json


def _graph(document: object) -> Graph:
    return Graph().parse(data=json.dumps(document), format="json-ld")


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
