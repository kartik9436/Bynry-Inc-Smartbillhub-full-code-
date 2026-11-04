// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-020 (EP-SHL-01)  Screens: the eight that will use it
// Rules:    BR-SHL-044 (a) per-tab primary action · (b) per-tab explainer,
//           below the strip · (c) a tab may have NO header action
// ───────────────────────────────────────────────────────
// TC numbering follows US-SHL-020. TCs that need a live browser (clicking
// between tabs) are honest it.todo → Playwright, per the shell convention.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PageHeader } from "./PageHeader";
import type { PageHeaderTab } from "./PageHeader";

// The prototype's own Plans & Rates configuration (PO walk, 2026-08-10).
const TABS: PageHeaderTab[] = [
  {
    id: "plans",
    label: "Plans",
    explainer: "A plan is what customers subscribe to.",
    primaryAction: <button type="button">+ New plan</button>,
  },
  {
    id: "rates",
    label: "Rate schedules",
    explainer: "Rate schedules define pricing formulas.",
    primaryAction: <button type="button">+ New rate schedule</button>,
  },
  // Meter detail → Audit: a tab with NO header action and NO explainer.
  { id: "audit", label: "Audit" },
];

function render(activeTabId: string, extra: Record<string, unknown> = {}): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <PageHeader
        title="Plans & Rates"
        kicker="PLANS"
        tabs={TABS}
        activeTabId={activeTabId}
        {...extra}
      />
    </MemoryRouter>,
  );
}

describe("B14 rule 2 · the action row holds ACTIONS (DEF-966)", () => {
  // ⚠ **WHAT THIS CAN AND CANNOT CLAIM.** It cannot see a wrapped row: jsdom
  // computes no layout, the markup is identical wrapped or not, and no gate in
  // this repo reads rendered output (hard-won law 6). DEF-966 was found by the
  // Product Owner looking at a screen, twice, and that is still the only
  // instrument that can find it.
  //
  // What it CAN hold is the decision that makes the wrap unlikely: **state is
  // not an action, so it is not in the action row.** That is a structural fact
  // a render can check, it is the property `margin-left: auto` could not give
  // (it fixed WHERE a wrapped row aligns, not WHY it wraps), and it is the one
  // that shrinks the row on ~20 detail screens at once.
  const STATE = "STATE-PILL";
  const ACTION = "PRIMARY-ACTION";

  function headOf(html: string): { actions: string; identity: string } {
    const actionsAt = html.indexOf("page-header-actions");
    return {
      identity: html.slice(html.indexOf("page-header-id"), actionsAt),
      actions: html.slice(actionsAt),
    };
  }

  it("renders the status with the IDENTITY and never in the action row", () => {
    const head = headOf(
      render("plans", { status: <span>{STATE}</span>, secondaryActions: <button>{ACTION}</button> }),
    );
    expect(head.identity).toContain(STATE);
    expect(head.actions).not.toContain(STATE);
  });

  it("still puts the actions in the action row — the move is one-directional", () => {
    // `secondaryActions` rather than `primaryAction`, because TAB CONFIG WINS
    // for the primary slot (addendum r2) and `TABS.plans` already declares one.
    const head = headOf(
      render("plans", { status: <span>{STATE}</span>, secondaryActions: <button>{ACTION}</button> }),
    );
    expect(head.actions).toContain(ACTION);
    expect(head.identity).not.toContain(ACTION);
  });

  it("keeps a pill and its honest-absence note on ONE line together (BR-SHL-025)", () => {
    // BIL-02 passes both: an "Issued" pill and a "Past-due unknown" note. They
    // are one fact in two parts and must not stack.
    const html = render("plans", {
      status: (
        <>
          <span>Issued</span>
          <span>Past-due unknown</span>
        </>
      ),
    });
    const row = html.slice(html.indexOf("page-header-id"), html.indexOf("page-header-actions"));
    expect(row).toContain("flex-wrap");
    expect(row).toContain("items-center");
    expect(row.indexOf("Issued")).toBeLessThan(row.indexOf("Past-due unknown"));
  });

  it("renders no state row at all when a screen passes no status", () => {
    // A row that appears and disappears would move the title, which is TC-3's
    // whole point one element over.
    const html = render("plans");
    const identity = html.slice(html.indexOf("page-header-id"), html.indexOf("page-header-actions"));
    expect(identity).not.toContain("mt-2 flex flex-wrap");
  });
});

