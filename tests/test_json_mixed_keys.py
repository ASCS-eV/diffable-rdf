"""Mixed JSON dictionary keys remain deterministic inside ordinary lists."""

from __future__ import annotations

import copy
import json

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


def test_mixed_key_dictionary_list_keeps_encoded_key_collisions():
    rendered = deterministic_json([{1: "number", "1": "string"}, 0])

    assert rendered.count('"1":') == 2
    assert '"number"' in rendered
    assert '"string"' in rendered


def test_custom_preserved_list_keeps_mixed_key_element_order():
    document = {"custom": [{1: "last", "b": 2}, {None: "first", "a": 1}]}

    result = json.loads(deterministic_json(document, preserve_list_order_keys=frozenset({"custom"})))

    assert result["custom"] == [{"1": "last", "b": 2}, {"null": "first", "a": 1}]


def test_parsed_json_rendering_is_idempotent():
    document = json.loads('[{"z": [3, 1, 2], "a": 0}, {"nested": [{"b": 2, "a": 1}, 0]}]')

    rendered = deterministic_json(document)

    assert deterministic_json(json.loads(rendered)) == rendered
