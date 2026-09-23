"""Making a JSON Schema strict: every object gets ``additionalProperties: false``.

Shared by the OpenAI adapter (strict ``response_format``) and the
Anthropic adapter (schema-constrained ``output_config``) — see
``infrastructure/llm/json_schema.py``'s module docstring for why this is
one function rather than one per adapter.
"""

from __future__ import annotations

from infrastructure.llm.json_schema import to_strict_schema


def test_a_flat_object_gets_additional_properties_false() -> None:
    schema = to_strict_schema({"type": "object", "properties": {"x": {"type": "string"}}})

    assert schema["additionalProperties"] is False


def test_a_nested_object_is_also_made_strict() -> None:
    schema = to_strict_schema(
        {
            "type": "object",
            "properties": {"nested": {"type": "object", "properties": {"x": {"type": "string"}}}},
        }
    )

    assert schema["properties"]["nested"]["additionalProperties"] is False


def test_defs_referenced_by_a_pydantic_model_schema_are_made_strict() -> None:
    # pydantic hoists nested models into $defs rather than inlining them.
    schema = to_strict_schema(
        {
            "type": "object",
            "properties": {"child": {"$ref": "#/$defs/Child"}},
            "$defs": {"Child": {"type": "object", "properties": {"y": {"type": "integer"}}}},
        }
    )

    assert schema["$defs"]["Child"]["additionalProperties"] is False


def test_an_object_inside_an_array_is_made_strict() -> None:
    schema = to_strict_schema(
        {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "object", "properties": {"x": {}}}}
            },
        }
    )

    assert schema["properties"]["items"]["items"]["additionalProperties"] is False


def test_an_object_inside_a_union_is_made_strict() -> None:
    schema = to_strict_schema(
        {
            "type": "object",
            "properties": {
                "value": {"anyOf": [{"type": "object", "properties": {"x": {}}}, {"type": "null"}]}
            },
        }
    )

    variants = schema["properties"]["value"]["anyOf"]
    assert variants[0]["additionalProperties"] is False


def test_a_schema_with_no_object_at_all_is_left_unchanged() -> None:
    schema = to_strict_schema({"type": "string"})

    assert "additionalProperties" not in schema
