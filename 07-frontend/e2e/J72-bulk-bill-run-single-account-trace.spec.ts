// ── Trace ──────────────────────────────────────────────
// Tracker:  BULK-CHG-56 (the clerk acceptance walk: E17, one account end to end)
// Journey:  J72 — the bulk bill run · 08-qa/01-e2e/journeys/J72-bulk-bill-run-redesign.md
//           (§ E16/E17 — the run audit in the database, and this trace)
// Plan:     15-bulk-bill-run-build-plan.md E17 (single-account trace)
// Proof:    20-bulk-run-clerk-acceptance.md §5 — the PO's per-step requirements, verbatim
// Verifier: 10-scripts/verify_bulk_run.py (--account … --json) — the DATABASE half
// Seed:     `manage.py seed_j72_bulk_run` (PLAIN — no --month-two) on top of `seed_demo`,
//           PostgreSQL; this spec plants October's readings itself, AFTER September is sent
// ───────────────────────────────────────────────────────
//
// E17 · ONE ACCOUNT, END TO END, AND INTO MONTH TWO. PO, verbatim (2026-09-30):
// *"here it is important process complete for 1 account end to end and does not
// break down in between"*.
//
// The account is AC-2026-00003 (Priya Natarajan, unit 103, meter W-72103): it has
// NO September reading, so the Check raises *No reading* and the clerk answers
// *Estimate the reading, 8 kgal* — a real problem whose answer must travel from
// the screen, into the decision store, into Calculate, onto the bill, into Meter
// Reads as an estimated reading, and then be TRUED UP by October's actual read.
//
// At every step the spec does what the clerk does in the browser, then asks the
// verifier for EVERY record the account touches (findings, decisions, Pending
// billing, the draft or bill and its lines, journal, delivery rows, audit rows,
// the meter's readings, the run's jobs) and asserts the §5 list for that step:
//
//   1 Scope → Check      the Check read the system and found the missing reading;
//                        no decision, no bill, no queue row yet
//   2 Answer             the decision is SAVED: estimate, 8 kgal, water, by the
//                        signed-in clerk, now — and nothing the clerk did not choose
//   3 Calculate          the answer was USED: one draft, water usage 8 kgal priced,
//                        the service marked estimated, no Pending-billing row
//   4 Sign off           the screen's Billed / total equal the database's drafts
//   5 Send               issued with a number, lines = draft to the cent, journal
//                        balanced and receivable moved by the total, paper queued,
//                        the estimate saved in Meter Reads and billed-locked, audit
//                        rows, no job left pending, the check record locked
//   6 Send again         the database gains NOTHING (the route answers a replay)
//   7 Month two          October's actual read (173.0) arrives through Meter
//                        Reads' own commit; the October bill starts Oct 1 (the day
//                        after September's), carries ONE base, and bills 7 kgal —
//                        173.0 − 158.0 − the 8 kgal already billed on the estimate
//
// Why October's reading is posted HERE and not by the seed: `--month-two`
// commits every October read up front, before September's estimate exists
// (DEF-BIL-8420 — its fix note says to post the reading between the runs), and
// it commits through `commit_read`, a history-setup helper that writes the row
// directly and never runs Meter Reads' true-up. So after September is sent this
// spec posts the Oct 31 reading through Meter Reads' OWN import (`/read-batches`
// stage → validate → post) — the path a route file takes, where BR-MET-029's
// true-up lives (`metering.services._post_row`).
//
// Run (the database the stack serves is passed to the verifier too):
//   E2E_DATABASE_URL=postgres://…/sbh_e17 E2E_VIEWPORT=1440 E2E_BASE_URL=… \
//     npx playwright test e2e/J72-bulk-bill-run-single-account-trace.spec.ts --workers=1
// Optional: E2E_PYTHON (the backend's python, default `python3`).
//
// Every step's result is written to `${E2E_STATE_DIR:-/tmp}/j72-e17-<width>.json`
// and attached as annotations. Assertions are soft inside the walk so one wrong
// record never hides the steps after it; the test fails if any of them failed.
import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const REPO_ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)), "../..");
const VERIFY = resolve(REPO_ROOT, "10-scripts/verify_bulk_run.py");
const PYTHON = process.env.E2E_PYTHON ?? "python3";
const DB = process.env.E2E_DATABASE_URL ?? "";
const STATE = `${process.env.E2E_STATE_DIR ?? "/tmp"}/j72-e17-${WIDTH}.json`;
const API = () => `/api/${tenant()}`;
const CYCLE = /J72-RIVERSIDE/;
const CLERK = "Dana Whitfield";

