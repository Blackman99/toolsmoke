const ROWS = [["models.list", "PASS", "1ms", "1 model(s) listed, 'qwen' present"], ["chat.basic", "PASS", "81ms", "finish_reason=stop, 3 completion tokens"], ["chat.system", "PASS", "61ms", "system instruction obeyed"], ["chat.multi_turn", "PASS", "59ms", "history passed through correctly"], ["chat.stop", "PASS", "216ms", "stopped before '7' (finish_reason=stop)"], ["chat.max_tokens", "PASS", "279ms", "truncated at 16 tokens, finish_reason=l…"], ["stream.basic", "PASS", "431ms", "29 content chunks, [DONE] received, fin…"], ["stream.usage", "PASS", "56ms", "usage chunk: 37 prompt / 3 completion t…"], ["tools.single", "PASS", "499ms", "get_weather({\"city\": \"Paris\", \"unit\": \"…"], ["tools.args_schema", "PASS", "552ms", "valid against schema: {\"city\": \"Tokyo\",…"], ["tools.parallel", "PASS", "1.0s", "2 calls with distinct ids: Paris, Tokyo"], ["tools.choice_none", "FAIL", "491ms", "tool call leaked into content as text: …"], ["tools.choice_required", "FAIL", "20.4s", "no tool call although tool_choice=requi…"], ["tools.choice_named", "FAIL", "473ms", "called 'get_weather'; named tool_choice…"], ["tools.clean_content", "PASS", "507ms", "tool_calls structured, content clean"], ["tools.result_roundtrip", "PASS", "429ms", "final answer uses the tool result"], ["tools.multi_result", "PASS", "729ms", "both results reflected in the answer"], ["stream.tools", "PASS", "485ms", "get_weather({\"city\": \"Paris\", \"unit\": \"…"], ["stream.tools_parallel", "PASS", "1.6s", "2 calls assembled with distinct indexes"], ["json.mode", "PASS", "245ms", "valid JSON object with keys ['age', 'na…"], ["json.schema", "PASS", "1.4s", "output validates against the strict sch…"], ["reasoning.field", "SKIP", "5.6s", "no reasoning returned (normal for non-r…"], ["errors.bad_model", "WARN", "127ms", "unknown model accepted with 200 (server…"], ["errors.bad_request", "WARN", "114ms", "invalid message role accepted with 200"], ["errors.bad_auth", "SKIP", "-", "no API key configured"], ["anthropic.basic", "PASS", "45ms", "stop_reason=end_turn, 3 output tokens"], ["anthropic.stream", "PASS", "499ms", "34 deltas, full event sequence"], ["anthropic.tools", "PASS", "519ms", "tool_use get_weather {'city': 'Paris'},…"], ["anthropic.tool_result", "PASS", "548ms", "answer uses the tool_result"], ["perf.ttft", "PASS", "917ms", "p50 22 ms (min 19, max 50, n=3)"], ["perf.throughput", "PASS", "4.2s", "62.4 tok/s (256 tokens via usage, 4.2s …"]];

const CMD = "toolsmoke --base-url http://localhost:8080/v1 --model qwen --anthropic";
const body = document.getElementById("term-body");
const esc = s => s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const pad = (s,n) => s + " ".repeat(Math.max(0,n-s.length));
const lpad = (s,n) => " ".repeat(Math.max(0,n-s.length)) + s;
let timer = null, run = 0;
const sleep = ms => new Promise(r => { timer = setTimeout(r, ms); });
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function rowHTML(r){
  const [id, st, t, d] = r;
  const cls = {PASS:"t-pass",FAIL:"t-fail",WARN:"t-warn",SKIP:"t-skip"}[st];
  const det = st === "FAIL" ? `<span style="color:#fca5a5">${esc(d)}</span>` : (st==="SKIP"?`<span class="t-dim">${esc(d)}</span>`:esc(d));
  return `  ${pad(id,22)} <span class="${cls}">${pad(st,4)}</span> <span class="t-dim">${lpad(t,6)}</span>  ${det}\n`;
}
function footer(){
  return `\n  <span class="t-head">TTFT p50</span> <b>22 ms</b> <span class="t-dim">·</span> <b>62.4 tok/s</b> <span class="t-dim">·</span> <span class="t-pass">24 pass</span> <span class="t-dim">·</span> <span class="t-warn">2 warn</span> <span class="t-dim">·</span> <span class="t-fail">3 fail</span> <span class="t-dim">·</span> <span class="t-skip">2 skip</span>\n  <span class="t-bad">NOT AGENT-READY: 3 failing probes</span>\n\n<span class="t-prompt">$</span> <span class="t-dim">echo $?</span>\n1\n<span class="t-prompt">$</span> <span class="cursor"></span>`;
}
async function play(){
  const me = ++run; clearTimeout(timer);
  let html = `<span class="t-prompt">$</span> `;
  body.innerHTML = html + `<span class="cursor"></span>`;
  if (!reduced) {
    await sleep(500);
    for (let i = 1; i <= CMD.length; i++) {
      if (me !== run) return;
      body.innerHTML = html + `<span class="t-cmd">${esc(CMD.slice(0,i))}</span><span class="cursor"></span>`;
      await sleep(18 + Math.random()*30);
    }
    await sleep(350);
  }
  html += `<span class="t-cmd">${esc(CMD)}</span>\n<span class="t-dim">toolsmoke 0.1.0 · http://localhost:8080/v1 · model qwen</span>\n\n  <span class="t-head">${pad("PROBE",22)} RESULT   TIME  DETAIL</span>\n`;
  for (const r of ROWS) {
    if (me !== run) return;
    html += rowHTML(r);
    body.innerHTML = html + `<span class="cursor"></span>`;
    body.scrollTop = body.scrollHeight;
    if (!reduced) await sleep(r[1]==="FAIL" ? 420 : 110 + Math.random()*90);
  }
  body.innerHTML = html + footer();
  body.scrollTop = body.scrollHeight;
}
document.getElementById("replay").addEventListener("click", play);
const io = new IntersectionObserver(es => { if (es[0].isIntersecting) { play(); io.disconnect(); } });
io.observe(document.getElementById("terminal"));

document.querySelectorAll(".tab").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === b));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + b.dataset.tab));
}));
document.querySelectorAll(".copy").forEach(b => b.addEventListener("click", async () => {
  const text = b.parentElement.querySelector("code").innerText;
  try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; } catch { b.textContent = "Select & copy"; }
  setTimeout(() => (b.textContent = "Copy"), 1500);
}));
