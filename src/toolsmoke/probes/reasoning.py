from __future__ import annotations

from ..core import FAIL, PASS, SKIP, Ctx, Outcome, content_of, find_think, message, probe, reasoning_of


@probe("reasoning.field", "reasoning", "Reasoning arrives in its own field, not in content")
def reasoning_field(ctx: Ctx) -> Outcome:
    _, data = ctx.chat([{"role": "user", "content": "What is 17 * 23? Think it through step by step, then give the answer."}])
    msg = message(data)
    text = content_of(msg)
    tag = find_think(text)
    if tag:
        return Outcome(FAIL, f"reasoning leaked into content ({tag!r}); enable the server's reasoning parser")
    key, value = reasoning_of(msg)
    if key:
        return Outcome(PASS, f"reasoning in '{key}' ({len(value)} chars), content clean")
    if ctx.cfg.require_reasoning:
        return Outcome(FAIL, "no reasoning field returned (--require-reasoning)")
    return Outcome(SKIP, "no reasoning returned (normal for non-reasoning models)")
