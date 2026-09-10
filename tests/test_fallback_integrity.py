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
from diffable_rdf.canonicalize import _deterministic_fallback_serialize

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


# Two ways to reach the fallback. Both are terms rdflib accepts and pyoxigraph
# rejects, which is what the fallback exists for.
RELATIVE_IRI = URIRef("relative/thing")
DOUBLED_FRAGMENT_IRI = URIRef("http://example.org/a#b#c")


def _degraded(*extra, trigger: URIRef = RELATIVE_IRI) -> Graph:
    """A graph that reaches the fallback rather than the pyoxigraph path."""
    graph = Graph()
    graph.add((trigger, EX.p, Literal("forces fallback")))
    for triple in extra:
        graph.add(triple)
    return graph


# The line-oriented sort is exercised directly rather than through
# `canonicalize_rdf_graph`, because no graph can currently reach it that way:
# a graph takes the fallback only by holding a term N-Triples cannot express,
# and the representability guard refuses those first. Verified for every
# trigger there is -- relative IRI, literal predicate, blank-node predicate,
# and IRIs pyoxigraph rejects (a doubled fragment, a bad percent-escape, a bad
# host). That guard is defence in depth, not a reason to leave the sort broken:
# it is one `_FORMAT_MAP` entry away from being reachable again.
@pytest.mark.parametrize("separator", UNICODE_BREAKS)
@pytest.mark.parametrize("output_format", ["nt", "nquads"])
def test_the_line_sort_preserves_a_literal_carrying_a_unicode_break(
    output_format: str, separator: str
) -> None:
    """`str.splitlines()` split the statement in two and rewrote the separator."""
    value = Literal("a" + separator + "b")
    graph = Graph()
    graph.add((EX.s, EX.p, value))
    graph.add((EX.z, EX.p, Literal("second statement, so the sort has work to do")))

    result = _deterministic_fallback_serialize(graph, output_format)
    reparsed = Graph().parse(data=result, format="nt")

    assert len(reparsed) == len(graph)
    assert isomorphic(reparsed, graph)
    assert reparsed.value(EX.s, EX.p) == value
    assert separator in result, "the separator must survive verbatim"


@pytest.mark.parametrize("output_format", ["nt", "nquads"])
def test_the_line_sort_still_sorts(output_format: str) -> None:
    """The sort is the reason this code exists; it must still happen."""
    graph = Graph()
    for name in ("z", "a", "m"):
        graph.add((EX[name], EX.p, Literal(name)))

    lines = [
        line for line in _deterministic_fallback_serialize(graph, output_format).split("\n")
        if line.strip()
    ]

    assert lines == sorted(lines)
    assert len(lines) == len(graph)


@pytest.mark.parametrize("output_format", LINE_ORIENTED)
def test_the_public_path_refuses_a_degraded_graph_for_line_formats(
    output_format: str,
) -> None:
    """Why the sort is unreachable from outside: the guard gets there first."""
    with pytest.raises(ValueError, match="absolute IRI"):
        canonicalize_rdf_graph(_degraded(), output_format=output_format)


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
    """The formats the error messages recommend have to actually work.

    The trigger here is the doubled fragment rather than the relative IRI: a
    relative IRI is resolved against the reader's base, so re-parsing bare
    text cannot reproduce the source term for any format, which is a property
    of relative IRIs and not of this code.
    """
    graph = _degraded((EX.s, EX.p, Literal("a\u2028b")), trigger=DOUBLED_FRAGMENT_IRI)

    for output_format in ("turtle", "ttl", "trig", "n3"):
        result = canonicalize_rdf_graph(graph, output_format=output_format)
        reparsed = Graph().parse(data=result, format=output_format)
        assert isomorphic(reparsed, graph), output_format
