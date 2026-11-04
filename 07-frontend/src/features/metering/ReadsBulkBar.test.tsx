// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 · ADDITION 2026-08-26 — W5 task 7 (bulk operations) and
//           task 6 (the quick single-reading modal).
// Story:    US-MET-012.  Screens: S25.
// Rules:    BR-MET-129 (a warned reading POSTS; flags are worked AFTER commit) ·
//           BR-MET-023 (why only ACCEPT is bulk) · BR-SHL-025 (a control a row
//           cannot offer renders DISABLED with its reason) · BR-MET-049 (what
//           makes a meter "simple") · CLAUDE.md hard rule 3 (an explicit unit)
// ───────────────────────────────────────────────────────
// **THE PO'S SENTENCE, AS EXECUTABLE CODE (2026-08-26):** *"keep the rule —
// speed comes from the bulk button… an auditor asking 'who chose to estimate
// M-4412?' gets a name"*. The screen's half of that is: the reason box is
// required, the clerk is TOLD their name is recorded, and a refused row comes
// back NAMED rather than folded into a count.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReadRow } from "@/api/endpoints";

import {
  BulkOutcome,
  ReadsBulkBar,
  bulkFixReads,
  bulkSelectable,
  bulkReasonSchema,
} from "./ReadsBulkBar";
import type { BulkFixResult } from "./ReadsBulkBar";
import {
  channelWord,
  displayMultiplier,
  quickReadBatchRequest,
  quickReadSchema,
} from "./QuickReadModal";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function read(over: Partial<ReadRow> = {}): ReadRow {
  return {
    id: "r-1",
    meter: "M-4412",
    asset_id: "a-1",
    cycle: null,
    cycle_id: null,
    route: null,
    route_id: null,
    service: null,
    premise: null,
    premise_no: null,
    premises_id: null,
    unit_label: null,
    unit_id: null,
    channel: "total",
    read_at: "2026-07-15",
    period_start: null,
    period_end: null,
    prior_value: null,
    current_value: "1000",
    prior_value_display: null,
    current_value_display: "1000 kWh",
    multiplier: "1",
    consumption: "684",
    unit: "kWh",
    usage_display: "684 kWh",
    days_since_prior: null,
    source: "import",
    source_detail: null,
    status: "high",
    ...over,
  } as ReadRow;
}

function render(node: JSX.Element): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>{node}</QueryClientProvider>,
  );
}

