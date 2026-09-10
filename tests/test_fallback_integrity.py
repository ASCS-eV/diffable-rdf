"""The fallback path must not corrupt, lose, or silently drop a graph.

Three defects lived here, all invisible to a green suite:

`str.splitlines()` was used to sort line-oriented output. It also breaks on the
Unicode line separators — U+2028, U+2029, U+0085, U+000B, U+000C, U+001C..E —
that N-Triples permits **raw** inside a quoted literal. One statement became
two "lines", they sorted independently, and the separator was rewritten as a
newline: the literal's value changed and the document no longer parsed.

`to_canonical_graph` returns a `ReadOnlyGraphAggregate`, a dataset container.
Handing it straight to rdflib's serializers made some of them emit an empty
document for a non-empty graph.

And rdflib's own errors reached callers raw, naming neither the format nor a
way forward.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph

EX = Namespace("http://example.org/")

# Characters str.splitlines() breaks on that a Turtle/N-Triples literal may
# carry raw. LF and CR are excluded: rdflib escapes those, and they are the
# only ones N-Triples forbids unescaped.
UNICODE_BREAKS = [
    pytest.param("\u2028", id="line-separator"),
    pytest.param("\u2029", id="paragraph-separator"),
    pytest.param("\u0085", id="next-line"),
    pytest.param("\v", id="vertical-tab"),
    pytest.param("\f", id="form-feed"),
    pytest.param("\x1c", id="file-separator"),
    pytest.param("\x1d", id="group-separator"),
    pytest.param("\x1e", id="record-separator"),
]

LINE_ORIENTED = ["nt", "ntriples", "n-triples", "nt11", "nquads", "n-quads"]


def _degraded(*extra) -> Graph:
    """A graph that reaches the fallback, with absolute IRIs throughout.

    A doubled ``#`` is an IRI rdflib accepts and pyoxigraph rejects, so it
    forces the fallback while every term stays absolute — which matters,
    because a relative IRI would make the line-oriented formats refuse before
    the sort is reached.
    """
    graph = Graph()
    graph.add((URIRef("http://example.org/a#b#c"), EX.p, Literal("forces fallback")))
    for triple in extra:
        graph.add(triple)
    return graph


@pytest.mark.parametrize("separator", UNICODE_BREAKS)
@pytest.mark.parametrize("output_format", LINE_ORIENTED)
def test_a_literal_carrying_a_unicode_line_break_survives(
    output_format: str, separator: str
) -> None:
    """The value must be preserved and the document must still parse."""
    value = Literal("a" + separator + "b")
    graph = _degraded((EX.s, EX.p, value))

    result = canonicalize_rdf_graph(graph, output_format=output_format)
    reparsed = Graph().parse(data=result, format="nt")

    assert len(reparsed) == len(graph)
    assert isomorphic(reparsed, graph)
    assert reparsed.value(EX.s, EX.p) == value


@pytest.mark.parametrize("output_format", LINE_ORIENTED)
def test_line_oriented_output_is_still_sorted(output_format: str) -> None:
    """The sort is the reason this code exists; it must still happen."""
    graph = _degraded(
        (EX.z, EX.p, Literal("last")),
        (EX.a, EX.p, Literal("first")),
        (EX.m, EX.p, Literal("middle")),
    )
    lines = [
        line
        for line in canonicalize_rdf_graph(graph, output_format=output_format).splitlines()
        if line.strip()
    ]

    assert lines == sorted(lines)
    assert len(lines) == len(graph)


def test_a_delegated_format_does_not_return_an_empty_document() -> None:
    """`hext` returned '' for a one-triple graph."""
    graph = Graph(bind_namespaces="none")
    graph.add((EX.s, EX.p, Literal("v")))

    result = canonicalize_rdf_graph(graph, "hext")

    assert result.strip(), "a non-empty graph must not serialize to nothing"
    assert "http://example.org/s" in result


def test_a_delegated_format_that_writes_nothing_is_refused_not_returned() -> None:
    """If a plugin ever does emit nothing, that must be an error, not output."""
    import diffable_rdf.canonicalize as module

    graph = Graph()
    graph.add((EX.s, EX.p, Literal("v")))

    original = Graph.serialize

    def empty(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return ""

    module.Graph.serialize = empty
    try:
        with pytest.raises(ValueError, match="empty document"):
            canonicalize_rdf_graph(graph, "longturtle")
    finally:
        module.Graph.serialize = original


def test_a_fallback_serializer_error_names_the_format_and_a_way_forward() -> None:
    """RDF/XML cannot express a literal predicate; the error must say so usefully."""
    graph = Graph()
    graph.bind("ex", EX)
    graph.addN([(EX.s, Literal("literal-predicate"), Literal("o"), graph)])

    with pytest.raises(ValueError) as raised:
        canonicalize_rdf_graph(graph, "xml")

    message = str(raised.value)
    assert "xml" in message
    assert "turtle" in message, "an alternative that works must be named"
    assert "Can't split" in message, "the underlying cause should stay visible"
    assert raised.value.__cause__ is not None, "the original error must be chained"


def test_an_unregistered_format_still_raises_rdflibs_own_error() -> None:
    """Wrapping must not swallow the documented PluginException."""
    from rdflib.plugin import PluginException

    with pytest.raises(PluginException):
        canonicalize_rdf_graph(_degraded(), "no-such-format")


def test_the_turtle_family_still_carries_a_degraded_graph() -> None:
    """The formats the error messages recommend have to actually work."""
    graph = _degraded((EX.s, EX.p, Literal("a" + "\u2028" + "b")))

    for output_format in ("turtle", "ttl", "trig", "n3"):
        result = canonicalize_rdf_graph(graph, output_format=output_format)
        reparsed = Graph().parse(data=result, format=output_format)
        assert isomorphic(reparsed, graph), output_format
