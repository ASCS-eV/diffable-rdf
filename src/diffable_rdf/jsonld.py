"""Deterministic JSON / JSON-LD serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass

# JSON-LD keys whose array values carry ordering semantics and must NOT be
# sorted.  ``@context`` arrays define an override cascade (JSON-LD 1.1 §4.1);
# ``@list`` containers are explicitly ordered; ``@graph``/``@set`` and
# ``imports`` are included defensively.
_JSONLD_ORDERED_KEYS: frozenset[str] = frozenset({"@context", "@list", "@graph", "@set", "imports"})
_JSONLD_KEYWORDS: frozenset[str] = frozenset(
    {
        "@context",
        "@graph",
        "@id",
        "@index",
        "@json",
        "@language",
        "@list",
        "@nest",
        "@none",
        "@reverse",
        "@set",
        "@type",
        "@value",
        "@vocab",
    }
)


@dataclass(frozen=True)
class _LocalContext:
    """The ordering facts that can be learned without JSON-LD expansion."""

    keyword_aliases: dict[str, str]
    json_terms: frozenset[str]
    list_terms: frozenset[str]
    unknown: bool = False


_EMPTY_CONTEXT = _LocalContext({}, frozenset(), frozenset())


def _resolve_keyword(value: object, context: _LocalContext) -> str | None:
    if not isinstance(value, str):
        return None
    if value in _JSONLD_KEYWORDS:
        return value
    return context.keyword_aliases.get(value)


def _without_term(context: _LocalContext, term: str) -> _LocalContext:
    aliases = dict(context.keyword_aliases)
    aliases.pop(term, None)
    return _LocalContext(
        aliases,
        context.json_terms - {term},
        context.list_terms - {term},
        context.unknown,
    )


def _with_unknown(context: _LocalContext) -> _LocalContext:
    return _LocalContext(
        dict(context.keyword_aliases),
        context.json_terms,
        context.list_terms,
        True,
    )


def _apply_local_context(value: object, active: _LocalContext) -> _LocalContext:
    """Extract ordering facts from local contexts, failing safe otherwise.

    This is deliberately not a JSON-LD context processor. Remote contexts,
    imports, scoped contexts, and definitions whose ordering semantics cannot
    be identified locally are marked unknown so their arrays remain untouched.
    """
    if value is None:
        return _EMPTY_CONTEXT
    if isinstance(value, list):
        result = active
        for entry in value:
            result = _apply_local_context(entry, result)
        return result
    if not isinstance(value, dict):
        return _with_unknown(active)

    result = active
    if any(key in {"@import", "@propagate", "@protected"} for key in value):
        result = _with_unknown(result)

    for raw_term, definition in value.items():
        if not isinstance(raw_term, str) or raw_term.startswith("@"):
            continue

        result = _without_term(result, raw_term)
        aliases = dict(result.keyword_aliases)
        json_terms = result.json_terms
        list_terms = result.list_terms

        if definition is None:
            continue
        if isinstance(definition, str):
            keyword = _resolve_keyword(definition, result)
            if keyword is not None:
                aliases[raw_term] = keyword
                if keyword == "@list":
                    list_terms |= {raw_term}
            result = _LocalContext(aliases, json_terms, list_terms, result.unknown)
            continue
        if not isinstance(definition, dict):
            result = _with_unknown(result)
            continue

        if not set(definition).issubset({"@id", "@type", "@container"}):
            result = _with_unknown(result)

        identifier = definition.get("@id")
        keyword = _resolve_keyword(identifier, result)
        if keyword is not None:
            aliases[raw_term] = keyword
            if keyword == "@list":
                list_terms |= {raw_term}

        type_mapping = _resolve_keyword(definition.get("@type"), result)
        if type_mapping == "@json":
            json_terms |= {raw_term}

        container = definition.get("@container")
        containers = container if isinstance(container, list) else [container]
        if "@list" in containers:
            list_terms |= {raw_term}

        if identifier is not None and not isinstance(identifier, str):
            result = _with_unknown(result)
        if "@type" in definition and not isinstance(definition["@type"], str):
            result = _with_unknown(result)
        if "@container" in definition and not isinstance(container, (str, list)):
            result = _with_unknown(result)

        result = _LocalContext(aliases, json_terms, list_terms, result.unknown)

    return result


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

    Recursively sorts dict keys and unordered list elements to produce stable
    output across Python versions and process invocations. JSON-LD arrays with
    ordering semantics are retained, including ``@list`` values, ``@json``
    literal payloads, and properties declared with ``@container: @list`` or
    ``@type: @json`` in a local context.

    List elements are sorted by their canonical JSON representation
    (``json.dumps(item, sort_keys=True)``), which handles lists of dicts,
    strings, and mixed types.

    :param obj: A JSON-serializable object.
    :param indent: Number of spaces for indentation.
    Local context arrays are applied in order and inherited by nested objects;
    a null context resets them. Remote, imported, scoped, or unsupported
    contexts are never loaded. Once such a context can affect a value, all
    descendant arrays are conservatively retained, even if the data contains
    ``@context: null``. This helper does not perform full JSON-LD context
    processing.

    :param preserve_list_order_keys: Dict keys whose list values must not be
        sorted. Defaults to the legacy set of JSON-LD ordered keys. Semantic
        ``@list`` and ``@json`` protections apply independently.
    :returns: Deterministic JSON string.
    """
    skip = preserve_list_order_keys if preserve_list_order_keys is not None else _JSONLD_ORDERED_KEYS

    def _deep_sort(
        value: object,
        context: _LocalContext = _EMPTY_CONTEXT,
        preserve_current_list: bool = False,
        preserve_descendant_lists: bool = False,
    ) -> object:
        if isinstance(value, dict):
            # Once an unresolved context can affect this value, a nested
            # ``@context: null`` may itself be data in an unknown ``@json``
            # property. Keep the conservative safeguard for the whole value.
            preserve_descendant_lists = preserve_descendant_lists or context.unknown
            local_context = context
            if not preserve_descendant_lists and "@context" in value:
                local_context = _apply_local_context(value["@context"], context)
            preserve_descendant_lists = preserve_descendant_lists or local_context.unknown

            value_keyword_keys = {
                k for k in value if isinstance(k, str) and _resolve_keyword(k, local_context) == "@value"
            }
            type_values = [
                v
                for k, v in value.items()
                if isinstance(k, str) and _resolve_keyword(k, local_context) == "@type"
            ]
            json_value_keys = (
                value_keyword_keys
                if any(_resolve_keyword(type_value, local_context) == "@json" for type_value in type_values)
                else set()
            )

            # Sort on the key's JSON-encoded name, not the raw key. json.dumps
            # coerces non-string keys (int, float, bool, None) to strings, so
            # sorting the raw keys would raise TypeError on any mix of types
            # -- rejecting input that the stdlib serializes happily.
            return {
                k: _deep_sort(
                    v,
                    local_context,
                    preserve_current_list=(
                        isinstance(k, str)
                        and (
                            k in skip
                            or _resolve_keyword(k, local_context) in _JSONLD_ORDERED_KEYS
                            or k in local_context.json_terms
                            or k in local_context.list_terms
                        )
                    ),
                    preserve_descendant_lists=(
                        preserve_descendant_lists
                        or (isinstance(k, str) and k in local_context.json_terms)
                        or k in json_value_keys
                    ),
                )
                for k, v in sorted(value.items(), key=lambda kv: _json_key(kv[0]))
            }
        if isinstance(value, list):
            sorted_items = [
                _deep_sort(item, context, preserve_descendant_lists=preserve_descendant_lists) for item in value
            ]
            if preserve_current_list or preserve_descendant_lists or context.unknown:
                return sorted_items
            try:
                return sorted(sorted_items, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
            except TypeError:
                return sorted_items
        return value

    return json.dumps(_deep_sort(obj), indent=indent, ensure_ascii=False)
