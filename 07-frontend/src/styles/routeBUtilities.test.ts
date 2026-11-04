/* ══════════════════════════════════════════════════════════════════════════
 * CR-018 Phase 1 · EVERY CLASS A MIGRATED COMPONENT ASKS FOR MUST BE REAL
 * ══════════════════════════════════════════════════════════════════════════
 *
 * WHY THIS EXISTS — G31's rule stops being true on the first migrated file
 * ------------------------------------------------------------------------
 * `10-scripts/gates/g31_declared_classes.py` refuses a component that names a
 * class no stylesheet declares. That gate closed a defect that recurred SIX
 * times in five months (DEF-244, DEF-305, DEF-308, DEF-314, DEF-315, DEF-327)
 * and its ratchet sits at 0.
 *
 * Route B breaks its PREMISE, not its usefulness. A utility is declared by the
 * COMPILER, not by a `.css` file, so the moment one component's markup reads
 * `flex items-end gap-3` G31 reports 25 undeclared classes and goes red on a
 * correct migration. Measured on this very screen, 2026-08-19: `0 → 25`.
 *
 * ⚠ THE CR PLANNED FOR THIS AT THE WRONG END. CR-018 §4.3 and the Route B
 * ruling both say G31 "becomes meaningless" and is retired at the END of
 * Phase 3, when there are no bespoke classes left. In fact it goes RED at the
 * START, on component 1 of 127. That is reported, not worked around.
 *
 * WHAT THIS ASKS, AND WHY IT IS STRICTER THAN THE GATE IT REPLACES
 * ---------------------------------------------------------------
 * For every file in `route-b-migrated.txt`, every class token in its markup
 * must EITHER be declared by a stylesheet (the shared classes a migrated file
 * still keeps — `card`, `btn`, `rating-tab`) OR compile to a real rule through
 * the ACTUAL Tailwind compiler, loaded from `node_modules` and handed this
 * app's own `tailwind.css`.
 *
 * That is strictly more than G31 could ever ask. G31 knows the name `flex` is
 * absent from the stylesheets and nothing more; it cannot tell `items-end`
 * from `itmes-end`, and under Route B a typo'd utility is the SAME defect as
 * an undeclared class — it renders nothing, tsc passes, eslint passes and
 * `toHaveClass()` passes. This asks Tailwind, so it knows.
 *
 * It also catches the two failure modes Phase 0 recorded but could not gate:
 *   · a utility whose theme key was cleared or renamed — `text-lg` and
 *     `bg-red-500` do not compile here, by construction, and if a Phase 2 lane
 *     writes one it fails on this file rather than on a screenshot;
 *   · a class name BUILT by interpolation, which Tailwind's scanner cannot
 *     see. `svc-${card.service}` is invisible to the compiler, so it must stay
 *     a stylesheet class — and this test says so out loud rather than leaving
 *     the next lane to rediscover it through 55 transparent swatches.
 *
 * IT RUNS IN `npm test`, WHICH IS WHERE IT CAN RUN
 * ------------------------------------------------
 * `.github/workflows/gates.yml` installs Python and NOTHING ELSE — no node, no
 * `npm ci`. A Python gate therefore cannot ask the Tailwind compiler anything.
 * `ci-frontend.yml` does `npm ci` and then `npm test`, so this is the only
 * place in the repo where the compiler is reachable by a merge-blocking check.
 * Putting it anywhere else would be a gate that never runs — the failure this
 * repo has recorded three times (G26, G27, DEF-323).
 * ══════════════════════════════════════════════════════════════════════════ */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";

// Node's own modules, reached the way `tailwindTheme.test.ts` next door does:
// the test environment is not jsdom here, but the string-split import keeps
// both files identical in shape and keeps Vite from trying to pre-bundle them.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string, o: { withFileTypes: true }): { name: string; isDirectory(): boolean }[];
  existsSync(p: string): boolean;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
  relative(a: string, b: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};
const nodeModule = (await import(/* @vite-ignore */ ["node", "module"].join(":"))) as {
  createRequire(p: string): { resolve(id: string): string };
};

const STYLES = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.dirname(STYLES);

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
    const full = nodePath.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

/*
 * DEF-INT-3580 · DEF-INT-3621 · DEF-INT-3630 (2026-09-03): this suite was RED at
 * the tip for a day on features/integrations/IntegrationsTab.tsx — twelve
 * `slate-*`, `bg-white` and `text-lg` utilities the theme zeroes — and nothing in
 * the merge gate runs it, so the grid shipped with no card surface and no state
 * colour while tsc, eslint and every toContain assertion passed. CR-069 wave B
 * mapped both integrations screens onto the theme's tokens and ran this file as
 * part of its proof; G31 reads class NAMES and cannot know a token is undeclared,
 * which is why this suite is the only check that saw it.
 */
const ALL_FILES = walk(SRC);

/** The ledger — the ONE list both this file and G31 read (hard-won law 5). */
const LEDGER_ENTRIES = nodeFs
  .readFileSync(nodePath.join(STYLES, "route-b-migrated.txt"), "utf8")
  .split("\n")
  .map((line) => line.trim())
  .filter((line) => line !== "" && !line.startsWith("#"));

