"""Base-IRI contracts for RDF terms read by standard format parsers.

RFC 3986 section 5.2.2 resolves `<#a>` against `http://ex.org/d#` as
`http://ex.org/d#a`. Format parsers must preserve those graph terms without
introducing an additional fragment separator.
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
def test_a_fragment_base_preserves_the_terms(output_format: str) -> None:
    """A fragment base preserves each IRI term in every verified format."""
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


def test_deterministic_turtle_preserves_fragment_base_terms() -> None:
    """Deterministic Turtle preserves terms from a graph with a fragment base."""
    graph = _hash_base_graph()

    result = deterministic_turtle(graph)

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


def test_deterministic_turtle_preserves_hash_path_and_slash_bases() -> None:
    """Hash, path, and slash bases preserve all graph terms."""
    for base in ("http://example.org/d#", "http://example.org/d", "http://example.org/d/"):
        graph = Graph(base=base)
        graph.add((URIRef("http://example.org/d#a"), EX.pred, Literal("v0")))
        graph.add((URIRef("http://example.org/d#b"), EX.pred, Literal("v1")))
        result = deterministic_turtle(graph)
        assert isomorphic(Graph().parse(data=result, format="turtle"), graph), base


def test_canonicalize_rdf_graph_handles_a_relative_base() -> None:
    """A relative RDFLib base produces a complete Turtle document."""
    graph = Graph(base="book/")
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("v")))
    assert "http://example.org/s" in canonicalize_rdf_graph(graph, output_format="turtle")


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
    """The serializer reports that it omits a fragment base."""
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
    """Round-trip validation rejects output containing an absent IRI."""
    graph = Graph()
    graph.add((URIRef("http://example.org/s"), URIRef("http://example.org/p"), Literal("v")))

    with pytest.raises(ValueError, match="does not round-trip"):
        canonicalize_module._assert_round_trips(
            graph,
            "<http://example.org/s> <http://example.org/p> <http://example.org/INVENTED> .\n",
            "nt",
        )


def test_the_guard_tolerates_rdflibs_literal_normalization() -> None:
    """Round-trip validation accepts RDFLib integer lexical normalization."""
    from rdflib.namespace import XSD

    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("01", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.p, Literal("1", datatype=XSD.integer, normalize=False)))

    result = canonicalize_rdf_graph(graph, "turtle")

    # Pyoxigraph preserves both lexical terms while RDFLib normalizes them.
    assert len(list(ox.parse(result, format=ox.RdfFormat.TURTLE))) == 2
