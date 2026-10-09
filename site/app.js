const ROWS = [["models.list", "PASS", "1ms", "1 model(s) listed, 'qwen' present"], ["chat.basic", "PASS", "81ms", "finish_reason=stop, 3 completion tokens"], ["chat.system", "PASS", "61ms", "system instruction obeyed"], ["chat.multi_turn", "PASS", "59ms", "history passed through correctly"], ["chat.stop", "PASS", "216ms", "stopped before '7' (finish_reason=stop)"], ["chat.max_tokens", "PASS", "279ms", "truncated at 16 tokens, finish_reason=l…"], ["stream.basic", "PASS", "431ms", "29 content chunks, [DONE] received, fin…"], ["stream.usage", "PASS", "56ms", "usage chunk: 37 prompt / 3 completion t…"], ["tools.single", "PASS", "499ms", "get_weather({\"city\": \"Paris\", \"unit\": \"…"], ["tools.args_schema", "PASS", "552ms", "valid against schema: {\"city\": \"Tokyo\",…"], ["tools.parallel", "PASS", "1.0s", "2 calls with distinct ids: Paris, Tokyo"], ["tools.choice_none", "FAIL", "491ms", "tool call leaked into content as text: …"], ["tools.choice_required", "FAIL", "20.4s", "no tool call although tool_choice=requi…"], ["tools.choice_named", "FAIL", "473ms", "called 'get_weather'; named tool_choice…"], ["tools.clean_content", "PASS", "507ms", "tool_calls structured, content clean"], ["tools.result_roundtrip", "PASS", "429ms", "final answer uses the tool result"], ["tools.multi_result", "PASS", "729ms", "both results reflected in the answer"], ["stream.tools", "PASS", "485ms", "get_weather({\"city\": \"Paris\", \"unit\": \"…"], ["stream.tools_parallel", "PASS", "1.6s", "2 calls assembled with distinct indexes"], ["json.mode", "PASS", "245ms", "valid JSON object with keys ['age', 'na…"], ["json.schema", "PASS", "1.4s", "output validates against the strict sch…"], ["reasoning.field", "SKIP", "5.6s", "no reasoning returned (normal for non-r…"], ["errors.bad_model", "WARN", "127ms", "unknown model accepted with 200 (server…"], ["errors.bad_request", "WARN", "114ms", "invalid message role accepted with 200"], ["errors.bad_auth", "SKIP", "-", "no API key configured"], ["anthropic.basic", "PASS", "45ms", "stop_reason=end_turn, 3 output tokens"], ["anthropic.stream", "PASS", "499ms", "34 deltas, full event sequence"], ["anthropic.tools", "PASS", "519ms", "tool_use get_weather {'city': 'Paris'},…"], ["anthropic.tool_result", "PASS", "548ms", "answer uses the tool_result"], ["perf.ttft", "PASS", "917ms", "p50 22 ms (min 19, max 50, n=3)"], ["perf.throughput", "PASS", "4.2s", "62.4 tok/s (256 tokens via usage, 4.2s …"]];
// Everything below is driven by ROWS (the README sample run); tests/test_docs_sync.py keeps it in sync.
const GROUPS = [["basics", "basics", /^(models|chat)\./], ["streaming", "stream", /^stream\.(basic|usage)$/], ["tools", "tools", /^(tools\.|stream\.tools)/],
  ["structured", "json", /^json\./], ["reasoning", "think", /^reasoning\./], ["errors", "errors", /^errors\./], ["anthropic", "anthropic", /^anthropic\./], ["performance", "perf", /^perf\./]];
const groupOf = id => GROUPS.find(g => g[2].test(id))[0];
const CMD = "toolsmoke --base-url http://localhost:8080/v1 --model qwen --anthropic";
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s, el = document) => el.querySelector(s);
const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const pad = (s, n) => s + " ".repeat(Math.max(0, n - s.length));
const lpad = (s, n) => " ".repeat(Math.max(0, n - s.length)) + s;
const CLS = {PASS: "t-pass", FAIL: "t-fail", WARN: "t-warn", SKIP: "t-skip"};
const TTFT = +ROWS.find(r => r[0] === "perf.ttft")[3].match(/p50 (\d+) ms/)[1];
const TPS = +ROWS.find(r => r[0] === "perf.throughput")[3].match(/([\d.]+) tok\/s/)[1];

