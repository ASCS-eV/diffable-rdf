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

## [0.4.0] - 2026-09-11

**Output bytes change** for graphs that take the rdflib fallback path and carry
a base IRI. If you serialize only standard RDF, nothing here changes your
output. Regenerate the affected artifact once and subsequent runs are stable.

### Added

- `canonicalize_rdf_graph` accepts `diff_stable=True`, applying the same
  Weisfeiler-Leman blank-node labelling as `wl_relabel_quads` so that editing
  one part of a graph no longer renumbers blank nodes elsewhere. Opt-in;
  output is deterministic and isomorphic to the input either way. The rdflib
  fallback path cannot relabel — Weisfeiler-Leman consumes pyoxigraph quads
  that path never produces — so it logs a warning rather than passing
  silently.

### Fixed

- The rdflib fallback no longer drops `graph.base` unconditionally. A document
  holding relative references and declaring no base is not self-describing:
  RFC 3986 §5.1.3 hands resolution to the retrieval URI, so the same bytes read
  from two directories produced two different graphs, and §5.1.4 places that
  responsibility on the sender. The base was dropped because rdflib's
  `Serializer.relativize` shortens IRIs by string prefix rather than by the
  component algorithm RFC 3986 §5.2.2 defines and Turtle §6.3 requires, which
  corrupts terms under a base ending in `#`, in `?`, or mid-path-segment.

  The blanket drop over-corrected: it also discarded safe path-segment and
  authority-only bases, which are the ones ordinary tooling actually emits.
  RFC 3986 specifies resolution and never its inverse, so no static test can
  decide this; the rendering is now re-read and the base kept only if every
  absolute IRI of the source survives. Only loss counts — a relative source
  term is outside the RDF abstract syntax (RDF 1.1 Concepts §3.2) and always
  resolves to something on re-reading. Each drop logs a warning naming the base
  and an IRI that forced it.

  This was already the documented contract for this path in `docs/api.md`
  ("every rendering must verify before it is returned"); only the fallback
  did not honour it.

- A base that is not itself a valid absolute IRI is never declared. rdflib
  stores whatever base string it is handed, and Turtle §6.5 `IRIREF` admits no
  space, brace or quote, so such a directive yields a document a strict parser
  rejects outright.

## [0.3.0] - 2026-09-11

Two kinds of change here, and the difference matters when you upgrade.

**Calls that used to return now raise.** These are breaking, and each replaces
silent data loss with an error naming the term and a format that can carry it:

- `Dataset` and `ConjunctiveGraph` arguments raise `TypeError` at both entry
  points, instead of one arbitrary graph being serialized as if it were the
  whole input.
- `nt` and `nquads` raise `ValueError` for a graph holding a term N-Triples
  cannot write, instead of returning text no parser will read.
- `xml` raises `ValueError` for a character XML 1.0 cannot represent, and
  degraded JSON-LD raises for a generalized term the interoperable subset
  cannot express.
- `deterministic_json` raises `ValueError` for two dict keys that encode to the
  same JSON name.
- Output that fails its own round-trip check raises rather than being returned.

If your input is standard RDF and your keys are strings, none of these fire.

**Output bytes change** on the paths below. Each is a one-time diff: regenerate
the affected artifact, commit it once, and subsequent runs are stable again.

### Changed

- **Turtle-family output declares a generated prefix only where the serializer
  asks for one.** `deterministic_turtle`, and the fallback rendering of
  `turtle`, `ttl`, `n3` and `trig`, no longer invent a namespace for every IRI
  in the graph. A namespace you bound is still used in every position. A
  namespace you did not bind is now declared only for the predicates that use
  it: subjects, objects and datatypes in an unbound namespace are written as
  complete IRIs, so `"42"^^ns2:integer` becomes
  `"42"^^<http://www.w3.org/2001/XMLSchema#integer>` and unused `@prefix` lines
  disappear. This is a one-time diff on affected artifacts: regenerate, commit
  once, and later runs are stable again. To keep a namespace compact in every
  position, bind it — `well_known_prefix_map()` supplies the standard names.
  RDF/XML, JSON-LD, N-Triples and N-Quads output is byte-identical, as is
  Turtle whose namespaces are all bound.
- `wl_blank_node_labels` and `wl_relabel_quads` now reject embedded
  `pyoxigraph.Triple` terms with `ValueError`. They operate on supported
  top-level quad terms only; direction-tagged literals remain supported.
- Base rendering is accepted only after RDFLib and pyoxigraph preserve direct
  and literal-datatype IRI terms. A rendering that does not verify is emitted
  once more without its base IRI, retaining valid prefixes. If compact prefix
  rendering still does not verify, a final rendering uses complete IRIs without
  prefixes or a base. Ordinary valid bindings remain compact. Turtle, TriG,
  and N3 prefix bindings equal to the base remain available for compact terms;
  RDF/XML keeps its XML namespace selection on the no-base retry.
