"""Base-IRI contracts for every IRI position read by standard parsers."""

from __future__ import annotations

import pyoxigraph as ox
import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import XSD

import diffable_rdf.canonicalize as canonicalize_module
from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

EX = Namespace("http://example.org/")
TURTLE_FAMILY = ["turtle", "ttl", "trig", "n3"]
XML_ALIASES = ["xml", "rdf/xml"]
PARSER = {"ttl": "turtle", "rdf/xml": "xml"}
OX_FORMAT = {
    "turtle": ox.RdfFormat.TURTLE,
    "ttl": ox.RdfFormat.TURTLE,
    "trig": ox.RdfFormat.TRIG,
    "n3": ox.RdfFormat.N3,
    "xml": ox.RdfFormat.RDF_XML,
    "rdf/xml": ox.RdfFormat.RDF_XML,
}


def _hash_base_graph() -> Graph:
    graph = Graph(base="http://ex.org/d#")
    graph.add((URIRef("http://ex.org/d#a"), URIRef("http://ex.org/d#p"), URIRef("http://ex.org/d#b")))
    return graph


@pytest.mark.parametrize("output_format", TURTLE_FAMILY + ["xml", "rdf/xml"])
def test_a_fragment_base_preserves_the_terms(output_format: str) -> None:
    """A fragment base preserves each IRI term in every verified format."""
    graph = _hash_base_graph()

    result = canonicalize_rdf_graph(graph, output_format=output_format)
    reparsed = Graph().parse(data=result, format=PARSER.get(output_format, output_format))

    assert isomorphic(reparsed, graph)
    assert {str(term) for triple in reparsed for term in triple} == {
        "http://ex.org/d#a",
        "http://ex.org/d#p",
        "http://ex.org/d#b",
    }
    assert "##" not in result


def test_deterministic_turtle_preserves_fragment_base_terms() -> None:
    """Deterministic Turtle preserves terms from a graph with a fragment base."""
    graph = _hash_base_graph()

    result = deterministic_turtle(graph)

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)


def test_deterministic_turtle_preserves_hash_path_and_slash_bases() -> None:
    """Hash, path, and slash bases preserve all graph terms."""
    for base in ("http://example.org/d#", "http://example.org/d", "http://example.org/d/"):
        graph = Graph(base=base)
        graph.add((URIRef("http://example.org/d#a"), EX.pred, Literal("v0")))
        graph.add((URIRef("http://example.org/d#b"), EX.pred, Literal("v1")))
        result = deterministic_turtle(graph)
        assert isomorphic(Graph().parse(data=result, format="turtle"), graph), base


def test_canonicalize_rdf_graph_handles_a_relative_base() -> None:
    """A relative RDFLib base produces a complete Turtle document."""
    graph = Graph(base="book/")
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("v")))
    assert "http://example.org/s" in canonicalize_rdf_graph(graph, output_format="turtle")


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
def test_an_ordinary_base_still_relativizes(output_format: str) -> None:
    """A base that verifies keeps its relative output."""
    graph = Graph(base="http://ex.org/d/")
    graph.add((URIRef("http://ex.org/d/a"), URIRef("http://ex.org/d/p"), Literal("v")))

    result = canonicalize_rdf_graph(graph, output_format=output_format)
    reparsed = Graph().parse(data=result, format=output_format)

    assert result == (
        '@base <http://ex.org/d/> .\n'
        '@prefix xsd: <//www.w3.org/2001/XMLSchema#> .\n'
        '<a> <p> "v" .\n'
    )
    assert isomorphic(reparsed, graph)


def test_removing_a_base_after_failed_verification_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """The serializer reports the verification-driven base retry."""
    import logging

    graph = _hash_base_graph()
    original = canonicalize_module._assert_round_trips
    attempts = 0
    logger = logging.getLogger("diffable_rdf.canonicalize")
    records: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    handler = Capture()
    logger.addHandler(handler)
    try:
        def fail_once(*args: object, **kwargs: object) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError("verification failed")
            original(*args, **kwargs)

        monkeypatch.setattr(canonicalize_module, "_assert_round_trips", fail_once)
        result = canonicalize_rdf_graph(graph, "turtle")
    finally:
        logger.removeHandler(handler)

    _assert_exact_parser_fidelity(graph, result, "turtle")
    assert any("failed round-trip verification" in message for message in records), records


def _all_iris(graph: Graph) -> set[str]:
    """Collect direct and datatype IRI terms from a graph."""
    return {
        str(iri)
        for triple in graph
        for term in triple
        for iri in (
            (term,)
            if isinstance(term, URIRef)
            else (term.datatype,)
            if isinstance(term, Literal) and term.datatype is not None
            else ()
        )
    }


