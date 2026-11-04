// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-34 · task 42 — S35's Correct-reference modal and the
//           corrected-value panel. Its backend half is task 41
//           (`POST /payments/{id}/correct-reference`), complete 2026-09-02.
// Story:    US-PAY-001 (the payment row) · CS-34 "correct what is not money"
// Screens:  S33 (the row action) · S35 (the modal) · S21 (the account Payments
//           tab, which gets the action from the SAME table config)
// Rules:    CLAUDE.md hard rule 4, NARROWED 2026-09-02 for `confirmation`,
//           `memo` and `method_id` and for nothing else (PO verbatim: *"(a)
//           Allow those fields to change"*, `OQ-1322` closed) · hard rule 7
//           (the correction writes an audit row) · BR-PAY-002 · BR-PAY-025
//           (the tender is refused once the payment is banked) · BR-PAY-026
//           (the tender vocabulary is the tenant's live list) · BR-SHL-020 r2
//           (server detail text never reaches a screen — the catalogue sentence
//           is the whole of what a clerk reads) · BR-SHL-025 (server-side
//           enforcement is THE enforcement) · B14 rule 15 (row actions are
//           ICONS) · B14 rule 21 (this directory is NOT on route-b-migrated.txt,
//           so no Tailwind utility may be written here) · B14 rule 31 (no
//           database id is the visible value of a field) · B14 rule 32 (a
//           stated absence is a `<details>` CLOSED by default)
// Defects:  DEF-3203 (the refusal key resolved to nothing, so every refusal on
//           this path rendered as SILENCE) · DEF-3206 (the door takes a tender
//           id and no read served one, so the tender third of the ruling was
//           unreachable from a screen)
// Questions: OQ-1340 — is a correction's audit row exempt from retention
//           pruning? OPEN. Nothing here may call this path a permanent record
//           of the previous value, and the disclosure below is what says so.
// ───────────────────────────────────────────────────────
// §3 test data is PE-1's own row: cheque **8842** for **292.87** on `ACC-1042`.
// The clerk keyed it as 8842 and the bank line reads **8482**, which is the
// whole reason this screen exists — an unmatched line is a reconciliation
// nobody can finish.
//
// ⚠ **THE ASSERTIONS THAT MATTER MOST ARE THE NEGATIVE ONES.** This screen must
// not send a field the clerk did not touch, must not describe the audit trail
// as permanent, must not print a rule id or a server code at a clerk, and must
// not leave the retention sentence OPEN on the work surface.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { CorrectedReference, PaymentMethodOption, PaymentRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  CorrectReferenceModal,
  CorrectedReferencePanel,
  // ⚠ `CorrectionRetentionNote` WAS IMPORTED HERE AND IS DELETED (`P3.18`,
  // 2026-09-23). It put the retention policy on screen; `OQ-1340` closed, and
  // B14 rule 33 puts rationale at ZERO words on screen — so the honest build is
  // silence rather than a corrected disclaimer. The `P3.18` block below proves
  // the absence on both surfaces, in both directions.
  correctReferenceChanges,
  correctReferenceSchema,
  paymentsCells,
  paymentsTableConfig,
} from "./PaymentsPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

const METHODS: PaymentMethodOption[] = [
  { id: "met-check", code: "check", name: "Check" },
  { id: "met-ach", code: "ach", name: "ACH" },
];

/** PE-1's cheque, as `GET /payments` serves it. */
function payment(over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "pay-8842",
    payment_no: "PMT-000241",
    account_id: "acc-1042",
    account_no: "ACC-1042",
    customer_name: "Ridge Coffee Co.",
    type: "payment",
    method: "check",
    method_name: "Check",
    confirmation: "8842",
    memo: null,
    amount: "292.870000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-07-14",
    cleared_at: "2026-07-16",
    applied_to: [],
    applied_total: "0.000000",
    deposit_batch_id: null,
    receipt_no: null,
    // CR-059 CS-30 · CS-32 — a cheque's own state and the move marks.
    // Null on an ordinary payment, which is a STATE and not a missing value.
    cheque_date: null,
    drawer_bank: null,
    bankable_from: null,
    moved_from_payment_no: null,
    moved_from_account_no: null,
    moved_to_payment_no: null,
    moved_to_account_no: null,
    // `CR-135` `P1.9` — the blueprint's §03 2·1 Source and Batch.
    origin: "entry",
    batch_ref: null,
    batch_kind: null,
    ...over,
  };
}

