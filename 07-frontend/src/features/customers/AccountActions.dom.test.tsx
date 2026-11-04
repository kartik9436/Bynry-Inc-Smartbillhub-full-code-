// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-5164 (Record payment — `What this money is for` is drawn
//          SECOND and was built LAST, past the memo box) ·
//          DEF-CUS-5165 (the two helper sentences the blueprint draws under
//          `Reference or cheque number` and `Memo` were not on the screen) ·
//          DEF-CUS-5166 (Add note — the drawn helper sat under the wrong
//          input) · DEF-CUS-5167 (Adjust — the Reason picker was optional on
//          the form and the server refuses an adjustment without one)
// Story:   US-CUS-012 (S22 Record payment) · US-CUS-013 (Adjust) ·
//          US-CUS-015 (Add note)
//          Screens: S21 · S22
// Rules:   B14 rule 41 (the product UI matches the blueprint EXACTLY —
//          *"layout, grouping, ORDER, labels, which facts appear — is the
//          drawing's and is built"*) · B14 rule 38 (the drawing decides which
//          fields, in which order, with which helper sentence) · B14 rule 39
//          (label → input → helper) · BR-PAY-012 · BR-TEN-036
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE DRAWN ORDER AND THE DRAWN HELPERS, AS ASSERTIONS                    ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// **WHY THIS FILE EXISTS AT ALL.** The sibling Record modal — `S35`, in
// `features/payments` — has carried a field-order test since `DEF-3507`
// (`recordFormOrder.dom.test.tsx`, 2026-09-03, written after the PO walked the
// deployed form). That fix names `S22` in its own trace header and never
// reached `S22`, and nothing noticed for ten days, because **no gate in this
// repository reads rendered output and this modal had no order test of its
// own.** So the account-side form kept the shape the PO rejected — purpose at
// the very foot of the dialog, on the far side of the memo box — while its twin
// two clicks away was fixed.
//
// ⚠ **THE ORDER ASSERTED HERE IS THE BLUEPRINT'S AND NOT `S35`'s, AND THE TWO
// DISAGREE BY ONE FIELD.** The accounts blueprint draws `What this money is
// for` SECOND, directly under `Amount`, in BOTH of its drawings of this form —
// the as-built frame `ACC-A06` (*"a modal, not a wizard — one step, eight
// fields, and it commits"*) and R4's redrawn `ACC-Q06`, where it is the second
// row of THE MONEY. `S35` puts it second-to-LAST, adjacent to `apply_to`.
// B14 rule 41 (ratified 2026-09-13) settles which one this screen is built to:
// *"Everything else — layout, grouping, order, labels, which facts appear — is
// the drawing's and is built."* Whether the two forms should then be reconciled
// is a question for a person and is recorded in `DEF-CUS-5164`, not decided
// here.
//
// ⚠ **jsdom COMPUTES NO LAYOUT, SO THIS FILE ASSERTS NO PIXEL.** B14 rule 39's
// 5 / 6 / 20 figures have no gate anywhere in this repo and this one does not
// pretend to be one. What is asserted is ORDER, PRESENCE, ATTACHMENT and
// BEHAVIOUR. Saying so is cheaper than being caught by hard-won law 7's
// *looking at the wrong thing*.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { AddNoteModal, AdjustModal, RecordPaymentModal } from "./AccountActions";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);
const TENANT = "brazosbend";
const ACCOUNT = "acc-10432";

/** Answers nothing useful. None of the assertions below depends on a read. */
function silentClient(): ApiClient {
  return {
    get: vi.fn().mockImplementation(() => Promise.resolve({ data: { results: [], count: 0 } })),
    post: vi.fn().mockImplementation(() => Promise.resolve({ data: {} })),
    patch: vi.fn().mockImplementation(() => Promise.resolve({ data: {} })),
    delete: vi.fn().mockImplementation(() => Promise.resolve({ data: {} })),
  } as unknown as ApiClient;
}

