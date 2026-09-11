"""Base-IRI contracts for the rdflib fallback path.

Graphs that pyoxigraph refuses reach a plain rdflib serializer, which
relativizes by string prefix (``rdflib.serializer.Serializer.relativize``)
rather than by the component algorithm RFC 3986 section 5.2.2 defines and
Turtle section 6.3 requires. Carrying a base is therefore correct for some
bases and destructive for others, and RFC 3986 specifies only resolution --
never its inverse -- so the sole sound test is to resolve the output back.
"""

from __future__ import annotations

import logging

import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph

EX = Namespace("http://example.org/")
LOGGER_NAME = "diffable_rdf.canonicalize"

# A relative IRI is what forces the fallback: pyoxigraph rejects it because
# RDF 1.1 Concepts section 3.2 requires IRIs in the abstract syntax to be
# absolute, while rdflib accepts it.
FALLBACK_TRIGGER = URIRef("relative-term")


def _fallback_graph(base: str, subjects: list[str]) -> Graph:
    """Build a graph with the given base that pyoxigraph will refuse.

    :param base: The base IRI to attach to the graph.
    :param subjects: Subject IRIs, absolute or relative, to add.
    :return: A graph guaranteed to take the rdflib fallback path.
    """
    graph = Graph(base=base)
    for subject in subjects:
        graph.add((URIRef(subject), EX.p, Literal("v")))
    graph.add((FALLBACK_TRIGGER, EX.p, Literal("v")))
    return graph


def _absolute_terms(graph: Graph) -> set[str]:
    """Return every absolute IRI appearing anywhere in ``graph``.

    :param graph: The graph to read.
    :return: The set of absolute IRI strings.
    """
    return {
        str(term)
        for triple in graph
        for term in triple
        if isinstance(term, URIRef) and "://" in str(term)
    }


# Each case pairs a base with terms and states whether the base can be
# declared without changing any of them. The "drop" cases are the ones a
# shape heuristic would get wrong: rejecting only bases that end in "#"
# still corrupts the partial-segment and query cases.
PRESERVING_BASES = [
    pytest.param("http://example.org/d/", ["http://example.org/d/a", "http://example.org/d/b"], id="path-segment"),
    pytest.param("http://example.org/d/", ["a", "http://example.org/d/b"], id="path-segment-with-relative-term"),
    pytest.param("http://ex.org/", ["http://ex.org/x"], id="authority-only"),
    pytest.param("http://ex.org/d/", ["http://ex.org/d/"], id="term-equal-to-base"),
]
CORRUPTING_BASES = [
    pytest.param("http://ex.org/d#", ["http://ex.org/d#a", "http://ex.org/d#b"], id="fragment"),
    pytest.param("http://ex.org/a/b", ["http://ex.org/a/bc"], id="partial-segment"),
    pytest.param("http://ex.org/d?q=1", ["http://ex.org/d?q=1x"], id="query"),
    pytest.param("http://ex.org/d#", ["a", "http://ex.org/d#b"], id="fragment-with-relative-term"),
]


@pytest.mark.parametrize(("base", "subjects"), PRESERVING_BASES)
def test_a_preserving_base_is_declared(base: str, subjects: list[str]) -> None:
    """The fallback declares a base that does not change any term.

    A document holding relative references with no declared base is not
    self-describing (RFC 3986 section 5.1.4), so the base is kept wherever
    keeping it is safe.
    """
    graph = _fallback_graph(base, subjects)

    result = canonicalize_rdf_graph(graph, output_format="turtle")

    assert "@base" in result
    assert _absolute_terms(Graph().parse(data=result, format="turtle")) >= _absolute_terms(graph)


@pytest.mark.parametrize(("base", "subjects"), CORRUPTING_BASES)
def test_a_corrupting_base_is_dropped(base: str, subjects: list[str]) -> None:
    """The fallback drops a base whose declaration would change a term.

    rdflib's prefix-string relativization is not RFC 3986 section 5.2.2
    resolution, so under these bases it emits references that resolve to
    different IRIs than the ones it was given.
    """
    graph = _fallback_graph(base, subjects)

    result = canonicalize_rdf_graph(graph, output_format="turtle")

    assert "@base" not in result
    assert _absolute_terms(Graph().parse(data=result, format="turtle")) >= _absolute_terms(graph)


@pytest.mark.parametrize(("base", "subjects"), PRESERVING_BASES + CORRUPTING_BASES)
def test_every_absolute_term_survives_whatever_the_base(base: str, subjects: list[str]) -> None:
    """No base shape loses an absolute IRI, whichever branch is taken.

    This is the invariant the decision exists to protect; the presence or
    absence of the directive is only how it is achieved.
    """
    graph = _fallback_graph(base, subjects)

    result = canonicalize_rdf_graph(graph, output_format="turtle")

    assert _absolute_terms(Graph().parse(data=result, format="turtle")) >= _absolute_terms(graph)


