// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.9` · `P3.10` · `P3.11` — screen 2·2 becomes a
//           PAGE, the row panel goes, the 👁 appears, and the three modals open.
// Screens:  2·2 (`S33`) · 2·3c · 2·3d · 2·3h
// Rules:    B14 rule 6 (danger tier on the destructive commit) · rule 9 (chips)
//           · rule 11 (a consequence preview) · rule 15 (max TWO visible row
//           icons) · rule 31 (no database id is a visible value) · rule 33
//           (RATIONALE is ZERO WORDS ON SCREEN) · BR-SHL-025 (a refused control
//           says WHY) · CLAUDE.md hard-won law 2 (both directions)
// ───────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════
// ⚠ EVERY CASE MOUNTS UNDER THE REAL PATH PATTERN
// ══════════════════════════════════════════════════════════════════════════
// A bare `MemoryRouter` with no `/:tenant/...` route leaves `useParams().tenant`
// undefined, so every address the screen builds comes out `//payments/…` — **a
// protocol-relative URL to another host, which reads as a perfectly good string
// to `toContain`**. That is how eight dead doors hid on the customer portal
// (CLAUDE.md law 2), and it is why `renderAt` below declares the tenant segment.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ AND THE REFUSALS ARE DRIVEN, NOT ASSERTED FROM A PROP
// ══════════════════════════════════════════════════════════════════════════
// The Cancel button's disabled state comes off the SERVER's `actions.cancel`,
// so the fixture serves both answers and the test reads the rendered control.
// Asserting the prop would have been green on the broken day.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { PaymentDetail, PaymentHistoryPage } from "@/api/paymentDetailEndpoints";
import { ToastProvider } from "@/components/Toast";

import {
  PaymentDetailPage,
  PaymentsSegmentRoute,
  segmentIsPaymentRef,
} from "./PaymentDetailPage";
import { paymentsTableConfig, paymentsCells } from "./PaymentsPage";
import { PAYMENTS_TABS } from "./paymentsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

const t: Translator = (key, params) => i18n.t(key, params);

afterEach(() => cleanup());

function detail(over: Partial<PaymentDetail> = {}): PaymentDetail {
  return {
    id: "8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11",
    payment_no: "PMT-2609-000418",
    account_id: "1c383cd3-0b7c-4b7e-9c94-1d38f8f2e4aa",
    account_no: "AC-2026-00001",
    customer_name: "Ana Alvarez",
    type: "payment",
    method: "check",
    method_name: "Cheque",
    confirmation: "4471",
    memo: null,
    amount: "158.100000",
    currency: "USD",
    status: "processing",
    purpose: "bill",
    posted_at: "2026-09-21",
    cleared_at: null,
    applied_to: [],
    origin: "entry",
    batch_ref: "DEP-260921-CHK",
    source: {
      origin: "entry",
      origin_is_derived: false,
      taken_by: null,
      counter_session_ref: null,
    },
    reconciled: null,
    actions: {
      edit: { allowed: true, reason: null, tender_locked: false },
      correction: { allowed: true, reason: null },
      cancel: { allowed: true, reason: null },
      receipt: { allowed: true, reason: null },
    },
    receipts: [],
    next_copy_no: 2,
    unavailable: ["history_is_pruned_like_every_audit_row"],
    ...over,
  } as unknown as PaymentDetail;
}

const HISTORY: PaymentHistoryPage = {
  results: [
    {
      at: "2026-09-21T11:42:00Z",
      what: "payment.recorded",
      who: { kind: "user", name: "Dana Whitfield" },
      note: "Cheque · First National",
    },
  ],
  count: 1,
  next: null,
  previous: null,
};

function clientFor(row: PaymentDetail, history: PaymentHistoryPage = HISTORY): ApiClient {
  return {
    get: vi.fn(async (path: string) => {
      if (path.includes("/history")) {
        return { status: 200, data: history, headers: new Headers() };
      }
      if (path.startsWith("/payments/")) {
        return { status: 200, data: row, headers: new Headers() };
      }
      return { status: 200, data: { results: [], methods: [] }, headers: new Headers() };
    }),
    post: vi.fn(async () => ({ status: 201, data: {}, headers: new Headers() })),
  } as unknown as ApiClient;
}

