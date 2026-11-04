// ── Trace ──────────────────────────────────────────────
// Change:  `DEF-CUS-6023` (2026-09-20) — **two of the five cut reasons could
//          never commit.** `CUT_REASONS` sent `tampering` and `abandoned`;
//          `disconnects.CUT_REASONS` and the `ck_disconnect_case_cut_reason`
//          CHECK constraint require `tampering_or_theft` and
//          `premises_abandoned`. A lawful tier-3 case with every other
//          precondition satisfied was refused on the reason alone.
// Rules:   BR-CUS-039 · BR-CUS-100 (tier 3 + certified proof is what gates a
//          cut — NOT the reason) · B14 rule 31 · CLAUDE.md hard-won law 2
// Tests:   this file IS the check; `DisconnectWizard.test.tsx` renders the step.
// ───────────────────────────────────────────────────────
//
// ⚠ **THE TEST THAT EXISTED WAS A MIRROR, AND A MIRROR PASSES FOR ANY FIVE
// STRINGS.** The front end held its own copy of the five reason codes and
// `DisconnectWizard.test.tsx` asserted that copy back to itself
// (`data-reason-unreachable="tampering"`). That is green for `tampering`, for
// `banana`, and for every other value the constant could ever hold. **Nothing
// in this repo compared the two sides**, and the wizard's own suite never
// commits, so the refusal that would have exposed it is never reached.
//
// This file is `signupServices.test.ts`'s shape — a vitest suite that reads a
// PYTHON file — and it is here for the identical reason: the failure was a
// frontend CONSTANT disagreeing with a BACKEND one, and every gate in this repo
// compares a frontend artefact to another frontend artefact. **`disconnects.py`
// is the authority; this file is the comparison.** It is deliberately written
// so that a SIXTH reason added on the server goes RED here rather than silently
// never appearing on the screen, which is hard-won law 2's usual costume: the
// row exists, the API serves it, `tsc` and every test pass, and the screen is
// simply wrong.
import { describe, expect, it } from "vitest";

import { CUT_REASONS, DEPOSIT_DISPOSITIONS } from "./transferDisconnectShared";

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
const DISCONNECTS_PY = nodePath.join(REPO, "06-backend", "apps", "customers", "disconnects.py");
const OPEN_QUESTIONS = nodePath.join(REPO, "12-governance", "01-open-questions.md");

const source = nodeFs.readFileSync(DISCONNECTS_PY, "utf8");

/**
 * The values of a `NAME: tuple[str, ...] = (A, B, C)` declaration, resolved
 * through the `A = "literal"` constants above it, IN THE DECLARED ORDER.
 *
 * ⚠ **IT RESOLVES NAMES RATHER THAN SCRAPING STRINGS.** `CUT_REASONS` is a
 * tuple of CONSTANT NAMES, not of literals, so a reader that grepped the file
 * for quoted words would happily return the five sentences in the docstring
 * above it — which is a check that passes on the defect, one layer down.
 */
function pythonTuple(name: string): string[] {
  const decl = new RegExp(`^${name}(?::[^=]+)? = \\(([^)]*)\\)`, "m").exec(source);
  if (decl === null) {
    throw new Error(`${name} is not declared in ${DISCONNECTS_PY} — the reader is pointed at the wrong file or the wrong name`);
  }
  return decl[1]
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .map((member) => {
      const literal = new RegExp(`^${member} = "([^"]+)"`, "m").exec(source);
      if (literal === null) {
        throw new Error(`${name} names ${member}, which is not a string constant in disconnects.py`);
      }
      return literal[1];
    });
}

describe("DEF-CUS-6023 — the reason a clerk picks is the reason the server accepts", () => {
  it("every cut reason the screen offers is a value `disconnects.CUT_REASONS` holds, in its order", () => {
    // ⚠ **`toEqual` ON THE WHOLE LIST, NOT `toContain` PER ITEM.** A containment
    // check passes over an EXTRA reason on the screen — a value the CHECK
    // constraint refuses — and over a reordering, which changes what a clerk
    // reads first on a screen that cuts somebody's supply.
    expect(CUT_REASONS.map((row) => row.code)).toEqual(pythonTuple("CUT_REASONS"));
  });

  it("every deposit disposition the screen offers is one `disconnects.DEPOSIT_DISPOSITIONS` holds", () => {
    expect(DEPOSIT_DISPOSITIONS.map((row) => row.code)).toEqual(
      pythonTuple("DEPOSIT_DISPOSITIONS"),
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE HOLD, AND THE TEST THAT FIRES WHEN IT EXPIRES
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **`reachable` IS NOT ABOUT THE SPELLING, AND FIXING THE SPELLING DOES NOT
// RETIRE IT.** Four of the five reasons carry `reachable: false` and the step
// renders a `RefusalStrip` over them. That hold tracks **OQ-382**, which is
// about AUTHORITY: `schedule_cut` requires tier 3 of the dunning ladder plus a
// certified proof of service, and a tampering cut, a safety cut, an abandoned
// premises and a customer request involve no ladder and will never reach tier
// 3. `disconnects.py` says the same in its own words — *"FOUR OF THE FIVE
// REASONS HAVE NO PATH TO A CUT AT ALL"* — and `schedule_cut` branches on the
// reason exactly once, to REFUSE an unknown one. So the two are independent:
// before `DEF-CUS-6023` two reasons were refused for their spelling AND four
// were unreachable for their authority; after it, four are still unreachable.
//
// **CLAUDE.md hard-won law 2's mirror is what this case is here to prevent** —
// a live path behind a dead control, which is what the hold becomes the day
// OQ-382 is ruled. Landing a ruling and releasing the control that pointed at
// it are two acts and only the first one feels like the work, so this case
// fires on the first one and names the second.
describe("OQ-382 — the hold on four reasons, and what retires it", () => {
  it("the four unreachable reasons are exactly the four with no ladder", () => {
    expect(CUT_REASONS.filter((row) => !row.reachable).map((row) => row.code)).toEqual([
      "unsafe_installation",
      "tampering_or_theft",
      "premises_abandoned",
      "customer_asked",
    ]);
  });

  it("goes RED the day OQ-382 is answered, because the refusal strip is then a lie", () => {
    const register = nodeFs.readFileSync(OPEN_QUESTIONS, "utf8");
    const row = /^\| OQ-382 \|.*$/m.exec(register);
    expect(row, "OQ-382 has no row in 12-governance/01-open-questions.md").not.toBeNull();
    const cells = (row as RegExpExecArray)[0].split("|").map((cell) => cell.trim());
    const status = cells[cells.length - 2];
    // WHEN THIS GOES RED: OQ-382 has been ruled. Read the ruling, then set
    // `reachable` on each reason the ruling admits and delete the strip's
    // sentence for it in AccountAndReasonStep.tsx — the screen is otherwise
    // refusing a cut the product now allows.
    expect(`OQ-382 ${status}`).toMatch(/OPEN/);
    expect(`OQ-382 ${status}`).not.toMatch(/CLOSED/);
  });
});
