// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave E · E7 (group the list by event) · E5 (the designer's
//          surface switcher, which is the same relationship read backwards)
// Screens: SET-09 · SET-10
// ───────────────────────────────────────────────────────
// The derivation, without a DOM — because the two rules worth pinning are
// arithmetic over an array and would otherwise only be observable through a
// rendered table, where a failure says "element not found" and not which rule
// broke.
//
// The two rules:
//
//  1. **RUNS ARE CONTIGUOUS.** `eventRuns` joins only ADJACENT rows, so a page
//     whose sort scatters an event produces runs of one rather than a heading
//     over rows that are not next to each other. A global `group-by` would look
//     identical on the seeded fixture (which IS sorted by name) and be wrong on
//     every other sort — this is the assertion that tells them apart.
//  2. **A GROUP OF ONE IS NOT A GROUP.** 32 of the 37 seeded rows are their own
//     event; `count === 1` is what lets the screen draw them exactly as it drew
//     them before E7, with no surface line and no count badge.
//
// The fixture names are QUOTED from `apps/notifications/catalogs.py`, not
// invented, because the derivation reads copy and a test on invented copy would
// prove the parser and not the product.
import { describe, expect, it } from "vitest";

import {
  SURFACE_SEPARATOR,
  eventRuns,
  siblingSurfaces,
  templateEvent,
  templateSurface,
} from "./templateEvents";

/** Quoted from `catalogs.py` — the four events CR-048 E7 counts, in the order
 *  the server's `name` sort puts them. */
const SORTED_BY_NAME = [
  { code: "email_bill_ready", name: "Bill ready · e-bill email" },
  { code: "sms_bill_ready", name: "Bill ready · SMS" },
  { code: "disconnect_notice_10_day", name: "Disconnect notice · 10-day warning" },
  { code: "disconnect_notice_5_day", name: "Disconnect notice · 5-day final reminder" },
  { code: "disconnect_notice_48_hour", name: "Disconnect notice · 48-hour certified" },
  { code: "sms_disconnect", name: "Disconnect notice · SMS supplement" },
  { code: "writeoff_notice", name: "Write-off notice" },
];

describe("CR-048 E7 — the event and the surface come out of the seeded name", () => {
  it("splits a seeded name at the first ` · `", () => {
    expect(templateEvent("Bill ready · e-bill email")).toBe("Bill ready");
    expect(templateSurface("Bill ready · e-bill email")).toBe("e-bill email");
    expect(SURFACE_SEPARATOR).toBe(" · ");
  });

  it("a template that is its own event has NO surface — `null`, never a guess", () => {
    // `null` and not `""` and not the row's `kind`: the name has not told us
    // which surface this is, and composing one here would be the screen
    // stating a fact the data does not.
    expect(templateEvent("Write-off notice")).toBe("Write-off notice");
    expect(templateSurface("Write-off notice")).toBeNull();
  });

  it("splits at the FIRST separator — later segments narrow, they do not re-parent", () => {
    expect(templateEvent("Payment plan · instalment due · reminder")).toBe("Payment plan");
    expect(templateSurface("Payment plan · instalment due · reminder")).toBe(
      "instalment due · reminder",
    );
  });

  it("does not split a bare `·` that carries no spaces", () => {
    // The separator is matched WITH its spaces, so a name that happens to
    // contain a middle dot is left whole rather than cut in an arbitrary place.
    expect(templateEvent("Notice·2")).toBe("Notice·2");
    expect(templateSurface("Notice·2")).toBeNull();
  });
});

describe("CR-048 E7 — runs, and the contiguity that makes a heading honest", () => {
  it("the first row of a run leads it and the rest do not", () => {
    const runs = eventRuns(SORTED_BY_NAME);
    expect(runs.map((r) => r.leads)).toEqual([
      true, // Bill ready · e-bill email
      false, // Bill ready · SMS
      true, // Disconnect notice · 10-day warning
      false,
      false,
      false, // … · SMS supplement
      true, // Write-off notice
    ]);
  });

  it("every row of a run carries the run's TOTAL, not the count so far", () => {
    // The lead row is rendered first and needs the total to print "4 surfaces";
    // a single forward pass would give it 1. This is the assertion that fails
    // if the second pass is ever optimised away.
    const runs = eventRuns(SORTED_BY_NAME);
    expect(runs.map((r) => r.count)).toEqual([2, 2, 4, 4, 4, 4, 1]);
  });

  it("a row that is its own event is a run of ONE, which the screen draws as it always did", () => {
    const runs = eventRuns(SORTED_BY_NAME);
    const writeoff = runs[6];
    expect(writeoff).toEqual({
      event: "Write-off notice",
      surface: null,
      leads: true,
      count: 1,
    });
  });

  it("⚠ NEVER gathers scattered rows — two runs of one, not one group of two", () => {
    // THE assertion of this file. A global group-by keyed on the event would
    // return `count: 2` for both Bill ready rows here and draw one heading
    // over rows with another event's row between them, which states something
    // false about the list. Contiguous runs return 1 and 1, so the screen
    // draws two ordinary rows.
    const scattered = [
      { code: "email_bill_ready", name: "Bill ready · e-bill email" },
      { code: "writeoff_notice", name: "Write-off notice" },
      { code: "sms_bill_ready", name: "Bill ready · SMS" },
    ];
    const runs = eventRuns(scattered);
    expect(runs.map((r) => r.count)).toEqual([1, 1, 1]);
    expect(runs.map((r) => r.leads)).toEqual([true, true, true]);
  });

  it("an empty page produces no runs rather than throwing", () => {
    expect(eventRuns([])).toEqual([]);
  });
});

describe("CR-048 E5 — the sibling surfaces of one template", () => {
  it("returns every surface of the event, the open one included", () => {
    const siblings = siblingSurfaces(SORTED_BY_NAME, "sms_bill_ready");
    expect(siblings.map((row) => row.code)).toEqual(["email_bill_ready", "sms_bill_ready"]);
  });

  it("a template that is its own event gets NO switcher", () => {
    // BR-SHL-010: one tab is a control that cannot do anything. An empty list
    // is what stops the screen drawing furniture for an absent capability.
    expect(siblingSurfaces(SORTED_BY_NAME, "writeoff_notice")).toEqual([]);
  });

  it("a code the page does not hold gets NO switcher, rather than a wrong one", () => {
    // The catalog page is one PAGE of rows. A detail screen reached by a
    // pasted `?template=` link whose row is not on it must draw nothing, never
    // a switcher built from whichever rows happened to be loaded.
    expect(siblingSurfaces(SORTED_BY_NAME, "email_statement")).toEqual([]);
  });
});
