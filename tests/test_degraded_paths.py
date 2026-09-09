"""Regression tests for the degraded (non-pyoxigraph) serialization paths.

pyoxigraph rejects some graphs that rdflib happily accepts — notably
literal predicates (produced by SHACL annotation mode) and relative
IRIs.  A plain ``graph.serialize()`` for those graphs assigns blank-node
labels from run-local state and is therefore **not** reproducible across
processes, which would silently break the core promise of this library.

These tests pin the contract: every public entry point stays
byte-reproducible across independent interpreter processes, including
on the degraded paths.
"""

from __future__ import annotations

import os
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

SHARED_TAIL_TURTLE = """
@prefix ex: <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
_:t rdf:first "z" ; rdf:rest rdf:nil .
_:a rdf:first "a" ; rdf:rest _:t .
_:b rdf:first "b" ; rdf:rest _:t .
ex:s1 ex:items _:a .
ex:s2 ex:items _:b .
"""


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


def _canonical_dataset_quads(nquads: bytes) -> list:
    """Canonical quads from an N-Quads document, for named-graph cases."""
    dataset = ox.Dataset(ox.parse(nquads, format=ox.RdfFormat.N_QUADS))
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return list(dataset)


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
    # Every statement of the smaller graph survives verbatim; only the new ones appear.
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


def test_wl_labels_graph_name_only_blank_nodes_by_content() -> None:
    """A blank node used only as a graph name must get a real signature.

    Such a node has no adjacency as a term, so before graph membership was
    considered its signature was the empty string -- every graph-name node in
    a dataset hashed identically and was separated only by the collision
    counter, which is assigned in ``c14nN`` order. That is precisely the
    RDFC-1.0 numbering instability WL labelling exists to remove.
    """
    quads = _canonical_dataset_quads(
        b"<http://example.org/s1> <http://example.org/p> <http://example.org/o1> _:g1 .\n"
        b"<http://example.org/s2> <http://example.org/p> <http://example.org/o2> _:g2 .\n"
    )
    labels = wl_blank_node_labels(quads)
    signatures = {label.split("_")[0] for label in labels.values()}

    assert len(labels) == 2
    assert len(signatures) == 2, "graph-name nodes still share a signature"
    assert all("_" not in label for label in labels.values()), (
        "no collision counter should be needed once the nodes are distinguishable"
    )


def test_wl_distinguishes_identical_structure_in_different_named_graphs() -> None:
    """The same shape in two named graphs must not collide.

    Ignoring ``graph_name`` merged both graphs into one adjacency index, so
    two blank nodes with identical local structure tied and fell back to the
    collision counter.
    """
    quads = _canonical_dataset_quads(
        b'<http://example.org/s> <http://example.org/p> _:a <http://example.org/gA> .\n'
        b'_:a <http://example.org/q> "v" <http://example.org/gA> .\n'
        b'<http://example.org/s> <http://example.org/p> _:b <http://example.org/gB> .\n'
        b'_:b <http://example.org/q> "v" <http://example.org/gB> .\n'
    )
    labels = wl_blank_node_labels(quads)
    signatures = {label.split("_")[0] for label in labels.values()}

    assert len(labels) == 2
    assert len(signatures) == 2, "the two named graphs are still indistinguishable"


def test_wl_labels_are_unchanged_for_default_graph_input() -> None:
    """Adding graph awareness must not relabel default-graph datasets.

    Every artifact this library has ever produced came from a default-graph
    input. A signature change there would rewrite all of them on the next
    run, which is the churn the library exists to prevent -- so the graph
    term is omitted entirely for the default graph, and these labels are
    pinned to the values produced before graph membership was considered.
    """
    labels = wl_blank_node_labels(_canonical_quads(_shapes_graph(3)))

    assert sorted(labels) == ["c14n0", "c14n1", "c14n2"]
    assert len(set(labels.values())) == 3
    assert all("_" not in label for label in labels.values())
    # Pinned bytes: recompute only if you intend to reformat every artifact.
    assert sorted(labels.values()) == ["b937674156d28", "be01e628a365e", "be8612b4db649"]


