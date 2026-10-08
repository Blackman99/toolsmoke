from __future__ import annotations

from typing import List

from ..core import (
    FAIL, PASS, WARN, Ctx, Outcome, ProbeFail, ToolCall, content_of, find_leak, finish_reason, message,
    parse_tool_calls, probe,
)
from ..schema import validate
from .fixtures import SCHEMAS, SYSTEM_TOOLS, TOOLS, WEATHER_RESULT_PARIS, WEATHER_RESULT_TOKYO


def _ask(ctx: Ctx, prompt: str, **params):
    msgs = [{"role": "system", "content": SYSTEM_TOOLS}, {"role": "user", "content": prompt}]
    _, data = ctx.chat(msgs, tools=TOOLS, **params)
    msg = message(data)
    return data, msg, parse_tool_calls(msg), content_of(msg)


def _call_problems(calls: List[ToolCall]) -> List[str]:
    out: List[str] = []
    for c in calls:
        out.extend(c.problems)
        if c.args is not None and c.name in SCHEMAS:
            out.extend(validate(c.args, SCHEMAS[c.name]))
        elif c.name and c.name not in SCHEMAS:
            out.append(f"called unknown tool {c.name!r}")
    return out


def _leak_fail(text: str) -> Outcome:
    leak = find_leak(text)
    return Outcome(FAIL, f"tool call leaked into content as text: {leak!r} (chat template / tool parser problem)")


@probe("tools.single", "tools", "Single tool call (tool_choice=auto)")
def tools_single(ctx: Ctx) -> Outcome:
    data, _msg, calls, text = _ask(ctx, "What's the weather in Paris right now?")
    if not calls:
        if find_leak(text):
            return _leak_fail(text)
        return Outcome(FAIL, f"no tool_calls returned (reply: {text.strip()[:50]!r})")
    problems = _call_problems(calls)
    if problems:
        return Outcome(FAIL, problems[0])
    c = calls[0]
    if c.name != "get_weather":
        return Outcome(FAIL, f"called {c.name!r}, expected get_weather")
    if "paris" not in str(c.args.get("city", "")).lower():
        return Outcome(WARN, f"city argument is {c.args.get('city')!r}")
    fr = finish_reason(data)
    if fr != "tool_calls":
        return Outcome(WARN, f"call OK but finish_reason={fr!r} (agents loop on 'tool_calls')")
    return Outcome(PASS, f"get_weather({c.raw_args}) finish_reason=tool_calls")


@probe("tools.args_schema", "tools", "Arguments match the JSON schema (enum, required)")
def tools_args_schema(ctx: Ctx) -> Outcome:
    _, _msg, calls, text = _ask(ctx, "What's the weather in Tokyo? I want the temperature in fahrenheit.")
    if not calls:
        return _leak_fail(text) if find_leak(text) else Outcome(FAIL, "no tool call returned")
    problems = _call_problems(calls)
    if problems:
        return Outcome(FAIL, "; ".join(problems[:2]))
    args = calls[0].args or {}
    if args.get("unit") != "fahrenheit":
        return Outcome(WARN, f"valid, but unit={args.get('unit')!r} (expected 'fahrenheit')")
    return Outcome(PASS, f"valid against schema: {calls[0].raw_args}")


@probe("tools.parallel", "tools", "Parallel tool calls in one turn")
def tools_parallel(ctx: Ctx) -> Outcome:
    _, _msg, calls, text = _ask(ctx, "Get the current weather for Paris and for Tokyo.")
    if not calls:
        return _leak_fail(text) if find_leak(text) else Outcome(FAIL, "no tool calls returned")
    problems = _call_problems(calls)
    if problems:
        return Outcome(FAIL, problems[0])
    if len(calls) == 1:
        return Outcome(WARN, "only 1 tool call (expected 2): parallel calls unsupported or disabled")
    ids = [c.id for c in calls]
    if len(set(ids)) != len(ids):
        return Outcome(FAIL, f"duplicate tool call ids {ids}: results can't be matched back")
    cities = sorted(str((c.args or {}).get("city", "")) for c in calls)
    return Outcome(PASS, f"{len(calls)} calls with distinct ids: {', '.join(cities)}")


@probe("tools.choice_none", "tools", "tool_choice=\"none\" suppresses tools")
def tools_choice_none(ctx: Ctx) -> Outcome:
    _, _msg, calls, text = _ask(ctx, "What's the weather in Paris right now?", tool_choice="none")
    if calls:
        return Outcome(FAIL, "tool was called despite tool_choice=none")
    if find_leak(text):
        return _leak_fail(text)
    if not text.strip():
        return Outcome(FAIL, "empty reply")
    return Outcome(PASS, "answered in text, no tool calls")


@probe("tools.choice_required", "tools", "tool_choice=\"required\" forces a call")
def tools_choice_required(ctx: Ctx) -> Outcome:
    _, _msg, calls, text = _ask(ctx, "Say hello to me.", tool_choice="required")
    if not calls:
        if find_leak(text):
            return _leak_fail(text)
        return Outcome(FAIL, f"no tool call although tool_choice=required (reply: {text.strip()[:40]!r})")
    problems = _call_problems(calls)
    if problems:
        return Outcome(FAIL, problems[0])
    return Outcome(PASS, f"forced call to {calls[0].name}")


