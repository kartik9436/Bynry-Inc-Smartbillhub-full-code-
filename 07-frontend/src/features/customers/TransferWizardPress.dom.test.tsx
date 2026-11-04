// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-CUS-5934` — the Product Owner, walking the live product on
//          2026-09-20: *"step 4 when last tick is press - uI breaks"*.
// Rules:   CLAUDE.md hard-won law 2 (built is not wired) · law 6 (diff the
//          running app — no gate here reads rendered output) · law 7 (a check
//          must be shown RED on the thing it was written for, and you must be
//          able to say what would make it pass wrongly) · `BR-SHL-018`
// Screens: `TRF-02.4` — Accounts blueprint p116, "What the buyer takes on"
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **WHY THIS FILE EXISTS, AND IT IS THE WHOLE POINT.** `TransferWizard.test.tsx`
// had **39 passing cases and a clean `tsc` over this defect**, because every one
// of them is `renderToStaticMarkup` — a STRING of HTML. A string cannot be
// pressed. The case that came closest reads
//
//     expect(html).toContain("trf_shown_to_buyer")
//
// which asserts that the tick was DRAWN and can never assert that pressing it
// does anything at all. The Product Owner found the defect in one pass of the
// product. **So the rule this file follows is: a control is proved by pressing
// it, and markup around a control is not evidence about the control.**
//
// ⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY, asked of each before it was
// trusted (law 7, habit 2):**
//
//   * *"the box is checked afterwards"* alone would pass on a screen that had
//     fallen over, because jsdom keeps the DOM node an error boundary has
//     replaced the SUBTREE of only if the boundary is above it. So every case
//     also asserts the step's own heading is still on screen and that React
//     logged no error — three claims, not one.
//   * *"the heading is still there"* alone would pass without the press having
//     done anything, so the box's checked state is read before AND after.
//   * Mounting the wizard bare in a `MemoryRouter` with no `/:tenant/...` route
//     makes every address it builds come out malformed while still reading as a
//     good string — the mechanism that shipped a front page full of
//     `//portal/…` links. So this mounts at the REAL route pattern, exactly as
//     `applicantCapture.dom.test.tsx` next door does.
//
// ⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN, IN THE HARNESS THAT RUNS IT.**
// With `TakeOnStep`'s tick handler changed to throw — which is the shape of the
// defect the PO reported — `npx vitest run TransferWizardPress.dom.test.tsx`
// reports the press case FAILED with the step's heading gone from the document.
// Restored, the file is green. Running it through `node <file>` instead would
// have exercised a path vitest never takes, which is `DEF-GOV-3733`'s lesson.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import { createApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { shellBootSeed } from "@/components/shellBootSeed";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

