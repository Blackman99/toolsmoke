---
title: Tool calling breaks silently. Here is how to catch it.
description: Tool calling quietly breaks across llama.cpp, Ollama, vLLM and API relays. Why it happens, what agents actually need from an endpoint, and a one-command check, with a real llama.cpp run.
---

# Your server says "OpenAI-compatible". Your agent disagrees.

*October 2026 · [中文版](tool-calling-breaks-silently-zh.md)*

You point an agent at a local endpoint. A plain chat request works, so you move on. Then the agent stops calling tools. Or it loops on the same step. Or every few requests it gets a 500. Nothing in the logs says "tool calling is broken", so the model gets the blame.

Usually the model is fine. The problem is the layer between the model and the HTTP API: the chat template, the tool-call parser, the reasoning parser, the code that assembles streamed deltas, and, if you use one, the relay or gateway in front of it all.

## Three issues, one pattern

These three issue threads have more than 200 comments between them:

- **[ollama#11621](https://github.com/ollama/ollama/issues/11621)**: Qwen3-Coder supports tool calling, but the chat template Ollama shipped for it had no tool support. Clients sent `tools` and got prose back. It was fixed in Ollama v0.12.0, which added a renderer and parser written just for qwen3-coder.
- **[llama.cpp#15012](https://github.com/ggml-org/llama.cpp/issues/15012)**: Qwen3-Coder writes tool calls in its own XML format (`<function=...><parameter=...>`), not JSON inside `<tool_call>`. If the server has no parser for that format, the call lands in `content` as text, and the client sees a chat reply instead of `tool_calls`.
- **[vllm#22403](https://github.com/vllm-project/vllm/issues/22403)**: gpt-oss-120b behind chat completions randomly returned 200, 400 (`Expected 2 output messages (reasoning and final), but got 7`) or 500. People running agent frameworks with tools hit errors, and some streams broke partway through. The problem was in how the server handled the model's response format for reasoning, tools and streaming.

In all three, the weights are fine and plain chat works. What breaks is the contract agents rely on, and it breaks in the serving layer. Relays and gateways add another translation step (OpenAI to Anthropic and back, renamed fields, buffered streams) where the same fields can be dropped or reshaped.

The failure also shows up far from the cause. The framework retries a call that will never succeed. It takes `<tool_call>{...}` text as the final answer. It throws a JSON error on half-assembled streamed arguments. By the time you see the stack trace, the endpoint is the last thing you suspect.

## What "works for agents" actually means

An endpoint that answers chat isn't necessarily agent-ready. Agents depend on a list of specific behaviors:

| The agent needs | toolsmoke probe |
|---|---|
| Tool calls returned in `tool_calls`, with `finish_reason: tool_calls`, and no markup left in `content` | `tools.single`, `tools.clean_content` |
| Arguments that are valid JSON and match the schema | `tools.args_schema` |
| Parallel calls, each with its own id | `tools.parallel` |
| `tool_choice` `none`, `required` and named actually enforced | `tools.choice_none`, `tools.choice_required`, `tools.choice_named` |
| Tool results that reach the model on the next turn | `tools.result_roundtrip`, `tools.multi_result` |
| Streamed tool-call deltas that assemble into the same call | `stream.tools`, `stream.tools_parallel` |
| `response_format` (`json_object`, strict `json_schema`) respected | `json.mode`, `json.schema` |
| Reasoning returned in `reasoning_content`, not as `<think>` inside the answer | `reasoning.field` |
| Bad requests rejected with a clean 4xx, not a 500 or a silent 200 | `errors.*` |
| Optionally, the Anthropic Messages API (`/v1/messages`) | `anthropic.*` |

Full details are in the [probe reference](../probes.md).

## One command to check it

[toolsmoke](https://github.com/Blackman99/toolsmoke) sends 31 small probes to your endpoint, using trivial prompts at `temperature: 0` and checking the results deterministically. It prints PASS, WARN or FAIL for each probe, plus time-to-first-token, tokens per second and an exit code you can use in CI. It needs Python 3.9+ and has no dependencies.

```bash
uvx --from git+https://github.com/Blackman99/toolsmoke toolsmoke \
    --base-url http://localhost:8080/v1 --model qwen --anthropic
```

To see what it reports without running a model, use `toolsmoke --demo broken`. It starts a built-in mock server with the common failure modes switched on:

![toolsmoke --demo broken, then --demo good](https://blackman99.github.io/toolsmoke/demo.gif)

## A real run: llama.cpp with a small Qwen

Setup: `llama-server --jinja` (build b11490) serving Qwen2.5-0.5B-Instruct on 8 CPU cores. Excerpt:

```console
$ toolsmoke --base-url http://localhost:8080/v1 --model qwen --anthropic
  ...
  tools.single            PASS     499ms  get_weather({"city": "Paris", "unit": "celsius"}) finish_reason=tool_calls
  tools.parallel          PASS      1.0s  2 calls with distinct ids: Paris, Tokyo
  tools.choice_none       FAIL     491ms  tool call leaked into content as text: '<tool_call> {{"name": "get_weather"…
  tools.choice_required   FAIL     20.4s  no tool call although tool_choice=required (reply: 'Hello! How can I assist…
  tools.choice_named      FAIL     473ms  called 'get_weather'; named tool_choice get_time was ignored
  tools.result_roundtrip  PASS     429ms  final answer uses the tool result
  stream.tools            PASS     485ms  get_weather({"city": "Paris", "unit": "celsius"}) assembled from deltas
  json.schema             PASS      1.4s  output validates against the strict schema
  errors.bad_model        WARN     127ms  unknown model accepted with 200 (server ignores the model name)
  errors.bad_request      WARN     114ms  invalid message role accepted with 200
  anthropic.tools         PASS     519ms  tool_use get_weather {'city': 'Paris'}, stop_reason=tool_use
  perf.ttft               PASS     917ms  p50 22 ms (min 19, max 50, n=3)
  perf.throughput         PASS      4.2s  62.4 tok/s (256 tokens via usage, 4.2s total)

  TTFT p50 22 ms · 62.4 tok/s · 24 pass · 2 warn · 3 fail · 2 skip
  NOT AGENT-READY: 3 failing probes
```

(The full 31-row output is in the [README](https://github.com/Blackman99/toolsmoke#usage).)

Most of it passes: structured tool calls, schema-valid arguments, parallel calls, streamed deltas, tool-result round trips, strict JSON schema, even the Anthropic Messages endpoint. All three failures are about `tool_choice`:

- **`none`**: we asked for a plain answer, but a tool call still came back, and it came back as raw `<tool_call>` markup in `content`. An agent that disabled tools for a summarization step gets markup in its summary.
- **`required`**: no tool call at all. The model spent 20.4 seconds writing a greeting.
- **named**: we asked for `get_time` and got `get_weather`.

A 0.5B model can miss tools on its own, and the [FAQ](../faq.md) says so. But enforcing `tool_choice` is the server's job, and leaked markup or an ignored named choice points to the serving stack, whatever the model size. In practice, if your agent uses `tool_choice` to force a step (routers and structured extraction often do), this setup will quietly skip it. Plain `auto` tool calling works fine, which is exactly why nobody notices.

The two warnings are milder. llama.cpp serves whatever model is loaded, whatever name you send, and it accepts an invalid message role with a 200. On CPU, speed was a 22 ms median time to first token and 62.4 tokens/s.

## Run it in CI

The real cost of these bugs comes from upgrades: a new llama.cpp build, a different chat template, a vLLM parser flag, a gateway config change. Run the check whenever one of those changes:

```yaml
- uses: Blackman99/toolsmoke@v0.1.1
  with:
    base-url: https://llm.example.com/v1
    model: qwen3-coder
    api-key: ${{ secrets.LLM_API_KEY }}
    max-ttft: "1500"
```

The step fails if any probe fails, and it writes a Markdown table to the job summary. See [CI & GitHub Action](../github-action.md), or get it from the [Marketplace](https://github.com/marketplace/actions/toolsmoke).

## What it doesn't do

toolsmoke doesn't benchmark model quality. It checks the API contract agents depend on. The prompts are trivial on purpose, so a failure almost always means the serving stack is broken, not that the model is weak. The detail line on each probe tells you which.

If a probe looks wrong for your server, please [open an issue](https://github.com/Blackman99/toolsmoke/issues/new/choose) and attach the `--format json` output.
