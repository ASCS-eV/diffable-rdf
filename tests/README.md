# Test strategy

The suite is organized by the contract or execution dimension it verifies.
Every test belongs to one group so related behavior is discoverable without
coupling independent concerns.

| Group | Responsibility | Primary dimensions |
| --- | --- | --- |
| `harness/` | Test-target selection and child-process isolation | source and wheel provenance, interpreter configuration |
| `contracts/` | Public API, accepted graph inputs, format names, and output framing | exports, annotations, input coercion, format guarantees |
| `serialization/` | RDF document fidelity and serializer fallbacks | bases, namespaces, literals, XML, list identity, process determinism |
| `properties/` | Seeded graph invariants | losslessness, idempotence, label independence, insertion-order independence |
| `json/` | Deterministic JSON and JSON-LD semantics | key ordering, mixed key types, list-order preservation |
| `wl/` | Weisfeiler-Lehman labels and relabelled quads | graph isomorphism, named graphs, collision handling, fixpoints |
| `dependencies/` | Direct dependency serializer capabilities | shared RDF lists, XML carriage returns |
| `integration/` | End-to-end public workflows | package entry points and complete documents |
| `performance/` | Bounded process-resource workloads | canonicalization time and WL address space |

Fixed seeds in `properties/` create semantic graph variations with stable
nodeids. Tests use RDFLib and pyoxigraph readers as independent parsing and
canonicalization oracles where their respective format semantics apply.
Process tests start a fresh interpreter to include hash state and generated
blank-node labels in the execution dimension.

Run the source tree suite with:

```bash
uv sync --locked --group dev
uv run --frozen pytest -q --package-under-test=source --cov=diffable_rdf --cov-report=term-missing --cov-fail-under=95
```

`--package-under-test=source` imports this checkout's `src/diffable_rdf`.
`--package-under-test=installed` requires a non-editable installed wheel and
verifies that pytest and every child interpreter use its recorded package file.
Child interpreters run from a temporary directory with user site packages
disabled; their selected hash seed is retained.

From a neutral directory outside the checkout, run the installed-wheel suite
with that wheel environment's Python:

```bash
/path/to/wheel-env/bin/python -I -m pytest -q --package-under-test=installed \
  -c /path/to/diffable-rdf/pyproject.toml /path/to/diffable-rdf/tests
```

Run focused groups with standard pytest selection, for example:

```bash
uv run --frozen pytest -q --package-under-test=source tests/serialization tests/wl
```
