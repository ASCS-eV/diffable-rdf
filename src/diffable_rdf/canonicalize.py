"""Deterministic RDF serialization via pyoxigraph RDFC-1.0 canonicalization.

This module provides a function to canonicalize an rdflib Graph using
pyoxigraph's RDFC-1.0 implementation, producing deterministic output
with stable blank node labels and sorted triples.

See ``docs/api.md`` for the full contract.

**Known limitations:**

1. **xsd:string normalization**: pyoxigraph follows RDF 1.1, where a literal
   with no datatype IRI and no language tag *has* datatype ``xsd:string``
   (Turtle §2.5.1), so plain string literals and ``"text"^^xsd:string`` are
   one term.  The output will never contain explicit ``^^xsd:string``
   annotations.  Code that re-parses the output with rdflib will see
   ``Literal("x")`` (datatype ``None``) rather than
   ``Literal("x", datatype=XSD.string)``.  This is an equivalence, not a
   normalization: RDF 1.1 Concepts §3.3 compares lexical forms character by
   character, so every *other* typed lexical form is preserved exactly.
   https://www.w3.org/TR/rdf11-concepts/#section-Graph-Literal

2. **Non-standard RDF**: Graphs with relative IRIs or generalized RDF terms
   are rejected by pyoxigraph. This function uses a deterministic rdflib
   fallback with format-specific policies. Degraded JSON-LD emits an
   interoperable standard-RDF subset and rejects terms outside that subset.

3. **Numeric short forms**: pyoxigraph uses Turtle short forms for
   ``xsd:integer`` (``42``), ``xsd:boolean`` (``true``), and
   ``xsd:decimal`` (``1.23``).  rdflib parses these back with the
   correct datatype, so this is lossless.

4. **Base IRI / prefix collision**: When a graph has ``@base`` and a
   prefix whose namespace equals the base IRI (e.g. rdflib's auto-bound
   ``base:`` prefix), pyoxigraph emits CURIEs like ``base:label`` that
   rdflib rejects.  We skip such prefixes during serialization.

5. **Trailing escaped dot in PN_LOCAL**: pyoxigraph emits CURIEs like
   ``prefix:local\\.`` for IRIs whose local part ends with ``.``.  This
   is valid Turtle (PN_LOCAL_ESC), but rdflib's notation3 parser rejects
   it because it conflicts with the statement-terminator dot.  We
   post-process Turtle-family output to expand such CURIEs to full ``<IRI>``
   form.
"""

import io
import json
import logging
import re
from xml.etree import ElementTree

import pyoxigraph as ox
import rdflib
from rdflib.plugin import PluginException
from rdflib import Graph
from rdflib.compare import to_canonical_graph

from .expanded_jsonld import _ABSOLUTE_IRI, serialize_expanded_jsonld
from .graph_input import _require_single_graph
from .jsonld import deterministic_json
from .namespaces import prepare_namespaces

logger = logging.getLogger(__name__)

# Mapping from rdflib format strings to pyoxigraph RdfFormat objects.
_FORMAT_MAP: dict[str, ox.RdfFormat] = {
    "turtle": ox.RdfFormat.TURTLE,
    "ttl": ox.RdfFormat.TURTLE,
    "nt": ox.RdfFormat.N_TRIPLES,
    "ntriples": ox.RdfFormat.N_TRIPLES,
    "n-triples": ox.RdfFormat.N_TRIPLES,
    "nt11": ox.RdfFormat.N_TRIPLES,
    "nquads": ox.RdfFormat.N_QUADS,
    "n-quads": ox.RdfFormat.N_QUADS,
    "xml": ox.RdfFormat.RDF_XML,
    "rdf/xml": ox.RdfFormat.RDF_XML,
    "trig": ox.RdfFormat.TRIG,
    "n3": ox.RdfFormat.N3,
    "json-ld": ox.RdfFormat.JSON_LD,
    "jsonld": ox.RdfFormat.JSON_LD,
    "application/ld+json": ox.RdfFormat.JSON_LD,
}

# Formats that support prefix declarations.
_PREFIX_FORMATS = frozenset({ox.RdfFormat.TURTLE, ox.RdfFormat.TRIG, ox.RdfFormat.N3, ox.RdfFormat.RDF_XML})

# Formats serialized as one statement per line, which rdflib does not emit
# in a stable order; these are sorted in the degraded fallback path.
_LINE_ORIENTED_FORMATS = frozenset({"nt", "ntriples", "n-triples", "nt11", "nquads", "n-quads"})
# Formats whose output is JSON and can therefore be canonicalized structurally.
_JSON_FORMATS = frozenset({"json-ld", "jsonld", "application/ld+json"})

