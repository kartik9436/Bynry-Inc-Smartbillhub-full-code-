// ── Trace ──────────────────────────────────────────────
// Journey:  T5-16 — Read on a retired meter (error stands; the swap flow is the
//           door). `08-qa/01-e2e/journeys/T5-16-read-on-retired-meter.md` is
//           the spec; this file walks its five-row step table in order.
// Story:    US-MET-008 (read validation + flagging) · US-AST-008 (retire an
//           asset — TERMINAL) · US-AST-009 (reassign with final-read capture) ·
//           US-IDN-001 (sign in)
//           Screens: S3 · S49 Asset registry · S28 read import (staging)
// Rules:    BR-MET-052 (a read filed against a RETIRED meter is a VEE ERROR) ·
//           BR-MET-015 (errors clear only by an explicit reason-coded
//           disposition) · BR-MET-016 (corrections travel as supersede rows)
// Money:    NONE. No step renders a figure; `moneyTriple` is not called rather
//           than borrowed from another journey.
// Tests:    this file. Fixture: built THROUGH the product — a spare meter is
//           retired via `POST /assets/{id}/retire` (US-AST-008), because the
//           seed script retires none.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const RETIRE_DATE = "2026-06-30";
const JULY_READ_DATE = "2026-07-14";
const JULY_READ_VALUE = "45340";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface AssetRow {
  id: string;
  asset_no: string;
  type: string;
  status: string;
  retire_date: string | null;
  actions: string[];
}

/** The journey's MTR-0299: a meter retired 2026-06-30. Idempotent. */
async function retiredMeter(request: APIRequestContext): Promise<AssetRow> {
  const response = await request.get(api("/assets?page_size=100"));
  expect(response.status()).toBe(200);
  const assets = ((await response.json()) as { results: AssetRow[] }).results;

  const already = assets.find((a) => a.type === "meter" && a.retire_date !== null);
  if (already !== undefined) {
    return already;
  }
  // A SPARE meter, so retiring it takes no unit out of service.
  const spare = assets.find((a) => a.type === "meter" && a.status === "inventory");
  expect(spare, "the fixture has no spare meter to retire for this journey").toBeDefined();
  const retire = await request.post(api(`/assets/${(spare as AssetRow).id}/retire`), {
    data: { retire_date: RETIRE_DATE, reason: "T5-16 fixture — retired before the July file" },
  });
  expect(
    [200, 201],
    `retiring the meter answered ${retire.status()}: ${await retire.text()}`,
  ).toContain(retire.status());
  const after = await request.get(api("/assets?page_size=100"));
  const refreshed = ((await after.json()) as { results: AssetRow[] }).results.find(
    (a) => a.id === (spare as AssetRow).id,
  );
  return refreshed as AssetRow;
}

async function stageJulyFile(request: APIRequestContext, meterNo: string): Promise<string> {
  const staged = await request.post(api("/read-batches"), {
    data: {
      source_kind: "csv",
      period_month: "2026-07-01",
      file_name: "reads-2026-07.csv",
      rows: [
        {
          meter_id: meterNo,
          read_date: JULY_READ_DATE,
          reading: JULY_READ_VALUE,
          channel: "total",
        },
      ],
    },
  });
  expect(staged.status()).toBe(201);
  const id = ((await staged.json()) as { id: string }).id;
  expect((await request.post(api(`/read-batches/${id}/validate`))).status()).toBe(200);
  return id;
}

interface BatchRow {
  severity: string;
  meter_read_id: string | null;
  rule_outcomes: { rule: string; severity: string; detail: Record<string, unknown> }[];
}

async function firstRow(request: APIRequestContext, batch: string): Promise<BatchRow> {
  const response = await request.get(api(`/read-batches/${batch}`));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { rows: BatchRow[] }).rows[0];
}

