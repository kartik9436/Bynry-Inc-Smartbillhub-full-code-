// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-013 (S29 read detail — correct & dispute) · US-MET-016
//           Change:  the Meter Reads blueprint, entries 04 (Correct the
//           reading), 05 (Dispute the reading) and 06 (Clear the dispute) —
//           three dialogs on one reading, built from the drawn pages as IMAGES
//           (B14 rule 42, PO 2026-09-13: "When you use images to create screens
//           your accuracy is higher; hence dont create screens using only
//           Text").  Screens: S29
// Rules:    B14 rule 11 (the consequence is stated BEFORE the commit) · rule 33
//           (on-screen text is capped by what it is FOR) · rule 38 (where a
//           drawing and our UI rules disagree about how a FORM is built, the UI
//           rules win) · rule 39 (label → input → helper, one spacing scale) ·
//           BR-MET-024 (a correction APPENDS; nothing is edited) · BR-MET-133
//           (a dispute on a billed reading: the issued bill stands) ·
//           CLAUDE.md hard rule 3 (a quantity ALWAYS carries its unit) ·
//           hard rule 4 (financial immutability)
// ───────────────────────────────────────────────────────
//
// WHAT THIS SUITE IS FOR, AND WHY IT IS ORDER-SENSITIVE
// -----------------------------------------------------
// These three dialogs are the only place in Meter Reads where a clerk changes a
// reading, marks one, or releases one back into a bill run. Every one of them is
// a FormModal with the same four parts — a kicker, a field or two, a consequence
// line, a footer — so the thing that distinguishes a correct build from a wrong
// one is almost entirely **which sentence sits where**. A `toContain` check
// passes over a consequence line printed above an empty form just as happily as
// over one printed against the button that commits it, and B14 rule 11 is the
// difference. So the cases below compare INDEXES in the rendered HTML, not
// presence.
//
// ⚠ **THE REGISTER IS THE POINT OF THE FIRST CASE (step-1 Q7, PO 2026-09-14).**
// A reading filed against the wrong register is PERMANENT — `supersede_read`
// takes a value and a reason and nothing else, and metering migration `0007`'s
// trigger freezes the channel — and on a demand plan the units differ, which is
// how `DEF-797` billed **412 kW as 14 kWh: $154.00 against $4,532.00**. A dialog
// COVERS the page that names the register, so while one is open its kicker is
// the only place the register appears. It said "Reads".
//
// ⚠ **AND NOTHING HERE DECIDES WHAT A WRONG REGISTER SHOULD HAVE BEEN.** The
// four shapes on the table for that (a correction that carries a channel · a
// re-register supersede · saying it on screen · refusing at the import door) are
// all unchosen, and B4/B5 are ❄️ FROZEN. These cases assert that the register is
// VISIBLE and that the unit is never missing — never that either is editable.
//
// RED PROOF (hard-won law 7), MEASURED — in a `git worktree` pinned to the tip
// `b3704ede`, with this file copied in and the ONLY other change being the three
// `export` keywords and a shim for `unitOrDash`, so that every case fails on its
// real subject rather than on an unresolved import:
//
//   npx vitest run src/features/metering/ReadActionDialogs.test.tsx
//   × entry 04 · the kicker names the meter AND the register
//       → expected '<div class="modal-overlay">…' to contain 'Total register'
//   × entry 04 · a TOU window says which window
//       → expected '<div class="modal-overlay">…' to contain 'On-peak'
//   × entry 04 · the consequence is the LAST thing before the footer
//       → expected 731 to be greater than 1214
//   × entry 04 · hard rule 3 — a missing unit is a DASH, never a blank
//       → expected '<div class="modal-overlay">…' to contain 'In —'
//   × entry 05 · the figure under dispute is the drawn warning rail
//       → expected '…' to contain 'data-dialog-rail="under-dispute"'
//   × entry 05 · the consequence sits against the commit, not above the form
//       → expected 731 to be greater than 996
//   × entry 05 · the kicker names the register here too
//       → expected '…' to contain 'Reading · M-7001 · Total register'
//   × entry 05 · BR-MET-133 sits beside the consequence
//       → expected 1096 to be greater than 1358
//   × entry 06 · the note comes first and the consequence last
//       → expected 1027 to be less than 728
//   × entry 06 · the kicker names the register here too
//       → expected '…' to contain 'Reading · M-7001 · Total register'
//   10 failed | 9 passed (19)
//
// ⚠ **THE NINE THAT PASSED AT THAT TIP ARE NAMED, BECAUSE A RED PROOF THAT DOES
// NOT SAY WHAT IT FAILED TO PROVE IS HALF A PROOF.** Three of them are the
// rule-33 copy cases (`valueHelp`, `reasonHelp`, `resolutionHelp`): a sibling
// lane had already landed the blueprint's copy-budget cuts in all eleven
// catalogues by the time the proof ran, so those three assertions were green
// before this file existed and this suite only holds them there. The other six
// assert things that were already true — the field order, the dash in the
// dispute figure, the absent register picker, and no database id on screen —
// and they are regression cover, not this lane's work.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReadChainEntry, ReadDetail } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  ClearDisputeModal,
  DisputeModal,
  LIFECYCLE_BILLED,
  OverrideModal,
  unitOrDash,
} from "./ReadDetailPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** M-7001's August total-register read — the fixture US-MET-013 §4 uses. */
function detail(over: Partial<ReadDetail> = {}): ReadDetail {
  const base = {
    id: "r-7001-aug",
    meter: "M-7001",
    asset_id: "a-7001",
    cycle: "08-A",
    cycle_id: "c-08a",
    route: "R-1",
    route_id: "rt-1",
    service: "electric",
    premise: "1408 Elm Street",
    premise_no: "P-00101",
    premises_id: "p-1408",
    unit_label: "Unit A",
    unit_id: "u-1408a",
    channel: "total",
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
    read_type: "consumption",
    read_method: "walk_by",
    read_method_origin: "derived",
    status: "ok",
    lifecycle: "committed",
    rule_outcomes: [],
    import_batch_id: "b-2608-04",
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
    corrections: [],
    net_pair: {
      is_net_meter: false,
      read_at: "2026-08-03",
      consumption: null,
      export: null,
      absent_reason: "asset_is_not_net_metering",
    },
    chain: [] as ReadChainEntry[],
    ...over,
  } as ReadDetail;
  if (base.chain.length === 0) {
    base.chain = [{ ...base, version: 1 } as unknown as ReadChainEntry];
  }
  return base;
}

