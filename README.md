# diffable-rdf

Deterministic, **diff-stable** serialization for [rdflib](https://rdflib.readthedocs.io/)
graphs. Isomorphic inputs produce byte-identical output, and an edit rewrites
only the lines it touches — so version-controlled RDF artifacts (OWL
ontologies, SHACL shapes, JSON-LD contexts) show meaningful diffs instead of
blank-node churn.

RDF serializers number blank nodes (`_:c14nN`, `_:Nb1e2…`) in a
process-dependent order, so regenerating a file can rewrite most of it even
when nothing semantically changed. `diffable-rdf` canonicalizes the graph with
[RDFC-1.0](https://www.w3.org/TR/2024/REC-rdf-canon-20240521/), replaces the canonical sequential
labels with Weisfeiler-Lehman structural hashes that depend only on each blank
node's neighbourhood, and re-serializes through rdflib for idiomatic output.
Every triple is preserved; only syntactic form changes.

## Install

```bash
pip install diffable-rdf
```

Requires Python 3.10+. Installs `rdflib>=6.3.2` and `pyoxigraph>=0.5.4`.

## Quickstart

<!-- example -->

```python
from rdflib import Graph, Literal, Namespace

from diffable_rdf import deterministic_turtle

EX = Namespace("http://example.org/")

graph = Graph()
graph.bind("ex", EX)
graph.add((EX.Widget, EX.label, Literal("Widget", lang="en")))
graph.add((EX.Widget, EX.partOf, EX.Assembly))

print(deterministic_turtle(graph))
```

```turtle
@prefix ex: <http://example.org/> .

ex:Widget ex:label "Widget"@en ;
    ex:partOf ex:Assembly .
```

Serializing the same graph again — in another process, with the triples added
in another order, or with the blank nodes renamed — produces the same bytes.

## Which function do I want?

| Function | Use it for |
|---|---|
| `deterministic_turtle(graph)` | Diff-stable, idiomatic Turtle. The default choice for files kept in version control. |
| `canonicalize_rdf_graph(graph, output_format="turtle")` | Deterministic serialization using RDFC-1.0 blank-node labels: N-Triples, N-Quads, RDF/XML, TriG, N3, JSON-LD. Its Turtle is laid out differently from `deterministic_turtle`'s — same terms, different presentation. Pass `diff_stable=True` for blank-node labels that keep an edit local. |
| `deterministic_json(obj)` | Ordering an existing JSON or JSON-LD document, without touching RDF. |
| `well_known_prefix_map()` | Normalizing prefix aliases (`sdo` → `schema`) to rdflib's curated names. |
| `wl_blank_node_labels(quads)` | Diff-stable labels for blank nodes in quads you have already canonicalized. |
| `wl_relabel_quads(quads)` | The same labels, applied — one line to add diff stability to a pipeline that runs RDFC-1.0 itself. |

Full signatures, error cases and per-format behavior are in the
[API guide](https://github.com/ASCS-eV/diffable-rdf/blob/main/docs/api.md).
Changes that affect the bytes this library emits are listed in the
[changelog](https://github.com/ASCS-eV/diffable-rdf/blob/main/CHANGELOG.md).

The [standards profile and pinned originals](https://github.com/ASCS-eV/diffable-rdf/blob/main/docs/standards/README.md) distinguish
RDF term fidelity from project-specific presentation. These graph serializers
use the dependency's RDFC-1.0 labeling algorithm; their output is not advertised
as standardized canonical N-Quads bytes or a standalone RDFC processor interface.
WL labels and JSON ordering are project features, not additional RDF standards.

## Limits worth knowing before you start

- **One graph at a time.** The graph serializers take an `rdflib.Graph` and
  raise `TypeError` for `Dataset` and `ConjunctiveGraph`, because triple
  serialization cannot carry graph names. Select a context explicitly
  (`deterministic_turtle(dataset.graph(graph_iri))`), or relabel quads with
  `wl_relabel_quads` and serialize the dataset yourself.
- **Canonical, not byte-preserving.** `"a"^^xsd:string` is written `"a"` (the
  same RDF 1.1 term) and language tags are lowercased (permitted: their value
  space is lower case). Every other typed lexical form is kept exactly,
  including `"01"^^xsd:integer`.
- **Diff stability is per connected blank-node region.** An edit inside one
  large interconnected structure can relabel all of it; unrelated regions of
  the graph keep their labels.
- **Byte reproducibility assumes the same setup.** The same prefix bindings,
  the same `graph.base`, and the same `rdflib`/`pyoxigraph` versions.
- **The guarantee covers the formats above.** `canonicalize_rdf_graph` also
  accepts any name rdflib has a plugin for, as an escape hatch, but warns that
  delegated output is only as deterministic as that plugin — and some order
  their output by a graph traversal that varies between processes.
- **Output is verified before it is returned.** Turtle, TriG, N3 and RDF/XML
  are re-parsed and compared against the input, and a mismatch raises
  `ValueError` rather than returning a lossy file. Graphs with relative IRIs
  or generalized RDF terms cannot be compared this way and take a more
  explicit fallback instead — see the API guide.

## License

[Apache-2.0](LICENSE)
