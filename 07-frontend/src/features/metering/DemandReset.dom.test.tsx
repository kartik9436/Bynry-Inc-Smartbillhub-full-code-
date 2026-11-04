// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-008 (S28 step 4 — the review step's bulk actions) ·
//           US-MET-012 (S25's usage column) · US-MET-013 (S29 read detail)
//           Screens: S25 · S28 · S29 · S50 · S21
// Rules:    BR-MET-051 (*"Demand: manual demand-register value at cycle read +
//           reset noted; ratchet off (BR-RAT proposal stands)"*, PO RD-4) ·
//           BR-MET-049 (*"demand → +demand record"*) · BR-MET-059 ·
//           BR-MET-062 (a demand peak is NEVER estimated) · BR-SHL-025 ·
//           CLAUDE.md hard rule 3 (a quantity never travels without its unit)
// CR:       CR-038 W4 — "complete DEMAND metering".
// ───────────────────────────────────────────────────────
// The two claims this file defends, both of which every other check in the
// repo is blind to:
//
//   1. **A peak is never printed as if it were energy.** `tsc` cannot tell a
//      kW figure from a kWh one — both are `string | null` — and a snapshot
//      test passes on either. So the assertions here are about the MARKER and
//      about WHICH FIGURE is shown: a demand row renders its REGISTER value,
//      not BR-MET-019's `(current − prior)` delta, because on a demand
//      register that delta is the difference between two maxima and nothing
//      bills it.
//   2. **A bulk action says what it did per row.** A control that answers
//      "done" cannot be checked by the person who clicked it.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReadImportBatchRow, ReadRow } from "@/api/endpoints";

import {
  DemandResetBulkControl,
  DemandResetChip,
  DemandResetRowToggle,
  PeakBadge,
  PeakQuantity,
  READ_CHANNEL_DEMAND,
  StagedRegisterValue,
  isPeakChannel,
} from "./demandShared";
import { UsageCell } from "./readsShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** A committed read, as `selectors.read_dict` serves one. */
function read(over: Partial<ReadRow> = {}): ReadRow {
  return {
    id: "r-7001-aug",
    meter: "M-7001",
    asset_id: "a-7001",
    cycle: null,
    cycle_id: null,
    route: null,
    route_id: null,
    service: "electric",
    premise: null,
    premise_no: null,
    premises_id: null,
    unit_label: null,
    unit_id: null,
    channel: "total",
    read_type: "consumption",
    read_at: "2026-08-03",
    period_start: "2026-07-03",
    period_end: "2026-08-03",
    prior_value: "42180.000000",
    current_value: "42864.000000",
    prior_value_display: "42180 kWh",
    current_value_display: "42864 kWh",
    multiplier: "1.000000",
    consumption: "684.000000",
    unit: "kWh",
    usage_display: "684 kWh",
    days_since_prior: 31,
    source: "import",
    source_detail: "walk_by",
    // CR-038 W3 added `read_method` to this payload and this fixture never
    // gained it — a type error nobody could see, because the parse error above
    // had `tsc` stopping before it type-checked anything.
    //
    // ⚠ TWO LANES ADDED THIS FIELD TO THE SAME OBJECT WITH DIFFERENT VALUES
    // and git kept both, which `tsc` then caught as TS1117 (duplicate property).
    // `walk_by`/`derived` is the one that survives, and the reason is two lines
    // up: this row carries `source_detail: "walk_by"`, so the DERIVED method
    // genuinely IS walk-by under BR-MET-123's declared mapping. `null` /
    // `not_stated` — the other lane's answer — is correct for a row whose
    // source says nothing, and would have contradicted this row's own source.
    read_method: "walk_by",
    read_method_origin: "derived",
    status: "ok",
    lifecycle: "committed",
    rule_outcomes: [],
    import_batch_id: null,
    import_batch_no: null,
    disposition: null,
    disposition_reason: null,
    estimation_method: null,
    consecutive_estimate_no: null,
    trues_up_read_ids: [],
    superseded_by_id: null,
    superseded_at: null,
    supersede_reason: null,
    disputed_at: null,
    dispute_reason: null,
    disputed: false,
    disputed_by: null,
    dispute_cleared_at: null,
    dispute_cleared_by: null,
    demand_reset_noted: false,
    is_peak: false,
    ...over,
  };
}

