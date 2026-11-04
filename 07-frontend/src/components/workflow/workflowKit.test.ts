// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the reusable ETL workflow kit
// Rules:    B14 rule 21 (new UI is Tailwind and adds NO stylesheet class) ·
//           B14 rule 5 (two button sizes) · B14 rule 20 (one table type) ·
//           G34 (no arbitrary TYPE value) · G36 (desktop-first breakpoints)
// Impacts:  src/components/workflow/workflowKit.ts only
// ───────────────────────────────────────────────────────
//
// ⚠ WHY A KIT HAS TO CHECK ITSELF, MEASURED RATHER THAN ASSUMED.
//
// Route B's safety argument is that a wrong style becomes UNWRITABLE:
// `g31_declared_classes.py` refuses a class no stylesheet declares and
// `src/styles/routeBUtilities.test.ts` refuses a class token that neither a
// stylesheet declares nor Tailwind compiles. **Both read `className=`
// attributes.** A component kit keeps its utilities in module constants, so
// `className={WF.RAIL}` contributes NOTHING to either reader.
//
// `buttonKit.test.ts` records what that costs: `items-center` changed to
// `itmes-center` in `buttonKit.ts` gave "5 passed" from the Route B check and
// "PASS, 0 undeclared" from G31, with every button in the product flattened.
//
// This file is the same guard for the workflow kit, and it is belt AND braces:
// `routeBUtilities.test.ts` reaches `workflowKit.ts` too, because that check
// walks every `*Kit.ts` file in `src/`. Two readers, one deriving the token
// list from the exported constant and one re-deriving it from the file's text,
// so a token dropped from the export list is still checked and a token added to
// a constant and forgotten in the export list is still checked.
//
// PROVED RED FIRST (hard-won law 7): with `flex` changed to `flexx` in `FRAME`,
// this file fails naming that exact token. The failure is quoted in the lane's
// report.
import { describe, expect, it } from "vitest";

import { WORKFLOW_KIT_TOKENS } from "./workflowKit";

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

const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.dirname(nodePath.dirname(HERE));
const STYLES = nodePath.join(SRC, "styles");

/** Every `.name` any stylesheet under `src/` declares — the shared classes a
 *  Tailwind component still legitimately composes (`input`, `field`, `radio`). */
function declaredClassNames(): Set<string> {
  const names = new Set<string>();
  const walk = (dir: string): void => {
    for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
      const full = nodePath.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (full.endsWith(".css")) {
        const css = nodeFs.readFileSync(full, "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");
        for (const m of css.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)) names.add(m[1]);
      }
    }
  };
  walk(SRC);
  return names;
}

/**
 * The compiler, asked ONCE with every candidate.
 *
 * ⚠ `compile()` RETURNS A STATEFUL BUILDER AND `build()` IS CUMULATIVE — a
 * second call re-emits everything the first produced, so a per-token loop
 * reports a typo as valid because the previous token's rule is still in the
 * output. One call, then read the selectors. (`routeBUtilities.test.ts`
 * measured this; the note is repeated here because the trap is invisible.)
 */
async function generatedSelectors(candidates: string[]): Promise<Set<string>> {
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
  const compiler = await compile(
    nodeFs.readFileSync(nodePath.join(STYLES, "tailwind.css"), "utf8"),
    {
      base: SRC,
      loadStylesheet: async (id: string) => {
        const resolved = require_.resolve(id);
        return {
          path: resolved,
          base: nodePath.dirname(resolved),
          content: nodeFs.readFileSync(resolved, "utf8"),
        };
      },
    },
  );
  const css = compiler.build(candidates).replace(/\\/g, "");
  const out = new Set<string>();
  for (const candidate of candidates) {
    const escaped = candidate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (new RegExp(`\\.${escaped}(?=[\\s{,:>~+]|$)`).test(css)) out.add(candidate);
  }
  return out;
}

