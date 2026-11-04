// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-054 W4 tasks 15, 17 and 25 — partial posting reaches the screen.
//           Screens: RDS-03 (S28) stages 3, 4 and 5
// Rules:    BR-MET-940 (PARTIAL POSTING — PO: "all or nothing will not work -
//           we accept what is correct and rejct what i not correct - then
//           create csv file at loading stage itself so that suer can see all
//           cases thata re rejcted"; supersedes BR-MET-015's ERROR half AT THE
//           POST GATE) · BR-MET-941 (the rejects export) · BR-MET-129 (a
//           warned reading POSTS) · BR-MET-130 (an incomplete cycle may post
//           once the shortfall is SHOWN) · B4.4 ❄️ FROZEN (tier thresholds
//           reset each bill and "scale with the prorated period") ·
//           BR-SHL-025 (a control you may not use renders disabled WITH its
//           reason) · B14 rule 21
// Defects:  DEF-2731 (stage 4 said "Rows that will become readings: 0" over a
//           post that filed 5; the receipt's breakdown summed to 6 over 1) ·
//           DEF-2732 (the cycle-coverage sentence double-counted and read
//           "expects 5 … cover 5 … 1 have not been read")
// ───────────────────────────────────────────────────────
// WHAT THIS FILE DEFENDS, and why nothing else can see it:
//
//   1. **`postSplit` is a PORT of `apps/metering/read_rejects.would_hold`.**
//      Both answer *"would this staged row post?"*, and if they ever disagree
//      the screen promises a number the server will not honour — that
//      function's own docstring says a pre-post list that disagrees with the
//      post is *worse than none*. Nothing mechanical compares a TypeScript
//      function with a Python one, so the four cases below are the comparison:
//      each names the server branch it mirrors.
//   2. **BR-MET-129's undispositioned warning POSTS.** This is the exact fact
//      DEF-2731 got wrong for five days on the last screen before an
//      irreversible click, and it is invisible to `tsc`, to eslint and to any
//      assertion on a label — the label was *present* and *wrong*.
//   3. **DEF-2732's arithmetic.** `expected − missing` versus
//      `received_in_batch + committed_before_batch`: both are plausible, both
//      typecheck, and only one of them can print "5 of 5 covered, 1 unread".
//
// ⚠ THE BROWSER HALF IS NOT HERE AND CANNOT BE. jsdom does no layout and no
// cascade, so the binding proof is
// `10-scripts/render-checks/cr054-w4-partial-post.mjs` — the PO's rule of
// 2026-08-30: *"All UI screen should be confirm using real broswer testing and
// not just based on test cases"*.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReadBatchCounts, ReadImportBatchRow } from "@/api/endpoints";

import {
  HOLD_DISPOSITIONED_OUT,
  HOLD_INCOMPLETE_ROW,
  HOLD_UNRESOLVED_ERROR,
  RULE_PLAN_REGISTERS,
  postSplit,
  tieredRowsOffMonth,
  wouldHoldRow,
} from "./UploadReadsWizard";
import { CycleShortfall, PostSplitStatement, RejectsDownload, TieredDateWarning } from "./readsImportRail";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function row(over: Partial<ReadImportBatchRow> = {}): ReadImportBatchRow {
  return {
    row_no: 1,
    meter_no: "M-7450",
    asset_id: "a-7450",
    read_at: "2026-08-03",
    read_at_raw: "2026-08-03",
    channel: "total",
    value: "424.000000",
    raw_value: "424.000000",
    unit: "kWh",
    service: "electric",
    read_method: null,
    note: null,
    severity: "ok",
    rule_outcomes: [],
    disposition: null,
    disposition_reason: null,
    demand_reset_noted: false,
    is_peak: false,
    meter_read_id: null,
    ...over,
  };
}

function counts(over: Partial<ReadBatchCounts> = {}): ReadBatchCounts {
  return {
    rows: 6,
    passed: 0,
    warnings: 5,
    errors: 1,
    rows_with_unevaluated: 0,
    accepted: 0,
    rejected: 0,
    field_visit: 0,
    skipped: 0,
    estimate_requested: 0,
    undispositioned: 6,
    posted: 0,
    severity_total: 6,
    reconciles: true,
    ...over,
  };
}

