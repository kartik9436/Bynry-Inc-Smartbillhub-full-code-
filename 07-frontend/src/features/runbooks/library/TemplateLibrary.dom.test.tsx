// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1. `vite.config.ts` keeps
// the default environment at `node` deliberately (`DEF-523`); an interactive
// suite opts in per file, and without this line every case here dies on
// `ReferenceError: document is not defined`.
// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-018 (EP-RBS-01) — CR-075 wave D task D3.
// Screens: RBS-002.1 · RBS-002.2.
// Rules:   `BR-RBS-025` · `TC-RBS-20` · `BR-RBS-002` · B14 rule 31 · rule 32.
// Defects: DEF-CWP-3925 (mount under the REAL path pattern) · DEF-RBS-4309 ·
//          DEF-RBS-4310.
// ───────────────────────────────────────────────────────
// EVERY CASE ASSERTS A RULE — a count, a missing word, a resolved address —
// and none asserts an impression.
//
// ══════════════════════════════════════════════════════════════════════════
// `TC-RBS-20`, AND HOW THIS FILE WAS PROVED RED BEFORE IT WAS TRUSTED GREEN
// ══════════════════════════════════════════════════════════════════════════
// The chip row was FIRST built from a hard-coded list of the sixteen categories
// (`models.CATEGORIES`, transcribed into the component). Run through
// `./node_modules/.bin/vitest` — the runner CI uses, never a different entry
// point (law 7's second half) — the three cases below failed by name:
//
//     × draws one chip per category the SERVER counted, and no others
//       → expected [ 'Platform1', …(15) ] to have a length of 8 but got 16
//     × draws no chip for a category holding no template
//       → Assets holds no template and must draw no chip: expected
//         'Platform1 · Onboarding & Cutover1 · D…' not to contain 'Assets'
//     × counts the LIBRARY and not the page — two rows still draw eight chips
//       → expected [ 'Platform1', …(15) ] to have a length of 8 but got 16
//
// The list was then deleted and the row built from `view.categoryChips`. All
// three went green. **The third case is the one that would still have passed on the
// broken build and is why it exists:** a screen counting `view.rows` also draws
// eight chips for this fixture, because the fixture has all eight categories on
// its page. `SHORT_PAGE` gives the same eight chips over TWO rows, so a
// row-counting screen draws two and this suite says so.
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { TemplateDetail } from "./TemplateDetail";
import { TemplateLibrary } from "./TemplateLibrary";
import type { TemplateLibraryView } from "./TemplateLibrary";
import {
  EIGHT_CHIPS,
  KIND_CHIPS,
  TWELVE_TEMPLATES,
  UNAVAILABLE_TEMPLATE,
} from "./libraryFixture";
import type { TemplateRow } from "./libraryTypes";

const TENANT = "silvercreek";

// ⚠ **THERE IS NO AUTO-CLEANUP IN THIS REPO.** `vite.config.ts` sets no
// `setupFiles`, so `@testing-library/react` registers no `afterEach` of its own
// and each render is ADDED to the same document. Every "exactly N" assertion
// below depends on this line.
afterEach(cleanup);

const NOOP = () => undefined;

const FULL_VIEW: TemplateLibraryView = {
  rows: TWELVE_TEMPLATES,
  total: TWELVE_TEMPLATES.length,
  categoryChips: EIGHT_CHIPS,
  kindChips: KIND_CHIPS,
};

/** The same server chips over a two-row PAGE. A screen counting rows draws two
 *  chips here; a screen reading the payload draws eight. */
const SHORT_PAGE: TemplateLibraryView = {
  ...FULL_VIEW,
  rows: TWELVE_TEMPLATES.slice(0, 2),
};

