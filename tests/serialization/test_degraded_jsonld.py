"""Structural contracts for the degraded expanded JSON-LD serializer."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from urllib.parse import urljoin

import pytest
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef, Variable
from rdflib.compare import isomorphic
from rdflib.namespace import XSD

from diffable_rdf import canonicalize_rdf_graph

EX = Namespace("http://example.org/")
BASE = "https://base.example/root/"


def test_degraded_json_ld_is_reproducible_across_processes() -> None:
    """Relative-node JSON-LD is stable across graph order and hash seeds."""
    script = textwrap.dedent(
        """
        from rdflib import BNode, Graph, Literal, Namespace, URIRef
        from diffable_rdf import canonicalize_rdf_graph
        import sys
        EX = Namespace("http://example.org/")
        seed = int(sys.argv[1])
        graph = Graph()
        graph.bind("ex", EX)
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
            graph.add(triple)
        sys.stdout.write(canonicalize_rdf_graph(graph, output_format="json-ld"))
        """
    )
    outputs = {
        subprocess.run(
            [sys.executable, "-c", script, str(seed)],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        ).stdout
        for seed in (1, 7, 23, 101, 997)
    }
    assert len(outputs) == 1, "degraded JSON-LD differs between interpreter processes"


def _resolve_relative_nodes(graph: Graph) -> Graph:
    """Apply the same explicit document base used to parse JSON-LD output."""
    resolved = Graph()

    def resolve(term):
        if isinstance(term, URIRef) and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", str(term)):
            return URIRef(urljoin(BASE, str(term)))
        return term

    for subject, predicate, obj in graph:
        resolved.add((resolve(subject), predicate, resolve(obj)))
    return resolved


def test_degraded_json_ld_rejects_literal_predicates() -> None:
    """JSON-LD rejects generalized predicate terms without omitting triples."""
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("kept")))
    graph.addN([(EX.s, Literal("literal-predicate"), Literal("unsupported"), graph)])
    with pytest.raises(ValueError, match="JSON-LD.*predicate.*Literal"):
        canonicalize_rdf_graph(graph, output_format="json-ld")


def _degraded_structure_graph() -> Graph:
    graph = Graph()
    tail = BNode("tail")
    left = BNode("left")
    right = BNode("right")
    graph.add((tail, RDF.first, Literal("tail")))
    graph.add((tail, RDF.rest, RDF.nil))
    graph.add((left, RDF.first, Literal("left")))
    graph.add((left, RDF.rest, tail))
    graph.add((right, RDF.first, Literal("right")))
    graph.add((right, RDF.rest, tail))
    graph.add((EX.left, EX.items, left))
    graph.add((EX.right, EX.items, right))

    cycle_a = BNode("cycle-a")
    cycle_b = BNode("cycle-b")
    graph.add((cycle_a, RDF.first, Literal("a")))
    graph.add((cycle_a, RDF.rest, cycle_b))
    graph.add((cycle_b, RDF.first, Literal("b")))
    graph.add((cycle_b, RDF.rest, cycle_a))
    graph.add((EX.cycle1, EX.items, cycle_a))
    graph.add((EX.cycle2, EX.items, cycle_a))

    graph.add((URIRef("relative/subject"), EX.link, URIRef("../target")))
    return graph


def test_degraded_json_ld_preserves_shared_cells_references_and_cycles() -> None:
    """Expanded references retain every RDF list cell and graph edge."""
    graph = _degraded_structure_graph()
    result = canonicalize_rdf_graph(graph, output_format="json-ld")
    reparsed = Graph().parse(data=result, format="json-ld", publicID=BASE)

    assert "@list" not in result
    assert len(list(reparsed.triples((None, RDF.first, None)))) == 5
    assert len(list(reparsed.triples((None, RDF.rest, None)))) == 5
    assert len(reparsed) == len(graph)
    assert isomorphic(reparsed, _resolve_relative_nodes(graph))

    left_tail = reparsed.value(reparsed.value(EX.left, EX.items), RDF.rest)
    right_tail = reparsed.value(reparsed.value(EX.right, EX.items), RDF.rest)
    assert left_tail == right_tail

    cycle_start = reparsed.value(EX.cycle1, EX.items)
    assert reparsed.value(EX.cycle2, EX.items) == cycle_start
    assert reparsed.value(reparsed.value(cycle_start, RDF.rest), RDF.rest) == cycle_start


@pytest.mark.parametrize(
    "output_format",
    ["json-ld", "jsonld", "application/ld+json", "JSON-LD", "JSONLD", "APPLICATION/LD+JSON"],
)
def test_degraded_json_ld_aliases_are_deterministic_and_leave_input_unchanged(
    output_format: str,
) -> None:
    """Every JSON-LD alias uses the same writer without mutating caller terms."""
    graph = _degraded_structure_graph()
    before = set(graph)

    result = canonicalize_rdf_graph(graph, output_format=output_format)

    assert result == canonicalize_rdf_graph(graph, output_format="json-ld")
    assert set(graph) == before


def test_degraded_json_ld_preserves_literal_lexical_strings_and_annotations() -> None:
    """Literal values stay strings with their complete language or datatype."""
    graph = Graph()
    subject = URIRef("relative/literals")
    graph.add((subject, EX.plain, Literal("plain")))
    graph.add((subject, EX.integer, Literal("01", datatype=XSD.integer, normalize=False)))
    graph.add((subject, EX.label, Literal("Hallo", lang="de-AT")))
    graph.add((subject, RDF.type, EX.Thing))

    document = json.loads(canonicalize_rdf_graph(graph, output_format="json-ld"))
    node = next(item for item in document if item["@id"] == "relative/literals")

    assert node[str(EX.plain)] == [{"@value": "plain"}]
    assert node[str(EX.integer)] == [{"@type": str(XSD.integer), "@value": "01"}]
    assert node[str(EX.label)] == [{"@language": "de-AT", "@value": "Hallo"}]
    assert node[str(RDF.type)] == [{"@id": str(EX.Thing)}]
    assert isinstance(node[str(EX.integer)][0]["@value"], str)


def test_normal_json_ld_path_still_uses_pyoxigraph(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fully representable absolute graph stays on the primary serializer."""
    import diffable_rdf.canonicalize as canonicalize_module

    def fail_if_called(_graph: Graph) -> str:
        raise AssertionError("degraded writer used for a normal graph")

    monkeypatch.setattr(canonicalize_module, "serialize_expanded_jsonld", fail_if_called)
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("normal")))

    result = canonicalize_rdf_graph(graph, output_format="json-ld")

    assert isomorphic(Graph().parse(data=result, format="json-ld"), graph)


