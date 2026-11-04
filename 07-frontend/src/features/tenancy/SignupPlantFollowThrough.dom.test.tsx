// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-3500 — ONB-04.5 stops following the seeding run after three
//          minutes and then NAVIGATES on that timeout, so steps 14–18 are
//          never seen.
//          DEF-3501 — a finished plant that never REACHED some steps reports
//          `ready`, because `anyStepFellShort` counts `failed` and `skipped`
//          and not `not_started`.
// Screens: ONB-04.5 (S114's post-commit state — CR-017's provisioning screen)
// Rules:   CR-064 (PO 2026-09-02, the eighteen named steps) · BR-SHL-025 (a
//          control a person may not use renders DISABLED WITH ITS REASON) ·
//          BR-SHL-020 · B14 rule 32
// ───────────────────────────────────────────────────────
/**
 * **THE PRODUCT OWNER, 2026-09-03, verbatim:**
 *
 *     "Currently It does not complete all 18 steps on screen - after step 13 it
 *      does background job and then just jump insight the applciation, I want
 *      to complete all 18 steps on this screen itself; and see all jobs are
 *      completed"
 *
 * **ROOT CAUSE, AND THE SCREEN'S OWN COPY IS THE CONFESSION.** `pollJob` was
 * given `maxPolls: 120` at 1500 ms — three minutes, and no more. That number
 * was sized in August against a plant of **ten** blocks measured at 41 s
 * (CR-017 profile, 2026-08-19); the plant walks **eighteen** now and the budget
 * never moved. When it runs out `pollJob` REJECTS, the panel sets `gaveUp`, and
 * `plantPhase` answers `waiting` — whose lead line reads *"The sample records
 * are still being prepared in the background and will appear on their own"*,
 * which is the PO's own sentence back at them. `waiting` was then one of the
 * two phases the automatic hand-over fired on, so four seconds later the
 * operator was in the application with five steps they had never seen.
 *
 * **THE SAME REJECTION HAPPENS ON ONE BAD REQUEST**, because `pollJob` throws
 * on the first poll it cannot complete — so a single 502 from the API
 * pass-through ended the narration at whatever step it had reached and
 * navigated away from it, which is why the step it stops on is arbitrary.
 *
 * **THIS SUITE NEEDS A REAL DOM AND FAKE TIMERS.** `renderToStaticMarkup` runs
 * no effects, so the poll — and therefore every state after the first frame —
 * is unreachable there. The resume waits one interval before asking again, and
 * a test that waited it out in real time would add a second and a half per
 * case for nothing.
 *
 * **RED-FIRST (r11 step 2d, hard-won law 7), six of eight, run against the
 * un-fixed panel at `db29f889` — quoted, not paraphrased:**
 *
 *     × the run outlives one poll window and the screen keeps following it
 *       AssertionError: thirteen steps ticked and five ended un-run because the
 *       screen stopped asking: expected 13 to be 18
 *
 *     × giving up NEVER navigates — the operator leaves by pressing the button
 *       AssertionError: the screen navigated on its own after it stopped
 *       asking: expected "spy" to not be called at all, but actually been
 *       called 1 times
 *
 *     × a finished run NEVER navigates on its own either
 *       AssertionError: expected "spy" to not be called at all, but actually
 *       been called 1 times
 *
 *     × a step the run never reached says WHY on its own line
 *       AssertionError: the unreached step carries no reason: expected null not
 *       to be null
 *
 *     × anyStepFellShort counts a step with no row
 *       AssertionError: expected false to be true
 *
 *     × a succeeded run with steps it never reached is PARTIAL, not READY
 *       AssertionError: the screen called an unfinished run ready and handed the
 *       owner on: expected 'ready' to be 'partial'
 *
 * ⚠ **THE TWO THAT PASSED RED ARE WORTH NAMING, BECAUSE ONE OF THEM ALMOST HID
 * THE DEFECT.** A first draft of the first case asserted that no step was left
 * in a NON-TERMINAL state, and it passed on the broken panel — because a step
 * the screen gave up on reads `notStarted`, which is terminal and is an honest
 * word for *"nobody told us"*. The complaint is not that the rows are
 * un-terminal; it is that five steps which DID run are reported as never having
 * run. So the case counts DONE rows instead, which is the thing the Product
 * Owner was looking at.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@testing-library/jest-dom/vitest";
import "@/i18n";

import i18n from "@/i18n";
import type { ApiClient, JobRecord } from "@/api/client";
import type { ProvisionResult } from "@/api/endpoints";

import {
  PROVISIONING_STEPS,
  ProvisioningPanel,
  anyStepFellShort,
  plantPhase,
  provisioningStepStates,
} from "./SignupWizard";

const JOB_ID = "0191d3c0-0000-7000-8000-0000000000cc";
const TOTAL = PROVISIONING_STEPS.length;

/** The states a step may be left in once the run has stopped. `queued` —
 *  "Waiting" on screen — is the one the PO reported and is deliberately absent:
 *  the run is over, so nothing is waiting for anything. */
