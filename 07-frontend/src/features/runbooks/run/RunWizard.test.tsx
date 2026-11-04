/* ══════════════════════════════════════════════════════════════════════════
 * CR-075 wave C · C4 — RBS-005's Check path, region by region
 * ══════════════════════════════════════════════════════════════════════════
 * MOUNTED UNDER THE REAL PATH PATTERN, AND THAT IS NOT A DETAIL
 * -------------------------------------------------------------
 * `DEF-CWP-3925`: the portal's front page was tested inside a bare
 * `MemoryRouter` with no `/:tenant/portal` route, so `useParams().tenant` came
 * back undefined and every address the page built came out `//portal/…` — a
 * protocol-relative URL to another host, which reads as a perfectly good string
 * to `toContain`. The one assertion that could have caught it was unwritable.
 *
 * So every render below goes through `<Routes><Route path="/:tenant/runbooks/
 * :key/run">`, and the address assertions are exact rather than substring:
 * `/silvercreek/runbooks`, never `//runbooks`.
 *
 * WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
 * ---------------------------------------------------
 * Two things, and both are answered:
 *
 *   1. **A missing translation renders as the KEY**, which contains the word it
 *      was named after — so `toContain("Stop")` would pass over a broken
 *      catalogue. `@/i18n` is imported, and one case asserts no `runbooks.run.`
 *      key survives into the markup at all.
 *   2. **A region that renders nothing** passes every `not.toContain`. So the
 *      per-region cases assert the region's own `data-` handle is PRESENT
 *      first, and the absence cases name the handle they expect to be gone.
 * ══════════════════════════════════════════════════════════════════════════ */
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { matchRoutes, MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";

import { RunWizard } from "./RunWizard";
import type { RunWizardProps } from "./RunWizard";
import type { RunPhase, StepCatalogueEntry } from "./runWizardModel";

const TENANT = "silvercreek";
const ROUTE = "/:tenant/runbooks/:key/run";
const HERE = `/${TENANT}/runbooks/configuration-check/run`;

/** Runbook 1's ten, exactly as `configuration_check.py` declares them. */
const TEN: StepCatalogueEntry[] = [
  { key: "services_and_units", label: "Services and units" },
  { key: "reference_data", label: "Reference data" },
  { key: "tax", label: "Tax" },
  { key: "plans_in_force", label: "Plans in force" },
  { key: "rate_coverage", label: "Rate coverage" },
  { key: "account_chain", label: "Account chain" },
  { key: "meters", label: "Meters" },
  { key: "reads_and_windows", label: "Reads and windows" },
  { key: "documents", label: "Documents" },
  { key: "books", label: "Books" },
];

const BASE: RunWizardProps = {
  runbookName: "Can we bill?",
  runbookTo: `/${TENANT}/runbooks/configuration-check`,
  phase: "scoping",
  // `BR-RBS-042` — the runbook's four DECLARED INPUTS, in its own order.
  inputs: [
    { id: "report", label: "Report", value: "Blockers and warnings" },
    { id: "usage_to_cover", label: "Usage to cover", value: "Ladder is unbounded" },
    { id: "include_held_accounts", label: "Include held accounts", value: "No" },
    { id: "raise_work_items", label: "Raise work items", value: "Yes" },
  ],
  matches: 1,
  matchesValue: "This utility",
  steps: TEN,
  outcomes: {},
  doneTiles: [
    { id: "blockers", label: "Blockers", value: "3" },
    { id: "warnings", label: "Warnings", value: "6" },
    { id: "clear", label: "Steps clear", value: "7 of 10" },
  ],
  doneHeadline: "3 things stop billing",
  needsYou: [],
  needsYouSubjectLabel: "Affects",
  downloads: [
    { id: "findings", label: "Findings", href: `/api/${TENANT}/runbooks/runs/r1/results/done.csv` },
  ],
  review: <div data-probe="review-slot">the result renderer goes here</div>,
  onStart: () => undefined,
  onSaveDraft: () => undefined,
  onCancel: () => undefined,
  onStop: () => undefined,
  onRetry: () => undefined,
  onTellSupport: () => undefined,
  onStepSelect: () => undefined,
};

function draw(overrides: Partial<RunWizardProps> = {}): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[HERE]}>
      <Routes>
        <Route path={ROUTE} element={<RunWizard {...BASE} {...overrides} />} />
      </Routes>
    </MemoryRouter>,
  );
}