/** ⚠ THE REAL PATH PATTERN, INCLUDING `:tenant` — see this file's header. */
function renderAt(row: PaymentDetail, history: PaymentHistoryPage = HISTORY) {
  const client = clientFor(row, history);
  const result = render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend/payments/${row.payment_no}`]}>
          <Routes>
            <Route
              path="/:tenant/payments/:paymentRef"
              element={<PaymentDetailPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...result, client };
}

describe("P3.9 — a payment has a home", () => {
  it("opens at its own address and titles itself with the NUMBER, not the id", async () => {
    const row = detail();
    renderAt(row);
    expect(await screen.findByRole("heading", { name: "PMT-2609-000418" })).toBeInTheDocument();
    // B14 rule 31 — the uuid is in the data and never on the screen.
    expect(document.body.textContent).not.toContain(row.id);
  });

  it("reads the payment by its NUMBER, which is what the address carries", async () => {
    const { client } = renderAt(detail());
    await waitFor(() => {
      // ⚠ ONE argument: `getPaymentDetail` passes no options. Asserting
      // `expect.anything()` for a second one is a check that cannot pass.
      expect(client.get).toHaveBeenCalledWith("/payments/PMT-2609-000418");
    });
  });

  it("draws the header strip — the drawing's four cells", async () => {
    renderAt(detail());
    const strip = await screen.findByTestId("payment-header-strip");
    expect(strip.textContent).toContain(t("payments.detail.source"));
    expect(strip.textContent).toContain(t("payments.col.batch"));
    expect(strip.textContent).toContain(t("payments.detail.reconciled"));
    expect(strip.textContent).toContain(t("payments.col.status"));
    // ⑤ the STORED word translated, never the drawn one matched on.
    expect(strip.textContent).toContain(t("payments.source.entry"));
    expect(strip.textContent).toContain("DEP-260921-CHK");
  });

  it("states ⑥ RECONCILED's absence rather than inventing the drawn BRM- series", async () => {
    renderAt(detail());
    const strip = await screen.findByTestId("payment-header-strip");
    expect(strip.textContent).toContain(t("payments.detail.notReconciled"));
    // ⚠ B14 rule 37 — the drawn figure is an ILLUSTRATION. This product mints
    // no `BRM-` series (`OQ-PAY-12602`), so it must never appear.
    expect(strip.textContent).not.toContain("BRM-");
  });

  it("keeps all eleven facts and the two-column bill table", async () => {
    renderAt(detail());
    await screen.findByRole("heading", { name: "PMT-2609-000418" });
    const body = document.body.textContent ?? "";
    for (const label of [
      "payments.col.account",
      "payments.col.customer",
      "payments.col.amount",
      "payments.col.status",
      "payments.col.type",
      "payments.col.purpose",
      "payments.col.method",
      "payments.col.confirmation",
      "payments.col.postedAt",
      "payments.col.clearedAt",
      "payments.form.memo",
    ]) {
      expect(body).toContain(t(label));
    }
    expect(body).toContain(t("payments.detail.billCol"));
    expect(body).toContain(t("payments.detail.appliedCol"));
  });

  it("a null clearing date says NOT CLEARED YET, never the absent-field dash", async () => {
    renderAt(detail({ cleared_at: null }));
    await screen.findByRole("heading", { name: "PMT-2609-000418" });
    // p036's *States* row: `processing` is a STATE, not a missing value.
    expect(document.body.textContent).toContain(t("payments.row.notCleared"));
  });

  it("draws ⑦ the history, with the audit CODE translated and the actor's NAME", async () => {
    renderAt(detail());
    const history = await screen.findByTestId("payment-history");
    expect(history.textContent).toContain(t("payments.audit.payment.recorded"));
    expect(history.textContent).toContain("Dana Whitfield");
    // B14 rule 35 — the raw code never reaches a clerk.
    expect(history.textContent).not.toContain("payment.recorded");
  });

  it("tells a broken history read apart from an empty one", async () => {
    renderAt(detail(), { results: [], count: 0, next: null, previous: null });
    await screen.findByRole("heading", { name: "PMT-2609-000418" });
    expect(document.body.textContent).toContain(t("payments.detail.historyEmpty"));
    expect(document.body.textContent).not.toContain(t("payments.detail.historyUnreadable"));
  });
});

describe("P3.18 / B14 rule 33 — the page never explains the retention policy", () => {
  it("says nothing about how long the history survives, and claims no permanence", async () => {
    // ⚠ The server SERVES `history_is_pruned_like_every_audit_row` on
    // `unavailable[]` and the fixture above includes it. **It is a machine fact
    // and must never become a sentence** — rule 33 puts rationale at ZERO words
    // on screen, and `P3.18` deleted exactly such a disclosure from the Edit
    // path on the same day. This case is what stops it coming back.
    renderAt(detail());
    await screen.findByRole("heading", { name: "PMT-2609-000418" });
    const body = (document.body.textContent ?? "").toLowerCase();
    for (const word of ["retention", "audit trail", "pruned", "for ever", "forever", "permanent"]) {
      expect(body).not.toContain(word);
    }
    // And the CODE itself is never printed (B14 rule 31).
    expect(document.body.textContent).not.toContain("history_is_pruned_like_every_audit_row");
  });
});

describe("P3.11 — the four header controls, and none of them is dead", () => {
  it("opens Cancel, and its commit carries the DANGER tier (B14 rule 6)", async () => {
    renderAt(detail());
    fireEvent.click(await screen.findByRole("button", { name: t("payments.cancel.action") }));
    const commit = await screen.findByRole("button", { name: t("payments.cancel.submit") });
    // ⚠ THE RENDERED CLASS, not the prop — a prop assertion would have been
    // green on the day `submitVariant` reached no payments modal at all.
    expect(commit.getAttribute("class")).toContain("border-danger-500");
    expect(commit.getAttribute("class")).toContain("text-danger-700");
  });

  it("Cancel states its CONSEQUENCE in the customer's terms (B14 rule 11)", async () => {
    renderAt(detail());
    fireEvent.click(await screen.findByRole("button", { name: t("payments.cancel.action") }));
    const box = await waitFor(() => {
      const found = document.querySelector('[data-consequence="cancel"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(box.textContent).toContain("Ana Alvarez");
    expect(box.textContent).toContain("$158.10");
  });

  it("a cleared payment refuses Cancel and the refusal names a refund or credit (CR-186-BRC10)", async () => {
    renderAt(
      detail({
        status: "cleared",
        cleared_at: "2026-09-21",
        actions: {
          edit: { allowed: true, reason: null, tender_locked: false },
          correction: { allowed: true, reason: null },
          cancel: { allowed: false, reason: "cancel_refused_cleared_use_reverse" },
          receipt: { allowed: true, reason: null },
        },
      } as Partial<PaymentDetail>),
    );
    const refusal = await screen.findByTestId("cancel-refusal");
    // ⚠ **IT MUST NAME THE RIGHT DOOR.** That clerk is not stuck, they are on
    // the wrong door, and a bare *"cannot be cancelled"* leaves them there.
    // CR-186-BRC10 (PO 2026-10-21): *"cleared payment cannot be cancled ; in
    // those cases refunds or credits will be issued"*. The door is a refund or
    // a credit now, no longer Reverse.
    expect(refusal.textContent).toBe(
      t("payments.cancel.refused.cancel_refused_cleared_use_reverse"),
    );
    // ⛔ `DEF-PAY-10733` (L3-01) — was `toBeDisabled()`. Cleared is final, so
    // the button is not drawn at all; the refusal above still names the door.
    expect(screen.queryByRole("button", { name: t("payments.cancel.action") })).toBeNull();
  });

  it("opens + Correction, and it says it changes nothing (the module's most misread rule)", async () => {
    renderAt(detail());
    fireEvent.click(
      await screen.findByRole("button", { name: t("payments.correction.action") }),
    );
    const box = await waitFor(() => {
      const found = document.querySelector('[data-consequence="correction-not-changed"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(box.textContent).toContain("PMT-2609-000418");
  });

  it("the correction commit is NOT danger — it creates a row and destroys nothing", async () => {
    renderAt(detail());
    fireEvent.click(
      await screen.findByRole("button", { name: t("payments.correction.action") }),
    );
    const commit = await screen.findByRole("button", { name: t("payments.correction.submit") });
    // The CONTROL for the Cancel case above: without it, that assertion would
    // pass on a build that reddened every commit in the product.
    expect(commit.getAttribute("class")).not.toContain("border-danger-500");
  });

  it("opens Resend as CHIPS (B14 rule 9), never a wall of checkboxes", async () => {
    renderAt(detail({ receipts: [{ channel: "email", copy_no: 1, sent_at: "2026-09-21T11:42:00Z" }] } as Partial<PaymentDetail>));
    fireEvent.click(await screen.findByRole("button", { name: t("payments.resend.action") }));
    await screen.findByRole("button", { name: t("payments.resend.submit") });
    expect(document.querySelectorAll('input[type="checkbox"]').length).toBe(0);
    expect(document.body.textContent).toContain(t("payments.resend.channels"));
  });

  it("Resend sends the copy number the SERVER showed, never one it computed", async () => {
    // ⚠ **THE RECEIPT ROW IS LOAD-BEARING IN THIS FIXTURE.** With none, the
    // modal opens with no channel selected and its own schema refuses the
    // submit — correct behaviour, and it made the first draft of this case fail
    // for a reason that had nothing to do with `copy_no`.
    const row = detail({
      next_copy_no: 7,
      receipts: [{ channel: "email", copy_no: 6, sent_at: "2026-09-21T11:42:00Z" }],
    } as Partial<PaymentDetail>);
    const { client } = renderAt(row);
    fireEvent.click(await screen.findByRole("button", { name: t("payments.resend.action") }));
    fireEvent.click(await screen.findByRole("button", { name: t("payments.resend.submit") }));
    await waitFor(() => {
      expect(client.post).toHaveBeenCalledWith(
        "/payments/PMT-2609-000418/receipt",
        expect.objectContaining({ copy_no: 7 }),
      );
    });
    // ⚠ **HARD RULE 6.** A `+ 1` here would post a second receipt on every
    // double-click while looking perfectly correct. `8` is what that bug prints.
    const body = (client.post as unknown as { mock: { calls: unknown[][] } }).mock.calls[0][1];
    expect((body as { copy_no: number }).copy_no).not.toBe(8);
  });
});

describe("P3.10 — the swap cannot half-land", () => {
  it("the row panel is GONE: the payments table declares no expander", () => {
    // ⚠ **THE PANEL AND THE PAGE ARE ONE COMMIT.** *"Not before"* — removing it
    // first takes away the only way to see what a payment paid off. *"Not
    // later"* — leaving both gives the product two answers to one question.
    const cells = paymentsCells(t, (path) => `/brazosbend${path}`, "UTC", "MM/DD/YYYY");
    expect(paymentsTableConfig(t, cells).renderExpanded).toBeUndefined();
  });

  it("the 👁 appears, and it is a LINK to the page's own address", () => {
    const cells = paymentsCells(t, (path) => `/brazosbend${path}`, "UTC", "MM/DD/YYYY");
    expect(cells.detailTo({ payment_no: "PMT-2609-000418", id: "x" } as never)).toBe(
      "/brazosbend/payments/PMT-2609-000418",
    );
    // ⚠ NOT `//payments/…` — a protocol-relative URL to another host is what a
    // missing tenant segment produces, and `toContain` reads it as fine.
    expect(
      cells.detailTo({ payment_no: "PMT-2609-000418", id: "x" } as never).startsWith("//"),
    ).toBe(false);
  });

  it("B14 rule 15: the ACTIONS column shows at most TWO icons plus the overflow", () => {
    // Adding the 👁 without moving Reverse into the `…` would have made three,
    // and `G37` counts these into a variable it never compares to the cap — so
    // nothing else in this repository would have said so.
    const cells = paymentsCells(t, (path) => `/brazosbend${path}`, "UTC", "MM/DD/YYYY");
    const config = paymentsTableConfig(
      t,
      cells,
      { onReverse: () => undefined, reasonFor: () => null },
      { onCorrect: () => undefined },
      { move: { onMove: () => undefined }, reapply: { onReapply: () => undefined } },
    );
    const actions = config.columns.find((column) => column.key === "actions");
    expect(actions).toBeDefined();
    const { container } = render(
      <MemoryRouter initialEntries={["/brazosbend/payments"]}>
        <Routes>
          <Route
            path="/:tenant/payments"
            // ⚠ A WHOLE ROW, NOT A STUB: `correctionBlockedReason` reads
            // `row.amount.trim()`, so a two-field fixture throws inside the
            // cell and the case fails for the wrong reason.
            element={<>{actions?.cell?.(detail() as never)}</>}
          />
        </Routes>
      </MemoryRouter>,
    );
    // Two visible controls (the 👁 link and the ✎ button) and the `…` trigger.
    const visible = container.querySelectorAll(":scope > * > a, :scope > * > button");
    expect(visible.length).toBeLessThanOrEqual(3);
  });
});

