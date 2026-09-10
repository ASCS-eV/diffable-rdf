"""Address-space bound for iterative Weisfeiler-Lehman refinement."""

from __future__ import annotations

import textwrap

import pytest


def test_wl_signatures_stay_bounded_under_many_iterations(python_runner) -> None:
    """Sixteen refinement iterations stay within the supported memory budget."""
    script = textwrap.dedent(
        """
        import sys

        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024 * 1024,) * 2)
        except (ImportError, ValueError, OSError):
            sys.exit(77)

        import pyoxigraph as ox
        from rdflib import BNode, Graph, Namespace
        from diffable_rdf import wl_blank_node_labels

        EX = Namespace("http://example.org/")
        graph = Graph()
        for index in range(20):
            previous = BNode()
            graph.add((EX[f"C{index}"], EX.subClassOf, previous))
            for depth in range(4):
                node = BNode()
                graph.add((previous, EX.intersectionOf, node))
                graph.add((node, EX.onProperty, EX[f"prop{depth}"]))
                previous = node

        dataset = ox.Dataset(ox.parse(graph.serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES))
        dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
        wl_blank_node_labels(list(dataset), iterations=16)
        print("ok")
        """
    )
    result = python_runner(script, capture_output=True, text=True, timeout=300)

    if result.returncode == 77:
        pytest.skip("this platform cannot cap a process address space")
    assert result.returncode == 0, f"WL refinement exceeded the memory budget: {result.stderr[-500:]}"
    assert result.stdout.strip() == "ok"
