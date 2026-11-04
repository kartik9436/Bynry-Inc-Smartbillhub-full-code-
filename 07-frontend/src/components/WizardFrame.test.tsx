// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-010 (EP-SHL-03 §Stories)  Screens: S18 (representative guided flow; all wizards)
// Rules:    BR-SHL-018 (rail semantics) · BR-SHL-019 (commit semantics)
// ───────────────────────────────────────────────────────
// TC tests for FE-06 WizardFrame. Prior-run conventions: markup asserts on
// react-dom/server static output; the navigation and commit laws run through
// the exported pure pieces (nav transitions + the framework-free commit
// controller — Toast-queue style, driven directly and also injected as the
// component's test seam). Browser-only behavior is an honest it.todo.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import i18n from "@/i18n"; // the i18next singleton with the five catalogs

import {
  WIZARD_PARK_REASONS,
  WIZARD_PARK_REASON_COPY,
  WizardFrame,
  backOne,
  clampStepToReached,
  continueFrom,
  createWizardCommitController,
  initialWizardNav,
  jumpBackTo,
} from "./WizardFrame";
import { isWizardParkReason, parkAgeDays } from "./WizardFrame";
import { buttonClasses } from "./buttonKit";
import type { WizardCommitController, WizardExit, WizardNavState, WizardStep } from "./WizardFrame";
import type { CommitTier } from "./StateFrame";

const noop = () => undefined;

// §4 test data — S18 New Account: Maria Delgado, maria.delgado@gmail.com,
// +1 (208) 555-0177; step 3 shows premises "Cedar Ridge Apartments" / Unit 3B
// (plan displayed, not re-selected). Content derives from CONSUMER state —
// that is what makes values persist across rail jumps (BR-SHL-018).
function s18Steps(values: { name: string }): WizardStep[] {
  return [
    { id: "customer", label: "Customer", content: <div>Customer: {values.name}</div> },
    {
      id: "contact",
      label: "Contact",
      content: <div>maria.delgado@gmail.com · +1 (208) 555-0177</div>,
    },
    {
      id: "premises",
      label: "Premises & unit",
      content: <div>Cedar Ridge Apartments · Unit 3B</div>,
    },
    { id: "review", label: "Review", content: <div>Review &amp; confirm</div> },
  ];
}

const okCommit = async () => ({ ok: true as const });

function renderFrame(
  nav: WizardNavState,
  controller?: WizardCommitController,
  commitVariant?: CommitTier,
): string {
  return renderToStaticMarkup(
    <WizardFrame
      steps={s18Steps({ name: "Maria Delgado" })}
      nav={nav}
      onNavChange={noop}
      commitLabel="Create account ✓"
      commitVariant={commitVariant}
      commitFailedTitle="Account not created."
      onCommit={okCommit}
      onCommitted={noop}
      controller={controller}
    />,
  );
}

/**
 * THE OPENING TAG OF THE `<button>` WHOSE LABEL CONTAINS `label` — the frame
 * renders five of them (four rail steps + the footer), so a bare `toContain`
 * on a tier would answer about whichever button happened to carry it.
 *
 * ⚠ **IT READS RENDERED OUTPUT, WHICH IS THE WHOLE POINT (DEF-712).** That
 * defect's escape reason is that no gate in this repo reads rendered output —
 * so a rule that CANNOT be obeyed looks identical to one nobody has got to. A
 * case asserting that a prop travelled would have passed on the broken day.
 */
function buttonTagLabelled(html: string, label: string): string {
  for (const match of html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)) {
    if (match[1].includes(label)) {
      return match[0].slice(0, match[0].indexOf(">") + 1);
    }
  }
  throw new Error(`no <button> labelled ${label} in the rendered output`);
}

