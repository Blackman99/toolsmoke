const ROWS = [["models.list", "PASS", "1ms", "1 model(s) listed, 'qwen' present"], ["chat.basic", "PASS", "81ms", "finish_reason=stop, 3 completion tokens"], ["chat.system", "PASS", "61ms", "system instruction obeyed"], ["chat.multi_turn", "PASS", "59ms", "history passed through correctly"], ["chat.stop", "PASS", "216ms", "stopped before '7' (finish_reason=stop)"], ["chat.max_tokens", "PASS", "279ms", "truncated at 16 tokens, finish_reason=l…"], ["stream.basic", "PASS", "431ms", "29 content chunks, [DONE] received, fin…"], ["stream.usage", "PASS", "56ms", "usage chunk: 37 prompt / 3 completion t…"], ["tools.single", "PASS", "499ms", "get_weather({\"city\": \"Paris\", \"unit\": \"…"], ["tools.args_schema", "PASS", "552ms", "valid against schema: {\"city\": \"Tokyo\",…"], ["tools.parallel", "PASS", "1.0s", "2 calls with distinct ids: Paris, Tokyo"], ["tools.choice_none", "FAIL", "491ms", "tool call leaked into content as text: …"], ["tools.choice_required", "FAIL", "20.4s", "no tool call although tool_choice=requi…"], ["tools.choice_named", "FAIL", "473ms", "called 'get_weather'; named tool_choice…"], ["tools.clean_content", "PASS", "507ms", "tool_calls structured, content clean"], ["tools.result_roundtrip", "PASS", "429ms", "final answer uses the tool result"], ["tools.multi_result", "PASS", "729ms", "both results reflected in the answer"], ["stream.tools", "PASS", "485ms", "get_weather({\"city\": \"Paris\", \"unit\": \"…"], ["stream.tools_parallel", "PASS", "1.6s", "2 calls assembled with distinct indexes"], ["json.mode", "PASS", "245ms", "valid JSON object with keys ['age', 'na…"], ["json.schema", "PASS", "1.4s", "output validates against the strict sch…"], ["reasoning.field", "SKIP", "5.6s", "no reasoning returned (normal for non-r…"], ["errors.bad_model", "WARN", "127ms", "unknown model accepted with 200 (server…"], ["errors.bad_request", "WARN", "114ms", "invalid message role accepted with 200"], ["errors.bad_auth", "SKIP", "-", "no API key configured"], ["anthropic.basic", "PASS", "45ms", "stop_reason=end_turn, 3 output tokens"], ["anthropic.stream", "PASS", "499ms", "34 deltas, full event sequence"], ["anthropic.tools", "PASS", "519ms", "tool_use get_weather {'city': 'Paris'},…"], ["anthropic.tool_result", "PASS", "548ms", "answer uses the tool_result"], ["perf.ttft", "PASS", "917ms", "p50 22 ms (min 19, max 50, n=3)"], ["perf.throughput", "PASS", "4.2s", "62.4 tok/s (256 tokens via usage, 4.2s …"]];
// Everything below is driven by ROWS (the README sample run); tests/test_docs_sync.py keeps it in sync.
const GROUPS = [["basics", /^(models|chat)\./], ["streaming", /^stream\.(basic|usage)$/], ["tools", /^(tools\.|stream\.tools)/], ["structured", /^json\./],
  ["reasoning", /^reasoning\./], ["errors", /^errors\./], ["anthropic", /^anthropic\./], ["performance", /^perf\./]];
const groupOf = id => GROUPS.find(g => g[1].test(id))[0];
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s, el = document) => el.querySelector(s);
const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const MARK = {PASS: "M3 11l4.5 4.5L17 4", FAIL: "M4 4l12 12M16 4L4 16", WARN: "M6.5 6.8a3.5 3.5 0 117 0c0 2.6-3.5 3-3.5 5.6M10 16.2v.3", SKIP: "M5 10h10"};
const GLYPH = {PASS: "✓", FAIL: "✗", WARN: "?", SKIP: "–"};
const TTFT = +ROWS.find(r => r[0] === "perf.ttft")[3].match(/p50 (\d+) ms/)[1];
const TPS = +ROWS.find(r => r[0] === "perf.throughput")[3].match(/([\d.]+) tok\/s/)[1];
const TOTAL = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0};
ROWS.forEach(r => TOTAL[r[1]]++);

/* ---------- sheet 1: the report prints line by line, gets ticked, stamped and signed ---------- */
const list = $("#results"), stamp = $("#stamp"), summary = $("#summary"), sig = $("#sig");
const seal = $("#seal"), fResults = $("#f-results"), fTtft = $("#f-ttft"), fTps = $("#f-tps"), fVerdict = $("#f-verdict");
list.innerHTML = ROWS.map(([id, st, t, d], i) =>
  `<li class="${st}" title="${esc(d)}"><span class="n">${String(i + 1).padStart(2, "0")}</span><span class="id">${id}</span>` +
  `<svg class="mk" viewBox="0 0 20 20" role="img" aria-label="${st}"><path pathLength="1" d="${MARK[st]}"/></svg>` +
  `<span class="t">${t}</span><span class="o">${esc(d)}</span></li>`).join("");
