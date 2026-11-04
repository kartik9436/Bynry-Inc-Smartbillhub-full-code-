// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave J — `ACC-S14` commits every quick action
//           to "a recap before it commits"; R4 draws this box thirteen times.
// Rules:    B14 rule 11 (a consequence preview before a commit) · rule 21
//           (Tailwind utilities; this file's subject is on
//           `src/styles/route-b-migrated.txt`) · rule 33 (a LABEL is three
//           words) · rule 36 (the shared kit is how you comply)
// ───────────────────────────────────────────────────────
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RecapBox } from "./RecapBox";

const ROWS = [
  { label: "Status now", value: "Pending activation" },
  { label: "Service starts", value: "09/11/2026" },
];

describe("RecapBox", () => {
  it("draws every row as a label and its value", () => {
    const html = renderToStaticMarkup(<RecapBox title="What happens next" rows={ROWS} />);
    expect(html).toContain("What happens next");
    expect(html).toContain("Status now");
    expect(html).toContain("Pending activation");
    expect(html).toContain("Service starts");
    expect(html).toContain("09/11/2026");
  });

  it("is a description list and NOT a table", () => {
    // A table promises a header row this box does not draw, and a screen reader
    // would announce one that is not there.
    const html = renderToStaticMarkup(<RecapBox title="t" rows={ROWS} />);
    expect(html).toContain("<dl");
    expect(html).toContain("<dt");
    expect(html).toContain("<dd");
    expect(html).not.toContain("<table");
  });

  it("announces itself as a note", () => {
    expect(renderToStaticMarkup(<RecapBox title="t" rows={ROWS} />)).toContain('role="note"');
  });

  it("draws the outcome under a rule, and only when one is given", () => {
    // R4's bold final row — *"Balance after this adjustment $2,000.00"*. Absent
    // means the rule is not drawn either, which is `ACC-Q08` and `ACC-Q13`.
    const without = renderToStaticMarkup(<RecapBox title="t" rows={ROWS} />);
    expect(without).not.toContain("border-t-2");
    const withOutcome = renderToStaticMarkup(
      <RecapBox title="t" rows={ROWS} outcome={{ label: "After this", value: "Active" }} />,
    );
    expect(withOutcome).toContain("border-t-2");
    expect(withOutcome).toContain("After this");
    expect(withOutcome).toContain("Active");
  });

  it("gives every row a hook a walkthrough can find it by", () => {
    const html = renderToStaticMarkup(
      <RecapBox
        title="t"
        rows={[{ label: "Plan", value: "SCW-RES", testId: "unitPlan" }]}
        outcome={{ label: "After this", value: "Active", testId: "outcomeSentence" }}
      />,
    );
    expect(html).toContain('data-recap-row="unitPlan"');
    expect(html).toContain('data-recap-outcome="outcomeSentence"');
  });

  it("carries a caller's own hook", () => {
    const html = renderToStaticMarkup(
      <RecapBox title="t" rows={ROWS} data-recap="quick-action" />,
    );
    expect(html).toContain('data-recap="quick-action"');
  });

  it("holds a consequence box inside it without becoming one", () => {
    // R4 puts its *"Two things the server will not manage"* panel INSIDE the
    // recap on `ACC-Q03`. The two are composed, never folded: one says what
    // the figures become, the other says what will not happen at all.
    const html = renderToStaticMarkup(
      <RecapBox title="t" rows={ROWS}>
        <p data-inner="">No deposit is charged.</p>
      </RecapBox>,
    );
    expect(html).toContain("No deposit is charged.");
    expect(html).toContain('data-inner=""');
  });

  it("never interpolates a class name", () => {
    // B14 rule 21's per-file clause (`DEF-974`): Tailwind's scanner cannot see
    // `border-${tone}`, and a class the compiler never emitted renders as
    // NOTHING while every `toContain` still passes.
    const html = renderToStaticMarkup(<RecapBox title="t" rows={ROWS} />);
    expect(html).not.toContain("${");
  });
});