describe("US-SHL-010 — wizard framework: step rail, Back/Continue, confirm & toast", () => {
  it("US-SHL-010 TC-1: after steps 1–2, clicking step 1 jumps back with values intact; Continue returns to step 2", () => {
    let nav = initialWizardNav();
    nav = continueFrom(nav, 4, true); // step 1 validates → 2
    nav = continueFrom(nav, 4, true); // step 2 validates → 3
    expect(nav).toEqual({ step: 3, reached: 3 });
    nav = jumpBackTo(nav, 1); // rail click on completed step 1
    expect(nav).toEqual({ step: 1, reached: 3 }); // reached is NOT forgotten
    // Step-1 values still populated — content re-renders from consumer state.
    const html = renderFrame(nav);
    expect(html).toContain("Customer: Maria Delgado");
    // Completed rail steps render as done/back-clickable; the rest do not.
    expect(html).toContain('data-state="active"');
    // Continue returns forward to step 2, its values equally consumer-held.
    nav = continueFrom(nav, 4, true);
    expect(nav).toEqual({ step: 2, reached: 3 });
  });

  it("US-SHL-010 TC-2 (negative): clicking a not-yet-reached step is a no-op — forward only via validated Continue", () => {
    const nav = initialWizardNav();
    // The transition returns the SAME object — nothing navigates.
    expect(jumpBackTo(nav, 3)).toBe(nav);
    // And the rail renders unreached steps as non-navigating (disabled).
    const html = renderFrame(nav);
    // Route B (2026-08-21): the state moved from a class to `data-state`, and
    // "not back-jumpable" is exactly `active` + `upcoming` — `disabled={!done}`.
    const disabledSteps = html.match(/data-state="(?:active|upcoming)"/g) ?? [];
    expect(disabledSteps.length).toBe(4); // on step 1 nothing is back-jumpable
    const midHtml = renderFrame({ step: 3, reached: 3 });
    const enabledDone = midHtml.match(/data-state="done"/g) ?? [];
    expect(enabledDone.length).toBe(2); // steps 1–2 completed → clickable
    expect(midHtml).toContain('aria-current="step"');
  });

  it("US-SHL-010 TC-3: Continue with an invalid step stays put — rail state unchanged (inline errors are US-SHL-009's)", () => {
    const nav: WizardNavState = { step: 2, reached: 2 };
    expect(continueFrom(nav, 4, false)).toBe(nav); // same object = no movement
    expect(backOne(nav)).toEqual({ step: 1, reached: 2 }); // Back needs no validation
  });

  it("US-SHL-010 TC-4: the final step renders the ✓ confirm; in flight it disables + shows 'Working…'; success reports ok", async () => {
    const finalNav: WizardNavState = { step: 4, reached: 4 };
    const idle = renderFrame(finalNav);
    expect(idle).toContain("Create account ✓"); // BR-SHL-019: ✓ commit copy
    expect(idle).toContain('data-variant="primary"');
    expect(idle).not.toContain(">Continue</button>"); // commit replaces Continue
    expect(idle).toContain(">Back</button>");

    // In flight: drive the controller (test seam) into working and re-render.
    const controller = createWizardCommitController("fallback");
    void controller.run(() => new Promise(() => undefined)); // never settles
    const working = renderFrame(finalNav, controller);
    expect(working).toContain("Working…");
    expect(working).toContain("disabled");

    // Success lifecycle: working → idle, no failure, outcome returned so the
    // frame can call onCommitted (toast + declared exit are the consumer's).
    const okController = createWizardCommitController("fallback");
    const seen: boolean[] = [];
    okController.subscribe(() => seen.push(okController.getState().working));
    const outcome = await okController.run(okCommit);
    expect(outcome).toEqual({ ok: true });
    expect(seen).toEqual([true, false]);
    expect(okController.getState()).toEqual({ working: false, failure: null });
  });

  it.todo(
    "US-SHL-010 TC-4 (browser/journey scope): success fires the account-created toast and routes to the declared exit screen",
  );

  it("US-SHL-010 TC-5 (negative): double-click sends exactly ONE commit request — single-flight", async () => {
    const controller = createWizardCommitController("fallback");
    const commit = vi.fn(okCommit);
    const [first, second] = await Promise.all([controller.run(commit), controller.run(commit)]);
    expect(commit).toHaveBeenCalledTimes(1); // BR-SHL-019: no duplicate record
    expect(first).toEqual({ ok: true });
    expect(second).toBeNull(); // the duplicate click was ignored
  });

  it("US-SHL-010 TC-6 (negative): a 500 commit renders the A18 §4 failed card with Retry; entered state preserved; retry clears it", async () => {
    const controller = createWizardCommitController("fallback");
    await controller.run(async () => ({
      ok: false as const,
      reason: "We could not save this account (server error 500).",
    }));
    const html = renderFrame({ step: 4, reached: 4 }, controller);
    expect(html).toContain("state-failed"); // FailedWithRetry, composed not rebuilt
    expect(html).toContain("Account not created.");
    expect(html).toContain("We could not save this account (server error 500).");
    expect(html).toContain(">Retry</button>");
    // Entered state preserved: the step content is still on screen above it.
    expect(html).toContain("Review &amp; confirm");
    // Retry re-submits the same commit; success clears the failure.
    const outcome = await controller.run(okCommit);
    expect(outcome).toEqual({ ok: true });
    expect(controller.getState()).toEqual({ working: false, failure: null });
  });

  it.todo(
    "US-SHL-010 TC-7 (browser scope): at 1000px the step rail scrolls horizontally without wrap or page overflow — Playwright viewport test (the A12 breakpoint rule lives in WizardFrame.css)",
  );

  // ── Supplementary (non-TC) coverage ──────────────────────────────────────

  it("US-SHL-010 (BR-SHL-018): a pasted ?step= clamps to the reached step — deep links never skip unvisited steps", () => {
    const nav: WizardNavState = { step: 2, reached: 2 };
    expect(clampStepToReached(9, nav, 4)).toEqual({ step: 2, reached: 2 });
    expect(clampStepToReached(0, nav, 4)).toEqual({ step: 1, reached: 2 });
    expect(clampStepToReached(Number.NaN, nav, 4)).toEqual({ step: 1, reached: 2 });
    expect(clampStepToReached(2, { step: 1, reached: 3 }, 4)).toEqual({ step: 2, reached: 3 });
  });

  it("US-SHL-010 (BR-SHL-020): a thrown commit (network drop) still fails in plain language, never a raw error", async () => {
    const controller = createWizardCommitController(i18n.t("wizard.failed.reason"));
    await controller.run(async () => {
      throw new Error("ECONNRESET");
    });
    expect(controller.getState().failure?.reason).toBe(
      "Something went wrong committing this step. Retry runs the same commit again.",
    );
  });

  it("US-SHL-010 (A18 §4): partial-success counts from the commit payload render with the failing-rows link", async () => {
    const controller = createWizardCommitController("fallback");
    await controller.run(async () => ({
      ok: false as const,
      reason: "2 rows could not be read.",
      partial: { imported: 84, needReview: 6, failed: 2 },
    }));
    const html = renderFrame({ step: 4, reached: 4 }, controller);
    expect(html).toContain("84 imported · 6 need review · 2 failed");
    expect(html).toContain("View failing rows");
  });

  it("US-SHL-010 (rail semantics): numbered rail with done/active state classes and an accessible name", () => {
    const html = renderFrame({ step: 3, reached: 3 });
    expect(html).toContain('aria-label="Wizard steps"');
    expect(html).toContain('data-wizard="rail"');
    expect(html).toContain(">1</span>"); // numbered .n badges
    expect(html).toContain(">2</span>");
    expect(html).toContain('data-state="done"');
    expect(html).toContain('data-state="active"');
    expect(html).toContain(">Continue</button>"); // not the final step yet
  });
});