def _assert_exact_parser_fidelity(graph: Graph, result: str, output_format: str) -> Graph:
    """Assert RDFLib and pyoxigraph preserve the same graph terms."""
    reparsed = Graph().parse(data=result, format=PARSER.get(output_format, output_format))

    assert isomorphic(reparsed, graph)
    assert _all_iris(reparsed) == _all_iris(graph)
    assert set(ox.parse(result, format=OX_FORMAT[output_format])) == set(
        ox.parse(graph.serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES)
    )
    return reparsed


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
@pytest.mark.parametrize(
    "base",
    ["http://ex/d/", "http://ex/d", "http://ex/d?x=", "urn:example:", "http://ex/d#"],
)
def test_an_equal_base_namespace_preserves_every_iri_position(base: str, output_format: str) -> None:
    """An equal-base prefix remains available for terms in every IRI position."""
    graph = Graph(base=base, bind_namespaces="none")
    graph.bind("base", URIRef(base))
    graph.add((URIRef(base + "subject"), URIRef(base + "predicate"), URIRef(base + "object")))
    graph.add(
        (
            URIRef(base + "subject"),
            URIRef(base + "predicate"),
            Literal("v", datatype=URIRef(base + "datatype")),
        )
    )
    before_triples = set(graph)
    before_base = graph.base
    before_bindings = tuple(graph.namespaces())

    result = canonicalize_rdf_graph(graph, output_format)
    reparsed = _assert_exact_parser_fidelity(graph, result, output_format)

    assert canonicalize_rdf_graph(graph, output_format) == result
    assert "@prefix base:" in result
    assert "base:subject base:predicate" in result
    assert str(reparsed.namespace_manager.store.namespace("base")) == base
    assert tuple(graph.namespaces()) == before_bindings
    assert graph.base == before_base
    assert set(graph) == before_triples


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
def test_an_unprefixed_query_base_retries_without_base_and_preserves_datatypes(
    output_format: str
) -> None:
    """A query base falls back to absolute terms when relative terms do not verify."""
    base = "http://ex/d?x="
    graph = Graph(base=base, bind_namespaces="none")
    graph.add((URIRef(base + "subject"), URIRef(base + "predicate"), URIRef(base + "object")))
    graph.add(
        (
            URIRef(base + "subject"),
            URIRef(base + "predicate"),
            Literal("v", datatype=URIRef(base + "datatype")),
        )
    )
    before_triples = set(graph)
    before_base = graph.base
    before_bindings = tuple(graph.namespaces())

    result = canonicalize_rdf_graph(graph, output_format)
    _assert_exact_parser_fidelity(graph, result, output_format)

    assert canonicalize_rdf_graph(graph, output_format) == result
    assert tuple(graph.namespaces()) == before_bindings
    assert graph.base == before_base
    assert set(graph) == before_triples


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
def test_a_datatype_only_query_base_retries_without_base(output_format: str) -> None:
    """A datatype IRI alone can require the no-base rendering."""
    base = "http://ex/d?x="
    graph = Graph(base=base, bind_namespaces="none")
    graph.add(
        (
            URIRef("http://other/s"),
            URIRef("http://other/p"),
            Literal("v", datatype=URIRef(base + "type")),
        )
    )

    result = canonicalize_rdf_graph(graph, output_format)
    _assert_exact_parser_fidelity(graph, result, output_format)

    assert canonicalize_rdf_graph(graph, output_format) == result


