"""Process-level contracts for serializers that use rdflib fallbacks.

Some valid rdflib graphs cannot be serialized by pyoxigraph, including graphs
with literal predicates or relative IRIs. These tests verify that public
serializers retain deterministic output and RDF term identity for those inputs.
"""

from __future__ import annotations

import textwrap

import pytest
from rdflib import BNode, Graph, Literal, Namespace

from diffable_rdf import deterministic_turtle

EX = Namespace("http://example.org/")


def _graph_with_named_bnode_and_literal_predicate() -> Graph:
    """Build a fallback graph with an explicitly serialized blank node."""
    graph = Graph()
    graph.bind("ex", EX)
    shared = BNode()
    graph.add((EX.a, EX.p, shared))
    graph.add((EX.b, EX.p, shared))
    graph.add((shared, EX.q, Literal("v")))
    graph.addN([(EX.a, Literal("literal-predicate"), Literal("x"), graph)])
    return graph


def _run_fallback_serializer_in_subprocess(python_runner, call: str) -> str:
    """Run a fallback serializer in a fresh interpreter."""
    script = textwrap.dedent(f"""
        import warnings
        warnings.simplefilter("ignore")
        from rdflib import BNode, Graph, Literal, Namespace
        from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

        EX = Namespace("http://example.org/")
        graph = Graph()
        graph.bind("ex", EX)
        shared = BNode()
        graph.add((EX.a, EX.p, shared))
        graph.add((EX.b, EX.p, shared))
        graph.add((shared, EX.q, Literal("v")))
        graph.addN([(EX.a, Literal("literal-predicate"), Literal("x"), graph)])
        print({call})
    """)
    result = python_runner(
        script,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


@pytest.mark.parametrize(
    "call",
    [
        'canonicalize_rdf_graph(graph, output_format="turtle")',
        "deterministic_turtle(graph)",
    ],
)
def test_fallback_path_is_reproducible_across_processes(python_runner, call: str) -> None:
    """Fallback serializers emit identical bytes in separate interpreters."""
    first = _run_fallback_serializer_in_subprocess(python_runner, call)
    second = _run_fallback_serializer_in_subprocess(python_runner, call)

    assert first == second
    assert "_:N" not in first


def test_deterministic_turtle_does_not_crash_on_literal_predicates() -> None:
    """Literal predicates remain represented in deterministic Turtle output."""
    result = deterministic_turtle(_graph_with_named_bnode_and_literal_predicate())

    assert "literal-predicate" in result
