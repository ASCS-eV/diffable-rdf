"""Capability boundaries of the RDF dependency serializers.

These tests exercise only dependency APIs. They define the serializer
properties that require this package's deterministic and lossless adapters.
"""

from __future__ import annotations

import io

import pyoxigraph as ox
from rdflib import BNode, Graph, Literal, Namespace, RDF
from rdflib.compare import isomorphic

EX = Namespace("http://example.org/")

# An N-Triples escape decodes to one carriage return in the literal value.
CR_NTRIPLES = '<http://example.org/s> <http://example.org/p> "a\\rb" .\n'


def _shared_tail_graph() -> Graph:
    """Build two RDF list heads that share one tail cell."""
    graph = Graph()
    tail = BNode()
    head = BNode()
    graph.add((tail, RDF.first, Literal("shared")))
    graph.add((tail, RDF.rest, RDF.nil))
    graph.add((head, RDF.first, Literal("head")))
    graph.add((head, RDF.rest, tail))
    graph.add((EX.a, EX.items, head))
    graph.add((EX.b, EX.items, tail))
    return graph


def test_rdflib_jsonld_serializer_does_not_preserve_shared_list_tail() -> None:
    """RDFLib JSON-LD list compaction does not preserve a shared tail."""
    graph = _shared_tail_graph()
    serialized = graph.serialize(format="json-ld")
    reparsed = Graph().parse(data=serialized, format="json-ld")

    assert not isomorphic(graph, reparsed), (
        "RDFLib JSON-LD serialization preserved a shared RDF list tail. "
        "Reassess the adapter boundary before selecting this serializer for shared-list graphs. "
        f"Input has {len(graph)} triples; round-tripped output has {len(reparsed)}."
    )
    assert len(reparsed) > len(graph), "shared-tail list compaction duplicates RDF list triples"
    assert "@list" in serialized


def test_pyoxigraph_rdf_xml_emits_raw_carriage_return() -> None:
    """Pyoxigraph RDF/XML writes a literal carriage return as a raw character."""
    quads = ox.parse(io.BytesIO(CR_NTRIPLES.encode("utf-8")), format=ox.RdfFormat.N_TRIPLES)
    serialized = ox.serialize(quads, format=ox.RdfFormat.RDF_XML).decode("utf-8")

    assert "\r" in serialized, (
        "Pyoxigraph RDF/XML escaped the literal carriage return. "
        "Reassess the RDF/XML output normalization boundary."
    )
    value = str(next(iter(Graph().parse(data=serialized, format="xml")))[2])
    assert value == "a\nb", "an XML parser normalizes the raw carriage return to a line feed"
