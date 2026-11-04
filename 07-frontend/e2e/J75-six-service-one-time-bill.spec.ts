// ── Trace ──────────────────────────────────────────────
// Journey:  J75 — every one-time bill kind, end to end, for a utility with SIX
//           services (water, sewer, trash, fire, battery, solar)
//           · 08-qa/01-e2e/journeys/J75-six-service-one-time-bill.md
// Request:  PO 2026-10-01, verbatim: "when you complete this please run end to
//           end run for all one tim ebill scenarios with utility ahving 6 utility
//           services - Water, Sewer, trash, Fire, Battery and Solar - and see we
//           are able to create one time bill for this utility if you face bugs
//           fix them - we already done end to end run before you can use that"
// Reuses:   J74's spec (this file is its copy: the same four clerk steps, the five
//           confirmations, the two replays), on a NEW utility.
// Seed:     10-scripts/seed_six_service_one_time.py (signs up `sixrivers` itself)
// Verifier: 10-scripts/verify_j74_one_time_bill.py --world j75
// ───────────────────────────────────────────────────────
//
//   E2E_TENANT=sixrivers E2E_EMAIL=priya@sixriversutility.com \
//   E2E_BASE_URL=http://127.0.0.1:<web> npx playwright test e2e/J75-six-service-one-time-bill.spec.ts --workers=1
//
// Every expected total below was priced BY HAND from the seed's prices before the
// run; the working is written beside each case and in the journey file.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Locator, Page, Request } from "@playwright/test";

import { expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const SHOTS = "../08-qa/screens/six-service-onetime-2026-10-01";
const RESULTS = `${SHOTS}/j75-results.json`;
const UNIT = (n: string) => new RegExp(`Unit ${n}(?:Active|Closed|Pending|\\s|,|$)`);

// ── the record each case leaves for the database verifier ────────────────────

interface ReviewLine {
  service: string;
  meter: string;
  charge: string;
  quantity: string;
  rate: string;
  amount: string;
  /** size × count · base · each, under a capacity line (BR-BIL-1067) */
  breakdown: string;
}

interface CaseRecord {
  case: number;
  kind: string;
  account: string;
  review: {
    lines: ReviewLine[];
    subtotal: string;
    tax: { label: string; amount: string }[];
    one_time_charges: string | null;
    total: string;
    groups: number;
    warnings: string;
  };
  sent: { run_id: string; invoice_id: string; invoice_no: string; total: string; status: string; created: boolean };
  replay_send: { status: number; created: boolean | null; invoice_no: string | null };
  replay_draft: { status: number; code: string | null };
  sent_text: string;
}

function record(row: CaseRecord): void {
  mkdirSync(SHOTS, { recursive: true });
  let all: Record<string, CaseRecord> = {};
  try {
    all = JSON.parse(readFileSync(RESULTS, "utf8")) as Record<string, CaseRecord>;
  } catch {
    all = {};
  }
  all[String(row.case)] = row;
  writeFileSync(RESULTS, `${JSON.stringify(all, null, 2)}\n`);
}

// ── helpers (J70's, unchanged in behaviour) ──────────────────────────────────

async function shot(page: Page, name: string): Promise<void> {
  await page.waitForTimeout(400);
  await expandInnerScroller(page);
  await page.screenshot({ path: `${SHOTS}/${WIDTH}-${name}.png`, fullPage: true });
}

async function openKind(page: Page, kind: string): Promise<void> {
  await page.goto(`/${tenant()}/billing/one-time?kind=${kind}`);
  await expect(page.locator("[data-screen=one-time-bill]")).toBeVisible({ timeout: 30_000 });
}

async function pickAccount(page: Page, term: string, unit: RegExp): Promise<void> {
  const combo = page.getByRole("combobox", { name: /Find account/ });
  await combo.fill(term);
  await expect(page.getByRole("option").first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole("option").filter({ hasText: unit }).first().click();
  await expect(page.locator("[data-otb-panel=account]")).toContainText(term.split(" ")[0]);
  const card = page.locator("[data-facts=otb-account]");
  await expect(card.locator("[data-fact=plan]")).not.toContainText("—", { timeout: 15_000 });
}

async function continueStep(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.waitForTimeout(1200);
}

async function onStep(page: Page, n: number, timeout = 30_000): Promise<boolean> {
  try {
    await expect(page.locator(`[data-wizard-step="${n}"][data-state=active]`)).toBeVisible({ timeout });
    return true;
  } catch {
    return false;
  }
}

/** What stands on the page when a step did not advance — for the failure message. */
async function whyStuck(page: Page): Promise<string> {
  const parts: string[] = [];
  for (const sel of ["[data-otb-problems]", "[data-wizard=blocked]", "[role=alert]"]) {
    const loc = page.locator(sel);
    if ((await loc.count()) > 0) parts.push((await loc.first().innerText()).trim());
  }
  return parts.join(" | ") || "(nothing named on screen)";
}

interface Read {
  meter: string;
  value: string;
  moveIn?: boolean;
}

async function typeReadings(page: Page, reads: Read[]): Promise<void> {
  for (const read of reads) {
    const role = read.moveIn ? "move_in" : "current";
    const input = page.locator(`[data-reading-row='${read.meter}'] input[id^='reading-'][id*='|${role}|']`).first();
    await input.fill(read.value);
  }
  if (reads.length > 0) await page.waitForTimeout(1500);
}

async function typeLastPeriod(page: Page, reads: [string, string][]): Promise<void> {
  for (const [meter, value] of reads) {
    const input = page.locator(`[data-reading-row='${meter}'] input[id^='reading-'][id*='|last_period|']`).last();
    if ((await input.count()) > 0 && (await input.isEditable())) await input.fill(value);
  }
  await page.waitForTimeout(1500);
}

async function fillPeriods(page: Page, periods: string[][]): Promise<void> {
  for (let i = 0; i < periods.length; i++) {
    if (i > 0) await page.getByRole("button", { name: "Add period" }).click();
    await page.locator(`[id='sub_periods[${i}].period_start']`).fill(periods[i][0]);
    await page.locator(`[id='sub_periods[${i}].period_end']`).fill(periods[i][1]);
  }
}

async function toServices(page: Page): Promise<void> {
  await continueStep(page);
  expect(await onStep(page, 2, 45_000), `step 1 reaches Services — ${await whyStuck(page)}`).toBe(true);
}

/** Review's bill, exactly as the clerk read it. */
async function readReview(page: Page): Promise<CaseRecord["review"]> {
  const bill = page.locator("[data-otb-bill]");
  const lines: ReviewLine[] = [];
  for (const row of await bill.locator("tr[data-bill-line]").all()) {
    const cells = (await row.locator("td").allInnerTexts()).map((c) => c.trim());
    lines.push({
      service: cells[0],
      meter: cells[1],
      charge: cells[2],
      quantity: cells[3],
      rate: cells[4],
      amount: cells[5],
      breakdown:
        (await row.locator("[data-size-breakdown]").count()) > 0
          ? (await row.locator("[data-size-breakdown]").innerText()).replace(/\s+/g, " ").trim()
          : "",
    });
  }
  const foot = bill.locator("tbody[data-bill-foot] tr");
  const footRows = await foot.all();
  const cellsOf = async (row: Locator) => (await row.locator("td").allInnerTexts()).map((c) => c.trim());
  const subtotal = (await cellsOf(footRows[0]))[1];
  const tax: { label: string; amount: string }[] = [];
  let oneTime: string | null = null;
  for (const row of footRows.slice(1, -1)) {
    const cells = await cellsOf(row);
    // DEF-BIL-8565 — the One-time charges footer line is not a tax.
    if ((await row.getAttribute("data-bill-one-time")) !== null) oneTime = cells[1];
    else tax.push({ label: cells[0], amount: cells[1] });
  }
  const total = (await bill.locator("[data-otb-total]").innerText()).trim();
  const groups = await bill.locator("tbody[data-bill-group]").count();
  const warn = page.locator("[data-otb-warnings]");
  const warnings = (await warn.count()) > 0 ? (await warn.first().innerText()).replace(/\s+/g, " ").trim() : "";
  return { lines, subtotal, tax, one_time_charges: oneTime, total, groups, warnings };
}

/** Steps 2 → 3 → 4 → Sent, all five ticks; then the two replays. */
async function reviewSendAndReplay(
  page: Page,
  c: { case: number; kind: string; account: string; name: string; expectTotal: string | null },
): Promise<CaseRecord> {
  await continueStep(page); // Services → Review (saves typed readings through Meter Reads)
  expect(await onStep(page, 3, 60_000), `Services reaches Review — ${await whyStuck(page)}`).toBe(true);
  await expect(page.locator("[data-otb-bill]")).toBeVisible();
  await shot(page, `case${label(c.case)}-${c.name}-3-review`);
  const review = await readReview(page);
  if (c.expectTotal !== null) {
    expect.soft(review.total, `case ${c.case}: the expected total, stated before the run`).toBe(c.expectTotal);
  }

  let draftRequest: Request | null = null;
  const onDraft = (req: Request) => {
    if (req.method() === "POST" && /\/billing\/one-time$/.test(new URL(req.url()).pathname)) draftRequest = req;
  };
  page.on("request", onDraft);
  await continueStep(page); // Review → Send (the draft is made here)
  expect(await onStep(page, 4, 60_000), `Review reaches Send — ${await whyStuck(page)}`).toBe(true);
  page.off("request", onDraft);

  const send = page.getByRole("button", { name: /^Send .* bill$/ });
  await expect(send).toBeDisabled();
  for (const id of ["compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final"]) {
    await expect(send, `Send is shut before ${id} is ticked`).toBeDisabled();
    await page.locator(`#otb-confirm-${id}`).check({ force: true });
  }
  await expect(send).toBeEnabled();
  const [sendResponse] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === "POST" && /\/billing\/one-time\/[^/]+\/send$/.test(r.url()), {
      timeout: 90_000,
    }),
    send.click(),
  ]);
  expect(sendResponse.status(), `Send answered ${sendResponse.status()}: ${await sendResponse.text()}`).toBeLessThan(
    300,
  );
  const sent = (await sendResponse.json()) as CaseRecord["sent"];
  await expect(page.locator("[data-otb-sent]")).toBeVisible({ timeout: 60_000 });
  await shot(page, `case${label(c.case)}-${c.name}-4-sent`);
  const sentText = (await page.locator("[data-otb-sent]").innerText()).trim();
  expect(sentText).toMatch(/Bill .+ sent/);

  // (j) the same Send again — a double click, a retry after a timeout.
  const sendReq = sendResponse.request();
  const headers = { ...(await sendReq.allHeaders()) };
  delete headers["content-length"];
  const again = await page.request.post(sendReq.url(), { headers, data: sendReq.postData() ?? "" });
  const againBody = (await again.json().catch(() => ({}))) as { created?: boolean; invoice_no?: string };
  // (j) the same draft again — a second clerk, or the page re-submitted.
  let replayDraft: CaseRecord["replay_draft"] = { status: 0, code: null };
  if (draftRequest !== null) {
    const req = draftRequest as Request;
    const dh = { ...(await req.allHeaders()) };
    delete dh["content-length"];
    const d = await page.request.post(req.url(), { headers: dh, data: req.postData() ?? "" });
    const db = (await d.json().catch(() => ({}))) as { code?: string; error?: { code?: string } };
    replayDraft = { status: d.status(), code: db.code ?? db.error?.code ?? null };
  }
  const row: CaseRecord = {
    case: c.case,
    kind: c.kind,
    account: c.account,
    review,
    sent,
    replay_send: { status: again.status(), created: againBody.created ?? null, invoice_no: againBody.invoice_no ?? null },
    replay_draft: replayDraft,
    sent_text: sentText,
  };
  record(row);
  expectFooterAddsUp(row);
  expect(Number(sent.total).toFixed(2), "the Send answer's total is Review's").toBe(
    review.total.replace(/[$,]/g, ""),
  );
  expect(row.replay_send.status, "a second Send answers, and writes nothing").toBeLessThan(300);
  expect(row.replay_send.created, "a second Send is not a second bill").toBe(false);
  expect(row.replay_send.invoice_no, "a second Send answers the SAME bill").toBe(sent.invoice_no);
  expect(row.replay_draft.status, "a second draft for the same period is refused").toBeGreaterThanOrEqual(400);
  return row;
}