- Degraded JSON-LD rejects a relative subject or object identifier exactly
  matching `@[A-Za-z]+`. JSON-LD reserves these strings, so returning them in an `@id`
  value can change or discard a graph term.
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
- **Blank-node labels change once more**, where structurally indistinguishable
  nodes share a signature and are told apart by a `_1`, `_2`, … suffix. Those
  suffixes are assigned in `c14nN` order, as documented, but the order was read
  as text: `c14n10` sorted between `c14n1` and `c14n2`. Adding a tenth tied
  blank node relabelled eight of the nine already there — the opposite of what
  this labelling is for. Numbers now compare as numbers.
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
- **`json-ld` is produced by pyoxigraph and re-indented, not delegated to
  rdflib.** In 0.2.0 the name was not mapped, so it fell through to rdflib's
  JSON-LD serializer with a warning and carried no determinism guarantee. It is
  now a first-class format: pyoxigraph writes expanded JSON-LD from the
  canonicalized dataset and `deterministic_json` renders it line by line. The
  bytes are entirely different, and the output is now stable across processes.
- **Every output ends with exactly one trailing newline.** 0.2.0 passed through
  whatever the serializer produced — sometimes none, sometimes two — so a
  committed artifact could differ from the same graph written by another path,
  and POSIX text tools disagreed about the last line.
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
  line-oriented formats already sort their lines. Descriptions with an IRI
  subject come before blank-node subjects, and property elements are ordered
  by predicate -- previously by the *object's* blank-node label where it had
  one, so a label change anywhere reshuffled unrelated properties.
- **`nt` and `nquads` now raise for a graph they cannot represent** instead of
  returning text no parser will read. Both accept only absolute IRIs, and a
  graph takes the fallback precisely because it holds a term that is not one.
  The error names the term and the formats that can carry the graph: `turtle`,
  `trig`, `xml` and `json-ld` all work, since Turtle permits relative IRIs.
- **`deterministic_json` raises for two dict keys that encode to the same JSON
  name**, such as `{1: "a", "1": "b"}`, instead of writing that name twice as
  `json.dumps` does. One object cannot carry a name twice: `json.loads` keeps
  only the last entry, so the text could not be read back, and the two items
  tie under the sort, so the equal dicts `{1: "a", "1": "b"}` and
  `{"1": "b", 1: "a"}` rendered differently — the one guarantee this function
  makes. Use string keys.
- **A namespace with an embedded fragment is now used as a prefix.** IRIs under
  `http://ex/a#b` were written in full because the filter treated any `#`
  before the last character as unusable. pyoxigraph accepts such a prefix and
  its CURIEs round-trip exactly, so the output is simply more compact than it
  was. Only a namespace that is not a valid IRI is skipped now.

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
- **Python 3.14** in the tested matrix, and the suite run on Windows and macOS
  as well as Linux — the package claims `Operating System :: OS Independent`,
  which nothing was checking.
- **The built wheel is installed and tested**, rather than only built and
  metadata-checked. The suite runs against the installed package with the
  `src/` import path cleared, so a module or data file missing from the wheel
  fails here instead of at an install; `py.typed` is checked explicitly,
  because without it a type checker silently ignores every annotation shipped.
- **A scheduled job against the newest permitted dependency versions.** The
  main matrix pins `uv.lock` and the floors job pins the declared minimums, so
  neither notices a new rdflib or pyoxigraph release. This library's output is
  coupled to both, so such a release is now found deliberately, daily, without
  letting an upstream break block unrelated pull requests.
- The coverage number is a **gate** (`--cov-fail-under`), not a report.
- Tests that fail when a worked-around dependency defect is fixed upstream, so
  the workaround gets retired rather than carried forever.

### Fixed

- **Valid IRIs that have no prefixed name are serialized instead of refused.**
  A subject, object or datatype IRI whose namespace split is not itself a valid
  IRI — `<http://a.example/%25>` splits into `http://a.example/%` plus `25` —
  made `deterministic_turtle` raise, because the declaration it produced could
  not be read back. Such IRIs are now written in full. A *predicate* in that
  shape is still refused: the namespace there is the RDFLib serializer's own
  choice, and `canonicalize_rdf_graph`, which writes predicates in full,
  serializes those graphs.
- **Multiline Turtle literals preserve a terminal quote after any backslash
  run.** The emitted long-string spelling keeps the literal's exact lexical
  text and remains parseable for Turtle-family output.
