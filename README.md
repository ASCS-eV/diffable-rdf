# diffable-rdf

Deterministic, **diff-stable** serialization for [rdflib](https://rdflib.readthedocs.io/)
graphs. Produces byte-identical Turtle across runs so version-controlled RDF
artifacts (OWL ontologies, SHACL shapes, JSON-LD contexts) show minimal,
meaningful diffs instead of blank-node churn.

## Why

RDF serializers assign blank-node identifiers (`_:c14nN`, `_:Nb1e2…`) based on
process-dependent ordering. Regenerating an ontology therefore produces large,
spurious diffs even when nothing semantically changed. `diffable-rdf` fixes this
with a standards-based pipeline:

1. **RDFC-1.0** ([W3C RDF Dataset Canonicalization](https://www.w3.org/TR/rdf-canon/))
   via [pyoxigraph](https://pypi.org/project/pyoxigraph/) — isomorphic inputs
   produce identical triple sets.
2. **Weisfeiler-Lehman structural hashing** — replaces sequential `_:c14nN`
   identifiers with content-based hashes that depend only on graph structure,
   so adding/removing a triple only touches the directly involved blank nodes.
3. **Idiomatic rdflib re-serialization** — inline blank nodes (`[ … ]`),
   collection syntax (`( … )`), and filtered prefixes (only prefixes actually
   used are declared).

All triples are preserved; only syntactic form changes.

## Install

```bash
pip install diffable-rdf
# or
uv add diffable-rdf
```

Requires Python 3.10+, `rdflib>=6`, and `pyoxigraph>=0.4`.

## Usage

```python
from rdflib import Graph
from diffable_rdf import deterministic_turtle

g = Graph().parse("ontology.ttl")
ttl = deterministic_turtle(g)          # diff-stable, idiomatic Turtle
open("ontology.ttl", "w", newline="\n").write(ttl)
```

Other entry points:

```python
from diffable_rdf import canonicalize_rdf_graph, deterministic_json, well_known_prefix_map

canonicalize_rdf_graph(graph, "turtle")   # lower-level RDFC-1.0 canonical form
deterministic_json(obj)                    # recursively key/list-sorted JSON(-LD)
well_known_prefix_map()                    # namespace IRI -> standard prefix name
```

## API

| Function | Purpose |
|---|---|
| `deterministic_turtle(graph) -> str` | Diff-stable, idiomatic Turtle (RDFC-1.0 + WL hashing + rdflib re-serialize). |
| `canonicalize_rdf_graph(graph, output_format="turtle") -> str` | RDFC-1.0 canonical serialization (with rdflib fallback for non-standard RDF). |
| `deterministic_json(obj, indent=3, preserve_list_order_keys=None) -> str` | Recursively sorted JSON; preserves JSON-LD ordered keys (`@context`, `@list`, …). |
| `well_known_prefix_map() -> dict[str, str]` | rdflib's curated namespace→prefix bindings. |

## Provenance

Extracted from the diff-stabilization work in
[`ASCS-eV/linkml#1`](https://github.com/ASCS-eV/linkml/pull/1) (itself a
review-ready rework of upstream [`linkml/linkml#3295`](https://github.com/linkml/linkml/pull/3295))
into a small, tool-agnostic library so LinkML, ShapeChange output, and other RDF
toolchains can share one canonicalizer.

## License

[Apache-2.0](LICENSE)
