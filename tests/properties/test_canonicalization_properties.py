"""Property tests for the canonicalization contract.

``deterministic_turtle`` makes four promises. Everything a consumer does with it — committing
generated RDF, diffing it, verifying it in CI — depends on all four holding together, and the
failure mode when one breaks is silent: a file that looks fine and no longer says what it said.

===  ============================================================================
P1   **Lossless.** Parsing the output yields a graph isomorphic to the input.
P2   **Idempotent.** Canonicalizing the output reproduces it byte for byte.
P3   **Label-independent.** Two inputs differing only in blank node identifiers
     produce identical bytes. This is what makes the form *canonical*.
P4   **Order-independent.** The order triples were added in does not affect output.
===  ============================================================================

The graphs are produced by a seeded generator rather than by hand, because the shape these
promises are hardest to keep for — a list cell referenced from two places, which rdflib's
Turtle serializer inlines and thereby detaches — is the kind of shape nobody writes on
purpose. Seeds are fixed, so a failure is reproducible; the seed is reported in the assertion
message.
"""

from __future__ import annotations

import random

import pyoxigraph as ox
import pytest
from rdflib import BNode, Graph, Literal, Namespace
from rdflib.compare import isomorphic
from rdflib.namespace import RDF, XSD

from diffable_rdf import deterministic_turtle

EX = Namespace("http://example.org/")

#: Enough seeds to exercise the generator's shape space without making the suite slow.
SEEDS = list(range(40))


# ─────────────────────────────────────────────────────────────────────────────
# graph generation
# ─────────────────────────────────────────────────────────────────────────────


def _literal(rng: random.Random) -> Literal:
    kind = rng.choice(("plain", "string", "int", "double", "bool", "lang"))
    if kind == "plain":
        return Literal(rng.choice(("red", "green", "", "with space", 'quote"inside')))
    if kind == "string":
        return Literal(rng.choice(("a", "b")), datatype=XSD.string)
    if kind == "int":
        return Literal(rng.randint(-3, 3))
    if kind == "double":
        return Literal(float(rng.randint(0, 3)), datatype=XSD.double)
    if kind == "bool":
        return Literal(rng.choice((True, False)))
    return Literal(rng.choice(("hello", "bonjour")), lang=rng.choice(("en", "fr")))


def _add_list(graph: Graph, rng: random.Random, values: list) -> BNode:
    """Add an rdf:List and return its head, cell by cell so cells can be reused."""
    head = RDF.nil
    for value in reversed(values):
        cell = BNode()
        graph.add((cell, RDF.first, value))
        graph.add((cell, RDF.rest, head))
        head = cell
    return head


def _random_graph(seed: int) -> Graph:
    """A small graph covering the shapes that break naive canonicalization."""
    rng = random.Random(seed)
    graph = Graph()
    graph.bind("ex", EX)

    subjects = [EX[f"s{i}"] for i in range(rng.randint(1, 4))]
    for subject in subjects:
        graph.add((subject, RDF.type, EX.Thing))
        for _ in range(rng.randint(1, 3)):
            graph.add((subject, EX[f"p{rng.randint(0, 2)}"], _literal(rng)))

    # plain blank nodes, sometimes nested, sometimes referenced twice
    anon = [BNode() for _ in range(rng.randint(0, 3))]
    for node in anon:
        graph.add((node, EX.label, _literal(rng)))
        for _ in range(rng.randint(1, 2)):
            graph.add((rng.choice(subjects), EX.has, node))
    if len(anon) >= 2:
        graph.add((anon[0], EX.next, anon[1]))
        if rng.random() < 0.3:
            # a cycle between blank nodes: RDFC-1.0 must still terminate
            graph.add((anon[1], EX.next, anon[0]))

    # RDF lists, in the four arrangements that matter
    lists: list[BNode] = []
    for _ in range(rng.randint(0, 3)):
        values = [_literal(rng) for _ in range(rng.randint(1, 3))]
        head = _add_list(graph, rng, values)
        if head != RDF.nil:
            lists.append(head)
            graph.add((rng.choice(subjects), EX.items, head))

    if lists:
        head = rng.choice(lists)
        if rng.random() < 0.5:
            # shared head: several statements point at the same list
            graph.add((rng.choice(subjects), EX.alsoItems, head))
        if rng.random() < 0.5:
            # shared interior cell: a statement points into the middle of a chain. An inline
            # ``( … )`` consumes that cell and leaves the other reference undefined.
            interior = graph.value(head, RDF.rest)
            if interior is not None and interior != RDF.nil:
                graph.add((rng.choice(subjects), EX.tail, interior))
        if rng.random() < 0.3:
            # a list whose member is itself a list
            graph.add((rng.choice(subjects), EX.nested, _add_list(graph, rng, [head])))

    # the empty list, which is an IRI rather than a blank node
    if rng.random() < 0.3:
        graph.add((rng.choice(subjects), EX.empty, RDF.nil))

    return graph