journey("T5-16", "Read on a retired meter — the error stands, the swap flow is the door", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's five hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the row flags ERROR 'read on retired meter' with the retirement date shown", async ({
    page,
  }) => {
    await signIn(page);
    const meter = await retiredMeter(page.request);
    const batch = await stageJulyFile(page.request, meter.asset_no);
    const row = await firstRow(page.request, batch);

    expect(row.severity, "BR-MET-052: a read on a retired meter is an ERROR").toBe("error");
    const outcome = row.rule_outcomes.find((o) => o.rule === "retired_meter");
    expect(outcome, "the retired-meter rule must have been evaluated").toBeDefined();
    expect(outcome?.severity).toBe("error");
    expect(
      String(outcome?.detail.retired_on),
      "the refusal must SHOW the retirement date",
    ).toBe(meter.retire_date);

    // Staged only; the terminal asset row stands untouched.
    expect(row.meter_read_id, "BR-MET-012: nothing commits from staging").toBeNull();
    const asset = await page.request.get(api(`/assets/${meter.id}`));
    expect(((await asset.json()) as AssetRow).retire_date).toBe(meter.retire_date);
  });

  test("step 2 — the batch commit is refused while the error is unresolved", async ({ page }) => {
    await signIn(page);
    const meter = await retiredMeter(page.request);
    const batch = await stageJulyFile(page.request, meter.asset_no);

    const post = await page.request.post(api(`/read-batches/${batch}/post`), {
      data: { certified: true },
    });
    expect(post.status(), "BR-MET-015: errors must be resolved before post").toBe(422);
    expect(((await post.json()) as { br_ref: string }).br_ref).toBe("BR-MET-015");
  });

  test("step 3 — the same ERROR raises on the manual single-entry path", async ({ page }) => {
    await signIn(page);
    const meter = await retiredMeter(page.request);

    // The guard is METER-STATE driven, not import-path driven: a hand-typed row
    // goes through the same parser and the same rules (US-MET-007).
    const staged = await page.request.post(api("/read-batches"), {
      data: {
        source_kind: "manual",
        period_month: "2026-07-01",
        rows: [
          {
            meter_id: meter.asset_no,
            read_date: JULY_READ_DATE,
            reading: JULY_READ_VALUE,
            channel: "total",
          },
        ],
      },
    });
    expect(staged.status()).toBe(201);
    const id = ((await staged.json()) as { id: string }).id;
    expect((await page.request.post(api(`/read-batches/${id}/validate`))).status()).toBe(200);
    const row = await firstRow(page.request, id);
    expect(row.severity, "the manual path must flag the identical ERROR").toBe("error");
    expect(row.rule_outcomes.some((o) => o.rule === "retired_meter" && o.severity === "error")).toBe(
      true,
    );
  });

  test("step 4 — retirement is TERMINAL: no reactivate action exists on the asset", async ({
    page,
  }) => {
    await signIn(page);
    const meter = await retiredMeter(page.request);

    // The served action list is the screen's own affordance set (US-AST-008).
    const response = await page.request.get(api(`/assets/${meter.id}`));
    expect(response.status()).toBe(200);
    const asset = (await response.json()) as AssetRow;
    expect(
      asset.actions ?? [],
      "US-AST-008: a retired asset offers no reactivate/un-retire action",
    ).not.toContain("reactivate");

    // …and no such path answers, either.
    for (const path of [`/assets/${meter.id}/reactivate`, `/assets/${meter.id}/unretire`]) {
      const probe = await page.request.post(api(path), { data: {} });
      expect(
        [404, 405],
        `${path} answered ${probe.status()} — retirement must be terminal`,
      ).toContain(probe.status());
    }

    // The screen a clerk would look on must not offer it either.
    await page.goto(`/${tenant()}/assets/${meter.id}`);
    await expect(
      page.getByRole("button", { name: /re-?activate|un-?retire/i }),
      "S50 must offer no un-retire control",
    ).toHaveCount(0);
  });

  test("step 5 — RECOVERY: rejecting the row with its reason lets the batch commit", async ({
    page,
  }) => {
    await signIn(page);
    const meter = await retiredMeter(page.request);
    const batch = await stageJulyFile(page.request, meter.asset_no);

    // Door (a): the value belongs to the replacement meter → REJECT and re-file.
    const disposition = await page.request.patch(api(`/read-batches/${batch}/rows/1`), {
      data: { disposition: "reject", reason: "wrong_meter" },
    });
    expect(disposition.status(), `the disposition answered ${disposition.status()}`).toBe(200);

    const post = await page.request.post(api(`/read-batches/${batch}/post`), {
      data: { certified: true },
    });
    expect(
      post.status(),
      `the commit after the error resolved answered ${post.status()}: ${await post.text()}`,
    ).toBe(200);

    // The retired meter never receives a committed read.
    // `meter` is NOT one of selectors.READ_FILTERS, so the retired meter is
    // matched on the served rows rather than pushed into the query.
    const reads = await page.request.get(api("/reads?per=200"));
    const onRetired = ((await reads.json()) as { results: { meter: string }[] }).results.filter(
      (r) => r.meter === meter.asset_no,
    );
    expect(onRetired, "the retired meter must never receive a committed read").toHaveLength(0);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-16 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the fixture RETIRES a spare (inventory) meter rather than the
//   journey's MTR-0299 on Unit 4B, so no unit loses its meter mid-suite — the
//   rule under test is meter-state driven and is unaffected · (2) retirement is
//   TERMINAL by the rule this journey asserts, so the fixture is not undone ·
//   (3) step 5 exercises door (a) (reject + re-file); doors (b) date-correction
//   and (c) the US-AST-009 reassign-with-final-read are NOT exercised, and the
//   spec says so rather than implying a fuller recovery than it ran
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
