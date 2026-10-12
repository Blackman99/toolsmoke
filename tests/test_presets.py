from toolsmoke import cli
from toolsmoke.presets import PRESET_NAMES, default_base_url, quirk_hint


def test_preset_names_and_urls():
    assert "ollama" in PRESET_NAMES
    assert default_base_url("ollama") == "http://localhost:11434/v1"
    assert default_base_url("openrouter").startswith("https://")


def test_quirk_hints_only_when_relevant():
    assert quirk_hint("ollama", "tools.single")
    assert quirk_hint("llamacpp", "tools.clean_content")
    assert quirk_hint("vllm", "chat.basic") is None
    assert quirk_hint(None, "tools.single") is None


def test_cli_preset_fills_base_url(monkeypatch):
    monkeypatch.delenv("TOOLSMOKE_BASE_URL", raising=False)
    a = cli.build_parser().parse_args(["--preset", "vllm", "--model", "m"])
    assert a.base_url is None  # filled in main(), not parse
    # config path used after fill:
    a.base_url = default_base_url(a.preset)
    cfg = cli.config_from_args(a)
    assert cfg.base_url == "http://localhost:8000/v1"
    assert cfg.preset == "vllm"


def test_explicit_base_url_wins_over_preset(monkeypatch):
    monkeypatch.delenv("TOOLSMOKE_BASE_URL", raising=False)
    a = cli.build_parser().parse_args(["--preset", "ollama", "--base-url", "http://custom:9/v1", "--model", "m"])
    cfg = cli.config_from_args(a)
    assert cfg.base_url == "http://custom:9/v1"
    assert cfg.preset == "ollama"
