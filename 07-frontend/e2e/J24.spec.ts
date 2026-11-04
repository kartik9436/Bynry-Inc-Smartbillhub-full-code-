// ── Trace ──────────────────────────────────────────────
// Journey:  J24 — the five-phase bill run (08-qa/01-e2e/journeys/J24-five-phase-bill-run.md).
//           THE FIRST ACTIVATED CATALOG JOURNEY IN THIS REPO. 0 of 304 had ever
//           run; this file is the one that makes the number 1, and it is
//           deliberately authored to FAIL where the product cannot perform the
//           step rather than to report a shape it did not execute.
// Story:    US-BIL-001 (step 1 — the idempotent run) · US-BIL-002 (step 2,
//           S31.2 findings) · US-BIL-003 (step 3, S31.3 decisions + bulk) ·
//           US-BIL-004 (step 4 — the background batch and the breaks) ·
//           US-BIL-005 (steps 5/6 — summary, the five-fact gate, release) ·
//           US-BIL-006 (the pending queue the tail catches up through) ·
//           US-BIL-029 (stage 6 assemble) · US-IDN-001 (sign in, S3)
//           Screens: S3 · shell-chrome · S30 · S31 · S31.2 · S31.3
// Rules:    BR-BIL-050 (the run row every later phase hangs off) · BR-BIL-005
//           (a repeat is REFUSED with who/when/link) · BR-BIL-061 (the base-only
//           cohort is a recorded choice with NO pre-committed default) ·
//           BR-BIL-062 (no prior read prices at the plan minimum, prorated) ·
//           BR-BIL-060 (bulk — N rows, ONE bulk_action_id) · BR-BIL-003 (a
//           first-time waiver is never bulk) · BR-BIL-051/052 (calculate is a
//           background batch; nothing money-bearing exists when it ends) ·
//           BR-BIL-053/054/055 (breaks come BEFORE the totals) · BR-BIL-056/
//           057/058/059 (the summary panel, its axes, the five confirmations,
//           the release record) · BR-BIL-015 (hold ≠ forget) · BR-BIL-064 /
//           OQ-120 (a replacement counts; the chain has no column, so the panel
//           REFUSES) · BR-SHL-020 (a failure is a plain-language sentence)
// Tests:    this file. Its stack is `08-qa/01-e2e/stack/boot_stack.sh`; its
//           world is `manage.py seed_demo` + `seed_e2e_fixture.py`.
// Impacts:  10-scripts/gates/g12_journeys.py (this file makes `activated`
//           non-empty for the first time, so `--wave-close` now reads the run
//           receipt for J24) · e2e/support/census.ts (writes that receipt) ·
//           nothing in 06-backend/apps/** or 07-frontend/src/**
// ───────────────────────────────────────────────────────
//
// WHY THIS SPEC IS SHAPED AS NINE TESTS AND NOT ONE
//
// J24's contract is a NINE-ROW STEP TABLE. A single test would report one
// verdict for nine independent claims and stop at the first gap, which is the
// precise failure mode `e2e/README.md` was written against: a result that reads
// as a summary and answers nothing. One test per step means the runner's own
// output IS the step table with a verdict per row, and the run receipt records
// the journey's status as the WORST of them (support/census.ts). Deliberately
// NOT `mode: "serial"` — a serial file turns every step after a failure into a
// SKIP, and "skipped" in the receipt would say the step was never asked when in
// fact it was never reachable. Each test states its own truth.
//
// THE RUN IS CARRIED IN THE URL, BY DESIGN AND NOT BY CONVENIENCE. BR-BIL-050:
// *"the run lives in the URL, not in React state … a wizard whose run id
// evaporates on a refresh is the browser-owned wizard that ruling forbids"*
// (BillRunWizard.tsx). So `openRun()` below keeps the created run's URL the way
// a clerk keeps a tab open, and every later step re-enters through it. That is
// the only resume path this product has — which is itself one of this run's
// findings, recorded at step 1.
//
// WHAT THIS SPEC WILL NOT DO, and the whole value of the exercise is here:
// it does not soften a step to reach green. Where the product cannot perform a
// step, the assertion is written against J24's contract and the test goes RED
// with the product's own words quoted back. Six of the nine steps have no
// surface at all today (`apps/billing/api.py` names each absence and its
// reason), so six of the nine assertions below are assertions that the screen's
// own "this is not built" panel is ABSENT. That panel disappearing is exactly
// what "the step now works" looks like, so these are the assertions that turn
// green on the day the phase lands and not one day earlier.
//
// WHY THE MONEY DOES NOT COME FROM `moneyTriple`. e2e/README.md's activation
// contract says a journey asserts its money through the 245-row expectation
// dataset. J24 cites NO row of it: its figures ($247.87 / $292.87 / $105.36)
// are its own fixture's, and the dataset is keyed (shape × bill_type × payment)
// with no row carrying any of them. That claim is not left as prose — the first
// test below PROVES it against the loader, and the figures are READ OUT OF THE
// JOURNEY FILE at run time rather than retyped here, for the same reason
// `W3-money-render.spec.ts` reads GT-1 out of B5: a second copy of a stated
// figure is the drift DEF-028 already cost this repo once.
import { expect, test } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { loadMoneyTriples } from "./support/expected";
import { journey } from "./support/journey";

