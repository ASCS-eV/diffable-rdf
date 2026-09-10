"""Weisfeiler-Lehman blank-node labelling for diff-stable RDF output.

RDFC-1.0 [1]_ makes blank-node labels *deterministic* but not *diff
stable*: it numbers blank nodes with a sequential ``c14nN`` counter, so
inserting a single triple can renumber every blank node after it and
rewrite large parts of an otherwise unchanged file.

This module assigns each blank node a label derived from a
Weisfeiler-Lehman [2]_ hash of its own neighbourhood, so a label only
changes when that node's surroundings change.  Adding or removing a
triple then rewrites only the lines it actually touches.

The functions here operate on **already-canonicalized** pyoxigraph quads.
They are the composable primitive behind :func:`diffable_rdf.deterministic_turtle`,
exposed separately so that a pipeline which already runs RDFC-1.0 itself can
add diff stability as a single extra step, keeping its own serialization,
prefix handling and base IRI.

References
----------
.. [1] W3C (2024). "RDF Dataset Canonicalization." W3C Recommendation,
   21 May 2024.  Defines the RDFC-1.0 algorithm.
   https://www.w3.org/TR/rdf-canon/
.. [2] Weisfeiler, B. & Leman, A. (1968). "The reduction of a graph to
   canonical form and the algebra which appears therein."
"""

from __future__ import annotations

import hashlib
import re

import pyoxigraph

__all__ = ["wl_blank_node_labels", "wl_relabel_quads"]


def _numbering_order_key(identifier: str) -> tuple[tuple[int, int, str], ...]:
    """Sort blank-node identifiers the way their numbering reads.

    RDFC-1.0 names blank nodes ``c14n0``, ``c14n1``, ... and this module's
    input is canonical quads, so a plain lexicographic sort puts ``c14n10``
    between ``c14n1`` and ``c14n2``.  The collision counter is assigned in
    this order, so from ten blank nodes onwards the suffixes stopped following
    the canonical numbering -- and inserting one node then shifted the suffix
    of every tied node after its lexicographic position: adding ``c14n10`` to
    ten tied nodes relabelled eight of them, for a change that should have
    added one label and moved none.

    Digit runs compare numerically and the run's own text breaks a tie between
    two spellings of the same number, so the order is total for any input,
    including identifiers this module did not choose.
    """
    return tuple(
        (1, int(part), part) if part.isdigit() else (0, 0, part) for part in re.split(r"(\d+)", identifier)
    )


