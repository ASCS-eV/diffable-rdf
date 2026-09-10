"""RDF literal identity contracts for serialization."""

from __future__ import annotations

from urllib.parse import urljoin

import pyoxigraph as ox
import pytest
import rdflib
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

EX = Namespace("http://example.org/")
FALLBACK_BASE = "https://consumer.example/base/"


def _boundary_literal_graph(subject: URIRef, line_ending: str) -> Graph:
    """Build literals whose terminal delimiters exercise Turtle quoting."""
    values = [
        line_ending + "\\" * backslashes + '"' * quotes
        for backslashes in range(4)
        for quotes in range(1, 5)
    ]
    values.extend(
        (
            "before" + line_ending + '"""' + "after",
            "terminal" + line_ending + "\\",
        )
    )

    graph = Graph()
    for index, value in enumerate(values):
        predicate = EX[f"boundary-{index}"]
        graph.add((subject, predicate, Literal(value)))
        graph.add((subject, predicate, Literal(value, datatype=EX.literal, normalize=False)))
        graph.add((subject, predicate, Literal(value, lang="en")))
    return graph


def _literal_identity(literal: Literal) -> tuple[str, str, str | None]:
    """Return the RDF literal fields compared by a Turtle reader."""
    if literal.language:
        datatype = RDF.langString
    else:
        datatype = literal.datatype or XSD.string
    return str(literal), str(datatype), literal.language


def _parsed_literal_identities(dataset: ox.Dataset) -> set[tuple[str, str, str | None]]:
    """Return lexical literal fields from an independently parsed dataset."""
    return {
        (quad.object.value, quad.object.datatype.value, quad.object.language)
        for quad in dataset
        if isinstance(quad.object, ox.Literal)
    }


def _assert_turtle_boundary_round_trip(
    graph: Graph,
    expected: Graph,
    serializer,
    rdf_format: ox.RdfFormat,
    *,
    base_iri: str | None = None,
    uses_long_strings: bool | None,
) -> None:
    """Check repeated public output with an independent Turtle-family reader."""
    before = set(graph)
    first = serializer(graph)
    second = serializer(graph)

    assert first == second
    assert set(graph) == before
    if uses_long_strings is not None:
        assert ('"""' in first) is uses_long_strings

    parsed = ox.Dataset(ox.parse(first, format=rdf_format, base_iri=base_iri))
    assert len(parsed) == len(expected)
    assert _parsed_literal_identities(parsed) == {
        _literal_identity(literal)
        for _, _, literal in expected
        if isinstance(literal, Literal)
    }
    assert _canonical_dataset(parsed) == _canonical_graph(expected)


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


def test_typed_literals_are_written_in_quoted_form() -> None:
    """Typed literals use quoted Turtle form.

    Quoted form preserves lexical presentation alongside RDF term fidelity. This
    test exists for the half the guard cannot see: the output form itself, which
    callers diff.
    """
    graph = Graph()
    graph.add((EX.s, EX.integer, Literal(42)))
    graph.add((EX.s, EX.boolean, Literal(True)))

    result = deterministic_turtle(graph)

    assert '"42"^^xsd:integer' in result
    assert '"true"^^xsd:boolean' in result
    assert " 42 " not in result and " true " not in result


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


@pytest.mark.parametrize(
    "line_ending",
    ["\n", "\r", "\r\n"],
    ids=["lf-long-string", "cr-short-string", "crlf-long-string"],
)
def test_deterministic_turtle_preserves_literal_quote_boundaries(line_ending: str) -> None:
    """Terminal quote runs retain their literal fields on the canonical path."""
    graph = _boundary_literal_graph(EX.subject, line_ending)

    _assert_turtle_boundary_round_trip(
        graph,
        graph,
        deterministic_turtle,
        ox.RdfFormat.TURTLE,
        uses_long_strings="\n" in line_ending,
    )


@pytest.mark.parametrize(
    "output_format,rdf_format",
    [
        ("turtle", ox.RdfFormat.TURTLE),
        ("ttl", ox.RdfFormat.TURTLE),
        ("trig", ox.RdfFormat.TRIG),
        ("n3", ox.RdfFormat.N3),
    ],
    ids=["turtle", "ttl", "trig", "n3"],
)
@pytest.mark.parametrize(
    "line_ending",
    ["\n", "\r", "\r\n"],
    ids=["lf-long-string", "cr-short-string", "crlf-long-string"],
)
def test_turtle_aliases_preserve_literal_quote_boundaries(
    output_format: str, rdf_format: ox.RdfFormat, line_ending: str
) -> None:
    """Every Turtle-family alias preserves literal terminal quote runs."""
    graph = _boundary_literal_graph(EX.subject, line_ending)

    _assert_turtle_boundary_round_trip(
        graph,
        graph,
        lambda source: canonicalize_rdf_graph(source, output_format=output_format),
        rdf_format,
        uses_long_strings=None,
    )


@pytest.mark.parametrize(
    "line_ending",
    ["\n", "\r", "\r\n"],
    ids=["lf-long-string", "cr-short-string", "crlf-long-string"],
)
def test_deterministic_turtle_fallback_preserves_literal_quote_boundaries(
    line_ending: str,
) -> None:
    """The relative-IRI fallback keeps literal terminal quote runs parseable."""
    subject = URIRef("relative/literal-subject")
    graph = _boundary_literal_graph(subject, line_ending)
    expected = _boundary_literal_graph(
        URIRef(urljoin(FALLBACK_BASE, str(subject))),
        line_ending,
    )

    _assert_turtle_boundary_round_trip(
        graph,
        expected,
        deterministic_turtle,
        ox.RdfFormat.TURTLE,
        base_iri=FALLBACK_BASE,
        uses_long_strings="\n" in line_ending,
    )


@pytest.mark.parametrize(
    "output_format,rdf_format",
    [
        ("turtle", ox.RdfFormat.TURTLE),
        ("ttl", ox.RdfFormat.TURTLE),
        ("trig", ox.RdfFormat.TRIG),
        ("n3", ox.RdfFormat.N3),
    ],
    ids=["turtle", "ttl", "trig", "n3"],
)
@pytest.mark.parametrize(
    "line_ending",
    ["\n", "\r", "\r\n"],
    ids=["lf-long-string", "cr-short-string", "crlf-long-string"],
)
def test_turtle_alias_fallbacks_preserve_literal_quote_boundaries(
    output_format: str, rdf_format: ox.RdfFormat, line_ending: str
) -> None:
    """Every Turtle-family fallback resolves relative subjects at the reader base."""
    subject = URIRef("relative/literal-subject")
    graph = _boundary_literal_graph(subject, line_ending)
    expected = _boundary_literal_graph(
        URIRef(urljoin(FALLBACK_BASE, str(subject))),
        line_ending,
    )

    _assert_turtle_boundary_round_trip(
        graph,
        expected,
        lambda source: canonicalize_rdf_graph(source, output_format=output_format),
        rdf_format,
        base_iri=FALLBACK_BASE,
        uses_long_strings="\n" in line_ending,
    )