@pytest.mark.parametrize(("base", "subjects"), CORRUPTING_BASES)
def test_dropping_a_base_names_the_term_it_would_have_lost(
    base: str, subjects: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    """Dropping a base reports which IRI forced the decision."""
    graph = _fallback_graph(base, subjects)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        canonicalize_rdf_graph(graph, output_format="turtle")

    messages = [record.getMessage() for record in caplog.records]
    dropped = [message for message in messages if "without the base directive" in message]
    assert len(dropped) == 1
    assert base in dropped[0]
    assert any(subject in dropped[0] for subject in subjects if "://" in subject)


@pytest.mark.parametrize(("base", "subjects"), PRESERVING_BASES)
def test_keeping_a_base_is_silent(
    base: str, subjects: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    """A base that preserves every term is kept without a warning."""
    graph = _fallback_graph(base, subjects)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        canonicalize_rdf_graph(graph, output_format="turtle")

    assert not [
        record.getMessage()
        for record in caplog.records
        if "without the base directive" in record.getMessage()
    ]


@pytest.mark.parametrize("output_format", ["turtle", "ttl", "trig", "n3", "xml"])
def test_the_base_decision_holds_across_formats(output_format: str) -> None:
    """Every format that can declare a base keeps the graph's terms."""
    preserving = _fallback_graph("http://example.org/d/", ["http://example.org/d/a"])
    corrupting = _fallback_graph("http://ex.org/d#", ["http://ex.org/d#a"])

    for graph in (preserving, corrupting):
        result = canonicalize_rdf_graph(graph, output_format=output_format)
        parser = "xml" if output_format == "xml" else "turtle"
        assert _absolute_terms(Graph().parse(data=result, format=parser)) >= _absolute_terms(graph)


@pytest.mark.parametrize("output_format", ["nt", "ntriples", "nquads"])
def test_line_oriented_output_never_declares_a_base(output_format: str) -> None:
    """N-Triples and N-Quads have no base directive to declare.

    Their grammars (N-Triples 1.1 section 2.2) admit only absolute IRIs, so a
    base is neither expressible nor needed. rdflib warns and ignores one; it
    is never offered.
    """
    graph = Graph(base="http://example.org/d/")
    graph.add((URIRef("http://example.org/d/a"), EX.p, Literal("v")))
    graph.add((URIRef("http://example.org/d/b"), URIRef("literal-predicate-forces-fallback"), Literal("v")))

    with pytest.raises(ValueError, match="not an absolute IRI"):
        canonicalize_rdf_graph(graph, output_format=output_format)


@pytest.mark.parametrize(
    "base",
    [
        pytest.param("http://ex.org/a b/", id="space"),
        pytest.param("http://ex.org/x{y}/", id="braces"),
        pytest.param('http://ex.org/a"b/', id="quote"),
        pytest.param("not a base at all", id="not-an-iri"),
    ],
)
def test_a_base_that_is_not_a_valid_iri_is_never_declared(base: str) -> None:
    """An unwritable base is dropped rather than emitted as invalid syntax.

    rdflib stores whatever base string it is handed. Turtle section 6.5 admits
    no space, brace or quote inside an ``IRIREF``, so declaring such a base
    yields a document a strict parser rejects outright -- strictly worse than
    the relativization the directive was meant to support.
    """
    graph = Graph(base=base)
    graph.add((URIRef("http://ex.org/keepme"), EX.p, Literal("v")))
    graph.add((FALLBACK_TRIGGER, EX.p, Literal("v")))

    result = canonicalize_rdf_graph(graph, output_format="turtle")

    assert "@base" not in result
    assert "http://ex.org/keepme" in _absolute_terms(Graph().parse(data=result, format="turtle"))


def test_an_invalid_base_says_why_it_was_dropped(caplog: pytest.LogCaptureFixture) -> None:
    """Dropping an unwritable base reports the base that could not be used."""
    graph = Graph(base="http://ex.org/a b/")
    graph.add((URIRef("http://ex.org/keepme"), EX.p, Literal("v")))
    graph.add((FALLBACK_TRIGGER, EX.p, Literal("v")))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        canonicalize_rdf_graph(graph, output_format="turtle")

    assert [
        record.getMessage()
        for record in caplog.records
        if "is not a valid absolute IRI" in record.getMessage()
    ]


def test_a_declared_base_makes_the_document_independent_of_where_it_is_read() -> None:
    """A carried base fixes resolution inside the document, not at the reader.

    RFC 3986 section 5.1.1 ranks a base embedded in the content above the
    retrieval URI of section 5.1.3. Reading the same bytes from two different
    locations must therefore yield the same graph -- otherwise the reader's
    own location becomes part of the graph's meaning.
    """
    graph = _fallback_graph("http://example.org/d/", ["a", "http://example.org/d/b"])

    result = canonicalize_rdf_graph(graph, output_format="turtle")
    assert "@base" in result

    here = Graph().parse(data=result, format="turtle", publicID="http://reader-one.example/somewhere/")
    there = Graph().parse(data=result, format="turtle", publicID="file:///a/totally/different/place/")

    assert isomorphic(here, there)
    assert {str(term) for triple in here for term in triple} == {
        str(term) for triple in there for term in triple
    }


def test_without_a_declared_base_the_reader_location_leaks_in() -> None:
    """Establish that the guarantee above is not vacuous.

    When a base cannot be declared -- here because keeping it would lose
    ``http://ex.org/d#b`` -- any relative reference left in the document
    resolves against wherever it happens to be read from. There is no correct
    answer for such a graph: it holds relative IRIs, which RDF 1.1 Concepts
    section 3.2 places outside the abstract syntax. Preserving the absolute
    terms is the choice made, and this records its cost.
    """
    graph = _fallback_graph("http://ex.org/d#", ["a", "http://ex.org/d#b"])

    result = canonicalize_rdf_graph(graph, output_format="turtle")
    assert "@base" not in result

    here = Graph().parse(data=result, format="turtle", publicID="http://reader-one.example/somewhere/")
    there = Graph().parse(data=result, format="turtle", publicID="file:///a/totally/different/place/")

    assert not isomorphic(here, there)
    # The terms that RDF actually defines are identical in both readings.
    assert _absolute_terms(here) >= _absolute_terms(graph)
    assert _absolute_terms(there) >= _absolute_terms(graph)