function at(phase: RunPhase, overrides: Partial<RunWizardProps> = {}): string {
  return draw({ phase, ...overrides });
}

/**
 * What a CLERK reads, with every tag and attribute removed.
 *
 * ⚠ B14 rule 31's own amendment says to read the value as `innerText`, never as
 * markup: *"this rule's own sentence puts the internal value on `title`, so a
 * check over the DOM string goes RED on a correct fix and green on the
 * breach"*. This screen stamps `data-screen="RBS-005"` — the handle every
 * hold-expiry check in this module reads — and a naive scan of the markup would
 * report that as an internal id on screen.
 */
function visibleText(markup: string): string {
  return markup.replace(/<[^>]*>/g, " ");
}

describe("the frame every state shares", () => {
  it("stamps the screen id, which is what a hold-expiry test elsewhere reads", () => {
    expect(draw()).toContain('data-screen="RBS-005"');
  });

  it("draws ONE page head — B14 rule 2 — with the runbook's name and no id", () => {
    const markup = draw();
    expect(markup.match(/<h1/g) ?? []).toHaveLength(1);
    expect(markup).toContain("Can we bill?");
    // B14 rule 31: no rule, story, defect or question number reaches a clerk —
    // read as TEXT, because the screen id rides on `data-screen` by design.
    expect(visibleText(markup)).not.toMatch(/\b(BR|US|OQ|DEF|TC|RBS)-\d/);
  });

  it("B14 rule 31 — nothing internal is visible in ANY of the five states", () => {
    for (const phase of ["scoping", "checking", "checkFailed", "review", "done"] as RunPhase[]) {
      const text = visibleText(at(phase));
      expect(text, phase).not.toMatch(/\b(BR|US|OQ|DEF|TC|RBS|S1\d\d)-?\d/);
      // …and no step KEY either: a clerk reads *Reads and windows*, never
      // `reads_and_windows`.
      expect(text, phase).not.toContain("reads_and_windows");
    }
  });

  it("B14 rule 1 — the ← is a REAL link out, not an arrow drawn into a string", () => {
    const markup = at("scoping");
    expect(markup).toContain(`href="/${TENANT}/runbooks/configuration-check"`);
    // …and never a protocol-relative address, which is DEF-CWP-3925's shape.
    expect(markup).not.toContain('href="//');
  });

  it("RBS-005.6 drops the ← once the run is over, and keeps the words", () => {
    const done = at("done");
    expect(done).toContain("Can we bill?");
    expect(done).not.toContain(`href="/${TENANT}/runbooks/configuration-check"`);
  });

  it("draws the four-step rail with the phase's cell current", () => {
    const markup = at("checking");
    for (const step of ["scope", "checking", "review", "done"]) {
      expect(markup, step).toContain(`data-run-step="${step}"`);
    }
    expect(markup).toContain('data-run-step="checking" data-state="current"');
    expect(markup).not.toContain('data-run-step="approve"');
  });

  it("every catalogue key resolves — a missing one renders as the key itself", () => {
    for (const phase of ["scoping", "checking", "checkFailed", "review", "done"] as RunPhase[]) {
      expect(at(phase), phase).not.toContain("runbooks.run.");
    }
  });
});

