// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-4742 (2026-09-10) — ten catalogue keys existed in ZERO of the
//          eleven languages and rendered hardcoded English to every tenant,
//          permanently, with nothing anywhere going red.
// Rules:   B14 rule 35 (a catalogue is written in its own language) · rule 32
//          (no internal code in clerk copy) · CLAUDE.md hard-won law 7 (a
//          check must print what it SKIPPED beside what it checked)
// ───────────────────────────────────────────────────────
/* ══════════════════════════════════════════════════════════════════════════
 * A `defaultValue` FOR A KEY NO CATALOGUE HAS IS ENGLISH, FOREVER, IN SILENCE
 * ══════════════════════════════════════════════════════════════════════════
 *
 * WHY THIS EXISTS, AND WHY THE PARITY GATE CANNOT SEE IT
 * ------------------------------------------------------
 * `t("some.key", { defaultValue: "English sentence" })` is a perfectly ordinary
 * call. When `some.key` is missing it renders the sentence — so **nothing is
 * ever missing at runtime**, no i18next warning fires, and a screen looks
 * finished in every language while a `ko-KR` tenant reads English.
 *
 * The i18n parity check compares the ten catalogues against `en.json`. A key in
 * NONE of the eleven is in `en.json` either, so there is nothing to compare and
 * it reports clean — truthfully, over everything it can see. That is hard-won
 * law 7's *reporting zero over a scope it silently excludes*, one layer up: the
 * check is not lying, it is looking at catalogues rather than at call sites.
 *
 * So this asks the question at the RAISE SITE instead: for every literal key in
 * the files below, is it in all eleven catalogues?
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY — asked before trusting it (law 7, habit 2)
 * ----------------------------------------------------------------------------
 *   · a key built from a template literal. `t(`work.orders.service.${code}`)`
 *     cannot be resolved by reading source, so it is SKIPPED and COUNTED, and
 *     the count is printed. Those are the calls where a `defaultValue` is the
 *     deliberate last resort for a value the catalogue has never heard of.
 *   · a key passed as a variable. Same reason, same skip, same count.
 *   · a file this test does not name. **That is the blind spot and it is
 *     large**, so the last case measures it and prints the number: a declared
 *     blind spot with no NUMBER attached is indistinguishable from an empty one.
 *
 * WHY NOT A GATE (PO ruling, 2026-09-10)
 * --------------------------------------
 * *"a new gate is the last resort and needs their agreement."* A test beside
 * the code goes red in the same run a lane is already reading.
 */
import { describe, expect, it } from "vitest";

// ⚠ **THE HOUSE FORM FOR REACHING NODE FROM A VITEST FILE, AND IT IS NOT
// COSMETIC** (`components/runbookKitClasses.test.ts`'s own precedent). This
// project's `tsconfig` has no Node types and `moduleResolution: bundler`, so a
// plain `import … from "node:fs"` is three `tsc` errors — in a file that runs
// perfectly. Assembling the specifier keeps the module out of the static graph
// and out of Vite's pre-bundle.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string): string[];
  statSync(p: string): { isDirectory(): boolean };
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
  relative(from: string, to: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};
const { readFileSync, readdirSync, statSync } = nodeFs;
const { join, relative } = nodePath;

const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
// `src/features/metering` → `src`, two levels up. Derived rather than typed, so
// moving this file cannot leave it silently scanning nothing (law 7: a check
// that covers nothing looks exactly like a check that found nothing).
const SRC = nodePath.dirname(nodePath.dirname(HERE));
const LOCALES = join(SRC, "i18n", "locales");

/** The eleven the product ships. Read off the directory rather than typed out,
 *  so a twelfth language is covered the day it lands (law: never hand-type a
 *  list — the service list is typed by hand in two places and an eleventh
 *  service did not appear on screen). */
function catalogues(): Record<string, Record<string, string>> {
  const out: Record<string, Record<string, string>> = {};
  for (const name of readdirSync(LOCALES)) {
    if (name.endsWith(".json")) {
      out[name.slice(0, -5)] = JSON.parse(readFileSync(join(LOCALES, name), "utf-8")) as Record<
        string,
        string
      >;
    }
  }
  return out;
}

/** The files this test GUARDS. Everything else is the blind spot the last case
 *  measures. */
const GUARDED = [
  "features/work/buildViews.tsx",
  "features/metering/CommonAreasTab.tsx",
  "features/metering/ServicesAvailableField.tsx",
];

