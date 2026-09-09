"""Every public serializer ends its output with exactly one newline.

Serializers disagree: pyoxigraph's RDF/XML writer ends without a newline while
its Turtle writer ends with one, and rdflib's Turtle writer -- reached on the
degraded path -- ends with two. A file with no final newline shows up in a diff
as "\\ No newline at end of file", and many tools add one, which then reads as a
spurious change the next time the artifact is regenerated. For a library whose
purpose is RDF that diffs cleanly, that is the wrong byte to leave to chance.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal, Namespace, URIRef

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle
from diffable_rdf.canonicalize import _FORMAT_MAP

EX = Namespace("http://example.org/")


def _graph() -> Graph:
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("v")))
    return graph


def _degraded_graph() -> Graph:
    """A relative IRI forces the rdflib fallback, whose writers differ again."""
    graph = _graph()
    graph.add((URIRef("relative/thing"), EX.p, Literal("forces fallback")))
    return graph


def _trailing_newlines(text: str) -> int:
    return len(text) - len(text.rstrip("\n"))


@pytest.mark.parametrize("output_format", sorted(_FORMAT_MAP))
def test_every_mapped_format_ends_with_exactly_one_newline(output_format: str) -> None:
    """Parametrized over ``_FORMAT_MAP`` so a format added later inherits this."""
    assert _trailing_newlines(canonicalize_rdf_graph(_graph(), output_format)) == 1


@pytest.mark.parametrize("output_format", sorted(_FORMAT_MAP))
def test_the_degraded_path_ends_with_exactly_one_newline(output_format: str) -> None:
    """The fallback uses rdflib's writers, which end Turtle output with two."""
    assert _trailing_newlines(canonicalize_rdf_graph(_degraded_graph(), output_format)) == 1


def test_deterministic_turtle_ends_with_exactly_one_newline() -> None:
    assert _trailing_newlines(deterministic_turtle(_graph())) == 1


def test_deterministic_turtle_ends_with_exactly_one_newline_when_degraded() -> None:
    assert _trailing_newlines(deterministic_turtle(_degraded_graph())) == 1


@pytest.mark.parametrize("output_format", sorted(_FORMAT_MAP))
def test_normalising_the_newline_does_not_add_a_blank_line(output_format: str) -> None:
    """One trailing newline, not a trailing blank line."""
    result = canonicalize_rdf_graph(_graph(), output_format)

    assert not result.endswith("\n\n")
    assert result.splitlines()[-1].strip(), "the last line must carry content"


def test_an_empty_graph_stays_an_empty_document() -> None:
    """Normalising must not turn nothing into a lone newline.

    Turtle and N-Triples both write nothing for an empty graph, and an empty
    document is valid in both. JSON-LD writes an empty array, which is content
    and therefore does get its newline.
    """
    assert canonicalize_rdf_graph(Graph(), "turtle") == ""
    assert canonicalize_rdf_graph(Graph(), "nt") == ""
    assert deterministic_turtle(Graph()) == ""
    assert canonicalize_rdf_graph(Graph(), "json-ld") == "[]\n"


def test_rdf_xml_output_still_parses_after_the_added_newline() -> None:
    """RDF/XML is the format that gained a byte; it must still be valid."""
    result = canonicalize_rdf_graph(_graph(), "xml")

    assert result.endswith("</rdf:RDF>\n")
    assert len(Graph().parse(data=result, format="xml")) == 1
