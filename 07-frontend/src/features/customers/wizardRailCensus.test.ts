// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave D — `DEF-CUS-5071`
// Rules:   B14 rule 3 (any flow with 2+ stages uses the numbered step rail and
//          a wizard-actions footer) · B14 rule 36 (compose the kit; where the
//          kit lacks a piece ADD IT TO THE KIT rather than hand-rolling it in
//          the screen) · BR-SHL-018 / BR-SHL-019 (the frame owns rail
//          semantics and the ONE transactional commit)
// Defects: DEF-CUS-5071 · DEF-WRK-5066
// ───────────────────────────────────────────────────────
/**
 * EVERY DECLARED STEP LIST REACHES A RAIL.
 *
 * `DEF-CUS-5071`'s prevention column, verbatim: *"A test that asserts every
 * exported STEPS const has a renderer would have caught it, and is writable
 * today."* This is it.
 *
 * **What went wrong without it.** `CHANGE_PLAN_STEPS` and
 * `PAYMENT_PLAN_STEPS` each had exactly two readers in the repository — their
 * own type alias, and a test asserting the array equals itself. Nothing
 * rendered either, so two of the eleven customers wizards drew no step rail at
 * all: measured in Chromium on `brazosbend`, 2026-09-12, **zero rail nodes**
 * on change-plan at step 1 AND at step 2 after a plan was picked, zero on
 * payment-plan, and the words `Plan`/`Effective`/`Confirm` and
 * `Terms`/`Schedule`/`Agreement` nowhere on either page. `tsc`, eslint, both
 * screens' suites and every gate were green over it, because a const nobody
 * renders is legal TypeScript and the tests asserted the const.
 *
 * **WHAT THIS CHECK CAN AND CANNOT SEE, said plainly (hard-won law 1).** It is
 * a SOURCE census: it asks whether some non-test file that mounts
 * `WizardFrame` names the const. It cannot tell you the rail renders — a
 * Tailwind utility in a file absent from `route-b-migrated.txt` is in the DOM
 * and styles nothing, and every source-reading check passes on that. The
 * rendered assertions live beside each screen (`AccountActions.test.tsx` and
 * `PaymentPlanWizard.test.tsx` both read `data-wizard="rail"` and which step
 * is `active`), and the browser walkthrough is above both. This check is the
 * one that fires for the TWELFTH wizard, which neither of those can.
 */
import { describe, expect, it } from "vitest";

// Node's own modules, reached the way `styles/routeBUtilities.test.ts` next
// door does — the string-split import keeps Vite from pre-bundling them and
// keeps `tsc` happy without a `@types/node` this tsconfig does not carry.
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

const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.dirname(nodePath.dirname(HERE));

/**
 * ⚠ **THE ONE EXCEPTION, NAMED WITH ITS REASON — AND IT MAY ONLY SHRINK.**
 *
 * `RULE_BUILDER_STEPS` does not reach `WizardFrame` and it is NOT the
 * `DEF-CUS-5071` shape: `features/work/RuleBuilder.tsx:138` hand-rolls its own
 * rail as an `<ol data-rule-steps>` with its own borders and its own active
 * styling. So it draws a SECOND rail rather than none, which is B14 rule 36's
 * clause (*"compose the kit… where the kit lacks a piece, ADD IT TO THE
 * KIT"*) and rule 3's, in the opposite direction from this defect.
 *
 * It is baselined rather than fixed because `features/work/` belongs to
 * another wave, and baselined rather than ignored because a check that is red
 * is a check nobody reads. `DEF-WRK-5066` carries it. **Delete this line when
 * that row is fixed** — a line that matches nothing fails below, so the list
 * cannot sit here as history pretending to be a measurement.
 *
 * ⚠ **FIXED 2026-10-04 (CR-168-BRC10 round 5, lane RULES, P3.19):** the rule
 * builder mounts `WizardFrame` with three steps, and its `RULE_BUILDER_STEPS`
 * line is deleted from the baseline below in the same commit.
 */
