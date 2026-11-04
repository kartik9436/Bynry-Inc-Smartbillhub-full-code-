// ── Trace ──────────────────────────────────────────────
// Change:  CR-064 (PO 2026-09-02) — *"can you show all 17 step - -list down all
//          17 steps and show 1 by 1 when they finish"*.
// Rules:   B14 rule 32 (one sentence per step; no rule id or internal code in
//          clerk-facing copy) · BR-TEN-060 (a block that did not seed is a
//          NAMED line) · CLAUDE.md hard-won law 2 (built is not wired)
// ───────────────────────────────────────────────────────
// ⚠ **WHY THIS FILE READS A DJANGO MODULE FROM A VITEST SUITE, AND WHY IT IS
// THE SAME ARGUMENT `signupServices.test.ts` MAKES.**
//
// `PROVISIONING_STEPS` is a hand-written copy of a backend list. That exact
// shape put SIX services on the sign-up screen for ten days after ELEVEN were
// ruled: the row existed, the API served it, `tsc` and every test passed, and
// the chip was simply never on the page. CLAUDE.md calls it hard-won law 2 and
// says it fails SILENTLY.
//
// The copy exists anyway, for one reason nothing else can meet: *"list down all
// 17 steps"* means BEFORE the first poll answers, and during the commit there
// is no server answer of any kind to draw from. So the copy is allowed and the
// comparison is made a test: this file parses `SAMPLE_MODULES` out of
// `06-backend/apps/tenancy/sample_data.py` and asserts the constant IS that
// tuple, in that order. A derived list would only ever agree with itself, which
// is exactly how the six survived.
//
// It also asserts the half a key set cannot: every one of the seventeen has a
// clerk-facing label in `en.json`. A missing key renders as the raw key string
// — `tenancy.signup.provisioning.block.metering.seed_sample_reads` printed to a
// utility owner on the first screen they ever see.
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

import { PROVISIONING_STEPS, stepLabelKey } from "./SignupWizard";

// ⚠ A BARE `import … from "node:fs"` PASSES VITEST AND FAILS `tsc` (no
// @types/node in the app tsconfig). Reached the way `signupServices.test.ts`
// and `styles/routeBUtilities.test.ts` already do.
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

/** The repo root, from this file's own location — `07-frontend/src/features/tenancy`. */
const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const REPO = nodePath.join(HERE, "..", "..", "..", "..");
const SAMPLE_DATA = nodePath.join(REPO, "06-backend", "apps", "tenancy", "sample_data.py");

/**
 * The seventeen block keys the orchestrator walks, in creation order.
 *
 * Read out of `SAMPLE_MODULES` — a tuple of `SampleModule("<module>",
 * "<seam>", "<label>", (...tables))` calls — rather than out of a copy. The
 * regex takes the FIRST TWO string arguments of each constructor call, which
 * is exactly what `SampleModule.key` is (`f"{module}:{seam}"`).
 */
