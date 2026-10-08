# Changelog

## v0.1.0 — 2026-10-08

First release.

- 31 probes across chat, streaming, tool calling, `tool_choice`, structured output, reasoning, error handling, the Anthropic Messages API and performance (TTFT p50, tokens/sec)
- Table, JSON and Markdown reports; exit codes 0/1/2; `--strict`, `--max-ttft`, `--min-tps`
- `toolsmoke-mock`: OpenAI/Anthropic-compatible mock server with 11 injectable defects; `toolsmoke --demo good|broken`
- Composite GitHub Action (`uses: Blackman99/toolsmoke@v0.1.0`)
