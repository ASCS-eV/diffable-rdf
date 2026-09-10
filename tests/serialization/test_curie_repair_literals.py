"""The trailing-dot CURIE repair must not reach into string literals.

pyoxigraph writes ``prefix:local\\.`` for an IRI whose local part ends in a dot,
which Turtle's PN_LOCAL_ESC production permits and rdflib's notation3 parser
rejects. The repair rewrites such CURIEs to full ``<IRI>`` form so the output
round-trips while preserving string-literal values.

The scanner protects literal and IRIREF spans before rewriting CURIE tokens.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal, Namespace
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle
from diffable_rdf.canonicalize import _expand_trailing_dot_curies, _turtle_protected_spans

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
        # An IRIREF is protected too, and for a reason: production [18]
        # excludes '"' but permits "'", so IRIREF spans protect apostrophes.
        (
            "<http://ex/a> <http://ex/p> <http://ex/b>",
            ["<http://ex/a>", "<http://ex/p>", "<http://ex/b>"],
        ),
        ("<http://ex/a'b> <http://ex/p> \"v\"", ["<http://ex/a'b>", "<http://ex/p>", '"v"']),
        ('"a<b" <http://ex/p>', ['"a<b"', "<http://ex/p>"]),
        ("<http://ex/a> \"lit'eral\" <http://ex/b>", ["<http://ex/a>", '"lit\'eral"', "<http://ex/b>"]),
        # An RDF-star quoted triple is a delimiter, not an IRIREF.
        (
            "<<<http://ex/s> <http://ex/p> <http://ex/o>>> <http://ex/q> \"v\"",
            ["<http://ex/s>", "<http://ex/p>", "<http://ex/o>", "<http://ex/q>", '"v"'],
        ),
        # Unterminated: protect the remainder rather than guess.
        ("<http://ex/unterminated", ["<http://ex/unterminated"]),
        ("no literals here", []),
    ],
)
def test_the_token_scanner_finds_exactly_the_protected_spans(text: str, expected: list[str]) -> None:
    """The scanner is what keeps the rewrite out of data, so pin its edges."""
    assert [text[start:end] for start, end in _turtle_protected_spans(text)] == expected


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
    """Literal spans remain unchanged by CURIE rewriting."""
    prefixes = {"ex": "http://example.org/"}
    text = 'ex:s ex:p "ex:thing\\. text" .\n'

    assert _expand_trailing_dot_curies(text, prefixes) == text


def test_a_literal_that_looks_like_a_trailing_dot_curie_serializes_intact() -> None:
    """Turtle CURIE repair leaves literal lexical values unchanged."""
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("see ex:thing\\. more")))
    graph.add((EX.other, EX.p, EX.o))
    result = canonicalize_rdf_graph(graph, output_format="turtle")
    reparsed = Graph().parse(data=result, format="turtle")
    assert isomorphic(reparsed, graph)
    assert reparsed.value(EX.s, EX.p) == Literal("see ex:thing\\. more")
    assert "ex:other" in result


def test_both_in_one_document() -> None:
    """A rewrite outside a literal and no rewrite inside, in the same text."""
    prefixes = {"ex": "http://example.org/"}
    text = 'ex:thing\\. ex:p "ex:other\\. text" .\n'
    result = _expand_trailing_dot_curies(text, prefixes)

    assert result.startswith("<http://example.org/thing.> ")
    assert '"ex:other\\. text"' in result


@pytest.mark.parametrize("output_format", ["turtle", "n3", "trig"])
def test_a_graph_whose_literal_looks_like_a_curie_serializes(output_format: str) -> None:
    """A CURIE-like literal round-trips in each Turtle-family format."""
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


def test_deterministic_turtle_preserves_curie_like_literal_values() -> None:
    """Deterministic Turtle preserves CURIE-like literal values."""
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


def test_an_apostrophe_in_an_iri_does_not_break_the_dot_repair() -> None:
    """IRIREF spans accept apostrophes permitted by RFC 3987."""
    graph = Graph()
    graph.bind("dotted", DOTTED)
    graph.add((EX["a'b"], EX.p, Literal("x")))
    graph.add((EX.z, EX.p, DOTTED["StrandEnum#."]))

    for output_format in ("turtle", "trig", "n3"):
        result = canonicalize_rdf_graph(graph, output_format=output_format)
        assert isomorphic(Graph().parse(data=result, format=output_format), graph), output_format

    assert isomorphic(Graph().parse(data=deterministic_turtle(graph), format="turtle"), graph)


def test_an_apostrophe_in_a_literal_still_shields_a_curie_lookalike() -> None:
    """The reason the scanner exists at all must keep working."""
    graph = Graph()
    graph.bind("dotted", DOTTED)
    graph.add((EX.s, EX.p, Literal("dotted:it's\\. not a curie")))
    graph.add((EX.z, EX.p, DOTTED["StrandEnum#."]))

    result = canonicalize_rdf_graph(graph, output_format="turtle")

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)
    assert graph.value(EX.s, EX.p) == Graph().parse(data=result, format="turtle").value(EX.s, EX.p)