const label = (n: number): string => String(n);

// ── the eight cases, Six Rivers Utility ──────────────────────────────────────
//
// Prices (seed): water 0–5 kgal $4.00, 5–15 $6.50, base W-58 $8.00 · sewer 90% of
// water × $5.00 + $9.00 · trash each CART-35 $10 / CART-64 $12 / CART-96 $15 / DUMP-4 $85,
// base by size CART-64 $2 / CART-96 $3 / DUMP-4 $10 / CART-35 NOT PRICED · fire each
// FL-2 $12 / FL-4 $30 / FL-6 $60, base $0.00 · battery $3.00/kW, base BAT-5 $2 / BAT-10 $4 /
// BAT-15 NOT PRICED · solar $14.00/kW, base SOL-P2 $1 / SOL-P4 $2 / SOL-P8 $3 / SOL-P6 NOT
// PRICED. Residential: Local 2.00% on every usage and base line; CONN, deposit, RECON and
// TAMPER untaxed. On a part month the bases, the tier bounds and the per-container /
// per-line charges of trash and fire are × days/30 (B4.3, DEF-BIL-8566), and so is the kW
// charge of battery and solar (B4.3, B5 WE-16/GT-31, GT-15 amended 2026-08-11 "BOTH lines
// prorate"; DEF-BIL-8743 — the first pass priced it whole, following the code).

