"""E3: the overlay page, one template for every layout (main 16:9, vertical 9:16, curtain, work).
It polls /state.json once a second and writes text only through textContent, never as markup.
When the state says curtain or off, every layout shows the curtain over everything."""

PAGE = r"""<!doctype html>
<html lang="en" data-layout="__LAYOUT__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Domus overlay</title>
<style>
:root {
  --ink: #f3ede4; --dim: #b9ad9c; --faint: #7d7266;
  --amber: #e8a33d; --ember: #c96f2b; --coal: #16130f; --panel: rgba(22, 19, 15, 0.86);
  --body: #8fa3b8; --game: #8a8178; --line: rgba(232, 163, 61, 0.28);
  --serif: Georgia, "Times New Roman", serif;
  --sans: "Segoe UI", system-ui, -apple-system, sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: calc(100vw / 120); }
html[data-layout="vertical"] { font-size: calc(100vw / 67.5); }
body { background: transparent; color: var(--ink); font-family: var(--sans); overflow: hidden;
  width: 100vw; height: 100vh; }
.hidden { display: none !important; }

/* main 16:9: the game fills the left 70% (top), the panel the right 30%, the body bar below. */
#panel { position: absolute; background: var(--panel); display: flex; flex-direction: column;
  gap: 1rem; padding: 1.5rem 1.5rem 1.25rem; border-left: 1px solid var(--line); }
#bar { position: absolute; background: var(--panel); border-top: 1px solid var(--line);
  display: grid; grid-template-columns: 1.4fr 1fr; gap: 1.5rem; padding: 1.25rem 1.75rem; }
html[data-layout="main"] #panel { top: 0; right: 0; width: 30vw; height: 100vh; }
html[data-layout="main"] #bar { left: 0; bottom: 0; width: 70vw; height: calc(100vh - 70vw * 9 / 16); }
html[data-layout="vertical"] #panel { left: 0; bottom: 0; width: 100vw; height: 46vh; border-left: 0;
  border-top: 1px solid var(--line); }
html[data-layout="vertical"] #bar { display: none; }
html[data-layout="vertical"] #needs-v { display: grid; }

.card { display: flex; align-items: baseline; gap: 0.75rem; font-size: 1.05rem; color: var(--dim);
  letter-spacing: 0.02em; }
.card .day { font-family: var(--serif); color: var(--amber); font-size: 1.35rem; }
.card .ai { margin-left: auto; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--faint); border: 1px solid var(--faint); border-radius: 0.3rem; padding: 0.1rem 0.45rem; }
#human { border: 1px solid var(--ink); border-radius: 0.4rem; padding: 0.45rem 0.75rem; font-size: 0.95rem;
  text-align: center; animation: breathe 2.4s ease-in-out infinite; }
@keyframes breathe { 50% { border-color: var(--faint); color: var(--dim); } }

h2 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.16em; color: var(--faint);
  font-weight: 600; margin-bottom: 0.45rem; }
#doing li { list-style: none; display: flex; align-items: center; gap: 0.6rem; font-size: 1.05rem;
  padding: 0.2rem 0; }
#doing li.queued { color: var(--dim); }
.by { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; border-radius: 0.25rem;
  padding: 0.12rem 0.4rem; white-space: nowrap; }
.by.her { background: var(--amber); color: var(--coal); }
.by.body { background: var(--body); color: var(--coal); }
.by.game { background: var(--game); color: var(--coal); }
.by.human { border: 1px solid var(--ink); }

#thoughts { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; gap: 0.9rem;
  overflow: hidden; mask-image: linear-gradient(to bottom, transparent 0, #000 18%); }
.pass { border-left: 2px solid var(--line); padding-left: 0.85rem; opacity: 0.62; }
.pass:last-child { border-left-color: var(--amber); opacity: 1; animation: land 0.9s ease-out; }
@keyframes land { from { transform: translateY(0.8rem); opacity: 0; } }
.pass .line { font-family: var(--serif); font-size: 1.3rem; line-height: 1.4; }
.pass .quiet, .pass .held { color: var(--faint); font-style: italic; font-size: 1rem; }
.pass .act, .pass .step { font-size: 0.92rem; color: var(--dim); margin-top: 0.3rem; }
.pass .act b { color: var(--amber); font-weight: 600; }
.pass .state { color: var(--faint); }

.needs { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.7rem 1.4rem; align-content: center; }
#needs-v { display: none; }
.need { font-size: 0.85rem; color: var(--dim); }
.need .track { height: 0.55rem; border-radius: 0.3rem; background: rgba(243, 237, 228, 0.12); margin-top: 0.25rem;
  overflow: hidden; }
.need .fill { height: 100%; border-radius: 0.3rem; background: var(--amber); transition: width 1.2s ease; }
.need.low .fill { background: var(--ember); }
.need.distress .fill { background: #d4493a; }
.feel { display: flex; flex-direction: column; justify-content: center; gap: 0.5rem; }
#mood { font-family: var(--serif); font-size: 1.6rem; color: var(--amber); }
#clock { font-size: 1rem; color: var(--dim); }
#moodlets { display: flex; flex-wrap: wrap; gap: 0.4rem; }
#moodlets span { font-size: 0.8rem; border: 1px solid var(--line); border-radius: 1rem; padding: 0.15rem 0.6rem;
  color: var(--dim); }

/* curtain and work: opaque, over everything */
.scene { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 42%, #2a221a 0, var(--coal) 62%);
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2.2rem; }
.shrine { position: relative; width: 9rem; height: 12rem; border: 2px solid var(--amber); border-bottom-width: 3px;
  border-radius: 4.5rem 4.5rem 0.3rem 0.3rem; }
.flame { position: absolute; left: 50%; bottom: 1.6rem; width: 1.6rem; height: 2.6rem; margin-left: -0.8rem;
  background: radial-gradient(ellipse at 50% 70%, #ffd68a 0, var(--amber) 45%, var(--ember) 80%, transparent 82%);
  border-radius: 50% 50% 45% 45% / 62% 62% 38% 38%; filter: blur(0.3px); animation: flicker 2.8s ease-in-out infinite; }
.hearth { position: absolute; left: 22%; right: 22%; bottom: 1.2rem; height: 2px; background: var(--amber); opacity: 0.7; }
@keyframes flicker { 0%, 100% { transform: scale(1, 1); opacity: 0.95; } 30% { transform: scale(0.94, 1.06) translateX(1px); }
  60% { transform: scale(1.04, 0.96); opacity: 0.85; } }
.scene .title { font-family: var(--serif); font-size: 3rem; letter-spacing: 0.04em; }
.scene .sub { color: var(--dim); font-size: 1.3rem; text-align: center; max-width: 60vw; font-family: var(--serif); }
.scene .card { font-size: 1.2rem; }
</style>
</head>
<body>
<section id="live">
  <aside id="panel">
    <div class="card"><span class="day" data-day></span><span data-time></span><span class="ai">AI-controlled</span></div>
    <div id="human" class="hidden">Human at the controls</div>
    <div><h2>Now</h2><ul id="doing"></ul></div>
    <div id="thoughts"></div>
    <div id="needs-v" class="needs"></div>
  </aside>
  <footer id="bar">
    <div id="needs" class="needs"></div>
    <div class="feel"><div id="mood"></div><div id="moodlets"></div><div id="clock"></div></div>
  </footer>
</section>
<section id="work" class="scene hidden">
  <div class="shrine"><div class="flame"></div><div class="hearth"></div></div>
  <div class="title">At work</div>
  <div class="sub" data-work></div>
  <div class="card"><span class="day" data-day></span><span data-time></span><span class="ai">AI-controlled</span></div>
</section>
<section id="curtain" class="scene hidden">
  <div class="shrine"><div class="flame"></div><div class="hearth"></div></div>
  <div class="title">Back soon</div>
  <div class="card"><span class="day" data-day></span><span class="ai">AI-controlled</span></div>
</section>
<script>
const layout = document.documentElement.dataset.layout;
const STATES = { requested: "asked", received: "on its way", accepted: "on its way", pushed: "in her queue",
  finished: "done", rejected: "the game said no", expired: "never reached the game", unknown: "lost track",
  invalid: "not on the list", planned: "next", dropped: "let go" };
const BY = { her: "her choice", body: "her body", game: "the game", human: "human hand" };
const el = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text; return node; };
const word = (value) => String(value || "").toLowerCase().replace(/_/g, " ");
let lastKey = "";

function stateText(item) {
  let text = STATES[item.state] || word(item.state);
  if (item.state === "finished" && item.how && !["NATURAL", "ANSWERED"].includes(item.how)) text = "ended: " + word(item.how);
  if (item.state === "rejected" && item.how) text += " (" + word(item.how) + ")";
  return text;
}

function needs(target, list) {
  target.replaceChildren(...(list || []).map((need) => {
    const node = el("div", "need " + (need.band || ""));
    node.append(el("div", null, need.need.charAt(0).toUpperCase() + need.need.slice(1)));
    const track = el("div", "track"), fill = el("div", "fill");
    fill.style.width = Math.max(0, Math.min(100, Number(need.value) || 0)) + "%";
    track.append(fill); node.append(track); return node;
  }));
}

function render(state) {
  const mode = layout === "curtain" ? "curtain" : layout === "work" && state.mode === "live" ? "work" : state.mode;
  const scene = mode === "off" || mode === "curtain" ? "curtain" : mode === "work" ? "work" : "live";
  for (const id of ["live", "work", "curtain"]) document.getElementById(id).classList.toggle("hidden", id !== scene);
  const card = state.card || {};
  document.querySelectorAll("[data-day]").forEach((node) => { node.textContent = card.day ? "Day " + card.day : ""; });
  document.querySelectorAll("[data-time]").forEach((node) => { node.textContent = card.time || ""; });
  if (scene === "work") document.querySelector("[data-work]").textContent = (state.work && state.work.title) || "";
  if (scene !== "live") return;
  document.getElementById("human").classList.toggle("hidden", !state.human_at_controls);
  document.getElementById("doing").replaceChildren(...(state.doing || []).map((item) => {
    const li = el("li", item.queued ? "queued" : "");
    if (item.by) li.append(el("span", "by " + item.by, BY[item.by]));
    li.append(el("span", null, (item.queued ? "next: " : "") + item.text));
    return li;
  }));
  const passes = state.passes || [];
  const key = JSON.stringify(passes);
  if (key !== lastKey) {
    lastKey = key;
    document.getElementById("thoughts").replaceChildren(...passes.map((pass) => {
      const node = el("div", "pass");
      if (pass.line) node.append(el("div", "line", pass.line));
      else node.append(el("div", pass.held ? "held" : "quiet", pass.held ? "…" : "a quiet moment"));
      if (pass.act) {
        const act = el("div", "act"); act.append("→ ", el("b", null, pass.act.label), " ", el("span", "state", "· " + stateText(pass.act)));
        node.append(act);
      }
      for (const step of pass.plan || []) node.append(el("div", "step", "then " + step.label + " · " + stateText(step)));
      return node;
    }));
  }
  needs(document.getElementById("needs"), state.needs);
  needs(document.getElementById("needs-v"), state.needs);
  document.getElementById("mood").textContent = state.mood || "";
  document.getElementById("moodlets").replaceChildren(...(state.moodlets || []).map((item) => el("span", null, item.text)));
  document.getElementById("clock").textContent = (card.time || "") + (state.paused ? " · paused" : "");
}

async function tick() {
  try {
    const response = await fetch("/state.json", { cache: "no-store" });
    render(await response.json());
  } catch (error) {
    render({ mode: "curtain", card: {} });
  }
}
tick();
setInterval(tick, 1000);
</script>
</body>
</html>
"""
