// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-064 task E1 (PO 2026-09-02) — *"Prove it by breaking it — force
//          one block to fail on a real PostgreSQL, and read the reason off the
//          screen"*, and the sentence the whole CR turns on: *"you ahve to
//          provide specific error on the screen itself"*.
// Rules:   B14 rule 32 (no rule id or internal code in clerk-facing copy) ·
//          BR-SHL-020 (the six A18 patterns) · BR-TEN-060
// ───────────────────────────────────────────────────────
// ⚠ **THE FIXTURE IN THIS TEST IS NOT WRITTEN BY HAND. IT IS THE SERVER'S OWN
// BYTES.**
//
// `__fixtures__/cr064-e1-plant-poll.json` was captured from
// `06-backend/tests/test_cr064_e1_live_pg.py` running against a live
// PostgreSQL 16, with `meter_reads` renamed out from under the seeder mid-run
// so block 6 fails the way a real schema problem fails. Only the job id was
// replaced, and it is never rendered.
//
// That matters more than it looks. CR-064's motive is stated in the PO's own
// words — *"this will help us to understand why it is breaking down in real
// time"* — and a screen proved against a sentence WE invented would prove
// nothing about the sentence a database actually produces. This test carries
// one real failure the whole way: PostgreSQL → the seeding job's ledger →
// `job_poll` → the rendered DOM.
//
// It needs a real DOM, not static markup, because the poll happens in an
// effect: `renderToStaticMarkup` runs no effects, so the step outcomes could
// never arrive there at all.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@testing-library/jest-dom/vitest";
import "@/i18n";

import i18n from "@/i18n";
import type { ApiClient, JobRecord } from "@/api/client";
import type { ProvisionResult } from "@/api/endpoints";

import { ProvisioningPanel, stepLabelKey } from "./SignupWizard";
import poll from "./__fixtures__/cr064-e1-plant-poll.json";

/** The sentence PostgreSQL produced, read straight out of the captured body. */
const BROKEN = poll.steps.find((step) => step.outcome === "failed");

const PROVISIONED: ProvisionResult = {
  id: "0191d3c0-0000-7000-8000-0000000000aa",
  name: "Brazos Bend Utilities",
  subdomain: "brazosbend",
  created: true,
  trial_ends_at: "2026-09-16T19:05:00+00:00",
  owner_user_id: "0191d3c0-0000-7000-8000-0000000000bb",
  reference_seed: { version: "2026.08", seeded: { uoms: 6 }, skipped: [] },
  sample_plant: {
    job_id: poll.id,
    status_url: `/api/jobs/${poll.id}`,
    status: "running",
    // ⚠ **THE CATALOGUE COMES OUT OF THE RECORDING, NOT OUT OF THE APP
    // (DEF-3320).** `sample_plant.steps` is what a real commit response carries
    // (CR-064 task A1), and this fixture is a capture of ONE real run — so the
    // catalogue for it is that run's own step list and nothing else. Without
    // these lines `stepCatalogue` falls back to `PROVISIONING_STEPS`, which is
    // TODAY's estate; the estate grew to eighteen on 2026-09-02 and this case
    // began rendering an eighteenth row the recording knows nothing about,
    // correctly reporting it `notStarted`. That is the screen working and the
    // FIXTURE being seventeen months of the world ago — so the fix is to hand
    // the recording its own catalogue rather than to pin a number.
    steps: poll.steps.map(({ position, key, module, block, label, tables }) => ({
      position,
      key,
      module,
      block,
      label,
      tables,
    })),
    total: poll.steps.length,
  },
};

/**
 * A client that is ONLY `pollJob`, which is the only method this panel calls —
 * the same stub `SignupHandover.dom.test.tsx` uses, and for the same reason: a
 * fetch shape between the test and the question would prove the network, not
 * the screen. It answers with the captured body, unmodified.
 */
function clientServing(body: unknown): ApiClient {
  return {
    pollJob: (_jobId: string, options?: { onProgress?: (job: JobRecord) => void }) => {
      options?.onProgress?.(body as JobRecord);
      return Promise.resolve(body as JobRecord);
    },
  } as unknown as ApiClient;
}

afterEach(cleanup);

describe("CR-064 E1 — a real PostgreSQL failure is readable on the step that broke", () => {
  it("step 6 carries the database's own sentence, on its own line", async () => {
    // RED-PROVED (law 7) in a clean worktree with the reason dropped from the
    // row — which is what a "link to Settings instead" version of this screen
    // would render. The failure message IS the complaint the PO made:
    //
    //     AssertionError: expected '6. Meter readings, first monthNot loa…' to
    //     contain 'relation "meter_reads" does not exist'
    expect(BROKEN, "the captured body must contain a failed block").toBeTruthy();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={clientServing(poll)}
        onDone={() => undefined}
      />,
    );

    const key = BROKEN!.key;
    const row = await waitFor(() => {
      const found = document.querySelector(`[data-step="${key}"]`);
      expect(found, `no row for ${key}`).not.toBeNull();
      expect(found?.getAttribute("data-state")).toBe("failed");
      return found as Element;
    });

    // ⚠ THE REQUIREMENT, ASSERTED AS THE PO WORDED IT: the reason is on THAT
    // step's line, not in a summary and not behind a link to Settings.
    expect(row.textContent).toContain('relation "meter_reads" does not exist');
    // And it is the SERVER's sentence, whole — not a paraphrase of it.
    expect(row.textContent).toContain(BROKEN!.detail);

    // The step is named and numbered where a person can find it.
    // ⚠ SEVENTH SINCE 2026-09-02 (`DEF-3340`). The number is read off the
    // RECAPTURED fixture rather than typed, because the fixture is the
    // server's own bytes and the position is one of the facts it carries.
    expect(BROKEN!.position).toBe(7);
    expect(row.textContent).toContain(`${BROKEN!.position}. ${i18n.t(stepLabelKey(key))}`);
    // Its state word is the failed one, and the reason line is scoped to it.
    expect(row.querySelector(`[data-step-reason="${key}"]`)).not.toBeNull();
  });

  it("the other sixteen still report, and the ones after the break still say Done", async () => {
    // BR-TEN-063 rendered: one block broke and the run carried on, so the
    // screen must not look like it stopped at six. This is hard-won law 14's
    // savepoint, visible to a person.
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={clientServing(poll)}
        onDone={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(document.querySelectorAll("[data-step]")).toHaveLength(poll.steps.length);
    });
    const states = [...document.querySelectorAll("[data-step]")].map((el) =>
      el.getAttribute("data-state"),
    );
    expect(states.filter((state) => state === "failed")).toHaveLength(1);
    // Nothing reads "not started" — every step in the recording was reached.
    expect(states).not.toContain("notStarted");
    // The blocks AFTER the failure seeded, which is what a savepoint buys.
    // ⚠ SLICED FROM THE BREAK, NOT FROM A TYPED INDEX (`DEF-3340`): with the
    // break at seventh, `slice(6)` included the failed row, so a check about
    // "everything after the break is Done" asserted the break was Done.
    expect(states.slice(BROKEN!.position).every((state) => state === "done")).toBe(
      true,
    );
  });

  it("B14 rule 32 — the internal error code stays off the screen", () => {
    // The captured body carries `SD-DB-ERROR`. It is real, it is useful in the
    // audit trail and on the Settings panel, and it is not something a utility
    // owner signing up should be asked to read. The SENTENCE is what helps them.
    expect(BROKEN!.error_code).toBeTruthy();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={clientServing(poll)}
        onDone={() => undefined}
      />,
    );
    expect(screen.queryByText(BROKEN!.error_code as string)).toBeNull();
  });
});
