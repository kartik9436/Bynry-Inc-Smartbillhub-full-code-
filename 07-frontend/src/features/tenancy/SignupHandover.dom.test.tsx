// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2370 — ONB-04.5's *Go to your utility* rendered under
//          `subdomain !== null` with no `disabled` prop and no reference to
//          `phase`, so it was live and inviting while the list underneath read
//          "Sample data so you can see it working — WORKING — Block 2 of 14".
//          PO, 2026-08-28, on a fresh database: *"dont enable go to utility
//          until all jobs are completed"*.
// Screens: ONB-04.5 (S114's post-commit state — CR-017's provisioning screen)
// Rules:   BR-SHL-025 (a control a person may not use renders DISABLED WITH ITS
//          REASON, never hidden) · B14 rule 32 (the reason a control is
//          disabled gets a declared line of its own, not a word crammed into
//          the control row) · BR-TEN-010 · BR-TEN-012
// ───────────────────────────────────────────────────────
/**
 * **THIS IS A RENDERED-OUTPUT TEST, WHICH IS THE ONLY KIND THAT COULD HAVE
 * CAUGHT IT (hard-won law 6: no gate in this repo looks at rendered output, and
 * nine defects were found by diffing the running app and by nothing else).**
 *
 * The existing suite asserted the button was PRESENT
 * (`toContain("signup-provisioning-continue")`) under a comment calling it *"a
 * way out that does not depend on the background work finishing"* — which is
 * the defect stated as an intention. Presence was never the question. Whether
 * the control can be PRESSED in a phase that cannot serve it is.
 *
 * `ProvisioningPanel` reaches `partial` and `ready` only through its polling
 * effect, so `renderToStaticMarkup` cannot see either — it renders one frame
 * and runs no effects. Hence a real DOM and a stub `pollJob`: the three phases
 * below are driven the way the deployed screen reaches them.
 *
 * **RED-FIRST (r11 2d), verbatim, run in a clean worktree at 9b023fd — the tree
 * WITHOUT the fix:**
 *
 *     × DEF-2370: while the sample-data job is still running the hand-over is refused
 *       → expected false to be true
 *     AssertionError: expected false to be true
 *      ❯ src/features/tenancy/SignupHandover.dom.test.tsx
 *         expect(button.disabled).toBe(true);
 *
 *     × DEF-2370: a disabled hand-over cannot be clicked, so nothing navigates
 *       → expected "spy" to not be called at all, but it was called once
 *
 * ⚠ **AND THE `ready` AND `partial` CASES PASSED THERE**, which is the point of
 * running them: the fix must not buy the guard by breaking the two states that
 * were always correct. `partial` in particular MUST stay usable — the panel's
 * own comment says *"something did not land and the user has to see which block
 * before they leave, so that one is theirs to dismiss"* — and it is the state
 * with no auto-handover at all, so disabling it would strand the user on a
 * screen with no way off it.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@testing-library/jest-dom/vitest";
import "@/i18n";

import i18n from "@/i18n";
import type { ApiClient, JobRecord } from "@/api/client";
import type { ProvisionResult } from "@/api/endpoints";

import { ProvisioningPanel } from "./SignupWizard";

const JOB_ID = "0191d3c0-0000-7000-8000-0000000000cc";

const PROVISIONED: ProvisionResult = {
  id: "0191d3c0-0000-7000-8000-0000000000aa",
  name: "Brazos Bend Utilities",
  subdomain: "brazosbend",
  created: true,
  trial_ends_at: "2026-08-22T19:05:00+00:00",
  owner_user_id: "0191d3c0-0000-7000-8000-0000000000bb",
  reference_seed: { version: "2026.08", seeded: { uoms: 6 }, skipped: [] },
  sample_plant: {
    job_id: JOB_ID,
    status_url: `/api/jobs/${JOB_ID}`,
    status: "running",
    total: 14,
  },
};

function record(status: JobRecord["status"], done: number): JobRecord {
  return {
    id: JOB_ID,
    kind: "tenancy.sample_data_plant",
    status,
    progress: { done, total: 14 },
    result_link: null,
    error: null,
  };
}

/**
 * A client that is ONLY `pollJob`, which is the only method this panel calls.
 * The real `createApiClient` would need a fetch stub per phase and would put a
 * network shape between the test and the question it is asking.
 */
