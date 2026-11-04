// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 W9 tasks 3/4/8 — the event-reads CAPTURE, frontend half.
// Rules:    BR-CUS-021 (reads commit through metering's own append-only
//           service) · BR-MET-128 (the event and its user ride the row) ·
//           BR-MET-129 (warnings post with their flags; only errors refuse) ·
//           BR-MET-026/027/058 (the estimate: disclosed, capped, per register)
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE IN THIS FILE IS ABOUT SOMETHING NOT HAPPENING**, and that is
// the shape of the risk. A capture control's failure mode is not a crash — it
// is a number appearing that nobody keyed:
//
//   1. a blank register reaching the payload as `0` — an invented reading on an
//      append-only table, which hard rule 4 then makes uncorrectable in place;
//   2. `[]` reaching the server when nothing was keyed, turning the lawful
//      "no readings this move" into a refusal;
//   3. a value AND an estimate on one register, which the door refuses whole;
//   4. an estimate REFUSAL ("no history — field visit") going unrendered, so a
//      clerk leaves believing every meter was handled.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { Translator } from "@/features/tenancy/settingsShared";

import {
  MoveReadsResult,
  eventReadRows,
  effectiveReadsDraft,
  prefilledReadsDraft,
  priorFinalValue,
  priorReadAgeDays,
  priorReadLine,
  readableAssets,
  readsPayloadPart,
  withReadDraft,
} from "./moveReadsCapture";
import type { EventReadsAnswer, ReadsDraft } from "./moveReadsCapture";
import type { UnitAssets } from "./UnitAssetsPanel";

const t: Translator = (key, params) => i18n.t(key, params);

/** Eight days after the fixture's `2026-07-31` read — the PO's own worked gap.
 *  Frozen, because an age measured off an ambient clock cannot be asserted. */
const NOW = new Date("2026-08-08T00:00:00Z");

function assets(over: Partial<UnitAssets> = {}): UnitAssets {
  return {
    unit: {
      id: "u-1",
      unit_no: "1",
      label: "88 Pine Vista · 1",
      premises_id: "p-1",
      premise_no: "P-1",
      premise_address: "88 Pine Vista",
    },
    counts: { total: 4 },
    reading_expected: { served: false, reason: "no reader", tracks: "DEF-495" },
    groups: [
      {
        category: "meters",
        assets: [
          {
            id: "ast-1",
            asset_no: "M-9101",
            type: "electric_meter",
            type_name: "Electric meter",
            category: "meters",
            qualifier: null,
            service: "electric",
            last_read: {
              read_id: "r-1",
              read_at: "2026-07-31",
              channel: "total",
              current_value: "42864.000000",
              consumption: "684.000000",
              unit: "kWh",
              current_value_display: "42864 kWh",
            },
          },
          {
            id: "ast-2",
            asset_no: "M-9102",
            type: "water_meter",
            type_name: "Water meter",
            category: "meters",
            qualifier: null,
            service: "water",
            last_read: null,
          },
        ],
      },
      {
        category: "sub_meters",
        assets: [
          {
            id: "ast-3",
            asset_no: "SM-8801",
            type: "sub_meter",
            type_name: "Sub-meter",
            category: "sub_meters",
            qualifier: "sub",
            service: "electric",
            last_read: null,
          },
        ],
      },
      {
        category: "behind_the_meter",
        assets: [
          {
            id: "ast-4",
            asset_no: "PV-3300",
            type: "pv",
            type_name: "PV inverter",
            category: "behind_the_meter",
            qualifier: "sub",
            service: "electric",
            last_read: null,
          },
        ],
      },
    ],
    ...over,
  };
}

function render(node: React.ReactElement): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const NOTHING: ReadsDraft = {};