/** Every capacity line on Review carries its size breakdown (BR-BIL-1067). */
function expectBreakdowns(row: CaseRecord, expected: Record<string, string[]>): void {
  for (const [service, parts] of Object.entries(expected)) {
    const lines = row.review.lines.filter((l) => l.service.toLowerCase().startsWith(service));
    const text = lines.map((l) => l.breakdown).join(" | ");
    for (const part of parts) {
      expect.soft(text, `case ${row.case}: the ${service} line shows "${part}"`).toContain(part);
    }
  }
}

/** DEF-BIL-8733 — a catch-up or penalty prints trash and fire as ONE line a month
 *  (PO 2026-09-30, "per service"), never usage + base. */
function expectOneCountedLinePerMonth(row: CaseRecord, months: number): void {
  for (const service of ["Trash", "Fire"]) {
    const lines = row.review.lines.filter((l) => l.service === service);
    expect.soft(lines.length, `case ${row.case}: one ${service} line a month (DEF-BIL-8733)`).toBe(months);
  }
}

/** DEF-BIL-8734 — the footer adds up: Subtotal + Tax + One-time charges = Total. */
function expectFooterAddsUp(row: CaseRecord): void {
  const m = (t: string | null): number => (t ? Number(t.replace(/[$,]/g, "")) : 0);
  const sum = m(row.review.subtotal) + row.review.tax.reduce((a, t) => a + m(t.amount), 0) + m(row.review.one_time_charges);
  expect.soft(sum.toFixed(2), `case ${row.case}: the footer adds up (DEF-BIL-8734)`).toBe(m(row.review.total).toFixed(2));
}