@pytest.mark.parametrize("output_format", XML_ALIASES)
@pytest.mark.parametrize("force_retry", [False, True])
@pytest.mark.parametrize(
    "datatype",
    [
        pytest.param(XSD.integer, id="xsd-integer"),
        pytest.param(URIRef("http://custom.example/type"), id="custom"),
    ],
)
def test_rdf_xml_retries_without_base_for_typed_literal_namespaces(
    output_format: str,
    force_retry: bool,
    datatype: URIRef,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RDF/XML retries without a base while retaining its namespace selection."""
    base = "http://ex.org/d/"
    graph = Graph(base=base, bind_namespaces="none")
    graph.add((URIRef(base + "s"), URIRef("http://ex.org/p"), Literal("1", datatype=datatype, normalize=False)))
    original = canonicalize_module.ox.serialize
    original_assertion = canonicalize_module._assert_round_trips
    validations = 0
    calls: list[dict[str, object]] = []

    def record(*args: object, **kwargs: object) -> bytes:
        calls.append(kwargs)
        return original(*args, **kwargs)

    def fail_once(*args: object, **kwargs: object) -> None:
        nonlocal validations
        validations += 1
        if validations == 1:
            raise ValueError("verification failed")
        original_assertion(*args, **kwargs)

    monkeypatch.setattr(canonicalize_module.ox, "serialize", record)
    if force_retry:
        monkeypatch.setattr(canonicalize_module, "_assert_round_trips", fail_once)
    result = canonicalize_rdf_graph(graph, output_format)
    _assert_exact_parser_fidelity(graph, result, output_format)

    if force_retry:
        assert "xml:base=" not in result
        assert len(calls) == 2
        assert calls[0]["prefixes"] == calls[1]["prefixes"]
        assert calls[0]["base_iri"] == base
        assert "base_iri" not in calls[1]


@pytest.mark.parametrize(
    ("output_format", "base_marker"),
    [
        pytest.param("turtle", "@base <http://ex/d/>", id="turtle"),
        pytest.param("xml", 'xml:base="http://ex/d/"', id="xml"),
        pytest.param("rdf/xml", 'xml:base="http://ex/d/"', id="rdf-xml"),
    ],
)
def test_a_verified_base_does_not_serialize_twice(
    output_format: str, base_marker: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful first rendering does not take the no-base retry."""
    graph = Graph(base="http://ex/d/", bind_namespaces="none")
    graph.add((URIRef("http://ex/d/a"), URIRef("http://ex/d/p"), Literal("v")))
    original = canonicalize_module.ox.serialize
    calls: list[dict[str, object]] = []

    def record(*args: object, **kwargs: object) -> bytes:
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(canonicalize_module.ox, "serialize", record)
    result = canonicalize_rdf_graph(graph, output_format)

    assert base_marker in result
    assert len(calls) == 1


@pytest.mark.parametrize("output_format", ["turtle", *XML_ALIASES])
def test_an_unrelated_backend_error_is_not_retried(
    output_format: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only rejected prefix and base values receive serializer recovery."""
    graph = Graph(base="http://ex/d/")
    graph.add((URIRef("http://ex/d/a"), URIRef("http://ex/d/p"), Literal("v")))
    calls = 0

    def fail(*args: object, **kwargs: object) -> bytes:
        nonlocal calls
        calls += 1
        raise ValueError("backend failed")

    monkeypatch.setattr(canonicalize_module.ox, "serialize", fail)
    with pytest.raises(ValueError, match="backend failed"):
        canonicalize_rdf_graph(graph, output_format)
    assert calls == 1


@pytest.mark.parametrize("output_format", ["turtle", *XML_ALIASES])
def test_a_failed_no_base_retry_propagates_its_validation_error(
    output_format: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bounded retry still requires a successful final verification."""
    graph = Graph(base="http://ex/d?x=", bind_namespaces="none")
    graph.add((URIRef("http://ex/d?x=s"), URIRef("http://ex/d?x=p"), Literal("v")))
    original = canonicalize_module._assert_round_trips
    calls = 0

    def fail(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise ValueError("validation failed")

    monkeypatch.setattr(canonicalize_module, "_assert_round_trips", fail)
    with pytest.raises(ValueError, match="validation failed"):
        canonicalize_rdf_graph(graph, output_format)
    assert calls == 2
    monkeypatch.setattr(canonicalize_module, "_assert_round_trips", original)


def test_the_guard_catches_an_iri_the_input_never_contained() -> None:
    """Round-trip validation rejects output containing an absent IRI."""
    graph = Graph()
    graph.add((URIRef("http://example.org/s"), URIRef("http://example.org/p"), Literal("v")))

    with pytest.raises(ValueError, match="does not round-trip"):
        canonicalize_module._assert_round_trips(
            graph,
            "<http://example.org/s> <http://example.org/p> <http://example.org/INVENTED> .\n",
            "nt",
        )


@pytest.mark.parametrize(
    ("source", "serialized"),
    [
        (
            Literal("v", datatype=URIRef("http://example.org/source-datatype")),
            '"v"^^<http://example.org/changed-datatype>',
        ),
        (
            Literal("v"),
            '"v"^^<http://example.org/invented-datatype>',
        ),
    ],
    ids=["missing-datatype", "invented-datatype"],
)
def test_the_guard_catches_missing_and_invented_literal_datatypes(source: Literal, serialized: str) -> None:
    """Datatype IRIs are checked in addition to direct URIRef terms."""
    graph = Graph()
    graph.add((EX.s, EX.p, source))

    with pytest.raises(ValueError, match="IRI"):
        canonicalize_module._assert_round_trips(
            graph,
            f"<http://example.org/s> <http://example.org/p> {serialized} .\n",
            "nt",
        )


def test_the_guard_accepts_plain_string_and_xsd_string_datatype_equivalence() -> None:
    """RDF 1.1 string equivalence applies only to literal datatype positions."""
    graph = Graph()
    graph.add((EX.s, EX.p, Literal("v")))

    canonicalize_module._assert_round_trips(
        graph,
        '<http://example.org/s> <http://example.org/p> "v"^^<http://www.w3.org/2001/XMLSchema#string> .\n',
        "nt",
    )


def test_the_guard_keeps_a_direct_xsd_string_iri_significant() -> None:
    """A direct xsd:string URIRef is not treated as a literal datatype."""
    graph = Graph()
    graph.add((XSD.string, EX.p, Literal("v")))

    with pytest.raises(ValueError, match="IRI"):
        canonicalize_module._assert_round_trips(
            graph,
            '<http://example.org/other> <http://example.org/p> '
            '"v"^^<http://www.w3.org/2001/XMLSchema#string> .\n',
            "nt",
        )


def test_the_guard_tolerates_rdflibs_literal_normalization() -> None:
    """Round-trip validation accepts RDFLib integer lexical normalization."""
    from rdflib.namespace import XSD

    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("01", datatype=XSD.integer, normalize=False)))
    graph.add((EX.s, EX.p, Literal("1", datatype=XSD.integer, normalize=False)))

    result = canonicalize_rdf_graph(graph, "turtle")

    # Pyoxigraph preserves both lexical terms while RDFLib normalizes them.
    assert len(list(ox.parse(result, format=ox.RdfFormat.TURTLE))) == 2
