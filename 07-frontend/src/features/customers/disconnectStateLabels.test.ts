// ── Trace ──────────────────────────────────────────────
// Change:  `DEF-CUS-6053` — three of the eight states the server offers reached
//          a clerk as their CODES (`closed_out`, `in_progress_draft`,
//          `parked`), because `STATE_LABELS` is hand-maintained and its
//          `defaultValue` fallback is designed to render SOMETHING.
// Rules:   B14 rule 31 (no stored code is the visible value of a field) ·
//          rule 33 (a LABEL is ≤ 3 words) · BR-SHL-010 (the server owns the
//          vocabulary; nothing is typed on the front end) · CLAUDE.md
//          hard-won law 2 (a silent absence is invisible to every check).
// ───────────────────────────────────────────────────────
// ⚠ **WHY A VITEST SUITE PARSES TWO DJANGO MODULES.**
//
// This is `signupServices.test.ts`'s shape, deliberately, and for the identical
// reason that file states: *"the failure was a frontend CONSTANT disagreeing
// with a DATABASE SEED, and no check in thirty-odd gates crosses that
// boundary."* Here the frontend constant is `STATE_LABELS` and the authority is
// the SERVER's vocabulary. G15 checks catalogue parity, G18 a dead key, G13 an
// unwired prop — every one of them compares a frontend artefact to another
// frontend artefact, and all of them were green while a clerk read
// `in_progress_draft` in a filter panel.
//
// **A derived list would only ever agree with itself**, which is exactly how
// the three survived: `disconnectFilterGroups` maps over whatever the payload
// sends, so the options are always "correct" and three of them were codes.
//
// ⚠ **THE VOCABULARY IS TWO FILES AND NOT ONE, AND THAT IS THE TRAP.**
// `disconnects.CASE_STATES` holds the eight stored case states;
// `disconnect_reads.DISCONNECT_FILTER_STATES` subtracts the two that take a row
// OFF the list, and then `list_disconnects` APPENDS two codes that are not case
// states at all — `in_progress_draft` and `parked` are facts about a
// `wizard_parks` row, which is why they are marked `drawn: false` and why
// neither could reuse a stored state. A test that read only `CASE_STATES` would
// have passed over two of the three codes this defect was filed for.
//
// So the assertion is against the UNION, and it is the union the STATE column
// and the filter panel both draw from: every stored case state (the column can
// show any of them, including the two the filter subtracts) plus the two minted
// draft codes.
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";
import { disconnectStateLabel } from "./DisconnectsTab";

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

/** The repo root, from this file's own location — `07-frontend/src/features/customers`. */
const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const REPO = nodePath.join(HERE, "..", "..", "..", "..");
const CUSTOMERS = nodePath.join(REPO, "06-backend", "apps", "customers");

function read(file: string): string {
  const source = nodeFs.readFileSync(nodePath.join(CUSTOMERS, file), "utf8");
  // A file that cannot be read is a FAILURE, never a skip — `DEF-524`, a gate
  // whose hardcoded path outlived the file it named and reported PASS through
  // six real defects.
  expect(source.length, `${file} is empty or unreadable`).toBeGreaterThan(0);
  return source;
}

/**
 * Every state code this tab can be handed, read from the server's own modules.
 *
 * `CASE_STATES` is a tuple of NAMES (`STATE_NOTICE_SENT`, …), so the constants
 * are resolved first and the tuple is then read through them. Nothing here is
 * a literal list of states: a ninth state added to `disconnects.py` arrives in
 * this test with no edit at all, which is the whole point.
 */
export function servedStateCodes(): string[] {
  const disconnects = read("disconnects.py");
  const reads = read("disconnect_reads.py");

  const constants = new Map<string, string>();
  for (const m of disconnects.matchAll(/^(STATE_[A-Z_]+)\s*=\s*"([a-z_]+)"$/gm)) {
    constants.set(m[1], m[2]);
  }
  expect(constants.size, "no STATE_* constants found in disconnects.py").toBeGreaterThan(0);

  const tuple = /^CASE_STATES:\s*tuple\[str, \.\.\.\]\s*=\s*\(([\s\S]*?)\)$/m.exec(disconnects);
  expect(tuple, "CASE_STATES not found in disconnects.py").not.toBeNull();
  const codes: string[] = [];
  for (const m of (tuple as RegExpExecArray)[1].matchAll(/(STATE_[A-Z_]+)\s*,/g)) {
    const code = constants.get(m[1]);
    expect(code, `${m[1]} is in CASE_STATES and is defined nowhere`).toBeDefined();
    codes.push(code as string);
  }

  // The two the LIST mints, which are not case states. Read as assignments so a
  // third one appended beside them is picked up here too.
  for (const m of reads.matchAll(/^DISCONNECT_STATE_[A-Z_]+\s*=\s*"([a-z_]+)"$/gm)) {
    codes.push(m[1]);
  }

  expect(codes.length, "the served vocabulary came back empty").toBeGreaterThan(0);
  return codes;
}

/** `t()` as the tab is handed it — catalogue first, `defaultValue` behind it. */
const catalogue = en as Record<string, string>;
function t(key: string, params?: Record<string, unknown>): string {
  return catalogue[key] ?? String((params as { defaultValue?: string } | undefined)?.defaultValue ?? key);
}

