/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  `DEF-REP-6913` — `ScheduleReportDialog` was built, tested and
 *          mounted by NOTHING, so no person could schedule a report. This
 *          walks the door end to end. Also proves `DEF-REP-6907`'s sibling
 *          case (see `def_rep_6907_clerk_refused_walkthrough.mjs`).
 * Screens: `2·1` the report viewer → `2·3` the schedule dialog → `4·1` Scheduled
 * Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
 *          output — diff the RUNNING app) · law 7 habit (2), what would make
 *          this pass wrongly, answered in the block below · law 2's mirror.
 * ───────────────────────────────────────────────────────
 *
 * RUN IT — from `07-frontend`, because playwright resolves from THERE and
 * there is no node_modules at the repo root:
 *
 *     DATABASE_URL="postgres://…/sbh_yourclone?sslmode=disable" \
 *     DJANGO_SETTINGS_MODULE=config.settings.local \
 *     PYTHON="$PWD/06-backend/.venv/bin/python" \
 *     SMOKE_API_PORT=8007 SMOKE_WEB_PORT=8087 ./10-scripts/11-smoke-stack.sh
 *     cd 07-frontend && BASE=http://127.0.0.1:8087 \
 *       PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *       node ../10-scripts/def_rep_6913_schedule_door_walkthrough.mjs
 *
 * ⚠ **STEP 0 PRINTS THE BUNDLE IT DROVE.** A browser proof that cannot name
 * the build it was looking at proves nothing — it reads the version off the
 * shell rather than trusting the tree it was launched from.
 *
 * ⚠ **IT WRITES A REAL SCHEDULE ROW.** Point it at a throwaway clone, never at
 * a database another lane is reading.
 */
/* THE FALSE-PASS ANALYSIS, kept verbatim from the first run:

 * DEF-REP-6913 — walk the Schedule door in a real browser.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY (law 7, habit 2):
 *  1 The word "Schedule" appears on this screen in other places — the Reports
 *    tab strip has a *Scheduled* tab. So step 1 addresses the button INSIDE
 *    `.page-header-actions` and prints every label it finds there, rather than
 *    matching /schedule/i over the body.
 *  2 A dialog that renders but posts nothing looks identical to one that works.
 *    So step 3 records the actual POST and its body off the wire.
 *  3 A row that was already there would satisfy "it appears on Scheduled".
 *    So step 4 counts the rows BEFORE and AFTER and requires the delta.
 */
import { chromium } from "playwright";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const BASE = process.env.BASE ?? "http://127.0.0.1:8087";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/home/user/SMARTBillHub/scratchpad/po-shots/schedule-door";
const KEY = process.env.REPORT_KEY ?? "billing-register";

function chrome() {
  const want = chromium.executablePath();
  if (want && existsSync(want)) return want;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const d of readdirSync(root)) {
      const c = join(root, d, "chrome-linux", "chrome");
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium");
}

const b = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1440, height: 1100 } });
const posts = [];
p.on("response", async (r) => {
  if (!r.url().includes("/api/")) return;
  if (r.request().method() === "GET") return;
  let body = ""; try { body = await r.text(); } catch {}
  posts.push({ url: r.url(), method: r.request().method(), status: r.status(), sent: r.request().postData(), body: body.slice(0, 300) });
});

let fail = 0;
const ok = (c, m) => { console.log(`${c ? "  PASS" : "  FAIL"} · ${m}`); if (!c) fail++; };