# Turtle-family formats whose serializer may use ``( … )`` collection syntax.
# That syntax can only express a list whose tail is referenced once, so on the
# degraded path -- which has no round-trip check, because relative IRIs are
# deliberately passed through verbatim and would fail an isomorphism test --
# it is rendered without collection syntax instead. Explicit
# rdf:first/rdf:rest can express any arrangement of cells, shared or not.
# ``n3`` and ``trig`` are included because rdflib's N3Serializer and
# TrigSerializer both subclass TurtleSerializer and inherit its ``( … )``
# rendering; rendering them through _NoCollectionTurtleSerializer instead is
# sound because Turtle is a subset of both, so collection-free Turtle text is
# also valid N3 and valid TriG. For TriG that is additionally the only way it
# works on this path at all: rdflib's own TrigSerializer requires a
# context-aware store, which the canonicalized graph is not, and writing the
# triples into a named graph instead would invent a graph name the input never
# had. Emitting them as TriG's default graph is what the pyoxigraph path does
# too.
_COLLECTION_CAPABLE_FORMATS = frozenset({"turtle", "ttl", "n3", "trig"})

# The plugin name rdflib registers for each format this library maps. Used only
# on the degraded path, where serialization goes through rdflib rather than
# pyoxigraph: rdflib's plugin lookup is exact, and several of the aliases
# accepted here are this library's rather than rdflib's.
_RDFLIB_SERIALIZER_NAMES: dict[ox.RdfFormat, str] = {
    ox.RdfFormat.TURTLE: "turtle",
    ox.RdfFormat.N_TRIPLES: "nt",
    # N-Quads, deliberately not rdflib's ``nquads``. Its serializer needs a
    # context-aware store, which a canonicalized graph is not, and satisfying
    # that with a Dataset makes the output depend on how the installed rdflib
    # spells the default graph: 6.3.2 writes an explicit
    # ``<urn:x-rdflib:default>`` graph term where 7.6.0 leaves the slot empty.
    # A single graph has no graph name to write, and the N-Quads grammar makes
    # the graph label optional, so every N-Triples document is already a valid
    # N-Quads document in the default graph. Emitting N-Triples is therefore
    # both correct and version-independent, and matches the pyoxigraph path
    # byte for byte.
    ox.RdfFormat.N_QUADS: "nt",
    ox.RdfFormat.RDF_XML: "xml",
    ox.RdfFormat.TRIG: "trig",
    ox.RdfFormat.N3: "n3",
    ox.RdfFormat.JSON_LD: "json-ld",
}

# Formats that need the trailing-dot CURIE compatibility rewrite.
_TURTLE_FAMILY_FORMATS = frozenset({ox.RdfFormat.TURTLE, ox.RdfFormat.TRIG, ox.RdfFormat.N3})

# Formats whose output is verified against the input before being returned.
# N-Triples and N-Quads have no compact list syntax and receive no text
# post-processing.
_VERIFIED_FORMATS = _TURTLE_FAMILY_FORMATS | {ox.RdfFormat.RDF_XML}


def _xml_10_forbidden_code_point(text: str) -> int | None:
    """Return the first code point that XML 1.0 cannot represent, if any."""
    for character in text:
        code_point = ord(character)
        if not (
            code_point in (0x09, 0x0A, 0x0D)
            or 0x20 <= code_point <= 0xD7FF
            or 0xE000 <= code_point <= 0xFFFD
            or 0x10000 <= code_point <= 0x10FFFF
        ):
            return code_point
    return None


def _assert_xml_10_text_representable(text: str) -> None:
    """Raise clearly when text contains a character forbidden by XML 1.0."""
    forbidden = _xml_10_forbidden_code_point(text)
    if forbidden is not None:
        raise ValueError(
            "RDF/XML uses XML 1.0, which cannot represent "
            f"character U+{forbidden:04X} in RDF graph data."
        )


def _assert_xml_10_representable(graph: rdflib.Graph) -> None:
    """Raise clearly when graph data cannot be represented in RDF/XML 1.0."""
    for subject, predicate, object_ in graph:
        for term in (subject, predicate, object_):
            _assert_xml_10_text_representable(str(term))
            if isinstance(term, rdflib.Literal):
                if term.language:
                    _assert_xml_10_text_representable(term.language)
                if term.datatype:
                    _assert_xml_10_text_representable(str(term.datatype))
    if graph.base:
        _assert_xml_10_text_representable(str(graph.base))


