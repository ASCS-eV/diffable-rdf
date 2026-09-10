"""Non-finite numeric literals retain their lexical RDF identity.

RDF numeric lexical forms include ``NaN`` and infinities. These tests cover
the local rendering and deterministic term ordering required for those values.
"""

from __future__ import annotations

import pyoxigraph as ox
import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import XSD

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

EX = Namespace("http://example.org/")

NON_FINITE = [
    pytest.param(Literal(float("nan")), id="python-nan"),
    pytest.param(Literal(float("inf")), id="python-inf"),
    pytest.param(Literal(float("-inf")), id="python-neg-inf"),
    pytest.param(Literal("NaN", datatype=XSD.double), id="double-NaN"),
    pytest.param(Literal("INF", datatype=XSD.double), id="double-INF"),
    pytest.param(Literal("-INF", datatype=XSD.double), id="double-neg-INF"),
    pytest.param(Literal("NaN", datatype=XSD.float), id="float-NaN"),
    pytest.param(Literal("INF", datatype=XSD.float), id="float-INF"),
]


@pytest.mark.parametrize("value", NON_FINITE)
def test_deterministic_turtle_serializes_a_non_finite_number(value: Literal) -> None:
    """Each non-finite numeric literal round-trips through Turtle."""
    graph = Graph()
    graph.add((EX.s, EX.p, value))

    result = deterministic_turtle(graph)

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


@pytest.mark.parametrize("value", NON_FINITE)
def test_the_lexical_form_the_graph_holds_is_what_is_written(value: Literal) -> None:
    """The point of rendering locally: write the term, not a re-spelling of it.

    Note what this means for `Literal(float("nan"))`: rdflib stores the Python
    repr `nan`, which is *not* in `xsd:double`'s lexical space, so the literal
    is ill-typed. RDF 1.1 permits that — an ill-typed literal is still a legal
    literal with no value — and preserving it is this library's contract.
    Silently rewriting it to `NaN` would change the term.
    """
    graph = Graph()
    graph.add((EX.s, EX.p, value))

    result = deterministic_turtle(graph)

    assert f'"{value}"' in result, result
    reparsed = Graph().parse(data=result, format="turtle")
    assert str(reparsed.value(EX.s, EX.p)) == str(value)


@pytest.mark.parametrize("value", NON_FINITE)
def test_both_entry_points_agree_on_a_non_finite_number(value: Literal) -> None:
    """Both public Turtle entry points produce isomorphic graphs."""
    graph = Graph()
    graph.add((EX.s, EX.p, value))

    assert isomorphic(
        Graph().parse(data=deterministic_turtle(graph), format="turtle"),
        Graph().parse(data=canonicalize_rdf_graph(graph, "turtle"), format="turtle"),
    )


def test_a_non_finite_number_beside_a_decimal_does_not_raise() -> None:
    """Mixed non-finite and decimal literals have a total output order."""
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("NaN", datatype=XSD.double)))
    graph.add((EX.s, EX.p, Literal("1.5", datatype=XSD.decimal)))

    result = deterministic_turtle(graph)

    assert len(Graph().parse(data=result, format="turtle")) == 2


def test_the_object_order_is_total_for_value_tied_and_mixed_terms() -> None:
    """A total order is what makes the output reproducible.

    rdflib's comparator ties distinct terms with equal values, leaving their
    order to graph iteration, and cannot compare a NaN with a decimal at all.
    Ordering by the complete term spelling settles every pair.
    """
    graph = Graph()
    graph.bind("ex", EX)
    for value in (
        Literal("01", datatype=XSD.integer, normalize=False),
        Literal("1", datatype=XSD.integer, normalize=False),
        Literal("NaN", datatype=XSD.double),
        Literal("1.5", datatype=XSD.decimal),
        Literal("z"),
        Literal("z", lang="en"),
        URIRef("http://example.org/o"),
        BNode("bb"),
    ):
        graph.add((EX.s, EX.p, value))

    first = deterministic_turtle(graph)
    # Same graph, objects added in the opposite order: the output must match.
    reversed_graph = Graph()
    reversed_graph.bind("ex", EX)
    for triple in reversed(list(graph)):
        reversed_graph.add(triple)

    assert deterministic_turtle(reversed_graph) == first

    # Counted with pyoxigraph, not rdflib: rdflib parses with
    # NORMALIZE_LITERALS on, so it reads "01"^^xsd:integer back as "1" and
    # merges the two into one triple. The file is faithful; rdflib's reader is
    # lossy, which is precisely why this library's own guard compares
    # pyoxigraph's parse rather than rdflib's.
    assert len(list(ox.parse(first, format=ox.RdfFormat.TURTLE))) == len(graph)
    assert '"01"^^xsd:integer' in first and '"1"^^xsd:integer' in first


def test_literals_needing_escapes_still_round_trip() -> None:
    """Local rendering preserves literals requiring Turtle escapes."""
    graph = Graph()
    for index, text in enumerate(
        [
            'say "hi"',
            "a\\b",
            "a\nb",
            "a\rb",
            "a\r\nb",
            "a\tb",
            'a"""b',
            'a\nb"',
            # Triple-quoted literal values require escaping embedded delimiters.
            'a\nb"""c',
            'a\nb""""c',
            'a\nb"""',
            'a\nb\\"""c',
            "",
            "a" + chr(0x2028) + "b",
            "hi \U0001f389",
        ]
    ):
        graph.add((EX.s, EX[f"p{index}"], Literal(text)))

    result = deterministic_turtle(graph)

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


def test_a_datatype_prefix_is_never_invented_during_the_write_phase() -> None:
    """`@prefix` declarations are already emitted by the time labels are written.

    Asking rdflib to generate a prefix here would produce a document using a
    prefix it never declares.
    """
    graph = Graph(bind_namespaces="none")
    graph.add((EX.s, EX.p, Literal("v", datatype=URIRef("http://datatype.example/t"))))

    result = deterministic_turtle(graph)

    reparsed = Graph().parse(data=result, format="turtle")
    assert isomorphic(reparsed, graph)
    declared = {line.split()[1].rstrip(":") for line in result.splitlines() if line.startswith("@prefix")}
    used = {
        token.split(":")[0]
        for line in result.splitlines()
        if not line.startswith("@prefix")
        for token in line.split()
        if ":" in token and not token.startswith(("<", '"'))
    }
    assert used <= declared, f"undeclared prefixes {used - declared} in:\n{result}"
