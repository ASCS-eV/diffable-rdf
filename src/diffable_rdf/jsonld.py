"""Deterministic JSON / JSON-LD serialization (recursive key + list sort)."""

from __future__ import annotations

import json

# JSON-LD keys whose array values carry ordering semantics and must NOT be
# sorted.  ``@context`` arrays define an override cascade (JSON-LD 1.1 §4.1);
# ``@list`` containers are explicitly ordered; ``@graph``/``@set`` and
# ``imports`` are included defensively.
_JSONLD_ORDERED_KEYS: frozenset[str] = frozenset({"@context", "@list", "@graph", "@set", "imports"})


def _json_key(key: object) -> str:
    """Return the string ``json.dumps`` will use for a dict key.

    ``json.dumps`` coerces ``int``/``float``/``bool``/``None`` keys to
    strings, so sorting must happen on that coerced form to stay both
    total (no ``TypeError`` on mixed key types) and consistent with the
    emitted output.
    """
    if isinstance(key, str):
        return key
    if key is None:
        return "null"
    if key is True:
        return "true"
    if key is False:
        return "false"
    return str(key)


def deterministic_json(
    obj: object,
    indent: int = 3,
    preserve_list_order_keys: frozenset[str] | None = None,
) -> str:
    """Serialize a JSON-compatible object with deterministic ordering.

    Recursively sorts all dict keys *and* list elements to produce stable
    output across Python versions and process invocations.

    List elements are sorted by their canonical JSON representation
    (``json.dumps(item, sort_keys=True)``), which handles lists of dicts,
    strings, and mixed types.

    :param obj: A JSON-serializable object.
    :param indent: Number of spaces for indentation.
    :param preserve_list_order_keys: Dict keys whose list values must NOT be
        sorted (e.g. ``@context``, ``@list`` in JSON-LD where array order is
        semantic).  Defaults to :data:`_JSONLD_ORDERED_KEYS`.
    :returns: Deterministic JSON string.
    """
    skip = preserve_list_order_keys if preserve_list_order_keys is not None else _JSONLD_ORDERED_KEYS

    def _deep_sort(value: object, parent_key: str = "") -> object:
        if isinstance(value, dict):
            # Sort on the key's JSON-encoded name, not the raw key. json.dumps
            # coerces non-string keys (int, float, bool, None) to strings, so
            # sorting the raw keys would raise TypeError on any mix of types
            # -- rejecting input that the stdlib serializes happily.
            return {
                k: _deep_sort(v, parent_key=k if isinstance(k, str) else "")
                for k, v in sorted(value.items(), key=lambda kv: _json_key(kv[0]))
            }
        if isinstance(value, list):
            sorted_items = [_deep_sort(item) for item in value]
            if parent_key in skip:
                return sorted_items
            try:
                return sorted(sorted_items, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
            except TypeError:
                return sorted_items
        return value

    return json.dumps(_deep_sort(obj), indent=indent, ensure_ascii=False)