// ══════════════════════════════════════════════════════════════════════════
// CR-030 W5 task 5.1 · BR-SHL-047 — PARK & RESUME, ONCE, ON THE FRAME
// ══════════════════════════════════════════════════════════════════════════
//
// It lives here rather than in a feature so the eleventh wizard to mount this
// component gets it free, which is the whole of task 5.1's "EVERY wizard".

function exitConfig(over: Partial<WizardExit> = {}): WizardExit {
  return {
    onSaveAndExit: noop,
    parkBlockedReason: null,
    parkOpen: false,
    onParkOpenChange: noop,
    onPark: async () => ({ ok: true as const }),
    dateFormat: "MM/DD/YYYY",
    parkedAt: null,
    ...over,
  };
}

function renderWithExit(exit: WizardExit, nav: WizardNavState = { step: 2, reached: 2 }): string {
  return renderToStaticMarkup(
    <WizardFrame
      steps={s18Steps({ name: "Maria Delgado" })}
      nav={nav}
      onNavChange={noop}
      commitLabel="Create account ✓"
      commitFailedTitle="Account not created."
      onCommit={okCommit}
      onCommitted={noop}
      exit={exit}
    />,
  );
}

describe("BR-SHL-047 · B18 §4.2 — park & resume on the shared frame", () => {
  it("B18 §4.2: the NINE reasons are a CLOSED vocabulary, in the ruled order", () => {
    expect([...WIZARD_PARK_REASONS]).toEqual([
      "customer",
      "documents",
      "deposit",
      "payment",
      "inspection",
      "permit",
      "materials",
      "site_access",
      "third_party",
    ]);
    // A tenth typed by a clerk would be a WAITING ON value nothing can filter,
    // count or age — so the type refuses it.
    expect(isWizardParkReason("documents")).toBe(true);
    expect(isWizardParkReason("waiting on the weather")).toBe(false);
    // Every reason has catalogue copy, and each key is a LITERAL so G18 can see
    // it — a template key renders perfectly and reads as nine dead entries.
    expect(WIZARD_PARK_REASON_COPY).toHaveLength(9);
    expect(WIZARD_PARK_REASON_COPY.map((row) => row.code)).toEqual([...WIZARD_PARK_REASONS]);
    for (const row of WIZARD_PARK_REASON_COPY) {
      expect(row.key.startsWith("wizard.park.reason.")).toBe(true);
      expect(row.en).toContain("waiting on");
    }
  });

  it("draws both controls beside the footer primary, and the park form only when opened", () => {
    const closed = renderWithExit(exitConfig());
    expect(closed).toContain('data-wizard="exit"');
    expect(closed).toContain("Save &amp; exit");
    expect(closed).toContain(">Park</button>");
    expect(closed).not.toContain('data-wizard="park"');
    // Back and Continue keep their place — the exit group takes the left of the
    // SAME row (B18 §4.2: "a secondary Park beside the footer primary").
    expect(closed).toContain(">Back</button>");
    expect(closed).toContain(">Continue</button>");

    const open = renderWithExit(exitConfig({ parkOpen: true }));
    expect(open).toContain('data-wizard="park"');
    // BR-SHL-047: the nine, the note AND the remind-on date, as the service
    // request already has.
    expect(open).toContain('id="wizard_park_reason"');
    expect(open).toContain('id="wizard_park_note"');
    expect(open).toContain('id="wizard_park_remind_on"');
    for (const row of WIZARD_PARK_REASON_COPY) {
      expect(open).toContain(`value="${row.code}"`);
    }
    // And the STEP the row will reopen at — B18 §4.2's resume contract.
    expect(open).toContain("Parked at step 2 of 4");
  });

  it("BR-SHL-025: a flow that cannot park says so ON the control, and the form stays shut", () => {
    const reason = "Parking has nowhere to be recorded yet.";
    const html = renderWithExit(exitConfig({ parkBlockedReason: reason, parkOpen: true }));
    expect(html).toContain('data-wizard="park-blocked"');
    expect(html).toContain(reason);
    expect(html).toContain("disabled=");
    // ⚠ A pasted `?park=1` cannot open a form whose submit has nowhere to go.
    expect(html).not.toContain('data-wizard="park"');
  });

  it("BR-SHL-047's OPEN half: the age of a parked flow is VISIBLE, and nothing refuses it", () => {
    const html = renderWithExit(exitConfig({ parkedAt: "2020-01-01T00:00:00Z" }));
    expect(html).toContain('data-wizard="park-age"');
    // No limit is drawn, because none was ruled: the PO settled that parking is
    // offered and not what stops a parked move-out holding a unit forever.
    expect(html).not.toContain("expired");
    expect(renderWithExit(exitConfig())).not.toContain('data-wizard="park-age"');
    expect(parkAgeDays("2026-08-19T00:00:00Z", new Date("2026-08-24T00:00:00Z"))).toBe(5);
  });

  it("a frame with no exit is unchanged — every wizard that has not been widened yet", () => {
    const html = renderFrame({ step: 2, reached: 2 });
    expect(html).not.toContain('data-wizard="exit"');
    expect(html).not.toContain("Save &amp; exit");
  });
});

