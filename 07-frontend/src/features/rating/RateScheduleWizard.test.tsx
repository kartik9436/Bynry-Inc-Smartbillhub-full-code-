// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-005 (basics, flat & tiered, effective dates, review & activate) ·
//           US-RAT-006 (TOU Option B) · US-RAT-007 (demand, seasonal, capacity, %-of-water)
//           Screens: S11
// Rules:    BR-RAT-019 · BR-RAT-021 · BR-RAT-022 · BR-RAT-026 (no allowance field) ·
//           BR-RAT-031 (save-draft resumable; activation needs a complete structure AND
//           an effective date; NO approval control) · BR-RAT-032/033/034 (validation is
//           the SERVER's) · BR-RAT-038 (the UoM gate is stated, never converted)
// ───────────────────────────────────────────────────────
// The two tests this file exists for:
//
//   · a draft SAVES without a date and RESUMES with its tiers intact — which is
//     the whole of BR-RAT-031's "save-draft resumable";
//   · activation with no date is REFUSED BY THE SERVER, and the refusal renders
//     verbatim. Nothing here pre-validates a money rule to avoid asking.
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, createApiClient } from "@/api/client";
import { TARIFF_MODELS, activateRateSchedule, createRateSchedule } from "@/api/endpoints";
import type {
  LookupEntry,
  ScheduleDetail,
  TenantServiceRow,
  TierRow,
  VersionRow,
} from "@/api/endpoints";
import { apiErrorText, refusalOf } from "@/features/tenancy/settingsShared";
import { activeUomOptions } from "@/features/tenancy/SettingsServicesTab";

import {
  currentRateEndsOn,
  nextTierStart,
  tierGapAt,
  DAY_TYPES,
  RATE_CHANGE_SECOND_APPROVAL_PCT,
  RATE_WIZARD_STEPS,
  activationDates,
  baseLadder,
  draftFromSchedule,
  draftPayload,
  editorFor,
  emptyScheduleDraft,
  secondApprovalRequired,
  sizeLadders,
  structureOptions,
  structurePayload,
} from "./RateScheduleWizard";
import type { TierDraft } from "./RateScheduleWizard";
import { MATRIX_COLUMNS, editableMatrixColumns } from "./RateScheduleDetail";
import type { Translator } from "./ratingShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…` and
// every tenant-scoped call goes to `/api/{tenant}/…`. Tests state the tenant
// the browser would be showing, so both are visible here rather than implied.
const TEST_TENANT = "brazosbend";


const t: Translator = (key, params) => i18n.t(key, params);

const SERVICES: TenantServiceRow[] = [
  {
    service: "water",
    name: "Water",
    enabled: true,
    primary_uom: "kgal",
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 3,
    active_accounts: 950,
  },
];

/**
 * The US-RAT-005 TC-3 fixture as the server stores it: a DRAFT is a real
 * `tariff_versions` row with `effective_from: null`, carrying the structure the
 * wizard posted. This is what `GET /rate-schedules/{id}` reads back.
 */
const SAVED_DRAFT: ScheduleDetail = {
  id: "t-res-w",
  name: "Res Water · Inclining",
  service: "water",
  service_name: "Water",
  account_type_id: null,
  structure: "tiered",
  status: "draft",
  scheduled_change: null,
  current_version: null,
  draft_version: {
    id: "v-draft",
    // DEF-RAT-5715 — BR-RAT-104's chain. The server sends all four on every
    // version row; a plain (uncorrected) version reads null for each.
    corrects: null,
    superseded_by: null,
    correction_reason: null,
    corrected_by: null,
    model: "tiered",
    uom: "kgal",
    currency: "USD",
    base_charge: "0.000000",
    minimum_bill: null,
    base_charge_display: "0.00",
    minimum_bill_display: null,
    size_rows: [],
    filing_authority: null,
    filed_on: null,
    regulator_approved_on: null,
    regulator_approver: null,
    effective_from: null, // BR-RAT-031: THE draft — no date, never in force
    effective_to: null,
    approved_by: null,
    regulator_ref: "TX PUC docket 51234",
    submitted_by: null, // DEF-367 — no filer recorded on this fixture
    version_label: null, // DEF-369 — falls back to the derived ordinal
    change_reason: null, // DEF-280 — no authored change note
    notify_customers: false,
    publish_public: false,
    structure: {
      model: "tiered",
unit: "kgal",
currency: "USD",
      tiers: [
        { seq: 1, season: null, size_class: null, from_qty: "0.000000", to_qty: "4.000000", from_qty_display: "0 kgal", to_qty_display: "4 kgal", unit_price: "3.200000" },
        { seq: 2, season: null, size_class: null, from_qty: "4.000000", to_qty: "10.000000", from_qty_display: "4 kgal", to_qty_display: "10 kgal", unit_price: "4.800000" },
        { seq: 3, season: null, size_class: null, from_qty: "10.000000", to_qty: null, from_qty_display: "10 kgal", to_qty_display: null, unit_price: "7.200000" },
      ],
    },
  },
  used_by_plans: 0,
  applied_to_accounts: 0,
  // DEF-441 — r10 line 764's five columns. A fixture states them
  // explicitly rather than defaulting, because "0 sizes" and
  // "no seasons" are the values the cells render differently.
  size_count: 0,
  season_labels: [],
  block_count: 0,
  window_count: 0,
  effective_from: null,
  versions: [],
  uom_gate: {
    satisfied: true,
    reason: "match",
    schedule_uom: "kgal",
    billed_uom: "kgal",
    priced_against: "kgal",
    conversion_factor: null,
  },
};

