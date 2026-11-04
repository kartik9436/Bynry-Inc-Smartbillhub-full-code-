// ── Trace ──────────────────────────────────────────────
// Change:  `DEF-CUS-6098` — two of the ten states the server offers reached a
//          clerk as their CODES (`in_progress_draft`, `parked`) in the Show
//          filter on the New connects tab, because `STATE_LABELS` is
//          hand-maintained and its `?? code` fallback is designed to render
//          SOMETHING.
// Rules:   B14 rule 31 (no stored code is the visible value of a field) ·
//          rule 33 (a LABEL is ≤ 3 words) · BR-SHL-010 (the server owns the
//          vocabulary; nothing is typed on the front end) · CLAUDE.md
//          hard-won law 2 (a silent absence is invisible to every check).
// ───────────────────────────────────────────────────────
// ⚠ **WHY A VITEST SUITE PARSES TWO DJANGO MODULES.**
//
// This is `disconnectStateLabels.test.ts`'s shape, deliberately — the identical
// defect one tab over, found in the same week — and `signupServices.test.ts`'s
// before it: *"the failure was a frontend CONSTANT disagreeing with a DATABASE
// SEED, and no check in thirty-odd gates crosses that boundary."* Here the
// frontend constant is `STATE_LABELS` and the authority is the SERVER's
// vocabulary. `G15` checks catalogue parity, `G18` a dead key, `G27` an
// untranslated literal, `G13` an unwired prop — every one of them compares a
// frontend artefact to another frontend artefact, and all were green while a
// clerk read `in_progress_draft` in a filter panel.
//
// **A derived list would only ever agree with itself**, which is exactly how the
// two survived: `connectionFilterGroups` maps over whatever the payload sends,
// so the options are always "correct" and two of them were codes.
//
// ⚠ **THE VOCABULARY IS TWO FILES AND NOT ONE, AND THAT IS THE TRAP.**
// `connections.CONNECTION_STATES` holds the seven stored build states;
// `connection_reads.STATE_FILTER_VALUES` puts `SCOPE_OPEN` in front of them —
// a value that is not a stored state at all but the KPI tile's own set — and
// `list_connections` then APPENDS `in_progress_draft` and `parked`, which are
// facts about a `wizard_parks` row and are marked `drawn: false` for that
// reason. A test that read only `CONNECTION_STATES` would have passed over both
// of the codes this defect was filed for.
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";
import { connectionStateLabel } from "./NewConnectsTab";

// ⚠ A BARE `import … from "node:fs"` PASSES VITEST AND FAILS `tsc` (no
// @types/node in the app tsconfig). Reached the way `disconnectStateLabels
// .test.ts` and `styles/routeBUtilities.test.ts` already do.
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

const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const REPO = nodePath.join(HERE, "..", "..", "..", "..");
const METERING = nodePath.join(REPO, "06-backend", "apps", "metering");

function read(file: string): string {
  const source = nodeFs.readFileSync(nodePath.join(METERING, file), "utf8");
  // A file that cannot be read is a FAILURE, never a skip — `DEF-524`, a gate
  // whose hardcoded path outlived the file it named and reported PASS through
  // six real defects.
  expect(source.length, `${file} is empty or unreadable`).toBeGreaterThan(0);
  return source;
}

/**
 * Every state code this tab can be handed, read from the server's own modules.
 *
 * Nothing here is a literal list of states: an eighth state added to
 * `connections.py` arrives in this test with no edit at all, which is the whole
 * point.
 */
