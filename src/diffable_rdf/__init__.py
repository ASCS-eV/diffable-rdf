"""diffable-rdf: deterministic, diff-stable serialization for rdflib graphs.

Isomorphic inputs serialize to identical bytes, and an edit rewrites only the
lines it touches, so RDF artifacts kept in version control show meaningful
diffs instead of blank-node churn.

Public API:
    deterministic_turtle(graph)
        Diff-stable, idiomatic Turtle. The usual entry point.
    canonicalize_rdf_graph(graph, output_format="turtle", diff_stable=False)
        Deterministic serialization using RDFC-1.0 labels in Turtle, N-Triples, N-Quads,
        RDF/XML, TriG, N3 or JSON-LD. Any other format name is delegated to
        rdflib with no determinism guarantee. Pass diff_stable=True for
        Weisfeiler-Leman blank-node labels that keep an edit local.
    deterministic_json(obj, indent=3, preserve_list_order_keys=None)
        Deterministically ordered JSON, keeping arrays whose order carries
        JSON-LD meaning.
    well_known_prefix_map()
        Namespace IRI -> standard prefix name, from rdflib's curated bindings.
    wl_blank_node_labels(quads, iterations=None)
        Diff-stable label for each blank node in canonical quads.
    wl_relabel_quads(quads, iterations=None)
        Those labels, applied to a new list of quads.

Contracts, error cases and per-format behavior are documented in docs/api.md.
The standards profile in docs/standards/README.md distinguishes dependency
labeling from standardized canonical N-Quads bytes and project-specific output.
"""

from __future__ import annotations

from diffable_rdf.canonicalize import canonicalize_rdf_graph
from diffable_rdf.jsonld import deterministic_json
from diffable_rdf.turtle import deterministic_turtle, well_known_prefix_map
from diffable_rdf.wl import wl_blank_node_labels, wl_relabel_quads

__all__ = [
    "deterministic_turtle",
    "canonicalize_rdf_graph",
    "deterministic_json",
    "well_known_prefix_map",
    "wl_blank_node_labels",
    "wl_relabel_quads",
    "__version__",
]

__version__ = "0.4.0"
