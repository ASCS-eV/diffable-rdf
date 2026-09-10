"""Exact RDF/XML literal serialization contracts."""

from __future__ import annotations

import importlib

import pyoxigraph as ox
import pytest
import rdflib
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

from diffable_rdf import canonicalize_rdf_graph

EX = Namespace("http://example.org/")


def _canonical_dataset(dataset: ox.Dataset) -> str:
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return "\n".join(
        sorted(str(ox.Triple(quad.subject, quad.predicate, quad.object)) for quad in dataset)
    )


def _canonical_graph(graph: Graph) -> str:
    source_nt = graph.serialize(format="nt")
    return _canonical_dataset(ox.Dataset(ox.parse(source_nt, format=ox.RdfFormat.N_TRIPLES)))


def _canonical_xml(text: str) -> str:
    return _canonical_dataset(ox.Dataset(ox.parse(text, format=ox.RdfFormat.RDF_XML)))


@pytest.mark.parametrize(
    "value",
    ["a\rb", "a\r\nb", "ex:thing\\. "],
    ids=["cr", "crlf", "curie-like-text"],
)
def test_rdf_xml_preserves_known_lossy_literal_values(value: str) -> None:
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal(value)))
    graph.add((EX.other, EX.p, EX.o))

    result = canonicalize_rdf_graph(graph, output_format="xml")

    assert _canonical_xml(result) == _canonical_graph(graph)
    assert str(next(Graph().parse(data=result, format="xml").objects(EX.s, EX.p))) == value


def test_rdf_xml_preserves_diverse_literal_content_and_identity() -> None:
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.unicode, Literal('Grüße 東京\tline\nreturn\rCRLF\r\n"<&')))
    graph.add((EX.s, EX.typed, Literal("typed\r\nvalue", datatype=EX.code)))
    graph.add((EX.s, EX.integer, Literal("01", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.integer, Literal("1", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.language, Literal("bonjour\rmonde", lang="fr-CA")))
    graph.add((EX.s, EX.curie_text, Literal("ex:thing\\. ")))

    result = canonicalize_rdf_graph(graph, output_format="xml")
    reparsed = Graph().parse(data=result, format="xml")

    assert _canonical_xml(result) == _canonical_graph(graph)
    assert str(next(reparsed.objects(EX.s, EX.typed))) == "typed\r\nvalue"
    language_literal = next(reparsed.objects(EX.s, EX.language))
    assert str(language_literal) == "bonjour\rmonde"
    assert language_literal.language == "fr-ca"
    assert "\r" not in result
    assert "&#xD;" in result
    assert "ex:thing\\. " in result
    assert "&amp;" in result and "&lt;" in result


@pytest.mark.parametrize("output_format", ["xml", "XML", "rdf/xml", "RDF/XML"])
def test_rdf_xml_aliases_use_exact_round_trip_guard(output_format: str) -> None:
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("a\r\nb")))

    result = canonicalize_rdf_graph(graph, output_format=output_format)

    assert _canonical_xml(result) == _canonical_graph(graph)
    assert str(next(Graph().parse(data=result, format="xml").objects())) == "a\r\nb"


@pytest.mark.parametrize("output_format", ["xml", "XML", "rdf/xml", "RDF/XML"])
def test_rdf_xml_aliases_work_on_degraded_fallback(output_format: str) -> None:
    graph = Graph()
    graph.add((URIRef("relative/s"), EX.p, Literal("a\r\nb")))

    result = canonicalize_rdf_graph(graph, output_format=output_format)
    reparsed = Graph().parse(data=result, format="xml")

    assert str(next(reparsed.objects(URIRef("relative/s"), EX.p))) == "a\r\nb"


@pytest.mark.parametrize("value", ["a\x00b", "a\x01b", "a\x0bb", "a\ufffeb"])
def test_rdf_xml_rejects_characters_forbidden_by_xml_10(value: str) -> None:
    graph = Graph()
    graph.add((EX.s, EX.p, Literal(value)))

    with pytest.raises(ValueError, match=r"RDF/XML uses XML 1\.0.*U\+[0-9A-F]{4}"):
        canonicalize_rdf_graph(graph, output_format="xml")


def test_rdf_xml_rejects_forbidden_characters_in_serializer_metadata() -> None:
    graph = Graph()
    graph.bind("bad\x01", EX)
    graph.add((EX.s, EX.p, Literal("value")))

    with pytest.raises(ValueError, match=r"RDF/XML uses XML 1\.0.*U\+0001"):
        canonicalize_rdf_graph(graph, output_format="xml")


@pytest.mark.parametrize(
    "replacement",
    [
        b"<rdf:RDF>",
        (
            b'<?xml version="1.0"?>\n'
            b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
            b'xmlns:ex="http://example.org/">\n'
            b'<rdf:Description rdf:about="http://example.org/s">'
            b'<ex:p>changed</ex:p></rdf:Description></rdf:RDF>'
        ),
    ],
    ids=["malformed", "changed-term"],
)
def test_rdf_xml_guard_rejects_corrupted_serializer_output(
    monkeypatch: pytest.MonkeyPatch, replacement: bytes
) -> None:
    canonicalize_module = importlib.import_module("diffable_rdf.canonicalize")
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("original")))
    monkeypatch.setattr(canonicalize_module.ox, "serialize", lambda *args, **kwargs: replacement)

    with pytest.raises(ValueError, match="does not (parse back|round-trip)"):
        canonicalize_rdf_graph(graph, output_format="xml")


def test_rdf_xml_is_stable_and_does_not_mutate_input_or_global_settings() -> None:
    graph = Graph(base="http://example.org/base/")
    graph.bind("ex", EX)
    graph.add((URIRef("relative/s"), EX.p, Literal("a\r\nb")))
    before_triples = set(graph)
    before_namespaces = list(graph.namespace_manager.namespaces())
    before_base = graph.base
    before_normalize = rdflib.NORMALIZE_LITERALS

    first = canonicalize_rdf_graph(graph, output_format="xml")
    second = canonicalize_rdf_graph(graph, output_format="xml")

    assert first == second
    assert str(next(Graph().parse(data=first, format="xml").objects())) == "a\r\nb"
    assert set(graph) == before_triples
    assert list(graph.namespace_manager.namespaces()) == before_namespaces
    assert graph.base == before_base
    assert rdflib.NORMALIZE_LITERALS is before_normalize
