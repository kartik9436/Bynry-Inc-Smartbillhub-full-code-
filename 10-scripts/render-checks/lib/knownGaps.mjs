/**
 * KNOWN GAPS — how a walkthrough stays READABLE while the product is unfinished.
 *
 * ⚠ **WHY THIS EXISTS, IN ONE SENTENCE: A CHECK THAT IS RED BY DESIGN IS A
 * CHECK NOBODY READS.**
 *
 * `cr068-f-home-accounts-details.mjs` was written correctly and finished RED on
 * every run, because two gaps between the wireframe and the product were
 * deliberately left open — a missing *Billed on* column that needs pricing
 * knowledge the portal may not hold, and two security controls nobody has yet
 * agreed the behaviour of. Both were the right calls. The consequence was not:
 * a walkthrough that exits 1 forever teaches its reader that red is its normal
 * colour, and **the day a real regression appears, its failure lands in a pile
 * of expected ones and is invisible.**
 *
 * That is `CLAUDE.md` hard-won law 7's first shape, and the register counts it
 * twenty times on one day: *"PROVED RED, THEN NEVER READ … a suite with 28
 * other failures in it is where a true one goes to hide."* `G78` was red for
 * three lanes. `G103` was red for 165 commits — the gate whose entire job is
 * that a hold cannot rot, rotted, and nobody read it.
 *
 * ╔═══════════════════════════════════════════════════════════════════════════╗
 * ║ THE ONE PROPERTY THAT MAKES THIS HONEST RATHER THAN A FUDGE               ║
 * ╚═══════════════════════════════════════════════════════════════════════════╝
 *
 * Silencing a failing assertion is trivial and worthless. What makes this
 * different is that **a known gap goes RED IN BOTH DIRECTIONS**:
 *
 *   · the gap is still open  → recorded, counted, printed, exit stays 0
 *   · the gap has CLOSED     → **FAILURE**, because the product grew the thing
 *                              and this file still says it has not
 *
 * The second half is the whole point, and it is the hold-expiry lesson (law 2's
 * mirror) applied to gaps: *when you write a hold, write the test that fires
 * when the hold expires.* A gap register with no expiry is the same promise
 * nobody is keeping — `holds.ts` exists for exactly this reason on the UI side,
 * and this is its walkthrough twin.
 *
 * ⚠ **AND THE COUNT IS ALWAYS PRINTED, NEVER IMPLIED.** Law 7's fifth shape:
 * *"a declared blind spot with no NUMBER attached is indistinguishable from an
 * empty one"* — `G32` truthfully reported 0 unresolved over 21 live refusals it
 * could not see. So a run that passes still prints `2 known gaps` and names
 * every one with its defect id. A reader who sees `0 failures, 0 known gaps`
 * knows something different from one who sees `0 failures, 9 known gaps`, and
 * they must never look the same.
 *
 * USE
 * ---
 *     import { Gaps } from "./lib/knownGaps.mjs";
 *     const gaps = new Gaps();
 *
 *     gaps.known(
 *       headers.some((h) => /billed on/i.test(h)),
 *       "…and it names what each service is BILLED ON",
 *       { defect: "DEF-CWP-4131",
 *         why: "absent from the screen AND the server's reply; needs pricing knowledge the portal is forbidden to hold (BR-CWP-xxx), so it is a backend job" },
 *     );
 *
 *     process.exit(gaps.report(failures));
 *
 * `known()` takes the SAME boolean as `check()` — true means the thing is
 * present. You do not invert it. That matters: when the gap closes, the
 * assertion you already wrote starts passing, and this file turns that pass
 * into a failure that names the row to delete.
 */

const GREEN = "✓";
const RED = "⛔";
const GAP = "○";

export class Gaps {
  constructor() {
    /** Gaps that are still open — expected, counted, printed, do not fail. */
    this.open = [];
    /** Gaps that have CLOSED — the product grew it and this file is stale. */
    this.closed = [];
  }