// ── B14 rule 6 · the commit tier (DEF-712) ─────────────────────────────────
//
// The defect: `WorkingButton` took no `variant`, so `WizardFrame` could only
// ever render the PRIMARY tier and rule 6's danger button was unreachable from
// every wizard commit in the product — a disconnection committed through a
// button styled exactly like Save. The fix is one optional tier per shared
// component. These cases read the RENDERED class attribute, because the
// defect's own escape reason is that nothing in this repo reads rendered
// output, and because a case that asked "did the prop travel" would have
// passed on the day the tier could not be reached at all.
const FINAL: WizardNavState = { step: 4, reached: 4 };

describe("B14 rule 6 (DEF-712) — a wizard declares whether its commit is destructive", () => {
  it("declared destructive: the commit renders the DANGER tier, and nothing else on the frame moves", () => {
    const html = renderFrame(FINAL, undefined, "danger");
    const commit = buttonTagLabelled(html, "Create account ✓");
    expect(commit).toContain('data-variant="danger"');
    expect(commit).toContain(`class="${buttonClasses("danger")}"`);
    // Rule 6 is about the COMMIT. Back stays the secondary it has always been,
    // and the rail is untouched — a tier that leaked would be a new defect.
    expect(buttonTagLabelled(html, "Back")).toContain('data-variant="secondary"');
    const railStep = buttonTagLabelled(html, "Review");
    expect(railStep).toContain('data-wizard-step="4"');
    expect(railStep).not.toContain("danger");
  });

  it("negative — a flow that declares NOTHING is byte-for-byte the primary commit it always was", () => {
    const html = renderFrame(FINAL);
    const commit = buttonTagLabelled(html, "Create account ✓");
    expect(commit).toContain('data-variant="primary"');
    expect(commit).toContain(`class="${buttonClasses("primary")}"`);
    // The negative half is the one that protects the other thirteen call
    // sites: creating an account is not destructive and must not go red.
    expect(commit).not.toContain("danger");
    expect(html).not.toContain('data-variant="danger"');
  });

  // ── THE THREE PROPERTIES THE W7 LANE REFUSED TO TRADE ────────────────────
  // It would not draw a second, danger-coloured commit button beside the
  // frame's, because that loses single-flight, the working state and
  // failure-with-entered-state-preserved. Threading a tier must cost none of
  // the three, so each is re-asserted WITH the danger tier set rather than
  // assumed to have survived.

  it("single-flight survives the tier: a double-click on a DANGER commit still sends exactly ONE request", async () => {
    const controller = createWizardCommitController("fallback");
    const commit = vi.fn(okCommit);
    const [first, second] = await Promise.all([controller.run(commit), controller.run(commit)]);
    expect(commit).toHaveBeenCalledTimes(1); // BR-SHL-019
    expect(first).toEqual({ ok: true });
    expect(second).toBeNull();
    // And the rendered danger button is the one carrying that guard.
    const inFlight = createWizardCommitController("fallback");
    void inFlight.run(() => new Promise(() => undefined)); // never settles
    const working = buttonTagLabelled(
      renderFrame(FINAL, inFlight, "danger"),
      "Working…",
    );
    expect(working).toMatch(/\sdisabled=/);
    expect(working).toContain('data-variant="danger"');
  });

  it("the A18 §3 working state survives the tier: 'Working…' on a button that is still the danger tier", () => {
    const controller = createWizardCommitController("fallback");
    void controller.run(() => new Promise(() => undefined));
    const html = renderFrame(FINAL, controller, "danger");
    expect(html).toContain("Working…");
    expect(buttonTagLabelled(html, "Working…")).toContain(
      `class="${buttonClasses("danger")}"`,
    );
  });

  it("A18 §4 failure-with-entered-state-preserved survives the tier: the failed card, and every value still on screen", async () => {
    const controller = createWizardCommitController("fallback");
    await controller.run(async () => ({
      ok: false as const,
      reason: "We could not schedule this (server error 500).",
    }));
    const html = renderFrame(FINAL, controller, "danger");
    expect(html).toContain("state-failed");
    expect(html).toContain("We could not schedule this (server error 500).");
    expect(html).toContain(">Retry</button>");
    expect(html).toContain("Review &amp; confirm"); // entered state, still there
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-010@b9eb83e (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 54/54✔ (7 todo this packet — browser/journey/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