/**
 * A trailing `/` names a DIRECTORY: every `.ts`/`.tsx` beneath it, tests
 * excluded — CR-068 wave A (2026-09-03), for the customer portal's own root.
 * G31's `route_b_migrated()` expands it the same way. A file born under
 * `portal/` is owned by this check from its first commit, which is the only
 * shape that closes DEF-974's trap rather than re-arming it per file.
 */
const MIGRATED = LEDGER_ENTRIES.flatMap((entry) => {
  if (!entry.endsWith("/")) return [entry];
  const folder = nodePath.join(SRC, entry);
  if (!nodeFs.existsSync(folder)) return [entry]; // reported by the existence test below
  return walk(folder)
    .filter((abs) => /\.tsx?$/.test(abs) && !abs.includes(".test."))
    .map((abs) => nodePath.relative(SRC, abs));
});

/* ── The class-name reader ─────────────────────────────────────────────────
 * Deliberately the SAME shape as G31's, including its two hard-won
 * corrections: a comparison operand is a VALUE not a class, and the STATIC
 * chunks of a template literal hold the base class (dropping them is how the
 * gate's first widening lost `rd-source-card`).
 *
 * ⚠ IT WAS A PORT WITH NOTHING KEEPING IT IN STEP, AND AS OF 2026-08-20 IT IS
 * NOT (OQ-277, CLOSED). The regex SOURCES now come from
 * `07-frontend/classname-grammar/patterns.json`, which G31 reads too, so
 * neither reader can be corrected alone. That was not hypothetical: THREE
 * corrections to this grammar had each landed in one language only — the
 * comparison operand (130 reported where 125 were real), the interpolated
 * template (871 -> 870, LOSING `is-selected` and `is-blocked` while gaining a
 * false name, which reads as an improvement), and G34's newline anchor.
 *
 * ⚠ SHARING THE PATTERNS IS ONLY HALF, AND IT IS THE SMALLER HALF. Not one of
 * those three bugs was a wrong character of regex; all three were in the code
 * AROUND it. So both readers also run the same golden corpus — this one in the
 * test below, G31's in `grammar_corpus_selftest()`, each in its own workflow,
 * neither needing the other's runtime. Sharing catches textual drift; the
 * corpus catches semantic drift.
 *
 * `TOKEN` is deliberately NOT shared. This reader asks "could Tailwind compile
 * this candidate?" and must accept `sm:foo` and `text-[13px]`; G31 asks "could
 * a stylesheet declare this name?" and must reject them forever, or it reports
 * every utility as an undeclared class and gets switched off (DEF-323).
 * Merging the two breaks one. Unshared is not unwatched: corpus case C10 gives
 * the divergence an exact size of one token, asserted on both sides.
 * ──────────────────────────────────────────────────────────────────────── */
const FRONTEND = nodePath.dirname(SRC);
const GRAMMAR = nodePath.join(FRONTEND, "classname-grammar");
const PATTERNS = JSON.parse(
  nodeFs.readFileSync(nodePath.join(GRAMMAR, "patterns.json"), "utf8"),
) as {
  forbidden_constructs: { literal: string; kind: string; why: string }[];
  patterns: Record<
    string,
    { source: string; group_count: number; probes: { input: string; matches: (string | null)[][] }[] }
  >;
  not_shared: { token: { typescript: { source: string } } };
};

/** Split a regex source into its bare metacharacters and its escape pairs.
 *
 * ⚠ THE NAIVE VERSION OF THIS IS WRONG AND FAILS LOUDLY ON ITS FIRST RUN — a
 * substring search for `^` fires on `[^"]*`, which every pattern here uses, and
 * one for `$` fires on the escaped `\$\{` of `interpolation`. So
 * character-class BODIES and ESCAPE PAIRS are skipped: `^`/`$` are refused only
 * as bare anchors, `\A`/`\Z` only as escapes. Written identically as
 * `_bare_and_escapes()` in `g31_declared_classes.py` — the one piece of shared
 * logic `patterns.json` cannot express as data. */
function bareAndEscapes(src: string): { bare: string; escapes: Set<string> } {
  let bare = "";
  const escapes = new Set<string>();
  let i = 0;
  let inClass = false;
  while (i < src.length) {
    const ch = src[i];
    if (ch === "\\" && i + 1 < src.length) {
      escapes.add(src.slice(i, i + 2));
      i += 2;
      continue;
    }
    if (inClass) {
      inClass = ch !== "]";
      i += 1;
      continue;
    }
    if (ch === "[") {
      inClass = true;
      i += 1;
      continue;
    }
    bare += ch;
    i += 1;
  }
  return { bare, escapes };
}

/** Compile one SHARED pattern, refusing anything Python cannot read the same
 *  way. An anchor is the likeliest way for these two readers to drift while
 *  both look correct — Python's `$` matches before a trailing newline and JS's
 *  does not, and `^\s*` spanning a newline is the G34 bug verbatim. */
