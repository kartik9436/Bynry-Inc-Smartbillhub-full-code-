/* `P0.10` of `05-prototype/06 Payments Page Blueprint.pdf` — the half of *"two
 * lists use it and the third inherits"* that is a fact about the SOURCE.
 *
 * Node environment on purpose, and the import shape is this repo's own: a
 * static `node:fs` import passes vitest and FAILS `tsc --noEmit`, and
 * `import.meta.url` under jsdom is an `http:` URL that `fileURLToPath` refuses.
 * `SettingsOwnedField.test.tsx` and `runbookKitClasses.test.ts` do it this way
 * for the same two reasons. The rendering assertions live in
 * `selectionToolbar.dom.test.tsx`.
 *
 * ⚠ **WHY A SOURCE READ AND NOT A RENDER.** Mounting either screen here would
 * need its whole fixture, and the question is not *does that screen work* — its
 * own suite answers that — but *is this component still the one it draws its
 * bar with*. That is a fact about the import, and it is exactly the fact that
 * goes quietly false when somebody hand-rolls a fourth bar: a kit component
 * nothing renders is the dead UI hard-won law 2 is about.
 */
import { describe, expect, it } from "vitest";

const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

const source = (relative: string): string =>
  nodeFs.readFileSync(nodeUrl.fileURLToPath(new URL(relative, import.meta.url)), "utf8");

describe("P0.10 — two lists use the kit's selection toolbar", () => {
  it("the debtor list (7·1) composes it, and its hand-rolled row is gone", () => {
    // ⚠ **ONE HOP FURTHER SINCE `68db7d740` (2026-09-23, `CR-138-BRC07`
    // P4.11).** The debtor list's bar became its own COMPONENT,
    // `DebtorBulkBar` — B14 rule 43, *a piece of UI is built as a component* —
    // and THAT file composes the kit's `SelectionToolbar`. This case read the
    // kit import off `OutstandingsTab.tsx` itself and was red from that commit
    // with the product exactly as the rule wants it. So the list is asked for
    // the component, and the component for the kit.
    const list = source("../features/payments/OutstandingsTab.tsx");
    expect(list).toContain('from "./DebtorBulkBar"');
    expect(list).toContain("<DebtorBulkBar");
    // Gone rather than left beside it — a replaced pattern that stays in the
    // file is the copy the next lane reaches for (hard-won law 1).
    expect(list).not.toContain('className="pay-bulk"');
    const bar = source("../features/payments/DebtorBulkBar.tsx");
    expect(bar).toContain('from "@/components/SelectionToolbar"');
    expect(bar).toContain("<SelectionToolbar");
    expect(bar).not.toContain('className="pay-bulk"');
  });

  it("the reads list composes it", () => {
    const text = source("../features/metering/ReadsBulkBar.tsx");
    expect(text).toContain('from "@/components/SelectionToolbar"');
    expect(text).toContain("<SelectionToolbar");
  });

  it("the payments bulk bar is the third, and it composes it now (P1.8)", () => {
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-22, AND THAT IS IT
    // WORKING.** It read `expect(text).not.toContain("<SelectionToolbar")` —
    // a HOLD shipped with the test that fires when it expires, hard-won law
    // 2's mirror. `P1.8` mounted the kit's bar in `paymentsBulk.tsx` and this
    // case went RED, in the words *"expected … not to contain
    // '<SelectionToolbar'"*, and named the file. **It was flipped rather than
    // deleted**: the question it asks — *is this list still drawn with the kit
    // piece* — is exactly the fact that goes quietly false when somebody
    // hand-rolls a fourth bar, and the three lists now answer it the same way.
    const text = source("../features/payments/paymentsBulk.tsx");
    expect(text).toContain('from "@/components/SelectionToolbar"');
    expect(text).toContain("<SelectionToolbar");
    // Gone rather than left beside it — a replaced pattern that stays in the
    // file is the copy the next lane reaches for (hard-won law 1). The three
    // `pay-bulk*` classes stay DECLARED in `payments.css`: G31's ceiling only
    // falls when a stylesheet shrinks, and that is its own piece of work.
    expect(text).not.toContain('className="pay-bulk"');
  });

  it("all three bars are the kit's, and none of them hand-rolls a row", () => {
    // ⚠ **THE HALF THAT MAKES THE THREE CASES ABOVE ONE FACT.** Each of them
    // reads one file, so all three would pass over a fourth list that invented
    // its own bar tomorrow — which is what `P0.10` measured happening three
    // times. This one names the population: every file that draws a selection
    // bar draws THIS component.
    for (const file of [
      // the debtor list's bar, extracted from `OutstandingsTab.tsx` (above)
      "../features/payments/DebtorBulkBar.tsx",
      "../features/metering/ReadsBulkBar.tsx",
      "../features/payments/paymentsBulk.tsx",
    ]) {
      expect(source(file), `${file} stopped composing the kit's selection bar`).toContain(
        "<SelectionToolbar",
      );
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p13 `P0.10`
// generated: 2026-09-22 by LANE P0-FE
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/components/selectionToolbarWiring.test.ts · tsc --noEmit
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
