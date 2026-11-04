// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-015 · US-BIL-016 · US-BIL-017 · US-BIL-031 (Fix a bill) ·
//           US-BIL-018 · US-BIL-019 · US-BIL-020 (Budget Bills) ·
//           US-BIL-021 (the bill-layout chooser) · US-BIL-022 (the document) ·
//           US-BIL-028 (the custom-field snapshot's Remarks & notes band) ·
//           US-BIL-006 (the pending queue) · US-BIL-026 (the detail's link)
//           Screens: S30 · S8
// Rules:    BR-BIL-004 (a correction is NEW ROWS — no edit affordance) ·
//           BR-BIL-017 (the ±30% bound is measured against the COMPUTED level)
//           · BR-BIL-026 (a layout choice affects FUTURE bills only) ·
//           BR-SHL-020 · BR-SHL-023 (one money path) · CLAUDE.md rule 2
// ───────────────────────────────────────────────────────
// The server-free half of the billing SURFACE lane's proof.
//
// What these assert is the class of defect this release is named after: **a
// figure that means "I do not know" rendered as a number**. Every one of them
// drives a real component with a fake transport and checks that a null comes
// out as a stated absence and never as `0.00`, and that no money figure reaches
// a screen without its CHAR(3).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MoneyOrDash } from "./BudgetBillsTab";
import { DocumentBand } from "./BillDocumentPage";
import { money, signedMoney } from "./fixABill/fixABillShared";
import { GapNotes, billDocumentPath, todayIso } from "./billingOpsShared";
import type { BudgetStatusRow, DocumentField } from "@/api/billingOpsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The catalogue is not loaded in unit tests; the key IS the assertion target,
 *  which is what makes "did this render an absence or a zero?" checkable. */
const t: Translator = (key, params) =>
  params === undefined ? key : `${key}:${JSON.stringify(params)}`;

/** The rendered markup as a string — the harness this suite already uses
 *  (`renderToStaticMarkup`), so no new test dependency enters the tree. */
function html(node: JSX.Element): string {
  return renderToStaticMarkup(node);
}

const ENROLLED: BudgetStatusRow = {
  account_id: "01a00000-0000-7000-8000-000000000001",
  // ⛔ DEF-3158 — served since 2026-09-02. The first column of the Budget Bills
  // tab printed `account_id.slice(0, 8)` with NO fallback, so `01a00000` was
  // the visible value on every row (B14 rule 31).
  account_no: "ACC-1042",
  // Served with the number since §05 screen 25 draws both in one cell.
  customer_name: "Navarro, P.",
  status: "enrolled",
  level: "242.000000",
  level_override: null,
  level_override_reason: null,
  effective_level: "242.000000",
  variance_balance: "-50.870000",
  currency: "USD",
  settle_up_month: 12,
  enrolled_on: "2026-08-16",
  last_leveled_at: "2026-08-16",
};

// `DEF-GOV-10106` — these cases pinned `LevelCell`, which the budget table
// stopped drawing when §05 screen 25 split the level into its own COMPUTED ·
// OVERRIDE · THEY PAY columns. They now pin `MoneyOrDash`, the one renderer all
// three columns share. US-BIL-020 TC-21's "computed stays visible beside an
// override" is structural now — the computed figure is a column of its own.
describe("US-BIL-018 / US-BIL-019 / US-BIL-020 — the budget level never lies", () => {
  it("US-BIL-018 TC-21 renders the level WITH its currency, never a bare number", () => {
    const markup = html(<MoneyOrDash amount={ENROLLED.effective_level} currency="USD" locale="en-US" />);
    // CLAUDE.md rule 2 — a lane shipped `-147.500000` into a toast with no
    // currency under 21 passing unit tests. This is the assertion that catches
    // the same shape here.
    expect(markup).toContain("$242.00");
  });

  it("US-BIL-019 TC-21 renders a NULL level as a stated absence, never as 0.00", () => {
    const markup = html(<MoneyOrDash amount={null} currency="USD" locale="en-US" />);
    expect(markup).toContain("—");
    expect(markup).not.toContain("0.00");
  });
});

// CR-180-BRC10 retired the nine-section case renderer with the screen that
// drew it; the money rule it guarded (WE-9's figures, 2 places, never without
// their CHAR(3), an absence never a zero) is asserted on the new screen's one
// money path instead.
describe("US-BIL-015 / US-BIL-016 — Fix a bill's money (CR-180-BRC10)", () => {
  const fmt = { t, currency: "USD", language: "en-US" };
  it("US-BIL-016 TC-21 renders ❄️ WE-9's figures with their currency, at two places", () => {
    expect(money("247.870000", fmt)).toBe("$247.87");
    expect(money("227.950000", fmt)).toBe("$227.95");
    // The delta always says which way it moved, and never as a bare number.
    expect(signedMoney("-19.920000", fmt)).toBe("\u2212$19.92");
    expect(signedMoney("19.920000", fmt)).toBe("+$19.92");
  });

  it("an absent figure is a dash, never 0.00", () => {
    expect(money(null, fmt)).toBe("—");
    expect(signedMoney(undefined, fmt)).toBe("—");
  });
});

