/* ══════════════════════════════════════════════════════════════════════════
 * CR-075 wave C · C1a — EVERY CLASS IN A TONE MAP, ASKED OF THE REAL COMPILER
 * ══════════════════════════════════════════════════════════════════════════
 *
 * WHY THIS EXISTS, AND WHY `routeBUtilities.test.ts` NEXT DOOR IS NOT ENOUGH
 * -------------------------------------------------------------------------
 * That suite already asks the real Tailwind compiler whether every class a
 * migrated file names compiles, and it is stricter than G31 in every way its
 * own header claims. It has TWO independent narrowings, they compound, and the
 * shape they leave uncovered is exactly the one a component kit uses. Both were
 * found by probing before writing rather than by any gate.
 *
 * **ONE — THE CONSTANT READER ONLY EVER OPENS `*Kit.ts` FILES.**
 *
 *     ALL_FILES.filter((f) => f.endsWith("Kit.ts"))
 *
 * That is `buttonKit.ts`, `workflowKit.ts`, `notificationsKit.ts` and nothing
 * else. `StatusPill.tsx`, `Disclosure.tsx`, `WarningBox.tsx` and every one of
 * the eight files below are never read by it at all. The suite is not lying
 * when it reports zero — it is reporting zero over a scope it does not name,
 * which is hard-won law 7's fifth shape.
 *
 * **TWO — AND EVEN INSIDE THOSE THREE FILES, AN ANNOTATED CONSTANT IS INVISIBLE.**
 *
 *     classname-grammar/patterns.json · kit_constant
 *         \bconst\s+[A-Za-z_$][\w$]*\s*=\s*([^;]*);
 *
 * The `=` must follow the identifier, so
 *
 *     const WARNING_TONE: Record<WarningTone, string> = { … }
 *
 * matches NOTHING. `buttonKit.ts`'s own `VARIANT: Record<ButtonVariant, string>`
 * is that shape, inside a file the reader does open — so the two narrowings are
 * genuinely separate and closing either one alone leaves the hole open.
 *
 * G31 sees none of it either: it reads `className=` attributes only.
 *
 * That is not hypothetical. `components/WarningBox.tsx` (2026-09-06) asks for
 * `border-danger` and `var(--color-danger)`; this theme declares
 * `--color-danger-500` and `--color-danger-700` and NO bare `--color-danger`,
 * so B14 rule 6's danger tier — the tone reserved for a state a person must act
 * on — draws with no border colour and no tint. `tsc` and eslint have no
 * opinion on a class name and `toContain("border-danger")` passes, because the
 * class IS in the DOM. `DEF-SHL-4281`, and it is `DEF-INT-4236` recurring in
 * the same file three lines under the comment that records it.
 *
 * MEASURED, so the blind spot has a NUMBER rather than a shrug (hard-won law 7:
 * a declared blind spot with no number attached is indistinguishable from an
 * empty one): **33 type-annotated constants holding utility-shaped class
 * strings, across the 310 files on `route-b-migrated.txt`** — `buttonKit.ts`'s
 * `VARIANT`, `StatusPill.tsx`'s `TONE_CLASS` and `Disclosure.tsx`'s four among
 * them. The core of the shared kit. Of those 33, only ONE sits in a file the
 * `*Kit.ts` filter opens.
 *
 * THE DURABLE FIX IS IN `patterns.json`, NOT HERE
 * -----------------------------------------------
 * `kit_constant` should accept an optional type annotation, with a corpus case
 * of that shape on BOTH readers so the two cannot drift — which is what the
 * defect row asks for. Until that lands this file covers the eight components
 * CR-075 wave C added, and it covers them the way the fix would: it reads their
 * SOURCE, takes every string in every constant regardless of annotation, and
 * asks the compiler.
 *
 * PROVED RED FIRST, IN THE HARNESS THAT RUNS IT
 * ---------------------------------------------
 * `border-danger` was pasted into `VerdictBand.tsx`'s tone map and this suite
 * failed by name — `VerdictBand.tsx names "border-danger", which this theme
 * does not compile`. The failure text is quoted in the lane report. It also
 * fails, deliberately, if one of the eight files stops declaring any class at
 * all: a check that silently covers nothing is the shape it exists to catch.
 * ══════════════════════════════════════════════════════════════════════════ */
import { describe, expect, it } from "vitest";

const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
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