/**
 * ⚠ MOUNTED UNDER THE REAL PATH PATTERN, not a bare `MemoryRouter`. A router
 * with no `/:tenant/...` route leaves `useParams().tenant` undefined and every
 * address a component builds comes out `//…` — a protocol-relative URL to
 * another host, which reads as a perfectly good string to `toContain`
 * (hard-won law 2's fixture clause).
 */
function mount(node: ReactNode): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads/r-7001-aug`]}>
        <Routes>
          <Route path="/:tenant/reads/:readId" element={<ToastProvider>{node}</ToastProvider>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const correct = (read = detail()): string =>
  mount(
    <OverrideModal
      read={read}
      working={false}
      onSubmit={async () => undefined}
      onClose={() => undefined}
    />,
  );

const dispute = (read = detail()): string =>
  mount(<DisputeModal read={read} onSubmit={async () => undefined} onClose={() => undefined} />);

const clear = (read = detail({ disputed: true })): string =>
  mount(
    <ClearDisputeModal read={read} onSubmit={async () => undefined} onClose={() => undefined} />,
  );

/** Where a string sits in the rendered markup. Fails loudly rather than -1. */
function at(html: string, needle: string): number {
  const index = html.indexOf(needle);
  expect(index, `not rendered at all: ${needle}`).toBeGreaterThan(-1);
  return index;
}

describe("blueprint entry 04 — Correct the reading", () => {
  it("step-1 Q7: the kicker names the meter AND the register", () => {
    // The dialog covers the page, so this is the only register on screen while
    // a clerk types a new value into a reading whose channel is frozen for ever.
    const html = correct();
    expect(html).toContain(t("metering.reads.channel.total"));
    expect(html).toContain("M-7001");
    // The list's own word named the screen you came from, not the row you are
    // about to change: `metering.reads.kicker` is "Reads".
    expect(html).toContain(
      t("metering.read.kicker", { meter: "M-7001", channel: t("metering.reads.channel.total") }),
    );
  });

  it("a TOU window says which window, because that is where DEF-797 happened", () => {
    // 412 kW filed on `total` and billed as 14 kWh is the register being wrong
    // rather than the number: the registers' own units differ.
    const html = correct(detail({ channel: "tou_on", unit: "kW", usage_display: "412 kW" }));
    expect(html).toContain(t("metering.reads.channel.tou_on"));
  });

  it("the drawn fields are there, in the drawn order, and nothing else is", () => {
    const html = correct();
    expect(at(html, t("metering.read.override.value"))).toBeLessThan(
      at(html, t("metering.read.override.reason")),
    );
    // Entry 04's field table is three items — two fields and the consequence.
    // A register picker is NOT one of them: the channel is frozen in the
    // database and which of four shapes fixes that is unruled.
    expect(html).not.toContain(t("metering.read.detail.unit"));
  });

  it("B14 rule 11: the consequence is the LAST thing before the footer", () => {
    // It used to open the dialog, above an empty form. A consequence read
    // before there is anything to commit is a sentence people learn to skip.
    const html = correct();
    expect(at(html, t("metering.read.override.note"))).toBeGreaterThan(
      at(html, t("metering.read.override.reason")),
    );
    expect(at(html, t("metering.read.override.note"))).toBeLessThan(
      at(html, t("metering.read.override.submit")),
    );
  });

  it("BR-MET-024: the consequence says the old reading SURVIVES", () => {
    // Hard rule 4 — a correction is a new row and the original is immutable.
    // The clerk is told that before the click, not after it.
    expect(t("metering.read.override.note")).toContain("history");
  });

  it("hard rule 3: the helper states the unit, and a missing unit is a DASH", () => {
    expect(correct()).toContain("kWh");
    // ⚠ `?? ""` rendered "In ." here — an empty gap where the unit belongs, on
    // the dialog that rewrites the number a bill is computed from.
    const html = correct(detail({ unit: null, usage_display: null }));
    expect(html).toContain("In —");
    expect(html).not.toContain("In .");
    expect(unitOrDash(null)).toBe("—");
    expect(unitOrDash("   ")).toBe("—");
    expect(unitOrDash("kgal")).toBe("kgal");
  });

  it("B14 rule 33: the helper is two short sentences, not one long one", () => {
    // "In kgal — consumption and every rule are recomputed." was one
    // eight-word consequence. Two sentences of six beat one of twelve.
    const help = t("metering.read.override.valueHelp", { unit: "kgal" });
    expect(help).toBe("In kgal. Usage and flags recompute.");
  });
});

describe("blueprint entry 05 — Dispute the reading", () => {
  it("the figure under dispute is FIRST, on the drawn warning rail", () => {
    const html = dispute();
    expect(html).toContain('data-dialog-rail="under-dispute"');
    expect(html).toContain("border-l-warning-700");
    // Rule 3: the quantity carries its unit, from the server's own composed
    // string — never a bare number a clerk could copy onto a bill.
    expect(html).toContain(t("metering.read.dispute.figure", { usage: "684 kWh" }));
    expect(at(html, t("metering.read.dispute.figure", { usage: "684 kWh" }))).toBeLessThan(
      at(html, t("metering.read.dispute.reason")),
    );
  });

  it("a reading whose unit never arrived shows a dash, not a bare number", () => {
    const html = dispute(detail({ usage_display: null, unit: null }));
    expect(html).toContain(t("metering.read.dispute.figure", { usage: "—" }));
  });

  it("B14 rule 11: the consequence sits against the commit, not above the form", () => {
    const html = dispute();
    expect(at(html, t("metering.read.dispute.note"))).toBeGreaterThan(
      at(html, t("metering.read.dispute.reason")),
    );
    expect(at(html, t("metering.read.dispute.note"))).toBeLessThan(
      at(html, t("metering.read.dispute.submit")),
    );
  });

  it("the kicker names the register here too", () => {
    expect(dispute()).toContain(
      t("metering.read.kicker", { meter: "M-7001", channel: t("metering.reads.channel.total") }),
    );
  });

  it("B14 rule 33: the helper quotes nobody and explains nothing", () => {
    // It carried a 10-word rationale AND an example sentence. Rationale is
    // ZERO words on screen; the example is what the clerk types, not copy.
    expect(t("metering.read.dispute.reasonHelp")).toBe("A System Admin reads this.");
  });

  it("BR-MET-133 still reaches the clerk on a BILLED reading, beside the consequence", () => {
    const html = dispute(detail({ lifecycle: LIFECYCLE_BILLED }));
    expect(html).toContain(t("metering.read.dispute.billedBillStands"));
    expect(at(html, t("metering.read.dispute.billedBillStands"))).toBeGreaterThan(
      at(html, t("metering.read.dispute.reason")),
    );
    // And it is absent where it does not apply.
    expect(dispute()).not.toContain(t("metering.read.dispute.billedBillStands"));
  });
});

describe("blueprint entry 06 — Clear the dispute", () => {
  it("the note is the only field, and the consequence is last", () => {
    const html = clear();
    expect(at(html, t("metering.read.dispute.resolution"))).toBeLessThan(
      at(html, t("metering.read.dispute.clearNote")),
    );
    expect(at(html, t("metering.read.dispute.clearNote"))).toBeLessThan(
      at(html, t("metering.read.dispute.clearSubmit")),
    );
  });

  it("the submit label is a sentence, because what it does is not “clear”", () => {
    // The blueprint's own words: it is *let the account bill*. B14 rule 33's
    // 3-word label cap is a LABEL cap; this one is deliberately a consequence
    // the button states, and the drawing draws it that way.
    expect(t("metering.read.dispute.clearSubmit")).toBe("Clear it and let the account bill");
  });

  it("B14 rule 33: the helper says where the note goes and stops", () => {
    // "…, not on the reading" was the half that explained what is NOT
    // happening — an absence rather than a fact.
    expect(t("metering.read.dispute.resolutionHelp")).toBe("Stored in the audit trail.");
  });

  it("the kicker names the register here too", () => {
    expect(clear()).toContain(
      t("metering.read.kicker", { meter: "M-7001", channel: t("metering.reads.channel.total") }),
    );
  });
});

describe("all three dialogs — what they do NOT offer", () => {
  it("none of them can move a reading to another register", () => {
    // Entry 04's own finding: `supersede_read` accepts two fields, value and
    // reason, and migration 0007 freezes asset · read_at · CHANNEL · values ·
    // multiplier · consumption · unit. A control here would be a promise the
    // database refuses — and which of the four shapes closes that gap is
    // unruled (the PO declined to classify it: "Money path, so I'm not
    // classifying it"). Visible, never editable.
    for (const html of [correct(), dispute(), clear()]) {
      expect(html).not.toContain(t("metering.reads.channel.tou_off"));
      expect(html).not.toContain(t("metering.reads.channel.demand"));
    }
  });

  it("no database id reaches the screen (B14 rule 31)", () => {
    for (const html of [correct(), dispute(), clear()]) {
      expect(html).not.toContain("r-7001-aug");
      expect(html).not.toContain("a-7001");
    }
  });
});