/** The same meter's DEMAND record — BR-MET-049's second row. */
function peakRead(over: Partial<ReadRow> = {}): ReadRow {
  return read({
    id: "r-7001-aug-demand",
    channel: READ_CHANNEL_DEMAND,
    is_peak: true,
    prior_value: "398.000000",
    current_value: "412.000000",
    prior_value_display: "398 kW",
    current_value_display: "412 kW",
    // ✅ **AMENDED 2026-08-27 — BR-MET-143 / DEF-797.** This fixture used to
    // carry `consumption: "14.000000"` / `usage_display: "14 kWh"` with
    // the note *"the delta the engine computed over two PEAKS. Nothing bills
    // it"* — and it was an accurate model of what the product committed, which
    // is why the defect was real: at $11.00/kW that delta billed **$154.00**
    // where the correct charge is **412 kW × $11.00 = $4,532.00**.
    //
    // A maximum register now commits BR-MET-051's own figure — *"manual
    // demand-register value at cycle read"* — in the REGISTER's own unit. So
    // consumption IS the peak, and its unit is `kW` rather than the meter's
    // energy `kWh`.
    consumption: "412.000000",
    unit: "kW",
    usage_display: "412 kW",
    ...over,
  });
}

function stagedRow(over: Partial<ReadImportBatchRow> = {}): ReadImportBatchRow {
  return {
    row_no: 1,
    meter_no: "M-7001",
    asset_id: "a-7001",
    read_at: "2026-08-03",
    read_at_raw: "2026-08-03",
    channel: "total",
    value: "42864.000000",
    raw_value: "42864.000000",
    // BR-MET-143 — the REGISTER's unit, served on the staged row so the S28
    // review step can print it beside the number (DEF-797's label half was
    // uncheckable while this cell was a bare figure).
    unit: "kWh",
    service: "E",
    note: null,
    severity: "ok",
    rule_outcomes: [],
    disposition: null,
    disposition_reason: null,
    demand_reset_noted: false,
    is_peak: false,
    // ⛔ DEF-816 (third finding) — `ReadImportBatchRow.read_method` is REQUIRED
    // (added by CR-038 W3's `read_method` column, the same afternoon this
    // fixture was written) and this object did not carry it, so the file did
    // not type-check. It was invisible until the missing `/**` in
    // `api/endpoints.ts` was fixed, because a parse error stops `tsc` before it
    // type-checks anything. `null` is the truth for a staged row that states no
    // method — BR-MET-014 makes the tag optional and null reads as "not
    // stated"; a demand-reset test says nothing about who read the meter.
    read_method: null,
    meter_read_id: null,
    ...over,
  };
}

function peakRow(over: Partial<ReadImportBatchRow> = {}): ReadImportBatchRow {
  return stagedRow({
    row_no: 2,
    channel: READ_CHANNEL_DEMAND,
    is_peak: true,
    value: "412.000000",
    raw_value: "412.000000",
    ...over,
  });
}

