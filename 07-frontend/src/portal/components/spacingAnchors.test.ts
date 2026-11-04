/* ══════════════════════════════════════════════════════════════════════════
 * B14 RULE 39 — THE THREE THINGS WHOSE QUIET REMOVAL WOULD UNDO IT.
 *
 * ── Trace ────────────────────────────────────────────────────────────────
 * Rules:   B14 rule 39 (ONE spacing scale; a field is label → input → helper
 *          at 5 / 6 / 20) — RATIFIED 2026-09-11, and its own status column
 *          says *"UNENFORCED — no gate reads computed spacing."*
 * ─────────────────────────────────────────────────────────────────────────
 *
 * ⚠ **SAY FIRST WHAT THIS CANNOT DO (hard-won law 1).** It does **not** measure
 * a rendered pixel. Nothing in this repo can: `getComputedStyle` needs a
 * browser, and the only instrument that reads rendered output here is a person
 * with a walkthrough script (law 6). So the ten anchors are NOT asserted, and a
 * lane must not read a green run here as "rule 39 holds".
 *
 * **What it does assert is the small set of facts that a later edit would
 * remove without anyone noticing**, each of which is load-bearing and none of
 * which needs a browser:
 *
 *   1. `--space-5: 20px` exists, in BOTH files that declare the scale, at the
 *      same value. It is the one step rule 39 was missing, and a scale
 *      declared in two places is a second copy free to drift — the failure
 *      hard-won law 5 names (two OpenAPI schemas) and `DEF-154` names again
 *      (two base-charge columns).
 *   2. **No `--sp-N` family exists anywhere.** The rule is stated in the PO's
 *      own words as `--sp-1 … --sp-7`, and the amendment ruled the same day
 *      says a lane ADDS to `--space-N` and mints NO second family. A future
 *      lane reading only the rule text would create exactly that; this is what
 *      tells them.
 *   3. The portal's paragraph reset exists AND the staff one survives it. Those
 *      two are one fact: the fix had to be scoped, because `global.css` is
 *      shared and ~100 staff screens depend on the rule being scoped OUT of,
 *      not deleted.
 * ══════════════════════════════════════════════════════════════════════════ */
import { describe, expect, it } from "vitest";

// Node's own modules, reached the way `pageHeadCensus.test.ts` next door does —
// `@types/node` is deliberately not installed, so a plain `import … from
// "node:fs"` fails `tsc` with *Cannot find module*.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};

const STYLES = new URL("../../styles/", import.meta.url).pathname;
const read = (name: string) => nodeFs.readFileSync(STYLES + name, "utf8");

/** Declarations only — a `--space-5` written inside a comment is prose. */
function scaleOf(css: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of css.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/(--space-\d+):\s*([^;]+);/g)) {
    out[m[1]] = m[2].trim();
  }
  return out;
}

describe("B14 rule 39 — the spacing scale", () => {
  it("declares all seven steps, and the two files agree on every one", () => {
    const tailwind = scaleOf(read("tailwind.css"));
    const tokens = scaleOf(read("tokens.css"));
    const WANTED = {
      "--space-1": "4px",
      "--space-2": "8px",
      "--space-3": "12px",
      "--space-4": "16px",
      "--space-5": "20px",
      "--space-6": "24px",
      "--space-8": "32px",
    };
    expect(
      tailwind,
      "tailwind.css's @theme block must declare all seven steps of rule 39. " +
        "`--space-5: 20px` is the one that was missing at ratification — it is " +
        "the rule's *step side padding, KPI cell side padding*.",
    ).toMatchObject(WANTED);
    expect(
      tokens,
      "tokens.css declares the same scale and must not drift from tailwind.css.",
    ).toMatchObject(WANTED);
  });

  it("mints no second `--sp-N` family", () => {
    // The rule QUOTES the PO as `--sp-1 … --sp-7` and then rules, verbatim
    // *"Okay"*, that the family is `--space-N`. A lane building from the quote
    // rather than from the amendment writes the second scale this test exists
    // to refuse.
    const everywhere = read("tailwind.css") + read("tokens.css") + read("global.css");
    const invented = [...everywhere.matchAll(/--sp-\d+\s*:/g)].map((m) => m[0]);
    expect(
      invented,
      "a `--sp-N` custom property was declared. Rule 39's amendment of " +
        "2026-09-11 is explicit: the token names are `--space-N`, and the " +
        "`--sp-N` spelling is the PO's own wording for the SCALE, not a token " +
        "name to implement. Two spacing scales in one product is the second " +
        "copy hard-won law 5 exists to prevent.",
    ).toEqual([]);
  });
});

describe("the paragraph margin is scoped, not deleted", () => {
  const global = read("global.css").replace(/\/\*[\s\S]*?\*\//g, "");

  it("the portal is reset — through `:where()`, which is the load-bearing half", () => {
    // ⚠ **THE `:where()` IS ASSERTED, NOT JUST THE SELECTOR.** Written plainly
    // as `[data-portal] p` the reset scores (0,1,1) and BEATS every Tailwind
    // margin utility, which are single classes at (0,1,0) — in the built sheet
    // both sit outside any cascade layer, so specificity alone decides. Rule
    // 39's own 6px helper gap would then render as 0, and the 59 `m-0`
    // workarounds this fix retires would break in the same commit. `:where()`
    // contributes no specificity, so the reset ties with the `p` rule it
    // overrides on source order and loses to anything a component asked for.
    expect(
      /:where\(\[data-portal\]\)\s+p\s*\{\s*margin-block:\s*0\s*;?\s*\}/.test(global),
      "`:where([data-portal]) p { margin-block: 0 }` is gone from global.css, " +
        "or the `:where()` around it has been removed — which is worse than " +
        "the rule being absent, because without it the reset outranks every " +
        "margin utility in the portal. It is " +
        "what makes rule 39's field anatomy render at all: without it the " +
        "browser's own `1em` puts 17px between an input and its helper where " +
        "the rule ratifies 6 — and because it is `1em` it is a different " +
        "number at every font size, which no fixed scale can contain.",
    ).toBe(true);
  });

  it("and the STAFF app still has its own paragraph rhythm", () => {
    // ⚠ THE BLAST RADIUS, ASSERTED. `global.css` is shared: 84 staff
    // paragraphs have no margin of their own and run their text together
    // without this rule. Deleting it to fix one portal form would change ~100
    // staff screens nobody measured — so the scoped reset above and this rule
    // are one decision and have to be checked as one.
    expect(
      /(^|\})\s*p\s*\{\s*margin-block:\s*1em\s*;?\s*\}/m.test(global),
      "the unscoped `p { margin-block: 1em }` has been removed from " +
        "global.css. That rule is the STAFF app's paragraph rhythm and is not " +
        "the portal's to delete — scope a portal fix, never widen it.",
    ).toBe(true);
  });
});
