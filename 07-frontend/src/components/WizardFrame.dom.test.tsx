// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-SHL-010 (EP-SHL-03)   Screens: every guided flow (S10, S18, S23,
//          S28, S31, S38, S110–S114)
// Change:  CR-043 finding 16 — DEF-936. The fix landed HERE and not only in
//          `BillRunWizard`, deliberately: the frame owned the refusal and the
//          step owned the reason, and neither could reach the other. All six
//          wizards inherit what this file asserts.
// Rules:   BR-SHL-018 (an invalid step stays put) · BR-SHL-019 (ONE
//          transactional commit — a step that writes on Continue is not one) ·
//          BR-SHL-025 (a control that cannot act says why) · hard-won law 2
// Tests:   TC-FRAME-1..5
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THIS FILE EXISTS BESIDE `WizardFrame.test.tsx`.** That suite is
// `renderToStaticMarkup` in a `node` environment — the project's posture — and
// it can assert the frame's PURE laws beautifully and can never press a button.
// Every law below is about what happens on a press, so it needs a DOM. The two
// layers stay visibly distinct through the `.dom.test.tsx` name, exactly as
// vite.config.ts asks.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";

import { WizardFrame } from "./WizardFrame";
import type { WizardStep, WizardStepVerdict } from "./WizardFrame";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

function steps(
  validate: () => WizardStepVerdict | Promise<WizardStepVerdict>,
): WizardStep[] {
  return [
    { id: "one", label: "Step one", content: <p>The first step</p>, validate },
    { id: "two", label: "Step two", content: <p>The second step</p> },
  ];
}

function mount(validate: () => WizardStepVerdict | Promise<WizardStepVerdict>) {
  render(
    <WizardFrame
      steps={steps(validate)}
      commitLabel="Commit ✓"
      commitFailedTitle="It failed."
      onCommit={async () => ({ ok: true })}
      onCommitted={() => undefined}
    />,
  );
}

function pressContinue(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  return user.click(screen.getByRole("button", { name: t("wizard.continue") }));
}

describe("WizardFrame · what a refused Continue says (DEF-936)", () => {
  it("TC-FRAME-1 · `false` still means the generic sentence — the field case, unchanged", async () => {
    const user = userEvent.setup();
    mount(() => false);
    await pressContinue(user);
    // Right, and it must stay right: when the unmet condition IS a marked
    // field, "fill in what's marked above" points at the mark.
    expect(screen.getByText(t("wizard.blocked"))).toBeVisible();
  });

  it("TC-FRAME-2 · a STRING is what the frame says instead, and the generic never appears", async () => {
    const user = userEvent.setup();
    mount(() => "Press Start before you can continue.");
    await pressContinue(user);
    expect(screen.getByText("Press Start before you can continue.")).toBeVisible();
    // ⛔ THE DEFECT ITSELF: a clerk sent hunting for a field that is already
    // correct. The generic line must not ALSO render.
    expect(screen.queryByText(t("wizard.blocked"))).not.toBeInTheDocument();
  });

  it("TC-FRAME-3 · a refusal blocks the step — BR-SHL-018 is not traded for a sentence", async () => {
    const user = userEvent.setup();
    mount(() => "Not yet.");
    await pressContinue(user);
    expect(screen.getByText("The first step")).toBeVisible();
    expect(screen.queryByText("The second step")).not.toBeInTheDocument();
  });

  it("TC-FRAME-4 · a step may do the work its Continue implies, and advances when it is done", async () => {
    const user = userEvent.setup();
    let resolve: (verdict: WizardStepVerdict) => void = () => undefined;
    mount(() => new Promise<WizardStepVerdict>((r) => (resolve = r)));
    await pressContinue(user);
    // A18 §3 while it is out — the same working state the commit has always had.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: t("states.working") })).toBeDisabled();
    });
    resolve(true);
    await waitFor(() => {
      expect(screen.getByText("The second step")).toBeVisible();
    });
  });

  it("TC-FRAME-5 · single-flight: Continue cannot be pressed again while its work is out", async () => {
    const user = userEvent.setup();
    // ⚠ `DEF-SHL-5119` — THE WORK IS RELEASED BY THE TEST, NEVER BY A CLOCK.
    // This read `setTimeout(() => r(true), 50)`: the assertions below had 50 ms
    // to find the Working button, and on a machine running other suites the
    // window closed first, so a TRUE guard went red as "flaky" (measured: at
    // 0 ms it fails *Unable to find role="button" and name "Working…"*). The
    // promise is now held open until the disabled button has been asserted and
    // clicked, exactly as TC-FRAME-4 holds its own.
    let release: (verdict: WizardStepVerdict) => void = () => undefined;
    const validate = vi.fn(() => new Promise<WizardStepVerdict>((r) => (release = r)));
    mount(validate);
    await pressContinue(user);
    // A second press would be a second `POST /billing/runs` for one intent.
    // The enforcement a test can SEE is the disabled attribute, so that is what
    // is asserted — dropping `working={continuing}` from the frame turns this
    // red. Clicking it anyway proves the event does not reach the handler.
    const working = await screen.findByRole("button", { name: t("states.working") });
    expect(working).toBeDisabled();
    fireEvent.click(working);
    release(true);
    await waitFor(() => {
      expect(screen.getByText("The second step")).toBeVisible();
    });
    expect(validate).toHaveBeenCalledTimes(1);
  });

  // ⚠ **ONE GUARD IN `handleContinue` IS DELIBERATELY NOT COVERED HERE, AND
  // SAYING SO IS THE POINT (DEF-182's lesson: a check that cannot distinguish
  // pass from fail is worse than none).** The frame also early-returns on
  // `continuing` at the top of `handleContinue`. While the button carries
  // `disabled`, React never delivers a click to that handler, so no DOM event
  // this suite can dispatch will exercise it — a test written for it would pass
  // whether or not the guard existed, which is exactly what happened when this
  // case was first written the other way round. The guard stays, as the belt to
  // the disabled brace for any future caller that invokes Continue other than
  // by clicking it; it is named as uncovered rather than claimed as covered.
});

