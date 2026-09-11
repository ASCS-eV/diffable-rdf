# Scoped requirement evidence

Generated from [requirements.json](requirements.json) by `python scripts/check_requirements.py --render`.
The default command checks this table without modifying it.

49 supported requirements; 5 explicit profile exclusions; 874 distinct collected tests; 1003 requirement-to-test links.

Counts describe collected evidence, not executed or passing tests. One test can support several rows.
This is not a percentage of all clauses in the copied specifications or a complete Cartesian test matrix.
Source and installed targets collect the same behavioral evidence; platform/resource and source-only
harness skips are reported by pytest when executing the suite, not hidden by collection counts.

## Feature inventory

| Feature | Contract | Export or format aliases |
| --- | --- | --- |
| `deterministic_turtle` | Diff-stable Turtle graph rendering | `deterministic_turtle` |
| `canonicalize_rdf_graph` | Single-graph serialization with backend canonical labels | `canonicalize_rdf_graph` |
| `deterministic_json` | Deterministic JSON ordering with bounded JSON-LD ordering awareness | `deterministic_json` |
| `well_known_prefix_map` | Independent namespace-to-prefix mappings | `well_known_prefix_map` |
| `wl_blank_node_labels` | Structural labels for canonicalized quads | `wl_blank_node_labels` |
| `wl_relabel_quads` | Relabelled copies of canonicalized quads | `wl_relabel_quads` |
| `format.turtle` | Turtle graph output | `turtle`, `ttl` |
| `format.nt` | N-Triples graph output | `nt`, `ntriples`, `n-triples`, `nt11` |
| `format.nquads` | N-Quads graph output | `nquads`, `n-quads` |
| `format.xml` | RDF/XML graph output | `xml`, `rdf/xml` |
| `format.trig` | TriG graph output | `trig` |
| `format.n3` | N3 graph output | `n3` |
| `format.jsonld` | JSON-LD graph output | `json-ld`, `jsonld`, `application/ld+json` |

## Requirement map

