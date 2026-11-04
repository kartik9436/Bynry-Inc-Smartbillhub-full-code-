// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane 01 — blueprint §02 entry 01 "All bills"
//           (p007 REDESIGN, read AS AN IMAGE per B14 rule 42). The half of
//           entry 01 that no rendered DOM can answer: a STYLESHEET rule.
//           Screens: S30 · BIL-01, and every list in the product
// Rules:    A12 (money/number cells right-aligned) · B14 rule 21
// Tests:    this file (the jsdom half is CR101Entry01.dom.test.tsx)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHY THIS IS A SOURCE ASSERTION AND NOT A DOM ONE.** `jsdom` computes no
 * layout and resolves no stylesheet cascade, so it cannot tell a header that
 * sits over its figures from one 35px adrift. Hard-won law 6: the finding came
 * from a browser and could not have come from anywhere else. The guard reads
 * the DECLARATION that fixes it, which is the trade `CR043BillsSurface` and
 * `tailwindTheme.test.ts` already make.
 *
 * This file lives in the NODE environment on purpose — `import.meta.url` is an
 * `http:` URL under jsdom and `fileURLToPath` throws on it.
 */
import { describe, expect, it } from "vitest";

const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(path: string, encoding: string): string;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...parts: string[]): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL): string;
};
const HERE = nodeUrl.fileURLToPath(new URL(".", import.meta.url));
const SRC = nodePath.join(HERE, "..", "..");

describe("CR-101 entry 01 · the TOTAL header sits over the money (A12)", () => {
  it("`.data-table th.cell-num` right-aligns, beating `.data-table th`", () => {
    // ⚠ THE MECHANISM, so nobody "simplifies" this away. `.cell-num` is
    // specificity (0,1,0); `.data-table th { text-align: left }` is (0,1,1) and
    // WINS, so every numeric column in the product shipped a left-aligned
    // header over right-aligned figures. Measured 2026-09-14 in Chromium at
    // 1440 on `/brazosbend/billing`: the TOTAL header's content ended 47px from
    // the cell's right edge against 12px for the money under it — 35px adrift,
    // and `getComputedStyle(th).textAlign` read `left` while the `td` read
    // `right`. `.settings-table th.cell-num` already carried this exact fix,
    // which is the tell that the kit rule was the one that was wrong.
    const css = nodeFs.readFileSync(nodePath.join(SRC, "components", "DataTable.css"), "utf8");
    const at = css.indexOf(".data-table th.cell-num");
    expect(at).toBeGreaterThan(-1);
    expect(css.slice(at, css.indexOf("}", at))).toContain("text-align: right");
    // The generic header rule KEEPS its left default — that is what holds every
    // text column where it belongs, and dropping it would move 120 headers the
    // other way.
    const generic = css.slice(css.indexOf(".data-table th {"));
    expect(generic.slice(0, generic.indexOf("}"))).toContain("text-align: left");
  });
});
