"""Command-line interface."""

from __future__ import annotations

import argparse
import os
import sys
import threading
from typing import List, Optional

from . import __version__
from .core import REGISTRY, Config, Ctx, exit_code, run_probe, select
from . import probes as _probes  # noqa: F401  (registers probes)
from .client import TransportError
from .report import markdown, table, to_json_text

EPILOG = """examples:
  toolsmoke --base-url http://localhost:8080/v1 --model qwen3-coder
  OPENAI_API_KEY=sk-... toolsmoke --base-url https://api.example.com/v1 --model my-model --anthropic
  toolsmoke --base-url http://localhost:11434/v1 --model llama3.1 --only 'tools.*' --json report.json
  toolsmoke --demo broken          # try it against the bundled mock server

exit codes: 0 = no failures, 1 = at least one FAIL (or WARN with --strict), 2 = usage/connection error
docs: https://blackman99.github.io/toolsmoke/docs/
"""


def env(name: str, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="toolsmoke",
        description="Check whether an OpenAI-compatible (and Anthropic-style) LLM endpoint actually works for agents, and how fast it is.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--base-url", default=env("TOOLSMOKE_BASE_URL"), help="OpenAI-compatible base URL, e.g. http://localhost:8080/v1 [env TOOLSMOKE_BASE_URL]")
    p.add_argument("--model", "-m", default=env("TOOLSMOKE_MODEL"), help="model name to request [env TOOLSMOKE_MODEL]")
    p.add_argument("--api-key-env", default=env("TOOLSMOKE_API_KEY_ENV", "OPENAI_API_KEY"), metavar="NAME", help="name of the env var holding the API key (default: OPENAI_API_KEY; TOOLSMOKE_API_KEY always wins)")
    p.add_argument("--header", "-H", action="append", default=[], metavar="'K: V'", help="extra HTTP header (repeatable)")
    p.add_argument("--anthropic", action="store_true", default=env("TOOLSMOKE_ANTHROPIC") in ("1", "true", "yes"), help="also probe the Anthropic Messages API (POST /v1/messages)")
    p.add_argument("--anthropic-base-url", default=env("TOOLSMOKE_ANTHROPIC_BASE_URL"), metavar="URL", help="base URL for the Messages API if different (default: --base-url)")
    p.add_argument("--only", action="append", default=[], metavar="GLOB", help="run only probes whose id or group matches (repeatable), e.g. 'tools.*'")
    p.add_argument("--skip", action="append", default=[], metavar="GLOB", help="skip probes whose id or group matches (repeatable)")
    p.add_argument("--strict", action="store_true", help="treat warnings as failures for the exit code")
    p.add_argument("--require-reasoning", action="store_true", help="fail reasoning.field if no reasoning is returned")
    p.add_argument("--format", "-f", choices=["table", "json", "markdown"], default="table", help="stdout format (default: table)")
    p.add_argument("--json", dest="json_out", metavar="FILE", help="also write the JSON report to FILE")
    p.add_argument("--markdown", dest="md_out", metavar="FILE", help="also write a Markdown report to FILE (append)")
    p.add_argument("--timeout", type=float, default=float(env("TOOLSMOKE_TIMEOUT", 120)), help="per-request timeout in seconds (default: 120)")
    p.add_argument("--max-tokens", type=int, default=1024, help="max tokens for most probes (default: 1024)")
    p.add_argument("--token-param", choices=["max_tokens", "max_completion_tokens"], default="max_tokens", help="parameter name used for the token limit")
    p.add_argument("--temperature", default="0", help="sampling temperature, or 'none' to omit it (default: 0)")
    p.add_argument("--max-ttft", type=float, metavar="MS", help="FAIL perf.ttft if median TTFT exceeds MS")
    p.add_argument("--min-tps", type=float, metavar="N", help="FAIL perf.throughput below N tokens/sec")
    p.add_argument("--perf-runs", type=int, default=3, help="streaming runs for the TTFT median (default: 3)")
    p.add_argument("--list", action="store_true", help="list probes and exit")
    p.add_argument("--demo", nargs="?", const="broken", choices=["good", "broken"], help="run against the bundled mock server (default mode: broken)")
    p.add_argument("--quiet", "-q", action="store_true", help="no live progress on stderr")
    p.add_argument("--version", action="version", version=f"toolsmoke {__version__}")
    return p


