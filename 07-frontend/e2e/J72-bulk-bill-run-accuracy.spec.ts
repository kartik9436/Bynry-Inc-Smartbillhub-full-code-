// ── Trace ──────────────────────────────────────────────
// Tracker:  BULK-CHG-56 (the clerk acceptance walk, A1–A6: E14, E16)
// Journey:  J72 — the bulk bill run · 08-qa/01-e2e/journeys/J72-bulk-bill-run-redesign.md
//           (§ HOW THIS WALK IS ORGANISED — BY THE CLERK'S 22 ACCEPTANCE CHECKS)
// Checks:   A1–A6 of 04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md
//           (the ACCURACY half; the sibling J72-bulk-bill-run.spec.ts walks E1–E11)
// Plan:     15-bulk-bill-run-build-plan.md E14 (the accuracy walk) · T8 (two months)
// Rulings:  16-check-decisions-next-bill.md §1 (estimate true-up, DEF-BIL-8280) and
//           §2 (the five fixed-charge cases, PO 2026-09-30)
// Seed:     `manage.py seed_j72_bulk_run --month-two` on top of `seed_demo`, PostgreSQL
// ───────────────────────────────────────────────────────
//
// ONE TEST PER CHECK, NAMED BY ITS ID, RUN IN FILE ORDER (`--workers=1`) on a
// database reset to the seeded snapshot before each width:
//
//   E2E_VIEWPORT=1440 E2E_BASE_URL=… npx playwright test e2e/J72-bulk-bill-run-accuracy.spec.ts --workers=1
//   (reset the database)
//   E2E_VIEWPORT=1280 E2E_BASE_URL=… npx playwright test e2e/J72-bulk-bill-run-accuracy.spec.ts --workers=1
//
// A1 WALKS SEPTEMBER, because A1 is the one check that needs every step: it reads
// the counts off Scope, Check, Sign off and Send, answers every decision the way
// the rulings below need, and sends. It saves what it READ (the screen figures
// and, at Sign off, each draft's total from the same API the screen reads) in a
// state file, so A2, A3, A4 and A6 judge the SENT run against what the clerk was
// shown — a sent run cannot re-open its Sign off. A5 then walks OCTOBER on the
// same accounts. Checks are soft (`expect.soft`) inside a walk so one wrong
// figure never stops the walk that the later checks depend on.
//
// SEPTEMBER'S ANSWERS, and which ruling each one sets up for October (A5):
//   AC-2026-00003  no reading      → Estimate the reading   → Oct true-up: 7 kgal
//                  (refused today, DEF-BIL-8551 → the walk HOLDS it: Oct bills Sep 1 – Oct 31, one base)
//   AC-2026-00009  gap             → Look into it (held)    → Oct: one base, Aug 1 – Oct 31
//   AC-2026-00010  overlap (whole) → Look into it (held)    → A2: never billed twice
//   AC-2026-00011  standing only   → Waive, with a reason   → nothing carried
//                  (refused today, DEF-BIL-8552 → the walk INCLUDES it)
//   AC-2026-00007  paid after cut  → Apply to this bill
//   AC-2026-00008  plan instalment → Skip                   → plan still 7 × $45, one month longer
//   AC-2026-00006  held in August  → (no tag)               → Sep: one base, Aug 1 – Sep 30
// Between the runs the walk sends a ONE-TIME interim bill for AC-2026-00001,
// Oct 1 – Oct 17, so October overlaps it: Oct 18 – 31, base $8.00 × 14 days over
// the run's days. The PO's worked figure is a 30-day run ($3.73); October has 31
// days, so the same rule reads $3.61 (B4.3's service_days / cycle_days).
//
// A check the bulk lane's unmerged fixes cannot pass yet is `test.fail(…)` naming
// the defect or task — never skipped — so the day it lands Playwright reports
// "expected to fail but passed" (hard-won law 2's hold expiry).
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
// Outside test-results/, which Playwright empties at the start of every run, so
// A2–A6 can be re-run on their own against the run A1 sent.
const STATE = `${process.env.E2E_STATE_DIR ?? "/tmp"}/j72-accuracy-${WIDTH}.json`;
const CYCLE = /J72-RIVERSIDE/;
const API = () => `/api/${tenant()}`;

/** The eleven accounts the J72 seed bills (unit 112 is vacant: nobody to bill). */
const ACCOUNTS = Array.from({ length: 11 }, (_, i) => `AC-2026-${String(i + 1).padStart(5, "0")}`);
const ACC = (n: number) => ACCOUNTS[n - 1];

/** Why a check is expected to fail today; the day the fix lands the case reports "expected to fail but passed". */
// Released 2026-09-30 by the bulk-run-rest lane (2.413.0): A1 (DEF-BIL-8554,
// DEF-BIL-8474, DEF-BIL-8220, DEF-BIL-8416), A3 (DEF-BIL-8553, DEF-BIL-8416),
// A6 (DEF-BIL-8555), and Estimate / Waive on Check (DEF-BIL-8551, DEF-BIL-8552).

/**
 * THE SERVED TAG CODES (DEF-BIL-8216): the screen reads the server's grouping,
 * so a tag is its engine code. Under the served taxonomy no plan and a
 * disputed reading are DECISIONS (`unit_has_no_plan`,
 * `account_held_by_disputed_read`), so on this seed nothing BLOCKS: `00004` and
 * `00005` wait on a decision the walk leaves open in September.
 */