function clientPolling(behaviour: (onProgress: (job: JobRecord) => void) => Promise<JobRecord>) {
  return {
    pollJob: (_jobId: string, options?: { onProgress?: (job: JobRecord) => void }) =>
      behaviour(options?.onProgress ?? (() => undefined)),
  } as unknown as ApiClient;
}

/** Still working: the record says `running`, and the promise never settles —
 *  exactly the state the PO screenshotted at "Block 2 of 14". */
const STILL_SEEDING = clientPolling((onProgress) => {
  onProgress(record("running", 2));
  return new Promise<JobRecord>(() => undefined);
});

/** The plant finished. */
const SUCCEEDED = clientPolling(() => Promise.resolve(record("succeeded", 14)));

/** The plant ended badly — `partial`, the state that is the user's to dismiss. */
const FAILED = clientPolling(() => Promise.resolve(record("failed", 6)));

function continueButton(): HTMLButtonElement {
  return screen.getByTestId("signup-provisioning-continue") as HTMLButtonElement;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DEF-2370 — ONB-04.5 does not offer the hand-over until the work is finished", () => {
  it("while the sample-data job is still running the hand-over is refused", async () => {
    const onDone = vi.fn();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={STILL_SEEDING}
        onDone={onDone}
      />,
    );

    // The screen is saying, in words, that block 2 of 14 is being written — the
    // PO's screenshot. Assert the thing that was actually wrong, on the frame
    // it was wrong on (r11 2d).
    await screen.findByText(
      i18n.t("tenancy.signup.provisioning.step.sampleProgress", { done: 2, total: 14 }),
    );

    const button = continueButton();
    expect(button).toBeInTheDocument(); // BR-SHL-025: refused, never hidden
    expect(button.disabled).toBe(true);
  });

  it("a disabled hand-over cannot be clicked, so nothing navigates", async () => {
    const onDone = vi.fn();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={STILL_SEEDING}
        onDone={onDone}
      />,
    );
    await screen.findByText(
      i18n.t("tenancy.signup.provisioning.step.sampleProgress", { done: 2, total: 14 }),
    );

    await userEvent.click(continueButton()).catch(() => undefined);
    expect(onDone).not.toHaveBeenCalled();
  });

  it("BR-SHL-025: the refused hand-over says WHY, in a line of its own that a screen reader reaches", async () => {
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={STILL_SEEDING}
        onDone={() => undefined}
      />,
    );
    await screen.findByText(
      i18n.t("tenancy.signup.provisioning.step.sampleProgress", { done: 2, total: 14 }),
    );

    // B14 rule 32: the reason is a DECLARED LINE, not a word in the control row
    // — so the button points at the reassurance the screen already renders for
    // this exact wait rather than minting a second sentence that could drift
    // from it.
    const described = continueButton().getAttribute("aria-describedby");
    expect(described).not.toBeNull();
    const reason = document.getElementById(described as string);
    expect(reason).not.toBeNull();
    expect(reason?.textContent).toBe(i18n.t("tenancy.signup.provisioning.reassure"));
  });

  it("the plant finished: the hand-over is usable and takes the owner to their utility", async () => {
    const onDone = vi.fn();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={SUCCEEDED}
        onDone={onDone}
      />,
    );

    await waitFor(() => expect(continueButton().disabled).toBe(false));
    // Nothing explains a control a person CAN use.
    expect(continueButton().getAttribute("aria-describedby")).toBeNull();

    await userEvent.click(continueButton());
    expect(onDone).toHaveBeenCalledWith("brazosbend");
  });

  it("PARTIAL STAYS USABLE — it is the one phase that never hands over on its own", async () => {
    // The panel's own comment: "`partial` does NOT [hand over on its own]:
    // something did not land and the user has to see which block before they
    // leave, so that one is theirs to dismiss." Disabling it would leave the
    // owner on a screen with no exit at all.
    const onDone = vi.fn();
    render(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={FAILED}
        onDone={onDone}
      />,
    );

    await screen.findByText(i18n.t("tenancy.signup.provisioning.partial.lead"));
    await waitFor(() => expect(continueButton().disabled).toBe(false));

    await userEvent.click(continueButton());
    expect(onDone).toHaveBeenCalledWith("brazosbend");
  });
});
