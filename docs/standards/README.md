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
