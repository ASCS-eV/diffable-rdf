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
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic

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


def test_deterministic_turtle_survives_a_hash_base():
    """A hash base must not corrupt terms or trip the round-trip guard.

    rdflib relativizes IRIs against ``graph.base`` by naive string
    prefixing, so carrying the base across would emit
    ``http://example.org/d#a`` as ``<a>`` -- which re-resolves to a
    *different* IRI. Hash namespaces are the most common OWL style, so
    this must degrade to full IRIs rather than raise.
    """
    for base in ("http://example.org/d#", "http://example.org/d", "http://example.org/d/"):
        g = Graph(base=base)
        g.add((URIRef("http://example.org/d#a"), EX.pred, Literal("v0")))
        g.add((URIRef("http://example.org/d#b"), EX.pred, Literal("v1")))
        result = deterministic_turtle(g)
        # Lossless: terms survive verbatim rather than being relativized away.
        assert isomorphic(Graph().parse(data=result, format="turtle"), g), base


def test_canonicalize_rdf_graph_recovers_from_an_invalid_base():
    """A relative base is legal in rdflib and must not crash the serializer.

    pyoxigraph rejects it with "Invalid base IRI ..."; that must be caught
    and retried without the base, exactly like the prefix-rejection path.
    """
    g = Graph(base="book/")
    g.bind("ex", EX)
    g.add((EX.s, EX.p, Literal("v")))
    assert "http://example.org/s" in canonicalize_rdf_graph(g, output_format="turtle")


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


def _to_rdflib(quads: list) -> Graph:
    """Rebuild an rdflib Graph from pyoxigraph quads for isomorphism checks."""
    return Graph().parse(
        data="\n".join(f"{q.subject} {q.predicate} {q.object} ." for q in quads),
        format="nt",
    )


def test_wl_relabel_quads_preserves_the_graph():
    """Relabelling must be a true isomorphism, not merely length-preserving.

    Asserting only the length and the predicate set is vacuous: relabelling
    is 1:1 on the list and never touches predicates, so a relabel that
    collapsed every blank node into one would still pass. Assert graph
    isomorphism and that the number of *distinct* blank nodes is preserved.
    """
    quads = _canonical_quads(_shapes_graph(8))
    relabelled = wl_relabel_quads(quads)

    assert len(relabelled) == len(quads)
    assert isomorphic(_to_rdflib(relabelled), _to_rdflib(quads))

    def distinct_bnodes(qs: list) -> int:
        return len({t.value for q in qs for t in (q.subject, q.object) if isinstance(t, ox.BlankNode)})

    assert distinct_bnodes(relabelled) == distinct_bnodes(quads) == 8


def test_wl_relabel_quads_remaps_blank_node_graph_names():
    """A blank node used as a graph name must get the same label as its term uses.

    Leaving ``graph_name`` unmapped splits one node into two and silently
    breaks the dataset: the triple that identifies the named graph would no
    longer point at it.
    """
    nquads = (
        b"<http://example.org/doc> <http://example.org/hasGraph> _:g <http://example.org/meta> .\n"
        b"<http://example.org/s> <http://example.org/p> <http://example.org/o> _:g .\n"
    )
    dataset = ox.Dataset(ox.parse(nquads, format=ox.RdfFormat.N_QUADS))
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)

    relabelled = wl_relabel_quads(list(dataset))
    as_object = {q.object.value for q in relabelled if isinstance(q.object, ox.BlankNode)}
    as_graph_name = {q.graph_name.value for q in relabelled if isinstance(q.graph_name, ox.BlankNode)}

    assert as_object and as_graph_name
    assert as_object == as_graph_name


@pytest.mark.parametrize("output_format", ["turtle", "json-ld", "xml", "nt", "nquads", "trig", "n3"])
def test_canonicalize_rdf_graph_is_deterministic_across_processes(output_format: str) -> None:
    """Every supported format must be byte-identical across interpreters.

    Formats pyoxigraph cannot handle (notably ``json-ld``) used to bypass
    canonicalization entirely and return raw rdflib output, leaking
    run-local blank-node labels and set-iteration node ordering.
    """
    script = textwrap.dedent(
        """
        from rdflib import Graph, Namespace, BNode, Literal, RDF
        from diffable_rdf import canonicalize_rdf_graph
        import sys
        EX = Namespace("http://example.org/")
        g = Graph()
        hub = BNode()  # multiply referenced -> must be emitted as a label
        for i in range(3):
            g.add((EX[f"s{i}"], RDF.type, EX.Thing))
            g.add((EX[f"s{i}"], EX.ref, hub))
        g.add((hub, EX.name, Literal("hub")))
        sys.stdout.write(canonicalize_rdf_graph(g, output_format=sys.argv[1]))
        """
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", script, output_format],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for _ in range(3)
    }
    assert len(runs) == 1, f"{output_format} is not reproducible across processes"
