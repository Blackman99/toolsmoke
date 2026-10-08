import json

from toolsmoke.client import SSEEvent, StreamResult, iter_sse, parse_json_events
from toolsmoke.core import assemble_chat_stream, find_leak, find_think, make_call, parse_tool_calls, reasoning_of


def lines(text):
    return [l.encode() + b"\n" for l in text.split("\n")]


def test_iter_sse_events_comments_multiline():
    evs = list(iter_sse(lines(": ping\nevent: a\ndata: {\"x\":1}\n\ndata: line1\ndata: line2\n\ndata: [DONE]\n"), clock=lambda: 1.0))
    assert [(e.event, e.data) for e in evs] == [("a", '{"x":1}'), (None, "line1\nline2"), (None, "[DONE]")]


def test_iter_sse_crlf_and_no_trailing_blank():
    evs = list(iter_sse([b"data: one\r\n", b"\r\n", b"data:two"], clock=lambda: 0))
    assert [e.data for e in evs] == ["one", "two"]


def test_parse_json_events_done_and_errors():
    evs = [SSEEvent(0, None, '{"a":1}'), SSEEvent(0, None, "oops"), SSEEvent(0, None, "[DONE]")]
    items, done, bad = parse_json_events(evs)
    assert done and bad == ["oops"] and items[0][2] == {"a": 1}


def _stream(chunks):
    evs = [SSEEvent(i * 0.01, None, json.dumps(c)) for i, c in enumerate(chunks)] + [SSEEvent(1, None, "[DONE]")]
    return StreamResult(200, 0.0, 0.0, 1.0, evs)


def test_assemble_tool_call_deltas():
    def tc(**kw):
        return {"choices": [{"index": 0, "delta": {"tool_calls": [kw]}}]}

    res = _stream([
        {"choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}}]},
        tc(index=0, id="call_a", type="function", function={"name": "get_weather", "arguments": ""}),
        tc(index=0, function={"arguments": '{"city": '}),
        tc(index=1, id="call_b", function={"name": "get_weather", "arguments": '{"city": "Tokyo"}'}),
        tc(index=0, function={"arguments": '"Paris"}'}),
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
        {"choices": [], "usage": {"completion_tokens": 12}},
    ])
    a = assemble_chat_stream(res)
    assert a.done and a.finish_reason == "tool_calls" and a.usage == {"completion_tokens": 12}
    assert [c.args for c in a.tool_calls] == [{"city": "Paris"}, {"city": "Tokyo"}]
    assert [c.id for c in a.tool_calls] == ["call_a", "call_b"]
    assert a.t_first is not None


def test_assemble_content_and_reasoning():
    res = _stream([
        {"choices": [{"index": 0, "delta": {"reasoning_content": "hmm "}}]},
        {"choices": [{"index": 0, "delta": {"content": "Hi"}}]},
        {"choices": [{"index": 0, "delta": {"content": " there"}, "finish_reason": "stop"}]},
    ])
    a = assemble_chat_stream(res)
    assert a.content == "Hi there" and a.reasoning == "hmm " and a.content_chunks == 2


def test_make_call_problems():
    assert make_call("id", "f", '{"a": 1}').problems == []
    assert "not valid JSON" in make_call("id", "f", '{"a": ').problems[0]
    assert "JSON object" in make_call("id", "f", {"a": 1}).problems[0]
    assert "no id" in " ".join(make_call(None, "f", "{}").problems)


def test_parse_tool_calls_from_message():
    msg = {"tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_time", "arguments": '{"timezone": "UTC"}'}}]}
    (c,) = parse_tool_calls(msg)
    assert c.name == "get_time" and c.args == {"timezone": "UTC"}


def test_leak_and_think_detection():
    assert find_leak('<tool_call>\n{"name": "get_weather", "arguments": {}}')
    assert find_leak("[TOOL_CALLS] [{...}]")
    assert find_leak("<function=get_weather>{}</function>")
    assert find_leak("The weather in Paris is sunny.") is None
    assert find_think("<think>hmm</think> 391") == "<think>"
    assert find_think("391") is None


def test_reasoning_of_variants():
    assert reasoning_of({"reasoning_content": "x"})[0] == "reasoning_content"
    assert reasoning_of({"reasoning": "x"})[0] == "reasoning"
    assert reasoning_of({"reasoning_details": [{"text": "x"}]})[0] == "reasoning_details"
    assert reasoning_of({"content": "x"}) == (None, "")
