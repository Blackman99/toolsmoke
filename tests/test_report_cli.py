
from toolsmoke import cli
from toolsmoke.core import FAIL, PASS, REGISTRY, SKIP, WARN, Config, Probe, Result, exit_code, select
from toolsmoke.report import markdown, table, to_json, verdict

CFG = Config(base_url="http://x/v1", model="m")


def R(status, id="a.b"):
    return Result(id, "g", "t", status, "detail | pipe", 0.12)


def test_exit_codes():
    assert exit_code([R(PASS), R(SKIP)]) == 0
    assert exit_code([R(PASS), R(WARN)]) == 0
    assert exit_code([R(PASS), R(WARN)], strict=True) == 1
    assert exit_code([R(FAIL)]) == 1


def test_verdicts():
    assert verdict([R(PASS)]) == "AGENT-READY"
    assert verdict([R(WARN)]) == "AGENT-READY, with warnings"
    assert verdict([R(FAIL), R(FAIL)]).startswith("NOT AGENT-READY: 2")


def test_select_globs():
    probes = [Probe("tools.single", "tools", "", lambda c: None), Probe("chat.basic", "basics", "", lambda c: None)]
    assert [p.id for p in select(probes, ["tools.*"], [])] == ["tools.single"]
    assert [p.id for p in select(probes, ["basics"], [])] == ["chat.basic"]
    assert [p.id for p in select(probes, [], ["tools*"])] == ["chat.basic"]


def test_renderers():
    rs = [R(PASS, "x.one"), R(FAIL, "x.two")]
    t = table(rs, CFG, color=False, width=100)
    assert "x.two" in t and "FAIL" in t and "NOT AGENT-READY" in t
    md = markdown(rs, CFG)
    assert "| `x.one` | ✅ PASS |" in md and "detail \\| pipe" in md
    j = to_json(rs, CFG)
    assert j["summary"] == {"pass": 1, "warn": 0, "fail": 1, "skip": 0}
    assert j["results"][1]["status"] == "fail"


def test_registry_ids_unique_and_count():
    ids = [p.id for p in REGISTRY]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 25


def test_cli_requires_url_and_model(capsys, monkeypatch):
    monkeypatch.delenv("TOOLSMOKE_BASE_URL", raising=False)
    monkeypatch.delenv("TOOLSMOKE_MODEL", raising=False)
    assert cli.main([]) == 2
    assert "required" in capsys.readouterr().err


def test_cli_unreachable_is_exit_2(capsys):
    assert cli.main(["--base-url", "http://127.0.0.1:9/v1", "--model", "m", "--timeout", "2"]) == 2
    assert "cannot reach" in capsys.readouterr().err


def test_cli_list(capsys):
    assert cli.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "tools.parallel" in out and "anthropic.tools" in out


def test_cli_bad_header(capsys, good_server):
    assert cli.main(["--base-url", good_server, "--model", "mock-model", "-H", "nocolon"]) == 2


def test_api_key_env_resolution(monkeypatch):
    monkeypatch.delenv("TOOLSMOKE_API_KEY", raising=False)
    monkeypatch.setenv("MY_KEY", "sk-1")
    a = cli.build_parser().parse_args(["--base-url", "http://x/v1", "--model", "m", "--api-key-env", "MY_KEY", "--temperature", "none"])
    cfg = cli.config_from_args(a)
    assert cfg.api_key == "sk-1" and cfg.temperature is None
    monkeypatch.setenv("TOOLSMOKE_API_KEY", "sk-2")
    assert cli.config_from_args(a).api_key == "sk-2"
