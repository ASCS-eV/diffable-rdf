"""Contracts for Weisfeiler-Lehman blank-node labels and relabelled quads."""

from __future__ import annotations

import pyoxigraph as ox
from rdflib import BNode, Graph, Namespace
from rdflib.compare import isomorphic

from diffable_rdf import wl_blank_node_labels, wl_relabel_quads

EX = Namespace("http://example.org/")


def _canonical_quads(graph: Graph) -> list:
    dataset = ox.Dataset(ox.parse(graph.serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES))
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return list(dataset)


def _canonical_dataset_quads(nquads: bytes) -> list:
    """Return canonical quads from an N-Quads document."""
    dataset = ox.Dataset(ox.parse(nquads, format=ox.RdfFormat.N_QUADS))
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return list(dataset)


def _shapes_graph(count: int, extra: bool = False) -> Graph:
    graph = Graph()
    graph.bind("ex", EX)
    names = [f"{index:02d}" for index in range(count)] + (["AAAnew"] if extra else [])
    for name in names:
        subject, property_node = EX[f"Shape{name}"], BNode()
        graph.add((subject, EX.property, property_node))
        graph.add((property_node, EX.path, EX[f"prop{name}"]))
    return graph


def test_wl_relabel_quads_is_diff_stable() -> None:
    """Adding a subject preserves labels of existing blank nodes."""
    before = {
        (str(quad.subject), str(quad.predicate), str(quad.object))
        for quad in wl_relabel_quads(_canonical_quads(_shapes_graph(20)))
    }
    after = {
        (str(quad.subject), str(quad.predicate), str(quad.object))
        for quad in wl_relabel_quads(_canonical_quads(_shapes_graph(20, extra=True)))
    }

    assert before <= after
    assert len(after - before) == 2


def test_wl_blank_node_labels_are_injective() -> None:
    """Structurally identical blank nodes receive distinct labels."""
    graph = Graph()
    for index in range(5):
        property_node = BNode()
        graph.add((EX[f"S{index}"], EX.property, property_node))
        graph.add((property_node, EX.path, EX.same))

    labels = wl_blank_node_labels(_canonical_quads(graph))

    assert len(labels) == 5
    assert len(set(labels.values())) == 5


def _to_rdflib(quads: list) -> Graph:
    """Build an rdflib graph from pyoxigraph quads."""
    return Graph().parse(
        data="\n".join(f"{quad.subject} {quad.predicate} {quad.object} ." for quad in quads),
        format="nt",
    )


def test_wl_relabel_quads_preserves_the_graph() -> None:
    """Relabelling preserves graph isomorphism and blank-node cardinality."""
    quads = _canonical_quads(_shapes_graph(8))
    relabelled = wl_relabel_quads(quads)

    assert len(relabelled) == len(quads)
    assert isomorphic(_to_rdflib(relabelled), _to_rdflib(quads))

    def distinct_bnodes(items: list) -> int:
        return len(
            {
                term.value
                for quad in items
                for term in (quad.subject, quad.object)
                if isinstance(term, ox.BlankNode)
            }
        )

    assert distinct_bnodes(relabelled) == distinct_bnodes(quads) == 8


def test_wl_relabel_quads_remaps_blank_node_graph_names() -> None:
    """A blank node has one label in term and graph-name positions."""
    nquads = (
        b"<http://example.org/doc> <http://example.org/hasGraph> _:g <http://example.org/meta> .\n"
        b"<http://example.org/s> <http://example.org/p> <http://example.org/o> _:g .\n"
    )
    dataset = ox.Dataset(ox.parse(nquads, format=ox.RdfFormat.N_QUADS))
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    relabelled = wl_relabel_quads(list(dataset))
    as_object = {quad.object.value for quad in relabelled if isinstance(quad.object, ox.BlankNode)}
    as_graph_name = {quad.graph_name.value for quad in relabelled if isinstance(quad.graph_name, ox.BlankNode)}

    assert as_object and as_graph_name
    assert as_object == as_graph_name