@pytest.mark.parametrize("output_format", ["turtle", "json-ld", "xml", "nt", "nquads", "trig", "n3"])
def test_canonicalize_rdf_graph_is_deterministic_across_processes(output_format: str) -> None:
    """Every supported format must be byte-identical across interpreters.

    Raw rdflib output would leak two process-local orderings into the file:
    run-local blank-node labels, and the set-iteration order in which node
    objects are written. Neither is visible within a single process.
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


def _chain_graph(chains: int = 20, depth: int = 4) -> Graph:
    """Blank-node chains shaped like the OWL restrictions ontology tooling emits."""
    g = Graph()
    for i in range(chains):
        prev = BNode()
        g.add((EX[f"C{i}"], EX.subClassOf, prev))
        for j in range(depth):
            node = BNode()
            g.add((prev, EX.intersectionOf, node))
            g.add((node, EX.onProperty, EX[f"prop{j}"]))
            prev = node
    return g


def test_wl_signatures_stay_bounded_under_many_iterations():
    """Refinement must not grow signatures without bound.

    Each round folds every neighbour's signature into a node's own, so
    without the per-round hash signature length grows by roughly a factor
    of the average degree per round (~2.7x on this shape) and exhausts
    memory within ~10 rounds. The final label is hashed either way, so
    label width cannot detect this — only memory can. The subprocess runs
    under a hard address-space cap so the regression surfaces as a clean
    failure instead of an OOM kill.
    """
    script = textwrap.dedent(
        """
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024 * 1024,) * 2)

        import pyoxigraph as ox
        from rdflib import BNode, Graph, Namespace
        from diffable_rdf import wl_blank_node_labels

        EX = Namespace("http://example.org/")
        g = Graph()
        for i in range(20):
            prev = BNode()
            g.add((EX[f"C{i}"], EX.subClassOf, prev))
            for j in range(4):
                node = BNode()
                g.add((prev, EX.intersectionOf, node))
                g.add((node, EX.onProperty, EX[f"prop{j}"]))
                prev = node

        ds = ox.Dataset(ox.parse(g.serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES))
        ds.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
        quads = list(ds)

        wl_blank_node_labels(quads, iterations=16)
        print("ok")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, (
        "WL refinement exceeded its memory budget; signatures are growing "
        f"per round instead of staying hashed: {result.stderr[-500:]}"
    )
    assert result.stdout.strip() == "ok"


def _partition(labels: dict[str, str]) -> list[tuple[str, ...]]:
    """Recover the signature-equivalence classes from the emitted labels.

    Colliding signatures are disambiguated with a ``_N`` suffix, which
    makes the returned labels injective by construction; stripping it
    recovers the classes WL actually distinguished.
    """
    groups: dict[str, set[str]] = {}
    for node, label in labels.items():
        groups.setdefault(label.split("_")[0], set()).add(node)
    return sorted(tuple(sorted(group)) for group in groups.values())


def _uniform_chain_graph(length: int) -> Graph:
    """A chain of blank nodes joined by one repeated predicate.

    Every edge carries the same IRI, so a node's identity is only fixed
    once refinement has propagated the chain's endpoints all the way to
    it. Separating a chain of ``length`` nodes therefore needs on the
    order of ``length`` rounds — far more than any small fixed count.
    """
    g = Graph()
    previous = BNode()
    g.add((EX.Start, EX.head, previous))
    for _ in range(length - 1):
        current = BNode()
        g.add((previous, EX.next, current))
        previous = current
    return g