function shared(name: string): RegExp {
  const src = PATTERNS.patterns[name].source;
  const { bare, escapes } = bareAndEscapes(src);
  for (const banned of PATTERNS.forbidden_constructs) {
    const hit = banned.kind === "escape" ? escapes.has(banned.literal) : bare.includes(banned.literal);
    if (hit) {
      throw new Error(
        `shared pattern "${name}" contains "${banned.literal}", which patterns.json forbids — ${banned.why}`,
      );
    }
  }
  return new RegExp(src, "g");
}

const CLASSNAME = shared("classname");
const COMPARISON = shared("comparison");
const QUOTED = shared("quoted");
const TEMPLATE = shared("template");
const INTERPOLATION = shared("interpolation");
const TOKEN = new RegExp(PATTERNS.not_shared.token.typescript.source);
const KIT_CONSTANT = shared("kit_constant");
/** `shared_rules.kit_string_is_all_or_nothing` — see `kitTokens` below. */
const UTILITY_SHAPED = /^[a-z0-9]\S*$/;

function kitTokens(text: string): string[] {
  /** The TypeScript twin of `kit_tokens()` in
   *  `10-scripts/gates/g31_declared_classes.py`. Keep the two bodies in the
   *  same shape — a reader comparing them line by line is how the 871 -> 870
   *  bug was found.
   *
   *  All-or-nothing per string: a constant holding prose contributes NOTHING
   *  rather than contributing its lowercase words, so `const LABEL = "Save
   *  changes"` cannot leak `changes` in as a class name. A false positive here
   *  would report ordinary copy as undeclared and get the grammar switched off
   *  (DEF-323, one register over). */
  const found: string[] = [];
  for (const m of text.matchAll(KIT_CONSTANT)) {
    // ⚠ The same comparison strip classTokens does. Leaving it out was
    // historical bug 1 in a new reader: `variant === "link"` inside a kit
    // constant contributed `link` and `ghost` as utilities.
    const body = (m[1] ?? "").replace(COMPARISON, " ");
    for (const q of body.matchAll(QUOTED)) {
      // ⚠ A QUOTED OBJECT KEY IS NOT A UTILITY. `{ "settings-row": "px-[6px]" }`
      // holds a key that is perfectly utility-SHAPED, so the all-or-nothing
      // rule cannot tell it from a class — position can. Found by this check
      // on the real buttonKit.ts: `settings-row`, `link`, `ghost`.
      // A key is `{ "k": v }` or `, "k": v` — PRECEDED by a brace or comma AND
      // followed by a colon. Both halves are needed: a ternary `? "a" : "b"` is
      // also followed by a colon. Caught by corpus case C16.
      const at = q.index ?? 0;
      if (/^\s*:/.test(body.slice(at + q[0].length)) && /[{,]\s*$/.test(body.slice(0, at))) continue;
      const blob = q[1] ?? q[2];
      if (!blob) continue;
      const tokens = blob.split(/\s+/).filter(Boolean);
      if (tokens.length === 0) continue;
      if (!tokens.every((t) => UTILITY_SHAPED.test(t) && !t.includes("://"))) continue;
      found.push(...tokens);
    }
  }
  return found;
}

function classTokens(text: string): string[] {
  const found: string[] = [];
  for (const m of text.matchAll(CLASSNAME)) {
    const blobs: string[] = [];
    if (m[1] !== undefined) {
      blobs.push(m[1]);
    } else {
      const expr = (m[2] ?? "").replace(COMPARISON, " ");
      for (const lit of expr.matchAll(QUOTED)) {
        const v = lit[1] ?? lit[2];
        if (v !== undefined && v !== "") blobs.push(v);
      }
      for (const tpl of expr.matchAll(TEMPLATE)) {
        blobs.push(...(tpl[1] ?? "").split(INTERPOLATION));
      }
    }
    for (const blob of blobs) {
      for (const token of blob.split(/\s+/)) {
        // A token ending in `-` is a PREFIX an interpolation completes
        // (`svc-${service}`), never a class name — G31's rule, kept.
        if (token === "" || token.endsWith("-")) continue;
        if (TOKEN.test(token)) found.push(token);
      }
    }
  }
  return [...new Set(found)];
}

/** Every `.name` any stylesheet under src/ declares — G31's "declared" set. */
const declared = (() => {
  const names = new Set<string>();
  for (const path of ALL_FILES) {
    if (!path.endsWith(".css")) continue;
    const css = nodeFs.readFileSync(path, "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");
    for (const m of css.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)) names.add(m[1]);
  }
  return names;
})();

