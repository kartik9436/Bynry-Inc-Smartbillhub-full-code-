// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-2376 — the Product Owner, on the deployed S61: "this Audit log
//           screen - took bar should be aligned properly, also check whther it
//           is in tailwind". In the screenshot the six filter controls (Actor ·
//           Action code · Entity type · Entity ID · From · To) do not sit on one
//           baseline: a three-line helper paragraph under "Action code" pushes
//           THAT box three lines below the other five, and the export and column
//           controls float beneath a ragged block.
// Rules:    B14 rule 32 (a screen has a description budget: ONE sentence per
//           section, a stated absence CLOSED by default) · B14 rule 21 (Tailwind
//           utilities, and only in a file on styles/route-b-migrated.txt) ·
//           BR-SHL-033 (a long list is searchable; date fields are pickers) ·
//           hard-won law 6 (no gate reads rendered output) · DEF-182
// ───────────────────────────────────────────────────────
// ⚠ **WHAT THIS SUITE CAN AND CANNOT CLAIM**, in the words DataTableSearchWidth
// already had to write for the same reason.
//
// It CANNOT claim the six boxes are on one baseline. jsdom computes no layout,
// the CSS is never applied, and no gate in this repo reads rendered output. A
// pixel assertion here would pass on the broken screen and on the fixed one.
//
// What it CAN claim is the STRUCTURE that decided the baseline, and that
// structure is the whole defect. `FormModal`'s field kit renders
//
//     label → [help paragraph] → input
//
// so a `help` string is the ONLY thing in this panel that can change the
// distance from the top of a grid cell to its control. Six fields with no
// paragraph are six controls at the same offset; one field with a paragraph is
// one control pushed down by exactly its height. That is a question about the
// markup, and jsdom can answer it.
//
// So the contract pinned here is: **every filter in this row is label + control
// and nothing else.** A future lane adding `help=` back to any one of them
// breaks this file and nothing else in the suite — which is the point, because
// on 2026-09-02 exactly that had been true for three weeks with every test
// green.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { AuditListResult, TenantUser } from "@/api/endpoints";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { queryKeys } from "@/api/queryClient";

import { AuditLogPage } from "./AuditLogPage";

const EMPTY_LIST: AuditListResult = {
  page: { results: [], count: 0, next: null, previous: null },
  window: { window: "hot", from: "2024-09-02T00:00:00Z" },
};

/** The six ids the panel declares, in the BR-AUD-009 order it draws them. */
const FILTER_IDS = ["f.actor", "f.action", "f.entity_type", "f.entity_id", "f.from", "f.to"];

/** No network, ever — the screen's client seam exists so it can be proved without one. */
const REFUSES: ApiClient = {
  get: async () => {
    throw new Error("this suite seeds the cache; nothing here reaches a network");
  },
} as unknown as ApiClient;

/**
 * `users === null` is the EXECUTIVE case: `GET /users` is System-Admin-only, so
 * the actor picker degrades from the BR-SHL-033 searchable select to a plain id
 * field — the state that used to carry the second helper paragraph.
 */
function renderPage(users: TenantUser[] | null) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.auditLog("sort=when&dir=desc&page=1&per=25|false"), EMPTY_LIST);
  if (users !== null) {
    queryClient.setQueryData(queryKeys.tenantUsers(1, DEFAULT_PAGE_SIZE), {
      count: users.length,
      next: null,
      previous: null,
      results: users,
    });
  }
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/audit-log"]}>
          <AuditLogPage client={REFUSES} timeZone="UTC" dateFormat="MM/DD/YYYY" />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const ALEX = { id: "u-1", name: "Alex Reed", email: "alex@brazos.test" } as TenantUser;

/** The `.field` wrapper the kit puts around one control. */
function fieldOf(id: string): HTMLElement {
  const control = document.getElementById(id);
  if (control === null) {
    throw new Error(`the ${id} filter is not in the DOM`);
  }
  const field = control.closest(".field");
  if (field === null) {
    throw new Error(`${id} is not inside a .field wrapper — the kit was bypassed`);
  }
  return field as HTMLElement;
}

afterEach(cleanup);

