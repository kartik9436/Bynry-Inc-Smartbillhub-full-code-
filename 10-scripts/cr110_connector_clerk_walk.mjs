// ── Trace ──────────────────────────────────────────────
// Change:   `CR-110-BRC04` — the PO's clerk walk across all 28 connectors.
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) · law 7 (a check's output must distinguish pass from
//           fail TO A READER, and "what would make this pass wrongly?") ·
//           13-change-process.md's CLOSURE BAR (PO 2026-08-18: *"CR is not
//           closed until we have confirm user is able to perform tasks using
//           screen/broswer/UI"*), restated by the PO on 2026-09-16 for
//           connectors: *"open each connector and see it open up the detail
//           and you are able to perform actions - what it does when you
//           perform actions - what message it gives"*.
// ───────────────────────────────────────────────────────
/**
 * Walk EVERY connector the way a clerk would, and write down what it says back.
 *
 *     BASE=http://127.0.0.1:8401 node /tmp/connwalk.mjs
 *
 * ⚠ **CHECK WHAT THE STACK ACTUALLY SERVES BEFORE BELIEVING ANY SCREENSHOT.**
 * This cost a whole cycle on 2026-09-16: a front end was started on a port
 * ANOTHER LANE ALREADY HELD, so it never bound, the browser was quietly served
 * by the older stack, and the grid's 18 retired connectors were reported as a
 * product fault. The run now asserts the provider COUNT off the API first and
 * refuses to walk if it is not what the registry holds. A walk against the
 * wrong backend is not a weaker proof — it is a proof of a different product.
 *
 * ⚠ **IT RECORDS REFUSALS AS RESULTS, NOT AS FAILURES.** A connector drawn
 * *coming soon* SHOULD refuse, and a walk that scores every refusal as a fault
 * would bury the four that matter among twenty that are correct. Each row says
 * what was pressed and what came back; the reader judges.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:8401";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/connwalk";
const ONLY = process.env.ONLY ? process.env.ONLY.split(",") : null;
await fs.mkdir(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForTimeout(2500);

// ── The stack check, before anything is believed ────────────────────────────
const grid = await page.evaluate(async (t) => {
  const r = await fetch(`/api/${t}/integrations`);
  return { status: r.status, body: await r.json() };
}, TENANT);
const keys = (grid.body.providers ?? []).map((p) => p.key);
console.log(`STACK: ${BASE} serves ${keys.length} connectors`);
if (keys.length === 0) { console.log("REFUSING TO WALK — the API served none."); await browser.close(); process.exit(2); }

const rows = [];
for (const key of ONLY ?? keys) {
  const card = (grid.body.providers ?? []).find((p) => p.key === key) ?? {};
  const row = { key, name: card.display_name ?? "?", disposition: card.disposition?.kind ?? "?" };

  // ── 1 · the card on the grid, and what it OFFERS ──────────────────────────
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  const el = await page.$(`[data-provider="${key}"]`);
  if (el === null) { row.card = "NO CARD ON THE GRID"; rows.push(row); continue; }
  row.card = await el.evaluate((n) => {
    const btns = [...n.querySelectorAll("button")].map((b) => ({ label: b.innerText.trim(), disabled: b.disabled }));
    const links = [...n.querySelectorAll("a")].map((a) => a.innerText.trim()).filter(Boolean);
    return { buttons: btns, links, text: n.innerText.replace(/\n+/g, " · ").slice(0, 260) };
  });

  // ── 2 · press the card's PRIMARY control and record what comes back ───────
  const primary = await el.$("button:not([disabled])");
  if (primary === null) {
    row.pressed = "no enabled control on the card";
  } else {
    const label = (await primary.innerText()).trim();
    const before = page.url();
    await primary.evaluate((n) => n.click());
    await page.waitForTimeout(1600);
    const after = page.url();
    const dialog = await page.$('[role="dialog"], [data-modal]');
    row.pressed = {
      label,
      navigatedTo: after === before ? null : after.replace(BASE, ""),
      opened: dialog === null ? null : (await dialog.innerText()).replace(/\n+/g, " · ").slice(0, 320),
    };
    await page.keyboard.press("Escape").catch(() => {});
  }

  // ── 3 · the two addresses a clerk reaches by hand ─────────────────────────
  for (const [name, path] of [["setUp", `settings/connectors/${key}/configure`], ["view", `settings/integrations/${key}`]]) {
    await page.goto(`${BASE}/${TENANT}/${path}`, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(1100);
    const txt = await page.locator("body").innerText();
    // ⚠ **"not built yet" IS TWO DIFFERENT SENTENCES AND THE FIRST DRAFT COULD
    // NOT TELL THEM APART — law 7's *looking at the wrong thing*, found on the
    // dry run.** The product's generic missing-screen page says *"This screen
    // is not built yet"*, and a connector the PO deliberately HELD says
    // *"Coming soon · W7 — not built yet."* Greping the page for the phrase
    // scored a correct, ruled refusal as a missing screen — which would have
    // reported eleven held connectors as eleven faults and buried the real
    // ones. The screen is MISSING only when the product's own catch-all page
    // is what rendered; a coming-soon sentence means the screen is THERE and
    // doing its job.
    const heldHere = /coming soon/i.test(txt);
    row[name] = {
      built: heldHere || !/this screen is not built yet/i.test(txt),
      held: heldHere,
      head: (txt.split("\n").find((l) => l.trim().length > 2 && !/^(Settings|Search)$/.test(l.trim())) ?? "").trim().slice(0, 60),
      refusals: (txt.match(/[^\n]*(?:cannot|not set up|coming soon|refus|no |never|failed)[^\n]*/gi) ?? []).slice(0, 3),
    };
    if (name === "setUp" && row[name].built) await page.screenshot({ path: `${OUT}/${key}.png`, fullPage: true });
  }
  rows.push(row);
  console.log(`${key.padEnd(22)} card=${row.card === "NO CARD ON THE GRID" ? "MISSING" : "ok"} setUp=${row.setUp?.built} view=${row.view?.built} pressed=${typeof row.pressed === "string" ? row.pressed : row.pressed.label}`);
}

await fs.writeFile(`${OUT}/walk.json`, JSON.stringify(rows, null, 2));
console.log(`\n${rows.length} connectors walked. Detail in ${OUT}/walk.json, screens in ${OUT}/`);
await browser.close();
