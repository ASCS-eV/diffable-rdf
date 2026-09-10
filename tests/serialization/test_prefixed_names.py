"""Public prefixed-name rendering contracts."""

from __future__ import annotations

import pyoxigraph as ox
import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic

import diffable_rdf.canonicalize as canonicalize_module
from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

EX = "http://example.org/"
TURTLE_FAMILY = ("turtle", "trig", "n3")
OX_FORMAT = {
    "turtle": ox.RdfFormat.TURTLE,
    "trig": ox.RdfFormat.TRIG,
    "n3": ox.RdfFormat.N3,
    "xml": ox.RdfFormat.RDF_XML,
}


def _assert_reader_fidelity(graph: Graph, rendered: str, output_format: str) -> None:
    """Assert both supported readers preserve every term in the graph."""
    reparsed = Graph().parse(data=rendered, format=output_format)
    assert isomorphic(reparsed, graph)
    expected = set(ox.parse(graph.serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES))
    assert set(ox.parse(rendered, format=OX_FORMAT[output_format])) == expected


def _graph_with_term(namespace: str, local: str, position: str, prefix: str) -> Graph:
    """Build a graph containing the named term in one RDF term position."""
    graph = Graph(bind_namespaces="none")
    graph.bind(prefix, namespace)
    term = URIRef(namespace + local)
    subject = URIRef(EX + "subject")
    predicate = URIRef(EX + "predicate")
    object_ = URIRef(EX + "object")
    if position == "subject":
        subject = term
    elif position == "predicate":
        predicate = term
    elif position == "object":
        object_ = term
    else:
        object_ = Literal("value", datatype=term)
    graph.add((subject, predicate, object_))
    return graph


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
@pytest.mark.parametrize("position", ("subject", "predicate", "object", "datatype"))
@pytest.mark.parametrize(
    ("prefix", "namespace", "local"),
    [
        pytest.param("é", EX + "unicode/", "x.", id="unicode-prefix"),
        pytest.param("ex", EX + "comma/", "x,.", id="comma"),
        pytest.param("ex", EX + "semicolon/", "x;().", id="punctuation"),
        pytest.param("ex", EX + "apostrophe/", "x'.", id="apostrophe"),
        pytest.param("ex", EX + "percent/", "x%2C.", id="percent-encoded"),
    ],
)
def test_prefixed_names_preserve_every_term_position(
    output_format: str, position: str, prefix: str, namespace: str, local: str
) -> None:
    """Optional compact names preserve terms in every RDF position."""
    graph = _graph_with_term(namespace, local, position, prefix)
    before_triples = set(graph)
    before_base = graph.base
    before_bindings = tuple(graph.namespaces())

    rendered = canonicalize_rdf_graph(graph, output_format)

    _assert_reader_fidelity(graph, rendered, output_format)
    assert canonicalize_rdf_graph(graph, output_format) == rendered
    assert set(graph) == before_triples
    assert graph.base == before_base
    assert tuple(graph.namespaces()) == before_bindings


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
def test_punctuation_prefixed_names_preserve_every_term(output_format: str) -> None:
    """Punctuation in a compact name cannot change a graph term."""
    namespace = EX + "dot/"
    graph = _graph_with_term(namespace, "x,.", "subject", "ex")
    graph.add((URIRef(namespace + "ordinary"), URIRef(EX + "predicate"), Literal("value")))

    rendered = canonicalize_rdf_graph(graph, output_format)

    _assert_reader_fidelity(graph, rendered, output_format)


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
def test_overlapping_prefixes_and_aliases_remain_optional(output_format: str) -> None:
    """Aliases and overlapping namespaces cannot alter graph terms."""
    graph = Graph(bind_namespaces="none")
    graph.bind("short", EX)
    graph.bind("long", EX + "overlap/")
    graph.bind("alias", EX + "overlap/")
    graph.add((URIRef(EX + "overlap/x,."), URIRef(EX + "predicate"), URIRef(EX + "overlap/ordinary")))

    rendered = canonicalize_rdf_graph(graph, output_format)

    _assert_reader_fidelity(graph, rendered, output_format)
    assert canonicalize_rdf_graph(graph, output_format) == rendered


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
def test_curie_looking_literal_content_is_data(output_format: str) -> None:
    """Single-line and multiline literal text remains unchanged."""
    namespace = EX + "literal/"
    graph = _graph_with_term(namespace, "x'.", "object", "ex")
    graph.add((URIRef(EX + "single"), URIRef(EX + "predicate"), Literal(r"ex:x\,\. remains text")))
    graph.add((URIRef(EX + "multi"), URIRef(EX + "predicate"), Literal("line one\nex:x\\. line two")))

    rendered = canonicalize_rdf_graph(graph, output_format)
    reparsed = Graph().parse(data=rendered, format=output_format)

    _assert_reader_fidelity(graph, rendered, output_format)
    assert reparsed.value(URIRef(EX + "single"), URIRef(EX + "predicate")) == Literal(r"ex:x\,\. remains text")
    assert reparsed.value(URIRef(EX + "multi"), URIRef(EX + "predicate")) == Literal("line one\nex:x\\. line two")