const BASELINE: Record<string, string> = {
  // ⚠ `DEF-GOV-9108` (2026-10-02) — four billing and rating wizards whose step
  // lists reach no WizardFrame. Each is another lane's screen, mid-build, and
  // the census lives in this folder, so none of those lanes ran it. Baselined
  // WITH the row rather than rewired from here; a NEW orphan still fails.
  BILL_RUN_STEPS: "DEF-GOV-9108 — the bulk bill run is one page of four (91eca0bff, 2026-09-30)",
  ONE_TIME_BILL_STEPS: "DEF-GOV-9108 — one-time bill, one page of four (9cf662125, 2026-09-30)",
  RATE_WIZARD_STEPS: "DEF-GOV-9108 — rate schedule Add/Edit, three steps (5804b0fc1, 2026-10-01)",
};

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
    const full = nodePath.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(full));
    } else if (/\.tsx?$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

interface Source {
  path: string;
  text: string;
}

const FILES = walk(nodePath.join(SRC, "features")).concat(
  walk(nodePath.join(SRC, "components")),
);
const SOURCE: Source[] = FILES.filter((f) => !/\.(test|dom\.test)\.tsx?$/.test(f)).map((f) => ({
  path: f,
  text: nodeFs.readFileSync(f, "utf-8"),
}));

/** Every `export const <NAME>_STEPS`, and where it is declared. */
function declaredStepLists(sources: Source[] = SOURCE): { name: string; path: string }[] {
  const found: { name: string; path: string }[] = [];
  for (const file of sources) {
    for (const m of file.text.matchAll(/^export const ([A-Z][A-Z0-9_]*_STEPS)\b/gm)) {
      found.push({ name: m[1], path: file.path });
    }
  }
  return found;
}

/**
 * Does any file that mounts `WizardFrame` USE this const?
 *
 * ⚠ **IT IS ASKED OF CODE AND NOT OF PROSE.** A first draft matched the bare
 * word, and that made a const "rendered" because a NEIGHBOURING FILE'S COMMENT
 * happened to mention it — `CHANGE_PLAN_STEPS` was named in a docstring in
 * `PaymentPlanWizard.tsx` and would have passed on that alone. That is a check
 * passing wrongly, so comment bodies are stripped before the search. The
 * self-test below feeds it exactly that case.
 */
function reachesAFrame(name: string, sources: Source[] = SOURCE): boolean {
  return sources.some((file) => {
    if (!file.text.includes("WizardFrame")) return false;
    const code = file.text
      .replace(/\/\*[\s\S]*?\*\//g, " ")
      .replace(/(^|[^:])\/\/.*$/gm, "$1 ");
    return new RegExp(`\\b${name}\\b`).test(code);
  });
}

/**
 * ⚠ **THE SELF-TEST, AND WHY IT IS HERE RATHER THAN A NOTE SAYING IT WAS DONE.**
 *
 * This census was first "proved red" by deleting one reference to
 * `CHANGE_PLAN_STEPS` from the wizard — **and it stayed GREEN**, because the
 * file still used the const elsewhere (`CHANGE_PLAN_STEPS.length`, in the
 * `Step n of 3` sentence) and still mounted the frame. The sabotage was aimed
 * at the wrong thing; the check was sound and could not say so.
 *
 * CLAUDE.md law 7's second habit is *"ask what would make this check pass
 * wrongly"*, and its answer here is an argument rather than a claim: the
 * predicates take their sources, so three synthetic cases below exercise the
 * exact shapes — an orphan, a real renderer, and a mention in a comment only.
 * Every gate in `10-scripts/gates/` prints `self-test: N sabotages bite` for
 * the same reason.
 */
const PROBE: Record<string, Source[]> = {
  orphan: [
    { path: "probe/Orphan.tsx", text: "export const PROBE_STEPS = [\"a\", \"b\"] as const;\n" },
    { path: "probe/Elsewhere.tsx", text: "import { WizardFrame } from \"@/components/WizardFrame\";\n" },
  ],
  wired: [
    { path: "probe/Orphan.tsx", text: "export const PROBE_STEPS = [\"a\", \"b\"] as const;\n" },
    {
      path: "probe/Wizard.tsx",
      text:
        "import { WizardFrame } from \"@/components/WizardFrame\";\n" +
        "const steps = PROBE_STEPS.map((id) => ({ id }));\n",
    },
  ],
  commentOnly: [
    { path: "probe/Orphan.tsx", text: "export const PROBE_STEPS = [\"a\", \"b\"] as const;\n" },
    {
      path: "probe/Wizard.tsx",
      text:
        "import { WizardFrame } from \"@/components/WizardFrame\";\n" +
        "/* PROBE_STEPS is named here and rendered nowhere. */\n" +
        "// PROBE_STEPS again, in a line comment.\n",
    },
  ],
};

describe("DEF-CUS-5071 · every declared step list reaches the shared rail", () => {
  it("finds the step lists at all — a census over nothing would pass silently", () => {
    const lists = declaredStepLists();
    // 18 on 2026-09-12. The number is asserted as a FLOOR, not an equality: a
    // new wizard must not have to edit this file, but a refactor that stops
    // this census seeing any of them must not read as a clean sheet (hard-won
    // law 7 — a check that cannot fail is worse than none).
    expect(lists.length).toBeGreaterThanOrEqual(18);
    expect(lists.map((l) => l.name)).toContain("CHANGE_PLAN_STEPS");
    expect(lists.map((l) => l.name)).toContain("PAYMENT_PLAN_STEPS");
  });

  it("B14 rule 3 · no declared step list is rendered by nothing", () => {
    const orphans = declaredStepLists()
      .filter(({ name }) => !reachesAFrame(name) && BASELINE[name] === undefined)
      .map(({ name, path }) => `${name} (declared in ${path.slice(SRC.length + 1)})`);
    expect(
      orphans,
      "a flow declares these steps and no file mounting WizardFrame uses them, so a clerk sees no rail — " +
        "wire the flow into components/WizardFrame, or baseline it with its defect row (DEF-CUS-5071)",
    ).toEqual([]);
  });

  it("self-test · the three shapes bite, so a green run above means something", () => {
    // 1 · a step list nobody renders is REPORTED.
    expect(declaredStepLists(PROBE.orphan).map((l) => l.name)).toEqual(["PROBE_STEPS"]);
    expect(reachesAFrame("PROBE_STEPS", PROBE.orphan)).toBe(false);
    // 2 · one a frame file actually uses is NOT.
    expect(reachesAFrame("PROBE_STEPS", PROBE.wired)).toBe(true);
    // 3 · one named only in a COMMENT is reported — the false pass this
    //     predicate was first written with.
    expect(reachesAFrame("PROBE_STEPS", PROBE.commentOnly)).toBe(false);
  });

  it("the baseline may only shrink — a line that matches nothing is not a measurement", () => {
    const names = new Set(declaredStepLists().map((l) => l.name));
    const stale = Object.keys(BASELINE).filter(
      (name) => !names.has(name) || reachesAFrame(name),
    );
    expect(stale, "these baseline entries no longer reproduce; delete them in this same diff").toEqual(
      [],
    );
  });
});