describe("US-SHL-020 — one page header (BR-SHL-044)", () => {
  it("TC-1: the primary action is per-TAB, in the same slot", () => {
    expect(render("plans")).toContain("+ New plan");
    expect(render("plans")).not.toContain("+ New rate schedule");
    expect(render("rates")).toContain("+ New rate schedule");
    expect(render("rates")).not.toContain("+ New plan");
  });

  it("TC-2: the explainer changes with the tab and sits BELOW the strip", () => {
    const html = render("rates");
    expect(html).toContain("Rate schedules define pricing formulas.");
    expect(html.indexOf("page-header-tabs")).toBeLessThan(html.indexOf("page-header-explainer"));
  });

  it("TC-3: a tab may have NO header action, and the action row still renders", () => {
    const html = render("audit");
    expect(html).toContain("page-header-actions"); // present, so nothing shifts
    expect(html).not.toContain("+ New");
  });

  it("TC-5: the back link renders on detail screens and nowhere else", () => {
    expect(render("plans")).not.toContain("page-header-back");
    expect(render("plans", { backTo: { to: "/assets", label: "Assets" } })).toContain("← Assets");
  });

  it("TC-6: a header can never offer two primary actions", () => {
    // One active tab ⇒ exactly one primaryAction is ever rendered. Guarding the
    // rule here means a screen cannot reintroduce a second by configuration.
    const html = render("plans");
    expect((html.match(/\+ New/g) ?? []).length).toBe(1);
  });

  it("TC-10: a tab whose action lives in its BODY renders it in the header slot", () => {
    // Addendum r2. `audit` declares no action of its own, so the button the
    // active tab body handed up through its render prop is what the header
    // shows — in the same slot, not in the body.
    const html = render("audit", {
      primaryAction: <button type="button">+ New charge code</button>,
    });
    expect(html).toContain("+ New charge code");
    expect(html.indexOf("page-header-actions")).toBeLessThan(html.indexOf("+ New charge code"));
  });

  it("TC-6 (r2): config and render-prop together still yield ONE primary", () => {
    // Both routes into the slot are live at once. The tab's own config wins and
    // the render-prop action is dropped, so a screen cannot stack two primaries
    // by wiring both — the law holds without the screens having to be careful.
    const html = render("plans", {
      primaryAction: <button type="button">+ New charge code</button>,
    });
    expect(html).toContain("+ New plan");
    expect(html).not.toContain("+ New charge code");
    expect((html.match(/\+ New/g) ?? []).length).toBe(1);
  });

  it("TC-7 (neg): a tab with no explainer renders no empty paragraph", () => {
    expect(render("audit")).not.toContain("page-header-explainer");
  });

  it("renders title, kicker and roll-up in the prototype's order", () => {
    const html = render("plans", { rollup: <span>6 plans · 4 rate schedules</span> });
    // ⚠ `"<h1"` AND NOT `"<h1>"` — B14 rule 40 (2026-09-12) put a class on this
    // element, and a matcher keyed to the bare tag answered **-1** for "the
    // title is nowhere on this page" while the title was right there. The
    // assertion below is about ORDER and is unchanged; only the way it finds
    // the title moved. A negative index compares as less-than everything, so
    // this exact shape can report the order as correct when it has lost the
    // element entirely — which is why the index is asserted non-negative first.
    const title = html.indexOf("<h1");
    expect(title).toBeGreaterThan(-1);
    expect(html.indexOf("kicker")).toBeLessThan(title);
    expect(title).toBeLessThan(html.indexOf("page-header-rollup"));
  });

  it("falls back to the first tab when no active id is given", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <PageHeader title="Plans & Rates" tabs={TABS} />
      </MemoryRouter>,
    );
    expect(html).toContain("+ New plan");
  });

  it("selects NO tab when the active id belongs to a sibling destination", () => {
    // Plans & Rates → History: the prototype gives History a top-right button
    // rather than a fifth tab, so the strip is drawn with nothing selected.
    // Falling back to the first tab here would put the Plans explainer and the
    // "+ New plan" button on a screen that is not Plans.
    const html = render("history");
    expect(html).toContain("page-header-tabs");
    expect(html).not.toContain("+ New plan");
    expect(html).not.toContain("A plan is what customers subscribe to.");
    expect(html).not.toContain('aria-selected="true"');
  });

  it.todo("TC-4: Meter detail carries Reassign/Log repair/Retire — screen conversion");
  it.todo("TC-8 (isolation): header content is per-tenant — screen conversion");
  it.todo("TC-9: visual conformance diff against the prototype frame");
});