describe("S61 filter row · DEF-2376", () => {
  it("draws all six filters, in the BR-AUD-009 order, inside ONE grid", async () => {
    renderPage([ALEX]);
    const fields = FILTER_IDS.map(fieldOf);
    const grid = fields[0].parentElement;
    expect(grid).not.toBeNull();
    for (const field of fields) {
      expect(field.parentElement, "a filter escaped the grid").toBe(grid);
    }
    // The grid, and the alignment it declares. `items-start` is stated rather
    // than left to `stretch`: it is what a reader checks when this row next
    // looks wrong, and `stretch` would say nothing about intent.
    const classes = (grid as HTMLElement).className;
    expect(classes).toContain("grid");
    expect(classes).toContain("items-start");
    expect(classes).toContain("grid-cols-[repeat(auto-fit,minmax(180px,1fr))]");
  });

  it("gives NO filter a helper paragraph — the one thing that can move a control", () => {
    renderPage([ALEX]);
    for (const id of FILTER_IDS) {
      const help = fieldOf(id).querySelector(".field-help");
      expect(
        help,
        `${id} carries a helper paragraph: the kit renders it BETWEEN the label and the `
          + `control, so this box now sits lower than the other five (DEF-2376). Put the `
          + `guidance in a placeholder, or one sentence for the whole section.`,
      ).toBeNull();
    }
  });

  it("every filter is label + control, so all six start at the same offset", () => {
    renderPage([ALEX]);
    for (const id of FILTER_IDS) {
      const field = fieldOf(id);
      // The kit's own label, and the control, and nothing between them. A date
      // field may render its regional echo AFTER the input (IS-8) — that hangs
      // below and cannot move the control, so it is not counted here.
      const label = field.querySelector("label");
      expect(label, `${id} has no label`).not.toBeNull();
      // The searchable actor select wraps its input in a positioning div, so the
      // question is where the control's BRANCH sits among `.field`'s children,
      // not where the input itself does.
      let branch = document.getElementById(id) as HTMLElement | null;
      while (branch !== null && branch.parentElement !== field) {
        branch = branch.parentElement;
      }
      const position = branch === null ? -1 : Array.from(field.children).indexOf(branch);
      expect(
        position,
        `${id}: the control is child ${position}, not 1 — something was inserted `
          + `between the label and the box, which is what put this row out of line`,
      ).toBe(1);
    }
  });

  it("keeps the guidance a person needs — as a PLACEHOLDER, not a paragraph", () => {
    renderPage([ALEX]);
    const action = document.getElementById("f.action") as HTMLInputElement;
    // Rule 32 is a budget, not a gag: the reader still learns what an action
    // code looks like. What went was the SECOND sentence, which stated an
    // absence (grouping by type or module arrives with the event catalogue) —
    // rule 32 closes a stated absence by default, and that sentence is now a
    // code comment where an engineer reads it.
    expect(action.placeholder).toBe("For example, invoice.issued");
    expect(action.placeholder).not.toContain("catalog");
  });

  /**
   * CR-067 B3's "Errors only" toggle, and **the reason it is not a seventh cell
   * in that grid.**
   *
   * Every box in the row is label-ABOVE-control; a checkbox is
   * label-BESIDE-control, so dropping one into the same grid puts its control at
   * a different offset from the other six — which is DEF-2376's exact fault, on
   * DEF-2376's own screen, arriving from a different direction.
   *
   * ⚠ **THIS CASE LIVES HERE AND NOT IN `cr067Diagnostic.test.tsx` BECAUSE THAT
   * FILE COULD NOT ANSWER IT.** The string form of the check — "does
   * `id="f.outcome"` appear after `id="f.to"` in the markup" — passed on a
   * sabotage that put the toggle straight into the grid with `className="contents"`,
   * because the ORDER does not change when the nesting does. A check that cannot
   * tell the breach from the fix is DEF-182's *"worse than no check, because it
   * is trusted"*. `closest()` can tell, so the case belongs where there is a DOM.
   *
   * RED-PROVED (measured, `scripts/cr067_red_proof.py toggle-inside-the-grid`):
   *
   *   AssertionError: the Errors-only toggle is inside the six-filter grid —
   *   a checkbox is label-BESIDE-control and breaks the baseline (DEF-2376):
   *   expected <div …(1)>…(7)</div> to be null
   *
   * ⚠ AND THE FIRST DRAFT OF THAT SABOTAGE PROVED NOTHING: it gave the toggle's
   * own row `className="contents"`, which is a CSS display value and moves no
   * DOM node — the checkbox stayed a child of the flex column and this case was
   * right to pass. The sabotage now MOVES the element, which is the only version
   * that can be wrong.
   */
  it("DEF-2376 — the Errors-only toggle is OUTSIDE the six-filter grid", () => {
    renderPage([ALEX]);
    const toggle = document.getElementById("f.outcome");
    expect(toggle, "the Errors-only control the PO asked for is not in the DOM").not.toBeNull();
    const grid = fieldOf("f.to").parentElement as HTMLElement;
    expect(grid.className).toContain("grid-cols-[repeat(auto-fit,minmax(180px,1fr))]");
    expect(
      (toggle as HTMLElement).closest(
        ".grid-cols-\\[repeat\\(auto-fit\\,minmax\\(180px\\,1fr\\)\\)\\]",
      ),
      "the Errors-only toggle is inside the six-filter grid — a checkbox is "
        + "label-BESIDE-control and breaks the baseline (DEF-2376)",
    ).toBeNull();
    // …and it is a real checkbox, not a link or a button pretending to be one.
    expect((toggle as HTMLInputElement).type).toBe("checkbox");
    expect((toggle as HTMLInputElement).checked).toBe(false);
  });

  it("an Executive still learns WHY the actor list is a text box — once, for the section", async () => {
    renderPage(null);
    // `GET /users` never succeeds here, so the panel renders its degraded form.
    await waitFor(() => expect(document.getElementById("f.actor")).not.toBeNull());
    const actor = document.getElementById("f.actor") as HTMLInputElement;
    expect(actor.tagName).toBe("INPUT");
    // The reason is ONE sentence, and it is OUTSIDE the grid — so it explains
    // the section without moving anything inside it (rule 32).
    const note = document.body.textContent ?? "";
    expect(note).toContain("Your role can't list users");
    expect(fieldOf("f.actor").querySelector(".field-help")).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-2376 · US-AUD-004 (S61 viewer) · B14 rules 21/32 · BR-SHL-033
// generated: 2026-09-02 by the audit-log defect lane
// checklist: A✔ B✔ C=n/a(no API change) D=n/a(no endpoint) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED-PROVED FIRST — with the `help={t("audit.filter.actionHelp")}` line
//   restored on `f.action`, "gives NO filter a helper paragraph" fails with
//   `expected <p class="field-help" id="f.action-help">…</p> to be null`, and
//   "every filter is label + control" fails with `f.action: the control is child
//   2, not 1`. Both go green with the line removed.
// exceptions: E4 this suite asserts MARKUP, never pixels — jsdom computes no
//   layout and this repo has no gate that reads rendered output (hard-won law 6).
//   The baseline itself was confirmed by eye against the deployed screen; what is
//   held here is the structure that decides it.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