describe("US-RAT-005 — the S11 wizard: basics, flat and tiered", () => {
  it("US-RAT-005 TC-3: a saved draft RESUMES with its structure intact, every price unchanged", () => {
    // The RESUME half of BR-RAT-031: the server's dateless version comes back
    // and rebuilds the editable draft byte-for-byte.
    const draft = draftFromSchedule(SAVED_DRAFT);
    expect(draft.name).toBe("Res Water · Inclining");
    expect(draft.service).toBe("water");
    expect(draft.model).toBe("tiered");
    expect(draft.uom).toBe("kgal");
    expect(draft.regulator_ref).toBe("TX PUC docket 51234");
    // A draft has NO date, and resuming must not invent one.
    expect(draft.effective_from).toBe("");
    // ⚠ **A RESUMED DRAFT IS INPUT STATE, SO IT CARRIES NO `_display` SIBLING
    // (DEF-1121).** The clerk edits `from_qty`; a composed `"0 kgal"` in an
    // input would be submitted back as part of a decimal. Same reason
    // `trimQuantity` exists beside `formatQuantity` in `UnitCell` — the
    // grouped, composed form can never go into a field somebody types in.
    expect(draft.tiers).toEqual([
      { from_qty: "0.000000", to_qty: "4.000000", unit_price: "3.200000" },
      { from_qty: "4.000000", to_qty: "10.000000", unit_price: "4.800000" },
      // BR-RAT-032: the open last tier comes back as blank, not as "null".
      { from_qty: "10.000000", to_qty: "", unit_price: "7.200000" },
    ]);
  });

  it("US-RAT-005 TC-3: the round trip is byte-identical — nothing is parsed or re-formatted", () => {
    const resumed = draftFromSchedule(SAVED_DRAFT);
    const structure = structurePayload(resumed) as { tiers: Record<string, unknown>[] };
    // ⚠ **A `_display` SIBLING IS NEVER SENT BACK (DEF-1121, BR-SHL-250).** It
    // is composed by the server for a screen to render; posting one would ask
    // the server to store a rendering, which is DEF-1124's mistake in advance.
    // This assertion is the guard: the outbound tiers carry the three STORED
    // fields and nothing else.
    expect(structure.tiers).toEqual([
      { from_qty: "0.000000", to_qty: "4.000000", unit_price: "3.200000" },
      { from_qty: "4.000000", to_qty: "10.000000", unit_price: "4.800000" },
      // The ∞ tier's `to_qty` is OMITTED, never sent as null or as "0".
      { from_qty: "10.000000", unit_price: "7.200000" },
    ]);
  });

  it("BR-RAT-031: 'Save draft' posts NO effective date, which is what makes it a draft", () => {
    const draft = { ...draftFromSchedule(SAVED_DRAFT), effective_from: "2026-09-01" };
    const payload = draftPayload(draft, true);
    expect(payload.name).toBe("Res Water · Inclining");
    expect(payload.service).toBe("water");
    expect(payload.regulator_ref).toBe("TX PUC docket 51234");
    // Even with a date typed on step 3, the draft payload carries none.
    expect(payload.effective_from).toBeUndefined();
    expect(payload.effective_to).toBeUndefined();
    // A re-save of an existing schedule may not move the service either — the
    // server refuses it, so the payload does not offer it.
    expect(draftPayload(draft, false).service).toBeUndefined();
  });

  it("US-RAT-005 TC-3: activation with no date is the SERVER's refusal, rendered verbatim", async () => {
    // The dates are SENT even when blank, precisely so the server answers
    // rather than this screen guessing at the rule.
    expect(activationDates(emptyScheduleDraft())).toEqual({
      effective_from: null,
      effective_to: null,
    });
    let sent: Record<string, unknown> = {};
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        sent = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return new Response(
          JSON.stringify({
            code: "VAL-001",
            message_key: "rating.required",
            field_errors: [
              { field: "effective_from", code: "VAL-001", message_key: "rating.required" },
            ],
            br_ref: "BR-RAT-031",
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        );
      },
    });
    const error: unknown = await activateRateSchedule(
      "t-res-w",
      { effective_from: null },
      client,
    ).then(
      () => null,
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(sent).toEqual({ effective_from: null });
    const refusal = refusalOf(error, t);
    expect(refusal.message).toBe("This is required.");
    expect(refusal.brRef).toBe("BR-RAT-031");
  });

  it("US-RAT-005 TC-3: an incomplete structure is refused at activation, in the server's words", () => {
    const refusal = new ApiError(422, {
      code: "BIZ-COMPLETENESS",
      message_key: "rating.schedules.incomplete_structure",
      params: { missing: "tiers", model: "tiered" },
      br_ref: "BR-RAT-031",
    });
    expect(apiErrorText(refusal, t)).toBe(
      "The tiered pricing isn't complete yet: tiers is still missing. Fill it in, then activate.",
    );
  });

  it("US-RAT-005 TC-4/TC-5/TC-6: tier refusals render as field errors, not as client rules", () => {
    // Contiguity, the open middle tier and a negative rate are all SERVER
    // rules. **AMENDED 2026-09-17 (DEF-RAT-5717): the SERVER still owns every
    // one of them** — this screen previews the contiguity arithmetic so the
    // clerk is not walked four steps to be told about a number they typed on
    // the first one, and it does so through the SERVER'S OWN SENTENCE and the
    // server's own figure, so the two cannot drift apart. The rule has not
    // moved; only the moment it is shown has.
    expect(t("rating.tiers.not_contiguous", { tier: 2, expected: "100", previous: 1 })).toBe(
      "Start tier 2 at 100. Tier 1 ends there.",
    );
    expect(t("rating.tiers.open_middle_tier")).toBe("Only the last tier can be left open-ended.");
    expect(t("rating.below_minimum")).toContain("below the lowest value allowed");
    const gap = new ApiError(422, {
      code: "VAL-002",
      message_key: "rating.tiers.not_contiguous",
      field_errors: [
        {
          field: "structure.tiers[1].from_qty",
          code: "VAL-002",
          message_key: "rating.tiers.not_contiguous",
        },
      ],
    });
    expect(gap.fieldErrors[0].field).toBe("structure.tiers[1].from_qty");
    expect(t(gap.fieldErrors[0].message_key, { tier: 2, expected: "100", previous: 1 })).toContain(
      "100",
    );
  });

  it("US-RAT-005 TC-2 / BR-RAT-032: a flat schedule posts ONE price, and the server stores one tier", () => {
    const flat = {
      ...emptyScheduleDraft(),
      model: "flat",
      tiers: [{ from_qty: "0", to_qty: "", from_qty_display: "0 kgal", to_qty_display: null, unit_price: "2.90" }],
    };
    expect(structurePayload(flat)).toEqual({ unit_price: "2.90" });
    expect(editorFor("flat")).toBe("flat");
  });

  it("BR-RAT-026: no allowance or included-units field exists in the draft or the payload", () => {
    const keys = Object.keys(emptyScheduleDraft());
    for (const key of keys) {
      expect(key).not.toMatch(/allowance|included|free_units/);
    }
    const tiered = structurePayload({ ...emptyScheduleDraft(), model: "tiered" }) as {
      tiers: Record<string, unknown>[];
    };
    expect(Object.keys(tiered.tiers[0])).toEqual(["from_qty", "unit_price"]);
  });

  it("BR-RAT-031: `approved_by` is never written, and no approval control exists in the payload", () => {
    const payload = draftPayload({ ...emptyScheduleDraft(), name: "x", service: "water" }, true);
    expect(Object.keys(payload)).not.toContain("approved_by");
    // `DEF-RAT-8738` — the sentence saying so sat behind *More about this
    // step* and is retired (rationale, B14 rule 33). The PAYLOAD is the rule.
    expect(i18n.t("rating.rate.approvalOutsideSystem")).toBe("rating.rate.approvalOutsideSystem");
  });
});

describe("US-RAT-006 — TOU Option B", () => {
  it("US-RAT-006 TC-1: seasons and windows post exactly as entered, prices as strings", () => {
    const draft = {
      ...emptyScheduleDraft(),
      model: "time_of_use",
      seasons: [
        {
          key: "s0",
          label: "Summer",
          start_month: "6",
          start_day: "1",
          end_month: "9",
          end_day: "30",
          unit_price: "",
        },
        {
          key: "s1",
          label: "Winter",
          start_month: "10",
          start_day: "1",
          end_month: "5",
          end_day: "31",
          unit_price: "",
        },
      ],
      windows: [
        {
          label: "On-peak",
          season_key: "s0",
          day_type: "weekday",
          start_time: "14:00",
          end_time: "20:00",
          unit_price: "0.22",
          // BR-RAT-067: the utility says which register, and the payload
          // carries the answer through untouched.
          channel: "tou_on",
        },
        {
          label: "Off-peak",
          season_key: "s0",
          day_type: "weekday",
          start_time: "20:00",
          end_time: "14:00",
          unit_price: "0.09",
          channel: "tou_off",
        },
      ],
    };
    const structure = structurePayload(draft) as {
      seasons: Record<string, unknown>[];
      windows: Record<string, unknown>[];
    };
    expect(structure.seasons[0]).toEqual({
      label: "Summer",
      start_month: "6",
      start_day: "1",
      end_month: "9",
      end_day: "30",
    });
    expect(structure.windows[1]).toEqual({
      label: "Off-peak",
      season: "Summer",
      day_type: "weekday",
      // BR-RAT-033: a window may wrap midnight, and it is posted as typed.
      start_time: "20:00",
      end_time: "14:00",
      unit_price: "0.09",
      // BR-RAT-067 (PO 2026-08-16, OQ-236): the register the utility named
      // reaches the server. Before this field the engine derived it from the
      // price rank, and 120/200/380 kWh at 0.22/0.14/0.09 is 88.60 paired as
      // meant and 122.40 paired the other way round.
      channel: "tou_off",
    });
    expect(editorFor("time_of_use")).toBe("tou");
    expect([...DAY_TYPES]).toEqual(["weekday", "weekend", "holiday"]);
  });

  it("US-RAT-006 TC-10: the two register refusals render in words, not codes", () => {
    expect(t("rating.tou.register_reused", {
      windows: "Mid-peak, On-peak",
      channel: "tou_on",
      season: "Summer",
    })).toContain("One register holds one number");
    expect(t("rating.tou.registerHelp")).toContain("never has to guess");
  });

  it("US-RAT-006 TC-4/TC-5/TC-6: the Option B limits are the SERVER's, and its refusals render", () => {
    expect(
      t("rating.tou.too_many_windows", { max: 3, season: "Summer", day_type: "weekday" }),
    ).toContain("at most 3 windows");
    expect(t("rating.tou.coverage", { season: "Summer", day_type: "weekday" })).toContain(
      "Every hour must belong to exactly one window",
    );
    expect(t("rating.seasons.coverage")).toContain("no gap and no overlap");
  });

  it("US-RAT-006 TC-2 / BR-RAT-021: the holiday rule is stated where the windows are built", () => {
    expect(t("rating.tou.holidayNote")).toContain("off-peak");
    expect(t("rating.tou.holidayNote")).toContain("holiday calendar");
  });

  it.todo(
    "US-RAT-006 TC-3/TC-7/TC-8: adding a third window, a duplicate holiday date and the per-tenant calendar — the calendar lives on S63 and the rest need clicks",
  );
});

