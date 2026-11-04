// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-019 (EP-TEN-03)   Screens: S8 (Settings → Company profile)
// Change:   CR-039 wave B tasks 6/7/8 (12-governance/11-change-requests.md),
//           PO 2026-08-26: *"we need to look at what of 1 job fails and does
//           not load the data - them what we do with rest of the jobs - we
//           should continue and should not lose entire setup"*
// Rules:    BR-TEN-060 (a NAMED line, never a skip) · BR-SHL-025 (a control a
//           role may not use renders disabled WITH its reason)
// ───────────────────────────────────────────────────────
// WHAT THIS SUITE IS FOR, AND WHY IT IS A SEPARATE FILE.
//
// `SettingsSampleData.test.tsx` pins the LEGACY module-line render — a report
// whose `blocks` list is empty, which is a real state (a run recorded before
// block-level reporting existed). This one pins the block render, and keeping
// them apart is deliberate: the two paths are two different answers over one
// ledger, and a suite that mixed them could not tell which one it was reading.
//
// The failure this guards against is specific and has happened here before, one
// grain coarser: a cascade of dependent failures rendered as N equal reds. The
// operator reads five lines, each true, and has no way to tell which one to fix
// — DEF-660 measured exactly that (*"a chain of five failures that read like
// five separate bugs"*).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { SampleDataBlock, SampleDataReport } from "@/api/endpoints";

import { SampleDataReportBody } from "./SettingsSampleData";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const READS_DETAIL =
  "the June read batch will not post: 3 of 48 row(s) failed validation and BR-MET-015 " +
  "resolves an error only by a human's override, reject, field visit or skip.";

function block(over: Partial<SampleDataBlock>): SampleDataBlock {
  return {
    module: "metering",
    block: "seed_sample_reads",
    label: "Meter reads",
    outcome: "failed",
    count: 0,
    reason_code: "exception",
    error_code: "SD-PRECONDITION",
    failure_class: "root",
    root_block: null,
    root_label: null,
    detail: READS_DETAIL,
    finished_at: "2026-08-26T10:00:00Z",
    retryable: true,
    ...over,
  };
}

/** The DEF-660 shape: reads break, and billing + payments break behind them. */
const CASCADE: SampleDataReport = {
  modules: [],
  blocks: [
    block({
      module: "rating",
      block: "seed_sample_records",
      label: "Plans & rates",
      outcome: "seeded",
      count: 12,
      reason_code: null,
      error_code: null,
      failure_class: null,
      detail: null,
      retryable: false,
    }),
    block({}),
    block({
      module: "billing",
      block: "seed_sample_records",
      label: "Bills (June billed — July is staged and yours to run)",
      failure_class: "consequence",
      root_block: "metering:seed_sample_reads",
      root_label: "Meter reads",
      detail: "no bill run was attempted: there is no cycle to bill.",
    }),
    block({
      module: "payments",
      block: "seed_sample_records",
      label: "Payments, deposits and the bank statement",
      failure_class: "consequence",
      root_block: "metering:seed_sample_reads",
      root_label: "Meter reads",
      detail: "no payment could be recorded: this tenant has NO ISSUED BILL to pay.",
    }),
  ],
  seeded_total: 12,
  not_loaded: [],
  succeeded: false,
  counts_toward_progress: false,
  has_run: true,
  blocks_recorded: true,
  removal: { order: [], removable: 0, retained: [], blocked: [] },
};

/**
 * React escapes `&` and `\'` into the markup, and the server's real sentences
 * contain both ("human's override", "Premises, units & service points"). The
 * assertions escape the same way rather than bending the fixture — a fixture
 * trimmed to fit an assertion stops covering the string the server sends.
 */
function escaped(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/'/g, "&#x27;");
}

function render(report: SampleDataReport, extra: Record<string, unknown> = {}): string {
  return renderToStaticMarkup(<SampleDataReportBody report={report} t={t} {...extra} />);
}

