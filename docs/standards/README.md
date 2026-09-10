# Standards profile and original references

This collection pins the specifications that define the RDF terms and document
syntaxes used by the library. The files in `references/` are complete,
unmodified original HTML or RFC text bodies, including publication status,
authorship and copyright notices. This README is a project-authored scope
summary, not a replacement for those originals.

The reference directory disables Git text conversion so publisher line endings
remain byte-exact on every checkout platform, including Windows.

The snapshots provide offline text and HTML fragment lookup. Linked style
sheets, scripts, images, examples and other resources are not mirrored; a local
HTML view need not render exactly like the publisher's site. Open the source
link for the publisher's presentation. A dated edition can contain publisher
errata or editorial updates; the digest identifies the exact bytes retained.

## Implementation profile

| Feature | Standard-derived behavior | Scope and project-specific behavior |
| --- | --- | --- |
| Graph serializers | RDF 1.1 Concepts §3.1 triple positions, §3.3 literal terms and §3.6 graph comparison | One `rdflib.Graph`; dataset inputs are rejected. Prefix bindings and graph base are presentation inputs, not RDF graph identity. |
| Turtle, N-Triples, TriG, N-Quads, RDF/XML | Each named RDF 1.1 syntax's grammar and term interpretation | TriG and N-Quads carry only the default graph. Prefix/base presentation can be omitted when it does not preserve terms. Not every generalized graph can be expressed in every syntax. |
| N3 | The Turtle-compatible RDF graph subset | No formulas, implications, variables or arbitrary Notation3 logic. |
| Canonical blank-node labels | The dependency's RDFC-1.0 algorithm | The wrapper has one-graph inputs and no hash-algorithm parameter. It does not claim the standalone processor conformance defined by RDFC §2. |
| Rendered bytes | RDF term fidelity plus each selected syntax | `canonicalize_rdf_graph` uses RDFC labels but does not advertise standardized canonical N-Quads bytes. Sorting, framing and optional compact syntax are project policies. Internal sorted term comparison keys are not standardized canonical byte output. |
| WL labels and diff stability | Canonicalized terms supply deterministic input | WL hashes, collision suffixes and locality are project features, not RDFC canonical labels or a cryptographic commitment scheme. Low-level quad helpers retain named graphs. Directional literals accepted by the dependency are a supported extension, not blanket RDF 1.2 conformance. Embedded triple terms are rejected. |
| JSON-LD graph output | JSON-LD 1.1 expanded RDF representation | A graph serializer, not a general JSON-LD processor. The degraded path supports its documented interoperable subset and rejects unsupported terms. |
| JSON ordering | RFC 8259 data model; JSON-LD §9.7 ordered lists and unordered sets; selected local context-ordering rules | `deterministic_json` is neither JCS nor a JSON-LD processor. It does not fetch remote contexts or implement the complete JSON-LD API algorithms. Python key coercion and non-finite float handling follow the documented Python encoder behavior; strict JSON requires JSON-compatible finite values. |
| IRIs and XML terms | RFC 3986 relative resolution, RFC 3987 IRIs, XML 1.0 characters and XML Namespaces qualified names | Relative/generalized terms use the documented degraded serialization paths where available; this is not an extension of RDF 1.1's absolute-IRI graph model. XML-inexpressible characters are rejected. |

The exact supported inputs, fallback boundaries, exceptions and reproducibility
conditions are in the [API contract](../api.md). This profile does not enlarge
those guarantees.

