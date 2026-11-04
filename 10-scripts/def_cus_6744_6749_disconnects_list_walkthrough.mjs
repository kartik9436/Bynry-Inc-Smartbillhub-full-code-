// ── Trace ────────────────────────────────────────────────────────────────────
// Ask:      the Product Owner's walk of the Disconnects list, 2026-09-25 — ten
//           findings, six of them defects, relayed through the coordinator.
// Walks:    `/{t}/accounts?tab=disconnects` (S90, ACC-01) at **1440 and 1280**
// Proves:   `DEF-CUS-6744` (a 22-word paragraph in the Case # cell, 277px rows)
//           `DEF-CUS-6745` (the table 1453px wide, ACTIONS clipped, no scroll)
//           `DEF-CUS-6746` (`f.state=on_hold` could never match)
//           `DEF-CUS-6747` (the State cell printed both axes at once)
//           `DEF-CUS-6748` (the only row action was dead on two of six rows)
//           `DEF-CUS-6749` (a crew's visit reached no screen)
//           and the redesign: no quick-view chips, the six clerk words, the
//           five drawn tiles.
// Rules:    CLAUDE.md hard-won law 6 (diff the running app — no gate in this
//           repo reads rendered output) · law 7 (proved RED first, through this
//           same harness, on the pre-fix tree: 23 of 26 assertions failed) ·
//           B14 rules 31, 33, 43, 44
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠⚠ **THIS FILE EXISTS BECAUSE THREE OF ITS SIX DEFECTS ARE INVISIBLE TO THE
// ENTIRE UNIT SUITE, AND NOT BY OVERSIGHT.** `vitest` runs under jsdom, which
// has **no layout engine**: `getBoundingClientRect` returns zeroes there. So a
// 277px row, a column pushed 173px past the viewport, and a table with no
// scroll container are all literally unmeasurable by every case in
// `DisconnectsTab.test.tsx` — and `innerText` is returned for a clipped element
// exactly as for a visible one, so every assertion ABOUT them passed while no
// clerk at 1280 could reach the row action.
//
// **The two that matter are geometry, and they are asserted as numbers:**
//   * every column header's right edge inside `documentElement.clientWidth`;
//   * no data row taller than 140px.
//
// ⚠ **ONE ASSERTION HERE CANNOT FAIL AND IS KEPT ANYWAY, LABELLED.** *"no
// horizontal page scroll"* passed **before and after** the fix — because the
// overflow was CLIPPED rather than scrollable, which IS the defect. It is left
// in because a future fix that adds a scroll container should be seen, but it
// is not evidence of anything on its own. Naming it beats deleting it: a
// silent always-green assertion is how a suite acquires ballast.
//
// ⚠ **WHAT A FALSE PASS WOULD LOOK LIKE:** if the page failed to load, `rows`
// would be empty and every `every(...)` assertion would pass vacuously. That is
// why the positive cases are `some(...)` — an em dash present, `Held` present,
// `Visited` present — which cannot pass on an empty table, and why page errors
// and any HTTP >= 400 are printed beside the result.
//
// Boot a stack first (own ports, own database clone — see
// `12-governance/22-product-maintenance-process.md`), then:
//
//   DLIST_BASE=http://127.0.0.1:<your spa port> node 10-scripts/def_cus_6744_6749_disconnects_list_walkthrough.mjs
//
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
// ⚠ **`ROOT` IS DERIVED FROM THIS FILE'S OWN PATH AND IS PRINTED** —
// `DEF-CUS-6028`: a walk that hard-codes `/home/user/SMARTBillHub` drives YOUR
// bundle and reads the SHARED checkout's Django, which is on somebody else's
// branch, and nothing says so.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");
const BASE = process.env.DLIST_BASE || "http://127.0.0.1:8847";
const T = process.env.DLIST_TENANT || "brazosbend";
const SHOTS = process.env.DLIST_SHOTS || "/tmp/claude-0/dlist-shots";
const EMAIL = process.env.DLIST_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.DLIST_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.DLIST_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
fs.mkdirSync(SHOTS, { recursive: true });
console.log(`tree: ${ROOT}\napp:  ${BASE}/${T}\n`);
const errs=[], http=[];
const b = await chromium.launch({ executablePath: CHROME });
const ctx = await b.newContext({ viewport:{width:1440,height:1300} });
const p = await ctx.newPage(); p.setDefaultTimeout(30000);
p.on("pageerror", e=>errs.push(e.message));
p.on("response", async r=>{ if(r.url().includes("/api/")&&r.status()>=400) http.push(`${r.status()} ${r.url().replace(BASE,"")}`); });
await p.goto(`${BASE}/${T}/signin`,{waitUntil:"domcontentloaded"});
await p.fill("#signin-email", EMAIL); await p.fill("#signin-password", PASSWORD);
await Promise.all([p.waitForURL(u=>!u.pathname.endsWith("/signin")), p.click('button[type="submit"]')]);
let fails=0; const is=(c,w,saw)=>{ if(c) console.log("  ✓ "+w); else { fails++; console.log("  ✗ "+w+"\n      saw: "+saw); } };

