from __future__ import annotations

import json
import re

from ..core import FAIL, PASS, WARN, Ctx, Outcome, content_of, expect_chat, finish_reason, message, probe
from ..schema import validate
from .fixtures import STRUCTURED_SCHEMA


def _parse(text: str):
    t = text.strip()
    fenced = False
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if m:
        t, fenced = m.group(1), True
    return json.loads(t), fenced


@probe("json.mode", "structured", "response_format json_object returns JSON")
def json_mode(ctx: Ctx) -> Outcome:
    res = ctx.client.post(
        "chat/completions",
        ctx.payload(
            [{"role": "user", "content": "Return a JSON object describing a fictional person with keys name and age."}],
            response_format={"type": "json_object"},
        ),
    )
    if res.status in (400, 422):
        return Outcome(FAIL, f"response_format json_object rejected: HTTP {res.status}: {res.snippet(80)}")
    text = content_of(message(expect_chat(res)))
    try:
        obj, fenced = _parse(text)
    except ValueError:
        return Outcome(FAIL, f"content is not valid JSON: {text.strip()[:50]!r}")
    if not isinstance(obj, dict):
        return Outcome(FAIL, f"JSON is a {type(obj).__name__}, expected an object")
    if fenced:
        return Outcome(WARN, "valid JSON but wrapped in ``` fences")
    return Outcome(PASS, f"valid JSON object with keys {sorted(obj)[:4]}")


@probe("json.schema", "structured", "response_format json_schema is enforced")
def json_schema(ctx: Ctx) -> Outcome:
    res = ctx.client.post(
        "chat/completions",
        ctx.payload(
            [{"role": "user", "content": "Give me facts about Paris: city, country, population in millions, and a few landmarks."}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "city_facts", "strict": True, "schema": STRUCTURED_SCHEMA},
            },
        ),
    )
    if res.status in (400, 422):
        return Outcome(FAIL, f"json_schema response_format rejected: HTTP {res.status}: {res.snippet(80)}")
    data = expect_chat(res)
    text = content_of(message(data))
    try:
        obj, fenced = _parse(text)
    except ValueError:
        if finish_reason(data) == "length" and text.lstrip().startswith("{"):
            return Outcome(WARN, "JSON cut off at max_tokens (model kept generating; grammar not bounding output?)")
        return Outcome(FAIL, f"schema ignored, content is not JSON: {text.strip()[:50]!r}")
    errors = validate(obj, STRUCTURED_SCHEMA)
    if errors:
        return Outcome(FAIL, f"JSON violates schema: {errors[0]}")
    if fenced:
        return Outcome(WARN, "matches schema but wrapped in ``` fences")
    return Outcome(PASS, "output validates against the strict schema")