def _canonical_dataset(dataset: ox.Dataset) -> str:
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return "\n".join(
        sorted(str(ox.Triple(quad.subject, quad.predicate, quad.object)) for quad in dataset)
    )


def _canonical_graph(graph: Graph) -> str:
    return _canonical_dataset(
        ox.Dataset(ox.parse(graph.serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES))
    )


def _canonical_turtle(text: str) -> str:
    return _canonical_dataset(ox.Dataset(ox.parse(text, format=ox.RdfFormat.TURTLE)))


def _relabelled(graph: Graph) -> Graph:
    """The same graph with every blank node given a different identifier."""
    mapping: dict[BNode, BNode] = {}

    def remap(term):
        if isinstance(term, BNode):
            return mapping.setdefault(term, BNode())
        return term

    out = Graph()
    for prefix, namespace in graph.namespaces():
        out.bind(prefix, namespace)
    for s, p, o in graph:
        out.add((remap(s), p, remap(o)))
    return out


def _reordered(graph: Graph, seed: int) -> Graph:
    """The same graph with triples inserted in a different order."""
    triples = list(graph)
    random.Random(seed).shuffle(triples)
    out = Graph()
    for prefix, namespace in graph.namespaces():
        out.bind(prefix, namespace)
    for triple in triples:
        out.add(triple)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# the four properties
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("seed", SEEDS)
def test_p1_canonical_output_is_lossless(seed: int) -> None:
    graph = _random_graph(seed)
    serialized = deterministic_turtle(graph)
    reparsed = Graph()
    reparsed.parse(data=serialized, format="turtle")
    assert len(reparsed) == len(graph), (
        f"seed {seed}: triple count changed, {len(graph)} in, {len(reparsed)} out"
    )
    assert _canonical_turtle(serialized) == _canonical_graph(graph), (
        f"seed {seed}: canonical output is not isomorphic to its input "
        f"({len(graph)} triples in, {len(reparsed)} out)"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_p2_canonicalization_is_idempotent(seed: int) -> None:
    graph = _random_graph(seed)
    once = deterministic_turtle(graph)
    reparsed = Graph()
    reparsed.parse(data=once, format="turtle")
    twice = deterministic_turtle(reparsed)
    assert twice == once, (
        f"seed {seed}: canonicalizing the canonical form changed it "
        f"({len(once)} bytes -> {len(twice)} bytes)"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_p3_output_does_not_depend_on_blank_node_labels(seed: int) -> None:
    graph = _random_graph(seed)
    assert deterministic_turtle(graph) == deterministic_turtle(_relabelled(graph)), (
        f"seed {seed}: relabelling blank nodes changed the canonical output, so the form is "
        "not canonical"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_p4_output_does_not_depend_on_insertion_order(seed: int) -> None:
    graph = _random_graph(seed)
    assert deterministic_turtle(graph) == deterministic_turtle(_reordered(graph, seed + 1)), (
        f"seed {seed}: inserting the same triples in a different order changed the output"
    )


# ─────────────────────────────────────────────────────────────────────────────
# shared RDF list structures
# ─────────────────────────────────────────────────────────────────────────────

SHARING_CASES = {
    "private_list": """
        ex:s1 ex:items ( "a" "b" ) .
    """,
    "shared_head_two_refs": """
        _:l rdf:first "a" ; rdf:rest rdf:nil .
        ex:s1 ex:items _:l .
        ex:s2 ex:items _:l .
    """,
    "shared_head_five_refs": """
        _:l rdf:first "a" ; rdf:rest rdf:nil .
        ex:s1 ex:items _:l . ex:s2 ex:items _:l . ex:s3 ex:items _:l .
        ex:s4 ex:items _:l . ex:s5 ex:items _:l .
    """,
    "shared_interior_cell": """
        _:t rdf:first "b" ; rdf:rest rdf:nil .
        _:l rdf:first "a" ; rdf:rest _:t .
        ex:s1 ex:items _:l .
        ex:s2 ex:items _:t .
    """,
    "two_lists_sharing_a_tail": """
        _:t rdf:first "z" ; rdf:rest rdf:nil .
        _:a rdf:first "a" ; rdf:rest _:t .
        _:b rdf:first "b" ; rdf:rest _:t .
        ex:s1 ex:items _:a .
        ex:s2 ex:items _:b .
    """,
    "list_containing_a_shared_list": """
        _:inner rdf:first "x" ; rdf:rest rdf:nil .
        _:outer rdf:first _:inner ; rdf:rest rdf:nil .
        ex:s1 ex:items _:outer .
        ex:s2 ex:items _:inner .
    """,
}

PREAMBLE = (
    "@prefix ex: <http://example.org/> .\n"
    "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
)


@pytest.mark.parametrize("name", sorted(SHARING_CASES))
def test_shared_list_structures_survive_canonicalization(name: str) -> None:
    """Every arrangement of shared rdf:List cells must round-trip exactly.

    The two ways compact collection syntax gets this wrong pull in opposite directions.
    ``shared_interior_cell`` loses a list entirely: the cell is consumed by an inline
    ``( … )`` and the second reference is left undefined. ``shared_head_*`` duplicates the
    list once per reference, so the triple count grows on every pass and canonicalization
    never reaches a fixed point.
    """
    graph = Graph()
    graph.parse(data=PREAMBLE + SHARING_CASES[name], format="turtle")

    once = deterministic_turtle(graph)
    reparsed = Graph()
    reparsed.parse(data=once, format="turtle")

    assert len(reparsed) == len(graph), f"{name}: triple count changed"
    assert isomorphic(reparsed, graph), f"{name}: not isomorphic to the input"
    assert deterministic_turtle(reparsed) == once, f"{name}: not idempotent"
    assert deterministic_turtle(_relabelled(graph)) == once, f"{name}: depends on bnode labels"


@pytest.mark.parametrize("name", sorted(SHARING_CASES))
def test_no_dangling_blank_node_references(name: str) -> None:
    """No statement may point at a blank node the output never defines.

    The corruption this rules out: ``ex:s2 ex:items _:t`` survives while ``_:t``'s own
    ``rdf:first``/``rdf:rest`` do not, so the constraint silently refers to nothing. The
    output parses cleanly, which is what makes it dangerous.
    """
    graph = Graph()
    graph.parse(data=PREAMBLE + SHARING_CASES[name], format="turtle")

    reparsed = Graph()
    reparsed.parse(data=deterministic_turtle(graph), format="turtle")

    defined = {s for s in reparsed.subjects() if isinstance(s, BNode)}
    referenced = {o for o in reparsed.objects() if isinstance(o, BNode)}
    assert not (referenced - defined), (
        f"{name}: {len(referenced - defined)} blank node(s) are referenced but never defined"
    )


def test_list_cells_are_neither_lost_nor_duplicated() -> None:
    """The number of rdf:List cells is preserved exactly.

    Counting cells catches both failure directions in one assertion: inlining a shared head
    duplicates cells, and inlining a shared interior cell detaches them.
    """
    graph = Graph()
    graph.parse(
        data=PREAMBLE + SHARING_CASES["two_lists_sharing_a_tail"] + SHARING_CASES["shared_head_five_refs"],
        format="turtle",
    )
    before = len(list(graph.triples((None, RDF.first, None))))

    reparsed = Graph()
    reparsed.parse(data=deterministic_turtle(graph), format="turtle")
    after = len(list(reparsed.triples((None, RDF.first, None))))

    assert after == before, f"rdf:List cells changed from {before} to {after}"


def test_repeated_canonicalization_reaches_a_fixed_point() -> None:
    """Ten passes over a graph full of shared lists must not drift.

    Duplicating a shared list is unbounded growth rather than a one-off error: on this graph
    it adds 76 further ``rdf:first`` and 76 further ``rdf:rest`` triples per pass, with no
    fixed point to converge on.
    """
    graph = Graph()
    graph.parse(data=PREAMBLE + "".join(SHARING_CASES.values()), format="turtle")

    current = deterministic_turtle(graph)
    for iteration in range(10):
        reparsed = Graph()
        reparsed.parse(data=current, format="turtle")
        nxt = deterministic_turtle(reparsed)
        assert nxt == current, f"output changed on pass {iteration + 2}"
        current = nxt

def _many_lists_sharing_tails(count: int = 12) -> Graph:
    """Many short lists whose tails are structurally identical, some multiply referenced.

    This is the shape of a real SHACL shapes graph produced from an ontology with dozens of
    enumerations: several ``sh:in`` constraints share a list, and lists that end in the same
    value share their final cell. Predicting which cells are safe to inline does not work
    here - rdflib chooses by a traversal that depends on blank node ordering - which is why
    the guarantee rests on checking the rendered output instead.
    """
    graph = Graph()
    graph.bind("ex", EX)
    tail = BNode()
    graph.add((tail, RDF.first, Literal("common")))
    graph.add((tail, RDF.rest, RDF.nil))
    for index in range(count):
        head = BNode()
        graph.add((head, RDF.first, Literal(f"v{index % 3}")))
        graph.add((head, RDF.rest, tail))
        graph.add((EX[f"shape{index}"], EX.items, head))
        if index % 4 == 0:
            # the same list referenced from a second shape
            graph.add((EX[f"other{index}"], EX.items, head))
    graph.add((EX.tailUser, EX.items, tail))
    return graph


def test_many_lists_sharing_tails_round_trip_exactly() -> None:
    graph = _many_lists_sharing_tails()
    before_cells = len(list(graph.triples((None, RDF.first, None))))

    once = deterministic_turtle(graph)
    reparsed = Graph()
    reparsed.parse(data=once, format="turtle")

    assert len(reparsed) == len(graph), f"{len(graph)} triples in, {len(reparsed)} out"
    assert len(list(reparsed.triples((None, RDF.first, None)))) == before_cells
    assert isomorphic(reparsed, graph)
    assert deterministic_turtle(reparsed) == once, "not idempotent"
    assert deterministic_turtle(_relabelled(graph)) == once, "depends on bnode labels"

    defined = {s for s in reparsed.subjects() if isinstance(s, BNode)}
    referenced = {o for o in reparsed.objects() if isinstance(o, BNode)}
    assert not (referenced - defined), "dangling blank node reference"


def test_collection_free_serializer_is_faithful_for_every_sharing_case() -> None:
    """The fallback must be correct on its own, since it is what guarantees the round trip."""
    import io

    from diffable_rdf.turtle import _NoCollectionTurtleSerializer

    for name, body in sorted(SHARING_CASES.items()):
        graph = Graph()
        graph.parse(data=PREAMBLE + body, format="turtle")

        buffer = io.BytesIO()
        _NoCollectionTurtleSerializer(graph).serialize(buffer, encoding="utf-8")
        reparsed = Graph()
        reparsed.parse(data=buffer.getvalue().decode("utf-8"), format="turtle")

        assert len(reparsed) == len(graph), f"{name}: triple count changed"
        assert isomorphic(reparsed, graph), f"{name}: not isomorphic"
        assert "( " not in buffer.getvalue().decode("utf-8"), f"{name}: used collection syntax"