const ACCOUNT = "AC-2026-00003";
const METER = "W-72103";
const OCTOBER_READING = "173.0";
const ESTIMATE = "8";
const TRUE_UP = 7; // Aug 31 158.0 → Oct 31 173.0 = 15 kgal, 8 of them billed in September

// ── the verifier: the database half of every step ───────────────────────────

type Json = Record<string, unknown>;
interface Bill {
  id: string;
  invoice_no: string | null;
  status: string;
  period: string;
  total: string;
  tax: string;
  issued_at: string | null;
  services: { code: string; estimated: boolean; read_id: string | null }[];
  lines: { kind: string; service: string; quantity: string | null; unit: string | null; amount: string }[];
  journals: { status: string; debits: string; credits: string; ar_net: string }[];
  deliveries: { channel: string; status: string }[];
  audit: Record<string, number>;
  payments_received: string | null;
}
interface Records {
  check: { status: string; stale: boolean };
  findings: { code: string; severity: string; service: string | null }[];
  decisions: {
    case: string;
    choice: string;
    amount: string | null;
    unit: string | null;
    service: string | null;
    decided_by: string | null;
    at: string;
    current: boolean;
  }[];
  pending_billing: Json | null;
  break: Json | null;
  bills: Bill[];
  estimates_written: { consumption: string; unit: string; source: string; lifecycle: string; read_at: string }[];
  meter_reads: {
    id: string;
    read_at: string;
    current_value: string | null;
    consumption: string | null;
    unit: string;
    source: string;
    lifecycle: string;
    superseded_by_id: string | null;
    trues_up_read_ids: string[] | null;
  }[];
  audit: { action: string; actor: string | null }[];
  jobs: { kind: string; status: string }[];
}
interface Verdict {
  run: { run_no: string; stage: string };
  accounts: { account_no: string; end: string; verdict: Record<string, string>; fail: string[] }[];
  run_checks: Record<string, { verdict: string; detail: string }>;
  counts: Record<string, number>;
  records: Records;
  ok: boolean;
}

function verifier(run: string, extra: string[] = []): Verdict {
  const out = spawnSync(
    PYTHON,
    [VERIFY, run, "--account", ACCOUNT, "--clerk", CLERK, "--json", ...extra],
    { env: { ...process.env, DATABASE_URL: DB }, encoding: "utf8" },
  );
  if (!out.stdout) throw new Error(`verify_bulk_run failed: ${out.stderr}`);
  return JSON.parse(out.stdout) as Verdict;
}

/**
 * October's actual reading for the account's meter, through METER READS' OWN
 * IMPORT — stage, validate, post (`/read-batches`, S28's pipeline, the path a
 * route file takes). Not the seed's `commit_read`: that is a history-setup
 * helper that writes the row directly, so it never runs the true-up
 * (BR-MET-029) this step exists to prove.
 */