describe("RBS-005.1 · Scope — five regions in this order", () => {
  it("region 3 · the declared INPUTS and what the scope matched", () => {
    const markup = at("scoping");
    expect(markup).toContain('data-run-scope="inputs"');
    for (const row of BASE.inputs) {
      expect(markup, row.id).toContain(`data-run-input="${row.id}"`);
      expect(markup).toContain(row.label);
    }
    expect(markup).toContain('data-run-input="matches"');
    expect(markup).toContain("This utility");
  });

  it("B14 rule 16 — a wizard summary table carries NO pagination footer", () => {
    // Rule 16 exempts wizard summary tables by name. The absence is asserted so
    // a later lane adding a pager meets a red instead of a review comment.
    expect(at("scoping")).not.toContain("data-listpager");
  });

  it("region 4 · the consequence box sits ABOVE the button row (B14 rule 11)", () => {
    const markup = at("scoping");
    const box = markup.indexOf("data-consequence");
    const start = markup.indexOf('data-run-action="start"');
    expect(box).toBeGreaterThan(-1);
    expect(start).toBeGreaterThan(-1);
    expect(box).toBeLessThan(start);
  });

  it("region 4 · both lines are true of a CHECK, and each is under six words", () => {
    const markup = at("scoping");
    expect(markup).toContain("This step sends nothing.");
    expect(markup).toContain("You will see everything first.");
    // The ladder's promise of a later send is NOT carried onto a Check path:
    // `BR-RBS-002` gives it no writer at all.
    expect(markup).not.toContain("Nothing is sent until you approve.");
    expect(markup).toContain("This check changes nothing.");
  });

  it("region 5 · one primary, then secondary, then a GHOST cancel", () => {
    const markup = at("scoping");
    expect(markup).toContain('data-variant="primary" data-size="default"');
    expect(markup).toMatch(/data-variant="ghost"[^>]*data-run-action="cancel"/);
    // `BR-RBS-002`: nothing on the Check path commits, so nothing is danger.
    expect(markup).not.toContain('data-variant="danger"');
  });

  it("region 5 · a one-subject Check does not offer 'Check these 1'", () => {
    expect(at("scoping")).not.toContain("Check these 1 ");
    expect(at("scoping")).toContain("Run this check");
    // …and above one it is the sheet's own words with the sheet's own number.
    expect(at("scoping", { matches: 1004, matchesValue: "1,004 accounts" })).toContain(
      "Check these 1,004",
    );
  });
});

describe("RBS-005.2 · Checking — five regions in this order", () => {
  it("region 1 · Stop is the danger tier and the small size (B14 rules 5, 6)", () => {
    expect(at("checking")).toMatch(
      /data-variant="danger" data-size="sm"[^>]*data-run-action="stop"/,
    );
  });

  it("regions 3 and 4 · the bar reports STEPS, and the label is a percentage", () => {
    const markup = at("checking", {
      outcomes: {
        services_and_units: { state: "done", detail: "11 services · 2s" },
        reference_data: { state: "done", detail: "2 series · 1s" },
      },
    });
    expect(markup).toContain('data-run-bar=""');
    expect(markup).toContain('aria-valuenow="20"'); // 2 of 10
    expect(markup).toContain("2 of 10 steps");
    expect(markup).toContain("20% done");
    // The sheet's "About 25 seconds left" is a time estimate nothing in this
    // product can make: a Check runs synchronously and no job measures a rate.
    expect(markup).not.toContain("seconds left");
  });

  it("region 5 · RBR-01 — all ten steps are drawn before the first one starts", () => {
    const markup = at("scoping");
    // Even on the Scope screen the list is not yet drawn (the region belongs to
    // Checking) — so assert it on the first frame of the run instead, which is
    // what "before the first one starts" means on screen.
    expect(markup).not.toContain('data-run-progress=""');

    const first = at("checking", { outcomes: {} });
    expect(first).toContain('data-run-progress=""');
    for (const step of TEN) {
      expect(first, step.key).toContain(`data-run-progress-step="${step.key}"`);
      expect(first).toContain(step.label);
    }
  });

  it("region 5 · not one row is blank, with nothing served for any step", () => {
    // `DEF-RBS-4286` — this is the state the product can actually serve today.
    const markup = at("checking", { outcomes: {} });
    const rows = markup.split('data-run-progress-step="').slice(1);
    expect(rows).toHaveLength(10);
    for (const row of rows) {
      const cell = row.slice(0, row.indexOf("</li>"));
      const speaks =
        cell.includes("data-run-progress-why") || cell.includes('data-state="current"');
      expect(speaks, `a step drew blank: ${cell.slice(0, 40)}`).toBe(true);
    }
  });

  it("region 5 · the five marker states are five different tones", () => {
    const markup = at("checkFailed", {
      outcomes: {
        services_and_units: { state: "done", detail: "1,004" },
        reference_data: { state: "failed", reason: "Could not read protections.", detail: "stopped" },
        tax: { state: "skipped", reason: "Not configured" },
      },
    });
    expect(markup).toContain('data-state="done"');
    expect(markup).toContain('data-state="failed"');
    expect(markup).toContain('data-state="skipped"');
    expect(markup).toContain('data-state="waiting"');
    expect(markup).toContain("bg-success-500");
    expect(markup).toContain("bg-danger-500");
    expect(markup).toContain("bg-neutral-300");
    expect(markup).toContain("bg-neutral-500");
  });
});

