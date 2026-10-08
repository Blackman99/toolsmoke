"""Probe framework: config, context, registry, runner and shared helpers."""

from __future__ import annotations

import fnmatch
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .client import Client, HTTPResult, StreamResult, TransportError, parse_json_events

PASS, WARN, FAIL, SKIP = "pass", "warn", "fail", "skip"
STATUS_ORDER = {FAIL: 0, WARN: 1, PASS: 2, SKIP: 3}


@dataclass
class Config:
    base_url: str
    model: str
    api_key: Optional[str] = None
    timeout: float = 60.0
    headers: Dict[str, str] = field(default_factory=dict)
    anthropic: bool = False
    anthropic_base_url: Optional[str] = None
    require_reasoning: bool = False
    temperature: Optional[float] = 0.0
    token_param: str = "max_tokens"
    max_tokens: int = 1024
    max_ttft_ms: Optional[float] = None
    min_tps: Optional[float] = None
    warn_ttft_ms: float = 3000.0
    warn_tps: float = 15.0
    perf_runs: int = 3


@dataclass
class Outcome:
    status: str
    detail: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Result:
    id: str
    group: str
    title: str
    status: str
    detail: str
    elapsed: float
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "group": self.group,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "elapsed_ms": round(self.elapsed * 1000, 1),
            "metrics": self.metrics,
        }


class ProbeFail(Exception):
    pass


@dataclass
class Probe:
    id: str
    group: str
    title: str
    fn: Callable[["Ctx"], Outcome]
    needs: Optional[str] = None  # "anthropic" | "api_key"


REGISTRY: List[Probe] = []


def probe(id: str, group: str, title: str, needs: Optional[str] = None):
    def deco(fn: Callable[["Ctx"], Outcome]):
        REGISTRY.append(Probe(id, group, title, fn, needs))
        return fn

    return deco


def anthropic_base(cfg: Config) -> str:
    if cfg.anthropic_base_url:
        return cfg.anthropic_base_url.rstrip("/")
    base = cfg.base_url.rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


class Ctx:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client = Client(cfg.base_url, cfg.api_key, cfg.timeout, cfg.headers, "openai")
        self.aclient = Client(anthropic_base(cfg), cfg.api_key, cfg.timeout, cfg.headers, "anthropic")
        self.cache: Dict[str, Any] = {}

    # -- OpenAI chat helpers ---------------------------------------------
    def payload(self, messages: List[Dict[str, Any]], **params: Any) -> Dict[str, Any]:
        p: Dict[str, Any] = {"model": self.cfg.model, "messages": messages}
        if self.cfg.temperature is not None:
            p["temperature"] = self.cfg.temperature
        max_tokens = params.pop("max_tokens", self.cfg.max_tokens)
        if max_tokens:
            p[self.cfg.token_param] = max_tokens
        p.update({k: v for k, v in params.items() if v is not None})
        return p

    def chat(self, messages: List[Dict[str, Any]], **params: Any) -> Tuple[HTTPResult, Dict[str, Any]]:
        res = self.client.post("chat/completions", self.payload(messages, **params))
        return res, expect_chat(res)

    def chat_stream(self, messages: List[Dict[str, Any]], **params: Any) -> Tuple[StreamResult, "Assembled"]:
        p = self.payload(messages, stream=True, **params)
        res = self.client.stream("chat/completions", p)
        if not res.ok:
            raise ProbeFail(f"HTTP {res.status}: {res.snippet()}")
        if not res.events:
            raise ProbeFail(f"no SSE events (Content-Type: {res.content_type or 'none'}): {res.snippet()}")
        return res, assemble_chat_stream(res)


def expect_chat(res: HTTPResult) -> Dict[str, Any]:
    if not res.ok:
        raise ProbeFail(f"HTTP {res.status}: {res.snippet()}")
    data = res.try_json()
    if not isinstance(data, dict):
        raise ProbeFail(f"response is not JSON: {res.snippet()}")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProbeFail(f"no choices[0] in response: {res.snippet()}")
    if not isinstance(choices[0].get("message"), dict):
        raise ProbeFail("choices[0].message missing")
    return data


def message(data: Dict[str, Any]) -> Dict[str, Any]:
    return data["choices"][0]["message"]


def finish_reason(data: Dict[str, Any]) -> Optional[str]:
    return data["choices"][0].get("finish_reason")


def content_of(msg: Dict[str, Any]) -> str:
    c = msg.get("content")
    if isinstance(c, list):  # some servers return content parts
        return "".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c or ""


def reasoning_of(msg: Dict[str, Any]) -> Tuple[Optional[str], str]:
    for key in ("reasoning_content", "reasoning", "thinking"):
        v = msg.get(key)
        if isinstance(v, str) and v.strip():
            return key, v
        if isinstance(v, dict) and v:
            return key, json.dumps(v)
    details = msg.get("reasoning_details")
    if isinstance(details, list) and details:
        return "reasoning_details", json.dumps(details)
    return None, ""


# -- tool calls --------------------------------------------------------------

@dataclass
class ToolCall:
    id: Optional[str]
    name: Optional[str]
    raw_args: Any
    args: Optional[Dict[str, Any]]
    problems: List[str] = field(default_factory=list)


def parse_tool_calls(msg: Dict[str, Any]) -> List[ToolCall]:
    out: List[ToolCall] = []
    for tc in msg.get("tool_calls") or []:
        fn = (tc or {}).get("function") or {}
        out.append(make_call(tc.get("id"), fn.get("name"), fn.get("arguments")))
    return out