def test_wl_refines_to_a_fixpoint_by_default():
    """The default must keep refining past any small fixed round count.

    The graph is chosen so the fixpoint is provably out of reach of the
    previous default of 4 rounds; otherwise this test would pass just as
    happily against a fixed count and would not guard the behaviour at
    all.
    """
    quads = _canonical_quads(_uniform_chain_graph(20))

    fixpoint = _partition(wl_blank_node_labels(quads))
    four_rounds = _partition(wl_blank_node_labels(quads, iterations=4))

    assert len(fixpoint) > len(four_rounds), (
        "the default must refine further than a fixed 4 rounds on a graph that needs more"
    )
    assert all(len(group) == 1 for group in fixpoint), (
        "every node in a uniform chain is structurally unique at the fixpoint"
    )

    # Refining past the fixpoint cannot change the partition.
    for iterations in (64, 128):
        forced = _partition(wl_blank_node_labels(quads, iterations=iterations))
        assert forced == fixpoint, (
            f"partition changed after {iterations} rounds; fixpoint was not reached"
        )


def test_wl_fixpoint_resolves_collisions_that_few_rounds_leave_behind():
    """Under-refining leaves nodes colliding, which leaks RDFC-1.0 numbering.

    Colliding signatures are disambiguated by a counter assigned in
    ``c14nN`` order, so nodes WL cannot yet tell apart inherit the very
    instability WL exists to remove. The ``_N`` suffix is the visible
    symptom, so assert on it directly.
    """
    quads = _canonical_quads(_uniform_chain_graph(20))

    four_rounds = wl_blank_node_labels(quads, iterations=4)
    fixpoint = wl_blank_node_labels(quads)

    assert any("_" in label for label in four_rounds.values()), (
        "4 rounds should leave this chain's middle nodes tied"
    )
    assert all("_" not in label for label in fixpoint.values()), (
        "the fixpoint should separate them, so no collision counter is needed"
    )


def test_degraded_turtle_is_lossless_for_shared_list_tails() -> None:
    """The degraded path must not detach a shared list cell.

    Compact ``( … )`` collection syntax can only express a list whose tail is
    referenced once. This path cannot fall back on a round-trip check, because
    it deliberately passes relative IRIs through verbatim and so cannot be
    compared with the input; it renders list structure explicitly instead, and
    that is what this test holds it to.
    """
    graph = Graph()
    graph.parse(data=SHARED_TAIL_TURTLE, format="turtle")
    graph.add((URIRef("relative/thing"), EX.p, Literal("v")))  # forces the degraded path

    result = deterministic_turtle(graph)
    reparsed = Graph()
    reparsed.parse(data=result, format="turtle")

    defined = {s for s in reparsed.subjects() if isinstance(s, BNode)}
    referenced = {o for o in reparsed.objects() if isinstance(o, BNode)}
    assert not (referenced - defined), f"{len(referenced - defined)} dangling blank-node reference(s)"
    assert len(reparsed) == len(graph), f"{len(graph)} triples in, {len(reparsed)} out"
    assert "( " not in result, "the degraded path must not use collection syntax"


def test_json_ld_is_lossless_for_shared_list_tails() -> None:
    """JSON-LD must not duplicate a shared list cell.

    rdflib's JSON-LD serializer applies ``@list`` compaction, which cannot
    express a shared tail and duplicated it into both lists -- 6 triples in,
    8 out. Routing JSON-LD through pyoxigraph's expanded serializer removes
    the failure class.
    """
    graph = Graph()
    graph.parse(data=SHARED_TAIL_TURTLE, format="turtle")

    result = canonicalize_rdf_graph(graph, output_format="json-ld")
    reparsed = Graph()
    reparsed.parse(data=result, format="json-ld")

    assert len(reparsed) == len(graph), f"{len(graph)} triples in, {len(reparsed)} out"
    assert isomorphic(reparsed, graph), "json-ld output is not isomorphic to the input"
    assert "@list" not in result, "expanded JSON-LD must not use @list compaction"


def test_canonicalize_rdf_graph_raises_rather_than_emitting_unparseable_turtle() -> None:
    """Output that rdflib cannot read back must raise, not be returned.

    ``_expand_trailing_dot_curies`` rewrites CURIEs by regex over the
    serialized text, which can match inside a string literal and corrupt it.
    Until that is fixed, the round-trip check must at least make the failure
    loud: a silent lossy canonical form is the one outcome this library must
    never produce.
    """
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("see ex:thing\\. more")))
    graph.add((EX.other, EX.p, EX.o))  # makes the ex: prefix used, so it is declared

    with pytest.raises(ValueError, match="does not (parse back|round-trip)"):
        canonicalize_rdf_graph(graph, output_format="turtle")