def parse_headers(items: List[str]) -> dict:
    out = {}
    for h in items:
        k, sep, v = h.partition(":")
        if not sep or not k.strip():
            raise ValueError(f"bad --header {h!r}, expected 'Name: value'")
        out[k.strip()] = v.strip()
    return out


def config_from_args(a: argparse.Namespace) -> Config:
    key = env("TOOLSMOKE_API_KEY") or (env(a.api_key_env) if a.api_key_env else None)
    temp = None if str(a.temperature).lower() in ("none", "null", "") else float(a.temperature)
    return Config(
        base_url=a.base_url.rstrip("/"),
        model=a.model,
        api_key=key,
        timeout=a.timeout,
        headers=parse_headers(a.header),
        anthropic=a.anthropic,
        anthropic_base_url=a.anthropic_base_url,
        require_reasoning=a.require_reasoning,
        temperature=temp,
        token_param=a.token_param,
        max_tokens=a.max_tokens,
        max_ttft_ms=a.max_ttft,
        min_tps=a.min_tps,
        perf_runs=a.perf_runs,
    )


def start_demo(mode: str):
    from .mock import serve

    server = serve("127.0.0.1", 0, mode=mode, ttft_ms=150, tps=120, api_key=None)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


def _safe_streams() -> None:
    # Windows consoles/redirects may not be UTF-8; never crash on "·" or emoji.
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if enc != "utf8" and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def main(argv: Optional[List[str]] = None) -> int:
    _safe_streams()
    parser = build_parser()
    a = parser.parse_args(argv)

    if a.list:
        for p in REGISTRY:
            print(f"{p.id:<24} {p.group:<12} {p.title}")
        return 0

    demo_server = None
    if a.demo:
        demo_server, a.base_url = start_demo(a.demo)
        a.model = a.model or "mock-model"
        a.anthropic = True

    if not a.base_url or not a.model:
        parser.print_usage(sys.stderr)
        print("toolsmoke: error: --base-url and --model are required (or set TOOLSMOKE_BASE_URL / TOOLSMOKE_MODEL)", file=sys.stderr)
        return 2
    try:
        cfg = config_from_args(a)
    except ValueError as e:
        print(f"toolsmoke: error: {e}", file=sys.stderr)
        return 2

    ctx = Ctx(cfg)
    chosen = select(REGISTRY, a.only, a.skip)
    if not chosen:
        print("toolsmoke: error: no probes match --only/--skip", file=sys.stderr)
        return 2

    # Preflight: fail fast with exit 2 if nothing is listening.
    try:
        ctx.client.get("models")
    except TransportError as e:
        print(f"toolsmoke: error: cannot reach {cfg.base_url}: {e}", file=sys.stderr)
        return 2

    live = not a.quiet and sys.stderr.isatty() and a.format == "table"
    results = []
    for i, p in enumerate(chosen, 1):
        if live:
            sys.stderr.write(f"\r\033[K  [{i}/{len(chosen)}] {p.id} …")
            sys.stderr.flush()
        results.append(run_probe(p, ctx))
    if live:
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    if a.format == "json":
        print(to_json_text(results, cfg, a.strict))
    elif a.format == "markdown":
        print(markdown(results, cfg, a.strict), end="")
    else:
        print(table(results, cfg, a.strict))

    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            f.write(to_json_text(results, cfg, a.strict) + "\n")
    if a.md_out:
        with open(a.md_out, "a", encoding="utf-8") as f:
            f.write(markdown(results, cfg, a.strict) + "\n")

    if demo_server is not None:
        demo_server.shutdown()
    return exit_code(results, a.strict)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
