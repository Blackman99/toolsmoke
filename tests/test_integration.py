"""End-to-end: run the real CLI against the bundled mock server."""

import json

from toolsmoke import cli

GOOD_ALL_PASS_EXCEPT = set()

BROKEN_EXPECTED = {
    "chat.basic": "warn",
    "chat.stop": "fail",
    "stream.usage": "warn",
    "tools.parallel": "warn",
    "tools.choice_none": "fail",
    "tools.choice_required": "fail",
    "tools.choice_named": "fail",
    "stream.tools": "fail",
    "stream.tools_parallel": "fail",
    "json.schema": "fail",
    "reasoning.field": "fail",
    "errors.bad_model": "warn",
    "errors.bad_request": "fail",
    "anthropic.basic": "fail",
    "anthropic.stream": "fail",
    "anthropic.tools": "fail",
    "anthropic.tool_result": "fail",
}


def run(tmp_path, url, *extra, env_key=None, monkeypatch=None):
    out = tmp_path / "r.json"
    code = cli.main(["--base-url", url, "--model", "mock-model", "--anthropic", "--quiet", "--perf-runs", "1",
                     "--json", str(out), *extra])
    return code, json.loads(out.read_text())


def test_good_server_is_agent_ready(tmp_path, good_server, monkeypatch, capsys):
    monkeypatch.setenv("TOOLSMOKE_API_KEY", "sk-test")
    code, report = run(tmp_path, good_server)
    statuses = {r["id"]: r["status"] for r in report["results"]}
    assert code == 0, capsys.readouterr().out
    bad = {k: v for k, v in statuses.items() if v != "pass"}
    assert bad == {}, bad
    assert report["verdict"] == "AGENT-READY"
    assert report["performance"]["tokens_per_sec"] > 0
    assert report["performance"]["ttft_ms_p50"] is not None


def test_broken_server_flags_each_defect(tmp_path, broken_server, monkeypatch):
    monkeypatch.delenv("TOOLSMOKE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    code, report = run(tmp_path, broken_server)
    statuses = {r["id"]: r["status"] for r in report["results"]}
    assert code == 1
    for pid, expected in BROKEN_EXPECTED.items():
        assert statuses[pid] == expected, (pid, statuses[pid])
    assert statuses["errors.bad_auth"] == "skip"
    # everything not listed as broken should still pass
    for pid, st in statuses.items():
        if pid not in BROKEN_EXPECTED and pid != "errors.bad_auth":
            assert st == "pass", (pid, st)


def test_wrong_key_is_rejected_by_good_server(tmp_path, good_server, monkeypatch):
    monkeypatch.setenv("TOOLSMOKE_API_KEY", "sk-wrong")
    code = cli.main(["--base-url", good_server, "--model", "mock-model", "--only", "chat.basic", "--quiet"])
    assert code == 1


def test_leak_in_non_streamed_tool_calls(tmp_path, start_mock, monkeypatch):
    monkeypatch.delenv("TOOLSMOKE_API_KEY", raising=False)
    url = start_mock(mode="good", defects=["leak_tool_calls"])
    code, report = run(tmp_path, url, "--only", "tools.*")
    statuses = {r["id"]: r for r in report["results"]}
    assert code == 1
    assert statuses["tools.single"]["status"] == "fail"
    assert "leaked" in statuses["tools.single"]["detail"]
    assert statuses["tools.clean_content"]["status"] == "fail"


def test_dropped_tool_results_warn(tmp_path, start_mock, monkeypatch):
    monkeypatch.delenv("TOOLSMOKE_API_KEY", raising=False)
    url = start_mock(mode="good", defects=["drop_extra_tool_results"])
    _, report = run(tmp_path, url, "--only", "tools.multi_result")
    assert report["results"][0]["status"] == "warn"


def test_strict_and_perf_gates(tmp_path, start_mock, monkeypatch):
    monkeypatch.delenv("TOOLSMOKE_API_KEY", raising=False)
    url = start_mock(mode="good", defects=["no_usage"])
    code, _ = run(tmp_path, url, "--only", "stream.usage")
    assert code == 0  # warn only
    code, _ = run(tmp_path, url, "--only", "stream.usage", "--strict")
    assert code == 1
    code, report = run(tmp_path, url, "--only", "perf.*", "--min-tps", "1000000")
    assert code == 1 and report["results"][-1]["status"] == "fail"


def test_markdown_and_json_stdout(tmp_path, good_server, monkeypatch, capsys):
    monkeypatch.setenv("TOOLSMOKE_API_KEY", "sk-test")
    md = tmp_path / "summary.md"
    assert cli.main(["--base-url", good_server, "--model", "mock-model", "--only", "chat.*", "--format", "json", "--markdown", str(md)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["pass"] == 5
    assert "| `chat.basic` | ✅ PASS |" in md.read_text()
