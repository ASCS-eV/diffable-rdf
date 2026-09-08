"""Regression tests for the degraded (non-pyoxigraph) serialization paths.

pyoxigraph rejects some graphs that rdflib happily accepts — notably
literal predicates (produced by SHACL annotation mode) and relative
IRIs.  Historically the fallback for those graphs returned a plain
``graph.serialize()``, which assigns blank-node labels from run-local
state and is therefore **not** reproducible across processes.  That
silently violated the core promise of this library.

These tests pin the contract: every public entry point stays
byte-reproducible across independent interpreter processes, including
on the degraded paths.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pyoxigraph as ox
import pytest
from rdflib import BNode, Graph, Literal, Namespace

from diffable_rdf import (
    canonicalize_rdf_graph,
    deterministic_turtle,
    wl_blank_node_labels,
    wl_relabel_quads,
)

EX = Namespace("http://example.org/")


def _graph_with_named_bnode_and_literal_predicate() -> Graph:
    """A graph that forces both the fallback path and a *named* blank node.

    The blank node is referenced twice, so rdflib cannot inline it as
    ``[ ... ]`` and must emit an explicit ``_:label`` — which is exactly
    where non-deterministic labelling becomes visible.  The literal
    predicate is what makes pyoxigraph reject the graph.
    """
    g = Graph()
    g.bind("ex", EX)
    shared = BNode()
    g.add((EX.a, EX.p, shared))
    g.add((EX.b, EX.p, shared))
    g.add((shared, EX.q, Literal("v")))
    g.addN([(EX.a, Literal("literal-predicate"), Literal("x"), g)])
    return g


def _run_in_subprocess(call: str) -> str:
    """Serialize the fixture graph in a fresh interpreter and return the output.

    Determinism must hold across *processes*, not just across calls: the
    non-determinism this guards against comes from run-local blank-node
    identifiers, which are stable within a single process.
    """
    script = textwrap.dedent(f"""
        import warnings
        warnings.simplefilter("ignore")
        from rdflib import BNode, Graph, Literal, Namespace
        from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

        EX = Namespace("http://example.org/")
        g = Graph()
        g.bind("ex", EX)
        shared = BNode()
        g.add((EX.a, EX.p, shared))
        g.add((EX.b, EX.p, shared))
        g.add((shared, EX.q, Literal("v")))
        g.addN([(EX.a, Literal("literal-predicate"), Literal("x"), g)])
        print({call})
    """)
    out = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout


@pytest.mark.parametrize(
    "call",
    [
        'canonicalize_rdf_graph(g, output_format="turtle")',
        "deterministic_turtle(g)",
    ],
)
def test_fallback_path_is_reproducible_across_processes(call):
    """The degraded path must stay byte-identical in separate interpreters."""
    first = _run_in_subprocess(call)
    second = _run_in_subprocess(call)
    assert first == second
    # Guard against the regression signature: rdflib's run-local labels.
    assert "_:N" not in first


def test_deterministic_turtle_does_not_crash_on_literal_predicates():
    """Literal predicates must degrade gracefully, not raise SyntaxError."""
    result = deterministic_turtle(_graph_with_named_bnode_and_literal_predicate())
    assert "literal-predicate" in result


def test_deterministic_turtle_preserves_base_iri():
    """A graph base must survive the rebuild into a fresh rdflib Graph."""
    g = Graph(base="http://example.org/base/")
    g.bind("ex", EX)
    g.add((EX.s, EX.p, Literal("v")))
    assert "@base" in deterministic_turtle(g)


def _canonical_quads(g: Graph) -> list:
    ds = ox.Dataset(ox.parse(g.serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES))
    ds.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return list(ds)


def _shapes_graph(n: int, extra: bool = False) -> Graph:
    g = Graph()
    g.bind("ex", EX)
    names = [f"{i:02d}" for i in range(n)] + (["AAAnew"] if extra else [])
    for name in names:
        subject, prop = EX[f"Shape{name}"], BNode()
        g.add((subject, EX.property, prop))
        g.add((prop, EX.path, EX[f"prop{name}"]))
    return g


def test_wl_relabel_quads_is_diff_stable():
    """Adding one subject must not relabel the untouched blank nodes.

    This is the property that distinguishes WL labelling from RDFC-1.0's
    sequential ``c14nN`` counter, and the reason the WL primitive is
    exposed as public API.
    """
    before = {
        (str(q.subject), str(q.predicate), str(q.object)) for q in wl_relabel_quads(_canonical_quads(_shapes_graph(20)))
    }
    after = {
        (str(q.subject), str(q.predicate), str(q.object))
        for q in wl_relabel_quads(_canonical_quads(_shapes_graph(20, extra=True)))
    }
    # Every original statement survives verbatim; only the new ones appear.
    assert before <= after
    assert len(after - before) == 2


def test_wl_blank_node_labels_are_injective():
    """Structurally identical nodes must still receive distinct labels."""
    g = Graph()
    for i in range(5):
        prop = BNode()
        g.add((EX[f"S{i}"], EX.property, prop))
        g.add((prop, EX.path, EX.same))  # deliberately identical structure
    labels = wl_blank_node_labels(_canonical_quads(g))
    assert len(labels) == 5
    assert len(set(labels.values())) == 5


def test_wl_relabel_quads_preserves_the_graph():
    """Relabelling must be an isomorphism: no statement added or lost."""
    quads = _canonical_quads(_shapes_graph(8))
    relabelled = wl_relabel_quads(quads)
    assert len(relabelled) == len(quads)
    assert {(str(q.predicate)) for q in relabelled} == {(str(q.predicate)) for q in quads}
