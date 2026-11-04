/* ══════════════════════════════════════════════════════════════════════════
 * CR-075 wave C · C4 — EVERY CLASS IN THIS SCREEN, ASKED OF THE REAL COMPILER
 * ══════════════════════════════════════════════════════════════════════════
 * WHY, WHEN TWO OTHER CHECKS ALREADY LOOK LIKE THEY COVER IT
 * ----------------------------------------------------------
 * B14 rule 21's migration clause is PER FILE: a Tailwind utility is emitted
 * only for a file the compiler is asked about. `features/runbooks/` is a
 * DIRECTORY entry on `route-b-migrated.txt`, so this file IS asked about and
 * its utilities do compile. That is the first half.
 *
 * The second half is whether the class NAMES exist in this theme at all, and
 * neither existing check can answer it here:
 *
 *   · `G31` reads `className=` attributes only.
 *   · `routeBUtilities.test.ts` reads constants only out of `*Kit.ts` files,
 *     and even there its `kit_constant` grammar requires `=` to follow the
 *     identifier — so `const MARK_TONE: Record<ProgressState, string> = {…}`
 *     matches NOTHING. All three tone maps in `RunWizard.tsx` are that shape.
 *
 * `DEF-SHL-4281` is what that costs: `components/WarningBox.tsx` asks for
 * `border-danger`, a colour this theme does not declare (`--color-danger-500`
 * and `--color-danger-700` exist; a bare `--color-danger` does not), so B14 rule
 * 6's danger tier draws with no colour — with `tsc`, eslint and every
 * `toContain` assertion green over it, because the class IS in the DOM.
 *
 * ⚠ **THE FIVE-TONE MARKER MAP IS EXACTLY THE SHAPE THAT BREAKS THAT WAY.**
 * `RBS-005.2` names its tones as *success-500 · accent · n300 · danger-500 ·
 * n500*, and a lane transcribing them could reasonably write `bg-neutral` or
 * `bg-success` — both of which compile to nothing here.
 *
 * PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (law 7)
 * -----------------------------------------------------
 * `bg-danger` was pasted into `MARK_TONE` and this suite failed by name:
 *     RunWizard.tsx names "bg-danger", which this theme does not compile
 * It also fails, deliberately, if a file stops declaring any class at all — a
 * check that silently covers nothing is the shape it exists to catch.
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

const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.dirname(nodePath.dirname(nodePath.dirname(HERE)));
const STYLES = nodePath.join(SRC, "styles");

/** Named rather than globbed: a glob would silently shrink to zero if the
 *  folder moved, and this suite would then pass over nothing at all. */
const FILES = ["RunWizard.tsx"];

function stripComments(source: string): string {
  // COMMENTS FIRST, and it is not tidiness: this file's own prose quotes
  // `bg-danger` and `border-danger` as examples of classes that do NOT compile,
  // and a reader that read prose would report a file's documentation as broken
  // CSS. A check that reports its own explanation as a failure gets switched
  // off (`DEF-323`).
  return source.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");
}

/**
 * A MESSAGE KEY, which is not a class and never can be.
 *
 * ⚠ **THIS EXCLUSION IS A DECLARED BLIND SPOT AND IT CARRIES A NUMBER**, which
 * is law 7's fifth shape: *a declared blind spot with no number attached is
 * indistinguishable from an empty one*. `TITLE_KEY` and `SUBTITLE_KEY` in
 * `RunWizard.tsx` are UPPER_SNAKE maps of locale keys, so the constant reader
 * below picks them up exactly as it picks up a tone map — and it must, because
 * scoping it to names ending `_TONE` would miss the next tone map somebody
 * calls something else.
 *
 * A dotted lowercase identifier with no bracket, colon or slash cannot be a
 * Tailwind class in this theme: every arbitrary value carries `[` and `]`
 * (`h-[5px]`), every variant carries `:` (`max-lg:`), and no declared utility
 * name contains a dot. The count skipped is asserted below, so this cannot
 * quietly grow into a hole.
 */
const MESSAGE_KEY = /^[a-z][a-zA-Z0-9]*(\.[a-zA-Z][a-zA-Z0-9]*)+$/;

/** Every class token a file asks for, from BOTH homes — the `className`
 *  attributes `G31` reads, and the UPPER_SNAKE constants it cannot. */
