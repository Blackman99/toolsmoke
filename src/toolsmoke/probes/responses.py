"""OpenAI Responses API probes (POST /v1/responses), opt-in with --responses.

The OpenAI Agents SDK, Codex CLI and other newer agent stacks talk to
/v1/responses instead of /v1/chat/completions. Its tool calls are top-level
`function_call` output items, tool results go back as `function_call_output`
input items, and streaming uses typed `response.*` events.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from ..client import parse_json_events
from ..core import FAIL, PASS, WARN, Ctx, Outcome, ProbeFail, ToolCall, find_leak, make_call, probe
from ..schema import validate
from .fixtures import SYSTEM_TOOLS, WEATHER_RESULT_PARIS, WEATHER_SCHEMA

R_TOOLS = [{"type": "function", "name": "get_weather", "description": "Get the current weather for a city.",
            "parameters": WEATHER_SCHEMA}]
ASK_WEATHER = "What's the weather in Paris right now?"


def _payload(ctx: Ctx, input_: Any, **extra: Any) -> Dict[str, Any]:
    p: Dict[str, Any] = {"model": ctx.cfg.model, "input": input_}
    max_tokens = extra.pop("max_output_tokens", ctx.cfg.max_tokens)
    if max_tokens:
        p["max_output_tokens"] = max_tokens
    if ctx.cfg.temperature is not None:
        p["temperature"] = ctx.cfg.temperature
    p.update({k: v for k, v in extra.items() if v is not None})
    return p


def _post(ctx: Ctx, payload: Dict[str, Any]) -> Dict[str, Any]:
    res = ctx.client.post("responses", payload)
    if not res.ok:
        raise ProbeFail(f"POST /responses → HTTP {res.status}: {res.snippet(90)}")
    data = res.try_json()
    if not isinstance(data, dict) or not isinstance(data.get("output"), list):
        raise ProbeFail(f"not a Responses API object (no output array): {res.snippet(90)}")
    return data


def _items(data: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    return [i for i in data.get("output") or [] if isinstance(i, dict) and i.get("type") == kind]


def _text(data: Dict[str, Any]) -> str:
    out = []
    for item in _items(data, "message"):
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") == "output_text":
                out.append(part.get("text") or "")
    return "".join(out)


def _calls(items: List[Dict[str, Any]]) -> List[ToolCall]:
    return [make_call(i.get("call_id"), i.get("name"), i.get("arguments")) for i in items]


def _check_call(calls: List[ToolCall], text: str, where: str) -> Tuple[Optional[Outcome], Optional[ToolCall]]:
    if not calls:
        leak = find_leak(text)
        if leak:
            return Outcome(FAIL, f"tool call leaked into {where} as text: {leak!r}"), None
        return Outcome(FAIL, f"no function_call item (reply: {text.strip()[:40]!r})"), None
    c = calls[0]
    problems = [p.replace("tool call has no id", "function_call has no call_id") for p in c.problems]
    if c.args is not None:
        problems += validate(c.args, WEATHER_SCHEMA)
    if c.name != "get_weather":
        problems.insert(0, f"called {c.name!r}, expected get_weather")
    if problems:
        return Outcome(FAIL, problems[0]), c
    return None, c


@probe("responses.basic", "responses", "POST /v1/responses returns a completed response", needs="responses")
def responses_basic(ctx: Ctx) -> Outcome:
    data = _post(ctx, _payload(ctx, "Say hello in five words or fewer.", instructions="You are terse."))
    text = _text(data)
    if not text.strip():
        kinds = [i.get("type") for i in data["output"] if isinstance(i, dict)]
        return Outcome(FAIL, f"no output_text in a message item (output types: {kinds})")
    problems = []
    if data.get("object") != "response":
        problems.append(f"object={data.get('object')!r}")
    if data.get("status") not in ("completed", None):
        problems.append(f"status={data.get('status')!r}")
    out_toks = (data.get("usage") or {}).get("output_tokens")
    if not out_toks:
        problems.append("no usage.output_tokens")
    if problems:
        return Outcome(WARN, "; ".join(problems))
    return Outcome(PASS, f"status=completed, {out_toks} output tokens")


def _stream(ctx: Ctx, payload: Dict[str, Any]):
    res = ctx.client.stream("responses", payload)
    if not res.ok:
        raise ProbeFail(f"POST /responses (stream) → HTTP {res.status}: {res.snippet(90)}")
    items, _done, bad = parse_json_events(res.events)
    if not items:
        raise ProbeFail(f"no SSE events (Content-Type: {res.content_type or 'none'}): {res.snippet(90)}")
    if bad:
        raise ProbeFail(f"non-JSON SSE data: {bad[0]!r}")
    events = [(ev or (d.get("type") if isinstance(d, dict) else None), d) for _t, ev, d in items]
    return [(t, d) for t, d in events if isinstance(d, dict)]


@probe("responses.stream", "responses", "Responses streaming emits typed response.* events", needs="responses")
def responses_stream(ctx: Ctx) -> Outcome:
    events = _stream(ctx, _payload(ctx, "Count from 1 to 10.", stream=True))
    types = [t for t, _d in events]
    text = "".join(str(d.get("delta") or "") for t, d in events if t == "response.output_text.delta")
    if not text:
        return Outcome(FAIL, f"no response.output_text.delta events (saw: {sorted(set(t for t in types if t))[:6]})")
    required = ["response.created", "response.output_item.added", "response.output_text.delta",
                "response.output_item.done", "response.completed"]
    missing = [r for r in required if r not in types]
    if "response.completed" in missing and ("response.failed" in types or "response.incomplete" in types):
        return Outcome(FAIL, "stream ended with response.failed/incomplete")
    if missing:
        return Outcome(WARN, f"missing events: {', '.join(m.replace('response.', '') for m in missing)}")
    return Outcome(PASS, f"{types.count('response.output_text.delta')} text deltas, created → completed")


@probe("responses.tools", "responses", "Responses API function_call item", needs="responses")
def responses_tools(ctx: Ctx) -> Outcome:
    data = _post(ctx, _payload(ctx, ASK_WEATHER, instructions=SYSTEM_TOOLS, tools=R_TOOLS))
    bad, c = _check_call(_calls(_items(data, "function_call")), _text(data), "output_text")
    if bad:
        return bad
    return Outcome(PASS, f"function_call get_weather({c.raw_args}) with call_id")


@probe("responses.stream_tools", "responses", "Streamed function_call arguments assemble into valid JSON", needs="responses")
def responses_stream_tools(ctx: Ctx) -> Outcome:
    events = _stream(ctx, _payload(ctx, ASK_WEATHER, instructions=SYSTEM_TOOLS, tools=R_TOOLS, stream=True))
    text = "".join(str(d.get("delta") or "") for t, d in events if t == "response.output_text.delta")
    added: Dict[Any, Dict[str, Any]] = {}
    deltas: Dict[Any, str] = {}
    done_items: List[Dict[str, Any]] = []
    for t, d in events:
        item = d.get("item") if isinstance(d.get("item"), dict) else {}
        if t == "response.output_item.added" and item.get("type") == "function_call":
            added[item.get("id") or d.get("output_index")] = item
        elif t == "response.function_call_arguments.delta":
            key = d.get("item_id") or d.get("output_index")
            deltas[key] = deltas.get(key, "") + str(d.get("delta") or "")
        elif t == "response.output_item.done" and item.get("type") == "function_call":
            done_items.append(item)
    if not added and not done_items:
        bad, _ = _check_call([], text, "streamed output_text")
        return bad
    if not deltas:
        # Arguments only in the final item: usable, but an agent UI cannot stream them.
        bad, c = _check_call(_calls(done_items), text, "streamed output_text")
        if bad:
            return bad
        return Outcome(WARN, f"no function_call_arguments.delta events; args only in output_item.done: {c.raw_args}")
    key, item = next(iter(added.items())) if added else (None, done_items[0])
    assembled = deltas.get(key) if key in deltas else next(iter(deltas.values()))
    bad, c = _check_call([make_call(item.get("call_id"), item.get("name"), assembled)], text, "streamed output_text")
    if bad:
        return Outcome(FAIL, f"assembled deltas: {bad.detail}")
    final = next((i for i in done_items if i.get("call_id") == c.id), None)
    if final is not None and isinstance(final.get("arguments"), str):
        try:
            if json.loads(final["arguments"]) != c.args:
                return Outcome(WARN, "assembled deltas differ from output_item.done arguments")
        except ValueError:
            return Outcome(WARN, "output_item.done arguments are not valid JSON (deltas were)")
    return Outcome(PASS, f"get_weather({c.raw_args}) assembled from deltas")


@probe("responses.tool_result", "responses", "function_call_output input item is accepted and used", needs="responses")
def responses_tool_result(ctx: Ctx) -> Outcome:
    input_ = [
        {"role": "user", "content": ASK_WEATHER},
        {"type": "function_call", "call_id": "call_ts_1", "name": "get_weather", "arguments": '{"city": "Paris"}'},
        {"type": "function_call_output", "call_id": "call_ts_1", "output": WEATHER_RESULT_PARIS},
    ]
    res = ctx.client.post("responses", _payload(ctx, input_, instructions=SYSTEM_TOOLS, tools=R_TOOLS))
    if not res.ok:
        raise ProbeFail(f"server rejected a function_call_output item: HTTP {res.status}: {res.snippet(90)}")
    data = res.try_json()
    if not isinstance(data, dict) or not isinstance(data.get("output"), list):
        raise ProbeFail(f"not a Responses API object (no output array): {res.snippet(90)}")
    text = _text(data)
    if "23" in text or "sunny" in text.lower():
        return Outcome(PASS, "final answer uses the function_call_output")
    if _items(data, "function_call"):
        return Outcome(WARN, "called the tool again instead of answering from the result")
    return Outcome(FAIL, f"function_call_output ignored (reply: {text.strip()[:50]!r})")
