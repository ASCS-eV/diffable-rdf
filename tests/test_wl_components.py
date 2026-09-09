"""Component-local convergence guarantees for WL blank-node labels."""

from __future__ import annotations

import re

import pyoxigraph as ox
import pytest
from rdflib import BNode, Graph, Literal, Namespace

from diffable_rdf import deterministic_turtle, wl_blank_node_labels, wl_relabel_quads

EX = Namespace("http://ex/")


def _canonical_quads(nquads: str) -> list:
    """Parse and RDFC-canonicalize a small quad fixture."""
    dataset = ox.Dataset(ox.parse(nquads.encode(), format=ox.RdfFormat.N_QUADS))
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return list(dataset)


def _chain(length: int, *, prefix: str = "n", tail: str = "tail") -> str:
    """Return a blank-node chain whose interior needs multi-round refinement."""
    lines = [f"<http://ex/start> <http://ex/head> _:{prefix}0 ."]
    lines.extend(
        f"_:{prefix}{index} <http://ex/next> _:{prefix}{index + 1} ."
        for index in range(length - 1)
    )
    lines.append(f'_:{prefix}{length - 1} <http://ex/value> "{tail}" .')
    return "\n".join(lines)


def _label_for_literal(quads: list, value: str, iterations: int | None = None) -> str:
    """Find a node through stable content instead of its temporary c14n ID."""
    labels = wl_blank_node_labels(quads, iterations=iterations)
    matches = [
        labels[quad.subject.value]
        for quad in quads
        if isinstance(quad.subject, ox.BlankNode)
        and isinstance(quad.object, ox.Literal)
        and quad.object.value == value
    ]
    assert len(matches) == 1
    return matches[0]


STABLE_SINGLETON = '_:a <http://ex/p> "stable" .'


@pytest.mark.parametrize(
    ("before_extra", "after_extra"),
    [
        ("", _chain(20)),
        (_chain(20, tail="old"), _chain(20, tail="new")),
        (_chain(20), _chain(5)),
    ],
    ids=("addition", "edit", "removal"),
)
def test_default_convergence_isolated_from_disconnected_changes(
    before_extra: str, after_extra: str
) -> None:
    """A deeper disconnected component must not advance a stable component."""
    before = _canonical_quads("\n".join(filter(None, (STABLE_SINGLETON, before_extra))))
    after = _canonical_quads("\n".join(filter(None, (STABLE_SINGLETON, after_extra))))

    assert _label_for_literal(before, "stable") == _label_for_literal(after, "stable")


def _public_graph(include_chain: bool) -> Graph:
    """Keep the stable node multiply referenced so Turtle must print its label."""
    graph = Graph()
    graph.bind("ex", EX)
    stable = BNode("stable")
    graph.add((EX.left, EX.ref, stable))
    graph.add((EX.right, EX.ref, stable))
    graph.add((stable, EX.value, Literal("stable")))
    if include_chain:
        previous = BNode("chain0")
        graph.add((EX.start, EX.head, previous))
        for index in range(1, 20):
            current = BNode(f"chain{index}")
            graph.add((previous, EX.next, current))
            previous = current
    return graph


def _visible_stable_label(turtle: str) -> str:
    match = re.search(r"(_:[A-Za-z0-9_]+) ex:value \"stable\"", turtle)
    assert match is not None
    return match.group(1)


def test_public_turtle_preserves_a_visible_disconnected_label() -> None:
    """The public serializer must expose the same label after an unrelated addition."""
    before = deterministic_turtle(_public_graph(include_chain=False))
    after = deterministic_turtle(_public_graph(include_chain=True))

    assert _visible_stable_label(before) == _visible_stable_label(after)


@pytest.mark.parametrize("graph_name", ["<http://ex/stable-graph>", "_:graph"])
def test_graph_membership_does_not_join_signature_independent_components(graph_name: str) -> None:
    """IRI and blank graph names do not make unrelated blank structures neighbours."""
    stable = (
        f'<http://ex/doc> <http://ex/hasGraph> {graph_name} <http://ex/meta> .\n'
        f'<http://ex/subject> <http://ex/ref> _:stable {graph_name} .\n'
        f'_:stable <http://ex/value> "stable" {graph_name} .'
    )
    before = _canonical_quads(stable)
    after = _canonical_quads(f"{stable}\n{_chain(20)}")

    assert _label_for_literal(before, "stable") == _label_for_literal(after, "stable")

    # A blank graph name can also be a term. Relabelling must keep both roles
    # on one identifier while component-local convergence isolates the chain.
    relabelled = wl_relabel_quads(after)
    if graph_name == "_:graph":
        graph_labels = {
            quad.graph_name.value
            for quad in relabelled
            if isinstance(quad.graph_name, ox.BlankNode)
        }
        object_labels = {
            quad.object.value
            for quad in relabelled
            if isinstance(quad.object, ox.BlankNode)
            and quad.predicate.value == "http://ex/hasGraph"
        }
        assert graph_labels == object_labels


def test_shared_blank_subject_object_roles_form_one_component() -> None:
    """Subject/object adjacency propagates refinement across the whole component."""
    quads = _canonical_quads(
        "\n".join(
            (
                '<http://ex/root> <http://ex/ref> _:a .',
                '_:a <http://ex/next> _:b .',
                '_:b <http://ex/next> _:a .',
                '_:b <http://ex/value> "cycle" .',
            )
        )
    )
    labels = wl_blank_node_labels(quads)

    assert len(labels) == 2
    assert len(set(labels.values())) == 2


def test_explicit_iterations_still_run_the_requested_global_round_count() -> None:
    """An integer iteration count must not use component fixpoint stopping."""
    singleton = _canonical_quads(STABLE_SINGLETON)
    combined = _canonical_quads(f"{STABLE_SINGLETON}\n{_chain(20)}")

    one_round = _label_for_literal(singleton, "stable", iterations=1)
    four_rounds = _label_for_literal(singleton, "stable", iterations=4)

    assert one_round != four_rounds
    assert _label_for_literal(singleton, "stable") == one_round
    assert _label_for_literal(combined, "stable", iterations=4) == four_rounds


def _rendered_quads(nquads: str) -> set[str]:
    return {str(quad) for quad in wl_relabel_quads(_canonical_quads(nquads))}


def test_component_labels_ignore_input_order_and_blank_node_names() -> None:
    """Component discovery may use IDs for traversal, but signatures may not."""
    first = "\n".join((STABLE_SINGLETON, _chain(6)))
    second = "\n".join(
        reversed(
            (
                '_:renamed <http://ex/p> "stable" .',
                _chain(6, prefix="other"),
            )
        )
    )

    assert _rendered_quads(first) == _rendered_quads(second)


def test_tied_components_remain_injective() -> None:
    """Indistinguishable components still use the global canonical-order suffix."""
    labels = wl_blank_node_labels(
        _canonical_quads(
            "\n".join(
                (
                    '_:a <http://ex/p> "same" .',
                    '_:b <http://ex/p> "same" .',
                )
            )
        )
    )

    assert len(set(labels.values())) == 2
    assert len({label.split("_")[0] for label in labels.values()}) == 1
    assert sum("_" in label for label in labels.values()) == 1
