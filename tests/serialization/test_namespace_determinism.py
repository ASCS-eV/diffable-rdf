"""Deterministic namespace allocation across independent processes."""

from __future__ import annotations

import re
import textwrap

import pyoxigraph as ox
import pytest
import rdflib
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import XSD

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle


PROCESS_SCRIPT = textwrap.dedent(
    """
    import random
    import sys

    from rdflib import BNode, Graph, Literal, URIRef
    from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

    seed = int(sys.argv[1])
    mode = sys.argv[2]
    randomizer = random.Random(seed)
    graph = Graph(bind_namespaces="none")
    shared = BNode(f"source-label-{seed}")
    triples = [
        (URIRef("http://subject.example/root"), URIRef("http://zeta.example/vocab/pred"), shared),
        (shared, URIRef("http://alpha.example/vocab/pred"), URIRef("http://objects.example/value")),
        (
            shared,
            URIRef("http://middle.example/vocab/pred"),
            Literal("01", datatype=URIRef("http://types.example/vocab/type"), normalize=False),
        ),
    ]
    if mode == "relative-predicates":
        triples.extend(
            (URIRef("http://subject.example/root"), URIRef(f"{name}/pred"), Literal(name))
            for name in ("zeta", "alpha", "middle")
        )
    elif mode != "normal":
        triples.append((URIRef("relative/item"), URIRef("http://relative.example/vocab/pred"), Literal("y")))
    randomizer.shuffle(triples)
    for triple in triples:
        graph.add(triple)

    if mode == "normal":
        result = deterministic_turtle(graph)
    elif mode == "relative-predicates":
        result = canonicalize_rdf_graph(graph, output_format=sys.argv[3])
    else:
        result = canonicalize_rdf_graph(graph, output_format=mode)
    print(result, end="")
    """
)