describe("the event-reads capture (CR-038 W9)", () => {
  // ══════════════════════════════════════════════════════════════════════════
  // THE RULE THAT MATTERS MOST, AS A PURE FUNCTION
  // ══════════════════════════════════════════════════════════════════════════
  it("⛔ a blank register never reaches the payload — not as 0, not as null", () => {
    const draft: ReadsDraft = {
      "ast-1": { meterNo: "M-9101", value: "", estimate: false, readAt: "" },
      "ast-2": { meterNo: "M-9102", value: "   ", estimate: false, readAt: "" },
      "ast-3": { meterNo: "SM-8801", value: "1204", estimate: false, readAt: "" },
    };
    // CR-038 W9 task 3, verbatim: *"unread registers stay visible and nothing
    // is invented"*.
    expect(eventReadRows(draft)).toEqual([{ meter_no: "SM-8801", value: "1204" }]);
  });

  it("⛔ an empty capture OMITS the key rather than sending `[]`", () => {
    // The server refuses `[]` on purpose (`customers.event_reads.rows_required`)
    // and a move with no readings is lawful — sending `[]` would turn the
    // lawful case into a refusal.
    expect(readsPayloadPart("initial_reads", NOTHING)).toEqual({});
    expect(
      readsPayloadPart("final_reads", {
        "ast-1": { meterNo: "M-9101", value: "43566", estimate: false, readAt: "" },
      }),
    ).toEqual({ final_reads: [{ meter_no: "M-9101", value: "43566" }] });
  });

  it("⛔ a value and an estimate never travel together for one register", () => {
    // The door refuses the contradiction rather than choosing between them
    // (`metering.event_reads.value_and_estimate`), so the draft cannot hold it.
    const typed = withReadDraft(NOTHING, "ast-1", "M-9101", { value: "43566" });
    const ticked = withReadDraft(typed, "ast-1", "M-9101", { estimate: true });
    // `readAt` joined the row in `CR-122-BRC06` — the blueprint's per-row
    // `READ DATE`. `""` means *the flow's own event date*, which is what every
    // row carried implicitly before the column existed.
    expect(ticked["ast-1"]).toEqual({
      meterNo: "M-9101",
      value: "",
      estimate: true,
      readAt: "",
    });
    expect(eventReadRows(ticked)).toEqual([{ meter_no: "M-9101", estimate: true }]);
  });

  // ══════════════════════════════════════════════════════════════════════
  // `CR-122-BRC06` — THE READ DATE, FROM THE DRAFT TO THE PAYLOAD
  // ══════════════════════════════════════════════════════════════════════
  //
  // ⚠ **EVERY OTHER DRAFT IN THIS FILE CARRIES `readAt: ""`, SO UNTIL THESE
  // THREE CASES THE COLUMN'S ONLY TESTED STATE WAS ITS DEFAULT.** That is the
  // join hard-won law 2 lives in: a date the table collects and the payload
  // drops looks perfect on screen, passes `tsc`, passes every case above, and
  // reaches the server as nothing. The backend half is proved on real
  // PostgreSQL in `test_cr122_brc06_move_in_reads_and_claim.py`; this is the
  // half that proves the screen HANDS it that date.
  it("`CR-122-BRC06` a typed read date reaches the payload as `read_at`", () => {
    const dated = withReadDraft(NOTHING, "ast-1", "M-9101", {
      value: "8902",
      readAt: "2026-04-29",
    });
    // The blueprint's own case (p072 of the 281-page edition): the register was
    // walked on the 29th and the tenant moved in on the 2nd.
    expect(eventReadRows(dated)).toEqual([
      { meter_no: "M-9101", value: "8902", read_at: "2026-04-29" },
    ]);
  });

  it("`CR-122-BRC06` an untouched row still sends NO `read_at`", () => {
    // ⛔ NOT the event date spelled out. `_commit_event_reads` fills an absent
    // `read_at` with the flow's own date, so an untouched row keeps exactly the
    // behaviour it had before this column existed — and sending the date
    // explicitly would look identical on screen while silently FREEZING a date
    // the clerk later changes on this same step.
    const plain = withReadDraft(NOTHING, "ast-1", "M-9101", { value: "41680" });
    const row = eventReadRows(plain)[0];
    expect(row).toEqual({ meter_no: "M-9101", value: "41680" });
    expect("read_at" in row).toBe(false);
  });

  it("`CR-122-BRC06` an unreadable register carries its own date too", () => {
    // A walk-by round that could not read a meter still happened on a DAY, and
    // the estimate is worked out against that day's history rather than the
    // move's. The row keeps carrying no `value` — the two never travel together.
    const ticked = withReadDraft(NOTHING, "ast-1", "M-9101", {
      estimate: true,
      readAt: "2026-04-29",
    });
    expect(eventReadRows(ticked)).toEqual([
      { meter_no: "M-9101", estimate: true, read_at: "2026-04-29" },
    ]);
  });

  it("the readable registers are the meters and sub-meters, and nothing else", () => {
    // A reading is a REGISTER position. `behind_the_meter` holds devices that
    // hang off a meter, and a box there asks for a number with nowhere to go.
    expect(readableAssets(assets()).map((asset) => asset.asset_no)).toEqual([
      "M-9101",
      "M-9102",
      "SM-8801",
    ]);
    expect(readableAssets(undefined)).toEqual([]);
    // ⚠ DEF-757's shape, one field along: the TYPE says `groups` is always
    // there, and DEF-757 is a payload that broke the whole move-in screen by
    // omitting a field typed exactly that way. Defended, not trusted.
    expect(readableAssets({ ...assets(), groups: undefined as never })).toEqual([]);
  });

  it("OQ-394 — the age is whole days, and today/yesterday read as words", () => {
    const asset = assets().groups[0].assets[0];
    expect(priorReadAgeDays(asset, NOW)).toBe(8);
    expect(priorReadLine(asset, NOW, t)).toContain("read 8 days ago");
    expect(priorReadLine(asset, new Date("2026-07-31T00:00:00Z"), t)).toContain("read today");
    expect(priorReadLine(asset, new Date("2026-08-01T00:00:00Z"), t)).toContain("read yesterday");
    // A read with no date on record says so rather than claiming an age.
    const undated = {
      ...asset,
      last_read: { ...asset.last_read!, read_at: null },
    };
    expect(priorReadAgeDays(undated, NOW)).toBeNull();
    expect(priorReadLine(undated, NOW, t)).toContain("date we do not hold");
  });

  it("OQ-394 — the SEEDED draft is the draft the payload is built from", () => {
    // ⚠ The failure this pins is a screen that SHOWS 42,864, takes a Next and
    // posts nothing — the ruling's own failure with a friendlier face.
    const draft = prefilledReadsDraft(assets());
    expect(draft["ast-1"]).toEqual({ meterNo: "M-9101", value: "42864", estimate: false, readAt: "" });
    expect(eventReadRows(draft)).toEqual([{ meter_no: "M-9101", value: "42864" }]);
    expect(readsPayloadPart("final_reads", draft)).toEqual({
      final_reads: [{ meter_no: "M-9101", value: "42864" }],
    });
    // The two unread registers seeded blank and stayed out of the payload.
    expect(priorFinalValue(assets().groups[0].assets[1])).toBe("");
    // A unit with nothing readable prefills nothing at all.
    expect(prefilledReadsDraft(undefined)).toEqual({});
    // ⚠ **THE CLERK'S ENTRY WINS, INCLUDING AN ENTRY THAT IS EMPTY.** Deleting
    // a prefilled number has to MEAN deleting it — a merge that put the seed
    // back would make the box impossible to clear, and the register would post
    // last period's reading no matter what anyone did.
    const cleared = effectiveReadsDraft(assets(), {
      "ast-1": { meterNo: "M-9101", value: "", estimate: false, readAt: "" },
    });
    expect(cleared["ast-1"].value).toBe("");
    expect(eventReadRows(cleared)).toEqual([]);
    // A typed correction wins the same way, and the untouched registers keep
    // their seed.
    const typed = effectiveReadsDraft(assets(), {
      "ast-2": { meterNo: "M-9102", value: "17", estimate: false, readAt: "" },
    });
    expect(typed["ast-1"].value).toBe("42864");
    expect(typed["ast-2"].value).toBe("17");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // THE ANSWER — and the half a posted count would hide
  // ══════════════════════════════════════════════════════════════════════════
  it("task 8 — an estimate REFUSAL is rendered per register, never a silent zero", () => {
    const answer: EventReadsAnswer = {
      event: "move_out",
      batch_id: null,
      posted_reads: 1,
      posted: [],
      estimates: [
        {
          meter_no: "M-9101",
          channel: "total",
          estimated: true,
          consumption: "304.918033",
          unit: "kWh",
          estimation_method: "3-cycle avg",
          consecutive_estimate_no: 1,
        },
        { meter_no: "M-9102", channel: "total", estimated: false, reason: "no_history" },
      ],
      warnings: [{ row_no: 1, meter_no: "M-9101", rules: [{ rule: "vacant_unit" }] }],
    };
    const html = render(<MoveReadsResult answer={answer} t={t} />);
    // The estimate that WORKED, with its disclosed working (BR-MET-026).
    expect(html).toContain("304.918033");
    expect(html).toContain("3-cycle avg");
    // ⛔ And the one that did NOT. A posted count alone would let a clerk leave
    // believing both meters were handled.
    expect(html).toContain('data-move-reads-refused="1"');
    expect(html).toContain("M-9102");
    // BR-MET-129 — the warned reading POSTED and travels with its flags.
    expect(html).toContain('data-move-reads-warned="1"');
    expect(html).toContain("flagged");
  });

  it("a flow that captured nothing renders nothing — never `0 readings recorded`", () => {
    // The server OMITS `event_reads` when no readings were carried, so the
    // done screen must not claim a capture happened and come up empty.
    expect(render(<MoveReadsResult answer={undefined} t={t} />)).toBe("");
  });
});