// e2e → 07-frontend → repo root.
const REPO_ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)), "../..");
const JOURNEY_FILE = resolve(REPO_ROOT, "08-qa/01-e2e/journeys/J24-five-phase-bill-run.md");

/**
 * J24's step-7 row, read from the journey file — the only place its money is
 * stated. The row bolds every figure it asserts (`**247.87**`), so the bolded
 * decimals of that row ARE the step's money, in order: ACC-1042's current
 * charges, its total due, and ACC-1077's total.
 *
 * A parse that found the wrong count of figures would make every later
 * assertion compare rendered text to a number nobody wrote down, so the count
 * is checked in the first test before anything is driven.
 */
function j24Step7Figures(): string[] {
  const text = readFileSync(JOURNEY_FILE, "utf-8");
  const row = text.split(/\r?\n/).find((line) => line.startsWith("| 7 |"));
  if (row === undefined) {
    throw new Error(`no step-7 row in ${JOURNEY_FILE} — the journey's step table moved`);
  }
  return [...row.matchAll(/\*\*(\d+(?:\.\d{2}))\*\*/g)].map((match) => match[1]);
}

const [ACC_1042_CURRENT, ACC_1042_TOTAL_DUE, ACC_1077_TOTAL] = j24Step7Figures();

// en-US + USD is what MoneyCell renders with (DEFAULT_MONEY_LOCALE). The DIGITS
// come from the journey file; only the symbol is here.
function asRendered(figure: string): string {
  return `$${figure}`;
}

// J24's fixture period — "period **Jul 1–31, 2026**, bill date Aug 1". Dates,
// not money: they are the run's identity under BR-BIL-005's idempotency key and
// they are typed here because a journey's own window is what it means to run
// THAT run. Event time is a PARAMETER, never a clock read (BR-TEN-043).
const PERIOD_START = "2026-07-01";
const PERIOD_END = "2026-07-31";
const BILL_DATE = "2026-08-01";

