"""Mixed JSON dictionary keys remain deterministic inside ordinary lists."""

from __future__ import annotations

import copy
import json

import pytest

from diffable_rdf import deterministic_json


def test_mixed_key_dictionary_list_permutations_are_deterministic():
    forward = [
        {
            None: "none",
            False: "false",
            2.5: "float",
            "word": {"nested": [{3: "three", "z": 2}, 0]},
        },
        {"plain": "value"},
    ]
    reverse = [
        {"plain": "value"},
        {
            "word": {"nested": [0, {"z": 2, 3: "three"}]},
            2.5: "float",
            False: "false",
            None: "none",
        },
    ]
    forward_original = copy.deepcopy(forward)
    reverse_original = copy.deepcopy(reverse)

    json.dumps(forward)
    json.dumps(reverse)

    assert deterministic_json(forward) == deterministic_json(reverse)
    assert forward == forward_original
    assert reverse == reverse_original


def test_encoded_key_collisions_are_refused_not_emitted_twice():
    """Keys with one JSON spelling are rejected before rendering."""
    forward = {1: "number", "1": "string"}
    reverse = {"1": "string", 1: "number"}
    assert forward == reverse, "equal data requires equal text"

    for document in (forward, reverse, [forward, 0], {"nested": [reverse]}):
        with pytest.raises(ValueError, match="both encode to the JSON name"):
            deterministic_json(document)


def test_two_distinct_nan_keys_are_refused_as_well():
    """The collision does not need two different key *types* to happen."""
    document = {float("nan"): "first", float("nan"): "second"}  # noqa: F601
    assert len(document) == 2, "distinct NaN objects are distinct dict keys"

    with pytest.raises(ValueError, match="both encode to the JSON name 'NaN'"):
        deterministic_json(document)


def test_custom_preserved_list_keeps_mixed_key_element_order():
    document = {"custom": [{1: "last", "b": 2}, {None: "first", "a": 1}]}

    result = json.loads(deterministic_json(document, preserve_list_order_keys=frozenset({"custom"})))

    assert result["custom"] == [{"1": "last", "b": 2}, {"null": "first", "a": 1}]


def test_parsed_json_rendering_is_idempotent():
    document = json.loads('[{"z": [3, 1, 2], "a": 0}, {"nested": [{"b": 2, "a": 1}, 0]}]')

    rendered = deterministic_json(document)

    assert deterministic_json(json.loads(rendered)) == rendered


def test_non_string_keys_sort_by_the_name_json_writes_not_by_str():
    """``json.dumps`` coerces keys with its own spellings, not ``str``.

    The encoder writes a float key through ``floatstr`` and an int key through
    ``int.__repr__``, so ``float("inf")`` is written ``Infinity`` and a subclass
    that overrides ``__str__`` is still written as its number. Ordering uses
    the names emitted by the JSON encoder.
    """

    class Numbered(int):
        def __str__(self) -> str:
            return "sorts-last-if-str-is-used"

    document = {
        float("nan"): "nan",
        float("-inf"): "neg-inf",
        float("inf"): "inf",
        Numbered(1): "one",
        "M": "m",
        "Zebra": "z",
    }

    names = list(json.loads(deterministic_json(document)))

    assert names == sorted(names), f"the emitted names are out of order: {names}"
    assert names == ["-Infinity", "1", "Infinity", "M", "NaN", "Zebra"]
