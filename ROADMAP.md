# Roadmap

Everything here serves [GOAL.md](GOAL.md): one command that tells you whether an endpoint works for agents, and how fast it is. Items move only when they make that answer more accurate or easier to get.

## v0.1 — MVP ✅

- 31 probes: chat basics, streaming, single/parallel/streamed tool calls, `tool_choice` none/required/named, tool-markup leaks, multi-turn tool results, JSON mode, JSON schema, reasoning field, error semantics, Anthropic Messages API, TTFT and tokens/sec
- Pass/warn/fail table, JSON and Markdown output, CI-friendly exit codes
- `--strict`, `--max-ttft`, `--min-tps` gates
- Built-in mock server with good and deliberately broken modes (`--demo`)
- Reusable GitHub Action with job summary
- Zero runtime dependencies, Python ≥ 3.9

## v0.2 — More providers, more probes

- Provider presets (`--preset ollama|vllm|llamacpp|lmstudio|sglang|openrouter|litellm`) with known-quirk hints in failure details
- OpenAI **Responses API** probes (`/v1/responses`: function calls, streaming events)
- Native Ollama API (`/api/chat`) tool-calling probes
- Probes: tool calls with nested/array arguments, enum adherence, long tool results, tool call after a long context, `parallel_tool_calls=false`, `n>1`, `logprobs`, image input (opt-in)
- Repeat mode (`--repeat N`) to measure flakiness: pass rate per probe instead of one-shot result
- Config file (`toolsmoke.toml`) for many endpoints

## v0.3 — HTML report and compare mode

- `--html report.html`: self-contained shareable report
- `toolsmoke compare a.json b.json …`: side-by-side matrix of endpoints/models/versions, regressions highlighted
- Concurrency/load probe: TTFT and throughput at 1/4/16 parallel requests
- Prompt-cache detection (second-request TTFT drop)

## v0.4 — Ecosystem

- Publish to PyPI and a container image
- Agent-framework smoke packs (LangChain, OpenAI Agents SDK, MCP-style tool loops) run against the endpoint
- Community "compatibility matrix" page generated from submitted JSON reports

## v1.0 — Stable

- Stable probe ids and JSON report schema (semver-guaranteed)
- Documented probe-authoring API for plugins
