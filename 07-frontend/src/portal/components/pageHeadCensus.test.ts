/* ══════════════════════════════════════════════════════════════════════════
 * EVERY PORTAL SCREEN COMPOSES THE ONE PAGE HEAD — a census over the source.
 *
 * ── Trace ────────────────────────────────────────────────────────────────
 * Defect:  DEF-CWP-4000 — 28 signed-in screens carried no heading of any
 *          kind, and the top row of actions went missing with it. Of the 49
 *          addresses walked on 2026-09-05, 33 emitted no `<h1>` anywhere.
 * Rules:   B14 rule 2 (ONE page header, every screen) · rule 36 (compose the
 *          kit) · audit row D14 (nothing in this repo compares a built portal
 *          screen with its drawing)
 *
 * ⚠ **WHY A SOURCE CENSUS AND NOT A RENDERED ONE, SAID PLAINLY SO NOBODY
 * MISTAKES WHAT THIS CHECKS.** A DOM census would have to mount fifty views,
 * each with its own mocked reads and its own routed path; the portal's suites
 * already do that one screen at a time and this file would be a fiftieth
 * fixture to keep in step. What it CAN do cheaply, and what nothing in the
 * repo did before, is answer the question D14 says belongs to nobody: *has
 * every screen been put on the shared head, and has a new one been born
 * without it.* That is a question about composition, and composition is
 * visible in the source.
 *
 * It therefore proves LESS than "a heading renders": a file could import
 * `PageHeader` and render it behind a condition. It proves exactly one thing
 * and proves it for every screen at once — **no portal screen is written
 * without the product's page head** — and it is the only check in this repo
 * that asks anything at all about a portal screen's SHAPE.
 *
 * ⚠ **`AWAITING_ANOTHER_LANE` IS ASSERTED IN THE NEGATIVE, ON PURPOSE.** Those
 * screens belong to lanes running in these files right now. A list of
 * exceptions that merely SKIPS them would go quietly stale the day one of them
 * lands a head — which is hard-won law 2's clock-in-a-rule, the thing that
 * cost `DEF-CWP-3925` a week. So the census asserts they DO NOT have one yet:
 * the day a lane adds it, this test goes RED and names the file, and the fix
 * is to move the line from one list to the other. A hold with no test that
 * fires when it expires is a promise nobody is keeping.
 * ══════════════════════════════════════════════════════════════════════════ */
import { describe, expect, it } from "vitest";

// ⚠ **NODE'S OWN MODULES, REACHED THE WAY `routeBUtilities.test.ts` NEXT DOOR
// DOES.** `@types/node` is deliberately not installed (see `tsconfig.e2e.json`
// for the standing reason), so a plain `import … from "node:fs"` fails `tsc`
// with *Cannot find module* — which is how the first draft of this file was
// caught. The string-split import carries its own local type and keeps Vite
// from trying to pre-bundle it.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string): string[];
  statSync(p: string): { isDirectory(): boolean };
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
};

const ROOT = new URL("..", import.meta.url).pathname; // src/portal/

