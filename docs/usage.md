# Usage

## The one command

```bash
toolsmoke --base-url http://localhost:8080/v1 --model qwen3-coder
```

- `--base-url` is the OpenAI-compatible root, the part before `/chat/completions` (usually ends in `/v1`).
- `--model` is the model name the server expects.
- The API key comes from `OPENAI_API_KEY` (or `TOOLSMOKE_API_KEY`, or any variable named by `--api-key-env`). It is never passed on the command line.

Typical base URLs (or use `--preset NAME` to fill the default for you; see [Configuration](configuration.md)):

| Server | Base URL |
|---|---|
| llama.cpp `llama-server` (start with `--jinja`) | `http://localhost:8080/v1` |
| vLLM | `http://localhost:8000/v1` |
| Ollama | `http://localhost:11434/v1` |
| LM Studio | `http://localhost:1234/v1` |
| SGLang | `http://localhost:30000/v1` |
| OpenAI | `https://api.openai.com/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |

## Reading the result

Each probe ends in one of:

| Status | Meaning |
|---|---|
| **PASS** | Behaves as agents expect |
| **WARN** | Deviates from the spec in a way most frameworks tolerate (or that might be intentional) |
| **FAIL** | Breaks real agent loops |
| **SKIP** | Not applicable (no API key given, Anthropic probes not requested, model has no reasoning) |

The footer line shows the headline numbers (median TTFT, decode tokens/sec) and the verdict:

- `AGENT-READY`: no failures and no warnings
- `AGENT-READY, with warnings`
- `NOT AGENT-READY: N failing probes`

## Exit codes

| Code | Meaning |
|---|---|
| `0` | No FAIL (warnings allowed unless `--strict`) |
| `1` | At least one FAIL, or a WARN with `--strict` |
| `2` | Usage error or the endpoint is unreachable |

## Choosing probes

```bash
toolsmoke --list                                  # all probe ids and groups
toolsmoke ... --only 'tools.*' --only stream.tools # glob on id or group, repeatable
toolsmoke ... --only tools                        # a whole group
toolsmoke ... --skip perf --skip errors           # everything except these
```

Groups: `basics`, `streaming`, `tools`, `structured`, `reasoning`, `errors`, `anthropic`, `responses`, `performance`.

## Anthropic Messages API

Servers like vLLM, llama.cpp, LiteLLM and many gateways also expose `POST /v1/messages`. Add `--anthropic` to probe it:

```bash
toolsmoke --base-url http://localhost:8080/v1 --model qwen --anthropic
# Messages API somewhere else:
toolsmoke --base-url https://gw.example.com/openai/v1 --model m --anthropic \
          --anthropic-base-url https://gw.example.com/anthropic/v1
```

## OpenAI Responses API

The OpenAI Agents SDK, Codex CLI and other newer clients call `POST /v1/responses` instead of chat completions. vLLM, Ollama, LM Studio, LiteLLM and many gateways serve it too. Add `--responses` to probe it on the same base URL:

```bash
toolsmoke --base-url http://localhost:8000/v1 --model qwen3 --responses
```

## Flaky endpoints: `--repeat`

A tool parser that breaks one request in five passes most single runs and still wrecks a long agent loop. `--repeat N` runs every probe N times. The worst run decides the result, and the detail line starts with the pass rate:

```console
$ toolsmoke-mock --port 8080 --defects flaky_tools &    # leaks every other tool call
$ toolsmoke --base-url http://127.0.0.1:8080/v1 --model mock-model --only tools.single --only tools.clean_content --repeat 4
  PROBE                RESULT    TIME  DETAIL
  tools.single         FAIL      52ms  flaky: 2/4 pass, 2 fail · tool call leaked into content as text: '<tool_call> …
  tools.clean_content  FAIL      52ms  flaky: 2/4 pass, 2 fail · tool call leaked into content as text: '<tool_call> …
```

Without `--repeat` the same server looks fine on a lucky run.

The JSON report gets `"repeat": 4` at the top and, per probe, `metrics.repeat` with the counts and `pass_rate`.

## Output formats

```bash
toolsmoke ... --format json > report.json      # machine-readable on stdout
toolsmoke ... --format markdown                # a Markdown table (good for PR comments)
toolsmoke ... --json report.json               # keep the table, also write JSON
toolsmoke ... --markdown "$GITHUB_STEP_SUMMARY" # append Markdown to a file
```

JSON report shape:

```json
{
  "tool": "toolsmoke", "version": "0.1.1",
  "endpoint": "http://localhost:8080/v1", "model": "qwen", "anthropic": true, "responses": false, "repeat": 1,
  "summary": {"pass": 25, "warn": 3, "fail": 3, "skip": 7},
  "performance": {"ttft_ms_p50": 22.0, "tokens_per_sec": 62.4},
  "verdict": "NOT AGENT-READY: 3 failing probes",
  "results": [
    {"id": "tools.single", "group": "tools", "title": "Single tool call (tool_choice=auto)",
     "status": "pass", "detail": "get_weather({\"city\": \"Paris\", \"unit\": \"celsius\"}) finish_reason=tool_calls",
     "elapsed_ms": 499.0, "metrics": {}}
  ]
}
```

## Speed gates

Performance probes only **warn** by default (TTFT > 3 s, < 15 tok/s). Make them hard requirements:

```bash
toolsmoke ... --max-ttft 800 --min-tps 30
```

TTFT is the median over `--perf-runs` (default 3) streamed requests. Throughput is decode speed: `(tokens − 1) / (last token time − first token time)`, using the server's usage count when available.

## Try it without a model

```bash
toolsmoke --demo good
toolsmoke --demo broken
toolsmoke-mock --mode broken --port 8080 &      # or run the mock yourself
toolsmoke --base-url http://127.0.0.1:8080/v1 --model mock-model --anthropic
```