// ── DEF-1083 ────────────────────────────────────────────────────────────────
describe("WizardFrame · the footer row holds BUTTONS (DEF-1083)", () => {
  // ⚠ **WHAT THIS CAN AND CANNOT CLAIM.** It cannot see the deformed row: jsdom
  // computes no layout, the markup is identical whether the sentence renders on
  // one line or three, and no gate in this repo reads rendered output (hard-won
  // law 6). The PO found it by looking at step 2 of the bill run.
  //
  // What it CAN hold is the decision — **prose is not a button, so it is not a
  // flex item in the button row** — which is the same call `PageHeader` now
  // makes one frame over (DEF-966). Both defects were a correct thing with
  // nowhere to put it; both are answered by giving it a declared home.
  const REASON = "A billing run cannot be parked yet: nothing would list it.";

  function mountWithBlockedPark(parkedAt: string | null = null) {
    render(
      <WizardFrame
        steps={steps(() => true)}
        commitLabel="Commit ✓"
        commitFailedTitle="It failed."
        onCommit={async () => ({ ok: true })}
        onCommitted={() => undefined}
        exit={{
          onSaveAndExit: () => undefined,
          parkBlockedReason: REASON,
          parkOpen: false,
          onParkOpenChange: () => undefined,
          onPark: async () => ({ ok: false, reason: REASON }),
          dateFormat: "MM/DD/YYYY",
          parkedAt,
        }}
      />,
    );
  }

  function actionsRow(): HTMLElement {
    const row = document.querySelector<HTMLElement>('[data-wizard="actions"]');
    if (row === null) {
      throw new Error("the wizard footer's action row is not in the DOM");
    }
    return row;
  }

  it("keeps the disabled Park's REASON out of the button row", () => {
    mountWithBlockedPark();
    expect(actionsRow().textContent ?? "").not.toContain(REASON);
  });

  it("renders the reason on the frame's declared note line, beneath the row", () => {
    mountWithBlockedPark();
    const note = document.querySelector<HTMLElement>('[data-wizard="exit-note"]');
    expect(note, "the declared exit-note line is not rendered").not.toBeNull();
    expect(note?.textContent ?? "").toContain(REASON);
    // BENEATH: the note follows the row in document order.
    expect(
      actionsRow().compareDocumentPosition(note as Node) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("ties the note to the control it explains, so the split costs no screen reader (BR-SHL-025)", () => {
    mountWithBlockedPark();
    const park = screen.getByRole("button", { name: t("wizard.exit.park") });
    const note = document.querySelector('[data-wizard="exit-note"]');
    expect(park).toBeDisabled();
    expect(park.getAttribute("aria-describedby")).toBe(note?.getAttribute("id"));
  });

  it("keeps the park AGE out of the button row too — it is prose as well", () => {
    mountWithBlockedPark("2026-08-20T00:00:00Z");
    expect(actionsRow().querySelector('[data-wizard="park-age"]')).toBeNull();
    expect(
      document.querySelector('[data-wizard="exit-note"] [data-wizard="park-age"]'),
    ).not.toBeNull();
  });

  it("renders NO note line at all when park is allowed and nothing is parked", () => {
    render(
      <WizardFrame
        steps={steps(() => true)}
        commitLabel="Commit ✓"
        commitFailedTitle="It failed."
        onCommit={async () => ({ ok: true })}
        onCommitted={() => undefined}
        exit={{
          onSaveAndExit: () => undefined,
          parkBlockedReason: null,
          parkOpen: false,
          onParkOpenChange: () => undefined,
          onPark: async () => ({ ok: true }),
          dateFormat: "MM/DD/YYYY",
          parkedAt: null,
        }}
      />,
    );
    expect(document.querySelector('[data-wizard="exit-note"]')).toBeNull();
  });
});

// ── 2026-09-19 · `Cancel` IS THE FRAME'S, AND IT IS IN THE FOOTER ──────────
//
// PO, on the Add units screen: ***"cancel button should be bottom not on
// top"***, then, on the shape put back to them — *"Footer: the wizard actions,
// with `Cancel`, and `← Back` meaning previous step only"* — ***"this is
// correct"***.
//
// ⚠ **THE SECOND CASE IS THE ONE THAT MATTERS TO THE OTHER 23 WIZARDS.** This
// prop is a KIT change, and a kit change is never local (B14 rule 38's own
// words). The branch in the frame is written so a wizard that passes no
// `cancel` renders what it always rendered; the test that says so is what
// stops a later "simplification" from putting a button on eighteen screens
// nobody asked.
describe("PO 2026-09-19 — the footer's Cancel", () => {
  function frame(cancel?: { label: string; onCancel: () => void }) {
    render(
      <WizardFrame
        steps={steps(() => true)}
        commitLabel="Commit ✓"
        commitFailedTitle="It failed."
        onCommit={async () => ({ ok: true })}
        onCommitted={() => undefined}
        {...(cancel === undefined ? {} : { cancel })}
      />,
    );
  }

  it("renders INSIDE the wizard-actions row, not anywhere a screen chose", () => {
    frame({ label: "Cancel", onCancel: () => undefined });
    const actions = document.querySelector('[data-wizard="actions"]');
    const button = screen.getByRole("button", { name: "Cancel" });
    // ⚠ *"a Cancel button exists"* passes while it is still in the page head —
    // which is exactly the state the PO reported. Containment is the assertion.
    expect(actions).not.toBeNull();
    expect(actions?.contains(button)).toBe(true);
  });

  it("sits at the LEFT of the row, ahead of the step-back and the commit", () => {
    frame({ label: "Cancel", onCancel: () => undefined });
    const buttons = [...document.querySelectorAll('[data-wizard="actions"] button')];
    expect(buttons[0]).toBe(screen.getByRole("button", { name: "Cancel" }));
  });

  it("is ABSENT, with no wrapper at all, when a wizard does not ask for one", () => {
    frame();
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
    expect(document.querySelector("[data-wizard-cancel]")).toBeNull();
    // The left-hand cluster is not emitted either — the 23 wizards that pass
    // neither `cancel` nor `exit` keep the markup they have always had.
    expect(document.querySelector('[data-wizard="left"]')).toBeNull();
  });

  it("does not share a label with the step-back (B14 rule 1)", () => {
    // `wizard.back` means *previous step*; a Cancel wearing the same word is
    // the collision rule 1 exists to prevent. The frame cannot enforce what a
    // consumer passes, so this pins the frame's own half: its step-back word
    // is `wizard.back`, and a consumer passing that as its Cancel label would
    // be visible here as two identical buttons.
    frame({ label: "Cancel", onCancel: () => undefined });
    expect(t("wizard.back")).not.toBe("Cancel");
  });

  it("is refused while the ONE transactional commit is in flight (BR-SHL-019)", async () => {
    const user = userEvent.setup();
    let release = (): void => undefined;
    render(
      <WizardFrame
        steps={[{ id: "only", label: "Only", content: <p>One step</p> }]}
        commitLabel="Commit ✓"
        commitFailedTitle="It failed."
        cancel={{ label: "Cancel", onCancel: () => undefined }}
        onCommit={() => new Promise((resolve) => { release = () => resolve({ ok: true }); })}
        onCommitted={() => undefined}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Commit ✓" }));
    // ⚠ A clerk must not be able to navigate out from under a write that has
    // already begun — the same guard `Save & exit` and `Park` already carry.
    await waitFor(() => expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled());
    release();
  });
});
