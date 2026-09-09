"""The scope of the deterministic-output guarantee.

``canonicalize_rdf_graph`` maps a fixed set of format names itself and
serializes those through pyoxigraph; anything else is handed to rdflib's
serializer plugins. Only the first group can be guaranteed: several rdflib
serializers choose their layout by walking the graph, and that walk depends on
set iteration order, which varies between processes. Canonicalizing blank-node
labels does not constrain it.

These tests pin both halves of that contract — the guarantee where it is
offered, and the warning where it is not.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import textwrap

import pytest
from rdflib import BNode, Graph, Literal, Namespace

from diffable_rdf import canonicalize_rdf_graph
from diffable_rdf.canonicalize import _FORMAT_MAP

EX = Namespace("http://example.org/")

# Hash seeds, not repeat count: rdflib's traversal order follows set iteration,
# which is stable within one process however many times it is called.
HASH_SEEDS = (0, 1, 2, 3, 5, 8)

# Shared list cells with two references into the chain. A serializer that
# decides what to nest by traversal has several defensible answers here, which
# is what makes the instability visible at all.
BUILD_GRAPH = """
from rdflib import BNode, Graph, Literal, Namespace, RDF
EX = Namespace("http://example.org/")
graph = Graph()
graph.bind("ex", EX)
cells = [BNode() for _ in range(6)]
for index, cell in enumerate(cells):
    graph.add((cell, RDF.first, Literal(f"v{index}")))
    graph.add((cell, RDF.rest, cells[index + 1] if index + 1 < len(cells) else RDF.nil))
graph.add((EX.first, EX.items, cells[0]))
graph.add((EX.second, EX.items, cells[3]))
"""


def _outputs_across_processes(output_format: str) -> set[str]:
    """Serialize the same graph in fresh interpreters, one per hash seed."""
    # BUILD_GRAPH is already unindented, so dedent the appended block on its
    # own -- dedenting the concatenation finds no common prefix and leaves the
    # second half indented.
    script = BUILD_GRAPH + textwrap.dedent(
        """
        import sys
        from diffable_rdf import canonicalize_rdf_graph
        sys.stdout.write(canonicalize_rdf_graph(graph, output_format=sys.argv[1]))
        """
    )
    results = set()
    for seed in HASH_SEEDS:
        completed = subprocess.run(
            [sys.executable, "-c", script, output_format],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        )
        results.add(completed.stdout)
    return results


@pytest.mark.parametrize("output_format", sorted(_FORMAT_MAP))
def test_every_mapped_format_is_byte_identical_across_processes(output_format: str) -> None:
    """The guarantee, for every name the library maps itself.

    Parametrized over ``_FORMAT_MAP`` rather than a hand-written list, so a
    format added later inherits the requirement instead of quietly escaping it.
    """
    outputs = _outputs_across_processes(output_format)
    assert len(outputs) == 1, (
        f"{output_format} is mapped by this library and must be byte-identical across "
        f"processes, but produced {len(outputs)} distinct outputs"
    )


def test_mapped_formats_cover_every_name_the_docstring_promises() -> None:
    """The docstring lists the guaranteed names; drift between the two is the bug."""
    promised = {
        "turtle", "ttl",
        "nt", "ntriples", "n-triples", "nt11",
        "nquads", "n-quads",
        "xml", "rdf/xml",
        "trig",
        "n3",
        "json-ld", "jsonld", "application/ld+json",
    }
    assert set(_FORMAT_MAP) == promised


def test_delegating_to_an_rdflib_plugin_warns_that_the_guarantee_does_not_apply(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A caller who gives up the guarantee must be told so, not left to assume it."""
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("v")))

    with caplog.at_level(logging.WARNING, logger="diffable_rdf.canonicalize"):
        canonicalize_rdf_graph(graph, output_format="longturtle")

    assert caplog.records, "delegating to an rdflib plugin must log a warning"
    message = caplog.records[0].getMessage()
    assert "longturtle" in message
    # The point of the warning is the consequence, not merely the delegation.
    assert "not guaranteed" in message
    assert "deterministic" in message.lower()


def test_an_unregistered_format_name_still_surfaces_rdflibs_own_error() -> None:
    """Distinguish our errors from a dependency's: this one is rdflib's to raise."""
    from rdflib.plugin import PluginException

    graph = Graph()
    graph.add((EX.s, EX.p, Literal("v")))

    with pytest.raises(PluginException):
        canonicalize_rdf_graph(graph, output_format="no-such-format")


def test_a_delegated_format_still_gets_canonical_blank_node_labels() -> None:
    """Delegation gives up layout stability, not blank-node canonicalization.

    ``longturtle`` is deterministic here, so it can pin what the fallback still
    does for a delegated format: labels come from RDFC-1.0 canonicalization
    rather than from rdflib's run-local counter.
    """
    graph = Graph()
    graph.bind("ex", EX)
    node = BNode("run-local-name")
    graph.add((EX.s, EX.p, node))
    graph.add((node, EX.q, Literal("v")))

    result = canonicalize_rdf_graph(graph, output_format="longturtle")

    assert "run-local-name" not in result
    # rdflib registers a longturtle *serializer* but no longturtle parser; the
    # output is Turtle syntax, so read it back with the Turtle parser.
    assert len(Graph().parse(data=result, format="turtle")) == len(graph)