def wl_blank_node_labels(
    quads: list,
    iterations: int | None = None,
) -> dict[str, str]:
    """Compute diff-stable blank-node labels via Weisfeiler-Lehman refinement.

    Uses 1-dimensional WL colour refinement to assign each blank node a
    deterministic signature derived from its multi-hop neighbourhood
    structure.  The signature depends only on predicate IRIs, literal
    values, and named-node IRIs — **not** on blank-node identifiers — so
    it remains stable when unrelated triples are added or removed.

    Parameters
    ----------
    quads : list
        Canonical quads from pyoxigraph (i.e. after RDFC-1.0).
    iterations : int | None
        Number of WL refinement rounds.  The default (``None``) refines
        each connected blank-node component until its partition stops
        changing (the WL fixpoint), which yields the most diff-stable
        labelling.  A non-negative integer forces exactly that many rounds
        across the whole dataset; ``0`` is a meaningful request for no
        refinement, leaving each label derived from its named-node edges
        alone.  A negative count is rejected.

    Returns
    -------
    dict[str, str]
        Mapping from canonical blank-node ID (e.g. ``c14n42``) to a
        truncated SHA-256 hash suitable for use as a stable blank-node
        label (e.g. ``b1f3a9c0d2e4``).

    Raises
    ------
    ValueError
        If ``iterations`` is negative.  ``range`` treats a negative count as
        zero, so such a call used to be accepted and return labels refined for
        no rounds at all -- plausible-looking, stable across processes, and
        less diff-stable than the caller believed, with nothing to say so.

    Notes
    -----
    Each round's signature is hashed before being fed into the next
    round.  This is load-bearing: signatures are built by concatenating a
    node's own signature with those of all its neighbours, so without the
    per-round hash their length grows by roughly a factor of the average
    degree every round (measured ~2.7x/round on OWL-restriction-shaped
    data), exhausting memory within ~10 rounds.  Hashing bounds each
    signature to a constant size while inducing exactly the same
    partition of the blank nodes.

    Labels use 12 hex chars (48 bits); the birthday-bound collision
    probability is ~n²/2^49 (~0.002% at 100k nodes).  Genuine collisions
    — and structurally indistinguishable nodes, which legitimately share
    a signature — are disambiguated by appending a counter, so the
    mapping is always injective.

    A quad's graph is part of its contribution to a signature, so the same
    structure in two different named graphs receives different labels and
    moving a triple between graphs relabels the nodes involved.  The default
    graph contributes no graph term, so a dataset with no named graphs is
    labelled from its triples alone.  A blank node used *as* a graph name is
    labelled from the quads it names, which distinguishes it from other
    graph-name nodes.

    One case remains unresolved by design: two graphs *named by blank
    nodes* whose contents are structurally identical still yield tied
    signatures for the nodes inside them, because a blank-node graph name
    collapses to a constant rather than to its own signature (a blank
    node's identifier must never enter a signature).  Such ties are broken
    by the collision counter in ``c14nN`` order -- numerically, so ``c14n2``
    precedes ``c14n10`` -- exactly as for genuinely indistinguishable nodes.
    """
    if iterations is not None and iterations < 0:
        raise ValueError(
            f"iterations must be None or a non-negative integer, got {iterations!r}. "
            "Pass None to refine each component to its fixpoint, which is the most "
            "diff-stable labelling, or 0 for no refinement."
        )

    # Collect all blank node IDs and build adjacency index.
    bnode_ids: set[str] = set()
    # outgoing[b] = list of (predicate_str, object_str_or_bnode_id, graph_tag, is_bnode)
    outgoing: dict[str, list[tuple[str, str, str, bool]]] = {}
    # incoming[b] = list of (subject_str_or_bnode_id, predicate_str, graph_tag, is_bnode)
    incoming: dict[str, list[tuple[str, str, str, bool]]] = {}
    # naming[b] = signature fragments for the quads that blank node b names
    naming: dict[str, list[str]] = {}
    # Neighbours whose previous-round signatures feed each other's next
    # signature. Named nodes are stable anchors, not paths between blank-node
    # regions. Blank graph names also stay local: graph tags and naming
    # fragments deliberately contain only a constant marker for blank nodes.
    neighbours: dict[str, set[str]] = {}

    def graph_tag(graph_name) -> str:
        """A stable, blank-node-free key for the graph a quad lives in.

        The empty string for the default graph, so a dataset with no named
        graphs is labelled from its triples alone and its signatures do not
        depend on graph handling at all.  A blank-node graph name collapses
        to a constant, because a blank node's own identifier must never
        enter a signature.
        """
        if isinstance(graph_name, pyoxigraph.DefaultGraph):
            return ""
        if isinstance(graph_name, pyoxigraph.BlankNode):
            return "_:"
        return str(graph_name)

    for q in quads:
        s, p, o = q.subject, q.predicate, q.object
        s_is_bn = isinstance(s, pyoxigraph.BlankNode)
        o_is_bn = isinstance(o, pyoxigraph.BlankNode)
        p_str = str(p)
        tag = graph_tag(q.graph_name)

        # A blank node used as a graph name must be relabelled consistently
        # with its uses as a term, otherwise one node is split into two.  It
        # also needs a signature of its own: derived from the quads it names,
        # since it may appear nowhere else and would otherwise hash to the
        # empty string along with every other graph-name node.
        if isinstance(q.graph_name, pyoxigraph.BlankNode):
            bnode_ids.add(q.graph_name.value)
            naming.setdefault(q.graph_name.value, []).append(
                f"~{'_:' if s_is_bn else str(s)}={p_str}={'_:' if o_is_bn else str(o)}"
            )

        if s_is_bn:
            bnode_ids.add(s.value)
            outgoing.setdefault(s.value, []).append((p_str, o.value if o_is_bn else str(o), tag, o_is_bn))
        if o_is_bn:
            bnode_ids.add(o.value)
            incoming.setdefault(o.value, []).append((s.value if s_is_bn else str(s), p_str, tag, s_is_bn))
        if s_is_bn and o_is_bn:
            neighbours.setdefault(s.value, set()).add(o.value)
            neighbours.setdefault(o.value, set()).add(s.value)

    def edge(direction: str, label: str, value: str, tag: str) -> str:
        """One signature fragment, carrying the graph tag only when there is one."""
        return f"{direction}{label}@{tag}={value}" if tag else f"{direction}{label}={value}"

    # Initialise signatures: named-node edges only (no bnode IDs).
    sig: dict[str, str] = {}
    for bid in bnode_ids:
        parts = []
        for p_str, o_str, tag, o_is_bn in outgoing.get(bid, []):
            if not o_is_bn:
                parts.append(edge("+", p_str, o_str, tag))
        for s_str, p_str, tag, s_is_bn in incoming.get(bid, []):
            if not s_is_bn:
                parts.append(edge("-", s_str, p_str, tag))
        parts.extend(naming.get(bid, []))
        sig[bid] = "|".join(sorted(parts))

    # Iterative refinement: incorporate neighbour signatures.
    #
    # Each round's signature is hashed to a fixed width.  Refinement folds
    # every neighbour's signature into a node's own, so leaving the
    # signatures unhashed makes their length grow multiplicatively with
    # degree each round and exhausts memory on real data.  Hashing induces
    # the identical partition (see the module tests) at constant size.
    #
    # WL refinement is monotone: a node's new signature always embeds its
    # previous one, so a component's partition can only get finer. Once its
    # number of classes stops growing, further rounds cannot change that
    # partition. Refining components independently prevents a deep unrelated
    # component from repeatedly rehashing one whose partition is already
    # stable. A component of n nodes can refine at most n times, which also
    # provides a finite bound for adversarial input.
    def refine(component: set[str], rounds: int, stop_at_fixpoint: bool) -> None:
        previous_classes = len({sig[bid] for bid in component})
        for _ in range(rounds):
            # Build every new value from the same previous-round mapping.
            # Updating sig only after this loop keeps refinement synchronous.
            new_sig: dict[str, str] = {}
            for bid in component:
                parts = [sig[bid]]
                for p_str, o_str, tag, o_is_bn in outgoing.get(bid, []):
                    if o_is_bn:
                        parts.append(edge("+", p_str, sig.get(o_str, ""), tag))
                for s_str, p_str, tag, s_is_bn in incoming.get(bid, []):
                    if s_is_bn:
                        parts.append(edge("-", sig.get(s_str, ""), p_str, tag))
                new_sig[bid] = hashlib.sha256(
                    "|".join(sorted(parts)).encode("utf-8")
                ).hexdigest()
            sig.update(new_sig)
            if stop_at_fixpoint:
                classes = len(set(new_sig.values()))
                if classes == previous_classes:
                    break
                previous_classes = classes

    if iterations is not None:
        # An explicit count means exactly that: every blank node is refined
        # synchronously for the requested number of rounds, with no
        # per-component fixpoint check. Zero refines nothing, leaving each
        # label derived from its named-node edges; negative counts are
        # rejected above rather than silently behaving like zero.
        refine(bnode_ids, iterations, stop_at_fixpoint=False)
    else:
        visited: set[str] = set()
        # One seed pass keeps discovery linear even when every node is an
        # isolated component. Components refine independently -- a component's
        # neighbours are all inside it -- and collision suffixes are assigned
        # globally below, so component order cannot affect the result. Seeding
        # in a fixed order rather than in set-iteration order costs nothing
        # and makes that independent of the process hash seed by construction
        # instead of by argument.
        for seed in sorted(bnode_ids, key=_numbering_order_key):
            if seed in visited:
                continue
            component: set[str] = set()
            pending = [seed]
            while pending:
                bid = pending.pop()
                if bid in visited:
                    continue
                visited.add(bid)
                component.add(bid)
                pending.extend(neighbours.get(bid, set()) - visited)
            refine(component, len(component), stop_at_fixpoint=True)

    # Convert signatures to truncated SHA-256 hashes.
    hash_map: dict[str, str] = {}
    seen_hashes: dict[str, int] = {}
    for bid in sorted(bnode_ids, key=_numbering_order_key):
        digest = hashlib.sha256(sig[bid].encode("utf-8")).hexdigest()[:12]
        # Handle collisions by appending a counter.
        count = seen_hashes.get(digest, 0)
        seen_hashes[digest] = count + 1
        label = f"b{digest}" if count == 0 else f"b{digest}_{count}"
        hash_map[bid] = label

    return hash_map


