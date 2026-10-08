# Probe reference

31 probes in 8 groups, run in this order. Every probe uses `temperature: 0` and trivial prompts, so a failure points at the server, chat template or parser, not at model quality.

Tools used by the probes: `get_weather(city: string, unit?: "celsius"|"fahrenheit")` and `get_time(timezone: string)`.

## basics

| Probe | Checks | WARN | FAIL |
|---|---|---|---|
| `models.list` | `GET /models` lists the requested model | 404, empty list, or model not listed | — |
| `chat.basic` | A plain non-streaming completion returns content and a `finish_reason` | odd `finish_reason` / missing usage | HTTP error, non-JSON, no `choices[0].message`, empty content |
| `chat.system` | The system message is applied ("reply with exactly the word …") | — | System prompt ignored (template drops it) |
| `chat.multi_turn` | A code word from an earlier turn is remembered | — | History lost |
| `chat.stop` | `stop: ["7"]` cuts a count from 1 to 10 | — | Generation continues past the stop sequence |
| `chat.max_tokens` | A 16-token limit is enforced and reported as `finish_reason: "length"` | Truncated but wrong `finish_reason` | More tokens than requested |

## streaming

| Probe | Checks | WARN | FAIL |
|---|---|---|---|
| `stream.basic` | SSE stream delivers several content deltas, a `finish_reason` and `data: [DONE]` | Missing `[DONE]`, single chunk, missing `finish_reason` | No SSE events, non-JSON `data:` lines, no content deltas |
| `stream.usage` | `stream_options: {include_usage: true}` yields a usage chunk | No usage (agents can't track tokens/cost) | Stream broken |

## tools

| Probe | Checks | WARN | FAIL |
|---|---|---|---|
| `tools.single` | "Weather in Paris?" produces one structured `get_weather` call with JSON-object arguments, an id, and `finish_reason: "tool_calls"` | Wrong city or `finish_reason` | No `tool_calls`; markup leaked into `content`; arguments not valid JSON; wrong tool |
| `tools.args_schema` | Arguments validate against the tool schema (required, enum) | Valid but `unit` not `fahrenheit` | Schema violation |
| `tools.parallel` | "Paris and Tokyo" yields 2 calls with distinct ids | Only one call | Duplicate ids (results can't be matched) |
| `tools.choice_none` | `tool_choice: "none"` answers in text | — | Tool called anyway, or tool-call markup printed as text |
| `tools.choice_required` | `tool_choice: "required"` forces a call even for "say hello" | — | No call |
| `tools.choice_named` | `tool_choice: {"type":"function","function":{"name":"get_time"}}` forces that tool | — | Another tool or no call |
| `tools.clean_content` | No `<tool_call>`, `<|python_tag|>`, `[TOOL_CALLS]`, `<function=…>` etc. in `content` | No call made, inconclusive | Raw markup in `content` |
| `tools.result_roundtrip` | A `role: "tool"` message is accepted and the answer uses it (23 °C, sunny) | Model calls the tool again | Rejected (`role=tool` unsupported) or result ignored |
| `tools.multi_result` | Two tool results in one turn are both used | Only one used (template drops extra tool messages) | Neither used / rejected |
| `stream.tools` | A streamed tool call assembles from `delta.tool_calls` into valid JSON arguments | Wrong `finish_reason` | Call streamed as content text, no deltas, invalid JSON |
| `stream.tools_parallel` | Two streamed calls keep separate `index` values | Only one call | Deltas merged / invalid |

## structured

| Probe | Checks | WARN | FAIL |
|---|---|---|---|
| `json.mode` | `response_format: {"type": "json_object"}` returns a JSON object | Wrapped in ```` ``` ```` fences | Rejected, not JSON, not an object |
| `json.schema` | `response_format: {"type": "json_schema", strict: true}` output validates against the schema | Fenced; or cut off at `max_tokens` (grammar not bounding output) | Rejected, not JSON, schema violation |

## reasoning

| Probe | Checks | WARN | FAIL |
|---|---|---|---|
| `reasoning.field` | Reasoning arrives in `reasoning_content` / `reasoning` / `thinking`, not in `content` | — | `<think>`-style tags in `content` (enable the server's reasoning parser); no reasoning with `--require-reasoning` |

SKIP when the model returns no reasoning (normal for non-reasoning models).

## errors

| Probe | Checks | WARN | FAIL |
|---|---|---|---|
| `errors.bad_model` | Unknown model → 4xx JSON error | 200 (single-model servers often ignore `model`), non-JSON error body | 5xx |
| `errors.bad_request` | Invalid role → 400/422 | Accepted with 200, non-JSON body | 5xx (agents retry forever) |
| `errors.bad_auth` | Wrong API key → 401/403 | Key accepted (auth not enforced), other 4xx | 5xx |

`errors.bad_auth` is skipped when no API key is configured.

## anthropic (opt-in: `--anthropic`)

| Probe | Checks | WARN | FAIL |
|---|---|---|---|
| `anthropic.basic` | `POST /v1/messages` returns a `message` with a text block, `stop_reason`, usage | Missing fields | HTTP error / not a message object |
| `anthropic.stream` | Streaming emits `message_start`, `content_block_start`, `content_block_delta` (`text_delta`), `content_block_stop`, `message_delta`, `message_stop` | Some events missing | No text deltas, non-JSON data |
| `anthropic.tools` | A `tool_use` block with an id and object `input`, `stop_reason: "tool_use"` | Wrong `stop_reason` | No `tool_use`, markup in text, bad input |
| `anthropic.tool_result` | A `tool_result` block is accepted and used | Tool called again | Ignored or rejected |

## performance

| Probe | Checks | WARN | FAIL |
|---|---|---|---|
| `perf.ttft` | Median time to first content token over `--perf-runs` streamed requests | > 3000 ms | > `--max-ttft` |
| `perf.throughput` | Decode tokens/sec of a ~200-token streamed answer | < 15 tok/s | < `--min-tps` |

Throughput = `(completion_tokens − 1) / (t_last_token − t_first_token)`. `completion_tokens` comes from the stream's usage chunk when available, otherwise the content-chunk count is used (noted in the detail line).