/** The compiler, asked once, with every candidate at once.
 *
 *  ⚠ `compile()` RETURNS A STATEFUL BUILDER AND `build()` IS CUMULATIVE — a
 *  second call re-emits everything the first call produced. Measured while
 *  writing this: calling `build([x])` in a loop reported `itmes-end` as valid
 *  because the previous candidate's rule was still in the output. One call
 *  with all candidates, then read the SELECTORS, is the only reading that is
 *  a fact about the candidate rather than about call order. */
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
  // Tailwind escapes `[`, `]`, `/`, `.`, `%`, `:` and friends in the selector
  // it emits (`.text-\[13px\]`). Unescaping the OUTPUT is exact; re-deriving
  // the escaping here would be a second implementation of someone else's rule.
  //
  // ⚠ AND THE SELECTOR IS THEN MATCHED WHOLE, NOT SPLIT ON PUNCTUATION. The
  // first draft harvested selectors with `\.([^\s,{}]+)` and reported
  // `grid-cols-[repeat(auto-fill,minmax(320px,1fr))]` as generating nothing —
  // because the COMMAS INSIDE `minmax(320px,1fr)` look exactly like the commas
  // between selectors in a selector list. A false positive on a utility that
  // works perfectly is the failure mode this whole family of gates cannot
  // afford (DEF-323: a gate with a false positive gets switched off), so the
  // candidate is looked for as a literal with a boundary after it instead.
  const css = compiler.build(candidates).replace(/\\/g, "");
  const out = new Set<string>();
  for (const candidate of candidates) {
    const escaped = candidate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    // The boundary keeps `flex` from matching `.flex-col`.
    if (new RegExp(`\\.${escaped}(?=[\\s{,:>~+]|$)`).test(css)) out.add(candidate);
  }
  return out;
}

/* ══════════════════════════════════════════════════════════════════════════
 * OQ-277 · THE OTHER READER OF THIS GRAMMAR IS A PYTHON GATE THAT CANNOT RUN
 * HERE, AND THIS IS HOW THE TWO ARE HELD TOGETHER
 * ══════════════════════════════════════════════════════════════════════════
 * Two assertions, and they catch different things:
 *   · the PROBES prove each shared pattern still means in JS what it means in
 *     Python — the expected matches below were produced by Python `re` and
 *     asserted here unchanged. Textual/engine drift.
 *   · the CORPUS proves this reader still EXTRACTS what the ruled answer says —
 *     the same fixture G31 runs, the same expected file. Semantic drift, which
 *     is what all three historical bugs actually were.
 * Neither needs Python. G31's half runs in `gates.yml` and needs no node. If
 * either reader drifts, its OWN workflow goes red.
 * ══════════════════════════════════════════════════════════════════════════ */
describe("OQ-277 · the className grammar is one source, read the same by both readers", () => {
  it("every shared pattern matches in JS exactly what it matched in Python", () => {
    for (const [name, spec] of Object.entries(PATTERNS.patterns)) {
      const rx = new RegExp(spec.source, "g");
      for (const probe of spec.probes) {
        const got = [...probe.input.matchAll(rx)].map((m) => {
          const row: (string | null)[] = [m[0]];
          for (let i = 1; i <= spec.group_count; i++) row.push(m[i] === undefined ? null : m[i]);
          return row;
        });
        expect(got, `pattern "${name}" on probe ${JSON.stringify(probe.input)}`).toEqual(
          probe.matches,
        );
      }
    }
  });

  it("the golden corpus extracts exactly the ruled set", () => {
    const expected = JSON.parse(
      nodeFs.readFileSync(nodePath.join(GRAMMAR, "corpus.expected.json"), "utf8"),
    ) as {
      shared_expected: string[];
      utility_reader_only: string[];
      must_not_find: string[];
      cases: { id: string; finds: string[]; rejects: string[]; guards: string }[];
    };
    const got = new Set(classTokens(nodeFs.readFileSync(nodePath.join(GRAMMAR, "corpus.tsx"), "utf8")));

    // Case by case FIRST: a set diff does not tell a reader WHICH of the ten
    // old bugs just came back, and that sentence is the whole value of the
    // corpus when it fails at 3am.
    for (const c of expected.cases) {
      for (const name of c.finds) {
        expect(got.has(name), `corpus case ${c.id} lost "${name}" — ${c.guards}`).toBe(true);
      }
      for (const name of c.rejects) {
        expect(got.has(name), `corpus case ${c.id} wrongly found "${name}" — ${c.guards}`).toBe(
          false,
        );
      }
    }
    for (const name of expected.must_not_find) {
      expect(got.has(name), `"${name}" is on must_not_find and was reported as a class`).toBe(false);
    }

    // SET EQUALITY, not `contains`. The 871 -> 870 bug GAINED a name while
    // losing two, so any assertion that only looks for what it expects passes
    // it. This reader's sanctioned extra is `utility_reader_only` — the TOKEN
    // divergence, one token wide, which is the only thing patterns.json does
    // not share.
    const want = [...expected.shared_expected, ...expected.utility_reader_only].sort();
    expect([...got].sort(), "the corpus extraction is not the ruled set").toEqual(want);
  });
});

