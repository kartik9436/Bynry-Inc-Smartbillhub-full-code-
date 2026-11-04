// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-21 — *"make application fees optional - so that we
//          can approve it"* and *"waiving is options and can you fix the issue
//          here"*, corrected the same day: *"in practical this does not ahppen
//          … $20 or $0 - some utilities will not take applciation fees also"*.
// Defects: DEF-CUS-6096 (the waive is a silent 500) · DEF-CUS-6097 (the raw
//          `{{receiptNo}}` and its impossible advice) · DEF-CUS-6102 (the fee
//          SURFACE on a utility that charges no fee) · DEF-CUS-5399 (the gate)
// Rules:   BR-CUS-090 (AMENDED 2026-09-21) · B14 rules 31/32/33
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS READS RENDERED OUTPUT, WHICH NO GATE IN THIS REPOSITORY DOES**
// (hard-won law 6). Every fault it walks was invisible to `tsc`, to vitest and
// to all of `run_gates`: a 500 the screen swallowed, a placeholder i18next
// renders verbatim rather than throwing, and a panel that is merely *present*.
//
// **THE THREE SHAPES THE PO NAMED, ONE REQUEST EACH**, because a walk of only
// the interesting one proves nothing about the ordinary day:
//
//   $20 UNPAID   the fee is reported, the approval goes through, the debt is
//                still on the screen afterwards
//   $20 PAID     recording a SECOND receipt is refused — and the refusal quotes
//                the receipt number instead of printing `{{receiptNo}}`
//   $0 / NO FEE  the utility that charges nothing: what does it still meet?
//
// ⚠ **IT PRESSES WAIVE FOR REAL.** The defect is that the press did nothing
// VISIBLE, so a walk that only looked at the markup would have reported the
// screen healthy — which is exactly what happened before it was filed.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/<your db> \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8188 --noreload)
//   (cd 07-frontend && npm run build && PORT=8189 \
//      API_PROXY_TARGET=http://127.0.0.1:8188 node server.mjs)
//   BASE=http://127.0.0.1:8189 UNPAID=<uuid> PAID=<uuid> NOFEE=<uuid> \
//      node 10-scripts/po20260921_application_fee_walkthrough.mjs
//
// ⛔ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
// looks exactly like a broken screen. `10-scripts/proof-db.sh clone <label>`.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8189";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const WIDTH = Number(process.env.WIDTH ?? 1440);
const SHOTS = process.env.SHOTS ?? "";

const CASES = [
  ["$20 UNPAID", process.env.UNPAID],
  ["$20 PAID", process.env.PAID],
  ["$0 NO FEE", process.env.NOFEE],
];
for (const [label, id] of CASES) {
  if (!id) throw new Error(`${label}: set its env var to a real request uuid — walk a row, not a fixture`);
}

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error("no chromium found — run `npx playwright install chromium` from 07-frontend");
}