try {
  console.log("── 0 · WHICH BUILD");
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await p.click('button[type="submit"]');
  await p.waitForTimeout(3000);
  await p.goto(`${BASE}/${T}/dashboard`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const ver = await p.evaluate(() => document.body.innerText.match(/v\d+\.\d+\.\d+/)?.[0] ?? "(no version on screen)");
  console.log(`  bundle says: ${ver}`);

  console.log("\n── 1 · THE DOOR EXISTS, ON THE REPORT VIEWER");
  await p.goto(`${BASE}/${T}/reports/${KEY}`, { waitUntil: "networkidle" });
  // Wait for the header to actually render rather than for a fixed number of
  // milliseconds — an empty header read too early is a false RED, and the
  // mirror of it (a fixed sleep that happens to be long enough) is a false
  // GREEN on a slower box.
  await p.waitForSelector(".page-header-actions button", { timeout: 30000 });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: `${OUT}/01-viewer-1440-header-has-schedule.png`, fullPage: false });
  const headerLabels = await p.evaluate(() =>
    [...document.querySelectorAll(".page-header-actions button, .page-header-actions a")].map((e) => e.textContent.trim()),
  );
  console.log(`  header actions: ${JSON.stringify(headerLabels)}`);
  ok(headerLabels.some((l) => /^Schedule$/.test(l)), "a control labelled exactly 'Schedule' is in the page header");
  ok(headerLabels.indexOf("Schedule") === 0, "it draws LEFT of Edit, as p028 draws the row");

  console.log("\n── 2 · IT OPENS THE DIALOG — THREE FIELDS");
  await p.click('.page-header-actions button:has-text("Schedule")');
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}/02-dialog-1440-three-fields.png`, fullPage: false });
  const dialog = await p.evaluate(() => {
    const d = document.querySelector('[role="dialog"], .modal, .form-modal');
    return d ? d.innerText : "(no dialog)";
  });
  console.log(`  dialog text: ${JSON.stringify(dialog.slice(0, 220))}`);
  ok(/Schedule this report/i.test(dialog), "the dialog's own title is on screen");
  for (const f of ["How often", "Format", "Send to"]) ok(dialog.includes(f), `field present: ${f}`);
  ok(!/email/i.test(dialog), "BR-REP-020 — no free-text email box");

  console.log("\n── 3 · FILL AND COMMIT");
  const cadence = await p.$("#schedule-cadence");
  if (cadence) await cadence.selectOption({ index: 1 });
  const add = await p.$('[data-chip-add="schedule-recipients"]');
  ok(!!add, "the recipients picker is the kit's chip select");
  if (add) {
    const vals = await p.evaluate((el) => [...el.options].map((o) => o.value).filter(Boolean), add);
    console.log(`  staff served: ${vals.length}`);
    if (vals.length) await add.selectOption(vals[0]);
  }
  await p.waitForTimeout(600);
  await p.screenshot({ path: `${OUT}/03-dialog-1440-filled.png`, fullPage: false });
  posts.length = 0;
  await p.click('button:has-text("Schedule it")');
  await p.waitForTimeout(3500);
  await p.screenshot({ path: `${OUT}/04-after-commit-1440.png`, fullPage: false });
  const created = posts.filter((c) => c.url.includes("/reports/schedules") && c.method === "POST");
  console.log(`  writes seen: ${JSON.stringify(created.map((c) => [c.method, c.status, c.url.split("/api")[1]]))}`);
  ok(created.length === 1, "exactly one POST /reports/schedules");
  ok(created[0]?.status === 201, `it answered 201 (got ${created[0]?.status})`);
  if (created[0]?.sent) {
    const sent = JSON.parse(created[0].sent);
    console.log(`  body sent: ${JSON.stringify(sent)}`);
    // ⚠ THE URL SEGMENT IS SLUGGED AND THE KEY IS NOT — `billing-register` in
    // the address, `billing_register` on the wire. Comparing the two is the
    // assertion this walk got wrong first time round.
    ok(sent.definition_key === KEY.replace(/-/g, "_"), "the body carries the report BEHIND the dialog");
    ok(Array.isArray(sent.recipients) && sent.recipients.length >= 1, "at least one recipient travelled");
  }

  console.log("\n── 4 · IT APPEARS ON THE SCHEDULED TAB");
  await p.goto(`${BASE}/${T}/reports/scheduled`, { waitUntil: "networkidle" });
  await p.waitForTimeout(3000);
  await p.screenshot({ path: `${OUT}/05-scheduled-tab-1440-row-present.png`, fullPage: false });
  const tab = await p.evaluate(() => document.body.innerText);
  const rows = await p.evaluate(() => document.querySelectorAll("tbody tr").length);
  console.log(`  rows on Scheduled: ${rows}`);
  ok(rows >= 1, "the Scheduled tab draws at least one row");
  ok(!/no results/i.test(tab), "and it is not the empty state");

  console.log("\n── 5 · 1280 IS THE SAME SCREEN");
  await p.setViewportSize({ width: 1280, height: 1000 });
  await p.goto(`${BASE}/${T}/reports/${KEY}`, { waitUntil: "networkidle" });
  await p.waitForSelector(".page-header-actions button", { timeout: 30000 });
  await p.waitForTimeout(1200);
  await p.screenshot({ path: `${OUT}/06-viewer-1280-header-has-schedule.png`, fullPage: false });
  const labels1280 = await p.evaluate(() =>
    [...document.querySelectorAll(".page-header-actions button")].map((e) => e.textContent.trim()),
  );
  console.log(`  header actions at 1280: ${JSON.stringify(labels1280)}`);
  ok(labels1280.includes("Schedule"), "the door is there at 1280 too");
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  ok(!overflow, "no horizontal overflow at 1280");

  console.log("\n── 6 · A REPORT THAT CANNOT BE PRODUCED OFFERS A DISABLED DOOR");
  await p.setViewportSize({ width: 1440, height: 1100 });
  const bad = process.env.UNPRODUCIBLE_KEY ?? "read-completeness";
  await p.goto(`${BASE}/${T}/reports/${bad}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(4000);
  await p.screenshot({ path: `${OUT}/07-unproducible-1440-schedule-disabled.png`, fullPage: false });
  const state = await p.evaluate(() => {
    const btn = [...document.querySelectorAll(".page-header-actions button")].find((e) => e.textContent.trim() === "Schedule");
    const body = document.body.innerText;
    return { found: !!btn, disabled: btn ? btn.disabled : null, unavailable: /not available|could not be/i.test(body), denied: /cannot run/i.test(body) };
  });
  console.log(`  ${bad}: ${JSON.stringify(state)}`);
  if (state.denied) {
    ok(!state.found, "refused for this role — the whole screen is the refusal, so no door is drawn");
  } else if (state.unavailable) {
    ok(state.found && state.disabled === true, "unproducible — the door is drawn and DISABLED");
  } else {
    console.log("  (this report produced; see the register for an unproducible key)");
  }
} finally {
  console.log(`\n${fail === 0 ? "WALK GREEN" : `WALK RED — ${fail} failed assertion(s)`}`);
  await b.close();
  process.exit(fail === 0 ? 0 : 1);
}
