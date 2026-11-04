// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-005 (the S56 chart of accounts a human can finally edit) ·
//           US-LED-006 (the export codes and their visible gaps) ·
//           US-LED-011 (S57 — an unbalanced entry cannot be submitted) ·
//           US-LED-012 (the accrual sweep) · US-LED-013 (reverse + repost) ·
//           US-LED-017 (TC-5 — an unsigned code is never presented as signed)
//           Screens: S56 · S57 · S73
// Rules:    BR-LED-003 · BR-LED-005 · BR-LED-014 · BR-LED-015 · BR-LED-037 ·
//           BR-BIL-010 · BR-SHL-023 (one money formatting path) · BR-SHL-025 ·
//           IS-1 (deactivate-first) · CLAUDE.md rule 2 · rule 4
// ───────────────────────────────────────────────────────
// **THE REFUSALS ARE THE POINT OF THIS FILE**, in the shape its two neighbours
// already set. Every case below has a tidier answer sitting beside it that a
// screen could have rendered instead, and each one would have been a lie:
//
//   · an UNBALANCED entry could simply be submitted and refused afterwards;
//   · a DELETE whose reference read failed could report "0 references";
//   · the eight PROPOSED cost accounts could be drawn like the signed ones;
//   · a service with NO revenue account could show a dash instead of the fact
//     that every bill for it will fail to issue.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { LedgerChartResponse, LedgerChartRow } from "@/api/endpoints";

import {
  CHART_COLUMNS,
  ChartTable,
  deleteBlockedReason,
  deleteCaveat,
  deleteRefusalText,
  holdingKinds,
} from "./ChartOfAccountsPanel";
import { canPost, emptyRow, rowProblem, rowProblems, toWireLines } from "./JournalEntryModal";
import { glViewFrom } from "./GeneralLedgerPage";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

function chartRow(overrides: Partial<LedgerChartRow> = {}): LedgerChartRow {
  return {
    account_id: "acc-1",
    code: "1200",
    name: "Accounts receivable",
    type: "asset",
    // CR-061 statement (1) — the chart HEADING. `null` is the lawful
    // *uncategorised* value and is what every row on a database provisioned
    // before 2026-09-02 carries, so the default here is a real state and not a
    // placeholder; the cases that care pass one through `overrides`.
    category: "accounts_receivable",
    designation: "accounts_receivable",
    status: "active",
    qbo_ref: null,
    xero_ref: null,
    created_at: "2026-08-01T00:00:00Z",
    finance_signed: true,
    seeded: true,
    ...overrides,
  };
}