/** What `amendments.amend_reference` answers with, shape for shape. */
function corrected(over: Partial<CorrectedReference> = {}): CorrectedReference {
  return {
    payment_id: "pay-8842",
    payment_no: "PMT-000241",
    corrected: { confirmation: "8482" },
    previous: { confirmation: "8842" },
    note: "keyed from the wrong line of the deposit slip",
    unavailable: [
      {
        code: "amendment_history_retention_unruled",
        br_ref: "OQ-1340 · CS-34",
        detail: "the value this correction replaced is now recorded in the audit trail and nowhere else",
      },
    ],
    ...over,
  };
}

describe("CS-34 · only what the clerk actually changed is sent", () => {
  const CURRENT_TENDER = "met-check";

  it("an untouched form sends NOTHING — a correction from a value to itself is not a correction", () => {
    // It would still write an audit row, and the audit trail is the only place
    // the previous value survives at all. Filling it with noise is not cosmetic.
    expect(
      correctReferenceChanges(
        payment(),
        { reference: "8842", memo: "", tenderId: CURRENT_TENDER },
        CURRENT_TENDER,
      ),
    ).toEqual({});
  });

  it("the mistyped cheque number goes on its own, and the tender does not ride along", () => {
    expect(
      correctReferenceChanges(
        payment(),
        { reference: "8482", memo: "", tenderId: CURRENT_TENDER },
        CURRENT_TENDER,
      ),
    ).toEqual({ reference: "8482" });
  });

  it("CLEARING a reference is a real correction and is NOT collapsed into 'untouched'", () => {
    // A clerk who typed a reference onto a cash payment by mistake must be able
    // to take it off. `""` and "the clerk did not touch this" are different
    // facts and only one of them may be omitted from the body.
    expect(
      correctReferenceChanges(
        payment(),
        { reference: "", memo: "", tenderId: CURRENT_TENDER },
        CURRENT_TENDER,
      ),
    ).toEqual({ reference: "" });
  });

  it("a payment with no memo yet: typing one is a change, leaving it blank is not", () => {
    expect(
      correctReferenceChanges(
        payment({ memo: null }),
        { reference: "8842", memo: "counter deposit", tenderId: CURRENT_TENDER },
        CURRENT_TENDER,
      ),
    ).toEqual({ memo: "counter deposit" });
    expect(
      correctReferenceChanges(
        payment({ memo: null }),
        { reference: "8842", memo: "", tenderId: CURRENT_TENDER },
        CURRENT_TENDER,
      ),
    ).toEqual({});
  });

  it("DEF-3206: the tender is sent as the row's ID, which the list now serves", () => {
    // The row carries the CODE (`check`); the door resolves the primary key.
    // Until `active_payment_methods()` served one, this branch could not exist.
    expect(
      correctReferenceChanges(
        payment(),
        { reference: "8842", memo: "", tenderId: "met-ach" },
        CURRENT_TENDER,
      ),
    ).toEqual({ tender_id: "met-ach" });
  });

  it("all three at once, and the note is never one of them", () => {
    const changes = correctReferenceChanges(
      payment(),
      { reference: "8482", memo: "re-keyed", tenderId: "met-ach" },
      CURRENT_TENDER,
    );
    expect(changes).toEqual({ reference: "8482", memo: "re-keyed", tender_id: "met-ach" });
    expect(Object.keys(changes)).not.toContain("note");
  });
});

