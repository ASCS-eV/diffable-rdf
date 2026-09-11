"""Namespace discovery by RDF term position in Turtle-family output.

A prefixed name is optional syntax: Turtle only admits one where the local part
matches ``PN_LOCAL`` (Turtle 1.1 section 6.5), so the serializer decides per
term position whether to declare a prefix or write the complete IRI. These
cases pin that decision at the public entry points: every valid IRI reaches the
output unchanged, and no position turns a valid IRI into a namespace
declaration that no conformant reader accepts.
"""

from __future__ import annotations

from collections import Counter
import io
import textwrap

import pyoxigraph
import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle


# Valid IRIs whose rdflib QName split is not a valid namespace IRI: splitting
# ``http://a.example/%25`` gives ``http://a.example/%`` plus ``25``, and an
# incomplete percent escape is not an IRI (RFC 3987 section 2.2).
SPLIT_HOSTILE_IRIS = {
    "percent-escape": "http://a.example/%25",
    "sub-delims": "http://a.example/_~.-!$&'()*+,;=/?#@%00",
}
ROLES = ("subject", "object", "datatype")
# The Turtle-family aliases whose output goes through a prefix-generating
# rdflib serializer, with the format each one is read back as.
TURTLE_FAMILY = {"turtle": "turtle", "ttl": "turtle", "n3": "n3", "trig": "trig"}

SUBJECT = URIRef("http://a.example/s")
PREDICATE = URIRef("http://a.example/p")
OBJECT = URIRef("http://a.example/o")
# Relative terms are only meaningful against a base, so the semantic
# comparisons below resolve them against one instead of reading them as
# absolute IRIs.
BASE = "http://neutral.example/base/"


def _graph_with(role: str, iri: str, *, extra: bool = False) -> Graph:
    """Build one triple that carries ``iri`` in the requested term position."""
    graph = Graph(bind_namespaces="none")
    if role == "subject":
        graph.add((URIRef(iri), PREDICATE, OBJECT))
    elif role == "object":
        graph.add((SUBJECT, PREDICATE, URIRef(iri)))
    elif role == "datatype":
        graph.add((SUBJECT, PREDICATE, Literal("v", datatype=URIRef(iri))))
    else:
        raise ValueError(f"unknown term position: {role}")
    if extra:
        # A term pyoxigraph cannot parse, which is what selects the degraded path.
        graph.add((URIRef("relative/thing"), PREDICATE, Literal("v")))
    return graph


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("iri", SPLIT_HOSTILE_IRIS.values(), ids=SPLIT_HOSTILE_IRIS)
def test_deterministic_turtle_writes_a_split_hostile_iri_in_every_position(role: str, iri: str) -> None:
    graph = _graph_with(role, iri)

    result = deterministic_turtle(graph)

    assert f"<{iri}>" in result, result
    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("iri", SPLIT_HOSTILE_IRIS.values(), ids=SPLIT_HOSTILE_IRIS)
def test_the_canonicalizer_writes_a_split_hostile_iri_in_every_position(
    iri: str, role: str, output_format: str
) -> None:
    graph = _graph_with(role, iri)

    result = canonicalize_rdf_graph(graph, output_format=output_format)

    assert f"<{iri}>" in result, result
    assert isomorphic(Graph().parse(data=result, format=TURTLE_FAMILY[output_format]), graph)


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
@pytest.mark.parametrize("role", ROLES)
def test_the_degraded_path_writes_a_split_hostile_iri_in_every_position(role: str, output_format: str) -> None:
    """The fallback serializer decides namespaces the same way the normal one does."""
    iri = SPLIT_HOSTILE_IRIS["percent-escape"]
    graph = _graph_with(role, iri, extra=True)

    result = canonicalize_rdf_graph(graph, output_format=output_format)

    assert f"<{iri}>" in result, result
    expected = Graph()
    for subject, predicate, object_ in graph:
        expected.add(
            tuple(
                URIRef(BASE + str(term)) if isinstance(term, URIRef) and ":" not in str(term) else term
                for term in (subject, predicate, object_)
            )
        )
    reparsed = Graph().parse(data=result, format=TURTLE_FAMILY[output_format], publicID=BASE)
    assert isomorphic(reparsed, expected)