function mountLibrary(
  view: TemplateLibraryView,
  handlers: Partial<Parameters<typeof TemplateLibrary>[0]> = {},
) {
  // ⚠ THE REAL PATH PATTERN, WITH A REAL SLUG IN IT. A component mounted bare
  // inside a `MemoryRouter` with no `/:tenant/…` route gets `undefined` from
  // `useParams()` and builds every address as `//host/…` — a protocol-relative
  // URL to another host that reads as a perfectly good string to `toContain`
  // (`DEF-CWP-3925`). A fixture that cannot tell a working link from a broken
  // one is how eight dead doors hid behind 391 green cases.
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/runbooks/templates`]}>
      <Routes>
        <Route
          path="/:tenant/runbooks/templates"
          element={
            <TemplateLibrary
              view={view}
              request={{ q: "", kind: "", category: "", page: 1, per: 50 }}
              onSearch={NOOP}
              onKind={NOOP}
              onCategory={NOOP}
              onClearFilters={NOOP}
              onPage={NOOP}
              onPer={NOOP}
              onAdd={NOOP}
              {...handlers}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** The category chips as a person reads them — label and count, in order. */
function categoryChipText(): string[] {
  const row = document.querySelector('[data-chips="category"]');
  const chips = row?.querySelectorAll("[data-category]") ?? [];
  return Array.from(chips, (chip) => (chip.textContent ?? "").trim());
}

describe("TC-RBS-20 — the chips are built from the templates PRESENT", () => {
  it("draws one chip per category the SERVER counted, and no others", () => {
    mountLibrary(FULL_VIEW);
    // Eight, not sixteen. `BR-RBS-025`: a category with no runbook is never
    // drawn as a filter, because a chip that filters to nothing is dead UI.
    expect(categoryChipText()).toHaveLength(EIGHT_CHIPS.length);
  });

  it("draws no chip for a category holding no template", () => {
    mountLibrary(FULL_VIEW);
    const drawn = categoryChipText().join(" · ");
    // `RB-019`'s *done looks like*, word for word: *"none reading Assets or
    // Work."* Four of the sixteen hold nothing in this library.
    for (const absent of ["Assets", "Work", "Customer portal", "Business"]) {
      expect(drawn, `${absent} holds no template and must draw no chip`).not.toContain(absent);
    }
  });

  it("counts the LIBRARY and not the page — two rows still draw eight chips", () => {
    mountLibrary(SHORT_PAGE);
    // The case a row-counting screen fails and a payload-reading screen passes.
    // At twelve templates on one page the two are indistinguishable, which is
    // precisely why this fixture is short.
    expect(categoryChipText()).toHaveLength(EIGHT_CHIPS.length);
    const billing = categoryChipText().find((text) => text.startsWith("Billing"));
    expect(billing, "Billing's count is the server's 4, not the page's 2").toBe("Billing4");
  });

  it("carries the server's kind counts — All 12 · Checks 7 · Actions 5", () => {
    mountLibrary(FULL_VIEW);
    const row = document.querySelector('[data-chips="kind"]');
    const chips = Array.from(row?.querySelectorAll("[data-kind]") ?? []).map((chip) =>
      (chip.textContent ?? "").trim(),
    );
    expect(chips).toEqual(["All12", "Checks7", "Actions5"]);
  });

  it("asks the server for the category rather than filtering the rows here", () => {
    const onCategory = vi.fn();
    mountLibrary(FULL_VIEW, { onCategory });
    const chip = document.querySelector('[data-category="billing"]') as HTMLElement;
    chip.click();
    // `NFR-3`: the filter is the server's. A screen that narrowed its own rows
    // would be right on page 1 and wrong on page 2, which is the shape
    // `DEF-PAY-4221` records four times over.
    expect(onCategory).toHaveBeenCalledWith("billing");
  });
});

describe("RBS-002.1 — the cards", () => {
  it("draws one card per row and no card carries a database id", () => {
    mountLibrary(FULL_VIEW);
    expect(screen.getAllByRole("listitem")).toHaveLength(TWELVE_TEMPLATES.length);
    // B14 rule 31. The wire never sends a template's UUID and this interface has
    // no field for one, so this asserts the guarantee rather than the habit.
    expect(document.body.innerHTML).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/);
  });

  it("opens an ADDED template at the setup screen and offers + Add on one that is not", () => {
    mountLibrary(FULL_VIEW);
    const open = document.querySelector('[data-card-open="configuration_check"]');
    // Asserted BY ADDRESS, never by "there is a link" — `DEF-CWP-3925`'s broken
    // `//portal/…` hrefs were perfectly good strings.
    expect(open?.getAttribute("href")).toBe(`/${TENANT}/runbooks/configuration_check`);
    expect(document.querySelector('[data-card-add="configuration_check"]')).toBeNull();
    expect(document.querySelector('[data-card-add="coverage_grid"]')).not.toBeNull();
  });

  it("sends every card title to the template detail, added or not", () => {
    mountLibrary(FULL_VIEW);
    for (const key of ["configuration_check", "coverage_grid"]) {
      const title = document.querySelector(`[data-card-title="${key}"]`);
      expect(title?.getAttribute("href")).toBe(`/${TENANT}/runbooks/templates/${key}`);
    }
  });

  it("draws NO sentence for a template whose purpose the wire does not carry", () => {
    mountLibrary(FULL_VIEW);
    // `DEF-RBS-4309`. An absent sentence draws nothing at all — no dash, no
    // placeholder, no text this screen invented. A placeholder is
    // indistinguishable from a real empty value and would hide the gap.
    const card = screen.getAllByRole("listitem")[0];
    expect(within(card).queryByText("—")).toBeNull();
    expect(card.querySelectorAll("p")).toHaveLength(0);
  });

  it("draws the sentence the moment the wire carries one, with no other change", () => {
    const described: TemplateRow = {
      ...TWELVE_TEMPLATES[0],
      description: "Finds what stops a bill run before it starts.",
    };
    mountLibrary({ ...FULL_VIEW, rows: [described] });
    expect(
      screen.getByText("Finds what stops a bill run before it starts."),
    ).not.toBeNull();
  });

  it("disables + Add on an unavailable template and RENDERS its reason", () => {
    mountLibrary({ ...FULL_VIEW, rows: [UNAVAILABLE_TEMPLATE] });
    const add = document.querySelector(
      '[data-card-add="budget_billing_relevel"]',
    ) as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    // `DEF-SHL-4043`: a `title` alone opens on hover, after a delay, and NEVER
    // on a touch screen — so twenty screens drew a grey button that said
    // nothing. The reason is TEXT as well.
    expect(screen.getByText("Budget billing is switched off for you.")).not.toBeNull();
    expect(add.getAttribute("title")).toBe("Budget billing is switched off for you.");
  });

  it("draws no chip the server did not count — the Not added chip is absent", () => {
    mountLibrary(FULL_VIEW);
    // `DEF-RBS-4310`. The sheet draws `Not added 5`; no count and no `f.state`
    // filter exist, so drawing it would be either a page-derived number or a
    // chip that filters nothing. Absent, and this is the assertion that keeps it
    // absent until the server can answer.
    const kinds = Array.from(document.querySelectorAll("[data-kind]"), (chip) =>
      chip.getAttribute("data-kind"),
    );
    expect(kinds).toEqual(["all", "check", "action"]);
  });
});

