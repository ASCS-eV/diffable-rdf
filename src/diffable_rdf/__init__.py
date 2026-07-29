"""diffable-rdf: deterministic, diff-stable serialization for rdflib graphs.

Public API:
    deterministic_turtle(graph)            -> diff-stable idiomatic Turtle
    canonicalize_rdf_graph(graph, format)  -> RDFC-1.0 canonical serialization
    deterministic_json(obj)                -> deterministically ordered JSON
    well_known_prefix_map()                -> namespace IRI -> standard prefix
"""

from __future__ import annotations

from diffable_rdf.canonicalize import canonicalize_rdf_graph
from diffable_rdf.jsonld import deterministic_json
from diffable_rdf.turtle import deterministic_turtle, well_known_prefix_map

__all__ = [
    "deterministic_turtle",
    "canonicalize_rdf_graph",
    "deterministic_json",
    "well_known_prefix_map",
    "__version__",
]

__version__ = "0.0.1"