describe("CR-038 W4 — a peak is not energy (BR-MET-051 · hard rule 3)", () => {
  it("the reads list marks a demand row and shows its REGISTER value, not the delta", () => {
    // RED, with the `is_peak` branch removed from UsageCell:
    //   AssertionError: expected '<span class="rd-usage">14.000000 kWh</span>'
    //   to contain 'Peak'
    const html = renderToStaticMarkup(<UsageCell row={peakRead()} />);
    expect(html).toContain(t("metering.reads.peak.badge"));
    // BR-MET-051: *"manual demand-register VALUE at cycle read"*.
    // ⚠ **AMENDED 2026-08-27 (DEF-1120).** The expected string was the SERVED
    // decimal, `412.000000`. This cell reaches the client's one implementation of
    // BR-MET-144 now (*at most two decimals, trailing zeros trimmed*, PO
    // 2026-08-27), so it reads `412`. What this case guards is unchanged.
    expect(html).toContain("412");
    // ...and NOT the delta between two peaks. ⚠ AMENDED 2026-08-27: that delta
    // is no longer something the cell has to STEP AROUND — BR-MET-143 stopped
    // committing it at all, so this line now asserts it is nowhere in the DOM
    // because it is nowhere in the payload either. DEF-797's $154.00.
    expect(html).not.toContain("14.000000");
    // hard rule 3: the quantity carries the unit the SERVER stored — and since
    // BR-MET-143 that is the REGISTER's `kW`, not the meter's `kWh`. This line
    // asserted `"kWh"` until 2026-08-27.
    expect(html).toContain("kW");
    expect(html).not.toContain("kWh");
  });

  it("a peak on a CT-RATIO meter renders the BILLED peak, not the raw register (BR-MET-143)", () => {
    // ⚠ **THIS TEST EXISTS BECAUSE THE ONE ABOVE CANNOT TELL PASS FROM FAIL ON
    // ITS OWN** (hard-won law 7 — a check whose output cannot distinguish the
    // two is worse than no check, because it is trusted). On the DEF-797 case
    // the meter multiplier is 1, so `current_value` and `consumption` are the
    // SAME number: swapping one for the other in `UsageCell` changes nothing
    // and the assertion above stays green over the defect it is pointed at.
    // Proved by sabotage: reverting the cell to `current_value` left all 11
    // cases passing.
    //
    // A CT ratio separates them, and it is a real case rather than a contrived
    // one: BR-MET-143 makes the meter's multiplier the thing that reconciles a
    // register's own scale with the unit that prices it, and a current
    // transformer on a demand register scales kW to kW. The register dial reads
    // **412**; the meter multiplies by **2**; the customer is billed on
    // **824 kW**, and 824 is the number a clerk must see beside the money.
    const html = renderToStaticMarkup(
      <UsageCell
        row={peakRead({
          multiplier: "2.000000",
          current_value: "412.000000",
          consumption: "824.000000",
          usage_display: "824 kW",
        })}
      />,
    );
    // ⚠ **AMENDED 2026-08-27 (DEF-1120).** The expected string was the SERVED
    // decimal, `824.000000`. This cell reaches the client's one implementation of
    // BR-MET-144 now (*at most two decimals, trailing zeros trimmed*, PO
    // 2026-08-27), so it reads `824`. What this case guards is unchanged.
    expect(html).toContain("824");
    expect(html).not.toContain("412"); // the RAW dial is not the bill
    expect(html).toContain("kW");
  });

  it("BR-MET-143: the S28 review step prints the unit BESIDE the staged register reading", () => {
    // ⚠ A UNIT A PERSON CANNOT SEE IS A UNIT NOBODY CAN CHECK. Step 4 printed a
    // bare `412`, so DEF-797's wrong unit — kWh on a kW register, $154.00 where
    // the correct charge was $4,532.00 — was uncheckable by the clerk approving
    // 1,180 rows, at the one moment a person looks at a reading before it
    // becomes an issued document.
    //
    // ⚠ AND THIS TEST EXISTS BECAUSE ITS TYPE-LEVEL SIBLING IN
    // UploadReadsPage.test.tsx CANNOT CATCH THE FAILURE IT DESCRIBES. That one
    // asserts the PAYLOAD carries `unit`; it says nothing about the SCREEN, and
    // sabotaging the component to drop the unit left all 17 of its cases green.
    // Hard-won law 2 — built is not wired — one field over.
    const html = renderToStaticMarkup(
      <StagedRegisterValue value="412.000000" unit="kW" t={t} />,
    );
    // ⚠ **AMENDED 2026-08-27 (DEF-1120).** The expected string was the SERVED
    // decimal, `412.000000`. This cell reaches the client's one implementation of
    // BR-MET-144 now (*at most two decimals, trailing zeros trimmed*, PO
    // 2026-08-27), so it reads `412`. What this case guards is unchanged.
    expect(html).toContain("412");
    expect(html).toContain("kW");
  });

  it("BR-MET-143: a staged row whose register declares NO unit states the absence, never a guess", () => {
    // CLAUDE.md rule 3 is satisfied by the TRUE unit or by a stated blank — an
    // unknown meter has no UoM to read, and a demand register on a meter whose
    // energy unit declares no demand unit has none either. Both already error
    // `unit_missing` at validation; the screen must not paper over either with
    // a plausible label.
    const html = renderToStaticMarkup(
      <StagedRegisterValue value="412.000000" unit={null} t={t} />,
    );
    // ⚠ **AMENDED 2026-08-27 (DEF-1120).** The expected string was the SERVED
    // decimal, `412.000000`. This cell reaches the client's one implementation of
    // BR-MET-144 now (*at most two decimals, trailing zeros trimmed*, PO
    // 2026-08-27), so it reads `412`. What this case guards is unchanged.
    expect(html).toContain("412");
    expect(html).toContain(t("metering.reads.unitUnknown"));
    expect(html).not.toContain("kW");
  });

  it("an energy row is untouched — the marker is for the demand register alone", () => {
    const html = renderToStaticMarkup(<UsageCell row={read()} />);
    expect(html).toContain("684 kWh");
    expect(html).not.toContain(t("metering.reads.peak.badge"));
  });

  it("a peak with no register value states the absence and why (BR-MET-062)", () => {
    // A demand peak is NEVER estimated, so a missing one is a field visit —
    // this cell must never fill in a number.
    const html = renderToStaticMarkup(
      <PeakQuantity quantity={null} unit={"kWh"} t={t} />,
    );
    expect(html).toContain(t("metering.reads.peak.absent"));
    expect(html).toContain(t("metering.reads.peak.absentWhy"));
  });

  it("the badge carries its own explanation, so the mark is not a mystery", () => {
    const html = renderToStaticMarkup(<PeakBadge t={t} />);
    expect(html).toContain(t("metering.reads.peak.badge"));
    expect(html).toContain("Peak");
    // The `why` rides as a `title`, so it is compared in its RENDERED form —
    // an apostrophe ships as `&#x27;` and an assertion that forgets it is
    // testing the escaper rather than the screen.
    expect(html).toContain(
      t("metering.reads.peak.why").replace(/&/g, "&amp;").replace(/'/g, "&#x27;"),
    );
  });

  it("the demand register is named ONCE, for the payloads that carry no flag", () => {
    expect(READ_CHANNEL_DEMAND).toBe("demand");
    expect(isPeakChannel("demand")).toBe(true);
    expect(isPeakChannel("total")).toBe(false);
    expect(isPeakChannel(null)).toBe(false);
  });

  it("BR-MET-051's reset shows wherever the read shows", () => {
    const html = renderToStaticMarkup(<DemandResetChip t={t} />);
    expect(html).toContain(t("metering.reads.demandReset.noted"));
    expect(html).toContain(t("metering.reads.demandReset.why"));
  });
});

describe("CR-038 W4 — the review step's reset controls (BR-MET-051)", () => {
  it("the bulk control counts the demand rows still needing the note", () => {
    // RED, before `DemandResetBulkControl` existed:
    //   Error: Failed to resolve import "./demandShared"
    const html = renderToStaticMarkup(
      <DemandResetBulkControl
        rows={[stagedRow(), peakRow(), peakRow({ row_no: 3 })]}
        busy={false}
        report={null}
        onNote={() => undefined}
        t={t}
      />,
    );
    expect(html).toContain(t("metering.upload.review.demandResetAll", { count: 2 }));
    // The button kit ships `disabled:opacity-45` as a UTILITY, so a bare
    // `not.toContain("disabled")` tests the stylesheet. The attribute is what
    // matters, and React renders it bare.
    expect(html).not.toContain('disabled=""');
    expect(html).not.toContain("<button disabled");
  });

  it("a batch with no demand row renders the control DISABLED with its reason (BR-SHL-025)", () => {
    const html = renderToStaticMarkup(
      <DemandResetBulkControl
        rows={[stagedRow()]}
        busy={false}
        report={null}
        onNote={() => undefined}
        t={t}
      />,
    );
    expect(html).toContain('disabled=""');
    // Drawn, not dropped: a clerk uploading a water file learns the control is
    // not for them rather than wondering where it went.
    expect(html).toContain(t("metering.upload.review.demandResetNone"));
  });

  it("the answer names the rows it wrote and the rows it skipped, never a bare count", () => {
    const html = renderToStaticMarkup(
      <DemandResetBulkControl
        rows={[stagedRow(), peakRow(), peakRow({ row_no: 3 })]}
        busy={false}
        report={{ noted: [2, 3], skipped: [{ row_no: 1, reason: "not_demand_channel" }] }}
        onNote={() => undefined}
        t={t}
      />,
    );
    expect(html).toContain(
      t("metering.upload.review.demandResetDone", { noted: 2, rows: "2, 3", skipped: 1 }),
    );
    expect(html).toContain("2, 3");
  });

  it("the per-row toggle is offered on a demand row and on NOTHING else", () => {
    const offered = renderToStaticMarkup(
      <DemandResetRowToggle row={peakRow()} busy={false} onToggle={() => undefined} t={t} />,
    );
    expect(offered).toContain(t("metering.upload.review.demandResetRow"));
    expect(offered).toContain("checkbox");
    // The server refuses a non-demand row by name; the screen agrees with it.
    const withheld = renderToStaticMarkup(
      <DemandResetRowToggle row={stagedRow()} busy={false} onToggle={() => undefined} t={t} />,
    );
    expect(withheld).toBe("");
  });

  it("a row whose reset is already noted shows the toggle checked", () => {
    const html = renderToStaticMarkup(
      <DemandResetRowToggle
        row={peakRow({ demand_reset_noted: true })}
        busy={false}
        onToggle={() => undefined}
        t={t}
      />,
    );
    expect(html).toContain("checked");
  });
});
