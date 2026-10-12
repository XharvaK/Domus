"""E3: the overlay page, one template for every layout (main 16:9, vertical 9:16, curtain, work).
It polls /state.json once a second and writes text only through textContent, never as markup.
When the state says curtain or off, every layout shows the curtain over everything.
Look: the Lararium palette, her thoughts in a monospace face, and the Domus house and wordmark as inline
vectors on the curtain and work scenes. No web fonts, so the page works offline."""

PAGE = r"""<!doctype html>
<html lang="en" data-layout="__LAYOUT__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Domus overlay</title>
<style>
:root {
  --ink: #fcefdd; --dim: #cdbba8; --faint: #8f7c6e;
  --cap: #f4b3aa; --leaf: #9ccfae; --stone: #9c968d; --coal: #2b201c; --panel: rgba(43, 32, 28, 0.88);
  --low: #e3a066; --distress: #e0705f; --line: rgba(244, 179, 170, 0.26);
  --mono: ui-monospace, "Cascadia Mono", "Cascadia Code", Consolas, "Courier New", monospace;
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

.card { display: flex; align-items: center; gap: 0.75rem; font-size: 1.05rem; color: var(--dim);
  letter-spacing: 0.02em; }
.card .glyph { width: 1.5rem; height: 1.5rem; flex: none; }
.card .day { color: var(--ink); font-size: 1.35rem; font-style: italic; font-weight: 600; }
.card .ai { margin-left: auto; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--faint); border: 1px solid var(--faint); border-radius: 0.3rem; padding: 0.1rem 0.45rem; }
#human, #privacy { border: 1px solid var(--ink); border-radius: 0.4rem; padding: 0.45rem 0.75rem; font-size: 0.95rem;
  text-align: center; animation: breathe 2.4s ease-in-out infinite; }
@keyframes breathe { 50% { border-color: var(--faint); color: var(--dim); } }

h2 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.16em; color: var(--faint);
  font-weight: 600; margin-bottom: 0.45rem; }
#doing li { list-style: none; display: flex; align-items: center; gap: 0.6rem; font-size: 1.05rem;
  padding: 0.2rem 0; }
#doing li.queued { color: var(--dim); }
.by { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; border-radius: 0.25rem;
  padding: 0.12rem 0.4rem; white-space: nowrap; }
.by.her { background: var(--cap); color: var(--coal); }
.by.body { background: var(--leaf); color: var(--coal); }
.by.game { background: var(--stone); color: var(--coal); }
.by.human { border: 1px solid var(--ink); }

#thoughts { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; gap: 0.9rem;
  overflow: hidden; mask-image: linear-gradient(to bottom, transparent 0, #000 18%); }
.pass { border-left: 2px solid var(--line); padding-left: 0.85rem; opacity: 0.62; }
.pass:last-child { border-left-color: var(--cap); opacity: 1; animation: land 0.9s ease-out; }
@keyframes land { from { transform: translateY(0.8rem); opacity: 0; } }
.pass .line { font-family: var(--mono); font-size: 1.12rem; line-height: 1.5; }
.pass .quiet, .pass .held { font-family: var(--mono); color: var(--faint); font-size: 0.95rem; }
.pass .act, .pass .step { font-size: 0.92rem; color: var(--dim); margin-top: 0.3rem; }
.pass .act b { color: var(--cap); font-weight: 600; }
.pass .state { color: var(--faint); }

.needs { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.7rem 1.4rem; align-content: center; }
#needs-v { display: none; }
.need { font-size: 0.85rem; color: var(--dim); }
.need .track { height: 0.55rem; border-radius: 0.3rem; background: rgba(252, 239, 221, 0.12); margin-top: 0.25rem;
  overflow: hidden; }
.need .fill { height: 100%; border-radius: 0.3rem; background: var(--leaf); transition: width 1.2s ease; }
.need.low .fill { background: var(--low); }
.need.distress .fill { background: var(--distress); }
.feel { display: flex; flex-direction: column; justify-content: center; gap: 0.5rem; }
#mood { font-size: 1.6rem; font-style: italic; font-weight: 600; color: var(--cap); }
#clock { font-size: 1rem; color: var(--dim); }
#moodlets { display: flex; flex-wrap: wrap; gap: 0.4rem; }
#moodlets span { font-size: 0.8rem; border: 1px solid var(--line); border-radius: 1rem; padding: 0.15rem 0.6rem;
  color: var(--dim); }

/* curtain and work: opaque, over everything. The house stands big and cropped on the right, the words on the left. */
.scene { position: absolute; inset: 0; background: var(--coal); overflow: hidden; }
.scene .house { position: absolute; height: 118vh; right: -24vw; bottom: -30vh; }
.scene .house .window { animation: glow 4.5s ease-in-out infinite; }
@keyframes glow { 50% { opacity: 0.78; } }
.scene .copy { position: absolute; left: 7vw; top: 50%; transform: translateY(-50%); max-width: 46vw;
  display: flex; flex-direction: column; align-items: flex-start; gap: 2.2rem; }
.scene .wordmark { width: 30vw; height: auto; fill: var(--ink); }
.scene .title { font-size: 2.8rem; font-style: italic; font-weight: 600; color: var(--cap); letter-spacing: 0.01em; }
.scene .sub { color: var(--dim); font-size: 1.3rem; font-family: var(--mono); line-height: 1.5; }
.scene .card { font-size: 1.2rem; }
html[data-layout="vertical"] .scene .house { height: 52vh; right: -30vw; bottom: -12vh; }
html[data-layout="vertical"] .scene .copy { top: 12vh; transform: none; max-width: 86vw; }
html[data-layout="vertical"] .scene .wordmark { width: 70vw; }
</style>
</head>
<body>
<section id="live">
  <aside id="panel">
    <div class="card"><svg class="glyph" viewBox="0 0 1820 1890" aria-hidden="true"><path d="M420 490L1400 0L1820 420L840 910Z" fill="#625d56"/><path d="M840 910L1820 420L1820 1400L840 1890Z" fill="#9c968d"/><path d="M0 1890L0 910L420 490L840 910L840 1890Z" fill="#f5f3ee"/><path class="window" d="M420 735L595 910L420 1085L245 910Z" fill="#f4b3aa"/></svg><span class="day" data-day></span><span data-time></span><span class="ai">AI-controlled</span></div>
    <div id="human" class="hidden">Human at the controls</div>
    <div id="privacy" class="hidden">The privacy list is missing: names and places are not held from this screen.</div>
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
  <svg class="house" viewBox="0 0 1820 1890" aria-hidden="true"><path d="M420 490L1400 0L1820 420L840 910Z" fill="#625d56"/><path d="M840 910L1820 420L1820 1400L840 1890Z" fill="#9c968d"/><path d="M0 1890L0 910L420 490L840 910L840 1890Z" fill="#f5f3ee"/><path class="window" d="M420 735L595 910L420 1085L245 910Z" fill="#f4b3aa"/></svg>
  <div class="copy">
    <svg class="wordmark" viewBox="165 470 710 138" role="img" aria-label="Lararium"><path d="M193.9 602Q182.9 602 176.4 597.1Q170 592.2 170 580.7Q170 578.8 170.2 577Q170.3 575.2 170.5 573.4L185.8 477H206.8L192 570.7Q191.9 571.7 191.8 572.5Q191.7 573.4 191.7 574.4Q191.7 579.5 194.6 581.3Q197.6 583.2 202.5 583.2H243.7L240.8 602ZM282.8 603Q275.9 603 270.1 599.8Q264.4 596.6 260.9 589.7Q257.4 582.9 257.4 572Q257.4 567.3 258.1 562.2Q258.8 557.1 259.3 553.6Q261.6 538.8 267.2 529.2Q272.8 519.7 282.6 514.9Q292.3 510.2 306.9 510.2Q314 510.2 321 511.5Q328 512.7 334 515.1Q339.9 517.5 344 520.7L331.1 602H312.6L311.6 592.7Q309.2 594.5 304.5 597Q299.8 599.5 294.1 601.2Q288.4 603 282.8 603ZM292.6 586.1Q299.1 586.1 304.2 583.8Q309.2 581.5 313.7 579L321.3 530.7Q319.4 529.7 315.3 528.4Q311.3 527.1 305.9 527.1Q297.6 527.1 292.4 530.3Q287.2 533.6 284.3 539.7Q281.3 545.9 279.8 555.2Q279.1 559.3 278.8 562.7Q278.4 566.1 278.4 568.3Q278.4 576.4 282.1 581.2Q285.7 586.1 292.6 586.1ZM350.7 602 365.1 511.2H383.6L384.3 522.7Q389.4 517.8 395.8 514Q402.2 510.2 410.2 510.2Q413.3 510.2 415.6 510.4Q418 510.7 420 511.4L417 532.2Q414.4 532 411.6 531.9Q408.9 531.7 405.8 531.7Q398.2 531.7 392.1 534.1Q386 536.4 381.7 539.5L371.8 602ZM445.3 603Q438.3 603 432.6 599.8Q426.8 596.6 423.3 589.7Q419.9 582.9 419.9 572Q419.9 567.3 420.5 562.2Q421.2 557.1 421.7 553.6Q424.1 538.8 429.7 529.2Q435.3 519.7 445 514.9Q454.8 510.2 469.3 510.2Q476.4 510.2 483.5 511.5Q490.5 512.7 496.4 515.1Q502.4 517.5 506.4 520.7L493.6 602H475.1L474.1 592.7Q471.7 594.5 467 597Q462.2 599.5 456.5 601.2Q450.9 603 445.3 603ZM455.1 586.1Q461.5 586.1 466.6 583.8Q471.7 581.5 476.1 579L483.7 530.7Q481.9 529.7 477.8 528.4Q473.7 527.1 468.3 527.1Q460 527.1 454.8 530.3Q449.7 533.6 446.7 539.7Q443.7 545.9 442.2 555.2Q441.5 559.3 441.2 562.7Q440.9 566.1 440.9 568.3Q440.9 576.4 444.5 581.2Q448.2 586.1 455.1 586.1ZM513.2 602 527.6 511.2H546.1L546.7 522.7Q551.8 517.8 558.3 514Q564.7 510.2 572.7 510.2Q575.7 510.2 578.1 510.4Q580.5 510.7 582.5 511.4L579.4 532.2Q576.9 532 574.1 531.9Q571.3 531.7 568.3 531.7Q560.6 531.7 554.5 534.1Q548.4 536.4 544.2 539.5L534.2 602ZM602.1 496.8Q600.8 496.8 599.9 496Q599.1 495.1 599.4 493.8L601.8 478.3Q602.5 475 605.5 475H621.4Q623 475 623.6 476Q624.2 477 623.8 478.3L621.4 493.8Q620.9 496.8 618.1 496.8ZM582.8 602 597.1 511.2H618.1L603.8 602ZM649.9 603Q638.2 603 632.7 597.3Q627.2 591.7 627.2 581.7Q627.2 578.5 627.5 576Q627.7 573.5 628.1 571.3L637.5 511.2H658.5L649.6 569Q649.4 570 649.3 571Q649.2 572 649.2 573.4Q649.2 579 652.4 581.6Q655.7 584.2 661.8 584.2Q668.9 584.2 674.5 582Q680.1 579.8 685.7 576.1L696 511.2H717L702.6 602H684.1L683.1 592.5Q678.2 595.7 673.4 598.1Q668.5 600.5 663 601.7Q657.4 603 649.9 603ZM722.6 602 736.8 511.2H754.1L756.3 520.7Q763.1 516.3 771.1 513.2Q779.2 510 789.5 510Q798.1 510 803.3 513.3Q808.5 516.6 811.5 523.6Q819.3 516.6 828.7 513.3Q838.1 510 846.4 510Q859.1 510 864.8 515.7Q870.5 521.4 870.5 531.9Q870.5 534.9 870.2 538.1Q870 541.2 869.4 544.1L860.3 602H839.3L848.4 544.6Q848.6 543.6 848.7 542.5Q848.8 541.5 848.8 540.5Q848.8 528.8 835.7 528.8Q829 528.8 823.1 531.3Q817.3 533.7 811.3 537.8Q811.5 539.3 811.4 541.3Q811.3 543.2 810.8 545.6L801.9 602H781L789.8 545.4Q790.2 543.7 790.3 542.7Q790.3 541.7 790.3 540.3Q790.3 534.7 787.3 531.8Q784.2 528.8 777.5 528.8Q770.2 528.8 764.8 531.2Q759.5 533.6 753.9 537.1L743.6 602Z"/></svg>
    <div class="title">At work</div>
    <div class="sub" data-work></div>
    <div class="card"><span class="day" data-day></span><span data-time></span><span class="ai">AI-controlled</span></div>
  </div>
</section>
<section id="curtain" class="scene hidden">
  <svg class="house" viewBox="0 0 1820 1890" aria-hidden="true"><path d="M420 490L1400 0L1820 420L840 910Z" fill="#625d56"/><path d="M840 910L1820 420L1820 1400L840 1890Z" fill="#9c968d"/><path d="M0 1890L0 910L420 490L840 910L840 1890Z" fill="#f5f3ee"/><path class="window" d="M420 735L595 910L420 1085L245 910Z" fill="#f4b3aa"/></svg>
  <div class="copy">
    <svg class="wordmark" viewBox="165 470 710 138" role="img" aria-label="Lararium"><path d="M193.9 602Q182.9 602 176.4 597.1Q170 592.2 170 580.7Q170 578.8 170.2 577Q170.3 575.2 170.5 573.4L185.8 477H206.8L192 570.7Q191.9 571.7 191.8 572.5Q191.7 573.4 191.7 574.4Q191.7 579.5 194.6 581.3Q197.6 583.2 202.5 583.2H243.7L240.8 602ZM282.8 603Q275.9 603 270.1 599.8Q264.4 596.6 260.9 589.7Q257.4 582.9 257.4 572Q257.4 567.3 258.1 562.2Q258.8 557.1 259.3 553.6Q261.6 538.8 267.2 529.2Q272.8 519.7 282.6 514.9Q292.3 510.2 306.9 510.2Q314 510.2 321 511.5Q328 512.7 334 515.1Q339.9 517.5 344 520.7L331.1 602H312.6L311.6 592.7Q309.2 594.5 304.5 597Q299.8 599.5 294.1 601.2Q288.4 603 282.8 603ZM292.6 586.1Q299.1 586.1 304.2 583.8Q309.2 581.5 313.7 579L321.3 530.7Q319.4 529.7 315.3 528.4Q311.3 527.1 305.9 527.1Q297.6 527.1 292.4 530.3Q287.2 533.6 284.3 539.7Q281.3 545.9 279.8 555.2Q279.1 559.3 278.8 562.7Q278.4 566.1 278.4 568.3Q278.4 576.4 282.1 581.2Q285.7 586.1 292.6 586.1ZM350.7 602 365.1 511.2H383.6L384.3 522.7Q389.4 517.8 395.8 514Q402.2 510.2 410.2 510.2Q413.3 510.2 415.6 510.4Q418 510.7 420 511.4L417 532.2Q414.4 532 411.6 531.9Q408.9 531.7 405.8 531.7Q398.2 531.7 392.1 534.1Q386 536.4 381.7 539.5L371.8 602ZM445.3 603Q438.3 603 432.6 599.8Q426.8 596.6 423.3 589.7Q419.9 582.9 419.9 572Q419.9 567.3 420.5 562.2Q421.2 557.1 421.7 553.6Q424.1 538.8 429.7 529.2Q435.3 519.7 445 514.9Q454.8 510.2 469.3 510.2Q476.4 510.2 483.5 511.5Q490.5 512.7 496.4 515.1Q502.4 517.5 506.4 520.7L493.6 602H475.1L474.1 592.7Q471.7 594.5 467 597Q462.2 599.5 456.5 601.2Q450.9 603 445.3 603ZM455.1 586.1Q461.5 586.1 466.6 583.8Q471.7 581.5 476.1 579L483.7 530.7Q481.9 529.7 477.8 528.4Q473.7 527.1 468.3 527.1Q460 527.1 454.8 530.3Q449.7 533.6 446.7 539.7Q443.7 545.9 442.2 555.2Q441.5 559.3 441.2 562.7Q440.9 566.1 440.9 568.3Q440.9 576.4 444.5 581.2Q448.2 586.1 455.1 586.1ZM513.2 602 527.6 511.2H546.1L546.7 522.7Q551.8 517.8 558.3 514Q564.7 510.2 572.7 510.2Q575.7 510.2 578.1 510.4Q580.5 510.7 582.5 511.4L579.4 532.2Q576.9 532 574.1 531.9Q571.3 531.7 568.3 531.7Q560.6 531.7 554.5 534.1Q548.4 536.4 544.2 539.5L534.2 602ZM602.1 496.8Q600.8 496.8 599.9 496Q599.1 495.1 599.4 493.8L601.8 478.3Q602.5 475 605.5 475H621.4Q623 475 623.6 476Q624.2 477 623.8 478.3L621.4 493.8Q620.9 496.8 618.1 496.8ZM582.8 602 597.1 511.2H618.1L603.8 602ZM649.9 603Q638.2 603 632.7 597.3Q627.2 591.7 627.2 581.7Q627.2 578.5 627.5 576Q627.7 573.5 628.1 571.3L637.5 511.2H658.5L649.6 569Q649.4 570 649.3 571Q649.2 572 649.2 573.4Q649.2 579 652.4 581.6Q655.7 584.2 661.8 584.2Q668.9 584.2 674.5 582Q680.1 579.8 685.7 576.1L696 511.2H717L702.6 602H684.1L683.1 592.5Q678.2 595.7 673.4 598.1Q668.5 600.5 663 601.7Q657.4 603 649.9 603ZM722.6 602 736.8 511.2H754.1L756.3 520.7Q763.1 516.3 771.1 513.2Q779.2 510 789.5 510Q798.1 510 803.3 513.3Q808.5 516.6 811.5 523.6Q819.3 516.6 828.7 513.3Q838.1 510 846.4 510Q859.1 510 864.8 515.7Q870.5 521.4 870.5 531.9Q870.5 534.9 870.2 538.1Q870 541.2 869.4 544.1L860.3 602H839.3L848.4 544.6Q848.6 543.6 848.7 542.5Q848.8 541.5 848.8 540.5Q848.8 528.8 835.7 528.8Q829 528.8 823.1 531.3Q817.3 533.7 811.3 537.8Q811.5 539.3 811.4 541.3Q811.3 543.2 810.8 545.6L801.9 602H781L789.8 545.4Q790.2 543.7 790.3 542.7Q790.3 541.7 790.3 540.3Q790.3 534.7 787.3 531.8Q784.2 528.8 777.5 528.8Q770.2 528.8 764.8 531.2Q759.5 533.6 753.9 537.1L743.6 602Z"/></svg>
    <div class="title">Back soon</div>
    <div class="card"><span class="day" data-day></span><span class="ai">AI-controlled</span></div>
  </div>
</section>
<script>
const layout = document.documentElement.dataset.layout;
const STATES = { requested: "asked", received: "on its way", accepted: "on its way", pushed: "in Ashley's queue",
  finished: "done", rejected: "the game said no", expired: "never reached the game", unknown: "lost track",
  invalid: "not on the list", planned: "next", dropped: "let go" };
const BY = { her: "Ashley's choice", body: "Ashley's body", game: "the game", human: "human hand" };
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
  document.getElementById("privacy").classList.toggle("hidden", state.privacy_list !== "missing");
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
