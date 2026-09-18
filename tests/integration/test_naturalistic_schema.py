"""End-to-end checks on a complete, naturalistic generated-schema document.

The seeded graphs in ``properties/`` cover the shapes that break canonicalization
one at a time. This module covers the other risk: a whole document of the kind a
schema generator actually emits, where those shapes occur together and interact.
It is the regression target for consumers that commit generated RDF, so the
assertions are about the document as a whole rather than an isolated dimension.

The fixture deliberately combines, in one graph:

* OWL restrictions hanging off ``rdfs:subClassOf``, several per class
* ``owl:unionOf`` lists, two of which **share a tail cell**
* a list whose member is itself a list
* one blank node referenced from two subjects, and a blank-node cycle
* SHACL property shapes and an ``sh:ignoredProperties`` list
* language-tagged, plain, empty, escaped and typed literals, and ``rdf:nil``
"""

from __future__ import annotations

import difflib
import re

import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, RDF, SH

from diffable_rdf import canonicalize_rdf_graph, deterministic_turtle

EX = Namespace("https://example.org/person-schema/")

#: A generated schema document, in the shape a LinkML-style OWL/SHACL generator emits.
SCHEMA_TURTLE = r"""
@prefix ex: <https://example.org/person-schema/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex: a owl:Ontology ;
    rdfs:label "Person schema"@en ;
    rdfs:label "Personenschema"@de ;
    owl:versionInfo "1.4.2" ;
    ex:sourceFile "https://example.org/person.yaml"^^xsd:anyURI ;
    ex:generated "2026-09-18"^^xsd:date ;
    ex:experimental false .

ex:Person a owl:Class ;
    rdfs:label "Person"@en ;
    rdfs:comment "A person.\nHas a \"name\", a C:\\path and a tab\there." ;
    ex:note "" ;
    ex:motto "caf\u00e9 na\u00efve \u2615" ;
    rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:name ; owl:someValuesFrom xsd:string ] ,
                    [ a owl:Restriction ; owl:onProperty ex:knows ; owl:allValuesFrom ex:Person ] ,
                    [ a owl:Restriction ; owl:onProperty ex:age ;
                      owl:maxCardinality "1"^^xsd:nonNegativeInteger ] ;
    ex:contactVia _:address ;
    ex:tagged ( "primary" ( "nested" "inner" ) ) ;
    ex:noAliases rdf:nil .

ex:Organization a owl:Class ;
    rdfs:label "Organization"@en ;
    rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:name ; owl:someValuesFrom xsd:string ] ;
    ex:contactVia _:address .

ex:Employee a owl:Class ;
    rdfs:subClassOf ex:Person ;
    owl:equivalentClass [ owl:unionOf _:employeeUnion ] .

ex:Contractor a owl:Class ;
    owl:equivalentClass [ owl:unionOf _:contractorUnion ] .

# Two unions sharing one tail cell: an inline "( ... )" would consume the shared
# cell for whichever list is written first and detach it from the other.
_:employeeUnion rdf:first ex:Person ; rdf:rest _:sharedTail .
_:contractorUnion rdf:first ex:Organization ; rdf:rest _:sharedTail .
_:sharedTail rdf:first ex:Customer ; rdf:rest rdf:nil .

ex:Customer a owl:Class .

_:address a ex:Address ;
    ex:city "Berlin"@de ;
    ex:postalCode "10115" ;
    ex:latitude "52.53"^^xsd:double ;
    ex:floor 3 .

# A cycle between blank nodes: label assignment must still terminate.
_:provenanceA ex:derivedFrom _:provenanceB ; ex:step 1 .
_:provenanceB ex:derivedFrom _:provenanceA ; ex:step 2 .
ex: ex:provenance _:provenanceA .

ex:PersonShape a sh:NodeShape ;
    sh:targetClass ex:Person ;
    sh:closed true ;
    sh:ignoredProperties ( rdf:type owl:sameAs ) ;
    sh:property [ sh:path ex:name ; sh:datatype xsd:string ; sh:minCount 1 ; sh:maxCount 1 ; sh:order 0 ] ,
                [ sh:path ex:age ; sh:datatype xsd:integer ; sh:minInclusive 0 ; sh:maxInclusive 150 ] ,
                [ sh:path ex:height ; sh:datatype xsd:double ; sh:minExclusive 0.0 ] ,
                [ sh:path ex:knows ; sh:class ex:Person ; sh:nodeKind sh:IRI ] .
"""