describe("CS-34 · the note is required, because the service requires it", () => {
  it("a blank note is refused HERE, in the same words, before the round trip", () => {
    const result = correctReferenceSchema(t).safeParse({ note: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe(t("payments.correct.noteRequired"));
    }
  });

  it("a reason is enough — nothing else on this form is validated client-side", () => {
    expect(correctReferenceSchema(t).safeParse({ note: "keyed wrong" }).success).toBe(true);
  });
});

/**
 * ⚠ **THE ACTIONS CELL CONTAINS A ROUTER `<Link>` SINCE `CR-137-BRC07` `P3.10`
 * AND MUST BE RENDERED UNDER A ROUTE.** The 👁 Detail action is a
 * `RowActionLink`, not a button: an address a clerk can middle-click, open in
 * a new tab and paste into a message is the whole point of screen 2·2, and an
 * `onClick` that calls `navigate` loses all three. Rendered bare it throws
 * *"Cannot destructure property 'basename'"*.
 *
 * ⚠ **THE PATTERN CARRIES `:tenant` ON PURPOSE.** A bare `MemoryRouter` with
 * no tenant segment leaves `useParams().tenant` undefined, so every address
 * the cell builds comes out `//payments/…` — a protocol-relative URL to
 * another host that reads as a perfectly good string to `toContain`
 * (CLAUDE.md hard-won law 2).
 */
function underRoute(node: React.ReactNode): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/acme/payments"]}>
      <Routes>
        <Route path="/:tenant/payments" element={<>{node}</>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CS-34 · the row action (B14 rule 15)", () => {
  const cells = paymentsCells(t, (p) => p, "UTC", "MM/DD/YYYY");

  it("the actions column exists when EITHER affordance is passed, and not otherwise", () => {
    expect(paymentsTableConfig(t, cells).columns.some((c) => c.key === "actions")).toBe(false);
    const correctOnly = paymentsTableConfig(t, cells, undefined, { onCorrect: () => undefined });
    expect(correctOnly.columns.some((c) => c.key === "actions")).toBe(true);
  });

  it("Correct is an ICON with an accessible name, and it is NEVER disabled", () => {
    // Every refusal this door makes is one the screen cannot see — the tender
    // rule turns on `deposit_batch_id`, which is documented as always null. A
    // client-side guard would offer the field exactly when it must not, so the
    // server's refusal is what a clerk reads (BR-SHL-025).
    const config = paymentsTableConfig(
      t,
      cells,
      { reasonFor: () => null, onReverse: () => undefined },
      { onCorrect: () => undefined },
    );
    const actions = config.columns.find((column) => column.key === "actions");
    if (actions?.cell === undefined) {
      throw new Error("the actions column is missing");
    }
    const html = underRoute(actions.cell(payment()));
    expect(html).toContain(`aria-label="${escaped(t("payments.correct.action"))}"`);
    expect(html).not.toContain('disabled=""');
    // ⚠ **REVERSE IS BEHIND THE `…` SINCE `CR-137-BRC07` `P3.10`** — p030 ⑥
    // draws the column as *"👁 Detail · ✎ Edit, then `…`"*, and B14 rule 15
    // caps the visible icons at two. **It is still in the cell**, which is what
    // this line has always been about: one column, every action reachable.
    expect(html.slice(html.indexOf("data-row-more"))).toContain(
      escaped(t("payments.reverse.action")),
    );
  });

  it("a Billing Clerk gets Correct even where Reverse is refused", () => {
    // The route takes AnyTenantRole — *"the clerk who records a payment"* — so
    // there is no role reason to compute and none is invented.
    const config = paymentsTableConfig(
      t,
      cells,
      { reasonFor: () => t("payments.reverse.adminOnly"), onReverse: () => undefined },
      { onCorrect: () => undefined },
    );
    const actions = config.columns.find((column) => column.key === "actions");
    const html = underRoute(actions?.cell?.(payment()));
    expect(html).toContain(escaped(t("payments.reverse.adminOnly")));
    expect(html).toContain(`aria-label="${escaped(t("payments.correct.action"))}"`);
  });
});