const TAG = {
  noReading: "missing_read",
  gapOrOverlap: "billing_continuity",
  standingChargesOnly: "base_only_billing",
  paidAfterCutoff: "paid_after_cutoff",
  planInstalmentDue: "plan_instalment_due",
} as const;

/** September's estimate for 00003: the true-up month needs Aug 158 → Oct 173
 *  = 15 kgal, 8 of them billed in September, so October bills 7 (§1). */
const SEPTEMBER_ESTIMATE = "8";

// ── state shared between the checks (a file: a failed test restarts the worker) ──

interface Figures {
  runId?: string;
  runNo?: string;
  scope?: Record<string, number>;
  check?: Record<string, number>;
  price?: number;
  signOff?: Record<string, number | null>;
  signOffTotal?: string;
  drafts?: Record<string, { total: string; invoice_id: string; period: string }>;
  sendButton?: number;
  sent?: { sent: number; notSent: number; total: string };
  notInRun?: { account: string; kind: string }[];
  octoberUnanswered?: string[];
  decided?: { account: string; answer: string; at: string }[];
  october?: { runId?: string };
  estimateRefused?: boolean;
  waiveRefused?: boolean;
}

function load(): Figures {
  try {
    return JSON.parse(readFileSync(STATE, "utf8")) as Figures;
  } catch {
    return {};
  }
}
function save(figures: Figures): void {
  writeFileSync(STATE, JSON.stringify(figures, null, 2));
}

// ── helpers ──────────────────────────────────────────────────────────────────

const num = (text: string | null): number | null => {
  const m = /-?\d[\d,]*/.exec(text ?? "");
  return m === null ? null : Number(m[0].replace(/,/g, ""));
};

/** A row of served JSON, typed as the fields the walk reads (absent ones read as undefined). */
interface Row {
  [field: string]: unknown;
  id: string;
  account_no: string;
  account_id: string;
  bill_run_id: string;
  invoice_no: string;
  status: string;
  total: string;
  period_start: string;
  period_end: string;
  kind: string;
  description: string;
  quantity: string | null;
  unit: string | null;
  amount: string;
  due_date: string;
  reason: string;
  message_key: string;
}
interface Body extends Row {
  results?: Row[];
  items?: Row[];
  lines?: Row[];
  run_id?: string;
  live_plan?: { installments?: Row[] } | null;
  plans?: { installments?: Row[] }[];
}

async function getJson(page: Page, path: string): Promise<Body> {
  const response = await page.request.get(`${API()}${path}`);
  expect(response.ok(), `GET ${path} → ${response.status()} ${await response.text()}`).toBe(true);
  return response.json();
}

function rowsOf(body: Body | Row[]): Row[] {
  if (Array.isArray(body)) return body;
  return body.results ?? body.items ?? (Array.isArray(body.data) ? (body.data as Row[]) : []);
}

async function runInvoices(page: Page, runId: string): Promise<Row[]> {
  return rowsOf(await getJson(page, `/invoices?f.bill_run_id=${runId}&per=200`));
}

async function invoiceLines(page: Page, invoiceId: string): Promise<Row[]> {
  const body = await getJson(page, `/invoices/${invoiceId}`);
  return body.lines ?? [];
}

/** A BASE (fixed) charge line, as the invoice read serves it (`kind`). */
const isBase = (line: Row) => line.kind === "base";

async function openRun(page: Page, query = ""): Promise<void> {
  await page.goto(`/${tenant()}/billing/run${query}`);
  await expect(page.locator("[data-screen=bulk-bill-run]")).toBeVisible({ timeout: 30_000 });
}

async function onStep(page: Page, label: string, timeout = 30_000): Promise<boolean> {
  try {
    await expect(page.locator("[data-wizard=rail] [aria-current=step]")).toContainText(label, {
      timeout,
    });
    return true;
  } catch {
    return false;
  }
}

async function fillScope(
  page: Page,
  s: { name: string; start: string; end: string; bill: string },
): Promise<void> {
  await page.locator("#label").fill(s.name);
  const cycle = page.locator("#cycle_id");
  const option = cycle.locator("option").filter({ hasText: CYCLE });
  await expect(option, "the seeded Riverside cycle is offered").toHaveCount(1, { timeout: 20_000 });
  await cycle.selectOption({ value: (await option.getAttribute("value")) ?? "" });
  await page.locator("#period_start").fill(s.start);
  await page.locator("#period_end").fill(s.end);
  await page.locator("#bill_date").fill(s.bill);
  await page.locator("#due_days").fill("21");
  const template = page.locator("#template_id");
  await expect(template.locator("option").nth(1)).toBeAttached({ timeout: 20_000 });
  await template.selectOption({ index: 1 });
  await page.waitForTimeout(1500); // the preview's debounce + round trip
}

async function scopeFigures(page: Page): Promise<Record<string, number>> {
  const covers = page.locator("[data-run-facts=covers]");
  await expect(covers.locator("[data-run-fact=accounts]")).toBeVisible({ timeout: 20_000 });
  const out: Record<string, number> = {};
  for (const id of ["units", "accounts", "regular", "master"]) {
    const text = await covers.locator(`[data-run-fact=${id}]`).innerText();
    out[id] = num(text.split("\n").find((l) => /^\d/.test(l.trim())) ?? text) ?? NaN;
  }
  const warning = await page
    .locator("[data-run-problems=warning]")
    .innerText()
    .catch(() => "");
  out.nobodyUnits = num(/(\d+) units? have nobody/.exec(warning)?.[1] ?? "0") ?? 0;
  return out;
}

