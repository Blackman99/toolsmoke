# Contributing

Thanks for helping! Read [GOAL.md](GOAL.md) first: every change must make the one-command "does this endpoint work for agents, and how fast" answer more accurate or easier to get.

## Dev setup

```bash
git clone https://github.com/Blackman99/toolsmoke && cd toolsmoke
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

No runtime dependencies are allowed (stdlib only). `pytest` is the only dev dependency.

## Try it without a real model

```bash
toolsmoke --demo good      # everything passes
toolsmoke --demo broken    # a server with common real-world bugs
toolsmoke-mock --mode broken --defects -no_usage --port 8080   # run the mock yourself
toolsmoke-mock --list-defects
```

## Adding a probe

1. Pick the right module in `src/toolsmoke/probes/` and register with `@probe("group.name", "group", "Short title")`.
2. Return `Outcome(PASS|WARN|FAIL|SKIP, "detail")`. The detail must explain *what the server did wrong* in one line.
3. FAIL only for behaviour that breaks real agent loops; use WARN for spec deviations that frameworks usually tolerate.
4. Teach the mock server (`src/toolsmoke/mock.py`) both the correct behaviour and, if useful, a new defect that triggers the failure.
5. Update `tests/test_integration.py` (good mode must stay all-PASS; add the expected status to `BROKEN_EXPECTED` if relevant) and `docs/probes.md`.

## Reporting a false positive

Open an issue with the server (and version), model, the failing probe line and, if possible, `--format json` output. Real-world server quirks are the most valuable reports we get.

## Pull requests

- Keep PRs focused; include tests.
- `pytest -q` and `ruff check src tests --select F,E9` must pass (CI runs both, plus the GitHub Action self-test).
- Changes to probe ids or the JSON report schema need a CHANGELOG entry.
