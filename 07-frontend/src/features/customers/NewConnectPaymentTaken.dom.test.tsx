// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-7611 — step 6 took no payment at all. The section offered
//          Payment terms and Posting date under the refusal *"No payment is
//          taken here. Record it against the account."*, over a server that
//          had taken six payment fields since 2.391.0 (BR-MET-1187). A clerk
//          holding a cheque at the counter had to key it twice.
//          DEF-CUS-7681 — the browser's CommitManifest declared seven of the
//          server's twelve MANIFEST_KEYS.
// Rules:   BR-MET-1187 (the connection, the invoice and the payment in ONE
//          act) · CR-186-BRC10 / DEF-CUS-10324 (every payment is `posted` at
//          entry; only bank reconciliation clears it, so no clearing date) ·
//          BR-PAY-026 (the tender list is the TENANT's own lookup) ·
//          CLAUDE.md hard rule 2 (no money is summed, multiplied or rounded in
//          a browser) · hard-won law 2 and its mirror (a live screen behind a
//          dead control) · B14 rules 31, 32, 33, 43, 44
// Screens: S87 step 6 · Charges
// ───────────────────────────────────────────────────────
//
// ⚠ **THESE CASES READ RENDERED OUTPUT, NEVER PROPS.** `DEF-CWP-3925`'s whole
// lesson is that asking *"is the prop passed"* cannot see a control that is
// there and refuses; the assertions below are against the markup a clerk gets.
//
// ⚠ **A NEW FILE RATHER THAN CASES ADDED TO `NewConnectWizard.test.tsx`**, for
// the reason `NewConnectStepRefusal.dom.test.tsx` gives one file over: that
// file is 1,400 lines, more than one lane edits this wizard at a time, and in
// a shared tree the second lane to commit a shared file reverts the first with
// a correct file count and nothing in the diff to notice (CLAUDE.md law 11).
//
// ⚠ **PROVED RED FIRST, IN THE HARNESS THAT RUNS THEM (law 7).** Every case
// below was run against the pre-fix tree and named its own failure — the
// refusal string present, `paymentTakenOf` absent, the manifest five keys
// short. The red output is quoted in the commit message.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { ChargesStep, paymentBlocksContinue } from "./NewConnectChargesStep";
import { emptyDraft, paymentTakenOf } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";

const t = (key: string, options?: Record<string, unknown>) => String(i18next.t(key, options));

/**
 * ⚠ **EVERY RENDER IS TORN DOWN BETWEEN CASES, AND THIS FILE SHIPPED WITHOUT
 *  IT** (added 2026-09-29, `DEF-CUS-7921`).
 *
 *  `vite.config.ts` declares **no global `setupFiles`**, on purpose — so
 *  Testing Library's automatic cleanup never runs and each `.dom.test.tsx`
 *  owns its own `afterEach(cleanup)`. Without it every `render` is APPENDED
 *  to the same `document.body`, and `document.querySelector` then answers
 *  from the FIRST case that drew a matching node rather than from this one.
 *
 *  ⚠ **IT WAS INVISIBLE UNTIL TODAY, WHICH IS THE WHOLE LESSON.** While the
 *  payment boxes were drawn ONLY when a payment was being taken, the
 *  no-payment case contributed no `#nc_payment_amount` and the query happened
 *  to find the right one. `22cf1c575` made the boxes always-present and
 *  `disabled`, and from that commit the no-payment render — three cases
 *  earlier, permanently disabled — shadowed every later lookup. Measured:
 *  `document.querySelectorAll("#nc_payment_amount").length` was **3**.
 *
 *  **This is law 7's *looking at the wrong thing*:** the case was passing on
 *  another case's DOM, so it could neither fail honestly nor pass honestly.
 */
afterEach(cleanup);

/** The tenant's own tender list, as `GET /payments` serves it. Two of the six
 *  seeds are enough to prove the picker is SERVED and not typed. */
const METHODS = [
  { code: "check", name: "Check" },
  { code: "ach", name: "ACH" },
];

/** A client that answers the two reads step 6 makes and nothing else. */
function stubClient(): { get: unknown; post: unknown } {
  return {
    get: async (path: string) => {
      if (path.startsWith("/payments")) {
        return { data: { results: [], methods: METHODS, currency: "USD", count: 0 } };
      }
      return { data: { results: [], count: 0 } };
    },
    post: async () => ({
      data: { priced: false, currency: null, lines: [], total: { stored: null, display: null }, unavailable: [] },
    }),
  };
}

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/…` PATH PATTERN.** CLAUDE.md law 2's
 * fixture clause: a component mounted bare in a `MemoryRouter` has
 * `useParams().tenant` undefined, every address it builds comes out
 * `//portal/…`, and that reads as a perfectly good string to `toContain`.
 */