def _finalize_rdf_xml(serialized: str) -> str:
    """Protect literal CR characters from XML 1.0 newline normalization.

    A character reference is not normalized by XML parsers. Replacing only
    raw CR characters preserves both CR and CRLF RDF literal values without
    touching serializer-produced markup, ordinary LF, or existing escapes.

    The replacement compensates for pyoxigraph writing a literal CR raw, which
    is an upstream defect rather than something this format requires;
    quick-xml fixed it in 0.42.0 and oxigraph's ``main`` already vendors that.
    When a pyoxigraph release carries it there will be no raw CR left here and
    this becomes a no-op, so it should be retired --
    ``tests/test_upstream_tripwires.py`` fails when that happens.
    """
    _assert_xml_10_text_representable(serialized)
    return serialized.replace("\r", "&#xD;")


def _sort_rdf_xml_elements(parent: ElementTree.Element, indent: str, closing: str) -> None:
    """Order ``parent``'s children and re-indent them, in place.

    Whitespace is reset rather than carried: an element's trailing text travels
    with it, so reordering alone would move the indentation around and leave
    the output varying by whitespace instead of by element order.
    """
    def key(element: ElementTree.Element) -> tuple[str, str, str]:
        identity = ""
        for attribute, value in sorted(element.attrib.items()):
            if attribute.endswith("}about") or attribute.endswith("}nodeID"):
                identity = value
                break
        # The serialized element breaks ties, so the order is total even for
        # elements with no identifying attribute -- property elements, whose
        # identity is their predicate and value.
        return identity, element.tag, ElementTree.tostring(element, encoding="unicode")

    children = sorted(parent, key=key)
    if not children:
        return
    for child in list(parent):
        parent.remove(child)
    parent.extend(children)
    parent.text = indent
    for child in children[:-1]:
        child.tail = indent
    children[-1].tail = closing


def _sort_rdf_xml_descriptions(serialized: str) -> str:
    """Order the elements of RDF/XML deterministically.

    rdflib's RDF/XML serializer, which the degraded path uses, emits both its
    ``rdf:Description`` elements and the property elements inside them in an
    order that follows its own graph traversal, and so varies between
    processes: measured at 6 distinct documents over 6 hash seeds for one
    graph, differing in element order alone. RDF/XML attaches no meaning to
    either order -- each property element is one triple -- so sorting them is
    lossless and makes the output reproducible.

    This is the same compensation the line-oriented branch already applies by
    sorting N-Triples lines, against the same serializer's instability.

    Parsed with ElementTree rather than rewritten as text, because element
    order is a structural property and a regex over serialized RDF reaches into
    content it should not.

    rdflib's *plain* XML serializer emits neither ``rdf:parseType="Collection"``
    nor ``parseType="Literal"`` -- only its pretty-printing serializer does, and
    that is never used here -- so nothing in this output has a meaningful
    order. The guard below keeps that assumption honest rather than implicit:
    if a ``parseType`` ever appears, the document is returned untouched.
    """
    root = ElementTree.fromstring(serialized)
    if any(name.endswith("}parseType") for element in root.iter() for name in element.attrib):
        return serialized

    _sort_rdf_xml_elements(root, "\n  ", "\n")
    for description in root:
        _sort_rdf_xml_elements(description, "\n    ", "\n  ")

    # Keep the declaration rdflib wrote; ElementTree does not reproduce it.
    declaration, newline, _ = serialized.partition("\n")
    body = ElementTree.tostring(root, encoding="unicode")
    return f"{declaration}{newline}{body}" if declaration.startswith("<?xml") else body


def _first_term_n_triples_cannot_write(
    graph: rdflib.Graph,
) -> tuple[str, rdflib.term.Node] | None:
    """Return the first term the line-oriented syntaxes cannot express.

    N-Triples and N-Quads accept only absolute IRIs -- "IRIs may be written
    only as absolute IRIs", N-Triples 1.1 §2.2 -- and only IRIs or blank nodes
    in the subject position and IRIs in the predicate position. Turtle is
    laxer: it permits relative IRIs against a base, which is why the
    Turtle-family formats can carry a graph on this path and these cannot.

    Returns ``(position, term)`` for the first offending term, or ``None`` if
    the graph is representable.
    """
    for subject, predicate, obj in graph:
        if isinstance(subject, rdflib.URIRef):
            if not _ABSOLUTE_IRI.match(str(subject)):
                return "subject", subject
        elif not isinstance(subject, rdflib.BNode):
            return "subject", subject

        if not isinstance(predicate, rdflib.URIRef):
            return "predicate", predicate
        if not _ABSOLUTE_IRI.match(str(predicate)):
            return "predicate", predicate

        if isinstance(obj, rdflib.URIRef):
            if not _ABSOLUTE_IRI.match(str(obj)):
                return "object", obj
        elif isinstance(obj, rdflib.Literal):
            datatype = obj.datatype
            if datatype is not None and not _ABSOLUTE_IRI.match(str(datatype)):
                return "literal datatype", datatype
        elif not isinstance(obj, rdflib.BNode):
            return "object", obj
    return None