/** Screens whose head belongs to a lane that is mid-flight in that file. */
const AWAITING_ANOTHER_LANE: Record<string, string> = {
  // ⚠ `usage/Usage.tsx` (CWP-033) WAS HERE AND HAS BEEN REMOVED — `CR-085`
  // step 2 lane 8 gave it the kicker `USAGE`, the `<h1>` *What you have used*
  // and the drawing's two head controls, so the negative assertion below went
  // red naming the file and this list moved in the SAME commit. It was the
  // LAST entry: every portal screen composes the product's page head now.
  //
  // ⚠ **AND IT NEARLY LEFT THIS CENSUS BLIND INSTEAD OF RED.** The first draft
  // of that fix wrapped the success branch in `<PortalScreen screen="CWP-033">`
  // — an identical DOM — which removed the literal `data-screen="CWP-033"` from
  // the SOURCE. `screenFiles()` below then stopped counting the file as a
  // screen at all, so this test went GREEN for the worst possible reason. See
  // the `PortalScreen` case at the foot of this file, which is the guard that
  // now catches it.
  // ⚠ `accounts/YourAccount.tsx` (CWP-065) WAS HERE AND HAS BEEN REMOVED — the
  // wave-F walkthrough lane gave it the kicker + title its drawing asks for
  // (`DEF-CWP-4135`), and this list moved in the SAME commit because the
  // negative assertion below would otherwise have gone red naming a file that
  // had just been FIXED. That is this list working, as `payments/Payments.tsx`
  // did before it.
  //
  // ⚠ AND `home/Home.tsx` (CWP-022) WAS HERE AND WAS NEVER A GAP AT ALL.
  // `08-screen-layouts.md` opens CWP-022 `PortalShell` → `KpiRow` × 4 and names
  // NO `PageHead`; the captured wireframe draws none either — the balance strip
  // is the first thing under the tab bar, which is the whole point of the
  // screen (*one number, one date, one button*). Listing it as awaiting a head
  // would have had the next lane ADD one and break the drawing. It moves to
  // CORRECTLY_HEADLESS below with that reason, rather than being deleted, so
  // the question is visibly answered and not merely dropped.
  // ⚠ `payments/Payments.tsx` (CWP-041) WAS HERE AND HAS BEEN REMOVED, WHICH
  // IS THIS LIST WORKING RATHER THAN THIS LIST BEING EDITED. The money-screens
  // lane landed its head hours after the census was written, and the negative
  // assertion below went red and named the file — the exact wake-up a plain
  // skip-list could never give. That is why the list is asserted in the
  // negative; see the header.
};

/**
 * **T7 — a focused task.** `08-screen-layouts.md`'s template table is explicit:
 * T7 is *"frame → single `Card` ≈ 70% wide, no rail"* and names no `PageHead`
 * at all. `CWP-015`'s kicker **SIGN IN** and title *Welcome back* are drawn
 * INSIDE the card, as are `CWP-019`'s **RESET** / *Send me a reset link*. The
 * 50-address audit walked all four and recorded every one as matching its
 * drawing.
 *
 * ⚠ **SO THESE ARE NOT EXCEPTIONS TO RULE 2, THEY ARE A DIFFERENT TEMPLATE** —
 * and they are listed here rather than silently skipped so the next lane can
 * see that the question was asked and where the answer came from. They DO
 * write their own `<h1>`, which is correct for T7 and wrong everywhere else.
 */
/**
 * Screens the drawing gives NO page head, on purpose.
 *
 * ⚠ **DIFFERENT FROM `OWN_HEADING_T7` AND FROM `STEP_BAR_INSTEAD`:** those two
 * draw a heading somewhere else. These draw none at all, because the screen
 * opens on something that IS the heading — `CWP-022`'s balance strip answers
 * *do I owe anything and by when* in the first thing the eye lands on, and a
 * title above it would push the one figure the page exists for below the fold.
 */
const CORRECTLY_HEADLESS: Record<string, string> = {
  "home/Home.tsx": "CWP-022 — the drawing opens PortalShell → KpiRow, no PageHead (its h1 is hidden, DEF-CWP-10563)",
};

const OWN_HEADING_T7: Record<string, string> = {
  "guest/HoldingPage.tsx": "CWP-001 holding — T7",
  "signin/FrontDoor.tsx": "CWP-015 — T7, kicker + title inside the card",
  "signin/Enrol.tsx": "CWP-016 · CWP-017 · CWP-018 — T7",
  "signin/ForgotPassword.tsx": "CWP-019 — T7",
  "signin/UpdateEmail.tsx": "CWP-079 — T7, the sign-in family's card heading (CR-189-BRC10)",
};

/**
 * The four screens `08-screen-layouts.md` gives a STEP BAR instead of a head,
 * plus the states that are steps inside one of them. A `Stepper` says where a
 * person is in a sequence; a page head would say it twice and disagree.
 */
/**
 * ⚠ **AND THIS LIST WENT STALE IN SILENCE, WHICH IS `DEF-CWP-4927`.** It still
 * named `requests/DisputeBill.tsx` as drawing no page head **after that file
 * had composed one since the wave-R work** — so the census was excluding a
 * screen that no longer needed excluding, and nothing said so. The header of
 * this file explains why `AWAITING_ANOTHER_LANE` is asserted in the NEGATIVE
 * and this list was not; the answer is that it should have been, for exactly
 * the same reason. **A skip-list rots the day one of its entries is fixed** —
 * hard-won law 2's clock-in-a-rule.
 *
 * The stale entry is gone and the negative assertion below now covers this
 * list too: the day a step-bar screen grows a page head, the suite goes red and
 * names it, and the fix is one line — delete its entry, or put the head back.
 */
