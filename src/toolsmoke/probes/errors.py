from __future__ import annotations

from ..core import FAIL, PASS, WARN, Ctx, Outcome, probe


def _has_error_obj(res) -> bool:
    data = res.try_json()
    return isinstance(data, dict) and ("error" in data or "message" in data or "detail" in data)


@probe("errors.bad_model", "errors", "Unknown model gives a clean 4xx")
def errors_bad_model(ctx: Ctx) -> Outcome:
    p = ctx.payload([{"role": "user", "content": "hi"}], max_tokens=8)
    p["model"] = "toolsmoke-no-such-model-0000"
    res = ctx.client.post("chat/completions", p)
    if res.status >= 500:
        return Outcome(FAIL, f"HTTP {res.status} (server error instead of a 4xx)")
    if res.ok:
        return Outcome(WARN, "unknown model accepted with 200 (server ignores the model name)")
    if not _has_error_obj(res):
        return Outcome(WARN, f"HTTP {res.status} but body is not a JSON error object")
    return Outcome(PASS, f"HTTP {res.status} with JSON error")


@probe("errors.bad_request", "errors", "Malformed request gives a clean 4xx")
def errors_bad_request(ctx: Ctx) -> Outcome:
    p = ctx.payload([{"role": "wizard", "content": "hi"}], max_tokens=8)
    res = ctx.client.post("chat/completions", p)
    if res.status >= 500:
        return Outcome(FAIL, f"HTTP {res.status} on an invalid role (should be 400/422); agents will retry forever")
    if res.ok:
        return Outcome(WARN, "invalid message role accepted with 200")
    if not _has_error_obj(res):
        return Outcome(WARN, f"HTTP {res.status} but body is not a JSON error object")
    return Outcome(PASS, f"HTTP {res.status} with JSON error")


@probe("errors.bad_auth", "errors", "Wrong API key is rejected", needs="api_key")
def errors_bad_auth(ctx: Ctx) -> Outcome:
    res = ctx.client.post("chat/completions", ctx.payload([{"role": "user", "content": "hi"}], max_tokens=8), api_key="sk-toolsmoke-invalid")
    if res.status in (401, 403):
        return Outcome(PASS, f"HTTP {res.status}")
    if res.ok:
        return Outcome(WARN, "a wrong API key was accepted (auth not enforced)")
    if res.status >= 500:
        return Outcome(FAIL, f"HTTP {res.status} for a bad key")
    return Outcome(WARN, f"HTTP {res.status} (expected 401/403)")