describe("US-BIL-022 / US-BIL-026 — the document", () => {
  it("US-BIL-022 TC-24 attaches an absence to the FIELD it belongs to", () => {
    const fields: DocumentField[] = [
      { label: "Amount due", value: "—", absent: { field: "total_due", why: "not stamped", br_ref: "OQ-117" } },
      { label: "Account", value: "A-10432", absent: null },
    ];
    const markup = html(<DocumentBand heading="Bill details" fields={fields} t={t} />);
    // ⚠ AMENDED FOR `DEF-2715`. This case asserted `toContain("not stamped")` —
    // the SERVER's own sentence, rendered verbatim at a clerk. The property the
    // case is named for is unchanged and is still what is proved: the absence
    // rides on the FIELD it belongs to, not in a list at the foot of the page.
    // What changed is which text a person reads. The server's words are kept —
    // support and an engineer read them off the element — and the clerk reads
    // the catalogue's sentence.
    expect(markup).toContain('data-absent-why="not stamped"');
    expect(markup).toContain('data-br-ref="OQ-117"');
    expect(markup).toContain("billing.document.fieldAbsent");
    expect(markup).toContain("A-10432");
  });

  it("US-BIL-026 TC-20 builds a document path off the invoice id", () => {
    expect(billDocumentPath("abc def")).toBe("/billing/bills/abc%20def/document");
  });

  // US-BIL-028 TC-9 (2026-08-12) — *"in remark or note section on bill"*, on the
  // viewer. The BAND is the whole screen half of that story: the values are
  // stamped strings and this side formats none of them, so what a test can
  // prove here is that every stamped value REACHES the page and that a tenant
  // with none gets no empty heading inviting the question of what belongs in it.
  it("US-BIL-028 TC-9 prints every custom field, and TC-5 draws nothing when there are none", () => {
    const remarks: DocumentField[] = [
      { label: "Account · Member no", value: "10432", absent: null },
      { label: "Account · Connected on", value: "2026-03-04", absent: null },
      { label: "Premises · Access notes", value: "Locked gate, Dog on site", absent: null },
    ];
    const markup = html(<DocumentBand heading="Remarks & notes" fields={remarks} t={t} />);
    // TC-10's literals, on the page: an identifier is NOT grouped and a date is
    // NOT localised — both are frozen into an append-only row.
    expect(markup).toContain("10432");
    expect(markup).not.toContain("10,432");
    expect(markup).toContain("2026-03-04");
    expect(markup).not.toContain("03/04/2026");
    expect(markup).toContain("Locked gate, Dog on site");

    // TC-5: `{}` stamps, and the section is omitted whole.
    expect(html(<DocumentBand heading="Remarks & notes" fields={[]} t={t} />)).toBe("");
  });
});

describe("US-BIL-006 / US-BIL-021 — the shared honesty pieces", () => {
  it("US-BIL-006 TC-20 states the business day rather than letting the server guess", () => {
    expect(todayIso(new Date("2026-08-16T23:30:00Z"))).toBe("2026-08-16");
  });

  it("US-BIL-021 TC-24 renders the gaps the SERVER reports about itself", () => {
    const markup = html(
      <GapNotes
        gaps={[{ code: "x", br_ref: "BR-BIL-026", detail: "no designer in R2" }]}
        t={t}
      />,
    );
    expect(markup).toContain("no designer in R2");
    // CR-016, 2026-08-19: the rule reference must NOT be drawn as text. It was
    // the bold lead of every bullet in this list on the deployed build, which is
    // one of the screens the Product Owner photographed. It stays on the element
    // so support can still read it.
    expect(markup).not.toContain("<b>BR-BIL-026</b>");
    expect(markup).toContain('data-br-ref="BR-BIL-026"');
  });

  it("US-BIL-021 TC-25 renders nothing when the server reports no gaps", () => {
    expect(html(<GapNotes gaps={[]} t={t} />)).toBe("");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-015@a71c4e2 (sources: EP-BIL-04-corrections.md · EP-BIL-05-budget-billing.md · EP-BIL-06-templates-delivery.md · EP-BIL-01-bill-run.md US-BIL-006 · 07-billing/02-business-rules.md · 07-billing/08-worked-examples.md WE-8/WE-9; co-packets US-BIL-016, US-BIL-017, US-BIL-018, US-BIL-019, US-BIL-020, US-BIL-021, US-BIL-022, US-BIL-026, US-BIL-031, US-BIL-006)
// generated: 2026-08-16 by story-coder (billing SURFACE lane — the server-free half)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — `US-BIL-019 TC-21` was shown to fail against a LevelCell that fell back to "0.00" on a null level (verbatim in the lane report), which is the class of defect this release is named after. tsc✔ · eslint --max-warnings 0✔ · vitest 12 passed✔ · vite build✔
// exceptions: E3 the harness is `renderToStaticMarkup`, the one this suite already uses — no new test dependency enters the tree for this lane · E3 the translator is the identity function on purpose: the KEY is the assertion target, which is what makes "did this render an absence or a zero?" checkable without loading a catalogue
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