const STEP_BAR_INSTEAD: Record<string, string> = {
  "payments/PayNow.tsx": "CWP-038 — step bar (T2)",
  // ⚠ `plans/AskForPlan.tsx` (CWP-042) WAS HERE AND HAS BEEN REMOVED — this
  // negative assertion went red naming it, which is the list working. The
  // answer is the one the comment below asks for: **the drawing changed.**
  // `08-screen-layouts.md`’s one-line T2 summary and `wireframes/CWP-042.png`
  // both open on the `Stepper` with no head — but `CR-085`’s own drawing for
  // this screen (lane 7, *Screen 42*) opens `← Past due` / *Ask for a payment
  // plan* / *Spread what you owe over several months* at BOTH 390 and 1280,
  // and draws no stepper at all. Two frames of one blueprint disagree, so the
  // screen is built on what they AGREE about and neither is deleted: the head
  // names the TASK, the step bar names the STEP, and they cannot say the same
  // thing twice because they do not say the same thing.
  //
  // The exemption’s cost was not theoretical. `SectionTitle` is a `<p>`, so
  // with no `PageHeader` this screen had NO heading element anywhere and the
  // first one a screen reader met was the rail’s `<h3> There may be help too`
  // — announced as the page, to a customer who arrived from the overdue
  // screen. That is `DEF-CWP-4912`.
  //
  // ⚠ **`payments/PayNow.tsx` BELOW IS IN THE SAME POSITION AND IS NOT MINE
  // TO MOVE.** It composes `PageHeader` today (`DEF-CWP-4926`, citing blueprint
  // 35) and is still listed here; it does not fire only because it declares no
  // literal `data-screen`, so `screenFiles()` cannot see it. The day its lane
  // restores that literal this assertion goes red naming it, and the answer
  // will be this same one.
  "guest/ReportRouted.tsx": "CWP-006 — a routed state of the report form",
  "guest/ReportSent.tsx": "CWP-007 — the report form's receipt",
  "methods/Autopay.tsx": "CWP-040 — the head is on AutopayPage.tsx",
  "payments/Fees.tsx": "CWP-050 — the head is on FeesPage.tsx",
};

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of nodeFs.readdirSync(dir)) {
    const full = nodePath.join(dir, name);
    if (nodeFs.statSync(full).isDirectory()) out.push(...walk(full));
    else if (name.endsWith(".tsx") && !name.includes(".test.")) out.push(full);
  }
  return out;
}

/** Files that mark themselves as a screen with `data-screen="CWP-…"`. */
function screenFiles(): { rel: string; source: string; screens: string[] }[] {
  return walk(ROOT)
    .map((full) => {
      const source = nodeFs.readFileSync(full, "utf8");
      // ⚠ **TWO SPELLINGS, AND THE SECOND ONE WAS MAKING THIS CENSUS
      // SHRINK WHILE NOBODY WATCHED (`DEF-CWP-4936`).** `PortalScreen` renders
      // `data-screen` at RUN TIME from a `screen` prop, so a screen written as
      // `<PortalScreen screen="CWP-027">` has an identical DOM and no literal
      // attribute in its SOURCE. On 2026-09-11 nineteen portal files were in
      // that state and `screenFiles()` had stopped counting them: the guard on
      // the guard below — *a census that found none would pass by accident* —
      // went from comfortably over 35 to EXACTLY 35 in forty minutes, which is
      // this census being eaten one file at a time.
      //
      // ⚠ **THIS FIXES THE CENSUS AND NOT THE PROBLEM.**
      // `g100_every_screen_has_a_door.py`'s `SCREEN_MARK` and
      // `g103_holds_cannot_rot.py`'s `DECLARES_SCREEN` read the literal too and
      // are NOT fixed here — g100's worse, because its own docstring says a
      // file with no `data-screen` IS THE FRAME, so those screens' doors are
      // credited to every screen at once. That is `DEF-CWP-4936` and it stays
      // open; the case at the foot of this file publishes the count.
      const screens = [
        ...source.matchAll(/data-screen="(CWP-\d+)"/g),
        ...source.matchAll(/<PortalScreen[^>]*?\sscreen="(CWP-\d+)"/g),
      ].map((m) => m[1]);
      return { rel: full.slice(ROOT.length), source, screens: [...new Set(screens)] };
    })
    .filter((f) => f.screens.length > 0);
}

