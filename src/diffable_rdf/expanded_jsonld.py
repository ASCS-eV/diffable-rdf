"""Expanded JSON-LD serialization for canonical rdflib graphs."""

from __future__ import annotations

import re

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.term import Node

from .jsonld import deterministic_json

_ABSOLUTE_IRI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _unsupported(position: str, term: Node) -> ValueError:
    return ValueError(
        f"degraded JSON-LD interoperable RDF subset does not support {position} term of type "
        f"{type(term).__name__}: {term!r}"
    )


def _iri_identifier(term: URIRef, position: str, *, require_absolute: bool) -> str:
    value = str(term)
    if value.startswith("_:"):
        raise ValueError(
            "degraded JSON-LD interoperable RDF subset does not accept a URIRef beginning with '_:' "
            f"in {position} position: {value!r}"
        )
    if require_absolute and not _ABSOLUTE_IRI.match(value):
        raise ValueError(
            f"degraded JSON-LD requires an absolute IRI in {position} "
            f"position: {value!r}"
        )
    return value


def _node_identifier(term: Node, position: str) -> str:
    if isinstance(term, URIRef):
        return _iri_identifier(term, position, require_absolute=False)
    if isinstance(term, BNode):
        return f"_:{term}"
    raise _unsupported(position, term)


def _object_value(term: Node) -> dict[str, str]:
    if isinstance(term, (URIRef, BNode)):
        return {"@id": _node_identifier(term, "object")}
    if not isinstance(term, Literal):
        raise _unsupported("object", term)

    value = {"@value": str(term)}
    if term.language is not None:
        value["@language"] = term.language
    elif term.datatype is not None:
        datatype = _iri_identifier(term.datatype, "datatype", require_absolute=True)
        value["@type"] = datatype
    return value


def serialize_expanded_jsonld(graph: rdflib.Graph) -> str:
    """Serialize a canonical graph without inferring recursive JSON-LD lists.

    Every RDF subject has one expanded node object. Blank-node and IRI objects
    remain references, so shared nodes and cycles retain their graph identity.
    This fallback emits an interoperable standard-RDF subset and rejects
    generalized terms before any output is returned.
    """
    nodes: dict[str, dict[str, object]] = {}
    for subject, predicate, obj in graph:
        subject_id = _node_identifier(subject, "subject")
        if not isinstance(predicate, URIRef):
            raise _unsupported("predicate", predicate)
        predicate_id = _iri_identifier(predicate, "predicate", require_absolute=True)
        object_value = _object_value(obj)

        node = nodes.setdefault(subject_id, {"@id": subject_id})
        values = node.setdefault(predicate_id, [])
        assert isinstance(values, list)
        values.append(object_value)

    return deterministic_json(list(nodes.values())) + "\n"