describe("the address does not collide with the seven tabs", () => {
  it("a tab segment is a tab, and a payment segment is a payment", () => {
    // ⚠ **THE SILENT FAILURE THIS GUARDS.** `paymentsTabFrom` answers an
    // unknown segment with `summary` and never 404s — correct for a typo, and
    // for a payment reference it means a clerk who pastes a link lands on the
    // SUMMARY TAB with nothing on screen saying they are in the wrong place.
    expect(segmentIsPaymentRef("summary")).toBe(false);
    expect(segmentIsPaymentRef("record")).toBe(false);
    expect(segmentIsPaymentRef("counter")).toBe(false);
    expect(segmentIsPaymentRef("collections")).toBe(false);
    expect(segmentIsPaymentRef("PMT-2609-000418")).toBe(true);
    expect(segmentIsPaymentRef("8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11")).toBe(true);
    // And a mistyped tab keeps today's fallback rather than 404ing on a route
    // this lane invented.
    expect(segmentIsPaymentRef("sumary")).toBe(false);
  });
});

describe("DEF-PAY-6316 — the guard accepts what the PRODUCT mints, not what the blueprint DRAWS", () => {
  /**
   * ⚠ **THE PATTERN WAS BUILT FROM A NUMBER DRAWN IN A WIREFRAME, WHICH B14
   * RULE 37 FORBIDS IN TERMS** — *"a figure drawn in a wireframe is an
   * ILLUSTRATION, never a fact to build to"*. p036 draws `PMT-2609-000418`
   * (cited at `06-backend/apps/payments/cancel.py:102`) and the old
   * `PAYMENT_REF_RE` accepted `PMT-` **and nothing else**. The product mints
   * from `core/numbering.py`'s `SERIES_CATALOG[PAYMENT]`, whose seeded default
   * is `PY-{YY}{MM}{DD}-{0000}`, so EVERY real payment address was rejected and
   * every clerk landed on the Summary tab.
   *
   * **These five strings are not samples typed from a screenshot.** They are
   * `numbering.render(f, 69, date(2026, 9, 21))` for each of the five formats
   * `SERIES_CATALOG[PAYMENT]` offers, run against the kernel itself. The first
   * is byte-for-byte the number on the Product Owner's screenshot.
   *
   * ⚠ **THE FIFTH IS WHY THIS IS NOT A PREFIX LIST.** `{00000000}` is in the
   * catalog, CR-005 calls a plain counter mandatory, and it renders a BARE
   * NUMBER with no prefix at all — so `(PY|PAY|P|PMT)-` would be the same
   * defect one tenant away. `validate_format` takes any literal text around one
   * sequence token, so the only thing a minted number is GUARANTEED to have is
   * a digit, and that is what the guard now tests for.
   */
  const MINTED = [
    "PY-260921-0069", // PY-{YY}{MM}{DD}-{0000} — the seeded default
    "PAY-2026-00069", // PAY-{YYYY}-{00000}
    "P-000069", // P-{000000}
    "PMT-26-00069", // PMT-{YY}-{00000}
    "00000069", // {00000000} — no prefix at all
  ];

  it.each(MINTED)("%s is a payment reference", (minted) => {
    expect(segmentIsPaymentRef(minted)).toBe(true);
  });

  it("the three references on the Product Owner's own screen open the detail", () => {
    expect(segmentIsPaymentRef("PY-260921-0069")).toBe(true);
    expect(segmentIsPaymentRef("PY-260919-0067")).toBe(true);
    expect(segmentIsPaymentRef("PY-260809-0063")).toBe(true);
  });

  it("every known tab is still a TAB and not a payment reference", () => {
    // The whole point of the function: these must keep rendering `PaymentsPage`
    // byte for byte as before. `collections` is answered deliberately by
    // `paymentsTabFrom`; `debtors` is a three-segment route whose bare first
    // segment still arrives here.
    for (const tab of PAYMENTS_TABS) {
      expect(segmentIsPaymentRef(tab.id)).toBe(false);
    }
    expect(segmentIsPaymentRef("collections")).toBe(false);
    expect(segmentIsPaymentRef("debtors")).toBe(false);
    // And a mistyped tab keeps today's deliberate fallback to Summary rather
    // than a 404 this lane invented.
    expect(segmentIsPaymentRef("sumary")).toBe(false);
    expect(segmentIsPaymentRef("")).toBe(false);
    expect(segmentIsPaymentRef(undefined)).toBe(false);
  });

  it("the uuid branch still resolves — a link built before the rule existed", () => {
    // Kept explicitly and NOT folded into the digit test: a uuid may legally
    // carry no digit at all.
    expect(segmentIsPaymentRef("8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11")).toBe(true);
    expect(segmentIsPaymentRef("abcdefab-abcd-abcd-abcd-abcdefabcdef")).toBe(true);
  });
});

