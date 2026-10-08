"""A deterministic mock OpenAI- and Anthropic-compatible server.

`good` mode behaves like a well-configured server. `broken` mode turns on a
set of defects that mirror real-world failures (tool calls leaking into the
streamed content, ignored tool_choice, no parallel calls, reasoning inside
<think> tags, 500s on bad input, ...). Individual defects can be toggled with
--defects. Used by toolsmoke's own tests, `toolsmoke --demo`, and for trying
toolsmoke without a real model.

    toolsmoke-mock --port 8080 --mode broken
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple, Union

from .schema import sample

DEFECTS: Dict[str, str] = {
    "stream_tool_leak": "streamed tool calls are emitted as <tool_call> text in content",
    "leak_tool_calls": "non-streamed tool calls are emitted as <tool_call> text in content",
    "ignore_tool_choice": "tool_choice none/required/named is ignored (always auto)",
    "no_parallel": "only the first of several tool calls is returned",
    "no_usage": "no usage block in responses or streams",
    "think_in_content": "reasoning is put in content inside <think> tags",
    "ignore_json_schema": "response_format json_schema is ignored (prose reply)",
    "bad_errors": "unknown model is accepted; invalid requests return HTTP 500",
    "ignore_stop": "stop sequences are ignored",
    "no_anthropic": "POST /v1/messages returns 404",
    "drop_extra_tool_results": "only the first of several tool results is seen",
}
BROKEN_DEFAULT = [
    "stream_tool_leak", "ignore_tool_choice", "no_parallel", "no_usage", "think_in_content",
    "ignore_json_schema", "bad_errors", "ignore_stop", "no_anthropic",
]

CITIES = ["Paris", "Tokyo", "Berlin", "London", "New York", "Madrid", "Rome", "Sydney"]
OCEAN = (
    "The ocean covers more than seventy percent of our planet and holds most of its water. "
    "It regulates the climate by absorbing heat and carbon dioxide, and its currents move warmth "
    "from the tropics toward the poles. Life began in the sea, and today it shelters creatures from "
    "microscopic plankton to the blue whale, the largest animal that has ever lived. Coral reefs, "
    "kelp forests and deep hydrothermal vents form ecosystems as rich as any rainforest. People have "
    "fished, traded and explored across the waves for thousands of years, yet more than eighty percent "
    "of the ocean remains unmapped and unexplored. Pollution, overfishing and warming waters now threaten "
    "this vast system, but protected areas and cleaner shipping show that recovery is possible when "
    "nations act together. Standing on a beach and watching the tide roll in, it is easy to feel how "
    "small we are, and how much we depend on the restless blue water that connects every continent."
)
VALID_ROLES = {"system", "developer", "user", "assistant", "tool", "function"}

ToolChoice = Union[str, Tuple[str, str]]


@dataclass
class Conv:
    system: str = ""
    turns: List[Tuple[str, str]] = field(default_factory=list)
    tool_results: List[str] = field(default_factory=list)
    tools: List[Dict[str, Any]] = field(default_factory=list)  # {"name", "schema"}
    tool_choice: ToolChoice = "auto"
    response_format: Any = None  # None | "json_object" | ("json_schema", schema)
    stop: List[str] = field(default_factory=list)
    max_tokens: Optional[int] = None

    @property
    def last_user(self) -> str:
        for role, text in reversed(self.turns):
            if role == "user":
                return text
        return ""

    def all_text(self) -> str:
        return " ".join([self.system] + [t for _, t in self.turns] + self.tool_results)


@dataclass
class Reply:
    text: str = ""
    reasoning: str = ""
    calls: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)
    finish: str = "stop"


def tokens(text: str) -> List[str]:
    return re.findall(r"\s*\S+", text or "")


def extract_cities(text: str) -> List[str]:
    low = text.lower()
    found = [(low.find(c.lower()), c) for c in CITIES if c.lower() in low]
    return [c for _, c in sorted(found)]


def args_for(name: str, text: str, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    if name == "get_weather":
        args: Dict[str, Any] = {"city": (extract_cities(text) or ["Paris"])[0]}
        if "fahrenheit" in text.lower():
            args["unit"] = "fahrenheit"
        return args
    if name == "get_time":
        return {"timezone": "Europe/Paris"}
    schema = next((t["schema"] for t in tools if t["name"] == name), {})
    return sample(schema) if schema else {}


def decide(conv: Conv, defects: set) -> Reply:
    user = conv.last_user
    low = user.lower()

    if conv.tool_results:
        results = conv.tool_results[:1] if "drop_extra_tool_results" in defects else conv.tool_results
        parts = []
        for r in results:
            try:
                d = json.loads(r)
                parts.append(f"{d.get('city', 'there')} is {d.get('temp_c')}°C and {d.get('condition')}")
            except (ValueError, AttributeError):
                parts.append(str(r))
        return finish(conv, defects, Reply(text="Here is what I found: " + "; ".join(parts) + "."))

    tc = conv.tool_choice
    if "ignore_tool_choice" in defects:
        tc = "auto"
    names = [t["name"] for t in conv.tools]
    if conv.tools and tc != "none":
        calls: List[Tuple[str, Dict[str, Any]]] = []
        if isinstance(tc, tuple) and tc[1] in names:
            calls = [(tc[1], args_for(tc[1], user, conv.tools))]
        elif "weather" in low and "get_weather" in names:
            unit = {"unit": "fahrenheit"} if "fahrenheit" in low else {}
            calls = [("get_weather", {"city": c, **unit}) for c in (extract_cities(user) or ["Paris"])]
        elif "time" in low and "get_time" in names:
            calls = [("get_time", {"timezone": "Europe/Paris"})]
        elif tc == "required":
            calls = [(names[0], args_for(names[0], user, conv.tools))]
        if calls:
            if "no_parallel" in defects:
                calls = calls[:1]
            return Reply(calls=calls, finish="tool_calls")

    if conv.response_format == "json_object":
        return finish(conv, defects, Reply(text=json.dumps({"name": "Ada Lovelace", "age": 36})))
    if isinstance(conv.response_format, tuple):
        if "ignore_json_schema" in defects:
            return finish(conv, defects, Reply(text="Paris is the capital of France, home to about 2.1 million people and the Eiffel Tower."))
        hints = {"city": "Paris", "country": "France", "population_millions": 2.1, "landmarks": ["Eiffel Tower", "Louvre"]}
        return finish(conv, defects, Reply(text=json.dumps(sample(conv.response_format[1], hints))))

    m = re.search(r"exactly the word (\w+)", conv.system, re.I)
    if m:
        return finish(conv, defects, Reply(text=m.group(1)))
    words = re.findall(r"code word is (\w+)", conv.all_text(), re.I)
    if words and "code word" in low:
        return finish(conv, defects, Reply(text=words[0].rstrip(".")))
    m = re.search(r"count from 1 to (\d+)", low)
    if m:
        n = min(int(m.group(1)), 100)
        return finish(conv, defects, Reply(text=", ".join(str(i) for i in range(1, n + 1))))
    if "17 * 23" in user or "17*23" in user:
        return finish(conv, defects, Reply(text="17 × 23 = 391.", reasoning="17 × 20 = 340 and 17 × 3 = 51, so 340 + 51 = 391."))
    if "ocean" in low:
        return finish(conv, defects, Reply(text=OCEAN))
    if "cat" in low:
        return finish(conv, defects, Reply(text="Cats sleep for up to sixteen hours a day."))
    if "weather" in low:
        return finish(conv, defects, Reply(text="I can't check live weather right now, but Paris is usually mild this time of year."))
    if "hello" in low:
        return finish(conv, defects, Reply(text="Hello there, nice to meet you!"))
    return finish(conv, defects, Reply(text="Hello! I'm the toolsmoke mock model."))


def finish(conv: Conv, defects: set, r: Reply) -> Reply:
    if r.reasoning and "think_in_content" in defects:
        r.text, r.reasoning = f"<think>{r.reasoning}</think>\n{r.text}", ""
    if conv.stop and "ignore_stop" not in defects:
        cut = min((r.text.find(s) for s in conv.stop if s and s in r.text), default=-1)
        if cut >= 0:
            r.text = r.text[:cut]
    if conv.max_tokens:
        toks = tokens(r.text)
        if len(toks) > conv.max_tokens:
            r.text, r.finish = "".join(toks[: conv.max_tokens]), "length"
    return r


# --------------------------------------------------------------------------- parsing

def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") in ("text", "input_text"):
                    out.append(part.get("text", ""))
                elif part.get("type") == "tool_result":
                    out.append(_text_of(part.get("content")))
        return " ".join(out)
    return "" if content is None else str(content)


class BadRequest(Exception):
    pass


def parse_openai(body: Dict[str, Any]) -> Conv:
    msgs = body.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise BadRequest("'messages' must be a non-empty array")
    conv = Conv()
    for m in msgs:
        role = (m or {}).get("role")
        if role not in VALID_ROLES:
            raise BadRequest(f"Invalid role: {role!r}")
    trailing: List[str] = []
    for m in msgs:
        role = m["role"]
        text = _text_of(m.get("content"))
        if role in ("system", "developer"):
            conv.system += text + "\n"
        elif role in ("tool", "function"):
            trailing.append(text)
            continue
        else:
            conv.turns.append((role, text))
        trailing = []
    conv.tool_results = trailing
    for t in body.get("tools") or []:
        fn = (t or {}).get("function") or {}
        if fn.get("name"):
            conv.tools.append({"name": fn["name"], "schema": fn.get("parameters") or {}})
    tc = body.get("tool_choice", "auto")
    if isinstance(tc, dict):
        conv.tool_choice = ("named", ((tc.get("function") or {}).get("name") or tc.get("name") or ""))
    elif tc in ("none", "auto", "required"):
        conv.tool_choice = tc
    rf = body.get("response_format") or {}
    if rf.get("type") == "json_object":
        conv.response_format = "json_object"
    elif rf.get("type") == "json_schema":
        conv.response_format = ("json_schema", (rf.get("json_schema") or {}).get("schema") or {})
    stop = body.get("stop")
    conv.stop = [stop] if isinstance(stop, str) else list(stop or [])
    conv.max_tokens = body.get("max_tokens") or body.get("max_completion_tokens")
    return conv


def parse_anthropic(body: Dict[str, Any]) -> Conv:
    msgs = body.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise BadRequest("messages: field required")
    conv = Conv()
    sysv = body.get("system")
    conv.system = _text_of(sysv) if sysv else ""
    for m in msgs:
        role = (m or {}).get("role")
        if role not in ("user", "assistant"):
            raise BadRequest(f"messages: unexpected role {role!r}")
    last = msgs[-1]
    blocks = last.get("content") if isinstance(last.get("content"), list) else []
    results = [_text_of(b.get("content")) for b in blocks if isinstance(b, dict) and b.get("type") == "tool_result"]
    for m in msgs:
        conv.turns.append((m["role"], _text_of(m.get("content"))))
    conv.tool_results = results
    for t in body.get("tools") or []:
        if isinstance(t, dict) and t.get("name"):
            conv.tools.append({"name": t["name"], "schema": t.get("input_schema") or {}})
    tc = body.get("tool_choice") or {"type": "auto"}
    conv.tool_choice = {"auto": "auto", "any": "required", "none": "none"}.get(tc.get("type"), "auto")
    if tc.get("type") == "tool":
        conv.tool_choice = ("named", tc.get("name", ""))
    conv.stop = list(body.get("stop_sequences") or [])
    conv.max_tokens = body.get("max_tokens")
    return conv


# --------------------------------------------------------------------------- server

class MockServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, defects: set, ttft_ms: float, tps: float, api_key: Optional[str], models: List[str], verbose: bool):
        super().__init__(addr, Handler)
        self.defects = defects
        self.ttft = ttft_ms / 1000.0
        self.tok_delay = 1.0 / tps if tps > 0 else 0.0
        self.api_key = api_key
        self.models = models
        self.verbose = verbose
        self.lock = threading.Lock()
        self.request_count = 0


class Handler(BaseHTTPRequestHandler):
    server: MockServer
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):  # noqa: D401
        if self.server.verbose:
            super().log_message(fmt, *args)

    # -- plumbing
    def _send_json(self, status: int, obj: Any) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, status: int, text: str) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _start_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def _sse(self, data: Any, event: Optional[str] = None) -> None:
        payload = data if isinstance(data, str) else json.dumps(data)
        msg = (f"event: {event}\n" if event else "") + f"data: {payload}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()

    def _path(self) -> str:
        p = self.path.split("?", 1)[0].rstrip("/")
        return p[3:] if p.startswith("/v1") else p

    def _authorized(self) -> bool:
        key = self.server.api_key
        if not key:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {key}" or self.headers.get("x-api-key") == key

    def _body(self) -> Optional[Dict[str, Any]]:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            data = json.loads(raw or b"{}")
            return data if isinstance(data, dict) else None
        except ValueError:
            return None

    # -- routes
    def do_GET(self) -> None:
        path = self._path()
        if path in ("", "/", "/health"):
            return self._send_text(200, "toolsmoke mock server\n")
        if path == "/models":
            if not self._authorized():
                return self._send_json(401, {"error": {"message": "Invalid API key", "type": "authentication_error"}})
            return self._send_json(200, {"object": "list", "data": [{"id": m, "object": "model", "owned_by": "toolsmoke"} for m in self.server.models]})
        return self._send_json(404, {"error": {"message": f"Unknown path {self.path}", "type": "not_found"}})

    def do_POST(self) -> None:
        path = self._path()
        with self.server.lock:
            self.server.request_count += 1
        if path == "/chat/completions":
            return self.chat()
        if path == "/messages":
            return self.messages()
        return self._send_json(404, {"error": {"message": f"Unknown path {self.path}", "type": "not_found"}})

    # -- OpenAI
    def chat(self) -> None:
        d = self.server.defects
        if not self._authorized():
            return self._send_json(401, {"error": {"message": "Invalid API key", "type": "authentication_error", "code": "invalid_api_key"}})
        body = self._body()
        if body is None:
            return self._send_json(400, {"error": {"message": "Request body is not valid JSON", "type": "invalid_request_error"}})
        model = body.get("model")
        if model not in self.server.models and "bad_errors" not in d:
            return self._send_json(404, {"error": {"message": f"The model `{model}` does not exist", "type": "invalid_request_error", "code": "model_not_found"}})
        try:
            conv = parse_openai(body)
        except BadRequest as e:
            if "bad_errors" in d:
                return self._send_text(500, "Internal Server Error")
            return self._send_json(400, {"error": {"message": str(e), "type": "invalid_request_error"}})
        reply = decide(conv, d)
        prompt_toks = len(tokens(conv.all_text()))
        if body.get("stream"):
            return self.chat_stream(body, reply, prompt_toks)
        calls = [self._openai_call(n, a) for n, a in reply.calls]
        msg: Dict[str, Any] = {"role": "assistant", "content": None if calls else reply.text}
        if calls and "leak_tool_calls" in d:
            msg = {"role": "assistant", "content": self._leak_text(reply.calls)}
            reply.finish, calls = "stop", []
        if calls:
            msg["tool_calls"] = calls
        if reply.reasoning:
            msg["reasoning_content"] = reply.reasoning
        out: Dict[str, Any] = {
            "id": "chatcmpl-" + uuid.uuid4().hex[:12],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": reply.finish}],
        }
        if "no_usage" not in d:
            out["usage"] = self._usage(prompt_toks, reply)
        time.sleep(self.server.ttft)
        self._send_json(200, out)

    @staticmethod
    def _openai_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": "call_" + uuid.uuid4().hex[:10], "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}

    @staticmethod
    def _leak_text(calls) -> str:
        return "\n".join(f'<tool_call>\n{{"name": "{n}", "arguments": {json.dumps(a)}}}\n</tool_call>' for n, a in calls)

    @staticmethod
    def _usage(prompt_toks: int, r: Reply) -> Dict[str, int]:
        ct = len(tokens(r.text)) + len(tokens(r.reasoning)) + sum(max(1, len(json.dumps(a)) // 4) for _, a in r.calls)
        return {"prompt_tokens": prompt_toks, "completion_tokens": max(ct, 1), "total_tokens": prompt_toks + max(ct, 1)}

    def chat_stream(self, body: Dict[str, Any], r: Reply, prompt_toks: int) -> None:
        d = self.server.defects
        cid = "chatcmpl-" + uuid.uuid4().hex[:12]
        base = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": body.get("model")}

        def chunk(delta: Dict[str, Any], fr: Optional[str] = None) -> Dict[str, Any]:
            return {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": fr}]}

        self._start_sse()
        time.sleep(self.server.ttft)
        self._sse(chunk({"role": "assistant", "content": ""}))
        for tok in tokens(r.reasoning):
            self._sse(chunk({"reasoning_content": tok}))
            time.sleep(self.server.tok_delay)
        finish_reason = r.finish
        text = r.text
        if r.calls and "stream_tool_leak" in d:
            text, finish_reason = self._leak_text(r.calls), "stop"
        elif r.calls:
            for i, (name, args) in enumerate(r.calls):
                call_id = "call_" + uuid.uuid4().hex[:10]
                self._sse(chunk({"tool_calls": [{"index": i, "id": call_id, "type": "function", "function": {"name": name, "arguments": ""}}]}))
                arg = json.dumps(args)
                step = max(1, len(arg) // 3)
                for j in range(0, len(arg), step):
                    self._sse(chunk({"tool_calls": [{"index": i, "function": {"arguments": arg[j : j + step]}}]}))
                    time.sleep(self.server.tok_delay)
            text = ""
        for tok in tokens(text):
            self._sse(chunk({"content": tok}))
            time.sleep(self.server.tok_delay)
        self._sse(chunk({}, finish_reason))
        if (body.get("stream_options") or {}).get("include_usage") and "no_usage" not in d:
            self._sse({**base, "choices": [], "usage": self._usage(prompt_toks, r)})
        self._sse("[DONE]")

    # -- Anthropic
    def messages(self) -> None:
        d = self.server.defects
        if "no_anthropic" in d:
            return self._send_json(404, {"error": {"message": "Not Found", "type": "not_found"}})
        if not self._authorized():
            return self._send_json(401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
        body = self._body()
        if body is None:
            return self._send_json(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "invalid JSON"}})
        model = body.get("model")
        if model not in self.server.models and "bad_errors" not in d:
            return self._send_json(404, {"type": "error", "error": {"type": "not_found_error", "message": f"model: {model}"}})
        try:
            conv = parse_anthropic(body)
        except BadRequest as e:
            return self._send_json(400, {"type": "error", "error": {"type": "invalid_request_error", "message": str(e)}})
        r = decide(conv, d)
        in_toks = len(tokens(conv.all_text()))
        out_toks = self._usage(0, r)["completion_tokens"]
        stop = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use"}[r.finish]
        blocks: List[Dict[str, Any]] = []
        if r.text:
            blocks.append({"type": "text", "text": r.text})
        for n, a in r.calls:
            blocks.append({"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:10], "name": n, "input": a})
        msg_id = "msg_" + uuid.uuid4().hex[:12]
        if not body.get("stream"):
            time.sleep(self.server.ttft)
            return self._send_json(200, {
                "id": msg_id, "type": "message", "role": "assistant", "model": model, "content": blocks,
                "stop_reason": stop, "stop_sequence": None,
                "usage": {"input_tokens": in_toks, "output_tokens": out_toks},
            })
        self._start_sse()
        time.sleep(self.server.ttft)
        self._sse({"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "model": model,
                   "content": [], "stop_reason": None, "stop_sequence": None,
                   "usage": {"input_tokens": in_toks, "output_tokens": 1}}}, "message_start")
        self._sse({"type": "ping"}, "ping")
        for i, b in enumerate(blocks):
            if b["type"] == "text":
                self._sse({"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}}, "content_block_start")
                for tok in tokens(b["text"]):
                    self._sse({"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": tok}}, "content_block_delta")
                    time.sleep(self.server.tok_delay)
            else:
                self._sse({"type": "content_block_start", "index": i, "content_block": {"type": "tool_use", "id": b["id"], "name": b["name"], "input": {}}}, "content_block_start")
                self._sse({"type": "content_block_delta", "index": i, "delta": {"type": "input_json_delta", "partial_json": json.dumps(b["input"])}}, "content_block_delta")
            self._sse({"type": "content_block_stop", "index": i}, "content_block_stop")
        self._sse({"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": out_toks}}, "message_delta")
        self._sse({"type": "message_stop"}, "message_stop")


def resolve_defects(mode: str, defects: Optional[List[str]] = None) -> set:
    chosen = set(BROKEN_DEFAULT if mode == "broken" else [])
    for name in defects or []:
        name = name.strip()
        if not name:
            continue
        if name.startswith("-"):
            chosen.discard(name[1:])
        elif name in DEFECTS:
            chosen.add(name)
        else:
            raise ValueError(f"unknown defect {name!r}; known: {', '.join(DEFECTS)}")
    return chosen


def serve(host: str = "127.0.0.1", port: int = 8080, mode: str = "good", defects: Optional[List[str]] = None,
          ttft_ms: float = 50, tps: float = 200, api_key: Optional[str] = None,
          models: Optional[List[str]] = None, verbose: bool = False) -> MockServer:
    return MockServer((host, port), resolve_defects(mode, defects), ttft_ms, tps, api_key, models or ["mock-model"], verbose)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="toolsmoke-mock", description="Mock OpenAI/Anthropic-compatible server for testing toolsmoke and agents.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--mode", choices=["good", "broken"], default="good")
    p.add_argument("--defects", default="", help="comma-separated defects to add (prefix with - to remove), see --list-defects")
    p.add_argument("--ttft-ms", type=float, default=50, help="simulated time to first token")
    p.add_argument("--tps", type=float, default=200, help="simulated tokens per second")
    p.add_argument("--api-key", default=None, help="require this API key")
    p.add_argument("--model-name", action="append", default=[], help="model id(s) to serve (default: mock-model)")
    p.add_argument("--list-defects", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    a = p.parse_args(argv)
    if a.list_defects:
        for k, v in DEFECTS.items():
            print(f"{k:<26} {'[broken] ' if k in BROKEN_DEFAULT else ''}{v}")
        return 0
    try:
        srv = serve(a.host, a.port, a.mode, a.defects.split(","), a.ttft_ms, a.tps, a.api_key, a.model_name or None, a.verbose)
    except ValueError as e:
        p.error(str(e))
    print(f"toolsmoke mock ({a.mode}; defects: {', '.join(sorted(srv.defects)) or 'none'}) on http://{a.host}:{srv.server_address[1]}/v1", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
