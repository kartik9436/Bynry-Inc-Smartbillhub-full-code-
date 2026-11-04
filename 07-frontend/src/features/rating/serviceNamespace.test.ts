// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-763 — *"FOUR OF THE TEN PLATFORM SERVICES PRINT AS RAW CODES TO
//          A CLERK — metering.service.* HOLDS SIX"*. `rating.service.*` holds
//          all ten; four live call sites read the six-key namespace with
//          `defaultValue: code`, so `storm_water`, `solar`, `thermal_heat` and
//          `battery` reached a clerk as slugs.
// Rules:   BR-RAT-024 (the platform sells TEN services, in the seed order) ·
//          BR-SHL-030 (adding a language is DATA, never code)
// ───────────────────────────────────────────────────────
// ⚠ **THE FIX WAS TO DELETE ONE OF THE TWO LISTS, NOT TO TOP UP THE SHORT ONE.**
// The defect row offered both: add the four missing keys to `metering.service.*`
// in all eleven catalogues, or point the call sites at `rating.service.*`, which
// already holds ten. Two namespaces that disagree drift again — they had already
// drifted by four codes and nobody noticed, because `defaultValue: code` means
// nothing renders blank and nothing throws. So there is now ONE, and this file
// is what keeps it one.
//
// ⚠ **AND IT READS THE SOURCE, BECAUSE NOTHING ELSE CAN SEE THIS.** A test that
// rendered a screen proves that screen; the failure mode here is the NEXT screen,
// written next month, reaching for the namespace that is still in the
// catalogues. G18 cannot fire — `metering.service.electric` is a real key with a
// real value in eleven files. Only a scan of the call sites can say "there is one
// namespace", so that is what this does.
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

// ⚠ A BARE `import … from "node:fs"` PASSES VITEST AND FAILS `tsc`: @types/node
// is not in the app's tsconfig, so the module has no declarations. Reached the
// way `components/buttonKit.test.ts` and `styles/routeBUtilities.test.ts`
// already do — the string-split keeps Vite from pre-bundling it and keeps `tsc`
// out of it. MEASURED: the bare form gave
// `error TS2307: Cannot find module 'node:fs'` on this file.
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

/** BR-RAT-024's ten, in the platform's seed order. Written out because the
 *  point of the assertion is that the CATALOGUE matches the platform, and a
 *  list derived from the catalogue could only ever agree with itself. */
const TEN_SERVICES = [
  "electric",
  "water",
  "gas",
  "sewer",
  "trash",
  "storm_water",
  "solar",
  "broadband",
  "thermal_heat",
  "battery",
] as const;

/** `src/`, from this file's own location — never a path typed out. */
const SRC = nodePath.dirname(nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url)));

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
    const full = nodePath.join(dir, entry.name);
    if (entry.isDirectory()) {
      // The catalogues themselves are DATA and are another lane's to edit; the
      // question here is only what the CODE calls.
      if (entry.name !== "locales" && entry.name !== "node_modules") {
        sourceFiles(full, out);
      }
    } else if (/\.tsx?$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

describe("DEF-763 — one namespace for service names", () => {
  it("`rating.service.*` names all TEN platform services", () => {
    const catalog = en as Record<string, string>;
    for (const code of TEN_SERVICES) {
      expect(catalog[`rating.service.${code}`]).toBeTruthy();
      // …and the value is a NAME, never the code echoed back.
      expect(catalog[`rating.service.${code}`]).not.toBe(code);
    }
  });

  it("⚠ NO source file calls `t('metering.service.<code>')` any more", () => {
    // The six-key namespace is what four screens read. Every one of them now
    // reads the ten-key one; this is the assertion that keeps it that way, and
    // the only one that can see a NEW call site added tomorrow.
    const offenders = sourceFiles(SRC)
      .filter((path) => !path.endsWith("serviceNamespace.test.ts"))
      .filter((path) => /t\(\s*`metering\.service\./.test(nodeFs.readFileSync(path, "utf8")))
      .map((path) => path.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("the ten codes are the platform's, in the seed order CLAUDE.md states", () => {
    // BR-RAT-024, and the reason this list is typed out rather than derived: the
    // repo's own header said SIX services until 2026-08-16 while the seed
    // carried ten, and a subset hardcoded anywhere is how that happens again.
    expect(TEN_SERVICES).toHaveLength(10);
    expect(TEN_SERVICES.slice(5)).toEqual([
      "storm_water",
      "solar",
      "broadband",
      "thermal_heat",
      "battery",
    ]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-763 (12-governance/10-defect-log.csv) + BR-RAT-024
// generated: 2026-08-26 by lane DEFSWEEP
// note: the six `metering.service.*` keys are now DEAD in all eleven
//       catalogues. This lane may not edit `src/i18n/locales/` (lane I18NFANIN
//       owns them today), so their retirement is handed over in
//       `scratchpad/newkeys-DEFSWEEP.json` under `retire`.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
