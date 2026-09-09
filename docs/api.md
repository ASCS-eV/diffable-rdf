# API guide

`diffable-rdf` exports six functions and `__version__`:

```python
from diffable_rdf import (
    canonicalize_rdf_graph,
    deterministic_json,
    deterministic_turtle,
    well_known_prefix_map,
    wl_blank_node_labels,
    wl_relabel_quads,
    __version__,
)
```

Every example below is standalone: it includes its imports and builds its own
sample data.

## Contents

- [`deterministic_turtle`](#deterministic_turtle) — diff-stable Turtle
- [`canonicalize_rdf_graph`](#canonicalize_rdf_graph) — canonical form in other formats
- [`deterministic_json`](#deterministic_json) — ordering a JSON or JSON-LD document
- [`well_known_prefix_map`](#well_known_prefix_map) — namespace IRI to standard prefix
- [`wl_blank_node_labels`](#wl_blank_node_labels) — diff-stable labels for canonical quads
- [`wl_relabel_quads`](#wl_relabel_quads) — those labels, applied
- [Writing output to a file](#writing-output-to-a-file)
- [What reproducibility depends on](#what-reproducibility-depends-on)

## deterministic_turtle

```python
def deterministic_turtle(graph: rdflib.Graph) -> str
```

Serializes one graph to Turtle that is both deterministic (isomorphic inputs
give identical bytes) and diff-stable (an edit rewrites only the lines it
touches). The returned string ends in a single newline.

Three stages: RDFC-1.0 canonicalization in pyoxigraph; replacement of the
canonical `c14nN` blank-node labels with Weisfeiler-Lehman structural hashes
(`b<12 hex digits>`), which depend only on predicate IRIs, literal values and
named-node IRIs; re-serialization through rdflib's Turtle writer, which
recovers inline blank nodes `[ … ]`, collection syntax `( … )` and prefix
declarations limited to the namespaces the graph uses.

The rendered text is re-parsed and compared with the input as RDFC-1.0
canonical forms. RDFC-1.0 ([RDF Dataset Canonicalization][rdfc], a W3C
Recommendation of 21 May 2024) produces one canonical form per isomorphism
class, so comparing those forms is an exact isomorphism test in the sense of
[RDF 1.1 Concepts §3.6][concepts]. Turtle's `( … )` syntax can only
express a list whose tail is referenced once, and canonicalization readily
produces graphs where several lists share a tail, so when the compact form does
not round-trip the graph is re-rendered with explicit `rdf:first`/`rdf:rest`
statements instead, which can express any arrangement of cells.

`graph.base` is not carried into the output and every absolute IRI is written
in full. rdflib relativizes against a base by string prefixing, which is not
RFC 3986 correct for a hash base: under base `http://ex.org/d#`, the IRI
`http://ex.org/d#a` would be written `<a>` and re-resolve to something else.

**Arguments.** `graph` — a single `rdflib.Graph`.

**Returns.** `str`, Turtle with `@prefix` declarations.

**Raises.**

- `TypeError` if `graph` is a `Dataset` or `ConjunctiveGraph`.
- `ImportError` if `pyoxigraph` is not installed.
- `ValueError` if the output does not round-trip even without collection
  syntax. That is a bug in this library, not bad input; the message asks for a
  report.

**Effect on the caller.** None. The input graph's triples and prefix bindings
are left as they were.

**Graphs pyoxigraph cannot parse.** A relative IRI or a generalized RDF term
(such as a literal predicate) makes RDFC-1.0 canonicalization impossible. The
call logs a warning and returns rdflib-based output whose blank-node labels
come from `rdflib.compare.to_canonical_graph`, so it stays reproducible across
processes — but it is not WL-relabelled, so it is not diff-stable, and it is
rendered without `( … )` because this path has no round-trip check to fall
back on. Relative IRIs are passed through verbatim rather than resolved.

```python
from rdflib import BNode, Graph, Literal, Namespace, RDF

from diffable_rdf import deterministic_turtle

EX = Namespace("http://example.org/")

graph = Graph()
graph.bind("ex", EX)
# Two lists sharing a tail: the shape that compact collection syntax cannot
# express, and that OWL unions produce routinely.
tail = BNode()
head = BNode()
graph.add((tail, RDF.first, Literal("shared")))
graph.add((tail, RDF.rest, RDF.nil))
graph.add((head, RDF.first, Literal("only in one list")))
graph.add((head, RDF.rest, tail))
graph.add((EX.first, EX.items, head))
graph.add((EX.second, EX.items, tail))

turtle = deterministic_turtle(graph)
assert deterministic_turtle(Graph().parse(data=turtle, format="turtle")) == turtle
print(turtle)
```

## canonicalize_rdf_graph

```python
def canonicalize_rdf_graph(graph: rdflib.Graph, output_format: str = "turtle") -> str
```

Serializes one graph to a canonical form in the requested format. Use this when
the target is not Turtle, or when RDFC-1.0's own labels are what you want.

This is the lower-level entry point: blank nodes keep their RDFC-1.0 `c14nN`
labels, which are deterministic but sequential, so inserting a triple can
renumber the rest. For output kept in version control, prefer
`deterministic_turtle`, or apply `wl_relabel_quads` in your own pipeline.

**Arguments.**

- `graph` — a single `rdflib.Graph`.
- `output_format` — a format name, matched case-insensitively:

  | Format | Accepted names |
  |---|---|
  | Turtle | `turtle`, `ttl` |
  | N-Triples | `nt`, `ntriples`, `n-triples`, `nt11` |
  | N-Quads | `nquads`, `n-quads` |
  | RDF/XML | `xml`, `rdf/xml` |
  | TriG | `trig` |
  | N3 | `n3` |
  | JSON-LD | `json-ld`, `jsonld`, `application/ld+json` |

  Any other name is delegated to rdflib's serializer plugins, with a logged
  warning, and **the determinism guarantee does not apply to it**. Several
  rdflib serializers order their output by a graph traversal that depends on
  set iteration order, so the same graph can serialize to different bytes in
  different processes; canonicalizing blank-node labels does not constrain
  that. Measured over six hash seeds on a graph of shared list cells,
  `pretty-xml` produced five different documents and `patch` six, while `hext`
  and `longturtle` were stable. If no plugin is registered for the name,
  rdflib raises `rdflib.plugin.PluginException`.

  Use a delegated format when you want the output and can live without the
  guarantee. If you need byte stability, use one of the mapped names above, or
  relabel quads with `wl_relabel_quads` and drive the plugin yourself.

**Returns.** `str`.

**Raises.**

- `TypeError` if `graph` is a `Dataset` or `ConjunctiveGraph`.
- `ValueError` if a verified format's output does not round-trip; if RDF/XML
  data contains a character XML 1.0 cannot represent, such as `U+0001`; or if
  a degraded JSON-LD graph contains a term outside the subset described below.
- `rdflib.plugin.PluginException` for an unregistered format name.

**Effect on the caller.** None.

**Verified formats.** Turtle, TriG, N3 and RDF/XML output is re-parsed and
compared with the input before it is returned. N-Triples, N-Quads and JSON-LD
have no compact list syntax and receive no text post-processing, so they are
not re-checked. Neither is any output from the fallback below: a graph that
pyoxigraph cannot parse has no RDFC-1.0 canonical form to compare against, so
that path relies on emitting explicit structure rather than on checking it.

**TriG and N-Quads are graph-level here.** Both entry points serialize the
triples of one graph, so quad formats place every statement in the default
graph and no graph name appears in the output. To keep graph names, relabel
quads with `wl_relabel_quads` and serialize the dataset with your own
serializer.

**`graph.base` is used on this path**, unlike in `deterministic_turtle`: a base
IRI is handed to pyoxigraph, which emits a `@base` directive and RFC
3986-correct relative references. If pyoxigraph rejects the base or a prefix
IRI, the call logs a warning and re-serializes without them.

**RDF/XML.** Literal carriage returns are written as `&#xD;` character
references, so XML newline normalization cannot turn CR or CRLF into LF.

**On the fallback path, every name above works**, and two names for one format
produce identical bytes. Two of them get there differently: TriG renders as
collection-free Turtle, which is valid TriG since Turtle is a subset of it,
because rdflib's own TriG serializer needs a context-aware store that a
canonicalized graph is not — and writing the triples into a *named* graph
instead would invent a graph name the input never had. N-Quads goes into a
Dataset's default graph for the same reason, and says exactly what N-Triples
says.

What the line-oriented formats cannot promise there is a clean reparse. A graph
only reaches the fallback because it holds something N-Triples cannot express —
a relative IRI, a literal predicate — which is precisely how it failed
pyoxigraph's parse. So `nt` and `nquads` output for such a graph keeps every
statement, in sorted order, with terms verbatim, but a strict parser will
reject the line carrying the offending term. Use `turtle`, `trig`, `xml` or
`json-ld` if the degraded output has to be read back.

**JSON-LD.** The normal path serializes pyoxigraph's expanded JSON-LD and
re-indents it so the document diffs line by line. When a graph reaches the
fallback, the expanded document is written directly from the canonical triples:
one node object per subject, `@id` references for IRI and blank-node objects,
and `@value` with `@language` or the full `@type` IRI for literals. Nothing is
compacted into `@list` and no blank node is inlined, so shared list cells and
cycles keep their identity. Within that fallback:

- Relative IRIs in subject and object position are kept verbatim, and resolve
  when a consumer parses with a document base.
- Predicate and datatype IRIs must be absolute. rdflib's JSON-LD parser drops
  relative ones, so emitting their text would not preserve their meaning.
- A literal or blank-node predicate, a literal subject, any other node kind,
  and a `URIRef` whose text begins with `_:` all raise `ValueError` before any
  output is produced. This keeps the fallback inside an interoperable
  standard-RDF subset instead of relying on optional generalized-RDF support.

```python
from rdflib import Graph, Literal, Namespace

from diffable_rdf import canonicalize_rdf_graph

EX = Namespace("http://example.org/")

graph = Graph()
graph.bind("ex", EX)
graph.add((EX.s, EX.p, Literal("value")))

for output_format in ("turtle", "nt", "xml", "json-ld"):
    print(f"--- {output_format} ---")
    print(canonicalize_rdf_graph(graph, output_format))
```

## deterministic_json

```python
def deterministic_json(
    obj: object,
    indent: int = 3,
    preserve_list_order_keys: frozenset[str] | None = None,
) -> str
```

Orders a JSON tree — nested `dict`, `list` and JSON scalars — so equal data
serializes to equal text. Object keys are sorted by the name `json.dumps` will
write, and array elements are sorted by their own serialized JSON text.

Sorting by text, not by value: `[2, 10, 1]` becomes `[1, 10, 2]`, because
`"10"` sorts before `"2"`. This is an ordering helper for diffable output, not
a JSON canonicalization scheme, and not a JSON-LD processor.

**Arguments.**

- `obj` — a JSON-serializable object.
- `indent` — spaces of indentation, passed to `json.dumps`.
- `preserve_list_order_keys` — keys whose immediate array value keeps its
  order. Defaults to `{"@context", "@list", "imports"}`. A set you pass
  **replaces** that default, so `imports` loses its protection unless you
  include it. The JSON-LD keyword protections below apply either way,
  including under an empty set.

`@graph` and `@set` are **not** protected, and their arrays sort like any
other. JSON-LD arrays carry no order unless a container says they do, and
`@set` exists to express "an unordered set of data" (JSON-LD 1.1 §1.7, §4.3.2);
`@list` is the ordered one (§4.3.1). An ordered construct nested inside a
`@graph` or `@set` array still keeps its order, because that protection comes
from the keyword rather than from the enclosing key.

**Returns.** `str`. The input object is not modified.

**Raises.** `TypeError` from `json.dumps` for a value it cannot encode, such as
a `set`.

**Arrays whose order carries meaning are kept.** `@list` values, `@json`
literal payloads, and terms declared with `@container: @list` or
`@type: @json` in a local `@context` are recognized, including keyword aliases,
ordered context arrays, inheritance by nested objects, and a `null` reset.
Remote contexts, `@import`, scoped contexts and definitions whose ordering
cannot be settled locally are never fetched and mark the value unknown; from
there every descendant array is left alone, which also covers a `@context: null`
that is itself data inside an unrecognized `@json` property.

Protection otherwise reaches the immediate array only: with `{"keep": …}`
protected, `{"keep": [{"inner": ["z", "a"]}]}` keeps the outer array's order
and still sorts `inner`.

**Prefer string keys.** `json.dumps` coerces `int`, `float`, `bool` and `None`
keys to strings, and this function sorts on that coerced name so mixed key
types do not raise. Two distinct Python keys that coerce to the same name —
`1` and `"1"` — produce an object with that name twice, exactly as
`json.dumps` does on its own. Tuples are another encoder extension: they are
written as arrays but are not recursed into, so their contents keep the order
you built them in.

```python
import json

from diffable_rdf import deterministic_json

document = {
    "@context": {"tags": {"@id": "http://example.org/tags", "@container": "@list"}},
    "@id": "http://example.org/thing",
    "tags": ["ordered", "by", "the", "author"],
    "aliases": ["zeta", "alpha"],
    "counts": [2, 10, 1],
}

print(deterministic_json(document))
assert json.loads(deterministic_json(document))["tags"] == ["ordered", "by", "the", "author"]
assert json.loads(deterministic_json(document))["aliases"] == ["alpha", "zeta"]
assert json.loads(deterministic_json(document))["counts"] == [1, 10, 2]
```

## well_known_prefix_map

```python
def well_known_prefix_map() -> dict[str, str]
```

Returns rdflib's curated default bindings as namespace IRI to prefix name — the
inverse direction of `Graph.namespaces()`. Use it to normalize a non-standard
alias to the conventional name, for example `sdo` to `schema` for
`https://schema.org/`. The exact set is rdflib's, and grows with rdflib
releases.

```python
from diffable_rdf import well_known_prefix_map

prefixes = well_known_prefix_map()
print(prefixes["https://schema.org/"])          # schema
print(prefixes["http://www.w3.org/ns/shacl#"])  # sh
```

## wl_blank_node_labels

```python
def wl_blank_node_labels(quads: list, iterations: int | None = None) -> dict[str, str]
```

Computes a diff-stable label for every blank node in a list of **already
RDFC-1.0-canonicalized** pyoxigraph quads. The signature of a node is built by
Weisfeiler-Lehman refinement from predicate IRIs, literal values, named-node
IRIs and graph names — never from a blank node's own identifier — so it changes
only when that node's own surroundings do.

Canonicalizing first is what makes the result reproducible: ties between
structurally indistinguishable nodes are broken in `c14nN` order, so labels
depend on canonical numbering wherever the structure alone cannot separate two
nodes.

**Arguments.**

- `quads` — a list of `pyoxigraph.Quad`, canonicalized with
  `Dataset.canonicalize(CanonicalizationAlgorithm.RDFC_1_0)`.
- `iterations` — refinement rounds. `None`, the default, refines each connected
  blank-node component until its own partition stops changing. An explicit
  integer runs exactly that many synchronous rounds across every blank node;
  `0` or a negative number therefore runs none, leaving each label derived from
  its named-node edges alone. Pass `None` unless a fixed round count is a
  requirement of your own.

**Returns.** `dict[str, str]`, from canonical blank-node identifier (`c14n0`,
`c14n1`, …) to a label `b` plus 12 hex digits. Structurally indistinguishable
nodes and genuine hash collisions get a `_1`, `_2`, … suffix, so the mapping is
always injective.

**Notes.** A quad's graph name is part of each signature, so identical
structure in two named graphs is labelled differently and moving a statement
between graphs relabels the nodes it touches; the default graph contributes no
graph term. A blank node used as a graph name is labelled from the quads it
names. Because a label covers a whole connected blank-node region, an edit
inside one large interconnected structure can relabel all of it — the stability
on offer is between unrelated regions of a graph, not within one.

## wl_relabel_quads

```python
def wl_relabel_quads(quads: list, iterations: int | None = None) -> list
```

Applies `wl_blank_node_labels` and returns a **new** list of
`pyoxigraph.Quad`, in the input order, with every blank node — including blank
nodes used as graph names — relabelled. The input list and its quads are
untouched. The result is isomorphic to the input.

This is the one-line way to add diff stability to a pipeline that already runs
RDFC-1.0 and owns its own serialization, prefix handling and base IRI. Such a
pipeline should not call `deterministic_turtle`, which would replace all of
that.

A complete reproducible dataset needs the sort too: relabelling makes the
identifiers stable, and sorting makes their order stable.

```python
import pyoxigraph as ox

from diffable_rdf import wl_relabel_quads

dataset = ox.Dataset(
    ox.parse(
        '<http://example.org/s> <http://example.org/items> _:cell .\n'
        '_:cell <http://example.org/value> "first" .\n',
        format=ox.RdfFormat.N_TRIPLES,
    )
)
dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)

quads = wl_relabel_quads(list(dataset))              # the only added step
quads.sort(key=lambda q: (str(q.graph_name), str(q.subject), str(q.predicate), str(q.object)))
print(ox.serialize(quads, format=ox.RdfFormat.N_QUADS).decode("utf-8"))
```

## Writing output to a file

Serialization returns a string, so writing it is yours to do. Two details are
easy to get wrong: `open()` uses the platform's locale encoding, which mangles
non-ASCII IRIs and labels on an ASCII default, and writing in place truncates
the existing file before the new content is known to be complete. Encode UTF-8
explicitly, write a sibling temporary file, and rename it over the target —
`os.replace` is atomic on the same filesystem.

```python
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from rdflib import Graph, Literal, Namespace

from diffable_rdf import deterministic_turtle

EX = Namespace("http://example.org/")

graph = Graph()
graph.bind("ex", EX)
graph.add((EX.Ampere, EX.label, Literal("André-Marie Ampère", lang="fr")))

path = Path("ontology.ttl")
text = deterministic_turtle(graph)

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
        temporary.write(text)
    os.replace(temporary_path, path)
except BaseException:
    if temporary_path is not None:
        temporary_path.unlink(missing_ok=True)
    raise
```

If the write fails part way through, the target keeps its previous bytes and
the temporary sibling is removed.

## What reproducibility depends on

Identical bytes across two runs assume the same inputs to the whole pipeline:

- **The same prefix bindings.** Caller prefix names are kept and take
  precedence; the remaining `ns1`, `ns2`, … names are allocated in IRI order,
  independent of insertion order and hash seed. Bind a namespace differently
  and the output changes accordingly.
- **The same `graph.base`.** `deterministic_turtle` ignores it;
  `canonicalize_rdf_graph` emits it.
- **The same `rdflib` and `pyoxigraph` versions.** RDFC-1.0 fixes which terms
  are equal, not how a serializer lays out a document.
- **Literal terms as they reach this library.** The promise covers the terms in
  the `Graph` you pass. If you parsed that graph from a file, rdflib may
  already have normalized values on the way in; lexical text lost there cannot
  be recovered here.
- **Every output ends with exactly one newline.** Serializers disagree about
  this — pyoxigraph's RDF/XML writer ends without one, rdflib's Turtle writer
  ends with two — and a missing final newline is itself a diff, so it is
  normalized. An empty graph is the exception: Turtle and N-Triples write
  nothing for it, and an empty document stays empty.
- **The graph, not the file.** `"a"^^xsd:string` is written `"a"`: under
  RDF 1.1 a literal with no datatype IRI and no language tag has datatype
  `xsd:string` (Turtle §2.5.1), so those are one term. Language tags are
  lowercased — a conversion [RDF 1.1 Concepts §3.3][concepts] explicitly
  permits ("Lexical representations of language tags MAY be converted to lower
  case. The value space of language tags is always in lower case"), though note
  that it is a change of lexical representation rather than an identity: §3.3
  compares language tags character by character. Every other typed lexical form
  is preserved exactly, including `"01"^^xsd:integer` versus
  `"1"^^xsd:integer`, `"1"^^xsd:boolean` versus `"true"^^xsd:boolean`, and `Z`
  versus `+00:00` in a `xsd:dateTime`. That is required rather than merely
  polite: §3.3 defines two literals as the same term only if their lexical
  forms, datatype IRIs and language tags "compare equal, character by
  character", and the specification's own example is that `"1"^^xsd:integer`
  and `"01"^^xsd:integer` denote the same value and are *not* the same term.

One consequence worth spelling out: because a language tag's case is
normalized, `rdflib.compare.isomorphic` — which is stricter than rdflib's own
`Literal` equality — reports the input and the re-parsed output as
non-isomorphic across a tag-case change. It cannot be used to check
losslessness in that case.

[rdfc]: https://www.w3.org/TR/rdf-canon/
[concepts]: https://www.w3.org/TR/rdf11-concepts/#section-Graph-Literal
