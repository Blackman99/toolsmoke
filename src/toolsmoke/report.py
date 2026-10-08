"""Render results as a terminal table, JSON or Markdown."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .core import FAIL, PASS, SKIP, WARN, Config, Result, summarize

LABEL = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL", SKIP: "SKIP"}
COLOR = {PASS: "32", WARN: "33", FAIL: "31", SKIP: "90"}
EMOJI = {PASS: "✅", WARN: "⚠️", FAIL: "❌", SKIP: "⏭️"}


def use_color(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def _c(text: str, code: str, on: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if on else text


def fmt_ms(seconds: float) -> str:
    if seconds <= 0:
        return "-"
    ms = seconds * 1000
    return f"{ms:.0f}ms" if ms < 1000 else f"{seconds:.1f}s"


def headline(results: List[Result]) -> Dict[str, Any]:
    ttft = tps = None
    for r in results:
        if r.id == "perf.ttft" and r.metrics.get("ttft_ms_p50") is not None:
            ttft = r.metrics["ttft_ms_p50"]
        if r.id == "perf.throughput" and r.metrics.get("tokens_per_sec") is not None:
            tps = r.metrics["tokens_per_sec"]
    return {"ttft_ms_p50": ttft, "tokens_per_sec": tps}


def verdict(results: List[Result], strict: bool = False) -> str:
    s = summarize(results)
    if s[FAIL]:
        return f"NOT AGENT-READY: {s[FAIL]} failing probe{'s' if s[FAIL] != 1 else ''}"
    if s[WARN] and strict:
        return f"NOT AGENT-READY (strict): {s[WARN]} warning{'s' if s[WARN] != 1 else ''}"
    if s[WARN]:
        return "AGENT-READY, with warnings"
    return "AGENT-READY"


def table(results: List[Result], cfg: Config, strict: bool = False, color: Optional[bool] = None, width: Optional[int] = None) -> str:
    on = use_color() if color is None else color
    if width is None:
        try:
            width = os.get_terminal_size().columns
        except OSError:
            width = 120
    width = max(80, min(width, 160))
    idw = max([len(r.id) for r in results] + [5])
    lines = [
        _c(f"toolsmoke {__version__}", "1", on) + f" · {cfg.base_url} · model {cfg.model}",
        "",
        "  " + _c(f"{'PROBE':<{idw}}  {'RESULT':<6}  {'TIME':>6}  DETAIL", "1", on),
    ]
    detail_w = width - idw - 22
    for r in results:
        d = r.detail if len(r.detail) <= detail_w else r.detail[: detail_w - 1] + "…"
        label = _c(f"{LABEL[r.status]:<6}", COLOR[r.status], on)
        lines.append(f"  {r.id:<{idw}}  {label}  {fmt_ms(r.elapsed):>6}  {d}")
    s = summarize(results)
    h = headline(results)
    perf = []
    if h["ttft_ms_p50"] is not None:
        perf.append(f"TTFT p50 {h['ttft_ms_p50']:.0f} ms")
    if h["tokens_per_sec"] is not None:
        perf.append(f"{h['tokens_per_sec']:.1f} tok/s")
    counts = f"{s[PASS]} pass · {s[WARN]} warn · {s[FAIL]} fail · {s[SKIP]} skip"
    v = verdict(results, strict)
    vcode = COLOR[FAIL] if v.startswith("NOT") else (COLOR[WARN] if "warn" in v else COLOR[PASS])
    lines += ["", "  " + " · ".join(perf + [counts]), "  " + _c(v, "1;" + vcode, on)]
    return "\n".join(lines)


def to_json(results: List[Result], cfg: Config, strict: bool = False) -> Dict[str, Any]:
    return {
        "tool": "toolsmoke",
        "version": __version__,
        "endpoint": cfg.base_url,
        "model": cfg.model,
        "anthropic": cfg.anthropic,
        "summary": summarize(results),
        "performance": headline(results),
        "verdict": verdict(results, strict),
        "results": [r.to_dict() for r in results],
    }


def to_json_text(results: List[Result], cfg: Config, strict: bool = False) -> str:
    return json.dumps(to_json(results, cfg, strict), indent=2, ensure_ascii=False)


def markdown(results: List[Result], cfg: Config, strict: bool = False) -> str:
    s = summarize(results)
    h = headline(results)
    perf = []
    if h["ttft_ms_p50"] is not None:
        perf.append(f"TTFT p50 **{h['ttft_ms_p50']:.0f} ms**")
    if h["tokens_per_sec"] is not None:
        perf.append(f"**{h['tokens_per_sec']:.1f} tok/s**")
    out = [
        f"### toolsmoke: {verdict(results, strict)}",
        "",
        f"`{cfg.model}` @ `{cfg.base_url}` · {s[PASS]} pass · {s[WARN]} warn · {s[FAIL]} fail · {s[SKIP]} skip"
        + (" · " + " · ".join(perf) if perf else ""),
        "",
        "| Probe | Result | Time | Detail |",
        "|---|---|---|---|",
    ]
    for r in results:
        detail = r.detail.replace("|", "\\|").replace("\n", " ")
        out.append(f"| `{r.id}` | {EMOJI[r.status]} {LABEL[r.status]} | {fmt_ms(r.elapsed)} | {detail} |")
    return "\n".join(out) + "\n"
