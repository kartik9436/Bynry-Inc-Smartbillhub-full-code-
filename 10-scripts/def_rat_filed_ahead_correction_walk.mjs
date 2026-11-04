// ── Trace ──────────────────────────────────────────────
// Defects:  the PO's beta report of 2026-10-01 on v2.418.9, tenant
//           ottumwa-water-works, screen RAT-03 then RAT-01: *"i ahve tried to
//           save draft rate schedule - 2 , it accept everything but again says
//           it is draft - why ; on step 4 it is now allowing me to input
//           effective dates- why ; it is saved but sagain says draft"*.
//           Filed as DEF-RAT-8703 (toast says live, list says Draft),
//           DEF-RAT-8704 (no hint on how to move the dates under Fix an error)
//           and DEF-RAT-8705 (We could not count the bills).
// Rules:    12-governance/22-product-maintenance-process.md §0 and §4 (reproduce,
//           then prove against the reproduction in a browser) · CLAUDE.md
//           hard-won law 6 (no gate reads rendered output) · B14 rule 37 (every
//           figure below belongs to the seeded tenant or is typed here).
// ───────────────────────────────────────────────────────
/**
 * Walk the PO's steps on a schedule FILED AHEAD OF TIME — its only live
 * version starts tomorrow, so nothing is in force today. That is the state the
 * PO's screenshots prove the Ottumwa row was in: the list printed `Draft` (no
 * version in force today) beside `Change scheduled — effective 01-Oct-26`.
 *
 *     BASE=http://127.0.0.1:8762 SHOTS=<dir> node 10-scripts/def_rat_filed_ahead_correction_walk.mjs
 *
 * It creates its own schedule through the API (a private database is assumed —
 * never run it against a database a sibling is using), then drives RAT-01 and
 * RAT-03 in Chromium at 1440 and prints named VERDICTS at the end.
 *
 * `EXPECT=before` asserts the reported symptoms are present; the default
 * `EXPECT=after` asserts they are gone.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8762";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "08-qa/screens/rat-draft-after-correct-2026-10-01";
const EXPECT = process.env.EXPECT ?? "after";
const PREFIX = process.env.PREFIX ?? EXPECT;
const FROM = process.env.FROM ?? "2026-10-02";
const TO = process.env.TO ?? "2026-12-31";
const NAME = `Repro ${PREFIX} ${Date.now() % 100000} — Residential water (filed ahead)`;
const REASON = "+6% across tiers · PUC #W-2025-1184";

const verdicts = [];
const verdict = (name, pass, detail = "") => {
  verdicts.push({ name, pass, detail });
  console.log(`  ${pass ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
};

const browser = await chromium.launch({
  ...(process.env.E2E_CHROMIUM_EXECUTABLE ? { executablePath: process.env.E2E_CHROMIUM_EXECUTABLE } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("    console: " + m.text()); });
const shot = async (n, label) => {
  const path = `${SHOTS}/${PREFIX}-${n}-${label}.png`;
  await page.screenshot({ path, fullPage: false });
  console.log(`    shot ${path}`);
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
console.log(`signed in as ${EMAIL}`);

// ── setup: a copy of the seeded inclining-tier water schedule, filed ahead ──
const api = (path) => `${BASE}/api/${TENANT}${path}`;
const list = await (await ctx.request.get(api("/rate-schedules?per=200"))).json();
const cards = list.results ?? list;
const sample = cards.find((c) => /Residential water \(inclining tiers\)/.test(c.name));
if (!sample) throw new Error("the seeded inclining-tier water schedule is not on this tenant");
const detail = await (await ctx.request.get(api(`/rate-schedules/${sample.id}`))).json();
const live = detail.current_version;
const payload = {
  name: NAME,
  service: detail.service,
  model: live.model ?? detail.structure,
  uom: live.uom,
  effective_from: FROM,
  effective_to: TO,
  account_type_id: detail.account_type_id ?? null,
  structure: {
    tiers: (live.structure.tiers ?? []).map((t) => ({
      from_qty: t.from_qty, to_qty: t.to_qty, unit_price: t.unit_price,
    })),
  },
  size_rows: (live.size_rows ?? []).map((r) => ({ size_class: r.size_class, ...(r.amount !== undefined ? { amount: r.amount } : {}) })),
};
const created = await ctx.request.post(api("/rate-schedules"), { data: payload });
if (!created.ok()) {
  throw new Error(`could not create the filed-ahead schedule: ${created.status()} ${await created.text()}`);
}
const schedule = await created.json();
console.log(`created ${schedule.name} · ${FROM} → ${TO} · status ${schedule.status} · scheduled ${schedule.scheduled_change}`);
verdict("setup: nothing is in force today and the version is scheduled",
  schedule.status === "draft" && schedule.scheduled_change === FROM,
  `status=${schedule.status} scheduled_change=${schedule.scheduled_change}`);

const rowOf = () => page.locator("tr", { hasText: NAME });

// 1 · RAT-01 before the edit
await page.goto(`${BASE}/${TENANT}/plans-rates/rates`, { waitUntil: "networkidle" });
await rowOf().first().scrollIntoViewIfNeeded();
await shot(1, "list-before");

// 2 · RAT-03, Fix an error
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/${schedule.id}/edit`, { waitUntil: "networkidle" });
await page.getByText("Fix an error", { exact: true }).click();
await page.waitForTimeout(400);
await shot(2, "this-edit-fix-an-error");
const couldNotCount = async () => (await page.getByText("We could not count the bills.").count()) > 0;
const top = await couldNotCount();
verdict(EXPECT === "before" ? "C reproduced: 'We could not count the bills.' at the top" : "C fixed: no 'We could not count the bills.' at the top",
  EXPECT === "before" ? top : !top);
const noBillsTop = (await page.getByText("No bills went out on this.").count()) > 0;
if (EXPECT === "after") verdict("C: the top says no bills went out on this version", noBillsTop);

// 3 · walk to step 4
for (let step = 1; step <= 3; step += 1) {
  await page.getByRole("button", { name: /^Continue/ }).click();
  await page.waitForTimeout(300);
}
await page.getByText("Dates and reach").scrollIntoViewIfNeeded();
await shot(3, "step4-dates-and-reach");
const dateInputs = await page.locator('input[type="date"], input[id*="effective"]').count();
verdict("B: no date input under Fix an error (BR-RAT-104, ruled)", dateInputs === 0, `${dateInputs} date input(s)`);
const hint = (await page.getByText("New dates? Choose Change the rate.").count()) > 0;
verdict(EXPECT === "before" ? "B reproduced: nothing says how to move the dates" : "B fixed: the step says how to move the dates",
  EXPECT === "before" ? !hint : hint);
const step4Count = await couldNotCount();
verdict(EXPECT === "before" ? "C reproduced at step 4" : "C fixed at step 4", EXPECT === "before" ? step4Count : !step4Count);
await page.locator("#rate-correction-reason").fill(REASON);
await shot(4, "step4-reason-typed");

// 4 · step 5, commit
await page.getByRole("button", { name: /^Continue/ }).click();
await page.waitForTimeout(400);
await page.getByRole("button", { name: /Correct this version/ }).scrollIntoViewIfNeeded();
await shot(5, "step5-review");
await page.getByRole("button", { name: /Correct this version/ }).click();
const toast = page.getByRole("status").filter({ hasText: NAME }).first();
await toast.waitFor({ timeout: 20000 }).catch(() => {});
const toastText = (await toast.textContent().catch(() => "")) ?? "";
console.log(`    toast: ${JSON.stringify(toastText)}`);
await rowOf().first().scrollIntoViewIfNeeded().catch(() => {});
await shot(6, "list-after-save-toast");
const saysLive = /is live/.test(toastText);
verdict(EXPECT === "before" ? "A reproduced: the toast says 'is live'" : "A fixed: the toast does not say 'is live' for a version that starts tomorrow",
  EXPECT === "before" ? saysLive : !saysLive && toastText.includes(NAME), toastText);
const rowText = (await rowOf().first().textContent()) ?? "";
verdict("A: the row still says Draft and Change scheduled (nothing is in force today)",
  /Draft/.test(rowText) && /Change scheduled/.test(rowText), rowText.replace(/\s+/g, " ").slice(0, 160));

// 5 · reload
await page.reload({ waitUntil: "networkidle" });
await rowOf().first().scrollIntoViewIfNeeded();
await shot(7, "list-after-reload");

// 6 · the money question, read through the API the screen reads
const after = await (await ctx.request.get(api(`/rate-schedules/${schedule.id}`))).json();
const versions = after.versions.filter(Boolean);
const liveRows = versions.filter((v) => v.superseded_by == null && v.superseded_by_id == null);
console.log(`    versions: ${versions.map((v) => `${v.effective_from}→${v.effective_to ?? "open"}${v.corrects ? " (correction)" : ""}`).join(" · ")}`);
verdict("money: exactly one un-superseded version, starting on the filed date",
  liveRows.length >= 1 && liveRows.every((v) => v.effective_from === FROM),
  liveRows.map((v) => `${v.effective_from}→${v.effective_to}`).join(", "));

// 7 · regression: a schedule IN FORCE today still counts its own version
const active = await (await ctx.request.get(api(`/rate-schedules/${sample.id}`))).json();
verdict("regression: the seeded in-force schedule still answers a bill count",
  active.status === "active" && typeof active.current_version_issued_bills === "number",
  `status=${active.status} bills=${active.current_version_issued_bills}`);

await browser.close();
const failed = verdicts.filter((v) => !v.pass);
console.log(`\nVERDICTS (${EXPECT}): ${verdicts.length - failed.length} pass, ${failed.length} fail`);
for (const v of verdicts) console.log(`  ${v.pass ? "PASS" : "FAIL"} ${v.name}`);
process.exit(failed.length === 0 ? 0 : 1);