def wl_relabel_quads(
    quads: list,
    iterations: int | None = None,
) -> list:
    """Rewrite canonical quads with diff-stable blank-node labels.

    Convenience wrapper around :func:`wl_blank_node_labels` that applies
    the computed labels, so callers with an existing serialization
    pipeline can gain diff stability by inserting a single step between
    RDFC-1.0 canonicalization and serialization::

        dataset.canonicalize(CanonicalizationAlgorithm.RDFC_1_0)
        quads = wl_relabel_quads(list(dataset))

    Parameters
    ----------
    quads : list
        Canonical quads from pyoxigraph (i.e. after RDFC-1.0).
    iterations : int | None
        Number of WL refinement rounds; ``None`` (the default) refines to
        the WL fixpoint.  See :func:`wl_blank_node_labels`.

    Returns
    -------
    list
        New quads with every blank node relabelled, including blank nodes
        used as graph names, so the result is isomorphic to the input.
    """
    labels = wl_blank_node_labels(quads, iterations=iterations)

    def remap(term):
        if isinstance(term, pyoxigraph.BlankNode) and term.value in labels:
            return pyoxigraph.BlankNode(labels[term.value])
        return term

    return [
        pyoxigraph.Quad(remap(q.subject), q.predicate, remap(q.object), remap(q.graph_name))
        for q in quads
    ]
