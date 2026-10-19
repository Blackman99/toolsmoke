"""Responses API probes (--responses) and repeat mode (--repeat N)."""

import json

from toolsmoke import cli
from toolsmoke.core import FAIL, PASS, SKIP, WARN, Result, aggregate
from toolsmoke.mock import parse_responses


def run(tmp_path, url, *extra):
    out = tmp_path / "r.json"
    code = cli.main(["--base-url", url, "--model", "mock-model", "--quiet", "--perf-runs", "1", "--json", str(out), *extra])
    return code, json.loads(out.read_text(encoding="utf-8"))


def by_id(report):
    return {r["id"]: r for r in report["results"]}


def test_responses_probes_are_opt_in(tmp_path, start_mock):
    url = start_mock(mode="good")
    code, report = run(tmp_path, url, "--only", "responses.*")
    assert code == 0 and report["responses"] is False
    assert {r["status"] for r in report["results"]} == {"skip"}
    assert "use --responses" in report["results"][0]["detail"]


def test_responses_probes_pass_on_good_server(tmp_path, start_mock):
    url = start_mock(mode="good")
    code, report = run(tmp_path, url, "--only", "responses.*", "--responses")
    r = by_id(report)
    assert code == 0, r
    assert set(r) == {"responses.basic", "responses.stream", "responses.tools", "responses.stream_tools", "responses.tool_result"}
    assert all(x["status"] == "pass" for x in r.values()), r
    assert "assembled from deltas" in r["responses.stream_tools"]["detail"]


def test_responses_missing_endpoint_fails(tmp_path, start_mock):
    url = start_mock(mode="good", defects=["no_responses"])
    code, report = run(tmp_path, url, "--only", "responses.*", "--responses")
    assert code == 1
    assert all(x["status"] == "fail" and "404" in x["detail"] for x in report["results"])


def test_responses_leaked_tool_call(tmp_path, start_mock):
    url = start_mock(mode="good", defects=["leak_tool_calls", "stream_tool_leak"])
    _, report = run(tmp_path, url, "--only", "responses.*tools", "--responses")
    r = by_id(report)
    assert r["responses.tools"]["status"] == "fail" and "leaked" in r["responses.tools"]["detail"]
    assert r["responses.stream_tools"]["status"] == "fail" and "leaked" in r["responses.stream_tools"]["detail"]


def test_parse_responses_items():
    conv = parse_responses({
        "instructions": "Be brief.",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "weather in Paris?"}]},
            {"type": "function_call", "call_id": "c1", "name": "get_weather", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "c1", "output": "sunny"},
        ],
        "tools": [{"type": "function", "name": "get_weather", "parameters": {"type": "object"}}],
        "tool_choice": {"type": "function", "name": "get_weather"},
        "max_output_tokens": 9,
    })
    assert conv.system.startswith("Be brief.") and conv.last_user == "weather in Paris?"
    assert conv.tool_results == ["sunny"] and conv.tools[0]["name"] == "get_weather"
    assert conv.tool_choice == ("named", "get_weather") and conv.max_tokens == 9


def _r(status, detail="d", t=0.1):
    return Result("x.y", "x", "X", status, detail, t, {"k": status})


def test_aggregate_worst_status_wins_and_shows_pass_rate():
    agg = aggregate([_r(PASS, "ok"), _r(FAIL, "leaked", 0.3), _r(PASS, "ok"), _r(WARN, "meh", 0.2)])
    assert agg.status == FAIL
    assert agg.detail == "flaky: 2/4 pass, 1 fail, 1 warn · leaked"
    assert agg.metrics["repeat"] == {"runs": 4, "pass": 2, "warn": 1, "fail": 1, "skip": 0, "pass_rate": 0.5}
    assert agg.metrics["k"] == FAIL and agg.elapsed == 0.2


def test_aggregate_stable_and_single():
    agg = aggregate([_r(PASS, "ok"), _r(PASS, "ok"), _r(PASS, "ok")])
    assert agg.status == PASS and agg.detail == "3/3 pass · ok"
    one = _r(SKIP, "off")
    assert aggregate([one]) is one


def test_repeat_catches_flaky_tool_calls(tmp_path, start_mock):
    url = start_mock(mode="good", defects=["flaky_tools"])
    code, report = run(tmp_path, url, "--only", "tools.single")
    assert code == 0  # one shot looks fine
    code, report = run(tmp_path, url, "--only", "tools.single", "--repeat", "4")
    r = report["results"][0]
    assert code == 1 and report["repeat"] == 4
    assert r["status"] == "fail" and r["detail"].startswith("flaky: 2/4 pass, 2 fail · ")
    assert r["metrics"]["repeat"]["pass_rate"] == 0.5


def test_repeat_skips_once_and_shows_in_header(tmp_path, start_mock, capsys):
    url = start_mock(mode="good")
    assert cli.main(["--base-url", url, "--model", "mock-model", "--only", "anthropic.basic", "--repeat", "3", "-q"]) == 0
    out = capsys.readouterr().out
    assert "repeat 3" in out and "Anthropic probes off" in out and "3/3" not in out


def test_repeat_bounds(capsys):
    assert cli.main(["--base-url", "http://127.0.0.1:9/v1", "--model", "m", "--repeat", "0"]) == 2
    assert "--repeat" in capsys.readouterr().err