| Requirement | Category / status | Concrete behavior | Tests |
| --- | --- | --- | --- |
| [API-SURFACE](#api-surface) | policy / supported | Six public functions have the documented exports and resolvable runtime annotations. | 10 |
| [API-EXAMPLES](#api-examples) | policy / supported | Eight executable documentation examples run against the selected package; six signature blocks parse as single function definitions. | 30 |
| [GRAPH-ADMISSION](#graph-admission) | policy / supported | Graph serializers admit individual graph contexts and reject Dataset and ConjunctiveGraph containers before dispatch. | 59 |
| [GRAPH-IMMUTABILITY](#graph-immutability) | policy / supported | Serialization retains caller triples, base, bindings and global literal settings in the checked native and degraded cases. | 71 |
| [FORMAT-DETERMINISM](#format-determinism) | policy / supported | Every guaranteed alias has byte-identical output across hash-seeded processes on a shared-list graph. | 22 |
| [FORMAT-ALIASES](#format-aliases) | policy / supported | Aliases select the same backend syntax; representative mixed-case names and degraded synonyms preserve their contract. | 19 |
| [FORMAT-DELEGATION](#format-delegation) | policy / supported | Unmapped plugins are explicitly outside the determinism guarantee; unknown plugins and empty delegated output fail visibly. | 5 |
| [FORMAT-FRAMING](#format-framing) | policy / supported | Nonempty mapped RDF output has exactly one trailing newline on normal and carrying degraded paths. | 41 |
| [FORMAT-EMPTY](#format-empty) | policy / supported | Empty Turtle and N-Triples stay empty; empty JSON-LD is a newline-terminated empty array. | 1 |
| [GRAPH-DEFAULT](#graph-default) | normative / supported | Single-graph N-Quads has no graph label; degraded TriG carries explicit default-graph list triples. | 27 |
| [RDF-ISOMORPHISM](#rdf-isomorphism) | normative / supported | Seeded Turtle graph shapes preserve RDF graph identity after serialization and parsing. | 40 |
| [TURTLE-STABILITY](#turtle-stability) | policy / supported | Seeded Turtle output is idempotent and independent of insertion order and source blank-node names. | 120 |
| [RDF-LEXICAL](#rdf-lexical) | normative / supported | Checked integer, boolean, dateTime, decimal, signed-zero and non-finite literal spellings retain lexical term identity. | 18 |
| [RDF-LANGUAGE](#rdf-language) | normative / supported | Plain strings and xsd:string render equivalently; normal-path language tags use the permitted lowercase spelling. | 4 |
| [RDF-IRI-BASE](#rdf-iri-base) | normative / supported | Fragment, path, query and equal-base namespaces preserve direct and datatype IRIs in the checked verified renderings. | 43 |
| [RDF-DATATYPE-GUARD](#rdf-datatype-guard) | policy / supported | Round-trip boundary checks distinguish missing or invented datatype IRIs from xsd:string literal equivalence. | 6 |
| [TURTLE-QUOTING](#turtle-quoting) | normative / supported | Quoted literals preserve terminal quote/backslash runs, LF, CR and CRLF in checked native and relative-subject outputs. | 31 |
| [TURTLE-NAMES](#turtle-names) | normative / supported | Punctuation, Unicode-prefix, overlapping-prefix and unprefixable IRI examples preserve subject, predicate, object and datatype IRIs. | 110 |
| [TURTLE-COLLECTIONS](#turtle-collections) | normative / supported | Private, shared-head and shared-tail list examples retain cell identity; the degraded path uses explicit list triples. | 9 |
| [TURTLE-PRESENTATION](#turtle-presentation) | policy / supported | Diff-stable Turtle uses quoted typed literals and inline blank nodes where the graph shape permits. | 3 |
| [NAMESPACES-ISOLATION](#namespaces-isolation) | policy / supported | Namespace selection preserves caller bindings, reserves generated names, generates them only where the serializer asks, and remains stable across processes in checked graph shapes. | 33 |
| [SERIALIZER-VERIFICATION](#serializer-verification) | policy / supported | Verified renderings remove base then prefixes only after failed fidelity checks; final validation and unrelated backend errors propagate. | 15 |
| [LINE-TERMS](#line-terms) | normative / supported | Line syntaxes refuse relative or malformed IRIs and name the offending term position rather than emit invalid N-Triples or N-Quads. | 11 |
| [LINE-SEPARATORS](#line-separators) | policy / supported | The internal line sorter preserves Unicode separators inside literals and sorts complete statement lines. | 18 |
| [XML-LITERALS](#xml-literals) | normative / supported | Checked RDF/XML literals retain CR, CRLF, tabs, Unicode, markup escapes, datatypes and language identity after parsing. | 9 |
| [XML-CHARACTERS](#xml-characters) | normative / supported | RDF/XML rejects XML 1.0-forbidden characters in literal content and serializer metadata. | 6 |
| [XML-NAMESPACE](#xml-namespace) | policy / supported | Checked RDF/XML namespace declarations survive sorting; an inexpressible generalized literal predicate surfaces its backend QName error. | 3 |
| [XML-ORDERING](#xml-ordering) | policy / supported | Degraded RDF/XML orders descriptions and property elements without altering graph meaning or caller prefixes. | 6 |
| [JSONLD-GRAPH](#jsonld-graph) | normative / supported | The normal expanded JSON-LD backend preserves shared RDF list cells instead of compacting them into duplicate lists. | 2 |
| [JSONLD-FALLBACK](#jsonld-fallback) | normative / supported | Expanded degraded JSON-LD retains shared cells, references, cycles and literal annotation strings. | 33 |
| [JSONLD-TERM-BOUNDARY](#jsonld-term-boundary) | policy / supported | The degraded JSON-LD subset refuses generalized term positions, relative predicate/datatype IRIs and URIRef values resembling blank-node identifiers. | 10 |
| [JSONLD-RESERVED](#jsonld-reserved) | policy / supported | The degraded writer refuses keyword-shaped relative identifiers, while keyword-shaped literal text and non-keyword identifier spellings survive. | 75 |
| [JSON-ORDERING](#json-ordering) | policy / supported | Object keys and application-unordered arrays sort deterministically without mutation; this changes ordinary JSON array order by project policy. | 4 |
| [JSON-MIXEDKEYS](#json-mixedkeys) | extension / supported | Mixed Python keys sort by their encoded names, and duplicate encoded names are refused before JSON object information can be lost. | 4 |
| [JSON-LISTS](#json-lists) | normative / supported | Explicit and locally declared lists retain order, including nested lists, while graph/set arrays may be reordered without changing the checked RDF meaning. | 9 |
| [JSON-CONTEXTS](#json-contexts) | policy / supported | Local ordering facts respect sequential context overrides, inheritance, null resets and checked forward alias definitions without claiming a full context processor. | 9 |
| [JSON-LITERALS](#json-literals) | normative / supported | Explicit and locally recognized JSON literal payload arrays retain their sequence and checked RDF meaning. | 5 |
| [JSON-UNKNOWN](#json-unknown) | policy / supported | Unknown remote, scoped and unsupported local contexts conservatively preserve descendant arrays and never fetch remote contexts. | 5 |
| [JSON-OVERRIDES](#json-overrides) | policy / supported | Custom preserved-key sets replace convenience defaults without disabling keyword-based list protection. | 4 |
| [WL-IDENTITY](#wl-identity) | policy / supported | WL relabelling returns a fresh isomorphic quad list, preserves blank-node cardinality and leaves input quads untouched. | 10 |
| [WL-COMPONENTS](#wl-components) | policy / supported | Unrelated additions, edits and removals do not advance a disconnected component's default refinement. | 9 |
| [WL-TIES](#wl-ties) | policy / supported | Structurally tied nodes remain injective and collision suffixes follow numeric canonical numbering. | 4 |
| [WL-GRAPHS](#wl-graphs) | policy / supported | Named graphs influence labels; blank graph-name identifiers remain consistent when also used as object terms. | 4 |
| [WL-ITERATIONS](#wl-iterations) | policy / supported | Default refinement reaches component fixpoints, explicit rounds remain synchronous, zero is valid and negative counts are refused. | 7 |
| [WL-BOUNDARY](#wl-boundary) | policy / supported | Embedded triple objects are rejected consistently at zero, explicit and default refinement rounds. | 33 |
| [WL-DIRECTION](#wl-direction) | extension / supported | Dependency-supported directional literals remain distinct and retain language and direction fields during WL relabelling. | 1 |
| [WORK-TIME](#work-time) | policy / supported | A representative 8400-triple OWL-shaped graph serializes within the tested process time budget. | 1 |
| [WORK-MEMORY](#work-memory) | policy / supported | A representative sixteen-round WL workload fits the tested address-space budget where the platform supports limits. | 1 |
| [PREFIX-MAP](#prefix-map) | policy / supported | Prefix maps invert the selected RDFLib nonempty bindings into independent string dictionaries. | 3 |
| [PROFILE-RDFC-PROCESSOR](#profile-rdfc-processor) | normative / out-of-profile | Standalone RDFC processor conformance, canonical N-Quads bytes and hash selection are outside the wrapper API. | 0 |
| [PROFILE-RDFC-LIMITS](#profile-rdfc-limits) | normative / out-of-profile | Configurable RDFC resource-limit reporting is not exposed by the graph serializer API. | 0 |
| [PROFILE-JSONLD-PROCESSOR](#profile-jsonld-processor) | normative / out-of-profile | Full JSON-LD expansion, compaction, remote loading and processing-algorithm conformance are outside the ordering helper. | 0 |
| [PROFILE-N3-LOGIC](#profile-n3-logic) | policy / out-of-profile | Notation3 formulas, implications and variable-based logic are outside the supported N3 graph subset. | 0 |
| [PROFILE-RDF12](#profile-rdf12) | extension / out-of-profile | Complete RDF 1.2 or embedded-triple conformance is outside the accepted WL term extension. | 0 |

### API-SURFACE

Six public functions have the documented exports and resolvable runtime annotations.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `deterministic_json`, `well_known_prefix_map`, `wl_blank_node_labels`, `wl_relabel_quads`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).
- local: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).
- local: [`diffable_rdf.jsonld:deterministic_json`](../../src/diffable_rdf/jsonld.py).
- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.turtle:well_known_prefix_map`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/contracts/test_public_api_surface.py::test_the_documented_surface_is_what_the_module_exports` (1)<br>`tests/contracts/test_public_api_surface.py::test_every_public_annotation_resolves_at_runtime` (6) |
| negative | Not applicable: Export enumeration and annotation inspection take no caller data to reject. |
| boundary | `tests/contracts/test_public_api_surface.py::test_the_turtle_entry_point_names_the_graph_type_it_takes` (1)<br>`tests/contracts/test_public_api_surface.py::test_the_preserved_keys_argument_admits_any_set` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | `tests/contracts/test_public_api_surface.py::test_both_dependencies_are_loaded_before_any_public_call_can_be_made` (1) |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### API-EXAMPLES

Eight executable documentation examples run against the selected package; six signature blocks parse as single function definitions.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `deterministic_json`, `well_known_prefix_map`, `wl_blank_node_labels`, `wl_relabel_quads`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).
- local: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).
- local: [`diffable_rdf.jsonld:deterministic_json`](../../src/diffable_rdf/jsonld.py).
- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.turtle:well_known_prefix_map`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/integration/test_documentation_examples.py::test_documentation_classifies_every_python_block` (1)<br>`tests/integration/test_documentation_examples.py::test_documented_signature_parses` (6) |
| negative | `tests/integration/test_documentation_examples.py::test_broken_documentation_example_fails_in_the_selected_interpreter` (1) |
| boundary | `tests/integration/test_documentation_examples.py::test_extractor_rejects_missing_and_invalid_markers` (14) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | `tests/integration/test_documentation_examples.py::test_documented_example_runs_from_a_neutral_directory` (8) |

### GRAPH-ADMISSION

Graph serializers admit individual graph contexts and reject Dataset and ConjunctiveGraph containers before dispatch.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`.

References: [RDF11-CONCEPTS §3.1 Triples](references/rdf11-concepts.html#section-triples) (normative).

- boundary: [`diffable_rdf.graph_input:_require_single_graph`](../../src/diffable_rdf/graph_input.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/contracts/test_graph_input.py::test_individual_dataset_graph_context_is_accepted_losslessly` (8)<br>`tests/contracts/test_graph_input.py::test_ordinary_graph_with_context_aware_store_is_accepted` (2) |
| negative | `tests/contracts/test_graph_input.py::test_dataset_containers_are_rejected_without_mutation` (32)<br>`tests/contracts/test_graph_input.py::test_canonicalize_rejects_datasets_before_every_format_dispatch` (16) |
| boundary | `tests/contracts/test_graph_input.py::test_canonicalize_rejects_dataset_before_inspecting_format` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### GRAPH-IMMUTABILITY

Serialization retains caller triples, base, bindings and global literal settings in the checked native and degraded cases.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).
- local: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_literal_fidelity.py::test_serialization_does_not_mutate_input_or_global_normalization` (1)<br>`tests/serialization/test_prefixed_names.py::test_prefixed_names_preserve_every_term_position` (60)<br>`tests/serialization/test_namespace_term_positions.py::test_the_caller_graph_and_its_bindings_are_untouched` (3) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_xml_fidelity.py::test_rdf_xml_is_stable_and_does_not_mutate_input_or_global_settings` (1)<br>`tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_aliases_are_deterministic_and_leave_input_unchanged` (6) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### FORMAT-DETERMINISM

Every guaranteed alias has byte-identical output across hash-seeded processes on a shared-list graph.

Features: `canonicalize_rdf_graph`, `format.turtle`, `format.nt`, `format.nquads`, `format.xml`, `format.trig`, `format.n3`, `format.jsonld`.

References: [RDFC10 §3.1 Terms defined by this specification](references/rdf-canon.html#canon-terms) (normative).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/contracts/test_format_guarantee.py::test_canonicalize_rdf_graph_is_deterministic_across_processes` (7) |
| negative | Not applicable: Format admission and delegated-name boundaries are mapped separately in FORMAT-DELEGATION. |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | `tests/contracts/test_format_guarantee.py::test_every_mapped_format_is_byte_identical_across_processes` (15) |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### FORMAT-ALIASES

Aliases select the same backend syntax; representative mixed-case names and degraded synonyms preserve their contract.

Features: `canonicalize_rdf_graph`, `format.turtle`, `format.nt`, `format.nquads`, `format.xml`, `format.trig`, `format.n3`, `format.jsonld`.

Project contract; no normative standard algorithm is claimed.

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/contracts/test_format_guarantee.py::test_mapped_formats_cover_every_name_the_docstring_promises` (1)<br>`tests/contracts/test_format_guarantee.py::test_canonicalize_rdf_graph_accepts_mixed_case_format_names` (3)<br>`tests/serialization/test_degraded_format_coverage.py::test_synonyms_for_one_format_produce_identical_bytes` (3) |
| negative | `tests/serialization/test_degraded_format_coverage.py::test_synonyms_refuse_for_the_same_reason` (2) |
| boundary | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_aliases_are_deterministic_and_leave_input_unchanged` (6)<br>`tests/serialization/test_xml_fidelity.py::test_rdf_xml_aliases_use_exact_round_trip_guard` (4) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### FORMAT-DELEGATION

Unmapped plugins are explicitly outside the determinism guarantee; unknown plugins and empty delegated output fail visibly.

Features: `canonicalize_rdf_graph`.

Project contract; no normative standard algorithm is claimed.

- boundary: [`diffable_rdf.canonicalize:_deterministic_fallback_serialize`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/contracts/test_format_guarantee.py::test_delegating_to_an_rdflib_plugin_warns_that_the_guarantee_does_not_apply` (1)<br>`tests/contracts/test_format_guarantee.py::test_a_delegated_format_still_gets_canonical_blank_node_labels` (1) |
| negative | `tests/contracts/test_format_guarantee.py::test_an_unregistered_format_name_still_surfaces_rdflibs_own_error` (1)<br>`tests/serialization/test_fallback_integrity.py::test_a_delegated_format_that_writes_nothing_is_refused_not_returned` (1) |
| boundary | `tests/serialization/test_degraded_format_coverage.py::test_an_unregistered_name_still_reaches_rdflib_on_the_degraded_path` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### FORMAT-FRAMING

Nonempty mapped RDF output has exactly one trailing newline on normal and carrying degraded paths.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `format.turtle`, `format.nt`, `format.nquads`, `format.xml`, `format.trig`, `format.n3`, `format.jsonld`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.canonicalize:_with_single_trailing_newline`](../../src/diffable_rdf/canonicalize.py).
- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/contracts/test_trailing_newline.py::test_every_mapped_format_ends_with_exactly_one_newline` (15)<br>`tests/contracts/test_trailing_newline.py::test_deterministic_turtle_ends_with_exactly_one_newline` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/contracts/test_trailing_newline.py::test_the_degraded_path_ends_with_exactly_one_newline` (9)<br>`tests/contracts/test_trailing_newline.py::test_deterministic_turtle_ends_with_exactly_one_newline_when_degraded` (1)<br>`tests/contracts/test_trailing_newline.py::test_normalising_the_newline_does_not_add_a_blank_line` (15) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### FORMAT-EMPTY

Empty Turtle and N-Triples stay empty; empty JSON-LD is a newline-terminated empty array.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `format.turtle`, `format.nt`, `format.jsonld`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).
- local: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/contracts/test_trailing_newline.py::test_an_empty_graph_stays_an_empty_document` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/contracts/test_trailing_newline.py::test_an_empty_graph_stays_an_empty_document` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### GRAPH-DEFAULT

Single-graph N-Quads has no graph label; degraded TriG carries explicit default-graph list triples.

Features: `canonicalize_rdf_graph`, `format.nquads`, `format.trig`.

References: [NQUADS11 §2.1 Simple Statements](references/n-quads.html#simple-triples) (normative); [TRIG11 §5.3.1 Output Graph](references/trig.html#output-graph) (normative).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_degraded_format_coverage.py::test_line_oriented_output_still_works_when_the_graph_is_representable` (1)<br>`tests/serialization/test_degraded_format_coverage.py::test_degraded_trig_states_list_structure_explicitly` (1) |
| negative | `tests/contracts/test_graph_input.py::test_canonicalize_rejects_datasets_before_every_format_dispatch` (16) |
| boundary | `tests/serialization/test_degraded_format_coverage.py::test_degraded_output_preserves_the_graph` (9) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### RDF-ISOMORPHISM

Seeded Turtle graph shapes preserve RDF graph identity after serialization and parsing.

Features: `deterministic_turtle`.

References: [RDF11-CONCEPTS §3.6 Graph Comparison](references/rdf11-concepts.html#section-graph-equality) (normative).

- dependency: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/properties/test_canonicalization_properties.py::test_p1_canonical_output_is_lossless` (40) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | `tests/properties/test_canonicalization_properties.py::test_p1_canonical_output_is_lossless` (40) |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### TURTLE-STABILITY

Seeded Turtle output is idempotent and independent of insertion order and source blank-node names.

Features: `deterministic_turtle`.

Project contract; no normative standard algorithm is claimed.

- dependency: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/properties/test_canonicalization_properties.py::test_p2_canonicalization_is_idempotent` (40) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | `tests/properties/test_canonicalization_properties.py::test_p2_canonicalization_is_idempotent` (40)<br>`tests/properties/test_canonicalization_properties.py::test_p3_output_does_not_depend_on_blank_node_labels` (40)<br>`tests/properties/test_canonicalization_properties.py::test_p4_output_does_not_depend_on_insertion_order` (40) |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### RDF-LEXICAL

Checked integer, boolean, dateTime, decimal, signed-zero and non-finite literal spellings retain lexical term identity.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `format.turtle`, `format.trig`, `format.n3`.

References: [RDF11-CONCEPTS §3.3 Literals](references/rdf11-concepts.html#section-Graph-Literal) (normative).

- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).
- local: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_literal_fidelity.py::test_deterministic_turtle_preserves_distinct_lexical_forms` (4)<br>`tests/serialization/test_literal_fidelity.py::test_lower_level_turtle_family_preserves_literal_identity` (3) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_literal_fidelity.py::test_deterministic_turtle_preserves_full_double_precision` (1)<br>`tests/serialization/test_literal_fidelity.py::test_deterministic_turtle_preserves_other_typed_lexical_forms` (2)<br>`tests/serialization/test_numeric_literal_edges.py::test_the_lexical_form_the_graph_holds_is_what_is_written` (8) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### RDF-LANGUAGE

Plain strings and xsd:string render equivalently; normal-path language tags use the permitted lowercase spelling.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`.

References: [RDF11-CONCEPTS §3.3 Literals](references/rdf11-concepts.html#section-Graph-Literal) (normative).

- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).
- local: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_literal_fidelity.py::test_intentional_string_and_language_equivalences_remain_canonical` (1)<br>`tests/integration/test_diffable_rdf.py::test_canonicalize_rdf_graph_normalizes_language_tag_case` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_base_iri_fidelity.py::test_the_guard_accepts_plain_string_and_xsd_string_datatype_equivalence` (1)<br>`tests/serialization/test_base_iri_fidelity.py::test_the_guard_keeps_a_direct_xsd_string_iri_significant` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### RDF-IRI-BASE

Fragment, path, query and equal-base namespaces preserve direct and datatype IRIs in the checked verified renderings.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `format.turtle`, `format.trig`, `format.n3`, `format.xml`.

References: [TURTLE11 §6.3 IRI References](references/turtle.html#sec-iri-references) (normative); [RFC3986 §5.2 Relative Resolution](references/rfc3986.txt) (normative).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).
- dependency: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_base_iri_fidelity.py::test_a_fragment_base_preserves_the_terms` (6)<br>`tests/serialization/test_base_iri_fidelity.py::test_an_equal_base_namespace_preserves_every_iri_position` (20) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_base_iri_fidelity.py::test_deterministic_turtle_preserves_hash_path_and_slash_bases` (1)<br>`tests/serialization/test_base_iri_fidelity.py::test_an_unprefixed_query_base_retries_without_base_and_preserves_datatypes` (4)<br>`tests/serialization/test_base_iri_fidelity.py::test_a_datatype_only_query_base_retries_without_base` (4)<br>`tests/serialization/test_base_iri_fidelity.py::test_rdf_xml_retries_without_base_for_typed_literal_namespaces` (8) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### RDF-DATATYPE-GUARD

Round-trip boundary checks distinguish missing or invented datatype IRIs from xsd:string literal equivalence.

Features: `canonicalize_rdf_graph`.

References: [RDF11-CONCEPTS §3.3 Literals](references/rdf11-concepts.html#section-Graph-Literal) (normative).

- boundary: [`diffable_rdf.canonicalize:_assert_round_trips`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_base_iri_fidelity.py::test_the_guard_accepts_plain_string_and_xsd_string_datatype_equivalence` (1) |
| negative | `tests/serialization/test_base_iri_fidelity.py::test_the_guard_catches_missing_and_invented_literal_datatypes` (2)<br>`tests/serialization/test_base_iri_fidelity.py::test_the_guard_catches_an_iri_the_input_never_contained` (1)<br>`tests/serialization/test_base_iri_fidelity.py::test_the_guard_keeps_a_direct_xsd_string_iri_significant` (1) |
| boundary | `tests/serialization/test_base_iri_fidelity.py::test_the_guard_tolerates_rdflibs_literal_normalization` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### TURTLE-QUOTING

Quoted literals preserve terminal quote/backslash runs, LF, CR and CRLF in checked native and relative-subject outputs.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `format.turtle`, `format.trig`, `format.n3`.

References: [TURTLE11 §6.4 Escape Sequences](references/turtle.html#sec-escapes) (normative); [TURTLE11 §6.5 Grammar](references/turtle.html#sec-grammar-grammar) (normative); [RDF11-CONCEPTS §3.3 Literals](references/rdf11-concepts.html#section-Graph-Literal) (normative).

- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).
- local: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_numeric_literal_edges.py::test_literals_needing_escapes_still_round_trip` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_literal_fidelity.py::test_deterministic_turtle_preserves_literal_quote_boundaries` (3)<br>`tests/serialization/test_literal_fidelity.py::test_turtle_aliases_preserve_literal_quote_boundaries` (12)<br>`tests/serialization/test_literal_fidelity.py::test_deterministic_turtle_fallback_preserves_literal_quote_boundaries` (3)<br>`tests/serialization/test_literal_fidelity.py::test_turtle_alias_fallbacks_preserve_literal_quote_boundaries` (12) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### TURTLE-NAMES

Punctuation, Unicode-prefix, overlapping-prefix and unprefixable IRI examples preserve subject, predicate, object and datatype IRIs.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `format.turtle`, `format.trig`, `format.n3`.

References: [TURTLE11 §6.5 Grammar](references/turtle.html#sec-grammar-grammar) (normative); [RFC3987 §2.2 ABNF for IRI References and IRIs](references/rfc3987.txt) (normative).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).
- dependency: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_prefixed_names.py::test_prefixed_names_preserve_every_term_position` (60)<br>`tests/serialization/test_prefixed_names.py::test_overlapping_prefixes_and_aliases_remain_optional` (3)<br>`tests/serialization/test_namespace_term_positions.py::test_deterministic_turtle_writes_a_split_hostile_iri_in_every_position` (6)<br>`tests/serialization/test_namespace_term_positions.py::test_the_canonicalizer_writes_a_split_hostile_iri_in_every_position` (24) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_prefixed_names.py::test_curie_looking_literal_content_is_data` (3)<br>`tests/serialization/test_prefixed_names.py::test_deterministic_turtle_preserves_curie_looking_literal_content` (1)<br>`tests/serialization/test_namespace_term_positions.py::test_the_degraded_path_writes_a_split_hostile_iri_in_every_position` (12)<br>`tests/serialization/test_namespace_term_positions.py::test_a_split_hostile_predicate_is_refused_rather_than_written_invalidly` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### TURTLE-COLLECTIONS

Private, shared-head and shared-tail list examples retain cell identity; the degraded path uses explicit list triples.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`, `format.turtle`, `format.trig`, `format.n3`.

References: [RDF11-CONCEPTS §3.6 Graph Comparison](references/rdf11-concepts.html#section-graph-equality) (normative); [TURTLE11 §2.8 Collections](references/turtle.html#collections) (informative context).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).
- dependency: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/properties/test_canonicalization_properties.py::test_shared_list_structures_survive_canonicalization` (6) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_degraded_collections.py::test_degraded_turtle_is_lossless_for_shared_list_tails` (1)<br>`tests/serialization/test_degraded_collections.py::test_degraded_n3_is_lossless_for_shared_list_tails` (1)<br>`tests/serialization/test_degraded_format_coverage.py::test_degraded_trig_states_list_structure_explicitly` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### TURTLE-PRESENTATION

Diff-stable Turtle uses quoted typed literals and inline blank nodes where the graph shape permits.

Features: `deterministic_turtle`.

References: [TURTLE11 §6.5 Grammar](references/turtle.html#sec-grammar-grammar) (normative).

- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_literal_fidelity.py::test_typed_literals_are_written_in_quoted_form` (1)<br>`tests/integration/test_diffable_rdf.py::test_deterministic_turtle_uses_inline_blank_nodes` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_numeric_literal_edges.py::test_the_object_order_is_total_for_value_tied_and_mixed_terms` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### NAMESPACES-ISOLATION

Namespace selection preserves caller bindings, reserves generated names, generates them only where the serializer asks, and remains stable across processes in checked graph shapes.

Features: `deterministic_turtle`, `canonicalize_rdf_graph`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.namespaces:bind_source_namespaces`](../../src/diffable_rdf/namespaces.py).
- local: [`diffable_rdf.namespaces:prepare_namespaces`](../../src/diffable_rdf/namespaces.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_namespace_determinism.py::test_caller_prefixes_are_preserved_and_generated_names_are_reserved` (1)<br>`tests/serialization/test_namespace_term_positions.py::test_only_the_predicate_position_earns_a_generated_prefix` (1)<br>`tests/serialization/test_namespace_term_positions.py::test_a_bound_namespace_is_used_in_every_position` (3)<br>`tests/serialization/test_namespace_term_positions.py::test_generated_names_follow_the_graph_not_its_insertion_order` (5) |
| negative | `tests/serialization/test_namespace_determinism.py::test_an_undeclarable_binding_preserves_usable_prefixes` (1) |
| boundary | `tests/serialization/test_namespace_determinism.py::test_deterministic_turtle_degraded_path_keeps_graph_and_bindings` (1)<br>`tests/serialization/test_namespace_determinism.py::test_the_prefix_filter_matches_what_pyoxigraph_will_accept` (10)<br>`tests/serialization/test_namespace_term_positions.py::test_a_keyword_predicate_declares_nothing` (1)<br>`tests/serialization/test_namespace_term_positions.py::test_preprocessing_presents_every_triple_exactly_once` (2)<br>`tests/serialization/test_namespace_term_positions.py::test_a_format_without_positional_discovery_preallocates_in_iri_order` (2) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | `tests/serialization/test_namespace_determinism.py::test_namespace_allocation_is_stable_across_processes` (5)<br>`tests/serialization/test_namespace_term_positions.py::test_split_hostile_output_is_stable_across_processes` (1) |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### SERIALIZER-VERIFICATION

Verified renderings remove base then prefixes only after failed fidelity checks; final validation and unrelated backend errors propagate.

Features: `canonicalize_rdf_graph`.

Project contract; no normative standard algorithm is claimed.

- boundary: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_base_iri_fidelity.py::test_a_verified_base_does_not_serialize_twice` (3)<br>`tests/serialization/test_prefixed_names.py::test_a_valid_compact_spelling_keeps_a_problematic_binding` (3) |
| negative | `tests/serialization/test_prefixed_names.py::test_final_prefix_attempt_propagates_validation_failure` (1)<br>`tests/serialization/test_base_iri_fidelity.py::test_an_unrelated_backend_error_is_not_retried` (3)<br>`tests/serialization/test_xml_fidelity.py::test_rdf_xml_guard_rejects_corrupted_serializer_output` (2) |
| boundary | `tests/serialization/test_prefixed_names.py::test_verification_failures_remove_options_in_order` (2)<br>`tests/serialization/test_prefixed_names.py::test_retry_options_do_not_affect_later_renderings` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### LINE-TERMS

Line syntaxes refuse relative or malformed IRIs and name the offending term position rather than emit invalid N-Triples or N-Quads.

Features: `canonicalize_rdf_graph`, `format.nt`, `format.nquads`.

References: [NTRIPLES11 §2.2 IRIs](references/n-triples.html#sec-iri) (normative); [NTRIPLES11 §7 Grammar](references/n-triples.html#n-triples-grammar) (normative); [NQUADS11 §4 Grammar](references/n-quads.html#sec-grammar) (normative); [RDF11-CONCEPTS §3.1 Triples](references/rdf11-concepts.html#section-triples) (normative).

- boundary: [`diffable_rdf.canonicalize:_first_term_n_triples_cannot_write`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_degraded_format_coverage.py::test_line_oriented_output_still_works_when_the_graph_is_representable` (1) |
| negative | `tests/serialization/test_degraded_format_coverage.py::test_line_oriented_aliases_refuse_a_graph_they_cannot_represent` (6)<br>`tests/serialization/test_degraded_format_coverage.py::test_the_refusal_covers_an_iri_that_is_absolute_but_not_valid` (3) |
| boundary | `tests/serialization/test_degraded_format_coverage.py::test_the_refusal_names_the_position_of_the_offending_term` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### LINE-SEPARATORS

The internal line sorter preserves Unicode separators inside literals and sorts complete statement lines.

Features: `canonicalize_rdf_graph`, `format.nt`, `format.nquads`.

References: [NTRIPLES11 §7 Grammar](references/n-triples.html#n-triples-grammar) (normative); [NQUADS11 §4 Grammar](references/n-quads.html#sec-grammar) (normative).

- local: [`diffable_rdf.canonicalize:_deterministic_fallback_serialize`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_fallback_integrity.py::test_the_line_sort_still_sorts` (2) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_fallback_integrity.py::test_the_line_sort_preserves_a_literal_carrying_a_unicode_break` (16) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This internal branch is tested directly; unrepresentable public line-format inputs are refused before it. |

### XML-LITERALS

Checked RDF/XML literals retain CR, CRLF, tabs, Unicode, markup escapes, datatypes and language identity after parsing.

Features: `canonicalize_rdf_graph`, `format.xml`.

References: [XML10 §2.11 End-of-Line Handling](references/xml.html#sec-line-ends) (normative); [RDF11-CONCEPTS §3.3 Literals](references/rdf11-concepts.html#section-Graph-Literal) (normative); [RDFXML11 §7 RDF/XML Grammar](references/rdf-syntax-grammar.html#section-Infoset-Grammar) (normative).

- boundary: [`diffable_rdf.canonicalize:_finalize_rdf_xml`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_xml_fidelity.py::test_rdf_xml_preserves_diverse_literal_content_and_identity` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_xml_fidelity.py::test_rdf_xml_preserves_known_lossy_literal_values` (3)<br>`tests/serialization/test_xml_fidelity.py::test_rdf_xml_aliases_work_on_degraded_fallback` (4)<br>`tests/serialization/test_degraded_rdfxml_determinism.py::test_a_literal_carriage_return_still_survives_the_sort` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### XML-CHARACTERS

RDF/XML rejects XML 1.0-forbidden characters in literal content and serializer metadata.

Features: `canonicalize_rdf_graph`, `format.xml`.

References: [XML10 §2.2 Characters](references/xml.html#charsets) (normative).

- boundary: [`diffable_rdf.canonicalize:_assert_xml_10_representable`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_xml_fidelity.py::test_rdf_xml_preserves_diverse_literal_content_and_identity` (1) |
| negative | `tests/serialization/test_xml_fidelity.py::test_rdf_xml_rejects_characters_forbidden_by_xml_10` (4) |
| boundary | `tests/serialization/test_xml_fidelity.py::test_rdf_xml_rejects_forbidden_characters_in_serializer_metadata` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### XML-NAMESPACE

Checked RDF/XML namespace declarations survive sorting; an inexpressible generalized literal predicate surfaces its backend QName error.

Features: `canonicalize_rdf_graph`, `format.xml`.

References: [XMLNS10 §4 Qualified Names](references/xml-names.html#ns-qualnames) (normative).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_degraded_rdfxml_determinism.py::test_the_callers_prefix_names_survive_the_sort` (1)<br>`tests/serialization/test_degraded_rdfxml_determinism.py::test_the_document_stays_well_formed_and_declared` (1) |
| negative | `tests/serialization/test_fallback_integrity.py::test_a_fallback_serializer_error_names_the_format_and_a_way_forward` (1) |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### XML-ORDERING

Degraded RDF/XML orders descriptions and property elements without altering graph meaning or caller prefixes.

Features: `canonicalize_rdf_graph`, `format.xml`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.canonicalize:_sort_rdf_xml_descriptions`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_degraded_rdfxml_determinism.py::test_sorting_preserves_the_graph` (1)<br>`tests/serialization/test_degraded_rdfxml_determinism.py::test_property_elements_within_a_subject_are_ordered_too` (1)<br>`tests/serialization/test_degraded_rdfxml_determinism.py::test_properties_are_ordered_by_predicate_not_by_their_objects_label` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_degraded_rdfxml_determinism.py::test_the_output_does_not_depend_on_process_global_xml_state` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | `tests/serialization/test_degraded_rdfxml_determinism.py::test_degraded_rdf_xml_is_byte_identical_across_processes` (2) |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSONLD-GRAPH

The normal expanded JSON-LD backend preserves shared RDF list cells instead of compacting them into duplicate lists.

Features: `canonicalize_rdf_graph`, `format.jsonld`.

References: [JSONLD11 §9.2 Node Objects](references/json-ld11.html#node-objects) (normative); [RDF11-CONCEPTS §3.6 Graph Comparison](references/rdf11-concepts.html#section-graph-equality) (normative).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_degraded_collections.py::test_json_ld_is_lossless_for_shared_list_tails` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_degraded_jsonld.py::test_normal_json_ld_path_still_uses_pyoxigraph` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSONLD-FALLBACK

Expanded degraded JSON-LD retains shared cells, references, cycles and literal annotation strings.

Features: `canonicalize_rdf_graph`, `format.jsonld`.

References: [JSONLD11 §9.2 Node Objects](references/json-ld11.html#node-objects) (normative); [JSONLD11 §9.5 Value Objects](references/json-ld11.html#value-objects) (normative); [RDF11-CONCEPTS §3.6 Graph Comparison](references/rdf11-concepts.html#section-graph-equality) (normative).

- local: [`diffable_rdf.expanded_jsonld:serialize_expanded_jsonld`](../../src/diffable_rdf/expanded_jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_preserves_shared_cells_references_and_cycles` (1)<br>`tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_preserves_literal_lexical_strings_and_annotations` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_preserves_nonkeyword_identifiers_with_an_explicit_base` (30) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_is_reproducible_across_processes` (1) |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSONLD-TERM-BOUNDARY

The degraded JSON-LD subset refuses generalized term positions, relative predicate/datatype IRIs and URIRef values resembling blank-node identifiers.

Features: `canonicalize_rdf_graph`, `format.jsonld`.

References: [RDF11-CONCEPTS §3.1 Triples](references/rdf11-concepts.html#section-triples) (normative); [JSONLD11 §9.2 Node Objects](references/json-ld11.html#node-objects) (normative); [JSONLD11 §9.5 Value Objects](references/json-ld11.html#value-objects) (normative).

- boundary: [`diffable_rdf.expanded_jsonld:serialize_expanded_jsonld`](../../src/diffable_rdf/expanded_jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_preserves_literal_lexical_strings_and_annotations` (1) |
| negative | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_rejects_terms_outside_interoperable_subset` (8)<br>`tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_rejects_literal_predicates` (1) |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSONLD-RESERVED

The degraded writer refuses keyword-shaped relative identifiers, while keyword-shaped literal text and non-keyword identifier spellings survive.

Features: `canonicalize_rdf_graph`, `format.jsonld`.

References: [JSONLD11-API §5.2 IRI Expansion](references/json-ld11-api.html#iri-expansion) (normative).

- boundary: [`diffable_rdf.expanded_jsonld:_iri_identifier`](../../src/diffable_rdf/expanded_jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_preserves_keyword_shaped_literal_text` (15) |
| negative | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_rejects_reserved_relative_identifiers` (30) |
| boundary | `tests/serialization/test_degraded_jsonld.py::test_degraded_json_ld_preserves_nonkeyword_identifiers_with_an_explicit_base` (30) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSON-ORDERING

Object keys and application-unordered arrays sort deterministically without mutation; this changes ordinary JSON array order by project policy.

Features: `deterministic_json`.

References: [RFC8259 §4 Objects](references/rfc8259.txt) (normative); [RFC8259 §5 Arrays](references/rfc8259.txt) (normative).

- local: [`diffable_rdf.jsonld:deterministic_json`](../../src/diffable_rdf/jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/integration/test_diffable_rdf.py::test_deterministic_json_sorts_keys_and_lists` (1)<br>`tests/json/test_jsonld_order.py::test_context_free_json_still_sorts_lists_and_does_not_mutate_input` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | `tests/json/test_json_mixed_keys.py::test_parsed_json_rendering_is_idempotent` (1)<br>`tests/integration/test_diffable_rdf.py::test_deterministic_json_is_stable_regardless_of_insertion_order` (1) |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSON-MIXEDKEYS

Mixed Python keys sort by their encoded names, and duplicate encoded names are refused before JSON object information can be lost.

Features: `deterministic_json`.

References: [RFC8259 §4 Objects](references/rfc8259.txt) (normative).

- local: [`diffable_rdf.jsonld:_json_key`](../../src/diffable_rdf/jsonld.py).
- boundary: [`diffable_rdf.jsonld:_sorted_items`](../../src/diffable_rdf/jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/json/test_json_mixed_keys.py::test_mixed_key_dictionary_list_permutations_are_deterministic` (1) |
| negative | `tests/json/test_json_mixed_keys.py::test_encoded_key_collisions_are_refused_not_emitted_twice` (1)<br>`tests/json/test_json_mixed_keys.py::test_two_distinct_nan_keys_are_refused_as_well` (1) |
| boundary | `tests/json/test_json_mixed_keys.py::test_non_string_keys_sort_by_the_name_json_writes_not_by_str` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSON-LISTS

Explicit and locally declared lists retain order, including nested lists, while graph/set arrays may be reordered without changing the checked RDF meaning.

Features: `deterministic_json`.

References: [JSONLD11 §9.7 Lists and Sets](references/json-ld11.html#lists-and-sets) (normative); [JSONLD11 §4.3 Value Ordering](references/json-ld11.html#sets-and-lists) (informative context).

- local: [`diffable_rdf.jsonld:deterministic_json`](../../src/diffable_rdf/jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/json/test_jsonld_order.py::test_context_defined_list_preserves_rdf_meaning` (1)<br>`tests/json/test_jsonld_order.py::test_explicit_list_preserves_rdf_meaning` (1)<br>`tests/json/test_jsonld_unordered_keys.py::test_sorting_an_unordered_container_does_not_change_the_rdf` (2) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/json/test_jsonld_order.py::test_an_array_nested_in_an_ordered_array_keeps_its_order` (2)<br>`tests/json/test_jsonld_unordered_keys.py::test_a_container_list_term_nested_in_a_set_array_keeps_its_order` (1)<br>`tests/json/test_jsonld_unordered_keys.py::test_an_aliased_list_nested_in_a_graph_array_keeps_its_order` (1)<br>`tests/json/test_jsonld_order.py::test_a_dict_inside_an_ordered_array_still_starts_a_sortable_node_object` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSON-CONTEXTS

Local ordering facts respect sequential context overrides, inheritance, null resets and checked forward alias definitions without claiming a full context processor.

Features: `deterministic_json`.

References: [JSONLD11-API §4.1 Context Processing Algorithm](references/json-ld11-api.html#context-processing-algorithm) (normative); [JSONLD11-API §4.2 Create Term Definition](references/json-ld11-api.html#create-term-definition) (normative).

- local: [`diffable_rdf.jsonld:_apply_local_context`](../../src/diffable_rdf/jsonld.py).
- local: [`diffable_rdf.jsonld:_apply_term_definitions`](../../src/diffable_rdf/jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/json/test_jsonld_order.py::test_context_overrides_are_applied_in_order` (1)<br>`tests/json/test_jsonld_order.py::test_local_context_is_inherited_and_null_resets_it` (1)<br>`tests/json/test_jsonld_order.py::test_list_keyword_alias_preserves_rdf_meaning` (2) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/json/test_jsonld_order.py::test_a_term_definition_may_reference_an_alias_declared_after_it` (3)<br>`tests/json/test_jsonld_order.py::test_a_shadowing_definition_in_a_nested_context_array_keeps_its_order` (1)<br>`tests/json/test_jsonld_unordered_keys.py::test_a_context_inside_a_graph_element_is_still_applied` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSON-LITERALS

Explicit and locally recognized JSON literal payload arrays retain their sequence and checked RDF meaning.

Features: `deterministic_json`.

References: [JSONLD11 §9.5 Value Objects](references/json-ld11.html#value-objects) (normative); [RFC8259 §5 Arrays](references/rfc8259.txt) (normative).

- local: [`diffable_rdf.jsonld:deterministic_json`](../../src/diffable_rdf/jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/json/test_jsonld_order.py::test_json_literal_arrays_preserve_rdf_meaning` (4) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/json/test_jsonld_order.py::test_a_term_definition_may_reference_an_alias_declared_after_it[type-json-through-an-alias-declared-later]` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSON-UNKNOWN

Unknown remote, scoped and unsupported local contexts conservatively preserve descendant arrays and never fetch remote contexts.

Features: `deterministic_json`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.jsonld:_apply_local_context`](../../src/diffable_rdf/jsonld.py).
- local: [`diffable_rdf.jsonld:deterministic_json`](../../src/diffable_rdf/jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/json/test_jsonld_order.py::test_scoped_context_fails_safe_for_the_document` (1)<br>`tests/json/test_jsonld_order.py::test_type_scoped_context_fails_safe_and_preserves_rdf_meaning` (1) |
| negative | `tests/json/test_jsonld_order.py::test_remote_context_is_never_loaded_and_fails_safe` (1) |
| boundary | `tests/json/test_jsonld_order.py::test_unsupported_context_directive_fails_safe` (2) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### JSON-OVERRIDES

Custom preserved-key sets replace convenience defaults without disabling keyword-based list protection.

Features: `deterministic_json`.

References: [JSONLD11 §9.7 Lists and Sets](references/json-ld11.html#lists-and-sets) (normative).

- local: [`diffable_rdf.jsonld:deterministic_json`](../../src/diffable_rdf/jsonld.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/json/test_jsonld_unordered_keys.py::test_a_custom_key_set_replaces_the_default_but_not_the_keyword_rules` (1)<br>`tests/contracts/test_public_api_surface.py::test_the_preserved_keys_argument_admits_any_set` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/json/test_jsonld_unordered_keys.py::test_imports_stays_protected_by_default_and_is_droppable` (1)<br>`tests/json/test_json_mixed_keys.py::test_custom_preserved_list_keeps_mixed_key_element_order` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WL-IDENTITY

WL relabelling returns a fresh isomorphic quad list, preserves blank-node cardinality and leaves input quads untouched.

Features: `wl_blank_node_labels`, `wl_relabel_quads`.

References: [RDF11-CONCEPTS §3.6 Graph Comparison](references/rdf11-concepts.html#section-graph-equality) (normative).

- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/wl/test_wl_contracts.py::test_wl_relabel_quads_preserves_the_graph` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/wl/test_wl_contracts.py::test_wl_functions_leave_supported_input_quads_unchanged` (9) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WL-COMPONENTS

Unrelated additions, edits and removals do not advance a disconnected component's default refinement.

Features: `wl_blank_node_labels`, `wl_relabel_quads`, `deterministic_turtle`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/wl/test_wl_components.py::test_default_convergence_isolated_from_disconnected_changes` (3)<br>`tests/wl/test_wl_components.py::test_public_turtle_preserves_a_visible_disconnected_label` (1)<br>`tests/wl/test_wl_contracts.py::test_wl_relabel_quads_is_diff_stable` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/wl/test_wl_components.py::test_shared_blank_subject_object_roles_form_one_component` (1)<br>`tests/wl/test_wl_components.py::test_graph_membership_does_not_join_signature_independent_components` (2) |
| property | `tests/wl/test_wl_components.py::test_component_labels_ignore_input_order_and_blank_node_names` (1) |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WL-TIES

Structurally tied nodes remain injective and collision suffixes follow numeric canonical numbering.

Features: `wl_blank_node_labels`, `wl_relabel_quads`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/wl/test_wl_contracts.py::test_wl_blank_node_labels_are_injective` (1)<br>`tests/wl/test_wl_components.py::test_tied_components_remain_injective` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/wl/test_wl_components.py::test_the_tie_break_follows_the_canonical_numbering` (1)<br>`tests/wl/test_wl_components.py::test_adding_a_blank_node_does_not_relabel_the_tied_ones_before_it` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WL-GRAPHS

Named graphs influence labels; blank graph-name identifiers remain consistent when also used as object terms.

Features: `wl_blank_node_labels`, `wl_relabel_quads`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/wl/test_wl_contracts.py::test_wl_distinguishes_identical_structure_in_different_named_graphs` (1)<br>`tests/wl/test_wl_contracts.py::test_wl_relabel_quads_remaps_blank_node_graph_names` (1) |
| negative | Not applicable: This is a transformation of admitted values, not a syntax parser or a new input-rejection API. |
| boundary | `tests/wl/test_wl_contracts.py::test_wl_labels_graph_name_only_blank_nodes_by_content` (1)<br>`tests/wl/test_wl_contracts.py::test_wl_labels_are_stable_for_default_graph_input` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WL-ITERATIONS

Default refinement reaches component fixpoints, explicit rounds remain synchronous, zero is valid and negative counts are refused.

Features: `wl_blank_node_labels`, `wl_relabel_quads`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/wl/test_wl_contracts.py::test_wl_refines_to_a_fixpoint_by_default` (1)<br>`tests/wl/test_wl_components.py::test_explicit_iterations_still_run_the_requested_global_round_count` (1) |
| negative | `tests/wl/test_wl_components.py::test_a_negative_iteration_count_is_rejected` (3)<br>`tests/wl/test_wl_components.py::test_the_error_names_the_argument_and_the_alternatives` (1) |
| boundary | `tests/wl/test_wl_components.py::test_zero_iterations_is_accepted_and_means_no_refinement` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WL-BOUNDARY

Embedded triple objects are rejected consistently at zero, explicit and default refinement rounds.

Features: `wl_blank_node_labels`, `wl_relabel_quads`.

References: [RDF11-CONCEPTS §3.1 Triples](references/rdf11-concepts.html#section-triples) (normative).

- boundary: [`diffable_rdf.wl:_validate_quad_terms`](../../src/diffable_rdf/wl.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/wl/test_wl_contracts.py::test_wl_functions_leave_supported_input_quads_unchanged` (9) |
| negative | `tests/wl/test_wl_contracts.py::test_wl_functions_reject_embedded_triple_objects` (24) |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WL-DIRECTION

Dependency-supported directional literals remain distinct and retain language and direction fields during WL relabelling.

Features: `wl_blank_node_labels`, `wl_relabel_quads`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/wl/test_wl_contracts.py::test_wl_keeps_direction_tagged_literals_complete_and_distinct` (1) |
| negative | Not applicable: This row covers dependency-constructible directional literals, not a directional-literal parser. |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WORK-TIME

A representative 8400-triple OWL-shaped graph serializes within the tested process time budget.

Features: `deterministic_turtle`.

Project contract; no normative standard algorithm is claimed.

- dependency: [`diffable_rdf.turtle:deterministic_turtle`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/performance/test_canonicalization_budget.py::test_owl_shaped_graph_canonicalizes_within_a_time_budget` (1) |
| negative | Not applicable: A representative workload bound is not an API promise to reject all resource-intensive graphs. |
| boundary | Not applicable: No additional boundary beyond the explicitly listed examples is claimed by this row. |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | `tests/performance/test_canonicalization_budget.py::test_owl_shaped_graph_canonicalizes_within_a_time_budget` (1) |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### WORK-MEMORY

A representative sixteen-round WL workload fits the tested address-space budget where the platform supports limits.

Features: `wl_blank_node_labels`, `wl_relabel_quads`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/performance/test_wl_memory_budget.py::test_wl_signatures_stay_bounded_under_many_iterations` (1) |
| negative | Not applicable: The process resource limit is a test oracle, not a library input-rejection API. |
| boundary | Not applicable: Platforms unable to set the address-space limit explicitly skip this measurement in pytest. |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | `tests/performance/test_wl_memory_budget.py::test_wl_signatures_stay_bounded_under_many_iterations` (1) |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### PREFIX-MAP

Prefix maps invert the selected RDFLib nonempty bindings into independent string dictionaries.

Features: `well_known_prefix_map`.

Project contract; no normative standard algorithm is claimed.

- dependency: [`diffable_rdf.turtle:well_known_prefix_map`](../../src/diffable_rdf/turtle.py).

| Dimension | Collected evidence or applicability |
| --- | --- |
| positive | `tests/contracts/test_prefix_map.py::test_prefix_map_inverts_current_nonempty_bindings` (1)<br>`tests/integration/test_diffable_rdf.py::test_well_known_prefix_map_contains_schema_org` (1) |
| negative | Not applicable: The no-argument snapshot function has no invalid input domain. |
| boundary | `tests/contracts/test_prefix_map.py::test_prefix_map_calls_return_independent_snapshots` (1) |
| property | Not applicable: No independent randomized property is claimed for this row; examples establish only the stated dimensions. |
| subprocess | Not applicable: This row has no process-state-specific obligation; process determinism is mapped separately. |
| end-to-end | Not applicable: This row isolates a contract dimension; executable composed workflows are mapped in API-EXAMPLES. |

### PROFILE-RDFC-PROCESSOR

Standalone RDFC processor conformance, canonical N-Quads bytes and hash selection are outside the wrapper API.

Features: `canonicalize_rdf_graph`.

References: [RDFC10 §2 Conformance](references/rdf-canon.html#conformance) (normative); [RDFC10 §A A Canonical form of N-Quads](references/rdf-canon.html#canonical-quads) (normative); [RDFC10 §3.1 Terms defined by this specification](references/rdf-canon.html#canon-terms) (normative).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

Outside this API profile: The wrapper supplies one graph to the dependency and reserializes it; it has no selectable hash algorithm or canonical-byte-output contract.

### PROFILE-RDFC-LIMITS

Configurable RDFC resource-limit reporting is not exposed by the graph serializer API.

Features: `canonicalize_rdf_graph`.

References: [RDFC10 §2 Conformance](references/rdf-canon.html#conformance) (normative).

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

Outside this API profile: Representative workload tests do not expose or establish a standalone processor resource-limit interface.

### PROFILE-JSONLD-PROCESSOR

Full JSON-LD expansion, compaction, remote loading and processing-algorithm conformance are outside the ordering helper.

Features: `deterministic_json`, `canonicalize_rdf_graph`.

References: [JSONLD11-API §3 Conformance](references/json-ld11-api.html#conformance) (normative).

- local: [`diffable_rdf.jsonld:deterministic_json`](../../src/diffable_rdf/jsonld.py).
- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

Outside this API profile: The public functions order a JSON tree or serialize an RDF graph; neither is a general JSON-LD processor.

### PROFILE-N3-LOGIC

Notation3 formulas, implications and variable-based logic are outside the supported N3 graph subset.

Features: `canonicalize_rdf_graph`, `format.n3`.

Project contract; no normative standard algorithm is claimed.

- dependency: [`diffable_rdf.canonicalize:canonicalize_rdf_graph`](../../src/diffable_rdf/canonicalize.py).

Outside this API profile: The N3 alias accepts the same single RDF graph as the other serializers and does not provide a logic input model.

### PROFILE-RDF12

Complete RDF 1.2 or embedded-triple conformance is outside the accepted WL term extension.

Features: `wl_blank_node_labels`, `wl_relabel_quads`.

Project contract; no normative standard algorithm is claimed.

- local: [`diffable_rdf.wl:wl_blank_node_labels`](../../src/diffable_rdf/wl.py).
- local: [`diffable_rdf.wl:wl_relabel_quads`](../../src/diffable_rdf/wl.py).

Outside this API profile: Dependency-supported literal direction is retained, but embedded triples are rejected and no complete RDF 1.2 profile is claimed.