const TERMINAL = new Set(["done", "skipped", "failed", "notStarted"]);

function catalogue() {
  return PROVISIONING_STEPS.map((key, index) => ({
    position: index + 1,
    key,
    module: key.split(":")[0],
    block: key.split(":")[1],
    label: key,
    tables: [] as string[],
  }));
}

/** The first `count` blocks recorded as seeded, the rest simply absent — which
 *  is exactly what `step_states()` serves for a run still in flight. */
function seededThrough(count: number) {
  return catalogue()
    .slice(0, count)
    .map((entry) => ({
      ...entry,
      outcome: "seeded",
      count: 1,
      reason_code: null,
      error_code: null,
      failure_class: null,
      root_block: null,
      detail: "1 row",
      finished_at: "2026-09-03T06:00:00+00:00",
    }));
}

/** …and the same list with the unreached blocks served as `not_started`, which
 *  is what the server actually sends: the catalogue LEFT-JOINED onto the
 *  ledger, never the ledger listed. */
function servedThrough(count: number) {
  const done = seededThrough(count);
  const rest = catalogue()
    .slice(count)
    .map((entry) => ({
      ...entry,
      outcome: "not_started",
      count: 0,
      reason_code: null,
      error_code: null,
      failure_class: null,
      root_block: null,
      detail: null,
      finished_at: null,
    }));
  return [...done, ...rest];
}

function record(status: JobRecord["status"], done: number, steps?: unknown[]): JobRecord {
  return {
    id: JOB_ID,
    kind: "tenancy.sample_data_plant",
    status,
    progress: { done, total: TOTAL },
    result_link: null,
    error: null,
    steps: (steps ?? servedThrough(done)) as JobRecord["steps"],
  };
}

const PROVISIONED: ProvisionResult = {
  id: "0191d3c0-0000-7000-8000-0000000000aa",
  name: "Brazos Bend Utilities",
  subdomain: "brazosbend",
  created: true,
  trial_ends_at: "2026-09-17T19:05:00+00:00",
  owner_user_id: "0191d3c0-0000-7000-8000-0000000000bb",
  reference_seed: { version: "2026.08", seeded: { uoms: 6 }, skipped: [] },
  sample_plant: {
    job_id: JOB_ID,
    status_url: `/api/jobs/${JOB_ID}`,
    status: "running",
    steps: catalogue(),
    total: TOTAL,
  },
};

/**
 * THE DEFECT, DRIVEN: the first poll window reports thirteen of eighteen and
 * then REJECTS — which is what a spent budget looks like to the caller, and
 * what a 502 looks like too. A resuming panel asks again and is answered with
 * the finished run; a panel that gives up is left holding thirteen.
 */
function clientThatWindowsOut() {
  let window = 0;
  const calls: number[] = [];
  const client = {
    pollJob: (_jobId: string, options?: { onProgress?: (job: JobRecord) => void }) => {
      window += 1;
      calls.push(window);
      if (window === 1) {
        options?.onProgress?.(record("running", 13));
        return Promise.reject(new Error("poll window expired"));
      }
      const finished = record("succeeded", TOTAL);
      options?.onProgress?.(finished);
      return Promise.resolve(finished);
    },
  } as unknown as ApiClient;
  return { client, calls };
}

/** A run that stops moving: every window answers "still 13" and then rejects,
 *  for ever. The screen must eventually stop asking — and must not navigate. */
function clientThatStalls() {
  let windows = 0;
  const client = {
    pollJob: (_jobId: string, options?: { onProgress?: (job: JobRecord) => void }) => {
      windows += 1;
      options?.onProgress?.(record("running", 13));
      return Promise.reject(new Error("poll window expired"));
    },
  } as unknown as ApiClient;
  return { client, windows: () => windows };
}

function rows() {
  return [...document.querySelectorAll("[data-step]")] as HTMLElement[];
}

function stuck(): string[] {
  return rows()
    .filter((row) => !TERMINAL.has(row.getAttribute("data-state") ?? ""))
    .map((row) => row.getAttribute("data-step") ?? "?");
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
  cleanup();
  vi.restoreAllMocks();
});

