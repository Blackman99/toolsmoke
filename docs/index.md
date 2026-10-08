# toolsmoke

**Tell you in one command whether your LLM endpoint actually works for agents (tool calling, streaming, structured output) and how fast it is.**

"OpenAI-compatible" servers (vLLM, llama.cpp, Ollama, LM Studio, SGLang, LiteLLM, hosted gateways…) all answer a plain chat request. Agents need much more: structured `tool_calls` instead of `<tool_call>` text in `content`, `tool_choice` that is actually enforced, streamed tool-call deltas that assemble into valid JSON, `response_format` schemas, reasoning kept out of the answer, and tool results that survive the chat template. When any of these is broken, agent frameworks fail in confusing ways far from the cause.

toolsmoke runs 31 small, deterministic probes and gives you a verdict (excerpt of the [README sample run](https://github.com/Blackman99/toolsmoke#usage)):

```console
$ toolsmoke --base-url http://localhost:8080/v1 --model qwen --anthropic
  ...
  tools.choice_required   FAIL     20.4s  no tool call although tool_choice=required (reply: 'Hello! How can I assist…
  stream.tools            PASS     485ms  get_weather({"city": "Paris", "unit": "celsius"}) assembled from deltas
  perf.ttft               PASS     917ms  p50 22 ms (min 19, max 50, n=3)
  perf.throughput         PASS      4.2s  62.4 tok/s (256 tokens via usage, 4.2s total)

  TTFT p50 22 ms · 62.4 tok/s · 24 pass · 2 warn · 3 fail · 2 skip
  NOT AGENT-READY: 3 failing probes
```

<div class="grid cards" markdown>

- **[Install](install.md)**: `uvx`, `pipx` or the release wheel. No dependencies.
- **[Usage](usage.md)**: run, filter, output formats, exit codes.
- **[Probe reference](probes.md)**: what each of the 31 probes checks and why it matters.
- **[Configuration](configuration.md)**: every flag and environment variable.
- **[CI & GitHub Action](github-action.md)**: gate deployments on agent-readiness.
- **[FAQ](faq.md)**: false positives, reasoning models, OpenAI quirks.

</div>

## What it is not

toolsmoke checks **protocol behaviour and speed**, not model intelligence. It deliberately asks trivial questions ("what's the weather in Paris?") so that a failure means the server, template or parser is broken, not that the model is dumb. For accuracy benchmarks use something like the Berkeley Function-Calling Leaderboard.
