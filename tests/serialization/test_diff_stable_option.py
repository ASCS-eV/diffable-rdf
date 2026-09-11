"""Contracts for the ``diff_stable`` option of :func:`canonicalize_rdf_graph`.

RDFC-1.0 labels blank nodes as a function of the whole graph, so a one-triple
edit can renumber every blank node in a document. Weisfeiler-Leman labels
depend only on a node's local neighbourhood, which keeps unrelated regions of
a file untouched. Both are deterministic; they differ only in how far an edit
propagates through the output.
"""

from __future__ import annotations

import difflib
import logging

import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph

EX = Namespace("http://example.org/")
LOGGER_NAME = "diffable_rdf.canonicalize"
FORMATS = ["turtle", "ttl", "trig", "n3", "xml", "nt", "json-ld"]
PARSER = {"ttl": "turtle", "n3": "turtle"}


def _nested_graph(count: int) -> Graph:
    """Build a graph of ``count`` independent blank-node branches.

    :param count: How many subject/blank-node pairs to create.
    :return: The constructed graph.
    """
    graph = Graph()
    for index in range(count):
        node = BNode()
        graph.add((EX[f"s{index}"], EX.has, node))
        graph.add((node, EX.value, Literal(index)))
    return graph


@pytest.mark.parametrize("output_format", FORMATS)
def test_diff_stable_output_is_reproducible(output_format: str) -> None:
    """Requesting diff stability does not cost determinism."""
    graph = _nested_graph(6)

    first = canonicalize_rdf_graph(graph, output_format=output_format, diff_stable=True)
    second = canonicalize_rdf_graph(graph, output_format=output_format, diff_stable=True)

    assert first == second


@pytest.mark.parametrize("output_format", FORMATS)
def test_diff_stable_output_says_the_same_thing(output_format: str) -> None:
    """Relabelling is a renaming, so the graph is unchanged.

    RDF 1.1 Concepts section 3.4 gives blank-node identifiers no meaning
    beyond a document, so any consistent renaming yields the same graph.
    """
    graph = _nested_graph(6)

    plain = canonicalize_rdf_graph(graph, output_format=output_format)
    stable = canonicalize_rdf_graph(graph, output_format=output_format, diff_stable=True)

    parser = PARSER.get(output_format, output_format)
    assert isomorphic(Graph().parse(data=plain, format=parser), graph)
    assert isomorphic(Graph().parse(data=stable, format=parser), graph)


def test_diff_stable_defaults_to_off() -> None:
    """The option is opt-in, so the default output is unchanged."""
    graph = _nested_graph(6)

    assert canonicalize_rdf_graph(graph) == canonicalize_rdf_graph(graph, diff_stable=False)


def _changed_lines(before: str, after: str) -> int:
    """Count added and removed lines between two documents.

    :param before: The earlier document.
    :param after: The later document.
    :return: How many lines the diff touches.
    """
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(), n=0)
    return sum(1 for line in diff if line[:1] in {"+", "-"} and not line.startswith(("+++", "---")))


def test_diff_stable_confines_an_edit_to_the_part_that_changed() -> None:
    """Adding one branch leaves the other branches' labels alone.

    This is the whole point of the option, so it is asserted as a strict
    improvement over the default rather than as a fixed number.
    """
    graph = _nested_graph(6)
    extended = Graph()
    for triple in graph:
        extended.add(triple)
    added = BNode()
    extended.add((EX.s99, EX.has, added))
    extended.add((added, EX.value, Literal(99)))

    plain_churn = _changed_lines(
        canonicalize_rdf_graph(graph),
        canonicalize_rdf_graph(extended),
    )
    stable_churn = _changed_lines(
        canonicalize_rdf_graph(graph, diff_stable=True),
        canonicalize_rdf_graph(extended, diff_stable=True),
    )

    assert stable_churn < plain_churn


def test_diff_stable_on_the_fallback_path_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    """The fallback names diff stability as unavailable, and still serializes.

    Weisfeiler-Leman relabelling consumes pyoxigraph quads; this path exists
    because pyoxigraph refused the graph, so there are none. Passing silently
    would tell a caller a guarantee applies to bytes that never received it.
    """
    graph = Graph()
    node = BNode()
    graph.add((URIRef("relative-term"), EX.p, Literal("v")))
    graph.add((EX.s, EX.has, node))
    graph.add((node, EX.value, Literal(1)))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        result = canonicalize_rdf_graph(graph, output_format="turtle", diff_stable=True)

    messages = [record.getMessage() for record in caplog.records]
    assert [message for message in messages if "diff_stable was requested" in message]

    # The graph still serializes: the option is unavailable, not fatal. It
    # holds a relative IRI, so it cannot be isomorphic to its own re-reading
    # (RFC 3986 section 5.1.3 resolves that term at the reader); the blank
    # node structure is what diff stability would have touched.
    reparsed = Graph().parse(data=result, format="turtle")
    assert len(reparsed) == len(graph)
    assert sum(1 for triple in reparsed for term in triple if isinstance(term, BNode)) == 2


def test_the_fallback_is_silent_when_diff_stability_was_not_asked_for(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The unavailability warning is tied to the request, not to the path."""
    graph = Graph()
    graph.add((URIRef("relative-term"), EX.p, Literal("v")))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        canonicalize_rdf_graph(graph, output_format="turtle")

    assert not [
        record.getMessage() for record in caplog.records if "diff_stable was requested" in record.getMessage()
    ]