/* ---------- hero: the bench replays the run probe by probe ---------- */
const term = $("#term"), leds = $("#leds"), statusEl = $("#status"), statusText = $("#status-text"), stamp = $("#stamp");
const ledFor = {};
for (const [name, label] of GROUPS) {
  const ids = ROWS.filter(r => groupOf(r[0]) === name);
  const g = document.createElement("div");
  g.className = "lg";
  g.innerHTML = `<div class="lg-cells">${ids.map(() => '<span class="led"></span>').join("")}</div><small>${label}</small>`;
  leds.appendChild(g);
  g.querySelectorAll(".led").forEach((el, i) => { ledFor[ids[i][0]] = el; el.title = ids[i][0]; });
}
function rowHTML([id, st, t, d]) {
  const det = st === "FAIL" ? `<span class="t-faildet">${esc(d)}</span>` : st === "SKIP" ? `<span class="t-dim">${esc(d)}</span>` : esc(d);
  return `  ${pad(id, 22)} <span class="${CLS[st]}">${pad(st, 4)}</span> <span class="t-dim">${lpad(t, 6)}</span>  ${det}`;
}
function footer() {
  return [`  <span class="t-head">TTFT p50</span> <b>22 ms</b> <span class="t-dim">·</span> <b>62.4 tok/s</b> <span class="t-dim">·</span> <span class="t-pass">24 pass</span> <span class="t-dim">·</span> <span class="t-warn">2 warn</span> <span class="t-dim">·</span> <span class="t-fail">3 fail</span> <span class="t-dim">·</span> <span class="t-skip">2 skip</span>`,
    `  <span class="t-bad">NOT AGENT-READY: 3 failing probes</span>`, "", `<span class="p">$</span> <span class="t-dim">echo $?</span>`, "1"];
}
function line(html, animate) {
  const d = document.createElement("div");
  d.className = animate ? "tl in" : "tl";
  d.innerHTML = html || " ";
  term.appendChild(d);
  while (term.children.length > 40) term.firstChild.remove();
  return d;
}
const counts = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0};
function gauges() {
  const n = ROWS.length, done = counts.PASS + counts.WARN + counts.FAIL + counts.SKIP;
  const bar = $("#g-bar").children;
  ["PASS", "WARN", "FAIL", "SKIP"].forEach((k, i) => { bar[i].style.width = (100 * counts[k] / n) + "%"; });
  $("#g-counts").textContent = done < n ? `${done} / ${n}` : `${counts.PASS} pass · ${counts.WARN} warn · ${counts.FAIL} fail · ${counts.SKIP} skip`;
}
function countUp(el, to, digits, unit) {
  if (reduced) { el.textContent = to.toFixed(digits) + unit; return; }
  const t0 = performance.now();
  const step = now => { const k = Math.max(0, Math.min(1, (now - t0) / 600)); el.textContent = (to * (1 - Math.pow(1 - k, 3))).toFixed(digits) + unit; if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
  setTimeout(() => { el.textContent = to.toFixed(digits) + unit; }, 700);
}
let run = 0, timer = null;
const sleep = ms => new Promise(r => { timer = setTimeout(r, ms); });
function reset() {
  clearTimeout(timer);
  term.innerHTML = "";
  Object.keys(counts).forEach(k => { counts[k] = 0; });
  Object.values(ledFor).forEach(el => { el.className = "led"; });
  $("#g-ttft").textContent = "–"; $("#g-tps").textContent = "–";
  stamp.classList.remove("on");
  gauges();
}
function apply(r, animate) {
  line(rowHTML(r), animate);
  ledFor[r[0]].className = "led " + r[1];
  counts[r[1]]++;
  if (r[0] === "perf.ttft") countUp($("#g-ttft"), TTFT, 0, " ms");
  if (r[0] === "perf.throughput") countUp($("#g-tps"), TPS, 1, " tok/s");
  gauges();
}
function finish(animate) {
  line("", false);
  footer().forEach(h => line(h, animate));
  line(`<span class="p">$</span> <span class="cursor"></span>`, false);
  statusEl.dataset.state = "fail"; statusText.textContent = "exit 1";
  stamp.classList.add("on");
}
async function play() {
  const me = ++run;
  reset();
  const head = `<span class="p">$</span> `;
  if (reduced) {
    line(head + `<span class="c">${esc(CMD)}</span>`);
    ROWS.forEach(r => apply(r, false));
    return finish(false);
  }
  statusEl.dataset.state = "run"; statusText.textContent = "typing";
  const cmd = line(head + '<span class="cursor"></span>');
  await sleep(350);
  for (let i = 3; i <= CMD.length; i += 3) {
    if (me !== run) return;
    cmd.innerHTML = head + `<span class="c">${esc(CMD.slice(0, i))}</span><span class="cursor"></span>`;
    await sleep(24);
  }
  cmd.innerHTML = head + `<span class="c">${esc(CMD)}</span>`;
  line(`<span class="t-dim">toolsmoke 0.1.1 · http://localhost:8080/v1 · model qwen</span>`, true);
  line(`  <span class="t-head">${pad("PROBE", 22)} RESULT TIME  DETAIL</span>`, true);
  statusText.textContent = "probing";
  await sleep(250);
  for (const r of ROWS) {
    if (me !== run) return;
    apply(r, true);
    await sleep(r[1] === "FAIL" ? 520 : 95 + Math.random() * 70);
  }
  await sleep(250);
  if (me === run) finish(true);
}
$("#replay").addEventListener("click", play);
// Start the run once the bench is mostly on screen (right away on desktop, on first scroll on small phones).
const heroIO = new IntersectionObserver(es => { if (es[0].isIntersecting) { heroIO.disconnect(); play(); } }, {threshold: 0.4});
heroIO.observe($("#bench"));

/* ---------- leak: scroll-driven walkthrough of the core mechanism ---------- */
const stage = $("#stage"), leaked = $("#leaked"), steps = [...document.querySelectorAll("#steps li")];
let typed = false;
function typeLeak() {
  if (typed || reduced) return;
  typed = true;
  const full = leaked.dataset.text;
  let i = 0;
  const tick = () => { leaked.textContent = full.slice(0, ++i); if (i < full.length) setTimeout(tick, 28); };
  tick();
}
function setStep(n) {
  stage.dataset.step = n;
  steps.forEach(li => li.classList.toggle("on", li.dataset.step === String(n)));
  if (n >= 2) typeLeak();
}
const stepIO = new IntersectionObserver(es => { es.forEach(e => { if (e.isIntersecting) setStep(+e.target.dataset.step); }); },
  {rootMargin: "-45% 0px -45% 0px"});
steps.forEach(li => stepIO.observe(li));
setStep(1);

/* ---------- probe board: chips lit with the sample run ---------- */
for (const grp of document.querySelectorAll(".grp")) {
  const rows = ROWS.filter(r => groupOf(r[0]) === grp.dataset.g);
  $("h3", grp).insertAdjacentHTML("beforeend", `<small>${rows.length} probe${rows.length > 1 ? "s" : ""}</small>`);
  grp.insertAdjacentHTML("beforeend", `<div class="chips">${rows.map(([id, st, t, d]) => `<span class="chip ${st}" title="${st} · ${t} · ${esc(d).replace(/"/g, "&quot;")}">${id}</span>`).join("")}</div>`);
}