def make_call(id_: Optional[str], name: Optional[str], raw: Any) -> ToolCall:
    problems: List[str] = []
    args: Optional[Dict[str, Any]] = None
    if isinstance(raw, dict):
        args = raw
        problems.append("arguments is a JSON object, the spec says a JSON-encoded string")
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw) if raw.strip() else {}
            if isinstance(parsed, dict):
                args = parsed
            else:
                problems.append(f"arguments decode to {type(parsed).__name__}, not an object")
        except ValueError:
            problems.append(f"arguments are not valid JSON: {raw[:60]!r}")
    else:
        problems.append("arguments missing")
    if not id_:
        problems.append("tool call has no id")
    if not name:
        problems.append("tool call has no function name")
    return ToolCall(id_, name, raw, args, problems)


LEAK_PATTERNS = [
    r"<tool_call>", r"</tool_call>", r"<\|tool_call", r"<\|python_tag\|>", r"\[TOOL_CALLS\]",
    r"<function=", r"<\|start_of_tool", r"<tool_use>", r"functions\.get_(weather|time)",
    r"\"name\"\s*:\s*\"get_(weather|time)\"", r"<\|tool▁call", r"<start_function_call>",
]
THINK_PATTERNS = [r"<think>", r"</think>", r"<thinking>", r"</thinking>", r"<\|channel\|>analysis", r"◁think▷"]


def find_leak(text: str) -> Optional[str]:
    for pat in LEAK_PATTERNS:
        m = re.search(pat, text or "")
        if m:
            start = max(0, m.start() - 10)
            return (text[start : m.end() + 30]).replace("\n", " ")
    return None


def find_think(text: str) -> Optional[str]:
    for pat in THINK_PATTERNS:
        m = re.search(pat, text or "")
        if m:
            return m.group(0)
    return None


# -- streaming assembly ------------------------------------------------------

@dataclass
class Assembled:
    content: str = ""
    reasoning: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    t_first: Optional[float] = None  # first content/reasoning/tool delta
    t_last: Optional[float] = None
    chunks: int = 0
    content_chunks: int = 0
    done: bool = False
    bad_events: List[str] = field(default_factory=list)


def assemble_chat_stream(res: StreamResult) -> Assembled:
    items, done, bad = parse_json_events(res.events)
    a = Assembled(done=done, bad_events=bad)
    calls: Dict[Any, Dict[str, Any]] = {}
    order: List[Any] = []
    for t, _ev, data in items:
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("usage"), dict) and data["usage"]:
            a.usage = data["usage"]
        for ch in data.get("choices") or []:
            a.chunks += 1
            delta = ch.get("delta") or {}
            got = False
            if isinstance(delta.get("content"), str) and delta["content"]:
                a.content += delta["content"]
                a.content_chunks += 1
                got = True
            for key in ("reasoning_content", "reasoning", "thinking"):
                if isinstance(delta.get(key), str) and delta[key]:
                    a.reasoning += delta[key]
                    got = True
            for pos, tc in enumerate(delta.get("tool_calls") or []):
                key = tc.get("index", tc.get("id") or pos)
                if key not in calls:
                    calls[key] = {"id": None, "name": "", "args": ""}
                    order.append(key)
                c = calls[key]
                if tc.get("id"):
                    c["id"] = c["id"] or tc["id"]
                fn = tc.get("function") or {}
                name = fn.get("name")
                if name and name != c["name"]:
                    c["name"] = name if not c["name"] else c["name"] + name
                argpart = fn.get("arguments")
                if isinstance(argpart, str):
                    c["args"] += argpart
                elif isinstance(argpart, dict):
                    c["args"] += json.dumps(argpart)
                got = True
            if got:
                a.t_first = a.t_first or t
                a.t_last = t
            if ch.get("finish_reason"):
                a.finish_reason = ch["finish_reason"]
    a.tool_calls = [make_call(calls[k]["id"], calls[k]["name"] or None, calls[k]["args"]) for k in order]
    return a


# -- runner --------------------------------------------------------------------

def select(probes: List[Probe], only: List[str], skip: List[str]) -> List[Probe]:
    def match(p: Probe, pats: List[str]) -> bool:
        return any(fnmatch.fnmatch(p.id, pat) or fnmatch.fnmatch(p.group, pat) for pat in pats)

    out = [p for p in probes if not only or match(p, only)]
    return [p for p in out if not match(p, skip)]


def run_probe(p: Probe, ctx: Ctx) -> Result:
    if p.needs == "anthropic" and not ctx.cfg.anthropic:
        return Result(p.id, p.group, p.title, SKIP, "Anthropic probes off (use --anthropic)", 0.0)
    if p.needs == "api_key" and not ctx.cfg.api_key:
        return Result(p.id, p.group, p.title, SKIP, "no API key configured", 0.0)
    t0 = time.perf_counter()
    try:
        out = p.fn(ctx)
    except ProbeFail as e:
        out = Outcome(FAIL, str(e))
    except TransportError as e:
        out = Outcome(FAIL, f"connection error: {e}")
    except Exception as e:  # a bug in the probe or a truly weird response
        out = Outcome(FAIL, f"unexpected response ({type(e).__name__}: {e})")
    return Result(p.id, p.group, p.title, out.status, out.detail, time.perf_counter() - t0, out.metrics)


def summarize(results: List[Result]) -> Dict[str, int]:
    s = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0}
    for r in results:
        s[r.status] += 1
    return s


def exit_code(results: List[Result], strict: bool = False) -> int:
    s = summarize(results)
    if s[FAIL] or (strict and s[WARN]):
        return 1
    return 0
