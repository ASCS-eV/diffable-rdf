"""Deterministic, diff-stable Turtle serialization for rdflib graphs.

Three-phase hybrid pipeline: RDFC-1.0 canonicalization (pyoxigraph) ->
Weisfeiler-Lehman blank-node hashing -> idiomatic rdflib re-serialization.
"""

from __future__ import annotations

import logging

import pyoxigraph
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.plugins.serializers.turtle import TurtleSerializer
from rdflib.term import Node

logger = logging.getLogger(__name__)


# The WL labelling primitive lives in diffable_rdf.wl so that tools which
# already run RDFC-1.0 themselves can reuse it without this serializer.
from diffable_rdf.wl import wl_blank_node_labels as _wl_signatures  # noqa: E402
from diffable_rdf.graph_input import _require_single_graph  # noqa: E402
from diffable_rdf.namespaces import prepare_namespaces  # noqa: E402


def _quote_turtle_string(text: str) -> str:
    """Return ``text`` as a quoted Turtle string literal.

    Turtle's ``STRING_LITERAL_QUOTE`` excludes only ``"``, ``\\``, LF and CR,
    so those are the escapes this needs; every other character, including a
    Unicode line separator, is legal raw. Values with newlines use long-quoted
    form; other values use short-quoted form.
    """
    if "\n" in text:
        encoded = text.replace("\\", "\\\\")
        if '"""' in text:
            encoded = encoded.replace('"""', '\\"\\"\\"')
        if encoded.endswith('"') and not encoded.endswith('\\"'):
            encoded = encoded[:-1] + '\\"'
        return '"""' + encoded.replace("\r", "\\r") + '"""'
    encoded = text.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r")
    return '"' + encoded + '"'


class _LiteralPreservingTurtleSerializer(TurtleSerializer):
    """Turtle serializer that writes literals exactly as the graph holds them."""

    def sortProperties(self, properties):  # noqa: N802
        """Order predicates, and each predicate's objects, by a total key.

        This deliberately does not call ``super()``. rdflib's implementation
        sorts each object list with a bare ``list.sort()``, which compares
        ``Literal``s through ``Literal.__lt__`` -- defined as "not greater and
        not equal" over the *value* space. That comparator is neither total nor
        exception-safe: distinct terms with equal values tie, so their order
        falls back to graph iteration order, and a ``NaN`` beside an
        ``xsd:decimal`` raises ``decimal.InvalidOperation`` from inside the
        sort. Ordering by the complete RDF term spelling instead is total by
        construction and cannot raise.
        """
        for objects in properties.values():
            objects.sort(key=self._object_sort_key)

        ordered: list = []
        seen = set()
        for predicate in self.predicateOrder:
            if predicate in properties and predicate not in seen:
                ordered.append(predicate)
                seen.add(predicate)
        for predicate in sorted(properties, key=str):
            if predicate not in seen:
                ordered.append(predicate)
                seen.add(predicate)
        return ordered

    @staticmethod
    def _object_sort_key(node: Node) -> tuple:
        """A total order over objects that never consults the value space."""
        # Rank blank nodes, IRIs, and literals in that order. Complete term
        # spelling provides a total order within each kind.
        if isinstance(node, BNode):
            return (0, str(node), "", "")
        if isinstance(node, URIRef):
            return (1, str(node), "", "")
        if isinstance(node, Literal):
            return (2, str(node), node.language or "", str(node.datatype or ""))
        return (3, str(node), "", "")

    def label(self, node: Node, position: int) -> str:
        from rdflib import Literal

        if isinstance(node, Literal):
            return self._literal_turtle(node)
        return super().label(node, position)

    def _literal_turtle(self, node) -> str:
        """Render a literal in quoted form, preserving its lexical text exactly.

        The graph term supplies the lexical form directly. This avoids private
        RDFLib APIs and preserves ``xsd:double`` and ``xsd:float`` NaN and
        infinity spellings.

        Turtle's numeric and boolean shorthand is not used at all: it renders
        the Python *value*, which merges distinct RDF terms such as ``01`` and
        ``1`` and can shorten a double's lexical form.
        """
        quoted = _quote_turtle_string(str(node))
        if node.language:
            return f"{quoted}@{node.language}"
        if node.datatype is None:
            return quoted
        # gen_prefix=False: this runs in the write phase, after the @prefix
        # block has been emitted, so a prefix invented here would be used and
        # never declared. prepare_namespaces has already bound every datatype
        # namespace the graph uses.
        get_pname = getattr(self, "get_pname", None) or self.getQName
        pname = get_pname(node.datatype, False)
        return f"{quoted}^^{pname or f'<{node.datatype}>'}"


