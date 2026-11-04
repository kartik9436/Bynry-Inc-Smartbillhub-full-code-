// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-010 — the parts register, and NO stock level.
//           US-WRK-012 — the Parts tab joins the Work strip.
//           Screens: Work-025 (asserted for what it must NOT show)
// Rules:    BR-WRK-019 · CLAUDE.md hard rule 2 (4 stored, 2 displayed) ·
//           hard rule 3 (a quantity carries its unit) · B14 rules 2 · 16 ·
//           17 · 19 · 20 · 31 · 32 · 33 · BR-SHL-025
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";

import { PartsPage, WORK_PARTS_SCREEN, partsTableConfig } from "./PartsPage";
import { WORK_TABS } from "./WorkShell";
import type { PartList, PartRow } from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** `US-WRK-010` §4's own fixture, as the server shapes it. */
function part(over: Partial<PartRow> = {}): PartRow {
  return {
    id: "p-mtr-w58",
    part_no: "MTR-W58",
    name: 'Water meter 5/8" · AMI',
    category: { id: "c-meters", name: "Meters" },
    unit_of_measure: "each",
    unit_cost: "92.4000",
    active: true,
    ...over,
  };
}

const ELECTRIC = part({
  id: "p-mtr-e1p",
  part_no: "MTR-E1P",
  name: "Electric meter · 1φ AMI",
  unit_cost: "96.0000",
});
const SEAL = part({
  id: "p-seal-01",
  part_no: "SEAL-01",
  name: "Wire seal",
  category: { id: "c-cons", name: "Consumables" },
  unit_cost: "0.2200",
});
const UNFILED = part({ id: "p-gskt", part_no: "GSKT-STD", name: "Gasket set", category: null });

