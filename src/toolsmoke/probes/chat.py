from __future__ import annotations

import re

from ..core import FAIL, PASS, WARN, Ctx, Outcome, ProbeFail, content_of, finish_reason, message, probe


@probe("models.list", "basics", "GET /models lists the model")
def models_list(ctx: Ctx) -> Outcome:
    res = ctx.client.get("models")
    if res.status == 404:
        return Outcome(WARN, "GET /models returns 404 (some clients use it for discovery)")
    if not res.ok:
        return Outcome(WARN, f"GET /models → HTTP {res.status}: {res.snippet(100)}")
    data = res.try_json()
    ids = [m.get("id") for m in (data or {}).get("data", []) if isinstance(m, dict)] if isinstance(data, dict) else []
    if not ids:
        return Outcome(WARN, "GET /models returned no models in data[]")
    if ctx.cfg.model in ids:
        return Outcome(PASS, f"{len(ids)} model(s) listed, '{ctx.cfg.model}' present")
    shown = ", ".join(str(i) for i in ids[:3])
    return Outcome(WARN, f"'{ctx.cfg.model}' not in /models ({shown}{'…' if len(ids) > 3 else ''})")


@probe("chat.basic", "basics", "Non-streaming chat completion")
def chat_basic(ctx: Ctx) -> Outcome:
    res, data = ctx.chat([{"role": "user", "content": "Say hello in five words or fewer."}], max_tokens=ctx.cfg.max_tokens)
    text = content_of(message(data)).strip()
    if not text:
        return Outcome(FAIL, "empty content")
    fr = finish_reason(data)
    usage = data.get("usage") or {}
    notes = []
    status = PASS
    if fr not in ("stop", "length", "end_turn", "eos"):
        status, notes = WARN, notes + [f"finish_reason={fr!r}"]
    if not usage.get("completion_tokens"):
        status, notes = WARN, notes + ["no usage.completion_tokens"]
    detail = f"finish_reason={fr}, {usage.get('completion_tokens', '?')} completion tokens"
    if notes:
        detail = "; ".join(notes) + f" (reply: {text[:40]!r})"
    return Outcome(status, detail)


@probe("chat.system", "basics", "System prompt is followed")
def chat_system(ctx: Ctx) -> Outcome:
    _, data = ctx.chat(
        [
            {"role": "system", "content": "Reply with exactly the word PINEAPPLE and nothing else."},
            {"role": "user", "content": "What is your favourite fruit?"},
        ]
    )
    text = content_of(message(data))
    if "PINEAPPLE" in text.upper():
        return Outcome(PASS, "system instruction obeyed")
    return Outcome(FAIL, f"system prompt ignored (reply: {text.strip()[:50]!r})")


@probe("chat.multi_turn", "basics", "Earlier turns are remembered")
def chat_multi_turn(ctx: Ctx) -> Outcome:
    _, data = ctx.chat(
        [
            {"role": "user", "content": "Remember this: my code word is OSPREY."},
            {"role": "assistant", "content": "Got it, your code word is OSPREY."},
            {"role": "user", "content": "Thanks. Now tell me: what is my code word? Answer with just the word."},
        ]
    )
    text = content_of(message(data))
    if "OSPREY" in text.upper():
        return Outcome(PASS, "history passed through correctly")
    return Outcome(FAIL, f"lost conversation history (reply: {text.strip()[:50]!r})")


@probe("chat.stop", "basics", "Stop sequences are honoured")
def chat_stop(ctx: Ctx) -> Outcome:
    _, data = ctx.chat(
        [{"role": "user", "content": "Count from 1 to 20, separated by commas and spaces. Output only the numbers."}],
        stop=["7"],
    )
    text = content_of(message(data))
    if not re.search(r"\b1\b", text) and "1" not in text:
        raise ProbeFail(f"model did not count (reply: {text[:50]!r})")
    if re.search(r"\b(7|8|9|1[0-9]|20)\b", text):
        return Outcome(FAIL, f"generation continued past stop sequence '7' (reply: {text.strip()[:40]!r})")
    return Outcome(PASS, f"stopped before '7' (finish_reason={finish_reason(data)})")


@probe("chat.max_tokens", "basics", "max_tokens limit is enforced")
def chat_max_tokens(ctx: Ctx) -> Outcome:
    _, data = ctx.chat(
        [{"role": "user", "content": "Write a long essay about the history of the ocean."}],
        max_tokens=16,
    )
    fr = finish_reason(data)
    usage = data.get("usage") or {}
    ct = usage.get("completion_tokens")
    if ct is not None and ct > 20:
        return Outcome(FAIL, f"asked for 16 tokens, got {ct}")
    if fr != "length":
        return Outcome(WARN, f"finish_reason={fr!r}, expected 'length' when truncated")
    return Outcome(PASS, f"truncated at {ct if ct is not None else '?'} tokens, finish_reason=length")