const composesHead = (source: string) => source.includes('from "@/components/PageHeader"');

/** Does this file hand the page head an action row at all? */
const composesActions = (source: string) =>
  /\b(secondaryActions|primaryAction)\b/.test(code(source));

/**
 * **THE DRAWING, READ AT RUN TIME RATHER THAN COPIED.**
 *
 * ⚠ **THE TITLE WAS THE SMALL HALF OF `DEF-CWP-4000` AND THIS IS THE OTHER
 * ONE.** `08-screen-layouts.md` puts each screen's main controls in the head
 * row — *Download all*, *Pay*, *↓ CSV*, *↓ PDF*, *Query this bill*, *Send a
 * reading*, *+ Add a method*, *↓ Agreement*, *↓ Download a year* — so a screen
 * that gained a heading and no action row is still missing the half a customer
 * came to press. Where a control survived at all it drifted to the FOOT of the
 * page: `CWP-041`'s *↓ CSV* sat in a `mt-3` row under the table, and the
 * bills list carried a bare *Pay* with no amount on it.
 *
 * ⚠ **IT ASKS WHETHER THERE IS AN ACTION ROW, NOT WHETHER EVERY DRAWN ACTION
 * IS IN IT (hard-won law 1 — say what a check cannot see).** `CWP-014` draws
 * *Call* and not *Get directions*, and passes. Counting the buttons would mean
 * matching a designer's prose against a component tree, which is a different
 * and much weaker check; this one closes the gap that actually happened —
 * a screen with a heading and NO action row at all.
 *
 * ⚠ **PARSED FROM THE DOCUMENT AND NOT LISTED HERE, ON PURPOSE.** A copied
 * list is a second source of truth that goes stale the day the drawing moves,
 * which is `DEF-524`'s shape — a hardcoded path outliving the file it named
 * and reporting PASS through six UI defects. This reads the same sentence the
 * designer wrote.
 */