describe("DEF-CUS-6053 — every state the server offers has a WORD, never a code", () => {
  it("the vocabulary is the eight case states plus the two minted draft codes", () => {
    const served = servedStateCodes();
    // Named rather than counted, so an edit that drops one and adds another
    // cannot keep this green on the arithmetic (`signupServices.test.ts`'s own
    // reasoning). Ten, because `CASE_STATES` is eight and the list mints two.
    expect(served).toHaveLength(10);
    for (const code of [
      "notice_sent",
      "scheduled",
      "on_hold",
      "cut",
      "reconnecting",
      "stopped",
      "restored",
      // `BR-CUS-430`, PO 2026-08-27 — the eighth, and the one that was DRAWN
      // by the server and had no word at all.
      "closed_out",
      // `DEF-CUS-5994`'s two.
      "in_progress_draft",
      "parked",
    ]) {
      expect(served).toContain(code);
    }
  });

  it("no served state renders as its own code, and none falls to the absence", () => {
    // ⚠ **THIS IS THE ASSERTION THE OLD TEST COULD NOT MAKE.** The case it
    // replaced asserted the OPPOSITE — *"a code the label map has never seen
    // renders as ITSELF — ugly and visible"* — which encoded the defect as the
    // contract. A code on screen is not ugly-and-visible; it is invisible,
    // because it looks deliberate and is never blank.
    //
    // ⚠ **AND THE FIRST DRAFT OF THIS CASE WAS ITSELF A CHECK THAT COULD NOT
    // FAIL.** It asserted only `label !== code`, and with `closed_out` deleted
    // from `STATE_LABELS` it went GREEN: the helper returns *Not named yet*,
    // which is not the code, so the assertion was satisfied by the very
    // fallback it exists to forbid. It was found by doing what CLAUDE.md law 7
    // requires — breaking the thing first — and it is the reason the absence
    // and the `console.error` are asserted here rather than only in the
    // unknown-code case below. **A served state must resolve to a WORD, and
    // landing on the absence is a failure, not a graceful degradation.**
    const unnamed = catalogue["customers.disconnects.state.unnamed"];
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    try {
      for (const code of servedStateCodes()) {
        const label = disconnectStateLabel(code, t);
        expect(label, `the state "${code}" renders as its own code`).not.toBe(code);
        expect(label.length, `the state "${code}" renders as nothing`).toBeGreaterThan(0);
        expect(
          label,
          `the state "${code}" has no word in STATE_LABELS and fell to the absence`,
        ).not.toBe(unnamed);
      }
    } finally {
      console.error = real;
    }
    // The loud half, asserted as a NUMBER rather than left implicit: a check
    // that reports zero over a scope it silently excludes is indistinguishable
    // from an empty one (CLAUDE.md law 7).
    expect(said, `STATE_LABELS is short: ${said.join(" | ")}`).toHaveLength(0);
  });

  it("every served state has a key in the catalogue, not merely a defaultValue", () => {
    // A `defaultValue` is English and the product ships eleven languages. A
    // state whose only word lives in `STATE_LABELS` reads English to a German
    // clerk, which is how `customers.disconnects.state.notice_sent` came to be
    // written in the first place.
    for (const code of servedStateCodes()) {
      expect(catalogue, `customers.disconnects.state.${code} is missing`).toHaveProperty(
        `customers.disconnects.state.${code}`,
      );
    }
  });

  it("a label is at most THREE words — B14 rule 33's cap for a label", () => {
    for (const code of servedStateCodes()) {
      const words = disconnectStateLabel(code, t).trim().split(/\s+/);
      expect(words.length, `"${code}" reads "${words.join(" ")}"`).toBeLessThanOrEqual(3);
    }
  });

  it("a state NOBODY has named states an absence and never the code, loudly", () => {
    // The loud half is the `console.error` the helper writes — a guard that
    // renders an honest absence and says nothing would be the quiet fallback
    // this defect was. `MoneyCell`'s boundary takes the same posture and gives
    // the same reason: *"LOUD, always."*
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    try {
      const label = disconnectStateLabel("zz_a_ninth_state", t);
      expect(label).not.toBe("zz_a_ninth_state");
      expect(label).toBe(catalogue["customers.disconnects.state.unnamed"]);
    } finally {
      console.error = real;
    }
    expect(said).toHaveLength(1);
    expect(said[0]).toContain("zz_a_ninth_state");
    expect(said[0]).toContain("DEF-CUS-6053");
  });

  it("the SERVER's own label is used when it sends one and this map has none", () => {
    // `list_disconnects` sends `label` for `in_progress_draft` and `parked` and
    // nothing has ever read it (hard-won law 2, read from the payload end). It
    // ranks BELOW the catalogue and this map — it is English from a wire — and
    // ABOVE the absence, because a real word beats *not named yet*.
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    try {
      expect(disconnectStateLabel("zz_a_ninth_state", t, "Ninth")).toBe("Ninth");
    } finally {
      console.error = real;
    }
    // …and when it sends one, nothing is wrong, so nothing is shouted about.
    expect(said).toHaveLength(0);
    // A catalogue key still wins over the wire's English.
    // ⚠ `Off` since 2026-09-25 — the clerk word for the stored code `cut`.
    // The point of the case is unchanged: a catalogue entry BEATS the English
    // the wire happens to carry.
    expect(disconnectStateLabel("cut", t, "Zzz")).toBe("Off");
  });
});