#: An independent class added later, the way a schema grows in version control.
ADDED_CLASS_TURTLE = r"""
@prefix ex: <https://example.org/person-schema/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:Robot a owl:Class ;
    rdfs:label "Robot"@en ;
    rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:serial ; owl:someValuesFrom xsd:string ] .

ex:RobotShape a sh:NodeShape ;
    sh:targetClass ex:Robot ;
    sh:property [ sh:path ex:serial ; sh:datatype xsd:string ; sh:minCount 1 ] .
"""


def _schema_graph() -> Graph:
    """Parse the generated-schema fixture."""
    return Graph().parse(data=SCHEMA_TURTLE, format="turtle")


def _extended_graph() -> Graph:
    """The same schema after an unrelated class is added."""
    graph = _schema_graph()
    graph.parse(data=ADDED_CLASS_TURTLE, format="turtle")
    return graph


def _relabelled(graph: Graph) -> Graph:
    """The same graph with every blank node given a different identifier."""
    mapping: dict[BNode, BNode] = {}

    def rename(term):
        if isinstance(term, BNode):
            return mapping.setdefault(term, BNode())
        return term

    renamed = Graph()
    for prefix, namespace in graph.namespaces():
        renamed.bind(prefix, namespace)
    for subject, predicate, obj in graph:
        renamed.add((rename(subject), predicate, rename(obj)))
    return renamed


def _reordered(graph: Graph) -> Graph:
    """The same graph with its triples inserted in the opposite order."""
    reordered = Graph()
    for prefix, namespace in graph.namespaces():
        reordered.bind(prefix, namespace)
    for triple in sorted(graph, key=str, reverse=True):
        reordered.add(triple)
    return reordered


def _renderings() -> list:
    """Every public rendering this document must survive, with its parse format."""
    return [
        pytest.param(deterministic_turtle, "turtle", id="deterministic_turtle"),
        pytest.param(lambda g: canonicalize_rdf_graph(g, "turtle"), "turtle", id="canonical_turtle"),
        pytest.param(lambda g: canonicalize_rdf_graph(g, "turtle", diff_stable=True), "turtle", id="stable_turtle"),
        pytest.param(lambda g: canonicalize_rdf_graph(g, "nt"), "nt", id="canonical_nt"),
        pytest.param(lambda g: canonicalize_rdf_graph(g, "nt", diff_stable=True), "nt", id="stable_nt"),
        pytest.param(lambda g: canonicalize_rdf_graph(g, "xml"), "xml", id="canonical_xml"),
        pytest.param(lambda g: canonicalize_rdf_graph(g, "json-ld"), "json-ld", id="canonical_jsonld"),
    ]


def test_fixture_contains_the_shapes_the_other_tests_rely_on() -> None:
    """Guard the fixture: every hard shape must really be present.

    Without this, a fixture that silently lost its shared list cell or its
    language tags would leave the round-trip assertions passing vacuously.
    """
    graph = _schema_graph()

    tails = [cell for cell in graph.subjects(RDF.rest, None) if len(list(graph.subjects(RDF.rest, cell))) > 1]
    assert tails, "no shared list tail cell"

    shared = [node for node in graph.objects(None, EX.contactVia) if len(list(graph.subjects(EX.contactVia, node))) > 1]
    assert shared and isinstance(shared[0], BNode), "no blank node shared between two subjects"

    cycle = set(graph.subjects(EX.derivedFrom, None)) & set(graph.objects(None, EX.derivedFrom))
    assert len(cycle) == 2, "no blank-node cycle"

    restrictions = set(graph.subjects(RDF.type, OWL.Restriction))
    assert len(restrictions) >= 4, "too few OWL restrictions"
    assert all(isinstance(node, BNode) for node in restrictions)

    literals = [obj for obj in graph.objects() if isinstance(obj, Literal)]
    assert {literal.language for literal in literals} >= {"en", "de"}, "no language-tagged literals"
    assert any(literal.datatype is not None for literal in literals), "no typed literals"
    assert any(str(literal) == "" for literal in literals), "no empty literal"
    assert any("\n" in str(literal) and '"' in str(literal) for literal in literals), "no escaped literal"
    assert (EX.Person, EX.noAliases, RDF.nil) in graph, "no rdf:nil object"
    assert set(graph.subjects(RDF.type, SH.NodeShape)), "no SHACL shapes"