describe("CS-34 · the modal (S35)", () => {
  function modal(row: PaymentRow = payment()): string {
    return renderToStaticMarkup(
      <ToastProvider>
        <CorrectReferenceModal
          client={{} as never}
          payment={row}
          methods={METHODS}
          onClose={() => undefined}
          onCorrected={() => undefined}
        />
      </ToastProvider>,
    );
  }

  it("the three correctable fields are there, PRE-FILLED with what is on the row", () => {
    const html = modal();
    expect(html).toContain('id="reference"');
    expect(html).toContain('id="memo"');
    expect(html).toContain('id="tender_id"');
    expect(html).toContain('id="note"');
    // Pre-filled, so the clerk corrects what they can see rather than retyping
    // from memory — the failure mode this whole path exists to fix.
    expect(html).toContain('value="8842"');
  });

  it("NO money field is offered, in any form — the trigger refuses them by name", () => {
    const html = modal();
    for (const field of ["amount", "account_id", "posted_at", "cleared_at", "allocations"]) {
      expect(html).not.toContain(`id="${field}"`);
    }
  });

  it("the tender picker offers the tenant's live list and starts on the row's own", () => {
    const html = modal();
    expect(html).toContain('value="met-check"');
    expect(html).toContain("Check");
    expect(html).toContain("ACH");
    // B14 rule 31: the id is the option's VALUE and never the label a clerk
    // reads. The method NAME is what is on screen.
    expect(html).not.toContain(">met-check<");
  });

  it("DEF-PAY-10735 — a payment with NO method shows 'No method yet', never ACH", () => {
    // RED FIRST: the select had no empty option, so with state `""` the
    // browser drew the first method (`Check` here, `ACH` on the tester's
    // tenant) and a reference fix read as if the tender were already set.
    const html = modal(payment({ method: null, method_name: null } as Partial<PaymentRow>));
    expect(html).toContain(`<option value="" selected="">${escaped(t("payments.correct.noMethod"))}</option>`);
    // …and not on a row that HAS a method: there it would read as "remove it",
    // which this door cannot do.
    expect(modal()).not.toContain(escaped(t("payments.correct.noMethod")));
  });

  it("DEF-PAY-10735 — saving only the reference on a no-method payment sends no tender", () => {
    const row = payment({ method: null, method_name: null } as Partial<PaymentRow>);
    expect(correctReferenceChanges(row, { reference: "4471", memo: "", tenderId: "" }, "")).toEqual({
      reference: "4471",
    });
  });

  it("the tender rule is stated BEFORE it is hit, because the screen cannot check it", () => {
    expect(modal()).toContain(escaped(t("payments.correct.tenderHelp")));
  });
});

describe("P3.18 · OQ-1340 CLOSED — the screen says NOTHING about retention", () => {
  // ══════════════════════════════════════════════════════════════════════════
  // THIS BLOCK USED TO ASSERT THE OPPOSITE, AND THE INVERSION IS THE POINT
  // ══════════════════════════════════════════════════════════════════════════
  // It read `describe("CS-34 · OQ-1340 — the caveat this path owes a reader")`
  // and pinned a closed `<details>` on BOTH surfaces carrying
  // `payments.correct.retentionSummary` — *"The old value is not kept for
  // ever"* — and `retentionDetail`, whose last sentence was *"Whether these are
  // kept for longer has not been decided."*
  //
  // ⚠ **THE PO DECIDED IT ON 2026-09-23** (`OQ-1340`, option b, against the
  // recommendation): *"keep the same rule s; when audit log is delete - it is
  // deleted thats okay"*. So the sentence became false.
  //
  // ⚠ **AND CORRECTING THE SENTENCE WOULD STILL HAVE BEEN WRONG.** B14 rule 33
  // puts RATIONALE — why the product works this way — at **ZERO WORDS ON
  // SCREEN**, and its own amendment says rationale is REMOVED rather than
  // SHORTENED. A retention policy is rationale in its purest form, so a screen
  // that explains it in order to be honest breaks rule 33 while trying to obey
  // the ruling. **The honest build is silence: never claim permanence, and do
  // not explain why.**
  //
  // So these cases now prove the ABSENCE, in both directions — the words are
  // gone from the screen AND the keys are gone from the catalogue — because an
  // absence is invisible to every other check in this repository
  // (`DEF-CUS-3653`).
  const surfaces = () => {
    const form = renderToStaticMarkup(
      <ToastProvider>
        <CorrectReferenceModal
          client={{} as never}
          payment={payment()}
          methods={METHODS}
          onClose={() => undefined}
          onCorrected={() => undefined}
        />
      </ToastProvider>,
    );
    const result = renderToStaticMarkup(
      <CorrectedReferencePanel result={corrected()} onDismiss={() => undefined} />,
    );
    return { form, result };
  };

  it("neither surface explains the retention policy", () => {
    const { form, result } = surfaces();
    for (const html of [form, result]) {
      for (const word of ["retention", "audit trail", "not kept", "for ever", "forever"]) {
        expect(html.toLowerCase()).not.toContain(word.toLowerCase());
      }
    }
  });

  it("and neither one CLAIMS permanence, which is the ruling's own prohibition", () => {
    const { form, result } = surfaces();
    for (const html of [form, result]) {
      for (const word of ["permanent", "always available", "kept for ever"]) {
        expect(html.toLowerCase()).not.toContain(word.toLowerCase());
      }
    }
  });

  it("the two retired keys are gone from the catalogue, so neither can print", () => {
    // ⚠ A catalogue entry BEATS a `defaultValue`, so a key left behind with its
    // old sentence would still render if any call site came back. Retired
    // through `10-scripts/i18n_fanin.py` — never by hand (CLAUDE.md law 11).
    expect(i18n.exists("payments.correct.retentionSummary")).toBe(false);
    expect(i18n.exists("payments.correct.retentionDetail")).toBe(false);
  });

  it("B14 rule 31: no rule id and no server code reaches the clerk", () => {
    const { form, result } = surfaces();
    for (const html of [form, result]) {
      // These live on the wire and in the code comments beside the call sites.
      expect(html).not.toContain("OQ-1340");
      expect(html).not.toContain("amendment_history_is_not_a_permanent_record");
      expect(html).not.toContain("amendment_history_retention_unruled");
      expect(html).not.toContain("BR-PAY");
      expect(html).not.toContain("CS-34");
    }
  });

  it("the CONSEQUENCE box stays — what the write does is a fact, not rationale", () => {
    // Deleting the disclosure must not take rule 11's box with it. *What is
    // about to change* is something a clerk acts on; *how long the old value
    // survives* is not. That distinction is the whole of rule 33's zero clause.
    expect(surfaces().form).toContain(escaped(t("payments.correct.consequence.title")));
  });
});

