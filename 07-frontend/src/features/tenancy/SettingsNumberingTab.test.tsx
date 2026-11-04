// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-012 (EP-TEN-08 §Stories)  Screens: S8 (Settings → Numbering)
// Rules:    BR-TEN-035 (grammar; format changes future-only; next-number forward-only) ·
//           BR-TEN-033 (the template panel is navigation only) · BR-TEN-043 (issue date is an input)
// ───────────────────────────────────────────────────────
// §4 test data: Brazos Bend — Account AC-{YYYY}-{00000} next 569 · Bill
// BL-{YY}{MM}-{000000} next 18,411 · Payment PY-{YY}{MM}{DD}-{0000} next 88 ·
// Adjustment ADJ-{000} next 41 · Asset AST-{00000} next 1,205. Issue date
// 2026-08-08, tenant timezone America/Chicago.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { NumberSeriesRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  NumberingTab,
  duplicatePrefixes,
  formatProblem,
  isPlainCounter,
  literalPrefix,
  nextNumberProblem,
  previewFormat,
  restartProblem,
  sampleNumber,
  seriesChanges,
  seriesDraftFrom,
  willOverflow,
} from "./SettingsNumberingTab";

const ISSUE_DATE = "2026-08-08";

/**
 * ⚠ EVERY ROW GAINED SIX FIELDS WITH CR-005 (2026-08-17), and none is
 * decoration: `options` is the SERVER's ready-made list (the screen never
 * composes one), `group` is the section kicker, `restart_period` is the
 * per-entity year/month restart, and `prefix`/`duplicate_prefix`/`overflow` are
 * the two warnings the CR asks for — computed on the server so the screen and
 * the save can never disagree about them.
 */
function row(
  series: string,
  group: string,
  format: string,
  next_number: number,
  preview: string,
  options: string[],
  extra: Partial<NumberSeriesRow> = {},
): NumberSeriesRow {
  return {
    series,
    group,
    format,
    next_number,
    preview,
    options,
    restart_period: "never",
    prefix: format.includes("{") ? format.slice(0, format.indexOf("{")) : format,
    duplicate_prefix: false,
    overflow: false,
    ...extra,
  };
}

const SERIES: NumberSeriesRow[] = [
  row("account", "customers_premises", "AC-{YYYY}-{00000}", 569, "AC-2026-00569", [
    "AC-{YYYY}-{00000}",
    "ACCT-{00000}",
    "{0000000}",
  ]),
  row("premises", "customers_premises", "P-{00000}", 13112, "P-13112", ["P-{00000}", "{00000}"]),
  row("bill", "billing_payments", "BL-{YY}{MM}-{000000}", 18411, "BL-2608-018411", [
    "BL-{YY}{MM}-{000000}",
    "BILL-{YYYY}-{00000}",
    "{00000000}",
  ]),
  row("payment", "billing_payments", "PY-{YY}{MM}{DD}-{0000}", 88, "PY-260808-0088", [
    "PY-{YY}{MM}{DD}-{0000}",
    "{00000000}",
  ]),
  row("receipt", "billing_payments", "R-{0000}", 8842, "R-8842", ["R-{0000}", "{000000}"]),
  row("adjustment", "billing_payments", "ADJ-{000}", 41, "ADJ-041", ["ADJ-{000}", "{00000}"]),
  row("journal_entry", "finance", "JE-{000000}", 291, "JE-000291", ["JE-{000000}", "{000000}"]),
  row("work_order", "work", "WO-{0000}", 4834, "WO-4834", ["WO-{0000}", "{000000}"]),
  row("asset", "assets_reads", "AST-{00000}", 1205, "AST-01205", ["AST-{00000}", "{00000}"]),
  row("import_run", "assets_reads", "RUN-{0000}", 2854, "RUN-2854", ["RUN-{0000}", "{000000}"]),
];

