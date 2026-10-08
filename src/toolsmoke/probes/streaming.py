from __future__ import annotations

from ..core import FAIL, PASS, WARN, Ctx, Outcome, probe


@probe("stream.basic", "streaming", "SSE streaming delivers incremental deltas")
def stream_basic(ctx: Ctx) -> Outcome:
    res, a = ctx.chat_stream([{"role": "user", "content": "Count from 1 to 10, separated by commas."}])
    if not a.content.strip():
        return Outcome(FAIL, f"{len(res.events)} SSE events but no content deltas")
    if a.bad_events:
        return Outcome(FAIL, f"non-JSON SSE data: {a.bad_events[0]!r}")
    problems = []
    if a.content_chunks < 2:
        problems.append("whole reply arrived in one chunk (not really streaming)")
    if not a.done:
        problems.append("no 'data: [DONE]' terminator")
    if not a.finish_reason:
        problems.append("no finish_reason in final chunk")
    ttft = (a.t_first - res.t_start) * 1000 if a.t_first else None
    metrics = {"ttft_ms": round(ttft, 1) if ttft else None, "chunks": a.content_chunks}
    if problems:
        return Outcome(WARN, "; ".join(problems), metrics)
    return Outcome(PASS, f"{a.content_chunks} content chunks, [DONE] received, finish_reason={a.finish_reason}", metrics)


@probe("stream.usage", "streaming", "stream_options.include_usage reports usage")
def stream_usage(ctx: Ctx) -> Outcome:
    _, a = ctx.chat_stream(
        [{"role": "user", "content": "Say hello in five words or fewer."}],
        stream_options={"include_usage": True},
    )
    if a.usage and a.usage.get("completion_tokens"):
        return Outcome(PASS, f"usage chunk: {a.usage.get('prompt_tokens', '?')} prompt / {a.usage['completion_tokens']} completion tokens")
    return Outcome(WARN, "no usage in stream (cost/token tracking in agents will be blind)")
