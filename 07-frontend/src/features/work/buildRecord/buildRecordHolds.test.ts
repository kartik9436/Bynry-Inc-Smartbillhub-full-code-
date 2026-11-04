// ── Trace ──────────────────────────────────────────────
// Change:   CR-126-BRC07 — the HOLD-EXPIRY tests for the build record.
// Rules:    CLAUDE.md hard-won law 2 and its MIRROR — *"WHEN YOU WRITE A HOLD,
//           WRITE THE TEST THAT FIRES WHEN THE HOLD EXPIRES, in the same
//           commit."* A hold with no such test is a promise nobody is keeping,
//           and that is what left the customer portal with two working doors
//           out of eight on 2026-09-05, every suite green · law 7 (*"ask what
//           would make this check PASS WRONGLY"*) · `OQ-MET-12520`, CONFIRMED
//           by the PO (decision log 2026-09-20, `8cb9a379c`) — its first
//           clause SUPERSEDED 2026-09-28 by `CR-151-BRC09` (a build has its
//           own page again), which the last case below now asserts
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE THREE HOLDS THAT STOOD HERE ARE DELETED WITH THE PANEL THEY HELD
 * (`DEF-GOV-10106`).** `Activate units`, `Edit details` and the gate banner
 * were controls on `BuildTab`, the Build panel the PO took off the property
 * and the account on 2026-10-02 (`CR-162-BRC10`): the New Connection's own
 * page tracks progress and takes every action, activation included. A hold on
 * a control nothing renders guards nothing. The ruling case below stays.
 *
 * What follows describes how these source-level checks work.
 *
 * ⚠ **THESE ARE SOURCE-LEVEL ASSERTIONS AND THEY SAY SO.** They cannot tell
 * you a screen is right — no check in this repo reads rendered output. What
 * they CAN do is fail the moment the thing a hold is waiting for arrives, so
 * that the person who lands it is told, by name, which greyed control to
 * release. That is the one job law 2 gives them.
 *
 * ⚠ **HOW EACH COULD PASS WRONGLY, WRITTEN DOWN BECAUSE LAW 7 SAYS A CHECK
 * YOU CANNOT DESCRIBE A FALSE PASS FOR IS ONE YOU DO NOT UNDERSTAND:** each
 * reads ONE file by path. A caller added in some OTHER file would not be seen,
 * and a file renamed would make the read throw rather than pass — which is the
 * safe direction. The `activate` test therefore walks the whole feature tree
 * rather than one file, because that is the hold most likely to be released
 * from somewhere unexpected.
 */
import { describe, expect, it } from "vitest";

// ⚠ A BARE `import … from "node:fs"` PASSES VITEST AND FAILS `tsc --noEmit`:
// `@types/node` is not in the app's tsconfig, so the module has no
// declarations. The string-split dynamic import is how `routeBUtilities.test.ts`
// and `buttonKit.test.ts` next door reach Node — it keeps Vite from
// pre-bundling and keeps `tsc` out of it. Copied rather than reinvented.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string, o: { withFileTypes: true }): { name: string; isDirectory(): boolean }[];
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(u: string): string;
};

const THIS_DIR = nodePath.join(nodeUrl.fileURLToPath(import.meta.url), "..");
const HERE = nodePath.join(THIS_DIR, "..", "..", "..");

function read(relative: string): string {
  return nodeFs.readFileSync(nodePath.join(HERE, relative), "utf8");
}

describe("the PO's ruling that a build HAS its own page at its own address", () => {
  it("keeps `/connections/:connectionId` a SCREEN (NCT-02), not a redirect", () => {
    // ⚠ **THIS GUARDS A RULING, NOT A COMPONENT — AND THE RULING MOVED.**
    // Until 2026-10-02 this case asserted the opposite — that the address was a
    // REDIRECT with no screen id — because `OQ-MET-12520` closed on option C on
    // 2026-09-21 (*"no second screen at its own address"*). On 2026-09-28 the
    // PO superseded that ruling's FIRST CLAUSE (`CR-151-BRC09`, decision log
    // *"A BUILD GETS ITS OWN PAGE AGAIN"*): shown (A) leave it, (B) a summary
    // panel, (C) a full detail page per build — *"They chose (C). A build has
    // its own page, at `/{tenant}/connections/{id}`"*. The flip landed in
    // `ab052ac04` (2.392.5) and this case went red that evening, unread, for
    // four days. It is TURNED AROUND rather than deleted: a lane reinstating
    // the doorway now meets a red test naming the ruling it would undo.
    const registry = read("routing/screenIds.ts");
    const row =
      /\{\s*path:\s*"\/:tenant\/connections\/:connectionId",[\s\S]{0,300}?\}/.exec(registry);

    expect(row, "the /connections/:connectionId row is gone from screenIds.ts").not.toBeNull();
    expect(
      row![0],
      "`/connections/:connectionId` has become a redirect again. The PO ruled on " +
        "2026-09-28 (CR-151-BRC09, superseding OQ-MET-12520's first clause) that a " +
        "build has its own page at this address. Reversing that needs a new ruling " +
        "in the register and the decision log FIRST — see DEF-GOV-6054.",
    ).not.toContain('noScreen: "redirect"');
    expect(row![0]).toContain('r10: "NCT-02"');

    // And the badge is allocated again: a badge says *"this is a screen"*, and
    // since 2026-09-28 one genuinely is.
    expect(read("../../10-scripts/gates/g29_allocated_badges.txt")).toContain("NCT-02");
  });
});
