# Test strategy

The suite is organized by the contract or execution dimension it verifies.
Every test belongs to one group so related behavior is discoverable without
coupling independent concerns.

| Group | Responsibility | Primary dimensions |
| --- | --- | --- |
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
PYTHONPATH=src uv run --frozen pytest -q --cov=diffable_rdf --cov-report=term-missing --cov-fail-under=95
```

Source-tree execution imports `src/diffable_rdf` directly and validates the
working files. Distribution verification requires imports in the test process
and every child process to resolve to the installed package. Source and
distribution origins must be checked separately; distribution verification uses
a built wheel or source archive in an environment without the source package.

Run focused groups with standard pytest selection, for example:

```bash
PYTHONPATH=src uv run --frozen pytest -q tests/serialization tests/wl
```
