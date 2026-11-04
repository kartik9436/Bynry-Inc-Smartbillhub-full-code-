/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-110-BRC04 wave B — the CONNECTION VIEW screen (S142 · INT-02) is
 *          the seven-column table the Integration Blueprint draws.
 * Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
 *          output) · law 7 (a check must be able to tell pass from fail to a
 *          READER) · B14 rule 42 (a screen is built from the drawing as an
 *          IMAGE) · BR-INT-028 (no aggregate word over several operations) ·
 *          PO rulings 2026-09-16 (the limit is display only · no clock box ·
 *          one key per connection and the word *token* leaves the product).
 * ───────────────────────────────────────────────────────
 *
 * WHAT IT WALKS, and why each check is here rather than in vitest.
 *
 *   FOUR ARCHETYPES, because one connector proves nothing about 28: one that
 *   holds a vendor's key (email_smtp), one with sixteen operations
 *   (meters_neptune360), one we issue a key to (payments_kiosk) and one drawn
 *   *coming soon* (sms_twilio).
 *
 *   THREE NEIGHBOURS, because a fix that breaks an adjacent screen is worse
 *   than the defect it fixed: the grid, S143 mappings (live and deliberately
 *   out of this CR's scope) and S144 machine keys.
 *
 * ⚠ **THE FIRST CHECK IS THAT THE SCREEN RENDERS AT ALL, AND IT IS THERE
 * BECAUSE THIS SCRIPT ONCE REPORTED *errors: none* OVER A CRASHED PAGE.** The
 * app's error boundary CATCHES the throw, so `pageerror` never fires and every
 * later assertion fails with a message about a missing column rather than the
 * one fact that mattered. A fixture that cannot tell a crashed screen from a
 * working one is law 7's *looking at the wrong thing*.
 *
 * ⚠ **AND IT IS WHAT CAUGHT AN EMPTY WAVE.** `git apply` is atomic; a
 * re-derivation onto the tip silently applied NOTHING, and tsc, eslint, 75
 * vitest cases and the build were all green over a screen that had reverted to
 * its shipped self. Only opening it in a browser showed it.
 *
 * RUN IT:
 *     (cd 07-frontend && ./node_modules/.bin/vite build)
 *     STATIC_DIR=$PWD/07-frontend/dist API_PROXY_TARGET=http://127.0.0.1:<api> \
 *       PORT=<port> node 07-frontend/server.mjs
 *     node 10-scripts/cr110_wave_b_connection_view_walkthrough.mjs
 *
 * ⚠ **CHECK THE SERVED BUNDLE IS YOURS.** The first run of this walkthrough
 * measured a SIBLING LANE'S app, because the port it assumed was free was not.
 * `curl -s <base>/ | grep -o 'assets/index-[^"]*\.js'` must name the file your
 * own build just wrote.
 */
import { createRequire } from "node:module";
const require = createRequire("file:///home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
const BASE="http://127.0.0.1:8298", T="brazosbend";
const OUT="/tmp/claude-0/-home-user-SMARTBillHub/d8cc0edb-6533-58a7-9b8e-548fbd3d8b79/scratchpad/after";
const b = await chromium.launch({ executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args:["--no-sandbox"] });
const p = await b.newPage({ viewport:{width:1440,height:1200} });
const errs=[]; p.on("pageerror",e=>errs.push(String(e).slice(0,160)));
p.on("response",r=>{ if(r.status()>=400 && r.url().includes("/api/")) errs.push(`${r.status()} ${r.url().split("/api/")[1]}`); });
await p.goto(`${BASE}/${T}/signin`,{waitUntil:"networkidle"});
await p.fill("#signin-email","dana@brazosbendutilities.com");
await p.fill("#signin-password","S3cure!passw0rd");
await p.click('button[type="submit"]'); await p.waitForTimeout(2500);
let fails=0; const say=(l,ok,d="")=>{ console.log(`${ok?"  OK":"  XX"} ${l}${d?" — "+d:""}`); if(!ok) fails++; };

console.log("\n== THE FOUR ARCHETYPES, captured at 1440 ==");
for (const [k,what] of [["email_smtp","holds a vendor key"],["meters_neptune360","16 operations"],["payments_kiosk","we issue the key"],["sms_twilio","drawn coming soon"]]){
  await p.goto(`${BASE}/${T}/settings/integrations/${k}`,{waitUntil:"networkidle"});
  await p.waitForTimeout(1500);
  await p.screenshot({path:`${OUT}/view-${k}.png`, fullPage:true});
  // ⚠ THE ERROR BOUNDARY SWALLOWS A CRASH, so `pageerror` stays EMPTY while the
  // page reads *Unexpected Application Error*. A fixture that cannot tell a
  // crashed screen from a working one is law 7's "looking at the wrong thing",
  // and this walkthrough had it until a page actually crashed.
  const crashed = (await p.locator("body").innerText()).includes("Unexpected Application Error");
  say(`${k}: the screen RENDERS (no error boundary)`, !crashed);
  const cols = await p.locator('[data-operations] thead th').allInnerTexts();
  const rows = await p.locator('[data-operations] tbody tr').count();
  say(`${k} (${what}): 7 drawn columns`, cols.length===7, cols.join(" | "));
  say(`${k}: ${rows} operation rows, each with its own state`, rows>0 && (await p.locator('[data-operation-state]').count())>=rows);
  say(`${k}: no aggregate word over the table (BR-INT-028)`, (await p.locator('[data-operations] thead [data-state]').count())===0);
  const body = await p.locator("body").innerText();
  say(`${k}: the word "token" appears nowhere (PO ruling)`, !/\btokens?\b/i.test(body));
  say(`${k}: no rate-limit input, no Save (display only)`, (await p.locator('[data-rate-limit] input, [data-rate-limit] button').count())===0);
  say(`${k}: no clock box / run time (scheduling is Runbooks')`, !/run time|next run|time zone/i.test(body));
}

console.log("\n== REGRESSION · the neighbours must still work ==");
for (const [path,marker,name] of [
  ["/settings/integrations","Custom SMTP","the connector grid"],
  ["/settings/integrations/bank_lockbox_file/mappings","", "S143 mappings (live, out of scope, must not break)"],
  // ⚠ `erp_sap` AND NOT `gl_partner`. The shared finance connector was SPLIT
  // into five named ERPs by wave A while this wave was being built, so a
  // walkthrough naming the old key goes red for a reason that is not a defect.
  // Any of the six `they_hold_ours` connectors serves — S144 is the screen for
  // a key WE issue.
  ["/settings/integrations/erp_sap/access","", "S144 machine keys / access log"],
]){
  await p.goto(`${BASE}/${T}${path}`,{waitUntil:"networkidle"});
  await p.waitForTimeout(1500);
  const body = await p.locator("body").innerText();
  say(name, !/went wrong|could not|Something broke|not built yet/i.test(body) && (marker===""||body.includes(marker)));
  await p.screenshot({path:`${OUT}/regress-${name.split(" ")[0].replace(/[^a-z0-9]/gi,"")}.png`, fullPage:true});
}
console.log("\nerrors:", errs.length? errs : "none");
console.log(fails? `\n${fails} CHECK(S) FAILED` : "\nall checks passed");
await b.close();
