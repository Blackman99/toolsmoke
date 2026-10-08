"""The README sample run is the source of truth; docs and the landing page must quote it exactly."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ROW = re.compile(r"^  (\S+)\s+(PASS|WARN|FAIL|SKIP)\s+(\S+)  (.*)$")
FOOTER = re.compile(r"TTFT p50 (\d+) ms · ([\d.]+) tok/s · (\d+) pass · (\d+) warn · (\d+) fail · (\d+) skip")

if not (ROOT / "README.md").exists() or not (ROOT / "site" / "app.js").exists():
    pytest.skip("repository checkout required", allow_module_level=True)


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _console(text):
    return re.search(r"```console\n(.*?)```", text, re.S).group(1).splitlines()


@pytest.fixture(scope="module")
def sample():
    lines = _console(_read("README.md"))
    rows = [ROW.match(line).groups() for line in lines if ROW.match(line)]
    footer = next(line for line in lines if FOOTER.search(line))
    verdict = next(line for line in lines if "AGENT-READY" in line)
    return {"lines": lines, "rows": rows, "footer": footer, "verdict": verdict,
            "nums": FOOTER.search(footer).groups()}


def test_readme_sample_is_self_consistent(sample):
    rows, nums = sample["rows"], sample["nums"]
    counts = [sum(1 for r in rows if r[1] == s) for s in ("PASS", "WARN", "FAIL", "SKIP")]
    assert [int(n) for n in nums[2:]] == counts
    assert f"runs {len(rows)} small probes" in _read("README.md")
    ttft = next(r for r in rows if r[0] == "perf.ttft")[3]
    tps = next(r for r in rows if r[0] == "perf.throughput")[3]
    assert ttft.startswith(f"p50 {nums[0]} ms") and tps.startswith(f"{nums[1]} tok/s")
    assert sample["verdict"].strip() == f"NOT AGENT-READY: {nums[4]} failing probes"


def test_docs_index_excerpt_matches_readme(sample):
    lines = [line for line in _console(_read("docs/index.md")) if line.strip() not in ("", "...")]
    assert lines, "docs/index.md lost its sample"
    for line in lines:
        assert line in sample["lines"], f"docs/index.md line not in README sample: {line!r}"
    assert sample["footer"] in lines and sample["verdict"] in lines


def test_landing_page_terminal_matches_readme(sample):
    js = _read("site/app.js")
    rows = json.loads(re.match(r"const ROWS = (.*);\n", js).group(1))
    assert len(rows) == len(sample["rows"])
    for (rid, st, t, detail), (eid, est, et, edetail) in zip(rows, sample["rows"]):
        assert (rid, st, t) == (eid, est, et)
        assert detail == edetail or (detail.endswith("…") and edetail.startswith(detail[:-1])), rid
    ttft, tps, p, w, f, s = sample["nums"]
    for frag in (f"<b>{ttft} ms</b>", f"<b>{tps} tok/s</b>", f"{p} pass", f"{w} warn", f"{f} fail", f"{s} skip",
                 sample["verdict"].strip()):
        assert frag in js, frag


def test_probe_counts_and_json_example_match_readme(sample):
    n = len(sample["rows"])
    assert f"{n} probes. One verdict." in _read("site/index.html")
    assert f"{n} probes in 8 groups" in _read("docs/probes.md")
    assert f"each of the {n} probes" in _read("docs/index.md")
    ttft, tps, p, w, f, s = sample["nums"]
    usage = _read("docs/usage.md")
    assert f'"summary": {{"pass": {p}, "warn": {w}, "fail": {f}, "skip": {s}}}' in usage
    assert f'"performance": {{"ttft_ms_p50": {float(ttft)}, "tokens_per_sec": {tps}}}' in usage
