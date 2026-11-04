// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-7640 — `+ Build your own` on Reports → Catalogue did
//          nothing (PO, deployed v2.388.0). The fix opens screen 2·2 on a
//          BLANK definition (PO ruling 2026-09-28: *"Opens the editor on a
//          blank definition, then Save as"*), and a blank definition has
//          nothing at all to preview.
// Screens: 2·2 (A1 S47) at `/{tenant}/reports/custom/new`
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT — this is the third
//          member of the preview family, beside `ReportSamplePreview` and
//          `ReportShapePreview`, rather than six lines inline in the page) ·
//          rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 words · RATIONALE is ZERO
//          words on screen) · rule 32 (one sentence per section) · rule 21
//          (Tailwind utilities; this file is listed in route-b-migrated.txt)
// Tests:   07-frontend/src/features/reports/reportEditorPage.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE THIRD ANSWER TO *WHAT DOES THE CLERK SEE WHILE THEY ARE CHOOSING?*  ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The page already had two, and they are a pair: `ReportSamplePreview` draws
// the report's own first five rows, and `ReportShapePreview` draws the column
// headings over grey bars where the query returned nothing. **Neither can
// speak for a report that has never been saved.**
//
//   · the rows come from `GET /reports/{key}`, and a blank draft has no key;
//   · the shape comes from the ticked columns, and a blank draft has none —
//     `ReportShapePreview` returns `null` on zero columns, deliberately,
//     because *"an empty frame under a heading is a promise with nothing
//     behind it"*.
//
// So the right column of a blank builder rendered **nothing at all**, and an
// empty half-screen is a screen that looks broken. This says the one true
// thing instead.
//
// ⚠ **IT SAYS WHAT IS, AND NEVER WHY.** B14 rule 33 puts RATIONALE at zero
// words on screen: *there is no preview until this report can be run* is the
// reason, it is correct, and it belongs in this docstring and in the register
// rather than under the heading. The sentence on screen is four words.
//
// ⚠ **AND IT CONTAINS NO FIGURE, FOR THE REASON `ReportShapePreview`'s OWN
// DOCSTRING GIVES.** The skill file forbids filling an empty state with
// placeholder data by name, and this product's posture is that *a confident
// wrong fact is worse than having none* — an invented `84.20` on a money
// screen is a number somebody eventually reads, quotes or reconciles. There is
// nothing here a reader could mistake for their utility's data, in any
// language, ever, and that is structural rather than a disclaimer.
import { Panel } from "@/components/Panel";
import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * THE PREVIEW OF A REPORT THAT DOES NOT EXIST YET — a heading and one fact.
 *
 * `data-report-blank-preview` is the hook the browser walk reads
 * (`10-scripts/def_rep_7640_build_your_own_walkthrough.mjs` step 5). A test
 * that searched for the SENTENCE would be asserting English against English
 * and would go green on a screen rendering a raw catalogue key.
 */
export function ReportBlankPreview(props: { t: Translator }) {
  const { t } = props;
  return (
    <Panel>
      <div className="fin-panel-head">
        {/* A LABEL — one word, and the SAME one its two siblings use, because
            a clerk who ticks a column watches this panel become the other
            one. Two words for one place is how a screen reads as two. */}
        <h3>{t("reports.edit.preview.title")}</h3>
      </div>
      <p
        data-report-blank-preview=""
        className="text-sm text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]"
      >
        {t("reports.edit.blank.fact")}
      </p>
    </Panel>
  );
}

export default ReportBlankPreview;

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-REP-7640 (PO, deployed v2.388.0, 2026-09-28) · PO ruling 2026-09-28 "Opens the editor on a blank definition, then Save as" · 12-governance/22-product-maintenance-process.md
// screens: 2·2 (A1 S47)
// generated: 2026-09-28 by lane REP-BUILD-YOUR-OWN
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the blank-preview case in reportEditorPage.dom.test.tsx was run before this file existed and failed on the absent `[data-report-blank-preview]` node. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) it draws no table and no bars — a report with no columns has no shape to draw, and `ReportShapePreview` already returns null there rather than framing nothing
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