const items = [...list.children];
function footer() {
  // Same numbers and wording as the CLI footer in the README sample.
  return `<span class="t-head">TTFT p50</span> <b>22 ms</b> <span class="t-dim">·</span> <b>62.4 tok/s</b> <span class="t-dim">·</span> <span class="t-pass">24 pass</span> <span class="t-dim">·</span> <span class="t-warn">2 warn</span> <span class="t-dim">·</span> <span class="t-fail">3 fail</span> <span class="t-dim">·</span> <span class="t-skip">2 skip</span><br><span class="t-bad">NOT AGENT-READY: 3 failing probes</span>`;
}
const counts = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0};
let run = 0, timer = null;
const sleep = ms => new Promise(r => { timer = setTimeout(r, ms); });
function reset() {
  clearTimeout(timer);
  items.forEach(li => li.classList.remove("p"));
  Object.keys(counts).forEach(k => { counts[k] = 0; });
  fResults.textContent = "awaiting print"; fTtft.textContent = "—"; fTps.textContent = "—";
  fVerdict.innerHTML = '<span class="blank">________________</span>';
  stamp.classList.remove("on"); summary.classList.remove("on"); sig.classList.remove("on"); seal.classList.remove("on");
}
function printRow(i) {
  const [id, st] = ROWS[i];
  items[i].classList.add("p");
  counts[st]++;
  const done = i + 1;
  fResults.textContent = done < ROWS.length ? `${done} / ${ROWS.length} printed` : `${TOTAL.PASS} pass · ${TOTAL.WARN} warn · ${TOTAL.FAIL} fail · ${TOTAL.SKIP} skip`;
  if (id === "perf.ttft") fTtft.textContent = `${TTFT} ms`;
  if (id === "perf.throughput") fTps.textContent = `${TPS} tok/s`;
}
function finish() {
  summary.innerHTML = footer(); summary.classList.add("on");
  fVerdict.innerHTML = '<span class="blank" aria-hidden="true">________________</span><span class="sr">NOT AGENT-READY: 3 failing probes</span>';
  stamp.classList.add("on");
}
async function play() {
  const me = ++run;
  reset();
  if (reduced) { ROWS.forEach((_, i) => printRow(i)); finish(); sig.classList.add("on"); seal.classList.add("on"); return; }
  await sleep(350);
  for (let i = 0; i < ROWS.length; i++) {
    if (me !== run) return;
    printRow(i);
    await sleep(ROWS[i][1] === "FAIL" ? 430 : 105);
  }
  await sleep(350); if (me !== run) return;
  finish();
  await sleep(650); if (me !== run) return;
  sig.classList.add("on");
  await sleep(700); if (me === run) seal.classList.add("on");
}
$("#reprint").addEventListener("click", play);
const printIO = new IntersectionObserver(es => { if (es[0].isIntersecting) { printIO.disconnect(); play(); } }, {threshold: 0.05});
printIO.observe(list);

/* ---------- sheet 2: reviewer's red-pen annotations, driven by scroll ---------- */
const sheet2 = $("#sheet2"), steps = [...document.querySelectorAll("#log li")];
function setStep(n) {
  for (let k = 1; k <= 4; k++) sheet2.classList.toggle("k" + k, k <= n);
  steps.forEach(li => li.classList.toggle("on", +li.dataset.step === n));
}
if (reduced) setStep(4);
else {
  const stepIO = new IntersectionObserver(es => { es.forEach(e => { if (e.isIntersecting) setStep(+e.target.dataset.step); }); }, {rootMargin: "-45% 0px -45% 0px"});
  steps.forEach(li => stepIO.observe(li));
}

/* ---------- sheet 3: schedule marks from the sample run ---------- */
for (const li of document.querySelectorAll("#sched li")) {
  const rows = ROWS.filter(r => groupOf(r[0]) === li.dataset.g);
  $(".gc", li).textContent = `${rows.length} probe${rows.length > 1 ? "s" : ""}`;
  li.insertAdjacentHTML("beforeend", `<div class="chips">${rows.map(([id, st, t, d]) =>
    `<span class="chip ${st}" tabindex="0"><i aria-hidden="true">${GLYPH[st]}</i>${id}<span class="tip" role="tooltip">${st} · ${t} · ${esc(d)}</span></span>`).join("")}</div>`);
}

/* ---------- micro-interactions: copy buttons, folder tabs ---------- */
document.querySelectorAll("[data-copy] .copy").forEach(b => b.addEventListener("click", async () => {
  const code = $("code", b.parentElement), text = code.innerText.replace(/^\$\s*/, "");
  try { await navigator.clipboard.writeText(text); b.textContent = "COPIED"; }
  catch { const r = document.createRange(); r.selectNodeContents(code); getSelection().removeAllRanges(); getSelection().addRange(r); b.textContent = "⌘/Ctrl+C"; }
  b.classList.add("done");
  setTimeout(() => { b.textContent = "[copy]"; b.classList.remove("done"); }, 1600);
}));
const tabs = [...document.querySelectorAll(".tab")];
function select(t, focus) {
  tabs.forEach(x => { const on = x === t; x.setAttribute("aria-selected", on); x.tabIndex = on ? 0 : -1; $("#tab-" + x.dataset.tab).hidden = !on; });
  if (focus) t.focus();
}
tabs.forEach((t, i) => {
  t.addEventListener("click", () => select(t));
  t.addEventListener("keydown", e => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (d) { e.preventDefault(); select(tabs[(i + d + tabs.length) % tabs.length], true); }
  });
});
