// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-6348 — twelve screens printed a database id whenever the
//          human label was missing: `{row.label ?? row.id}` in a JSX text
//          position. B14 rule 31: no database id is ever the visible value of a
//          field; where no label exists the field says so in WORDS.
// ───────────────────────────────────────────────────────
//
// WHY A TEST AND NOT ONE OF THE TWO GATES: G44 classifies by the FIELD it reads
// and never follows the right-hand side of `??`, and G69 matches truncated ids
// and middle-dot templates — each says in its own output that this shape passes
// it. This reads the source for exactly that shape.
//
// WHAT IT SKIPS, SAID OUT LOUD (hard-won law 7): test files, comment lines, and
// any `?? x.id` that is not the whole of a JSX expression in text position — an
// id as a React `key`, a route parameter or a `title` is allowed by rule 31.
// It prints how many files it read, so a scan that silently read none fails.
//
// ⚠ KNOWN AND WAITING — SELF-EXPIRING (CLAUDE.md hard-won law 2's hold rule).
// The two UnitPricingPanel.tsx sites are left to lane MOVEIN-WIZ, which has
// that file open (`DEF-SHL-6348`, coordinator's ruling 2026-09-24). The second
// case FAILS the day either stops falling back to an id, so the exception is
// deleted in the commit that fixes it rather than outliving it.
//
// ⚠ **THE SOURCES ARE READ THROUGH `import.meta.glob`, NOT `node:fs`.** The
// first version imported `node:fs`/`node:path`/`node:url`, and `tsc` went red
// with TS2307 on all three: this project's tsconfig carries no Node types for
// `src/`. `import.meta.glob` is Vite's own and needs none — the approach
// `portal/routing/everyRouteHasADoor.test.ts` already takes.
import { describe, expect, it } from "vitest";

/** Every `.tsx` under `src/`, as text, keyed `../<path from src>`. */
const SOURCES = import.meta.glob("../**/*.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** `{ … ?? <expr>.id }`, `?? <expr>_id`, `?? <expr>Id` as a whole JSX child. */
const ID_FALLBACK =
  /(?:^\s*|>)\{[^{}]*\?\?\s*[\w?.]+(?:\.id|_id|Id)\b(?:\s*\?\?[^{}]*)?\}/;

/** DEF-SHL-6348 — MOVEIN-WIZ fixes these; each entry must still be present.
 *  EMPTY since `b0b96260a` (2.351.18): both UnitPricingPanel.tsx sites read
 *  "—" now, and this list went red on them exactly as designed. */
const KNOWN_AND_WAITING: Record<string, string[]> = {};

function sourceFiles(): [string, string][] {
  return Object.entries(SOURCES)
    .filter(([key]) => !key.includes(".test."))
    .map(([key, text]) => [key.replace(/^\.\.\//, ""), text]);
}

function fallbacks(): { file: string; line: string }[] {
  return sourceFiles().flatMap(([file, text]) => {
    return text
      .split("\n")
      .filter((line) => !/^\s*(\/\/|\*|\/\*)/.test(line) && ID_FALLBACK.test(line))
      .map((line) => ({ file, line: line.trim() }));
  });
}

describe("DEF-SHL-6348 — no screen falls back to printing a database id", () => {
  it("reads the front end, and finds no `?? <x>.id` in a JSX text position", () => {
    expect(sourceFiles().length).toBeGreaterThan(400);
    const known = (hit: { file: string; line: string }) =>
      (KNOWN_AND_WAITING[hit.file] ?? []).some((expr) => hit.line.includes(expr));
    expect(fallbacks().filter((hit) => !known(hit))).toEqual([]);
  });

  it("every known-and-waiting site still falls back to an id — delete it the day it is fixed", () => {
    const found = fallbacks();
    const stale = Object.entries(KNOWN_AND_WAITING).flatMap(([file, exprs]) =>
      exprs
        .filter((expr) => !found.some((hit) => hit.file === file && hit.line.includes(expr)))
        .map((expr) => `${file}: ${expr}`),
    );
    expect(stale).toEqual([]);
  });
});
