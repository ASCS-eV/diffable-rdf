"""Namespace-to-prefix mappings are independent snapshots of RDFLib bindings."""

from rdflib import Graph

from diffable_rdf import well_known_prefix_map


def test_prefix_map_inverts_current_nonempty_bindings() -> None:
    expected = {str(namespace): prefix for prefix, namespace in Graph().namespaces() if prefix}

    mapping = well_known_prefix_map()

    assert mapping == expected
    assert all(
        isinstance(namespace, str) and isinstance(prefix, str) and prefix for namespace, prefix in mapping.items()
    )


def test_prefix_map_calls_return_independent_snapshots() -> None:
    first = well_known_prefix_map()
    second = well_known_prefix_map()

    assert first == second
    assert first is not second
    first.clear()
    first["urn:caller:namespace"] = "caller"

    assert second
    assert "urn:caller:namespace" not in second
    assert well_known_prefix_map() == second