def _with_single_trailing_newline(text: str) -> str:
    """Return ``text`` ending in exactly one newline, or empty if it has none.

    A file with no final newline shows up in a diff as "\\ No newline at end of
    file", and many editors and tools add one, which then reads as a spurious
    change the next time the artifact is regenerated -- precisely the churn
    this library exists to remove. Serializers disagree here: pyoxigraph's
    RDF/XML writer ends without a newline while its Turtle writer ends with
    one, and rdflib's Turtle writer ends with two.

    An empty graph stays an empty document rather than becoming a lone
    newline.
    """
    stripped = text.rstrip("\n")
    return stripped + "\n" if stripped else ""


def _deterministic_fallback_serialize(graph: rdflib.Graph, output_format: str) -> str:
    """Serialize a graph that pyoxigraph cannot canonicalize, deterministically.

    pyoxigraph rejects some graphs that rdflib accepts -- notably graphs
    containing relative IRIs or literal predicates (SHACL annotation mode).
    A plain ``graph.serialize()`` for such graphs is *not* reproducible
    across processes: rdflib assigns blank-node labels non-deterministically,
    so the structure and grouping of the output varies run to run.

    To degrade gracefully instead of silently emitting non-deterministic
    output, blank-node labels are canonicalized with rdflib's own
    isomorphism-based canonicalization (:func:`rdflib.compare.to_canonical_graph`,
    which uses a content-derived hash, not run-local ids) and the original
    prefix and base bindings that the canonical graph drops are restored.
    For line-oriented formats the serialized lines are additionally sorted.

    Relative IRIs are preserved verbatim (not resolved against the base):
    the goal is deterministic output, and silently rewriting them would
    mask what is really a data problem in the source graph.  The source
    graph's ``base`` is deliberately not carried across either -- rdflib
    relativizes against it by naive string prefixing, which corrupts terms
    under a hash base (see :func:`deterministic_turtle`).

    Turtle-family output is rendered without ``( … )`` collection syntax,
    because that syntax cannot express a list whose tail is referenced more
    than once and this path has no round-trip check to fall back on.

    :param graph: The rdflib Graph that pyoxigraph could not parse.
    :param output_format: Target serialization format (e.g. ``"turtle"``, ``"nt"``).
    :return: Deterministic string serialization of the graph.
    """
    if output_format.lower() in _LINE_ORIENTED_FORMATS:
        # rdflib's N-Triples serializer reuses Turtle's term rendering and does
        # not enforce the absolute-IRI rule, so it will happily write a
        # relative IRI that its own parser then rejects. Refusing here means a
        # caller gets an actionable error instead of a file that looks fine and
        # no parser will read.
        unwritable = _first_term_n_triples_cannot_write(graph)
        if unwritable is not None:
            position, term = unwritable
            raise ValueError(
                f"{output_format} cannot represent this graph: the {position} "
                f"{term!r} is not an absolute IRI, and N-Triples and N-Quads accept "
                "only absolute IRIs (N-Triples 1.1 section 2.2). Use turtle, trig, "
                "xml or json-ld, which can carry this graph, or make the term absolute."
            )
    if output_format.lower() in _JSON_FORMATS:
        # Expanded node objects preserve shared blank nodes and cycles. The
        # rdflib JSON-LD serializer may compact them into recursive @list
        # values, which cannot retain shared list-cell identity.
        return serialize_expanded_jsonld(to_canonical_graph(graph))
    if output_format.lower() in _COLLECTION_CAPABLE_FORMATS:
        canonicalized = to_canonical_graph(graph)
        # to_canonical_graph creates a Graph() with rdflib's built-in
        # namespaces. Copy its canonical triples into a namespace-empty graph
        # so only caller bindings and deterministic generated names can win.
        canonical = Graph(bind_namespaces="none")
        for triple in canonicalized:
            canonical.add(triple)
        prepare_namespaces(canonical, graph)
        # Imported here, not at module level: diffable_rdf.turtle imports this
        # module from inside deterministic_turtle, so importing it back at
        # module level here would create an import cycle. Deferring the
        # import to call time avoids that without either module needing to
        # know the other's internals.
        from .turtle import _NoCollectionTurtleSerializer

        buffer = io.BytesIO()
        _NoCollectionTurtleSerializer(canonical).serialize(buffer, encoding="utf-8")
        serialized = buffer.getvalue().decode("utf-8")
    else:
        # Copy into a clean single Graph, as the branch above does.
        # ``to_canonical_graph`` returns a ReadOnlyGraphAggregate -- a
        # ConjunctiveGraph subclass with a context-aware store and a fresh
        # random identifier per call. Handing that straight to rdflib's
        # serializers made some of them emit an empty document for a non-empty
        # graph (``hext`` did), and put a dataset container into a serializer
        # one function after ``_require_single_graph`` refused one at the door.
        canonical = Graph(bind_namespaces="none")
        for triple in to_canonical_graph(graph):
            canonical.add(triple)
        prepare_namespaces(canonical, graph)
        # This library accepts more aliases than rdflib registers plugins for
        # -- ``n-triples``, ``n-quads`` and ``rdf/xml`` are ours, not rdflib's,
        # and its lookup is exact. Translate every mapped alias to the name
        # rdflib knows, so two spellings of one format cannot behave
        # differently here the way they used to.
        ox_target = _FORMAT_MAP.get(output_format.lower())
        serializer_format = (
            _RDFLIB_SERIALIZER_NAMES.get(ox_target, output_format)
            if ox_target is not None
            else output_format
        )
        try:
            serialized = canonical.serialize(format=serializer_format)
        except PluginException:
            # rdflib's own "no such format" error, which the public contract
            # documents as propagating.
            raise
        except Exception as exc:
            raise ValueError(
                f"cannot serialize this graph as {output_format!r}: {exc}. This graph "
                "took the fallback path because pyoxigraph could not parse it, and "
                f"rdflib's {serializer_format!r} serializer cannot represent it either. "
                "turtle, ttl, trig and n3 can carry any graph that reaches this path."
            ) from exc
        if not serialized.strip() and len(canonical) > 0:
            # A delegated serializer that writes nothing for a non-empty graph
            # is silent total loss; refuse rather than return it.
            raise ValueError(
                f"rdflib's {serializer_format!r} serializer produced an empty document for a "
                f"graph of {len(canonical)} triples. Use turtle, ttl, trig or n3, which "
                "carry any graph that reaches the fallback path."
            )
    if output_format.lower() in _LINE_ORIENTED_FORMATS:
        # Split on newlines only, never with ``str.splitlines()``: that also
        # breaks on the Unicode line separators (U+2028, U+0085, U+000B and
        # friends) which N-Triples permits *raw* inside a quoted literal, so a
        # single statement became two "lines", they sorted independently, and
        # the separator was rewritten as a newline -- corrupting the value and
        # leaving a document that would not parse. rdflib escapes \n and \r,
        # so a bare newline can only be a statement boundary.
        lines = [line for line in serialized.split("\n") if line.strip()]
        return "\n".join(sorted(lines)) + "\n"
    return serialized