// The run URL the wizard put its run id into, carried between steps the way a
// clerk carries a browser tab.
//
// ON DISK, AND THAT IS A HARNESS DEFECT THIS FILE PAID FOR. It was a
// module-level `let` for the first live run, and Playwright CREATES A NEW WORKER
// PROCESS AFTER A FAILING TEST to guarantee a clean environment — so the moment
// step 1's second test went red (it does; see below), module state reset and
// every one of steps 2–9 re-entered the create branch, was refused by
// BR-BIL-005, and reported *"expected /[?&]run=/"* instead of its own verdict.
// Nine steps reporting one bookkeeping failure is exactly the uninformative
// result this journey exists to replace, so the tab a clerk keeps open is
// modelled by a file that survives a worker restart, reset by the first test so
// a fresh suite never resumes a run from a dropped database.
//
// NOT under `test-results/`, and that is the second half of the same lesson:
// **Playwright DELETES its output directory at the START of every run**, so a
// second lane starting a suite would wipe this file — and the census receipt
// beside it — out from under a run already in flight. Measured in this session,
// with three suites running at once. It lives beside the stack's own run
// directory instead (`08-qa/01-e2e/stack/boot_stack.sh` uses /tmp/sbh-e2e-stack
// for the same reason), and takes its lane from E2E_RUN_DIR when one is set.
const RUN_URL_FILE = resolve(
  process.env.E2E_RUN_DIR ?? "/tmp",
  `sbh-j24-run-url-${process.env.E2E_TENANT ?? "brazosbend"}.txt`,
);

function rememberRun(url: string): void {
  mkdirSync(dirname(RUN_URL_FILE), { recursive: true });
  writeFileSync(RUN_URL_FILE, url, "utf-8");
}

function rememberedRun(): string | null {
  // `try` rather than `existsSync`, and an empty file rather than a delete, so
  // this needs no addition to `support/node-shims.d.ts` — a file three other
  // lanes are editing in this same session (DEF-054's hazard, one directory up).
  try {
    return readFileSync(RUN_URL_FILE, "utf-8").trim() || null;
  } catch {
    return null;
  }
}

/** Sign in and land on S31 step 1 with an empty form (the clerk's own entry). */
async function openWizard(page: import("@playwright/test").Page): Promise<void> {
  await signIn(page);
  await page.goto(`/${tenant()}/billing/run`);
  // The cycle SELECT replaces a loading skeleton once `GET /cycles` answers;
  // waiting on the control rather than on a timeout means a cycle list that
  // never loads fails as itself instead of as a mis-filled form.
  await page.locator("#brun-cycle").waitFor();
}

/** Fill step 1 exactly as S31 asks for it, then click Start. */
async function fillAndStart(page: import("@playwright/test").Page): Promise<void> {
  // BY INDEX, not by code: J24's fixture names cycle 07-A and the seeded tenant
  // has 08-A/08-B, so naming a code here would hard-code one fixture's
  // reference data (the same reasoning W4 records for the payment method).
  // Index 1 is the first real cycle — index 0 is the "Choose a cycle" placeholder.
  await page.locator("#brun-cycle").selectOption({ index: 1 });
  await page.locator("#brun-period-start").fill(PERIOD_START);
  await page.locator("#brun-period-end").fill(PERIOD_END);
  await page.locator("#brun-bill-date").fill(BILL_DATE);
  // J24 step 1: "scope = all services". The chips' <input> is visually replaced
  // by its dot, so a human clicks the LABEL and so does this.
  for (const code of ["electric", "water"]) {
    await page.locator(`label[for="brun-service-${code}"]`).click();
  }
  await page.getByRole("button", { name: /Start this run/ }).click();
}

/**
 * Re-enter the run created by step 1 at a given wizard step.
 *
 * Steps 2–9 all need the run that step 1 made. The product offers NO other way
 * back to it (see step 1's second test), so the URL is the resume path and this
 * helper is honest about that rather than reaching into the database for an id
 * a clerk could not have.
 */
async function openRun(page: import("@playwright/test").Page, step: number): Promise<void> {
  let runUrl = rememberedRun();
  if (runUrl === null) {
    await openWizard(page);
    await fillAndStart(page);
    await expect(page).toHaveURL(/[?&]run=/);
    runUrl = page.url();
    rememberRun(runUrl);
  } else {
    await signIn(page);
  }
  const url = new URL(runUrl);
  url.searchParams.set("step", String(step));
  await page.goto(`${url.pathname}${url.search}`);
  await expect(page.locator('[data-brun="h"]')).toBeVisible();
}