function classTokens(raw: string): Set<string> {
  const source = stripComments(raw);
  const found = new Set<string>();
  const add = (text: string) => {
    for (const token of text.replace(/\$\{[^}]*\}/g, " ").split(/\s+/)) {
      // A token ending in `-` is a PREFIX an interpolation completes.
      if (token !== "" && !token.endsWith("-") && /^[a-z][^\s"'`]*$/.test(token)) found.add(token);
    }
  };
  for (const m of source.matchAll(/className=\{?[`"]([^`"]*)[`"]/g)) add(m[1]);
  // The concatenated form this screen uses: `"a b " + "c d " + MAP[x]`.
  for (const m of source.matchAll(/"([a-z0-9:[\]&_-][^"\n]*)"\s*\+/g)) add(m[1]);
  for (const m of source.matchAll(/\+\s*"([a-z0-9:[\]&_-][^"\n]*)"/g)) add(m[1]);
  for (const m of source.matchAll(
    /\bconst\s+([A-Z][A-Z0-9_]*)[^=;]*=\s*(\{[\s\S]*?\n\}|"[^"\n]*"|`[^`\n]*`)/g,
  )) {
    const body = m[2];
    for (const q of body.matchAll(/"([^"\n]*)"|`([^`\n]*)`/g)) {
      const after = (q.index ?? 0) + q[0].length;
      // A QUOTED OBJECT KEY is not a utility — position separates them.
      if (/^\s*:/.test(body.slice(after))) continue;
      const literal = q[1] ?? q[2] ?? "";
      const tokens = literal.split(/\s+/).filter((t) => t !== "");
      // All or nothing per string: a constant holding prose contributes NOTHING
      // rather than its lowercase words.
      if (tokens.length > 0 && tokens.every((t) => /^[a-z0-9$][^\s"'`]*$/.test(t))) add(literal);
    }
  }
  for (const token of [...found]) if (MESSAGE_KEY.test(token)) found.delete(token);
  return found;
}

/** What the exclusion above removed, so the blind spot has a number. */
function messageKeys(raw: string): string[] {
  const all = new Set<string>();
  for (const m of stripComments(raw).matchAll(
    /\bconst\s+([A-Z][A-Z0-9_]*)[^=;]*=\s*\{([\s\S]*?)\n\}/g,
  )) {
    for (const q of m[2].matchAll(/"([^"\n]*)"/g)) if (MESSAGE_KEY.test(q[1])) all.add(q[1]);
  }
  return [...all];
}

/** The compiler, asked ONCE with every candidate. `build()` is cumulative, so
 *  one call per candidate would report a typo as valid because the previous
 *  candidate's rule is still in the output. */
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
  const compiler = await compile(nodeFs.readFileSync(nodePath.join(STYLES, "tailwind.css"), "utf8"), {
    base: SRC,
    loadStylesheet: async (id: string) => {
      const p = require_.resolve(id);
      return { path: p, base: nodePath.dirname(p), content: nodeFs.readFileSync(p, "utf8") };
    },
  });
  const css = compiler.build(candidates).replace(/\\/g, "");
  const out = new Set<string>();
  for (const candidate of candidates) if (css.includes(`.${candidate}`)) out.add(candidate);
  return out;
}

describe("B14 rule 21 — every class this screen asks for compiles in THIS theme", () => {
  it("finds classes to check at all — a suite covering nothing is the defect", async () => {
    for (const file of FILES) {
      const tokens = classTokens(nodeFs.readFileSync(nodePath.join(HERE, file), "utf8"));
      expect(tokens.size, `${file} declared no class at all`).toBeGreaterThan(20);
    }
  });

  it("prints what it SKIPPED beside what it checked (law 7's fifth shape)", () => {
    // Every skipped token is a locale key, and every locale key is asserted to
    // exist by `RunWizard.test.tsx` (which fails if any `runbooks.run.` string
    // survives into the rendered markup). So the two checks together cover the
    // whole of both constants, and neither one silently covers a scope it
    // cannot name.
    const source = nodeFs.readFileSync(nodePath.join(HERE, "RunWizard.tsx"), "utf8");
    const skipped = messageKeys(source);
    // Ten DISTINCT keys across the three maps: `TITLE_KEY` has four (Checking
    // is the title of two phases) and `SUBTITLE_KEY` adds four, its `done`
    // entry being the same string as `TITLE_KEY`'s because that phase reads the
    // run's own headline instead. `LIVE_SUBTITLE_KEY` adds two (2026-10-13,
    // `OQ-WRK-12792`): the two subtitles that would be false over a run that
    // ACTS — *"This check changes nothing"* and *"Nothing has changed"*.
    expect(skipped.length, `skipped ${skipped.length}: ${skipped.join(" ")}`).toBe(10);
    for (const key of skipped) expect(key.startsWith("runbooks.run.")).toBe(true);
  });

  it("compiles every one of them, and names any that does not", async () => {
    const perFile = FILES.map((file) => ({
      file,
      tokens: [...classTokens(nodeFs.readFileSync(nodePath.join(HERE, file), "utf8"))],
    }));
    const all = [...new Set(perFile.flatMap((entry) => entry.tokens))];
    const generated = await generatedSelectors(all);
    const misses = perFile.flatMap((entry) =>
      entry.tokens
        .filter((token) => !generated.has(token))
        .map((token) => `${entry.file} names "${token}", which this theme does not compile`),
    );
    expect(misses, misses.join("\n")).toEqual([]);
  });
});
