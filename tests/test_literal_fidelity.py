"""Regression tests for preserving RDF literal identity through serialization."""

from __future__ import annotations

import pyoxigraph as ox
import pytest
import rdflib
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

EX = Namespace("http://example.org/")


def _canonical_dataset(dataset: ox.Dataset) -> str:
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return "\n".join(
        sorted(str(ox.Triple(quad.subject, quad.predicate, quad.object)) for quad in dataset)
    )


def _canonical_graph(graph: Graph) -> str:
    return _canonical_dataset(
        ox.Dataset(ox.parse(graph.serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES))
    )


def _canonical_text(text: str, rdf_format: ox.RdfFormat) -> str:
    return _canonical_dataset(ox.Dataset(ox.parse(text, format=rdf_format)))


def _rdflib_graph(triples: list[ox.Triple]) -> Graph:
    """Rebuild an rdflib graph without normalizing typed lexical forms."""
    graph = Graph()

    def convert(term):
        if isinstance(term, ox.NamedNode):
            return URIRef(term.value)
        if isinstance(term, ox.BlankNode):
            return rdflib.BNode(term.value)
        if isinstance(term, ox.Literal):
            if term.language:
                return Literal(term.value, lang=term.language)
            return Literal(term.value, datatype=URIRef(term.datatype.value), normalize=False)
        raise TypeError(term)

    for triple in triples:
        graph.add((convert(triple.subject), convert(triple.predicate), convert(triple.object)))
    return graph


@pytest.mark.parametrize(
    "left,right",
    [
        (
            Literal("01", datatype=XSD.integer, normalize=False),
            Literal("1", datatype=XSD.integer, normalize=False),
        ),
        (
            Literal("1", datatype=XSD.boolean, normalize=False),
            Literal("true", datatype=XSD.boolean, normalize=False),
        ),
        (
            Literal("2020-01-01T00:00:00Z", datatype=XSD.dateTime, normalize=False),
            Literal("2020-01-01T00:00:00+00:00", datatype=XSD.dateTime, normalize=False),
        ),
        (
            Literal("-0.0", datatype=XSD.double, normalize=False),
            Literal("0.0", datatype=XSD.double, normalize=False),
        ),
    ],
    ids=["integer", "boolean", "dateTime", "signed-zero"],
)
def test_deterministic_turtle_preserves_distinct_lexical_forms(left: Literal, right: Literal) -> None:
    graph = Graph()
    graph.add((EX.s, EX.p, left))
    graph.add((EX.s, EX.p, right))

    result = deterministic_turtle(graph)

    assert len(graph) == 2
    assert _canonical_text(result, ox.RdfFormat.TURTLE) == _canonical_graph(graph)


def test_deterministic_turtle_preserves_full_double_precision() -> None:
    graph = Graph()
    graph.add((EX.s, EX.p, Literal(1.2345678901234567)))

    result = deterministic_turtle(graph)

    assert "1.2345678901234567" in result
    assert _canonical_text(result, ox.RdfFormat.TURTLE) == _canonical_graph(graph)


@pytest.mark.parametrize(
    "literal",
    [
        Literal("1.2300", datatype=XSD.decimal, normalize=False),
        Literal("not-an-integer", datatype=XSD.integer, normalize=False),
    ],
    ids=["decimal", "invalid-lexical-form"],
)
def test_deterministic_turtle_preserves_other_typed_lexical_forms(literal: Literal) -> None:
    graph = Graph()
    graph.add((EX.s, EX.p, literal))

    result = deterministic_turtle(graph)

    assert _canonical_text(result, ox.RdfFormat.TURTLE) == _canonical_graph(graph)


@pytest.mark.parametrize(
    ("output_format", "rdf_format"),
    [
        ("turtle", ox.RdfFormat.TURTLE),
        ("trig", ox.RdfFormat.TRIG),
        ("n3", ox.RdfFormat.N3),
    ],
)
def test_lower_level_turtle_family_preserves_literal_identity(
    output_format: str, rdf_format: ox.RdfFormat
) -> None:
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("01", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.p, Literal("1", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.boolean, Literal("1", datatype=XSD.boolean, normalize=False)))
    graph.add((EX.s, EX.boolean, Literal("true", datatype=XSD.boolean, normalize=False)))
    graph.add((EX.s, EX.decimal, Literal("1.2300", datatype=XSD.decimal, normalize=False)))
    graph.add(
        (EX.s, EX.when, Literal("2020-01-01T00:00:00Z", datatype=XSD.dateTime, normalize=False))
    )
    graph.add(
        (
            EX.s,
            EX.when,
            Literal("2020-01-01T00:00:00+00:00", datatype=XSD.dateTime, normalize=False),
        )
    )
    graph.add((EX.s, EX.precise, Literal(1.2345678901234567)))
    graph.add((EX.s, EX.zero, Literal("-0.0", datatype=XSD.double, normalize=False)))
    graph.add((EX.s, EX.zero, Literal("0.0", datatype=XSD.double, normalize=False)))
    graph.add((EX.s, EX.invalid, Literal("not-an-integer", datatype=XSD.integer, normalize=False)))

    result = canonicalize_rdf_graph(graph, output_format=output_format)

    assert _canonical_text(result, rdf_format) == _canonical_graph(graph)


def test_intentional_string_and_language_equivalences_remain_canonical() -> None:
    plain = Graph()
    plain.add((EX.s, EX.p, Literal("text")))
    typed = Graph()
    typed.add((EX.s, EX.p, Literal("text", datatype=XSD.string)))

    upper_language = Graph()
    upper_language.add((EX.s, EX.p, Literal("hello", lang="EN-us")))
    lower_language = Graph()
    lower_language.add((EX.s, EX.p, Literal("hello", lang="en-US")))

    assert deterministic_turtle(plain) == deterministic_turtle(typed)
    assert deterministic_turtle(upper_language) == deterministic_turtle(lower_language)


def test_deterministic_turtle_is_stable_after_lexical_preserving_reparse() -> None:
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("01", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.p, Literal("1", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.precise, Literal(1.2345678901234567)))

    once = deterministic_turtle(graph)
    parsed = list(ox.parse(once, format=ox.RdfFormat.TURTLE))
    twice = deterministic_turtle(_rdflib_graph(parsed))

    assert twice == once


def test_serialization_does_not_mutate_input_or_global_normalization() -> None:
    graph = Graph(base="http://example.org/base#")
    graph.add((EX.s, EX.p, Literal("01", datatype=XSD.integer, normalize=False)))
    before_triples = set(graph)
    before_base = graph.base
    before_normalize = rdflib.NORMALIZE_LITERALS

    deterministic_turtle(graph)

    assert set(graph) == before_triples
    assert graph.base == before_base
    assert rdflib.NORMALIZE_LITERALS is before_normalize
