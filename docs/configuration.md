# Configuration

Everything is a CLI flag; the endpoint can also come from environment variables. There is no config file in v0.1.

## Endpoint

| Flag | Env | Default | Description |
|---|---|---|---|
| `--base-url URL` | `TOOLSMOKE_BASE_URL` | — (required) | OpenAI-compatible base, e.g. `http://localhost:8080/v1` |
| `--model, -m NAME` | `TOOLSMOKE_MODEL` | — (required) | Model name sent in every request |
| `--api-key-env NAME` | — | `OPENAI_API_KEY` | Name of the env var that holds the API key |
| — | `TOOLSMOKE_API_KEY` | — | If set, always used as the key (overrides `--api-key-env`) |
| `--header, -H 'K: V'` | — | — | Extra HTTP header, repeatable (e.g. `-H 'OpenAI-Organization: org_x'`) |
| `--timeout SEC` | — | `120` | Per-request timeout |

The key is sent as `Authorization: Bearer <key>`. For the Messages API it is also sent as `x-api-key`, together with `anthropic-version: 2023-06-01`.

!!! tip "Keys never go on the command line"
    Shell history and CI logs are where keys leak. Use an env var: `MY_KEY=… toolsmoke --api-key-env MY_KEY …`

## Anthropic Messages API

| Flag | Default | Description |
|---|---|---|
| `--anthropic` | off | Run the `anthropic.*` probes |
| `--anthropic-base-url URL` | `--base-url` (with `/v1` appended if missing) | Where `POST …/messages` lives |

## Probe selection

| Flag | Description |
|---|---|
| `--only GLOB` | Run only probes whose id **or** group matches; repeatable (`--only 'tools.*' --only stream.basic`) |
| `--skip GLOB` | Skip matching probes; repeatable |
| `--require-reasoning` | `reasoning.field` FAILs instead of SKIPping when no reasoning is returned |
| `--list` | Print all probes and exit |

## Request parameters

| Flag | Default | Description |
|---|---|---|
| `--max-tokens N` | `1024` | Token limit for most probes |
| `--token-param NAME` | `max_tokens` | Use `max_completion_tokens` for OpenAI reasoning models (o-series, GPT-5) that reject `max_tokens` |
| `--temperature T` | `0` | Sampling temperature; `none` omits the field (some models only accept the default) |

## Verdict and gates

| Flag | Default | Description |
|---|---|---|
| `--strict` | off | Exit 1 on any WARN as well |
| `--max-ttft MS` | — | FAIL `perf.ttft` above this median TTFT (otherwise WARN only above 3000 ms) |
| `--min-tps N` | — | FAIL `perf.throughput` below this (otherwise WARN only below 15 tok/s) |
| `--perf-runs N` | `3` | Streamed requests used for the TTFT median |

## Output

| Flag | Description |
|---|---|
| `--format, -f table\|json\|markdown` | What goes to stdout (default `table`) |
| `--json FILE` | Also write the JSON report |
| `--markdown FILE` | Also append a Markdown report (works with `$GITHUB_STEP_SUMMARY`) |
| `--quiet, -q` | No live progress on stderr |
| `NO_COLOR=1` / `FORCE_COLOR=1` | Disable / force ANSI colours |

## Mock server (`toolsmoke-mock`)

| Flag | Default | Description |
|---|---|---|
| `--host`, `--port` | `127.0.0.1`, `8080` | Bind address |
| `--mode good\|broken` | `good` | `broken` enables the common real-world defects |
| `--defects a,b,-c` | — | Add defects, or remove with a `-` prefix |
| `--ttft-ms`, `--tps` | `50`, `200` | Simulated latency and speed |
| `--api-key KEY` | — | Require this key |
| `--model-name NAME` | `mock-model` | Model id(s) to serve, repeatable |
| `--list-defects` | | Show all defects |

Defects: `stream_tool_leak`, `leak_tool_calls`, `ignore_tool_choice`, `no_parallel`, `no_usage`, `think_in_content`, `ignore_json_schema`, `bad_errors`, `ignore_stop`, `no_anthropic`, `drop_extra_tool_results`.