describe("DEF-PAY-6316 end to end — a PY- address opens the page, and the two controls are on it", () => {
  /**
   * ⚠ **MOUNTED AT `payments/:tab`, WHICH IS THE PATTERN `App.tsx` ACTUALLY
   * USES.** A fixture that declares `:paymentRef` is testing its own fixture —
   * it was green all through `DEF-PAY-6316` — so this walks the real thing:
   * `PaymentsSegmentRoute` → `segmentIsPaymentRef` → `PaymentDetailPage`.
   *
   * **The two controls are asserted here and not only on the page's own tests**
   * because the Product Owner reported them as *"Add Correction is missing"*
   * and *"Cancel Payment is missing"* — consequences of the screen never
   * opening, not faults of their own. This case is what proves that is all
   * they were.
   */
  it("PY-260921-0069 draws the detail page with + Correction and Cancel", async () => {
    const row = detail({ payment_no: "PY-260921-0069" } as Partial<PaymentDetail>);
    const client = clientFor(row);
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/payments/PY-260921-0069"]}>
            <Routes>
              <Route
                path="/:tenant/payments/:tab"
                element={<PaymentsSegmentRoute client={client} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    // The page, titled with the NUMBER (B14 rule 31) — not the Summary tab.
    expect(
      await screen.findByRole("heading", { name: "PY-260921-0069" }),
    ).toBeInTheDocument();
    // And it read the payment by the number the address carries.
    expect(client.get).toHaveBeenCalledWith("/payments/PY-260921-0069");
    // ③ and ④ — the two the Product Owner reported as missing.
    expect(screen.getByRole("button", { name: t("payments.correction.action") })).toBeEnabled();
    expect(screen.getByRole("button", { name: t("payments.cancel.action") })).toBeEnabled();
  });
});
