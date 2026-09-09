"""Degraded RDF/XML must be byte-stable across processes.

`xml` is a format this library maps itself, so it carries the determinism
guarantee. The fallback goes through rdflib's RDF/XML serializer, which orders
both its ``rdf:Description`` elements and the property elements inside them by
its own graph traversal — measured at 6 distinct documents over 6 hash seeds
for one graph, differing in element order alone. RDF/XML gives neither order
any meaning, so they are sorted, exactly as the line-oriented branch already
sorts N-Triples lines against the same serializer's instability.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph

EX = Namespace("http://example.org/")
BASE = "https://base.example/root/"
HASH_SEEDS = (0, 1, 2, 3, 5, 8)

# A hub referenced from several subjects, a shared list tail, a deep chain and a
# subject with two properties: enough for a traversal-ordered serializer to
# disagree with itself at both levels.
BUILD = """
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
EX = Namespace("http://example.org/")
graph = Graph()
graph.bind("ex", EX)
hub = BNode()
for i in range(4):
    graph.add((EX[f"s{i}"], EX.ref, hub))
graph.add((hub, EX.value, Literal("hub")))
graph.add((hub, EX.other, Literal("second property on one subject")))
cells = [BNode() for _ in range(6)]
for i, cell in enumerate(cells):
    graph.add((cell, RDF.first, Literal(f"v{i}")))
    graph.add((cell, RDF.rest, cells[i + 1] if i + 1 < len(cells) else RDF.nil))
graph.add((EX.a, EX.items, cells[0]))
graph.add((EX.b, EX.items, cells[3]))
graph.add((URIRef("relative/thing"), EX.p, Literal("forces the degraded path")))
"""


def _degraded_graph() -> Graph:
    namespace: dict[str, object] = {}
    exec(BUILD, namespace)  # noqa: S102 - the same source the subprocess runs
    return namespace["graph"]  # type: ignore[return-value]


@pytest.mark.parametrize("output_format", ["xml", "rdf/xml"])
def test_degraded_rdf_xml_is_byte_identical_across_processes(output_format: str) -> None:
    """Hash seeds, not repeats: the traversal is stable within one process."""
    script = BUILD + textwrap.dedent(
        """
        import sys
        from diffable_rdf import canonicalize_rdf_graph
        sys.stdout.write(canonicalize_rdf_graph(graph, output_format=sys.argv[1]))
        """
    )
    outputs = {
        subprocess.run(
            [sys.executable, "-c", script, output_format],
            capture_output=True, text=True, check=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        ).stdout
        for seed in HASH_SEEDS
    }
    assert len(outputs) == 1, (
        f"degraded {output_format} produced {len(outputs)} distinct documents "
        f"over {len(HASH_SEEDS)} hash seeds"
    )


def test_sorting_preserves_the_graph() -> None:
    """Reordering must not drop, duplicate or alter a statement."""
    graph = _degraded_graph()
    result = canonicalize_rdf_graph(graph, "xml")
    reparsed = Graph().parse(data=result, format="xml", publicID=BASE)

    resolved = Graph()
    for subject, predicate, obj in graph:
        resolved.add((
            URIRef(BASE + str(subject)) if isinstance(subject, URIRef) and "://" not in str(subject) else subject,
            predicate,
            URIRef(BASE + str(obj)) if isinstance(obj, URIRef) and "://" not in str(obj) else obj,
        ))
    assert len(reparsed) == len(graph)
    assert isomorphic(reparsed, resolved)


def test_a_literal_carriage_return_still_survives_the_sort() -> None:
    """The sort re-serializes the tree, so the CR protection must outlast it."""
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("a" + chr(13) + "b")))
    graph.add((EX.t, EX.p, Literal("plain")))
    graph.add((URIRef("relative/thing"), EX.p, Literal("forces the degraded path")))

    result = canonicalize_rdf_graph(graph, "xml")

    assert "&#xD;" in result
    reparsed = Graph().parse(data=result, format="xml", publicID=BASE)
    assert reparsed.value(EX.s, EX.p) == Literal("a" + chr(13) + "b")


def test_the_document_stays_well_formed_and_declared() -> None:
    """The XML declaration and the root's namespace declarations must survive."""
    result = canonicalize_rdf_graph(_degraded_graph(), "xml")

    assert result.startswith("<?xml ")
    assert "xmlns:rdf=" in result
    assert result.endswith("\n")
    assert result.count("<rdf:RDF") == 1


def test_property_elements_within_a_subject_are_ordered_too() -> None:
    """The first fix only sorted the top level, and that was not enough."""
    graph = Graph()
    graph.bind("ex", EX)
    for predicate in ("zeta", "alpha", "mu"):
        graph.add((EX.s, EX[predicate], Literal(predicate)))
    graph.add((URIRef("relative/thing"), EX.p, Literal("forces the degraded path")))

    result = canonicalize_rdf_graph(graph, "xml")
    order = [
        line.strip().split(">")[0].lstrip("<")
        for line in result.splitlines()
        if line.strip().startswith("<ex:")
    ]
    assert order == sorted(order), result


def test_the_normal_path_is_untouched() -> None:
    """pyoxigraph's RDF/XML is already stable; the sort must not reach it."""
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("v")))
    graph.add((EX.t, EX.p, Literal("w")))

    result = canonicalize_rdf_graph(graph, "xml")

    # pyoxigraph writes a self-closing description with attributes, which the
    # ElementTree round trip would reformat; seeing it here proves the sort did
    # not run on this path.
    assert "rdf:Description" in result
    assert isomorphic(Graph().parse(data=result, format="xml"), graph)