def _iri_terms(triples: list) -> set[str]:
    """Return the set of IRI strings appearing anywhere in ``triples``.

    Walks subjects, predicates, non-literal objects, and literal datatypes.
    Used to filter the prefix dict down to namespaces that are actually
    referenced by the canonicalized graph, so the output isn't padded with
    unused ``@prefix`` declarations.
    """
    iris: set[str] = set()
    for t in triples:
        for term in (t.subject, t.predicate, t.object):
            if isinstance(term, ox.NamedNode):
                iris.add(term.value)
            elif isinstance(term, ox.Literal):
                dt = term.datatype
                if dt is not None:
                    iris.add(dt.value)
    return iris


def _filter_prefixes_to_used(prefixes: dict[str, str], used_iris: set[str]) -> dict[str, str]:
    """Drop prefix bindings whose namespace is not a prefix of any used IRI.

    A prefix is kept if at least one IRI in ``used_iris`` starts with its
    namespace string. Parent-namespace matches are honored (e.g. a prefix
    bound to ``http://schema.org/`` is kept when ``http://schema.org/Person``
    appears in the graph).
    """
    return {prefix: ns for prefix, ns in prefixes.items() if any(iri.startswith(ns) for iri in used_iris)}


# Characters that may appear escaped in a Turtle PN_LOCAL via PN_LOCAL_ESC.
_PN_LOCAL_ESC_UNESCAPE = re.compile(r"\\([_~.\-!$&'()*+,;=/?#@%])")


def _turtle_string_spans(text: str) -> list[tuple[int, int]]:
    """Return half-open spans of the Turtle string literals in ``text``.

    Used to keep text rewrites out of literal content.  Turtle has four string
    forms: single- and triple-quoted, each with either quote character, and a
    backslash escapes the next character inside all of them.  IRIs need no
    handling: an IRIREF cannot contain an unescaped quote, so one can never
    open a span.
    """
    spans: list[tuple[int, int]] = []
    index = 0
    length = len(text)
    while index < length:
        character = text[index]
        if character not in ('"', "'"):
            index += 1
            continue
        delimiter = character * 3 if text[index : index + 3] == character * 3 else character
        start = index
        index += len(delimiter)
        while index < length:
            if text[index] == "\\":
                index += 2
                continue
            if text.startswith(delimiter, index):
                index += len(delimiter)
                break
            index += 1
        spans.append((start, index))
    return spans