describe("RBS-002.2 — what it can touch", () => {
  function mountDetail(template: TemplateRow) {
    return render(
      <MemoryRouter initialEntries={[`/${TENANT}/runbooks/templates/${template.template_key}`]}>
        <Routes>
          <Route
            path="/:tenant/runbooks/templates/:key"
            element={<TemplateDetail template={template} onAdd={NOOP} />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("says a Check writes Nothing and sends Nothing", () => {
    mountDetail(TWELVE_TEMPLATES[2]); // Coverage grid — a Check, not added
    // The frame's own design note: *"for a Check it always reads Nothing. That
    // single table is what a clerk needs before adding anything."*
    // `BR-RBS-002` is why it can: a Check is CONSTRUCTED with no ports, so the
    // capability is ABSENT rather than withheld.
    const table = document.querySelector("[data-plaintable]") as HTMLElement;
    expect(within(table).getAllByText("Nothing")).toHaveLength(2);
    expect(within(table).getByText("Writes")).not.toBeNull();
    expect(within(table).getByText("Sends")).not.toBeNull();
  });

  it("draws NO Reads and NO Runs for row, because nothing serves them", () => {
    mountDetail(TWELVE_TEMPLATES[2]);
    // `DEF-RBS-4309`. Two rows, not the sheet's four — and the two missing ones
    // are missing rather than dashed.
    const table = document.querySelector("[data-plaintable]") as HTMLElement;
    expect(table.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(within(table).queryByText("Reads")).toBeNull();
    expect(within(table).queryByText("Runs for")).toBeNull();
  });

  it("draws them the moment the wire carries them", () => {
    mountDetail({
      ...TWELVE_TEMPLATES[2],
      reads: "Accounts, plans, reads",
      runs_for: "About 40 seconds",
    });
    const table = document.querySelector("[data-plaintable]") as HTMLElement;
    expect(table.querySelectorAll("tbody tr")).toHaveLength(4);
    expect(within(table).getByText("Accounts, plans, reads")).not.toBeNull();
  });

  it("states the absence for an Action rather than inventing the port map", () => {
    mountDetail(TWELVE_TEMPLATES[4]); // Collections ladder — an Action
    // The wave C lane measured it: thirteen ports, three drawn rows, and one of
    // the three (*Change bills*) maps to no port at all. Inventing the map here
    // would resolve an unstated design question AND break `RB-020`.
    expect(document.querySelector("[data-plaintable]")).toBeNull();
    expect(document.querySelector("[data-touch-absent]")).not.toBeNull();
  });

  it("draws NO What it does list while the step labels are unserved", () => {
    mountDetail(TWELVE_TEMPLATES[2]);
    // `DEF-RBS-4309`. A heading over nothing is furniture, and B14 rule 33 puts
    // rationale at zero words on screen.
    expect(document.querySelector('[data-region="what-it-does"]')).toBeNull();
    expect(document.querySelector('[data-region="what-it-can-touch"]')).not.toBeNull();
  });

  it("draws the step list the moment the labels arrive", () => {
    mountDetail({
      ...TWELVE_TEMPLATES[2],
      step_labels: ["Pick one account per plan", "Price each one", "Group by outcome"],
    });
    const section = document.querySelector('[data-region="what-it-does"]') as HTMLElement;
    expect(section.querySelectorAll("li")).toHaveLength(3);
    expect(within(section).getByText("Group by outcome")).not.toBeNull();
  });

  it("offers ONE primary — Add on a template that is not added, Open on one that is", () => {
    mountDetail(TWELVE_TEMPLATES[2]);
    expect(document.querySelector("[data-detail-add]")).not.toBeNull();
    expect(document.querySelector("[data-detail-open]")).toBeNull();
    cleanup();
    mountDetail(TWELVE_TEMPLATES[0]);
    // B14 rule 4 — one primary, and `+ Add to my runbooks` over an already-added
    // template would be a button onto a duplicate.
    expect(document.querySelector("[data-detail-add]")).toBeNull();
    expect(document.querySelector("[data-detail-open]")?.getAttribute("href")).toBe(
      `/${TENANT}/runbooks/configuration_check`,
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-018 (EP-RBS-01; CR-075 wave D task D3) · TC-RBS-20 · BR-RBS-025 · BR-RBS-002 · wireframes/RBS-002.1 and RBS-002.2
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST through ./node_modules/.bin/vitest — the chip row built from a hard-coded sixteen failed THREE cases by name ("expected [ 'Platform1', …(15) ] to have a length of 8 but got 16" twice, and "Assets holds no template and must draw no chip"); quoted verbatim in this file's header and in the lane report · tsc --noEmit (the LOCAL compiler)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
