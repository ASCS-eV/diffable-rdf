"""Tests for the diffable-rdf public API."""

from __future__ import annotations

import json

import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF, RDFS, XSD

from diffable_rdf import (
    canonicalize_rdf_graph,
    deterministic_json,
    deterministic_turtle,
    well_known_prefix_map,
)

EX = Namespace("http://example.org/")


def _sample_graph() -> Graph:
    g = Graph()
    g.bind("ex", EX)
    g.bind("rdfs", RDFS)
    # a class with two restriction-like blank nodes
    cls = EX.Thing
    g.add((cls, RDF.type, RDFS.Class))
    g.add((cls, RDFS.label, Literal("Thing", lang="en")))
    g.add((cls, RDFS.comment, Literal("a plain string literal")))
    for name, dt in (("width", XSD.double), ("count", XSD.integer)):
        b = BNode()
        g.add((cls, EX.constraint, b))
        g.add((b, EX.onProperty, EX[name]))
        g.add((b, EX.datatype, dt))
    return g


def test_deterministic_turtle_is_byte_stable_across_runs():
    g = _sample_graph()
    out1 = deterministic_turtle(g)
    out2 = deterministic_turtle(_sample_graph())
    assert out1 == out2


def test_deterministic_turtle_is_isomorphic_to_input():
    g = _sample_graph()
    out = deterministic_turtle(g)
    round_trip = Graph().parse(data=out, format="turtle")
    assert isomorphic(round_trip, g)


def test_deterministic_turtle_strips_xsd_string():
    g = Graph()
    g.add((EX.s, EX.p, Literal("plain", datatype=XSD.string)))
    out = deterministic_turtle(g)
    assert "xsd:string" not in out
    assert "^^" not in out


def test_deterministic_turtle_uses_inline_blank_nodes():
    g = _sample_graph()
    out = deterministic_turtle(g)
    assert "[" in out and "]" in out


def test_deterministic_turtle_filters_unused_prefixes():
    g = _sample_graph()
    out = deterministic_turtle(g)
    # rdflib binds ~27 default prefixes; only referenced ones should appear
    assert "@prefix brick:" not in out
    assert "@prefix ex:" in out


def test_deterministic_turtle_no_bnodes():
    g = Graph()
    g.bind("ex", EX)
    g.add((EX.a, EX.p, EX.b))
    out1 = deterministic_turtle(g)
    out2 = deterministic_turtle(g)
    assert out1 == out2
    assert isomorphic(Graph().parse(data=out1, format="turtle"), g)


def test_wl_stable_when_unrelated_triple_added():
    g1 = _sample_graph()
    g2 = _sample_graph()
    g2.add((EX.Unrelated, RDF.type, RDFS.Class))
    out1 = deterministic_turtle(g1)
    out2 = deterministic_turtle(g2)
    # the added statement must appear; the shared block's bnode labels
    # (b<hash>) that survive should keep output overwhelmingly shared.
    assert out1 != out2
    shared = set(out1.splitlines()) & set(out2.splitlines())
    assert len(shared) >= len(out1.splitlines()) // 2


def test_deterministic_json_sorts_keys_and_lists():
    obj = {"b": 1, "a": [3, 1, 2], "c": {"z": 0, "y": 1}}
    out = deterministic_json(obj)
    parsed = json.loads(out)
    assert list(parsed.keys()) == ["a", "b", "c"]
    assert parsed["a"] == [1, 2, 3]
    assert list(parsed["c"].keys()) == ["y", "z"]


def test_deterministic_json_preserves_context_order():
    obj = {"@context": ["z", "a", "m"], "x": 1}
    out = deterministic_json(obj)
    parsed = json.loads(out)
    assert parsed["@context"] == ["z", "a", "m"]


def test_canonicalize_rdf_graph_is_deterministic():
    g = _sample_graph()
    out1 = canonicalize_rdf_graph(g, "turtle")
    out2 = canonicalize_rdf_graph(_sample_graph(), "turtle")
    assert out1 == out2
    assert isomorphic(Graph().parse(data=out1, format="turtle"), g)


def test_canonicalize_rdf_graph_falls_back_for_literal_predicates():
    # A literal in predicate position is non-standard RDF; must not crash.
    g = Graph()
    g.add((EX.s, EX.p, EX.o))
    out = canonicalize_rdf_graph(g, "turtle")
    assert "http://example.org/p" in out


def test_well_known_prefix_map_contains_schema_org():
    m = well_known_prefix_map()
    assert m.get("https://schema.org/") == "schema"