- **A graph whose `base` contains a fragment no longer serializes to something
  rdflib reads back differently.** `canonicalize_rdf_graph` relativized
  `http://ex.org/d#a` to `<#a>` under base `http://ex.org/d#`, which is correct
  per RFC 3986 but which rdflib's parser resolves by concatenation, reading
  back `http://ex.org/d##a` — every term of the graph changed, silently, on
  `turtle`, `trig` and `n3`. Such a base is now skipped with a warning and
  absolute IRIs are written. An ordinary base still relativizes as before.
- **The round-trip guard now checks the IRIs rdflib reads back**, not just that
  it parses. rdflib normalizes literals but not IRIs, so an IRI in its re-parse
  that the input never contained means the output says something different to
  the library's primary consumer. The base defect passed the old guard because
  it compared pyoxigraph's reading against pyoxigraph's — two correct readings.

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

- **`deterministic_json` no longer reorders an array nested inside an ordered
  array.** Only the outer array was protected, so `{"@list": [["b", "a"], "c"]}`
  had its inner array sorted — and a nested array expands to a nested list, so
  that changed the RDF. The protection now follows array items; it still stops
  at a dict, which begins a fresh node object.
- **A `@context` term may name an alias declared after it.** Key order inside a
  `@context` object carries no meaning — Create Term Definition (JSON-LD 1.1
  API §4.2.2) keeps a `defined` map and resolves a referenced term recursively
  — but the object was folded once, front to back, so `{"payload": {"@type":
  "jsn"}, "jsn": "@json"}` left an ordered `@json` payload looking unordered
  and it got sorted, changing the RDF.
- **Non-string dict keys sort by the name the encoder writes.** Sorting used
  `str(key)`, but `json.dumps` writes a float key through `floatstr` and an int
  key through `int.__repr__`, so `float("inf")` is emitted as `Infinity` while
  it sorted as `inf`: the object came out in an order its own key names do not
  have.
- **`nt` and `nquads` refuse an IRI that has a scheme but is not a valid IRI.**
  The representability check was a regex for a leading `scheme:`, which
  `http://ex/%zz`, `http://ex/a#b#c` and `http://ex/a[1]` all pass, so the term
  was written out and pyoxigraph raised a syntax error on line 1 of the result.
  The check now asks pyoxigraph, which implements the grammar. N-Triples 1.1
  §2.2 admits only IRIs.
- **An apostrophe in an IRI no longer makes the turtle family refuse the
  graph.** Turtle's IRIREF production [18] excludes `"` but permits `'`, and an
  apostrophe is legal in an IRI path (RFC 3987 `sub-delims`) -- but the scanner
  that keeps text rewrites out of literal content treated it as a string
  delimiter. `<http://ex/a'b>` opened a span that ran to the end of the
  document, the trailing-dot CURIE repair then ran inside a literal instead of
  outside one, and `canonicalize_rdf_graph` reported "canonical turtle
  serialization does not parse back" for an ordinary graph. IRIREFs are now
  skipped as tokens, as are RDF-star quoted-triple delimiters.
- **One undeclarable namespace binding no longer erases every other prefix.**
  A binding whose namespace is not a valid IRI, such as `http://ex/%2`, could
  still be a prefix of a valid term, so it reached pyoxigraph, which refused
  it -- and the recovery re-serializes with no prefixes at all. The caller's
  unrelated prefixes silently disappeared, and the output bytes depended on a
  binding that contributed nothing.
- **Degraded RDF/XML keeps the prefix names the caller bound.** The
  determinism pass parsed rdflib's document and re-serialized it through
  `ElementTree`, which discards a document's prefix mapping on parse and
  re-derives it on write, so a caller's `beta:` came back as `ns1:`. rdflib had
  written it correctly; this library replaced it. Elements are now moved as
  spans of rdflib's own text, so every byte within one -- prefix names,
  escaping, whitespace -- is the serializer's.
- **Degraded RDF/XML output no longer depends on process-global state.**
  `ElementTree` resolves prefixes through a module-global registry, so an
  unrelated `ElementTree.register_namespace` call anywhere in the process
  changed the bytes this library produced for the same graph -- against the
  guarantee the format carries. Nothing is re-serialized now, and the sort key
  is built from the parsed element rather than from serialized text, so no
  prefix name enters the ordering either.
- **`deterministic_turtle`'s annotations resolve at runtime.** Its `graph`
  parameter was annotated with a name imported only under `TYPE_CHECKING`, so
  `typing.get_type_hints` raised `NameError: name 'RdfGraph' is not defined` --
  breaking Pydantic, FastAPI, `typer`, `beartype` and documentation generators,
  all of which evaluate annotations at runtime. rdflib is a required
  dependency, so there was nothing to defer.
- **`preserve_list_order_keys` accepts any set.** It was annotated
  `frozenset[str] | None`, so a type checker rejected the `{"custom"}` literal
  the documentation invites; callers had to add a cast to pass what the docs
  told them to.
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