const failures = [];
function fail(message) {
  failures.push(message);
  console.log(`    ✗ ${message}`);
}
function pass(message) {
  console.log(`    ✓ ${message}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: WIDTH, height: 1200 } });

// ⚠ **EVERY 5xx IS RECORDED, WHICH IS THE WHOLE POINT OF `DEF-CUS-6096`.** The
// server threw four times and the screen said nothing; a walk that only reads
// the DOM would have called that a healthy screen too.
const serverErrors = [];
page.on("response", (res) => {
  if (res.status() >= 500) serverErrors.push(`${res.status()} ${res.request().method()} ${res.url()}`);
});
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });

async function open(id) {
  await page.goto(`${BASE}/${TENANT}/requests/${id}`, { waitUntil: "networkidle" });
  await page.waitForSelector("h1", { timeout: 15000 });
}

/** What the FEES panel is showing right now, read off the rendered page.
 *
 * ⚠ **A `$0` REQUEST DRAWS NO FIGURES AT ALL** — the panel prints the
 * `noCurrencyYet` sentence instead, so `[data-display]` does not exist there.
 * An unconditional read of it timed out for 30 seconds and killed the walk
 * mid-way, which reads exactly like a broken screen and is a harness fault
 * (law 7: a check's output must distinguish pass from fail to a reader). The
 * count is asked FIRST and the absence is reported as an absence. */
async function fees() {
  const panel = page.locator('[data-panel-name="fees"]');
  const figures = panel.locator("[data-display]");
  const n = await figures.count();
  return {
    present: (await panel.count()) > 0,
    text: ((await panel.textContent()) ?? "").replace(/\s+/g, " ").trim(),
    outstanding: n === 0 ? "(no figures drawn)" : ((await figures.last().textContent()) ?? ""),
    collectButton: await page
      .getByRole("button", { name: "Record what was handed over" })
      .count(),
  };
}

async function shot(name) {
  if (SHOTS) await page.screenshot({ path: join(SHOTS, `${name}.png`), fullPage: true });
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 · $20 UNPAID — the fee is reported, the approval goes through, and the
//     debt is STILL THERE afterwards. That last clause is the narrow reading
//     of the ruling and it is what stops this becoming a forgotten debt.
// ═══════════════════════════════════════════════════════════════════════════
console.log(`\n══ $20 UNPAID · ${process.env.UNPAID}`);
await open(process.env.UNPAID);
const before = await fees();
console.log(`    fees panel: ${before.outstanding.trim()} outstanding`);
await shot("unpaid-before");

const approveButton = page.locator('[data-decision-action="approve"]');
if (await approveButton.isDisabled()) {
  fail("the head's Approve is disabled — the fee is still gating, or this state does not offer it");
} else {
  pass("Approve is live over an unpaid fee");
  await approveButton.click();
  const modal = page.locator('[role="dialog"]').first();
  await modal.waitFor({ timeout: 10000 });
  const commit = modal.getByRole("button", { name: /Approve/ }).last();
  const blocked = (await modal.locator("[data-commit-blocked]").allTextContents()).join(" | ");
  const told = (await modal.locator("[data-approve-outstanding]").allTextContents()).join(" | ");
  console.log(`    modal: commit ${(await commit.isDisabled()) ? "REFUSED" : "live"}${blocked ? ` · ${blocked}` : ""}`);
  if (told) console.log(`    told about: ${told}`);
  await shot("unpaid-modal");
  if (await commit.isDisabled()) {
    fail(`the commit is refused over an unpaid fee: ${blocked}`);
  } else {
    await commit.click();
    await page.waitForTimeout(3000);
    await shot("unpaid-after");
    const state = ((await page.locator("h1").first().textContent()) ?? "") + " " + ((await page.locator("[data-state-pill]").first().textContent().catch(() => "")) ?? "");
    const after = await fees();
    console.log(`    after approving: ${after.outstanding.trim()} outstanding · ${state.replace(/\s+/g, " ").trim()}`);
    if (!after.text.includes("20.00")) {
      fail("the outstanding fee is NOT visible on the request after approval — a blocked approval became a forgotten debt");
    } else {
      pass("the $20.00 outstanding is still on the request after approval");
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 2 · $20 PAID — the second receipt. `DEF-CUS-6097`, read as a clerk reads it.
// ═══════════════════════════════════════════════════════════════════════════
console.log(`\n══ $20 PAID · ${process.env.PAID}`);
await open(process.env.PAID);
await page.getByRole("button", { name: "Record what was handed over" }).click();
const collect = page.locator('[role="dialog"]').first();
await collect.waitFor({ timeout: 10000 });
await collect.locator("input").first().fill("20.00");
// The receipt field is the LAST text input in the dialog; a different number
// from the one already recorded is what makes this the refusal path.
await collect.locator('input[type="text"]').last().fill("RCP-APP8-SECOND");
await collect.getByRole("button", { name: "Record it" }).click();
await page.waitForTimeout(2000);
// ⚠ **THE REFUSAL ELEMENT, NOT THE WHOLE DIALOG.** `FormModal` renders the
// server's sentence in its own strip; falling back to the dialog's text would
// let a walk report a sentence that never appeared, over copy that is simply
// elsewhere on the form.
const strip = collect.locator('[data-refusal], [role="alert"]');
const refusal = ((await strip.allTextContents()) ?? []).join(" | ").replace(/\s+/g, " ").trim();
if (!refusal) {
  fail("the second receipt produced NO refusal on screen at all");
}
console.log(`    refusal: ${refusal.slice(0, 240)}`);
await shot("paid-refusal");
if (refusal.includes("{{")) {
  fail(`a raw placeholder is on screen: ${refusal.match(/\{\{[^}]*\}\}/g)?.join(", ")}`);
} else {
  pass("no raw placeholder — the sentence interpolated");
}
if (!refusal.includes("RCP-APP8-FEE20PAID")) {
  fail("the refusal does not quote the receipt number it exists to quote");
} else {
  pass("the receipt number is quoted");
}
if (/Record further payment in Payments/i.test(refusal)) {
  fail("the refusal still sends the clerk to Payments, which cannot move this figure");
} else {
  pass("the advice no longer points at Payments");
}

// ═══════════════════════════════════════════════════════════════════════════
// 3 · WAIVING — pressed for real, with the network watched.
// ═══════════════════════════════════════════════════════════════════════════
console.log(`\n══ WAIVE · ${process.env.UNPAID}`);
await open(process.env.UNPAID);
const errorsBefore = serverErrors.length;
const toggle = page.locator('[data-panel-name="fees"] button[aria-expanded="false"]').first();
await toggle.click();
const waiveRow = page.getByRole("button", { name: "Waive this fee" }).first();
const feeLineBefore = ((await page.locator("[data-fee-line]").first().textContent()) ?? "")
  .replace(/\s+/g, " ")
  .trim();
console.log(`    line before: ${feeLineBefore.slice(0, 160)}`);
await waiveRow.click();
await page.waitForTimeout(3000);
await shot("waive-after");
const feeLineAfter = ((await page.locator("[data-fee-line]").first().textContent()) ?? "")
  .replace(/\s+/g, " ")
  .trim();
const alert = ((await page.locator('[data-action-error]').allTextContents()) ?? []).join(" | ").trim();
console.log(`    line after:  ${feeLineAfter.slice(0, 160)}`);
if (alert) console.log(`    alert: ${alert}`);
if (serverErrors.length > errorsBefore) {
  fail(`the waive raised a server error: ${serverErrors.slice(errorsBefore).join(" · ")}`);
} else {
  pass("no 5xx on the waive");
}
if (feeLineAfter === feeLineBefore && !alert) {
  fail("the screen changed in NO WAY and said NOTHING — the exact defect");
} else if (feeLineAfter === feeLineBefore) {
  fail(`the waive did not take, but at least it said so: ${alert}`);
} else {
  pass("the line now reads as waived");
}

// ═══════════════════════════════════════════════════════════════════════════
// 4 · $0 — the utility that takes no application fee.
//     ⚠ **THIS SECTION REPORTS RATHER THAN REFUSES.** What a `$0` utility
//     should see is a PO requirement of 2026-09-21; what it sees today is
//     measured here and filed as `DEF-CUS-6102`, because hiding a panel needs
//     a per-tenant setting this product does not have.
// ═══════════════════════════════════════════════════════════════════════════
console.log(`\n══ $0 NO FEE · ${process.env.NOFEE}`);
await open(process.env.NOFEE);
const zero = await fees();
await shot("nofee");
console.log(`    fees panel present : ${zero.present}`);
console.log(`    its whole text     : ${zero.text.slice(0, 200)}`);
console.log(`    collect button     : ${zero.collectButton > 0 ? "OFFERED" : "absent"}`);
await page.goto(`${BASE}/${TENANT}/requests/${process.env.NOFEE}?tab=decision`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const decision = ((await page.locator("main").textContent()) ?? "").replace(/\s+/g, " ");
const feeRow = /fee/i.test(decision);
console.log(`    decision tab names a fee: ${feeRow}`);
await shot("nofee-decision");
const zeroApprove = page.locator('[data-decision-action="approve"]');
console.log(`    Approve: ${(await zeroApprove.isDisabled()) ? "disabled" : "live"}`);
if (await zeroApprove.isDisabled()) {
  fail("a $0 utility cannot approve — a fee gate is firing where there is no fee");
} else {
  pass("no fee GATE on a $0 request");
}

console.log(`\nserver 5xx over the whole walk: ${serverErrors.length}`);
for (const e of serverErrors) console.log(`   ${e}`);
console.log(failures.length === 0 ? "\nWALK CLEAN" : `\n${failures.length} FAILURE(S)`);
for (const f of failures) console.log(`   ✗ ${f}`);
await browser.close();
process.exit(failures.length === 0 ? 0 : 1);
