// ── Trace ──────────────────────────────────────────────
// Defect:   **DEF-2715** — the bill document printed the server's engineering
//           prose at a clerk: A19 section numbers, `BR-` ids, backticked
//           database columns and module paths, in the bands and in both gap
//           panels.
//           Screens: S30 (bill detail → View the bill as sent)
// Rules:    B14 rule 32 clause 4 (no rule id or internal code in clerk-facing
//           copy) · B14 rule 31 (the internal value MOVES, it is not deleted) ·
//           BR-SHL-020 (an absence is stated in plain language) ·
//           BR-SHL-041 (eleven catalogues) · law 7 (RED first)
// ───────────────────────────────────────────────────────
// **THE MEASUREMENT.** On a live bill, under the field labelled *Utility*, a
// clerk read:
//
//     "A19 §1.1 mastheads the bill with the utility's name; the snapshot stamps
//      no tenant identity, so the document cannot say who sent it. BR-BIL-030
//      lists 'tenant identity and branding reference' as stamped."
//
// and under *Worth looking at*, a paragraph naming `OQ-117`, `BR-BIL-035`,
// `bill_payload` and `apps/billing/stages/assemble_document.py`.
//
// **NOTHING IN THIS REPO COULD CATCH IT.** `G28` part 1 scans the eleven
// catalogues and these strings are in none of them — they never enter `en.json`
// at all, because they are composed in Python and rendered straight through.
// `G33` counts refusal keys and these are not refusals.
//
// **THE ASSERTIONS THAT MATTER HERE ARE THE NEGATIVES**, and they are written
// as PATTERNS rather than as the exact sentences: a check pinned to today's
// wording would go green the moment somebody reworded the prose while leaving
// it prose. What must never appear on this screen is the SHAPE — a rule id, an
// A19 section number, a backtick, a `.py` path.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DocumentBand } from "./BillDocumentPage";
import type { DocumentField } from "@/api/billingOpsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";
import en from "@/i18n/locales/en.json";

const catalogue = en as Record<string, string>;
const t: Translator = (key, params) => {
  const value = catalogue[key];
  if (value === undefined) {
    return (params?.defaultValue as string | undefined) ?? key;
  }
  return value.replace(/\{\{(\w+)\}\}/g, (_whole, name: string) =>
    String((params as Record<string, unknown> | undefined)?.[name] ?? ""),
  );
};

/** The exact string `documents._masthead` composes, copied from `documents.py`. */
const SERVER_WHY =
  "A19 §1.1 mastheads the bill with the utility's name; the snapshot " +
  "stamps no tenant identity, so the document cannot say who sent it. " +
  "BR-BIL-030 lists 'tenant identity and branding reference' as stamped.";

const FIELDS: DocumentField[] = [
  {
    label: "Utility",
    value: "—",
    absent: { field: "utility_name", why: SERVER_WHY, br_ref: "BR-BIL-030" },
  },
  { label: "Address", value: "1 Mill Race, Brazos", absent: null },
];

const markup = () =>
  renderToStaticMarkup(<DocumentBand heading="Who sent it" fields={FIELDS} t={t} />);

/** Everything B14 rule 32 clause 4 and rule 31 forbid in copy a clerk reads.
 *  Shapes, not sentences — see the header. */
const INTERNAL = [
  /\bBR-[A-Z]{3}-\d{3,5}(?!\d)\b/,
  /\bOQ-\d{3,5}(?!\d)\b/,
  /\bDEF-\d{3,5}(?!\d)\b/,
  /\bA19 §/,
  /`[a-z_]+`/,
  /\.py\b/,
];

describe("DEF-2715 — the document's absences are stated in words, not in module notes", () => {
  it("prints none of the server's internal vocabulary as text", () => {
    // The rendered TEXT, with every element's attributes stripped: rule 31 puts
    // the internal value on the element deliberately, so a check over the raw
    // markup would go RED on a correct fix and GREEN on the breach.
    const text = markup().replace(/<[^>]*>/g, " ");

    for (const shape of INTERNAL) {
      expect(text).not.toMatch(shape);
    }
    expect(text).not.toContain(SERVER_WHY);
  });

  it("says what the dash means, from the catalogue", () => {
    expect(markup()).toContain(en["billing.document.fieldAbsent"]);
  });

  it("keeps the server's own words and its rule id ON the element", () => {
    // NOT deleted, and NOT on `title` — a tooltip is clerk-facing, so
    // `BR-BIL-030` in one is still `BR-BIL-030` on the screen. Support and an
    // engineer read these off the DOM; the lane report and the log are
    // unaffected because the server still composes them.
    const html = markup();

    expect(html).toContain('data-br-ref="BR-BIL-030"');
    expect(html).toContain('data-absent-field="utility_name"');
    expect(html).toContain("data-absent-why=");
    expect(html).not.toContain('title="');
  });

  it("leaves a field that HAS a value completely alone", () => {
    expect(markup()).toContain("1 Mill Race, Brazos");
  });
});