[RDFC §2](references/rdf-canon.html#conformance) defines processor conformance.
[§3.1](references/rdf-canon.html#canon-terms) and
[Appendix A](references/rdf-canon.html#canonical-quads) define canonical N-Quads.
Testing labels or graph isomorphism does not alone test that byte format.
The specification itself also explains that passing its test suite establishes
only the aspects tested, not complete conformance.

[RDF 1.1 Concepts §3.6](references/rdf11-concepts.html#section-graph-equality)
is the graph-comparison clause; the separate
[§3.3](references/rdf11-concepts.html#section-Graph-Literal) defines literal terms.
For JSON-LD ordering, the normative clause is
[§9.7 Lists and Sets](references/json-ld11.html#lists-and-sets), while
[§4.3 Value Ordering](references/json-ld11.html#sets-and-lists) is informative.
Ordered contexts and recursive term definitions are described by the normative
JSON-LD API [§4.1](references/json-ld11-api.html#context-processing-algorithm)
and [§4.2](references/json-ld11-api.html#create-term-definition) algorithms;
the ordering helper implements only the local facts documented in its API.

## Reference inventory

All entries were retrieved on 2026-09-10. Publication dates and status below
refer to the pinned edition, not a claim that no newer edition exists. RFCs
whose originals specify only a month retain month-level publication precision.
The [manifest](manifest.json) records exact requested and resolved URLs, media
types, SHA-256 digests, license references and selected clause anchors.

| ID | Original copy | Edition | Publisher source |
| --- | --- | --- | --- |
| `RDF11-CONCEPTS` | [RDF 1.1 Concepts and Abstract Syntax](references/rdf11-concepts.html) | W3C Recommendation, 25 February 2014 | [Original](https://www.w3.org/TR/2014/REC-rdf11-concepts-20140225/) |
| `RDFC10` | [RDF Dataset Canonicalization](references/rdf-canon.html) | W3C Recommendation, 21 May 2024 | [Original](https://www.w3.org/TR/2024/REC-rdf-canon-20240521/) |
| `TURTLE11` | [RDF 1.1 Turtle](references/turtle.html) | W3C Recommendation, 25 February 2014 | [Original](https://www.w3.org/TR/2014/REC-turtle-20140225/) |
| `TRIG11` | [RDF 1.1 TriG](references/trig.html) | W3C Recommendation, 25 February 2014 | [Original](https://www.w3.org/TR/2014/REC-trig-20140225/) |
| `NTRIPLES11` | [RDF 1.1 N-Triples](references/n-triples.html) | W3C Recommendation, 25 February 2014 | [Original](https://www.w3.org/TR/2014/REC-n-triples-20140225/) |
| `NQUADS11` | [RDF 1.1 N-Quads](references/n-quads.html) | W3C Recommendation, 25 February 2014 | [Original](https://www.w3.org/TR/2014/REC-n-quads-20140225/) |
| `RDFXML11` | [RDF 1.1 XML Syntax](references/rdf-syntax-grammar.html) | W3C Recommendation, 25 February 2014 | [Original](https://www.w3.org/TR/2014/REC-rdf-syntax-grammar-20140225/) |
| `JSONLD11` | [JSON-LD 1.1](references/json-ld11.html) | W3C Recommendation, 16 July 2020 | [Original](https://www.w3.org/TR/2020/REC-json-ld11-20200716/) |
| `JSONLD11-API` | [JSON-LD 1.1 Processing Algorithms and API](references/json-ld11-api.html) | W3C Recommendation, 16 July 2020 | [Original](https://www.w3.org/TR/2020/REC-json-ld11-api-20200716/) |
| `XML10` | [Extensible Markup Language (XML) 1.0 (Fifth Edition)](references/xml.html) | W3C Recommendation, 26 November 2008 | [Original](https://www.w3.org/TR/2008/REC-xml-20081126/) |
| `XMLNS10` | [Namespaces in XML 1.0 (Third Edition)](references/xml-names.html) | W3C Recommendation, 8 December 2009 | [Original](https://www.w3.org/TR/2009/REC-xml-names-20091208/) |
| `RFC3986` | [Uniform Resource Identifier (URI): Generic Syntax](references/rfc3986.txt) | Standards Track, January 2005 | [Original](https://www.rfc-editor.org/rfc/rfc3986.txt) |
| `RFC3987` | [Internationalized Resource Identifiers (IRIs)](references/rfc3987.txt) | Standards Track, January 2005 | [Original](https://www.rfc-editor.org/rfc/rfc3987.txt) |
| `RFC8259` | [The JavaScript Object Notation (JSON) Data Interchange Format](references/rfc8259.txt) | Standards Track, December 2017 | [Original](https://www.rfc-editor.org/rfc/rfc8259.txt) |

## Notices and redistribution

Original publisher notices remain in every specification. The project's Apache-2.0
license does not replace third-party document terms. These copies preserve
source links, publication status, authorship, copyright and disclaimers; the
project does not modify the standards bodies.

The [2002 W3C document-use license](references/w3c-document-license-2002.html)
records the document-use terms active for the 2008, 2009 and 2014 editions.
Their original unversioned document-use link resolves on retrieval to the
[2023 document license](references/w3c-document-license.html); both are retained
and their roles distinguished in the manifest. The JSON-LD Recommendations
explicitly link the
[2015 Software and Document license](references/w3c-software-document-2015.html).
RDFC explicitly links the
[2023 Software and Document license](references/w3c-software-document-2023.html).
These document licenses are not interchangeable with test-suite licenses.

RFC 3986 and RFC 3987 retain their complete embedded copyright and BCP 78
notices. [RFC 3667](references/rfc3667.txt) is the February 2004 BCP 78 text
applicable to their January 2005 publication. RFC 8259 retains its complete
IETF Trust notice and its original license-info link, whose resolved
[index](references/ietf-license-info.html) is pinned for provenance.
[Trust Legal Provisions 5.0](references/ietf-tlp-5.html), effective 25 March
2015, is retained as the publisher's text including its stated clerical
correction to the BSD license name. Its §3.c permits redistribution of
unmodified IETF documents outside the IETF Standards Process.

## Verification and maintenance

Run `python scripts/check_standards.py` from the project root. The command is
dependency-free and offline: it validates the schema, complete expected
reference inventory, unique identities and paths, contained paths, original
text identities, digests, license relationships and selected HTML anchors.
It never downloads documents or rewrites hashes. The generic tests in
`tests/standards/` cover valid catalogs and malformed or corrupted evidence.
Catalog validation is not a claim that every copied clause is implemented.

To update a reference:

1. Select the exact dated Recommendation or numbered RFC and inspect its
   publication status and redistribution notice. Do not replace a pinned
   edition with an unreviewed moving latest URL.
2. Download the original complete body without reformatting, rewriting links
   or changing line endings. Reject error pages, challenge pages and incomplete
   responses. Record requested and resolved URLs and the actual retrieval date.
3. Verify the original title, publication identity and copyright/status notice;
   retain any newly applicable license text and distinguish redirected current
   notices from publication-era terms.
4. Update the manifest digest, provenance and clause anchors together. Cite the
   pinned edition, label informative explanations, and review the implementation
   profile and affected requirement/test mappings for changes in scope.
5. Run the offline checker and standards tests, then the full source and
   installed-wheel suites. Confirm the source distribution includes the
   collection and licenses. Runtime wheels intentionally exclude these assets.

The catalog schema version changes when its structure changes. The checker
keeps an explicit expected specification inventory; adding or removing a
standard requires a reviewed change to that inventory as well as the catalog.

## Requirement-to-test evidence

[coverage.md](coverage.md) is the readable feature and requirement map;
[requirements.json](requirements.json) is its declarative source. A row names
a concrete, scoped behavior, its implementation owner and actual collected
tests. It does not establish every possible input or every clause of a copied
standard. The map is not a percentage of specification conformance and is not
a complete cross-product of formats, terms and execution environments.

The categories distinguish:

- `normative`: a concrete behavior supported by at least one verified normative
  clause. For example, RDF literal identity depends on lexical forms, not merely
  equal interpreted values. A reference to an informative explanation alone
  cannot qualify a row as normative.
- `policy`: an API boundary, rendering choice or ordering algorithm owned by
  this project. Referenced standard clauses constrain or explain the behavior;
  they do not make the chosen algorithm a standard algorithm.
- `extension`: an explicitly bounded behavior outside the copied standards'
  core data model, such as Python mixed-key input or dependency-supported
  directional literals. This does not enlarge the conformance profile.

The source and installed suites validate the map during ordinary pytest runs.
Only the standards integration fixture requests a full collect-only subprocess,
lazily and once per test session. Collection imports test modules but never
executes test bodies or recursively validates the catalog. A focused command
outside `tests/standards/` runs only its selected tests.

```bash
python scripts/check_standards.py
python scripts/check_requirements.py
python -m pytest -q --package-under-test=source tests/standards
```

The requirement command requires the project's pytest development dependency
and installed RDF dependencies, but no extra plugin and no network access. Its
child uses the same Python executable, isolated mode, a temporary working
directory, absolute test/config paths and an explicit package target. Inherited
pytest options and plugin requests are removed. The package inventory is read
only after the test harness selects and verifies the package origin.

For a non-editable wheel environment, use its Python with the checkout's
script and assets:

```bash
/path/to/wheel-env/bin/python -I /path/to/diffable-rdf/scripts/check_requirements.py \
  --package-under-test=installed
```

The report counts collected test matches, not executed or passing tests. The
full test run remains the execution gate. The two source-only package-harness
tests remain collected but skip under installed mode, and the address-space
measurement skips on platforms without resource limits. These outcomes are
reported by pytest; a collected selector is not interpreted as a passing result.

### Requirement catalog schema

Schema version 1 has exactly three top-level fields: `schema_version`,
`features` and `requirements`. Unknown fields, enum values and duplicate JSON
keys fail validation. Collections use the following fields:

| Object | Fields and invariants |
| --- | --- |
| Callable feature | Unique `id`, `kind: callable`, `description`, and `export`. Exports must equal the selected package's actual public callable exports. |
| Format feature | Unique `id`, `kind: format`, `description`, `aliases`, and `backend`. The complete alias-to-backend mapping must equal the selected package's `_FORMAT_MAP`, including synonym membership. |
| Requirement | Unique stable uppercase-hyphenated `id`, `description`, known `features`, `category`, `clauses`, nonempty `owners`, `status`, `reason`, `evidence`, and `not_applicable`. Every feature needs supported evidence. |
| Clause | `reference`, exact `section`, `anchor`, and boolean `normative`. HTML entries must match the verified reference manifest's anchor, heading label and normative status. Numbered RFC text sections use a null anchor and must match a complete heading in the checked original text. |
| Owner | `role`, `target`, and `path`. Roles are `local` contract/algorithm, `dependency`-owned syntax/canonicalization or binding data, and `boundary` validation. Targets are actual local callable entry points in the selected package; paths must match their source files. A dependency role identifies the local call site, not an independent implementation of that backend. |
| Supported row | `status: supported`, null `reason`, and nonempty `evidence`. Each dimension appears either in evidence or in `not_applicable`, never both. |
| Excluded row | `status: out-of-profile` and a nonempty `reason`. Both evidence maps must be empty; exclusions are visible profile boundaries, not silently passing tests. |

The six evidence dimensions are `positive`, `negative`, `boundary`, `property`,
`subprocess` and `end-to-end`. Evidence values are nonempty lists of pytest
selectors. `not_applicable` values explain why the dimension is not separately
claimed in that row: a no-argument snapshot has no invalid-input domain, for
example, and serializer term fidelity does not require syntax-parser rejection
tests. Shared process or composed-workflow obligations can be mapped in their
own rows. Explicit examples do not imply an independent randomized property.

A selector is either an exact collected nodeid, such as
`tests/contracts/test_prefix_map.py::test_prefix_map_calls_return_independent_snapshots`,
or a function-family selector matching that exact name followed by pytest's
`[` parameter suffix. Module paths alone, globs, substring matches, nonexistent
functions and empty evidence sets are rejected. A function with both a bare
nodeid and parametrized children is ambiguous and fails validation. Renaming
or removing a referenced test therefore fails the gate even if its file remains.

When changing the feature or evidence set:

1. Read the selected tests' assertions and keep each row no broader than the
   concrete evidence. Identify local versus dependency ownership explicitly.
2. Add verified anchors only from the same pinned original bytes. Distinguish
   normative grammar and algorithms from informative examples. Original assets
   and their hashes need not change when the selected anchor inventory grows.
3. Update feature, requirement and evidence entries together; do not make a
   supported behavior out of profile merely because a test fails.
4. Run `python scripts/check_requirements.py --render` to explicitly update the
   generated table, then run the default check. The default never rewrites it.
5. Run the full source and exact installed-wheel suites. The source distribution
   carries documents, scripts and tests; runtime wheels carry none of these assets.