describe("RBS-005.8 · a check itself failed — three regions", () => {
  const FAILED = {
    outcomes: {
      services_and_units: { state: "done" as const, detail: "1,004" },
      reference_data: {
        state: "failed" as const,
        reason: "Could not read protections. Nothing was changed.",
        detail: "stopped",
      },
    },
  };

  it("region 2 · the failed step carries the run's OWN sentence, verbatim", () => {
    expect(at("checkFailed", FAILED)).toContain("Could not read protections. Nothing was changed.");
  });

  it("region 2 · every step after it reads Never reached, never blank", () => {
    const markup = at("checkFailed", FAILED);
    const list = markup.slice(markup.indexOf('data-run-progress=""'));
    const after = list.slice(list.indexOf('data-run-progress-step="tax"'));
    expect(after).toContain("The run did not get this far.");
    // Nothing in the PROGRESS LIST is still running — scoped to the list,
    // because the RAIL correctly leaves *Checking* current on a failed run.
    expect(list).not.toContain('data-state="current"');
    expect(markup).toContain('data-run-step="checking" data-state="current"');
  });

  it("region 2 · the bar is gone — a frozen bar reads as a run still going", () => {
    expect(at("checkFailed", FAILED)).not.toContain('data-run-bar=""');
  });

  it("region 3 · Try again and Tell support, both small, one primary", () => {
    const markup = at("checkFailed", FAILED);
    expect(markup).toMatch(/data-variant="primary" data-size="sm"[^>]*data-run-action="retry"/);
    expect(markup).toMatch(
      /data-variant="secondary" data-size="sm"[^>]*data-run-action="tell-support"/,
    );
  });

  it("the frame's own caption never ships — B14 rules 31 and 32", () => {
    // `08-screen-layouts.md` warns that RBS-005.7 and RBS-005.8 still caption
    // themselves `S151.8 · a check itself failed` INSIDE the drawing, and that
    // neither string may ship.
    expect(at("checkFailed", FAILED)).not.toContain("S151");
  });
});

describe("RBS-005.6 · Done — five regions in this order", () => {
  const ROWS = {
    needsYou: [
      {
        id: "n1",
        subject: "Nunes, R.",
        outcome: { label: "Failed", tone: "danger" as const },
        detail: "No deliverable address",
        fix: { label: "Add an address", to: `/${TENANT}/premises/p-42` },
      },
    ],
  };

  it("region 1 · the downloads are real files that LEAVE the app", () => {
    const markup = at("done");
    expect(markup).toContain('data-run-download="findings"');
    expect(markup).toContain(`href="/api/${TENANT}/runbooks/runs/r1/results/done.csv"`);
    expect(markup).toContain("↓ Findings");
  });

  it("region 3 · the KPI strip draws the run's own tiles", () => {
    const markup = at("done");
    expect(markup).toContain("kpi-grid");
    expect(markup).toContain("Blockers");
    expect(markup).toContain("Steps clear");
  });

  it("region 4 · the first column is the RUNBOOK's word, not always Account", () => {
    // `RBS-005.6` is drawn on the collections ladder, where every row IS an
    // account. Runbook 1's findings are about a tax region and a rate ladder,
    // so the heading comes from the runbook — the engine's own word for that
    // column is *Affects*. `runbooks.run.done.col.account` stays in the eleven
    // catalogues for the ladder's own route to pass.
    expect(at("done", ROWS)).toContain("Affects");
    expect(at("done", { ...ROWS, needsYouSubjectLabel: "Account" })).toContain("Account");
  });

  it("region 4 · every failed row carries a fix route (BR-RBS-011)", () => {
    const markup = at("done", ROWS);
    expect(markup).toContain('data-run-needs-you="rows"');
    expect(markup).toContain('data-run-fix="n1"');
    expect(markup).toContain(`href="/${TENANT}/premises/p-42"`);
    expect(markup).toContain("Add an address");
    // The account's NAME, never its id (B14 rule 31).
    expect(markup).toContain("Nunes, R.");
    expect(markup).not.toContain("p-42<");
  });

  it("region 4 · an empty list is a STATED outcome, never an empty table", () => {
    const markup = at("done");
    expect(markup).toContain('data-run-needs-you="empty"');
    expect(markup).toContain("Nothing needs you.");
    expect(markup).toContain("Every record came back clean.");
  });

  it("region 5 · both ways on are REAL links, so neither can rot", () => {
    // `DEF-CWP-3925` — a nav word that is a `<span>`, or a card whose control
    // still refuses over a screen that shipped days ago. Both of these are
    // ordinary links: the day RBS-007 and RBS-001 land, they simply open.
    const markup = at("done", ROWS);
    expect(markup).toMatch(
      new RegExp(`<a[^>]*data-run-action="work-list"[^>]*href="/${TENANT}/runbooks/work"`),
    );
    expect(markup).toMatch(
      new RegExp(`<a[^>]*data-run-action="runbooks"[^>]*href="/${TENANT}/runbooks"`),
    );
    expect(markup).not.toContain('href="//');
  });
});

