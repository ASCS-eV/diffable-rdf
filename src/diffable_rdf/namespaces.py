"""Internal namespace preparation for deterministic rdflib serialization."""

from __future__ import annotations

from rdflib import Graph, Literal, URIRef


def prepare_namespaces(target: Graph, source: Graph) -> None:
    """Bind source prefixes and allocate missing prefixes in a stable order.

    ``target`` must use a namespace manager created with
    ``bind_namespaces="none"``. Caller bindings are installed first so their
    names, including otherwise-unused ``nsN`` names, are reserved before
    rdflib generates any prefixes. Turtle serializers only declare bindings
    they actually use, so reserving an unused caller binding does not leak it
    into the document.
    """
    source_bindings = sorted(
        (("" if prefix is None else str(prefix), str(namespace)) for prefix, namespace in source.namespaces()),
        key=lambda binding: (binding[0], binding[1]),
    )
    for prefix, namespace in source_bindings:
        target.namespace_manager.bind(prefix, URIRef(namespace), override=True, replace=True)

    # A namespace can have multiple aliases. Restore the source manager's
    # preferred alias after the sorted binding pass so serialization keeps the
    # caller's choice rather than making lexicographic order decide it.
    for namespace in sorted({namespace for _, namespace in source_bindings}):
        preferred = source.namespace_manager.store.prefix(URIRef(namespace))
        if preferred is not None:
            target.namespace_manager.bind(str(preferred), URIRef(namespace), override=True, replace=True)

    iris: set[str] = set()
    for subject, predicate, object_ in target:
        for term in (subject, predicate, object_):
            if isinstance(term, URIRef):
                iris.add(str(term))
            elif isinstance(term, Literal) and term.datatype is not None:
                iris.add(str(term.datatype))

    # rdflib normally creates ns1/ns2/... while traversing the graph, whose
    # iteration order varies between processes. Force that discovery to occur
    # in lexical IRI order instead. compute_qname only splits relative IRIs;
    # it does not resolve them against a base, so degraded output retains them.
    for iri in sorted(iris):
        try:
            target.namespace_manager.compute_qname(iri, generate=True)
        except ValueError:
            # Some legal RDF IRIs have no QName split. rdflib emits those in
            # angle brackets, so there is no namespace to preallocate.
            continue