def test_an_ordinary_binding_keeps_its_compact_rendering() -> None:
    """A first verified rendering retains ordinary caller bindings."""
    graph = _graph_with_term(EX + "ordinary/", "name", "subject", "ex")

    rendered = canonicalize_rdf_graph(graph, "turtle")

    _assert_reader_fidelity(graph, rendered, "turtle")
    assert "@prefix ex: <http://example.org/ordinary/> ." in rendered
    assert "ex:name" in rendered


def test_deterministic_turtle_preserves_curie_looking_literal_content() -> None:
    """The deterministic Turtle entry point preserves literal lexical forms."""
    graph = Graph(bind_namespaces="none")
    graph.bind("ex", EX)
    graph.add((URIRef(EX + "subject"), URIRef(EX + "predicate"), Literal(r"ex:x\,\. text")))

    rendered = deterministic_turtle(graph)

    assert isomorphic(Graph().parse(data=rendered, format="turtle"), graph)


@pytest.mark.parametrize(
    ("output_format", "ox_format"),
    [
        pytest.param("turtle", ox.RdfFormat.TURTLE, id="turtle"),
        pytest.param("xml", ox.RdfFormat.RDF_XML, id="xml"),
    ],
)
def test_verification_failures_remove_options_in_order(
    output_format: str, ox_format: ox.RdfFormat, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each failed verification removes one serialization option."""
    base = "http://example.org/query?x="
    namespace = EX + "dot/"
    graph = Graph(base=base, bind_namespaces="none")
    graph.bind("ex", namespace)
    graph.add((URIRef(namespace + "x,."), URIRef(base + "predicate"), URIRef(base + "object")))
    original_assertion = canonicalize_module._assert_round_trips
    original_serialize = canonicalize_module.ox.serialize
    validations = 0
    calls: list[dict[str, object]] = []

    def fail_before_final(*args: object, **kwargs: object) -> None:
        nonlocal validations
        validations += 1
        if validations < 3:
            raise ValueError("verification failed")
        original_assertion(*args, **kwargs)

    def record(*args: object, **kwargs: object) -> bytes:
        calls.append(kwargs)
        return original_serialize(*args, **kwargs)

    monkeypatch.setattr(canonicalize_module, "_assert_round_trips", fail_before_final)
    monkeypatch.setattr(canonicalize_module.ox, "serialize", record)
    rendered = canonicalize_rdf_graph(graph, output_format)

    _assert_reader_fidelity(graph, rendered, output_format)
    assert validations == 3
    assert calls == [
        {"format": ox_format, "prefixes": {"ex": namespace}, "base_iri": base},
        {"format": ox_format, "prefixes": {"ex": namespace}},
        {"format": ox_format},
    ]


@pytest.mark.parametrize("output_format", TURTLE_FAMILY)
def test_a_valid_compact_spelling_keeps_a_problematic_binding(
    output_format: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful first verification retains the caller binding."""
    namespace = EX + "retained/"
    graph = _graph_with_term(namespace, "x,.", "subject", "ex")
    rendered = (
        f"@prefix ex: <{namespace}> .\n"
        f"<{namespace}x,.> <{EX}predicate> <{EX}object> .\n"
    ).encode()
    calls: list[dict[str, object]] = []

    def record(*args: object, **kwargs: object) -> bytes:
        calls.append(kwargs)
        return rendered

    monkeypatch.setattr(canonicalize_module.ox, "serialize", record)
    result = canonicalize_rdf_graph(graph, output_format)

    _assert_reader_fidelity(graph, result, output_format)
    assert "@prefix ex:" in result
    assert len(calls) == 1


def test_final_prefix_attempt_propagates_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """The final option stage must verify before returning."""
    graph = Graph(base="http://example.org/query?x=", bind_namespaces="none")
    graph.bind("ex", EX)
    graph.add((URIRef(EX + "subject"), URIRef(EX + "predicate"), Literal("value")))
    validations = 0

    def fail(*args: object, **kwargs: object) -> None:
        nonlocal validations
        validations += 1
        raise ValueError("verification failed")

    monkeypatch.setattr(canonicalize_module, "_assert_round_trips", fail)
    with pytest.raises(ValueError, match="verification failed"):
        canonicalize_rdf_graph(graph, "turtle")
    assert validations == 3


def test_retry_options_do_not_affect_later_renderings(monkeypatch: pytest.MonkeyPatch) -> None:
    """A retry selects options only for its current serialization."""
    retry_graph = Graph(base="http://example.org/query?x=", bind_namespaces="none")
    retry_graph.bind("ex", EX + "ordinary/")
    retry_graph.add((URIRef(EX + "ordinary/subject"), URIRef(EX + "predicate"), Literal("value")))
    original = canonicalize_module._assert_round_trips
    validations = 0

    def fail_once(*args: object, **kwargs: object) -> None:
        nonlocal validations
        validations += 1
        if validations < 3:
            raise ValueError("verification failed")
        original(*args, **kwargs)

    monkeypatch.setattr(canonicalize_module, "_assert_round_trips", fail_once)
    canonicalize_rdf_graph(retry_graph, "turtle")
    ordinary = _graph_with_term(EX + "ordinary/", "name", "subject", "ex")
    rendered = canonicalize_rdf_graph(ordinary, "turtle")
    _assert_reader_fidelity(ordinary, rendered, "turtle")
    assert "@prefix ex: <http://example.org/ordinary/> ." in rendered
