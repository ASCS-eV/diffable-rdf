"""Every advertised format works on the degraded path, and two spellings agree.

A graph pyoxigraph cannot parse takes the rdflib fallback. These tests define
the format aliases and syntax accepted by that path.

Aliases: this library accepts names RDFLib does not register as plugins --
``n-triples``, ``n-quads``, and ``rdf/xml``. Exact plugin lookup maps each
alias to its serializer name.

TriG: a canonicalized graph renders through collection-free Turtle, which is
valid TriG because Turtle is a subset of it. Explicit RDF list triples retain
shared cells on this fallback path.

N-Quads: emitted as N-Triples, since the N-Quads graph label is optional and a
single graph has no graph name -- so an N-Triples document is already a valid
N-Quads document in the default graph.

The line-oriented formats then turn out not to be able to carry a degraded
graph at all: N-Triples and N-Quads accept only absolute IRIs (N-Triples 1.1
section 2.2), and a graph reaches this path precisely because it holds
something -- a relative IRI, a generalized term -- that N-Triples cannot
express. They refuse with an actionable error rather than writing a file no
parser will read; the Turtle family, RDF/XML and JSON-LD carry it fine.
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


LINE_ORIENTED_ALIASES = ["nt", "ntriples", "n-triples", "nt11", "nquads", "n-quads"]
CARRYING_ALIASES = [a for a in ALL_ALIASES if a not in LINE_ORIENTED_ALIASES]


@pytest.mark.parametrize("output_format", CARRYING_ALIASES)
def test_every_alias_that_can_carry_a_degraded_graph_does(output_format: str) -> None:
    """Each advertised carrying alias emits a non-empty document."""
    result = canonicalize_rdf_graph(_degraded_graph(), output_format=output_format)
    assert result.strip(), f"{output_format} returned empty output"


@pytest.mark.parametrize("output_format", LINE_ORIENTED_ALIASES)
def test_line_oriented_aliases_refuse_a_graph_they_cannot_represent(
    output_format: str,
) -> None:
    """Refusing beats writing a file no parser will read.

    rdflib's N-Triples serializer reuses Turtle's term rendering and does not
    enforce the absolute-IRI rule, so it emits a relative IRI that its own
    parser then rejects. The error has to say which term and what to use
    instead.
    """
    with pytest.raises(ValueError) as raised:
        canonicalize_rdf_graph(_degraded_graph(), output_format=output_format)

    message = str(raised.value)
    assert output_format in message
    assert "relative/thing" in message, "the offending term must be named"
    assert "absolute IRI" in message
    assert "turtle" in message, "an alternative that works must be named"


CARRYING_SYNONYM_GROUPS = [g for g in SYNONYM_GROUPS if g[0] not in LINE_ORIENTED_ALIASES]
LINE_ORIENTED_SYNONYM_GROUPS = [g for g in SYNONYM_GROUPS if g[0] in LINE_ORIENTED_ALIASES]


@pytest.mark.parametrize(
    "group", CARRYING_SYNONYM_GROUPS, ids=[g[0] for g in CARRYING_SYNONYM_GROUPS]
)
def test_synonyms_for_one_format_produce_identical_bytes(group: tuple[str, ...]) -> None:
    """Synonyms for one format produce identical bytes."""
    graph = _degraded_graph()
    outputs = {name: canonicalize_rdf_graph(graph, output_format=name) for name in group}
    first = outputs[group[0]]
    for name, result in outputs.items():
        assert result == first, f"{name} disagrees with {group[0]} on the degraded path"


@pytest.mark.parametrize(
    "group", LINE_ORIENTED_SYNONYM_GROUPS, ids=[g[0] for g in LINE_ORIENTED_SYNONYM_GROUPS]
)
def test_synonyms_refuse_for_the_same_reason(group: tuple[str, ...]) -> None:
    """Agreeing on the refusal is the same contract as agreeing on the bytes."""
    graph = _degraded_graph()
    reasons = []
    for name in group:
        with pytest.raises(ValueError) as raised:
            canonicalize_rdf_graph(graph, output_format=name)
        message = str(raised.value)
        assert message.startswith(f"{name} cannot represent"), message
        # Compare what follows the format name, so "nt" inside "ntriples" is
        # not mangled by a blind replace.
        reasons.append(message.split(" cannot represent", 1)[1])
    assert len(set(reasons)) == 1, f"{group} disagree on why they refuse"


# Formats that can express this graph. N-Triples and N-Quads require absolute
# IRIs, while the fixture includes a relative IRI and RDF list triples. The
# line-oriented tests verify their explicit refusal and stable aliases.
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


def test_line_oriented_output_still_works_when_the_graph_is_representable() -> None:
    """The refusal is about the terms, not about the format or the path.

    A graph of absolute IRIs does not reach the degraded path at all, so this
    also pins that the guard has not disturbed the normal path: N-Quads and
    N-Triples agree byte for byte there, because the N-Quads graph label is
    optional and a single graph has no graph name to write.
    """
    graph = Graph()
    graph.bind("ex", EX)
    graph.add((EX.s, EX.p, Literal("v")))

    quads = canonicalize_rdf_graph(graph, output_format="nquads")
    triples = canonicalize_rdf_graph(graph, output_format="nt")

    assert quads == triples
    assert "urn:x-rdflib:default" not in quads
    assert quads.endswith("\n")


def test_the_refusal_names_the_position_of_the_offending_term() -> None:
    """A relative IRI can sit in any position; the message must say which."""
    for position, triple in (
        ("subject", (URIRef("relative/s"), EX.p, Literal("v"))),
        ("object", (EX.s, EX.p, URIRef("relative/o"))),
        ("predicate", (EX.s, URIRef("relative/p"), Literal("v"))),
    ):
        graph = Graph()
        graph.add(triple)
        with pytest.raises(ValueError) as raised:
            canonicalize_rdf_graph(graph, output_format="nt")
        assert position in str(raised.value), f"expected {position} in the message"


@pytest.mark.parametrize("output_format", ["turtle", "trig", "n3", "json-ld"])
def test_degraded_formats_that_carry_the_graph_are_stable_across_processes(
    output_format: str,
) -> None:
    """The stable carrying formats produce identical process output."""
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


def test_degraded_json_ld_uses_its_expanded_writer() -> None:
    """Degraded JSON-LD uses the expanded JSON-LD writer."""
    result = canonicalize_rdf_graph(_degraded_graph(), output_format="json-ld")
    document = json.loads(result)

    assert isinstance(document, list)
    assert "@list" not in result


@pytest.mark.parametrize(
    "iri",
    [
        pytest.param("http://ex/%zz", id="bad-percent-escape"),
        pytest.param("http://ex/a#b#c", id="two-fragments"),
        pytest.param("http://ex/a[1]", id="brackets-outside-a-host"),
    ],
)
def test_the_refusal_covers_an_iri_that_is_absolute_but_not_valid(iri: str) -> None:
    """Having a scheme is not the same as being an IRI.

    N-Triples 1.1 §2.2 admits only valid IRIs. Pyoxigraph validates the full
    grammar rather than only the leading scheme.
    """
    graph = Graph()
    graph.add((URIRef(iri), EX.p, Literal("v")))

    with pytest.raises(ValueError) as raised:
        canonicalize_rdf_graph(graph, output_format="nt")

    message = str(raised.value)
    assert "subject" in message
    assert "absolute IRI" in message
    assert iri in message, "the offending term must be named"