type Call = { file: string; key: string; hasDefault: boolean };

/** Every `t("literal", …)` call in a file. Template-literal and variable keys
 *  are not matched at all — see the false-pass note above. */
function literalCalls(file: string): Call[] {
  const text = readFileSync(join(SRC, file), "utf-8");
  const out: Call[] = [];
  const pattern = /\bt\(\s*"([^"\n]+)"\s*(,|\))/g;
  for (let m = pattern.exec(text); m !== null; m = pattern.exec(text)) {
    let hasDefault = false;
    if (m[2] === ",") {
      // Read the argument object that follows, to its matching brace.
      const rest = text.slice(m.index + m[0].length);
      const open = rest.indexOf("{");
      if (open !== -1 && rest.slice(0, open).trim() === "") {
        let depth = 0;
        let end = open;
        for (; end < rest.length; end += 1) {
          if (rest[end] === "{") depth += 1;
          else if (rest[end] === "}") {
            depth -= 1;
            if (depth === 0) break;
          }
        }
        hasDefault = rest.slice(open, end + 1).includes("defaultValue");
      }
    }
    out.push({ file, key: m[1], hasDefault });
  }
  return out;
}

function tsxFilesUnder(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      out.push(...tsxFilesUnder(full));
    } else if ((name.endsWith(".tsx") || name.endsWith(".ts")) && !name.includes(".test.")) {
      out.push(relative(SRC, full));
    }
  }
  return out;
}

describe("DEF-4742 — a defaultValue for a key no catalogue has", () => {
  const catalogue = catalogues();
  const languages = Object.keys(catalogue).sort();

  it("reads all eleven catalogues, so the check cannot be true of a subset", () => {
    expect(languages.length).toBe(11);
  });

  it("no guarded file carries a defaultValue for a key that is in NO catalogue", () => {
    // ⚠ THIS IS THE DEFECT ITSELF. Ten such call sites shipped, rendering
    // English on every tenant with nothing going red anywhere.
    const englishOnly = GUARDED.flatMap((file) =>
      literalCalls(file)
        .filter((call) => call.hasDefault)
        .filter((call) => languages.every((lang) => catalogue[lang][call.key] === undefined))
        .map((call) => `${call.file} → ${call.key}`),
    );
    expect(englishOnly).toEqual([]);
  });

  it("every literal key a guarded file asks for is in ALL eleven catalogues", () => {
    // The stronger form: a key in `en.json` and missing from `de.json` reaches a
    // German clerk as the KEY ITSELF once the fallback is gone. The parity gate
    // catches that one; asking at the raise site catches it in the same run a
    // lane is already reading, and names the file.
    const gaps = GUARDED.flatMap((file) =>
      literalCalls(file).flatMap((call) =>
        languages
          .filter((lang) => catalogue[lang][call.key] === undefined)
          .map((lang) => `${call.file} → ${call.key} missing from ${lang}`),
      ),
    );
    expect(gaps).toEqual([]);
  });

  it("prints the SIZE of what it does not cover, so the blind spot has a number", () => {
    // Hard-won law 7: *"a declared blind spot with no NUMBER attached is
    // indistinguishable from an empty one, so a check that cannot cover its
    // whole subject must print what it skipped beside what it checked."*
    //
    // ⚠ **THIS CASE DELIBERATELY ASSERTS NOTHING ABOUT THE NUMBER**, and that
    // is not a check that cannot fail wearing a disguise — it is a REPORT, and
    // it says so in its own name. A ratchet on a repo-wide figure was
    // considered and rejected: three lanes are adding `t()` calls to this tree
    // right now, so it would go red on work that is not this file's, in a file
    // whose owner would have no idea why.
    const guarded = new Set(GUARDED);
    const elsewhere = tsxFilesUnder(SRC)
      .filter((file) => !guarded.has(file))
      .flatMap((file) => literalCalls(file))
      .filter((call) => call.hasDefault)
      .filter((call) => languages.every((lang) => catalogue[lang][call.key] === undefined));
    const files = new Set(elsewhere.map((call) => call.file));
    // eslint-disable-next-line no-console
    console.info(
      `[DEF-4742] checked ${String(GUARDED.length)} file(s); NOT checked: ` +
        `${String(elsewhere.length)} English-only call site(s) across ` +
        `${String(files.size)} other file(s) in src/.`,
    );
    expect(elsewhere.length).toBeGreaterThanOrEqual(0);
  });
});