def _process_outputs(python_runner, mode: str, output_format: str | None = None) -> list[str]:
    outputs = []
    for seed in (1, 7, 31, 509):
        arguments = [str(seed), mode]
        if output_format is not None:
            arguments.append(output_format)
        completed = python_runner(
            PROCESS_SCRIPT,
            *arguments,
            env={"PYTHONHASHSEED": str(seed)},
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(completed.stdout)
    return outputs


@pytest.mark.parametrize(
    ("mode", "output_format"),
    [
        ("normal", None),
        ("turtle", None),
        ("n3", None),
        ("relative-predicates", "turtle"),
        ("relative-predicates", "n3"),
    ],
)
def test_namespace_allocation_is_stable_across_processes(python_runner, mode: str, output_format: str | None) -> None:
    outputs = _process_outputs(python_runner, mode, output_format)
    assert len(set(outputs)) == 1
    if mode == "normal":
        assert '@prefix ns1: <http://alpha.example/vocab/> .' in outputs[0]
    else:
        assert "relative" in outputs[0] or "alpha/" in outputs[0]


def _prefixes(turtle: str) -> dict[str, str]:
    return dict(re.findall(r"^@prefix ([^:]*): <([^>]*)> \.$", turtle, flags=re.MULTILINE))


def _graph_with_caller_bindings() -> Graph:
    graph = Graph(bind_namespaces="none")
    graph.bind("ns1", Namespace("http://reserved.example/"))
    graph.bind("old", Namespace("http://zeta.example/vocab/"))
    graph.bind("vocab", Namespace("http://zeta.example/vocab/"), override=True)
    graph.bind("dt", Namespace("http://types.example/vocab/"))
    graph.bind("", Namespace("http://default.example/"))
    graph.bind("unused", Namespace("http://unused.example/"))

    shared = BNode("caller-label")
    for triple in (
        (URIRef("http://default.example/root"), URIRef("http://alpha.example/vocab/pred"), shared),
        (shared, URIRef("http://middle.example/vocab/pred"), URIRef("http://objects.example/value")),
        (shared, URIRef("http://zeta.example/vocab/pred"), Literal("x", datatype=URIRef("http://types.example/vocab/type"))),
        (shared, URIRef("http://punct.example/vocab/has-value"), URIRef("http://trailing.example/vocab/value.")),
    ):
        graph.add(triple)
    return graph


def test_caller_prefixes_are_preserved_and_generated_names_are_reserved() -> None:
    graph = _graph_with_caller_bindings()
    before = tuple((str(prefix), str(namespace)) for prefix, namespace in graph.namespaces())
    preferred_before = graph.namespace_manager.store.prefix(URIRef("http://zeta.example/vocab/"))

    result = deterministic_turtle(graph)

    # Generated names are for predicates, numbered in lexical predicate order
    # after the caller's own ``ns1`` is reserved. A namespace that only a
    # subject, object or datatype uses gets no invented prefix: those terms
    # keep their complete IRI unless the caller bound the namespace, as with
    # ``dt`` here, because a prefixed name is optional syntax the serializer
    # chooses per position (Turtle 1.1 section 6.5).
    assert _prefixes(result) == {
        "": "http://default.example/",
        "dt": "http://types.example/vocab/",
        "ns2": "http://alpha.example/vocab/",
        "ns3": "http://middle.example/vocab/",
        "ns4": "http://punct.example/vocab/",
        "vocab": "http://zeta.example/vocab/",
    }
    assert "<http://objects.example/value>" in result
    assert "<http://trailing.example/vocab/value.>" in result
    assert "reserved.example" not in result
    assert "unused.example" not in result
    assert "old:" not in result
    assert tuple((str(prefix), str(namespace)) for prefix, namespace in graph.namespaces()) == before
    assert graph.namespace_manager.store.prefix(URIRef("http://zeta.example/vocab/")) == preferred_before


def test_standard_graph_round_trip_preserves_exact_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = Graph(bind_namespaces="none")
    graph.add(
        (
            URIRef("http://subject.example/root"),
            URIRef("http://predicate.example/value"),
            Literal("01", datatype=XSD.integer, normalize=False),
        )
    )

    # rdflib normally canonicalizes numeric lexical forms while parsing. Turn
    # that parser option off so this assertion compares the exact RDF terms.
    monkeypatch.setattr(rdflib, "NORMALIZE_LITERALS", False)
    reparsed = Graph(bind_namespaces="none").parse(data=deterministic_turtle(graph), format="turtle")

    assert set(reparsed) == set(graph)


@pytest.mark.parametrize("output_format", ["turtle", "n3"])
def test_degraded_relative_terms_are_retained(output_format: str) -> None:
    graph = Graph(bind_namespaces="none")
    graph.add((URIRef("relative/subject"), URIRef("alpha/predicate"), Literal("value")))
    before = tuple(graph.namespaces())

    result = canonicalize_rdf_graph(graph, output_format=output_format)

    assert "relative/" in result
    assert "alpha/" in result
    assert tuple(graph.namespaces()) == before


def test_deterministic_turtle_degraded_path_keeps_graph_and_bindings() -> None:
    graph = _graph_with_caller_bindings()
    graph.add((URIRef("relative/item"), URIRef("relative/predicate"), Literal("relative")))
    before = tuple(graph.namespaces())

    result = deterministic_turtle(graph)

    assert "relative/" in result
    assert tuple(graph.namespaces()) == before


@pytest.mark.parametrize(
    "namespace",
    [
        "http://query.example/vocab?v=",
        "http://query.example/a?b=c&d=",
        "http://query.example/?",
    ],
)
def test_a_query_string_namespace_is_declared_as_a_prefix(namespace: str) -> None:
    """A namespace with a query string is usable, so its binding must survive.

    Query-string namespaces form valid CURIEs and retain compact output.
    """
    graph = Graph(bind_namespaces="none")
    graph.bind("q", URIRef(namespace))
    graph.add((URIRef(namespace + "s"), URIRef(namespace + "p"), Literal("v")))

    result = canonicalize_rdf_graph(graph, output_format="turtle")

    assert f"@prefix q: <{namespace}>" in result, result
    assert "q:s q:p" in result, result
    # And it has to survive the round trip that the guard already enforces.
    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


@pytest.mark.parametrize(
    ("namespace", "usable"),
    [
        pytest.param("http://ex/vocab#", True, id="trailing-fragment"),
        pytest.param("http://ex/vocab/", True, id="trailing-slash"),
        pytest.param("http://ex/a?b=c&d=", True, id="query-string"),
        # Embedded fragments form valid CURIEs under pyoxigraph.
        pytest.param("http://ex/a#b", True, id="embedded-fragment"),
        pytest.param("http://ex/a#b/", True, id="embedded-fragment-then-slash"),
        # Not IRIs at all, and each is rejected as a prefix by pyoxigraph.
        pytest.param("http://ex/a#b#", False, id="two-fragments"),
        pytest.param("http://ex/%2", False, id="incomplete-percent-escape"),
        pytest.param("http://ex/a b/", False, id="space"),
        pytest.param("vocab/", False, id="relative"),
        pytest.param("not an iri", False, id="not-an-iri"),
    ],
)
def test_the_prefix_filter_matches_what_pyoxigraph_will_accept(namespace: str, usable: bool) -> None:
    """The filter's job is to predict pyoxigraph's answer, so check it against it."""
    from diffable_rdf.canonicalize import _is_safe_prefix_iri

    triple = [ox.Triple(ox.NamedNode("http://ex/s"), ox.NamedNode("http://ex/p"), ox.Literal("v"))]
    try:
        ox.serialize(triple, format=ox.RdfFormat.TURTLE, prefixes={"n": namespace})
        accepted = True
    except (ValueError, SyntaxError):
        accepted = False

    assert accepted is usable, "the premise of this case no longer holds"
    assert _is_safe_prefix_iri(namespace) is usable


def test_an_undeclarable_binding_preserves_usable_prefixes() -> None:
    """An undeclarable binding does not remove usable caller prefixes."""
    good = Namespace("http://good.example/")
    graph = Graph(bind_namespaces="none")
    graph.bind("good", good)
    graph.bind("half", URIRef("http://ex/%2"))
    graph.add((URIRef("http://ex/%20x"), good.p, Literal("v")))
    graph.add((good.s, good.p, Literal("v")))

    result = canonicalize_rdf_graph(graph, output_format="turtle")

    assert "@prefix good: <http://good.example/>" in result, result
    assert "good:s good:p" in result, result
    assert "half:" not in result, "the undeclarable binding must not be declared"
    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)