def _expand_trailing_dot_curies(turtle_text: str, prefixes: dict[str, str]) -> str:
    """Replace CURIEs whose local part ends in ``\\.`` with full ``<IRI>`` form.

    rdflib's notation3 parser rejects PN_LOCAL ending in an escaped dot
    even though Turtle permits it (PN_LOCAL_ESC).  pyoxigraph emits this
    form for IRIs ending in ``.`` (e.g. ``biolink:StrandEnum#.``).  We
    rewrite each such CURIE to its expanded ``<IRI>`` form so the output
    round-trips through rdflib.

    The rewrite is applied only outside string literals.  A literal whose text
    happens to look like such a CURIE -- ``"ex:thing\\. "`` -- is ordinary RDF
    data, and rewriting inside it corrupted the value and produced output that
    would not parse.  Only the other IRIs in that namespace keep their prefix,
    so this stays more compact than dropping the prefix binding altogether.
    """
    if not prefixes:
        return turtle_text

    # Match: a prefix name, ':', a local part (no whitespace or token
    # delimiters), ending in ``\.``, followed by whitespace.  Use a
    # negative lookbehind to avoid matching inside ``<...>`` or word
    # characters that would make this a substring of something else.
    pattern = re.compile(
        r"(?<![<\w])"
        r"([A-Za-z_][\w.-]*?):"
        r"([^\s,;()<>\"'\[\]]*?\\\.)"
        r"(?=\s)"
    )

    def replace(match: re.Match[str]) -> str:
        prefix = match.group(1)
        local_escaped = match.group(2)
        namespace = prefixes.get(prefix)
        if namespace is None:
            return match.group(0)
        local = _PN_LOCAL_ESC_UNESCAPE.sub(r"\1", local_escaped)
        return f"<{namespace}{local}>"

    rewritten: list[str] = []
    cursor = 0
    for start, end in _turtle_string_spans(turtle_text):
        rewritten.append(pattern.sub(replace, turtle_text[cursor:start]))
        rewritten.append(turtle_text[start:end])
        cursor = end
    rewritten.append(pattern.sub(replace, turtle_text[cursor:]))
    return "".join(rewritten)


def _is_safe_prefix_iri(iri: str) -> bool:
    """Check whether a namespace IRI is safe for prefix serialization.

    Only one shape is actually unsafe: an IRI carrying a second ``#``, which
    pyoxigraph rejects as an invalid prefix IRI ("Invalid prefix … IRI",
    verified on 0.5.4 and 0.5.11).  Raising over a namespace binding the caller
    may not even know about would be a poor trade for a prefix declaration, so
    such a binding is skipped during prefix collection instead; a skipped
    prefix only means its IRIs are written in full.

    Query strings are *not* unsafe, despite an earlier claim that rdflib could
    not round-trip such CURIEs.  That does not reproduce on any supported
    version: ``@prefix n: <http://ex/?q=>`` with ``n:x``, and the harder
    ``<http://ex/a?b=c&d=>``, both round-trip exactly on rdflib 6.3.2 and
    7.6.0 with pyoxigraph 0.5.4 and 0.5.11.
    """
    # A namespace IRI should end with '/' or '#'.  If '#' appears
    # *before* the final character, the IRI contains an embedded
    # fragment which produces unusable CURIEs.
    return "#" not in iri[:-1]