describe("Review is the RESULT RENDERER's, and this screen only holds the slot", () => {
  it("draws whatever it was handed, and writes no report renderer of its own", () => {
    const markup = at("review");
    expect(markup).toContain('data-probe="review-slot"');
    // Two implementations of one report is `DEF-RBS-4284`'s whole shape; this
    // screen composes `RBS-006` (task C2) rather than inventing a second.
    expect(markup).not.toContain('data-block="');
  });

  it("the slot is REQUIRED, so a caller cannot leave it dead", () => {
    // A compile-time claim, asserted at runtime as far as a test can: the prop
    // is not optional in `RunWizardProps`, so `tsc` refuses a caller that omits
    // it. This case pins the behaviour that makes that worth doing.
    const custom: ReactNode = <p data-probe="other">something else</p>;
    expect(at("review", { review: custom })).toContain('data-probe="other"');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// *Open work list →* LANDS ON RBS-007 — BY ADDRESS AND BY SCREEN ID
// ══════════════════════════════════════════════════════════════════════════
// `DEF-RBS-9136`. The address used to be a `workListTo` prop that no screen
// passed, and this file — its only supplier — handed it `/runbooks/work-list`
// and then asserted the string it had just supplied, so it could never
// disagree with the router. The router opens that address as `RBS-004`, the
// setup screen for a runbook keyed `work-list`, because `runbooks/:key`
// swallows any word it is given. So these two cases ask the REAL route table
// and the REAL source, never this file's own fixture:
//   1. BY ADDRESS — the href the button draws is matched by `APP_ROUTES` with
//      the `runbooks/work` pattern of its own, not by `runbooks/:key`;
//   2. BY SCREEN ID — the component that route mounts declares `RBS-007`.
// Proved red first: put `/runbooks/work-list` back in `DoneStep` and (1) fails
// naming `runbooks/:key`; rename `data-screen` in `WorkList.tsx` and (2) fails.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

function workListHref(): string {
  const found = at("done").match(/<a[^>]*data-run-action="work-list"[^>]*href="([^"]*)"/);
  expect(found, "the Done step no longer draws Open work list → as a link").not.toBeNull();
  return found?.[1] ?? "";
}

describe("Open work list → opens RBS-007, the work list (DEF-RBS-9136)", () => {
  it("BY ADDRESS — the real route table matches the href with runbooks/work, not runbooks/:key", () => {
    const href = workListHref();
    expect(href).toBe(`/${TENANT}/runbooks/work`);
    const matched = matchRoutes(APP_ROUTES, href) ?? [];
    const leaf = matched[matched.length - 1]?.route?.path ?? "";
    expect(
      leaf,
      `Open work list → points at ${href} and the router matches it with "${leaf}" — ` +
        `runbooks/:key would open RBS-004 for a runbook of that name, not the work list.`,
    ).toBe("runbooks/work");
  });

  it("BY SCREEN ID — the screen mounted at that route declares RBS-007", () => {
    // Comments stripped first: a sentence ABOUT `data-screen="RBS-007"` is not
    // a screen declaring it (homeHoldExpiry.test.tsx's `codeOf`, same reason).
    const file = nodeUrl.fileURLToPath(new URL("../work/WorkList.tsx", import.meta.url));
    const code = nodeFs
      .readFileSync(file, "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, " ")
      .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
    expect(code).toContain('data-screen="RBS-007"');
  });
});