import { TransferWizard } from "./TransferWizard";
import { TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";

afterEach(cleanup);

const TEST_TENANT = "brazosbend";
const t = (key: string): string => i18n.t(key) as string;

/**
 * ⚠ **THE WORDS A CLERK READS, NOT THE KEYS — AND A DRAFT OF THIS FILE FAILED
 * FOUR CASES FOR ASKING THE WRONG QUESTION.** Step 4 renders through
 * `t(key, { defaultValue })` and only **four** of its keys are in `en.json`
 * (`asAt`, `asAtUnset`, `takenOn`, `toldTitle`); the rest live as defaults in
 * the component. So asking i18n for one of those keys hands back THE KEY
 * ITSELF, and a test matching on it finds nothing on a perfectly good screen.
 * The literals below are what is actually drawn, which is also the thing the
 * defect was reported about — the PO pressed a control labelled *"I have shown
 * this to the buyer"*, not one labelled `customers.transfer.step4.shown`.
 */
const STEP4 = {
  title: "What the buyer takes on",
  shown: "I have shown this to the buyer",
  balance: "Account balance",
  takenOn: "Taken on by the buyer",
  interest: "Deposit interest earned",
} as const;

/**
 * **STEP 4's SECTION HEADING — the `<h3>` INSIDE the step, never the page
 * head's `<h1>` (`DEF-CUS-6542`, 2026-09-24).**
 *
 * ⚠ **THE DRAWING PUTS THESE FIVE WORDS ON THE SCREEN TWICE.** p130 titles the
 * page *"What the buyer takes on"* AND heads the left column with the same
 * sentence, so from the moment the page head started naming its own step —
 * before that it read *"Find the account, and who is selling"* on all five —
 * `getByText(STEP4.title)` matches TWO nodes and throws.
 *
 * ⚠ **THE COLLISION IS GONE AND THE SELECTOR STAYS — 2026-09-24, lane TRF-CAP.**
 * The PO ruled the five page heads shortened to B14 rule 33's cap (*"Shorten all
 * five to the cap"*), so step 4's `<h1>` now reads *The money* and only the
 * section heading carries these five words. **That is not a reason to go back to
 * `getByText`.** Addressing the heading by role and level is what these three
 * assertions always meant; a selector that can settle on the `<h1>` passes over
 * the exact crash they exist to catch, and the head is one ruling away from
 * colliding again.
 *
 * ⚠ **AND RESOLVING IT THE OTHER WAY WOULD HAVE GUTTED THE CASE.** The three
 * assertions below use this to mean *the step is still the step*, and their own
 * comment says why: *"a boundary replaces the CONTENT and leaves the frame, so
 * the frame being there proves nothing"*. **The `<h1>` is the frame.** A
 * selector that quietly settled on it would have gone on passing over the exact
 * crash the PO reported — hard-won law 7's *looking at the wrong thing*, one
 * heading level up. So this addresses the CONTENT heading by role and level,
 * which is what the cases meant all along and could not say while only one node
 * carried the words.
 */
const step4SectionHeading = (): HTMLElement =>
  screen.getByRole("heading", { level: 3, name: STEP4.title });
const findStep4SectionHeading = async (): Promise<HTMLElement> =>
  await screen.findByRole("heading", { level: 3, name: STEP4.title });

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Mount the REAL wizard at the REAL address, on the step asked for.
 *
 * ⚠ The account payload is the one the finder resolves; it is shaped rather
 * than empty because step 4's figures are the SERVER's and a screen given
 * nothing to draw would prove nothing about drawing.
 */
function mountAt(step: number): void {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      if (/\/accounts\/[^/?]+$/.test(url)) {
        return json({
          id: "acc-10012",
          account_no: "AC-2026-00012",
          balance: "412.7500",
          deposit_on_file: "150.0000",
          currency: "USD",
          premise_address: "123 Willow Bend Dr, Silver Creek, TX 78611",
        });
      }
      return json({ count: 0, results: [] });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${TRANSFER_WIZARD_ROUTE}?step=${step}`]}>
          <Routes>
            <Route
              path={`/:tenant${TRANSFER_WIZARD_ROUTE}`}
              element={<TransferWizard client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** React logs an error boundary's catch through `console.error`, and a crashed
 *  subtree is otherwise silent in jsdom. Captured so a case can say "nothing
 *  was thrown" rather than only "something is still on screen". */
let reactErrors: string[] = [];
beforeEach(() => {
  reactErrors = [];
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    reactErrors.push(args.map(String).join(" "));
  });
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("DEF-CUS-5934 · step 4's last tick is PRESSED, not merely drawn", () => {
  /**
   * **THE DEFECT ITSELF.** The Product Owner pressed this control in the live
   * product and the screen went down. Three claims, because any one of them
   * alone can pass over a broken screen — see this file's header.
   */
  it("pressing `I have shown this to the buyer` ticks it and leaves the step standing", async () => {
    mountAt(4);

    const heading = await findStep4SectionHeading();
    expect(heading).toBeInTheDocument();

    const box = screen.getByLabelText(new RegExp(STEP4.shown, "i"));
    expect(box).not.toBeChecked();

    await userEvent.click(box);

    // 1 · the control did something
    await waitFor(() => expect(box).toBeChecked());
    // 2 · the step is still the step — a boundary replaces the CONTENT and
    //     leaves the frame, so the frame being there proves nothing
    expect(step4SectionHeading()).toBeInTheDocument();
    // 3 · and React caught nothing on the way
    expect(reactErrors.filter((line) => /Error|Uncaught|boundary/i.test(line))).toEqual([]);
  });

  /** An UNTICK is the other half of the control, and a tick that records and
   *  then refuses to come back is the same defect one press later. */
  it("and it unticks again, with the step still standing", async () => {
    mountAt(4);
    const box = await screen.findByLabelText(new RegExp(STEP4.shown, "i"));

    await userEvent.click(box);
    await waitFor(() => expect(box).toBeChecked());
    await userEvent.click(box);
    await waitFor(() => expect(box).not.toBeChecked());

    expect(step4SectionHeading()).toBeInTheDocument();
    expect(reactErrors.filter((line) => /Error|Uncaught|boundary/i.test(line))).toEqual([]);
  });

  /**
   * ⛔ **THE FIGURES AROUND THE TICK SURVIVE THE PRESS TOO.** The defect the PO
   * reported was the whole step going down; a narrower version of it — the
   * money table disappearing while the tick and the heading stayed — would pass
   * both cases above. `BR-CUS-057`'s absence is asserted in the same breath,
   * because `$0.00` over an unbuilt interest engine is a claim, and a press
   * that replaced an absence with a zero is a money defect wearing a UI costume.
   */
  it("the money the buyer takes on is still drawn after the press", async () => {
    mountAt(4);
    const box = await screen.findByLabelText(new RegExp(STEP4.shown, "i"));
    await userEvent.click(box);
    await waitFor(() => expect(box).toBeChecked());

    expect(screen.getByText(STEP4.balance)).toBeInTheDocument();
    expect(screen.getByText(STEP4.takenOn)).toBeInTheDocument();
    expect(screen.getByText(STEP4.interest)).toBeInTheDocument();
    // The interest row is an ABSENCE with its reason and never a figure.
    expect(screen.queryByText("$0.00")).toBeNull();
  });
});

describe("DEF-CUS-5934 · every OTHER control on step 4 is pressed as well", () => {
  /**
   * ⚠ **THE SWEEP IS THE WHOLE SCREEN, NOT THE CONTENT PANE.** A first draft of
   * the browser walk scoped its control sweep to `[data-wizard="content"]` and
   * reported *"1 control pressed"* on this step — it saw the tick and none of
   * `Back`, `Continue`, `Save & exit` or `Park`, which live in the frame around
   * it. On this step the footer is where the two controls broken by
   * `DEF-CUS-5948` actually were. The COUNT is asserted so that a control
   * quietly disappearing from the footer fails this case rather than shrinking
   * the sweep in silence.
   */
  it("the step draws its four frame controls, all enabled, and none of them is a dead <span>", async () => {
    mountAt(4);
    await findStep4SectionHeading();

    for (const key of ["wizard.back", "wizard.continue", "wizard.exit.saveAndExit", "wizard.exit.park"]) {
      const control = screen.getByRole("button", { name: t(key) });
      expect(control).toBeInTheDocument();
      // Hard-won law 2's mirror: a control that is drawn and cannot act is a
      // refusal, and a refusal must carry its reason (`BR-SHL-025`). Here all
      // four can act, so none of them may be disabled.
      expect(control).toBeEnabled();
    }
  });
});
