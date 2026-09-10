# Changelog

Notable changes to `diffable-rdf`, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Read the Changed section before upgrading.** This library's job is to make
RDF files diff cleanly, so a change to the bytes it emits is the change most
likely to matter to you: it shows up as one large diff the next time you
regenerate a committed artifact. Every such change is listed with what to do
about it.

## [Unreleased]

### Changed

Output bytes change on the paths below. Each is a one-time diff: regenerate the
affected artifact, commit it once, and subsequent runs are stable again.

- **Typed literals in `deterministic_turtle` keep their exact lexical form.**
  An `xsd:integer` is now written `"42"^^xsd:integer` rather than `42`, and
  likewise for booleans and other typed values. Turtle's numeric short form
  renders the *value*, which merges terms RDF 1.1 keeps distinct — `"01"` and
  `"1"` are one value but two terms — and can shorten a double's lexical form.
  Output is more verbose and no longer loses a triple to that merge.
  `canonicalize_rdf_graph` still uses the short form; both are exact.
- **Blank-node labels change once**, for graphs whose disconnected blank-node
  components previously converged after different numbers of refinement rounds.
  Each component now converges independently, so an edit in one region no
  longer relabels an unrelated one.
- **Generated `ns1`, `ns2`, … prefix names are allocated in IRI order**, so the
  same graph gets the same names in every process. Prefixes you bind yourself
  are unaffected and still take precedence.
- **RDF/XML writes a literal carriage return as `&#xD;`.** XML parsers
  normalize a raw CR to LF before parsing, which silently changed the literal.
- **Blank-node labels now depend on which graph a statement is in**, for quad
  input. A dataset with only a default graph is labelled as before.
- **`deterministic_json` keeps ordered JSON-LD values** — `@list`, `@json`
  payloads, and terms a local context declares ordered — and sorts lists whose
  dictionaries have mixed key types, which previously left the whole enclosing
  list unsorted.
- **`deterministic_json` now sorts `@graph` and `@set` arrays.** JSON-LD leaves
  both unordered; protecting them defeated the determinism the function is for.
  An ordered construct nested inside them still keeps its order.
- **Degraded JSON-LD is written as expanded node objects with explicit `@id`
  references, never `@list`.** The previous output duplicated a shared list
  tail. Terms the interoperable subset cannot represent now raise `ValueError`.
- **N-Quads and TriG work on the degraded path**, emitting N-Triples and
  collection-free Turtle respectively — each a valid document in its own format
  for a single graph, and neither inventing a graph name the input did not have.
- **Degraded RDF/XML element order is now deterministic.** rdflib's RDF/XML
  serializer orders both its `rdf:Description` elements and the property
  elements inside them by its own graph traversal, so the same graph produced
  different bytes in different processes. Both are sorted now, as the
  line-oriented formats already sort their lines.
- **`nt` and `nquads` now raise for a graph they cannot represent** instead of
  returning text no parser will read. Both accept only absolute IRIs, and a
  graph takes the fallback precisely because it holds a term that is not one.
  The error names the term and the formats that can carry the graph: `turtle`,
  `trig`, `xml` and `json-ld` all work, since Turtle permits relative IRIs.

### Added

- **`docs/api.md`**, a full API reference with exact signatures, error cases,
  per-format behavior and runnable examples. Shipped in the sdist.
- **Output verification on every path that can be verified.** Turtle, TriG, N3
  and RDF/XML output is re-parsed and compared with the input before it is
  returned; a mismatch raises `ValueError` rather than returning a plausible
  but lossy file.
- **Explicit rejection of input a format cannot represent**, in place of silent
  loss: `Dataset` and `ConjunctiveGraph` containers raise `TypeError`, RDF/XML
  raises for characters XML 1.0 forbids, and degraded JSON-LD raises for
  generalized terms.
- **Every advertised format name is handled on the degraded path**, and two
  names for one format behave identically — producing the same bytes where the
  format can carry the graph, and refusing for the same reason where it cannot.
- Lint, type-check and coverage gates; a job that resolves the declared
  dependency floors and runs the suite against them; a check that the committed
  lockfile is not stale.
- Tests that fail when a worked-around dependency defect is fixed upstream, so
  the workaround gets retired rather than carried forever.

### Fixed

- **A literal containing a Unicode line separator no longer corrupts
  line-oriented fallback output.** N-Triples permits U+2028, U+2029, U+0085,
  U+000B, U+000C and U+001C-1E raw inside a quoted literal, and the sort used
  `str.splitlines()`, which breaks on all of them: one statement became two
  lines, they sorted independently, the separator was rewritten as a newline,
  and the document no longer parsed.
- **A delegated format no longer returns an empty document for a non-empty
  graph.** `hext` did. Every fallback format now serializes from a clean single
  graph rather than from the dataset container `to_canonical_graph` returns,
  and an empty result for a non-empty graph is refused rather than returned.
- **A serializer error on the fallback path names the format and a way
  forward** instead of surfacing rdflib's raw message. RDF/XML with a literal
  predicate reported only `Can't split 'literal-predicate'`; the original
  error is still chained.

- **`deterministic_turtle` no longer raises for a NaN or infinite number.**
  Every `xsd:double`/`xsd:float` NaN, `INF` and `-INF` literal previously
  failed with "this is a bug in diffable-rdf", because rdflib's literal
  rendering re-spells `nan` to `NaN` and `inf` to `INF` regardless of the
  option asking it not to, and the round-trip guard rightly refused a lexical
  form the graph never held. Literals are now rendered directly from the term.
  `canonicalize_rdf_graph` always handled these.
- **A NaN beside an `xsd:decimal` no longer raises `decimal.InvalidOperation`.**
  Objects are ordered by their complete RDF term spelling rather than through
  rdflib's value-space comparison, which is neither total nor defined for that
  pair. Output is unchanged for graphs that already worked.

- Two triples differing only in a literal's lexical form are no longer merged
  into one.
- A graph with a shared `rdf:List` tail no longer loses or duplicates cells on
  any output path.
- The same graph no longer serializes to different bytes in different processes
  through unstable prefix generation or unstable node ordering.
- `deterministic_turtle` no longer raises for an ordinary high-precision float.
- The documented file-rewrite recipe writes UTF-8 explicitly and no longer
  truncates the target before the new content is complete.

### Removed

- The determinism guarantee no longer extends to format names this library does
  not map itself. Those are still accepted and delegated to rdflib's serializer
  plugins, now with a warning: some order their output by a graph traversal
  that varies between processes, which no amount of blank-node canonicalization
  constrains.

### Dependencies

- Declared floors corrected to `rdflib>=6.3.2` and `pyoxigraph>=0.5.4`, which
  are the versions the code actually requires, and are now exercised in CI.

## Earlier releases

`0.2.0` and before predate this file. Their contents are recorded in the
[release notes](https://github.com/ASCS-eV/diffable-rdf/releases) and the
commit history.
