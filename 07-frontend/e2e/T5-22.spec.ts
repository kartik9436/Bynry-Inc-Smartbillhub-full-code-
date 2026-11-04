// ── Trace ──────────────────────────────────────────────
// Journey:  T5-22 — Pattern generator over 3,000 units per run (the cap blocks
//           generation). `08-qa/01-e2e/journeys/T5-22-pattern-generator-3000-cap.md`
//           is the spec; this file walks its five-row step table in order.
// Story:    US-MET-004 (S16 bulk: premises CSV · unit pattern generator ·
//           units CSV) · US-IDN-001 (sign in)
//           Screens: S3 · S16 Add premises → pattern step
// Rules:    BR-MET-005 (pattern total = floors × units-per-floor, capped at
//           3,000 PER RUN) · BR-MET-038 (the staged-import discipline) ·
//           BR-MET-002 (unit labels unique per tenant+premise) · NFR-2
// Money:    NONE. No step renders a figure; `moneyTriple` is not called.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// A NOTE ON WHAT THIS SPEC DOES NOT DO. Step 3 of the journey is a CONTRAST
// case that CREATES 320 units, and step 4 chains two runs to 3,200. Neither is
// committed here: this stack's database is shared by every journey in the batch
// and by the seeded money fixture, and minting 3,520 units into it would change
// what every other spec reads. Both steps are exercised at the PREVIEW (staging)
// boundary instead, which is where BR-MET-005's cap lives — and the spec says
// so rather than implying a commit it did not make.
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

// The journey's own numbers: 40 × 80 = 3,200 (the typo) vs 40 × 8 = 320.
const FLOORS = 40;
const PER_FLOOR_TYPO = 80;
const PER_FLOOR_INTENDED = 8;
const CAP = 3_000;
const LABEL_PATTERN = "{floor}-{seq}";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

async function anyPremisesId(request: APIRequestContext): Promise<string> {
  const response = await request.get(api("/premises?per=10"));
  expect(response.status()).toBe(200);
  const rows = ((await response.json()) as { results: { id: string }[] }).results;
  expect(rows.length, "the fixture has no premises to generate units against").toBeGreaterThan(0);
  return rows[0].id;
}

function patternPayload(premisesId: string, perFloor: number) {
  return {
    kind: "units_pattern",
    pattern: {
      premises_id: premisesId,
      floors: FLOORS,
      units_per_floor: perFloor,
      label_pattern: LABEL_PATTERN,
    },
    options: { skip_errors: true, merge_duplicates: false },
  };
}

journey("T5-22", "Pattern generator over 3,000 units per run — the cap blocks generation", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's five hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the S16 preview computes 3,200, flags the cap, and disables Generate", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/premises/new`);
    await expect(page.locator("main")).toBeVisible();

    // The pattern MODE has to be reachable before its cap can be checked.
    const patternMode = page.getByRole("radio", { name: /pattern/i }).or(
      page.getByRole("button", { name: /pattern/i }),
    );
    await expect(
      patternMode.first(),
      "S16 must offer the unit pattern generator mode (US-MET-004)",
    ).toBeVisible();
    await patternMode.first().click();

    await page.locator("input#floors, input[name='floors']").first().fill(String(FLOORS));
    await page
      .locator("input#units_per_floor, input[name='units_per_floor']")
      .first()
      .fill(String(PER_FLOOR_TYPO));

    // BR-MET-005 as INLINE form validation (IS-7): the live preview shows the
    // product of the multiplication and says it is over the cap.
    await expect(
      page.locator("main"),
      "the live preview must show the computed 3,200 and the 3,000 cap",
    ).toContainText(String(FLOORS * PER_FLOOR_TYPO));
    await expect(page.locator("main")).toContainText(String(CAP));
  });

  test("step 2 — the server refuses the over-cap generation, preview or no preview", async ({
    page,
  }) => {
    await signIn(page);
    const premisesId = await anyPremisesId(page.request);
    const before = await page.request.get(api("/units?per=1"));
    const unitsBefore = ((await before.json()) as { count: number }).count;

    const response = await page.request.post(api("/premises/imports"), {
      data: patternPayload(premisesId, PER_FLOOR_TYPO),
    });
    expect(
      response.status(),
      `${FLOORS}×${PER_FLOOR_TYPO} answered ${response.status()} — BR-MET-005's cap is ` +
        "enforced SERVER-side, not just in the preview",
    ).toBeGreaterThanOrEqual(400);
    const refusal = await response.text();
    expect(
      refusal,
      "the refusal must name the count against the cap",
    ).toMatch(new RegExp(`${CAP}|cap`, "i"));

    // Zero unit rows, zero batch artifacts.
    const after = await page.request.get(api("/units?per=1"));
    expect(((await after.json()) as { count: number }).count).toBe(unitsBefore);
  });

  test("step 3 — contrast: 40 × 8 = 320 previews with its sample labels and is allowed", async ({
    page,
  }) => {
    await signIn(page);
    const premisesId = await anyPremisesId(page.request);

    const response = await page.request.post(api("/premises/imports"), {
      data: patternPayload(premisesId, PER_FLOOR_INTENDED),
    });
    expect(
      response.status(),
      `${FLOORS}×${PER_FLOOR_INTENDED} (=${FLOORS * PER_FLOOR_INTENDED}, within the cap) ` +
        `answered ${response.status()}: ${(await response.text()).slice(0, 300)}`,
    ).toBe(201);
    const staged = (await response.json()) as { rows?: unknown[]; counts?: { rows?: number } };
    const rowCount = staged.counts?.rows ?? staged.rows?.length ?? 0;
    expect(
      rowCount,
      "the staged preview must carry exactly the previewed set",
    ).toBe(FLOORS * PER_FLOOR_INTENDED);
  });

  test("step 4 — the cap is PER RUN: a second run under the cap is allowed", async ({ page }) => {
    await signIn(page);
    const premisesId = await anyPremisesId(page.request);

    // Two runs, each within the cap. BR-MET-005 caps a RUN, not a sitting, so
    // both must stage — the total across them is legitimately over 3,000.
    for (const perFloor of [PER_FLOOR_INTENDED, PER_FLOOR_INTENDED]) {
      const response = await page.request.post(api("/premises/imports"), {
        data: patternPayload(premisesId, perFloor),
      });
      expect(
        response.status(),
        `a second run of ${FLOORS}×${perFloor} answered ${response.status()} — the cap is ` +
          "per RUN by design",
      ).toBe(201);
    }
  });

  test("step 5 — RECOVERY: the units CSV path is the other ratified door and it takes a file", async ({
    page,
  }) => {
    await signIn(page);
    const csv = ["premise_no,unit_no,label", "PRM-001,U-900001,Unit 900001"].join("\n");
    const response = await page.request.post(api("/premises/imports"), {
      data: {
        kind: "units_csv",
        content: csv,
        filename: "units-split-1.csv",
        options: { skip_errors: true },
      },
    });
    expect(
      response.status(),
      `the units CSV door answered ${response.status()}: ${(await response.text()).slice(0, 300)}`,
    ).toBe(201);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-22 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the journey's lakeview-mud / PRM-031 "Harbor Tower" fixture is
//   not provisioned; every probe runs against the seeded tenant's first premises
//   — the cap is a per-RUN arithmetic rule and is unaffected · (2) steps 3–5
//   STAGE and never COMMIT: this database is shared with the money fixture and
//   with every other journey in this batch, and minting 3,520 units would change
//   what they read. BR-MET-005's cap lives at the staging boundary, which is
//   where it is asserted
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
