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
4. **Verified round-trip** — the rendered Turtle is re-parsed and required to
   preserve the input's RDF terms before it is returned.

All triples are preserved; only syntactic form changes.

### Why step 4 exists

Turtle's compact collection syntax, `( … )`, can only express a list whose tail
is referenced once. Canonicalization readily produces graphs where several lists
share a tail — OWL ontologies do this routinely through `owl:unionOf`,
`owl:oneOf`, and the `sh:in` lists derived from them — and for those, the compact
form silently drops triples or restates a shared tail under a fresh blank node.
The output parses cleanly and looks plausible, which is what makes it dangerous
([#1](https://github.com/ASCS-eV/diffable-rdf/issues/1)).

So `deterministic_turtle` checks its own work. When the compact form does not
round-trip, it falls back to stating list structure explicitly with
`rdf:first`/`rdf:rest`, which is always faithful. If neither form round-trips it
raises rather than returning a lossy result — a canonical form that silently
rewrites the graph is worse than none.

In practice this means output is idiomatic for almost every graph, and slightly
more verbose for the ones where idiomatic would be wrong. Consumers do not need
to do anything: the guarantee is that what comes out says what went in.

## Install

```bash
pip install diffable-rdf
# or
uv add diffable-rdf
```

Requires Python 3.10+, `rdflib>=6.3.2`, and `pyoxigraph>=0.5.4`.

## Usage

```python
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from rdflib import Graph
from diffable_rdf import deterministic_turtle

path = Path("ontology.ttl")
g = Graph().parse(path)
ttl = deterministic_turtle(g)          # diff-stable, idiomatic Turtle

temporary_path = None
try:
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(ttl)
    os.replace(temporary_path, path)
except BaseException:
    if temporary_path is not None:
        temporary_path.unlink(missing_ok=True)
    raise
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
| `wl_blank_node_labels(quads, iterations=None) -> dict[str, str]` | Diff-stable label for each blank node, from canonical pyoxigraph quads. |
| `wl_relabel_quads(quads, iterations=None) -> list` | The same labels, already applied to the quads. |

`iterations=None` (the default) refines each connected blank-node component
independently until its partition stops changing — the Weisfeiler-Lehman
fixpoint. Stopping early leaves structurally distinct blank nodes sharing a
signature, and those ties are broken in RDFC-1.0's `c14nN` order, which
reintroduces exactly the instability the labels exist to remove. Pass an
explicit integer only if you need a fixed round count across the whole dataset.

Because a node's label is derived from its whole connected blank-node
structure, an edit *inside* one large connected structure can relabel all of
it. Diff stability comes from isolating unrelated regions of the graph from
each other, not from isolating parts of a single interconnected one. Each
region now stops refining at its own fixpoint, so a deeper disconnected region
cannot change the number of times an already-stable region is hashed.

This component-local convergence correction causes a one-time label change in
existing output whose disconnected blank-node components previously converged
after different numbers of rounds. Regenerate and commit those affected
artifacts once; subsequent unrelated component edits preserve their labels.

For quad datasets, a blank node's label also depends on which graph its
statements are in, so the same structure in two named graphs is labelled
distinctly and relocating a statement relabels the nodes it touches. Datasets
with only a default graph are labelled exactly as before.

### Composing with an existing pipeline

If a tool already runs RDFC-1.0 itself, it does not need `deterministic_turtle`
— and should not use it, because that would replace the tool's own prefix,
base-IRI and fallback handling. Such callers can gain diff stability by
inserting one step before serializing:

```python
from diffable_rdf import wl_relabel_quads

dataset.canonicalize(CanonicalizationAlgorithm.RDFC_1_0)
quads = wl_relabel_quads(list(dataset))   # <- the only added line
```

This is format-agnostic: it relabels blank nodes and leaves serialization
entirely to the caller.

## Guarantees, and how they are tested

Four properties are asserted over seeded pseudo-random graphs and over hand-built
arrangements of shared collections, in `tests/test_canonicalization_properties.py`:

| | Property |
|---|---|
| P1 | **Lossless** — the output parses back to a graph isomorphic to the input |
| P2 | **Idempotent** — canonicalizing the output reproduces it byte-for-byte |
| P3 | **Label-independent** — renaming blank nodes does not change the output |
| P4 | **Order-independent** — shuffling input triples does not change the output |

Plus checks that no `sh:in`-style list reference dangles, that list cell counts
survive, and that ten repeated passes produce no byte drift. Comparison follows
RDF 1.1 literal identity: `"a"^^xsd:string` and `"a"` are treated as the same
term, while distinct typed lexical forms such as `"01"^^xsd:integer` and
`"1"^^xsd:integer` remain distinct even when they denote the same value.

`tests/test_degraded_paths.py` covers the paths pyoxigraph cannot handle
(literal predicates, relative IRIs) and the formats it does not support
(notably `json-ld`). Determinism there is asserted across *separate
interpreter processes*, since the failure mode being guarded against —
rdflib's run-local blank-node identifiers, and rdflib's set-iteration
node ordering — is invisible within a single process.

### Normalizations applied

Canonicalization is not byte-preserving; two inputs that denote the same
RDF graph are deliberately mapped onto the same output:

- **Language tags are lowercased** (`"hi"@en-US` → `"hi"@en-us`). Language
  tags are case-insensitive in RDF 1.1, and rdflib's own `Literal`
  equality agrees that the two are equal. Note that
  `rdflib.compare.isomorphic` is *stricter* than that equality and reports
  such graphs as non-isomorphic, so it cannot be used to check
  losslessness across a language-tag case change.
- **`"a"^^xsd:string` and `"a"`** are the same term under RDF 1.1.
- **Other typed literal lexical forms are preserved exactly.** This includes
  numeric precision and distinct spellings with equal values, such as integer
  `"01"`/`"1"`, boolean `"1"`/`"true"`, and dateTime `Z`/`+00:00`.
- **Prefix declarations are filtered** to the namespaces the graph
  actually uses, so unused bindings do not appear in the output. Caller
  prefix names take precedence, and otherwise-generated `ns1`, `ns2`, ...
  names are allocated in stable IRI order, independent of graph insertion
  order and process hash seed. Literal datatype namespaces participate in
  the same allocation.
- **`graph.base` is not carried into the output.** rdflib relativizes
  against a base by naive string prefixing, which is not RFC-3986-correct
  for hash bases: `http://ex.org/d#a` under base `http://ex.org/d#` would
  be emitted as `<a>` and re-resolve to a different IRI. Absolute IRIs are
  always written in full.
- **On the degraded path, list structure is always explicit.** For graphs
  pyoxigraph cannot canonicalize (literal predicates, relative IRIs), Turtle
  is rendered without `( … )` collection syntax, because that syntax cannot
  express a list whose tail is referenced more than once and this path has no
  round-trip check to fall back on.

The whole suite runs on Python 3.10 through 3.13.

## Provenance

Extracted from the diff-stabilization work in
[`ASCS-eV/linkml#1`](https://github.com/ASCS-eV/linkml/pull/1) (itself a
review-ready rework of upstream [`linkml/linkml#3295`](https://github.com/linkml/linkml/pull/3295))
into a small, tool-agnostic library so LinkML, ShapeChange output, and other RDF
toolchains can share one canonicalizer.

## License

[Apache-2.0](LICENSE)