class _NoCollectionTurtleSerializer(_LiteralPreservingTurtleSerializer):
    """Turtle serializer that never uses ``( … )`` collection syntax.

    The fallback for graphs where the inline form cannot represent the collections faithfully.
    Whether it can depends on how the serializer decides to use ``( … )``, which is rdflib's
    decision to make and not this library's to second-guess; what belongs here is checking the
    result. An inline collection is written out at one reference only, so a chain that anything
    else points into is either detached from those references or copied once per reference, and
    in both cases the text says something the graph does not.

    Explicit ``rdf:first``/``rdf:rest`` statements can express any arrangement of cells, shared
    or not, so this is always faithful — at the cost of verbosity, and only for the graphs that
    need it.
    """

    def isValidList(self, l_: Node) -> bool:
        return False


def _canonical_dataset_form(dataset: pyoxigraph.Dataset) -> str:
    dataset.canonicalize(pyoxigraph.CanonicalizationAlgorithm.RDFC_1_0)
    return "\n".join(
        sorted(str(pyoxigraph.Triple(quad.subject, quad.predicate, quad.object)) for quad in dataset)
    )


def _rdfc_canonical_form(graph: Graph) -> str | None:
    """Return the RDFC-1.0 canonical N-Triples of ``graph``, as sorted lines.

    RDFC-1.0 is a canonical form: two graphs are isomorphic exactly when
    their canonical serializations are identical.  Comparing these strings
    is therefore an exact isomorphism test, and — unlike
    ``rdflib.compare.isomorphic``, which canonicalizes in Python — it runs
    in pyoxigraph's Rust implementation, which the pipeline already invokes
    in phase 1.

    Returns ``None`` when the graph cannot be represented in pyoxigraph at
    all (non-standard RDF such as literal predicates).  Callers treat that
    as "cannot be compared", never as "equal".
    """
    try:
        dataset = pyoxigraph.Dataset(
            pyoxigraph.parse(graph.serialize(format="nt"), format=pyoxigraph.RdfFormat.N_TRIPLES)
        )
    except SyntaxError:
        return None
    return _canonical_dataset_form(dataset)


def _rdfc_canonical_text(data: str, rdf_format: pyoxigraph.RdfFormat) -> str:
    """Return the exact RDFC-1.0 form of serialized RDF text."""
    dataset = pyoxigraph.Dataset(pyoxigraph.parse(data, format=rdf_format))
    return _canonical_dataset_form(dataset)