describe("CR-054 task 15 / BR-MET-940 — postSplit ports read_rejects.would_hold", () => {
  it("BR-MET-129: an UNDISPOSITIONED warning POSTS — the fact DEF-2731 got wrong", () => {
    // PO 2026-08-26, verbatim: *"we cannot reject the reading, when reading are
    // colelcted then only we will know whether there is usage or not"*. The
    // server synthesizes `accept` for an ok/warning row with no disposition.
    expect(wouldHoldRow(row({ severity: "warning", disposition: null }))).toBeNull();
    expect(wouldHoldRow(row({ severity: "ok", disposition: null }))).toBeNull();
  });

  it("an ERROR nobody has decided is held — and it is a DIFFERENT reason from one a person decided", () => {
    // `commit_read_batch`'s own branch: `REASON_UNRESOLVED_ERROR` when
    // `row.disposition is None and row.severity == ERROR`, else
    // `REASON_DISPOSITIONED_OUT`. Two facts, two sentences, because the clerk's
    // next act differs: *"nobody has decided this"* versus *"you decided this"*.
    expect(wouldHoldRow(row({ severity: "error", disposition: null }))).toBe(
      HOLD_UNRESOLVED_ERROR,
    );
    expect(wouldHoldRow(row({ severity: "warning", disposition: "reject" }))).toBe(
      HOLD_DISPOSITIONED_OUT,
    );
    expect(wouldHoldRow(row({ severity: "error", disposition: "field_visit" }))).toBe(
      HOLD_DISPOSITIONED_OUT,
    );
    // …and an error a person ACCEPTED does post: `accept` is in
    // `models.POSTING_DISPOSITIONS`, which is why `would_hold` and
    // `services._unresolved_errors` deliberately disagree about that row.
    expect(wouldHoldRow(row({ severity: "error", disposition: "accept_with_flag" }))).toBeNull();
  });

  it("a row too incomplete to file is held even with a decision on it", () => {
    // `would_hold`'s third clause — `meter_no_raw`/`read_at`/`value` absent and
    // nothing posted yet. `meter_no` IS the server's `meter_no_raw`.
    expect(wouldHoldRow(row({ disposition: "accept", meter_no: null }))).toBe(
      HOLD_INCOMPLETE_ROW,
    );
    expect(wouldHoldRow(row({ disposition: "accept", read_at: null }))).toBe(HOLD_INCOMPLETE_ROW);
    expect(wouldHoldRow(row({ disposition: "accept", value: null }))).toBe(HOLD_INCOMPLETE_ROW);
  });

  it("the split is the CR's own worked case, and it reconciles against the SERVER's row count", () => {
    // CR-054's figure: 1,180 rows, 2 unknown meters → 1,178 post, 2 held.
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => row({ row_no: i + 1, severity: "warning" })),
      row({ row_no: 5, severity: "error", disposition: null }),
      row({ row_no: 6, severity: "warning", disposition: "reject" }),
    ];
    const split = postSplit(rows, counts({ rows: 6 }));
    expect(split.willPost).toBe(4);
    expect(split.willHold).toBe(2);
    expect(split.unresolvedErrors).toBe(1);
    expect(split.heldRowNos).toEqual([5, 6]);
    expect(split.reconciles).toBe(true);
  });

  it("DEF-016's failure mode: a partial row list refuses to state a split at all", () => {
    // The screen holds 2 rows; the server says the batch has 6. Printing
    // "2 will post" immediately above an irreversible click would be a
    // confident wrong number, so the panel says it cannot state the split.
    const split = postSplit([row({ row_no: 1 }), row({ row_no: 2 })], counts({ rows: 6 }));
    expect(split.reconciles).toBe(false);
  });
});