const COMPONENTS = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.dirname(COMPONENTS);
const STYLES = nodePath.join(SRC, "styles");

/** The eight files CR-075 wave C added to the shared kit. Named rather than
 *  globbed: a glob would silently shrink to zero if the folder moved, and this
 *  suite would then pass over nothing at all. */
const FILES = [
  // ⚠ **`WarningBox.tsx` IS NOT ONE OF CR-075 WAVE C's EIGHT — IT IS THE FILE
  // THIS SUITE'S OWN HEADER NAMES AS THE DEFECT, AND IT WAS NOT COVERED
  // (`DEF-SHL-4281`, added by the CR-089 wave I lane 2026-09-08).** The header
  // above records at length that `WarningBox` asks for `border-danger` and
  // `var(--color-danger)`, which this theme does not declare — and then the
  // suite written from that finding covered the eight NEW components and not
  // the one the finding was about. Two days later the danger tone reached a
  // real screen: `CR-089`'s protection banner, the one thing on a unit's
  // Account tab that stops a supervisor arranging a shut-off, drew a
  // `rgb(32, 30, 29)` left bar and a fully transparent background. Nothing
  // could see it — `tsc`, eslint, `G31`, `routeBUtilities.test.ts` and this
  // file were all green, and the dom test asserting `data-warning-tone="now"`
  // passed on the attribute. It was found by opening the page and reading
  // `getComputedStyle` (hard-won law 6).
  "WarningBox.tsx",
  "VerdictBand.tsx",
  "Chain.tsx",
  "ContributionBars.tsx",
  "OutcomeCard.tsx",
  "SettingsOwnedField.tsx",
  "PercentCell.tsx",
  "Sparkline.tsx",
  "RecordGrid.tsx",
];

function stripComments(source: string): string {
  // ⚠ COMMENTS FIRST, AND THIS IS NOT TIDINESS. The first draft of this reader
  // reported `border-danger`, `kit_constant` and `neutral-100` as undeclared
  // classes in files that never ask for them — every one of them a word inside
  // a DOCSTRING, several of them quoting this very defect. A check that reports
  // a file's own prose as a broken class is a check that gets switched off
  // (DEF-323, one register over), so the prose goes before anything is read.
  return source.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");
}

/**
 * Every class token a file asks for, from BOTH homes — the `className`
 * attributes G31 reads, and the constants it cannot.
 *
 * ⚠ THE CONSTANT HALF IS SCOPED TO `UPPER_SNAKE_CASE` NAMES, WHICH IS THE
 * KIT'S OWN CONVENTION FOR A TONE MAP (`BASE`, `TONE_CLASS`, `VARIANT`,
 * `CHIP_TONE`, `CELL_STATE`). A lower-case local holds ordinary values —
 * `const source = props.source ?? "read"` — and reading those reports `read`,
 * `up`, `down` and `flat` as broken classes, which is the same false-positive
 * failure one level down. The kit convention is the discriminator BECAUSE the
 * shape being guarded is the kit's.
 */