function renderStep(draft: NewConnectDraft) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/brazosbend/connections/new?step=6"]}>
        <Routes>
          <Route
            path="/:tenant/connections/new"
            element={
              <ChargesStep
                draft={draft}
                onPatch={() => undefined}
                t={t}
                dateFormat="MM/DD/YYYY"
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                client={stubClient() as any}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function taking(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  return { ...emptyDraft(), takePayment: "deposit", ...over };
}

// ════════════════════════════════════════════════════════════════════════════
// 1 · THE REFUSAL IS GONE AND THE CONTROL IS THERE (law 2's mirror)
// ════════════════════════════════════════════════════════════════════════════
describe("the charges step's payment block", () => {
  it("no longer tells the clerk that no payment is taken here", () => {
    // ⚠ **THE STRING IS ASSERTED ABSENT FROM THE MARKUP, NOT FROM THE
    // CATALOGUE.** A key retired while the component still renders a
    // `defaultValue` would pass a catalogue check and still print the
    // sentence — which is exactly the shape of a check looking at the wrong
    // thing (law 7).
    renderStep(emptyDraft());
    expect(screen.queryByText(/No payment is taken here/i)).toBeNull();
    expect(document.querySelector('[data-take-payment="not-built"]')).toBeNull();
  });

  it("offers a Payment option, and it is CLOSED by default", () => {
    // ⊕ **AMENDED 2026-09-29 (`22cf1c575`, `CR-150-BRC09` tasks 11–14).** Two
    // things moved and NEITHER is the capability — `DEF-CUS-7611`'s fix is
    // still on the screen, it is built differently:
    //   · **`Take payment` and `Method` became ONE `Payment option`.**
    //     `step4-charges.png` draws a single chooser whose empty entry IS
    //     *No payment now*, so the closed state is `value === ""` where it
    //     used to be the string `"none"` on a separate yes/no.
    //   · **The other boxes are DISABLED rather than ABSENT.** The drawing
    //     draws the whole panel at all times.
    // **The question is unchanged and is re-asked, not relaxed:** a clerk who
    // has not chosen a tender cannot enter a payment. Asserting `disabled`
    // holds that as tightly as asserting absence did — and it is the stricter
    // check of the two now, because a box that is merely gone tells you
    // nothing about a box that comes back enabled.
    renderStep(emptyDraft());
    const control = document.querySelector("#nc_payment_option") as HTMLSelectElement | null;
    expect(control).not.toBeNull();
    // The empty option is the ordinary answer and the drawn default: a build
    // committed with an invoice and no receipt.
    expect(control?.value).toBe("");
    const amount = document.querySelector("#nc_payment_amount") as HTMLInputElement | null;
    expect(amount).not.toBeNull();
    expect(amount?.disabled).toBe(true);
  });

  it("draws the tender, the reference and the amount once a payment is taken", () => {
    // ⊕ **AMENDED 2026-09-29 (`22cf1c575`).** `#nc_payment_method` is folded
    // into `#nc_payment_option`, which IS the tender list (`BR-PAY-026` — the
    // tenant's own `GET /payments` `methods[]`, never typed here). The four
    // facts this case names are the same four; the first one has a new id.
    // Each is also asserted ENABLED, which is the half that used to be
    // implied by the field merely existing.
    renderStep(taking());
    const tender = document.querySelector("#nc_payment_option") as HTMLSelectElement | null;
    const reference = document.querySelector("#nc_payment_reference") as HTMLInputElement | null;
    const amount = document.querySelector("#nc_payment_amount") as HTMLInputElement | null;
    expect(tender).not.toBeNull();
    expect(reference).not.toBeNull();
    expect(amount).not.toBeNull();
    expect(reference?.disabled).toBe(false);
    expect(amount?.disabled).toBe(false);
  });

  it("DEF-CUS-10324: asks NO clearing date — the payment is posted at entry (CR-186-BRC10)", () => {
    // Every payment is `posted` when it is taken and `cleared` only when its
    // deposit batch is reconciled with the bank. No screen sets a clearing
    // date, so neither the field nor the S22 form's clearing words appear.
    renderStep(taking());
    expect(document.querySelector("#nc_payment_cleared_date")).toBeNull();
    expect(document.querySelector('label[for="nc_payment_cleared_date"]')).toBeNull();
    expect(screen.queryByText(i18next.t("payments.form.clearedAtBrief") as string)).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 2 · NO MONEY ARITHMETIC ON SCREEN (hard rule 2)
// ════════════════════════════════════════════════════════════════════════════
describe("the payment summary", () => {
  it("states the absence of Outstanding rather than subtracting for it", () => {
    // `Quoted − Taken` is money arithmetic in a browser: forbidden, and the
    // shape of DEF-088 and DEF-127. The server publishes it on the build.
    // ⊕ **AMENDED 2026-09-29 (`22cf1c575`).** The line is called `Remaining`
    // on `step4-charges.png` and its marker is `data-charge-remaining-absent`;
    // it was `data-outstanding-absent`. **The rule it guards did not move an
    // inch** — `Total − Paid now` is money arithmetic in a browser, which hard
    // rule 2 forbids and `DEF-088`, `DEF-127` and `DEF-CUS-7704` are the cost
    // of — and the new marker is rendered UNCONDITIONALLY by `ChargeTotals`,
    // so the figure cannot appear even when both operands are known. That is
    // strictly stronger than what this line asked before.
    renderStep(taking({ paymentAmount: "1500.00" }));
    expect(document.querySelector("[data-charge-remaining-absent]")).not.toBeNull();
    expect(screen.queryByText(/1,530|1530/)).toBeNull();
  });

  it("never prints $0.00 for a figure nobody has given", () => {
    // A zero on a money line reads as *free*; the truth is *nothing yet*.
    //
    // ⊕ **AMENDED 2026-09-29 (`22cf1c575`).** The footer became three named
    // lines — Total, Paid now, Remaining — each stating its own absence, in
    // place of the one `data-payment-summary-absent="taken"` span. The case
    // asks the same thing of the line it was about: this fixture takes a
    // payment and gives NO amount, so `Paid now` has no figure and must say
    // so rather than print a zero.
    renderStep(taking());
    expect(document.querySelector("[data-charge-paid-absent]")).not.toBeNull();
    expect(screen.queryByText("$0.00")).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 3 · WHAT REACHES THE WIRE
// ════════════════════════════════════════════════════════════════════════════
describe("paymentTakenOf", () => {
  it("sends nothing at all when no payment is taken", () => {
    // Not nulls — NOTHING. A half-filled block a clerk then switched back must
    // not reach `_payment_taken_at_the_counter`, which refuses an amount with
    // no tender and a tender with no amount, each by name.
    expect(paymentTakenOf(emptyDraft())).toEqual({});
    expect(
      paymentTakenOf({ ...emptyDraft(), paymentAmount: "150.00", paymentMethod: "check" }),
    ).toEqual({});
  });

  it("sends the four keys the server reads, and no clearing date", () => {
    expect(
      paymentTakenOf(
        taking({
          paymentMethod: "check",
          paymentAmount: " 1500.00 ",
          paymentReference: " CHQ 118420 ",
          quotePostingDate: "2026-05-04",
        }),
      ),
    ).toEqual({
      payment_method: "check",
      payment_amount: "1500.00",
      payment_date: "2026-05-04",
      payment_reference: "CHQ 118420",
    });
  });

  it("DEF-CUS-10324: never puts a clearing date on the wire (CR-186-BRC10)", () => {
    const wire = paymentTakenOf(taking({ paymentMethod: "cash", paymentAmount: "20" }));
    expect("payment_cleared_date" in wire).toBe(false);
  });

  it("never sends a total and never rounds the amount", () => {
    // Hard rule 2: the clerk's characters travel, the server rounds once.
    const wire = paymentTakenOf(taking({ paymentMethod: "cash", paymentAmount: "20.005" }));
    expect(wire.payment_amount).toBe("20.005");
    expect(Object.keys(wire)).not.toContain("quote_total");
    expect(Object.keys(wire)).not.toContain("payment_outstanding");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 4 · THE STEP GATE MIRRORS THE SERVER AND INVENTS NOTHING
// ════════════════════════════════════════════════════════════════════════════
describe("paymentBlocksContinue", () => {
  it("passes a build taking no payment", () => {
    expect(paymentBlocksContinue(emptyDraft())).toBeNull();
  });

  it("refuses a tender with no amount, and an amount with no tender", () => {
    expect(paymentBlocksContinue(taking({ paymentMethod: "check" }))).toBe(
      "metering.connection_payment_amount_required",
    );
    expect(paymentBlocksContinue(taking({ paymentAmount: "150" }))).toBe(
      "metering.connection_payment_method_required",
    );
  });

  it("passes a complete tender with no clearing date (there is none to ask)", () => {
    expect(
      paymentBlocksContinue(taking({ paymentMethod: "check", paymentAmount: "150" })),
    ).toBeNull();
  });

  it("uses the SERVER's own sentence for each refusal", () => {
    // BR-SHL-020 r2 — one rule, one sentence, whether it is refused on the
    // step or at the commit. Both keys are in the catalogue already.
    for (const key of [
      "metering.connection_payment_amount_required",
      "metering.connection_payment_method_required",
    ]) {
      expect(String(i18next.t(key))).not.toBe(key);
    }
  });
});
