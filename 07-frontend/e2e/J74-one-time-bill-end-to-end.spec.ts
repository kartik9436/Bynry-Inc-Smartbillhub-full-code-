// ── Trace ──────────────────────────────────────────────
// Journey:  J74 — the one-time bill, end to end for a clerk, eight cases, each
//           BILLED AND SENT in a browser and then CHECKED IN THE DATABASE
//           · 08-qa/01-e2e/journeys/J74-one-time-bill-end-to-end.md
// Request:  PO 2026-09-30, verbatim: "for every one time bill interim, first
//           bill, final bill - all 6 or 7 cases, generate end to end bill and
//           send it - it should work for clerk end to end - take 7 or 8 cases
//           and run it end to end - bill should be generated check in database"
// Stories:  US-BIL-010, US-BIL-011, US-BIL-012, US-BIL-013, US-BIL-014,
//           US-BIL-032, US-BIL-033
// Seed:     10-scripts/seed_j70_one_time_bill.py (on top of `manage.py seed_demo`)
// Verifier: 10-scripts/verify_j74_one_time_bill.py (reads the database this
//           spec wrote, and the JSON it leaves beside the screenshots)
// ───────────────────────────────────────────────────────
//
// HOW TO RUN IT — on a FRESH database (migrate + seed_demo + the J70 seed); a
// second pass over the same database meets its own bills as "Already billed":
//
//   E2E_BASE_URL=http://127.0.0.1:<web> npx playwright test e2e/J74-one-time-bill-end-to-end.spec.ts
//   DATABASE_URL=… python 10-scripts/verify_j74_one_time_bill.py
//
// Every case walks the clerk's four steps — Account → Services → Review →
// Send, ticking all five confirmations — and leaves a Sent screenshot. After
// Send it replays the two writes a double-click or a retry would repeat: the
// SAME `POST …/send` (must answer the same bill, `created: false`) and the
// SAME `POST /billing/one-time` draft (must be refused — already billed). What
// Review showed, the Send answer and both replays go to
// `08-qa/screens/one-time-bill-e2e-j74/j74-results.json` for the verifier.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Locator, Page, Request } from "@playwright/test";

import { expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const SHOTS = "../08-qa/screens/one-time-bill-e2e-j74";
const RESULTS = `${SHOTS}/j74-results.json`;
const UNIT = (letter: string) => new RegExp(`Unit ${letter}(?:Active|Closed|Pending|\\s|$)`);

// ── the record each case leaves for the database verifier ────────────────────

interface ReviewLine {
  service: string;
  meter: string;
  charge: string;
  quantity: string;
  rate: string;
  amount: string;
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
  return { lines, subtotal, tax, one_time_charges: oneTime, total, groups };
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

// ── the eight cases ──────────────────────────────────────────────────────────

test.describe(`J74 — eight one-time bills, end to end, at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(Number(process.env.E2E_TEST_TIMEOUT ?? "420000"));

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await signIn(page);
  });

  test("case 1 · interim: two water meters, electric, sewer at 40%, one cart; readings typed on step 2", async ({
    page,
  }) => {
    // Expected (seed figures, Sep 1–30): water 2 × (5 × $3.25 + 1.1 × $4.50 + $8.00) = $58.40 ·
    // electric 600 kWh × $0.1245 = $74.70, base $0.00 · trash $15.00 + $3.00 · sewer 40% × 12.2 kgal
    // = 4.88 × $5.00 = $24.40 + $6.00 → $181.50; usage and base are taxable (B4.2) and this
    // institutional account meets Local 2.00% only → $3.63 → $185.13.
    // BR-BIL-1066 (PO 2026-10-01, "A · Cut down (10/30)"): an interim base is cut down by
    // days over the account's own cycle. Sep 1–30 on J70-MONTHLY's 30-day September is
    // 30/30 = 1, so the $8.00 water bases, the $15.00 cart, the $3.00 trash base and the
    // $6.00 sewer base stay whole and the tier bound stays 5 kgal: $185.13 does not move.
    await openKind(page, "interim");
    await pickAccount(page, "Alvarez", UNIT("A"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await toServices(page);
    await typeReadings(page, [
      { meter: "W-10442", value: "488.4" },
      { meter: "W-10443", value: "136.7" },
      { meter: "E-55120", value: "19020" },
    ]);
    await expect(page.locator("[data-reading-row='W-10442']")).toContainText("Accepted", { timeout: 20_000 });
    await shot(page, "case1-interim-2-services");
    await reviewSendAndReplay(page, {
      case: 1,
      kind: "interim",
      account: "Unit A",
      name: "interim",
      expectTotal: "$185.13",
    });
  });

  test("case 2 · interim: one service, no reading in the period, estimated on step 2", async ({ page }) => {
    // Expected: W-10460 read 0.2 kgal a day since Jun 30 (6.2 kgal in July, 6.2 in August); the
    // meter's own estimate for Sep 1–30 is 6.0 kgal → water 5 × $3.25 + 1.0 × $4.50 + $8.00 = $28.75;
    // sewer follows water on this plan (the %-of-service exception, PO 2026-09-30): 2.4 kgal × $5.00
    // + $6.00 = $18.00 → $46.75 + 2.00% $0.94 = $47.69. (Stated $29.33 before the first run, which
    // left sewer out — the hand figure's own error, corrected here.) BR-BIL-1066: Sep 1–30 of a
    // 30-day cycle is 30/30 = 1, so the $8.00 and $6.00 bases stay whole — $47.69 does not move.
    await openKind(page, "interim");
    await pickAccount(page, "Ortiz", UNIT("I"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await toServices(page);
    const row = page.locator("[data-reading-row='W-10460']");
    await expect(row).toBeVisible();
    // The clerk types nothing: the meter is to be ESTIMATED (DEF-BIL-8562).
    const estimate = row.getByRole("button", { name: "Estimate W-10460" });
    await expect(estimate, "step 2 offers to estimate a meter with no reading (DEF-BIL-8562)").toBeVisible();
    await estimate.click();
    await expect(row).toContainText("Estimated", { timeout: 20_000 });
    await shot(page, "case2-interim-estimated-2-services");
    await reviewSendAndReplay(page, {
      case: 2,
      kind: "interim",
      account: "Unit I",
      name: "interim-estimated",
      expectTotal: "$47.69",
    });
  });

  test("case 3 · first bill: move-in date from the account, move-in reading typed, deposit and CONN", async ({
    page,
  }) => {
    // Expected (Sep 12–30, 19 of 30 days): W-10442C 479.8 → 488.4 = 8.6 kgal, W-10443C 128.9 →
    // 136.7 = 7.8 kgal, E-55120C 18,500 → 19,020 = 520 kWh. DEF-BIL-8331 (2.416.3): a first bill
    // prorates from the move-in day — Sep 12–30 is 19 of the cycle's 30 days, so f = 19/30:
    //   water tier bound 5 × 19/30 = 3.1667 kgal: W-10442C 3.1667 × $3.25 = $10.29 + 5.4333 × $4.50 =
    //   $24.45 → $34.74; W-10443C $10.29 + 4.6333 × $4.50 = $20.85 → $31.14; bases 2 × ($8.00 × 19/30 =
    //   $5.07) = $10.14 · electric 520 × $0.1245 = $64.74 · trash cart $15.00 × 19/30 = $9.50 (DEF-BIL-8566,
    //   PO 2026-10-01: the cart prorates like the base) + $3.00 × 19/30 = $1.90 · sewer 40% × 16.4 = 6.56
    //   kgal × $5.00 = $32.80 + $6.00 × 19/30 = $3.80 → $188.76 + 2.00% $3.78 = $192.54, + deposit $150.00
    //   + CONN $45.00 (neither taxed) → $387.54 (was $393.15 with the cart whole, $397.82 bases whole).
    await openKind(page, "first");
    await pickAccount(page, "Alvarez", UNIT("C"));
    await expect(page.locator("#period_start")).toHaveValue("2026-09-12", { timeout: 15_000 });
    await page.locator("#period_end").fill("2026-09-30");
    await toServices(page);
    await typeReadings(page, [
      { meter: "W-10443C", value: "128.9", moveIn: true },
      { meter: "W-10442C", value: "488.4" },
      { meter: "W-10443C", value: "136.7" },
      { meter: "E-55120C", value: "19020" },
    ]);
    const moveIn = page.locator("[data-otb-panel=move-in]");
    await shot(page, "case3-first-2-services");
    // DEF-BIL-8563 — from the account's own move-in date the move-in reading of
    // that day is not found, nothing prices and Move-in charges stay $0.00.
    await expect(moveIn, "DEF-BIL-8563: the move-in reading on the move-in day opens the bill").toContainText("CONN");
    await expect(moveIn).toContainText(/Deposit/);
    await reviewSendAndReplay(page, {
      case: 3,
      kind: "first",
      account: "Unit C",
      name: "first",
      expectTotal: "$387.54",
    });
  });

  test("case 4 · final: the deposit ($50.00) is LESS than owed, a balance stays due", async ({ page }) => {
    // Expected (Sep 1–18 = 18 of the cycle's 30 days, f = 18/30 = 0.6; DEF-BIL-8331/8333): water
    // 2.7 kgal $8.78 + 2.4 kgal $7.80 (both under the 5 × 0.6 = 3 kgal bound) + bases 2 × ($8.00 × 0.6 =
    // $4.80) · electric 280 kWh $34.86 · trash cart $15.00 × 0.6 = $9.00 (DEF-BIL-8566, PO 2026-10-01)
    // + $3.00 × 0.6 = $1.80 · sewer 2.04 kgal $10.20 + $6.00 × 0.6 = $3.60 → $85.64 + 2.00% $1.71 = $87.35
    // (was $93.47 with the cart whole, $103.67 bases whole); less the $50.00 deposit → Left to pay $37.35.
    await openKind(page, "final");
    await pickAccount(page, "Okafor", UNIT("J"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-18");
    await toServices(page);
    await typeReadings(page, [
      { meter: "W-10442J", value: "485.0" },
      { meter: "W-10443J", value: "133.0" },
      { meter: "E-55120J", value: "18700" },
    ]);
    const settlement = page.locator("[data-otb-panel=settlement]");
    await expect(settlement).toBeVisible({ timeout: 20_000 });
    await expect(settlement).toContainText(/Left to pay/);
    await expect(settlement).toContainText("$37.35");
    const collect = settlement.getByRole("radio", { name: "Collect" });
    if ((await collect.count()) > 0) await collect.check({ force: true });
    await shot(page, "case4-final-deposit-less-2-services");
    await reviewSendAndReplay(page, {
      case: 4,
      kind: "final",
      account: "Unit J",
      name: "final-deposit-less",
      expectTotal: "$87.35",
    });
  });

  test("case 5 · final: the deposit ($150.00) is MORE than owed ($87.35), Refund due $62.65", async ({ page }) => {
    // The same 18/30 arithmetic as case 4 on Unit D's meters → $87.35; $150.00 − $87.35 = $62.65.
    await openKind(page, "final");
    await pickAccount(page, "Alvarez", UNIT("D"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-18");
    await toServices(page);
    await typeReadings(page, [
      { meter: "W-10442D", value: "485.0" },
      { meter: "W-10443D", value: "133.0" },
      { meter: "E-55120D", value: "18700" },
    ]);
    const settlement = page.locator("[data-otb-panel=settlement]");
    await expect(settlement).toBeVisible({ timeout: 20_000 });
    await expect(settlement).toContainText("Refund due");
    await expect(settlement).toContainText("$62.65");
    await shot(page, "case5-final-deposit-more-2-services");
    await reviewSendAndReplay(page, {
      case: 5,
      kind: "final",
      account: "Unit D",
      name: "final-deposit-more",
      expectTotal: "$87.35",
    });
  });

  test("case 6 · catch-up Jul–Sep: split at the Jul 16 price change, one stretch never read", async ({ page }) => {
    await openKind(page, "backbill");
    await pickAccount(page, "Alvarez", UNIT("E"));
    await fillPeriods(page, [
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
      ["2026-09-01", "2026-09-30"],
    ]);
    await page.locator("#reason_code").selectOption("MISSED");
    await toServices(page);
    await typeLastPeriod(page, [
      ["W-10442E", "482.3"],
      ["W-10443E", "130.6"],
      ["E-55120E", "18420"],
    ]);
    await expect(page.locator("[data-otb-panel=periods]")).toContainText(/07\/16|Jul/);
    await expect(page.locator("[data-wizard=content]")).toContainText("Estimated");
    await shot(page, "case6-catch-up-2-services");
    await reviewSendAndReplay(page, {
      case: 6,
      kind: "backbill",
      account: "Unit E",
      name: "catch-up",
      // Hand-priced month by month: $710.06 on the J70 walk, which bills sewer for
      // August and September on the two months' water TWICE ($59.39 each where the
      // pair is $59.39) — DEF-BIL-8560. Without it: $636.75 + 2.00% $12.74 = $649.49 with the cart
      // whole in each July half; DEF-BIL-8566 (PO 2026-10-01) prorates it like the base, 15/31 × $15.00
      // = $7.26 + 16/31 × $15.00 = $7.74 → $621.75 + 2.00% $12.44 = $634.19 (10-scripts/j74_reprice_case6.py).
      expectTotal: "$634.19",
    });
  });

  test("case 7 · penalty / theft: assessed usage, a tamper charge, Approved by recorded", async ({ page }) => {
    await openKind(page, "penalty");
    await pickAccount(page, "Alvarez", UNIT("F"));
    await fillPeriods(page, [
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
      ["2026-09-01", "2026-09-30"],
    ]);
    await page.locator("#reason_code").selectOption("TAMPER");
    const tamper = await page.locator("#charge_code option", { hasText: "Tamper" }).first().getAttribute("value");
    await page.locator("#charge_code").selectOption(tamper ?? "TAMPER");
    await toServices(page);
    await page.locator("#otb-evidence").fill("Bypass pipe found at meter W-10442F");
    await page.locator("#otb-approved-by").selectOption({ label: "Dana Whitfield" });
    await shot(page, "case7-penalty-2-services");
    await reviewSendAndReplay(page, {
      case: 7,
      kind: "penalty",
      account: "Unit F",
      name: "penalty",
      // Hand-priced month by month (Jul split 15/16 at the price change; Aug 16.3 + 9.6 kgal,
      // 1,020 kWh; Sep 14.2 + 9.3 kgal, 890 kWh): $1,149.85 of charges incl. TAMPER $250.00
      // (not taxed) + 2.00% of $899.85 = $18.00 → $1,167.85 with the cart whole in each July half.
      // DEF-BIL-8566 (PO 2026-10-01): $7.26 + $7.74 for July's cart → $884.85 taxable + 2.00% $17.70
      // + TAMPER $250.00 = $1,152.55. DEF-BIL-8560 billed $1,268.62.
      expectTotal: "$1,152.55",
    });
  });

  test("case 8 · fee: a taxable reconnection fee (RECON)", async ({ page }) => {
    // Expected: RECON $75.00, taxable; the institutional account meets Local 2.00% only → $1.50 → $76.50.
    // The bill is dated the day it is raised (its period is that day at both ends); the verifier
    // checks it against the run's bill date and the issue day, never a fixed 30 September.
    await openKind(page, "fee");
    await pickAccount(page, "Robert", UNIT("H"));
    const recon = await page.locator("#charge_code option", { hasText: "Reconnection" }).first().getAttribute("value");
    await page.locator("#charge_code").selectOption(recon ?? "RECON");
    await toServices(page);
    await page.locator("#otb-note").fill("Reconnected Sep 30 after payment");
    await shot(page, "case8-fee-2-services");
    await reviewSendAndReplay(page, { case: 8, kind: "fee", account: "Unit H", name: "fee", expectTotal: "$76.50" });
  });
});
