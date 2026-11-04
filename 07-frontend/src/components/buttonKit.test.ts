// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 3 — the shared button family, Route B (PO 2026-08-19)
// Defect:   the hole this file exists to close is recorded in the decision log
//           row "CR-018 PHASE 3" §"THE SAFETY NET DOES NOT REACH A COMPONENT
//           API" and as OQ-280.
// Rules:    B14 rule 5 (two button sizes only — default and small, 12px)
// Impacts:  src/components/buttonKit.ts only
// ───────────────────────────────────────────────────────
//
// ⚠ WHY THIS FILE HAD TO BE WRITTEN, AND IT IS THE PHASE 3 SPIKE'S SHARPEST
// FINDING
//
// Route B's whole safety argument is that a wrong style becomes UNWRITABLE:
// `g31_declared_classes.py` refuses a class no stylesheet declares, and
// `src/styles/routeBUtilities.test.ts` asks the stricter question of a migrated
// file — every class token must be declared OR compile to a real rule.
//
// **Both read `className=` attributes.** The moment the utilities move into a
// component API they stop living in an attribute and start living in a string
// constant, and both readers go blind. Measured, not assumed: `items-center`
// was changed to `itmes-center` in `buttonKit.ts` and
//
//     npx vitest run src/styles/routeBUtilities.test.ts   → 5 passed
//     python3 10-scripts/gates/g31_declared_classes.py    → PASS, 0 undeclared
//
// with `components/buttonKit.ts` listed in `route-b-migrated.txt`. A typo that
// would have flattened every button in the product was invisible to the entire
// safety net — which is DEF-327's failure mode arriving through the front door
// of the migration bought to remove it.
//
// So the kit checks ITSELF, at the real Tailwind compiler, in `npm test`. Every
// token of every string must generate a rule. The parity spec next door
// (`e2e/CR-018-phase3-button-parity.spec.ts`) would also have caught this, but
// it needs Postgres, Django and a browser; this needs none of them and runs on
// every push.
//
// PROVED RED FIRST (hard-won law 7): with `itmes-center` in place this test
// fails naming that exact token.
import { describe, expect, it } from "vitest";

import { BUTTON_KIT_TOKENS, buttonClasses } from "./buttonKit";
import type { ButtonSize } from "./buttonKit";

// ⚠ A BARE `import … from "node:fs"` PASSES VITEST AND FAILS `tsc`: @types/node
// is not in the app's tsconfig, so the module has no declarations. This file
// already reaches Node through the string-split shim below; the CSS walker uses
// the same handles rather than adding a second copy of them.
function allCss(dir: string, out: string[] = []): string[] {
  for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
    const full = nodePath.join(dir, entry.name);
    if (entry.isDirectory()) allCss(full, out);
    else if (full.endsWith(".css")) out.push(full);
  }
  return out;
}

// Node's own modules, reached exactly the way `src/styles/routeBUtilities.test.ts`
// next door does — the string-split import keeps Vite from pre-bundling them and
// keeps `tsc` (which does not carry @types/node for `src/`) out of it.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string, o: { withFileTypes: true }): { name: string; isDirectory(): boolean }[];
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};
const nodeModule = (await import(/* @vite-ignore */ ["node", "module"].join(":"))) as {
  createRequire(p: string): { resolve(id: string): string };
};

const SRC = nodePath.dirname(nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url)));
const STYLES = nodePath.join(SRC, "styles");

async function tailwind(): Promise<{ build(candidates: string[]): string }> {
  const { compile } = (await import("tailwindcss")) as {
    compile(
      css: string,
      opts: {
        base: string;
        loadStylesheet(
          id: string,
          base: string,
        ): Promise<{ path: string; base: string; content: string }>;
      },
    ): Promise<{ build(candidates: string[]): string }>;
  };
  const require_ = nodeModule.createRequire(nodePath.join(SRC, "index.ts"));
  return compile(nodeFs.readFileSync(nodePath.join(STYLES, "tailwind.css"), "utf8"), {
    base: SRC,
    loadStylesheet: async (id: string) => {
      const resolved = require_.resolve(id);
      return {
        path: resolved,
        base: nodePath.dirname(resolved),
        content: nodeFs.readFileSync(resolved, "utf8"),
      };
    },
  });
}