function chart(rows: LedgerChartRow[]): LedgerChartResponse {
  return {
    rows,
    // `DEF-LED-6715` — the roles with NO live account. Empty here on purpose:
    // these cases are about ACCOUNT rows, and `chartOneTable.dom.test.tsx` owns
    // the non-empty case. A fixture that quietly carried one would make every
    // assertion below run against a screen showing a count nobody asserted.
    roles_needing_account: [],
    // CR-061 (PO 2026-09-01, *"no, you cannot file discount under revenue"*) —
    // `contra_revenue` is the SIXTH value the server publishes here. The panel
    // renders this list into both the filter and the add-account picker, so a
    // fixture short of it would test a screen the server no longer describes.
    types: ["asset", "liability", "equity", "revenue", "contra_revenue", "expense"],
    // CR-061 statement (1) (PO 2026-09-01, *"actually you need more GL code s
    // and categories"*) — the eighteen headings the server publishes, in the
    // order a chart is READ rather than alphabetically. The panel renders this
    // list into the category filter and the add-account picker, so a fixture
    // short of it would test a screen the server no longer describes.
    categories: [
      "cash_investments",
      "accounts_receivable",
      "inventory",
      "fixed_assets",
      "construction_cip",
      "accumulated_depreciation",
      "accounts_payable",
      "taxes_payable",
      "customer_deposits",
      "debt",
      "grants_contributions",
      "net_position",
      "customer_revenue",
      "revenue_adjustments",
      "non_operating",
      "transfers",
      "cost_of_service",
      "operating_expenses",
    ],
    designations: ["accounts_receivable", "cash", "budget_variance"],
    pending_finance_re_sign: [],
    pending_finance_re_sign_cost: ["5100", "5110"],
    // The THIRD register — CR-061's 67 utility-books accounts, none of them
    // finance-signed.
    pending_finance_re_sign_books: ["1500", "2000"],
    cost_section_source: "B5 line 74 … awaits a finance RE-SIGN via HUMAN-GUIDE §6",
    utility_books_source: "B5 line 74 … awaits a finance RE-SIGN via HUMAN-GUIDE §6",
    currency: "USD",
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// US-LED-011 — an unbalanced entry cannot be SUBMITTED, not merely refused
// ═══════════════════════════════════════════════════════════════════════════
describe("US-LED-011 · S57 · the Post control", () => {
  it("cannot be pressed until a SAVED draft foots and carries a memo", () => {
    // No saved draft at all: the balance is a fact about rows in the database,
    // so a modal that had never saved cannot know it.
    expect(canPost(null, "Reclass")).toBe(false);

    const unbalanced = {
      entry_id: "je-1",
      created: true,
      entry_date: "2026-08-06",
      type: "standard",
      status: "draft",
      currency: "USD",
      debits: "500.000000",
      credits: "490.000000",
      balanced: false,
      gap: "10.000000",
      line_count: 2,
      date_note: null,
      unavailable: [],
    };
    expect(canPost(unbalanced, "Reclass")).toBe(false);

    const balanced = { ...unbalanced, credits: "500.000000", balanced: true, gap: "0.000000" };
    // BR-LED-003's third demand: a memo. The entry is immutable the moment it
    // posts, so this is the only place the reason can ever be written.
    expect(canPost(balanced, "   ")).toBe(false);
    expect(canPost(balanced, "Reclass card fees")).toBe(true);
  });

  it("names what is wrong with a row rather than greying out in silence", () => {
    expect(rowProblem(emptyRow())).toBeNull();
    expect(rowProblem({ accountId: "", debit: "10.00", credit: "" })).toBe(
      "finance.je.error.accountRequired",
    );
    // A line is a debit or a credit, never both — `journal_lines` stores one
    // side and one non-negative amount.
    expect(rowProblem({ accountId: "a", debit: "10.00", credit: "10.00" })).toBe(
      "finance.je.error.oneSideOnly",
    );
    expect(rowProblem({ accountId: "a", debit: "", credit: "" })).toBe(
      "finance.je.error.amountRequired",
    );
    // A NEGATIVE DEBIT IS A CREDIT WEARING THE WRONG WORD.
    expect(rowProblem({ accountId: "a", debit: "-10.00", credit: "" })).toBe(
      "finance.je.error.amountFormat",
    );
    expect(rowProblem({ accountId: "a", debit: "10.00", credit: "" })).toBeNull();
    expect(rowProblems([emptyRow(), { accountId: "a", debit: "", credit: "" }])).toEqual([
      null,
      "finance.je.error.amountRequired",
    ]);
  });

  it("sends amounts as STRINGS and drops only the untouched rows", () => {
    const lines = toWireLines([
      { accountId: "a", debit: "500.00", credit: "" },
      { accountId: "b", debit: "", credit: "500.00" },
      emptyRow(),
    ]);
    expect(lines).toEqual([
      { ledger_account_id: "a", side: "debit", amount: "500.00" },
      { ledger_account_id: "b", side: "credit", amount: "500.00" },
    ]);
    // CLAUDE.md rule 2 — every amount on the wire is a string, never a number.
    for (const line of lines) {
      expect(typeof line.amount).toBe("string");
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// US-LED-005 — the chart, and the two DIFFERENT reasons a Delete is refused
// ═══════════════════════════════════════════════════════════════════════════
describe("US-LED-005 · S56 · the chart of accounts", () => {
  it("distinguishes 'something points at this' from 'we cannot tell'", () => {
    const referenced = chartRow({
      references: {
        account_id: "acc-1",
        counts: { journal_lines: 14, designation: 1 },
        services: [],
        referenced: true,
        answerable: true,
        unavailable: [],
      },
    });
    expect(deleteBlockedReason(referenced)).toBe("finance.coa.delete.referenced");
    expect(holdingKinds(referenced)).toEqual(["journal_lines", "designation"]);

    // **THE DEF-127 SHAPE, REFUSED.** Nothing points at this row as far as the
    // counts go — and one reference kind could not be READ, so the honest
    // answer is "I cannot tell" and the delete stays off. A screen that read
    // `referenced: false` alone would delete a chart row on a missing query.
    const unknown = chartRow({
      references: {
        account_id: "acc-1",
        counts: { journal_lines: 0, designation: 0 },
        services: [],
        referenced: false,
        answerable: false,
        unavailable: [
          { code: "charge_code_references_are_not_readable_here", br_ref: "BR-BIL-010", detail: "" },
        ],
      },
    });
    expect(deleteBlockedReason(unknown)).toBe("finance.coa.delete.unanswerable");
    expect(deleteBlockedReason(unknown)).not.toBe("finance.coa.delete.referenced");

    // And a row nobody has asked about is not "safe to delete" either.
    expect(deleteBlockedReason(chartRow())).toBe("finance.coa.delete.notChecked");

    // BOTH AT ONCE is the normal case, and the ACTIONABLE fact wins the
    // sentence: an account pinned by fourteen journal lines whose charge-code
    // reference is also unreadable must not say "we cannot tell" and then list
    // what it found. The caveat rides beside it instead.
    const both = chartRow({
      references: {
        account_id: "acc-1",
        counts: { journal_lines: 14 },
        services: [],
        referenced: true,
        answerable: false,
        unavailable: [
          { code: "charge_code_references_are_not_readable_here", br_ref: "BR-BIL-010", detail: "" },
        ],
      },
    });
    expect(deleteBlockedReason(both)).toBe("finance.coa.delete.referenced");
    expect(deleteCaveat(both)).toBe("finance.coa.delete.alsoUnreadable");
    expect(deleteCaveat(referenced)).toBeNull();
  });

  it("US-LED-017 TC-5 — an unsigned cost account is never drawn as signed", () => {
    const html = renderToStaticMarkup(
      <ChartTable
        // `DEF-LED-6715` — REQUIRED, not optional. An optional prop nothing
        // passes is dead UI (hard-won law 2), and a default `visibleColumns`
        // here would let these cases assert nine columns while the real
        // screen draws seven.
        visibleColumns={CHART_COLUMNS.map((column) => column.key)}
        columnsControl={null}
        rolesNeedingAccount={[]}
        showingRoles={false}
        chart={chart([
          chartRow(),
          chartRow({
            account_id: "acc-2",
            code: "5100",
            name: "Purchased power",
            type: "expense",
            designation: null,
            finance_signed: false,
          }),
        ])}
        t={t}
        onAdd={() => undefined}
        onEdit={() => undefined}
        onToggleActive={() => undefined}
        onDelete={() => undefined}
      />,
    );
    expect(html).toContain(t("finance.coa.unsigned"));
    // The proposal is SHOWN, not hidden — it is a real account a capture can
    // point at, and hiding it would be its own defect.
    expect(html).toContain("Purchased power");
    // …and the route the signature has to come through is named on screen.
    expect(html).toContain("5100");
  });

  // ═══════════════════════════════════════════════════════════════════════
  // CR-061 statement (1) — the chart HEADING reaches the screen
  // ═══════════════════════════════════════════════════════════════════════
  it("CR-061 — every row is drawn under a heading a person can read", () => {
    const html = renderToStaticMarkup(
      <ChartTable
        // `DEF-LED-6715` — REQUIRED, not optional. An optional prop nothing
        // passes is dead UI (hard-won law 2), and a default `visibleColumns`
        // here would let these cases assert nine columns while the real
        // screen draws seven.
        visibleColumns={CHART_COLUMNS.map((column) => column.key)}
        columnsControl={null}
        rolesNeedingAccount={[]}
        showingRoles={false}
        chart={chart([
          chartRow({ code: "1500", name: "Land", category: "fixed_assets" }),
          chartRow({
            account_id: "acc-3",
            code: "2000",
            name: "Vendor accounts payable",
            type: "liability",
            category: "accounts_payable",
            designation: null,
          }),
        ])}
        t={t}
        onAdd={() => undefined}
        onEdit={() => undefined}
        onToggleActive={() => undefined}
        onDelete={() => undefined}
      />,
    );
    // B14 rule 32 / the 2026-09-01 ruling that a fallback must not print a
    // machine value: the heading is the CATALOGUE's words, never the code.
    expect(html).toContain(t("finance.gl.category.fixed_assets"));
    expect(html).toContain(t("finance.gl.category.accounts_payable"));
    expect(html).not.toContain("fixed_assets");
    expect(html).not.toContain("accounts_payable");
    expect(html).toContain(t("finance.coa.col.category"));
  });

  it("CR-061 — an account nobody has filed is NAMED uncategorised, not dashed", () => {
    // ⚠ THIS IS THE COMMON CASE, NOT THE EDGE. Nothing backfills `category`
    // (hard-won law 4), so on any database provisioned before 2026-09-02 EVERY
    // row is null. A dash would read as "this account has no heading and never
    // will"; the group has a name because a clerk has to be able to find it.
    const html = renderToStaticMarkup(
      <ChartTable
        // `DEF-LED-6715` — REQUIRED, not optional. An optional prop nothing
        // passes is dead UI (hard-won law 2), and a default `visibleColumns`
        // here would let these cases assert nine columns while the real
        // screen draws seven.
        visibleColumns={CHART_COLUMNS.map((column) => column.key)}
        columnsControl={null}
        rolesNeedingAccount={[]}
        showingRoles={false}
        chart={chart([chartRow({ code: "1150", name: "Trade debtors", category: null })])}
        t={t}
        onAdd={() => undefined}
        onEdit={() => undefined}
        onToggleActive={() => undefined}
        onDelete={() => undefined}
      />,
    );
    expect(html).toContain(t("finance.coa.category.none"));
  });

  // ═══════════════════════════════════════════════════════════════════════
  // DEF-3061 — the sixth account type had no translation key
  // ═══════════════════════════════════════════════════════════════════════
  it("DEF-3061 — a contra-revenue account prints its NAME, never `contra_revenue`", () => {
    // CR-061 minted `contra_revenue` on 2026-09-01 and the lane that did was
    // instructed not to edit the catalogues, so the Type column fell back to
    // the raw machine value on S56, on Settings → Accounting and on the trial
    // balance. G27 could not see it — the call site is a TEMPLATE LITERAL,
    // t(`finance.gl.type.${row.type}`) — and G15 read perfect parity, because
    // the key was missing from all eleven catalogues equally.
    const html = renderToStaticMarkup(
      <ChartTable
        // `DEF-LED-6715` — REQUIRED, not optional. An optional prop nothing
        // passes is dead UI (hard-won law 2), and a default `visibleColumns`
        // here would let these cases assert nine columns while the real
        // screen draws seven.
        visibleColumns={CHART_COLUMNS.map((column) => column.key)}
        columnsControl={null}
        rolesNeedingAccount={[]}
        showingRoles={false}
        chart={chart([
          chartRow({
            code: "4760",
            name: "Customer discounts (contra-revenue)",
            type: "contra_revenue",
            category: "revenue_adjustments",
            designation: "discount_contra_revenue",
            finance_signed: false,
          }),
        ])}
        t={t}
        onAdd={() => undefined}
        onEdit={() => undefined}
        onToggleActive={() => undefined}
        onDelete={() => undefined}
      />,
    );
    expect(html).toContain(t("finance.gl.type.contra_revenue"));
    expect(html).not.toContain("contra_revenue");
  });

  // ═══════════════════════════════════════════════════════════════════════
  // DEF-LED-6170 — the resting screen carries no paragraph under a row
  //
  // ⚠ **WHAT MADE THIS INVISIBLE IS WORTH MORE THAN THE CASES BELOW.** Every
  // string on this table was in the catalogue, resolved, translated eleven
  // ways and asserted by a `toContain` that passed. **Nothing anywhere asked
  // how many TIMES it renders, or how long it is.** G33 caps a refusal at six
  // words and never saw one of these: it walks `g32_refusal_keys.raised_keys()`
  // — the `message_key`s the BACKEND raises — and these four strings are
  // rendered by this component and raised by no Python, so they were never on
  // its baseline and its count never covered them. That is hard-won law 7's
  // "reports zero over a scope it silently excludes", and the honest number
  // came from a browser: **129 rows, 224 notes, 3,980 words, 14,043px.**
  //
  // So these assert the two things a `toContain` cannot: that a cell holds
  // ONLY what it is for, and that what a clerk reads at rest is within B14
  // rule 33's caps. Proved red against the pre-fix component before they were
  // trusted green.
  // ═══════════════════════════════════════════════════════════════════════
  const RULE_33_WORDS = 6;

  /** The longest sentence in a message, in words — G33's own crude, generous
   *  counter, so the two cannot disagree about what "six words" means. */
  function longestSentence(value: string): number {
    return Math.max(
      ...value
        .replace(/…/g, ".")
        .split(/(?<=[.!?])\s+/)
        .map((part) => part.trim().split(/\s+/).filter(Boolean).length),
    );
  }

  it("DEF-LED-6170 — every string this table renders at rest is within rule 33", () => {
    // The four the PO's paste was made of, plus the section note.
    for (const key of [
      "finance.coa.unsigned",
      "finance.coa.delete.referenced",
      "finance.coa.delete.unanswerable",
      "finance.coa.delete.alsoUnreadable",
      "finance.coa.delete.notChecked",
      "finance.coa.costSection",
    ]) {
      expect(`${key}: ${longestSentence(t(key))}w`).toBe(
        `${key}: ${Math.min(longestSentence(t(key)), RULE_33_WORDS)}w`,
      );
    }
    // A LABEL is capped harder than a fact — three words, and no sentence.
    expect(t("finance.coa.unsigned").split(/\s+/).length).toBeLessThanOrEqual(3);
    expect(t("finance.coa.unsigned")).not.toContain(".");
  });

  /** The visible TEXT of each `<td>` of the first body row.
   *
   * ⚠ **READING THE MARKUP INSTEAD OF THE TEXT IS WHY THE FIRST DRAFT OF THE
   * CASE BELOW PASSED ON THE BROKEN COMPONENT.** The PO sees *"Petty
   * cashProposed — finance has not…"* because two inline elements render with
   * no separator between them; in the HTML SOURCE they are
   * `Petty cash<span …>Proposed…`, so `expect(html).not.toContain("Petty
   * cash" + note)` is true of the defect and of the fix alike. It was proved
   * red before it was trusted, found green, and rewritten — which is the only
   * reason it is a check rather than decoration (hard-won law 7, habit 2:
   * ask what would make this pass WRONGLY). */
  function cellTexts(html: string): string[] {
    const body = html.split("<tbody>")[1]?.split("</tbody>")[0] ?? "";
    return (body.match(/<td[^>]*>[\s\S]*?<\/td>/g) ?? []).map((cell) =>
      cell
        .replace(/<[^>]+>/g, "")
        .replace(/&amp;/g, "&")
        .replace(/&#x27;/g, "'")
        .trim(),
    );
  }

  it("DEF-LED-6170 — the Name cell holds the name and nothing else", () => {
    // The PO's paste reads "Petty cashProposed — finance has not approved this
    // account number yet." — one run-on word, on all 94 unsigned rows of the
    // demo chart.
    const html = renderToStaticMarkup(
      <ChartTable
        // `DEF-LED-6715` — REQUIRED, not optional. An optional prop nothing
        // passes is dead UI (hard-won law 2), and a default `visibleColumns`
        // here would let these cases assert nine columns while the real
        // screen draws seven.
        visibleColumns={CHART_COLUMNS.map((column) => column.key)}
        columnsControl={null}
        rolesNeedingAccount={[]}
        showingRoles={false}
        chart={chart([chartRow({ code: "1020", name: "Petty cash", finance_signed: false })])}
        t={t}
        onAdd={() => undefined}
        onEdit={() => undefined}
        onToggleActive={() => undefined}
        onDelete={() => undefined}
      />,
    );
    const cells = cellTexts(html);
    expect(cells[1]).toBe("Petty cash");
    // …and the status did not vanish on the way — it moved to the STATUS cell,
    // which is what stops this being "delete the note and call it fixed".
    //
    // ⚠ **THE INDEX IS READ FROM THE HEADER NOW, NOT COUNTED (`DEF-LED-6715`),
    // AND THIS CASE CAUGHT A REAL BUG WHILE THE COLUMNS MOVED.** The table went
    // from seven columns to nine and `Designation` swapped ahead of `Category`
    // to match the Finance blueprint's FIELDS order (p024). The first draft of
    // that change reordered the HEADER and left the CELLS where they were, so
    // every row drew its category under a heading reading *Role in the books* —
    // and nothing else in this repository could have seen it, because both
    // cells hold real, non-empty strings and no gate reads rendered output.
    //
    // Asking the header where the column is makes the next arrival MOVE this
    // case instead of breaking it, and makes it go red the day the two rows
    // disagree again — which is the thing actually worth asserting.
    const head = html.slice(html.indexOf("<thead"), html.indexOf("</thead>"));
    const headers = [...head.matchAll(/<th[^>]*>(.*?)<\/th>/g)].map((match) =>
      match[1].replace(/<[^>]*>/g, "").trim(),
    );
    const statusColumn = headers.indexOf(t("finance.coa.col.status"));
    expect(statusColumn).toBeGreaterThan(-1);
    expect(cells[statusColumn]).toContain(t("finance.coa.unsigned"));
    expect(cells[statusColumn]).toContain(t("finance.coa.status.active"));
  });

  it("DEF-LED-6170 — a blocked row carries its reason ONCE, on the control", () => {
    const blocked = chartRow({
      references: {
        account_id: "acc-1",
        counts: { journal_lines: 14 },
        services: [],
        referenced: true,
        answerable: true,
        unavailable: [],
      },
    });
    const html = renderToStaticMarkup(
      <ChartTable
        // `DEF-LED-6715` — REQUIRED, not optional. An optional prop nothing
        // passes is dead UI (hard-won law 2), and a default `visibleColumns`
        // here would let these cases assert nine columns while the real
        // screen draws seven.
        visibleColumns={CHART_COLUMNS.map((column) => column.key)}
        columnsControl={null}
        rolesNeedingAccount={[]}
        showingRoles={false}
        chart={chart([blocked])}
        t={t}
        onAdd={() => undefined}
        onEdit={() => undefined}
        onToggleActive={() => undefined}
        onDelete={() => undefined}
      />,
    );
    // ONCE: the paragraph under the row was a second copy of the control's own
    // tooltip, and 129 of them are what the PO was reading.
    const occurrences = html.split(t("finance.coa.delete.referenced")).length - 1;
    expect(occurrences).toBe(1);
    // …and the one that remains is the CONTROL's, still disabled (BR-SHL-025).
    expect(html).toContain("disabled");
  });

  it("DEF-LED-6170 — the reason on the control still names what holds the row", () => {
    // Rule 33 takes "in use by journal lines" off the RESTING screen. It does
    // not take it out of the product: a clerk about to retire an account needs
    // it, so it rides on the control they reach for.
    const held = chartRow({
      references: {
        account_id: "acc-1",
        counts: { journal_lines: 14, designation: 1 },
        services: [],
        referenced: true,
        answerable: false,
        unavailable: [
          { code: "charge_code_references_are_not_readable_here", br_ref: "BR-BIL-010", detail: "" },
        ],
      },
    });
    const text = deleteRefusalText(held, t);
    expect(text).toContain(t("finance.coa.delete.referenced"));
    expect(text).toContain(t("finance.coa.reference.journal_lines"));
    expect(text).toContain(t("finance.coa.reference.designation"));
    // The caveat is a SECOND fact, not an alternative to the first.
    expect(text).toContain(t("finance.coa.delete.alsoUnreadable"));
    // ⚠ AND NO DANGLING COLON. The old `referenced` string ended "In use by:"
    // because the kinds were appended in the paragraph and NOT in the tooltip,
    // so every blocked row's tooltip trailed off mid-sentence. One composer
    // now, so the two cannot disagree.
    expect(text?.trimEnd().endsWith(":")).toBe(false);
  });

  it("DEF-LED-6170 — a row that may go carries no reason at all", () => {
    const free = chartRow({
      references: {
        account_id: "acc-1",
        counts: {},
        services: [],
        referenced: false,
        answerable: true,
        unavailable: [],
      },
    });
    expect(deleteRefusalText(free, t)).toBeNull();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // DEF-LED-6171 — no designation falls back to its raw enum code
  // ═══════════════════════════════════════════════════════════════════════
  it("DEF-LED-6171 — 5700 prints a phrase, never `depreciation_expense`", () => {
    // The column renders t(`finance.designation.${d}`, {defaultValue: d}), so a
    // missing key does not fail — it prints the machine value. 13 of the 14
    // designations the demo tenant uses had a key and this one did not, which
    // is B14 rule 32's "no internal code in clerk-facing copy" reaching a
    // clerk. G18 and G27 read literal `t("…")` calls and cannot see a key built
    // from a server value, so nothing counted it.
    const html = renderToStaticMarkup(
      <ChartTable
        // `DEF-LED-6715` — REQUIRED, not optional. An optional prop nothing
        // passes is dead UI (hard-won law 2), and a default `visibleColumns`
        // here would let these cases assert nine columns while the real
        // screen draws seven.
        visibleColumns={CHART_COLUMNS.map((column) => column.key)}
        columnsControl={null}
        rolesNeedingAccount={[]}
        showingRoles={false}
        chart={chart([
          chartRow({
            code: "5700",
            name: "Depreciation expense",
            type: "expense",
            designation: "depreciation_expense",
          }),
        ])}
        t={t}
        onAdd={() => undefined}
        onEdit={() => undefined}
        onToggleActive={() => undefined}
        onDelete={() => undefined}
      />,
    );
    expect(html).toContain(t("finance.designation.depreciation_expense"));
    expect(html).not.toContain("depreciation_expense");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// US-LED-006 + BR-BIL-010 — the GL map's four panels, DELETED (`DEF-LED-6715`)
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THREE CASES STOOD HERE AND THEY ARE GONE WITH THE COMPONENT THEY
// RENDERED. RECORDED RATHER THAN DELETED QUIETLY** — a suite that stops asking
// a question leaves no trace, which is hard-won law 1 pointed at a test file.
//
// They mounted `GlMappingPanels`, the four sections under the chart, and asked:
//
//   1. *"keeps THREE empty states apart instead of drawing three blanks"* — a
//      retired account's designation (an ALERT), an account finance may not
//      write yet (a NOTE) and a missing export ref (US-LED-006 TC-1's visible
//      empty state).
//   2. `DEF-261` — a SEEDED code awaiting a signature says so BESIDE its
//      number, and `DEF-LED-6613`'s half: the marker must not render GLUED to
//      the account name.
//   3. `BR-BIL-010` — a service with no revenue account says the bill will
//      fail.
//
// **The PO merged all four panels into the one table on 2026-09-25** (*"i will
// have 1 table only and i will use columns to manage rest of the table"*), so
// the component has no mount and these cases cannot be kept as they were.
//
// **WHERE EACH ONE'S SUBJECT LIVES NOW, so nobody concludes the behaviour went
// with the test:**
//   · The missing export ref is a CELL of the one table — `finance.map.noRef`
//     in the QuickBooks and Xero columns — and is asserted by
//     `chartOneTable.dom.test.tsx`.
//   · The unsigned marker is the `Proposed` pill the accounts table already
//     drew per row, which `US-LED-005 · S56` above covers.
//   · **A designation with NO live account is the one that had nowhere to go**,
//     and it is the reason `DEF-LED-6715` was filed with a warning in it: it is
//     now a served list, a count and a filter value, and
//     `chartOneTable.dom.test.tsx` fails if that warning stops being reachable.
//   · `BR-BIL-010`'s service→revenue map is Settings → Accounting → Mapping,
//     a DIFFERENT editor (`SettingsAccountingTab`'s `MappingPanel`), and its
//     cases belong to that file. **They are not written here and that is a
//     real gap**, filed on `DEF-LED-6715`'s row rather than absorbed.

// ═══════════════════════════════════════════════════════════════════════════
// S73 · S74 — the boundary panel is GONE, and this suite says why (DEF-2346)
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE SUITE THAT STOOD HERE IS PART OF WHY THE DEFECT LASTED, SO IT IS
// REPLACED RATHER THAN DELETED.** It rendered `CostOfServiceBoundary` and
// asserted six sentences were PRESENT — *"Not built. Five questions have to be
// answered…"*, three question bullets, the ruling note and *"Nothing records a
// supplier invoice yet"*. Every assertion passed for as long as the panel
// existed, because **presence is not truth**: no assertion in it could go red
// when the feature it called unbuilt shipped.
//
// Its own comment had the principle exactly right — *"a panel whose whole job
// is to say what is undecided must stop saying it the hour it is decided"* —
// and it could not check the thing it was right about. That is hard-won law 1
// wearing a green tick.
//
// **What replaces it asks the opposite question**: not *is the sentence on the
// screen* but *can the sentence still be bought at all*. A stated absence whose
// copy no longer exists cannot come back by accident, and the catalogue is what
// would have to move first.
describe("the cost-of-service boundary is gone (DEF-2346)", () => {
  it("its copy is retired, so the panel cannot quietly come back", () => {
    // PROVED RED FIRST. `finance.cost.blocked` was written back into all
    // eleven catalogues and this test was run. Verbatim:
    //   AssertionError: expected 'Not built. Five questions have to be …' to be ''
    //   + Not built. Five questions have to be answered by your team before a
    //     single figure here could be trusted, and this product will not guess
    //     at any of them:
    // The probe is `defaultValue: ""`, because i18next returns the KEY ITSELF
    // for a missing key — asserting on the key would pass for the wrong reason,
    // which is the G27 failure (a screen rendering its own source) as a test.
    for (const key of [
      "finance.cost.blocked",
      "finance.cost.whatExists",
      "finance.cost.ruled",
      "finance.cost.q.units",
      "finance.cost.q.afterClose",
      "finance.cost.q.home",
    ]) {
      expect(i18n.t(key, { defaultValue: "" })).toBe("");
    }
  });

  it("the one question that was REAL is still stated where it bites", () => {
    // Removing the panel must not remove a live refusal. The unit mismatch was
    // one of its three bullets and is still true; it reaches a clerk on the
    // reconciliation ROW now, rather than as an essay on the chart tab.
    expect(t("finance.cost.problem.purchase_unit_does_not_match_billed_unit")).not.toBe("");
    // And one it listed as undecided is BUILT: correcting a purchase after the
    // month is closed has its own form copy and its own already-exported note.
    expect(t("finance.cost.field.correctionReasonHelp")).not.toBe("");
    expect(t("finance.cost.correctedButExported")).not.toBe("");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// US-LED-012 / the S56 sub-views
// ═══════════════════════════════════════════════════════════════════════════
describe("US-LED-012 · the S56 sections", () => {
  it("an unknown ?view= falls back to the LANDING view and never 404s", () => {
    // ⚠ **AMENDED 2026-09-24 (`P1.15`) — THE FALLBACK MOVED FROM `balance` TO
    // `journal`, AND THAT IS THE RULING RATHER THAN A BROKEN TEST.** This case
    // read `toBe("balance")` and was correct while the strip had three
    // sections. The Finance blueprint splits it into four (p020 · p023 · p025 ·
    // p027) and marks the journal *"the landing view"*; p022's DOORS line puts
    // it plainly — *"It is the landing view, so every door to `/finance` is a
    // door to this screen"*. What the case asserts is unchanged: an unknown
    // value resolves to SOMETHING and never 404s.
    expect(glViewFrom(null)).toBe("journal");
    expect(glViewFrom("")).toBe("journal");
    expect(glViewFrom("nonsense")).toBe("journal");
    // ⚠ **`balance` STILL RESOLVES, WHICH IS THE HALF THAT MATTERS TO A
    // BOOKMARK.** The word on screen changed from *"Trial balance & journal"*
    // to *"Balance"*; the URL VALUE did not, deliberately, so every existing
    // ticket link and saved tab still lands where it did.
    expect(glViewFrom("balance")).toBe("balance");
    expect(glViewFrom("chart")).toBe("chart");
    expect(glViewFrom("accruals")).toBe("accruals");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-005@e85081b (co-packets US-LED-006 · US-LED-011 · US-LED-012 · US-LED-013 · US-LED-017 — sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-02-chart-mapping.md · EP-LED-04-manual-je.md · EP-LED-06-cost-of-service-capture.md · 09-ledger/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.10)
// generated: 2026-08-16 by story-coder (the ledger surface lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — with the balance check removed from `canPost`, "AssertionError: expected true to be false // Object.is equality" on "the Post control > cannot be pressed until a SAVED draft foots and carries a memo". Restored: 30 passed across the three ledger test files. tsc✔ eslint✔ vite build✔
// exceptions: (1) the modal itself is never opened by a click here — the balance rule is proved on the PURE `canPost`/`rowProblem` functions and end to end in a BOOTED BROWSER against the e2e stack (quoted in the lane report), which is stronger evidence than a jsdom click · (2) the panels are rendered through `renderToStaticMarkup`, where effects never run, so the assertions are about what the screen SAYS given a served response — the same posture `financeSurface.test.tsx` takes · (3) no test asserts a money FORMAT: `MoneyCell` owns that and has its own suite (BR-SHL-023)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
