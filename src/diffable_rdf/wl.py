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
exposed separately so that tools which already run RDFC-1.0 themselves
(for example the LinkML generators) can add diff stability as a single
extra step without replacing their own serialization pipeline.

References
----------
.. [1] W3C (2024). "RDF Dataset Canonicalization (RDFC-1.0)."
   W3C Recommendation.  https://www.w3.org/TR/rdf-canon/
.. [2] Weisfeiler, B. & Leman, A. (1968). "The reduction of a graph to
   canonical form and the algebra which appears therein."
"""

from __future__ import annotations

import hashlib

import pyoxigraph

__all__ = ["wl_blank_node_labels", "wl_relabel_quads"]


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
        until the partition stops changing (the WL fixpoint), which
        yields the most diff-stable labelling; pass an explicit integer
        to force exactly that many rounds.

    Returns
    -------
    dict[str, str]
        Mapping from canonical blank-node ID (e.g. ``c14n42``) to a
        truncated SHA-256 hash suitable for use as a stable blank-node
        label (e.g. ``b1f3a9c0d2e4``).

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
    """
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

        # A blank node used as a graph name must be relabelled consistently
        # with its uses as a term, otherwise one node is split into two.
        if isinstance(q.graph_name, pyoxigraph.BlankNode):
            bnode_ids.add(q.graph_name.value)

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
    #
    # Each round's signature is hashed to a fixed width.  Refinement folds
    # every neighbour's signature into a node's own, so leaving the
    # signatures unhashed makes their length grow multiplicatively with
    # degree each round and exhausts memory on real data.  Hashing induces
    # the identical partition (see the module tests) at constant size.
    #
    # WL refinement is monotone: a node's new signature always embeds its
    # previous one, so the partition can only get finer and the number of
    # distinct signatures never decreases.  Once that count stops growing
    # the partition is stable and further rounds cannot change it, so the
    # fixpoint is both the cheapest and the most diff-stable stopping
    # point.  A partition of n nodes can refine at most n times, which
    # bounds the loop even for adversarial input.
    max_rounds = len(bnode_ids) if iterations is None else iterations
    previous_classes = len(set(sig.values()))
    for _ in range(max_rounds):
        new_sig: dict[str, str] = {}
        for bid in bnode_ids:
            parts = [sig[bid]]
            for p_str, o_str, o_is_bn in outgoing.get(bid, []):
                if o_is_bn:
                    parts.append(f"+{p_str}={sig.get(o_str, '')}")
            for s_str, p_str, s_is_bn in incoming.get(bid, []):
                if s_is_bn:
                    parts.append(f"-{sig.get(s_str, '')}={p_str}")
            new_sig[bid] = hashlib.sha256("|".join(sorted(parts)).encode("utf-8")).hexdigest()
        sig = new_sig
        if iterations is None:
            classes = len(set(sig.values()))
            if classes == previous_classes:
                break
            previous_classes = classes

    # Convert signatures to truncated SHA-256 hashes.
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