export function servedConnectionStateCodes(): string[] {
  const connections = read("connections.py");
  const reads = read("connection_reads.py");

  const constants = new Map<string, string>();
  for (const m of connections.matchAll(/^([A-Z][A-Z_]*)\s*=\s*"([a-z_]+)"$/gm)) {
    constants.set(m[1], m[2]);
  }
  expect(constants.size, "no state constants found in connections.py").toBeGreaterThan(0);

  const tuple = /^CONNECTION_STATES:\s*tuple\[str, \.\.\.\]\s*=\s*\(([\s\S]*?)\)$/m.exec(
    connections,
  );
  expect(tuple, "CONNECTION_STATES not found in connections.py").not.toBeNull();
  const codes: string[] = [];
  for (const m of (tuple as RegExpExecArray)[1].matchAll(/^\s*([A-Z][A-Z_]*)\s*,/gm)) {
    const code = constants.get(m[1]);
    expect(code, `${m[1]} is in CONNECTION_STATES and is defined nowhere`).toBeDefined();
    codes.push(code as string);
  }

  // `open` — the toolbar's first chip, which is the KPI tile's set and not a
  // stored state. It is a filter VALUE the screen must label like any other.
  const scope = /^SCOPE_OPEN\s*=\s*"([a-z_]+)"$/m.exec(reads);
  expect(scope, "SCOPE_OPEN not found in connection_reads.py").not.toBeNull();
  codes.push((scope as RegExpExecArray)[1]);

  // The two the LIST mints, which are not build states. Read as assignments so
  // a third one appended beside them is picked up here too.
  for (const m of reads.matchAll(/^NEW_CONNECT_STATE_[A-Z_]+\s*=\s*"([a-z_]+)"$/gm)) {
    codes.push(m[1]);
  }

  expect(codes.length, "the served vocabulary came back empty").toBeGreaterThan(0);
  return codes;
}

/** `t()` as the tab is handed it — catalogue first, `defaultValue` behind it. */
const catalogue = en as Record<string, string>;
function t(key: string, params?: Record<string, unknown>): string {
  return (
    catalogue[key] ??
    String((params as { defaultValue?: string } | undefined)?.defaultValue ?? key)
  );
}

describe("DEF-CUS-6098 — every state the server offers has a WORD, never a code", () => {
  it("the vocabulary is the seven build states plus `open` plus the two draft codes", () => {
    const served = servedConnectionStateCodes();
    // Named rather than counted, so an edit that drops one and adds another
    // cannot keep this green on the arithmetic.
    expect(served).toHaveLength(10);
    for (const code of [
      "draft",
      "requested",
      "in_progress",
      "partly_activated",
      "on_hold",
      "activated",
      "cancelled",
      // The toolbar's first chip — the KPI tile's own set.
      "open",
      // `DEF-CUS-5994`'s two, and `DEF-CUS-6098`'s subject.
      "in_progress_draft",
      "parked",
    ]) {
      expect(served).toContain(code);
    }
  });

  it("no served state renders as its own code, and none falls to the absence", () => {
    // ⚠ **THE ABSENCE IS ASSERTED AS WELL AS THE CODE**, which is the lesson
    // `disconnectStateLabels.test.ts` records from its own first draft: a case
    // asserting only `label !== code` goes GREEN with a label deleted, because
    // the helper returns *Not named yet* — the very fallback it exists to
    // forbid. A served state must resolve to a WORD, and landing on the absence
    // is a failure rather than a graceful degradation.
    const unnamed = catalogue["customers.newConnects.state.unnamed"];
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    try {
      for (const code of servedConnectionStateCodes()) {
        const label = connectionStateLabel(code, t);
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
    // clerk — which is exactly what `in_progress_draft` and `parked` did.
    for (const code of servedConnectionStateCodes()) {
      expect(catalogue, `customers.newConnects.state.${code} is missing`).toHaveProperty(
        `customers.newConnects.state.${code}`,
      );
    }
  });

  it("a label is at most THREE words — B14 rule 33's cap for a label", () => {
    for (const code of servedConnectionStateCodes()) {
      const words = connectionStateLabel(code, t).trim().split(/\s+/);
      expect(words.length, `"${code}" reads "${words.join(" ")}"`).toBeLessThanOrEqual(3);
    }
  });

  it("a state NOBODY has named states an absence and never the code, loudly", () => {
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    let label: string;
    try {
      label = connectionStateLabel("a_state_from_the_future", t);
    } finally {
      console.error = real;
    }
    expect(label).not.toBe("a_state_from_the_future");
    expect(label).toBe(catalogue["customers.newConnects.state.unnamed"]);
    expect(said.join(" ")).toContain("a_state_from_the_future");
  });

  it("the SERVER's own word is read when it sends one, and beats the absence", () => {
    // `list_connections` serves `label` on the two draft codes. It sits below
    // the catalogue and below the map — it is English from a payload — but
    // ABOVE the absence, because a real word beats *not named yet*.
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    let label: string;
    try {
      label = connectionStateLabel("a_state_from_the_future", t, "Held for review");
    } finally {
      console.error = real;
    }
    expect(label).toBe("Held for review");
    expect(said, "a served label is not a missing label").toHaveLength(0);
  });
});