def test_only_the_predicate_position_earns_a_generated_prefix() -> None:
    """Generated names exist to shorten predicates, which repeat; terms elsewhere do not."""
    graph = Graph(bind_namespaces="none")
    graph.add(
        (
            URIRef("http://subject.example/thing"),
            URIRef("http://predicate.example/relates"),
            Literal("v", datatype=URIRef("http://datatype.example/kind")),
        )
    )
    graph.add((URIRef("http://subject.example/thing"), URIRef("http://predicate.example/other"), OBJECT))

    result = deterministic_turtle(graph)

    assert "@prefix ns1: <http://predicate.example/> ." in result, result
    assert "ns1:relates" in result and "ns1:other" in result, result
    assert "<http://subject.example/thing>" in result, result
    assert "<http://datatype.example/kind>" in result, result
    assert "subject.example/> ." not in result, "a subject namespace was invented"
    assert "datatype.example/> ." not in result, "a datatype namespace was invented"


@pytest.mark.parametrize("role", ROLES)
def test_a_bound_namespace_is_used_in_every_position(role: str) -> None:
    """Declaring a namespace is the caller's decision, and it holds everywhere."""
    namespace = "http://bound.example/vocab/"
    graph = _graph_with(role, namespace + "term")
    graph.bind("b", Namespace(namespace))

    result = deterministic_turtle(graph)

    assert f"@prefix b: <{namespace}> ." in result, result
    assert "b:term" in result, result
    assert f"<{namespace}term>" not in result, result


def test_a_keyword_predicate_declares_nothing() -> None:
    """``a`` is Turtle's keyword for ``rdf:type``, so that namespace stays undeclared."""
    graph = Graph(bind_namespaces="none")
    graph.add((SUBJECT, RDF.type, URIRef("http://a.example/C")))

    result = deterministic_turtle(graph)

    assert " a " in result, result
    assert "@prefix" not in result, result
    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


@pytest.mark.parametrize(
    "serializer_name", ["_LiteralPreservingTurtleSerializer", "_NoCollectionTurtleSerializer"]
)
def test_preprocessing_presents_every_triple_exactly_once(serializer_name: str) -> None:
    """Reference counts decide blank-node and collection layout.

    The counts collected while traversing the graph are what tell the
    serializer whether a blank node can be inlined or a list written as
    ``( … )``, so presenting a triple twice would silently change the layout
    rather than only the order of discovery.
    """
    from diffable_rdf import turtle as turtle_module

    serializer_class = getattr(turtle_module, serializer_name)
    graph = Graph(bind_namespaces="none")
    head, tail = BNode("head"), BNode("tail")
    graph.add((SUBJECT, PREDICATE, head))
    graph.add((head, RDF.first, Literal("a")))
    graph.add((head, RDF.rest, tail))
    graph.add((tail, RDF.first, Literal("b")))
    graph.add((tail, RDF.rest, RDF.nil))
    graph.add((URIRef("http://a.example/s2"), PREDICATE, tail))
    seen: list = []

    class _CountingSerializer(serializer_class):  # type: ignore[misc, valid-type]
        def preprocessTriple(self, triple):  # noqa: N802
            seen.append(triple)
            super().preprocessTriple(triple)

    buffer = io.BytesIO()
    _CountingSerializer(graph).serialize(buffer, encoding="utf-8")

    assert Counter(seen) == Counter(graph)


@pytest.mark.parametrize("output_format", [None, *TURTLE_FAMILY])
def test_generated_names_follow_the_graph_not_its_insertion_order(output_format: str | None) -> None:
    """The same statements must spell the same document however they were added."""
    triples = [
        (URIRef("http://subject.example/root"), URIRef("http://zeta.example/vocab/pred"), OBJECT),
        (URIRef("http://subject.example/root"), URIRef("http://alpha.example/vocab/pred"), Literal("a")),
        (URIRef("http://subject.example/root"), URIRef("http://middle.example/vocab/pred"), Literal("m")),
        (
            URIRef("http://subject.example/root"),
            URIRef("http://punct.example/vocab/pred"),
            URIRef(SPLIT_HOSTILE_IRIS["percent-escape"]),
        ),
    ]
    outputs = set()
    for order in (triples, list(reversed(triples)), triples[2:] + triples[:2]):
        graph = Graph(bind_namespaces="none")
        for triple in order:
            graph.add(triple)
        if output_format is None:
            outputs.add(deterministic_turtle(graph))
        else:
            outputs.add(canonicalize_rdf_graph(graph, output_format=output_format))

    assert len(outputs) == 1, outputs