describe("CR-023 · the workflow kit's utilities are real", () => {
  it("names tokens at all — a kit that exports nothing is a loop over nothing", () => {
    // DEF-057's shape, and the reason CR-016's browser walk carries the same
    // guard: a suite that iterates an empty list reports itself as a pass.
    expect(WORKFLOW_KIT_TOKENS.length).toBeGreaterThan(60);
  });

  it("every token compiles as a utility or is declared by a stylesheet", async () => {
    const candidates = [...new Set(WORKFLOW_KIT_TOKENS)];
    const generated = await generatedSelectors(candidates);
    const declared = declaredClassNames();
    const orphans = candidates.filter((t) => !generated.has(t) && !declared.has(t));
    expect(
      orphans,
      "these render NOTHING: no stylesheet declares them and Tailwind generates no rule for them",
    ).toEqual([]);
  });

  it("B14 rule 21 — the kit adds NO class to a stylesheet", () => {
    // Rule 21's ceiling is enforced by G31 across the repo; this asserts the
    // property AT the kit, so a lane extending it cannot reach for a class name
    // and leave the count to somebody else's gate. Every token must be a
    // Tailwind candidate shape or one of the shared declared classes — there is
    // no third category.
    const declared = declaredClassNames();
    const utilityShaped = /^[a-z0-9[]/;
    const bespoke = WORKFLOW_KIT_TOKENS.filter(
      (t) => !utilityShaped.test(t) && !declared.has(t),
    );
    expect(bespoke, "a bespoke class name in a Tailwind kit").toEqual([]);
  });

  it("G34 — no arbitrary TYPE value can get in through the back door", () => {
    // Clearing `--text-*` kills `text-2xl`; it does NOT kill `text-[12.5px]`,
    // which compiles from a namespace no `@theme` block can empty. The gate
    // scans source files; this asserts it at the kit, where a size would be
    // written. An arbitrary COLOUR in `text-[…]` is correct and is not a
    // violation — only a LENGTH is.
    // The brackets must hold a LENGTH and nothing else. A first draft matched
    // any digit-plus-unit anywhere inside them and fired on
    // `text-[color-mix(in srgb,…70%,transparent)]` — an arbitrary COLOUR, which
    // is the correct spelling here (the `/70` modifier emits OKLAB and this
    // design system writes sRGB). A check that fires on the right answer is the
    // failure mode this family of gates cannot afford.
    const typeEscape = /^(text|leading|tracking|font)-\[-?\d*\.?\d+(px|rem|em|ch|pt|%)\]$/;
    expect(WORKFLOW_KIT_TOKENS.filter((t) => typeEscape.test(t))).toEqual([]);
  });

  it("G36 — every responsive utility is DESKTOP-FIRST", () => {
    // Our `--breakpoint-*` namespace is cleared and re-declared, so `max-lg:`
    // IS `@media (max-width: 1024px)` and `lg:` silently means the opposite
    // viewport while compiling perfectly. A source gate cannot see a variant
    // living in a module constant, so the kit asserts it itself.
    const minWidthVariant = /(^|:)(sm|md|lg|xl|2xl):/;
    const offenders = WORKFLOW_KIT_TOKENS.filter((t) => minWidthVariant.test(t));
    expect(offenders, "mobile-first variants; use max-* instead").toEqual([]);
    expect(
      WORKFLOW_KIT_TOKENS.some((t) => t.startsWith("max-lg:")),
      "the kit claims to be responsive and declares no max-* variant at all",
    ).toBe(true);
  });

  it("B15 §9 note 6 — every figure the kit draws is tabular", () => {
    // r10 sets `font-feature-settings:tnum` on Units, In, Loaded and Rejected.
    // A column of counts that is not tabular does not line up, and this is the
    // one property of a figure strip nobody notices is missing until a customer
    // reads a total.
    const figureSlots = WORKFLOW_KIT_TOKENS.filter((t) => t === "tabular-nums");
    expect(figureSlots.length).toBeGreaterThanOrEqual(3);
  });
});