function classTokens(raw: string): Set<string> {
  const source = stripComments(raw);
  const found = new Set<string>();
  const add = (text: string) => {
    // An interpolation is invisible to Tailwind's scanner anyway; the STATIC
    // chunks around it still hold real classes (the 871 -> 870 bug).
    for (const token of text.replace(/\$\{[^}]*\}/g, " ").split(/\s+/)) {
      // A token ending in `-` is a PREFIX an interpolation completes, never a
      // class name — G31's rule, kept.
      if (token !== "" && !token.endsWith("-") && /^[a-z][^\s"'`]*$/.test(token)) found.add(token);
    }
  };
  for (const m of source.matchAll(/className=\{?[`"]([^`"]*)[`"]/g)) add(m[1]);
  for (const m of source.matchAll(/\bconst\s+([A-Z][A-Z0-9_]*)[^=;]*=\s*(\{[\s\S]*?\n\}|"[^"\n]*"|`[^`\n]*`)/g)) {
    const body = m[2];
    for (const q of body.matchAll(/"([^"\n]*)"|`([^`\n]*)`/g)) {
      const at = (q.index ?? 0) + q[0].length;
      // A QUOTED OBJECT KEY is not a utility: `{ "settings-row": "px-2" }` holds
      // a key that is perfectly utility-shaped, and position separates them.
      if (/^\s*:/.test(body.slice(at))) continue;
      const literal = q[1] ?? q[2] ?? "";
      // All or nothing per string: a constant holding prose contributes NOTHING
      // rather than its lowercase words.
      const tokens = literal.split(/\s+/).filter((t) => t !== "");
      if (tokens.length > 0 && tokens.every((t) => /^[a-z0-9$][^\s"'`]*$/.test(t))) add(literal);
    }
  }
  return found;
}

/** The compiler, asked ONCE with every candidate. `build()` is cumulative — one
 *  call per candidate reports a typo as valid because the previous candidate's
 *  rule is still in the output. */
async function generatedSelectors(candidates: string[]): Promise<Set<string>> {
  const { compile } = (await import("tailwindcss")) as {
    compile(
      css: string,
      opts: {
        base: string;
        loadStylesheet(id: string, base: string): Promise<{ path: string; base: string; content: string }>;
      },
    ): Promise<{ build(candidates: string[]): string }>;
  };
  const require_ = nodeModule.createRequire(nodePath.join(SRC, "index.ts"));
  const compiler = await compile(nodeFs.readFileSync(nodePath.join(STYLES, "tailwind.css"), "utf8"), {
    base: SRC,
    loadStylesheet: async (id: string) => {
      const p = require_.resolve(id);
      return { path: p, base: nodePath.dirname(p), content: nodeFs.readFileSync(p, "utf8") };
    },
  });
  const css = compiler.build(candidates).replace(/\\/g, "");
  const out = new Set<string>();
  for (const candidate of candidates) {
    const escaped = candidate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (new RegExp(`\\.${escaped}(?=[\\s{,:>~+]|$)`).test(css)) out.add(candidate);
  }
  return out;
}

/** Classes these files legitimately keep that a stylesheet declares rather than
 *  the compiler. Empty today — all eight are Tailwind-only under B14 rule 21 —
 *  and it is written down so that adding one is a deliberate act. */
const DECLARED_BY_A_STYLESHEET = new Set<string>([]);

describe("CR-075 wave C — every class in these kit components compiles", () => {
  it("the suite covers every file and each of them names classes", () => {
    // A check that silently covers nothing is the failure this whole file is
    // about. If a file stops asking for any class, that is a finding.
    for (const file of FILES) {
      const source = nodeFs.readFileSync(nodePath.join(COMPONENTS, file), "utf8");
      expect(classTokens(source).size, `${file} names no class at all`).toBeGreaterThan(0);
    }
  });

  it("no file asks for a class this theme does not compile", async () => {
    const asked = new Map<string, string[]>();
    for (const file of FILES) {
      const source = nodeFs.readFileSync(nodePath.join(COMPONENTS, file), "utf8");
      for (const token of classTokens(source)) {
        asked.set(token, [...(asked.get(token) ?? []), file]);
      }
    }
    const candidates = [...asked.keys()];
    const generated = await generatedSelectors(candidates);
    const orphans = candidates
      .filter((t) => !generated.has(t) && !DECLARED_BY_A_STYLESHEET.has(t))
      .map((t) => `${(asked.get(t) ?? []).join(" · ")} names "${t}", which this theme does not compile`);
    expect(orphans, orphans.join("\n")).toEqual([]);
  });

  it("the tone maps in particular are covered — the shape the grammar cannot see", () => {
    // Named explicitly so that deleting a tone map does not quietly shrink this
    // suite's scope to the `className` attributes the other readers already see.
    const withToneMaps: [string, string][] = [
      ["WarningBox.tsx", "WARNING_TONE"],
      ["VerdictBand.tsx", "CHIP_TONE"],
      ["Chain.tsx", "CELL_STATE"],
      ["OutcomeCard.tsx", "RAIL_TONE"],
      ["OutcomeCard.tsx", "LABEL_TONE"],
      ["PercentCell.tsx", "DIRECTION_CLASS"],
      ["RecordGrid.tsx", "CELL_STATE"],
    ];
    for (const [file, constant] of withToneMaps) {
      const source = nodeFs.readFileSync(nodePath.join(COMPONENTS, file), "utf8");
      expect(source, `${file} no longer declares ${constant}`).toContain(`const ${constant}`);
      // and it is the ANNOTATED shape, which is the whole point
      expect(source).toMatch(new RegExp(`const ${constant}\\s*:\\s*Record<`));
    }
  });
});