@probe("tools.choice_named", "tools", "tool_choice={function} forces that tool")
def tools_choice_named(ctx: Ctx) -> Outcome:
    _, _msg, calls, text = _ask(
        ctx, "What's the weather in Paris right now?", tool_choice={"type": "function", "function": {"name": "get_time"}}
    )
    if not calls:
        return _leak_fail(text) if find_leak(text) else Outcome(FAIL, "no tool call although a function was forced")
    if calls[0].name != "get_time":
        return Outcome(FAIL, f"called {calls[0].name!r}; named tool_choice get_time was ignored")
    problems = _call_problems(calls)
    if problems:
        return Outcome(FAIL, problems[0])
    return Outcome(PASS, f"get_time({calls[0].raw_args})")


@probe("tools.clean_content", "tools", "No raw tool-call markup leaks into content")
def tools_clean_content(ctx: Ctx) -> Outcome:
    _, _msg, calls, text = _ask(ctx, "Check the weather in Berlin for me, please.")
    if find_leak(text):
        return _leak_fail(text)
    if not calls:
        return Outcome(WARN, "no tool call made, so leak check is inconclusive")
    return Outcome(PASS, "tool_calls structured, content clean")


def _roundtrip_msgs(results):
    calls = []
    tool_msgs = []
    for i, (city, payload) in enumerate(results):
        cid = f"call_ts_{i + 1}"
        calls.append({"id": cid, "type": "function", "function": {"name": "get_weather", "arguments": f'{{"city": "{city}"}}'}})
        tool_msgs.append({"role": "tool", "tool_call_id": cid, "content": payload})
    cities = " and ".join(c for c, _ in results)
    return [
        {"role": "system", "content": SYSTEM_TOOLS},
        {"role": "user", "content": f"What's the weather in {cities}?"},
        {"role": "assistant", "content": None, "tool_calls": calls},
        *tool_msgs,
    ]


@probe("tools.result_roundtrip", "tools", "Tool result is accepted and used")
def tools_result_roundtrip(ctx: Ctx) -> Outcome:
    res = ctx.client.post("chat/completions", ctx.payload(_roundtrip_msgs([("Paris", WEATHER_RESULT_PARIS)]), tools=TOOLS))
    if not res.ok:
        raise ProbeFail(f"server rejected a role=tool message: HTTP {res.status}: {res.snippet(100)}")
    from ..core import expect_chat

    data = expect_chat(res)
    msg = message(data)
    text = content_of(msg)
    if parse_tool_calls(msg):
        return Outcome(WARN, "called a tool again instead of answering from the result")
    if "23" in text or "sunny" in text.lower():
        return Outcome(PASS, "final answer uses the tool result")
    return Outcome(FAIL, f"answer ignores the tool result (reply: {text.strip()[:50]!r})")


@probe("tools.multi_result", "tools", "Several tool results in one turn")
def tools_multi_result(ctx: Ctx) -> Outcome:
    msgs = _roundtrip_msgs([("Paris", WEATHER_RESULT_PARIS), ("Tokyo", WEATHER_RESULT_TOKYO)])
    res = ctx.client.post("chat/completions", ctx.payload(msgs, tools=TOOLS))
    if not res.ok:
        raise ProbeFail(f"HTTP {res.status} with two tool results: {res.snippet(100)}")
    from ..core import expect_chat

    text = content_of(message(expect_chat(res)))
    has_p = "23" in text or "sunny" in text.lower()
    has_t = "17" in text or "rain" in text.lower()
    if has_p and has_t:
        return Outcome(PASS, "both results reflected in the answer")
    if has_p or has_t:
        return Outcome(WARN, "only one of two tool results used (template may drop extra tool messages)")
    return Outcome(FAIL, f"neither tool result used (reply: {text.strip()[:50]!r})")


@probe("stream.tools", "tools", "Streamed tool call assembles into valid JSON")
def stream_tools(ctx: Ctx) -> Outcome:
    msgs = [{"role": "system", "content": SYSTEM_TOOLS}, {"role": "user", "content": "What's the weather in Paris right now?"}]
    _, a = ctx.chat_stream(msgs, tools=TOOLS)
    if not a.tool_calls:
        if find_leak(a.content):
            return Outcome(FAIL, f"streamed tool call arrived as content text: {find_leak(a.content)!r}")
        return Outcome(FAIL, f"no tool_calls deltas in stream (content: {a.content.strip()[:40]!r})")
    problems = _call_problems(a.tool_calls)
    if problems:
        return Outcome(FAIL, problems[0])
    if a.finish_reason != "tool_calls":
        return Outcome(WARN, f"assembled OK but finish_reason={a.finish_reason!r}")
    return Outcome(PASS, f"{a.tool_calls[0].name}({a.tool_calls[0].raw_args}) assembled from deltas")


@probe("stream.tools_parallel", "tools", "Streamed parallel tool calls keep separate indexes")
def stream_tools_parallel(ctx: Ctx) -> Outcome:
    msgs = [{"role": "system", "content": SYSTEM_TOOLS}, {"role": "user", "content": "Get the current weather for Paris and for Tokyo."}]
    _, a = ctx.chat_stream(msgs, tools=TOOLS)
    if not a.tool_calls:
        if find_leak(a.content):
            return Outcome(FAIL, f"streamed tool calls arrived as content text: {find_leak(a.content)!r}")
        return Outcome(FAIL, "no tool_calls deltas in stream")
    problems = _call_problems(a.tool_calls)
    if problems:
        return Outcome(FAIL, problems[0])
    if len(a.tool_calls) == 1:
        return Outcome(WARN, "only 1 streamed tool call (expected 2)")
    return Outcome(PASS, f"{len(a.tool_calls)} calls assembled with distinct indexes")