describe("CS-34 · what the correction did", () => {
  it("the old value and the new one, side by side, against the payment NUMBER", () => {
    const html = renderToStaticMarkup(
      <CorrectedReferencePanel result={corrected()} onDismiss={() => undefined} />,
    );
    expect(html).toContain("PMT-000241");
    expect(html).toContain("8842");
    expect(html).toContain("8482");
    // B14 rule 31: the payment's id is on the response and is not on the screen.
    expect(html).not.toContain("pay-8842");
  });

  it("a field that was EMPTY before says so in a word, never as a blank", () => {
    // A blank reads as a failed load. "was empty" is a fact.
    const html = renderToStaticMarkup(
      <CorrectedReferencePanel
        result={corrected({ corrected: { memo: "counter deposit" }, previous: { memo: null } })}
        onDismiss={() => undefined}
      />,
    );
    expect(html).toContain(escaped(t("payments.correct.wasEmpty")));
    expect(html).toContain("counter deposit");
  });

  it("only the fields that moved are listed — a one-field correction lists one", () => {
    const html = renderToStaticMarkup(
      <CorrectedReferencePanel result={corrected()} onDismiss={() => undefined} />,
    );
    expect(html).toContain(escaped(t("payments.correct.field.confirmation")));
    expect(html).not.toContain(escaped(t("payments.correct.field.method_id")));
  });
});

describe("DEF-3203 · the refusal a clerk reads is a SENTENCE, not silence", () => {
  it("payments.correct_reference.refused resolves in the catalogue", () => {
    // The backend has raised this key since task 41 landed and no catalogue
    // defined it. Server `detail` never reaches a screen (BR-SHL-020 r2), so an
    // undefined key renders as NOTHING AT ALL: the modal would close on a
    // refusal and the clerk would be told the correction had worked.
    const sentence = t("payments.correct_reference.refused");
    expect(sentence).not.toBe("payments.correct_reference.refused");
    expect(sentence.length).toBeGreaterThan(0);
  });

  it("G33: at most two sentences, each of six words or fewer", () => {
    const sentence = t("payments.correct_reference.refused");
    const parts = sentence.split(".").filter((piece) => piece.trim() !== "");
    expect(parts.length).toBeLessThanOrEqual(2);
    for (const part of parts) {
      expect(part.trim().split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });

  it("it carries no rule id and no field name a clerk would not recognise", () => {
    const sentence = t("payments.correct_reference.refused");
    expect(sentence).not.toContain("BR-");
    expect(sentence).not.toContain("method_id");
    expect(sentence).not.toContain("confirmation");
  });
});