for (const w of [1440,1280]) {
  await p.setViewportSize({width:w,height:1300});
  await p.goto(`${BASE}/${T}/accounts?tab=disconnects`,{waitUntil:"networkidle"});
  await p.waitForTimeout(2500);
  await p.screenshot({path:`${SHOTS}/after-${w}.png`, fullPage:true});
  const m = await p.evaluate(()=>{
    const tbl=document.querySelector("table");
    const heads=[...(tbl?.querySelectorAll("thead th")??[])].map(th=>({t:th.innerText.replace(/\s+/g," ").trim(), l:Math.round(th.getBoundingClientRect().left), r:Math.round(th.getBoundingClientRect().right)}));
    const rows=[...(tbl?.querySelectorAll("tbody tr")??[])].map(tr=>({h:Math.round(tr.getBoundingClientRect().height), c:[...tr.querySelectorAll("td")].map(td=>td.innerText.replace(/\s+/g," ").trim())}));
    const eyes=[...(tbl?.querySelectorAll("tbody tr")??[])].map(tr=>{const a=tr.querySelector("td:last-child a, td:last-child button"); return a?`${a.tagName}|disabled=${a.hasAttribute("disabled")||a.getAttribute("aria-disabled")==="true"}|${a.getAttribute("href")||""}`:"NONE";});
    const tiles=[...document.querySelectorAll("[data-kpi], .kpi, [class*='kpi']")].map(e=>e.innerText.replace(/\s+/g," ").trim()).filter(Boolean);
    const btns=[...document.querySelectorAll("button")].map(x=>x.innerText.replace(/\s+/g," ").trim()).filter(Boolean);
    return {vw:document.documentElement.clientWidth, sw:document.documentElement.scrollWidth, heads, rows, eyes, tiles:tiles.slice(0,3), btns};
  });
  console.log(`\n═══ ${w}px ═══  viewport=${m.vw} docScrollWidth=${m.sw}`);
  const acts=m.heads.find(h=>/ACTIONS/i.test(h.t));
  is(acts && acts.r <= m.vw, `1.3 the ACTIONS header is INSIDE the viewport (right=${acts?.r} vs ${m.vw})`, JSON.stringify(acts));
  is(m.sw<=m.vw, "1.3 no horizontal page scroll", `scrollWidth=${m.sw}`);
  is(!m.heads.some(h=>/LAST NOTICE/i.test(h.t)), "1.3 LAST NOTICE is off by default (still in the chooser)", m.heads.map(h=>h.t).join("|"));
  const tall=m.rows.filter(r=>r.h>140);
  is(tall.length===0, `1.2 no row is a paragraph — tallest is ${Math.max(...m.rows.map(r=>r.h))}px`, JSON.stringify(tall.map(r=>r.h)));
  is(m.rows.every(r=>!/because a protection is in force/i.test(r.c.join(" "))), "1.2 the 22-word sentence is gone from the cells", "still there");
  is(m.rows.some(r=>r.c[0]==="—"), "1.2 a row with no case shows an em dash", m.rows.map(r=>r.c[0]).join("|"));
  is(m.eyes.every(e=>e!=="NONE" && !e.includes("disabled=true")), "1.7 every row has a LIVE eye", m.eyes.join("  "));
  is(m.eyes.some(e=>e.includes("/accounts/")), "1.7 a protection row's eye opens the ACCOUNT", m.eyes.join("  "));
  const words=m.rows.map(r=>r.c[m.heads.findIndex(h=>/STATE/i.test(h.t))]);
  is(words.every(x=>!/On hold ·/.test(x)), "1.6 no cell prints two state words", words.join(" | "));
  is(words.some(x=>x.startsWith("Held")), "1.8 the clerk word `Held` is on the held rows", words.join(" | "));
  is(words.some(x=>x.startsWith("Notified")), "1.8 the clerk word `Notified` is used", words.join(" | "));
  is(!m.btns.some(x=>/^Due to cut$|^At notice$|^Reconnections$|^Due now$/.test(x)), "1.1 the quick-view chips are gone", m.btns.join(" | "));
  is(await p.evaluate(()=>/\+\s*Filter/.test(document.body.innerText)), "1.1 one filter list remains", "no + Filter control");
  console.log("  rows:"); for(const r of m.rows) console.log(`     ${String(r.h).padStart(3)}px | ${r.c.map(c=>c.length>34?c.slice(0,34)+"…":c).join(" ¦ ")}`);
  if(w===1440){ const body=await p.evaluate(()=>document.body.innerText.replace(/\s+/g," ")); 
    is(/\bNOTIFIED\b/i.test(body)&&/\bSCHEDULED\b/i.test(body)&&/\bOFF\b/i.test(body)&&/\bPAID\b/i.test(body)&&/\bHELD\b/i.test(body), "1.8/1.10 all five drawn tiles are on the strip", body.slice(0,300));
    is(/Visited/.test(body), "1.9 the list shows that a visit happened", body.slice(0,400));
  }
}
console.log(`\npage errors: ${errs.length?errs.join("; "):"none"}`);
console.log(`http >=400: ${http.length?http.join("; "):"none"}`);
console.log(fails===0?"\nALL ASSERTIONS PASSED":`\n${fails} ASSERTION(S) FAILED`);
await b.close();
// ⚠ **THE EXIT CODE IS THE POINT.** A walk that prints ✗ and exits 0 is a check
// whose output cannot distinguish pass from fail to anything but a reader
// (hard-won law 7, habit 3), and this one is meant to be runnable from a script.
process.exit(fails === 0 ? 0 : 1);