function renderTab(rows: NumberSeriesRow[], readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.numberSeries, rows);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <NumberingTab readOnly={readOnly} today={ISSUE_DATE} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-TEN-012 — number formats per series (prefix · next-number · preview)", () => {
  it("US-TEN-012 TC-1: each series renders its format, its counter and the SERVER's preview", () => {
    const html = renderTab(SERIES);
    expect(html).toContain("AC-{YYYY}-{00000}");
    expect(html).toContain("18411");
    // At rest the preview is the server's — the client never allocates one.
    expect(html).toContain("Next number will be BL-2608-018411");
    expect(html).toContain("Next number will be AST-01205");
  });

  it("US-TEN-012 TC-2: the local echo shows an UNSAVED format's shape without allocating anything", () => {
    // BR-TEN-043: the issue date is an argument, never a wall clock read.
    expect(previewFormat("BBU-{YYYY}{MM}-{000000}", 18411, ISSUE_DATE)).toBe("BBU-202608-018411");
    expect(previewFormat("AC-{YYYY}-{00000}", 569, ISSUE_DATE)).toBe("AC-2026-00569");
    expect(previewFormat("PY-{YY}{MM}{DD}-{0000}", 88, ISSUE_DATE)).toBe("PY-260808-0088");
    expect(previewFormat("ADJ-{000}", 41, ISSUE_DATE)).toBe("ADJ-041");
    // A counter wider than the pad is never truncated — padStart only pads.
    expect(previewFormat("ADJ-{000}", 12345, ISSUE_DATE)).toBe("ADJ-12345");
    // An illegal format previews NOTHING rather than teaching a wrong shape.
    expect(previewFormat("BL-{YY}{MM}", 1, ISSUE_DATE)).toBeNull();
  });

  it("US-TEN-012 TC-4 (neg): a malformed format is refused with its SPECIFIC problem", () => {
    expect(formatProblem("AC-{YYYY}-{00000}")).toBeNull();
    expect(formatProblem("")).toBe("empty");
    expect(formatProblem("   ")).toBe("empty");
    // No sequence token at all.
    expect(formatProblem("BL-{YY}{MM}")).toBe("no_sequence_token");
    // Two sequence tokens.
    expect(formatProblem("BL-{000}-{000}")).toBe("multiple_sequence_tokens");
    // An unknown token.
    expect(formatProblem("BL-{QQ}-{000}")).toBe("unknown_token");
    // A stray brace is named as such, before any token diagnosis.
    expect(formatProblem("BL-{YY-{000}")).toBe("unbalanced_braces");
  });

  it("US-TEN-012 TC-5 (neg): the counter may only move FORWARD", () => {
    expect(nextNumberProblem(18411, "18411")).toBeNull();
    expect(nextNumberProblem(18411, "20000")).toBeNull();
    expect(nextNumberProblem(18411, "500")).toBe("backward");
    expect(nextNumberProblem(568, "1000")).toBeNull(); // TC-3: forward is allowed
    expect(nextNumberProblem(41, "forty")).toBe("not_int");
    expect(nextNumberProblem(41, "")).toBe("not_int");
    expect(nextNumberProblem(41, "4.5")).toBe("not_int");
  });

  it("BR-TEN-035: the tab says format changes are future-only and offers no renumber anywhere", () => {
    const html = renderTab(SERIES);
    expect(html).toContain("Numbers already issued are never renumbered or reformatted.");
    expect(html.toLowerCase()).not.toContain("renumber all");
    expect(html.toLowerCase()).not.toContain("reformat existing");
  });

  it("the PUT carries only the field the user touched", () => {
    const row = SERIES[1];
    const draft = seriesDraftFrom(row);
    expect(seriesChanges(draft, row)).toEqual({});
    expect(seriesChanges({ ...draft, format: "BBU-{YYYY}{MM}-{000000}" }, row)).toEqual({
      format: "BBU-{YYYY}{MM}-{000000}",
    });
    expect(seriesChanges({ ...draft, next_number: "20000" }, row)).toEqual({ next_number: 20000 });
  });

  it("US-TEN-012 TC-7 / BR-TEN-033: the template panel points at Templates and stores nothing here", () => {
    const html = renderTab(SERIES);
    expect(html).toContain("Settings → Templates");
    expect(html).toContain("nothing is stored for it here");
  });

  it("a tenant with no series rows says so instead of rendering an empty form", () => {
    const html = renderTab([]);
    expect(html).toContain("No number series are set up for this utility yet.");
  });

  it.todo(
    "US-TEN-012 TC-6: two concurrent bill issuances get distinct numbers — the in-transaction allocator (BE-06), server scope",
  );
  it.todo("US-TEN-012 TC-8 (isolation): per-tenant counters — server/RLS scope (G5)");
});