async function tile(page: Page, label: RegExp): Promise<number | null> {
  const button = page.getByRole("button", { name: label });
  if ((await button.count()) === 0) return null;
  return num((await button.first().innerText()).replace(/^\D+/, ""));
}

async function checkFigures(page: Page): Promise<Record<string, number>> {
  await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 120_000 });
  // The saved Check, not a read taken while it ran (DEF-BIL-8417).
  await expect(page.locator("[data-screen=bulk-bill-run]")).toContainText(/Checked [1-9]\d* accounts/i, {
    timeout: 60_000,
  });
  const out: Record<string, number> = {};
  const checked = await page.locator("[data-screen=bulk-bill-run]").innerText();
  out.checked = num(/CHECKED (\d+) ACCOUNTS/i.exec(checked)?.[1] ?? null) ?? NaN;
  out.blocked = (await tile(page, /^Blocked accounts \d+$/)) ?? NaN;
  out.decision = (await tile(page, /^Need a decision \d+$/)) ?? NaN;
  out.ready = (await tile(page, /^Ready accounts \d+$/)) ?? NaN;
  return out;
}

async function openTag(page: Page, tag: string): Promise<void> {
  const row = page.locator(`[data-tag=${tag}]`).first();
  await expect(row, `tag ${tag} is listed`).toBeVisible({ timeout: 30_000 });
  await row.click();
  await expect(page.locator(`[data-tag-pane=${tag}]`)).toBeVisible({ timeout: 15_000 });
}

/** Answer ONE row by its own select; a Waive then asks for a reason. */
async function decide(
  page: Page,
  tag: string,
  account: string,
  answer: string,
  reason?: string,
  timeout = 20_000,
): Promise<void> {
  await openTag(page, tag);
  const pane = page.locator(`[data-tag-pane=${tag}]`);
  const row = pane.locator("tr", {
    has: page.getByRole("combobox", { name: `Decide for ${account}` }),
  });
  await pane
    .getByRole("combobox", { name: `Decide for ${account}` })
    .selectOption({ label: answer });
  if (answer === "Estimate") {
    const box = row.locator("[data-estimate-box]");
    await expect(box, "Estimate asks how much").toBeVisible({ timeout: 10_000 });
    await box.getByLabel("Usage").fill(SEPTEMBER_ESTIMATE);
    if ((await box.getByLabel("Unit").inputValue()) === "") await box.getByLabel("Unit").fill("kgal");
    await box.getByRole("button", { name: "Record this estimate" }).click();
  }
  if (reason !== undefined) {
    const box = row.locator("[data-reason-box]");
    await expect(box, `${answer} asks for a reason`).toBeVisible({ timeout: 10_000 });
    await box.locator("input").fill(reason);
    await box.getByRole("button").first().click();
  }
  await expect(
    row.locator("[data-decision=answered]"),
    `${account} answered ${answer}`,
  ).toBeVisible({
    timeout,
  });
}

/** The tag a row sits under (its served code since DEF-BIL-8471/8216). Waits
 *  for the tag's page to arrive before looking (DEF-BIL-8419). */
async function tagHolding(page: Page, candidates: string[], account: string): Promise<string> {
  for (const tag of candidates) {
    const row = page.locator(`[data-tag=${tag}]`);
    if ((await row.count()) === 0) continue;
    await row.first().click();
    const pane = page.locator(`[data-tag-pane=${tag}]`);
    await expect(pane.locator("[data-row-account], [role=status]").first()).toBeVisible({
      timeout: 15_000,
    });
    const box = pane.getByRole("combobox", {
      name: `Decide for ${account}`,
    });
    if ((await box.count()) > 0) return tag;
  }
  throw new Error(`${account} is under none of ${candidates.join(", ")}`);
}

async function whoIsBilled(page: Page): Promise<Record<string, number | null>> {
  const table = page.locator("[data-run-table=who-accounts]");
  await expect(table).toBeVisible({ timeout: 30_000 });
  const out: Record<string, number | null> = {};
  for (const tr of await table.locator("tbody tr").all()) {
    const label = (await tr.locator("th").innerText()).trim();
    out[label] = num(await tr.locator("td[data-num]").innerText());
  }
  return out;
}

const pick = (m: Record<string, number | null>, re: RegExp): number | null => {
  const key = Object.keys(m).find((k) => re.test(k));
  return key === undefined ? null : m[key];
};

/** Tick the five confirmations, Sign off, tick the final one, Send. */
async function signOffAndSend(page: Page): Promise<number> {
  const confirmations = page.getByRole("group", { name: "Sign off" });
  for (const name of [
    "Bills follow our rules and rates",
    "Email customers have agreed to e-bills",
    "SMS customers have agreed to texts",
    "Autopay customers charged on due date",
    "I checked the totals",
  ]) {
    await confirmations.getByRole("checkbox", { name }).check();
  }
  const actions = page.locator("[data-wizard=actions]");
  await actions.getByRole("button", { name: "Sign off", exact: true }).click();
  expect(await onStep(page, "Send", 60_000), "Sign off opens Send").toBe(true);
  await page
    .getByRole("region", { name: "Send" })
    .getByRole("checkbox", { name: "I checked the totals" })
    .check();
  const send = actions.getByRole("button", { name: /^Send \d+ bills?$/ });
  const n = num(await send.innerText()) ?? NaN;
  await send.click();
  await expect(page.locator("[data-sent-card]")).toBeVisible({ timeout: 180_000 });
  return n;
}

