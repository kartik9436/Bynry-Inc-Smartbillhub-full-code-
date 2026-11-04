// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-7681 — `CommitManifest` declared SEVEN of the server's
//          twelve `MANIFEST_KEYS`. It had been missing `messages` and
//          `one_time_charge_invoice_no` since CR-109 on 2026-09-16, and
//          `one_time_charge_payment_no` / `one_time_charge_paid` arrived with
//          BR-MET-1187 on 2026-09-28.
// Rules:   CLAUDE.md hard-won law 2 (built is not wired) · law 1 (a comment
//          claiming a guarantee is not the guarantee)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY A TEST AND NOT A TYPE.** A TypeScript interface that declares fewer
// keys than the server sends is **not an error in TypeScript**: the extra keys
// are simply invisible to every screen, `tsc` is green, every test is green,
// and the only symptom is a value nobody can render. That is hard-won law 2
// through a type instead of through a prop, and nothing in this repo compared
// the two sides — `test_w6_connections.py` asserts the server's set and went
// red correctly when the keys landed; the browser's copy was never in the
// comparison.
//
// ⚠ **IT READS THE PYTHON, NOT A SECOND LIST TYPED HERE.** A copy of
// `MANIFEST_KEYS` in this file would be a third spelling of one contract and
// would agree with itself for ever (`DEF-MET-5428`'s shape). Both sides are
// parsed from the files that define them.
//
// ⚠ **PROVED RED FIRST (law 7):** run against the pre-fix interface it printed
//     expected [ 'customers', 'premises', … ] to equal [ … 'messages',
//     'one_time_charge_invoice_no', 'one_time_charge_paid',
//     'one_time_charge_payment_no' … ]
// naming all five missing keys.
import { describe, expect, it } from "vitest";

// ⚠ **NODE'S OWN MODULES ARE IMPORTED THE WAY `runbookKitClasses.test.ts`
// IMPORTS THEM, AND NOT WITH A PLAIN `import … from "node:fs"`.** The project's
// `tsconfig.json` declares no `types: ["node"]`, so a static import of
// `node:fs` is **five real `tsc` errors** — `Cannot find module 'node:fs'`,
// the same for `node:path`, and `Cannot find name '__dirname'` three times.
// The first draft of this file did exactly that, `vitest` was perfectly green
// on it (vite resolves the modules at run time), and only `tsc --noEmit`
// caught it. That is hard-won law 7's *a check you did not run is not a check*
// — and the reason the typecheck is a push gate rather than a formality.
//
// `import.meta.url` replaces `__dirname`, which does not exist in an ES module.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  dirname(p: string): string;
  resolve(...parts: string[]): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(u: string): string;
};

/** This file's own folder, and the repository root above it — never an
 *  absolute path typed into the source (`DEF-524`: G14's hardcoded path
 *  outlived the file it named and reported PASS through six UI defects). */
const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const REPO = nodePath.resolve(HERE, "../../../..");
const readFileSync = (p: string, enc: string) => nodeFs.readFileSync(p, enc);
const resolve = (...parts: string[]) => nodePath.resolve(...parts);

function serverManifestKeys(): string[] {
  const source = readFileSync(
    resolve(REPO, "06-backend/apps/metering/connections.py"),
    "utf8",
  );
  const block = /MANIFEST_KEYS:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(([\s\S]*?)\n\)/.exec(source);
  if (block === null) {
    throw new Error("MANIFEST_KEYS is not where this test looks — fix the test, not the app");
  }
  // Comment lines carry quoted words too (`"none"`, `""`), so they are dropped
  // before the strings are read. A check that counted a word out of a comment
  // would be the "looking at the wrong thing" shape law 7 names.
  const body = block[1]
    .split("\n")
    .filter((line) => !line.trim().startsWith("#"))
    .join("\n");
  return [...body.matchAll(/"([a-z_]+)"/g)].map((hit) => hit[1]);
}

function browserManifestKeys(): string[] {
  const source = readFileSync(resolve(HERE, "newConnectEndpoints.ts"), "utf8");
  const block = /export interface CommitManifest \{([\s\S]*?)\n\}/.exec(source);
  if (block === null) {
    throw new Error("CommitManifest is not where this test looks — fix the test, not the app");
  }
  return [...block[1].matchAll(/^ {2}([a-z_]+)\??:/gm)].map((hit) => hit[1]);
}

describe("the commit manifest, both sides of the wire", () => {
  it("declares every key the server sends, and no key it does not", () => {
    const server = serverManifestKeys();
    // The guard against a regex that finds nothing and calls it agreement —
    // law 7's "reporting zero over a scope it silently excludes".
    expect(server.length).toBeGreaterThanOrEqual(12);
    expect([...browserManifestKeys()].sort()).toEqual([...server].sort());
  });

  it("carries the four keys that were missing, by name", () => {
    // Named rather than left to the set comparison, so a future failure says
    // WHICH contract moved rather than printing two twelve-item lists.
    const browser = browserManifestKeys();
    for (const key of [
      "messages",
      "one_time_charge_invoice_no",
      "one_time_charge_payment_no",
      "one_time_charge_paid",
    ]) {
      expect(browser).toContain(key);
    }
  });

  it("no longer CLAIMS the quote is posted by nothing", () => {
    // `OQ-379` was answered on 2026-09-16 and the sentence outlived it by
    // twelve days. Under BR-MET-1187 a build whose charges cannot reach the
    // books is not created at all, so the claim is now false twice over.
    //
    // ⚠ **THE ASSERTION IS AGAINST THE LIVE SENTENCE, NOT AGAINST THE WORDS.**
    // The first draft of this case banned the phrase outright and went red on
    // the DATED CORRECTION that records what the line used to say — which
    // step W requires and `G63`'s ruling states in as many words: *"KEEP the
    // paragraph and put a dated correction above it … do not delete it,
    // because why a money file went unguarded is worth knowing."* A check that
    // forbids a repo from remembering its own mistakes is a check looking at
    // the wrong thing (law 7).
    const source = readFileSync(resolve(HERE, "newConnectEndpoints.ts"), "utf8");
    expect(source).not.toContain("(recorded, posted by nothing — OQ-379)");
    // …and the correction that replaced it is still there to be read.
    expect(source).toContain("posted by nothing");
  });
});