def _assert_round_trips(source: rdflib.Graph, serialized: str, output_format: str) -> None:
    """Raise if ``serialized`` does not say the same thing as ``source``.

    A canonical form that does not round-trip is worse than none: it
    silently rewrites the graph.  This function compares RDFC-1.0 canonical
    forms, which is an exact isomorphism test, and is skipped when the
    source graph is not representable in pyoxigraph (the degraded path,
    which deliberately passes relative IRIs through verbatim and so cannot
    be compared this way).

    :param source: The graph that was serialized.
    :param serialized: The text produced for it.
    :param output_format: The rdflib format name, used for re-parsing.
    :raises ValueError: If the output does not round-trip.
    """
    from .turtle import _rdfc_canonical_form, _rdfc_canonical_text

    expected = _rdfc_canonical_form(source, ox)
    if expected is None:
        return
    ox_format = _FORMAT_MAP[output_format.lower()]
    rdflib_format = "xml" if ox_format == ox.RdfFormat.RDF_XML else output_format.lower()
    reparsed = rdflib.Graph()
    try:
        # rdflib's parser plugin lookup is case-sensitive ("Turtle" is not
        # registered, only "turtle" is), unlike every other format lookup in
        # this module (_FORMAT_MAP.get(output_format.lower()), and the
        # .lower() checks against _COLLECTION_CAPABLE_FORMATS,
        # _LINE_ORIENTED_FORMATS, _JSON_FORMATS). Normalise here so a
        # mixed-case alias that pyoxigraph accepted does not misreport a
        # plugin-name miss as a round-trip failure. The original spelling is
        # kept in the messages below, since that is what the caller passed.
        reparsed.parse(data=serialized, format=rdflib_format)
    except Exception as exc:
        raise ValueError(
            f"canonical {output_format} serialization does not parse back "
            f"({type(exc).__name__}: {exc}). This is a bug in diffable-rdf: "
            "please report it with the input graph."
        ) from exc
    # rdflib parsing above is an interoperability check only. It normalizes
    # numeric lexical forms, so use pyoxigraph's parsed terms for the exact
    # identity comparison.
    try:
        actual = _rdfc_canonical_text(serialized, ox_format, ox)
    except SyntaxError as exc:
        raise ValueError(
            f"canonical {output_format} serialization does not parse back "
            f"({type(exc).__name__}: {exc}). This is a bug in diffable-rdf: "
            "please report it with the input graph."
        ) from exc
    if actual != expected:
        raise ValueError(
            f"canonical {output_format} serialization does not round-trip; "
            f"{len(source)} triples in, {len(reparsed)} out. This is a bug in "
            "diffable-rdf: please report it with the input graph."
        )


