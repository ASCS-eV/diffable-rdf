"""Validation shared by the public single-graph serializers."""

from __future__ import annotations

from rdflib import ConjunctiveGraph, Dataset, Graph


def _require_single_graph(graph: Graph) -> None:
    """Reject dataset containers whose graph names cannot survive triple serialization."""
    if isinstance(graph, (Dataset, ConjunctiveGraph)):
        raise TypeError(
            "A single rdflib.Graph is required; Dataset and ConjunctiveGraph containers "
            "are unsupported. Select an individual graph, for example with "
            "dataset.graph(graph_iri)."
        )