describe("DEF-3500 — the seeding screen follows all eighteen steps to the end", () => {
  it("the run outlives one poll window and the screen keeps following it", async () => {
    const { client, calls } = clientThatWindowsOut();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={client}
        onDone={() => undefined}
      />,
    );

    // Thirteen ticked and then the window ended — the PO's screenshot.
    await waitFor(() => expect(rows()).toHaveLength(TOTAL));
    await vi.advanceTimersByTimeAsync(10_000);

    // ⚠ COUNT THE **DONE** ROWS, NOT THE UN-TERMINAL ONES. A step the screen
    // gave up on reads `notStarted`, which IS terminal and is an honest word —
    // so an un-terminal count passes on the broken panel. What the PO was
    // looking at is five steps that ran and are reported as never having run.
    await waitFor(() => {
      const done = rows().filter((r) => r.getAttribute("data-state") === "done");
      expect(
        done.length,
        "steps ticked and the rest ended un-run because the screen stopped asking",
      ).toBe(TOTAL);
    });
    expect(stuck(), `left un-terminal: ${stuck().join(", ")}`).toHaveLength(0);
    expect(calls.length).toBeGreaterThan(1); // it asked again rather than giving up
  });

  it("giving up NEVER navigates — the operator leaves by pressing the button", async () => {
    const onDone = vi.fn();
    const { client } = clientThatStalls();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={client}
        onDone={onDone}
      />,
    );

    await waitFor(() => expect(rows()).toHaveLength(TOTAL));
    // Well past every window, every stall budget and the old four-second
    // hand-over timer put together.
    await vi.advanceTimersByTimeAsync(30 * 60_000);

    expect(onDone, "the screen navigated on its own after it stopped asking").not.toHaveBeenCalled();

    // …and the way off is still there, which is BR-SHL-025's other half: a
    // screen with no exit would be a worse defect than the one being fixed.
    const button = screen.getByTestId("signup-provisioning-continue") as HTMLButtonElement;
    await waitFor(() => expect(button.disabled).toBe(false));
    await userEvent.click(button);
    expect(onDone).toHaveBeenCalledWith("brazosbend");
  });

  it("a finished run NEVER navigates on its own either — all eighteen done, still no jump", async () => {
    const onDone = vi.fn();
    const client = {
      pollJob: (_j: string, o?: { onProgress?: (job: JobRecord) => void }) => {
        const finished = record("succeeded", TOTAL);
        o?.onProgress?.(finished);
        return Promise.resolve(finished);
      },
    } as unknown as ApiClient;
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={client}
        onDone={onDone}
      />,
    );

    await waitFor(() => expect(stuck()).toHaveLength(0));
    await vi.advanceTimersByTimeAsync(60_000);
    // PO: "I want to complete all 18 steps on this screen itself; and see all
    // jobs are completed". Seeing them is the operator's, so is leaving.
    expect(onDone).not.toHaveBeenCalled();
  });

  it("a step the run never reached says WHY on its own line, and never reads Waiting", async () => {
    const { client } = clientThatStalls();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={client}
        onDone={() => undefined}
      />,
    );

    await waitFor(() => expect(rows()).toHaveLength(TOTAL));
    await vi.advanceTimersByTimeAsync(30 * 60_000);

    const unreached = PROVISIONING_STEPS[TOTAL - 1];
    await waitFor(() => {
      const row = document.querySelector(`[data-step="${unreached}"]`);
      expect(row?.getAttribute("data-state")).toBe("notStarted");
    });
    // PO, 2026-09-02: "if you skip the step, then show the reason for that step
    // also". A step nobody reached is the third case that sentence covers, and
    // it carried NO sentence at all.
    const reason = document.querySelector(`[data-step-reason="${unreached}"]`);
    expect(reason, "the unreached step carries no reason").not.toBeNull();
    expect(reason?.textContent).toBe(i18n.t("tenancy.signup.provisioning.steps.notReached"));

    // And no row anywhere still reads "Waiting" once the screen has stopped.
    expect(rows().map((r) => r.getAttribute("data-state"))).not.toContain("queued");
  });
});

describe("DEF-3501 — a run that never reached a step did not succeed", () => {
  it("anyStepFellShort counts a step with no row, not only failed and skipped", () => {
    const short = record("succeeded", 13);
    expect(anyStepFellShort(short)).toBe(true);
    const whole = record("succeeded", TOTAL);
    expect(anyStepFellShort(whole)).toBe(false);
  });

  it("a succeeded run with steps it never reached is PARTIAL, not READY", () => {
    const phase = plantPhase({
      committed: true,
      plant: PROVISIONED.sample_plant,
      job: record("succeeded", 13),
      gaveUp: false,
    });
    expect(phase, "the screen called an unfinished run ready and handed the owner on").toBe(
      "partial",
    );
  });

  it("a server that serves no step rows at all cannot be made to invent a failure", () => {
    // A deployment predating CR-064 sends no `steps` key. Absence is not a
    // verdict, and reading it as one would put every old tenant on `partial`.
    const old = { ...record("succeeded", TOTAL), steps: undefined } as JobRecord;
    expect(anyStepFellShort(old)).toBe(false);
    expect(
      plantPhase({ committed: true, plant: PROVISIONED.sample_plant, job: old, gaveUp: false }),
    ).toBe("ready");
  });

  it("every one of the eighteen is terminal once the run has stopped", () => {
    const states = provisioningStepStates("partial", PROVISIONED.sample_plant, record("succeeded", 13));
    expect(states).toHaveLength(TOTAL);
    expect(states.filter((row) => !TERMINAL.has(row.state))).toHaveLength(0);
    // …and the five it never reached each carry a sentence rather than silence.
    const unreached = states.filter((row) => row.state === "notStarted");
    expect(unreached).toHaveLength(TOTAL - 13);
    expect(unreached.every((row) => row.reasonKey !== null)).toBe(true);
  });
});