def test_degraded_json_ld_is_reproducible_across_processes() -> None:
    """Relative-node JSON-LD stays stable across labels, order, and hash seeds."""
    script = textwrap.dedent(
        """
        from rdflib import BNode, Graph, Literal, Namespace, URIRef
        from diffable_rdf import canonicalize_rdf_graph
        import sys
        EX = Namespace("http://example.org/")
        seed = int(sys.argv[1])
        g = Graph()
        g.bind("ex", EX)
        shared = BNode(f"input-{seed}")
        triples = [
            (EX.a, EX.ref, shared),
            (EX.b, EX.ref, shared),
            (shared, EX.value, Literal("shared")),
            (URIRef("relative/subject"), EX.p, Literal("fallback")),
        ]
        if seed % 2:
            triples.reverse()
        for triple in triples:
            g.add(triple)
        sys.stdout.write(canonicalize_rdf_graph(g, output_format="json-ld"))
        """
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", script, str(seed)],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        ).stdout
        for seed in (1, 7, 23, 101, 997)
    }
    assert len(runs) == 1, "degraded json-ld is not reproducible across processes"


def test_degraded_json_ld_rejects_literal_predicates() -> None:
    """JSON-LD reports a generalized predicate instead of dropping its triple."""
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("kept")))
    graph.addN([(EX.s, Literal("literal-predicate"), Literal("unsupported"), graph)])

    with pytest.raises(ValueError, match="JSON-LD.*predicate.*Literal"):
        canonicalize_rdf_graph(graph, output_format="json-ld")


@pytest.mark.parametrize("output_format", ["Turtle", "TTL", "N3"])
def test_canonicalize_rdf_graph_accepts_mixed_case_format_names(output_format: str) -> None:
    """A mixed-case format alias must round-trip, not raise.

    Format lookup is case-insensitive throughout, so ``"Turtle"`` reaches
    pyoxigraph and serializes. ``rdflib.Graph.parse``'s plugin lookup is
    not: handing it the caller's raw spelling reports a parser-plugin miss
    ("No plugin registered for (Turtle, ...)") as a ValueError from the
    round-trip guard, which reads as a fidelity failure and is not one. The
    guard normalises case for the same reason every other lookup here does.
    """
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("v")))

    result = canonicalize_rdf_graph(graph, output_format=output_format)
    reparsed = Graph()
    reparsed.parse(data=result, format=output_format.lower())

    assert isomorphic(reparsed, graph), f"{output_format} output is not isomorphic to the input"


def test_degraded_n3_is_lossless_for_shared_list_tails() -> None:
    """N3's degraded path must not duplicate a shared list cell either.

    rdflib's N3Serializer subclasses TurtleSerializer and inherits its
    ``( … )`` collection rendering, so the degraded path's collection-free
    fix for Turtle silently left N3 unfixed unless "n3" is also in
    ``_COLLECTION_CAPABLE_FORMATS``. Turtle is a subset of N3, so rendering
    N3 through the collection-free Turtle serializer is valid N3 output.
    """
    rdf_first = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
    graph = Graph()
    graph.parse(data=SHARED_TAIL_TURTLE, format="turtle")
    graph.add((URIRef("relative/thing"), EX.p, Literal("v")))  # forces the degraded path

    result = canonicalize_rdf_graph(graph, output_format="n3")
    reparsed = Graph()
    reparsed.parse(data=result, format="n3")

    cells_in = len(list(graph.triples((None, rdf_first, None))))
    cells_out = len(list(reparsed.triples((None, rdf_first, None))))
    assert cells_out == cells_in, f"{cells_in} rdf:first cell(s) in, {cells_out} out"
    assert len(reparsed) == len(graph), f"{len(graph)} triples in, {len(reparsed)} out"
    assert "( " not in result, "the degraded n3 path must not use collection syntax"
