# FAQ

### A probe fails but my agent seems to work. False positive?

Maybe your framework works around it (many parse `<tool_call>` text themselves, or never use `tool_choice`). toolsmoke reports what the **endpoint** does, against the OpenAI/Anthropic API contract. If you believe the probe is wrong, please [open an issue](https://github.com/Blackman99/toolsmoke/issues/new/choose) with `--format json` output.

### Small models fail tool probes. Is that the server's fault?

Prompts are trivial on purpose, but tiny models (≤1B) can still fail `tools.*` on their own. The tell-tale sign of a *server* problem is the detail line: markup such as `<tool_call>` in `content`, ignored `tool_choice`, or a 5xx is a template/parser/server issue regardless of model size. A model that just answers in prose is more likely the model.

### llama.cpp: tools don't work at all

Start `llama-server` with `--jinja` so the model's chat template (and tool-call parser) is used. Some templates need `--chat-template-file`. Note that `tool_choice` `required`/named enforcement depends on the template handler; toolsmoke will tell you.

### vLLM: tool calls come back as text

vLLM needs `--enable-auto-tool-choice --tool-call-parser <parser>` (e.g. `hermes`, `llama3_json`, `mistral`, `qwen3_coder`). Reasoning models also need `--reasoning-parser` or `<think>` ends up in `content` (`reasoning.field` FAIL).

### Ollama: streamed tool calls / `tool_choice`

Behaviour differs between versions and models; run `toolsmoke --base-url http://localhost:11434/v1 --model <model>` after each upgrade. That's exactly what it's for.

### OpenAI reasoning models reject my request

Use `--token-param max_completion_tokens --temperature none`.

### `errors.bad_model` warns on my local server

Single-model servers (llama.cpp, LM Studio) serve whatever is loaded regardless of `model`. That's a WARN, not a FAIL, because agents still work; behind a router it can mean requests silently hit the wrong model.

### Why is `reasoning.field` skipped?

The model returned no reasoning, which is normal for non-reasoning models. Use `--require-reasoning` when you expect a thinking model.

### Does it send my data anywhere?

No. toolsmoke only talks to the endpoint you give it. No telemetry.

### How long does a run take, and how many tokens?

About 30–40 requests, mostly with tiny outputs; under a minute on a typical GPU server, a few thousand tokens total. Use `--only`/`--skip` to narrow it.

### How is this different from other tools?

- Model benchmarks (BFCL, etc.) measure *how well a model* calls functions; toolsmoke checks whether *the serving stack* delivers tool calls, streaming and structured output correctly, and how fast.
- Load testers (e.g. `llmperf`, `genai-perf`) measure throughput at scale; toolsmoke gives one-command latency/throughput numbers next to the functional verdict.
- Other endpoint probers exist (e.g. `llmprobe`); toolsmoke focuses on agent features with pass/warn/fail semantics, an Anthropic Messages API mode, a bundled broken mock server, and a CI action.

### Can I add my own probe?

Yes, see [CONTRIBUTING.md](https://github.com/Blackman99/toolsmoke/blob/main/CONTRIBUTING.md).
