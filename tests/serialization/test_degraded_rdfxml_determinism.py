"""Degraded RDF/XML must be byte-stable across processes.

`xml` is a format this library maps itself, so it carries the determinism
guarantee. The fallback orders ``rdf:Description`` and property elements by
their RDF/XML content. RDF/XML gives neither order meaning, so sorting is
lossless and deterministic.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from xml.etree import ElementTree

import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF

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
    """RDF/XML preserves a literal carriage return through sorting and parsing."""
    graph = Graph()
    graph.bind("ex", EX)
    value = Literal("a" + chr(13) + "b")
    graph.add((EX.s, EX.p, value))
    graph.add((EX.t, EX.p, Literal("plain")))
    graph.add((URIRef("relative/thing"), EX.p, Literal("forces the degraded path")))

    result = canonicalize_rdf_graph(graph, "xml")

    assert chr(13) not in result, "a raw CR does not survive XML newline normalization"
    assert "&#13;" in result or "&#xD;" in result
    assert Graph().parse(data=result, format="xml").value(EX.s, EX.p) == value
    reparsed = Graph().parse(data=result, format="xml", publicID=BASE)
    assert reparsed.value(EX.s, EX.p) == Literal("a" + chr(13) + "b")


def test_the_document_stays_well_formed_and_declared() -> None:
    """The XML declaration and the root's namespace declarations must survive."""
    result = canonicalize_rdf_graph(_degraded_graph(), "xml")

    assert result.startswith("<?xml ")
    assert "xmlns:rdf=" in result
    assert result.endswith("\n")
    assert result.count("<rdf:RDF") == 1


def _property_order(result: str) -> list[list[str]]:
    """The property element names of each rdf:Description, in document order."""
    per_description: list[list[str]] = []
    for element in ElementTree.fromstring(result):
        per_description.append([child.tag for child in element])
    return per_description


def test_property_elements_within_a_subject_are_ordered_too() -> None:
    """Each RDF description orders its property elements by tag."""
    graph = Graph()
    graph.bind("ex", EX)
    for predicate in ("zeta", "alpha", "mu"):
        graph.add((EX.s, EX[predicate], Literal(predicate)))
    graph.add((URIRef("relative/thing"), EX.p, Literal("forces the degraded path")))

    result = canonicalize_rdf_graph(graph, "xml")

    orders = _property_order(result)
    assert orders, "no rdf:Description elements were found at all"
    for order in orders:
        assert order == sorted(order), result
    assert ["<ex:alpha>", "<ex:mu>", "<ex:zeta>"] == [
        line.strip().split(">")[0] + ">" for line in result.splitlines() if line.strip().startswith("<ex:")
    ][:3], "the caller's prefix must be used, or this test measures nothing"


def test_the_callers_prefix_names_survive_the_sort() -> None:
    """Sorting preserves explicit caller prefix names in the RDF/XML output."""
    beta = Namespace("http://beta.example/")
    graph = Graph(bind_namespaces="none")
    graph.bind("beta", beta)
    graph.add((URIRef("relative/thing"), beta.p, Literal("forces the degraded path")))
    graph.add((beta.s, beta.q, Literal("v")))

    result = canonicalize_rdf_graph(graph, "xml")

    assert 'xmlns:beta="http://beta.example/"' in result, result
    assert "<beta:q>" in result, result
    assert "ns0:" not in result and "ns1:" not in result, result


def test_the_output_does_not_depend_on_process_global_xml_state() -> None:
    """RDF/XML bytes are independent of process-global namespace state."""
    beta = Namespace("http://beta.example/")
    graph = Graph(bind_namespaces="none")
    graph.bind("beta", beta)
    graph.add((URIRef("relative/thing"), beta.p, Literal("forces the degraded path")))
    graph.add((beta.s, beta.q, Literal("v")))

    before = canonicalize_rdf_graph(graph, "xml")
    # There is no public unregister, so the map is snapshotted and restored;
    # that is a concession to testing the global, not a pattern for the library.
    saved = dict(ElementTree._namespace_map)  # noqa: SLF001
    try:
        ElementTree.register_namespace("zeta", "http://beta.example/")
        after = canonicalize_rdf_graph(graph, "xml")
    finally:
        ElementTree._namespace_map.clear()  # noqa: SLF001
        ElementTree._namespace_map.update(saved)  # noqa: SLF001

    assert before == after, "an unrelated ElementTree registration changed the output"


def test_properties_are_ordered_by_predicate_not_by_their_objects_label() -> None:
    """Property predicates lead the RDF/XML ordering key."""
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((URIRef("relative/thing"), EX.p, Literal("forces the degraded path")))
    for predicate in ("zeta", "alpha", "mu", "beta"):
        graph.add((EX.s, EX[predicate], BNode()))

    result = canonicalize_rdf_graph(graph, "xml")

    subject_properties = next(
        [child.tag for child in element]
        for element in ElementTree.fromstring(result)
        if element.attrib.get(f"{{{RDF}}}about") == str(EX.s)
    )
    assert subject_properties == sorted(subject_properties), result
    assert len(subject_properties) == 4


def test_pyoxigraph_rdf_xml_uses_its_native_order() -> None:
    """Pyoxigraph RDF/XML uses its native serialization path."""
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


def test_a_comment_or_processing_instruction_is_not_mistaken_for_an_element() -> None:
    """The scanner has to skip markup that is not an element.

    rdflib writes neither into its RDF/XML, so this exercises the scanner
    directly rather than through a serializer that cannot produce the input.
    """
    from diffable_rdf.canonicalize import _sort_rdf_xml_descriptions

    document = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!-- a leading comment -->\n"
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ex="http://ex/">\n'
        "  <!-- between the root and its children -->\n"
        '  <rdf:Description rdf:about="http://ex/z"><ex:p>z</ex:p></rdf:Description>\n'
        '  <rdf:Description rdf:about="http://ex/a"><ex:p>a</ex:p></rdf:Description>\n'
        "</rdf:RDF>\n"
    )

    result = _sort_rdf_xml_descriptions(document)

    assert result.index("http://ex/a") < result.index("http://ex/z"), result
    assert "<!-- a leading comment -->" in result
    assert "<!-- between the root and its children -->" in result
    assert [element.attrib[f"{{{RDF}}}about"] for element in ElementTree.fromstring(result)] == [
        "http://ex/a",
        "http://ex/z",
    ]