describe("CR-038 W5 T7 — S25 bulk operations (BR-MET-129 · BR-MET-023)", () => {
  it("BR-SHL-025: an unflagged row and a derived row are NOT selectable, each with a reason", () => {
    // A flagged, stored reading — the thing an accept is ABOUT.
    expect(bulkSelectable(read()).ok).toBe(true);

    // An accept on an unflagged reading files a judgment about nothing.
    const clean = bulkSelectable(read({ status: "ok" }));
    expect(clean.ok).toBe(false);
    expect(clean.reason).toBe("notFlagged");

    // A DERIVED pending entry (`f.status=pending`) carries `id: null` — it is
    // not a stored read at all, so there is nothing to disposition.
    const pending = bulkSelectable(read({ id: "" as string }));
    expect(pending.ok).toBe(false);
    expect(pending.reason).toBe("derived");

    // Every reason resolves to a real sentence — no raw key reaches a clerk.
    expect(t("metering.reads.bulk.notSelectable.notFlagged")).not.toContain("metering.");
    expect(t("metering.reads.bulk.notSelectable.derived")).not.toContain("metering.");
  });

  it("the bar renders NOTHING until something is selected", () => {
    const html = render(
      <ReadsBulkBar selected={[]} rows={[read()]} onClear={() => {}} t={t} />,
    );
    expect(html).toBe("");
  });

  it("with a selection it offers ACCEPT and says why the other verbs are absent", () => {
    const html = render(
      <ReadsBulkBar selected={["r-1", "r-2"]} rows={[read()]} onClear={() => {}} t={t} />,
    );
    expect(html).toContain(t("metering.reads.bulk.selected", { count: 2 }));
    expect(html).toContain(t("metering.reads.bulk.accept"));
    // BR-MET-023's other verbs are NOT offered, and the clerk is TOLD rather
    // than left hunting for Override.
    expect(html).toContain("Accept only");
    expect(html).not.toContain("Override");
  });

  it("a REFUSED row is named, never folded into a count", () => {
    const result: BulkFixResult = {
      disposition: "accept",
      reason: "checked against the route sheet",
      acted_by: "u-1",
      selected: 3,
      applied: [{ read_id: "r-1", meter: "M-4412", channel: "total", status: "high" }],
      applied_count: 1,
      refused: [
        { read_id: "r-2", meter: "M-4413", reason: "not_head" },
        { read_id: "r-3", meter: "M-4414", reason: "already_dispositioned" },
      ],
      refused_count: 2,
      rule_ref: "BR-MET-129",
    };
    const html = render(<BulkOutcome result={result} onDismiss={() => {}} t={t} />);

    expect(html).toContain(t("metering.reads.bulk.result", { applied: 1, selected: 3 }));
    // "38 of 40 accepted" is a number a clerk cannot act on. These are.
    expect(html).toContain("M-4413");
    expect(html).toContain("M-4414");
    expect(html).toContain(
      t("metering.reads.bulk.refused.not_head", { meter: "M-4413" }),
    );
    expect(html).toContain('data-reason="already_dispositioned"');
  });

  it("no reason, no bulk action — the schema refuses before anything is posted", () => {
    const schema = bulkReasonSchema(t);
    expect(schema.safeParse({ reason: "   " }).success).toBe(false);
    expect(schema.safeParse({ reason: "checked the route sheet" }).success).toBe(true);
  });

  it("BR-MET-061: the reason travels to the server, so an accept is never a silent pass", async () => {
    // ⚠ **THE RULE THIS BAR EXISTS UNDER.** BR-MET-061 (CONFIRMED) makes the TOU
    // sum-sanity check a WARNING that is *"postable only via explicit accept +
    // reason … never a silent pass"*. BR-MET-129 moved WHEN the accept happens —
    // after the commit, from here — and did not touch the reason.
    //
    // A bulk accept that dropped the reason would look identical on screen and
    // would turn that explicit accept into the silent pass the rule forbids, for
    // every row at once. So the assertion is on the PAYLOAD, not the form.
    //
    // ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, ASKED BEFORE TRUSTING IT** (law 7,
    // habit 2). It exercises the WIRE FUNCTION, so it would stay green if
    // `BulkAcceptModal` called it with a constant instead of the typed reason —
    // that one link is NOT asserted here, and it is named rather than left for
    // a reader to assume. It is covered on both sides: `bulkReasonSchema`
    // refuses an empty reason before the form submits (the case above), and
    // `services._bulk_reason` refuses it again on the server. Closing the last
    // link needs jsdom, and this file renders statically.
    const sent: { path: string; body: unknown }[] = [];
    const client = {
      post: async (path: string, body?: unknown) => {
        sent.push({ path, body });
        return {
          ok: true,
          status: 200,
          data: {
            disposition: "accept",
            reason: "heatwave — checked against 2025 August",
            acted_by: "u-1",
            selected: 2,
            applied: [],
            applied_count: 2,
            refused: [],
            refused_count: 0,
            rule_ref: "BR-MET-061",
          },
        };
      },
    } as unknown as Parameters<typeof bulkFixReads>[1];

    await bulkFixReads(
      {
        read_ids: ["r-1", "r-2"],
        reason: "heatwave — checked against 2025 August",
        disposition: "accept",
      },
      client,
    );

    expect(sent).toHaveLength(1);
    expect(sent[0].path).toBe("/reads/bulk-fix");
    expect(sent[0].body).toMatchObject({
      read_ids: ["r-1", "r-2"],
      reason: "heatwave — checked against 2025 August",
      disposition: "accept",
    });
  });

  it("NFR-5: nothing on this screen caps the selection", () => {
    // A bulk action must not silently shorten what a clerk picked. The server
    // holds a 500-row BLAST-RADIUS guard and REFUSES past it by name
    // (`metering.reads.bulk.too_many`, which states the selection and the
    // maximum) — a refusal a clerk can see, never a truncation they cannot.
    const many = Array.from({ length: 640 }, (_, i) => `r-${i}`);
    const html = render(
      <ReadsBulkBar selected={many} rows={[read()]} onClear={() => {}} t={t} />,
    );
    expect(html).toContain(t("metering.reads.bulk.selected", { count: 640 }));
    expect(t("metering.reads.bulk.too_many", { max: 500 })).toContain("500");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// ENTRY 13's DRAWING — the three things that moved to match it
// ══════════════════════════════════════════════════════════════════════════
// Nothing in this repo reads rendered output, so these read the rendered CLASS
// ATTRIBUTE — the same instrument B14 rule 6's own checks use, and for the same
// reason: a prop assertion would have been green on the day it was wrong.
describe("entry 13 — the selection bar as it is drawn", () => {
  function bar(): string {
    return render(
      <ReadsBulkBar selected={["r-1", "r-2"]} rows={[read()]} onClear={() => {}} t={t} />,
    );
  }

  it("is a plain bordered bar — the accent rail is this module's WARNING device", () => {
    const html = bar();
    expect(html).toContain("border border-divider");
    // The rail says *something is wrong with this meter*. A selection is not.
    expect(html).not.toContain("border-l-accent-500");
  });

  it("puts the count in bold — it is the one thing in the row that changes", () => {
    expect(bar()).toContain(
      `<strong>${t("metering.reads.bulk.selected", { count: 2 })}</strong>`,
    );
  });

  it("pushes the *Accept only* sentence to the far right, out of the run of controls", () => {
    // B14 rule 32's clause: a row of controls holds only things a person can
    // PRESS. This is a fact about the bar, so it is drawn away from the buttons.
    const html = bar();
    expect(html).toMatch(/class="ml-auto [^"]*">Accept only/);
    expect(html).not.toContain("italic");
  });
});

describe("CR-038 W5 T6 — the quick single-reading modal", () => {
  it("builds a ONE-ROW batch whose period is DERIVED from the read date", () => {
    // CR-038's period/cycle sanity statement, clause 1: *"The read date is the
    // truth… Period membership is DERIVED from `read_at` … never typed."*
    const request = quickReadBatchRequest({
      meter_no: "M-4412",
      read_date: "2026-07-15",
      notes: "",
      cycleId: "cy-1",
      registers: [{ channel: "total", reading: "1300" }],
    });
    expect(request.rows).toHaveLength(1);
    expect(request.period_month).toBe("2026-07-01");
    expect(request.source_kind).toBe("manual");
    expect(request.cycle_id).toBe("cy-1");
    // An empty note is ABSENT, not an empty string on the row.
    expect(request.rows[0]).not.toHaveProperty("notes");
  });

  it("MR-25: a multi-register meter stages ONE ROW PER REGISTER, in the server's order", () => {
    // ⚠ **Q7, the ruling the PO put first.** The register of a filed reading can
    // never be changed — `supersede_read` takes only a value and a reason, and
    // migration `0007`'s trigger freezes the channel — so a form that collects
    // three numbers and files them against one register is a permanent error.
    // They are three rows of ONE batch: one visit to one meter, recorded as one.
    const request = quickReadBatchRequest({
      meter_no: "M-4412",
      read_date: "2026-07-15",
      notes: "",
      cycleId: "cy-1",
      registers: [
        { channel: "tou_on", reading: "12480" },
        { channel: "tou_off", reading: "31220" },
        { channel: "total", reading: "51710" },
      ],
    });
    expect(request.rows.map((row) => row.channel)).toEqual(["tou_on", "tou_off", "total"]);
    expect(request.rows.map((row) => row.reading)).toEqual(["12480", "31220", "51710"]);
    // One meter, one date — the only thing that varies is the register.
    expect(new Set(request.rows.map((row) => row.meter_id)).size).toBe(1);
    expect(new Set(request.rows.map((row) => row.read_date)).size).toBe(1);
  });

  it("a meter on NO cycle carries no cycle tag at all — an empty tag would be a claim", () => {
    const request = quickReadBatchRequest({
      meter_no: "M-4412",
      read_date: "2026-07-15",
      notes: "seal intact",
      cycleId: null,
      registers: [{ channel: "total", reading: "1300" }],
    });
    expect(request).not.toHaveProperty("cycle_id");
    expect(request.rows[0].notes).toBe("seal intact");
  });

  it("the form refuses an empty meter, date or reading before anything is staged", () => {
    const schema = quickReadSchema(t);
    expect(schema.safeParse({ meter_no: "", read_date: "2026-07-15", reading: "1" }).success).toBe(
      false,
    );
    expect(schema.safeParse({ meter_no: "M-1", read_date: "", reading: "1" }).success).toBe(false);
    expect(schema.safeParse({ meter_no: "M-1", read_date: "2026-07-15", reading: "" }).success).toBe(
      false,
    );
    expect(
      schema.safeParse({ meter_no: "M-1", read_date: "2026-07-15", reading: "1300" }).success,
    ).toBe(true);
  });

  it("and on a multi-register meter it refuses until EVERY register has a number", () => {
    // Two of three filed is a hole in a month nobody can correct.
    const schema = quickReadSchema(t, ["tou_on", "tou_off", "total"]);
    const base = { meter_no: "M-1", read_date: "2026-07-15" };
    expect(
      schema.safeParse({ ...base, reading_tou_on: "1", reading_tou_off: "2" }).success,
    ).toBe(false);
    expect(
      schema.safeParse({
        ...base,
        reading_tou_on: "1",
        reading_tou_off: "2",
        reading_total: "3",
      }).success,
    ).toBe(true);
  });

  it("MR-31: the register resolves to a WORD, and an unknown one falls back to the CODE", () => {
    // The reads list already translates a channel through this exact prefix, so
    // the modal reads it the same way and the two screens cannot disagree.
    expect(channelWord(t, "tou_on")).toBe(t("metering.reads.channel.tou_on"));
    expect(channelWord(t, "tou_on")).toBe("On-peak");
    // ⚠ A channel with no word must NEVER render its catalogue PATH at a clerk
    // (B14 rule 31). The code is ugly; a path is a defect.
    expect(channelWord(t, "solar_export_x")).toBe("solar_export_x");
    expect(channelWord(t, "solar_export_x")).not.toContain("metering.");
  });

  it("Q9: the multiplier reads as drawn — ×1, never ×1.000000", () => {
    // PO 2026-09-14, *"as drawn"*. Display only; the value the batch is rated
    // against is the server's, untouched.
    expect(displayMultiplier("1.000000")).toBe("1");
    expect(displayMultiplier("1")).toBe("1");
    expect(displayMultiplier("2.50")).toBe("2.5");
    // Hard rule 3's own sentence: a dash is the honest answer for an absence.
    expect(displayMultiplier(null)).toBe("—");
  });

  it("every message the modal can show resolves to a real sentence (G18's law, asserted)", () => {
    for (const key of [
      "metering.quickRead.open",
      "metering.quickRead.title",
      "metering.quickRead.meterHelp",
      "metering.quickRead.valueHelp",
      "metering.quickRead.registersUnknown",
      "metering.quickRead.registersUnknownAction",
      "metering.quickRead.cycleAbsentActionNoRoute",
      "metering.quickRead.cycleAbsentActionNoCycle",
      "metering.quickRead.outOfWindow",
    ]) {
      expect(t(key)).not.toBe(key);
    }
    // The count-bearing sentences interpolate rather than hardcoding a number.
    expect(t("metering.quickRead.multiExpects", { count: 4 })).toContain("4");
    expect(t("metering.quickRead.registerLabel", { register: "On-peak", unit: "kWh" })).toBe(
      "On-peak · kWh",
    );
  });
});
