# toolsmoke

**Tell you in one command whether your LLM endpoint actually works for agents (tool calling, streaming, structured output) and how fast it is.**

Every "OpenAI-compatible" server answers a plain chat request. Agents need more: structured `tool_calls` instead of `<tool_call>` text in `content`, `tool_choice` that is enforced, streamed tool-call deltas that assemble into valid JSON, JSON-schema output, reasoning kept out of the answer, tool results that survive the chat template. When one of these is broken (see [ollama#11621](https://github.com/ollama/ollama/issues/11621), [vllm#22403](https://github.com/vllm-project/vllm/issues/22403), [llama.cpp#15012](https://github.com/ggml-org/llama.cpp/issues/15012)), your agent fails somewhere far from the cause. toolsmoke runs 31 small probes against your endpoint (OpenAI chat completions, optionally Anthropic Messages) and gives you a pass/warn/fail verdict, time-to-first-token, tokens/sec and an exit code.

## Install

```bash
uvx --from git+https://github.com/Blackman99/toolsmoke toolsmoke --help     # run without installing
pipx install git+https://github.com/Blackman99/toolsmoke                   # or install the command
```

Zero dependencies, Python 3.9+. Wheels are on the [releases page](https://github.com/Blackman99/toolsmoke/releases). Try it without a model: `toolsmoke --demo broken`.

## Usage

Real output against llama.cpp (`llama-server --jinja`, b11490) serving Qwen2.5-0.5B-Instruct on 8 CPU cores:

```console
$ toolsmoke --base-url http://localhost:8080/v1 --model qwen --anthropic
  PROBE                   RESULT    TIME  DETAIL
  models.list             PASS       1ms  1 model(s) listed, 'qwen' present
  chat.basic              PASS      81ms  finish_reason=stop, 3 completion tokens
  chat.system             PASS      61ms  system instruction obeyed
  chat.multi_turn         PASS      59ms  history passed through correctly
  chat.stop               PASS     216ms  stopped before '7' (finish_reason=stop)
  chat.max_tokens         PASS     279ms  truncated at 16 tokens, finish_reason=length
  stream.basic            PASS     431ms  29 content chunks, [DONE] received, finish_reason=stop
  stream.usage            PASS      56ms  usage chunk: 37 prompt / 3 completion tokens
  tools.single            PASS     499ms  get_weather({"city": "Paris", "unit": "celsius"}) finish_reason=tool_calls
  tools.args_schema       PASS     552ms  valid against schema: {"city": "Tokyo", "unit": "fahrenheit"}
  tools.parallel          PASS      1.0s  2 calls with distinct ids: Paris, Tokyo
  tools.choice_none       FAIL     491ms  tool call leaked into content as text: '<tool_call> {{"name": "get_weather"…
  tools.choice_required   FAIL     20.4s  no tool call although tool_choice=required (reply: 'Hello! How can I assist…
  tools.choice_named      FAIL     473ms  called 'get_weather'; named tool_choice get_time was ignored
  tools.clean_content     PASS     507ms  tool_calls structured, content clean
  tools.result_roundtrip  PASS     429ms  final answer uses the tool result
  tools.multi_result      PASS     729ms  both results reflected in the answer
  stream.tools            PASS     485ms  get_weather({"city": "Paris", "unit": "celsius"}) assembled from deltas
  stream.tools_parallel   PASS      1.6s  2 calls assembled with distinct indexes
  json.mode               PASS     245ms  valid JSON object with keys ['age', 'name']
  json.schema             PASS      1.4s  output validates against the strict schema
  reasoning.field         SKIP      5.6s  no reasoning returned (normal for non-reasoning models)
  errors.bad_model        WARN     127ms  unknown model accepted with 200 (server ignores the model name)
  errors.bad_request      WARN     114ms  invalid message role accepted with 200
  errors.bad_auth         SKIP         -  no API key configured
  anthropic.basic         PASS      45ms  stop_reason=end_turn, 3 output tokens
  anthropic.stream        PASS     499ms  34 deltas, full event sequence
  anthropic.tools         PASS     519ms  tool_use get_weather {'city': 'Paris'}, stop_reason=tool_use
  anthropic.tool_result   PASS     548ms  answer uses the tool_result
  perf.ttft               PASS     917ms  p50 22 ms (min 19, max 50, n=3)
  perf.throughput         PASS      4.2s  62.4 tok/s (256 tokens via usage, 4.2s total)

  TTFT p50 22 ms · 62.4 tok/s · 24 pass · 2 warn · 3 fail · 2 skip
  NOT AGENT-READY: 3 failing probes
```

Exit code is `0` when nothing fails, `1` on failures (or warnings with `--strict`), `2` if the endpoint is unreachable. The API key is read from `OPENAI_API_KEY` (or `--api-key-env NAME`).

**Docs:** [blackman99.github.io/toolsmoke/docs](https://blackman99.github.io/toolsmoke/docs/) · [GitHub Action](https://blackman99.github.io/toolsmoke/docs/github-action/) · [Probe reference](https://blackman99.github.io/toolsmoke/docs/probes/) · MIT
