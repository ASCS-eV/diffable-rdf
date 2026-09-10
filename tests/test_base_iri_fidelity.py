"""A graph's base must never change the terms a consumer reads back.

`canonicalize_rdf_graph` hands `graph.base` to pyoxigraph, which relativizes
per RFC 3986 section 5.1 — resolving `<#a>` against `http://ex.org/d#` discards
the base's fragment and gives `http://ex.org/d#a`. rdflib's notation3 parser
concatenates instead, yielding `http://ex.org/d##a`: every term of the graph
changed, silently.

The round-trip guard could not see it, because it checked only that rdflib
*parses* and then compared **pyoxigraph's** canonical forms — two correct
readings, agreeing with each other. `deterministic_turtle` was never affected;
it drops the base outright, with a comment citing this exact hazard.
"""

from __future__ import annotations

import pyoxigraph as ox
import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic

import diffable_rdf.canonicalize as canonicalize_module
from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

EX = Namespace("http://example.org/")
VERIFIED = ["turtle", "ttl", "trig", "n3", "xml", "rdf/xml"]
PARSER = {"ttl": "turtle", "rdf/xml": "xml"}


def _hash_base_graph() -> Graph:
    graph = Graph(base="http://ex.org/d#")
    graph.add((URIRef("http://ex.org/d#a"), URIRef("http://ex.org/d#p"), URIRef("http://ex.org/d#b")))
    return graph


@pytest.mark.parametrize("output_format", VERIFIED)
def test_a_fragment_base_does_not_change_the_terms(output_format: str) -> None:
    """The defect: every IRI came back with a doubled `#`."""
    graph = _hash_base_graph()

    result = canonicalize_rdf_graph(graph, output_format=output_format)
    reparsed = Graph().parse(data=result, format=PARSER.get(output_format, output_format))

    assert isomorphic(reparsed, graph)
    assert {str(term) for triple in reparsed for term in triple} == {
        "http://ex.org/d#a",
        "http://ex.org/d#p",
        "http://ex.org/d#b",
    }
    assert "##" not in result


def test_deterministic_turtle_was_never_affected() -> None:
    """It drops the base; pin that so the two entry points cannot diverge again."""
    graph = _hash_base_graph()

    result = deterministic_turtle(graph)

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


@pytest.mark.parametrize("output_format", ["turtle", "trig", "n3"])
def test_an_ordinary_base_still_relativizes(output_format: str) -> None:
    """Only a *fragment* base is dropped; a path base keeps working."""
    graph = Graph(base="http://ex.org/d/")
    graph.add((URIRef("http://ex.org/d/a"), URIRef("http://ex.org/d/p"), Literal("v")))

    result = canonicalize_rdf_graph(graph, output_format=output_format)
    reparsed = Graph().parse(data=result, format=output_format)

    assert "@base" in result
    assert "<a>" in result, "an ordinary base should still produce relative references"
    assert isomorphic(reparsed, graph)


def test_dropping_a_fragment_base_is_reported() -> None:
    """Silently changing how output is written would be worse than the bug."""
    import logging

    graph = _hash_base_graph()
    logger = logging.getLogger("diffable_rdf.canonicalize")
    records: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    handler = Capture()
    logger.addHandler(handler)
    try:
        canonicalize_rdf_graph(graph, "turtle")
    finally:
        logger.removeHandler(handler)

    assert any("fragment" in message for message in records), records


def test_the_guard_catches_an_iri_the_input_never_contained() -> None:
    """The general defence, not just the base case.

    rdflib normalizes literals but not IRIs, so an IRI in its re-parse that the
    source lacks means the output says something else to the library's primary
    consumer — which is exactly what the base defect did.
    """
    graph = Graph()
    graph.add((URIRef("http://example.org/s"), URIRef("http://example.org/p"), Literal("v")))

    with pytest.raises(ValueError, match="does not round-trip"):
        canonicalize_module._assert_round_trips(
            graph,
            "<http://example.org/s> <http://example.org/p> <http://example.org/INVENTED> .\n",
            "nt",
        )


def test_the_guard_still_tolerates_rdflibs_literal_normalization() -> None:
    """It must not fire on the thing it deliberately delegates to pyoxigraph.

    rdflib reads `"01"^^xsd:integer` back as `"1"`, which is why the exact
    identity comparison uses pyoxigraph. The new IRI check must not turn that
    into a false alarm.
    """
    from rdflib.namespace import XSD

    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("01", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.p, Literal("1", datatype=XSD.integer, normalize=False)))

    # The call succeeding at all is the assertion: the guard runs inside it,
    # and a false alarm would raise here.
    result = canonicalize_rdf_graph(graph, "turtle")

    # Both terms survive. Counted with pyoxigraph, because rdflib's parser
    # merges them -- the very normalization the guard delegates around. This
    # path writes Turtle's integer shorthand (`01`, `1`) rather than the quoted
    # form deterministic_turtle uses, so assert on the terms, not the text.
    assert len(list(ox.parse(result, format=ox.RdfFormat.TURTLE))) == 2