async function sentFigures(page: Page): Promise<{ sent: number; notSent: number; total: string }> {
  const card = page.locator("[data-sent-card]");
  const sent = Number(await card.locator("[data-sent-count]").getAttribute("data-sent-count"));
  const notSentEl = card.locator("[data-not-sent]");
  const notSent = (await notSentEl.count())
    ? Number(await notSentEl.getAttribute("data-not-sent"))
    : 0;
  const total = (await card.locator("dd").first().innerText()).trim();
  return { sent, notSent, total };
}

async function notInRunRows(page: Page): Promise<{ account: string; kind: string }[]> {
  const out: { account: string; kind: string }[] = [];
  // The list arrives after Sent is drawn; on a loaded machine an immediate read
  // saw none of it and A2/A3 then found every held account "nowhere".
  await page
    .locator("[data-not-in-run-row]")
    .first()
    .waitFor({ state: "visible", timeout: 30_000 })
    .catch(() => undefined);
  for (const tr of await page.locator("[data-not-in-run-row]").all()) {
    const kind = (await tr.getAttribute("data-not-in-run-row")) ?? "";
    const text = await tr.innerText();
    out.push({ account: /AC-\d{4}-\d{5}/.exec(text)?.[0] ?? "—", kind });
  }
  return out;
}

const money = (s: string) => Number(String(s).replace(/[^0-9.-]/g, ""));

// ── the checks ───────────────────────────────────────────────────────────────