describe("CR-054 task 15 — the banner states, and never refuses", () => {
  it("names both numbers and offers the download", () => {
    render(
      <PostSplitStatement
        willPost={1178}
        willHold={2}
        unresolvedErrors={2}
        reconciles
        onDownload={() => undefined}
        downloading={false}
        downloadError={null}
        t={t}
      />,
    );
    const panel = screen.getByRole("status");
    expect(panel).toHaveTextContent("1178 rows will post. 2 will not");
    // ⛔ **THE OLD SENTENCE IS GONE AND MUST STAY GONE.** BR-MET-940 retired the
    // refusal `commit_read_batch` used to raise; a screen still saying "cannot
    // be posted" would be describing a server that no longer exists.
    expect(panel).not.toHaveTextContent("cannot be posted");
    // …and it is a STATUS, not an ALERT. The tier is a claim about whether the
    // operator is blocked, and they are not.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(
      screen.getByRole("button", { name: /Download the 2 rows that will not post/ }),
    ).toBeEnabled();
  });

  it("a clean batch says so, and offers no download over an empty file", () => {
    render(
      <PostSplitStatement
        willPost={1180}
        willHold={0}
        unresolvedErrors={0}
        reconciles
        onDownload={() => undefined}
        downloading={false}
        downloadError={null}
        t={t}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("All 1180 rows will post.");
    // DEF-320's posture: a header with no rows under it reads as an ANSWER.
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("CR-054 task 17 / DEF-2672 — what the rejects file is, and is not", () => {
  it("never calls it the clerk's own spreadsheet", async () => {
    const onDownload = vi.fn();
    render(
      <RejectsDownload
        count={2}
        onDownload={onDownload}
        downloading={false}
        error={null}
        where="receipt"
        t={t}
      />,
    );
    // `read_import.parse_csv` keeps only the nine mapped targets, so their own
    // header spellings and any extra column are gone. The account importer's
    // file IS byte-for-byte theirs; this one is not, and the copy must not
    // borrow that promise.
    const note = screen.getByText(/standard template's columns/);
    expect(note).toHaveTextContent("It is not the spreadsheet you uploaded.");
    await userEvent.click(
      screen.getByRole("button", { name: /Download the 2 rows that were not filed/ }),
    );
    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it("BR-SHL-025: before the rules have run there is nothing to press, and the reason is on screen", () => {
    // `results.csv` refuses a batch below `validated`, and its refusal keys say
    // *"run"* and *"loaded"* where reads says *"batch"* and *"posted"* — the
    // two sentences CR-054's backend lane recorded as OWED (DEF-2733). The
    // screen states the reads-vocabulary reason rather than rendering theirs.
    render(
      <RejectsDownload count={0} onDownload={null} downloading={false} error={null} where="review" t={t} />,
    );
    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.getByText(/Run the rules first/)).toBeInTheDocument();
  });
});

describe("CR-054 task 25 / B4.4 — a tiered read date off the stated month", () => {
  function tiered(over: Partial<ReadImportBatchRow> = {}) {
    return row({
      rule_outcomes: [
        { rule: RULE_PLAN_REGISTERS, severity: "ok", detail: { plan_model: "tiered" } },
      ],
      ...over,
    });
  }

  it("flags a tiered row dated outside the reading month the clerk chose", () => {
    const rows = [
      tiered({ row_no: 1, read_at: "2026-08-03" }),
      tiered({ row_no: 2, read_at: "2026-07-03" }),
      tiered({ row_no: 3, read_at: "2026-09-01" }),
    ];
    expect(tieredRowsOffMonth(rows, "2026-08-01")).toEqual([2, 3]);
  });

  it("says nothing about a FLAT meter on the same wrong date — B4.4 is why this rule exists", () => {
    // On a flat tariff a wrong date moves the period and the money moves
    // visibly with it. On a TIERED one the bands are re-cut and the bill still
    // looks plausible, which is the whole reason for a separate warning.
    const flat = row({
      row_no: 9,
      read_at: "2026-07-03",
      rule_outcomes: [
        { rule: RULE_PLAN_REGISTERS, severity: "ok", detail: { plan_model: "flat" } },
      ],
    });
    expect(tieredRowsOffMonth([flat], "2026-08-01")).toEqual([]);
  });

  it("ignores a row whose date would not parse — it already errors by name", () => {
    const unparsed = tiered({ row_no: 4, read_at: null, read_at_raw: "3rd Aug" });
    expect(tieredRowsOffMonth([unparsed], "2026-08-01")).toEqual([]);
  });

  it("states the consequence in B4.4's own terms, and gates nothing", () => {
    render(<TieredDateWarning rowNos={[2, 3]} statedMonth="2026-08-01" t={t} />);
    const panel = screen.getByRole("status");
    expect(panel).toHaveTextContent("2 row(s) on a tiered tariff are dated outside 2026-08");
    expect(panel).toHaveTextContent("A 0–1,000 band becomes 0–500 over fifteen days of thirty.");
    expect(panel).toHaveTextContent("Rows: 2, 3");
    // It is a warning. Nothing here refuses, and no button appears to.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("draws nothing at all when every tiered row is in the stated month", () => {
    const { container } = render(<TieredDateWarning rowNos={[]} statedMonth="2026-08-01" t={t} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("DEF-2732 — the cycle-coverage sentence adds up", () => {
  it("expected − missing, not received + committed", () => {
    // The measured browser reading on 2026-08-31 was *"This cycle expects 5
    // readings. This batch and the readings already on file cover 5. 1 have not
    // been read."* — five of five covered AND one unread, because a meter in
    // both counters is counted twice.
    render(
      <CycleShortfall
        coverage={{
          cycle_code: "CY-002",
          expected_meters: 5,
          received_in_batch: 3,
          committed_before_batch: 2,
          missing_after_batch: 1,
          missing_meter_nos: ["W-7001"],
          missing_truncated: false,
        }}
        absentReason={null}
        t={t}
      />,
    );
    const line = screen.getByText(/meters covered/);
    expect(line).toHaveTextContent("4 of 5 meters covered");
    expect(line).toHaveTextContent("1 meters still unread");
    // The double-count's own reading: 3 received + 2 committed = 5 of 5.
    expect(line).not.toHaveTextContent("5 of 5");
  });

  it("the figure is METERS, and the sentence says so", () => {
    // ⛔ The same line called `expected_meters` "readings" — a meter count in
    //   a reading's clothes, which is DEF-2730's confusion one screen over.
    //   `batch_cycle_coverage` is meters by construction: *"Meters, not
    //   records, because the review step's question is 'which meters does this
    //   cycle still wait on'"*.
    render(
      <CycleShortfall
        coverage={{
          cycle_code: "CY-002",
          expected_meters: 5,
          received_in_batch: 3,
          committed_before_batch: 2,
          missing_after_batch: 1,
          missing_meter_nos: ["W-7001"],
          missing_truncated: false,
        }}
        absentReason={null}
        t={t}
      />,
    );
    const line = screen.getByText(/meters covered/);
    expect(line).not.toHaveTextContent("readings");
  });

  it("B14 rule 33: every sentence in the block is six words or fewer", () => {
    // RATIFIED 2026-08-30 — a FACT is ≤ 6 words and an INSTRUCTION ≤ 6 words
    // PER SENTENCE. The line this replaced was three sentences and 24 words,
    // and the note under it ran to 18 in one. Counted here rather than
    // eyeballed, because the next edit to this copy will not remember the cap.
    const { container } = render(
      <CycleShortfall
        coverage={{
          cycle_code: "CY-002",
          expected_meters: 5,
          received_in_batch: 3,
          committed_before_batch: 2,
          missing_after_batch: 1,
          missing_meter_nos: ["W-7001"],
          missing_truncated: false,
        }}
        absentReason={null}
        t={t}
      />,
    );
    // ⚠ PER PARAGRAPH, NOT OVER `container.textContent`. The first draft split
    //   the whole subtree and read "1 meters still unread.You can post anyway."
    //   as one nine-word sentence — two <p> elements concatenated with no space
    //   between them. A check that reports a fault the screen does not have is
    //   the same defect as one that misses a fault it does: it cannot be
    //   trusted either way.
    const sentences = [...container.querySelectorAll("p")].flatMap((p) =>
      (p.textContent ?? "")
        .split(/(?<=\.)\s+/)
        .map((s) => s.trim())
        .filter((s) => s !== ""),
    );
    expect(sentences.length).toBeGreaterThan(0);
    const overCap = sentences.filter((s) => s.split(/\s+/).length > 6);
    expect(overCap).toEqual([]);
  });
});