/**
 * Mounted UNDER THE REAL PATH PATTERN, never a bare `MemoryRouter`.
 *
 * Hard-won law 2's fixture clause: a routed component with no `/:tenant/...`
 * route leaves `useParams()` undefined, every address the screen builds comes
 * out `//…`, and a broken link still reads as a perfectly good string to
 * `toContain`.
 */
function mount(element: React.ReactElement) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/accounts/${ACCOUNT}`]}>
          <Routes>
            <Route path="/:tenant/accounts/:accountId" element={element} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Every control the dialog draws, in DOM order, by id — the same instrument
 *  `recordFormOrder.dom.test.tsx` uses on the sibling modal, so a reader can
 *  put the two lists side by side. */
function fieldOrder(): string[] {
  return [...document.querySelectorAll<HTMLElement>(".modal-body [id]")]
    .map((el) => el.id)
    .filter((id) => id !== "" && !id.endsWith("-help") && !id.endsWith("-error"));
}

/** The helper actually attached to a field, read the way a screen reader reads
 *  it: the element the input points at with `aria-describedby`. Reading the
 *  page for the SENTENCE would pass wherever it happened to render, which is
 *  the defect this guards. */
function helperOf(id: string): string {
  const input = document.getElementById(id);
  expect(input).not.toBeNull();
  const described = (input as HTMLElement).getAttribute("aria-describedby") ?? "";
  const ids = described.split(/\s+/).filter((one) => one.endsWith("-help"));
  return ids
    .map((one) => document.getElementById(one)?.textContent ?? "")
    .join(" ")
    .trim();
}

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-5164 / DEF-CUS-5165 — Record payment is the form the blueprint draws", () => {
  function open(balance: string | null = "2410.000000") {
    return mount(
      <RecordPaymentModal
        accountId={ACCOUNT}
        accountLabel="Bramble Bakery"
        currency="USD"
        balance={balance}
        today="2026-09-13"
        dateFormat="MM/DD/YYYY"
        client={silentClient()}
        onClose={() => undefined}
        onRecorded={() => undefined}
      />,
    );
  }

  it("draws the drawn fields in the order BOTH drawings put them in", () => {
    open();
    // `ACC-A06` and `ACC-Q06`, read top to bottom:
    //   Amount · What this money is for · Posting date · Clearing date ·
    //   Method · Reference or cheque number · Apply to · Memo
    //
    // ⚠ THE ONE THAT MOVED IS `purpose`. It was LAST on this form from
    // 2026-08-15 to 2026-09-13 — after `memo`, at the foot of the dialog.
    // ⛔ `Clearing date` is drawn and NOT built since `DEF-PAY-10750`
    // (2026-10-30): CR-186-BRC10 gives the clearing date to the bank
    // reconciliation alone, a signed rule the drawing predates.
    expect(fieldOrder()).toEqual([
      "amount",
      "purpose",
      "posted_at",
      "method",
      "confirmation",
      "apply_to",
      "memo",
    ]);
  });

  it("the drawn helper is attached to `Reference or cheque number`", () => {
    open();
    // Drawn verbatim on both frames. It says whose number this is, which is
    // what stops a clerk typing one of OUR references into it.
    expect(helperOf("confirmation")).toBe("Whatever the customer can quote back.");
    expect(t("customers.account.payment.confirmationHelp")).toBe(
      "Whatever the customer can quote back.",
    );
  });

  it("the drawn helper is attached to `Memo`", () => {
    open();
    expect(helperOf("memo")).toBe(
      "Kept with the payment and read by anyone asking why later.",
    );
  });

  it("still shows and pre-fills money to TWO decimals (hard rule 2)", () => {
    // Carried here as well as in `AccountActions.test.tsx` because this file
    // MOVED a field in this form, and the cheapest way for a reorder to break
    // something is to break the thing that was fixed last.
    open("2410.000000");
    expect(screen.getByLabelText(/Amount/)).toHaveValue("2410.00");
    expect(document.body.textContent).toContain("$2,410.00");
    expect(document.body.textContent).not.toContain("2410.000000");
  });

  // RED PROVED FIRST (2026-10-30, `DEF-PAY-10750`): against the tip's
  // AccountActions.tsx `#cleared_at` was drawn, asking for a date the server
  // never stores.
  it("asks no clearing date and sends none (CR-186-BRC10)", async () => {
    const client = silentClient();
    mount(
      <RecordPaymentModal
        accountId={ACCOUNT}
        accountLabel="Bramble Bakery"
        currency="USD"
        balance="2410.000000"
        today="2026-09-13"
        dateFormat="MM/DD/YYYY"
        client={client}
        onClose={() => undefined}
        onRecorded={() => undefined}
      />,
    );
    expect(document.querySelector("#cleared_at")).toBeNull();
    expect(document.body.textContent).not.toContain(t("payments.form.clearedAt"));
    fireEvent.click(screen.getByRole("button", { name: t("payments.form.submit") }));
    const post = client.post as unknown as ReturnType<typeof vi.fn>;
    await waitFor(() => expect(post).toHaveBeenCalled());
    const body = (post.mock.calls[0] as unknown as [string, Record<string, unknown>])[1];
    expect(body.posted_at).toBe("2026-09-13");
    expect(body.cleared_at).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-5167 — Adjust asks for the one field its endpoint refuses to do without", () => {
  function open() {
    return mount(
      <AdjustModal
        accountId={ACCOUNT}
        accountLabel="Bramble Bakery"
        currency="USD"
        today="2026-09-13"
        dateFormat="MM/DD/YYYY"
        client={silentClient()}
        onClose={() => undefined}
        onRecorded={() => undefined}
      />,
    );
  }

  it("marks Reason required, because the server refuses an adjustment without one", () => {
    open();
    // `payments.services._reason_code`: *"REQUIRED on a credit or an
    // adjustment, because the reason is what makes 'how much did we give away
    // last year, and why' a question with an answer, and because it is what
    // chooses the GL account"*. Every row THIS form writes is an adjustment.
    const reason = screen.getByLabelText(/Reason/);
    expect(reason.closest(".field")?.querySelector(".field-required")).not.toBeNull();
  });

  it("refuses to post with no reason, instead of letting the server say it", () => {
    open();
    fireEvent.change(screen.getByLabelText(/Amount/), { target: { value: "25.00" } });
    fireEvent.click(screen.getByRole("button", { name: t("customers.account.adjust.submit") }));
    // The form stays open and the message is the one a clerk can act on.
    expect(screen.getByText("Choose a reason. An adjustment always carries one.")).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-5166 — Add note attaches its helper to the field the blueprint draws it under", () => {
  function open() {
    return mount(
      <AddNoteModal
        accountId={ACCOUNT}
        accountLabel="Bramble Bakery"
        client={silentClient()}
        onClose={() => undefined}
        onSaved={() => undefined}
      />,
    );
  }

  it("the title-or-body rule sits under `Title`, where `ACC-A15` draws it", () => {
    open();
    expect(helperOf("title")).toBe("Fill in a title, a note, or both.");
  });

  it("and NOT under `Note`, which is where it rendered until 2026-09-13", () => {
    // The negative is the half that cannot rot into a tautology: a later lane
    // that adds the sentence back under the body, or to both, fails here.
    open();
    expect(helperOf("body")).toBe("");
  });

  it("draws the four rows `ACC-A15` draws, in its order", () => {
    open();
    expect(fieldOrder()).toEqual(["title", "body", "pinned", "customer_visible"]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 lane C · blueprint 02-account-detail.md ACC-A06 / ACC-A15 · 16-service-requests-list.md ACC-Q06 · 14-ui-conventions.md rules 38, 39, 41
// generated: 2026-09-13 by the CR-094 lane C build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — every case in this file run against the pre-fix tip in a detached `git worktree`, output quoted in the lane's conformance file · tsc --noEmit✔ (the LOCAL binary, itself proved able to fail) · vitest✔
// exceptions: E3 no pixel is asserted — jsdom computes no layout, so B14 rule 39's figures are unverifiable here and are said to be rather than implied · E3 the field ORDER asserted is the blueprint's and differs from `S35`'s by one field (`purpose`); B14 rule 41 settles it for this screen and the disagreement is recorded in DEF-CUS-5164 rather than reconciled by this lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