  /**
   * Assert something the wireframe requires and the product does not have yet.
   *
   * @param {boolean} ok      true when the thing IS present (same sense as check())
   * @param {string}  message what was being looked for
   * @param {{defect: string, why: string}} row
   *        `defect` — the register id, so a reader can find why it is open.
   *        `why`    — one plain sentence. Not a rule id; a reason.
   */
  known(ok, message, row) {
    if (!row || !row.defect || !row.why) {
      throw new Error(
        `knownGaps: "${message}" needs { defect, why }. A gap with no id and no ` +
          `reason is indistinguishable from a bug somebody gave up on.`,
      );
    }
    if (ok) {
      // The product grew it. This is a FAILURE — of the register, not the product.
      this.closed.push({ message, ...row });
      console.log(`   ${RED} GAP CLOSED — ${message}`);
      console.log(
        `      ${row.defect} says this is missing and it is PRESENT. ` +
          `Delete the gap row, restore the plain assertion, and close ${row.defect}.`,
      );
    } else {
      this.open.push({ message, ...row });
      console.log(`   ${GAP} known gap — ${message}`);
      console.log(`      ${row.defect}: ${row.why}`);
    }
  }

  /**
   * Print the two counts side by side and return the exit code.
   *
   * @param {string[]} failures the walkthrough's own failure list
   * @returns {number} 0 only when there are no failures AND no closed gaps
   */
  report(failures) {
    const bad = failures.length;
    const closed = this.closed.length;
    const open = this.open.length;

    console.log("");
    console.log(
      `   ${bad === 0 ? GREEN : RED} ${bad} failure(s) · ` +
        `${closed === 0 ? GREEN : RED} ${closed} gap(s) that have CLOSED and are still recorded · ` +
        `${GAP} ${open} known gap(s) still open`,
    );
    for (const f of failures) console.log(`      ${RED} ${f}`);
    for (const g of this.closed) console.log(`      ${RED} stale gap row: ${g.defect} — ${g.message}`);
    for (const g of this.open) console.log(`      ${GAP} ${g.defect} — ${g.message}`);

    if (bad === 0 && closed === 0) {
      console.log(
        open === 0
          ? "   PASS — nothing failed and nothing is knowingly missing."
          : `   PASS — nothing failed. ${open} thing(s) the drawing asks for are ` +
              `knowingly absent and named above; this run does not prove them.`,
      );
      return 0;
    }
    console.log("   FAIL");
    return 1;
  }
}

/**
 * Self-test — run `node lib/knownGaps.mjs` to watch it refuse in both
 * directions. Law 7: prove a guard goes RED before trusting it green, and prove
 * it through the path that will actually run it.
 */
function selftest() {
  const row = { defect: "DEF-TEST-0001", why: "a reason" };
  const out = [];
  const log = console.log;
  console.log = (...a) => out.push(a.join(" "));

  const stillOpen = new Gaps();
  stillOpen.known(false, "a thing the drawing wants", row);
  const openCode = stillOpen.report([]);

  const hasClosed = new Gaps();
  hasClosed.known(true, "a thing the drawing wants", row);
  const closedCode = hasClosed.report([]);

  const realFailure = new Gaps();
  realFailure.known(false, "a thing the drawing wants", row);
  const failCode = realFailure.report(["something genuinely broke"]);

  let threw = false;
  try {
    new Gaps().known(false, "no id", null);
  } catch {
    threw = true;
  }
  const cleanCode = new Gaps().report([]);
  const cleanSaid = out.some((l) => l.includes("nothing is knowingly missing"));
  console.log = log;

  const checks = [
    ["an open gap does NOT fail the run", openCode === 0],
    ["an open gap is still COUNTED and printed", out.some((l) => l.includes("1 known gap(s) still open"))],
    ["a gap that CLOSED fails the run", closedCode === 1],
    ["a closed gap names the row to delete", out.some((l) => l.includes("stale gap row"))],
    ["a real failure fails even with gaps open", failCode === 1],
    ["a gap with no defect id is refused", threw],
    ["a clean run exits 0 and says nothing is missing", cleanCode === 0 && cleanSaid],
  ];
  let bad = 0;
  for (const [what, ok] of checks) {
    console.log(`${ok ? GREEN : RED} ${what}`);
    if (!ok) bad += 1;
  }
  console.log(bad === 0 ? "knownGaps selftest: PASS" : `knownGaps selftest: ${bad} FAILED`);
  return bad === 0 ? 0 : 1;
}

if (process.argv[1] && process.argv[1].endsWith("knownGaps.mjs")) {
  process.exit(selftest());
}
