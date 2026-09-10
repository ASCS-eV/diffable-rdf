"""Tripwires for the dependency defects this library works around.

Each test asserts that a *dependency* still misbehaves, using only that
dependency's own API and none of this library's code. They pass while a
workaround is still needed, and fail the moment upstream fixes the defect —
which is the signal to delete the workaround rather than carry it forever.

**A failure here is good news.** It does not mean this library is broken; it
means a local workaround has become dead code. Each failure message names the
workaround to remove.

Both defects were reproduced on the declared floors (rdflib 6.3.2,
pyoxigraph 0.5.4) and on the newest releases at the time of writing
(rdflib 7.6.0, which is the latest, and pyoxigraph 0.5.11), so neither test is
merely pinning an old version.
"""

from __future__ import annotations

import io

import pyoxigraph as ox
import rdflib
from rdflib import BNode, Graph, Literal, Namespace, RDF
from rdflib.compare import isomorphic

EX = Namespace("http://example.org/")

# A literal CR expressed as an N-Triples escape, so the parser decodes it to a
# real carriage return in the term rather than rejecting a raw line break.
CR_NTRIPLES = '<http://example.org/s> <http://example.org/p> "a\\rb" .\n'


def _shared_tail_graph() -> Graph:
    """Two rdf:List heads sharing one tail cell, in standard RDF throughout.

    Only absolute IRIs and standard terms: the defect does not need generalized
    RDF or anything else exotic to appear.
    """
    graph = Graph()
    tail = BNode()
    head = BNode()
    graph.add((tail, RDF.first, Literal("shared")))
    graph.add((tail, RDF.rest, RDF.nil))
    graph.add((head, RDF.first, Literal("head")))
    graph.add((head, RDF.rest, tail))
    graph.add((EX.a, EX.items, head))
    graph.add((EX.b, EX.items, tail))
    return graph


def test_rdflib_jsonld_serializer_still_duplicates_a_shared_list_tail() -> None:
    """rdflib's JSON-LD serializer compacts a shared tail into two @list values.

    Six triples in, eight out, and the result is not isomorphic to the input:
    ``Converter.to_collection`` turns a list into ``@list`` without checking
    whether anything else references its cells.
    """
    graph = _shared_tail_graph()
    serialized = graph.serialize(format="json-ld")
    reparsed = Graph().parse(data=serialized, format="json-ld")

    assert not isomorphic(graph, reparsed), (
        f"rdflib {rdflib.__version__} now preserves shared rdf:List tails through its "
        "JSON-LD serializer (reported as RDFLib/rdflib#3542, fix proposed in #3543). "
        "src/diffable_rdf/expanded_jsonld.py no longer needs to avoid that defect, so "
        "re-examine what remains of its rationale -- deterministic key order and the "
        "refusal of terms the interoperable subset cannot carry are requirements of "
        "this library, not workarounds, so switching to rdflib's serializer would give "
        "up both. Delete this tripwire either way. "
        f"(input {len(graph)} triples, round-tripped {len(reparsed)})"
    )
    # Pin the shape of the defect too, so a *different* future breakage does not
    # keep this tripwire green by accident.
    assert len(reparsed) > len(graph), "expected duplication, not loss"
    assert "@list" in serialized


def test_pyoxigraph_rdf_xml_still_writes_a_literal_carriage_return_raw() -> None:
    """pyoxigraph emits a literal CR unescaped, so XML parsers normalize it away.

    XML 1.0 §2.11 requires a processor to translate a lone ``#xD`` to ``#xA``
    before parsing, so a raw CR in the serialized document is silent data loss;
    a character reference would survive. quick-xml fixed this in 0.42.0 (its
    #990 escapes ``\\r`` in text content as ``&#13;``), and oxigraph's ``main``
    vendors 0.42.0 while released 0.5.9 and 0.5.11 both vendor 0.37.5 — so this
    should start failing after the next pyoxigraph release.
    """
    quads = ox.parse(io.BytesIO(CR_NTRIPLES.encode("utf-8")), format=ox.RdfFormat.N_TRIPLES)
    serialized = ox.serialize(quads, format=ox.RdfFormat.RDF_XML).decode("utf-8")

    assert "\r" in serialized, (
        f"pyoxigraph {ox.__version__} now escapes a literal carriage return in RDF/XML "
        "instead of writing it raw. The `.replace(chr(13), '&#xD;')` in "
        "_finalize_rdf_xml (src/diffable_rdf/canonicalize.py) is therefore redundant on "
        "the pyoxigraph path -- it already is on the degraded path, where rdflib writes "
        "`&#13;` itself. Retire the replacement, keep the XML 1.0 representability "
        "check and the round-trip verification, and delete this tripwire."
    )
    # And confirm the consequence, which is what actually matters: an XML parser
    # turns that raw CR into LF, changing the literal.
    value = str(next(iter(Graph().parse(data=serialized, format="xml")))[2])
    assert value == "a\nb", (
        "the raw CR no longer survives as LF through an XML parser; re-check what "
        "pyoxigraph writes before trusting the workaround's rationale"
    )
