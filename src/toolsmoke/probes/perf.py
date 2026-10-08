from __future__ import annotations

import statistics

from ..core import FAIL, PASS, WARN, Ctx, Outcome, ProbeFail, probe


@probe("perf.ttft", "performance", "Time to first token (median of runs)")
def perf_ttft(ctx: Ctx) -> Outcome:
    samples = []
    for _ in range(max(1, ctx.cfg.perf_runs)):
        res, a = ctx.chat_stream([{"role": "user", "content": "Reply with one short sentence about cats."}], max_tokens=32)
        if a.t_first is None:
            raise ProbeFail("stream produced no tokens")
        samples.append((a.t_first - res.t_start) * 1000)
    med = statistics.median(samples)
    metrics = {"ttft_ms_p50": round(med, 1), "ttft_ms_min": round(min(samples), 1), "ttft_ms_max": round(max(samples), 1), "runs": len(samples)}
    detail = f"p50 {med:.0f} ms (min {min(samples):.0f}, max {max(samples):.0f}, n={len(samples)})"
    if ctx.cfg.max_ttft_ms is not None and med > ctx.cfg.max_ttft_ms:
        return Outcome(FAIL, detail + f" > --max-ttft {ctx.cfg.max_ttft_ms:.0f} ms", metrics)
    if med > ctx.cfg.warn_ttft_ms:
        return Outcome(WARN, detail + " (slow for interactive agents)", metrics)
    return Outcome(PASS, detail, metrics)


@probe("perf.throughput", "performance", "Decode speed in tokens/sec")
def perf_throughput(ctx: Ctx) -> Outcome:
    res, a = ctx.chat_stream(
        [{"role": "user", "content": "Write about 150 words about the ocean."}],
        max_tokens=256,
        stream_options={"include_usage": True},
    )
    if a.t_first is None or a.t_last is None:
        raise ProbeFail("stream produced no tokens")
    if a.usage and a.usage.get("completion_tokens"):
        tokens, source = int(a.usage["completion_tokens"]), "usage"
    else:
        tokens, source = a.content_chunks, "chunk count"
    span = max(a.t_last - a.t_first, 1e-6)
    tps = (tokens - 1) / span if tokens > 1 else 0.0
    total = res.t_end - res.t_start
    metrics = {"tokens_per_sec": round(tps, 1), "completion_tokens": tokens, "token_source": source, "total_s": round(total, 2)}
    detail = f"{tps:.1f} tok/s ({tokens} tokens via {source}, {total:.1f}s total)"
    if ctx.cfg.min_tps is not None and tps < ctx.cfg.min_tps:
        return Outcome(FAIL, detail + f" < --min-tps {ctx.cfg.min_tps:g}", metrics)
    if tps < ctx.cfg.warn_tps:
        return Outcome(WARN, detail + " (slow)", metrics)
    if source != "usage":
        return Outcome(PASS, detail + "; estimate, no usage in stream", metrics)
    return Outcome(PASS, detail, metrics)
