"""JSON Schema strictness, shared by every provider that wants it.

Both OpenAI (``response_format`` strict mode) and Anthropic (schema-
constrained decoding via ``output_config``) refuse — or silently permit
more than intended — a schema missing ``additionalProperties: false``.
Pydantic's own ``model_json_schema()`` never emits it, so every provider
that wants a genuinely closed schema runs its output through
:func:`to_strict_schema` first, rather than each adapter growing its own
copy of the same recursive walk.
"""

from __future__ import annotations

from typing import Any


def to_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Add ``additionalProperties: false`` to every object in a JSON Schema.

    Applied recursively so nested models and ``$defs`` are covered.
    """
    if schema.get("type") == "object" or "properties" in schema:
        schema["additionalProperties"] = False

    for key in ("properties", "$defs", "definitions"):
        nested = schema.get(key)
        if isinstance(nested, dict):
            for value in nested.values():
                if isinstance(value, dict):
                    to_strict_schema(value)

    for key in ("items", "additionalItems"):
        nested_item = schema.get(key)
        if isinstance(nested_item, dict):
            to_strict_schema(nested_item)

    for key in ("anyOf", "oneOf", "allOf"):
        variants = schema.get(key)
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict):
                    to_strict_schema(variant)

    return schema