PROCESS_SCRIPT = textwrap.dedent(
    """
    import random
    import sys

    from rdflib import Graph, Literal, URIRef
    from diffable_rdf import deterministic_turtle

    randomizer = random.Random(int(sys.argv[1]))
    triples = [
        (URIRef("http://a.example/%25"), URIRef("http://zeta.example/vocab/p"), Literal("z")),
        (URIRef("http://a.example/s"), URIRef("http://alpha.example/vocab/p"), URIRef("http://a.example/%25")),
        (
            URIRef("http://a.example/s"),
            URIRef("http://middle.example/vocab/p"),
            Literal("v", datatype=URIRef("http://a.example/%25")),
        ),
    ]
    randomizer.shuffle(triples)
    graph = Graph(bind_namespaces="none")
    for triple in triples:
        graph.add(triple)
    print(deterministic_turtle(graph), end="")
    """
)


def test_split_hostile_output_is_stable_across_processes(python_runner) -> None:
    """Namespace discovery may not depend on process-level hash randomization."""
    outputs = {
        python_runner(
            PROCESS_SCRIPT,
            str(seed),
            env={"PYTHONHASHSEED": str(seed)},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in (1, 7, 31, 509)
    }

    assert len(outputs) == 1, outputs
    assert "<http://a.example/%25>" in outputs.pop()


def test_a_split_hostile_predicate_is_refused_rather_than_written_invalidly() -> None:
    """The predicate position is the dependency's own namespace decision.

    rdflib generates a prefix for a predicate whatever its local part is, so a
    predicate whose split is not a valid IRI yields a document that a
    conformant reader rejects. This library refuses that output instead of
    returning it, and the canonicalizer's normal path, which spells predicates
    in full, still writes the graph.
    """
    graph = Graph(bind_namespaces="none")
    graph.add((SUBJECT, URIRef(SPLIT_HOSTILE_IRIS["percent-escape"]), OBJECT))

    unassisted = graph.serialize(format="turtle")
    assert "@prefix ns1: <http://a.example/%>" in unassisted, "the premise of this case no longer holds"
    with pytest.raises(SyntaxError):
        list(pyoxigraph.parse(unassisted, format=pyoxigraph.RdfFormat.TURTLE))

    with pytest.raises(ValueError):
        deterministic_turtle(graph)

    result = canonicalize_rdf_graph(graph, output_format="turtle")
    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


@pytest.mark.parametrize("role", ROLES)
def test_the_caller_graph_and_its_bindings_are_untouched(role: str) -> None:
    graph = _graph_with(role, SPLIT_HOSTILE_IRIS["percent-escape"])
    graph.bind("keep", Namespace("http://keep.example/"))
    bindings_before = tuple((str(prefix), str(namespace)) for prefix, namespace in graph.namespaces())
    triples_before = set(graph)

    deterministic_turtle(graph)
    canonicalize_rdf_graph(graph, output_format="turtle")

    assert tuple((str(prefix), str(namespace)) for prefix, namespace in graph.namespaces()) == bindings_before
    assert set(graph) == triples_before


@pytest.mark.parametrize("output_format", ["xml", "nt"])
def test_a_format_without_positional_discovery_preallocates_in_iri_order(output_format: str) -> None:
    """The other fallback serializers discover namespaces in store order.

    Only the Turtle family decides per position which terms may carry a
    prefixed name. Every other rdflib serializer numbers namespaces as it
    meets them while traversing the graph, so the preparation that feeds them
    allocates in lexical IRI order first, and leaves an IRI that has no split
    at all — ``http://a.example/`` has no local part — to be written in full.
    """
    graph = Graph(bind_namespaces="none")
    graph.add((URIRef("http://a.example/"), PREDICATE, Literal("v", datatype=URIRef("http://dt.example/kind"))))
    graph.add((URIRef("http://a.example/thing"), PREDICATE, URIRef("relative/object")))

    if output_format == "nt":
        # N-Triples admits only absolute IRIs, so this graph is refused there
        # rather than written; the refusal is what keeps unreadable output out.
        with pytest.raises(ValueError):
            canonicalize_rdf_graph(graph, output_format=output_format)
        return

    result = canonicalize_rdf_graph(graph, output_format=output_format)

    assert "http://a.example/" in result, result
    assert "http://dt.example/kind" in result, result
