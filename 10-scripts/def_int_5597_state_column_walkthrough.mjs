// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-INT-5597 — the State column on CON-01 showed an API's state
//          instead of the CONNECTOR's, on any connector with exactly one API.
//          PO, 2026-09-17: *"Here in Table - State - it should be for
//          conenctor not for APis - you are showing the wrong status"*, and
//          *"Connector status is with respect ot partner and that tenant - so
//          it will be tenant /utility speicific"*.
// Screens: S8 · CON-01, at `/:tenant/settings/integrations`.
// Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//          output) · law 7 habit 3 (the OUTPUT must distinguish pass from fail
//          to a READER) · BR-INT-028 as narrowed 2026-09-16.
// ───────────────────────────────────────────────────────
/**
 * Read the State column off the LIVE DOM and put it beside the two facts it
 * could be describing — the CONNECTION's own status and the single API's
 * state — for every row, and name every row where they part.
 *
 *     BASE=http://127.0.0.1:5200 node 10-scripts/def_int_5597_state_column_walkthrough.mjs
 *
 * ⚠ **WHAT WOULD MAKE THIS WALK PASS WRONGLY, AND WHAT IS DONE ABOUT IT:**
 *
 *  * **On 26 of the 28 connectors the two candidate facts AGREE**, so a walk
 *    that merely checked "does the column show the connection's status" would
 *    score a pass on a broken build. It therefore prints the DISAGREEING ROWS
 *    AS A COUNT and names them; a run finding zero disagreeing rows *and* zero
 *    rows where the two facts differ at all has proved NOTHING, and says so.
 *  * **The State cell is English and the API is an enum.** Comparing them
 *    needs a mapping, and a mapping written here would drift from the
 *    catalogue. So the cell's `data-state-is` attribute is read — it carries
 *    the raw `display_state` the component was handed — and the visible words
 *    are printed BESIDE it so a reader can see the two agree.
 *  * **A walk against the wrong bundle is a proof of a different product.**
 *    The served connector count and the JS bundle hash are printed first.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:5200";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/def_int_5597";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
await fs.mkdir(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();

const html = await (await fetch(`${BASE}/${TENANT}/settings/integrations`)).text();
const bundle = (/assets\/(index-[^"]+\.js)/.exec(html) ?? [])[1] ?? "UNKNOWN";
console.log(`STACK: ${BASE} · bundle ${bundle}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 20000 });

const api = await page.evaluate(async (tenant) => {
  const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
  if (!r.ok) return { error: `HTTP ${r.status}` };
  const body = await r.json();
  return {
    rows: (body.providers ?? []).map((p) => ({
      key: p.key,
      name: p.display_name,
      ops: (p.operations ?? []).length,
      opStates: (p.operations ?? []).map((o) => o.state),
      connStatus: p.connection ? p.connection.status : null,
      lastTestAt: p.connection ? p.connection.last_test_at : null,
      displayState: p.display_state,
    })),
  };
}, TENANT);
if (api.error) { console.log(`API: ${api.error}`); process.exit(1); }
console.log(`STACK: the API serves ${api.rows.length} connectors`);

await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForSelector("table tbody tr", { timeout: 15000 });
const screen = await page.evaluate(() =>
  [...document.querySelectorAll("table tbody tr")].map((tr) => ({
    key: tr.querySelector("[data-provider]")?.getAttribute("data-provider") ?? "?",
    stateWords: (tr.querySelector('[data-cell="state"]')?.textContent ?? "").trim(),
    stateRaw: tr.querySelector('[data-cell="state"]')?.getAttribute("data-state-is") ?? "?",
    apis: (tr.querySelector('[data-cell="apis"]')?.textContent ?? "").trim(),
    actionsLive: [...(tr.querySelector("[data-row-actions]")?.querySelectorAll("a") ?? [])]
      .map((a) => a.getAttribute("aria-label")),
  })),
);
await page.screenshot({ path: `${OUT}/con01-table.png`, fullPage: true });

const byKey = new Map(api.rows.map((r) => [r.key, r]));

// ── THE MEASUREMENT ────────────────────────────────────────────────────────
// Rows where the two candidate facts DIFFER AT ALL. Only these can tell a
// right build from a wrong one; everywhere else the question is unanswerable.
const decisive = screen.filter((s) => {
  const a = byKey.get(s.key);
  return a && a.connStatus !== null && a.ops === 1 && a.opStates[0] !== a.connStatus;
});
console.log(`\nDECISIVE ROWS (one API, and the API's state ≠ the connection's status): ${decisive.length}`);
if (decisive.length === 0) {
  console.log("  ⚠ NOTHING HERE CAN DISTINGUISH A RIGHT BUILD FROM A WRONG ONE.");
  console.log("    Seed a single-API connector whose run failed and which was never tested.");
}
console.log(
  `\n${"connector".padEnd(24)} ${"apis".padEnd(5)} ${"CONNECTION".padEnd(12)} ${"the API".padEnd(12)} ${"State cell".padEnd(12)} shown as`,
);
for (const s of decisive) {
  const a = byKey.get(s.key);
  const verdict = s.stateRaw === a.connStatus ? "✔ the CONNECTOR" : "✘ the API";
  console.log(
    `${a.name.padEnd(24)} ${String(a.ops).padEnd(5)} ${String(a.connStatus).padEnd(12)} ${a.opStates[0].padEnd(12)} ${s.stateRaw.padEnd(12)} "${s.stateWords}" · ${verdict} · APIs cell "${s.apis}"`,
  );
}

// ── EVERY ROW, so a regression in the 26 agreeing rows is visible too ──────
const wrong = screen.filter((s) => {
  const a = byKey.get(s.key);
  if (!a) return true;
  const expected = a.connStatus === null ? "not_set_up" : a.displayState;
  return s.stateRaw !== expected;
});
console.log(`\nALL ${screen.length} ROWS: cells disagreeing with the served display_state: ${wrong.length}`);

// ── THE ACTIONS MATRIX, before and after, on the decisive rows ─────────────
console.log("\nROW ACTIONS on the decisive rows (live = a real link):");
for (const s of decisive) console.log(`  ${s.key}: live ${JSON.stringify(s.actionsLive)}`);

const bad = decisive.filter((s) => s.stateRaw !== byKey.get(s.key).connStatus);
console.log(
  `\nVERDICT: ${bad.length} of ${decisive.length} decisive rows show the API instead of the connector.`,
);
console.log(bad.length === 0 && decisive.length > 0 ? "DEFECT NOT PRESENT" : "DEFECT PRESENT");
console.log(`screenshot: ${OUT}/con01-table.png`);
await browser.close();
