"""The base model every API response and request body is built on.

Python names its fields `call_ids`; JSON, and every client that consumes
it, expects `callIds`. This converts between the two in one place so that
neither side has to live with the other's convention.

## Why one base rather than aliases per field

Fifty-odd models carry a few hundred fields between them. Written out, each
alias is a chance to typo a key that a client then cannot read, and the typo
would be invisible in review — `call_ids` and `callIds` look alike at a
glance. Generated, there is nothing to get wrong and nothing to keep in
step when a field is added.

## Both spellings are accepted on the way in

`populate_by_name` stays on, so a request body may use either form. That
matters for the tests and the CLI, which construct these models in Python by
their field names, and it means a client sending the snake_case spelling is
not rejected for it. Responses always serialise as camelCase — FastAPI
serialises a `response_model` by alias.

## It applies to every endpoint, not only the new ones

An API where `/insights` speaks camelCase and `/runs` speaks snake_case is
worse than either convention: every client needs a rule for which is which,
and the rule is "whichever we happened to write first". The existing
endpoints are converted with the same base.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """A model whose JSON keys are camelCase and whose fields are not."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
