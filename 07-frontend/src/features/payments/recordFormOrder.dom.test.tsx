// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-3507 — the Product Owner, walking the deployed Record payment
//          modal on 2026-09-03: *"too much text on the form and Im not sure
//          whether inputs are arranged in logical order"*.
// Story:   US-PAY-001 (the S22/S35 Record modal)
//          Screens: S22 · S35
// Rules:   B14 rule 32 (a screen has a description budget: ONE sentence per
//          section, a stated absence CLOSED by default, a row never repeats
//          what its own control offers, no rule id or internal code in
//          clerk-facing copy) · BR-PAY-012 (purpose) · BR-PAY-021 (both dates)
// ───────────────────────────────────────────────────────
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE ORDER A CLERK WORKS IN, AS AN ASSERTION                             ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// WHO PAID → HOW MUCH → WHEN → HOW (kind, tender, reference, memo) → WHAT IT
// IS FOR. A counter transaction happens in that order and this form did not.
//
// **RED PROVED FIRST (hard-won law 7).** Both cases were run against the tip
// this lane started from (`44d6b23f`) in a detached `git worktree`, so the
// pre-fix component was the real one and nothing shared was moved. Verbatim:
//
//     × the fields are in the order a clerk works in
//         - Expected
//         + Received
//           Array [
//             "account_query",
//         +   "account_id",
//             "amount",
//             "posted_at",
//             "cleared_at",
//             "type",
//             "method",
//             "confirmation",
//         +   "apply_to",
//             "memo",
//             "purpose",
//         -   "apply_to",
//           ]
//     × the long copy is present and CLOSED, never led with
//       → expected null not to be null   [no <details> in the modal at all]
//
//     Tests  2 failed (2)
//
// Read that diff as a sentence rather than as two lists. **`purpose` was LAST**
// — past the memo box, past `apply_to`, at the very bottom of the form — so the
// two questions that between them decide where the money lands sat on either
// side of a free-text note. That is the whole of the PO's second clause, and it
// is why this is asserted as an ORDER and not as a set of ids being present.
//
// The `+ "account_id"` line is DEF-3506 showing through: the select used to be
// in the DOM before anything had been searched for, which is the other half of
// this same walk and is proved in `accountSearch.dom.test.tsx`.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { PaymentMethodOption } from "@/api/endpoints";
import i18n from "@/i18n";
import { ToastProvider } from "@/components/Toast";

// ⚠ **`RecordPaymentModal` BECAME `RecordPaymentForm` ON 2026-09-23 (`DEF-PAY-6317`).**
// 2·3a is a PAGE at `/:tenant/payments/record/new` (blueprint p037), so the
// form is a COMPONENT (B14 rule 43) inside `FormPage` rather than `FormModal`.
// Same props, with `onClose` renamed `onCancel` — a page goes BACK somewhere;
// it does not close. Every case below is unchanged and asserts the same thing.
import { RecordPaymentForm } from "./RecordPaymentPage";

const t = (key: string): string => i18n.t(key);

afterEach(cleanup);

const METHODS: PaymentMethodOption[] = [
  { id: "met-check", code: "check", name: "Check" },
  { id: "met-cash", code: "cash", name: "Cash" },
];

/** Answers nothing. The order of the fields does not depend on any read. */
const SILENT: ApiClient = {
  get: vi.fn().mockImplementation(() => Promise.resolve({ data: { results: [], count: 0 } })),
} as unknown as ApiClient;

