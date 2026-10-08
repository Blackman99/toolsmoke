"""Tiny stdlib HTTP client with Server-Sent Events support.

toolsmoke deliberately has zero runtime dependencies so `uvx toolsmoke` /
`pipx run` start instantly and nothing can conflict with your environment.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

USER_AGENT = "toolsmoke"


class TransportError(Exception):
    """The request never produced an HTTP response (DNS, refused, TLS, timeout)."""


@dataclass
class HTTPResult:
    status: int
    body: bytes
    elapsed: float
    headers: Dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text())

    def try_json(self) -> Any:
        try:
            return self.json()
        except (ValueError, UnicodeDecodeError):
            return None

    def snippet(self, n: int = 160) -> str:
        t = " ".join(self.text().split())
        return t if len(t) <= n else t[: n - 1] + "…"


@dataclass
class SSEEvent:
    t: float  # perf_counter timestamp when the event was dispatched
    event: Optional[str]
    data: str


@dataclass
class StreamResult:
    status: int
    t_start: float
    t_headers: float
    t_end: float
    events: List[SSEEvent] = field(default_factory=list)
    body: bytes = b""  # only filled for non-2xx responses or non-SSE replies
    content_type: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def snippet(self, n: int = 160) -> str:
        t = " ".join(self.body.decode("utf-8", errors="replace").split())
        return t if len(t) <= n else t[: n - 1] + "…"


def iter_sse(lines: Iterable[bytes], clock=time.perf_counter) -> Iterator[SSEEvent]:
    """Parse an SSE byte-line stream (per the WHATWG spec, minus retry/id)."""
    event: Optional[str] = None
    data: List[str] = []
    for raw in lines:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line == "":
            if data:
                yield SSEEvent(clock(), event, "\n".join(data))
            event, data = None, []
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if name == "event":
            event = value
        elif name == "data":
            data.append(value)
    if data:
        yield SSEEvent(clock(), event, "\n".join(data))


class Client:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        headers: Optional[Dict[str, str]] = None,
        style: str = "openai",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = dict(headers or {})
        self.style = style

    def url(self, path: str) -> str:
        return self.base_url + "/" + path.lstrip("/")

    def _headers(self, api_key: Optional[str]) -> Dict[str, str]:
        h = {"User-Agent": USER_AGENT, "Content-Type": "application/json", "Accept": "*/*"}
        key = self.api_key if api_key is None else api_key
        if self.style == "anthropic":
            h["anthropic-version"] = "2023-06-01"
            if key:
                h["x-api-key"] = key
                h["Authorization"] = "Bearer " + key
        elif key:
            h["Authorization"] = "Bearer " + key
        h.update(self.extra_headers)
        return h

    def _open(self, method: str, path: str, payload: Any, api_key: Optional[str]):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url(path), data=data, method=method, headers=self._headers(api_key))
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:  # non-2xx still has a response
            return e
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise TransportError(f"{type(reason).__name__}: {reason}") from None

    def request(self, method: str, path: str, payload: Any = None, api_key: Optional[str] = None) -> HTTPResult:
        t0 = time.perf_counter()
        resp = self._open(method, path, payload, api_key)
        try:
            body = resp.read()
        except (socket.timeout, OSError) as e:
            raise TransportError(f"read failed: {e}") from None
        finally:
            resp.close()
        status = getattr(resp, "status", None) or resp.getcode()
        return HTTPResult(status, body, time.perf_counter() - t0, dict(resp.headers.items()))

    def post(self, path: str, payload: Any, api_key: Optional[str] = None) -> HTTPResult:
        return self.request("POST", path, payload, api_key)

    def get(self, path: str) -> HTTPResult:
        return self.request("GET", path)

    def stream(self, path: str, payload: Any) -> StreamResult:
        t0 = time.perf_counter()
        resp = self._open("POST", path, payload, None)
        t_headers = time.perf_counter()
        status = getattr(resp, "status", None) or resp.getcode()
        ctype = resp.headers.get("Content-Type", "") if resp.headers else ""
        result = StreamResult(status, t0, t_headers, t_headers, content_type=ctype)
        try:
            if not (200 <= status < 300) or "text/event-stream" not in ctype:
                result.body = resp.read()
            else:
                result.events = list(iter_sse(_readlines(resp)))
        except (socket.timeout, OSError) as e:
            raise TransportError(f"stream read failed: {e}") from None
        finally:
            resp.close()
        result.t_end = time.perf_counter()
        return result


def _readlines(resp) -> Iterator[bytes]:
    while True:
        line = resp.readline()
        if not line:
            return
        yield line


def parse_json_events(events: List[SSEEvent]) -> Tuple[List[Tuple[float, Optional[str], Any]], bool, List[str]]:
    """Decode SSE data payloads as JSON. Returns (items, saw_done, errors)."""
    items: List[Tuple[float, Optional[str], Any]] = []
    errors: List[str] = []
    done = False
    for ev in events:
        if ev.data.strip() == "[DONE]":
            done = True
            continue
        try:
            items.append((ev.t, ev.event, json.loads(ev.data)))
        except ValueError:
            errors.append(ev.data[:80])
    return items, done, errors
