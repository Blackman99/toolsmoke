from __future__ import annotations

from typing import Any, Dict, List

from ..client import parse_json_events
from ..core import FAIL, PASS, WARN, Ctx, Outcome, ProbeFail, find_leak, probe
from ..schema import validate
from .fixtures import WEATHER_RESULT_PARIS, WEATHER_SCHEMA

A_TOOLS = [{"name": "get_weather", "description": "Get the current weather for a city.", "input_schema": WEATHER_SCHEMA}]


def _payload(ctx: Ctx, messages: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
    p: Dict[str, Any] = {"model": ctx.cfg.model, "max_tokens": extra.pop("max_tokens", ctx.cfg.max_tokens), "messages": messages}
    if ctx.cfg.temperature is not None:
        p["temperature"] = ctx.cfg.temperature
    p.update(extra)
    return p


def _post(ctx: Ctx, payload: Dict[str, Any]) -> Dict[str, Any]:
    res = ctx.aclient.post("messages", payload)
    if not res.ok:
        raise ProbeFail(f"POST /messages → HTTP {res.status}: {res.snippet(90)}")
    data = res.try_json()
    if not isinstance(data, dict) or not isinstance(data.get("content"), list):
        raise ProbeFail(f"not an Anthropic message object: {res.snippet(90)}")
    return data


def _text(data: Dict[str, Any]) -> str:
    return "".join(b.get("text", "") for b in data["content"] if isinstance(b, dict) and b.get("type") == "text")


@probe("anthropic.basic", "anthropic", "POST /v1/messages returns a message", needs="anthropic")
def anthropic_basic(ctx: Ctx) -> Outcome:
    data = _post(ctx, _payload(ctx, [{"role": "user", "content": "Say hello in five words or fewer."}], system="You are terse."))
    text = _text(data)
    if not text.strip():
        return Outcome(FAIL, f"no text block (content types: {[b.get('type') for b in data['content']]})")
    problems = []
    if data.get("type") != "message":
        problems.append(f"type={data.get('type')!r}")
    if data.get("stop_reason") not in ("end_turn", "max_tokens", "stop_sequence"):
        problems.append(f"stop_reason={data.get('stop_reason')!r}")
    if not (data.get("usage") or {}).get("output_tokens"):
        problems.append("no usage.output_tokens")
    if problems:
        return Outcome(WARN, "; ".join(problems))
    return Outcome(PASS, f"stop_reason={data['stop_reason']}, {data['usage']['output_tokens']} output tokens")


@probe("anthropic.stream", "anthropic", "Messages streaming emits the standard event sequence", needs="anthropic")
def anthropic_stream(ctx: Ctx) -> Outcome:
    res = ctx.aclient.stream("messages", _payload(ctx, [{"role": "user", "content": "Count from 1 to 10."}], stream=True))
    if not res.ok:
        raise ProbeFail(f"HTTP {res.status}: {res.snippet(90)}")
    items, _done, bad = parse_json_events(res.events)
    if bad:
        return Outcome(FAIL, f"non-JSON SSE data: {bad[0]!r}")
    types = [(ev or (d.get("type") if isinstance(d, dict) else None)) for _t, ev, d in items]
    text = "".join(
        (d.get("delta") or {}).get("text", "") for _t, _e, d in items if isinstance(d, dict) and d.get("type") == "content_block_delta"
    )
    required = ["message_start", "content_block_start", "content_block_delta", "content_block_stop", "message_delta", "message_stop"]
    missing = [r for r in required if r not in types]
    if not text:
        return Outcome(FAIL, f"no text_delta events (saw: {sorted(set(t for t in types if t))})")
    if missing:
        return Outcome(WARN, f"missing events: {', '.join(missing)}")
    return Outcome(PASS, f"{types.count('content_block_delta')} deltas, full event sequence")


@probe("anthropic.tools", "anthropic", "Messages API tool_use block", needs="anthropic")
def anthropic_tools(ctx: Ctx) -> Outcome:
    data = _post(ctx, _payload(ctx, [{"role": "user", "content": "What's the weather in Paris right now?"}], tools=A_TOOLS))
    uses = [b for b in data["content"] if isinstance(b, dict) and b.get("type") == "tool_use"]
    if not uses:
        text = _text(data)
        if find_leak(text):
            return Outcome(FAIL, f"tool call leaked into text: {find_leak(text)!r}")
        return Outcome(FAIL, f"no tool_use block (reply: {text.strip()[:40]!r})")
    u = uses[0]
    if not isinstance(u.get("input"), dict):
        return Outcome(FAIL, f"tool_use.input is {type(u.get('input')).__name__}, expected object")
    errs = validate(u["input"], WEATHER_SCHEMA)
    if errs or not u.get("id"):
        return Outcome(FAIL, errs[0] if errs else "tool_use has no id")
    if data.get("stop_reason") != "tool_use":
        return Outcome(WARN, f"tool_use OK but stop_reason={data.get('stop_reason')!r}")
    return Outcome(PASS, f"tool_use get_weather {u['input']}, stop_reason=tool_use")


@probe("anthropic.tool_result", "anthropic", "Messages API accepts tool_result blocks", needs="anthropic")
def anthropic_tool_result(ctx: Ctx) -> Outcome:
    msgs = [
        {"role": "user", "content": "What's the weather in Paris right now?"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_ts_1", "name": "get_weather", "input": {"city": "Paris"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_ts_1", "content": WEATHER_RESULT_PARIS}]},
    ]
    data = _post(ctx, _payload(ctx, msgs, tools=A_TOOLS))
    text = _text(data)
    if "23" in text or "sunny" in text.lower():
        return Outcome(PASS, "answer uses the tool_result")
    if any(b.get("type") == "tool_use" for b in data["content"] if isinstance(b, dict)):
        return Outcome(WARN, "called the tool again instead of answering")
    return Outcome(FAIL, f"tool_result ignored (reply: {text.strip()[:50]!r})")