/**
 * ⚠ **TWO PRODUCT-OWNER REPORTS OF 2026-09-03 ARE FIXED ENTIRELY IN CSS, AND
 * NOTHING IN THIS REPO READS RENDERED OUTPUT** — B14's own status table says so
 * in one line: *"most are RATIFIED and UNENFORCED, because no gate in this repo
 * reads rendered output"*. A markup assertion cannot see either fix: the class
 * names do not change, the DOM order does not change, and every existing case
 * in this file passes with the declarations removed again.
 *
 * So the guard reads the STYLESHEET. It is the same move
 * `notificationsLayout.dom.test.tsx` makes for the same reason, and it is not a
 * substitute for looking at the screen — it is the thing that fails when a
 * later lane tidies a declaration away without knowing which report it closed.
 *
 * Both were proved RED before they were trusted green: deleting
 * `margin-bottom` from `.page-header-tabs` fails the first case naming that
 * property, and deleting `flex: 1 1 16rem` from `.page-header-id` fails the
 * second.
 */
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  // ⚠ **`URL | string`, NOT `string` — DEF-2354.** The first draft of this
  // block declared the parameter as `string` and handed it a `URL`, which
  // vitest does not care about and `tsc --noEmit` does: it put the branch's
  // typecheck in the red for one commit, and a full green suite of 4,000+
  // cases said nothing about it, because a test run is not a typecheck. The
  // signature is copied verbatim from the two suites that already declare it
  // — `styles/routeBUtilities.test.ts` and
  // `features/notifications/notificationsLayout.dom.test.tsx` — rather than
  // invented a third time.
  fileURLToPath(url: URL | string): string;
};
const PAGE_HEADER_CSS = nodeFs.readFileSync(
  `${nodeUrl.fileURLToPath(new URL(".", import.meta.url))}PageHeader.css`,
  "utf8",
);

/** One rule's declaration block, by selector, with comments stripped. */
function declarations(selector: string): string {
  const body = PAGE_HEADER_CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  const at = body.indexOf(`${selector} {`);
  expect(at, `${selector} is declared in PageHeader.css`).toBeGreaterThanOrEqual(0);
  return body.slice(at, body.indexOf("}", at));
}