def test_wl_labels_graph_name_only_blank_nodes_by_content() -> None:
    """Graph-name-only blank nodes receive distinguishable signatures."""
    quads = _canonical_dataset_quads(
        b"<http://example.org/s1> <http://example.org/p> <http://example.org/o1> _:g1 .\n"
        b"<http://example.org/s2> <http://example.org/p> <http://example.org/o2> _:g2 .\n"
    )
    labels = wl_blank_node_labels(quads)
    signatures = {label.split("_")[0] for label in labels.values()}

    assert len(labels) == 2
    assert len(signatures) == 2, "graph-name nodes require distinct signatures"
    assert all("_" not in label for label in labels.values()), "distinct signatures require no collision suffix"


def test_wl_distinguishes_identical_structure_in_different_named_graphs() -> None:
    """Named-graph membership contributes to blank-node signatures."""
    quads = _canonical_dataset_quads(
        b'<http://example.org/s> <http://example.org/p> _:a <http://example.org/gA> .\n'
        b'_:a <http://example.org/q> "v" <http://example.org/gA> .\n'
        b'<http://example.org/s> <http://example.org/p> _:b <http://example.org/gB> .\n'
        b'_:b <http://example.org/q> "v" <http://example.org/gB> .\n'
    )
    labels = wl_blank_node_labels(quads)
    signatures = {label.split("_")[0] for label in labels.values()}

    assert len(labels) == 2
    assert len(signatures) == 2, "named-graph membership must distinguish both nodes"


def test_wl_labels_are_stable_for_default_graph_input() -> None:
    """Default-graph input has stable labels and no collision suffixes."""
    labels = wl_blank_node_labels(_canonical_quads(_shapes_graph(3)))

    assert sorted(labels) == ["c14n0", "c14n1", "c14n2"]
    assert len(set(labels.values())) == 3
    assert all("_" not in label for label in labels.values())
    assert sorted(labels.values()) == ["b937674156d28", "be01e628a365e", "be8612b4db649"]


def _partition(labels: dict[str, str]) -> list[tuple[str, ...]]:
    """Group nodes by the signature portion of their labels."""
    groups: dict[str, set[str]] = {}
    for node, label in labels.items():
        groups.setdefault(label.split("_")[0], set()).add(node)
    return sorted(tuple(sorted(group)) for group in groups.values())


def _uniform_chain_graph(length: int) -> Graph:
    """Build a chain whose repeated edges need iterative refinement."""
    graph = Graph()
    previous = BNode()
    graph.add((EX.Start, EX.head, previous))
    for _ in range(length - 1):
        current = BNode()
        graph.add((previous, EX.next, current))
        previous = current
    return graph


def test_wl_refines_to_a_fixpoint_by_default() -> None:
    """Default refinement separates a chain and reaches a stable partition."""
    quads = _canonical_quads(_uniform_chain_graph(20))
    fixpoint = _partition(wl_blank_node_labels(quads))
    four_rounds = _partition(wl_blank_node_labels(quads, iterations=4))

    assert len(fixpoint) > len(four_rounds), "default refinement must exceed four rounds for this graph"
    assert all(len(group) == 1 for group in fixpoint), "each chain node is unique at the fixpoint"

    for iterations in (64, 128):
        forced = _partition(wl_blank_node_labels(quads, iterations=iterations))
        assert forced == fixpoint, f"partition changed after {iterations} iterations"


def test_wl_fixpoint_resolves_collisions_that_few_rounds_leave_behind() -> None:
    """Fixpoint refinement removes collision suffixes from the chain labels."""
    quads = _canonical_quads(_uniform_chain_graph(20))
    four_rounds = wl_blank_node_labels(quads, iterations=4)
    fixpoint = wl_blank_node_labels(quads)

    assert any("_" in label for label in four_rounds.values()), "four iterations leave tied chain nodes"
    assert all("_" not in label for label in fixpoint.values()), "fixpoint labels require no collision suffix"