async function postOctoberReading(page: Page): Promise<string> {
  const staged = await page.request.post(`${API()}/read-batches`, {
    data: {
      source_kind: "manual",
      period_month: "2026-10-01",
      rows: [{ meter_id: METER, read_date: "2026-10-31", reading: OCTOBER_READING, channel: "total" }],
    },
  });
  if (staged.status() !== 201) throw new Error(`stage: ${staged.status()} ${await staged.text()}`);
  const id = ((await staged.json()) as { id: string }).id;
  const validated = await page.request.post(`${API()}/read-batches/${id}/validate`);
  if (!validated.ok()) throw new Error(`validate: ${validated.status()} ${await validated.text()}`);
  const posted = await page.request.post(`${API()}/read-batches/${id}/post`, { data: { certified: true } });
  if (!posted.ok()) throw new Error(`post: ${posted.status()} ${await posted.text()}`);
  return `batch ${id}: ${posted.status()}`;
}

// ── the step table (what the J72 results section reports) ────────────────────

interface Step {
  step: string;
  check: string;
  ok: boolean;
  detail: string;
}
const steps: Step[] = [];
function record(step: string, check: string, ok: boolean, detail: string): void {
  steps.push({ step, check, ok, detail });
  test.info().annotations.push({ type: ok ? "PASS" : "FAIL", description: `${step} · ${check} — ${detail}` });
  expect.soft(ok, `${step} · ${check}: ${detail}`).toBe(true);
  writeFileSync(STATE, JSON.stringify({ account: ACCOUNT, width: WIDTH, steps }, null, 2));
}
const verdictOf = (v: Verdict, key: string) => v.accounts[0]?.verdict[key] ?? "–";
const failsOf = (v: Verdict, key: string) =>
  (v.accounts[0]?.fail ?? []).filter((f) => f.startsWith(`[${key}]`)).join("; ");
const passes = (v: Verdict, key: string) => verdictOf(v, key) === "PASS";
const money = (s: string | null | undefined) => Number(String(s ?? "NaN").replace(/[^0-9.-]/g, ""));
const water = (b: Bill) => b.lines.filter((l) => l.kind === "usage" && l.service === "water");
const bases = (b: Bill) => b.lines.filter((l) => l.kind === "base");

// ── the clerk's screen (the same selectors J72's accuracy walk uses) ─────────

async function onStep(page: Page, label: string, timeout = 30_000): Promise<boolean> {
  try {
    await expect(page.locator("[data-wizard=rail] [aria-current=step]")).toContainText(label, { timeout });
    return true;
  } catch {
    return false;
  }
}

async function scopeAndStart(page: Page, s: { name: string; start: string; end: string; bill: string }): Promise<string> {
  await page.goto(`/${tenant()}/billing/run`);
  await expect(page.locator("[data-screen=bulk-bill-run]")).toBeVisible({ timeout: 30_000 });
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
  await page.getByRole("button", { name: "Start checking", exact: true }).click();
  expect(await onStep(page, "Check", 120_000), "Start checking opens Check").toBe(true);
  await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 120_000 });
  await expect(page.locator("[data-screen=bulk-bill-run]")).toContainText(/Checked [1-9]\d* accounts/i, {
    timeout: 60_000,
  });
  return new URL(page.url()).searchParams.get("run") ?? "";
}

/** The row for ACCOUNT under a tag; answers it with `answer`. */
async function answerRow(page: Page, tag: string, answer: string): Promise<boolean> {
  const tagRow = page.locator(`[data-tag=${tag}]`).first();
  if ((await tagRow.count()) === 0) return false;
  await tagRow.click();
  const pane = page.locator(`[data-tag-pane=${tag}]`);
  await expect(pane.locator("[data-row-account], [role=status]").first()).toBeVisible({ timeout: 15_000 });
  const box = pane.getByRole("combobox", { name: `Decide for ${ACCOUNT}` });
  if ((await box.count()) === 0) return false;
  // `has` is queried INSIDE each row, so it must be an unscoped locator: a
  // pane-scoped one looks for the pane inside the row and matches nothing.
  const row = pane.locator("tr", { has: page.getByRole("combobox", { name: `Decide for ${ACCOUNT}` }) });
  await box.selectOption({ label: answer });
  if (answer === "Estimate") {
    const est = row.locator("[data-estimate-box]");
    await expect(est, "Estimate asks how much").toBeVisible({ timeout: 10_000 });
    await est.getByLabel("Usage").fill(ESTIMATE);
    if ((await est.getByLabel("Unit").inputValue()) === "") await est.getByLabel("Unit").fill("kgal");
    await est.getByRole("button", { name: "Record this estimate" }).click();
  }
  await expect(row.locator("[data-decision=answered]"), `${ACCOUNT} answered ${answer}`).toBeVisible({
    timeout: 20_000,
  });
  return true;
}