describe("the two 2026-09-03 layout reports, held at the declaration", () => {
  it('DEF-3481: the tab strip declares a gap below it — "toolkit is got atatched the Tab line"', () => {
    // The PO's words: *"toolkit is got atatched the Tab line , tehre is no
    // seperations - this is problem on many screens"*. The strip ended at its
    // 1px underline and declared nothing below, so `.table-toolbar` — which
    // sets `margin-bottom` and no `margin-top` — began on that line.
    expect(declarations(".page-header-tabs")).toContain("margin-bottom");
  });

  it('DEF-3482: the identity column may SHRINK, so the actions stay on the title line', () => {
    // The PO's words: *"on this screen Buttons are misplaced - as per UI rule,
    // we have all Buttons on Top right"*. `.page-header-top` wraps, and this
    // column sized from its content — an address chain plus one chip per
    // service — so on the screens with the most to say the action row was
    // pushed onto a line of its own beneath the roll-up.
    expect(declarations(".page-header-id")).toContain("flex: 1 1 16rem");
    // DEF-966's own fix stays: a row that DOES wrap still lands right, and the
    // buttons themselves never shrink — they wrap.
    const actions = declarations(".page-header-actions");
    expect(actions).toContain("margin-left: auto");
    expect(actions).toContain("flex-wrap: wrap");
    expect(actions).toContain("justify-content: flex-end");
    expect(actions).toContain("flex-shrink: 0");
  });
});

describe("B14 rule 40 · the page-head title is 32px, at whatever heading level", () => {
  // ⚠ **WHAT THIS CAN AND CANNOT CLAIM, SAID FIRST.** It asserts the component
  // EMITS the size class. It cannot tell you the class renders: a Tailwind
  // utility written in a file absent from `styles/route-b-migrated.txt` is in
  // the DOM and styles nothing, and this assertion passes either way (the
  // skill's §7.1). The measurement that closes that gap is
  // `10-scripts/render-checks/cr093-page-title-size.mjs`, which reads
  // `getComputedStyle` against the BUILT stylesheet at 1280 and 1440. Neither
  // check is sufficient alone and this comment exists so the next reader does
  // not delete one believing the other covers it.
  //
  // B14 rule 40, PO 2026-09-12: *"use 32 pixels — for every ordinary screen"*,
  // confirmed *"Please use 32 pixels"*. `DEF-SHL-4947`: 136 of the 137 files
  // mounting this component drew their title at `--text-h1` 40px — the size
  // `tokens.css` reserves for a full-page wizard — because this component
  // rendered a bare `h1` and `global.css` sizes a bare `h1` at 40px.

  it("an ordinary screen keeps its h1 AND gets the 32px size", () => {
    const html = render("overview");
    // The level is the document outline's business: one h1 per page.
    expect(html).toContain("<h1");
    expect(html).not.toContain("<h2");
    // The size is set explicitly, so it no longer follows from the tag.
    expect(html).toMatch(/<h1[^>]*class="[^"]*\btext-h2\b/);
  });

  it("a head nested under another page's h1 drops the LEVEL and keeps the SIZE", () => {
    // `TemplateDetail` is the one legitimate caller: it is drawn inside
    // Settings, which has already written "Settings" as the document's h1, and
    // two h1s is two page titles in one outline. Before rule 40 this prop was
    // also the ONLY way to get 32px, which is why a screen wanting the right
    // size had to surrender its h1 — the thing rule 40 decouples.
    const html = render("overview", { titleAs: "h2" });
    expect(html).toContain("<h2");
    expect(html).not.toContain("<h1");
    expect(html).toMatch(/<h2[^>]*class="[^"]*\btext-h2\b/);
  });

  it("no page head asks for the wizard size — rule 2 says every screen shares this head", () => {
    // B14 rule 2 is RATIFIED and reads "One page header. Every screen,
    // including task pages and workflows" — and 15 wizards mount this
    // component. A second size for them would re-create the very defect rule 40
    // closes, whose title is *two page-title sizes and nothing splits them by
    // kind*. `--text-h1` stays a token; it is simply not a page head.
    expect(render("overview")).not.toContain("text-h1");
    expect(render("overview", { titleAs: "h2" })).not.toContain("text-h1");
  });
});


// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-020@9941789 (EP-SHL-01)
// generated: 2026-08-10 by Eng-Lead (prevention session 1)
// checklist: A✔ B✔ C✔ D=deferred(no API call) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: vitest✔ tsc✔ suite✔ run_gates 12-PASS✔
// exceptions: TC-4/TC-8 need the screen conversions and TC-9 needs the visual
//         gate — all three are honest it.todo rather than silently absent
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