def canonicalize_rdf_graph(
    graph: rdflib.Graph,
    output_format: str = "turtle",
) -> str:
    """Serialize an rdflib Graph deterministically using RDFC-1.0 canonicalization.

    The graph is transferred to pyoxigraph via N-Triples, canonicalized
    with RDFC-1.0, sorted, and serialized back to the requested format.
    Prefix bindings from the rdflib Graph are preserved in the output
    for formats that support them (Turtle, TriG, N3, RDF/XML).

    The deterministic-output guarantee covers the format names this function
    maps itself: ``turtle``/``ttl``, ``nt``/``ntriples``/``n-triples``/``nt11``,
    ``nquads``/``n-quads``, ``xml``/``rdf/xml``, ``trig``, ``n3``, and
    ``json-ld``/``jsonld``/``application/ld+json``. For those, isomorphic
    inputs serialize to identical bytes in any process.

    Any other name is delegated to rdflib's serializer plugins with a logged
    warning, and carries **no** determinism or round-trip guarantee: several
    rdflib serializers order their output by a graph traversal whose result
    depends on set iteration order, so the same graph can produce different
    bytes in different processes. An unregistered name raises
    ``rdflib.plugin.PluginException`` from rdflib.

    Graphs containing terms pyoxigraph cannot parse take a deterministic
    rdflib-based fallback. Degraded JSON-LD preserves relative subject and
    object IRIs verbatim, while term positions outside its interoperable
    standard-RDF subset raise ``ValueError``.

    :param graph: A single rdflib Graph to serialize. Dataset and
        ConjunctiveGraph containers are not supported; select an individual
        graph context.
    :param output_format: Target serialization format (e.g. ``"turtle"``, ``"nt"``).
    :return: Deterministic string serialization of the graph.
    :raises TypeError: If ``graph`` is a Dataset or ConjunctiveGraph container.
    """
    _require_single_graph(graph)

    ox_format = _FORMAT_MAP.get(output_format.lower())
    if ox_format is None:
        logger.warning(
            "%r is not one of the formats this library serializes itself; delegating to "
            "rdflib's serializer plugins. Deterministic output and round-trip verification "
            "are not guaranteed for it: some rdflib serializers order their output by graph "
            "traversal, which varies between processes.",
            output_format,
        )
        # The fallback still canonicalizes blank-node labels and sorts
        # line-oriented and JSON output, so a delegated format is as stable as
        # this library can make it without reimplementing someone else's
        # serializer. What it cannot fix is a plugin whose *traversal* order
        # varies; see the guarantee wording in the docstring above.
        return _with_single_trailing_newline(
            _deterministic_fallback_serialize(graph, output_format)
        )

    if ox_format == ox.RdfFormat.RDF_XML:
        _assert_xml_10_representable(graph)

    # 1. Transfer rdflib graph to pyoxigraph via N-Triples.
    nt_data = graph.serialize(format="nt")
    nt_bytes = nt_data.encode("utf-8") if isinstance(nt_data, str) else nt_data

    # 2. Parse into pyoxigraph and build a Dataset for canonicalization.
    #    Fall back to rdflib if the graph contains non-standard RDF
    #    (e.g. literal predicates from annotations) that pyoxigraph rejects.
    try:
        triples = list(ox.parse(io.BytesIO(nt_bytes), format=ox.RdfFormat.N_TRIPLES))
    except SyntaxError:
        logger.warning(
            "Graph contains non-standard RDF (e.g. relative IRIs or literal predicates) "
            "that pyoxigraph cannot parse; falling back to rdflib. Output is still "
            "deterministic (blank-node labels are canonicalized via rdflib) but is not "
            "canonicalized with pyoxigraph RDFC-1.0."
        )
        result = _deterministic_fallback_serialize(graph, output_format)
        if ox_format == ox.RdfFormat.RDF_XML:
            # Sort before protecting the CRs: the sort re-serializes the tree,
            # which would undo a character reference written earlier.
            result = _finalize_rdf_xml(_sort_rdf_xml_descriptions(result))
        return _with_single_trailing_newline(result)

    dataset = ox.Dataset()
    for triple in triples:
        dataset.add(ox.Quad(triple.subject, triple.predicate, triple.object, ox.DefaultGraph()))

    # 3. Canonicalize blank node labels with RDFC-1.0.
    dataset.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)

    # 4. Sort triples for deterministic ordering.
    quads = list(dataset)
    sorted_triples = sorted(
        (ox.Triple(q.subject, q.predicate, q.object) for q in quads),
        key=lambda t: (str(t.subject), str(t.predicate), str(t.object)),
    )

    # 5. Collect prefixes for formats that support them.
    base_iri = str(graph.base) if graph.base else None
    prefixes: dict[str, str] | None = None
    if ox_format in _PREFIX_FORMATS:
        prefixes = {}
        for prefix, namespace in graph.namespace_manager.namespaces():
            if not prefix:  # skip empty prefix (base)
                continue
            ns_str = str(namespace)
            # Skip prefixes whose namespace matches the base IRI to avoid
            # pyoxigraph emitting CURIEs like `base:label` that conflict
            # with the @base directive.
            if base_iri and ns_str == base_iri:
                continue
            # Skip namespace IRIs that pyoxigraph rejects or that produce
            # CURIEs rdflib cannot round-trip.  Valid namespace IRIs for
            # prefix use should end with '/' or '#' and contain no query
            # parameters or fragment-like characters in the middle.
            if not _is_safe_prefix_iri(ns_str):
                continue
            prefixes[str(prefix)] = ns_str
        # Drop prefix bindings whose namespace is not referenced by any IRI
        # in the graph. This prevents the rdflib NamespaceManager's default
        # bindings (~30 well-known vocabularies) from being emitted into
        # every output file regardless of whether the graph actually uses
        # them.
        prefixes = _filter_prefixes_to_used(prefixes, _iri_terms(sorted_triples))
    used_prefixes = prefixes
    try:
        result_bytes = ox.serialize(
            sorted_triples,
            format=ox_format,
            prefixes=prefixes,
            base_iri=base_iri,
        )
    except ValueError as e:
        # pyoxigraph 0.5.x reports a rejected prefix IRI with a message that
        # begins with "Invalid prefix", and a rejected base IRI with one that
        # begins with "Invalid base IRI" (both verified empirically). A
        # relative base is legal in rdflib, so both cases must degrade
        # gracefully by retrying without them. Any *other* ValueError (an
        # unrelated future serializer bug) must propagate so it surfaces as a
        # stack trace rather than silently dropping all prefix declarations.
        message = str(e)
        if not message.startswith(("Invalid prefix", "Invalid base IRI")):
            raise
        logger.warning("pyoxigraph rejected the prefix or base IRIs (%s); serializing without them", message)
        result_bytes = ox.serialize(
            sorted_triples,
            format=ox_format,
        )
        used_prefixes = None
    # pyoxigraph's serialize() stub is a single flat `-> bytes | None` with no
    # overload distinguishing output=None (returns bytes) from output=<stream>
    # (returns None). Neither call above passes output=, so this is always bytes.
    result = result_bytes.decode("utf-8")  # type: ignore[union-attr]
    if ox_format == ox.RdfFormat.RDF_XML:
        result = _finalize_rdf_xml(result)
    if ox_format == ox.RdfFormat.JSON_LD:
        # pyoxigraph emits compact single-line JSON; re-render it indented so
        # the output is diffable line by line, which is the point of this
        # library. Safe to route through deterministic_json: pyoxigraph writes
        # *expanded* JSON-LD, so there is no @context or @list array whose
        # order carries meaning, and the triples were already sorted above.
        result = deterministic_json(json.loads(result)) + "\n"
    if ox_format in _TURTLE_FAMILY_FORMATS and used_prefixes:
        result = _expand_trailing_dot_curies(result, used_prefixes)
    if ox_format in _VERIFIED_FORMATS:
        _assert_round_trips(graph, result, output_format)
    return _with_single_trailing_newline(result)
