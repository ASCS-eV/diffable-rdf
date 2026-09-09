"""Every advertised format works on the degraded path, and two spellings agree.

A graph pyoxigraph cannot parse takes the rdflib fallback. Three things used to
go wrong there and are pinned here.

Aliases: this library accepts names rdflib has no plugin for -- ``n-triples``,
``n-quads``, ``rdf/xml`` -- and rdflib's lookup is exact, so those raised
``PluginException`` while their own synonyms worked.

TriG: rdflib's TrigSerializer needs a context-aware store, which a
canonicalized graph is not. It now renders as collection-free Turtle, which is
valid TriG because Turtle is a subset of it -- the same argument the module
already makes for N3. That matters for correctness, not just for the error:
TrigSerializer inherits Turtle's ``( … )`` rendering, and this path has no
round-trip guard to catch a detached list.

N-Quads: rdflib's serializer needs a context-aware container, so the triples go
into a Dataset's default graph -- which invents no graph name the input did not
have, and matches what the pyoxigraph path writes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from urllib.parse import urljoin

import pytest
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.compare import isomorphic

from diffable_rdf import canonicalize_rdf_graph

EX = Namespace("http://example.org/")
BASE = "https://base.example/root/"

# Every name the library advertises, so a gap cannot hide behind a synonym.
ALL_ALIASES = [
    "turtle", "ttl",
    "nt", "ntriples", "n-triples", "nt11",
    "nquads", "n-quads",
    "xml", "rdf/xml",
    "trig",
    "n3",
    "json-ld", "jsonld", "application/ld+json",
]

# Groups that name one format and must therefore agree byte for byte.
SYNONYM_GROUPS = [
    ("turtle", "ttl"),
    ("nt", "ntriples", "n-triples", "nt11"),
    ("nquads", "n-quads"),
    ("xml", "rdf/xml"),
    ("json-ld", "jsonld", "application/ld+json"),
]

RDFLIB_PARSER_NAME = {
    "ttl": "turtle", "ntriples": "nt", "n-triples": "nt", "nt11": "nt",
    "n-quads": "nquads", "rdf/xml": "xml", "jsonld": "json-ld",
    "application/ld+json": "json-ld",
}


def _degraded_graph() -> Graph:
    """A relative IRI forces the fallback; the shared list tail makes it risky.

    Two list heads share one tail cell, which is exactly what compact ``( … )``
    syntax cannot express -- so this graph is the reason TriG has to render
    without it.
    """
    graph = Graph()
    graph.bind("ex", EX)
    tail = BNode()
    head = BNode()
    graph.add((tail, RDF.first, Literal("shared")))
    graph.add((tail, RDF.rest, RDF.nil))
    graph.add((head, RDF.first, Literal("head")))
    graph.add((head, RDF.rest, tail))
    graph.add((EX.a, EX.items, head))
    graph.add((EX.b, EX.items, tail))
    graph.add((URIRef("relative/thing"), EX.p, Literal("forces fallback")))
    return graph


def _resolved(graph: Graph) -> Graph:
    """Resolve relative IRIs the way a consumer parsing with a base would."""
    resolved = Graph()

    def resolve(term: object) -> object:
        if isinstance(term, URIRef) and "://" not in str(term):
            return URIRef(urljoin(BASE, str(term)))
        return term

    for subject, predicate, obj in graph:
        resolved.add((resolve(subject), predicate, resolve(obj)))
    return resolved


@pytest.mark.parametrize("output_format", ALL_ALIASES)
def test_every_advertised_alias_serializes_on_the_degraded_path(output_format: str) -> None:
    """No advertised name may raise here; three of them used to."""
    result = canonicalize_rdf_graph(_degraded_graph(), output_format=output_format)
    assert result.strip(), f"{output_format} returned empty output"


@pytest.mark.parametrize("group", SYNONYM_GROUPS, ids=[g[0] for g in SYNONYM_GROUPS])
def test_synonyms_for_one_format_produce_identical_bytes(group: tuple[str, ...]) -> None:
    """The actual defect: two names for one format behaving differently."""
    graph = _degraded_graph()
    outputs = {name: canonicalize_rdf_graph(graph, output_format=name) for name in group}
    first = outputs[group[0]]
    for name, result in outputs.items():
        assert result == first, f"{name} disagrees with {group[0]} on the degraded path"


# Formats that can express this graph. N-Triples and N-Quads cannot: they
# require absolute IRIs, and a graph only reaches the degraded path because it
# holds something -- a relative IRI, a generalized term -- that N-Triples
# cannot represent, which is how it failed pyoxigraph's parse in the first
# place. Their degraded output is deterministic but not reparseable by a strict
# parser, which is a pre-existing limitation of the format rather than of this
# change; see the line-ordering and synonym tests below for what they do
# guarantee.
REPARSEABLE_ALIASES = [
    "turtle", "ttl", "xml", "rdf/xml", "trig", "n3",
    "json-ld", "jsonld", "application/ld+json",
]


@pytest.mark.parametrize("output_format", REPARSEABLE_ALIASES)
def test_degraded_output_preserves_the_graph(output_format: str) -> None:
    """Working is not enough; the output has to still say what went in."""
    graph = _degraded_graph()
    result = canonicalize_rdf_graph(graph, output_format=output_format)
    parser = RDFLIB_PARSER_NAME.get(output_format, output_format)
    reparsed = Graph().parse(data=result, format=parser, publicID=BASE)

    assert isomorphic(reparsed, _resolved(graph)), f"{output_format} did not preserve the graph"


@pytest.mark.parametrize("output_format", ["nt", "ntriples", "n-triples", "nt11", "nquads", "n-quads"])
def test_degraded_line_oriented_output_contains_every_statement(output_format: str) -> None:
    """What the line-oriented formats can promise here: nothing is dropped.

    They cannot promise a clean reparse, because the very thing that sent this
    graph down the degraded path -- a relative IRI -- is not expressible in
    N-Triples or N-Quads. So count statements instead of round-tripping, and
    check the terms are present verbatim.
    """
    result = canonicalize_rdf_graph(_degraded_graph(), output_format=output_format)
    lines = [line for line in result.splitlines() if line.strip()]

    assert len(lines) == len(_degraded_graph())
    assert "<relative/thing>" in result, "the relative IRI must be passed through verbatim"
    assert '"forces fallback"' in result
    assert '"shared"' in result and '"head"' in result


def test_degraded_trig_states_list_structure_explicitly() -> None:
    """TriG inherits Turtle's ``( … )``, which cannot express a shared tail.

    The empty collection ``()`` is exempt: it is Turtle shorthand for the
    single IRI ``rdf:nil``, not a list structure, so it loses nothing.
    """
    result = canonicalize_rdf_graph(_degraded_graph(), output_format="trig")

    assert result.count("(") == result.count("()"), (
        "degraded TriG used collection syntax for something other than rdf:nil:\n" + result
    )
    # Both heads must still reach the same tail, stated with rdf:first/rdf:rest.
    reparsed = Graph().parse(data=result, format="trig", publicID=BASE)
    assert len(list(reparsed.triples((None, RDF.first, None)))) == 2
    assert len(list(reparsed.triples((None, RDF.rest, None)))) == 2
    shared = reparsed.value(reparsed.value(EX.a, EX.items), RDF.rest)
    assert shared is not None
    assert shared == reparsed.value(EX.b, EX.items), "the shared tail was detached"


def test_degraded_nquads_states_exactly_what_ntriples_states() -> None:
    """A single Graph has no graph names, so none may appear in the output.

    The N-Quads graph label is optional, so an N-Triples document is already a
    valid N-Quads document in the default graph -- which makes byte equality
    the right assertion, and keeps the output independent of how a given rdflib
    spells a Dataset's default graph.
    """
    graph = _degraded_graph()
    quads = canonicalize_rdf_graph(graph, output_format="nquads")
    triples = canonicalize_rdf_graph(graph, output_format="nt")

    assert quads == triples
    assert quads.endswith("\n")
    # No graph term of any spelling, including the one rdflib 6.3.2 writes for
    # a Dataset's default graph.
    assert "urn:x-rdflib:default" not in quads


def test_degraded_nquads_lines_are_sorted() -> None:
    """N-Quads is line-oriented, which is what makes its output stable."""
    result = canonicalize_rdf_graph(_degraded_graph(), output_format="nquads")
    lines = [line for line in result.splitlines() if line.strip()]
    assert lines == sorted(lines)


@pytest.mark.parametrize("output_format", ["trig", "nquads", "n-quads", "n-triples"])
def test_newly_working_degraded_formats_are_stable_across_processes(output_format: str) -> None:
    """The formats this change enables must be as reproducible as the rest."""
    script = textwrap.dedent(
        """
        import sys
        from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
        from diffable_rdf import canonicalize_rdf_graph
        EX = Namespace("http://example.org/")
        graph = Graph()
        graph.bind("ex", EX)
        tail, head = BNode(f"t{sys.argv[2]}"), BNode(f"h{sys.argv[2]}")
        graph.add((tail, RDF.first, Literal("shared")))
        graph.add((tail, RDF.rest, RDF.nil))
        graph.add((head, RDF.first, Literal("head")))
        graph.add((head, RDF.rest, tail))
        graph.add((EX.a, EX.items, head))
        graph.add((EX.b, EX.items, tail))
        graph.add((URIRef("relative/thing"), EX.p, Literal("forces fallback")))
        sys.stdout.write(canonicalize_rdf_graph(graph, output_format=sys.argv[1]))
        """
    )
    outputs = {
        subprocess.run(
            [sys.executable, "-c", script, output_format, str(seed)],
            capture_output=True, text=True, check=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        ).stdout
        for seed in (1, 7, 23, 101)
    }
    assert len(outputs) == 1, f"degraded {output_format} is not reproducible across processes"


def test_an_unregistered_name_still_reaches_rdflib_on_the_degraded_path() -> None:
    """Alias translation must not swallow rdflib's own unknown-format error."""
    from rdflib.plugin import PluginException

    with pytest.raises(PluginException):
        canonicalize_rdf_graph(_degraded_graph(), output_format="no-such-format")


def test_degraded_json_ld_is_untouched_by_the_alias_change() -> None:
    """JSON-LD has its own writer; it must not be routed through the plugin table."""
    result = canonicalize_rdf_graph(_degraded_graph(), output_format="json-ld")
    document = json.loads(result)

    assert isinstance(document, list)
    assert "@list" not in result