test.describe(`J75 — every one-time bill kind for a six-service utility, at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(Number(process.env.E2E_TEST_TIMEOUT ?? "420000"));

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await signIn(page);
  });

  test("case 1 · interim, all six services on one account", async ({ page }) => {
    // Sep 1–30 (30/30). W-2001 500.0 → 512.0 = 12 kgal: 5 × 4.00 + 7 × 6.50 = 65.50 + base 8.00 = 73.50 ·
    // sewer 10.8 kgal × 5.00 = 54.00 + 9.00 = 63.00 · trash 2 × (15 + 3) + 1 × (10 + 0.00 unpriced) = 46.00 ·
    // fire 60 + 2 × 12 = 84.00 · battery 10 kW × 3 = 30 + 4 = 34.00 · solar 14 kW × 14 = 196 + 1 + 2 + 3 = 202.00
    // → 502.50 + 2.00% 10.05 = $512.55.
    await openKind(page, "interim");
    await pickAccount(page, "Ruiz", UNIT("1"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await toServices(page);
    await typeReadings(page, [{ meter: "W-2001", value: "512.0" }]);
    await expect(page.locator("[data-reading-row='W-2001']")).toContainText("Accepted", { timeout: 20_000 });
    await shot(page, "case1-interim-2-services");
    const row = await reviewSendAndReplay(page, {
      case: 1, kind: "interim", account: "Unit 1", name: "interim", expectTotal: "$512.55",
    });
    expectBreakdowns(row, {
      trash: ["96-gallon cart × 2", "35-gallon cart × 1"],
      fire: ['6" × 1', '2" × 2'],
      battery: ["10 kW × 1"],
      solar: ["2 kW × 1", "4 kW × 1", "8 kW × 1"],
    });
  });

  test("case 2 · interim, no reading in the period, estimated on step 2", async ({ page }) => {
    // W-2002 0.2 kgal a day to Aug 31 → Sep estimate 6.0 kgal: 20.00 + 6.50 + 8.00 = 34.50 · sewer 5.4 × 5 =
    // 27.00 + 9.00 = 36.00 · trash DUMP-4 85 + 10 = 95.00 · battery BAT-15 15 kW × 3 = 45 + base NOT PRICED 0.00
    // → 210.50 + 2.00% 4.21 = $214.71.
    await openKind(page, "interim");
    await pickAccount(page, "Okoro", UNIT("2"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await toServices(page);
    const reading = page.locator("[data-reading-row='W-2002']");
    await expect(reading).toBeVisible();
    await reading.getByRole("button", { name: "Estimate W-2002" }).click();
    await expect(reading).toContainText("Estimated", { timeout: 20_000 });
    await shot(page, "case2-interim-estimated-2-services");
    const row = await reviewSendAndReplay(page, {
      case: 2, kind: "interim", account: "Unit 2", name: "interim-estimated", expectTotal: "$214.71",
    });
    expectBreakdowns(row, { trash: ["4 cu-yd dumpster × 1"], battery: ["15 kW × 1"] });
  });

  test("case 3 · first bill from the account's move-in day, deposit and CONN", async ({ page }) => {
    // Sep 12–30 = 19/30. W-2003 100.0 → 108.6 = 8.6 kgal; bound 5 × 19/30 = 3.1667: 12.67 + 5.4333 × 6.50 = 35.32
    // + base 8 × 19/30 = 5.07 → 53.06 · sewer 7.74 × 5 = 38.70 + 9 × 19/30 = 5.70 → 44.40 · trash CART-64
    // (12 + 2) × 19/30 = 8.87 · fire FL-4 30 × 19/30 = 19.00 · battery BAT-5 5 kW × 3 × 19/30 = 9.50 + 2 × 19/30
    // = 1.27 → 10.77 · solar SOL-P6 6 kW × 14 × 19/30 = 53.20 + base NOT PRICED 0.00 → 189.30 + 2.00% 3.79 = 193.09
    // + deposit 150.00 + CONN 45.00 = $388.09 (DEF-BIL-8743; $425.11 with the kW charges whole).
    await openKind(page, "first");
    await pickAccount(page, "Mendes", UNIT("3"));
    await expect(page.locator("#period_start")).toHaveValue("2026-09-12", { timeout: 15_000 });
    await page.locator("#period_end").fill("2026-09-30");
    await toServices(page);
    await typeReadings(page, [{ meter: "W-2003", value: "108.6" }]);
    const moveIn = page.locator("[data-otb-panel=move-in]");
    await expect(moveIn).toContainText("CONN");
    await expect(moveIn).toContainText(/Deposit/);
    await shot(page, "case3-first-2-services");
    const row = await reviewSendAndReplay(page, {
      case: 3, kind: "first", account: "Unit 3", name: "first", expectTotal: "$388.09",
    });
    expectBreakdowns(row, { trash: ["64-gallon cart × 1"], fire: ['4" × 1'], battery: ["5 kW × 1"], solar: ["6 kW × 1"] });
  });

  test("case 4 · final, the deposit ($50.00) is LESS than owed", async ({ page }) => {
    // Sep 1–18 = 18/30 = 0.6. W-2004 400.0 → 404.2 = 4.2 kgal; bound 3: 12.00 + 1.2 × 6.50 = 7.80 + base 4.80 → 24.60
    // · sewer 3.78 × 5 = 18.90 + 5.40 → 24.30 · trash (15 + 3) × 0.6 = 10.80 · fire 12 × 0.6 = 7.20 · battery 30.00
    // × 0.6 = 18.00 + 4 × 0.6 = 2.40 → 20.40 · solar 4 kW × 14 × 0.6 = 33.60 + 2 × 0.6 = 1.20 → 34.80 → 122.10
    // + 2.00% 2.44 = $124.54 (DEF-BIL-8743; $159.63 with the kW charges whole); less the $50.00 deposit → Left
    // to pay $74.54.
    await openKind(page, "final");
    await pickAccount(page, "Patel", UNIT("4"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-18");
    await toServices(page);
    await typeReadings(page, [{ meter: "W-2004", value: "404.2" }]);
    const settlement = page.locator("[data-otb-panel=settlement]");
    await expect(settlement).toBeVisible({ timeout: 20_000 });
    await expect(settlement).toContainText(/Left to pay/);
    await expect.soft(settlement).toContainText("$74.54");
    const collect = settlement.getByRole("radio", { name: "Collect" });
    if ((await collect.count()) > 0) await collect.check({ force: true });
    await shot(page, "case4-final-deposit-less-2-services");
    const row = await reviewSendAndReplay(page, {
      case: 4, kind: "final", account: "Unit 4", name: "final-deposit-less", expectTotal: "$124.54",
    });
    expectBreakdowns(row, { trash: ["96-gallon cart × 1"], fire: ['2" × 1'], battery: ["10 kW × 1"], solar: ["4 kW × 1"] });
  });

  test("case 5 · final, the deposit ($200.00) is MORE than owed, Refund due $75.46", async ({ page }) => {
    // Unit 4's arithmetic on Unit 5's equipment → $124.54; $200.00 − $124.54 = $75.46.
    await openKind(page, "final");
    await pickAccount(page, "Brooks", UNIT("5"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-18");
    await toServices(page);
    await typeReadings(page, [{ meter: "W-2005", value: "404.2" }]);
    const settlement = page.locator("[data-otb-panel=settlement]");
    await expect(settlement).toBeVisible({ timeout: 20_000 });
    await expect(settlement).toContainText("Refund due");
    await expect.soft(settlement).toContainText("$75.46");
    await shot(page, "case5-final-deposit-more-2-services");
    const row = await reviewSendAndReplay(page, {
      case: 5, kind: "final", account: "Unit 5", name: "final-deposit-more", expectTotal: "$124.54",
    });
    expectBreakdowns(row, { trash: ["96-gallon cart × 1"], fire: ['2" × 1'], battery: ["10 kW × 1"], solar: ["4 kW × 1"] });
  });

  test("case 6 · catch-up Jul–Sep, every month read", async ({ page }) => {
    // Jul 7.0 kgal: 20 + 13 = 33 + 8 = 41.00, sewer 6.3 × 5 = 31.50 + 9 = 40.50 · Aug 8.0: 39.50 + 8 = 47.50, sewer
    // 36.00 + 9 = 45.00 · Sep 7.5 (typed 228.5): 36.25 + 8 = 44.25, sewer 33.75 + 9 = 42.75 → 261.00; each month
    // trash 18 + fire 12 + battery 5 kW 15 + 2 + solar 2 kW 28 + 1 = 76.00 × 3 = 228.00 → 489.00 + 2.00% 9.78 = $498.78.
    await openKind(page, "backbill");
    await pickAccount(page, "Adeyemi", UNIT("6"));
    await fillPeriods(page, [
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
      ["2026-09-01", "2026-09-30"],
    ]);
    await page.locator("#reason_code").selectOption("MISSED");
    await toServices(page);
    await typeLastPeriod(page, [["W-2006", "228.5"]]);
    await shot(page, "case6-catch-up-2-services");
    const row = await reviewSendAndReplay(page, {
      case: 6, kind: "backbill", account: "Unit 6", name: "catch-up", expectTotal: "$498.78",
    });
    expectBreakdowns(row, { trash: ["96-gallon cart × 1"], fire: ['2" × 1'], battery: ["5 kW × 1"], solar: ["2 kW × 1"] });
    expectOneCountedLinePerMonth(row, 3);
  });

  test("case 7 · penalty / theft Jul–Sep, TAMPER $250.00, Approved by recorded", async ({ page }) => {
    // Jul 10.0 kgal: 52.50 + 8 = 60.50, sewer 45 + 9 = 54.00 · Aug 11.0: 59.00 + 8 = 67.00, sewer 49.50 + 9 = 58.50 ·
    // Sep 9.0: 46.00 + 8 = 54.00, sewer 40.50 + 9 = 49.50 → 343.50; each month trash 12 + 2 = 14, fire 30, battery
    // 30 + 4 = 34, solar 6 kW 84 + 1 + 2 = 87 → 165 × 3 = 495.00 → 838.50 + 2.00% 16.77 + TAMPER 250.00 = $1,105.27.
    await openKind(page, "penalty");
    await pickAccount(page, "Rao", UNIT("7"));
    await fillPeriods(page, [
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
      ["2026-09-01", "2026-09-30"],
    ]);
    await page.locator("#reason_code").selectOption("TAMPER");
    const tamper = await page.locator("#charge_code option", { hasText: "Tamper" }).first().getAttribute("value");
    await page.locator("#charge_code").selectOption(tamper ?? "TAMPER");
    await toServices(page);
    await page.locator("#otb-evidence").fill("Bypass found at meter W-2007");
    await page.locator("#otb-approved-by").selectOption({ label: "Priya Shah" });
    await shot(page, "case7-penalty-2-services");
    const row = await reviewSendAndReplay(page, {
      case: 7, kind: "penalty", account: "Unit 7", name: "penalty", expectTotal: "$1,105.27",
    });
    expectBreakdowns(row, { trash: ["64-gallon cart × 1"], fire: ['4" × 1'], battery: ["10 kW × 1"], solar: ["2 kW × 1", "4 kW × 1"] });
    expectOneCountedLinePerMonth(row, 3);
  });

  test("case 8 · fee: reconnection (RECON), untaxed in this utility", async ({ page }) => {
    // RECON $75.00, the signup's own code, not taxable → $75.00.
    await openKind(page, "fee");
    await pickAccount(page, "Lind", UNIT("8"));
    const recon = await page.locator("#charge_code option", { hasText: "Reconnection" }).first().getAttribute("value");
    await page.locator("#charge_code").selectOption(recon ?? "RECON");
    await toServices(page);
    await page.locator("#otb-note").fill("Reconnected after payment");
    await shot(page, "case8-fee-2-services");
    await reviewSendAndReplay(page, { case: 8, kind: "fee", account: "Unit 8", name: "fee", expectTotal: "$75.00" });
  });
});
