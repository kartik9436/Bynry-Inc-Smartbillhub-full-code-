// ── Trace ──────────────────────────────────────────────
// Journey:  T5-21 — Bulk import over 10,000 rows (the file cap rejects at
//           staging). `08-qa/01-e2e/journeys/T5-21-import-10k-cap.md` is the
//           spec; this file walks its five-row step table in order.
// Story:    US-AST-010 (assets bulk import) · US-CUS-019 (S68 accounts
//           onboarding upload) · US-MET-004 (S16 units CSV) · US-IDN-001
//           Screens: S3 · S49 assets import · S68 account import · S16
// Rules:    BR-AST-034 (assets: 10,000-row-per-file cap, rejected AT UPLOAD) ·
//           BR-CUS-051 (accounts) · BR-MET-038 (units) · NFR-2 (the shared
//           platform import discipline)
// Money:    NONE. No step of this journey renders a figure; `moneyTriple` is
//           not called rather than borrowed from another journey.
// Tests:    this file. The oversized files are BUILT IN MEMORY here (12,481
//           and 10,001 rows, exactly the journey's counts) — a fixture file of
//           that size committed to the repo would be the second copy of a
//           generated artifact CLAUDE.md law 5 forbids.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

// The journey's own counts.
const OVERSIZE_ROWS = 12_481;
const CAP = 10_000;
const JUST_OVER = CAP + 1;

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

/** An assets CSV of `rows` data lines. Header shape per US-AST-010's template. */
function assetsCsv(rows: number): string {
  const lines = ["asset_no,type,serial_no,meter_type,unit_of_measure,multiplier"];
  for (let i = 1; i <= rows; i++) {
    lines.push(`CUT-${String(i).padStart(6, "0")},meter,SN-${i},ami,kWh,1`);
  }
  return lines.join("\n");
}

function accountsCsv(rows: number): string {
  const lines = ["account_no,full_name,unit_no,status"];
  for (let i = 1; i <= rows; i++) {
    lines.push(`ACC-${String(i).padStart(6, "0")},Cutover ${i},U-${i},pending_activation`);
  }
  return lines.join("\n");
}

function unitsCsv(rows: number): string {
  const lines = ["premise_no,unit_no,label"];
  for (let i = 1; i <= rows; i++) {
    lines.push(`PRM-001,U-${String(i).padStart(6, "0")},Unit ${i}`);
  }
  return lines.join("\n");
}

journey("T5-21", "Bulk import over 10,000 rows — the file cap rejects at staging", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's five hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — a 12,481-row assets file is refused at upload, with the count and the cap", async ({
    page,
  }) => {
    await signIn(page);
    const before = await page.request.get(api("/assets?page_size=1"));
    const assetsBefore = ((await before.json()) as { count: number }).count;

    const response = await page.request.post(api("/assets/imports"), {
      data: { content: assetsCsv(OVERSIZE_ROWS), filename: "assets-cutover.csv" },
    });
    expect(
      response.status(),
      `a ${OVERSIZE_ROWS}-row file answered ${response.status()} — BR-AST-034 rejects it ` +
        "at file acceptance, before staging a single row",
    ).toBeGreaterThanOrEqual(400);
    const refusal = (await response.json()) as {
      br_ref: string | null;
      message_key: string;
      params: Record<string, unknown>;
    };
    expect(refusal.br_ref, "the refusal must cite the cap rule").toBe("BR-AST-034");
    expect(
      String(refusal.params.max_rows),
      "the refusal must SHOW the cap so the user knows how to split",
    ).toBe(String(CAP));

    // ZERO rows staged, and no partial acceptance of the first 10,000.
    const after = await page.request.get(api("/assets?page_size=1"));
    expect(((await after.json()) as { count: number }).count).toBe(assetsBefore);
  });

  test("step 2 — the same cap refuses a 10,001-row file on the accounts and units surfaces", async ({
    page,
  }) => {
    await signIn(page);

    const accounts = await page.request.post(api("/accounts/imports"), {
      data: { content: accountsCsv(JUST_OVER), filename: "accounts-cutover.csv" },
    });
    expect(
      accounts.status(),
      `the accounts import took a ${JUST_OVER}-row file (${accounts.status()}) — ` +
        "BR-CUS-051 makes the cap the shared import standard",
    ).toBeGreaterThanOrEqual(400);

    const units = await page.request.post(api("/premises/imports"), {
      data: {
        kind: "units_csv",
        content: unitsCsv(JUST_OVER),
        filename: "units-cutover.csv",
        options: { skip_errors: true },
      },
    });
    expect(
      units.status(),
      `the units import took a ${JUST_OVER}-row file (${units.status()}) — ` +
        "BR-MET-038 makes the cap the shared import standard",
    ).toBeGreaterThanOrEqual(400);
  });

  test("step 3 — the count check happens before any validation work begins", async ({ page }) => {
    await signIn(page);
    // A file that is BOTH oversized and full of invalid rows must be refused
    // for its SIZE — a per-row error report would mean the server did the work
    // the cap exists to prevent.
    const rubbish = ["asset_no,type"]
      .concat(Array.from({ length: OVERSIZE_ROWS }, () => ",not_a_type"))
      .join("\n");
    const response = await page.request.post(api("/assets/imports"), {
      data: { content: rubbish, filename: "assets-cutover.csv" },
    });
    const body = await response.text();
    expect(response.status()).toBeGreaterThanOrEqual(400);
    expect(
      body,
      "the refusal must be the ROW CAP, not a per-row validation report",
    ).toMatch(/row_cap|max_rows/i);
  });

  test("step 4 — contrast: two split files are both accepted into staging", async ({ page }) => {
    await signIn(page);
    for (const [name, rows] of [
      ["assets-cutover-1.csv", CAP],
      ["assets-cutover-2.csv", OVERSIZE_ROWS - CAP],
    ] as const) {
      const response = await page.request.post(api("/assets/imports"), {
        data: { content: assetsCsv(rows), filename: name },
      });
      expect(
        response.status(),
        `${name} (${rows} rows, within the cap) answered ${response.status()}: ` +
          `${(await response.text()).slice(0, 300)}`,
      ).toBe(201);
      const batch = (await response.json()) as { id: string; row_count?: number };
      expect(batch.id, "a staged batch must be identified").toBeTruthy();
    }
  });

  test("step 5 — RECOVERY: the split upload is the ratified door and it is reachable", async ({
    page,
  }) => {
    await signIn(page);
    // The clerk's half of the recovery: the assets import surface must exist
    // on a screen, or "split the file and re-upload" is advice about a door
    // nobody can open.
    await page.goto(`/${tenant()}/assets`);
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /import/i }).or(page.getByRole("link", { name: /import/i })).first(),
      "S49 must offer the bulk import US-AST-010 describes",
    ).toBeVisible();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-21 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the journey's large-tenant fixture `lakeview-mud` is not
//   provisioned on this stack, so every probe runs against the seeded
//   brazosbend tenant — the cap is a per-FILE rule and is unaffected by tenant
//   size · (2) step 4's split files are STAGED, not committed: committing
//   12,481 invented assets into a shared fixture database would corrupt every
//   other journey in this batch, and the journey's own step-4 claim under test
//   is "both accepted into staging"
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