@pytest.mark.parametrize(("render", "parse_format"), _renderings())
def test_every_rendering_preserves_the_document(render, parse_format: str) -> None:
    """Each public rendering round-trips the whole document without losing anything."""
    graph = _schema_graph()
    round_trip = Graph().parse(data=render(graph), format=parse_format)
    assert len(round_trip) == len(graph)
    assert isomorphic(round_trip, graph)


@pytest.mark.parametrize(("render", "parse_format"), _renderings())
def test_every_rendering_is_idempotent(render, parse_format: str) -> None:
    """Re-rendering a rendered document reproduces it byte for byte."""
    first = render(_schema_graph())
    second = render(Graph().parse(data=first, format=parse_format))
    assert second == first


@pytest.mark.parametrize(("render", "parse_format"), _renderings())
def test_every_rendering_ignores_incoming_blank_node_names(render, parse_format: str) -> None:
    """Renaming every blank node must not change a single byte."""
    assert render(_relabelled(_schema_graph())) == render(_schema_graph())


@pytest.mark.parametrize(("render", "parse_format"), _renderings())
def test_every_rendering_ignores_insertion_order(render, parse_format: str) -> None:
    """Inserting the same triples in another order must not change a single byte."""
    assert render(_reordered(_schema_graph())) == render(_schema_graph())


def test_adding_a_class_rewrites_nothing_rdfc_alone_would_rewrite() -> None:
    """An unrelated addition adds lines without rewriting the rest of the file.

    This is the behavior consumers commit generated RDF for, and the assertion
    carries its own control: RDFC-1.0 assigns ``c14nN`` labels in a global order,
    so a new blank node renumbers every label sorting after it. Checking the
    baseline in the same test keeps a fixture that stopped demonstrating the
    problem from turning the real assertions into no-ops.
    """
    before, after = _schema_graph(), _extended_graph()

    def rewritten_lines(render) -> list[str]:
        diff = difflib.unified_diff(render(before).splitlines(), render(after).splitlines(), n=0, lineterm="")
        return [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")]

    baseline = rewritten_lines(lambda graph: canonicalize_rdf_graph(graph, "turtle"))
    assert len(baseline) > 10, "fixture no longer demonstrates the RDFC-1.0 relabelling it is meant to contrast"

    for render in (deterministic_turtle, lambda graph: canonicalize_rdf_graph(graph, "turtle", diff_stable=True)):
        assert rewritten_lines(render) == [], "diff-stable output rewrote lines the edit did not touch"

    assert len(deterministic_turtle(after).splitlines()) > len(deterministic_turtle(before).splitlines())


def test_adding_a_class_keeps_every_untouched_statement_verbatim() -> None:
    """Every N-Triples line, blank-node label included, must survive the edit unchanged.

    The comparison is textual on purpose: parsing mints fresh rdflib identifiers,
    which would hide exactly the relabelling this option exists to prevent.
    """
    before = canonicalize_rdf_graph(_schema_graph(), "nt", diff_stable=True)
    after = canonicalize_rdf_graph(_extended_graph(), "nt", diff_stable=True)

    missing = set(before.splitlines()) - set(after.splitlines())
    assert missing == set(), f"the edit rewrote statements it did not touch: {sorted(missing)[:3]}"

    def labels(document: str) -> set[str]:
        return set(re.findall(r"_:(\S+)", document))

    assert labels(before), "fixture produced no blank-node labels"
    assert labels(before) <= labels(after)


def test_the_document_survives_a_named_node_rename() -> None:
    """Renaming one IRI must change that subject's lines and leave the rest alone."""
    graph = _schema_graph()
    renamed = Graph()
    for prefix, namespace in graph.namespaces():
        renamed.bind(prefix, namespace)
    for subject, predicate, obj in graph:
        swap = {EX.Customer: URIRef(EX.Client)}
        renamed.add((swap.get(subject, subject), predicate, swap.get(obj, obj)))

    assert not isomorphic(renamed, graph)
    round_trip = Graph().parse(data=deterministic_turtle(renamed), format="turtle")
    assert isomorphic(round_trip, renamed)
