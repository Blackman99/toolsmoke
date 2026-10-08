import pytest

from toolsmoke.mock import Conv, decide, parse_anthropic, parse_openai, resolve_defects, BadRequest


def test_resolve_defects():
    assert resolve_defects("good") == set()
    assert "stream_tool_leak" in resolve_defects("broken")
    assert "no_usage" not in resolve_defects("broken", ["-no_usage"])
    assert resolve_defects("good", ["no_parallel"]) == {"no_parallel"}
    with pytest.raises(ValueError):
        resolve_defects("good", ["nope"])


def test_decide_parallel_and_defect():
    conv = Conv(turns=[("user", "Weather for Paris and Tokyo?")], tools=[{"name": "get_weather", "schema": {}}])
    assert [a["city"] for _, a in decide(conv, set()).calls] == ["Paris", "Tokyo"]
    assert len(decide(conv, {"no_parallel"}).calls) == 1


def test_decide_stop_and_max_tokens():
    conv = Conv(turns=[("user", "count from 1 to 20")], stop=["7"])
    assert "7" not in decide(conv, set()).text
    conv = Conv(turns=[("user", "write about the ocean")], max_tokens=5)
    r = decide(conv, set())
    assert r.finish == "length" and len(r.text.split()) == 5


def test_parse_openai_roles_and_tool_results():
    with pytest.raises(BadRequest):
        parse_openai({"messages": [{"role": "wizard", "content": "x"}]})
    conv = parse_openai({"messages": [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": None, "tool_calls": []},
        {"role": "tool", "tool_call_id": "1", "content": "r1"},
        {"role": "tool", "tool_call_id": "2", "content": "r2"},
    ], "tool_choice": {"type": "function", "function": {"name": "f"}}})
    assert conv.tool_results == ["r1", "r2"] and conv.tool_choice == ("named", "f")


def test_parse_anthropic_tool_result():
    conv = parse_anthropic({"messages": [
        {"role": "user", "content": "q"},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "res"}]},
    ], "tool_choice": {"type": "any"}})
    assert conv.tool_results == ["res"] and conv.tool_choice == "required"
