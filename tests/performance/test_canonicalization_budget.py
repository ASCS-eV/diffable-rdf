"""Resource bounds for representative canonicalization workloads."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_owl_shaped_graph_canonicalizes_within_a_time_budget() -> None:
    """An OWL-shaped graph with 8,400 triples canonicalizes within 30 seconds."""
    script = textwrap.dedent(
        """
        from rdflib import BNode, Graph, Literal, Namespace
        from rdflib.namespace import OWL, RDF, RDFS
        from diffable_rdf import deterministic_turtle

        EX = Namespace("http://example.org/")
        graph = Graph()
        for index in range(600):
            cls = EX[f"C{index}"]
            graph.add((cls, RDF.type, OWL.Class))
            graph.add((cls, RDFS.label, Literal(f"Class {index}", lang="en")))
            for property_index in range(3):
                restriction = BNode()
                graph.add((cls, RDFS.subClassOf, restriction))
                graph.add((restriction, RDF.type, OWL.Restriction))
                graph.add((restriction, OWL.onProperty, EX[f"p{property_index}"]))
                graph.add((restriction, OWL.someValuesFrom, EX[f"C{(index + property_index + 1) % 600}"]))
        assert len(graph) == 8400, len(graph)
        deterministic_turtle(graph)
        print("ok")
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stderr[-500:]
    assert result.stdout.strip() == "ok"