@pytest.mark.parametrize(
    ("triple", "message"),
    [
        ((Literal("subject"), EX.p, Literal("value")), r"subject.*Literal"),
        ((EX.s, Literal("predicate"), Literal("value")), r"predicate.*Literal"),
        ((EX.s, BNode("predicate"), Literal("value")), r"predicate.*BNode"),
        ((EX.s, URIRef("relative/predicate"), Literal("value")), r"absolute IRI.*predicate"),
        (
            (EX.s, EX.p, Literal("value", datatype=URIRef("relative/datatype"), normalize=False)),
            r"absolute IRI.*datatype",
        ),
        ((URIRef("_:iri-shaped"), EX.p, Literal("value")), r"URIRef beginning.*subject"),
        ((EX.s, EX.p, URIRef("_:iri-shaped")), r"URIRef beginning.*object"),
        ((EX.s, EX.p, Variable("unsupported")), r"object.*Variable"),
    ],
)
def test_degraded_json_ld_rejects_terms_outside_interoperable_subset(triple, message: str) -> None:
    """Terms outside the interoperable fallback subset fail before serialization."""
    graph = Graph()
    graph.add(triple)
    graph.add((URIRef("relative/trigger"), EX.valid, Literal("forces fallback")))

    with pytest.raises(ValueError, match=message):
        canonicalize_rdf_graph(graph, output_format="json-ld")
