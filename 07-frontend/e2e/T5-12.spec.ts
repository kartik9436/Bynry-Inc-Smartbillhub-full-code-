// ── Trace ──────────────────────────────────────────────
// Journey:  T5-12 — Negative-usage auto-fix attempt (the hard error stands).
//           `08-qa/01-e2e/journeys/T5-12-negative-usage-auto-fix.md` is the
//           spec; this file walks its five-row step table in order.
// Story:    US-MET-008 (validation + flagging) · US-MET-011 (the read
//           validation rule page) · US-MET-012 (staged batches commit nothing
//           until every error is resolved) · US-IDN-001 (sign in)
//           Screens: S3 · S25 Reads · S28 read import (staging)
// Rules:    BR-MET-052 (negative usage is a HARD ERROR, never auto-fixed) ·
//           BR-MET-019 (the consumption formula, unrounded) · BR-MET-015 (an
//           error is cleared only by an explicit reason-coded disposition) ·
//           BR-MET-016 (corrections to committed history travel as supersede
//           rows) · BR-MET-012 (nothing commits from staging)
// Money:    NONE. No step of this journey renders a money figure on any
//           surface, so `moneyTriple` is not called — borrowing a figure from
//           another journey to satisfy the house rule would be a money claim
//           about a screen this journey never opens.
// Tests:    this file. Fixture: built THROUGH the product by `priorRead()`
//           below (stage → validate → certify → post), because
//           08-qa/01-e2e/stack/seed_e2e_fixture.py seeds no committed reads.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// THE SPLIT THIS JOURNEY EXPOSES, and why the tests are ordered the way they
// are: the reads ENGINE (stage · validate · disposition · commit) is served and
// complete — eleven endpoints under `/reads` and `/read-batches`. The read
// IMPORT SCREEN is not: `07-frontend/src/App.tsx` mounts `reads`, `reads/routes`
// and `reads/cycles`, and S28 has no route at all. So a clerk cannot perform
// step 1 of this journey by clicking, while the rule step 1 is about is
// implemented and correct.
//
// Each step therefore asserts BOTH halves where they exist: the engine's
// behaviour (which is the rule) and the clerk's reachability (which is the
// product). The tests are NOT serial — each builds its own precondition — so
// the run reports which individual rows hold rather than stopping at the first
// that does not.
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

// The journey's fixture, verbatim: meter ×1 multiplier, channel `total`,
// prior committed read 45,210 (2026-06-14), import row 44,890 (2026-07-14)
// → BR-MET-019 computes −320 kWh.
const METER = "M-7001";
const PRIOR_VALUE = "45210";
const PRIOR_DATE = "2026-06-14";
const CURRENT_VALUE = "44890";
const CURRENT_DATE = "2026-07-14";
const EXPECTED_DROP = "320.000000";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface BatchRow {
  row_no: number;
  value: string;
  severity: string;
  disposition: string | null;
  meter_read_id: string | null;
  rule_outcomes: { rule: string; severity: string; detail: Record<string, unknown> }[];
}

/** Ensures a committed prior read exists. Idempotent across suite re-runs. */
async function priorRead(request: APIRequestContext): Promise<void> {
  const reads = await request.get(api("/reads?per=200"));
  expect(reads.status()).toBe(200);
  const existing = ((await reads.json()) as { results: { current_value: string }[] }).results;
  if (existing.some((r) => r.current_value === "45210.000000")) {
    return;
  }
  const staged = await request.post(api("/read-batches"), {
    data: {
      source_kind: "manual",
      period_month: "2026-06-01",
      rows: [{ meter_id: METER, read_date: PRIOR_DATE, reading: PRIOR_VALUE, channel: "total" }],
    },
  });
  expect(staged.status(), "the T5-12 fixture prior read could not be staged").toBe(201);
  const id = ((await staged.json()) as { id: string }).id;
  expect((await request.post(api(`/read-batches/${id}/validate`))).status()).toBe(200);
  expect(
    (await request.post(api(`/read-batches/${id}/post`), { data: { certified: true } })).status(),
  ).toBe(200);
}

/** Stages the journey's July file and validates it. Returns the batch id. */
async function stageJulyFile(request: APIRequestContext): Promise<string> {
  const staged = await request.post(api("/read-batches"), {
    data: {
      source_kind: "csv",
      period_month: "2026-07-01",
      file_name: "reads-CYC-A-2026-07.csv",
      rows: [
        { meter_id: METER, read_date: CURRENT_DATE, reading: CURRENT_VALUE, channel: "total" },
      ],
    },
  });
  expect(staged.status()).toBe(201);
  const id = ((await staged.json()) as { id: string }).id;
  const validated = await request.post(api(`/read-batches/${id}/validate`));
  expect(validated.status()).toBe(200);
  return id;
}

async function batchRows(request: APIRequestContext, id: string): Promise<BatchRow[]> {
  const response = await request.get(api(`/read-batches/${id}`));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { rows: BatchRow[] }).rows;
}

