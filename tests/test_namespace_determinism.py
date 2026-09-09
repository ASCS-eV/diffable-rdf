"""Deterministic namespace allocation across independent processes."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap

import pytest
import rdflib
from rdflib import BNode, Graph, Literal, Namespace, URIRef
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


def _process_outputs(mode: str, output_format: str | None = None) -> list[str]:
    source = str(Path(__file__).resolve().parents[1] / "src")
    outputs = []
    for seed in (1, 7, 31, 509):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = str(seed)
        env["PYTHONPATH"] = source
        command = [sys.executable, "-c", PROCESS_SCRIPT, str(seed), mode]
        if output_format is not None:
            command.append(output_format)
        completed = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
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
def test_namespace_allocation_is_stable_across_processes(mode: str, output_format: str | None) -> None:
    outputs = _process_outputs(mode, output_format)
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

    assert _prefixes(result) == {
        "": "http://default.example/",
        "dt": "http://types.example/vocab/",
        "ns2": "http://alpha.example/vocab/",
        "ns3": "http://middle.example/vocab/",
        "ns4": "http://objects.example/",
        "ns5": "http://punct.example/vocab/",
        "vocab": "http://zeta.example/vocab/",
    }
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
