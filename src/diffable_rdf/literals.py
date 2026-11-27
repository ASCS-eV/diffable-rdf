"""Internal literal helpers shared by the serializers."""

from __future__ import annotations

from rdflib import Literal, URIRef

# The datatype rdflib gives a literal written without one: ``None`` in rdflib 7,
# and ``xsd:string`` in an rdflib that follows RDF 1.1 Concepts and Abstract
# Syntax, section 3.3, where every literal has a datatype and a simple literal
# is syntactic sugar for an ``xsd:string`` literal.
_SIMPLE_LITERAL_DATATYPE = Literal("").datatype


def written_datatype(literal: Literal) -> URIRef | None:
    """Return the datatype IRI a serialization writes for ``literal``.

    Returns ``None`` when the datatype is implied: for a language-tagged
    literal, whose datatype is ``rdf:langString``, and for a literal with the
    datatype rdflib gives a literal written without one. Where every literal
    has a datatype, ``"x"^^xsd:string`` is the simple literal ``"x"`` and is
    written as one. In rdflib 7, which keeps the two apart, an explicit
    ``xsd:string`` is written.
    """
    if literal.language or literal.datatype == _SIMPLE_LITERAL_DATATYPE:
        return None
    return literal.datatype