describe("CR-005 — SET-08 Numbering: every system-generated number gets a defined format", () => {
  it("the table is grouped, and every group prints its section kicker", () => {
    const html = renderTab(SERIES);
    for (const kicker of [
      "Customers &amp; premises",
      "Billing &amp; payments",
      "Finance",
      "Work",
      "Assets &amp; reads",
    ]) {
      expect(html).toContain(kicker);
    }
    // The five column headings CR-005 names, plus the restart the counter
    // behaviour section adds.
    expect(html).toContain("Entity");
    expect(html).toContain("Next counter");
    expect(html).toContain("Preview");
    expect(html).toContain("Restart");
  });

  it("the WORK rows ship as formats and create nothing — PO 2026-08-16", () => {
    // *"Yes; it should work standalone in settings; we will link it later ith
    // work"*. A work-order NUMBER is a format; OQ-249 (is Work a tenth module?)
    // is untouched by its presence here.
    const html = renderTab(SERIES);
    expect(html).toContain("Work order #");
    expect(html).toContain("WO-4834");
  });

  it("the format picker offers ONLY what the server sent, plus Custom", () => {
    const html = renderTab(SERIES);
    expect(html).toContain("ACCT-{00000}");
    expect(html).toContain("BILL-{YYYY}-{00000}");
    expect(html).toContain("Custom…");
    // The screen never invents an option: a format absent from `options` and
    // from the row cannot appear in the markup.
    expect(html).not.toContain("NOPE-{0000}");
  });

  it("the plain, prefix-free option is labelled as what it is (user rule)", () => {
    // CR-005: *"Plain-number option is mandatory in every category (user rule):
    // just {00000} with no prefix"*. The server guarantees it is IN the list;
    // the screen's job is to make it findable rather than showing a bare
    // "{00000}" that reads like a placeholder.
    const html = renderTab(SERIES);
    expect(html).toContain("plain, no prefix");
    expect(literalPrefix("{00000}")).toBe("");
    expect(literalPrefix("AC-{YYYY}-{00000}")).toBe("AC-");
  });

  it("a format is refused when it is too long or its counter too wide", () => {
    // CR-005 clause (a): ≤ 24 chars, pad ≤ 8. The pad MINIMUM of four is
    // deliberately NOT enforced (OQ-250) — `ADJ-{000}` is shipped and legal.
    expect(formatProblem("ADJ-{000}")).toBeNull();
    expect(formatProblem("VERYLONGPREFIXINDEED-{00000}")).toBe("too_long");
    expect(formatProblem("AC-{000000000}")).toBe("pad_too_long");
  });

  it("a restart is refused unless the date token that keeps numbers unique is present", () => {
    // OQ-252: yearly restart on a plain counter re-mints AC-00001 every
    // January, and January's is on a bill nobody may correct (rule 4).
    expect(restartProblem("AC-{00000}", "never")).toBeNull();
    expect(restartProblem("AC-{00000}", "yearly")).toBe("needs_year_token");
    expect(restartProblem("AC-{YYYY}-{00000}", "yearly")).toBeNull();
    expect(restartProblem("AC-{YY}-{00000}", "yearly")).toBeNull();
    // Monthly needs BOTH: {MM}-{0000} alone repeats every January.
    expect(restartProblem("AC-{MM}-{0000}", "monthly")).toBe("needs_year_and_month_tokens");
    expect(restartProblem("BL-{YY}{MM}-{000000}", "monthly")).toBeNull();
  });

  it("duplicate prefixes WARN and never block, and empty prefixes never collide", () => {
    // CR-005: *"duplicate prefixes across entities → warning (not blocking)"*.
    expect([...duplicatePrefixes(["AC-{00000}", "AC-{YYYY}-{000}", "BL-{0000}"])]).toEqual(["AC-"]);
    // Every plain option shares the empty prefix, and the CR calls that option
    // mandatory — so empty must never be a collision.
    expect([...duplicatePrefixes(["{00000}", "{000000}", "{0000}"])]).toEqual([]);
  });

  it("an overflowing counter warns on screen and keeps issuing", () => {
    // CR-005 edge case: *"keep issuing, widen number, surface a warning
    // banner"*. `ADJ-{000}` at 1,000 renders ADJ-1000 — four digits, no
    // truncation, nothing refused.
    expect(willOverflow("ADJ-{000}", 999)).toBe(false);
    expect(willOverflow("ADJ-{000}", 1000)).toBe(true);
    expect(previewFormat("ADJ-{000}", 1000, ISSUE_DATE)).toBe("ADJ-1000");
    const overflowing = SERIES.map((series) =>
      series.series === "adjustment" ? { ...series, next_number: 1000, overflow: true } : series,
    );
    const html = renderTab(overflowing);
    expect(html).toContain("has passed the length its format shows");
    expect(html).toContain("Longer than the format shows");
  });

  it("the right rail shows the formats IN CONTEXT and follows an unsaved edit", () => {
    const html = renderTab(SERIES);
    expect(html).toContain("How they appear together");
    expect(html).toContain("Bill header");
    expect(html).toContain("Work order card");
    expect(html).toContain("Finance trail");
    // At rest the sample is the saved configuration…
    expect(sampleNumber("account", SERIES, {}, ISSUE_DATE)).toBe("AC-2026-00569");
    // …and it re-renders from the DRAFT the moment a format changes, which is
    // the whole point of the rail: *"so the admin sees the downstream effect
    // before saving"*.
    const edited = { account: { format: "CUST-{000000}", next_number: "569", restart_period: "never" as const } };
    expect(sampleNumber("account", SERIES, edited, ISSUE_DATE)).toBe("CUST-000569");
    // A series this tenant does not have leaves its line out rather than
    // inventing a number for it.
    expect(sampleNumber("dispatch_batch", SERIES, {}, ISSUE_DATE)).toBeNull();
  });

  it("the screen STATES that issued numbers are never renumbered, and offers no way to", () => {
    const html = renderTab(SERIES);
    expect(html).toContain("Numbers already issued are never renumbered or reformatted.");
    expect(html).toContain("Changes apply to numbers issued from now on.");
    expect(html.toLowerCase()).not.toContain("renumber all");
  });

  it("a role that may not write sees every control WITH its reason, never hidden", () => {
    // PO 2026-08-16 (CR-005/006/007) + BR-SHL-025: Billing Clerk and Executive
    // LOOK at numbering and cannot change it. The reason is on the control.
    //
    // ⚠ THE ASSERTIONS ARE MARKUP-EXACT BECAUSE A LOOSER ONE COULD NOT FAIL.
    // Proving this RED (law 7) by deleting the standalone reason line left the
    // test GREEN: the same sentence is also the `help` text of every field and
    // the `title` of every select, so `toContain("Your role can view this…")`
    // was satisfied twenty times over by controls the break had not touched.
    // Each place is now named.
    const html = renderTab(SERIES, true);
    // 1 · the primary Save: present, disabled, and carrying the reason.
    expect(html).toContain(
      'disabled="" title="Your role can view this, but not change it.">Save formats',
    );
    // 2 · the standalone reason beside it.
    expect(html).toContain('class="settings-readonly">Your role can view this, but not change it.');
    // 3 · the rows are still READABLE — a hidden table is the defect this rule
    // exists to prevent — and their controls carry the reason too.
    expect(html).toContain("AC-{YYYY}-{00000}");
    expect(html).toContain("Reset counter");
    expect(html.split('title="Your role can view this, but not change it."').length - 1).
      toBeGreaterThan(SERIES.length); // one per select and per reset icon, at least
  });

  it("the whole-tab save posts every CHANGED row and nothing else", () => {
    const bill = SERIES[2];
    const draft = seriesDraftFrom(bill);
    expect(seriesChanges(draft, bill)).toEqual({});
    expect(seriesChanges({ ...draft, restart_period: "monthly" }, bill)).toEqual({
      restart_period: "monthly",
    });
    expect(
      seriesChanges({ ...draft, format: "INV-{YY}-{00000}", next_number: "20000" }, bill),
    ).toEqual({ format: "INV-{YY}-{00000}", next_number: 20000 });
  });

  it.todo(
    "CR-005: Save persists every row in ONE transaction with ONE audit entry — server scope (tests/test_cr005_numbering_set08.py)",
  );

  describe("DEF-197 — only the BARE counter is the plain option", () => {
    /**
     * ⚠ THE FIXTURE ABOVE COULD NOT HAVE CAUGHT THIS, which is the lesson.
     *
     * Every option in `SERIES` begins with literal characters, so the shipped
     * predicate (`literalPrefix(o) === ""`) happened to be right for all of
     * them. The REAL catalog is not like that: `core/numbering.py:141` offers
     * the account row `{YYYY}{00000}` AND `{0000000}`, and a format that OPENS
     * with a token has no literal prefix either — so both announced themselves
     * as "plain, no prefix" and picking the wrong one issued `202600001`.
     *
     * So this block uses the SERVER'S OWN option list verbatim. A fixture that
     * cannot express the defect is a fixture that will pass through it.
     *
     * Proved RED before the fix: the shipped predicate returned "" for two of
     * these six, i.e. two options each claiming to be the plain one.
     */
    const REAL_ACCOUNT_OPTIONS = [
      "AC-{YYYY}-{00000}",
      "ACCT-{00000}",
      "{YYYY}{00000}",
      "A-{YY}-{0000}",
      "CUST-{000000}",
      "{0000000}",
    ];

    it("a format that STARTS with a date token is not the plain option", () => {
      expect(isPlainCounter("{0000000}")).toBe(true);
      expect(isPlainCounter("{00000}")).toBe(true);
      // The two the old predicate got wrong, named individually.
      expect(isPlainCounter("{YYYY}{00000}")).toBe(false);
      expect(isPlainCounter("{YYYY}{MM}{DD}-{0000}")).toBe(false);
      expect(isPlainCounter("AC-{YYYY}-{00000}")).toBe(false);
      // `literalPrefix` is NOT wrong — it is right for what it is FOR. It
      // stays empty for a token-leading format on purpose, because empty
      // prefixes are never duplicates of one another (duplicatePrefixes).
      // Pinned here so nobody "fixes" it into agreeing with isPlainCounter.
      expect(literalPrefix("{YYYY}{00000}")).toBe("");
    });

    it("EXACTLY ONE option in a row is labelled plain, however many lack a prefix", () => {
      // The user-visible statement of the same fact. The PO's rule requires a
      // plain no-prefix option in every category precisely so it is FINDABLE;
      // a label pointing at two formats defeats the rule it implements.
      const html = renderTab([
        row("account", "customers_premises", "AC-{YYYY}-{00000}", 569, "AC-2026-00569",
          REAL_ACCOUNT_OPTIONS),
      ]);
      const labelled = html.split("· plain, no prefix").length - 1;
      expect(labelled).toBe(1); // was 2 before the fix
      expect(html).toContain("{0000000} · plain, no prefix");
      // and the date-led one is offered under its own name, unlabelled.
      expect(html).toContain(">{YYYY}{00000}<");
    });
  });
  it.todo(
    "CR-005: the reset dialog confirms before moving a counter — browser scope (a click path, not a render)",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-012@80cdedf (story+rules snapshot hash — EP-TEN-08)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