{ const c = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0}; ROWS.forEach(r => c[r[1]]++);
  $("#vc-line").innerHTML = `<b class="t-pass">${c.PASS} pass</b> · <b class="t-warn">${c.WARN} warn</b> · <b class="t-fail">${c.FAIL} fail</b> · <b class="t-skip">${c.SKIP} skip</b> · TTFT p50 ${TTFT} ms · ${TPS} tok/s`; }

/* ---------- micro-interactions: copy buttons and tabs ---------- */
document.querySelectorAll("[data-copy] .copy").forEach(b => b.addEventListener("click", async () => {
  const text = $("code", b.parentElement).innerText.replace(/^\$\s*/, "");
  const label = $("span", b);
  try { await navigator.clipboard.writeText(text); label.textContent = "Copied ✓"; b.classList.add("done"); }
  catch { const r = document.createRange(); r.selectNodeContents($("code", b.parentElement)); getSelection().removeAllRanges(); getSelection().addRange(r); label.textContent = "Press ⌘/Ctrl+C"; }
  setTimeout(() => { label.textContent = "Copy"; b.classList.remove("done"); }, 1600);
}));
const tabs = [...document.querySelectorAll(".tab")], ink = $(".tab-ink");
function inkTo(t) { ink.style.width = t.offsetWidth + "px"; ink.style.transform = `translateX(${t.offsetLeft}px)`; }
function select(t, focus) {
  tabs.forEach(x => { const on = x === t; x.setAttribute("aria-selected", on); x.tabIndex = on ? 0 : -1; $("#tab-" + x.dataset.tab).hidden = !on; });
  inkTo(t); if (focus) t.focus();
}
tabs.forEach((t, i) => {
  t.addEventListener("click", () => select(t));
  t.addEventListener("keydown", e => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (d) { e.preventDefault(); select(tabs[(i + d + tabs.length) % tabs.length], true); }
  });
});
requestAnimationFrame(() => inkTo(tabs[0]));
addEventListener("resize", () => inkTo(tabs.find(t => t.getAttribute("aria-selected") === "true")));