journey("T5-12", "Negative-usage auto-fix attempt — the hard error stands", () => {
  skipUnlessAppServer(test);

  test("step 1 — the row flags ERROR with the threshold math, and NOTHING is auto-corrected", async ({
    page,
  }) => {
    await signIn(page);
    await priorRead(page.request);
    const batch = await stageJulyFile(page.request);
    const rows = await batchRows(page.request, batch);

    expect(rows).toHaveLength(1);
    const row = rows[0];
    expect(row.severity, "BR-MET-052: negative usage is an ERROR, never a warning").toBe("error");

    const negative = row.rule_outcomes.find((o) => o.rule === "negative_usage");
    expect(negative, "the negative-usage rule must have been evaluated").toBeDefined();
    expect(negative?.severity).toBe("error");
    // BR-MET-019's math SHOWN, unrounded: 45,210 → 44,890 = −320.
    expect(String(negative?.detail.prior)).toBe("45210.000000");
    expect(String(negative?.detail.current)).toBe("44890.000000");
    expect(String(negative?.detail.drop)).toBe(EXPECTED_DROP);
    // The whole point of the journey.
    expect(negative?.detail.auto_fix, "BR-MET-052: no auto-fix of any kind").toBe(false);

    // Staged only, and the stored value is EXACTLY as filed — no swap, no abs,
    // no rollover rewrite.
    expect(row.value).toBe("44890.000000");
    expect(row.meter_read_id, "BR-MET-012: staging commits no meter_reads row").toBeNull();
  });

  test("step 2 — the commit is refused while the error is unresolved", async ({ page }) => {
    await signIn(page);
    await priorRead(page.request);
    const batch = await stageJulyFile(page.request);

    const post = await page.request.post(api(`/read-batches/${batch}/post`), {
      data: { certified: true },
    });
    expect(post.status(), "BR-MET-015: errors must be resolved before post").toBe(422);
    const refusal = (await post.json()) as { br_ref: string; message_key: string };
    expect(refusal.br_ref).toBe("BR-MET-015");
    expect(refusal.message_key).toContain("errors_need_resolution");

    // Billing inputs untouched: no committed read for this meter/date.
    const reads = await page.request.get(api("/reads?per=200"));
    const committed = ((await reads.json()) as { results: { period_end: string }[] }).results;
    expect(
      committed.some((r) => r.period_end === CURRENT_DATE),
      "no meter_reads row may exist for the refused date",
    ).toBe(false);
  });

  test("step 3 — a bulk accept-warnings sweep never carries an ERROR row along", async ({
    page,
  }) => {
    await signIn(page);
    await priorRead(page.request);
    const batch = await stageJulyFile(page.request);

    // The sweep a clerk would reach for: accept everything that is merely a
    // warning. BR-MET-015 says an ERROR needs its own explicit disposition, so
    // whatever this call does it must NOT clear the row.
    await page.request.patch(api(`/read-batches/${batch}/rows/1`), {
      data: { disposition: "accept" },
    });
    const rows = await batchRows(page.request, batch);
    expect(rows[0].severity, "the ERROR row must still be an error after the sweep").toBe("error");
    const post = await page.request.post(api(`/read-batches/${batch}/post`), {
      data: { certified: true },
    });
    expect(post.status(), "the commit must still be blocked").toBe(422);
  });

  test("step 4 — no autofix path exists at any address", async ({ page }) => {
    await signIn(page);
    await priorRead(page.request);
    const batch = await stageJulyFile(page.request);

    for (const path of [
      `/read-imports/rows/1/autofix`,
      `/read-batches/${batch}/rows/1/autofix`,
      `/read-batches/${batch}/autofix`,
    ]) {
      const response = await page.request.post(api(path), { data: {} });
      expect(
        [404, 405],
        `${path} answered ${response.status()} — BR-MET-052 says "never auto-fixed" is ` +
          "a system property, so no such path may exist",
      ).toContain(response.status());
    }
  });

  test("step 5 — RECOVERY: an explicit reason-coded disposition clears the row and the batch commits", async ({
    page,
  }) => {
    await signIn(page);
    await priorRead(page.request);
    const batch = await stageJulyFile(page.request);

    // Door (b) of the journey's three: data-entry error → REJECT the row with
    // its reason. The disposition, not the sweep, is what BR-MET-015 accepts.
    const disposition = await page.request.patch(api(`/read-batches/${batch}/rows/1`), {
      data: { disposition: "reject", reason: "data_entry_error" },
    });
    expect(
      disposition.status(),
      `the reason-coded disposition answered ${disposition.status()}`,
    ).toBe(200);

    const rows = await batchRows(page.request, batch);
    expect(rows[0].disposition, "the disposition must be STORED per row").toBe("reject");

    const post = await page.request.post(api(`/read-batches/${batch}/post`), {
      data: { certified: true },
    });
    expect(
      post.status(),
      `the commit after every error is resolved answered ${post.status()}: ${await post.text()}`,
    ).toBe(200);

    // Exactly one truthful consumption reaches rating: the rejected value is
    // NOT committed, and the original filed value stays visible in the batch.
    const reads = await page.request.get(api("/reads?per=200"));
    const committed = ((await reads.json()) as { results: { current_value: string }[] }).results;
    expect(
      committed.some((r) => r.current_value === "44890.000000"),
      "a rejected row must never reach meter_reads",
    ).toBe(false);
    expect((await batchRows(page.request, batch))[0].value).toBe("44890.000000");
  });

  test("reachability — a clerk must be able to run step 1 by clicking", async ({ page }) => {
    // The PO's 2026-08-11 ruling is the reason this test exists beside the five
    // above: *"we ahve to prove against human clicking"*. Every rule this
    // journey tests is implemented; the question this row asks is whether the
    // clerk in the step table can reach it.
    await signIn(page);
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Reads", exact: true }).first().click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/reads`));
    await expect(
      page.getByRole("button", { name: /import/i }).or(page.getByRole("link", { name: /import/i })).first(),
      "S25 must offer the read import the journey's step 1 starts from (S28)",
    ).toBeVisible();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-12 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the tests are NOT serial: each builds its own precondition so
//   the run reports which of the journey's five rows hold, rather than stopping
//   at the first that does not · (2) the fixture (a committed prior read) is
//   built THROUGH the product, because the seed script commits none · (3) the
//   five rule steps are driven at the API, and the separate reachability row
//   states plainly that S28 has no route — the rule is implemented, the clerk
//   cannot reach it, and both are reported
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