/** The screen's own "this phase is not built" note (RunGap), by its heading. */
function gap(page: import("@playwright/test").Page, heading: string | RegExp) {
  return page.locator('[data-brun="gap"]').filter({ hasText: heading });
}

journey("J24", "the five-phase bill run — prepare → calculate → breaks → summary + gate → release", () => {
  skipUnlessAppServer(test);

  test("the figures this journey asserts are the ones its own file states", () => {
    // The suite's reset point: a fresh selection starts a fresh run, so a URL
    // left by an earlier run against a database that has since been dropped can
    // never be resumed into (see RUN_URL_FILE).
    rememberRun("");

    // Not ceremony. Every money assertion below compares rendered text to a
    // number parsed out of a markdown table, and a parser that silently mis-read
    // would make the whole journey assert the wrong thing while looking healthy.
    expect(j24Step7Figures()).toHaveLength(3);
    expect(ACC_1042_CURRENT).toBe("247.87");
    expect(ACC_1042_TOTAL_DUE).toBe("292.87");
    expect(ACC_1077_TOTAL).toBe("105.36");

    // And the machine proof of this file's header claim: the 245-row expectation
    // dataset — the source e2e/README.md makes the default for journey money —
    // carries NO row for any of J24's figures, which is why they are read from
    // the journey file instead. If a regenerated dataset ever DOES carry them,
    // this goes red and the money source for J24 should move to `moneyTriple`.
    const totals = new Set(loadMoneyTriples().map((row) => row.total));
    expect(totals.size).toBeGreaterThan(0);
    for (const figure of [ACC_1042_CURRENT, ACC_1042_TOTAL_DUE, ACC_1077_TOTAL]) {
      expect(totals.has(figure)).toBe(false);
    }
  });

  // ── STEP 1 · PHASE 1 PREPARE ─────────────────────────────────────────────
  // "Priya starts run 07-A (S31 step 1), scope = all services."
  // Handoff: ONE `bill_runs` row, status = phase 1, period Jul 1–31, scope
  // recorded even when it is "all of them"; `idempotency_key` set.
  test("step 1 · starting the run leaves ONE run the wizard then works from", async ({ page }) => {
    await openWizard(page);
    await fillAndStart(page);

    // The run row exists and the wizard is working from it: BR-BIL-050 puts the
    // id in the URL, and step 2 is where a created run lands.
    await expect(page).toHaveURL(/[?&]run=[0-9a-f-]{36}/);
    await expect(page).toHaveURL(/[?&]step=2/);
    rememberRun(page.url());
    // The period the run was scoped to is the period it reports back.
    await expect(page.locator('[data-brun="phase"]')).toContainText("Prepare");
  });

  // Downstream: "A second identical (tenant, cycle, period) is REFUSED with
  // who/when/link — no second row. Closing the wizard and re-opening from S30
  // returns to the same run at the phase its status names."
  test("step 1 · a second identical run is refused with who, when and a link back", async ({
    page,
  }) => {
    await openWizard(page);
    await fillAndStart(page);

    // Refused: the wizard must NOT advance, because no second run exists.
    await expect(page).not.toHaveURL(/[?&]step=2/);
    const refusal = page.locator('[data-brun="failure"]');
    await expect(refusal).toBeVisible();

    // BR-BIL-005's three facts, as the rule states them. The server sends all
    // three in the 409 envelope (`run_id`, `ran_by`, `ran_at`); this asserts
    // that a human READS them, which is the half no API test can see.
    await expect(refusal).not.toHaveText(/^billing\./); // a message key is not a message
    await expect(refusal).toContainText(/already|second|ran/i);
    // …and the LINK the rule names, so the clerk can get back to the run they
    // already have. This is also the only resume path the product could offer:
    // the S30 "Past billing runs" tab is an arrives-later placeholder.
    await expect(refusal.getByRole("link")).toHaveCount(1);
  });

  // ── STEP 2 · PHASE 1 PREPARE — "Check what we found" ─────────────────────
  // Handoff: nothing written; stages 1–5 run as PREVIEW; "consumption shown per
  // service **with its explicit unit**".
  // Downstream: the base-only cohort with a count and NO pre-committed default;
  // the no-prior-read account is NOT under Missing reads; zero `invoices` rows.
  test("step 2 · the findings review shows consumption per service with its unit", async ({
    page,
  }) => {
    await openRun(page, 2);

    // A run whose ready cohort is empty has nothing to review, and J24 step 2 is
    // a REVIEW of what will be billed. This is the assertion that says whether
    // the product can perform the step at all.
    const ready = page.locator(".kpi").filter({ hasText: /ready to bill/i });
    await expect(ready).toHaveCount(1);
    await expect(ready.locator(".v")).not.toHaveText("0");

    // CLAUDE.md rule 3 — a quantity never travels without its unit. The seeded
    // tenant meters kWh and kgal; whichever a ready account carries, a unit is
    // rendered beside the number and never inferred.
    await expect(page.locator('[data-brun="svc"]').first()).toHaveText(/\b(kWh|kgal|ccf|kW)\b/);
  });

  test("step 2 · the base-only cohort is offered with a count and no default chosen", async ({
    page,
  }) => {
    await openRun(page, 2);

    // BR-BIL-061: ACC-1077 (vacation hold) + ACC-1602 (suspended) are a COHORT
    // with a count, and nothing is pre-committed for them — the choice is step
    // 3's. The screen states the undecided half in words, which is the part a
    // pre-selected control would silently destroy.
    await expect(page.getByText(/Standing charges only — \d+ customers/)).toBeVisible();
    await expect(page.getByText(/Not decided\./)).toBeVisible();
    // The cohort must not be empty: a cohort of nobody cannot be opted in or out,
    // and step 3's decision has no subject.
    const cohort = page.locator(".kpi").filter({ hasText: /standing charges only/i });
    await expect(cohort.locator(".v")).not.toHaveText("0");
  });

  // ── STEP 3 · PHASE 1 PREPARE — the decisions ─────────────────────────────
  // Handoff: one `bill_run_decisions` row PER ACCOUNT; the rows from one click
  // share ONE `bulk_action_id`.
  // Downstream: the confirm dialog showed selection count and Σ fee BEFORE the
  // click; bulk WAIVE is refused; a later change of mind APPENDS.
  test("step 3 · the whole late-fee candidate set is applied in ONE click", async ({ page }) => {
    await openRun(page, 3);

    // The case categories carry COUNTS — a category whose size is unknown cannot
    // be selected whole, which is the capability BR-BIL-060 exists for
    // ("it is impossible for user to do this manually account by account").
    const lateFee = page.locator('[data-brun="caselist"] button, [data-brun="caselist"] a').filter({
      hasText: /Late fee due/,
    });
    await expect(lateFee).toHaveCount(1);
    await expect(lateFee).not.toContainText("—");
    await lateFee.click();

    // Select every row in the category and apply in one click.
    await page.getByRole("checkbox", { name: /Select every row in this category/ }).check();
    await expect(page.locator('[data-brun="selcount"]')).not.toContainText("0 selected");

    // BR-BIL-060: the confirm dialog shows the selection count AND the Σ fee
    // BEFORE the click — a bulk money action whose total is unknown at the
    // moment of confirming is the one thing this step exists to prevent.
    await page.getByRole("button", { name: /Apply for the selected/ }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(/worth \$/);
  });

  test("step 3 · bulk WAIVE is refused — a first-time waiver is per-case", async ({ page }) => {
    await openRun(page, 3);

    const lateFee = page.locator('[data-brun="caselist"] button, [data-brun="caselist"] a').filter({
      hasText: /Late fee due/,
    });
    await lateFee.click();
    await page.getByRole("checkbox", { name: /Select every row in this category/ }).check();

    // BR-BIL-003. The control exists and is DISABLED WITH ITS REASON
    // (BR-SHL-025) — an absent control would leave the clerk guessing.
    const waive = page.getByRole("button", { name: /Waive for the selected/ });
    await expect(waive).toBeDisabled();
    await expect(page.getByText(/decided one customer at a time/)).toBeVisible();
  });

  // ── STEP 4 · PHASE 2 CALCULATE ───────────────────────────────────────────
  // "Priya continues — and closes the browser." The run is SUBMITTED as a
  // background batch; output = DRAFT invoices + invoice_lines; nothing
  // money-bearing exists when it ends.
  test("step 4 · continuing SUBMITS the calculation as a background batch", async ({ page }) => {
    await openRun(page, 4);

    // BR-BIL-051/052. The screen's own note is the product saying it cannot
    // keep this promise; the step is performed when that note is gone.
    await expect(gap(page, "The billing itself runs in the background")).toHaveCount(0);

    // Output: DRAFT invoices for the ready set. A calculated run that produced
    // nothing has not calculated.
    const drafts = page.locator(".kpi").filter({ hasText: /draft bills/i });
    await expect(drafts.locator(".v")).not.toHaveText("0");
  });

  // ── STEP 5 · PHASE 3 BREAKS ──────────────────────────────────────────────
  // Shown BEFORE the totals: account · failing stage BY NAME · staff-readable
  // reason; retry re-runs stages 1–6 for one account; the other two become
  // `bill_run_exclusions`.
  test("step 5 · the breaks are listed before the totals, each naming its stage", async ({
    page,
  }) => {
    await openRun(page, 4); // the wizard draws breaks and totals on one step

    // BR-BIL-053/055.
    await expect(gap(page, "The broken bills cannot be listed yet")).toHaveCount(0);
    // BR-BIL-054: ACC-3020's 312 % draft is a POST-calculation exception listed
    // here with its required actions — it never stopped the batch.
    await expect(gap(page, "The flagged bills cannot be listed yet")).toHaveCount(0);
  });

  // ── STEP 6 · PHASE 4 SUMMARY + GATE ──────────────────────────────────────
  // ONE `bill_run_releases` row: summary jsonb + account_count · bill_count ·
  // total_amount + currency, and the confirmations with confirmed_by/at. The
  // panel carries accounts · bills · consumption per service each with its unit
  // · amount with currency · category breakdowns.
  test("step 6 · the summary panel carries accounts, bills, consumption and amount", async ({
    page,
  }) => {
    await openRun(page, 5);

    // BR-BIL-056. "Not worked out" is the screen refusing to state a figure it
    // cannot compute — correct behaviour, and precisely what makes the step
    // unperformable: there is nothing to sign off on.
    const summary = page.locator('[data-brun="section"]').filter({ hasText: /What this run adds up to/ });
    await expect(summary).toHaveCount(1);
    await expect(summary).not.toContainText("Not worked out");
  });

  test("step 6 · release is refused while any of the five confirmations is untaken", async ({
    page,
  }) => {
    await openRun(page, 5);

    // BR-BIL-058/059 — the refusal NAMES the missing confirmation, which is the
    // half that makes five separate facts worth more than one "confirm".
    await expect(page.getByText(/Not ready to send: \d+ confirmations have not been taken/)).toBeVisible();
    // …and the record that sign-off is supposed to leave must be storable. This
    // is the assertion that separates "the gate refuses" from "the gate exists":
    // a gate that can never be satisfied is not a gate.
    await expect(gap(page, "Your sign-off cannot be recorded yet")).toHaveCount(0);
  });

  // ── STEP 7 · PHASE 5 RELEASE ─────────────────────────────────────────────
  // "confirm → Priya is returned to S30." Numbers minted, due dates set, lines
  // frozen, GL stamped, template pinned, documents rendered, delivery queued,
  // the balanced posting handoff emitted; `released_at` stamped at the end.
  test("step 7 · release issues the run and the bills carry their signed totals", async ({
    page,
  }) => {
    await openRun(page, 6);

    // BR-BIL-051. The screen's own gap is the product saying `POST
    // /billing/runs/{id}/issue` is not served (`apps/billing/api.py` states the
    // three things it would need and does not have).
    await expect(gap(page, "The bills cannot be sent yet")).toHaveCount(0);

    // The five confirmations, then the ONE transactional commit.
    for (const confirmation of [
      /I confirm this run meets our compliance checks/,
      /I have seen how many customers can be emailed/,
      /I have seen how many customers have agreed to texts/,
      /I have seen how many customers are on automatic payment/,
      /I confirm these bills are ready to send/,
    ]) {
      await page.getByRole("checkbox", { name: confirmation }).check();
    }
    await page.getByRole("button", { name: /Send all now/ }).click();

    // Returned to S30, and the bills J24 names are issued at the figures it
    // states — read from the journey file, never retyped (see the header).
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing$`));
    const acc1042 = page.getByRole("row").filter({ hasText: "ACC-1042" });
    await expect(acc1042.locator(".cell-money-amount")).toHaveText(
      asRendered(ACC_1042_TOTAL_DUE),
    );
    const acc1077 = page.getByRole("row").filter({ hasText: "ACC-1077" });
    await expect(acc1077.locator(".cell-money-amount")).toHaveText(asRendered(ACC_1077_TOTAL));
  });

  // ── STEP 8 · THE TAIL ────────────────────────────────────────────────────
  // "1,122 issued + 2 queued is a run that worked": the queue rows carry the
  // break's failing stage and are marked phase-3 origin; the run's own status
  // reads COMPLETED, not failed.
  test("step 8 · the run completes with its held accounts queued, not failed", async ({ page }) => {
    await openRun(page, 6);

    // US-BIL-006 / BR-BIL-015 — "hold ≠ forget". `GET /billing/pending` is
    // served; what J24 asserts is that a clerk can SEE the door back, and the
    // run that left two accounts behind still reads as a run that worked.
    await page.goto(`/${tenant()}/billing/history`);
    await expect(page.getByText(/It arrives with the billing run work/)).toHaveCount(0);
    await expect(page.getByText(/completed/i).first()).toBeVisible();
  });

  // ── STEP 9 · THE RECORD IS FIXED, THE SCREEN IS LIVE ─────────────────────
  // (a) re-opening the run shows the panel RECALCULATED; (b) the
  // `bill_run_releases` row is byte-for-byte what it was at confirm. And a run
  // holding a CORRECTED bill REFUSES the whole panel, naming the missing column
  // (`invoices.corrects_invoice_id`, OQ-120).
  test("step 9 · re-opening the run recalculates the panel from its current bills", async ({
    page,
  }) => {
    await openRun(page, 5);

    // BR-BIL-056 + the PO's 2026-08-11 option-B ruling: the panel is a QUERY
    // over the run's current bill set, so it must state a live bill count and a
    // live amount rather than reading back the release row. Both are "Not worked
    // out" today, which is the same absence step 6 names — asserted separately
    // because the two are different claims and the PO ruled on them separately.
    const summary = page.locator('[data-brun="section"]').filter({ hasText: /What this run adds up to/ });
    await expect(summary).toContainText(/Bills produced/);
    await expect(summary).not.toContainText("Not worked out");
    // The live-vs-fixed distinction must be visible to the clerk signing it.
    await expect(page.getByText(/worked out fresh every time/)).toBeVisible();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: J24 (08-qa/01-e2e/journeys/J24-five-phase-bill-run.md) · DEF-057 / PO
//   ruling 2026-08-11 ("we ahve to prove against human clicking") · B12 r3 §5
//   journey activation · gate G12
// generated: 2026-08-15 by the E2E journey-activation lane (group C release gate)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e`✔ · playwright against the live stack booted by
//   08-qa/01-e2e/stack/boot_stack.sh (Postgres db `sbh_j24_lane`, Django :8024,
//   built SPA :8124, one origin) — **14 tests, 2 passed, 12 failed, 42 executed
//   assertions**, receipt `07-frontend/test-results/journey-run.json` records
//   `J24: failed (42)` · `python 10-scripts/gates/run_gates.py --wave-close` →
//   **19 PASS, 2 FAIL, 0 SKIP — MERGE BLOCKED**, G12 naming `journey J24 last
//   ran failed — a wave cannot close red` (its other 51 complaints are the
//   other lanes' journeys, absent from this lane's receipt — DEF-113)
// red-proof (law 7): not staged — EVERY failing assertion below went red against
//   the running product on its first execution, and each quotes what the screen
//   actually showed. The two that PASS are the two the product can perform. The
//   harness itself was also proved wrong and fixed rather than worked around:
//   the run URL was a module-level `let`, Playwright restarts the worker after a
//   failing test, and steps 2–9 all reported `expected /[?&]run=/` — one
//   bookkeeping failure wearing nine hats. Fixed to a file outside
//   `test-results/` (which Playwright deletes at the start of every run), after
//   which all nine reported their own verdicts. That is the only harness change
//   made; no product assertion was softened.
// exceptions, every one REPORTED rather than worked around:
//   (1) THE JOURNEY IS RED AND THAT IS THE FINDING. Six of its nine steps have
//       no product surface (`apps/billing/api.py` names each absence: the issue
//       route, the break list, the phase-4 summary, the release record and
//       `GET /billing/runs/{id}` are none of them served, and TD-17 means there
//       is no job runner to make "background" mean anything). The assertions are
//       written against J24's contract and go green the day the phase lands.
//   (2) THE FIXTURE J24 DESCRIBES DOES NOT EXIST AND NOTHING IN THIS REPO SEEDS
//       IT. J24 wants 1,124 accounts, named breaks and a late-fee candidate set;
//       `seed_demo` + `seed_e2e_fixture.py` give ONE account, ZERO meter reads,
//       ZERO unit plan assignments. Steps 2 and 3 therefore fail on an empty
//       cohort rather than on a missing screen, and the two causes are called
//       apart in the lane report so neither hides the other.
//   (3) the CYCLE is chosen by index, not by code: J24 names cycle 07-A and the
//       seeded tenant has 08-A/08-B, so naming a code would hard-code one
//       fixture's reference data (the reasoning W4 records for payment method).
//   (4) THIS SPEC CREATES A RUN, so it needs a database in which J24's
//       (cycle, period) has none — a fresh `boot_stack.sh` lane database. A
//       re-run against the same database is refused by BR-BIL-005, which is the
//       product behaving correctly and the spec being honest about its fixture
//       rather than deleting a row to make itself repeatable (hard rule 4's
//       spirit: financial rows are appended, never tidied away).
//   (5) money is read from the JOURNEY FILE, not from `moneyTriple` — the
//       245-row dataset carries no row for J24's figures, and the first test
//       proves that against the loader rather than asserting it in prose.
//   (6) step 1's second test fails on a gap that was ALREADY KNOWN and parked:
//       `billing.run.duplicate` is line 59 of 10-scripts/gates/i18n_known_gaps.txt
//       under DEF-055, one of 107 refusal keys no catalogue defines. What is new
//       is not the gap but its COST, which a static register could not show:
//       the parked key is the only thing the 409 renders, so BR-BIL-005's
//       who/when/link never reaches the clerk and J24 step 1's own downstream
//       assertion is unperformable. A copy backlog is blocking a journey step —
//       reported at that severity rather than re-filed as a new defect.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
