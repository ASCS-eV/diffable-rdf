"""The trailing-dot CURIE repair must not reach into string literals.

pyoxigraph writes ``prefix:local\\.`` for an IRI whose local part ends in a dot,
which Turtle's PN_LOCAL_ESC production permits and rdflib's notation3 parser
rejects. The repair rewrites such CURIEs to full ``<IRI>`` form so the output
round-trips. Applied over the whole document it also matched inside string
literals, corrupting the value and producing text that would not parse -- which
the round-trip guard then reported as a refusal of a valid graph.

The rewrite now skips literals. These tests cover the scanner that decides
where a literal is, because that is the part with edge cases.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal, Namespace
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle
from diffable_rdf.canonicalize import _expand_trailing_dot_curies, _turtle_string_spans

EX = Namespace("http://example.org/")
DOTTED = Namespace("https://w3id.org/biolink/vocab/")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('a "b" c', ['"b"']),
        ("a 'b' c", ["'b'"]),
        ('a """b""" c', ['"""b"""']),
        ("a '''b''' c", ["'''b'''"]),
        # An escaped delimiter does not end the literal.
        (r'a "b\"c" d', [r'"b\"c"']),
        # A backslash before the closing delimiter is itself escaped.
        (r'a "b\\" d', [r'"b\\"']),
        # A quote of the other kind inside is ordinary text.
        ('a "b\'c" d', ['"b\'c"']),
        # A single quote inside a triple-quoted literal is ordinary text.
        ('a """b"c""" d', ['"""b"c"""']),
        # Two literals in one line are two spans.
        ('"x" p "y"', ['"x"', '"y"']),
        # An IRI cannot open a span: IRIREF forbids an unescaped quote.
        ("<http://ex/a> <http://ex/p> <http://ex/b>", []),
        ("no literals here", []),
    ],
)
def test_the_literal_scanner_finds_exactly_the_string_spans(text: str, expected: list[str]) -> None:
    """The scanner is what keeps the rewrite out of data, so pin its edges."""
    assert [text[start:end] for start, end in _turtle_string_spans(text)] == expected


def test_a_curie_outside_a_literal_is_still_rewritten() -> None:
    """The repair must keep working; skipping literals is not skipping everything."""
    prefixes = {"ex": "http://example.org/"}
    text = 'ex:thing\\. ex:p "value" .\n'

    # The escaped dot is part of the local name, so it survives unescaped
    # inside the angle brackets.
    assert _expand_trailing_dot_curies(text, prefixes).startswith(
        "<http://example.org/thing.> "
    )


def test_a_curie_inside_a_literal_is_left_alone() -> None:
    """The defect, at the level of the function that had it."""
    prefixes = {"ex": "http://example.org/"}
    text = 'ex:s ex:p "ex:thing\\. text" .\n'

    assert _expand_trailing_dot_curies(text, prefixes) == text


def test_both_in_one_document() -> None:
    """A rewrite outside a literal and no rewrite inside, in the same text."""
    prefixes = {"ex": "http://example.org/"}
    text = 'ex:thing\\. ex:p "ex:other\\. text" .\n'
    result = _expand_trailing_dot_curies(text, prefixes)

    assert result.startswith("<http://example.org/thing.> ")
    assert '"ex:other\\. text"' in result


@pytest.mark.parametrize("output_format", ["turtle", "n3", "trig"])
def test_a_graph_whose_literal_looks_like_a_curie_serializes(output_format: str) -> None:
    """End to end: a valid graph that used to be refused for all three formats."""
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("ex:thing\\. ")))
    graph.add((EX.other, EX.p, EX.o))

    result = canonicalize_rdf_graph(graph, output_format=output_format)
    reparsed = Graph().parse(data=result, format=output_format)

    assert isomorphic(reparsed, graph)
    assert reparsed.value(EX.s, EX.p) == Literal("ex:thing\\. ")


def test_a_trailing_dot_iri_still_round_trips_and_keeps_sibling_prefixes() -> None:
    """The case the repair exists for, and the compactness it preserves."""
    graph = Graph()
    graph.bind("biolink", DOTTED)
    graph.add((DOTTED["StrandEnum#."], EX.p, Literal("dotted")))
    graph.add((DOTTED["Normal"], EX.p, Literal("plain")))

    result = canonicalize_rdf_graph(graph, output_format="turtle")

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)
    # The dotted IRI is written in full...
    assert "<https://w3id.org/biolink/vocab/StrandEnum#.>" in result
    # ...while its sibling keeps the prefix, which dropping the binding would lose.
    assert "biolink:Normal" in result


def test_a_dotted_iri_and_a_curie_like_literal_together() -> None:
    """The combination: one must be rewritten, the other must not."""
    graph = Graph()
    graph.bind("biolink", DOTTED)
    graph.add((DOTTED["StrandEnum#."], EX.p, Literal("biolink:StrandEnum#\\. ")))

    result = canonicalize_rdf_graph(graph, output_format="turtle")
    reparsed = Graph().parse(data=result, format="turtle")

    assert isomorphic(reparsed, graph)
    assert reparsed.value(DOTTED["StrandEnum#."], EX.p) == Literal("biolink:StrandEnum#\\. ")


def test_deterministic_turtle_is_unaffected() -> None:
    """It renders through rdflib and never applied this rewrite; keep it that way."""
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("ex:thing\\. ")))

    result = deterministic_turtle(graph)

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


def test_a_multiline_literal_containing_a_curie_is_left_alone() -> None:
    """Triple-quoted literals span newlines, so the scanner must too."""
    prefixes = {"ex": "http://example.org/"}
    text = 'ex:s ex:p """line one\nex:thing\\. line two""" .\n'

    assert _expand_trailing_dot_curies(text, prefixes) == text
