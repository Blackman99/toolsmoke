# Changelog

## Unreleased

- `--preset ollama|vllm|llamacpp|lmstudio|sglang|openrouter|litellm`: fills a default `--base-url` when omitted and appends short known-quirk hints on FAIL/WARN
- New probes: `tools.nested_args` (nested object + array tool arguments via `search_flights`) and `tools.no_parallel` (`parallel_tool_calls=false`; HTTP 400/422 → WARN)
- Mock server: `bad_nested_args` defect; honour `parallel_tool_calls=false` in good mode
- `--responses`: five opt-in OpenAI Responses API probes (`POST /v1/responses`, used by the OpenAI Agents SDK and Codex): `responses.basic`, `responses.stream`, `responses.tools`, `responses.stream_tools`, `responses.tool_result`
- `--repeat N`: runs every probe N times to catch flaky endpoints; the worst run counts, the detail starts with the pass rate (`flaky: 4/5 pass, 1 fail · …`) and JSON gets `metrics.repeat`
- GitHub Action inputs `responses` and `repeat`; JSON report fields `responses` and `repeat`
- Mock server: `POST /v1/responses` (JSON and streaming), defects `no_responses` and `flaky_tools`; `--demo` now probes the Responses API too
- Probe count: 31 → 38

## v0.1.1 — 2026-10-08

- Shorten the GitHub Action description to meet the Marketplace limit so the Action can be published to the GitHub Marketplace.

## v0.1.0 — 2026-10-08

First release.

- 31 probes across chat, streaming, tool calling, `tool_choice`, structured output, reasoning, error handling, the Anthropic Messages API and performance (TTFT p50, tokens/sec)
- Table, JSON and Markdown reports; exit codes 0/1/2; `--strict`, `--max-ttft`, `--min-tps`
- `toolsmoke-mock`: OpenAI/Anthropic-compatible mock server with 11 injectable defects; `toolsmoke --demo good|broken`
- Composite GitHub Action (`uses: Blackman99/toolsmoke@v0.1.0`)