function list(rows: PartRow[]): PartList {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function render(data: PartList | null): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: data !== null } },
  });
  if (data !== null) {
    queryClient.setQueryData(queryKeys.workParts("", 1, DEFAULT_PAGE_SIZE), data);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/work/parts`]}>
        <PartsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const CONFIG = () =>
  partsTableConfig(t, { category: () => null, unitCost: () => null, status: () => null });

describe("US-WRK-010 — the parts register (Work-025, template W1)", () => {
  it("draws the head — kicker, title, the one sentence — and the six columns in the pack's order", () => {
    const html = render(list([part(), ELECTRIC, SEAL, UNFILED]));
    expect(html).toContain("Parts");
    expect(html).toContain("What your crews fit, and what each one costs.");
    const config = CONFIG();
    expect(config.screenId).toBe(WORK_PARTS_SCREEN);
    expect(config.columns.map((c) => c.key)).toEqual([
      "part_no",
      "name",
      "category",
      "unit_of_measure",
      "unit_cost",
      "active",
    ]);
    // B14 rule 33 — a column label is a name of at most three words.
    for (const column of config.columns) {
      expect(column.label.split(/\s+/).length).toBeLessThanOrEqual(3);
    }
    // B14 rule 19 — this list's own prompt, as a KEY the catalogues hold.
    expect(config.searchPlaceholder).toBe("work.parts.search");
    expect(i18n.exists("work.parts.search")).toBe(true);
  });

  it("US-WRK-010 TC-5: the register draws NO stock column — on hand, reorder at, location — by name", () => {
    // ⚠ THE POINT OF THIS SCREEN. `Work-025` draws all three columns, a reorder
    // banner and *"Issues deduct stock the moment they are recorded"*; the card
    // that specifies the same screen says *"No stock levels, no reorder
    // points"* and wins (DEF-WRK-3550). OQ-WRK-1490 is OPEN.
    const config = CONFIG();
    const keys = config.columns.map((column) => column.key);
    for (const forbidden of ["on_hand", "reorder_at", "location"]) {
      expect(keys).not.toContain(forbidden);
    }
    const html = render(list([part(), ELECTRIC, SEAL, UNFILED]));
    for (const heading of ["On hand", "Reorder at", "Location", "In cover", "Below reorder"]) {
      expect(html).not.toContain(heading);
    }
    // …and no banner offering to reorder anything.
    expect(html.toLowerCase()).not.toContain("reorder level");
  });

  it("hard rule 2: 92.4000 on the wire reads $92.40 on the screen, and 96.0000 reads $96.00", () => {
    const html = render(list([part(), ELECTRIC, SEAL]));
    expect(html).toContain("$92.40");
    expect(html).toContain("$96.00");
    expect(html).toContain("$0.22");
    // The four-decimal working figure never reaches a pair of eyes.
    expect(html).not.toContain("92.4000");
    expect(html).not.toContain("96.0000");
  });

  it("hard rule 3: the unit is its own column, never glued onto the cost", () => {
    const html = render(list([part()]));
    expect(html).toContain("each");
    expect(html).not.toContain("$92.40 each");
  });

  it("a part with no category draws a dash, never a blank cell", () => {
    const html = render(list([UNFILED]));
    expect(html).toContain('class="cus-muted">—<');
  });

  it("the segmented control has two segments and the Issue log is RELEASED (CR-168 P3.11, DEF-WRK-9574)", () => {
    // ⚠ THIS CASE ASSERTED THE HOLD UNTIL 2026-10-04 — *"Issue log is disabled
    // WITH ITS REASON"*, *"Arrives with parts on jobs."* — and it is the hold's
    // EXPIRY TEST now (hard-won law 2's mirror): parts on jobs landed in wave
    // N, `GET /work/parts/issues` and `listPartIssues` existed, and the segment
    // still refused. It goes red if the segment is ever greyed again.
    const html = render(list([part()]));
    expect(html).toContain('data-segmented-control=""');
    expect(html).toContain('data-segment="register"');
    expect(html).toContain('data-segment="issues"');
    expect(html).not.toContain('data-segment-disabled="true"');
    expect(html).not.toContain('data-segment-reason="issues"');
    const visible = html.replace(/<[^>]*>/g, " ");
    expect(visible).not.toContain("Arrives with parts on jobs.");
    expect(i18n.exists("work.parts.segment.issuesReason")).toBe(false);
    // The drawing labels the first segment *Stock register*; a register with no
    // stock must not be named after what it does not hold.
    expect(html).not.toContain("Stock register");
  });

  it("ruling 32: the second column is Name — the drawing's DESCRIPTION is the same field", () => {
    const html = render(list([part()]));
    const name = CONFIG().columns.find((c) => c.key === "name");
    expect(name?.label).toBe("Name");
    expect(html).not.toContain(">Description<");
  });

  it("B14 rules 31 and 32: no database id, no rule id and no internal code reaches a clerk", () => {
    const html = render(list([part(), ELECTRIC, SEAL, UNFILED]));
    const text = html.replace(/<[^>]*>/g, " ");
    for (const pattern of [
      /\bBR-[A-Z]{3}-\d{3,5}\b/,
      /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
      /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
      /\bWM-\d\d\b/,
      /\bWork-0\d\d\b/,
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    ]) {
      expect(text).not.toMatch(pattern);
    }
    // rule 31 — the row's id is in the DOM as a key, never as a visible value.
    expect(text).not.toContain("p-mtr-w58");
  });

  it("B14 rule 17: the empty state says what is missing and offers the action that fills it", () => {
    const html = render(list([]));
    expect(html).toContain("No parts yet");
    expect(html).toContain("Add the parts your crews fit.");
    expect(html).toContain("+ Add part");
  });
});

describe("US-WRK-012 — the Work strip gains Parts", () => {
  it("the tab exists, points at the register, and sits in the inventory's order", () => {
    // ⚠ FIVE since CR-070 wave F added *Crews* before Parts (`Work-023`,
    // 2026-09-05); four before that, since wave B put *Awaiting approval*
    // between Orders and Parts (`Work-009`). Parts still sits in the
    // inventory's order, which is what this case is really asserting — and the
    // order is the INVENTORY's, not the order the waves happened to land in.
    expect(WORK_TABS.map((tab) => tab.id)).toEqual([
      "orders",
      // CR-168-BRC10 §30 — At risk, its own tab right after Orders.
      "at-risk",
      "approvals",
      // CR-187-BRC10 — `Work-034`, *From the field*, beside Approvals.
      "field",
      // ⚠ **SIX SINCE CR-070 WAVE I (2026-09-05) — the Map screen landed, so
      // its tab did, in the same commit.** This assertion has now gone red on
      // FOUR consecutive waves, which is exactly its job.
      "map",
      "crews",
      "parts",
      "templates",
      // ⚠ **EIGHT SINCE CR-070 WAVE M (2026-09-05)** — `Work-026` landed
      // with its tab in the same commit, between Templates and Performance.
      // Parts is unmoved, which is what this case is really asserting.
      "rules",
      "performance",
    ]);
    const parts = WORK_TABS.find((tab) => tab.id === "parts");
    expect(parts?.path).toBe("/work/parts");
    expect(i18n.exists("work.tabs.parts")).toBe(true);
  });
});