describe("CR-018 Route B · a migrated component's classes are all real", () => {
  it("the ledger names files that exist, and is not empty", () => {
    // Without this the whole suite is a loop over nothing that reports itself
    // as a pass — DEF-057's shape, and the reason CR-016's walk carries the
    // same guard.
    expect(MIGRATED.length).toBeGreaterThan(0);
    for (const rel of MIGRATED) {
      expect(nodeFs.existsSync(nodePath.join(SRC, rel)), `${rel} is on the ledger and absent`).toBe(
        true,
      );
    }
  });

  it("every utility a KIT names in a constant compiles (OQ-280)", async () => {
    // ⚠ THIS IS THE CHECK PHASE 3 PROVED WAS MISSING. It planted
    // `itmes-center` in buttonKit.ts and got 5 passed here and PASS / 0
    // undeclared from G31 — because BOTH readers extract from `className=`
    // and a component kit keeps its utilities in module-level constants.
    // Phase 3 also established that shared classes MUST become components
    // (repeating utilities at 250 sites gave 540 differing properties), so
    // this is the shape all 173 shared classes are heading into.
    const asked = new Map<string, string>();
    // ⚠ ALL_FILES holds ABSOLUTE paths (walk(SRC)), unlike MIGRATED which holds
    // ledger-relative ones. Joining SRC onto these double-prefixes the path.
    for (const abs of ALL_FILES.filter((f) => f.endsWith("Kit.ts"))) {
      const rel = nodePath.relative(SRC, abs);
      for (const token of kitTokens(nodeFs.readFileSync(abs, "utf8"))) {
        if (!asked.has(token)) asked.set(token, rel);
      }
    }
    expect(asked.size, "no kit constants found at all — has the convention moved?").toBeGreaterThan(10);

    const candidates = [...asked.keys()];
    const generated = await generatedSelectors(candidates);
    const orphans = candidates
      .filter((token) => !generated.has(token) && !declared.has(token))
      .map((token) => `${token} (named by ${asked.get(token) ?? "?"})`);

    expect(
      orphans,
      "a kit names these and Tailwind generates no rule for them — a typo here renders NOTHING and every other check passes",
    ).toEqual([]);
  });

  it("every tone StatusPill can render compiles — the shared pills, which NEITHER reader above sees (DEF-722)", async () => {
    // ⚠ THIS IS A THIRD BLIND SPOT, FOUND BY WALKING INTO IT (2026-08-26).
    // `StatusPill` is in the ledger, so the test above reads it — and finds
    // only `pill`. Its markup is `className={`pill ${TONE_CLASS[props.tone]}`}`
    // and the tone utilities live in a module-level constant, which is exactly
    // the OQ-280 shape the kit check was written for. But that check scans
    // files named `*Kit.ts`, and this is `StatusPill.tsx`; and `kitTokens`
    // matches `const NAME = …`, while this constant is annotated
    // (`const TONE_CLASS: Record<StatusTone, string> = …`), so the pattern does
    // not reach it either. Net: since CR-018 deleted `StatusPill.css` and
    // ported its rules to `bg-success-100 text-success-700` and friends, NO
    // check in this repo has asked whether those utilities exist. Measured by
    // deleting `--color-info-100` / `--color-info-700` from the `@theme` block:
    // this file stayed green over a pill rendering no colour at all.
    //
    // Asked here through the RENDER rather than through the source, because
    // what has to compile is the class attribute that reaches the DOM. Every
    // shared component that keeps utilities in an annotated constant has the
    // same hole; this closes the one the tone palette depends on and the rest
    // is reported rather than quietly widened.
    const tones: StatusTone[] = ["success", "warning", "danger", "info", "neutral", "muted"];
    const asked = new Set<string>();
    for (const tone of tones) {
      const html = renderToStaticMarkup(createElement(StatusPill, { tone, children: "x" }));
      const attr = /class="([^"]*)"/.exec(html);
      expect(attr, `StatusPill(${tone}) rendered no class attribute`).not.toBeNull();
      for (const token of (attr?.[1] ?? "").split(/\s+/).filter(Boolean)) asked.add(token);
    }
    const candidates = [...asked];
    const generated = await generatedSelectors(candidates);
    const orphans = candidates.filter((t) => !generated.has(t) && !declared.has(t));
    expect(
      orphans,
      "StatusPill renders these and nothing declares or generates them — the pill draws no colour and every other check passes",
    ).toEqual([]);
  });

  it("the kit corpus extracts exactly the ruled set, and no prose (OQ-280)", () => {
    const expected = JSON.parse(
      nodeFs.readFileSync(nodePath.join(GRAMMAR, "corpus.expected.json"), "utf8"),
    ) as { kit_constant_expected: string[] };
    const got = new Set(
      kitTokens(nodeFs.readFileSync(nodePath.join(GRAMMAR, "corpus.tsx"), "utf8")),
    );
    const want = new Set<string>(expected.kit_constant_expected);
    // Set equality, for the 871 -> 870 reason: that bug GAINED a name while
    // losing two, and every assertion that only looks for what it expects
    // passed it.
    expect([...got].sort(), "the kit reader drifted from the ruled set").toEqual([...want].sort());
  });

  it("every class token compiles as a utility or is declared by a stylesheet", async () => {
    const asked = new Map<string, string>(); // token -> the file that asks
    const askedIn = new Map<string, Set<string>>(); // token -> every file that asks
    for (const rel of MIGRATED) {
      for (const token of classTokens(nodeFs.readFileSync(nodePath.join(SRC, rel), "utf8"))) {
        if (!asked.has(token)) asked.set(token, rel);
        (askedIn.get(token) ?? askedIn.set(token, new Set()).get(token)!).add(rel);
      }
    }
    expect(asked.size, "a migrated file that asks for no classes at all").toBeGreaterThan(10);

    const candidates = [...asked.keys()];
    const generated = await generatedSelectors(candidates);

    // ⚠ THE TWO MARKER CLASSES, AND WHY THE RULE ABOVE IS FALSE FOR EXACTLY
    // THESE TWO (DEF-569, 2026-08-22). `peer` and `group` are Tailwind's
    // relationship markers: they generate NO rule of their own — by design,
    // there is nothing to declare — and they are read by the VARIANTS that
    // name them, `peer-checked:bg-accent` compiling to
    // `.peer-checked\:bg-accent:is(:where(.peer):checked ~ *)`. So this test's
    // premise ("a token that generates no rule renders nothing") is wrong here
    // and only here: strike them out and the checkbox's checked, hover and
    // focus states silently stop working.
    //
    // THE ALLOWANCE IS NOT A HOLE, because a marker with no variant reading it
    // IS dead markup — the exact defect this file exists to catch. So a marker
    // is forgiven only in a file that also asks for a `<marker>-…` variant
    // WHICH ITSELF COMPILES. `peer` alone stays an orphan; `peer` beside a
    // typo'd `peer-checekd:bg-accent` stays an orphan, because the typo
    // generates nothing either. Both were planted and both went RED before this
    // was trusted green.
    const MARKERS = new Set(["peer", "group"]);
    const earnsItsPlace = (token: string) =>
      MARKERS.has(token) &&
      [...(askedIn.get(token) ?? [])].some((file) =>
        candidates.some(
          (other) =>
            other.startsWith(`${token}-`) &&
            generated.has(other) &&
            (askedIn.get(other) ?? new Set()).has(file),
        ),
      );

    const orphans = candidates
      .filter((token) => !generated.has(token) && !declared.has(token) && !earnsItsPlace(token))
      .map((token) => `${token} (asked for by ${asked.get(token) ?? "?"})`);

    expect(
      orphans,
      "these render NOTHING: no stylesheet declares them and Tailwind generates no rule for them",
    ).toEqual([]);
  });

  it("every custom property an arbitrary value names is one the theme declares", async () => {
    // THE HALF THE ORPHAN CHECK ABOVE CANNOT ASK, AND IT IS THE SAME SHAPE AS
    // EVERY OTHER HOLE RECORDED IN THIS FILE: a check reporting truthfully over
    // a scope it does not cover.
    //
    // That check asks Tailwind *does this token compile?* — and an ARBITRARY
    // value always does. `bg-[color-mix(in_srgb,var(--color-danger)_6%,transparent)]`
    // compiles to a perfectly good rule; it is the BROWSER that then drops the
    // declaration, because `--color-danger` is declared nowhere in this repo.
    // So the token is not an orphan, the test is not lying, and the background
    // is invisible.
    //
    // MEASURED, 2026-09-12, on `AssetDetailPage`'s attention strip — the one
    // element on that screen whose whole job is to be noticed. It asked for
    // `border-l-danger`, `text-danger` AND that background: the first two were
    // named by the orphan check (`DEF-SHL-5088`), the third was not, and all
    // three failed together, so the danger state rendered identically to the
    // calm one. `var(--color-danger)` was the only use in the codebase, and the
    // tone scale it meant is `--color-danger-100/500/700`.
    //
    // ⚠ WHAT WOULD MAKE THIS PASS WRONGLY (law 7's second habit): reading the
    // declared set from the STYLESHEETS alone. Tailwind's `@theme` keys reach
    // the page as `:root` custom properties emitted by the COMPILER, so half
    // the real answers are not in any `.css` file as a plain declaration. Both
    // sources are read below, and the test was shown red with the compiler half
    // removed — it then named 30+ properties that do exist.
    // ⚠ READ FROM THE WHOLE SOURCE WITH ITS COMMENTS STRIPPED, NOT FROM THE
    // CLASS TOKENS — and that is a correction to this check's first draft, made
    // before it was trusted. A property reference is not a class token: it can
    // sit in a kit constant, and an ANNOTATED constant escapes BOTH readers
    // this file owns (`kitTokens` matches `const NAME = …` and not
    // `const NAME: Type = …`, as the comment on the StatusPill case above
    // records). `components/WarningBox.tsx` holds exactly that shape — a
    // `Record<Tone, string>` of tinted rails — and it is where this same
    // mistake was found on 2026-09-08 by a lane READING A SCREENSHOT, because
    // no check could see it. Scanning class tokens alone would have left the
    // one file with the known history outside the guard.
    //
    // Comments are stripped first, for the reason the rest of this fix records
    // at three call sites: a comment explaining a dead name is read as a use of
    // it, and `WarningBox.tsx` names the very property that was wrong there in
    // the comment that explains the repair. Stripping is what lets a defect be
    // documented where it happened.
    const stripComments = (source: string) =>
      source.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
    // ⚠ A REFERENCE CARRYING A FALLBACK IS NOT A BUG, AND THIS IS THE FALSE
    // ACCUSATION THE FIRST DRAFT MADE — found by asking law 7's second habit of
    // this check rather than of somebody else's. `var(--doc-max-h,28rem)` in
    // `notifications/notificationsKit.ts` names a property NOTHING declares on
    // purpose: `TemplateDetail.tsx` MEASURES a height in the browser and sets
    // it as an inline style, so the property exists only at runtime and the
    // fallback is what the box uses until it does. The CSS is valid either way,
    // which is the whole difference from the two real defects this case was
    // written for — both of those named a property with NO fallback, so the
    // browser had nothing to fall back TO and dropped the declaration.
    // So the rule is: a bare `var(--x)` must be declared; `var(--x, …)` need
    // not. Narrowing it this way was preferred to allow-listing the property,
    // because the fallback is the author stating the absence is expected.
    const referenced = new Map<string, string>(); // property -> the file naming it
    for (const rel of MIGRATED) {
      const source = stripComments(nodeFs.readFileSync(nodePath.join(SRC, rel), "utf8"));
      // The capture stops at `)` or `,`: a comma means a fallback follows.
      for (const m of source.matchAll(/var\(\s*(--[\w-]+)\s*([,)])/g)) {
        if (m[2] === ",") continue;
        if (!referenced.has(m[1])) referenced.set(m[1], rel);
      }
    }
    // Law 7's third habit: the output has to distinguish a pass from an EMPTY
    // SCOPE to a reader, so the size is asserted rather than assumed. ⚠ The
    // first draft of this line guessed 60 and the assertion caught the guess:
    // the ledger's 298 entries expand to 385 files naming 23 properties, of
    // which 14 appear ONLY in prose — so 9 reach CSS. A floor rather than the
    // exact number, because the count moves with ordinary work and an equality
    // here would be a test about churn rather than about coverage.
    expect(
      referenced.size,
      "no custom property is named anywhere in the ledger's files — the scan found nothing to check",
    ).toBeGreaterThan(5);

    // Source one: every `--name:` a stylesheet declares. A namespace clear
    // (`--color-*: initial`) is not a declaration and does not match, because
    // `*` is not a name character.
    const declaredProps = new Set<string>();
    for (const path of ALL_FILES) {
      if (!path.endsWith(".css")) continue;
      const css = nodeFs.readFileSync(path, "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");
      for (const m of css.matchAll(/(--[\w-]+)\s*:/g)) declaredProps.add(m[1]);
    }
    // Source two: what the compiler emits into `:root` from the `@theme` block.
    // Asked with one real candidate so the build is not empty.
    const emitted = await generatedSelectors(["text-base"]);
    void emitted; // the selectors are not the answer; the emitted CSS is
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
        const resolved = require_.resolve(id);
        return { path: resolved, base: nodePath.dirname(resolved), content: nodeFs.readFileSync(resolved, "utf8") };
      },
    });
    for (const m of compiler.build(["text-base"]).matchAll(/(--[\w-]+)\s*:/g)) declaredProps.add(m[1]);
    // Source three: a property this tree SETS ITSELF, through an inline style
    // object — `{ "--brand": tenant.colour }`. It is declared by code rather
    // than by a sheet, and a screen carrying a tenant's own colour is the
    // reason that door exists at all.
    for (const abs of ALL_FILES) {
      if (!/\.tsx?$/.test(abs) || abs.includes(".test.")) continue;
      for (const m of nodeFs.readFileSync(abs, "utf8").matchAll(/["'](--[\w-]+)["']\s*:/g)) {
        declaredProps.add(m[1]);
      }
    }

    const unknown = [...referenced.entries()]
      .filter(([prop]) => !declaredProps.has(prop))
      .map(([prop, rel]) => `${prop} (named by ${rel})`);
    expect(
      unknown,
      "these custom properties are named in an arbitrary value and declared nowhere — the declaration reaches the browser and is DROPPED, so the utility compiles and renders nothing",
    ).toEqual([]);
  });

  it("the cleared namespaces really are unreachable from a migrated file", async () => {
    // B14 rules 5 and 20 by construction (Phase 0 §3). This is the same claim
    // the specimen page proves by rendering, asserted here at the compiler so
    // it also runs in CI, where there is no browser.
    //
    // ⚠ `text-base` AND `text-xs` LEFT THIS LIST ON 2026-08-19, AND THE REASON
    // IS A RULING, NOT A RELAXATION. When Phase 0 wrote it, clearing `--text-*`
    // deleted every one of Tailwind's own sizes and nothing re-declared those
    // NAMES, so `text-base` meant "Tailwind's 16px, which B14 never ratified".
    // The type scale is now ruled (decision log 2026-08-19, "THE TYPE SCALE IS
    // RULED — OQ-275 and OQ-276 CLOSED", commit 4b6baa6) and four of those
    // names answer to OUR steps: xs 11px, sm 12px, base 13px, md 14px. The
    // namespace is still cleared first and Tailwind's sizes are still gone —
    // which is what the sizes remaining on this list check. The test below
    // checks the other half, that what answers to the name is the ruled figure.
    const dead = ["text-lg", "text-xl", "text-2xl", "text-9xl", "bg-red-500", "bg-blue-500", "shadow-2xl", "font-sans"];
    const generated = await generatedSelectors(dead);
    expect([...generated].filter((c) => dead.includes(c))).toEqual([]);
  });

  it("the four small-text utilities emit the RULED px, not Tailwind's rem", async () => {
    // The half that a "generates nothing" check can never ask. `text-base`
    // exists again, so the danger is no longer that it renders nothing — it is
    // that it renders 1rem/16px, Tailwind's own value, and every 13px panel
    // body in Phase 3 silently grows three pixels with every gate green.
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
        const resolved = require_.resolve(id);
        return {
          path: resolved,
          base: nodePath.dirname(resolved),
          content: nodeFs.readFileSync(resolved, "utf8"),
        };
      },
    });
    const css = compiler.build(["text-xs", "text-sm", "text-base", "text-md", "text-display"]).replace(/\\/g, "");
    // Both halves, because either alone passes a sabotage the other catches:
    // the RULE has to read the token (not a baked literal), and the token the
    // compiler emits into `:root` has to be the ruled figure (not Tailwind's
    // 1rem). Proved by setting `--text-base: 1rem` in tailwind.css — the first
    // half alone passed it, and this line failed naming 1rem.
    const emitted = new Map<string, string>();
    for (const m of css.matchAll(/(--text-[a-z0-9-]+)\s*:\s*([^;]+);/g)) emitted.set(m[1], m[2].trim());
    for (const [utility, token, px] of [
      ["text-xs", "--text-xs", "11px"],
      ["text-sm", "--text-sm", "12px"],
      ["text-base", "--text-base", "13px"],
      ["text-md", "--text-md", "14px"],
      ["text-display", "--text-display", "56px"],
    ] as const) {
      const rule = new RegExp(`\\.${utility}\\s*\\{([^}]*)\\}`).exec(css);
      expect(rule, `${utility} generated no rule at all`).not.toBeNull();
      expect(rule?.[1], `${utility} does not read ${token}`).toContain(`var(${token})`);
      expect(emitted.get(token), `${utility} resolves to the wrong size`).toBe(px);
    }
  });

  it("an INTERPOLATED class name cannot be a utility, and the app no longer has one", () => {
    // ⚠ THIS ASSERTION WAS INVERTED ON 2026-08-21 (DEF-441), AND THE INVERSION
    // IS THE POINT. It used to read `expect(source).toContain("svc-${card.
    // service}")` — the app's ONE runtime-assembled class name, in
    // RateSchedulesTab's card grid, kept as a stylesheet class because Tailwind
    // generates only what its scanner can SEE in source text (Phase 0: 55 of 76
    // checks first came back transparent for exactly this).
    //
    // The card grid is gone — r10 line 764 draws a nine-column table — and its
    // `<span className={`rating-tag svc-${card.service}`}>` went with it. The
    // Svc column uses the shared `ServiceTags`, which carries the service colour
    // in a `style` attribute reading a `--color-service-*` TOKEN. A token is
    // invisible to the scanner in a way a class name is not, which is why that
    // component needs no stylesheet class at all.
    //
    // So the guard now protects the STRONGER property: no component may
    // reintroduce an assembled class name. That is a real rule with a real
    // failure mode (a silently transparent element), and it is checkable across
    // the whole tree rather than in one file.
    // ⚠ SCOPED TO THE MIGRATED LEDGER, AND THAT IS NOT A WEAKENING. The rule is
    // "an interpolated class name cannot be a UTILITY" — it bites only where the
    // Tailwind compiler is the thing that has to see the name. A file still
    // using stylesheet classes may legitimately assemble one (`skeleton-${
    // variant}` in StateFrame.tsx, with all four rules declared in
    // StateFrame.css), and G31 already answers for those. Running this over the
    // whole tree named 13 innocent files, which is how a check gets switched off.
    const offenders: string[] = [];
    for (const relative of MIGRATED.filter((line) => line.endsWith(".tsx"))) {
      const file = nodePath.join(SRC, relative);
      const source = nodeFs.readFileSync(file, "utf8");
      // ⚠ THE CHECK IS NARROWER THAN "a template literal in a className", AND
      // THE FIRST DRAFT WAS THE WIDE ONE. It named 19 files, every one of them
      // innocent: `className={`btn ${active ? "on" : "off"}`}` interpolates a
      // whole class LITERAL, which the scanner sees perfectly well. The
      // dangerous form is an interpolation GLUED to the end of a class stem —
      // `svc-${code}` — because there the class NAME itself only exists at
      // runtime and Tailwind never emits a rule for it. So: a `${` immediately
      // preceded by a class-name character.
      if (/className=\{`[^`]*[A-Za-z0-9_-]\$\{/.test(source)) {
        offenders.push(relative);
      }
    }
    expect(
      offenders,
      "a className built at runtime is invisible to Tailwind's scanner — use a token in `style`, or a whole string literal per branch",
    ).toEqual([]);

    // The `.rating-tag.svc-*` rules in PlansRates.css now have NO caller. They
    // are dead CSS, filed as DEF-460 for CR-018 Phase 2 to delete along with the
    // rest of the shared-class sweep; deleting them from here would be a
    // one-caller edit to a shared stylesheet, which is the thing Phase 2 exists
    // to do carefully. Their continued declaration is asserted so the deletion
    // is a DELIBERATE act that turns this line red, not a silent one.
    for (const svc of ["electric", "water", "gas", "sewer", "trash", "broadband"]) {
      expect(
        declared.has(`svc-${svc}`),
        `.svc-${svc} is unreferenced dead CSS (DEF-460) — delete it WITH this assertion, not without it`,
      ).toBe(true);
    }
  });
});