async function priceAndSignOff(page: Page): Promise<number> {
  const price = page.getByRole("button", { name: /^Price \d+ accounts?$/ });
  await expect(price).toBeEnabled({ timeout: 30_000 });
  const n = Number(/\d+/.exec(await price.innerText())?.[0] ?? NaN);
  await price.click();
  expect(await onStep(page, "Sign off", 240_000), "Calculate opens Sign off").toBe(true);
  return n;
}

async function billedOnSignOff(page: Page): Promise<number | null> {
  const table = page.locator("[data-run-table=who-accounts]");
  await expect(table).toBeVisible({ timeout: 30_000 });
  for (const tr of await table.locator("tbody tr").all()) {
    if ((await tr.locator("th").innerText()).trim() === "Billed") {
      return Number((await tr.locator("td[data-num]").innerText()).replace(/[^0-9]/g, ""));
    }
  }
  return null;
}

async function signOffAndSend(page: Page): Promise<{ button: number; sent: number; total: string }> {
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
  await page.getByRole("region", { name: "Send" }).getByRole("checkbox", { name: "I checked the totals" }).check();
  const send = actions.getByRole("button", { name: /^Send \d+ bills?$/ });
  const button = Number(/\d+/.exec(await send.innerText())?.[0] ?? NaN);
  await send.click();
  const card = page.locator("[data-sent-card]");
  await expect(card).toBeVisible({ timeout: 180_000 });
  const sent = Number(await card.locator("[data-sent-count]").getAttribute("data-sent-count"));
  const total = (await card.locator("dd").first().innerText()).trim();
  return { button, sent, total };
}

// ── E17 ──────────────────────────────────────────────────────────────────────