test.describe(`J72 accuracy — clerk checks A1–A6 at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(Number(process.env.E2E_TEST_TIMEOUT ?? "600000"));

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await signIn(page);
  });

  test("A1 · totals reconcile on every step: Scope = Ready + Blocked + Held + Nothing + Left out; billed = sent", async ({
    page,
  }) => {
    const f: Figures = {};
    save(f);
    // ── Scope ──
    await openRun(page);
    await fillScope(page, {
      name: "September 2026 · Riverside (accuracy)",
      start: "2026-09-01",
      end: "2026-09-30",
      bill: "2026-10-01",
    });
    f.scope = await scopeFigures(page);
    expect(f.scope.accounts, "Scope: the seed's 11 accounts").toBe(11);
    expect.soft(f.scope.units, "Scope: 12 units").toBe(12);
    expect
      .soft(f.scope.regular + f.scope.master, "regular + master = accounts")
      .toBe(f.scope.accounts);
    await page.getByRole("button", { name: "Start checking", exact: true }).click();
    expect(await onStep(page, "Check", 120_000), "Start checking opens Check").toBe(true);
    f.runId = new URL(page.url()).searchParams.get("run") ?? undefined;
    save(f);

    // ── Check, before any answer ──
    f.check = await checkFigures(page);
    save(f);
    expect.soft(f.check.checked, "Check checked every Scope account").toBe(f.scope.accounts);
    expect
      .soft(
        f.check.ready + f.check.blocked + f.check.decision,
        "Check: Ready + Blocked + Need a decision = Scope's accounts",
      )
      .toBe(f.scope.accounts);

    // ── the answers (see the header) ──
    const decided: Figures["decided"] = [];
    const answer = async (tag: string, account: string, label: string, reason?: string) => {
      await decide(page, tag, account, label, reason);
      decided.push({ account, answer: label, at: new Date().toISOString() });
    };
    // DEF-BIL-8551: the server refuses Estimate (no quantity sent) and the row
    // falls back to Choose. The walk records that and HOLDS 00003 instead, so
    // September still goes out; A5's true-up then has no estimate to true up.
    try {
      await decide(page, TAG.noReading, ACC(3), "Estimate", undefined, 10_000);
      decided.push({
        account: ACC(3),
        answer: "Estimate",
        at: new Date().toISOString(),
      });
    } catch {
      f.estimateRefused = true;
      await answer(TAG.noReading, ACC(3), "Hold");
    }
    await answer(TAG.gapOrOverlap, ACC(9), "Look into it");
    await answer(TAG.gapOrOverlap, ACC(10), "Look into it");
    // DEF-BIL-8552: Waive asks no reason and the server refuses it without one;
    // the walk records that and bills the standing charges (Include) instead.
    try {
      await decide(page, TAG.standingChargesOnly, ACC(11), "Waive", "Vacation hold — agreed", 10_000);
      decided.push({ account: ACC(11), answer: "Waive", at: new Date().toISOString() });
    } catch {
      f.waiveRefused = true;
      await answer(TAG.standingChargesOnly, ACC(11), "Include");
    }
    await answer(
      await tagHolding(page, [TAG.paidAfterCutoff], ACC(7)),
      ACC(7),
      "Apply to this bill",
    );
    await answer(
      await tagHolding(page, [TAG.planInstalmentDue], ACC(8)),
      ACC(8),
      "Skip",
    );
    f.decided = decided;
    save(f);

    // ── Check, after the answers: the Price button is what goes on ──
    const price = page.getByRole("button", { name: /^Price \d+ accounts?$/ });
    await expect(price).toBeEnabled({ timeout: 30_000 });
    // The last answer's re-read of the tiles must land before the count is
    // read: on a loaded machine it arrived after, and the walk read 5 where
    // Calculate then priced 6 (the answer, not the product, was early).
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    f.price = num(await price.innerText()) ?? NaN;
    save(f);
    // Held by an answer: 00009 and 00010 (Look into it), and 00003 when its
    // estimate is refused. Waived: 00011. Still waiting on a decision (the
    // tile, after the answers): 00004 and 00005. Blocked: none on this seed.
    const heldByAnswer = 2 + (f.estimateRefused === true ? 1 : 0);
    const waiting = (await tile(page, /^Need a decision \d+$/)) ?? 0;
    expect
      .soft(
        f.price + f.check.blocked + waiting + heldByAnswer + (f.waiveRefused === true ? 0 : 1),
        "Check: Price + Blocked + Waiting + Held + Waived = Scope's accounts",
      )
      .toBe(f.scope.accounts);
    await price.click();
    expect(await onStep(page, "Sign off", 240_000), "Calculate opens Sign off").toBe(true);

    // ── Sign off ──
    const who = await whoIsBilled(page);
    f.signOff = who;
    const toBill = pick(who, /^Accounts to bill/);
    const billed = pick(who, /^Billed$/);
    const blocked = pick(who, /^Blocked/) ?? 0;
    const held = pick(who, /^Held/) ?? 0;
    const nothing = pick(who, /^Nothing/) ?? 0;
    const leftOut = (pick(who, /^Left out/) ?? 0) + (pick(who, /^Waived/) ?? 0);
    const drafts = (await runInvoices(page, f.runId ?? "")).filter((i) => i.status === "draft");
    f.drafts = Object.fromEntries(
      drafts.map((i) => [
        i.account_no,
        {
          total: i.total,
          invoice_id: i.id ?? i.invoice_id,
          period: `${i.period_start}..${i.period_end}`,
        },
      ]),
    );
    f.signOffTotal = (
      await page
        .locator("[data-run-table=by-type] tr[data-total] td[data-num]")
        .last()
        // Bounded: the served By customer type table draws no total row, and an
        // unbounded read waited out the whole test (the 2026-09-30 re-walk).
        .innerText({ timeout: 5_000 })
        .catch(() => "")
    ).trim();
    save(f);
    expect.soft(toBill, "Sign off: Accounts to bill = Scope's accounts").toBe(f.scope.accounts);
    expect.soft(billed, "Sign off: Billed = the accounts Check priced").toBe(f.price);
    expect.soft(billed, "Sign off: Billed = the drafts actually made").toBe(drafts.length);
    expect
      .soft(
        (billed ?? 0) + blocked + held + nothing + leftOut,
        "Sign off: Billed + Blocked + Held + Nothing + Left out = Accounts to bill",
      )
      .toBe(toBill);

    // ── Send ──
    f.sendButton = await signOffAndSend(page);
    f.sent = await sentFigures(page);
    f.notInRun = await notInRunRows(page);
    save(f);
    const issued = (await runInvoices(page, f.runId ?? "")).filter((i) => i.status !== "draft");
    expect.soft(f.sendButton, "Send N bills = Sign off's Billed").toBe(billed);
    expect
      .soft(f.sent.sent + f.sent.notSent, "Sent + not sent = what Send was asked to send")
      .toBe(f.sendButton);
    expect.soft(f.sent.sent, "Sent card = bills actually issued").toBe(issued.length);
    expect.soft(billed, "Sign off's Billed = bills Send issued").toBe(issued.length);
  });

  test("A2 · nobody billed twice: the account a sent one-time bill already covers gets no second base or usage", async ({
    page,
  }) => {
    const f = load();
    expect(f.runId, "A1 walked and sent September").toBeTruthy();
    // DEF-BIL-8473: the whole-period overlap (AC-2026-00010, a one-time bill for
    // Sep 1 – Sep 30 already sent) must not be drafted or issued again.
    const mine = (await runInvoices(page, f.runId ?? "")).filter((i) => i.account_no === ACC(10));
    expect.soft(mine, `${ACC(10)} has no bill in the September run`).toHaveLength(0);
    // And generally: no September bill's days overlap an earlier bill of the same account.
    const all = rowsOf(await getJson(page, "/invoices?per=500"));
    const issued = all.filter((i) => i.status !== "draft" && i.period_start && i.period_end);
    for (const bill of issued.filter((i) => i.bill_run_id === f.runId)) {
      const earlier = issued.filter(
        (o) => o.account_no === bill.account_no && o.bill_run_id !== f.runId && o.id !== bill.id,
      );
      for (const o of earlier) {
        const overlaps = !(o.period_end < bill.period_start || o.period_start > bill.period_end);
        expect
          .soft(
            overlaps,
            `${bill.account_no}: ${bill.period_start}..${bill.period_end} overlaps ${o.invoice_no} ${o.period_start}..${o.period_end}`,
          )
          .toBe(false);
      }
    }
    // The clerk sees it: 00010 is in Not in this run, held.
    expect
      .soft(
        f.notInRun?.some((r) => r.account === ACC(10)),
        `${ACC(10)} is listed in Not in this run`,
      )
      .toBe(true);
  });

  test("A3 · no account vanishes: every account is sent, failed with a reason, or in Not in this run", async ({
    page,
  }) => {
    const f = load();
    expect(f.runId, "A1 walked and sent September").toBeTruthy();
    const issued = (await runInvoices(page, f.runId ?? ""))
      .filter((i) => i.status !== "draft")
      .map((i) => i.account_no as string);
    const breaks = rowsOf(await getJson(page, `/billing/runs/${f.runId}/breaks`)).map(
      (b) => `${b.account_no ?? b.account_id}|${b.reason ?? b.message_key ?? ""}`,
    );
    const outside = (f.notInRun ?? []).map((r) => r.account);
    const where: Record<string, string[]> = {};
    for (const acc of ACCOUNTS) {
      where[acc] = [
        ...(issued.includes(acc) ? ["sent"] : []),
        ...(breaks.some((b) => b.startsWith(`${acc}|`)) ? ["failed"] : []),
        ...(outside.includes(acc) ? ["not in this run"] : []),
      ];
    }
    test.info().annotations.push({ type: "where", description: JSON.stringify(where) });
    for (const acc of ACCOUNTS) {
      expect
        .soft(
          where[acc].length,
          `${acc} ends in exactly one place (${where[acc].join(", ") || "nowhere"})`,
        )
        .toBe(1);
    }
    for (const b of breaks) {
      expect.soft(b.split("|")[1], `failure ${b.split("|")[0]} carries its reason`).not.toBe("");
    }
    expect
      .soft(outside.filter((a) => a === "—").length, "the vacant unit is listed too")
      .toBe(f.scope?.nobodyUnits ?? 1);
  });

  test("A4 · each issued bill equals its Sign off draft, to the cent", async ({ page }) => {
    const f = load();
    expect(f.runId, "A1 walked and sent September").toBeTruthy();
    const issued = (await runInvoices(page, f.runId ?? "")).filter((i) => i.status !== "draft");
    expect(issued.length, "September issued bills").toBeGreaterThan(0);
    for (const bill of issued) {
      const draft = f.drafts?.[bill.account_no];
      expect.soft(draft, `${bill.account_no} had a draft at Sign off`).toBeTruthy();
      if (draft) {
        expect
          .soft(money(bill.total).toFixed(2), `${bill.account_no} issued = drafted`)
          .toBe(money(draft.total).toFixed(2));
      }
    }
    const sumIssued = issued.reduce((s, b) => s + money(b.total), 0).toFixed(2);
    expect
      .soft(money(f.sent?.total ?? "NaN").toFixed(2), "Sent card total = sum of issued bills")
      .toBe(sumIssued);
  });

  test("A5 · the rulings hold on month two: prorated overlap base, 7 kgal true-up, one base after a hold, $45 instalments", async ({
    page,
  }) => {
    // DEF-BIL-8551 and DEF-BIL-8556 are fixed by the bulk-run-rest lane (the
    // estimate is recorded; the screen saves the Check the extension reads).
    // DEF-BIL-8243's Add to bill is merged (2.414.0): the instalment is PRINTED
    // on the bill from its stamped payload, never a charge line (it is arrears
    // already in the balance forward), so the walk reads the bill's DOCUMENT.
    // DEF-BIL-8420 is fixed: the seed no longer plants 00003's October reading;
    // the walk plants it below, AFTER September is sent, through Meter Reads'
    // own commit (E2E_J72_LATE_READ runs `seed_j72_bulk_run --late-october-read`).
    const f = load();
    expect(f.runId, "A1 walked and sent September").toBeTruthy();
    const figure = (name: string, ok: boolean, detail: string) => {
      test
        .info()
        .annotations.push({ type: ok ? "PASS" : "FAIL", description: `${name} — ${detail}` });
      expect.soft(ok, `${name}: ${detail}`).toBe(true);
    };
    const bases = async (invoice: Row) =>
      (await invoiceLines(page, invoice.id)).filter(isBase).map((l) => money(l.amount).toFixed(2));
    const september = await runInvoices(page, f.runId ?? "");
    const accountId = async (acc: string): Promise<string> => {
      const known = september.find((i) => i.account_no === acc)?.account_id as string | undefined;
      if (known) return known;
      const found = rowsOf(await getJson(page, `/invoices?q=${acc}&per=5`))[0];
      return (found?.account_id as string | undefined) ?? "";
    };

    // Case 3 on its OWN month two: 00006 was held in August, so September
    // bills it Aug 1 – Sep 30 with ONE base.
    const tom = september.find((i) => i.account_no === ACC(6) && i.status !== "draft");
    figure(
      "hold → one base (Aug hold, Sep bill)",
      tom?.period_start === "2026-08-01" &&
        JSON.stringify(tom ? await bases(tom) : []) === '["8.00"]',
      `${ACC(6)} ${tom?.period_start}..${tom?.period_end}, bases ${JSON.stringify(tom ? await bases(tom) : [])}`,
    );

    // Between the runs: a one-time interim bill for 00001, Oct 1 – Oct 17, sent.
    const maria = await accountId(ACC(1));
    expect(maria, `${ACC(1)} is known`).not.toBe("");
    const created = await page.request.post(`${API()}/billing/one-time`, {
      data: {
        account_id: maria,
        kind: "interim",
        period_start: "2026-10-01",
        period_end: "2026-10-17",
        bill_date: "2026-10-17",
        due_days: 21,
      },
    });
    expect(created.ok(), `one-time interim: ${created.status()} ${await created.text()}`).toBe(
      true,
    );
    const oneTime = await created.json();
    const oneTimeRun = oneTime.bill_run_id ?? oneTime.run_id ?? oneTime.data?.bill_run_id;
    const sentOneTime = await page.request.post(`${API()}/billing/one-time/${oneTimeRun}/send`, {
      data: {
        delivery: "email",
        sent_at: "2026-10-17T12:00:00-05:00",
        confirmations: {
          compliance: true,
          email_mandate: true,
          sms_mandate: true,
          autopay_mandate: true,
          final: true,
        },
      },
    });
    expect(
      sentOneTime.ok(),
      `one-time send: ${sentOneTime.status()} ${await sentOneTime.text()}`,
    ).toBe(true);

    // DEF-BIL-8420 — 00003's Oct 31 reading, planted NOW that September's
    // estimate is in Meter Reads (B22), so Meter Reads trues it up at commit.
    const late = process.env.E2E_J72_LATE_READ ?? "";
    expect(late, "E2E_J72_LATE_READ names the late-read command").not.toBe("");
    execSync(late, { stdio: "inherit" });

    // October, on the same accounts, through the screen.
    await openRun(page);
    await fillScope(page, {
      name: "October 2026 · Riverside (accuracy)",
      start: "2026-10-01",
      end: "2026-10-31",
      bill: "2026-11-01",
    });
    await page.getByRole("button", { name: "Start checking", exact: true }).click();
    expect(await onStep(page, "Check", 120_000), "October reaches Check").toBe(true);
    const octRun = new URL(page.url()).searchParams.get("run") ?? "";
    f.october = { runId: octRun };
    save(f);
    await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 120_000 });
    // The tag list is the served grouped read; take it only once it has settled,
    // or a tag still arriving is never opened and its account leaves October
    // unbilled (seen once at load 8: 00008 and 00009 undecided).
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    // Every open row is answered — an unanswered one leaves the run unbilled
    // (DEF-BIL-8474). The instalment goes ON the bill; a price change bills at
    // the period-end price (the suggestion, BR-BIL-1055); standing charges are
    // included; an overlap keeps the ruled answer (bill from the day after).
    const prefer = [
      /Add to bill/,
      /^Include$/,
      /Accept|period end|as suggested/i,
      /Bill as it stands/,
    ];
    f.octoberUnanswered = [];
    for (const tagRow of await page.locator("[data-tag]").all()) {
      const tag = (await tagRow.getAttribute("data-tag")) ?? "";
      if (tag === "ready") continue;
      await tagRow.click();
      const pane = page.locator(`[data-tag-pane="${tag}"]`);
      if ((await pane.count()) === 0) continue;
      // The tag's page arrives after the click (DEF-BIL-8419): wait for it,
      // or an open row is skipped and the account leaves October unbilled.
      await expect(pane.locator("[data-row-account], [role=status]").first()).toBeVisible({
        timeout: 15_000,
      });
      // DEF-BIL-8652 — a row is answered when its SAVED state says so
      // (`data-decision`), never because its select shows a value: the old
      // loop skipped every pre-filled row and walked October with 0 answers.
      // The list re-renders after each answer, so take the first OPEN row
      // each time; a row with no choice the walk will make is counted, not
      // retried forever.
      let skipped = 0;
      for (let guard = 0; guard < 50; guard += 1) {
        const open = pane.locator("[data-decision=open]");
        if ((await open.count()) <= skipped) break;
        const row = open.nth(skipped);
        const box = row.getByRole("combobox", { name: /^Decide for / });
        const labels = (await box.locator("option").allInnerTexts()).filter((l) => l !== "Choose");
        const choice =
          prefer.map((re) => labels.find((l) => re.test(l))).find((l) => l !== undefined) ??
          labels.find((l) => !/Hold|Look into|Estimate/i.test(l));
        if (choice === undefined) {
          const account = await row.locator("xpath=ancestor::tr[1]").getAttribute("data-row-account");
          f.octoberUnanswered = [...(f.octoberUnanswered ?? []), `${account}:${tag}`];
          skipped += 1;
          continue;
        }
        const before = await open.count();
        await box.selectOption({ label: choice });
        await expect.poll(async () => open.count(), { timeout: 20_000 }).toBeLessThan(before);
      }
    }
    save(f);
    // Every open decision is answered before Price — the clerk's rule, and the
    // thing A5's figures depend on (an unanswered account is not billed). The
    // ONE row left open is deliberate and named: 00005's disputed reading
    // offers Hold or Bill on estimate, and the walk takes neither, as in
    // September (the header's `00005` note) — so it stays in Not in this run.
    expect(f.octoberUnanswered ?? [], "October: every open decision row was answered").toEqual([
      "AC-2026-00005:account_held_by_disputed_read",
    ]);
    const price = page.getByRole("button", { name: /^Price \d+ accounts?$/ });
    await expect(price).toBeEnabled({ timeout: 30_000 });
    await price.click();
    expect(await onStep(page, "Sign off", 240_000), "October reaches Sign off").toBe(true);
    await signOffAndSend(page);
    const october = (await runInvoices(page, octRun)).filter((i) => i.status !== "draft");
    const bill = (acc: string) => october.find((i) => i.account_no === acc);

    // Case 4 — the overlap starts the day after the last bill and prorates the
    // base by B4.3's service_days / cycle_days. The PO's worked figure is a
    // 30-day run ($8.00 × 14/30 = $3.73); October has 31 days, so the same rule
    // reads $8.00 × 14/31 = $3.61 here.
    const m = bill(ACC(1));
    const expected = ((8 * 14) / 31).toFixed(2);
    figure(
      "overlap → base prorated from the day after the last bill",
      m?.period_start === "2026-10-18" &&
        JSON.stringify(m ? await bases(m) : []) === `["${expected}"]`,
      `${ACC(1)} ${m?.period_start}..${m?.period_end}, bases ${JSON.stringify(m ? await bases(m) : [])} (want ["${expected}"])`,
    );

    // §1 — the estimate true-up: Aug 158.0, Sep ESTIMATED, Oct 173.0 → 7 kgal.
    // With DEF-BIL-8551 September could not estimate, so 00003 was HELD: October
    // then bills Sep 1 – Oct 31 with one base and all 15 kgal — the hold case.
    const p = bill(ACC(3));
    const pUsage = p
      ? (await invoiceLines(page, p.id))
          .filter((l) => l.quantity !== null && /kgal/i.test(String(l.unit)))
          .reduce((s, l) => s + Number(l.quantity), 0)
      : NaN;
    figure(
      "estimate true-up = 7 kgal",
      f.estimateRefused !== true && pUsage === 7,
      f.estimateRefused === true
        ? `not reachable: September's Estimate was refused (DEF-BIL-8551); ${ACC(3)} was held and October billed ${pUsage} kgal`
        : `${ACC(3)} October usage ${pUsage} kgal`,
    );
    if (f.estimateRefused === true) {
      figure(
        "hold → one base (Sep hold, Oct bill)",
        p?.period_start === "2026-09-01" && JSON.stringify(p ? await bases(p) : []) === '["8.00"]',
        `${ACC(3)} ${p?.period_start}..${p?.period_end}, bases ${JSON.stringify(p ? await bases(p) : [])}`,
      );
    }
    // Case 3 — held in September by Look into it: Aug 1 – Oct 31, ONE base.
    const s = bill(ACC(9));
    figure(
      "hold → one base (Look into it in Sep, Oct bill)",
      s?.period_start === "2026-08-01" && JSON.stringify(s ? await bases(s) : []) === '["8.00"]',
      `${ACC(9)} ${s?.period_start}..${s?.period_end}, bases ${JSON.stringify(s ? await bases(s) : [])}`,
    );

    // Case 5 — the skipped instalment: still 7 × $45.00, one month longer, never $90.
    const plans = await getJson(page, `/accounts/${await accountId(ACC(8))}/payment-plans`);
    const inst = (plans.live_plan ?? plans.plans?.[0])?.installments ?? [];
    const dues = inst.map((r) => r.due_date as string);
    figure(
      "skip → plan 7 × $45.00, no September instalment, ends a month later",
      inst.length === 7 &&
        inst.every((r) => money(r.amount).toFixed(2) === "45.00") &&
        !dues.includes("2026-09-15") &&
        dues.at(-1) === "2027-04-15",
      `${ACC(8)} instalments ${inst.map((r) => `${r.due_date} ${r.amount}`).join(", ")}`,
    );
    const d = bill(ACC(8));
    // Printed, not charged: no charge line names the plan, and the document
    // says the one instalment due — "Instalment 1: 45.00 USD due 2026-10-15."
    const planLines = d
      ? (await invoiceLines(page, d.id)).filter((l) =>
          /instal|plan/i.test(`${l.kind} ${l.description}`),
        )
      : [];
    // The document prints money as "45.00 USD" (documents._money); a page may
    // carry the sentence more than once (field + rendered page), so count the
    // DISTINCT instalments it names.
    const printed = d
      ? [
          ...new Set(
            JSON.stringify(await getJson(page, `/invoices/${d.id}/document`)).match(
              /Instalment \d+: 45\.00 USD due [0-9-]+/g,
            ) ?? [],
          ),
        ]
      : [];
    figure(
      "October bill prints one $45.00 instalment and charges none",
      planLines.length === 0 && printed.length === 1,
      d
        ? `${ACC(8)} printed ${JSON.stringify(printed)}, plan charge lines ${planLines.length}`
        : `${ACC(8)} has no October bill`,
    );
  });

  test("A6 · every clerk decision is traceable in the run's check report after Send: who, what, when, which account", async ({
    page,
  }) => {
    const f = load();
    expect(f.runId, "A1 walked and sent September").toBeTruthy();
    expect(f.decided?.length, "A1 recorded its answers").toBeGreaterThan(0);
    // On screen: the sent run, re-opened, shows its check report with each answer.
    await openRun(page, `?run=${f.runId}`);
    const screen = page.locator("[data-screen=bulk-bill-run]");
    // The sent run opens on Sent; its Check report is the tab beside it.
    await page.getByRole("tab", { name: "Check report" }).click({ timeout: 30_000 });
    const report = page.locator("[data-check-report]");
    await expect(report, "the sent run shows a check report").toBeVisible({ timeout: 15_000 });
    for (const d of f.decided ?? []) {
      const row = report.locator("tr", { hasText: d.account });
      await expect.soft(row, `${d.account} is in the report`).toHaveCount(1);
      await expect.soft(row, `${d.account}: what was answered`).toContainText(d.answer);
      await expect.soft(row, `${d.account}: who answered`).toContainText(/Dana Whitfield/);
      await expect.soft(row, `${d.account}: when`).toContainText(/\d{2}\/\d{2}\/\d{4}/);
    }
    await expect(screen).toBeVisible();
  });
});