function seededStepKeys(): string[] {
  const source = nodeFs.readFileSync(SAMPLE_DATA, "utf8");
  const tuple = /SAMPLE_MODULES:\s*tuple\[SampleModule,\s*\.\.\.\]\s*=\s*\(([\s\S]*?)\n\)\n/.exec(
    source,
  );
  // A file that no longer holds the tuple is a FAILURE, never a skip: a test
  // that quietly passes when it cannot find its authority is DEF-524's shape —
  // a check whose hardcoded path outlived the thing it named, reporting PASS
  // through six real defects.
  expect(tuple, `SAMPLE_MODULES not found in ${SAMPLE_DATA}`).not.toBeNull();

  const keys: string[] = [];
  for (const m of (tuple as RegExpExecArray)[1].matchAll(
    /SampleModule\(\s*"([a-z_]+)",\s*"([a-z_]+)"/g,
  )) {
    keys.push(`${m[1]}:${m[2]}`);
  }
  expect(keys.length, `no SampleModule entries parsed from ${SAMPLE_DATA}`).toBeGreaterThan(0);
  return keys;
}

const catalogue = en as unknown as Record<string, string>;

describe("CR-064 — the seeding steps the sign-up screen names", () => {
  it("the screen's list IS the orchestrator's list, in creation order", () => {
    // RED-PROVED (law 7) by deleting `payments:seed_sample_plan_payments` from
    // the hand-typed constant — the exact shape of the six-services defect:
    //
    //     AssertionError: expected [ …(16) ] to deeply equal [ …(17) ]
    const seeded = seededStepKeys();
    // ⚠ **THE EXPECTED LENGTH IS DERIVED FROM PYTHON, NOT TYPED HERE
    // (DEF-3320).** This line read `expect(seeded).toHaveLength(17)` and it did
    // its job: `rating:seed_sample_enrolments` was appended to `SAMPLE_MODULES`
    // on 2026-09-02 and this was the ONE check in the repository that went red
    // for it — every backend test asserts against `len(SAMPLE_MODULES)`, which
    // is correct and is exactly why none of them could see it.
    //
    // But the literal made this case red for a LAWFUL change rather than for a
    // wrong one, and the sentence below already says the whole thing: the
    // screen's list IS the orchestrator's list. A floor keeps the parse honest —
    // a regex that matched nothing would otherwise compare two empty arrays and
    // pass, which is the check-that-cannot-fail this file exists to avoid.
    expect(seeded.length).toBeGreaterThanOrEqual(17);
    expect(PROVISIONING_STEPS).toEqual(seeded);
  });

  it("every step THE SEEDER WALKS has a label a clerk can read", () => {
    // ⚠ **THIS ITERATES THE PARSED LIST, NOT THE TYPED ONE, AND THE
    // DIFFERENCE IS THE WHOLE OF `DEF-3340`.** It read `PROVISIONING_STEPS`
    // — the hand-typed copy — so a step MISSING FROM THE COPY could never
    // be found to be missing a label. When `CR-062`'s addendum inserted the
    // Municipal discount the copy stayed at seventeen, this check kept
    // passing over seventeen keys it had chosen itself, and the eighteenth
    // step rendered the server's English sentence in all eleven catalogues.
    // A check that carries its own copy of the thing it polices agrees only
    // with itself; the authority is `SAMPLE_MODULES` and it is read here.
    //
    // RED-PROVED (law 7) at 05eef3e8, before the key existed:
    //
    //     AssertionError: rating:seed_sample_enrolments has no label in
    //     en.json: expected undefined to be truthy
    //
    // A missing key does not throw — the screen falls back to the server's
    // `label`, so a Japanese or Hindi operator reads one English line in a
    // list of eighteen and nothing anywhere goes red.
    for (const key of seededStepKeys()) {
      const labelKey = stepLabelKey(key);
      expect(catalogue[labelKey], `${key} has no label in en.json`).toBeTruthy();
    }
  });

  it("no step label carries a rule id, a screen id or an internal code", () => {
    // B14 rule 32, ratified 2026-08-31 after the PO said *"too much content -
    // desctiption is too much for clark to read"*: no rule id or internal code
    // in clerk-facing copy. The SERVER's own labels break this — they carry
    // `spec §4 case 14` and `S17.2` — which is the whole reason the screen
    // renders its own catalogue instead of what the API sends.
    const forbidden = /\b(BR-[A-Z]{3}-\d+|OQ-\d+|DEF-\d+|GT-\d+|US-[A-Z]{3}-\d+|S\d{1,3}(\.\d+)?)\b|spec §/;
    for (const key of PROVISIONING_STEPS) {
      const label = catalogue[stepLabelKey(key)];
      expect(label, `${key}: ${label}`).not.toMatch(forbidden);
    }
  });

  it("the six step states each have a word, and none of them is a colour", () => {
    // The dot is `aria-hidden`, so the STATE WORD is the only thing a screen
    // reader can read out. All six must exist or a step reports nothing at all.
    for (const state of ["queued", "notStarted", "working", "done", "skipped", "failed"]) {
      expect(
        catalogue[`tenancy.signup.provisioning.state.${state}`],
        `no word for the ${state} state`,
      ).toBeTruthy();
    }
    // And "skipped" is not spelled the same as "failed", which is the
    // conflation CR-064 was raised to end: nothing broke when a seam is
    // unwired, and the operator must be able to tell the two apart.
    expect(catalogue["tenancy.signup.provisioning.state.skipped"]).not.toBe(
      catalogue["tenancy.signup.provisioning.state.failed"],
    );
  });
});