function screensTheDrawingGivesAnAction(): Set<string> {
  const drawing = nodeFs.readFileSync(
    new URL("../../../../04-docs/05-modules/15-portal/08-screen-layouts.md", import.meta.url)
      .pathname,
    "utf8",
  );
  const wanted = new Set<string>();
  for (const section of drawing.split(/\n### /).slice(1)) {
    const id = /^(CWP-\d+)/.exec(section)?.[1];
    if (!id) continue;
    // The head clause only: everything up to the first arrow, which is where
    // `PageHead` stops and the body begins. An `action` named in the BODY
    // (a rail's `Button(outline)`, a row action) is not a head action.
    const body = section.split("\n---")[0];
    const from = body.indexOf("PageHead");
    const clause = (from >= 0 ? body.slice(from) : body).split("→")[0];
    if (/·\s*actions?\s/.test(clause)) wanted.add(id);
  }
  return wanted;
}

/**
 * Screens the drawing heads with an action that the product does not draw yet.
 *
 * ⚠ **ASSERTED IN THE NEGATIVE, exactly as `AWAITING_ANOTHER_LANE` is** — see
 * this file's header for why a skip-list rots and a negative assertion cannot.
 * The day one of these gains its action row the suite goes red and names it,
 * and the fix is to delete the line.
 */
const ACTION_ROW_OUTSTANDING: Record<string, string> = {
  "CWP-029": "*↓ Download* · *🖨 Print* — the printed bill, another lane's file today",
  "CWP-032": "*↓ PDF* · *Pay $63.40* — the final bill, another lane's file today",
  "CWP-050":
    "*Pay $335.00* is a LIVE control into CWP-038. Inventing a money destination is not a layout fix",
  "CWP-051":
    "*Add a note* · *Withdraw*. NOT a move: the withdraw button is bound to the sentence BR-CWP-079 signs and to a refusal line rendered beside it, so relocating it changes behaviour and needs its own pass",
  "CWP-066":
    "*↓ CSV* — no control exists on this screen at all, so it needs a new hold row in holds.ts and copy in eleven catalogues",
};

/**
 * Screens whose head action the SIGNED-OFF WIREFRAME puts in the body instead.
 *
 * ⚠ **THIS IS NOT A BACKLOG AND IT IS NOT `ACTION_ROW_OUTSTANDING`.** That map
 * lists action rows the product has not built yet; this one lists action rows
 * the product has DELIBERATELY not built, because the drawing the layout
 * document was written from has since been superseded by the wireframe set
 * `CR-085` signs off. Two different facts, and rolling them together would let
 * a deliberate divergence be "fixed" by a later lane reading it as a to-do.
 *
 * ⚠ **ASSERTED IN THE NEGATIVE, like every other list in this file.** If one of
 * these screens ever grows a head action again the suite goes red and names it,
 * so the divergence cannot rot into a habit — hard-won law 2's clock-in-a-rule.
 */
const HEAD_ACTION_MOVED_TO_THE_BODY: Record<string, string> = {
  "CWP-057":
    "wireframe screen 41 groups the THREE ways out — pay (filled), ask for a plan, " +
    "see what help there is — in one body panel, and its own note is the reason: " +
    "*a customer who cannot pay must not have to leave to find the alternative*. " +
    "One of the three in the head split the pair across two boxes and left the " +
    "filled one off the screen entirely. 08-screen-layouts.md still heads it " +
    "with an action and is stale here",
};

/**
 * Source with comments removed.
 *
 * ⚠ **THE FIRST DRAFT OF THE `<h1>` CASE WAS RED ON SEVENTEEN FILES AND EVERY
 * ONE WAS A FALSE POSITIVE — its own doc comments.** The sweep's note says
 * *"leaves the page with no `<h1>` for as long as the request takes"*, and a
 * regex over raw source cannot tell that sentence from markup. A check that
 * fires on the prose explaining it is worse than no check, because the next
 * lane silences it.
 */
function code(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

describe("every portal screen composes the one page head (DEF-CWP-4000)", () => {
  it("finds the screens — a census that found none would pass by accident", () => {
    // The guard on the guard. A broken walk or a renamed attribute would make
    // every assertion below vacuously true, which is the failure mode a census
    // is most prone to.
    const files = screenFiles();
    expect(files.length).toBeGreaterThan(35);
  });

  it("no screen is written without it", () => {
    const missing = screenFiles()
      .filter((f) => !composesHead(f.source))
      .filter(
        (f) =>
          !(f.rel in AWAITING_ANOTHER_LANE) &&
          !(f.rel in STEP_BAR_INSTEAD) &&
          !(f.rel in CORRECTLY_HEADLESS) &&
          !(f.rel in OWN_HEADING_T7),
      )
      .map((f) => `${f.rel} (${f.screens.join(", ")})`);
    expect(
      missing,
      "these portal screens draw no page head: they open with a Card and an " +
        "eleven-pixel SectionTitle, so the page has no <h1> and the drawing's " +
        "top row of actions has nowhere to go. Compose components/PageHeader.tsx.",
    ).toEqual([]);
  });

  it("fires the day another lane lands the head it is holding", () => {
    // See the header: asserted in the NEGATIVE so the list cannot go stale in
    // silence. If this goes red, the fix is one line — move the entry out of
    // AWAITING_ANOTHER_LANE, and delete this comment's reason with it.
    const arrivedEarly = screenFiles()
      .filter((f) => f.rel in AWAITING_ANOTHER_LANE && composesHead(f.source))
      .map((f) => `${f.rel} — ${AWAITING_ANOTHER_LANE[f.rel]}`);
    expect(
      arrivedEarly,
      "these screens now HAVE a page head and are still listed as awaiting " +
        "one. Move them out of AWAITING_ANOTHER_LANE in this file.",
    ).toEqual([]);
  });

  it("fires the day a step-bar screen grows a page head (DEF-CWP-4927)", () => {
    // The same negative assertion `AWAITING_ANOTHER_LANE` uses, applied to the
    // list that did NOT have one and went stale because of it. These screens
    // are drawn with a `Stepper` INSTEAD of a head: a page head would say where
    // the person is a second time and disagree. If one of them composes the
    // head anyway, either the drawing changed — delete the line — or the head
    // arrived by accident, which is what this catches.
    // ⚠ **AMENDED 2026-09-11 (`CR-085` step 2 lane 8) — A STEP-BAR SCREEN MAY
    // COMPOSE THE HEAD FOR ITS FAILED AND LOADING BRANCHES, AND THAT IS NOT
    // WHAT THIS CASE IS ABOUT.** Widening `screenFiles()` to read the
    // `PortalScreen` prop spelling made two screens visible to this census for
    // the first time — `payments/PayNow.tsx` and `plans/AskForPlan.tsx` — and
    // both DO import `PageHeader` now: the R-10 sweep gave every failure branch
    // a head, which is `DEF-CWP-4926` working. Their SUCCESS branch still draws
    // the `Stepper` the drawing draws, and a page head there would say where the
    // person is a second time and disagree. That is the question this case asks
    // and a source regex cannot tell the two branches apart, so a file that
    // composes `PortalScreen` is excluded and the limit is said out loud rather
    // than left as a silent hole: **what is no longer checked is whether a
    // step-bar screen heads its SUCCESS branch, for the 3 of these 6 that use
    // `PortalScreen`.** The other 3 are still fully covered.
    const grewAHead = screenFiles()
      .filter((f) => f.rel in STEP_BAR_INSTEAD && composesHead(f.source))
      .filter((f) => !/<PortalScreen\s/.test(f.source))
      .map((f) => `${f.rel} — ${STEP_BAR_INSTEAD[f.rel]}`);
    expect(
      grewAHead,
      "these screens now compose the page head and are still listed as " +
        "drawing a step bar instead. Delete their lines from STEP_BAR_INSTEAD.",
    ).toEqual([]);
  });

  it("a screen the drawing heads with an action DRAWS one", () => {
    // The half of D1 that costs. A screen with the right facts, the right
    // heading and no action row passes every other check in this repo.
    const wanted = screensTheDrawingGivesAnAction();
    const built = new Map<string, { rel: string; source: string }>();
    for (const f of screenFiles()) {
      for (const id of f.screens) {
        // A screen can be marked in two files (a page and its view). It counts
        // as having an action row if ANY of them draws one.
        const prior = built.get(id);
        if (!prior || !composesActions(prior.source)) built.set(id, f);
      }
    }
    const missing = [...wanted]
      .filter((id) => built.has(id)) // an unbuilt screen is DEF-CWP-3988's row, not this one
      .filter((id) => !composesActions(built.get(id)!.source))
      .filter((id) => !(id in ACTION_ROW_OUTSTANDING))
      .filter((id) => !(id in HEAD_ACTION_MOVED_TO_THE_BODY))
      .map((id) => `${id} (${built.get(id)!.rel})`);
    expect(
      missing,
      "08-screen-layouts.md heads these screens with an action and the screen " +
        "draws none. The controls belong in the page head's action row — where " +
        "one survived at all it drifted to the foot of the page (audit row D1). " +
        "Pass them to PageHeader's secondaryActions / primaryAction.",
    ).toEqual([]);
  });

  it("fires the day an outstanding action row lands", () => {
    // See ACTION_ROW_OUTSTANDING: asserted in the negative so the list cannot
    // go stale in silence, which is hard-won law 2's clock-in-a-rule.
    const built = new Map(screenFiles().flatMap((f) => f.screens.map((id) => [id, f] as const)));
    const arrived = Object.keys(ACTION_ROW_OUTSTANDING)
      .filter((id) => built.has(id) && composesActions(built.get(id)!.source))
      .map((id) => `${id} — ${ACTION_ROW_OUTSTANDING[id]}`);
    expect(
      arrived,
      "these screens now HAVE an action row and are still listed as " +
        "outstanding. Delete their lines from ACTION_ROW_OUTSTANDING.",
    ).toEqual([]);
  });

  it("fires the day a wireframe divergence quietly goes away", () => {
    // See HEAD_ACTION_MOVED_TO_THE_BODY: the same negative assertion the two
    // lists above use. A screen that regains a head action is either a lane
    // undoing the wireframe on purpose — in which case delete the line — or a
    // lane undoing it by accident, which is what this catches.
    const built = new Map(screenFiles().flatMap((f) => f.screens.map((id) => [id, f] as const)));
    const returned = Object.keys(HEAD_ACTION_MOVED_TO_THE_BODY)
      .filter((id) => built.has(id) && composesActions(built.get(id)!.source))
      .map((id) => `${id} — ${HEAD_ACTION_MOVED_TO_THE_BODY[id]}`);
    expect(
      returned,
      "these screens draw a head action again and the wireframe puts it in the " +
        "body. Either the drawing changed — delete the line — or the move was " +
        "accidental.",
    ).toEqual([]);
  });

  it("a screen's id is in the SOURCE, not only in a prop (CR-085 lane 8)", () => {
    // ⚠ **THE CENSUS CAN GO GREEN BY LOSING ITS SUBJECT, AND IT ALMOST DID.**
    // `screenFiles()` above finds a portal screen by grepping the literal
    // `data-screen="CWP-…"`. `PortalScreen` renders that attribute at RUN TIME
    // from a `screen` prop, so a screen rewritten as
    // `<PortalScreen screen="CWP-033">` has an identical DOM and **no literal
    // in its source** — and this whole file silently stops seeing it. On
    // 2026-09-11 a lane did exactly that to `usage/Usage.tsx` and the negative
    // assertion that should have gone red went green instead.
    //
    // ⚠ **AND TWO GATES READ THE SAME LITERAL, WHICH IS WHY THIS IS NOT A
    // PEDANTRY.** `g100_every_screen_has_a_door.py`'s `SCREEN_MARK` decides
    // WHICH SCREEN A DOOR IS ON — `CWP-033` holds the only door in the product
    // to `CWP-034` and `CWP-037` — and `g103_holds_cannot_rot.py`'s
    // `DECLARES_SCREEN` decides which files it looks at for expired holds.
    // Both would have reported ZERO over a scope they had silently excluded,
    // which is hard-won law 7's own named shape.
    //
    // So: a file may COMPOSE `PortalScreen` — that is how the head reaches the
    // failed and loading branches — but it must still declare its id as a
    // literal somewhere. This is the cheap half; teaching all three scanners
    // about the prop is the expensive one, and it is a change to two gates that
    // needs its own red proof.
    // ⚠ **AND IT FOUND SEVENTEEN FILES ON ITS FIRST RUN AND NINETEEN
    // FORTY MINUTES LATER, WHICH IS WHY THIS IS A RATCHET AND NOT A LIST**
    // (`DEF-CWP-4936`, filed and open). The whole of plans, bills, arrears,
    // payments and documents declares its screen only through the prop while
    // `CR-085` step 2 is still landing, so an exact set would go red on every
    // sibling push and teach its reader that red is its normal colour — which
    // is the failure `cr068-h`'s own header names.
    //
    // **A CEILING THAT MAY ONLY FALL, with the NUMBER printed either way**, is
    // what this repo already does for exactly this (G26's grandfathered rows).
    // A twentieth file goes RED and names itself; the nineteen are published
    // rather than hidden, because a declared blind spot with no number attached
    // is indistinguishable from an empty one (hard-won law 7).
    //
    // ⚠ **THE CENSUS ITSELF IS NO LONGER BLIND — `screenFiles()` READS BOTH
    // SPELLINGS NOW.** What these nineteen are still invisible to is
    // `g100_every_screen_has_a_door.py` and `g103_holds_cannot_rot.py`, and
    // fixing those two is a gate change with its own red proof.
    // ⚠ **LOWERED 19 → 7 ON 2026-09-11, WHEN `CR-085` STEP 2 FINISHED LANDING.**
    // The nineteen bought headroom for a reason that has now expired: all eight
    // step-2 lanes have pushed, so an exact number no longer goes red on every
    // sibling push. Seven is what the filter above actually returns at
    // `218564230`, and a ceiling twelve above the truth is twelve screens a
    // regression can hide in — which is the ratchet failing at the one job it
    // has. It may only ever fall again. The seven are `DEF-CWP-4936`'s and each
    // needs the literal on its success branch, as `bills/BillDetail.tsx`,
    // `usage/Usage.tsx` and now `payments/PayNowCheck.tsx` do.
    const CEILING = 7;
    // ⚠ **COMMENTS ARE STRIPPED BEFORE THE LITERAL IS LOOKED FOR, AND THAT IS
    // NOT TIDINESS — IT IS THE WHOLE POINT (`CR-085`, 2026-09-11).** This census
    // exists to protect `g100_every_screen_has_a_door.py` and
    // `g103_holds_cannot_rot.py`, and **`g100` strips comments before it
    // matches.** Reading the raw source instead let a file satisfy THIS check
    // with a comment while staying invisible to the gate this check is FOR.
    // It was live: `home/Home.tsx` carried the sentence
    // `// the loading branch carried no data-screen="CWP-022" at all` two
    // hundred lines above its render, so it left this list while `g100` still
    // read it as the FRAME — and a frame's doors are credited to every screen,
    // which is `g100` reporting reachability it has not proven. Home had NINE
    // doors, more than `GuestFrame` or `PortalShell`, the two real frames.
    // A guard that measures something narrower than the guard it protects is a
    // guard with a hole exactly the width of the difference.
    const stripComments = (src: string) =>
      src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    const propOnly = walk(ROOT)
      .map((full) => ({ rel: full.slice(ROOT.length), source: nodeFs.readFileSync(full, "utf8") }))
      .filter((f) => /<PortalScreen\s/.test(f.source))
      .filter((f) => !/data-screen="CWP-\d+"/.test(stripComments(f.source)))
      .map((f) => f.rel)
      .sort();
    expect(
      propOnly.length,
      `${propOnly.length} portal file(s) declare a screen id ONLY through the ` +
        `PortalScreen prop, and the ceiling is ${CEILING} (DEF-CWP-4936). ` +
        `g100_every_screen_has_a_door.py reads a file with no literal ` +
        `data-screen="CWP-…" as the FRAME, so those screens' doors are credited ` +
        `to every screen at once; g103_holds_cannot_rot.py stops scanning them ` +
        `for expired holds. Keep the literal on the success branch, as ` +
        `bills/BillDetail.tsx and usage/Usage.tsx do. The list: ` +
        JSON.stringify(propOnly),
    ).toBeLessThanOrEqual(CEILING);
  });

  it("nobody re-invents a second page head inside a screen", () => {
    // `DEF-CWP-3655` deleted the portal's own `PageHead`; `CWP-012` still had
    // one hand-rolled inside its card until DEF-CWP-4000 — a `SectionTitle`
    // for the kicker and a bare `<h2>` for the title. A screen writing its own
    // heading element is that pattern coming back, and it is how the portal
    // acquired two `TwoCol`s and three `Panel`s.
    //
    // ⚠ **ONE SHAPE IS NOT A PAGE HEAD AND IS LEFT OUT BY NAME: the hidden h1
    // of a CORRECTLY_HEADLESS screen** (`DEF-CWP-10563`; PO/QA 2026-10-23,
    // Group D ruling 2 — *"Signed-in Home gets an h1 that is hidden from sight
    // and read by screen readers … Nothing on screen changes."*). It draws
    // nothing, so it cannot be a second visible head; any OTHER `<h1>` in such a
    // file — or a hidden one anywhere else — is still counted.
    const hiddenH1 = /<h1 className="sr-only">/g;
    const handRolled = screenFiles()
      .filter((f) => !(f.rel in OWN_HEADING_T7))
      .filter((f) =>
        /<h1[\s>]/.test(f.rel in CORRECTLY_HEADLESS ? code(f.source).replace(hiddenH1, "") : code(f.source)),
      )
      .map((f) => f.rel);
    expect(
      handRolled,
      "a portal screen writes its own <h1>. The page head owns the heading — " +
        "compose components/PageHeader.tsx instead.",
    ).toEqual([]);
  });
});
