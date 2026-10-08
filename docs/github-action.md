# CI & GitHub Action

Gate a deployment, a model upgrade or a gateway config change on agent-readiness.

## Reusable action

```yaml
- uses: Blackman99/toolsmoke@v0.1.1
  with:
    base-url: https://llm.internal.example.com/v1
    model: qwen3-coder
    api-key: ${{ secrets.LLM_API_KEY }}
    anthropic: "true"
    max-ttft: "1500"
```

The action installs toolsmoke (no other dependencies), runs it, appends a Markdown table to the **job summary**, writes a JSON report, and fails the step if any probe fails.

### Inputs

| Input | Default | Description |
|---|---|---|
| `base-url` | required | OpenAI-compatible base URL |
| `model` | required | Model name |
| `api-key` | `""` | API key; pass a secret |
| `anthropic` | `false` | Also probe the Messages API |
| `only` / `skip` | `""` | Comma-separated globs, e.g. `tools.*,stream.*` |
| `strict` | `false` | Fail on warnings too |
| `max-ttft` / `min-tps` | `""` | Hard speed gates |
| `args` | `""` | Extra raw CLI arguments |
| `report` | `toolsmoke-report.json` | JSON report path |
| `fail-on-error` | `true` | Set `false` to record results without failing the step |
| `python-version` | `3.12` | Python used to run toolsmoke |

### Outputs

`verdict`, `passed`, `warned`, `failed`, `ttft-ms`, `tokens-per-sec`, `report`, `exit-code`.

## Example: test a self-hosted model in CI

```yaml
name: agent-readiness
on: [pull_request]
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - name: Start llama.cpp
        run: |
          curl -sL -o llama.tgz https://github.com/ggml-org/llama.cpp/releases/download/b11490/llama-b11490-bin-ubuntu-x64.tar.gz
          tar xzf llama.tgz
          curl -sL -o model.gguf https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
          nohup ./llama-b11490/llama-server -m model.gguf --jinja --port 8080 --alias qwen &
          until curl -sf localhost:8080/health; do sleep 1; done
      - id: smoke
        uses: Blackman99/toolsmoke@v0.1.1
        with:
          base-url: http://localhost:8080/v1
          model: qwen
          fail-on-error: "false"
      - run: echo "${{ steps.smoke.outputs.verdict }} — ${{ steps.smoke.outputs.tokens-per-sec }} tok/s"
      - uses: actions/upload-artifact@v7
        with: {name: toolsmoke-report, path: toolsmoke-report.json}
```

## Scheduled check of a hosted provider

```yaml
on:
  schedule: [{cron: "0 6 * * *"}]
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: Blackman99/toolsmoke@v0.1.1
        with:
          base-url: https://openrouter.ai/api/v1
          model: qwen/qwen3-coder
          api-key: ${{ secrets.OPENROUTER_API_KEY }}
          skip: errors
```

## Without the action

Any CI works, it's one command and an exit code:

```bash
uvx --from git+https://github.com/Blackman99/toolsmoke@v0.1.1 toolsmoke \
  --base-url "$LLM_URL" --model "$LLM_MODEL" --json report.json --markdown summary.md
```

GitLab CI, Jenkins, etc. can read `report.json` or the exit code (0 ok, 1 failures, 2 unreachable).
