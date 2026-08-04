"""Deterministic, diff-stable Turtle serialization for rdflib graphs.

Three-phase hybrid pipeline: RDFC-1.0 canonicalization (pyoxigraph) ->
Weisfeiler-Lehman blank-node hashing -> idiomatic rdflib re-serialization.

Extracted from ASCS-eV/linkml (feat/deterministic-output, PR #1) into a
standalone, tool-agnostic library.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rdflib import Graph as RdfGraph

logger = logging.getLogger(__name__)


from rdflib import RDF  # noqa: E402  (kept beside the serializer that uses it)
from rdflib.plugins.serializers.turtle import TurtleSerializer  # noqa: E402


def _wl_signatures(
    quads: list,
    iterations: int = 4,
) -> dict[str, str]:
    """Compute Weisfeiler-Lehman structural signatures for blank nodes.

    Uses 1-dimensional WL colour refinement [1]_ to assign each blank
    node a deterministic signature derived from its multi-hop
    neighbourhood structure.  The signature depends only on predicate
    IRIs, literal values, and named-node IRIs — **not** on blank-node
    identifiers — so it remains stable when unrelated triples are added
    or removed.

    Parameters
    ----------
    quads : list
        Canonical quads from pyoxigraph (after RDFC-1.0).
    iterations : int
        Number of WL refinement rounds (default 4).

    Returns
    -------
    dict[str, str]
        Mapping from canonical blank-node ID (e.g. ``c14n42``) to a
        truncated SHA-256 hash suitable for use as a stable blank-node
        label.

    References
    ----------
    .. [1] Weisfeiler, B. & Leman, A. (1968). "The reduction of a graph
       to canonical form and the algebra which appears therein."
    """
    import hashlib

    import pyoxigraph  # guaranteed available — caller (deterministic_turtle) checks

    # Collect all blank node IDs and build adjacency index.
    bnode_ids: set[str] = set()
    # outgoing[b] = list of (predicate_str, object_str_or_bnode_id, is_bnode)
    outgoing: dict[str, list[tuple[str, str, bool]]] = {}
    # incoming[b] = list of (subject_str_or_bnode_id, predicate_str, is_bnode)
    incoming: dict[str, list[tuple[str, str, bool]]] = {}

    for q in quads:
        s, p, o = q.subject, q.predicate, q.object
        s_is_bn = isinstance(s, pyoxigraph.BlankNode)
        o_is_bn = isinstance(o, pyoxigraph.BlankNode)
        p_str = str(p)

        if s_is_bn:
            bnode_ids.add(s.value)
            outgoing.setdefault(s.value, []).append((p_str, o.value if o_is_bn else str(o), o_is_bn))
        if o_is_bn:
            bnode_ids.add(o.value)
            incoming.setdefault(o.value, []).append((s.value if s_is_bn else str(s), p_str, s_is_bn))

    # Initialise signatures: named-node edges only (no bnode IDs).
    sig: dict[str, str] = {}
    for bid in bnode_ids:
        parts = []
        for p_str, o_str, o_is_bn in outgoing.get(bid, []):
            if not o_is_bn:
                parts.append(f"+{p_str}={o_str}")
        for s_str, p_str, s_is_bn in incoming.get(bid, []):
            if not s_is_bn:
                parts.append(f"-{s_str}={p_str}")
        sig[bid] = "|".join(sorted(parts))

    # Iterative refinement: incorporate neighbour signatures.
    for _ in range(iterations):
        new_sig: dict[str, str] = {}
        for bid in bnode_ids:
            parts = [sig[bid]]
            for p_str, o_str, o_is_bn in outgoing.get(bid, []):
                if o_is_bn:
                    parts.append(f"+{p_str}={sig.get(o_str, '')}")
            for s_str, p_str, s_is_bn in incoming.get(bid, []):
                if s_is_bn:
                    parts.append(f"-{sig.get(s_str, '')}={p_str}")
            new_sig[bid] = "|".join(sorted(parts))
        sig = new_sig

    # Convert signatures to truncated SHA-256 hashes.
    # Use 12 hex chars (48 bits) — birthday-bound collision probability
    # is ~n²/2^49: ~0.002% at 100k nodes.  Collisions are handled by
    # appending a counter (see below), so correctness is preserved.
    hash_map: dict[str, str] = {}
    seen_hashes: dict[str, int] = {}
    for bid in sorted(bnode_ids):
        digest = hashlib.sha256(sig[bid].encode("utf-8")).hexdigest()[:12]
        # Handle collisions by appending a counter.
        count = seen_hashes.get(digest, 0)
        seen_hashes[digest] = count + 1
        label = f"b{digest}" if count == 0 else f"b{digest}_{count}"
        hash_map[bid] = label

    return hash_map




class _SharingAwareTurtleSerializer(TurtleSerializer):
    """Turtle serializer that only uses ``( … )`` for lists nothing else points into.

    rdflib's :meth:`isValidList` checks that every cell of an ``rdf:List`` carries exactly
    two predicates, but not how many statements point *into* the chain. When a cell is
    referenced from more than one place, the inline collection form consumes it and the other
    reference is left dangling, with no ``rdf:first``/``rdf:rest`` of its own::

        _:tail rdf:first "b" ; rdf:rest rdf:nil .
        _:l1   rdf:first "a" ; rdf:rest _:tail .
        ex:s1 sh:in _:l1 .
        ex:s2 sh:in _:tail .

    serialized as::

        ex:s1 sh:in ( "a" "b" ) .
        ex:s2 sh:in _:tail .          # _:tail is never defined -> the list is lost

    A shared *head* is corrupted differently: the collection is written inline at every
    reference, so re-parsing yields one private copy per reference and the triple count grows.
    Either way the output does not round-trip, which defeats the point of a canonical form.

    Requiring that every cell in the chain has exactly one inbound reference keeps the
    readable ``( … )`` form for the overwhelmingly common private list, and falls back to
    explicit ``rdf:first``/``rdf:rest`` statements exactly where sharing makes it unsafe.
    """

    def isValidList(self, l_: "Node") -> bool:
        if not super().isValidList(l_):
            return False
        node = l_
        while node and node != RDF.nil:
            # A cell of a private list is pointed at once: by the statement that introduces
            # the list, or by its predecessor's rdf:rest. More than that means sharing.
            if sum(1 for _ in self.store.subject_predicates(node)) > 1:
                return False
            node = self.store.value(node, RDF.rest)
        return True


class _NoCollectionTurtleSerializer(TurtleSerializer):
    """Turtle serializer that never uses ``( … )`` collection syntax.

    The fallback for graphs where the inline form cannot represent the collections faithfully.
    Explicit ``rdf:first``/``rdf:rest`` statements are always correct, if less readable, so this
    guarantees a round-trip at the cost of verbosity - and only for the graphs that need it.
    """

    def isValidList(self, l_: "Node") -> bool:
        return False


def deterministic_turtle(graph: "RdfGraph") -> str:
    """Serialize an RDF graph to Turtle with deterministic output ordering.

    Uses a three-phase hybrid pipeline for **correctness**, **diff
    stability**, and **readability**:

    1. **RDFC-1.0** [1]_ (via ``pyoxigraph``) canonicalizes the graph,
       ensuring isomorphic inputs produce identical triple sets.
    2. **Weisfeiler-Lehman structural hashing** replaces the sequential
       ``_:c14nN`` identifiers with content-based hashes derived from
       each blank node's multi-hop neighbourhood.  These hashes depend
       only on predicate IRIs, literal values, and named-node IRIs —
       not on blank-node numbering — so adding or removing a triple
       only affects the identifiers of directly involved blank nodes.
    3. **Hybrid rdflib re-serialization** parses the canonicalized,
       WL-hashed triples back into an rdflib ``Graph`` and serializes
       with rdflib's native Turtle writer.  This recovers idiomatic
       Turtle features that pyoxigraph cannot emit:

       - **Inline blank nodes** (``[ … ]``) for singly-referenced
         blank nodes (Turtle §2.7 [2]_), instead of verbose named
         ``_:bHASH`` syntax.
       - **Collection syntax** (``( … )``) for ``rdf:List`` chains
         (Turtle §2.8 [2]_).
       - **Prefix filtering**: only prefixes actually used in the
         graph's IRIs are declared, following the practice of Apache
         Jena, Eclipse RDF4J, and Raptor.

    All triples from the source graph are preserved — the hybrid step
    only changes syntactic form, never semantic content.

    Parameters
    ----------
    graph : rdflib.Graph
        An rdflib Graph to serialize.

    Returns
    -------
    str
        Deterministic Turtle string with ``@prefix`` declarations.

    References
    ----------
    .. [1] W3C (2024). "RDF Dataset Canonicalization (RDFC-1.0)."
       W3C Recommendation.  https://www.w3.org/TR/rdf-canon/
    .. [2] W3C (2014). "RDF 1.1 Turtle — Terse RDF Triple Language."
       W3C Recommendation.  https://www.w3.org/TR/turtle/
    """
    try:
        import pyoxigraph
    except ImportError as exc:
        raise ImportError(
            "pyoxigraph >= 0.4.0 is required for --deterministic output. "
            "Install it with: pip install 'pyoxigraph>=0.4.0'"
        ) from exc

    from rdflib import BNode, Graph, Literal, URIRef

    # ── Phase 1: RDFC-1.0 canonicalization ──────────────────────────
    nt_data = graph.serialize(format="nt")

    dataset = pyoxigraph.Dataset(pyoxigraph.parse(nt_data, format=pyoxigraph.RdfFormat.N_TRIPLES))
    dataset.canonicalize(pyoxigraph.CanonicalizationAlgorithm.RDFC_1_0)

    canonical_quads = list(dataset)

    # ── Phase 2: WL structural hashing for diff-stable blank node IDs
    wl_map = _wl_signatures(canonical_quads)

    def _remap(term):
        if isinstance(term, pyoxigraph.BlankNode) and term.value in wl_map:
            return pyoxigraph.BlankNode(wl_map[term.value])
        return term

    remapped = [pyoxigraph.Triple(_remap(q.subject), q.predicate, _remap(q.object)) for q in canonical_quads]

    # ── Phase 3: Hybrid rdflib re-serialization ─────────────────────
    # Convert pyoxigraph terms to rdflib terms and populate a clean
    # Graph that only carries explicitly-bound prefixes.
    def _to_rdflib(term):
        """Convert a pyoxigraph term to the equivalent rdflib term."""
        if isinstance(term, pyoxigraph.NamedNode):
            return URIRef(term.value)
        if isinstance(term, pyoxigraph.BlankNode):
            return BNode(term.value)
        if isinstance(term, pyoxigraph.Literal):
            if term.language:
                return Literal(term.value, lang=term.language)
            if term.datatype:
                dt_iri = term.datatype.value
                # In RDF 1.1, simple literals are syntactic sugar for
                # xsd:string (Turtle §2.5.1).  Preserve the shorter form
                # to match the original owlgen output and avoid spurious
                # diffs on every string literal.
                if dt_iri == "http://www.w3.org/2001/XMLSchema#string":
                    return Literal(term.value)
                return Literal(term.value, datatype=URIRef(dt_iri))
            return Literal(term.value)
        raise TypeError(f"Unexpected pyoxigraph term type: {type(term).__name__}: {term}")

    result_graph = Graph(bind_namespaces="none")
    for triple in remapped:
        result_graph.add(
            (
                _to_rdflib(triple.subject),
                _to_rdflib(triple.predicate),
                _to_rdflib(triple.object),
            )
        )

    # Bind only prefixes whose namespace IRI is actually referenced
    # by at least one subject, predicate, or object in the graph.
    # This filters out rdflib's ~27 built-in default bindings
    # (brick, csvw, doap, …) that leak through Graph() even when
    # the schema never declared them.
    used_iris: set[str] = set()
    for s, p, o in result_graph:
        for term in (s, p, o):
            if isinstance(term, URIRef):
                used_iris.add(str(term))

    for pfx, ns in sorted(graph.namespaces()):
        pfx_s, ns_s = str(pfx), str(ns)
        if pfx_s and any(iri.startswith(ns_s) for iri in used_iris):
            result_graph.bind(pfx_s, ns_s)

    # rdflib's Turtle serializer always emits a trailing double newline;
    # normalize to a single newline for consistent file endings.
    import io

    from rdflib.compare import isomorphic

    def _render(serializer_class) -> str:
        buffer = io.BytesIO()
        serializer_class(result_graph).serialize(buffer, encoding="utf-8")
        return buffer.getvalue().decode("utf-8").rstrip("\n") + "\n"

    def _round_trips(text: str) -> bool:
        reparsed = Graph(bind_namespaces="none")
        reparsed.parse(data=text, format="turtle")
        return len(reparsed) == len(result_graph) and isomorphic(reparsed, result_graph)

    # A canonical form that does not round-trip is worse than none: it silently rewrites the
    # graph. rdflib decides where to use inline ``( … )`` collection syntax with a heuristic
    # that does not account for statements pointing into a collection, so for some graphs the
    # inline form detaches cells or duplicates them. Verify, and fall back to explicit
    # rdf:first/rdf:rest statements - always faithful - for the graphs where it does.
    text = _render(_SharingAwareTurtleSerializer)
    if not _round_trips(text):
        text = _render(_NoCollectionTurtleSerializer)
        if not _round_trips(text):
            raise ValueError(
                "canonical serialization does not round-trip even without collection syntax; "
                f"{len(result_graph)} triples in. This is a bug in diffable-rdf: please report "
                "it with the input graph."
            )
    return text




def well_known_prefix_map() -> dict[str, str]:
    """Return a mapping from namespace URI to standard prefix name.

    Uses rdflib's curated default namespace bindings as the source of truth.
    For example, ``https://schema.org/`` maps to ``schema``.

    This allows generators to normalise non-standard prefix aliases
    (e.g. ``sdo`` for ``https://schema.org/``) to their conventional names.
    """
    from rdflib import Graph as RdfGraph

    return {str(ns): str(pfx) for pfx, ns in RdfGraph().namespaces() if str(pfx)}


