"""Single-graph input contract for the public serializers."""

from __future__ import annotations

import warnings
from collections.abc import Callable

import pytest
from rdflib import ConjunctiveGraph, Dataset, Graph, Literal, URIRef
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

PREDICATE = URIRef("urn:example:predicate")
NAMED_GRAPH = URIRef("urn:example:graph")
DEFAULT_SUBJECT = URIRef("urn:example:default-subject")
NAMED_SUBJECT = URIRef("urn:example:named-subject")

CANONICAL_FORMATS = [
    "turtle",
    "ttl",
    "nt",
    "ntriples",
    "n-triples",
    "nt11",
    "nquads",
    "n-quads",
    "xml",
    "rdf/xml",
    "trig",
    "n3",
    "json-ld",
    "jsonld",
    "application/ld+json",
    "pretty-xml",  # supported by rdflib through the fallback dispatch
]


class DatasetSubclass(Dataset):
    """A Dataset subtype must retain the same container contract."""


class ConjunctiveGraphSubclass(ConjunctiveGraph):
    """A ConjunctiveGraph subtype must retain the same container contract."""


def _new_container(container_type: type[ConjunctiveGraph]) -> ConjunctiveGraph:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return container_type()


def _default_graph(container: ConjunctiveGraph) -> Graph:
    # default_context is available at the rdflib 6.3.2 dependency floor.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return container.default_context


def _populate(container: ConjunctiveGraph, contents: str) -> None:
    if contents in {"default", "mixed"}:
        _default_graph(container).add((DEFAULT_SUBJECT, PREDICATE, Literal("default")))
    if contents in {"named", "mixed"}:
        named_graph = (
            container.graph(NAMED_GRAPH)
            if isinstance(container, Dataset)
            else container.get_context(NAMED_GRAPH)
        )
        named_graph.add((NAMED_SUBJECT, PREDICATE, Literal("named")))


def _snapshot(container: ConjunctiveGraph) -> set[tuple]:
    return set(container.quads((None, None, None, None)))


@pytest.mark.parametrize("serializer", [deterministic_turtle, canonicalize_rdf_graph])
@pytest.mark.parametrize(
    "container_type",
    [Dataset, ConjunctiveGraph, DatasetSubclass, ConjunctiveGraphSubclass],
)
@pytest.mark.parametrize("contents", ["empty", "default", "named", "mixed"])
def test_dataset_containers_are_rejected_without_mutation(
    serializer: Callable[[Graph], str],
    container_type: type[ConjunctiveGraph],
    contents: str,
) -> None:
    container = _new_container(container_type)
    _populate(container, contents)
    before = _snapshot(container)

    with pytest.raises(TypeError, match=r"single rdflib\.Graph.*dataset\.graph\(graph_iri\)"):
        serializer(container)

    assert _snapshot(container) == before


@pytest.mark.parametrize("output_format", CANONICAL_FORMATS)
def test_canonicalize_rejects_datasets_before_every_format_dispatch(output_format: str) -> None:
    dataset = Dataset()
    _populate(dataset, "mixed")
    before = _snapshot(dataset)

    with pytest.raises(TypeError, match="single rdflib.Graph"):
        canonicalize_rdf_graph(dataset, output_format=output_format)

    assert _snapshot(dataset) == before


def test_canonicalize_rejects_dataset_before_inspecting_format() -> None:
    class UninspectableFormat:
        def lower(self) -> str:
            raise AssertionError("format dispatch ran before graph validation")

    with pytest.raises(TypeError, match="single rdflib.Graph"):
        canonicalize_rdf_graph(Dataset(), output_format=UninspectableFormat())  # type: ignore[arg-type]


@pytest.mark.parametrize("context", ["default", "named"])
@pytest.mark.parametrize("serializer", [deterministic_turtle, canonicalize_rdf_graph])
@pytest.mark.parametrize("container_type", [Dataset, ConjunctiveGraph])
def test_individual_dataset_graph_context_is_accepted_losslessly(
    serializer: Callable[[Graph], str],
    context: str,
    container_type: type[ConjunctiveGraph],
) -> None:
    container = _new_container(container_type)
    _populate(container, "mixed")
    before = _snapshot(container)
    if context == "default":
        graph = _default_graph(container)
    else:
        graph = (
            container.graph(NAMED_GRAPH)
            if isinstance(container, Dataset)
            else container.get_context(NAMED_GRAPH)
        )

    result = serializer(graph)
    reparsed = Graph().parse(data=result, format="turtle")

    assert isomorphic(reparsed, graph)
    assert _snapshot(container) == before


@pytest.mark.parametrize("serializer", [deterministic_turtle, canonicalize_rdf_graph])
def test_ordinary_graph_with_context_aware_store_is_accepted(
    serializer: Callable[[Graph], str],
) -> None:
    graph = Graph()
    graph.add((NAMED_SUBJECT, PREDICATE, Literal("value")))
    assert graph.store.context_aware

    result = serializer(graph)

    assert isomorphic(Graph().parse(data=result, format="turtle"), graph)
