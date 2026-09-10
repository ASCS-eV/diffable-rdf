"""RDF list topology contracts for serialization."""

from __future__ import annotations

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

EX = Namespace("http://example.org/")

SHARED_TAIL_TURTLE = """
@prefix ex: <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
_:t rdf:first "z" ; rdf:rest rdf:nil .
_:a rdf:first "a" ; rdf:rest _:t .
_:b rdf:first "b" ; rdf:rest _:t .
ex:s1 ex:items _:a .
ex:s2 ex:items _:b .
"""


def test_degraded_turtle_is_lossless_for_shared_list_tails() -> None:
    """Degraded Turtle keeps shared RDF list cells connected."""
    graph = Graph()
    graph.parse(data=SHARED_TAIL_TURTLE, format="turtle")
    graph.add((URIRef("relative/thing"), EX.p, Literal("v")))

    result = deterministic_turtle(graph)
    reparsed = Graph().parse(data=result, format="turtle")
    defined = {subject for subject in reparsed.subjects() if isinstance(subject, BNode)}
    referenced = {obj for obj in reparsed.objects() if isinstance(obj, BNode)}

    assert not (referenced - defined), f"{len(referenced - defined)} dangling blank-node references"
    assert len(reparsed) == len(graph), f"{len(graph)} triples in, {len(reparsed)} out"
    assert "( " not in result, "degraded Turtle uses explicit RDF list triples"


def test_json_ld_is_lossless_for_shared_list_tails() -> None:
    """Expanded JSON-LD preserves shared RDF list cells."""
    graph = Graph()
    graph.parse(data=SHARED_TAIL_TURTLE, format="turtle")

    result = canonicalize_rdf_graph(graph, output_format="json-ld")
    reparsed = Graph().parse(data=result, format="json-ld")

    assert len(reparsed) == len(graph), f"{len(graph)} triples in, {len(reparsed)} out"
    assert isomorphic(reparsed, graph), "JSON-LD output is not isomorphic to the input"
    assert "@list" not in result, "expanded JSON-LD does not use list compaction"


def test_degraded_n3_is_lossless_for_shared_list_tails() -> None:
    """Degraded N3 preserves shared RDF list cells with explicit triples."""
    rdf_first = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
    graph = Graph()
    graph.parse(data=SHARED_TAIL_TURTLE, format="turtle")
    graph.add((URIRef("relative/thing"), EX.p, Literal("v")))

    result = canonicalize_rdf_graph(graph, output_format="n3")
    reparsed = Graph().parse(data=result, format="n3")
    cells_in = len(list(graph.triples((None, rdf_first, None))))
    cells_out = len(list(reparsed.triples((None, rdf_first, None))))

    assert cells_out == cells_in, f"{cells_in} rdf:first cells in, {cells_out} out"
    assert len(reparsed) == len(graph), f"{len(graph)} triples in, {len(reparsed)} out"
    assert "( " not in result, "degraded N3 uses explicit RDF list triples"