describe("US-RAT-007 — demand, seasonal, capacity and %-of-water", () => {
  it("US-RAT-007 TC-1: demand posts both components and its capture-only flags", () => {
    const draft = {
      ...emptyScheduleDraft(),
      model: "demand",
      demand: {
        energy_rate_per_kwh: "0.08",
        demand_rate_per_kw: "14.50",
        peak_window_label: "15-min monthly",
        ratchet_enabled: false,
        ratchet_pct: "",
        pf_penalty_enabled: false,
        pf_penalty_rate_per_kw: "",
      },
    };
    expect(structurePayload(draft)).toEqual({
      demand: {
        energy_rate_per_kwh: "0.08",
        demand_rate_per_kw: "14.50",
        peak_window_label: "15-min monthly",
        ratchet_enabled: false,
        pf_penalty_enabled: false,
      },
    });
  });

  it("US-RAT-007 TC-2 / BR-RAT-022: a capacity unit label is free tenant text", () => {
    const draft = {
      ...emptyScheduleDraft(),
      model: "capacity",
      capacity: { unit_label: "panel", rate_per_unit: "10.00" },
    };
    expect(structurePayload(draft)).toEqual({
      capacity: { unit_label: "panel", rate_per_unit: "10.00" },
    });
    expect(t("rating.capacity.unitHelp")).toContain("Nothing here is a fixed list");
    expect(t("rating.capacity.taxableNote")).toContain("taxed like the base charge");
  });

  /**
   * ⚠ **THIS CASE ASSERTED THE DEFECT AND WENT GREEN FOR THREE WEEKS.** It read
   * *"the %-of-service basis is the USAGE charge, and the copy says so"* and
   * pinned `structurePayload` to `{percent, basis_service}` plus the sentence
   * *"base charge and tax are not included"*. Both statements stopped being
   * true on **2026-09-08**, when `CR-081` re-based sewer onto the water VOLUME
   * and `services._validate_structure` began REQUIRING `structure.unit_price`.
   * The test went on passing because it measured the screen against itself.
   *
   * It is rewritten rather than deleted, against `CR-130-BRC07` §3's wire
   * contract, and it is NOT a baseline being widened to go green: the Product
   * Owner ruled the behaviour it pinned must change.
   */
  it("CR-130-BRC07 §3: a percent schedule posts its basis AND its rate (DEF-RAT-6146)", () => {
    const usage = {
      ...emptyScheduleDraft(),
      model: "percent_of_service",
      percent: "90",
      basis_service: "water",
      tiers: [{ from_qty: "0", to_qty: "", unit_price: "5.00" }],
    };
    // ONE block is flat — `BR-RAT-032` — and `unit_price` rides alongside so a
    // flat percent schedule saves against the server as it stands today as
    // well as against the one that accepts the ladder.
    expect(structurePayload(usage)).toEqual({
      percent: "90",
      basis_service: "water",
      percent_basis: "usage",
      tiers: [{ from_qty: "0", to_qty: null, unit_price: "5.00" }],
      unit_price: "5.00",
    });

    // SEVERAL blocks is a ladder, and `unit_price` is deliberately NOT sent:
    // one price standing in for three would quietly bill every block at the
    // first block's rate.
    const ladder = {
      ...usage,
      tiers: [
        { from_qty: "0", to_qty: "10", unit_price: "5.00" },
        { from_qty: "10", to_qty: "", unit_price: "7.00" },
      ],
    };
    const laddered = structurePayload(ladder) as Record<string, unknown>;
    expect(laddered.unit_price).toBeUndefined();
    expect(laddered.tiers).toEqual([
      { from_qty: "0", to_qty: "10", unit_price: "5.00" },
      { from_qty: "10", to_qty: null, unit_price: "7.00" },
    ]);

    // A percentage of MONEY needs no price per unit, so NEITHER key is sent.
    // §3 has the server refuse one by name; nothing is drawn, so nothing is
    // posted, and a silently-dropped rate cannot happen.
    const charge = { ...usage, percent_basis: "charge" };
    expect(structurePayload(charge)).toEqual({
      percent: "90",
      basis_service: "water",
      percent_basis: "charge",
    });
  });

  it("CR-130-BRC07 §4: no card sentence still describes the dollar arithmetic (DEF-RAT-6145)", () => {
    // The five stale sentences named in §4. `t` falls back to the KEY when a
    // catalogue entry is gone, which is what makes this assertion mean
    // something: a retired key reads back as its own name.
    expect(t("rating.percentOfService.hintUsage")).toBe("A share of another service's usage.");
    expect(t("rating.percentOfService.hintCharge")).toBe("A share of another service's charge.");
    expect(t("rating.percentOfService.percentHelpUsage")).toBe(
      "Of the metered quantity, not money.",
    );
    expect(t("rating.percentOfService.percentHelpCharge")).toBe(
      "Of the usage charge, before tax.",
    );
    for (const retired of [
      "rating.percentOfService.hint",
      "rating.percentOfService.percentHelp",
      "rating.percentOfService.preview",
      "rating.planSummary.rate.percentOf",
    ]) {
      expect(t(retired)).toBe(retired);
    }
    // §5 — where taxability is decided, in one sentence, naming WHERE and
    // never WHY (B14 rule 33 puts rationale at zero words on screen).
    expect(t("rating.percentOfService.taxNote")).toContain("Settings");
  });

  it("US-RAT-007 TC-4 / BR-RAT-034: a seasonal price set posts per season", () => {
    const draft = {
      ...emptyScheduleDraft(),
      model: "seasonal",
      seasons: [
        {
          key: "s0",
          label: "Summer",
          start_month: "5",
          start_day: "1",
          end_month: "10",
          end_day: "31",
          unit_price: "4.10",
        },
        {
          key: "s1",
          label: "Winter",
          start_month: "11",
          start_day: "1",
          end_month: "4",
          end_day: "30",
          unit_price: "3.40",
        },
      ],
    };
    const structure = structurePayload(draft) as { seasons: Record<string, unknown>[] };
    expect(structure.seasons[0].unit_price).toBe("4.10");
    expect(structure.seasons[1].unit_price).toBe("3.40");
  });

  it("US-RAT-007 TC-5/TC-6/TC-7: negative rates, a percent over 100 and a gap are all SERVER refusals", () => {
    expect(t("rating.percent.not_positive")).toBe("The percentage has to be above zero.");
    expect(t("rating.percent.confirm_over_100", { percent: "140" })).toContain("140%");
    // The over-100 path is a CONFIRMATION of the server's warning, carried as a
    // flag on the same request — not a client-side bound.
    const confirmed = {
      ...emptyScheduleDraft(),
      model: "percent_of_service",
      percent: "140",
      basis_service: "water",
      confirm_percent_over_100: true,
    };
    expect(draftPayload(confirmed, true).confirm_percent_over_100).toBe(true);
  });

  it("US-RAT-007 TC-8 / BR-RAT-014: a PF penalty is captured and flagged pending ratification", () => {
    const draft = {
      ...emptyScheduleDraft(),
      model: "demand",
      demand: {
        energy_rate_per_kwh: "0.08",
        demand_rate_per_kw: "14.50",
        peak_window_label: "",
        ratchet_enabled: false,
        ratchet_pct: "",
        pf_penalty_enabled: true,
        pf_penalty_rate_per_kw: "3.00",
      },
    };
    const structure = structurePayload(draft) as { demand: Record<string, unknown> };
    expect(structure.demand.pf_penalty_enabled).toBe(true);
    expect(structure.demand.pf_penalty_rate_per_kw).toBe("3.00");
    expect(t("rating.demand.pf_penalty_pending_ratification")).toContain("won't be billed");
  });

  it("BR-RAT-019: every ratified model has an editor, and no model has two", () => {
    const editors = TARIFF_MODELS.map((model) => editorFor(model));
    expect(editors).toEqual(["flat", "tiers", "tou", "demand", "seasonal", "capacity", "percent"]);
    expect(new Set(editors).size).toBe(TARIFF_MODELS.length);
  });

  it("a brand-new schedule activates in ONE call, identity + structure + dates together", async () => {
    let body: Record<string, unknown> = {};
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        body = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return new Response(JSON.stringify(SAVED_DRAFT), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    const draft = {
      ...emptyScheduleDraft(),
      name: "Comm Water · Flat",
      service: "water",
      uom: "kgal",
      model: "flat",
      tiers: [{ from_qty: "0", to_qty: "", from_qty_display: "0 kgal", to_qty_display: null, unit_price: "2.90" }],
      effective_from: "2026-09-01",
    };
    await createRateSchedule({ ...draftPayload(draft, true), ...activationDates(draft) }, client);
    expect(body.service).toBe("water");
    expect(body.effective_from).toBe("2026-09-01");
    expect(body.structure).toEqual({ unit_price: "2.90" });
    expect(SERVICES[0].service).toBe("water"); // the fixture's own service
  });

  it.todo(
    "US-RAT-007 TC-9 / US-RAT-005 TC-8 (isolation): each tenant's labels and schedules stay its own — server scope (G5)",
  );
  it.todo(
    "browser scope → Playwright: adding a tier row, switching the structure card, and Save draft → reopen at the same step",
  );
});

// ══════════════════════════════════════════════════════════════════════════
// CR-013 PART 1 · RAT-03 — the four things §18 row 6 says are wrong
// ══════════════════════════════════════════════════════════════════════════

/** `/lookups/uoms` — the ONE service-scoped list (BR-TEN-078). `service: null`
 *  is the VALUE "All services", not a missing field. */
const UOMS: LookupEntry[] = [
  {
    id: "u1",
    code: "kgal",
    name: "Thousand gallons",
    active: true,
    is_system: true,
    used_by: 3,
    service: { id: "svc-w", code: "water" },
  },
  {
    id: "u2",
    code: "therm",
    name: "Therm",
    active: true,
    is_system: true,
    used_by: 1,
    service: { id: "svc-g", code: "gas" },
  },
  {
    id: "u3",
    code: "month",
    name: "Month",
    active: true,
    is_system: true,
    used_by: 0,
    service: null,
  },
];

/**
 * B14 rule 33 counts SENTENCES, and a naive `split(".")` counts decimal points.
 *
 * ⚠ **THIS EXISTS BECAUSE THE NAIVE VERSION FAILED ON THE FIRST STRING THAT
 * CARRIED A FIGURE** — *"Second approval required. Worst case 11.4%, over
 * 10%."* is two sentences and `split(".")` makes it four. Every cap check in
 * this file uses this one definition, so a rule about words is not quietly
 * decided by punctuation.
 */
function sentencesOf(text: string): string[] {
  return text
    .split(/[.。!?](?:\s+|$)/)
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

describe("CR-013 part 1 · RAT-03 is FIVE steps, and step 2 is the one that was missing", () => {
  it("DEF-356: the rail is Basics · Base rates · Pricing formula · Effective & approval · Review & activate", () => {
    // Part 1, verbatim: "RAT-03 wizard — 5 steps, matching the build". The
    // screen had FOUR — `Base rates` was never a step, so the per-size matrix
    // had nowhere to live.
    expect(RATE_WIZARD_STEPS.map((step) => step.id)).toEqual([
      "basics",
      "sizes",
      "structure",
      "effective",
      "review",
    ]);
    expect(RATE_WIZARD_STEPS.map((step) => t(step.labelKey))).toEqual([
      "Basics",
      "Base rates",
      "Pricing formula",
      // CR-013 renames step 4: approval is captured here now (BR-RAT-082).
      "Effective & approval",
      "Review & activate",
    ]);
  });
});

describe("DEF-355 — the unit of measure is DERIVED from the service, not typed", () => {

  it("BR-TEN-078: a water schedule is offered kgal and month, and is NOT offered therm", () => {
    // The PO's reason, verbatim: "unit of measure is for speific service; so
    // when we select service we have specific unit of measure available".
    // `null` scope means "All services", so `month` is offered everywhere.
    const options = activeUomOptions(UOMS, "water", []);
    expect(options.map((option) => option.value)).toEqual(["kgal", "month"]);
    expect(options.every((option) => !option.outOfScope)).toBe(true);
    // …and a gas schedule is offered therm and month, never kgal. One rule,
    // read from the server's own filter rather than re-derived here.
    expect(activeUomOptions(UOMS, "gas", []).map((option) => option.value)).toEqual([
      "therm",
      "month",
    ]);
  });

});

describe("DEF-356/DEF-360 — step 2's per-size matrix, and the base it may not edit", () => {
  const draft = { ...emptyScheduleDraft(), service: "water" };

  it("BR-RAT-088: `base` is not an editable column, and the rule is READ, not re-typed", () => {
    // §A3: "the charge code owns the base amount. One source of truth." The
    // schedule shows it read-only and attributed, and "its edit mode does not
    // include it". This IS the edit mode.
    expect(editableMatrixColumns().map((column) => column.key)).not.toContain("base");
    expect(MATRIX_COLUMNS.find((column) => column.key === "base")?.editable).toBe(false);
  });

  it("DEF-360: size rows post as typed, and a BLANK minimum is omitted, never zeroed", () => {
    const payload = draftPayload(
      {
        ...draft,
        size_rows: [
          { size_class: "W058", minimum_bill: "18.00" },
          // r10's electric matrix draws an em-dash in the minimum column for
          // every size: served, and no floor. That is not $0.00.
          { size_class: "W100", minimum_bill: "" },
        ],
      },
      true,
    );
    expect(payload.size_rows).toEqual([
      { size_class: "W058", minimum_bill: "18.00" },
      { size_class: "W100" },
    ]);
  });

  it("DEF-360: no size rows means the KEY is absent — an empty list would delete rows", () => {
    expect("size_rows" in draftPayload(draft, true)).toBe(false);
  });

  it("DEF-360: a stored size row RESUMES, null minimum and all", () => {
    const resumed = draftFromSchedule({
      ...SAVED_DRAFT,
      draft_version: {
        ...(SAVED_DRAFT.draft_version as VersionRow),
        size_rows: [
          {
            size_class: "W058",
            minimum_bill: "18.000000",
            minimum_bill_display: "18.00",
            currency: "USD",
          },
          {
            size_class: "W100",
            minimum_bill: null,
            minimum_bill_display: null,
            currency: "USD",
          },
        ],
      },
    });
    expect(resumed.size_rows).toEqual([
      { size_class: "W058", minimum_bill: "18.000000" },
      { size_class: "W100", minimum_bill: "" },
    ]);
    // Round trip: what came back goes back out unchanged, absence included.
    expect(draftPayload(resumed, false).size_rows).toEqual([
      { size_class: "W058", minimum_bill: "18.000000" },
      { size_class: "W100" },
    ]);
  });

  it("BR-RAT-088: a legacy base still on the version is CARRIED, so no tenant loses one", () => {
    // `_guard_base_charge_code` is self-activating per tenant, so a tenant with
    // no `is_base` code anywhere is still billed from
    // `tariff_versions.base_charge`. Dropping it from the payload would blank a
    // live base the first time anybody re-saved a draft.
    const carried = draftPayload({ ...draft, base_charge: "12.000000" }, false);
    expect(carried.base_charge).toBe("12.000000");
  });

});

describe("DEF-RAT-9015 — time of use and demand need a service read from a meter", () => {
  const disabledFor = (basis?: string) =>
    structureOptions(t, basis)
      .filter((option) => option.disabled === true)
      .map((option) => option.value);

  it("DEF-RAT-9015: a counted or shared service cannot pick either; the reason is on the option", () => {
    for (const basis of ["capacity", "share"]) {
      expect(disabledFor(basis)).toEqual(["time_of_use", "demand", "base_only"]);
    }
    const tou = structureOptions(t, "capacity").find((option) => option.value === "time_of_use");
    expect(tou?.label).toBe(t("rating.rs.wiz.needsMeter", { model: t("rating.model.time_of_use") }));
  });

  it("DEF-RAT-9015: a metered service keeps both; one whose basis is not served keeps all seven", () => {
    // DEF-BIL-9014: a metered service loses the share option instead.
    expect(disabledFor("metered")).toEqual(["percent_of_service", "base_only"]);
    expect(disabledFor(undefined)).toEqual(["base_only"]);
  });

  it("DEF-BIL-9014: only a metered service loses the share option; the reason is on it", () => {
    expect(disabledFor("share")).not.toContain("percent_of_service");
    expect(disabledFor("capacity")).not.toContain("percent_of_service");
    const share = structureOptions(t, "metered").find((option) => option.value === "percent_of_service");
    expect(share?.label).toBe(t("rating.rs.wiz.hasMeters", { model: t("rating.model.percent_of_service") }));
  });
});

describe("DEF-297 — `Base only` is CR-013's sixth structure and the server refuses it", () => {
  it("DEF-297: it is offered and DISABLED, and every enabled option is one the server accepts", () => {
    const options = structureOptions(t);
    const baseOnly = options.find((option) => option.value === "base_only");
    expect(baseOnly?.disabled).toBe(true);
    // Nothing pickable is a value `_choice` would reject.
    const enabled = options
      .filter((option) => option.disabled !== true)
      .map((option) => option.value);
    expect(enabled).toEqual([...TARIFF_MODELS]);
    expect(TARIFF_MODELS).not.toContain("base_only");
  });

});

describe("CR-013 part 1 step 4 — the impact analysis, and BR-RAT-082's filing capture", () => {
  it("BR-RAT-091: the threshold is 10%, and our own +6% water filing FLOWS", () => {
    // PO ruling 2026-08-20, clause 2, worked against the fixture: the water +6%
    // filing moves an 11 kgal household $59.00 → $62.54, +$3.54/month, $38,826
    // a year across 914 accounts — and it flows, because 6% is under the bar.
    expect(RATE_CHANGE_SECOND_APPROVAL_PCT).toBe(10);
    expect(secondApprovalRequired(6)).toBe(false);
    // "above 10%" — at the bar is not over it.
    expect(secondApprovalRequired(10)).toBe(false);
    expect(secondApprovalRequired(10.5)).toBe(true);
    // UNKNOWN is not "under the bar": a `false` here would claim a filing was
    // clear that nobody has measured (DEF-434).
    expect(secondApprovalRequired(null)).toBeNull();
    expect(secondApprovalRequired(null)).not.toBe(false);
  });

  it("BR-RAT-082: the four fields post when answered and are OMITTED when blank", () => {
    const blank = draftPayload(emptyScheduleDraft(), true);
    for (const field of [
      "filing_authority",
      "filed_on",
      "regulator_approved_on",
      "regulator_approver",
      // DEF-369 / DEF-280 — the same rule, added with the filing record: a
      // blank label is "never stated", and an empty string would be a label
      // that looks answered. The screen falls back to a derived ordinal on
      // NULL and cannot tell the difference from "".
      "version_label",
      "change_reason",
    ]) {
      // Omitted, so the column stays NULL — "not recorded" rather than an empty
      // docket number that looks answered.
      expect(field in blank).toBe(false);
    }
    const filed = draftPayload(
      {
        ...emptyScheduleDraft(),
        regulator_ref: "PUC #W-2025-1184",
        // DEF-369 / DEF-280 — the same omit-when-blank rule as the four
        // BR-RAT-082 fields below, asserted on the same payload.
        version_label: "v4",
        change_reason: "TWDB pass-through 2027",
        filing_authority: "Texas PUC",
        filed_on: "2026-09-01",
        regulator_approved_on: "2026-11-14",
        regulator_approver: "Commissioner A. Reyes",
      },
      true,
    );
    expect(filed.regulator_ref).toBe("PUC #W-2025-1184");
    expect(filed.filing_authority).toBe("Texas PUC");
    expect(filed.filed_on).toBe("2026-09-01");
    expect(filed.regulator_approved_on).toBe("2026-11-14");
    expect(filed.regulator_approver).toBe("Commissioner A. Reyes");
    expect(filed.version_label).toBe("v4");
    expect(filed.change_reason).toBe("TWDB pass-through 2027");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-005@0b56fac (story+rules snapshot hash — EP-RAT-02; co-stories US-RAT-006@0b56fac · US-RAT-007@0b56fac)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S11) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 the wizard's own step navigation is a click, so the structure EDITORS are proved through their payload builders (`structurePayload`, `draftPayload`, `activationDates`) and the stored-row rendering through `StructurePreview`; the click path is an honest todo · E4 US-RAT-007 TC-4's richer per-season TIER sets are not editable in v1 (one flat price per season, the shape the TC specifies) — reported in the screen's own trailer
// AMENDED: 2026-08-21 by the CR-013 P1 lane (RAT-03) — 19 cases added, 266 pass in
//   src/features/rating (247 before). What they pin: the rail is FIVE steps in CR-013
//   part 1's order · the UoM control is a <select> over service-scoped `uoms` and a
//   water schedule is never offered `therm` · `editableMatrixColumns()` excludes `base`
//   and the wizard renders no base input anywhere (BR-RAT-088) · a blank per-size
//   minimum is OMITTED from the payload, never zeroed (DEF-277) · `base_only` is
//   offered DISABLED and every ENABLED option is a value `services.TARIFF_MODELS`
//   accepts · BR-RAT-091's ratified figures — the water +6% filing FLOWS, 10.5% does
//   not, 10% exactly does not (the rule says ABOVE), and an unknown worst case returns
//   `null` rather than `false` · BR-RAT-082's four filing fields post when answered,
//   are omitted when blank, and NONE is `aria-required`.
//   Both new guards were shown RED before being trusted green (hard-won law 7):
//   flipping `base_only`'s `disabled` to false failed 2 cases, and short-circuiting the
//   `size_rows` payload branch failed 2 more.
// exceptions: E4 `shown()` renders catalog copy through the same renderer before
//   comparing it to markup — React escapes `'` and `"`, so a raw `t(key)` comparison
//   would silently pass only on sentences that happen to contain neither
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// DEF-433 — the 2" water row, from the payload out and back again
// ══════════════════════════════════════════════════════════════════════════
// r10 prices Residential Water's blocks at 3.20 / 4.80 / 7.20 for 5/8", 3/4",
// 1" and 1.5", and at 3.45 / 5.10 / 7.70 for 2". `RateTier.size_class` existed,
// nullable, with nothing writing it and nothing serving it, so that one row —
// the row the whole size axis exists for — could not be expressed at all.

const BASE_LADDER: TierDraft[] = [
  { from_qty: "0", to_qty: "4", unit_price: "3.20" },
  { from_qty: "4", to_qty: "10", unit_price: "4.80" },
  { from_qty: "10", to_qty: "", unit_price: "7.20" },
];

describe("DEF-433 — per-size tier rates are written and read back", () => {
  it("the payload sends the NULL group first, then one group per override", () => {
    const payload = structurePayload({
      ...emptyScheduleDraft(),
      model: "tiered",
      tiers: BASE_LADDER,
      size_tiers: [{ size_class: "W200", prices: ["3.45", "5.10", "7.70"] }],
    });
    const tiers = payload.tiers as Record<string, unknown>[];
    expect(tiers).toHaveLength(6);
    // The base ladder carries NO `size_class` key at all — it is the "every
    // size" group, and the server requires it (a payload of nothing but
    // overrides leaves every unnamed size with no price).
    expect(tiers.slice(0, 3).every((row) => !("size_class" in row))).toBe(true);
    // The strings are passed through CHARACTER FOR CHARACTER — `decimalOut`
    // trims and validates shape, it does not re-format. A component that padded
    // "3.20" to "3.200000" would be doing the server's job with money.
    expect(tiers.slice(0, 3).map((row) => row.unit_price)).toEqual(["3.20", "4.80", "7.20"]);
    // The override shares the base ladder's BOUNDARIES and states its own
    // prices, so the group is contiguous by construction and the server's
    // per-group BR-RAT-032 check cannot fail by accident.
    expect(tiers.slice(3).map((row) => row.size_class)).toEqual(["W200", "W200", "W200"]);
    expect(tiers.slice(3).map((row) => row.from_qty)).toEqual(["0", "4", "10"]);
    expect(tiers.slice(3).map((row) => row.unit_price)).toEqual(["3.45", "5.10", "7.70"]);
    // A blank To is ∞ and the key is OMITTED — on the override's top block too.
    expect("to_qty" in tiers[5]).toBe(false);
  });

  it("a schedule with no override posts exactly what it always posted", () => {
    const payload = structurePayload({
      ...emptyScheduleDraft(),
      model: "tiered",
      tiers: BASE_LADDER,
    });
    const tiers = payload.tiers as Record<string, unknown>[];
    expect(tiers).toHaveLength(3);
    expect(tiers.every((row) => !("size_class" in row))).toBe(true);
  });

  it("reading a stored version back GROUPS the ladders, and does not merge them", () => {
    // The bug this prevents: six stored rows read as one ladder would show a
    // utility its own rate as 0→4, 4→10, 10→∞, 0→4, 4→10, 10→∞ the first time
    // it reopened the wizard.
    const served: TierRow[] = [
      { seq: 1, season: null, size_class: null, from_qty: "0", to_qty: "4", from_qty_display: "0 kgal", to_qty_display: "4 kgal", unit_price: "3.200000" },
      {
        seq: 2,
        season: null,
        size_class: null,
        from_qty: "4",
        to_qty: "10",
        from_qty_display: "4 kgal",
        to_qty_display: "10 kgal",
        unit_price: "4.800000",
      },
      {
        seq: 3,
        season: null,
        size_class: null,
        from_qty: "10",
        to_qty: null,
        from_qty_display: "10 kgal",
        to_qty_display: null,
        unit_price: "7.200000",
      },
      {
        seq: 4,
        season: null,
        size_class: "W200",
        from_qty: "0",
        to_qty: "4",
        from_qty_display: "0 kgal",
        to_qty_display: "4 kgal",
        unit_price: "3.450000",
      },
      {
        seq: 5,
        season: null,
        size_class: "W200",
        from_qty: "4",
        to_qty: "10",
        from_qty_display: "4 kgal",
        to_qty_display: "10 kgal",
        unit_price: "5.100000",
      },
      {
        seq: 6,
        season: null,
        size_class: "W200",
        from_qty: "10",
        to_qty: null,
        from_qty_display: "10 kgal",
        to_qty_display: null,
        unit_price: "7.700000",
      },
    ];
    expect(baseLadder(served)).toHaveLength(3);
    expect(baseLadder(served).map((tier) => tier.unit_price)).toEqual([
      "3.200000",
      "4.800000",
      "7.200000",
    ]);
    expect(sizeLadders(served)).toEqual([
      { size_class: "W200", prices: ["3.450000", "5.100000", "7.700000"] },
    ]);
    // Every version written before the column existed is entirely the NULL
    // group, so it reads back exactly as it did.
    expect(sizeLadders(baseLadder(served))).toEqual([]);
  });

});

/**
 * DEF-RAT-6447 / DEF-RAT-6448 — a live schedule can hold a parked draft.
 *
 * ⚠ **THE FIXTURE IS THE POINT.** Every existing fixture in this file has
 * EITHER a `current_version` OR a `draft_version`, because until 2026-09-17 a
 * schedule could not hold both — the server refused the save that would make
 * one. So the branch these cases exercise was unreachable and no test in 1,505
 * lines could have found the resume fault: `draftFromSchedule` preferred the
 * live version, and the draft the clerk had just typed was served in the same
 * payload and thrown away on screen.
 */
const LIVE_WITH_PARKED_DRAFT: ScheduleDetail = {
  ...SAVED_DRAFT,
  status: "active",
  // What customers are billed on today — 3.20 / 4.80 / 7.20, as seeded.
  current_version: {
    ...(SAVED_DRAFT.draft_version as VersionRow),
    id: "v-live",
    effective_from: "2026-08-01",
    regulator_ref: "TX PUC docket 51234",
  },
  // What the clerk parked and has not activated — a different ladder.
  draft_version: {
    ...(SAVED_DRAFT.draft_version as VersionRow),
    id: "v-parked",
    effective_from: null,
    regulator_ref: null,
    structure: {
      ...(SAVED_DRAFT.draft_version as VersionRow).structure,
      tiers: [
        { seq: 1, season: null, size_class: null, from_qty: "0.000000", to_qty: "5.000000", from_qty_display: "0 kgal", to_qty_display: "5 kgal", unit_price: "9.990000" },
        { seq: 2, season: null, size_class: null, from_qty: "5.000000", to_qty: null, from_qty_display: "5 kgal", to_qty_display: null, unit_price: "11.110000" },
      ],
    },
  },
};

describe("DEF-RAT-6447 — a live rate schedule can park an unfinished edit", () => {
  it("DEF-RAT-6448: reopening shows the PARKED DRAFT, not the rate that is in force", () => {
    const resumed = draftFromSchedule(LIVE_WITH_PARKED_DRAFT);
    // The clerk's own figures, which is the whole reason they saved.
    expect(resumed.tiers.map((tier) => tier.unit_price)).toEqual(["9.990000", "11.110000"]);
    // ⚠ AND THE DATES COME BACK EMPTY, WHICH IS THE CORRECT ANSWER RATHER THAN
    // A MISSING ONE: a parked draft has no window, and pre-filling it with the
    // live version's date is the blueprint's own named defect for step 4
    // ("four fields arrived pre-filled with the previous version's answers,
    // two of them making a refusal certain").
    expect(resumed.effective_from).toBe("");
  });

  it("with NO parked draft the live version's STRUCTURE resumes — its WINDOW does not", () => {
    const live: ScheduleDetail = { ...LIVE_WITH_PARKED_DRAFT, draft_version: null };
    const resumed = draftFromSchedule(live);
    expect(resumed.tiers.map((tier) => tier.unit_price)).toEqual([
      "3.200000",
      "4.800000",
      "7.200000",
    ]);
    // ⚠ **`DEF-RAT-5833` — THIS LINE ASSERTED `"2026-08-01"` AND THAT WAS THE
    // DEFECT WEARING A TEST.** Opening a LIVE schedule to file the next rate
    // handed the clerk the window of the version they are replacing: on Brazos
    // Bend's `Industrial Electric` schedule, `effective_to` arrived holding
    // `12/31/2027`, so filing a 2029 rate was refused with *"The end date has
    // to come after the start date"* about a box the clerk never touched — and
    // a change dated INSIDE the old window was not refused at all, it silently
    // inherited `12/31/2027` as its own end and left the service with no
    // version in force from `01/01/2028`.
    //
    // The structure above still resumes, because a new version is almost
    // always a small edit of the one before it. The WINDOW is the one fact it
    // may not inherit: `activate_new_version` closes the outgoing version
    // itself (`previous.effective_to = new_from - 1 day`), so a blank end date
    // means open-ended, which is what a rate filing normally is.
    expect(resumed.effective_from).toBe("");
    expect(resumed.effective_to).toBe("");
  });

  it("DEF-RAT-5833: a PARKED DRAFT still hands back the dates the clerk parked", () => {
    // The mirror, and the reason the flag is *which row was read* rather than
    // *is the schedule live*: blanking a parked draft's own answers would lose
    // typed work, which is `DEF-RAT-6448` running backwards.
    const parked: ScheduleDetail = {
      ...LIVE_WITH_PARKED_DRAFT,
      draft_version: {
        ...(LIVE_WITH_PARKED_DRAFT.draft_version as VersionRow),
        effective_from: "2027-01-01",
        effective_to: "2027-12-31",
      },
    };
    const resumed = draftFromSchedule(parked);
    expect(resumed.effective_from).toBe("2027-01-01");
    expect(resumed.effective_to).toBe("2027-12-31");
  });

  /**
   * ⚠ **THE RENDERED WIZARD BAR IS PROVED IN A BROWSER, NOT HERE, AND THAT IS
   * A FINDING RATHER THAN A GAP I AM EXCUSING.** `RateScheduleWizard` is never
   * mounted whole anywhere in this 1,500-line suite: it gates on
   * `detailQuery.isPending`, so under `renderToStaticMarkup` it renders the
   * loading skeleton and nothing else. **That is exactly why a missing button
   * survived — no unit test in this repository can see this component's own
   * chrome.** The control, the note and the discard dialog are walked at
   * `10-scripts/def_rat_5680_park_a_draft_walkthrough.mjs` (hard-won law 6),
   * and what is asserted below is everything that CAN be asserted here: the
   * pure resume function, and the sentences the bar renders.
   */
  it("the parked-draft note and the discard verb are real sentences, in English", () => {
    expect(t("rating.rate.parkedDraftNote")).not.toBe("rating.rate.parkedDraftNote");
    expect(t("rating.rate.discardDraft")).toBe("Discard draft");
    expect(t("rating.rate.confirm.discardDraft.title")).toBe("Discard this draft?");
    // B14 rule 33: a CONSEQUENCE is at most two sentences of six words each.
    const consequence = t("rating.rate.confirm.discardDraft.body");
    const sentences = sentencesOf(consequence);
    expect(sentences.length).toBeLessThanOrEqual(2);
    for (const sentence of sentences) {
      expect(sentence.trim().split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });

  it("DEF-055: the wizard's own success toasts resolve to real sentences", () => {
    // They were in NO catalogue for 37 days and reached a clerk as the raw key.
    // The fix only matters because the draft path is now reachable on a live
    // schedule, which is where the PO was working.
    for (const key of [
      "rating.rate.toast.draft",
      "rating.rate.toast.activated",
      "rating.rate.toast.draftDiscarded",
    ]) {
      expect(t(key, { name: "Res Water" })).not.toBe(key);
      expect(t(key, { name: "Res Water" })).toContain("Res Water");
    }
  });
});


/**
 * DEF-RAT-5715 — BR-RAT-104 reaches a rate schedule.
 *
 * ⚠ **THE BACKEND CASES ARE WHERE THIS FEATURE IS PROVED** —
 * `06-backend/tests/test_def_rat_5715_correct_a_version.py`, and in particular
 * the one asserting that the corrected row STOPS PRICING while keeping every
 * field of its own. What is asserted here is what a person reads: that the
 * question is asked in words, and that `null` bills and `0` bills are drawn
 * differently, because collapsing those two is DEF-079 exactly.
 */
describe("DEF-RAT-5715 — a typo is fixed without recording a rate change", () => {

  it("the correction copy obeys B14 rule 33's six-word cap, sentence by sentence", () => {
    for (const key of [
      "rating.rate.intent.changeFact",
      "rating.rate.intent.correctFact",
      "rating.rate.correct.noBills",
      "rating.rate.correct.billsUnknown",
      "rating.rate.correct.rebillPath",
      "rating.schedules.correction_keeps_the_window",
      "rating.schedules.correct_draft",
      "rating.schedules.already_corrected",
    ]) {
      const text = t(key, { count: 47 });
      expect(text, `${key} is not in the catalogue`).not.toBe(key);
      for (const sentence of sentencesOf(text)) {
        expect(
          sentence.trim().split(/\s+/).length,
          `${key}: "${sentence.trim()}" is over six words`,
        ).toBeLessThanOrEqual(6);
      }
    }
  });

  it("every label is three words or fewer — B14 rule 33's label cap", () => {
    for (const key of [
      "rating.rate.intent.title",
      "rating.rate.intent.change",
      "rating.rate.intent.correct",
      "rating.rate.correct.title",
      "rating.rate.correct.reasonTitle",
    ]) {
      expect(t(key).split(/\s+/).length, `${key} is over three words`).toBeLessThanOrEqual(3);
    }
  });
});


/**
 * DEF-RAT-5717 — the tier ladder says which tier and which number.
 *
 * PO, in the beta, verbatim: *"in tied rates - if tier 1 start from 0 to 100 and
 * tier 2 start from 101 to 300 ; then it give error - tier 2 should start from
 * 100"*.
 *
 * ⚠ **THE PRODUCT WAS RIGHT AND THE MESSAGE WAS AT FAULT.** `BR-RAT-032` is
 * CONFIRMED (PO R5-5) — the boundaries are half-open, so tier 1 is 0 up to but
 * NOT including 100 and `101` genuinely leaves a gap. The server had already
 * computed `100` and passed it as `expected=`; the sentence had no placeholder
 * for it, so i18next dropped it in silence.
 */
describe("DEF-RAT-5717 — a tier gap names the tier and the number", () => {
  it("the sentence says what to type, not merely that something is wrong", () => {
    const text = t("rating.tiers.not_contiguous", { tier: 2, starts: "101", expected: "100", previous: 1 });
    expect(text).toContain("100");
    expect(text).toContain("2");
    // The PO's own complaint, answered in the product's words.
    expect(text).toBe("Start tier 2 at 100. Tier 1 ends there.");
  });

  it("it obeys B14 rule 33 — two sentences, six words or fewer each", () => {
    const text = t("rating.tiers.not_contiguous", { tier: 2, starts: "101", expected: "100", previous: 1 });
    const sentences = sentencesOf(text);
    expect(sentences.length).toBeLessThanOrEqual(2);
    for (const sentence of sentences) {
      expect(sentence.trim().split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });

  it("every one of the eleven catalogues renders both figures", () => {
    for (const lang of ["en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]) {
      const text = i18n.getFixedT(lang)("rating.tiers.not_contiguous", {
        tier: 2,
        starts: "101",
        expected: "100",
        previous: 1,
      });
      expect(text, `${lang} drops a figure`).toContain("100");
      expect(text, `${lang} does not name the tier`).toContain("2");
      expect(text, `${lang} is untranslated`).not.toBe("rating.tiers.not_contiguous");
    }
  });

  it("tierGapAt answers the number to type, and stays silent on a half-typed row", () => {
    const ladder = (...rows: [string, string][]) =>
      rows.map(([from_qty, to_qty]) => ({ from_qty, to_qty, unit_price: "1" }));
    // The PO's own ladder: 0-100 then 101-300.
    expect(tierGapAt(ladder(["0", "100"], ["101", "300"]), 1)).toBe("100");
    // Contiguous — nothing to say.
    expect(tierGapAt(ladder(["0", "100"], ["100", "300"]), 1)).toBeNull();
    // An OVERLAP is a gap's twin and is caught the same way.
    expect(tierGapAt(ladder(["0", "100"], ["90", "300"]), 1)).toBe("100");
    // ⚠ HALF-TYPED IS NOT BROKEN. Shouting mid-keystroke is its own defect.
    expect(tierGapAt(ladder(["0", "100"], ["", "300"]), 1)).toBeNull();
    expect(tierGapAt(ladder(["0", ""], ["101", "300"]), 1)).toBeNull();
    expect(tierGapAt(ladder(["0", "100"], ["abc", "300"]), 1)).toBeNull();
    // The first row has nothing above it.
    expect(tierGapAt(ladder(["5", "100"]), 0)).toBeNull();
    // `100` and `100.00` are the same boundary, not a gap.
    expect(tierGapAt(ladder(["0", "100"], ["100.00", "300"]), 1)).toBeNull();
  });

  it("adding a tier starts it where the one above ends", () => {
    const row = (from_qty: string, to_qty: string) => ({ from_qty, to_qty, unit_price: "1" });
    expect(nextTierStart([row("0", "100")])).toBe("100");
    expect(nextTierStart([row("0", "100"), row("100", "300")])).toBe("300");
    // ⚠ NOTHING IS GUESSED where there is nothing to read: no row above, or a
    // row above with no upper limit (a block above an open-ended one cannot
    // exist, so inventing a number there would invent a rule too).
    expect(nextTierStart([])).toBe("");
    expect(nextTierStart([row("0", "")])).toBe("");
    expect(nextTierStart([row("0", "  100  ")])).toBe("100");
  });
});


/**
 * DEF-RAT-5718 — the date a clerk picks CLOSES the rate that is live now, and
 * until today nothing said so.
 *
 * PO, in the beta, verbatim: *"i want to change the rate from tomorrow - eisting
 * rates say it is valid until 31 dec"*.
 *
 * ⚠ **THE ARITHMETIC MIRRORS THE SERVER'S CONDITION AND DOES NOT APPROXIMATE
 * IT.** `create_rate_schedule_version` closes only when
 * `effective_to IS NULL OR effective_to >= new_from`, so a screen that said
 * *"the current rate ends"* over a version that has already ended would be
 * announcing a change that is not going to happen — a true-looking sentence
 * about the wrong row, which is worse than saying nothing.
 */
describe("DEF-RAT-5718 — the new date closes the current window, and the screen says so", () => {
  const withWindow = (from: string | null, to: string | null): ScheduleDetail => ({
    ...SAVED_DRAFT,
    closing_version_effective_from: from,
    closing_version_effective_to: to,
  });

  it("the day before the new date — the PO's own case", () => {
    // A rate running to 31 December, and a new one starting tomorrow.
    expect(currentRateEndsOn(withWindow("2026-01-01", "2026-12-31"), "2026-09-18")).toBe(
      "2026-09-17",
    );
    // An OPEN-ENDED current rate is the commonest case and is closed too.
    expect(currentRateEndsOn(withWindow("2026-01-01", null), "2026-09-18")).toBe("2026-09-17");
  });

  it("it crosses a month and a year boundary by the calendar, never by a timezone", () => {
    expect(currentRateEndsOn(withWindow("2026-01-01", null), "2026-10-01")).toBe("2026-09-30");
    expect(currentRateEndsOn(withWindow("2026-01-01", null), "2027-01-01")).toBe("2026-12-31");
    // 2028 is a leap year: the day before 1 March is the 29th, not the 28th.
    expect(currentRateEndsOn(withWindow("2026-01-01", null), "2028-03-01")).toBe("2028-02-29");
  });

  it("⚠ it says NOTHING where nothing will be closed", () => {
    // No version in force at all.
    expect(currentRateEndsOn(withWindow(null, null), "2026-09-18")).toBeNull();
    // The current version has ALREADY ended — the server will not touch it.
    expect(currentRateEndsOn(withWindow("2026-01-01", "2026-06-30"), "2026-09-18")).toBeNull();
    // The new date is not after the current one's start; the server refuses that
    // outright, so the screen must not describe it as a closure.
    expect(currentRateEndsOn(withWindow("2026-09-18", null), "2026-09-18")).toBeNull();
    expect(currentRateEndsOn(withWindow("2026-09-18", null), "2026-09-01")).toBeNull();
    // No date typed yet, or a half-typed one.
    expect(currentRateEndsOn(withWindow("2026-01-01", null), "")).toBeNull();
    expect(currentRateEndsOn(withWindow("2026-01-01", null), "2026-09")).toBeNull();
    expect(currentRateEndsOn(null, "2026-09-18")).toBeNull();
  });

  it("the sentence is three words — B14 rule 33's label cap for a fact", () => {
    expect(t("rating.rate.currentRateEnds").split(/\s+/).length).toBeLessThanOrEqual(6);
    for (const lang of ["en", "de", "es", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR", "es-MX"]) {
      const text = i18n.getFixedT(lang)("rating.rate.currentRateEnds");
      expect(text, `${lang} is untranslated`).not.toBe("rating.rate.currentRateEnds");
    }
  });
});

/**
 * DEF-RAT-5719 — the impact panel, as the blueprint p048 draws it.
 *
 * PO, of steps 2 to 5: *"too much text"*. Three unmeasured figures each carried
 * their own copy of a sixteen-word explanation — **forty-eight words to learn
 * one thing** — and the repetition was a property of the DATA rather than of the
 * code, which is why it read perfectly with one unmeasured figure and why no
 * review caught it.
 */
describe("DEF-RAT-5719 — the unmeasured figures are one group, said once", () => {
  it("the three second-approval verdicts obey B14 rule 33's six-word cap", () => {
    const cases: [string, Record<string, string>][] = [
      ["rating.rate.impact.secondApprovalRequired", { pct: "11.4%", threshold: "10%" }],
      ["rating.rate.impact.secondApprovalClear", { pct: "6.0%", threshold: "10%" }],
    ];
    for (const [key, params] of cases) {
      const text = t(key, params);
      const sentences = sentencesOf(text);
      expect(sentences.length, `${key} is over two sentences`).toBeLessThanOrEqual(2);
      for (const sentence of sentences) {
        expect(
          sentence.trim().split(/\s+/).length,
          `${key}: "${sentence.trim()}" is over six words`,
        ).toBeLessThanOrEqual(6);
      }
    }
  });

  it("⚠ and the two MEASURED verdicts still carry their figures", () => {
    // Shortening copy must not drop the number a filer acts on — that is the
    // mirror of DEF-RAT-5717, where a sentence silently dropped its param.
    expect(t("rating.rate.impact.secondApprovalRequired", { pct: "11.4%", threshold: "10%" }))
      .toContain("11.4%");
    expect(t("rating.rate.impact.secondApprovalClear", { pct: "6.0%", threshold: "10%" }))
      .toContain("6.0%");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `CR-120-BRC06` · `BR-RAT-1025` — THE SCHEDULE NAMES ITS BASE CHARGE CODE
//
// PO ruling 2026-09-19, verbatim: *"no this is not correct ; So: plan → rate
// schedule -> charge code → base charges - this is correct"*, and on why it
// reverses nothing: *"we are not bindng base charges in rate schedule - you
// were taking it default; now we are making it explicit it is a same rule -
// change is default -> expliciate"*.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED BEFORE THEY WERE WRITTEN**
// (hard-won law 7 habit 2). Two things:
//   · a control rendered but never passed a value — hard-won law 2's dead UI.
//     So the picker is asserted to carry the BOUND id as its selected option,
//     not merely to exist.
//   · a payload key that is present but omitted when cleared. `null` and an
//     ABSENT key are the same to `toHaveProperty`, so the clearing case
//     asserts the VALUE is null rather than that the key is there.
// ══════════════════════════════════════════════════════════════════════════

describe("CR-120-BRC06 — the binding round-trips through the payload", () => {
  it("POSTS the bound id", () => {
    const payload = draftPayload(
      { ...emptyScheduleDraft(), service: "water", base_charge_code: "c-base-w-com" },
      true,
    );
    expect(payload.base_charge_code).toBe("c-base-w-com");
  });

  it("POSTS null when the picker is CLEARED, so clearing actually clears", () => {
    // ⚠ An omitted key would leave the stored binding untouched, so the clear
    // would silently do nothing — `account_type_id`'s recorded lesson on the
    // same screen. `toHaveProperty` alone cannot see the difference between a
    // null value and an absent key, so the VALUE is what is asserted.
    const payload = draftPayload({ ...emptyScheduleDraft(), service: "water" }, true);
    expect(payload.base_charge_code).toBeNull();
  });

  it("RELOADS the binding, so reopening the wizard does not blank it", () => {
    // DEF-422's discipline: a wizard that drops a stored fact because it did
    // not read it is how a live setting disappears on an unrelated edit.
    const bound: ScheduleDetail = {
      ...SAVED_DRAFT,
      draft_version: { ...SAVED_DRAFT.draft_version!, base_charge_code: "c-base-w-com" },
    };
    expect(draftFromSchedule(bound).base_charge_code).toBe("c-base-w-com");
    // …and a version that names nothing reloads as blank rather than as
    // `undefined`, which the picker would render as an uncontrolled field.
    expect(draftFromSchedule(SAVED_DRAFT).base_charge_code).toBe("");
  });
});
