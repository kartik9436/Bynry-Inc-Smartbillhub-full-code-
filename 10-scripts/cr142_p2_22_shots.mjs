// ── Trace ──────────────────────────────────────────────
// Story:   CR-142-BRC07 Phase 2 · P2.22 — the PAIR the Product Owner asked to
//          see: the refused total beside the SAME report ungrouped, where the
//          total is lawful, plus the exported CSV's footer row.
// Rules:   CLAUDE.md hard-won law 6 (*"diff the running app — no gate looks at
//          rendered output"*) · B14 rule 44 (staff app verified at 1280 AND
//          1440)
// ───────────────────────────────────────────────────────
//
// PHOTOGRAPH WHAT IS THERE. Nothing is dressed for the picture: no CSS is
// injected, no element is hidden, no value is substituted. Where a view cannot
// be captured the script SAYS SO in 00-README.txt rather than skipping it
// silently — an absence with no reason beside it is indistinguishable from a
// pass (law 7's fifth shape).
//
//   node 10-scripts/cr142_p2_22_shots.mjs
//
// Env: SMOKE_BASE (http://127.0.0.1:8080) · SMOKE_TENANT · SMOKE_EMAIL ·
//      SMOKE_PASSWORD · SHOT_OUT

import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

// ⚠ NO DEPENDENCY OF ITS OWN — it borrows `playwright-core` from the front
// end's install, exactly as `12-smoke-walkthrough.mjs` does. A bare
// `import "playwright"` resolves from THIS directory upward, and `10-scripts/`
// has no `node_modules`, so it fails with a module-not-found that reads like a
// missing install rather than a resolution root.
const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOT_OUT ?? "/tmp/p2-model-shots";
const EXE =
  process.env.PW_CHROME ??
  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const notes = [];
function note(line) {
  console.log(line);
  notes.push(line);
}

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 900 });
  await page.waitForTimeout(700);
  // ⚠ **SCROLL THE FOOTER INTO VIEW — IT IS THE SUBJECT OF THE PHOTOGRAPH.**
  // The first run of this script captured the top of the page at both widths
  // and the totals row was below the fold in every shot, so the pair showed
  // nothing of what it was taken to show. Nothing is hidden or restyled to
  // achieve this; the page is scrolled the way a clerk scrolls it.
  const footer = page.locator("tr.fin-total-row").first();
  if (await footer.count()) {
    await footer.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
  }
  const file = path.join(OUT, `${name}-${width}.png`);
  await page.screenshot({ path: file, fullPage: false });
  note(`  captured ${path.basename(file)}`);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  note(`base ${BASE} · tenant ${TENANT}`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  note(`signed in; landed on ${page.url()}`);

  // ── A · the SAME report, ungrouped — the total is lawful and is a number ──
  const ungrouped = `${BASE}/${TENANT}/reports/ar_aging`;
  await page.goto(ungrouped, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  for (const w of [1440, 1280]) await shot(page, "A-ungrouped-total-is-a-number", w);
  const ungroupedFooter = await page
    .locator("tr.fin-total-row")
    .first()
    .textContent()
    .catch(() => null);
  note(`  A footer text: ${JSON.stringify(ungroupedFooter)}`);

  // ── B · the same report grouped by month — the total refuses ──────────────
  const grouped = `${ungrouped}?group_by=accounting_period&from=2026-05-01&to=2026-07-31`;
  await page.goto(grouped, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  for (const w of [1440, 1280]) await shot(page, "B-grouped-total-refuses", w);
  const groupedFooter = await page
    .locator("tr.fin-total-row")
    .first()
    .textContent()
    .catch(() => null);
  note(`  B footer text: ${JSON.stringify(groupedFooter)}`);

  // ── C · what the API actually served, so the picture can be checked ───────
  for (const [label, url] of [
    ["ungrouped", `${BASE}/api/${TENANT}/reports/ar_aging`],
    [
      "grouped",
      `${BASE}/api/${TENANT}/reports/ar_aging?group_by=accounting_period&from=2026-05-01&to=2026-07-31`,
    ],
  ]) {
    const body = await page.evaluate(async (u) => {
      const r = await fetch(u, { credentials: "include" });
      return { status: r.status, text: (await r.text()).slice(0, 4000) };
    }, url);
    note(`  API ${label}: ${body.status}`);
    writeFileSync(path.join(OUT, `C-api-${label}.json`), body.text);
  }

  await browser.close();
  writeFileSync(path.join(OUT, "00-README.txt"), notes.join("\n") + "\n");
  note(`wrote ${OUT}/00-README.txt`);
}

main().catch((err) => {
  note(`FAILED: ${err.message}`);
  mkdirSync(OUT, { recursive: true });
  writeFileSync(path.join(OUT, "00-README.txt"), notes.join("\n") + "\n");
  process.exitCode = 1;
});