def deterministic_turtle(graph: Graph) -> str:
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
       relabels only the blank nodes whose own neighbourhood changed,
       instead of renumbering every blank node in the graph as RDFC-1.0
       alone does.  Note that a blank node referenced
       from many subjects (a "hub") folds all of those references into
       its signature, so editing any one of them relabels the hub and
       churns the lines that reference it.
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
    only changes syntactic form, never semantic content.  Typed literals keep
    their exact lexical form, because RDF 1.1 term equality compares lexical
    forms character by character [3]_: ``"1"^^xsd:integer`` and
    ``"01"^^xsd:integer`` denote one value but are two distinct RDF terms, and
    collapsing them would drop a triple.

    Parameters
    ----------
    graph : rdflib.Graph
        A single rdflib Graph to serialize. Dataset and ConjunctiveGraph
        containers are not supported; select an individual graph context.

    Returns
    -------
    str
        Deterministic Turtle string with ``@prefix`` declarations.

    Raises
    ------
    TypeError
        If ``graph`` is a Dataset or ConjunctiveGraph container.

    References
    ----------
    .. [1] W3C (2024). "RDF Dataset Canonicalization." W3C Recommendation,
       21 May 2024.  Defines the RDFC-1.0 algorithm.
       https://www.w3.org/TR/rdf-canon/
    .. [2] W3C (2014). "RDF 1.1 Turtle — Terse RDF Triple Language."
       W3C Recommendation.  https://www.w3.org/TR/turtle/
    .. [3] W3C (2014). "RDF 1.1 Concepts and Abstract Syntax", §3.3 Literals
       (literal term equality) and §3.6 Graph Comparison (isomorphism).
       W3C Recommendation.  https://www.w3.org/TR/rdf11-concepts/
    """
    _require_single_graph(graph)

    # ── Phase 1: RDFC-1.0 canonicalization ──────────────────────────
    nt_data = graph.serialize(format="nt")

    try:
        dataset = pyoxigraph.Dataset(pyoxigraph.parse(nt_data, format=pyoxigraph.RdfFormat.N_TRIPLES))
    except SyntaxError:
        # Non-standard RDF that rdflib accepts but pyoxigraph rejects
        # (relative IRIs, or literal predicates from SHACL annotation
        # mode). Degrade to the deterministic rdflib path rather than
        # crashing: the output is no longer diff-stable, but it is still
        # reproducible across processes.
        from diffable_rdf.canonicalize import (
            _deterministic_fallback_serialize,
            _with_single_trailing_newline,
        )

        logger.warning(
            "Graph contains non-standard RDF (e.g. relative IRIs or literal predicates) "
            "that pyoxigraph cannot parse; falling back to rdflib. Output is still "
            "deterministic but is not diff-stable."
        )
        return _with_single_trailing_newline(
            _deterministic_fallback_serialize(graph, "turtle")
        )

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
                # xsd:string (Turtle §2.5.1).  Write the shorter form, so
                # every string literal does not carry a redundant datatype
                # annotation that says nothing about the term.
                if dt_iri == "http://www.w3.org/2001/XMLSchema#string":
                    return Literal(term.value)
                return Literal(term.value, datatype=URIRef(dt_iri), normalize=False)
            return Literal(term.value)
        raise TypeError(f"Unexpected pyoxigraph term type: {type(term).__name__}: {term}")

    result_graph = Graph(bind_namespaces="none")
    # NOTE: the source graph's ``base`` is deliberately NOT carried across.
    # rdflib relativizes IRIs against a base by naive string prefixing, which
    # is not RFC-3986-correct for hash bases ("http://ex.org/d#") or bases
    # without a trailing slash: "http://ex.org/d#a" is emitted as "<a>", which
    # re-resolves to a different IRI.  Preserving the base therefore corrupts
    # terms and trips the round-trip guard below.  Absolute IRIs are always
    # emitted in full, which is lossless and diff-stable.
    for triple in remapped:
        result_graph.add(
            (
                _to_rdflib(triple.subject),
                _to_rdflib(triple.predicate),
                _to_rdflib(triple.object),
            )
        )

    prepare_namespaces(result_graph, graph)

    # rdflib's Turtle serializer always emits a trailing double newline;
    # normalize to a single newline for consistent file endings.
    import io

    def _render(serializer_class) -> str:
        buffer = io.BytesIO()
        serializer_class(result_graph).serialize(buffer, encoding="utf-8")
        return buffer.getvalue().decode("utf-8").rstrip("\n") + "\n"

    # Compare with the source graph, not the intermediate rdflib graph: that
    # catches any identity loss during pyoxigraph-to-rdflib term conversion.
    expected = _rdfc_canonical_form(graph)

    def _round_trips(text: str) -> bool:
        reparsed = Graph(bind_namespaces="none")
        try:
            reparsed.parse(data=text, format="turtle")
        except Exception:
            # Output rdflib cannot read back is a failed round trip, not a
            # crash: fall through to the collection-free rendering, which is
            # what the two-attempt structure below exists for.
            return False
        try:
            actual = _rdfc_canonical_text(text, pyoxigraph.RdfFormat.TURTLE)
        except SyntaxError:
            return False
        return expected is not None and actual == expected

    # A canonical form that does not round-trip is worse than none: it silently rewrites the
    # graph. Where inline ``( … )`` collection syntax is safe is rdflib's decision, and it is
    # the one place this pipeline cannot verify by construction, because it depends on how many
    # statements point into a chain rather than on anything the graph says locally. So take
    # rdflib's output and check it, rather than predicting it: on the graphs where the inline
    # form detaches or duplicates cells, fall back to explicit rdf:first/rdf:rest statements,
    # which can express any arrangement of cells.
    text = _render(_LiteralPreservingTurtleSerializer)
    if not _round_trips(text):
        text = _render(_NoCollectionTurtleSerializer)
        if not _round_trips(text):
            raise ValueError(
                "canonical serialization does not round-trip even without collection syntax; "
                f"{len(result_graph)} triples in. This is a bug in diffable-rdf: please report "
                "it with the input graph."
            )
    # _render appends a newline unconditionally, which turns an empty graph
    # into a lone newline; normalise here so every return agrees.
    from diffable_rdf.canonicalize import _with_single_trailing_newline

    return _with_single_trailing_newline(text)




def well_known_prefix_map() -> dict[str, str]:
    """Return a mapping from namespace URI to standard prefix name.

    Uses rdflib's curated default namespace bindings as the source of truth.
    For example, ``https://schema.org/`` maps to ``schema``.

    This allows generators to normalise non-standard prefix aliases
    (e.g. ``sdo`` for ``https://schema.org/``) to their conventional names.
    """
    from rdflib import Graph as RdfGraph

    return {str(ns): str(pfx) for pfx, ns in RdfGraph().namespaces() if str(pfx)}
