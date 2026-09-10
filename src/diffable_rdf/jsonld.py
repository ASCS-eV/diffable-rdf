"""Deterministic JSON / JSON-LD serialization."""

from __future__ import annotations

import json
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

# The JSON-LD keywords whose array values genuinely carry order, and so must
# never be sorted.  An ``@context`` array is processed in order, each entry
# overriding the last -- the JSON-LD 1.1 API's Context Processing Algorithm
# (§4.1) wraps a non-array local context in an array at step 4 and iterates it
# at step 5: https://www.w3.org/TR/2020/REC-json-ld11-api-20200716/#context-processing-algorithm
# ``@list`` is the ordered container (normative JSON-LD 1.1 §9.7):
# https://www.w3.org/TR/2020/REC-json-ld11-20200716/#lists-and-sets
#
# ``@graph`` and ``@set`` are deliberately absent. JSON-LD arrays are unordered
# unless a container says otherwise, and ``@set`` expresses an unordered set of
# data (§9.7), so their arrays are sorted deterministically. The explanation
# in §4.3 Value Ordering is informative, not the normative definition.
_ORDERED_JSONLD_KEYWORDS: frozenset[str] = frozenset({"@context", "@list"})

# What ``preserve_list_order_keys`` defaults to. This is a superset of the
# keywords above by one entry: ``imports`` is not a JSON-LD keyword at all, but
# an ordered list in vocabularies that use it, so it stays a local convenience
# a caller can drop by passing their own set.
_JSONLD_ORDERED_KEYS: frozenset[str] = frozenset({"@context", "@list", "imports"})
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

    # Context-object key order is not meaningful. Repeat term-definition
    # resolution until stable so aliases can refer to terms defined elsewhere
    # in the same object, as the JSON-LD 1.1 Create Term Definition algorithm
    # permits. Each pass learns a term or reaches the stable result.
    for _ in range(len(value) + 1):
        before = (dict(result.keyword_aliases), result.json_terms, result.list_terms, result.unknown)
        result = _apply_term_definitions(value, result)
        after = (dict(result.keyword_aliases), result.json_terms, result.list_terms, result.unknown)
        if before == after:
            break

    return result


def _apply_term_definitions(value: dict, active: _LocalContext) -> _LocalContext:
    """One pass over a context object's term definitions."""
    result = active
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
    if isinstance(key, float):
        # json.encoder uses floatstr, not str: NaN and the infinities get these
        # spellings, and every other float its repr.
        if key != key:
            return "NaN"
        if key == float("inf"):
            return "Infinity"
        if key == float("-inf"):
            return "-Infinity"
        return float.__repr__(key)
    if isinstance(key, int):
        return int.__repr__(key)
    return str(key)


def _sorted_items(value: dict) -> list:
    """Order a dict's items by the name ``json.dumps`` will write.

    Refuses two keys that encode to the same name, as ``{1: "a", "1": "b"}``
    and ``{float("nan"): "a", float("nan"): "b"}`` do. Such a dict has two
    entries but serializes to one object carrying the same name twice, which
    RFC 8259 section 4 leaves to unpredictable interpretation; ``json.loads``
    keeps only the last, so the text cannot be read back and rendering is not
    idempotent. It also breaks this function's contract that equal data
    serializes to equal text: the colliding items compare equal under the
    sort key, so a stable sort leaves their order to insertion order, and the
    equal dicts ``{1: "a", "1": "b"}`` and ``{"1": "b", 1: "a"}`` render
    differently. Refusing is the only answer that neither drops an entry nor
    invents one.
    """
    seen: dict[str, object] = {}
    for key in value:
        name = _json_key(key)
        if name in seen:
            raise ValueError(
                f"keys {seen[name]!r} and {key!r} both encode to the JSON name "
                f"{name!r}, which one object cannot carry twice. Use string keys."
            )
        seen[name] = key
    return sorted(value.items(), key=lambda item: _json_key(item[0]))


def deterministic_json(
    obj: object,
    indent: int = 3,
    preserve_list_order_keys: AbstractSet[str] | None = None,
) -> str:
    """Serialize a JSON-compatible object with deterministic ordering.

    Recursively sorts dict keys and unordered list elements, so equal data
    serializes to equal text across Python versions and processes. Keys sort
    by the name ``json.dumps`` will write and list elements by their own
    serialized JSON text, which orders ``[2, 10, 1]`` as ``[1, 10, 2]``: this
    is an ordering helper for diffable output, not a JSON canonicalization
    scheme and not a JSON-LD processor. The argument is not modified.

    Arrays whose order carries JSON-LD meaning are left alone: ``@list``
    values, ``@json`` literal payloads, and terms declared with
    ``@container: @list`` or ``@type: @json`` in a local ``@context``,
    including keyword aliases (in any order within the ``@context`` object,
    since its key order carries no meaning), arrays nested directly inside
    such an array, ordered context arrays, inheritance by nested objects, and
    a ``null`` reset. Protection stops at a dict, which begins a fresh node
    object whose own arrays sort again. Remote contexts, ``@import``, scoped
    contexts and definitions whose ordering cannot be settled locally are
    never fetched; from such a value on, every descendant array is retained,
    which also covers a ``@context: null`` that is itself data inside an
    unrecognized ``@json`` property.

    :param obj: A JSON-serializable object.
    :param indent: Number of spaces of indentation, passed to ``json.dumps``.
    :param preserve_list_order_keys: Dict keys whose immediate list value
        keeps its order. Defaults to ``@context``, ``@list`` and ``imports``;
        a set passed here replaces that default, while the JSON-LD keyword
        protections above still apply. Any set abstraction is accepted.
        ``@graph`` and ``@set`` are not
        protected: JSON-LD leaves both unordered, so their arrays are sorted
        like any other.
    :returns: Deterministic JSON string.
    :raises TypeError: From ``json.dumps``, for a value it cannot encode.
    :raises ValueError: If two keys of one dict encode to the same JSON name,
        as ``{1: "a", "1": "b"}`` does. One object cannot carry a name twice:
        ``json.loads`` would keep only the last entry, and the two items tie
        under the sort, so equal data would not render as equal text.
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
                            or _resolve_keyword(k, local_context) in _ORDERED_JSONLD_KEYWORDS
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
                for k, v in _sorted_items(value)
            }
        if isinstance(value, list):
            # An array nested directly inside an ordered array is ordered
            # too: it expands to a nested list, not to a fresh unordered
            # value, so its order reaches the RDF as list structure just the
            # same (``@list`` is the ordered container, JSON-LD 1.1 §9.7).
            # Carry the protection into array items only -- a dict starts a
            # fresh node object, which is the documented point where sorting
            # resumes.
            sorted_items = [
                _deep_sort(
                    item,
                    context,
                    preserve_current_list=preserve_current_list and isinstance(item, list),
                    preserve_descendant_lists=preserve_descendant_lists,
                )
                for item in value
            ]
            if preserve_current_list or preserve_descendant_lists or context.unknown:
                return sorted_items
            try:
                return sorted(sorted_items, key=lambda x: json.dumps(x, ensure_ascii=False))
            except TypeError:
                return sorted_items
        return value

    return json.dumps(_deep_sort(obj), indent=indent, ensure_ascii=False)