describe("the button kit compiles — the class strings a component API hides from G31", () => {
  it("every token of every variant and size generates a real rule", async () => {
    const compiler = await tailwind();
    expect(BUTTON_KIT_TOKENS.length, "the kit reported no tokens").toBeGreaterThan(40);

    // ⚠ `compile()` returns an INCREMENTAL builder: `build([t])` adds `t` to the
    // set it has already seen and returns the WHOLE sheet. The first draft of
    // this test compared every token against the empty-set length, so once any
    // token had grown the sheet every later token looked alive — and a
    // deliberate `itmes-center` sabotage PASSED. That is the vacuous green this
    // repo has recorded three times (G26, G27, DEF-323), reproduced here by
    // trusting an API's shape instead of measuring it.
    //
    // So the comparison is against the length BEFORE this token, and the list is
    // de-duplicated first — a token that appears in two variants (`bg-transparent`
    // does) adds nothing the second time and would otherwise read as dead.
    const unique = [...new Set(BUTTON_KIT_TOKENS)];
    let previous = compiler.build([]).length;
    const dead: string[] = [];
    for (const token of unique) {
      const grown = compiler.build([token]).length;
      if (grown <= previous) dead.push(token);
      previous = grown;
    }
    expect(dead.join(", ")).toBe("");
  });

  it("the check itself goes red on a typo", async () => {
    // The guard on the guard. Without this, a `build()` that silently returned
    // the same string for everything would make the test above pass over
    // nothing at all — the vacuous-green failure recorded in G26/G27 and
    // DEF-323.
    const compiler = await tailwind();
    const floor = compiler.build([]).length;
    expect(compiler.build(["itmes-center"]).length).toBe(floor);
    expect(compiler.build(["items-center"]).length).toBeGreaterThan(floor);
    // …and that a token already seen adds nothing, which is the incremental
    // behaviour the test above had to be rewritten around.
    const seen = compiler.build(["items-center"]).length;
    expect(compiler.build(["items-center"]).length).toBe(seen);
  });

  it("B14 rule 5 — a SIZE is padding AND type, and the kit renders three (DEF-342)", () => {
    // ⚠ THIS IS THE GUARD DEF-342 IS ABOUT, AND THE OLD ONE READ THE WRONG
    // THING. CR-016 measures `distinctButtonFontSizes` and B14 rule 5 says
    // "two button SIZES". A button's size is its padding and its type
    // TOGETHER — the old check read one third of it and reported conformance
    // while the product rendered four sizes under one conforming font size.
    //
    // Measured off `buttonClasses()`, which is what actually reaches the DOM,
    // rather than off the constant maps — a size that stopped being wired
    // would otherwise still be counted.
    // ⚠ `text-text` IS A COLOUR, NOT A SIZE. A bare /^text-/ matches both and
    // my first draft of this guard failed on exactly that — the ruled size
    // names are listed instead.
    const TYPE_SIZE = /^(?:[a-z-]+:)?text-(?:btn|btn-sm|xs|sm|base|md|body|h[1-5]|display|metric|metric-sm|metric-lg)$/;
    const SIZES: ButtonSize[] = ["default", "sm", "row"];
    const shape = (size: ButtonSize) => {
      const tokens = buttonClasses("secondary", size).split(/\s+/);
      const pick = (re: RegExp) => tokens.filter((t) => re.test(t)).sort().join(" ");
      // ⚠ THE BOX IS PART OF THE SHAPE NOW. `row` is the only tier with a
      // fixed 32x32, and a check that read only padding would call a 32px
      // square and a zero-padding word the same size — which is the shape of
      // the original bug in this guard, one property further along.
      return [pick(/^py-/), pick(/^px-/), pick(/^[wh]-/), pick(TYPE_SIZE)].join(" | ");
    };
    const distinct = new Set(SIZES.map(shape));

    // ⚠ RATCHETED AT 3, NOT ASSERTED AT 2, DELIBERATELY. It was 4 until
    // 2026-08-20 and it may FALL and must never RISE — a permanently-red guard
    // earns a `skip` rather than a fix.
    //
    // ⚠ WHAT MADE IT FALL WAS NOT A PADDING EDIT, AND THAT WAS DEF-342's WHOLE
    // FINDING. `row` and `settings-row` were `0 8px` and `2px 6px` because half
    // the product's row actions were TEXT squeezed into a table row and half
    // were 16px GLYPHS. Two contents, two paddings, neither wrong. The PO ruled
    // on the content instead (2026-08-20, "Icons everywhere, per r10 and rule
    // 15"), the two became one 32x32 icon tier, and the fourth shape stopped
    // existing rather than being argued away.
    //
    // Whether the remaining three satisfy rule 5's "two" is a live question:
    // `row` is a different SHAPE (a fixed box) rather than a third scale step.
    // That is for the r10 pass, which is why this stays a ratchet.
    expect(
      distinct.size,
      `button SIZES (padding + box + type), one per rendered shape: ${[...distinct].join("  ·  ")}`,
    ).toBeLessThanOrEqual(3);

    // The half that IS conformant, kept as its own assertion so a regression in
    // it cannot hide behind the ratchet above.
    const fontSizes = SIZES.flatMap((size) =>
      buttonClasses("secondary", size).split(/\s+/).filter((t) => TYPE_SIZE.test(t)),
    );
    expect([...new Set(fontSizes)].sort()).toEqual(["text-btn", "text-btn-sm"]);
  });

  it("B14 rule 5 — the kit writes exactly TWO button font sizes", async () => {
    // Rule 5 is "two button sizes only — default and small (12px)". The kit is
    // now the only place a button font size is written, so the rule can be
    // asserted on the SOURCE rather than on 24 rendered screens.
    const sizes = BUTTON_KIT_TOKENS.filter((t) => /(^|:)text-(btn|xs|sm|base|md|lg)/.test(t));
    expect([...new Set(sizes)].sort()).toEqual(["text-btn", "text-btn-sm"]);
  });

  it("the legacy variant rules stay DELETED — no second implementation grows back", () => {
    // ⚠ THIS REPLACES `e2e/CR-018-phase3-button-parity.spec.ts`, WHICH IS
    // DELETED ON THIS COMMIT AND SHOULD BE. That spec rendered the legacy class
    // names beside the kit's output in a live bundle and diffed every computed
    // property in four states — the strongest proof this migration had, and the
    // reason the rules could be deleted at all. It cannot run now: the thing it
    // compared against no longer exists, so it would report several hundred
    // differences and mean nothing by them. A check that can only fail is worse
    // than no check. Retired deliberately, with this in its place.
    //
    // What is left to protect is the OPPOSITE property: that nobody declares
    // `.btn-primary` in a stylesheet again and quietly gives the product two
    // button implementations that drift. That is DEF-344's shape (`.met-danger`
    // beside `.btn-danger`) and it has happened here before.
    const DELETED = ["btn-primary", "btn-secondary", "btn-ghost", "btn-sm", "btn-danger", "btn-link"];
    const sheets = allCss(SRC);
    const offenders: string[] = [];
    for (const rel of sheets) {
      // ⚠ STRIP `/* … */` FIRST. Every one of these names is DISCUSSED in a
      // stylesheet comment — StateFrame.css's own note about deleting them,
      // metering.css on `.met-danger`, AppShell.css describing the prototype's
      // menu — and the first draft of this check reported eleven "declarations"
      // that were all prose. Same trap as G31's, third time today: a check that
      // reads source has to be told the difference between code and a sentence
      // about code.
      const css = nodeFs.readFileSync(rel, "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");
      for (const name of DELETED) {
        if (new RegExp(`(^|[^-\\w])\\.${name}\\b`, "m").test(css)) {
          offenders.push(`${rel} declares .${name}`);
        }
      }
    }
    expect(
      offenders,
      "the button kit is the ONE implementation — a stylesheet declaring these " +
        "again is a second one, and two that render the same today drift tomorrow",
    ).toEqual([]);
  });
});