test.describe(`J72 E17 — one account end to end, into month two, at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(Number(process.env.E2E_TEST_TIMEOUT ?? "900000"));

  test("E17 · AC-2026-00003 no reading → estimate: Scope → Check → answer → Calculate → Sign off → Send → Send again → month two", async ({
    page,
  }) => {
    test.skip(DB === "", "E17 reads the database: set E2E_DATABASE_URL to the PostgreSQL the stack serves");
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await signIn(page);

    // ── 1 · Scope → Check: the Check read the system and found the problem ──
    const sep = await scopeAndStart(page, {
      name: "September 2026 · Riverside (E17 trace)",
      start: "2026-09-01",
      end: "2026-09-30",
      bill: "2026-10-01",
    });
    expect(sep, "the run id is in the address").not.toBe("");
    let v = verifier(sep);
    let r = v.records;
    record("1 Check", "account checked, needs a decision", r.check.status === "decision" && !r.check.stale,
      `status ${r.check.status}, stale ${r.check.stale}`);
    record("1 Check", "the missing reading was found in Meter Reads",
      r.findings.some((f) => f.code === "missing_read" && f.service === "water" && f.severity === "decision")
        && !r.meter_reads.some((m) => m.read_at.startsWith("2026-09-30")),
      `findings ${r.findings.map((f) => `${f.code}/${f.service}/${f.severity}`).join(", ")}; ` +
        `reads ${r.meter_reads.map((m) => m.read_at.slice(0, 10)).join(", ")}`);
    record("1 Check", "nothing written yet: no decision, no bill, no queue row",
      r.decisions.length === 0 && r.bills.length === 0 && r.pending_billing === null,
      `${r.decisions.length} decision(s), ${r.bills.length} bill(s), queue ${r.pending_billing ? "yes" : "no"}`);
    record("1 Check", "the Check job finished",
      r.jobs.some((j) => j.kind === "billing.run.check" && j.status === "succeeded")
        && !r.jobs.some((j) => ["queued", "running", "failed"].includes(j.status)),
      r.jobs.map((j) => `${j.kind} ${j.status}`).join(", "));

    // ── 2 · Answer on screen: the decision is SAVED ──
    const answeredAt = Date.now();
    const answered = await answerRow(page, "missing_read", "Estimate");
    record("2 Answer", "the clerk answered on screen", answered, `Estimate the reading, ${ESTIMATE} kgal`);
    v = verifier(sep);
    r = v.records;
    const cur = r.decisions.filter((d) => d.current);
    const est = cur.find((d) => d.case === "missing_read");
    record("2 Answer", "saved: estimate, 8 kgal, water",
      est !== undefined && est.choice === "estimate" && money(est.amount) === Number(ESTIMATE)
        && est.unit === "kgal" && est.service === "water",
      est ? `${est.case}=${est.choice} ${est.amount} ${est.unit} ${est.service}` : "no current row");
    record("2 Answer", "saved: who and when",
      est !== undefined && est.decided_by === CLERK && Math.abs(Date.parse(est.at) - answeredAt) < 180_000,
      est ? `by ${est.decided_by} at ${est.at}` : "no current row");
    record("2 Answer", "nothing the clerk did not choose", cur.length === 1,
      `${cur.length} current decision(s): ${cur.map((d) => `${d.case}=${d.choice}`).join(", ")}`);
    record("2 Answer", "still no bill and no queue row", r.bills.length === 0 && r.pending_billing === null,
      `${r.bills.length} bill(s), queue ${r.pending_billing ? "yes" : "no"}`);

    // ── 3 · Calculate: the answer was USED ──
    const priceN = await priceAndSignOff(page);
    v = verifier(sep);
    r = v.records;
    const draft = r.bills[0];
    record("3 Calculate", "one draft for the account", r.bills.length === 1 && draft?.status === "draft",
      r.bills.map((b) => `${b.status} ${b.total}`).join(", ") || "no draft");
    const wl = draft ? water(draft) : [];
    record("3 Calculate", "the estimate is on the draft: water usage 8 kgal",
      wl.length > 0 && wl.reduce((s, l) => s + money(l.quantity), 0) === Number(ESTIMATE)
        && wl.every((l) => l.unit === "kgal"),
      wl.map((l) => `${l.quantity} ${l.unit} = ${l.amount}`).join(", ") || "no water usage line");
    record("3 Calculate", "the draft says the water was estimated",
      !!draft && draft.services.some((s) => s.code === "water" && s.estimated),
      JSON.stringify(draft?.services ?? []));
    record("3 Calculate", "one base charge, no Pending-billing row",
      !!draft && bases(draft).length === 1 && r.pending_billing === null,
      `${draft ? bases(draft).length : 0} base line(s); queue ${r.pending_billing ? "yes" : "no"}`);
    record("3 Calculate", "decision effect (verifier P3.effect)", passes(v, "P3.effect"),
      failsOf(v, "P3.effect") || verdictOf(v, "P3.effect"));

    // ── 4 · Sign off: the screen equals the database ──
    const billed = await billedOnSignOff(page);
    record("4 Sign off", "Billed on screen = drafts in the database",
      billed === v.counts.drafts && priceN === v.counts.drafts,
      `screen Billed ${billed}, Price ${priceN}; database ${v.counts.drafts} draft(s)`);
    record("4 Sign off", "one draft per priced account (verifier P4.drafts)", passes(v, "P4.drafts"),
      failsOf(v, "P4.drafts") || verdictOf(v, "P4.drafts"));
    const draftTotal = draft?.total ?? "NaN";

    // ── 5 · Send ──
    const sent = await signOffAndSend(page);
    v = verifier(sep);
    r = v.records;
    const bill = r.bills[0];
    record("5 Send", "the screen's Send N and Sent card = the database",
      sent.button === v.counts.issued && sent.sent === v.counts.issued,
      `Send ${sent.button}, Sent ${sent.sent} (${sent.total}); database issued ${v.counts.issued}`);
    record("5 Send", "issued, numbered, dated", !!bill && bill.status === "issued" && !!bill.invoice_no && !!bill.issued_at,
      bill ? `${bill.status} ${bill.invoice_no} ${bill.issued_at}` : "no bill");
    record("5 Send", "bill = draft to the cent", !!bill && money(bill.total).toFixed(2) === money(draftTotal).toFixed(2)
      && passes(v, "S6.draft"), `issued ${bill?.total} vs draft ${draftTotal}; ${failsOf(v, "S6.draft")}`);
    record("5 Send", "journal balanced, receivable moved by the total", passes(v, "S6.ledger"),
      failsOf(v, "S6.ledger") || JSON.stringify(bill?.journals ?? []));
    record("5 Send", "paper queued (and the customer's election)", passes(v, "S5.delivery")
      && !!bill?.deliveries.some((d) => d.channel === "pdf_print"),
      (bill?.deliveries ?? []).map((d) => `${d.channel} ${d.status}`).join(", "));
    const writ = r.estimates_written;
    record("5 Send", "the estimate is saved in Meter Reads (Sep 30, 8 kgal, estimated)",
      writ.length === 1 && money(writ[0].consumption) === Number(ESTIMATE) && writ[0].unit === "kgal"
        && writ[0].source === "estimated" && writ[0].read_at.startsWith("2026-09-30") && passes(v, "P3.next"),
      writ.map((e) => `${e.read_at.slice(0, 10)} ${e.consumption} ${e.unit} ${e.source} ${e.lifecycle}`).join(", ") ||
        "no estimate written");
    record("5 Send", "readings billed-locked", passes(v, "S5.reads"), failsOf(v, "S5.reads") || "every reading billed");
    record("5 Send", "audit rows", passes(v, "S6.audit") && r.audit.some((a) => a.action === "read.estimated"),
      r.audit.map((a) => `${a.action} (${a.actor})`).join(", "));
    record("5 Send", "no background job pending or failed", passes(v, "S5.jobs"),
      r.jobs.map((j) => `${j.kind} ${j.status}`).join(", "));
    record("5 Send", "decisions and check record locked", passes(v, "S5.locked"), failsOf(v, "S5.locked") || "nothing after Send");
    record("5 Send", "ends in exactly one place", passes(v, "A3.end"), v.accounts[0]?.end ?? "?");
    record("5 Send", "run-level: release, status, no draft left",
      ["release", "release=issued", "release audited once", "run status", "no draft left"].every(
        (k) => v.run_checks[k]?.verdict === "PASS"),
      Object.entries(v.run_checks).map(([k, c]) => `${k} ${c.verdict}`).join(", "));

    // ── 6 · Send again: nothing more is written ──
    const before = v.counts;
    const again = await page.request.post(`${API()}/billing/runs/${sep}/issue`, {
      data: { issued_at: new Date().toISOString() },
    });
    const againBody = await again.json().catch(() => ({}));
    v = verifier(sep);
    const same = ["issued", "invoices", "journals", "deliveries", "issue_audits", "releases", "estimates"].every(
      (k) => v.counts[k] === before[k],
    );
    record("6 Send again", "a second Send issues nothing", again.ok() && same && passes(v, "S6.once"),
      `HTTP ${again.status()} created ${(againBody as Json).created}; before ${JSON.stringify(before)} after ${JSON.stringify(v.counts)}`);

    // ── 7 · Month two ──
    let planted = "";
    try {
      planted = await postOctoberReading(page);
    } catch (e) {
      planted = String(e);
    }
    record("7 Month two", "October's reading accepted by Meter Reads' import (stage → validate → post)",
      planted.startsWith("batch "), planted);
    const afterPlant = verifier(sep).records.meter_reads;
    const oct = afterPlant.find((m) => m.read_at.startsWith("2026-10-31"));
    const sepEst = afterPlant.find((m) => m.read_at.startsWith("2026-09-30") && m.source === "estimated");
    record("7 Month two", "October's actual reading is in Meter Reads and trues up the estimate",
      !!oct && money(oct.current_value) === 173 && money(oct.consumption) === TRUE_UP,
      oct ? `Oct 31 ${oct.current_value}, consumption ${oct.consumption} ${oct.unit}, trues up ${JSON.stringify(oct.trues_up_read_ids)}; ` +
        `Sep estimate ${sepEst ? `${sepEst.consumption} ${sepEst.lifecycle}` : "missing"}` : "no Oct 31 reading");
    await page.goto(`/${tenant()}/dashboard`);
    const octRun = await scopeAndStart(page, {
      name: "October 2026 · Riverside (E17 trace)",
      start: "2026-10-01",
      end: "2026-10-31",
      bill: "2026-11-01",
    });
    let v2 = verifier(octRun);
    // If October asks anything of this account, answer it with a billing (non-hold) choice.
    for (const f of v2.records.findings.filter((x) => x.severity === "decision")) {
      const box = page.locator(`[data-tag=${f.code}]`);
      if ((await box.count()) === 0) continue;
      await box.first().click();
      const pane = page.locator(`[data-tag-pane=${f.code}]`);
      const select = pane.getByRole("combobox", { name: `Decide for ${ACCOUNT}` });
      if ((await select.count()) === 0) continue;
      const labels = (await select.locator("option").allInnerTexts()).filter((l) => l !== "Choose");
      const choice = labels.find((l) => !/Hold|Look into|Waive/i.test(l));
      if (choice) await answerRow(page, f.code, choice);
    }
    v2 = verifier(octRun);
    record("7 Month two", "October's Check lets the account through",
      ["ready", "decision"].includes(v2.records.check.status) && !v2.records.findings.some((f) => f.code === "missing_read"),
      `status ${v2.records.check.status}; findings ${v2.records.findings.map((f) => f.code).join(", ") || "none"}`);
    await priceAndSignOff(page);
    await signOffAndSend(page);
    v2 = verifier(sep, ["--next-run", octRun]);
    const m2 = verifier(octRun).records.bills[0];
    record("7 Month two", "October billed and issued", !!m2 && m2.status === "issued",
      m2 ? `${m2.invoice_no} ${m2.period} ${m2.total}` : "no October bill");
    record("7 Month two", "starts the day after September's bill (Oct 1)", passes(v2, "M2.next")
      && !!m2 && m2.period.startsWith("2026-10-01"), failsOf(v2, "M2.next") || m2?.period || "");
    record("7 Month two", "no base charge twice", passes(v2, "M2.base") && !!m2 && bases(m2).length === 1,
      failsOf(v2, "M2.base") || `${m2 ? bases(m2).length : 0} base line(s)`);
    const octWater = m2 ? water(m2).reduce((s, l) => s + money(l.quantity), 0) : NaN;
    record("7 Month two", "the estimate is trued up: October bills 7 kgal, 15 over both months",
      passes(v2, "M2.usage") && octWater === TRUE_UP,
      `October water ${octWater} kgal; ${failsOf(v2, "M2.usage") || verdictOf(v2, "M2.usage")}`);
    record("7 Month two", "October bill's own after-Send checks",
      ["S6.issued", "S6.draft", "S6.ledger", "S5.delivery", "S5.reads", "S6.audit", "S6.once", "S5.jobs"].every(
        (k) => verifier(octRun).accounts[0]?.verdict[k] === "PASS"),
      JSON.stringify(verifier(octRun).accounts[0]?.verdict ?? {}));
  });
});
