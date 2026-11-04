// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-003 (global search) — the WIRING half
//           Screens: shell chrome, every authenticated screen
// Defect:   DEF-2423 (the box that searched nothing) · DEF-3462 (G13 cannot
//           guard a prop whose NAME another component also uses)
// Rules:    CLAUDE.md hard-won law 2 (built is not wired) ·
//           BR-SHL-005 AS AMENDED 2026-09-03
// ───────────────────────────────────────────────────────
//
// **THIS FILE EXISTS BECAUSE G13 CANNOT DO THIS JOB, AND THAT WAS DISCOVERED BY
// RED-PROVING G13 RATHER THAN BY TRUSTING IT GREEN (law 7).**
//
// `10-scripts/gates/check_unwired_props.py` is the built-is-not-wired gate, and
// it exempted `components/AppShell.tsx:onSearch` by name for months so it would
// pass on purpose while `GET /search` did not exist. The exemption is removed in
// this commit. Then the wiring was deleted to watch the gate bite — **and it did
// not**: `has_caller()` matches the prop NAME across every non-test file and
// never asks which component receives it, and `features/rating/PlanWizard.tsx`
// passes `onSearch` to a SearchSelectField three times. So AppShell's own
// `onSearch` has had a satisfying caller since that wizard shipped, and the
// exemption was belt on a brace that was never fastened (DEF-3462).
//
// A prop name is not a component. These assertions name the component.
//
// ⚠ **IT READS SOURCE, IT DOES NOT RENDER.** `ShellWithSession` needs a router,
// a QueryClientProvider and a live session to render at all, and every one of
// those would have to be faked — at which point the test proves the fake passes
// the prop, which is the same class of nothing the gate was doing. Reading the
// file for the attribute asks the one question that matters and cannot be
// satisfied by a mock. `features/tenancy/BrandMark` and the sign-out redirect
// are asserted the same way and for the same reason (see ShellWithSession's own
// trailer: "E4 the sign-out redirect's wiring is asserted by reading this
// file's source").

import { describe, expect, it } from "vitest";

// Node's own modules, reached the way `styles/routeBUtilities.test.ts` and
// `styles/tailwindTheme.test.ts` do: the string-split import keeps Vite from
// pre-bundling them and keeps this file the same shape as its neighbours. A
// bare `import … from "node:fs"` does not typecheck here — the project carries
// no `@types/node`, which is why the three files that read the tree all do it
// this way rather than each inventing an escape.
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
const SOURCE = nodeFs.readFileSync(nodePath.join(HERE, "ShellWithSession.tsx"), "utf8");

describe("US-SHL-003 — the shell's search props are actually passed", () => {
  // The five that make the box work. `onSearch` alone is not enough: a handler
  // with nothing rendering its results is the same dead UI one step along, and
  // that is exactly how the bell shipped (bellItems + onBellSelect + onMarkAllRead
  // were built together and wired together, for this reason).
  it.each([
    ["onSearch", "the debounced query reaches the component that can fetch it"],
    ["searchGroups", "the results reach the popover"],
    ["searchStatus", "loading, failed and no-match are distinguishable on screen"],
    ["onSearchRetry", "A18 §4's Retry does something"],
    ["formatSearchMoney", "a bill's total renders to two places (hard rule 2)"],
  ])("passes %s to AppShell — %s", (prop) => {
    expect(
      SOURCE.includes(`${prop}={`),
      `ShellWithSession no longer passes ${prop} to AppShell. ` +
        `That is hard-won law 2: AppShell renders the feature behind an optional ` +
        `prop, so nothing throws, every other test passes, and the search box goes ` +
        `quietly dead on every screen in the product. G13 will NOT tell you — see ` +
        `DEF-3462.`,
    ).toBe(true);
  });

  it("calls the ONE typed wrapper rather than building the URL itself", () => {
    // `globalSearch` encodes the query and types the response. A hand-built
    // `client.get("/search?q=" + q)` here would drop the encoding and the type
    // in one line, and neither `tsc` nor the gate would say anything.
    expect(SOURCE).toContain("globalSearch");
    expect(SOURCE).toContain("queryKeys.globalSearch");
  });

  it("guards the fetch with the SAME minimum the box's debouncer uses", () => {
    // Not a literal 2. A second copy of the minimum is a second thing to
    // change, and IS-3's minimum lives in `createSearchDebouncer`'s module.
    expect(SOURCE).toContain("SEARCH_MIN_CHARS");
    expect(SOURCE).not.toMatch(/length\s*>=\s*2\b/);
  });
});