describe("CR-039 wave B — the panel says WHICH part failed, and which one to fix", () => {
  it("renders one line per BLOCK, with its own count and its own sentence", () => {
    const html = render(CASCADE);

    for (const row of CASCADE.blocks) {
      expect(html).toContain(`data-block="${row.module}:${row.block}"`);
      if (row.detail !== null) {
        expect(html).toContain(escaped(row.detail));
      }
    }
    // The seeded block's count is a MEASURED figure and is shown as one.
    expect(html).toContain(t("settings.sampleData.block.rows", { count: 12 }));
  });

  it("marks ONE root and names it on every consequence — five reds, one cause", () => {
    const html = render(CASCADE);

    // Exactly one line is the place to start.
    const roots = html.match(/data-failure-class="root"/g) ?? [];
    expect(roots).toHaveLength(1);
    expect(html).toContain(t("settings.sampleData.block.root"));

    // …and the two behind it NAME it rather than each claiming to be a fault.
    const consequences = html.match(/data-failure-class="consequence"/g) ?? [];
    expect(consequences).toHaveLength(2);
    expect(html).toContain(t("settings.sampleData.block.consequence", { root: "Meter reads" }));
  });

  it("shows the stable code beside the sentence, never instead of it", () => {
    const html = render(CASCADE);
    // The code is for counting and for a support call; the sentence is what an
    // operator acts on. A screen with only the code is a regression, and so is
    // one with only the sentence.
    expect(html).toContain("SD-PRECONDITION");
    expect(html).toContain(escaped(READS_DETAIL));
  });

  it("offers retry on the failed blocks and NOT on the seeded one", () => {
    const html = render(CASCADE, { onRetry: () => undefined, readOnly: false });
    const buttons = html.match(/Try this part again/g) ?? [];
    // Three non-seeded blocks in the fixture, and the seeded one gets nothing:
    // a retry button over a block that worked is a control with no meaning.
    expect(buttons).toHaveLength(3);
  });

  it("DEF-3224 · a block that SUCCEEDED still shows its sentence, and still offers no retry", () => {
    // ⚠ **THE HALF THAT DID NOT EXIST, AND IT IS A SUCCESS AND NOT A FAILURE.**
    // The estate for a utility selling Electric, Water and Sewer was built —
    // block seeded, 0 of 17 failed, 95 bills issued — and electric got no
    // meter, no read and no line on any of them, not even its $12.00 monthly
    // charge ($576.00 a month across 48 units). The server composed a correct
    // sentence naming it and sent it to a log file. `sample_data.py` recorded
    // `detail: None` on every seeded block, so there was nowhere to put it.
    //
    // This asserts the SCREEN half of that fix: the sentence renders on a
    // seeded line, and the line does not grow a Retry button — retrying a block
    // that worked is a control with no meaning (the case above).
    const note =
      "electric: the estate is metered in water and this fixture declares one register per unit";
    const report: SampleDataReport = {
      ...CASCADE,
      blocks: [
        block({
          module: "metering",
          block: "seed_sample_records",
          label: "Premises, units & service points",
          outcome: "seeded",
          count: 44,
          reason_code: null,
          error_code: null,
          failure_class: null,
          detail: note,
          retryable: false,
        }),
      ],
    };
    const html = render(report, { onRetry: () => undefined, readOnly: false });

    expect(html).toContain(escaped(note));
    expect(html).toContain('data-outcome="seeded"');
    expect(html).not.toContain("Try this part again");
  });

  it("BR-SHL-025 · a view-only role sees the retry control DISABLED with its reason", () => {
    const html = render(CASCADE, { onRetry: () => undefined, readOnly: true });
    expect(html).toContain(t("settings.readOnlyReason"));
    expect(html).toContain("disabled");
  });

  it("says a legacy run has no breakdown rather than showing an empty list", () => {
    // ⚠ THE DEF-127 SHAPE, ONE LEVEL DOWN. `blocks: []` on a run that HAPPENED
    // is not "no blocks" — it is "recorded before we tracked them". A blank
    // list would read as an answer.
    const legacy: SampleDataReport = {
      ...CASCADE,
      blocks: [],
      blocks_recorded: false,
      modules: [
        {
          module: "metering",
          label: "Premises, units & service points",
          outcome: "failed",
          reason_code: "exception",
          detail: READS_DETAIL,
          count: 0,
        },
      ],
    };
    const html = render(legacy);
    expect(html).toContain(t("settings.sampleData.block.notRecorded"));
    // …and the module lines still render, so the operator is not left blank.
    expect(html).toContain(escaped(READS_DETAIL));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-019@c3b7d18 (EP-TEN-03 — S8's Sample data panel) + CR-039 wave B tasks 6/7/8 (12-governance/11-change-requests.md)
// generated: 2026-08-26 by story-coder (CR-039 wave B lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — no money figure, threshold or key is authored here)
// gates: vitest src/features/tenancy 444 passed / 33 todo across 28 files · tsc clean on this lane's files (1 PRE-EXISTING error in features/metering/DemandReset.dom.test.tsx, another lane's) · eslint --max-warnings 0 clean · G31 PASS at the 509 ceiling with SettingsSampleData.tsx handed to routeBUtilities.test.ts (10 passed)
// exceptions: this suite renders `SampleDataReportBody` directly rather than the whole panel, because the panel owns the react-query wiring and the thing under test is what the REPORT renders. The panel's own wiring (which button reports busy, what the toast says) is covered by the shape of `retryingBlock` and by the backend's API tests, and a full-panel interaction test is REPORTED as owed rather than claimed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

/**
 * CR-040 task E17 — *"the seeding panel names the new blocks rather than
 * reporting a module short"*.
 *
 * Waves C and D put three blocks between the two bill runs: a refund, an
 * overcharge correction and the second billing cycle. All three reached this
 * screen with **no dependency edge**, so `_root_for` had nothing to walk and
 * marked each one its own ROOT. The panel then drew *"Start here"* four times
 * over a single cause — on the one screen whose entire job is to say which line
 * to read first — and the module line above it reported `billing` once for
 * three blocks.
 *
 * This is the render of the fixed graph. It is a separate `describe` from the
 * CR-039 one above for the reason that file's own header gives: two cascades,
 * two shapes, and a suite that mixed them could not say which it was reading.
 */
/** Literal count, never a regex — see the note in the second case below. */
function occurrences(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1;
}

const MONEY_CASCADE: SampleDataReport = {
  ...CASCADE,
  blocks: [
    block({
      module: "billing",
      block: "seed_sample_records",
      label: "Bills, first cycle (June — issued and mostly paid)",
      failure_class: "root",
      root_block: null,
      root_label: null,
      error_code: "SD-PRECONDITION",
      detail:
        "no bill can issue on this tenant. 1 tax authority(ies) have no 2200-series " +
        "liability account.",
    }),
    block({
      module: "payments",
      block: "seed_sample_records",
      label: "Payments, deposits and the bank statement",
      failure_class: "consequence",
      root_block: "billing:seed_sample_records",
      root_label: "Bills, first cycle (June — issued and mostly paid)",
      detail: "no payment could be recorded: this tenant has NO ISSUED BILL to pay.",
    }),
    block({
      module: "payments",
      block: "seed_sample_refund",
      label: "A refund (requested, approved, issued, cleared — spec §4 case 14)",
      failure_class: "consequence",
      root_block: "billing:seed_sample_records",
      root_label: "Bills, first cycle (June — issued and mostly paid)",
      detail:
        "no refund was recorded: the account that should have OVERPAID its June bill " +
        "carries no seeded payment at all.",
    }),
    block({
      module: "billing",
      block: "seed_sample_correction",
      label: "An overcharge, corrected (restatement — spec §4 case 15)",
      failure_class: "consequence",
      root_block: "billing:seed_sample_records",
      root_label: "Bills, first cycle (June — issued and mostly paid)",
      detail:
        "no correction was made: the account that should carry an over-read June bill " +
        "has no ISSUED bill.",
    }),
  ],
};

describe("CR-040 E17 — the money blocks between the two bill runs are named, not counted", () => {
  it("names all four blocks on their own lines, including the two that share a module", () => {
    const html = render(MONEY_CASCADE);

    // `billing` appears TWICE and `payments` TWICE. A per-module render collapses
    // each pair into one verdict; this is the assertion that says it does not.
    for (const key of [
      "billing:seed_sample_records",
      "billing:seed_sample_correction",
      "payments:seed_sample_records",
      "payments:seed_sample_refund",
    ]) {
      expect(html).toContain(`data-block="${key}"`);
    }
    expect(html).toContain(escaped("A refund (requested, approved, issued, cleared — spec §4 case 14)"));
    expect(html).toContain(escaped("An overcharge, corrected (restatement — spec §4 case 15)"));
  });

  it("draws ONE 'Start here' over the bill run, not one per money block", () => {
    const html = render(MONEY_CASCADE);

    const roots = html.match(/data-failure-class="root"/g) ?? [];
    expect(roots).toHaveLength(1);

    const consequences = html.match(/data-failure-class="consequence"/g) ?? [];
    expect(consequences).toHaveLength(3);
    // Each of the three says WHOSE consequence it is, by the bill run's own
    // label. Counted by SPLITTING rather than by a regex: the label carries
    // parentheses and an em dash, and `new RegExp` over it silently matches
    // nothing — which is a test that passes by finding zero of what it wanted.
    expect(
      occurrences(
        html,
        escaped(
          t("settings.sampleData.block.consequence", {
            root: "Bills, first cycle (June — issued and mostly paid)",
          }),
        ),
      ),
    ).toBe(3);
  });

  it("tells the operator to fix the bill run before retrying any of the three", () => {
    const html = render(MONEY_CASCADE, { onRetry: () => {} });

    expect(occurrences(html, escaped(t("settings.sampleData.block.retryRootFirst")))).toBe(3);
  });
});
