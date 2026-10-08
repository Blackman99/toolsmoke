# Goal

Tell you in one command whether your LLM endpoint actually works for agents (tool calling, streaming, structured output) and how fast it is.

## Guardrails

Every change must serve that sentence. In practice:

- **One command, one verdict.** `toolsmoke --base-url … --model …` must keep producing a clear pass/warn/fail answer and an exit code. No mandatory config files, accounts, or services.
- **Agent features first.** Probes check behaviour agent frameworks depend on (tool calls, `tool_choice`, streaming deltas, structured output, multi-turn tool results, reasoning separation, error semantics) plus latency and throughput. Model *quality* benchmarks (accuracy, leaderboards, evals) are out of scope.
- **Zero runtime dependencies.** Installing must stay trivial (`uvx`/`pipx`, stdlib only).
- **Deterministic and honest.** A probe fails only for behaviour that breaks real agent loops, and its detail line says what went wrong.