function mount() {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazos/payments/record"]}>
          <RecordPaymentForm
            client={SILENT}
            methods={METHODS}
            today="2026-09-03"
            dateFormat="MM/DD/YYYY"
            currency="USD"
            onCancel={() => undefined}
            onRecorded={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Every field the modal draws, in DOM order, by id.
 *
 *  ⚠ **A FIELD'S OWN FURNITURE IS NOT A FIELD.** The filter already drops the
 *  `-help` line and the `-error` line a field carries; since `DEF-PAY-6319` the
 *  account picker is a combobox, so it also carries a `-listbox` its
 *  `aria-controls` names and an `-opt-N` per match. None of those is a field a
 *  clerk fills in, and counting them would make this census red every time a
 *  control grew a piece of ARIA. */
function fieldOrder(): string[] {
  // ⚠ **`[data-form-page]` AND NOT `.modal-body` SINCE 2026-09-23 (`DEF-PAY-6317`).**
  // 2·3a is a PAGE now (blueprint p037), so the fields sit in `FormPage`'s form
  // element rather than a modal body. The QUESTION and the expected order below
  // are unchanged — which is the point: the frame moved and the form did not.
  return [...document.querySelectorAll<HTMLElement>("[data-form-page] [id]")]
    .map((el) => el.id)
    .filter(
      (id) =>
        id !== "" &&
        !id.endsWith("-help") &&
        !id.endsWith("-error") &&
        !id.endsWith("-listbox") &&
        !/-opt-\d+$/.test(id),
    );
}

describe("DEF-3507 — the Record payment modal reads in the order a clerk works", () => {
  it("the fields are in the order a clerk works in", () => {
    mount();
    // ⚠ **`account_id` IS THE WHOLE PICKER SINCE 2026-09-23 (`DEF-PAY-6319`).**
    // It was two ids — an `account_query` box, and an `account_id` select that
    // appeared under it once a search matched (DEF-3506), which is why only the
    // first of them was ever in this list. The PO reported the two gestures on
    // the refund form (*"user has to do two clicks"*) and it is one combobox
    // now, drawn always, keyed on the id the form validates. The picker's own
    // file still owns its five states; `method` and `confirmation` are drawn
    // under the cash kind, which is the default, so both are here.
    expect(fieldOrder()).toEqual([
      // WHO PAID
      "account_id",
      // HOW MUCH
      "amount",
      // ⚠ **WHAT IT IS FOR, SECOND — PO RULING 2026-09-13, SUPERSEDING THE
      // ORDER THIS TEST WAS WRITTEN TO PIN.** `purpose` sat ninth here, next
      // to `apply_to` at the foot, on `DEF-3507`'s reasoning that purpose is
      // the coarse question and apply_to the fine one. **That fix named `S22`
      // in its own trace header and never reached `S22`** — so the account's
      // twin of this form kept the shape the PO had rejected for ten days,
      // because THIS screen had a field-order test and that one had none.
      // Lane C then built `S22` to the blueprint under B14 rule 41, which
      // draws this form twice with `purpose` directly under the amount, and
      // the collision between the PO's own September ruling and rule 41 was
      // put to them: **the blueprint order, on BOTH screens.**
      //
      // So the coarse/fine adjacency is deliberately broken: a clerk answers
      // *what is this money for* while the amount is still under their hand,
      // and `apply_to` moves up beside the bills it names. The eight fields
      // the two forms share are now in identical relative order — this file
      // is the assertion that they stay that way.
      "purpose",
      // WHEN — BR-PAY-021's two dates, posting first because it is the one
      // billing judges lateness by and the one that is pre-filled.
      "posted_at",
      // ⛔ `cleared_at` LEFT 2026-10-30 (`DEF-PAY-10737`, CR-186: the bank
      // reconciliation writes the clearing date; the server never stored it).
      // HOW — the kind decides whether there IS a tender, so it leads the
      // group it governs; the memo is the last thing written on a receipt.
      "type",
      "method",
      "confirmation",
      "apply_to",
      "memo",
    ]);
  });

  it("the long copy is present and CLOSED, never led with", () => {
    mount();
    const details = document.querySelector<HTMLDetailsElement>("[data-form-page] details");
    expect(details).not.toBeNull();

    // B14 rule 32: a stated absence — and here, an explanation — is a
    // `<details>` CLOSED by default. Closed is what it IS, so the copy cannot
    // leak back onto the screen through a prop nobody passes.
    expect((details as HTMLDetailsElement).open).toBe(false);

    // ⚠ NOTHING WAS DELETED. Each sentence a lane wrote to stop the next
    // reader filing a gap as a bug is still in the DOM and still findable.
    const inside = (details as HTMLDetailsElement).textContent ?? "";
    expect(inside).toContain(t("payments.form.purposeHelp"));
    expect(inside).toContain(t("payments.form.postedAtHelp"));
    // ⛔ `clearedAtHelp` went with its box (`DEF-PAY-10737`) — it said a blank
    // clearing date "meets no bill", which CR-186 made false.
    expect(inside).not.toContain(t("payments.form.clearedAtHelp"));
    expect(inside).toContain(t("payments.form.typeHelp"));
    expect(inside).toContain(t("payments.form.methodHelp"));
    expect(inside).toContain(t("payments.form.amountHelp"));

    // …and the four purposes are NOT restated beside the control that offers
    // them. That sentence naming all four is rule 32's own worked example of
    // "a row never repeats what its own control offers".
    const purposeHelp = document.querySelector("#purpose-help");
    expect(purposeHelp).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-3507 (the Product Owner's walk of all four Payments tabs, 2026-09-03) · US-PAY-001 · CR-059 §8 CS-4/CS-23/CS-35 · B14 rule 32 · 04-docs/02-decisions/14-ui-conventions.md
// generated: 2026-09-03 by the payments PO-walk lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — both cases run against the pre-fix tip 44d6b23f in a detached worktree, output quoted verbatim above · tsc --noEmit✔ · eslint --max-warnings 0 (features/payments)✔ · vitest src/features/payments src/styles = 287 passed / 20 files✔
// exceptions: the modal's LOOK is not asserted — no gate in this repo reads rendered output (hard-won law 6), so the spacing, the disclosure marker and the one-row toolbars this lane also changed are proved by clicking and by nothing else
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
