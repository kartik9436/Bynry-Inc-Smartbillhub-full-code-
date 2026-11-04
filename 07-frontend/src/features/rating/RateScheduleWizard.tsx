// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-005 (basics + flat & tiered, effective dates, review & activate) ·
//           US-RAT-006 (TOU Option B: windows × seasons × day-types) · US-RAT-007
//           (demand, seasonal, capacity and sewer %-of-water) · US-RAT-010 (a change to a
//           live schedule is a NEW version with a required reason) · US-RAT-004 (the S9
//           card grid this wizard returns to)
//           Screens: S11 (entered from S9 Rate schedules, or from S10 step 3)
// Rules:    BR-RAT-019 (the tariff-model set) · BR-RAT-021 (TOU v1 = Option B) ·
//           BR-RAT-022 (capacity unit label + rate are TENANT-defined) · BR-RAT-026 (pure
//           tiers — no allowance field exists) · BR-RAT-031 (one service, one model,
//           internal name; SAVE-DRAFT RESUMABLE; activation requires a complete structure
//           AND effective_from; the board-approval workflow is REMOVED and
//           `approved_by` is optional metadata, never a gate) · BR-RAT-032 (tier
//           contiguity — SERVER-enforced) · BR-RAT-033 (TOU coverage — SERVER-enforced) ·
//           BR-RAT-034 (seasonal coverage — SERVER-enforced) · BR-RAT-037 (in-force
//           versions are never edited in place) · BR-RAT-038 (the UoM gate is stated,
//           never silently converted) · BR-SHL-018/019 · BR-SHL-020 · BR-SHL-033/034
// ───────────────────────────────────────────────────────
// S11 — the rate-schedule builder.
//
// The two laws this screen exists to keep:
//
//   **Save draft round-trips.** BR-RAT-031 makes a draft a real stored version
//   with NO effective date. "Save draft" therefore posts the structure without
//   dates, the server keeps it as the one dateless `tariff_versions` row, and
//   reopening reads it back through `draft_version` — tiers, windows, seasons
//   and all. Nothing about the draft is kept in browser state between visits.
//
//   **The server owns every rule.** Tier contiguity, "only the last tier may be
//   open-ended", 24-hour window coverage, ≤ 3 windows, season coverage, rate
//   ≥ 0, percent > 0, and "activation needs a date" are all validated by the
//   backend, which answers B12 §3 field errors. This file therefore performs
//   NO money validation of its own — Activate is pressable with an empty date
//   precisely so the server's refusal is what the user reads. The only
//   client-side checks are SHAPE (is this text a decimal at all) and PRESENCE
//   (did they type a name), neither of which is a money rule.
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import {
  TARIFF_MODELS,
  getPercentBasisOptions,
} from "@/api/endpoints";
import type {
  RateChangeImpact,
  ScheduleDetail,
  TierRow,
  VersionRow,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { monthLabel } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { RATE_MIN_DISPLAY_DECIMALS } from "@/components/MoneyCell";
import {
  CheckboxField,
  SegmentedField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import {
  Panel,
} from "@/features/tenancy/settingsShared";

import { baseChargeFor } from "./baseCharge";
import { RateScheduleThreeStep } from "./RateScheduleThreeStep";
// ⚠ **DEF-355's SCOPE RULE IS STILL THE SERVER'S AND IS STILL IMPORTED RATHER
// THAN RE-DERIVED — it has simply moved one door along.** `scheduleUomOptions`
// CALLS `SettingsServicesTab.activeUomOptions`, which is
// `selectors.uom_scope_filter` written once on the client and carries
// *"Change one, change both"* in its own docstring. `CR-130-BRC07` §8.3 adds a
// SECOND, screen-only narrowing on top of it — what THIS utility declared it
// measures this service in — and layering keeps the mirror a mirror.
import {
  CELL_NONE,
  MoreAbout,
  PERCENT_BASIS_CHARGE,
  PERCENT_BASIS_KINDS,
  PERCENT_BASIS_USAGE,
  activeSizeClasses,
  decimalOut,
  decimalShapeError,
  MoneyTextField,
} from "./ratingShared";
import type { Translator } from "./ratingShared";


/** The cache key for the base-attribution read. Named because `queryKeys.charges`
 *  takes an opaque query string and two callers with different strings would
 *  fetch the same rows twice. */

// ── The draft (every price is a STRING, start to finish) ───────────────────

export interface TierDraft {
  from_qty: string;
  to_qty: string; // "" on the LAST row means ∞ (BR-RAT-032)
  unit_price: string;
}

export interface SeasonDraft {
  /**
   * **A STABLE DRAFT-ONLY IDENTITY, AND IT IS WHAT MAKES THE NESTING HONEST**
   * (`DEF-RAT-5736`). A window used to name its season by LABEL, which is the
   * one field a clerk retypes: rename *Summer* to *Peak* and every window
   * pointing at it became `rating.tou.unknown_season` at activation. Two
   * unnamed seasons were worse — both labels are `""`, so the two collections
   * were indistinguishable.
   *
   * Minted by `nextSeasonKey`, never typed, never posted. `structurePayload`
   * resolves it back to the label the server's contract expects, so the API
   * shape is byte-for-byte what it was.
   */
  key: string;
  label: string;
  start_month: string;
  start_day: string;
  end_month: string;
  end_day: string;
  unit_price: string; // the seasonal model's per-season flat price
}

/** The lowest `s<n>` no season is using. Deterministic on purpose — a clock or
 *  a random suffix would make `draftFromSchedule` untestable by equality. */
export function nextSeasonKey(seasons: readonly SeasonDraft[]): string {
  const taken = new Set(seasons.map((season) => season.key));
  for (let n = 0; ; n += 1) {
    if (!taken.has(`s${n}`)) return `s${n}`;
  }
}

export interface WindowDraft {
  label: string;
  /** `SeasonDraft.key` — which season this window belongs to. The editor nests
   *  the window under that season and never asks, so *forgot to pick a season*
   *  is unreachable rather than refused (`DEF-RAT-5736`). A window whose key
   *  matches no season is shown, named and removable; it is never silently
   *  dropped, because a resumed draft may hold one. */
  season_key: string;
  day_type: string;
  start_time: string; // "HH:MM"; may wrap midnight (BR-RAT-033)
  end_time: string;
  unit_price: string;
  /**
   * WHICH METER REGISTER THIS WINDOW IS READ FROM — `tou_on | tou_mid |
   * tou_off`, metering's own vocabulary (B2 r8 / BR-MET-059).
   *
   * PO ruling 2026-08-16, verbatim: *"make the rate wizard say which register
   * is which"* (BR-RAT-067, OQ-236 CLOSED). Before this field a window carried
   * only the LABEL the utility typed and the engine matched it to a register by
   * PRICE RANK — a defensible reading of a signed rule that nonetheless decided
   * a customer's bill: 120/200/380 kWh at $0.22/$0.14/$0.09 is **$88.60**
   * paired as the utility means it and **$122.40** paired the other way round,
   * a 38% overcharge with nothing on the bill looking wrong. Empty string means
   * unanswered; the server refuses it as a required field.
   */
  channel: string;
}

/** metering's TOU register vocabulary (B2 r8 / BR-MET-059) — the whole set. */
export const TOU_CHANNELS = ["tou_on", "tou_mid", "tou_off"] as const;

/**
 * DEF-356/DEF-360 · one editable row of step 2's per-connection-size matrix.
 *
 * ⚠ **NO `base` FIELD, AND NO WAY TO ADD ONE BY ACCIDENT.** BR-RAT-088 gives the
 * base to the charge code; §A3's *"one source, two surfaces"* lets the schedule
 * DISPLAY it, attributed, and says *"its edit mode does not include it"*. This
 * IS the edit mode. `MATRIX_COLUMNS` carries `editable: false` on `base` and the
 * row renderer walks `editableMatrixColumns()`, so a base input cannot appear
 * here without first changing the rule where the rule lives.
 *
 * ⚠ **AN EMPTY `minimum_bill` IS NOT `0.00`.** CR-013 part 1: *"Blank base =
 * size not served"* (DEF-277), and the same distinction one column across — a
 * blank minimum is "this size has no floor", which is r10's electric matrix,
 * where the minimum column is an em-dash for every size. `decimalOut` omits an
 * empty string from the payload rather than zeroing it, and the column is
 * nullable so the absence round-trips.
 */
export interface SizeRowDraft {
  size_class: string;
  minimum_bill: string;
}

/**
 * DEF-433 · ONE CONNECTION SIZE THAT PRICES ITS TIERS DIFFERENTLY.
 *
 * This is the row r10's water matrix exists for: every size prices its blocks
 * at `3.20 / 4.80 / 7.20` and 2" prices them at `3.45 / 5.10 / 7.70`. A per-size
 * tier rate cannot be derived from a base, a multiplier or anything else — it
 * can only come from its own row — which is why the schedule needs a size axis
 * for reasons that have nothing to do with the base charge.
 *
 * ⚠ **THE BLOCK BOUNDARIES ARE NOT HERE, AND THAT IS THE DESIGN.** An override
 * states PRICES against the base ladder's own blocks, one entry per block in
 * the same order. r10's matrix has one set of column headers and five rows of
 * prices under them; letting a size move a boundary as well would be a second
 * ladder, which is a different product and one no drawing asks for. It also
 * makes the server's per-group contiguity rule impossible to fail by accident:
 * the boundaries are the base ladder's, so the group is contiguous by
 * construction.
 *
 * `prices` is therefore ALWAYS the same length as the base ladder — the control
 * seeds it from the base prices when an override is added and re-aligns it when
 * a block is added or removed, so a half-filled override cannot be posted.
 */
export interface SizeTierOverride {
  size_class: string;
  prices: string[];
}

export interface ScheduleDraft {
  name: string;
  service: string;
  uom: string;
  /**
   * CR-087 · WHICH CUSTOMER CLASS THIS SCHEDULE PRICES — `""` means every one.
   *
   * ⚠ **THE COLUMN HAS BEEN SERVED AND ACCEPTED SINCE `DEF-471` AND THIS SCREEN
   * OFFERED A SENTENCE INSTEAD OF A PICKER.** `account_type_id` is in
   * `services.SCHEDULE_FIELDS`, `_validate_schedule_identity` cleans it, and the
   * plan builder already FILTERS candidate schedules on it — so the one screen
   * that decides the value was the one screen that could not set it. Without it
   * a utility cannot run a residential water schedule and an industrial one
   * side by side, and it is the field that picks which base charge the next
   * step reads.
   */
  account_type_id: string;
  model: string;
  /**
   * ⚠ **CARRIED, NEVER EDITED — BR-RAT-088.** The wizard has offered a "Base
   * charge on this version" input since W1 and it is GONE from step 3, because
   * the ruling retires `tariff_versions.base_charge` as a claimant: with a base
   * on two objects a 5/8" residential water account carrying `$12.00` in both
   * bills **$24.00**, priced at **$23,069.50 a month across 1,247 connections**.
   *
   * The value is still read out of the stored version and still posted back,
   * and that is deliberate rather than an oversight: `_guard_base_charge_code`
   * is self-activating per tenant, so a tenant that has NOT declared an
   * `is_base` charge code is still billed from this column
   * (`apps.billing.gather._base_charge_for`). Dropping it from the payload would
   * blank a live base the first time anybody re-saved a draft, and every bill
   * for that service would then refuse instead of carrying its base. So: no
   * control, no editing, no loss.
   */
  base_charge: string;
  /**
   * `CR-120-BRC06` · `BR-RAT-1025` — **THE CHARGE CODE THIS SCHEDULE NAMES,
   * AS AN ID. IT IS THE OPPOSITE OF THE FIELD ABOVE.** PO ruling 2026-09-19:
   * *"plan → rate schedule -> charge code → base charges - this is correct"*,
   * and *"change is default -> expliciate"*.
   *
   * `base_charge` above is a retired FIGURE this screen carries and never
   * edits. This is a POINTER, it has a control — the searchable picker on
   * step 1 — and choosing one is the whole ruling.
   *
   * **`""` is a real answer and it is the common one:** the schedule names
   * nothing and its base resolves from the `is_base` code for the service,
   * exactly as every schedule does today. There is no asterisk on the field
   * for that reason.
   */
  base_charge_code: string;
  minimum_bill: string;
  /** DEF-360 — the size axis. Empty means one row prices every size. */
  size_rows: SizeRowDraft[];
  tiers: TierDraft[];
  /** DEF-433 — sizes that price the ladder above differently. Empty is normal:
   *  *"a schedule states the exception, not the rule"* (`RateTier`). */
  size_tiers: SizeTierOverride[];
  seasons: SeasonDraft[];
  windows: WindowDraft[];
  capacity: { unit_label: string; rate_per_unit: string };
  demand: {
    energy_rate_per_kwh: string;
    demand_rate_per_kw: string;
    peak_window_label: string;
    ratchet_enabled: boolean;
    ratchet_pct: string;
    pf_penalty_enabled: boolean;
    pf_penalty_rate_per_kw: string;
  };
  percent: string;
  basis_service: string;
  /**
   * `CR-130-BRC07` §3 — **WHICH NUMBER THE PERCENTAGE IS TAKEN OF.**
   * `"usage"` (the basis service's metered QUANTITY) or `"charge"` (its usage
   * MONEY). PO, verbatim, 2026-09-22: *"if water charge is $100, and %age is
   * 80% then sewer cahrge will be $80; if % of usage then if Water usage will
   * be 100 gallan %age is 80% then sewer uage will be 80 gallan"*.
   *
   * ⚠ **THE RATE LIVES IN `tiers`, NOT IN A SECOND FIELD.** `BR-RAT-032`
   * already says one price is ONE `0→∞` `rate_tiers` row, which is how `flat`
   * and today's `percent_of_service` both store one — so **flat versus tiered
   * is how many blocks there are**, and there is nothing new to keep in step.
   */
  percent_basis: string;
  confirm_percent_over_100: boolean;
  effective_from: string;
  effective_to: string;
  regulator_ref: string;
  /** DEF-369 — the label a regulator's docket references (`v3`, `2027-A`). */
  version_label: string;
  /** DEF-280 — the authored note describing what changed in this version. */
  change_reason: string;
  // BR-RAT-082 (PO 2026-08-20): *"this is correct; it is system of record so we
  // can collect the details and keep it."* The regulator signs OUTSIDE the
  // product. Step 4 is where the sign-off is TYPED IN — *"a date and a docket
  // number typed in, not a workflow step"* — and nothing here gates anything.
  filing_authority: string;
  filed_on: string;
  regulator_approved_on: string;
  regulator_approver: string;
  notify_customers: boolean;
  publish_public: boolean;
  /**
   * ⚠ **RETIRED BY CR-087 AND KEPT AS A COMMENT SO NOBODY ADDS IT BACK.**
   * `reason` held a SECOND free-text box on step 4 — *"Reason for this
   * change"* — beside *"What changed"*, writing to the compliance record while
   * its neighbour wrote the version's own note. One box asks the question once
   * and its value is posted to both, so the field is gone from the draft rather
   * than left carrying a value nothing sets. `BR-RAT-037`'s NOT NULL is
   * unchanged and is still satisfied at `createRateScheduleVersion`.
   */
}

/**
 * BR-RAT-091 (PO ruling 2026-08-20, closing OQ-284), clause 2, verbatim:
 * **"RATE CHANGE: worst-case bill change above `10%`."** Not annualised revenue
 * and not accounts-affected — both were offered to the PO and both were
 * declined.
 *
 * **Why this number is declared and not typed at the call site.** The rule's
 * own worked example is the test: our water +6% filing moves an 11 kgal
 * household `$59.00 → $62.54`, `+$3.54`/month, `$38,826`/year across 914
 * accounts — and **it FLOWS**, because 6% is under the bar. *"The threshold is
 * deliberately set where a routine annual filing passes and a repricing does
 * not."* A second copy of `10` would let one surface start refusing that filing.
 *
 * ⚠ **THIS WAS THE ONLY HOME THE FIGURE HAD, AND THAT WAS DEF-435 — CLOSED
 * 2026-08-21.** The paragraph here read: *"The rate half has no server
 * counterpart: no endpoint computes a worst-case change and nothing refuses an
 * activation over the bar, so this constant governs a screen and not a write.
 * A client-side-only gate is advice, not a control."* It is quoted rather than
 * deleted (hard-won law 1), because it is the whole reason the server side now
 * exists.
 *
 * **The figure's home is now `apps/rating/impact.RATE_CHANGE_SECOND_APPROVAL_PCT`**,
 * `POST /rate-schedules/{id}/versions` REFUSES a filing above it, and the panel
 * renders `second_approval_threshold_pct_display` off the server's own answer.
 * This constant survives as the documented MIRROR and as the fallback for the
 * moment before the endpoint has answered — and `secondApprovalRequired(null)`
 * still returns `null`, so the fallback can never report a filing as clear.
 * `RateScheduleWizard.test.tsx` and `test_br_rat_091_rate_change_impact.py`
 * each assert `10` on their own side, so the two cannot drift silently.
 */
export const RATE_CHANGE_SECOND_APPROVAL_PCT = 10;

/**
 * BR-RAT-091's gate, as a pure function so the figure is provable.
 *
 * `null` in means the worst case is UNKNOWN, and unknown is not "under the
 * bar": nothing computes these figures yet (DEF-434), so a boolean `false` here
 * would assert a schedule is clear when nobody has measured it. The screen
 * renders the third state — *not computed* — instead.
 */
export function secondApprovalRequired(worstCasePct: number | null): boolean | null {
  if (worstCasePct === null) {
    return null;
  }
  return worstCasePct > RATE_CHANGE_SECOND_APPROVAL_PCT;
}

/**
 * CR-013 part 1 step 4, verbatim: *"mandatory impact analysis: accounts affected
 * by plan, average and worst-case bill change per class, annualised revenue
 * change, accounts over threshold."* Part 1's own gloss makes the shape binding:
 * *"The impact analysis is MANDATORY and is four figures, not a warning
 * banner."*
 *
 * ⚠ **THIS USED TO BE THE LIST OF WHAT WAS MISSING (DEF-434) AND IS NOW THE
 * LIST OF WHAT IS SERVED.** It read *"No endpoint computes any of the four"*,
 * which was true until `GET /rate-schedules/{id}/impact` landed on 2026-08-21.
 * The order is unchanged and the labels are unchanged, so the step draws the
 * same four rows it always drew; what changed is that `impactValues` can now
 * fill them.
 *
 * The FIGURES stay declared here rather than inlined in the panel for the
 * reason they always were: *"MANDATORY … four figures, not a warning banner"* is
 * a shape a test can read (`IMPACT_FIGURES.length === 4`) rather than a
 * sentence a document restates. `accountsAvailable` is GONE — every row is
 * served now, and a per-row availability flag would be a second, staler answer
 * to a question `impactValues` already answers per render.
 */
export interface ImpactFigure {
  key: string;
  labelKey: string;
}

export const IMPACT_FIGURES: readonly ImpactFigure[] = [
  { key: "accounts", labelKey: "rating.rate.impact.accountsLabel" },
  { key: "billChange", labelKey: "rating.rate.impact.billChangeLabel" },
  { key: "revenue", labelKey: "rating.rate.impact.revenueLabel" },
  { key: "overThreshold", labelKey: "rating.rate.impact.overThresholdLabel" },
];

export const DAY_TYPES = ["weekday", "weekend", "holiday"] as const;

export function emptyScheduleDraft(): ScheduleDraft {
  return {
    name: "",
    service: "",
    uom: "",
    account_type_id: "",
    model: "flat",
    base_charge: "",
    // `CR-120-BRC06` — blank is *this schedule has not said*, which resolves
    // the base the way it always has. A new schedule is not born bound.
    base_charge_code: "",
    minimum_bill: "",
    // DEF-360: no size rows until the user adds them. An empty axis is what
    // every schedule built before today has, and it prices every size the same.
    size_rows: [],
    // BR-RAT-026: pure tiers. There is no allowance/"included units" field in
    // this draft, on this screen, or anywhere in v1.
    tiers: [{ from_qty: "0", to_qty: "", unit_price: "" }],
    // DEF-433 — no override is the normal schedule. Adding one is a deliberate
    // act on step 3, never a default a utility has to notice and remove.
    size_tiers: [],
    seasons: [],
    windows: [],
    capacity: { unit_label: "", rate_per_unit: "" },
    demand: {
      energy_rate_per_kwh: "",
      demand_rate_per_kw: "",
      peak_window_label: "",
      ratchet_enabled: false,
      ratchet_pct: "",
      pf_penalty_enabled: false,
      pf_penalty_rate_per_kw: "",
    },
    percent: "",
    basis_service: "",
    // `CR-130-BRC07` §2 — `usage` is what every percent schedule in the product
    // does today and what `CR-081` re-signed six ❄️ FROZEN figures onto. A new
    // schedule is born doing the thing the engine already does.
    percent_basis: PERCENT_BASIS_USAGE,
    confirm_percent_over_100: false,
    effective_from: "",
    effective_to: "",
    regulator_ref: "",
    version_label: "",
    change_reason: "",
    filing_authority: "",
    filed_on: "",
    regulator_approved_on: "",
    regulator_approver: "",
    notify_customers: false,
    publish_public: false,
  };
}

/**
 * DEF-433 · the ladder that prices every size — the stored rows whose
 * `size_class` is null. Every version written before the size axis existed is
 * entirely this group, so an unaffected schedule reads back exactly as it did.
 */
export function baseLadder(tiers: readonly TierRow[] | undefined): TierRow[] {
  // `DEF-RAT-10148` — a line tagged with a SEASON is that season's price, not
  // a rung of the base ladder. A seasonal schedule stores one such line per
  // season (`services._validate_structure`, MODEL_SEASONAL), and reading them
  // here put Summer's and Winter's prices into `draft.tiers` as a ladder the
  // seasonal editor never draws — a second copy of each price, waiting for the
  // model to change under it. They are read by `seasonPriceFor` instead.
  return (tiers ?? []).filter((tier) => tier.size_class === null && (tier.season ?? null) === null);
}

/**
 * `DEF-RAT-10148` · **A SEASON'S PRICE LIVES ON THE RATE LINE TAGGED WITH ITS
 * NAME, NOT ON THE SEASON.** The server writes a seasonal price as a `0 → ∞`
 * `RateTier` whose season is that season, and serves it in `structure.tiers`
 * with `season: "<label>"`; `structure.seasons` carries the dates alone. The
 * View tab has always read it this way (`rateScheduleViewTabs.tsx`, seasonal);
 * the wizard did not, so reopening Ann Arbor's seasonal kW-DC schedule showed
 * both prices blank on step 2 and on Review, and a save would have posted two
 * seasons with no price at all.
 *
 * The FIRST line for the season is taken, in served order (`seq`). The wizard
 * edits one price per season; a per-season LADDER (which the server accepts as
 * `season.tiers` and this screen never sends) is not something it can draw.
 */
export function seasonPriceFor(tiers: readonly TierRow[] | undefined, label: string): string {
  return (tiers ?? []).find((tier) => tier.season === label)?.unit_price ?? "";
}

/**
 * `DEF-RAT-10149` · **THE DATE A NEW VERSION IS PROPOSED TO START FROM**
 * (decision log 2026-10-14, *"RATE SCHEDULE EDIT: "EFFECTIVE FROM" IS
 * PREFILLED WITH THE FIRST DAY OF NEXT MONTH"*, PO *"go A"*).
 *
 * The first day of next month in the TENANT's calendar — `today` is the
 * tenant-zone day from `todayInZone`, never the browser clock (BR-TEN-043) —
 * or the day after the outgoing version's start when that is later, because
 * the server refuses a start on or before it (`activate_new_version`). Worked:
 * today `2026-10-14` → `2026-11-01`; outgoing start `2026-12-01` →
 * `2026-12-02`. Arithmetic is on the ISO string through UTC so no zone can move
 * a day. A suggestion: the field stays editable.
 */
export function suggestedEffectiveFrom(today: string, outgoingFrom: string | null | undefined): string {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(today.trim());
  if (match === null) return "";
  const year = Number(match[1]);
  const month = Number(match[2]); // 1–12, so as a 0-based month it IS next month
  const firstOfNext = new Date(Date.UTC(year, month, 1)).toISOString().slice(0, 10);
  const from = (outgoingFrom ?? "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(from)) return firstOfNext;
  const dayAfter = new Date(`${from}T00:00:00Z`);
  dayAfter.setUTCDate(dayAfter.getUTCDate() + 1);
  const next = dayAfter.toISOString().slice(0, 10);
  return next > firstOfNext ? next : firstOfNext;
}

/**
 * DEF-433 · the per-size ladders, grouped, in the order the server served them.
 *
 * Only the PRICES survive the round trip, because only the prices are editable
 * (see `SizeTierOverride`): the boundaries are the base ladder's. A group whose
 * length disagrees with the base ladder — which the server cannot currently
 * produce, but a hand-written row could — is still read back price-for-price,
 * and the editor re-aligns it against the base ladder rather than dropping it.
 */
export function sizeLadders(tiers: readonly TierRow[] | undefined): SizeTierOverride[] {
  const groups = new Map<string, string[]>();
  for (const tier of tiers ?? []) {
    if (tier.size_class === null) {
      continue;
    }
    const prices = groups.get(tier.size_class) ?? [];
    prices.push(tier.unit_price ?? "");
    groups.set(tier.size_class, prices);
  }
  return [...groups.entries()].map(([size_class, prices]) => ({ size_class, prices }));
}

/**
 * A stored version → the editable draft. This is the RESUME half of
 * BR-RAT-031: a saved draft's tiers/windows/seasons come back exactly as they
 * were posted, so reopening the wizard shows the structure that was left.
 */
export function draftFromSchedule(detail: ScheduleDetail, today?: string): ScheduleDraft {
  // ⚠ **THE DRAFT COMES FIRST, AND IT READ THE OTHER WAY UNTIL 2026-09-17
  // (DEF-RAT-6448).** `current_version ?? draft_version` is right only while a
  // schedule cannot hold both, which stopped being true the moment a live
  // schedule could park a draft (DEF-RAT-6447). With the live version first, a
  // clerk saved their unfinished change, reopened, and were handed the rate
  // that is in force — their work stored, served in the same payload, and
  // silently ignored. Hard-won law 2 in its second form: the data exists and
  // the screen does not read it.
  //
  // The parked draft IS the newer answer — it is what the clerk last typed —
  // and it prices nothing until it is activated, so preferring it cannot put a
  // wrong number in front of a customer. `parkedDraft()` below is what tells
  // the screen which of the two it is showing.
  const version: VersionRow | null = detail.draft_version ?? detail.current_version;
  /** `DEF-RAT-5833` — true when the row above is the clerk's own PARKED DRAFT,
   *  so the dates it carries are an answer they gave and parked. False when it
   *  is the version IN FORCE, which is a row being replaced rather than
   *  resumed. See the two date lines below for what turns on it. */
  const resuming = detail.draft_version !== null;
  const base = emptyScheduleDraft();
  if (version === null) {
    return {
      ...base,
      name: detail.name,
      service: detail.service,
      account_type_id: detail.account_type_id ?? "",
    };
  }
  const structure = version.structure;
  return {
    ...base,
    name: detail.name,
    service: detail.service,
    account_type_id: detail.account_type_id ?? "",
    uom: version.uom ?? "",
    model: version.model,
    base_charge: version.base_charge ?? "",
    // `CR-120-BRC06` — reopening the wizard must reload the binding, or a
    // re-save would silently clear it (`DEF-422`'s discipline: a wizard that
    // drops a stored fact because it did not read it is how a live setting
    // disappears on an unrelated edit).
    base_charge_code: version.base_charge_code ?? "",
    minimum_bill: version.minimum_bill ?? "",
    // DEF-360. `minimum_bill: null` is a size that HAS a row and has no floor,
    // so it reads back as an empty string and posts back as an omitted key —
    // the absence survives the round trip instead of becoming 0.00.
    size_rows: version.size_rows.map((row) => ({
      size_class: row.size_class,
      minimum_bill: row.minimum_bill ?? "",
    })),
    // DEF-433 — the NULL group is the base ladder. Grouping on read rather than
    // taking the list whole: a version with a 2" override stores six tier rows
    // in one list, and the old `structure.tiers.map(...)` read all six as one
    // ladder, which would have shown a utility its own rate as `0→10→30→0→10→30`
    // the first time it reopened the wizard.
    tiers:
      baseLadder(structure.tiers).length > 0
        ? baseLadder(structure.tiers).map((tier) => ({
            from_qty: tier.from_qty ?? "",
            to_qty: tier.to_qty ?? "",
            unit_price: tier.unit_price ?? "",
          }))
        : base.tiers,
    size_tiers: sizeLadders(structure.tiers),
    seasons: (structure.seasons ?? []).map((season, index) => ({
      // `s0`, `s1`, … in stored order. The key is minted HERE rather than read
      // back, because the server has no such column and does not need one.
      key: `s${index}`,
      label: season.label,
      start_month: String(season.start_month),
      start_day: String(season.start_day),
      end_month: String(season.end_month),
      end_day: String(season.end_day),
      // `DEF-RAT-10148` — this read `""`, so every season came back unpriced.
      unit_price: seasonPriceFor(structure.tiers, season.label),
    })),
    windows: (structure.windows ?? []).map((window) => ({
      label: window.label,
      // The stored link is a LABEL; resolve it to the key of the season that
      // carries it. A window naming a season the version does not hold keeps
      // an unresolvable key and the editor shows it under its own heading
      // rather than losing it (`DEF-RAT-5736`).
      season_key: seasonKeyForLabel(structure.seasons ?? [], window.season ?? ""),
      day_type: window.day_type,
      start_time: window.start_time,
      end_time: window.end_time,
      unit_price: window.unit_price ?? "",
      // A window stored before the register field existed reads back as "" and
      // the picker shows unanswered, which is the honest state: the utility has
      // not said yet, and nothing here picks one for them (BR-RAT-067).
      channel: window.channel ?? "",
    })),
    capacity: {
      unit_label: structure.capacity?.unit_label ?? "",
      rate_per_unit: structure.capacity?.rate_per_unit ?? "",
    },
    demand: {
      energy_rate_per_kwh: structure.demand?.energy_rate_per_kwh ?? "",
      demand_rate_per_kw: structure.demand?.demand_rate_per_kw ?? "",
      peak_window_label: structure.demand?.peak_window_label ?? "",
      ratchet_enabled: structure.demand?.ratchet_enabled ?? false,
      ratchet_pct: structure.demand?.ratchet_pct ?? "",
      pf_penalty_enabled: structure.demand?.pf_penalty_enabled ?? false,
      pf_penalty_rate_per_kw: structure.demand?.pf_penalty_rate_per_kw ?? "",
    },
    percent: structure.percent ?? "",
    basis_service: structure.basis_service ?? "",
    // `CR-130-BRC07` §2 — **a stored schedule that says nothing reads back as
    // `usage`, which is what it has always been billing.** The column is
    // `NOT NULL DEFAULT 'usage'` and every existing row is backfilled BY NAME,
    // so this fallback covers only the moment between this screen shipping and
    // the migration landing. A schedule silently changing basis would move real
    // money on a real customer (hard rule 4).
    percent_basis: structure.percent_basis ?? PERCENT_BASIS_USAGE,
    // ── `DEF-RAT-5833` · **A NEW VERSION'S WINDOW IS NOT THE OUTGOING ONE'S**
    //
    // These two read `version.effective_from ?? ""` / `version.effective_to ??
    // ""` unconditionally, so reopening a LIVE schedule to file the next rate
    // handed the clerk the dates of the version they are replacing — two dates
    // nobody typed, on the one step where a date decides when money changes.
    //
    // **It cost two different failures and the second is the quiet one.**
    //   · Brazos Bend's `Industrial Electric — Energy + demand` runs to
    //     `12/31/2027`. Filing a `2029` rate was refused with *"The end date
    //     has to come after the start date"* — `2029-02-20 >= 2027-12-31`,
    //     `rating.schedules.window_inverted` — about the `effective_to` box,
    //     which the clerk never touched and which step 4 does not mark.
    //   · A new window starting INSIDE the outgoing one is not refused at all:
    //     it is stored carrying `12/31/2027` as its OWN end, so on `01/01/2028`
    //     that service has no version in force and every bill for it refuses.
    //
    // **THE SERVER ALREADY CLOSES THE OLD WINDOW** — `activate_new_version`
    // sets `previous.effective_to = new_from - 1 day` — so an end date on the
    // NEW version is never how the old one is ended, and blank means
    // open-ended, which is what a rate filing normally is.
    //
    // ⚠ **THE FLAG IS *WHICH ROW WAS READ*, NOT *IS THE SCHEDULE LIVE*, AND
    // THAT KEEPS `DEF-RAT-6448` INTACT.** Resuming a PARKED DRAFT must hand
    // back the dates the clerk themselves typed and parked; blanking those
    // would lose typed work, which is the defect the draft-first read above
    // was written for. Starting a new version from the row IN FORCE is the
    // opposite case: there is no earlier answer to preserve, so the window is
    // the one fact this form may not inherit.
    //
    // A CORRECTION never reaches either line — the server copies the corrected
    // row's window (`version_fields["effective_to"] = original.effective_to`)
    // and step 4 draws no date fields at all on that path.
    //
    // ⚠ **AMENDED 2026-10-14 (`DEF-RAT-10149`, PO *"go A"*): `effective_from`
    // IS NO LONGER BLANK ON THAT PATH — IT IS A PROPOSED DATE, NOT AN INHERITED
    // ONE.** The rule above still holds: nothing of the outgoing WINDOW is
    // copied. When the caller passes the tenant's `today`, a new version
    // starting from the row in force is offered `suggestedEffectiveFrom` — the
    // first of next month, or the day after the outgoing start when that is
    // later (`closing_version_effective_from`, the row the server closes). A
    // parked draft still keeps the date the clerk typed; `effective_to` stays
    // blank; with no `today` the field stays blank as before.
    effective_from: resuming
      ? (version.effective_from ?? "")
      : today === undefined
        ? ""
        : suggestedEffectiveFrom(today, detail.closing_version_effective_from ?? version.effective_from),
    effective_to: resuming ? (version.effective_to ?? "") : "",
    regulator_ref: version.regulator_ref ?? "",
    version_label: version.version_label ?? "",
    change_reason: version.change_reason ?? "",
    // BR-RAT-082 — the filing details ride with the VERSION they were filed
    // for, so reopening a version shows the docket that version was signed on.
    filing_authority: version.filing_authority ?? "",
    filed_on: version.filed_on ?? "",
    regulator_approved_on: version.regulator_approved_on ?? "",
    regulator_approver: version.regulator_approver ?? "",
    notify_customers: version.notify_customers,
    publish_public: version.publish_public,
  };
}

/** The model's own structure block. Empty strings are OMITTED, never zeroed. */
export function structurePayload(draft: ScheduleDraft): Record<string, unknown> {
  switch (draft.model) {
    case "flat":
      // BR-RAT-032: flat is stored as ONE 0→∞ tier so the engine has a single
      // execution path. The server does that conversion from `unit_price`.
      return { unit_price: decimalOut(draft.tiers[0]?.unit_price ?? "") ?? "" };
    case "tiered": {
      const ladder = (unitPrice: (index: number) => string, sizeClass: string | null) =>
        draft.tiers.map((tier, index) => {
          const row: Record<string, unknown> = {
            from_qty: decimalOut(tier.from_qty) ?? "",
            unit_price: decimalOut(unitPrice(index)) ?? "",
          };
          // A blank To is ∞ — the key is OMITTED rather than sent as null,
          // and only the last row may legally leave it blank (server's rule).
          const to = decimalOut(tier.to_qty);
          if (to !== undefined) {
            row.to_qty = to;
          }
          if (sizeClass !== null) {
            row.size_class = sizeClass;
          }
          return row;
        });
      return {
        tiers: [
          // The NULL group FIRST and always. The server requires it — a payload
          // of nothing but size-specific ladders leaves every size the utility
          // did not name with no price at all, which is the refusal
          // `rating.tiers.size_override_without_base` exists for.
          ...ladder((index) => draft.tiers[index]?.unit_price ?? "", null),
          // DEF-433 — one group per override, sharing the base ladder's
          // BOUNDARIES and stating its own PRICES. `size_class` is what makes
          // them a separate group; without the key the server would read all of
          // them as one non-contiguous ladder and refuse.
          ...draft.size_tiers.flatMap((override) =>
            ladder((index) => override.prices[index] ?? "", override.size_class),
          ),
        ],
      };
    }
    case "time_of_use":
      return {
        seasons: draft.seasons.map(seasonPayload),
        windows: draft.windows.map((window) => ({
          label: window.label.trim(),
          // The CONTRACT is unchanged: the server still receives the season's
          // label. It is derived rather than typed, so it cannot name a season
          // this schedule does not have (`DEF-RAT-5736`).
          season: seasonLabelForKey(draft.seasons, window.season_key),
          day_type: window.day_type,
          start_time: window.start_time.trim(),
          end_time: window.end_time.trim(),
          unit_price: decimalOut(window.unit_price) ?? "",
          channel: window.channel,
        })),
      };
    case "seasonal":
      return { seasons: draft.seasons.map(seasonPayload) };
    case "capacity":
      return {
        capacity: {
          // BR-RAT-022: the unit label is free tenant text ("panel", "kW block").
          unit_label: draft.capacity.unit_label.trim(),
          rate_per_unit: decimalOut(draft.capacity.rate_per_unit) ?? "",
        },
      };
    case "demand": {
      const demand: Record<string, unknown> = {
        energy_rate_per_kwh: decimalOut(draft.demand.energy_rate_per_kwh) ?? "",
        demand_rate_per_kw: decimalOut(draft.demand.demand_rate_per_kw) ?? "",
        ratchet_enabled: draft.demand.ratchet_enabled,
        pf_penalty_enabled: draft.demand.pf_penalty_enabled,
      };
      if (draft.demand.peak_window_label.trim() !== "") {
        demand.peak_window_label = draft.demand.peak_window_label.trim();
      }
      const ratchet = decimalOut(draft.demand.ratchet_pct);
      if (ratchet !== undefined) {
        demand.ratchet_pct = ratchet;
      }
      const pf = decimalOut(draft.demand.pf_penalty_rate_per_kw);
      if (pf !== undefined) {
        demand.pf_penalty_rate_per_kw = pf;
      }
      return { demand };
    }
    default: {
      // ── `percent_of_service` · `CR-130-BRC07` §3, THE WIRE CONTRACT ───────
      //
      // ⚠ **THIS RETURNED `{percent, basis_service}` AND THE SERVER HAS
      // REQUIRED `structure.unit_price` SINCE 2026-09-08 — SO NO PERCENT
      // SCHEDULE COULD BE SAVED FROM THIS SCREEN AT ALL (`DEF-RAT-6146`).**
      // Reproduced in a browser before it was fixed, on the seeded water+sewer
      // utility: the POST answered `422 VAL-001`, `field_errors:
      // [{field: "structure.unit_price"}]`, and the card carried no rate field
      // for the clerk to fill in and no place to show the error. `CR-081`'s own
      // lifecycle block called its frontend half *"deferred (no-frontend-half;
      // the CONFIG half is S11's %-of-service card, already built)"* — the card
      // WAS built, for the DOLLAR basis, three weeks before the basis changed.
      // Hard-won law 1: a comment claiming a guarantee is not the guarantee.
      const body: Record<string, unknown> = {
        percent: decimalOut(draft.percent) ?? "",
        basis_service: draft.basis_service,
        percent_basis: draft.percent_basis,
      };
      if (draft.percent_basis === PERCENT_BASIS_CHARGE) {
        // ⚠ **NO RATE AT ALL ON THE CHARGE BASIS, AND IT IS OMITTED RATHER
        // THAN SENT EMPTY.** A percentage of MONEY needs no price per gallon;
        // §3 says the server REFUSES `tiers`/`unit_price` here BY NAME rather
        // than ignoring them, and a silently-dropped rate is the shape of the
        // `tiers[0]` discard that same section is fixing one layer down.
        return body;
      }
      // `BR-RAT-032` — one price is ONE `0→∞` row, so ONE block is flat and
      // several are a ladder. Nothing else distinguishes them and no flag says
      // which it is.
      body.tiers = draft.tiers.map((tier) => ({
        from_qty: tier.from_qty.trim(),
        to_qty: tier.to_qty.trim() === "" ? null : tier.to_qty.trim(),
        unit_price: decimalOut(tier.unit_price) ?? "",
      }));
      if (draft.tiers.length === 1) {
        // ⚠ **`unit_price` RIDES ALONGSIDE FOR A SINGLE BLOCK, AND THE REASON
        // IS THE TWO LANES.** §3 keeps it *"accepted for one block, as today …
        // so existing callers do not break"*, and the backend half of this
        // change is built by a different lane. With it, a flat percent schedule
        // saves against the server as it stands TODAY as well as against the
        // one that accepts the ladder. A MULTI-block ladder deliberately does
        // NOT get this treatment: against today's server it earns a visible
        // refusal naming the missing rate, where sending `tiers[0]`'s price
        // alone would quietly bill every block at the first block's rate.
        body.unit_price = decimalOut(draft.tiers[0]?.unit_price ?? "") ?? "";
      }
      return body;
    }
  }
}

/**
 * `DEF-RAT-5736` — the two ends of the key/label bridge, in one place so they
 * cannot disagree.
 *
 * The SERVER's contract is unchanged and is not negotiable here: a window
 * carries its season's LABEL (`_validate_windows` looks it up by name and
 * refuses `rating.tou.unknown_season`). The DRAFT carries a key instead,
 * because a label is the field a clerk retypes. These two functions are the
 * only places either crosses over.
 */
export function seasonKeyForLabel(
  seasons: readonly { label: string }[],
  label: string,
): string {
  const index = seasons.findIndex((season) => season.label === label);
  // "" is not a key `nextSeasonKey` can mint, so an unresolvable label reads as
  // *no season* everywhere downstream without a second sentinel.
  return index === -1 ? "" : `s${index}`;
}

export function seasonLabelForKey(seasons: readonly SeasonDraft[], key: string): string {
  return seasons.find((season) => season.key === key)?.label ?? "";
}

/**
 * **THE REFERENCE YEAR IS 2001 AND IT IS NOT AN ARBITRARY CHOICE.** It is the
 * year `apps/rating/services.py::_season_intervals` uses, chosen there because
 * it is NOT a leap year — so 29 February never participates in coverage math,
 * and `date(2001, 2, 29)` raises, which is how the server refuses it.
 *
 * The day picker below therefore offers 28 days in February. Offering 29 and
 * having the server refuse it is the defect this whole wave is about, one
 * control further down.
 */
const DAYS_PER_YEAR = 365;
const DAYS_IN_SEASON_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

/** The twelve month NUMBERS. The month's NAME comes from `Intl` through the
 *  date kit's `monthLabel`, never from a catalogue: B14 rule 35 says a
 *  catalogue is written in its own language, and twelve hand-written month
 *  names in eleven files would breach it the day a twelfth language lands. */
export const SEASON_MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;

export function daysInSeasonMonth(month: string): number {
  const index = Number(month) - 1;
  return Number.isInteger(index) && index >= 0 && index <= 11
    ? DAYS_IN_SEASON_MONTH[index]
    : 31;
}

/** The 1–365 ordinal on the reference year, or `null` while a half-typed row
 *  is not yet a date. A half-typed season is not a broken one. */
export function seasonDayOfYear(month: string, day: string): number | null {
  const m = Number(month);
  const d = Number(day);
  if (!Number.isInteger(m) || m < 1 || m > 12) return null;
  if (!Number.isInteger(d) || d < 1 || d > DAYS_IN_SEASON_MONTH[m - 1]) return null;
  let ordinal = d;
  for (let i = 0; i < m - 1; i += 1) ordinal += DAYS_IN_SEASON_MONTH[i];
  return ordinal;
}

/** The inverse — an ordinal back to `{month, day}`, for naming where a gap
 *  starts in words a clerk can act on. */
export function seasonDateAt(ordinal: number): { month: number; day: number } {
  let left = ordinal;
  for (let m = 0; m < 12; m += 1) {
    if (left <= DAYS_IN_SEASON_MONTH[m]) return { month: m + 1, day: left };
    left -= DAYS_IN_SEASON_MONTH[m];
  }
  return { month: 12, day: 31 };
}

/** `1 Apr`, in the language the app is rendering. */
export function seasonDayLabel(month: string | number, day: string | number, locale: string): string {
  return `${day} ${monthLabel(month, locale, "short")}`;
}

/**
 * **THE RANGE, ECHOED BACK** — `1 Apr – 30 Sep`. Empty while any of the four
 * boxes is unanswered, so a clerk part-way through a season is not shown half
 * a sentence.
 */
export function seasonRangeEcho(season: SeasonDraft, locale: string): string {
  if (
    seasonDayOfYear(season.start_month, season.start_day) === null ||
    seasonDayOfYear(season.end_month, season.end_day) === null
  ) {
    return "";
  }
  const from = seasonDayLabel(season.start_month, season.start_day, locale);
  const to = seasonDayLabel(season.end_month, season.end_day, locale);
  return `${from} \u2013 ${to}`;
}

export type SeasonCoverageIssue =
  | { kind: "overlap"; first: string; second: string }
  | { kind: "gap"; month: number; day: number };

/**
 * `DEF-RAT-5733` — **GAPS AND OVERLAPS, AS THE CLERK TYPES.**
 *
 * This is the same walk `_validate_seasons` does — intervals on the 2001
 * reference year, wrapping seasons split in two, sorted, then a cursor from
 * day 1 — so the screen and the server cannot disagree about whether a year is
 * covered. What it adds is WHICH of the two it is and WHERE, because the
 * server sends one message for both (`rating.seasons.coverage`) and a clerk
 * reading *no gap and no overlap* cannot tell which they have.
 *
 * The blueprint names the whole pattern for tiers on p047 — *"checked here,
 * where the numbers are typed … all three were server refusals discovered on
 * the last step"* — and this is that sentence applied to the calendar.
 *
 * Returns `null` while any row is incomplete: shouting mid-keystroke is its
 * own defect (`tierGapAt` has the same rule and for the same reason).
 */
export function seasonCoverageIssue(
  seasons: readonly SeasonDraft[],
): SeasonCoverageIssue | null {
  if (seasons.length === 0) return null;
  const intervals: { start: number; end: number; label: string }[] = [];
  for (const season of seasons) {
    const start = seasonDayOfYear(season.start_month, season.start_day);
    const end = seasonDayOfYear(season.end_month, season.end_day);
    if (start === null || end === null) return null;
    if (start <= end) {
      intervals.push({ start, end, label: season.label });
    } else {
      // Wraps the year end — Oct 1 – Mar 31 is two intervals, exactly as the
      // server splits it.
      intervals.push({ start, end: DAYS_PER_YEAR, label: season.label });
      intervals.push({ start: 1, end, label: season.label });
    }
  }
  intervals.sort((a, b) => a.start - b.start || a.end - b.end);
  let cursor = 1;
  let covered = 0;
  let previous = "";
  for (const interval of intervals) {
    if (interval.start < cursor) {
      return { kind: "overlap", first: previous, second: interval.label };
    }
    if (interval.start > cursor) {
      return { kind: "gap", ...seasonDateAt(cursor) };
    }
    covered += interval.end - interval.start + 1;
    cursor = interval.end + 1;
    previous = interval.label;
  }
  if (covered !== DAYS_PER_YEAR) {
    return { kind: "gap", ...seasonDateAt(cursor) };
  }
  return null;
}

function seasonPayload(season: SeasonDraft): Record<string, unknown> {
  const row: Record<string, unknown> = {
    label: season.label.trim(),
    start_month: season.start_month,
    start_day: season.start_day,
    end_month: season.end_month,
    end_day: season.end_day,
  };
  const price = decimalOut(season.unit_price);
  if (price !== undefined) {
    row.unit_price = price;
  }
  return row;
}

/** Everything but the dates — what "Save draft" posts (BR-RAT-031). */
export function draftPayload(
  draft: ScheduleDraft,
  includeIdentity: boolean,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    name: draft.name.trim(),
    model: draft.model,
    structure: structurePayload(draft),
    notify_customers: draft.notify_customers,
    publish_public: draft.publish_public,
    confirm_percent_over_100: draft.confirm_percent_over_100,
  };
  if (includeIdentity) {
    // `service` is immutable once the tariff exists — PATCH refuses it.
    payload.service = draft.service;
  }
  if (draft.uom.trim() !== "") {
    // CLAUDE.md #3 + BR-RAT-038: a schedule's unit is explicit, never assumed.
    payload.uom = draft.uom.trim();
  }
  // CR-087 · THE CLASS IS POSTED EVEN WHEN IT IS EMPTY, and that is the whole
  // difference between the two states. `null` is *this schedule prices every
  // class* — a deliberate answer a clerk can go back and choose — where an
  // omitted key would leave whatever was there before, so clearing the field
  // would silently do nothing. `_validate_schedule_identity` reads the key's
  // PRESENCE, so sending it is what makes the clear work.
  payload.account_type_id = draft.account_type_id === "" ? null : draft.account_type_id;
  const base = decimalOut(draft.base_charge);
  if (base !== undefined) {
    payload.base_charge = base;
  }
  // `CR-120-BRC06` · `BR-RAT-1025` — **POSTED EVEN WHEN EMPTY, and that is the
  // whole difference between the two states.** `null` is *this schedule names
  // nothing* — a deliberate answer a clerk can go back and choose — where an
  // omitted key would leave whatever was there before, so CLEARING the picker
  // would silently do nothing. It is exactly the reasoning `account_type_id`
  // records four lines down, and the server reads the key's PRESENCE the same
  // way.
  payload.base_charge_code = draft.base_charge_code === "" ? null : draft.base_charge_code;
  // ⚠ **NO VERSION MINIMUM IS EVER SENT (PO 2026-10-01, option A; billed per
  // size since 2.433.0, `rating/0053`).** The API refuses a stated version
  // minimum; the per-size minimums below are the ones billing reads.
  // `DEF-RAT-8736` — a row added with `+ Add row` and no size yet is not a row:
  // `Save draft` must not post `size_class: ""` (step 2's Continue refuses it).
  const sizedRows = draft.size_rows.filter((row) => row.size_class !== "");
  if (sizedRows.length > 0) {
    // DEF-360. The KEY is omitted entirely when there are no rows, so a schedule
    // that never had a size axis is not handed an empty list that would delete
    // rows another surface wrote. Within a row, an empty minimum is omitted the
    // same way — `null` reaches the nullable column and means "no floor", never
    // `0.00` (DEF-277's distinction, one column across).
    payload.size_rows = sizedRows.map((row) => {
      const item: Record<string, unknown> = { size_class: row.size_class };
      const floor = decimalOut(row.minimum_bill);
      if (floor !== undefined) {
        item.minimum_bill = floor;
      }
      return item;
    });
  }
  if (draft.regulator_ref.trim() !== "") {
    payload.regulator_ref = draft.regulator_ref.trim();
  }
  // BR-RAT-082 — captured and kept. Each key is omitted when blank rather than
  // sent as an empty string, so "not recorded" stays NULL in the column and
  // never becomes an empty docket number that looks answered.
  for (const field of [
    "filing_authority",
    "filed_on",
    "regulator_approved_on",
    "regulator_approver",
    // DEF-369 / DEF-280 — the same rule for the same reason: a blank label is
    // "never stated", and an empty string would be a label that looks answered.
    // The screen falls back to a derived ordinal on NULL and cannot tell the
    // difference from `""`.
    "version_label",
    "change_reason",
  ] as const) {
    const value = draft[field].trim();
    if (value !== "") {
      payload[field] = value;
    }
  }
  return payload;
}

/** The dates the activation adds. An EMPTY date is still sent, so the server
 *  answers its own "effective_from is required" instead of this screen guessing. */
export function activationDates(draft: ScheduleDraft): Record<string, unknown> {
  return {
    effective_from: draft.effective_from === "" ? null : draft.effective_from,
    effective_to: draft.effective_to === "" ? null : draft.effective_to,
  };
}

/**
 * DEF-297 · **`Base only` — CR-013 part 1's SIXTH structure, offered and
 * DISABLED, because the server would refuse it.**
 *
 * Part 1 names six: *"Flat · Tiered (ascending boundaries, open-ended last
 * tier) · TOU (windows must cover 24h) · Seasonal (ranges must cover the year) ·
 * Demand + energy (with demand determinant) · **Base only**."*
 * `apps/rating/services.TARIFF_MODELS` registers **seven** — the five plus
 * BR-RAT-019's `capacity` and BR-RAT-015's `percent_of_service` — and
 * `base_only` is not among them. A `POST` carrying it is refused by `_choice`
 * as an unknown value.
 *
 * **So it is drawn, and it cannot be picked.** Hiding it would make the missing
 * structure invisible to the operator who was told the product has six; offering
 * it live would hand them a value the server rejects at save, after they have
 * filled in a whole wizard. `FieldOption.disabled` is the third answer, and the
 * gap is stated beside the control in words rather than left to a stuck click.
 *
 * ⚠ The concept is not missing from the product — `engine.price_bill` already
 * takes `base_only_services` and `apps/customers` has a
 * `billable_base_only` behaviour class, so a service CAN bill base-only today.
 * What has no home is a base-only **rate schedule structure**, which is what
 * part 1 asked for. DEF-297.
 */
export const BASE_ONLY_MODEL = "base_only";

/** The structure picker's options. Pure, so "which are offered, which are
 *  disabled" is a fact a test can assert instead of a click. */
export function structureOptions(
  t: Translator,
  billingBasis?: string,
): { value: string; label: string; disabled?: boolean }[] {
  // DEF-RAT-9015 — time of use and demand price meter READS, so a service the
  // tenant does not read from a meter (`share` or `capacity`) cannot use them;
  // the server refuses the save. An unknown basis offers both: the server is
  // the one that knows, and hiding a method on a guess is the worse failure.
  const noMeter = billingBasis === "share" || billingBasis === "capacity";
  // DEF-BIL-9014 (PO 2026-10-02) — the mirror: a service the tenant DOES read
  // from its own meter is priced from its readings, never as a share of
  // another service, because a share on a metered service is charged once
  // per meter. The server refuses that save too.
  const hasMeters = billingBasis === "metered";
  const offered = TARIFF_MODELS.map((value) =>
    noMeter && (value === "time_of_use" || value === "demand")
      ? {
          value: value as string,
          label: t("rating.rs.wiz.needsMeter", { model: t(`rating.model.${value}`) }),
          disabled: true,
        }
      : hasMeters && value === "percent_of_service"
        ? {
            value: value as string,
            label: t("rating.rs.wiz.hasMeters", { model: t(`rating.model.${value}`) }),
            disabled: true,
          }
        : { value: value as string, label: t(`rating.model.${value}`) },
  );
  return [
    ...offered,
    {
      value: BASE_ONLY_MODEL,
      // The reason travels IN the label, because a disabled <option> has no
      // other place to carry one — the same idiom `activeUomOptions` uses for
      // an out-of-scope unit (FieldOption's rule).
      label: t("rating.rate.baseOnlyDisabled", { model: t("rating.model.base_only") }),
      disabled: true,
    },
  ];
}

/**
 * DEF-356 · the matrix's ROW AXIS — `service_size_classes`, active rows only.
 *
 * BR-TEN-029 (a deactivated entry leaves every picker) is applied here and
 * BR-TEN-078's service scope is deliberately NOT: the PO ruled the size-class
 * list unscoped **twice**, the second time specifically because r10's card
 * text is service-segmented and reads like the strongest candidate for scoping.
 * *"I have clariffied - already - dont attached them to service."* A lane must
 * not re-open it on the strength of that card text, so the reason is here where
 * the filtering would otherwise go.
 */
/** DEF-2190 — MOVED to `./ratingShared` (three screens ask it now) and
 *  re-exported so every existing importer and test keeps working. */
export { activeSizeClasses };

/**
 * BR-RAT-088 · which charge code owns this service's base, or `null`.
 *
 * ⚠ **MOVED TO `./baseCharge` (DEF-431) AND RE-EXPORTED FROM HERE.** RAT-02's
 * matrix has to answer the same question — §A3's *"one source, two surfaces"* —
 * and two screens resolving one fact independently is how they start
 * disagreeing about which code owns a base. The re-export keeps every existing
 * importer working; new callers should read `./baseCharge` directly.
 */
export { baseChargeFor };

/** Which structure editor a model uses. Pure, so the mapping is provable. */
export function editorFor(model: string): string {
  if (model === "flat") {
    return "flat";
  }
  if (model === "tiered") {
    return "tiers";
  }
  if (model === "time_of_use") {
    return "tou";
  }
  if (model === "seasonal") {
    return "seasonal";
  }
  if (model === "capacity") {
    return "capacity";
  }
  if (model === "demand") {
    return "demand";
  }
  return "percent";
}

/**
 * **RAT-03's FIVE STEPS, IN ORDER** — CR-013 part 1: *"RAT-03 wizard — 5 steps,
 * matching the build: 1. Basics · 2. Base rates · 3. Pricing formula ·
 * 4. Effective & approval · 5. Review & activate"*, and §8's rail labels for
 * RAT-03 are the same five words.
 *
 * ⚠ **THE SCREEN HAD FOUR.** `Base rates` was never a step: the wizard went
 * Basics → Pricing formula → Effective dates → Review, so the per-size matrix
 * had nowhere to live and the rail said four where the spec says five
 * (DEF-356). Adding it is what makes step 2 exist at all.
 *
 * Declared here so the rail is derived rather than typed twice.
 */
export const RATE_WIZARD_STEPS = [
  { id: "basics", labelKey: "rating.rate.step.basics" },
  { id: "sizes", labelKey: "rating.rate.step.sizes" },
  { id: "structure", labelKey: "rating.rate.step.structure" },
  { id: "effective", labelKey: "rating.rate.step.effective" },
  { id: "review", labelKey: "rating.rate.step.review" },
] as const;

/**
 * DEF-RAT-8703 — **THE TOAST SAYS WHAT THE SAVED SCHEDULE SAYS.**
 *
 * It read `is live` for every activation, and the server's answer to that
 * same commit carried `status` and `scheduled_change`. So a version that
 * starts tomorrow — a rate filed ahead, or a correction of one — toasted
 * *"is live"* over a list row that said `Draft` and `Change scheduled`, and
 * the PO, a day ahead of the utility's clock, read the row as the save having
 * failed. `status` is `selectors.schedule_state`'s derivation: `active` only
 * when a version is in force on the utility's today. No clock is read here
 * (BR-TEN-043): the server already answered.
 */
export function commitToast(
  mode: "draft" | "activate",
  saved: Pick<ScheduleDetail, "status" | "scheduled_change">,
): { key: string; date: string | null } {
  if (mode === "draft") {
    return { key: "rating.rate.toast.draft", date: null };
  }
  if (saved.status === "active") {
    return { key: "rating.rate.toast.activated", date: null };
  }
  if (saved.scheduled_change !== null && saved.scheduled_change !== undefined) {
    return { key: "rating.rate.toast.scheduled", date: saved.scheduled_change };
  }
  return { key: "rating.rate.toast.saved", date: null };
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface RateScheduleWizardProps {
  client?: ApiClient;
  dateFormat?: RegionalDateFormat;
}

/**
 * CR-157-BRC10 wave B — **RAT-03 IS THREE STEPS NOW: Details · Pricing ·
 * Review**, built from images 40–71 in `./RateScheduleThreeStep`. This export
 * keeps its name and its route (`App.tsx` mounts it at `…/rates/new` and
 * `…/rates/:tariffId/edit`), and the five-step body it used to hold is gone.
 *
 * ⚠ **THE PURE PIECES ABOVE AND THE EDITORS BELOW STAY** — the draft shape,
 * the payload builders and `PercentEditor` are what the new wizard is built
 * on. ⚠ **THE OLD FIVE-STEP PANELS ARE DELETED (`DEF-GOV-10106`, closing
 * `DEF-RAT-8755`'s retirement).** `BasicsStep`, `SizeMatrixStep`,
 * `StructureStep`, `EffectiveStep`, `ReviewStep`, the intent picker and every
 * editor only they rendered had been mounted by no screen since `5804b0fc1`
 * (2026-10-01), and G40 counted them as dead UI. `TierLadder` stays because
 * `PercentEditor` renders it.
 */
export function RateScheduleWizard(props: RateScheduleWizardProps) {
  return <RateScheduleThreeStep client={props.client} dateFormat={props.dateFormat} />;
}

// ── The pure pieces and the one editor the three-step wizard still uses ────

function shapeError(t: (key: string) => string, value: string): string | undefined {
  return decimalShapeError(value) === null ? undefined : t("rating.error.notDecimal");
}

/**
 * DEF-RAT-5717 · `BR-RAT-032` — **WHERE A LADDER STOPS RUNNING ON, AND WHAT TO
 * TYPE INSTEAD.**
 *
 * The PO, in the beta, verbatim: *"in tied rates - if tier 1 start from 0 to 100
 * and tier 2 start from 101 to 300 ; then it give error - tier 2 should start
 * from 100"*. **The product is right and the message was at fault.** BR-RAT-032
 * is CONFIRMED (PO R5-5) and the boundaries are half-open — tier 1 is 0 up to
 * but NOT including 100 — so `101` leaves a gap and `100` is the answer.
 *
 * The server has always computed that number and passed it as `expected=`. The
 * catalogue sentence had no placeholder for it, so i18next dropped it in
 * silence and the clerk was told *"tiers must run on from one another"* and
 * left to work out which tier and which number. **Nothing went red**, because
 * a key that resolves is all any check here asks about.
 *
 * ⚠ **AND IT IS COMPUTED HERE RATHER THAN WAITED FOR.** The Plans & Rates
 * blueprint p047 names the whole defect: *"Contiguity, inverted tiers and an
 * open middle tier are checked here, where the numbers are typed. All three
 * were server refusals discovered on the last step."* This is the same
 * arithmetic the server does, so the two cannot disagree — the server still
 * refuses, and still owns the answer; this only stops a clerk walking four
 * steps to be told about a number they typed on the first one.
 *
 * Returns `null` while a row is blank or unparseable: a half-typed ladder is
 * not a broken one, and shouting at somebody mid-keystroke is its own defect.
 */
export function tierGapAt(tiers: readonly TierDraft[], index: number): string | null {
  if (index === 0) {
    return null;
  }
  const previous = tiers[index - 1];
  const here = tiers[index];
  if (previous === undefined || here === undefined) {
    return null;
  }
  const to = previous.to_qty.trim();
  const from = here.from_qty.trim();
  if (to === "" || from === "" || Number.isNaN(Number(to)) || Number.isNaN(Number(from))) {
    return null;
  }
  return Number(to) === Number(from) ? null : to;
}

/**
 * DEF-RAT-5717 — **A NEW BLOCK STARTS WHERE THE ONE ABOVE IT ENDS.**
 *
 * Pre-filled and still editable. The Plans & Rates blueprint p046 draws `FROM`
 * as an ordinary input and draws its own ladder contiguous (`0–2`, `2–10`,
 * `10–blank`), so this is the drawn state reached by default rather than a
 * control the drawing does not have. A clerk who means something else types it.
 *
 * Empty when there is no row above, or when the row above has no upper limit —
 * because a block above an open-ended one cannot exist, and guessing a number
 * there would be inventing one.
 */
export function nextTierStart(tiers: readonly TierDraft[]): string {
  return tiers[tiers.length - 1]?.to_qty.trim() ?? "";
}

/**
 * The id of the ladder's ONE sentence about a blank upper bound.
 *
 * ⚠ **IT IS NOT `tier-to-<n>-help`, AND THE DIFFERENCE IS THE DEFECT.** That
 * spelling is what `TextField` generates for a `help=` prop, one per row —
 * which is the shape `DEF-RAT-6164` removed. This one is singular by name
 * because the sentence is singular: only the LAST row's `To` points at it.
 */
const TIER_TO_HELP_ID = "tier-to-help";

/**
 * ── `CR-130-BRC07` · THE LADDER ITSELF, AS A COMPONENT ─────────────────────
 *
 * **B14 rule 43** (ratified 2026-09-20): *a piece of UI is built as a
 * COMPONENT; standalone code inside a page is not reuse.* Two structures price
 * through blocks now — `tiered` has always, and `percent_of_service` does from
 * this change, because the PO asked for *"consumtiom can be charge flat or
 * tiered"* on the percent card. Copying these rows into the percent editor
 * would be exactly the 120-lines-inline the rule was ruled against, and it
 * would have to be kept in step with `tierGapAt`'s contiguity message by hand.
 *
 * ⚠ **THE FIELD `id`s ARE UNCHANGED — `tier-from-0`, `tier-to-0`,
 * `tier-price-0`.** Only one structure editor renders at a time (the model
 * picker decides which), so the two callers cannot collide, and every existing
 * test and walkthrough that reaches for those ids keeps working. Renaming them
 * would be a silent break of checks nothing else re-derives.
 *
 * It renders the ROWS and the add button and nothing else: no `Panel`, no
 * heading, no size overrides. What a ladder is FOR differs by structure, and
 * that is the caller's sentence to write.
 */
export function TierLadder(props: {
  tiers: readonly TierDraft[];
  fieldErrors: Record<string, string>;
  onChange: (tiers: TierDraft[]) => void;
}) {
  const { t } = useTranslation();
  const { tiers } = props;
  function patchTier(index: number, next: Partial<TierDraft>): void {
    props.onChange(tiers.map((tier, i) => (i === index ? { ...tier, ...next } : tier)));
  }
  return (
    <>
      {tiers.map((tier, index) => (
        <div key={index} className="rating-tier-row">
          <TextField
            id={`tier-from-${index}`}
            label={t("rating.tier.from")}
            value={tier.from_qty}
            onChange={(from_qty) => patchTier(index, { from_qty })}
            numeric
            error={
              props.fieldErrors[`structure.tiers[${index}].from_qty`] ??
              shapeError(t, tier.from_qty) ??
              // DEF-RAT-5717 — the blueprint's own sentence, naming BOTH tiers
              // and BOTH numbers "so the fix is visible without re-reading the
              // table" (p047). It is the same words the server uses, from the
              // same catalogue key, so the two cannot drift apart.
              (tierGapAt(tiers, index) === null
                ? undefined
                : t("rating.tiers.not_contiguous", {
                    tier: index + 1,
                    starts: tier.from_qty.trim(),
                    previous: index,
                    expected: tierGapAt(tiers, index) as string,
                  }))
            }
          />
          <TextField
            id={`tier-to-${index}`}
            label={t("rating.tier.to")}
            value={tier.to_qty}
            onChange={(to_qty) => patchTier(index, { to_qty })}
            numeric
            // BR-RAT-032: blank = ∞ and is legal on the LAST row only. The
            // sentence that says so is `TIER_TO_HELP_ID` below — written ONCE
            // for the ladder, never `help=` on this box. `DEF-RAT-6164`.
            describedBy={index === tiers.length - 1 ? TIER_TO_HELP_ID : undefined}
            error={
              props.fieldErrors[`structure.tiers[${index}].to_qty`] ?? shapeError(t, tier.to_qty)
            }
          />
          <MoneyTextField
            id={`tier-price-${index}`}
            label={t("rating.tier.rate")}
            value={tier.unit_price}
            onChange={(unit_price) => patchTier(index, { unit_price })}
            error={
              props.fieldErrors[`structure.tiers[${index}].unit_price`] ??
              shapeError(t, tier.unit_price)
            }
          />
          {tiers.length > 1 && (
            <Button
              variant="ghost"
              onClick={() => props.onChange(tiers.filter((_, i) => i !== index))}
            >
              {t("rating.tier.remove")}
            </Button>
          )}
        </div>
      ))}
      {/* ── THE LADDER'S ONE SENTENCE · `DEF-RAT-6164` ────────────────────────
          **ONCE, AFTER THE LAST ROW — NOT `help=` ON EVERY `To` BOX.** Three
          things the Product Owner reported on the deployed build were this one
          prop, and the third names the fault in the first two: *"'Leave blank
          on the last row for no upper limit.' This text is reapeted"*. It said
          *the LAST row* under every row, so on a six-block ladder it printed
          six times and was false on five of them (B14 rule 32 clause 3).

          ⚠ **AND IT WAS ALSO THE MISALIGNMENT.** `help` renders inside the
          field's box, so `To` measured **103px** against **60px** for `From`
          and `Rate`; the row is a grid on `align-items: end`, which bottom-
          aligns the BOXES, so the taller box carried its input **43px** above
          its neighbours on every row. Blueprint p046 draws all four controls
          on one line with the sentence hanging below the last `To`, which is
          what this renders.

          It is attached to the last `To` input through `describedBy` above, so
          detaching it from the box did not detach it from the field. Rendered
          only when there are rows: the percent card's flat case passes an
          EMPTY ladder and draws its price above, where there is no `To` box
          for this sentence to be about. */}
      {tiers.length > 0 && (
        <p className="field-help" id={TIER_TO_HELP_ID}>
          {t("rating.tier.toHelp")}
        </p>
      )}
      {/* ⚠ **THE WRAPPER IS LOAD-BEARING — IT IS THE "UI BREAKING AT BOTTOM"**
          (`DEF-RAT-6164`). `Panel` is `display:flex; flex-direction:column`, so
          a Button that is its DIRECT child is a flex item and stretches across
          the cross axis: `+ Add tier` measured **1088px** wide, against 69px
          for `Back` and 102px for `Continue`, and read as an empty input rather
          than as a button. Inside a block wrapper the same Button is
          `inline-flex` again and takes its content's width, which is what
          blueprint p046 draws. Do not "tidy" this div away. */}
      <div>
        <Button
          variant="secondary"
          onClick={() =>
            props.onChange([
              ...tiers,
              {
                // DEF-RAT-5717 — a new block STARTS where the one above it
                // ends, pre-filled and still editable. The blueprint draws
                // this field as an ordinary input (p046) and its own drawn
                // ladder is contiguous, so this is the drawn state arrived at
                // by default rather than a control the drawing does not have.
                from_qty: nextTierStart(tiers),
                to_qty: "",
                unit_price: "",
              },
            ])
          }
        >
          {t("rating.tier.add")}
        </Button>
      </div>
    </>
  );
}


/**
 * ── `CR-130-BRC07` · A PERCENTAGE OF ANOTHER SERVICE'S MONEY **OR** OF ITS
 * METER ─────────────────────────────────────────────────────────────────────
 *
 * **PO, verbatim, 2026-09-22, looking at this card on a live build:**
 * *"we also need to create 2 option 5age of charges or % of usage - when we say
 * charges - in that case if water charge is $100, and %age is 80% then sewer
 * cahrge will be $80; if % of usage then if Water usage will be 100 gallan
 * %age is 80% then sewer uage will be 80 gallan = sewer charge will be 80 X
 * { flat rate or tiered rate} - this is how it should be done"*.
 *
 * ⚠ **NOTHING IS REVERSED AND THAT IS THE WHOLE OF §2.** `CR-081` moved sewer
 * from a percentage of water's MONEY to a percentage of water's VOLUME on
 * 2026-09-08 and the Product Owner re-signed six ❄️ FROZEN figures onto it
 * (`GT-17` = 8 kgal → 7.2 kgal × `$5.0000` = **`$36.00`**). This puts the
 * dollar basis back BESIDE it as a CHOICE; it does not take the volume basis
 * away, and every stored schedule is migrated to `usage` by name.
 *
 * ⚠ **AND THE CARD IS WHY THE REQUEST EXISTS (`DEF-RAT-6145`).** Its five
 * sentences still described the DOLLAR arithmetic the engine stopped doing on
 * 2026-09-08 — *"another service's usage charge"*, *"the base charge and tax
 * are not included"* — so the Product Owner read the screen, believed the
 * product already took a percentage of money, and asked for the OTHER one.
 * **A stale sentence did not merely confuse: it produced a change request for
 * a feature that already existed.** That is hard-won law 1 with a cost
 * attached.
 *
 * **THE ORDER ON SCREEN IS THE ORDER OF THE QUESTIONS.** Which number → how
 * much of it → of which service → at what price. The basis sits ABOVE
 * Percentage because it changes what every field under it means.
 */
export function PercentEditor(props: {
  draft: ScheduleDraft;
  /** The wizard's own client, threaded so a test can serve the Based-on list
   *  without a network. `services` is GONE from these props on purpose: this
   *  card no longer derives the list from it (Appendix A.2). */
  client?: ApiClient;
  fieldErrors: Record<string, string>;
  onPatch: (next: Partial<ScheduleDraft>) => void;
}) {
  const { t } = useTranslation();
  const { draft } = props;
  const onUsage = draft.percent_basis !== PERCENT_BASIS_CHARGE;
  /**
   * `CR-130-BRC07` §3 · Appendix A.2 — **ASKED OF THE SERVER, NOT DERIVED
   * HERE.** Keyed by the service AND the basis, because the usage list is a
   * strict subset of the charge list and caching one under the other would
   * offer a clerk services the write path refuses. `enabled` waits for step 1:
   * with no service chosen there is no question to ask.
   */
  const basisQuery = useQuery({
    queryKey: queryKeys.percentBasisOptions(draft.service, draft.percent_basis),
    queryFn: () => getPercentBasisOptions(draft.service, draft.percent_basis, props.client),
    enabled: draft.service !== "",
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const basisOptions = (basisQuery.data ?? []).map((row) => ({
    value: row.code,
    // The tenant's own word for the service, never the wire code — B14 rule 32.
    label: row.name,
  }));
  /**
   * ⚠ **CHANGING THE BASIS CAN INVALIDATE THE SERVICE ALREADY CHOSEN, AND
   * LEAVING IT WOULD BE THE WORST OF THE THREE OUTCOMES.** The usage list is a
   * SUBSET of the charge list — a service that meters nothing has no quantity —
   * so switching charge → usage can strand a basis the new list does not offer.
   * A `<select>` whose value matches no option renders BLANK while the draft
   * still holds the old code, and the save would then post a pairing the screen
   * never showed. Clearing it asks the question again, visibly.
   */
  function chooseBasisKind(percent_basis: string): void {
    props.onPatch({ percent_basis });
  }
  /**
   * ⚠ **A BASIS THE NEW LIST DOES NOT OFFER IS CLEARED WHEN THAT LIST
   * ARRIVES**, never before — the answer is the server's now, so the clearing
   * has to wait for it. `isSuccess` is the guard and it is load-bearing:
   * clearing while the query is in flight, or after it FAILED, would throw away
   * a stored `basis_service` because the screen could not reach the server,
   * which is data loss wearing the costume of validation.
   */
  useEffect(() => {
    if (!basisQuery.isSuccess || draft.basis_service === "") {
      return;
    }
    if (!(basisQuery.data ?? []).some((row) => row.code === draft.basis_service)) {
      props.onPatch({ basis_service: "" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basisQuery.isSuccess, basisQuery.data, draft.basis_service]);
  return (
    <Panel
      title={t("rating.model.percent_of_service")}
      hint={onUsage ? t("rating.percentOfService.hintUsage") : t("rating.percentOfService.hintCharge")}
    >
      <SegmentedField
        id="percent-basis-kind"
        label={t("rating.percentOfService.basisKindLabel")}
        value={onUsage ? PERCENT_BASIS_USAGE : PERCENT_BASIS_CHARGE}
        onChange={chooseBasisKind}
        options={PERCENT_BASIS_KINDS.map((kind) => ({
          value: kind,
          label: t(`rating.percentOfService.basisKind.${kind}`),
        }))}
      />
      <TextField
        id="percent-value"
        label={t("rating.percentOfService.percentLabel")}
        value={draft.percent}
        onChange={(percent) => props.onPatch({ percent })}
        numeric
        // What the percentage is OF, in one sentence, per basis. It is a FACT
        // and B14 rule 33 caps a fact at six words — which is why the old
        // sentence, at fourteen and describing the wrong arithmetic, is gone
        // rather than shortened.
        help={
          onUsage
            ? t("rating.percentOfService.percentHelpUsage")
            : t("rating.percentOfService.percentHelpCharge")
        }
        error={props.fieldErrors["structure.percent"] ?? shapeError(t, draft.percent)}
      />
      <SelectField
        id="percent-basis"
        label={t("rating.percentOfService.basisLabel")}
        value={draft.basis_service}
        onChange={(basis_service) => props.onPatch({ basis_service })}
        options={basisOptions}
        placeholder={t("rating.percentOfService.basisChoose")}
        required
        error={props.fieldErrors["structure.basis_service"]}
      />
      {basisQuery.isSuccess && basisOptions.length === 0 && (
        // A derived list can legitimately come out empty — a utility whose only
        // other service meters nothing has nothing to take a percentage of a
        // quantity FROM. Said out loud, because an empty picker with no
        // sentence reads as a broken screen (B14 rule 32's stated absence).
        <Note>{t("rating.percentOfService.basisNone")}</Note>
      )}
      {onUsage ? (
        <>
          {/* ── THE RATE · `DEF-RAT-6146` ───────────────────────────────────
              **THIS SCREEN HAS NEVER HAD ONE, AND THE SERVER HAS REQUIRED IT
              SINCE 2026-09-08** — so a percent schedule could not be saved
              from here at all. Reproduced in a browser on the seeded
              water+sewer utility before this was written: `422 VAL-001`,
              `field_errors: [{field: "structure.unit_price"}]`, with no field
              on the card to fill in and nowhere to show the error.

              ONE block is a flat rate and renders as one box, exactly as
              `FlatEditor` does — `BR-RAT-032` stores both the same way and
              `from 0 / to ∞` on a single row are facts, not questions. Press
              *Add tier* and the bounds appear, because now they are. */}
          {draft.tiers.length === 1 ? (
            <MoneyTextField
              id="percent-unit-price"
              label={t("rating.rate.flat.priceLabel")}
              value={draft.tiers[0]?.unit_price ?? ""}
              onChange={(unit_price) =>
                props.onPatch({ tiers: [{ from_qty: "0", to_qty: "", unit_price }] })
              }
              help={t("rating.percentOfService.rateHelp")}
              error={
                props.fieldErrors["structure.unit_price"] ??
                props.fieldErrors["structure.tiers[0].unit_price"] ??
                shapeError(t, draft.tiers[0]?.unit_price ?? "")
              }
            />
          ) : null}
          <TierLadder
            // A single block draws its price above, so the ladder starts at the
            // *Add tier* button and grows the bounds into view. Two or more and
            // it draws every row, because every bound is now a real question.
            tiers={draft.tiers.length === 1 ? [] : draft.tiers}
            fieldErrors={props.fieldErrors}
            onChange={(tiers) =>
              props.onPatch({
                tiers:
                  draft.tiers.length === 1
                    ? // Growing 1 → 2. The flat price becomes block ONE and
                      // keeps its money; block one's upper bound goes blank
                      // because only the clerk knows where it ends, and
                      // guessing a rate boundary is inventing one. These are
                      // the same two rows `tiered` produces from its own first
                      // *Add tier*, so the two structures behave alike.
                      [{ ...(draft.tiers[0] as TierDraft), from_qty: "0", to_qty: "" }, ...tiers]
                    : tiers,
              })
            }
          />
          {props.fieldErrors["structure.tiers"] !== undefined && (
            <RefusalStrip role="alert">{props.fieldErrors["structure.tiers"]}</RefusalStrip>
          )}
        </>
      ) : null}
      {/* ⚠ **NO RATE FIELD AT ALL ON THE CHARGE BASIS, AND THAT IS A DECISION
          RATHER THAN AN OMISSION.** A percentage of MONEY is already money; a
          price per gallon beside it invites a number that cannot be right, and
          `CR-130-BRC07` §3 has the server REFUSE one BY NAME rather than
          ignore it. Nothing is drawn, so nothing can be typed. */}
      <CheckboxField
        id="percent-confirm-over-100"
        // US-RAT-007 TC-6: above 100 % the server refuses UNLESS this explicit
        // confirmation rides with the request. It is a confirmation of the
        // server's warning, not a client-side bound.
        label={t("rating.percentOfService.confirmOver100")}
        checked={draft.confirm_percent_over_100}
        onChange={(confirm_percent_over_100) => props.onPatch({ confirm_percent_over_100 })}
      />
      {/* ── WHERE TAXABILITY IS DECIDED · `CR-130-BRC07` §5 ─────────────────
          The Product Owner asked for *"a check for tableble or non tablebale
          in this"*. It is NOT built here, and the decision log of 2026-09-22
          carries the two independent reasons in full — the switch already
          exists on the TAX (`taxes.applies_to_services`, read by
          `resolution.py`, which also narrows the base), and a second one here
          would move ❄️ FROZEN **B4.2**, under which taxability is a property
          of the LINE'S KIND.

          ⚠ **WHAT SHIPS IS WHERE, NEVER WHY.** B14 rule 33 puts RATIONALE at
          ZERO WORDS ON SCREEN, and rationale is REMOVED rather than shortened
          — so the sentence names Settings and stops. A clerk hunting the
          switch is sent to it instead of concluding there is none. */}
      <MoreAbout>
        <Note>{t("rating.percentOfService.taxNote")}</Note>
      </MoreAbout>
    </Panel>
  );
}

/**
 * DEF-RAT-5718 — **THE DAY THE CURRENT RATE WILL STOP**, or `null` when nothing
 * will be closed.
 *
 * PO, in the beta, verbatim: *"i want to change the rate from tomorrow - eisting
 * rates say it is valid until 31 dec"*. Filing a new version closes the previous
 * window the day before the new one opens — correct, and what BR-RAT-037
 * requires, and **said nowhere.** A rate whose own screen reads *valid until 31
 * December* stops on the 17th of September and the clerk learns it afterwards.
 *
 * ⚠ **IT MIRRORS THE SERVER'S CONDITION EXACTLY RATHER THAN APPROXIMATING IT.**
 * `services.create_rate_schedule_version` closes only when
 * `effective_to IS NULL OR effective_to >= new_from`; a screen that said
 * *"current rate ends"* on a version that has ALREADY ended before the new date
 * would be announcing a change that will not happen. The two scalars this reads
 * are served for exactly this, off `latest_version` — the row the server
 * closes — and not off `current_version`, which is a different row whenever a
 * future-dated version is already filed.
 *
 * The arithmetic is a calendar day, done on the ISO string so nothing passes
 * through a timezone: `DateCell`'s calendar-date law, and the reason
 * `effective_from` is a raw `YYYY-MM-DD` end to end.
 */
export function currentRateEndsOn(
  detail: ScheduleDetail | null,
  effectiveFrom: string,
): string | null {
  if (detail === null || !/^\d{4}-\d{2}-\d{2}$/.test(effectiveFrom.trim())) {
    return null;
  }
  const from = detail.closing_version_effective_from ?? null;
  if (from === null || from >= effectiveFrom.trim()) {
    // Nothing is in force before the new date, so nothing is being closed.
    // (The server refuses `new_from <= previous.effective_from` outright.)
    return null;
  }
  const to = detail.closing_version_effective_to ?? null;
  if (to !== null && to < effectiveFrom.trim()) {
    return null; // it has already ended; the server will not touch it
  }
  const day = new Date(`${effectiveFrom.trim()}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - 1);
  return day.toISOString().slice(0, 10);
}

/**
 * CR-087 · **WHY EACH ACCOUNT COULD NOT BE PRICED — a column the server has
 * counted all along and no screen read.**
 *
 * `selectors.impact_figures` builds a `{reason: count}` tally at five call
 * sites and serves it as `unpriced_reasons`; the whole front end read it
 * nowhere. What a clerk got instead was the trailing clause of one sentence —
 * *"no read, a read in another unit, or a base charge a bill would refuse"* —
 * a LIST OF POSSIBILITIES over a screen that knew the answer. That clause is
 * deleted with this build, so the sentence and the panel cannot say different
 * things.
 *
 * ⚠ **TWO THINGS THE REASON KEYS FORCE, AND BOTH ARE B14 RULE 31.** They are
 * internal codes, and one FAMILY of them carries a Python exception CLASS NAME
 * (`engine:<ExceptionClass>`). Neither may reach a clerk, so every code is
 * translated through the catalogue and the whole `engine:*` family collapses
 * into ONE sentence rather than rendering a class name. A code this screen has
 * never met falls back to *reason not recorded* — never to the code itself.
 */
export function unpricedReasonKey(code: string): string {
  const stem = code.startsWith("engine:") ? "engine" : code;
  const known = [
    "consumption_read_unwired",
    "no_metered_consumption",
    "base_charge_refused",
    "no_percentage_from_zero_before",
    "no_affected_accounts",
    "engine",
  ];
  return `rating.rate.impact.reason.${known.includes(stem) ? stem : "unknown"}`;
}

/**
 * One rendered string per figure, or `null` for NOT COMPUTED.
 *
 * ⚠ **`null` IS RETURNED, NEVER `"0"` OR `"0.00%"`** — the same third state the
 * server serves and for the same reason (DEF-434): a zero on this panel reads
 * as *"this rate change affects nobody"*, which is the one thing a filing that
 * nobody could measure must not say. The panel renders the em-dash and the
 * reason instead.
 *
 * The accounts row is served even when there is nothing to compare, because the
 * count is a fact about the schedule rather than about the change — a schedule
 * with one version and 914 accounts affects 914 accounts and changes none of
 * their bills.
 */
export function impactValues(
  impact: RateChangeImpact | null,
  detail: ScheduleDetail | null,
  t: Translator,
): Record<string, string | null> {
  const accounts =
    impact !== null
      ? impact.accounts_affected
      : detail !== null
        ? detail.applied_to_accounts
        : null;
  const plans = impact !== null ? impact.accounts_by_plan.length : (detail?.used_by_plans ?? 0);
  return {
    accounts: accounts === null ? null : t("rating.rate.impact.accountsValue", { accounts, plans }),
    billChange:
      impact === null || impact.worst_case_pct_display === null
        ? null
        : t("rating.rate.impact.billChangeValue", {
            worst: impact.worst_case_pct_display,
            average: impact.average_pct_display ?? CELL_NONE,
            change: impact.average_change_display ?? CELL_NONE,
          }),
    revenue:
      impact === null || impact.annualised_revenue_change_display === null
        ? null
        : t("rating.rate.impact.revenueValue", {
            annual: impact.annualised_revenue_change_display,
            monthly: impact.monthly_revenue_change_display ?? CELL_NONE,
          }),
    // "Accounts over threshold" is CR-013's fourth figure and it is the count of
    // accounts whose own bill change is above the bar. The endpoint serves the
    // WORST case rather than a per-account tally, so this row reports how many
    // of the affected accounts were priced at all — which is the honest half —
    // and the tally itself rides with OQ-319's answer about what the bar reads.
    overThreshold:
      impact === null || !impact.comparable
        ? null
        : t("rating.rate.impact.pricedValue", {
            priced: impact.accounts_priced,
            affected: impact.accounts_affected,
          }),
  };
}

/**
 * **A RATE ON SCREEN IS FOUR DECIMAL PLACES** — PO ruling 2026-08-27, verbatim:
 * *"A rate is not money and not a quantity - 4 decimal places"*.
 *
 * ⚠ AMENDED 2026-10-02 (PO: *"Show unit prices with up to 4 decimals and keep
 * every total at 2."*): the pad is back to TWO, not four — `0.0425` keeps its
 * four, `3.200000` reads `3.20`. The examples below are the old rule's.
 *
 * `moneyIn`'s arithmetic, one column further right: strip the zeros a storage
 * column pads with, then pad back to four. Lossless and string-only — there is
 * no `Number()` here and there must not be, because this figure is SHOWN.
 * `3.200000` → `3.2000` · `0.09` → `0.0900` · `0.14205` → `0.14205`, kept whole
 * rather than rounded, so a figure we cannot render at four places is visible
 * instead of quietly altered.
 *
 * ⚠ **IT IS A DISPLAY FUNCTION AND NOTHING POSTS ITS OUTPUT.** The draft keeps
 * the clerk's own bytes; this is only ever read by the review table.
 */
/**
 * `DEF-RAT-8742` — **A BLOCK BOUND ON SCREEN CARRIES NO PADDING ZEROS.** The
 * server stores a quantity to six places and the review printed it raw:
 * `0.000000 kW and above`. String-only, like `rateIn`: `0.000000` → `0`,
 * `500.500000` → `500.5`, `1000` → `1000`. Display only; nothing posts it.
 */
export function quantityIn(value: string | null | undefined): string {
  const raw = (value ?? "").trim();
  if (!/^-?\d+\.\d+$/.test(raw)) {
    return raw;
  }
  return raw.replace(/0+$/, "").replace(/\.$/, "");
}

export function rateIn(value: string | null | undefined): string {
  const raw = (value ?? "").trim();
  if (raw === "") {
    return CELL_NONE;
  }
  if (!/^-?\d+\.\d+$/.test(raw)) {
    return raw; // no decimal point, or mid-typing bytes — hand it back untouched
  }
  const [whole, fraction] = raw.split(".");
  const kept = fraction.replace(/0+$/, "");
  // PO 2026-10-02 — *"Show unit prices with up to 4 decimals and keep every
  // total at 2."* The floor is money's two (`RATE_MIN_DISPLAY_DECIMALS`, the
  // shared unit-price rule in `MoneyCell`), so `0.09` reads `0.09` and
  // `3.200000` reads `3.20` where both read four places before the ruling.
  return `${whole}.${kept.padEnd(RATE_MIN_DISPLAY_DECIMALS, "0")}`;
}

/** One line of the review's RATES table: what it is, what is in force, what
 *  this version will store. */
export interface ReviewRateRow {
  key: string;
  label: string;
  before: string;
  after: string;
}

/**
 * `DEF-RAT-5826` · **THE RATES A VERSION WILL STORE — FOR ALL SEVEN
 * STRUCTURES, NOT FOR THE TWO THAT HAPPEN TO USE `tiers`.**
 *
 * The review step's own hint is *"Check what will be stored, then activate"*,
 * and this table mapped `draft.tiers`, which only `flat` and `tiered` ever
 * fill. Everything else drew the one empty tier the draft is seeded with:
 *
 *   · a time-of-use schedule with two seasons and four priced windows, after
 *     **47 acts** of typing, reviewed as `0 kWh and above · — · —`
 *   · a demand schedule carrying `0.0850` and `14.5000` reviewed the same way
 *   · so did seasonal, and so did capacity
 *
 * **Four of the seven asked a clerk to approve a page showing nothing**, and
 * then activated a live price off that approval.
 *
 * ⚠ **EVERY ROW'S LABEL DISTINGUISHES IT FROM ITS SIBLINGS, AND THAT IS THE
 * PART A WEAKER FIX GETS WRONG.** *A price appears* passes on a screen showing
 * one season's prices twice over. So a time-of-use row names its SEASON, its
 * WINDOW and its hours, and a seasonal row names its season — which is what
 * lets the test assert a whole composed string against a fixture whose two
 * seasons carry DIFFERENT ladders.
 *
 * ⚠ **THE `before` SIDE IS THE VERSION IN FORCE, MATCHED BY NAME AND NOT BY
 * POSITION** wherever a name exists. The tier ladder has no names and is
 * matched by index, exactly as it always was; seasons and windows have labels,
 * and matching those by index would print last year's summer price against
 * this year's winter the first time a utility reorders them.
 */
export function reviewRateRows(
  draft: ScheduleDraft,
  inForce: VersionRow | null,
  t: Translator,
): ReviewRateRow[] {
  const stored = inForce?.structure ?? null;
  const cell = (value: string | null | undefined): string => rateIn(value);
  const named = (label: string, fallback: string): string =>
    label.trim() === "" ? fallback : label.trim();

  switch (draft.model) {
    case "time_of_use": {
      // Ordered by the SEASON that owns the window, so the table reads the way
      // the editor above it is nested (`BR-RAT-1017`, `DEF-RAT-5736`).
      const rows: ReviewRateRow[] = [];
      const seasonOf = (key: string) => draft.seasons.find((season) => season.key === key) ?? null;
      const ordered = [
        ...draft.seasons.flatMap((season) =>
          draft.windows
            .map((window, index) => ({ window, index }))
            .filter((row) => row.window.season_key === season.key),
        ),
        // A window whose season was removed still has a price and still posts,
        // so it is reviewed rather than dropped — the editor shows it too.
        ...draft.windows
          .map((window, index) => ({ window, index }))
          .filter((row) => seasonOf(row.window.season_key) === null),
      ];
      for (const { window, index } of ordered) {
        const seasonLabel = named(
          seasonOf(window.season_key)?.label ?? "",
          t("rating.rate.review.unnamed"),
        );
        const match =
          (stored?.windows ?? []).find(
            (row) =>
              (row.season ?? "") === (seasonOf(window.season_key)?.label ?? "") &&
              row.label === window.label,
          ) ?? null;
        rows.push({
          key: `window:${index}`,
          label: t("rating.rate.review.touRow", {
            season: seasonLabel,
            window: named(window.label, t("rating.rate.review.unnamed")),
            start: window.start_time,
            end: window.end_time,
          }),
          before: match === null ? CELL_NONE : cell(match.unit_price),
          after: cell(window.unit_price),
        });
      }
      return rows;
    }
    case "seasonal":
      return draft.seasons.map((season) => {
        const match =
          (stored?.tiers ?? []).find((row) => (row.season ?? "") === season.label) ?? null;
        return {
          key: `season:${season.key}`,
          label: named(season.label, t("rating.rate.review.unnamed")),
          before: match === null ? CELL_NONE : cell(match.unit_price),
          after: cell(season.unit_price),
        };
      });
    case "demand": {
      const rows: ReviewRateRow[] = [
        {
          key: "demand:energy",
          label: t("rating.demand.energyLabel"),
          before: cell(stored?.demand?.energy_rate_per_kwh),
          after: cell(draft.demand.energy_rate_per_kwh),
        },
        {
          key: "demand:demand",
          label: t("rating.demand.demandLabel"),
          before: cell(stored?.demand?.demand_rate_per_kw),
          after: cell(draft.demand.demand_rate_per_kw),
        },
      ];
      // The two OPTIONS are reviewed only where the version states them, so an
      // ordinary demand schedule keeps two rows (B14 rule 32's budget) and a
      // schedule that carries a penalty shows the figure it will store.
      if (draft.demand.pf_penalty_enabled || stored?.demand?.pf_penalty_enabled) {
        rows.push({
          key: "demand:pf",
          label: t("rating.demand.pfRateLabel"),
          before: cell(stored?.demand?.pf_penalty_rate_per_kw),
          after: draft.demand.pf_penalty_enabled
            ? cell(draft.demand.pf_penalty_rate_per_kw)
            : CELL_NONE,
        });
      }
      if (draft.demand.ratchet_enabled || stored?.demand?.ratchet_enabled) {
        rows.push({
          key: "demand:ratchet",
          label: t("rating.demand.ratchetPctLabel"),
          before: cell(stored?.demand?.ratchet_pct),
          after: draft.demand.ratchet_enabled ? cell(draft.demand.ratchet_pct) : CELL_NONE,
        });
      }
      return rows;
    }
    case "capacity":
      return [
        {
          key: "capacity:rate",
          // BR-RAT-022 — the unit is the TENANT's own word ("panel", "kW
          // block"), so the row is labelled with it and falls back to the
          // field's own label when nothing has been typed yet.
          label: named(draft.capacity.unit_label, t("rating.capacity.rateLabel")),
          before: cell(stored?.capacity?.rate_per_unit),
          after: cell(draft.capacity.rate_per_unit),
        },
      ];
    case "percent_of_service": {
      // `CR-130-BRC07` — **THE BASIS IS REVIEWED FIRST, AND IT IS THE ROW THAT
      // MATTERS MOST ON THIS STEP.** `90%` means two entirely different bills
      // depending on which number it is taken of, so a comparison that shows
      // the percentage moving and not the basis moving is a comparison that
      // hides the change. `basisKindText` renders both sides through the same
      // catalogue keys the card's own control uses, so a clerk reads the same
      // two words on step 3 and on step 5.
      const basisKindText = (value: string | null | undefined): string =>
        value === null || value === undefined || value.trim() === ""
          ? CELL_NONE
          : t(`rating.percentOfService.basisKind.${value}`, { defaultValue: value });
      const rows: ReviewRateRow[] = [
        {
          key: "percent:basisKind",
          label: t("rating.percentOfService.basisKindLabel"),
          // A version stored before the column existed is `usage` — that is
          // what it has been billing and what the backfill writes BY NAME
          // (§2). It is not an absence and must not print as one.
          before:
            stored === undefined || stored === null
              ? CELL_NONE
              : basisKindText(stored.percent_basis ?? PERCENT_BASIS_USAGE),
          after: basisKindText(draft.percent_basis),
        },
        {
          key: "percent:value",
          label: t("rating.percentOfService.percentLabel"),
          // A PERCENTAGE, not a rate: hard rule 2 displays one at two places,
          // so this is the clerk's own bytes rather than `rateIn`'s four.
          before: stored?.percent ?? CELL_NONE,
          after: draft.percent.trim() === "" ? CELL_NONE : draft.percent,
        },
      ];
      if (draft.percent_basis !== PERCENT_BASIS_CHARGE) {
        // ⚠ **THE RATE IS REVIEWED ONLY WHERE THERE IS ONE.** On the charge
        // basis there is no price per unit at all — §3 has the server refuse
        // one by name — so a row reading "—" would be inviting a clerk to look
        // for a field that is deliberately absent.
        for (const [index, tier] of draft.tiers.entries()) {
          const match = (stored?.tiers ?? []).filter(
            (row) => row.size_class === null || row.size_class === undefined,
          )[index];
          rows.push({
            key: `percent:rate:${index}`,
            label:
              draft.tiers.length === 1
                ? t("rating.rate.flat.priceLabel")
                : tier.to_qty.trim() === ""
                  ? t("rating.rateDetail.chart.bandOpen", { from: quantityIn(tier.from_qty), uom: draft.uom })
                  : t("rating.rateDetail.chart.band", {
                      from: quantityIn(tier.from_qty),
                      to: quantityIn(tier.to_qty),
                      uom: draft.uom,
                    }),
            before: match === undefined ? CELL_NONE : cell(match.unit_price),
            after: cell(tier.unit_price),
          });
        }
      }
      return rows;
    }
    default:
      // `flat` and `tiered` — the ladder, unchanged in shape from the row this
      // function was extracted from.
      return draft.tiers.map((tier, index) => {
        // The BLOCK label is the two bounds the clerk typed with the unit
        // beside them — a string put together, never a sum. `and above` is
        // its own sentence rather than a dash into nothing.
        const label =
          tier.to_qty.trim() === ""
            ? t("rating.rateDetail.chart.bandOpen", { from: quantityIn(tier.from_qty), uom: draft.uom })
            : t("rating.rateDetail.chart.band", {
                from: quantityIn(tier.from_qty),
                to: quantityIn(tier.to_qty),
                uom: draft.uom,
              });
        const match = (stored?.tiers ?? []).filter(
          (row) => row.size_class === null || row.size_class === undefined,
        )[index];
        return {
          key: `${tier.from_qty}:${index}`,
          label,
          before: match === undefined ? CELL_NONE : cell(match.unit_price),
          after: cell(tier.unit_price),
        };
      });
  }
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-005@0b56fac (story+rules snapshot hash — EP-RAT-02 lead story; co-stories US-RAT-006@0b56fac · US-RAT-007@0b56fac · US-RAT-010@f69a661)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S11) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 the shared field kit (BR-SHL-017) designs no TIME control, so a TOU window's start/end hours are typed as HH:MM text and parsed server-side — reported rather than growing a second, screen-local widget · E4 the seasonal model's per-season TIER sets (the richer of the two shapes the server accepts) are not editable here: the editor captures one flat price per season, which is the shape US-RAT-007 TC-4 specifies; per-season tier tables are reported as a gap · E3 SUPERSEDED 2026-08-21 (DEF-471): `account_types` IS served (apps/customers/lookups.py:441) and `account_type_id` IS in SCHEDULE_FIELDS, so the S11 step-1 customer class is a picker nobody has wired, not an absence — it still renders as a note and is not posted, and the note now cites DEF-471 · E4 `approved_by` is never written by this screen: BR-RAT-031 as-modified makes it out-of-system metadata and no control should imply an in-system approval exists
// AMENDED: 2026-08-21 by the CR-013 P1 lane (RAT-03, §18 row 6) — FIVE steps, not four.
//   `Base rates` is NEW (step 2, DEF-356): the per-connection-size matrix, rows from
//   `service_size_classes`, editable column = minimum bill, base column READ-ONLY and
//   ATTRIBUTED per BR-RAT-088 · unit of measure is a SELECT over service-scoped `uoms`
//   (DEF-355, BR-TEN-078) · `Base only` drawn DISABLED with its reason (DEF-297) ·
//   step 4 gains the mandatory impact analysis (four named figures, three of them
//   absences — DEF-434) and BR-RAT-082's regulator-filing capture (four new columns).
// exceptions (CR-013 P1): E4 "increase all by %" is NOT built — an uplift is money
//   arithmetic under ❄️ FROZEN B4 rounding, so it belongs where `_changed_price` lives
//   (DEF-432) · ✅ DEF-431 CLOSED (Wave E): the base is per SIZE, resolved by
//   `./baseCharge` from `charge_row.size_amounts` and shared with RAT-02 so the two
//   screens cannot disagree; a code with no per-size rows still shows its one amount
//   and SAYS SO · ✅ DEF-433 CLOSED (Wave E): step 3 states a per-size tier override
//   beside the ladder it differs from — r10's 2" water row, 3.45 / 5.10 / 7.70 — seeded
//   from the base prices so a group is a complete contiguous ladder by construction.
//   ⚠ E4 THE OVERRIDE IS STORED AND DOES NOT REACH A BILL: `pricing_inputs` takes a
//   `size_class` and `apps/billing/gather.py` passes none (DEF-484), which the server
//   returns as a notice on every save that stores one and this step prints
//   · ✅ DEF-434 CLOSED (Wave F): all four of step 4's figures are SERVED —
//   `GET /rate-schedules/{id}/impact` prices every affected account twice through
//   `engine.price_period`, and an account that cannot be priced is COUNTED rather than
//   priced at zero. ✅ DEF-435 CLOSED the same commit: the 10% bar lives in
//   `apps/rating/impact.py`, `POST /rate-schedules/{id}/versions` refuses above it, and
//   this screen reads `second_approval_threshold_pct_display` off the server —
//   `RATE_CHANGE_SECOND_APPROVAL_PCT` survives as the documented mirror. ⚠ E3 THE
//   REFUSAL ITSELF IS OQ-318 (BR-RAT-031 as-modified left nowhere for a second approval
//   to land) and the per-CUSTOMER-CLASS breakdown part 1 asks for is still unserved —
//   named on the panel as `by_class_unavailable_reason`, never answered with the
//   by-PLAN cut (OQ-319) · E3 step 5's worked
//   example at low/typical/high usage needs an endpoint that prices an unsaved draft
//   (DEF-436) · E4 `tariff_versions.base_charge` is CARRIED and re-posted though no
//   control edits it — `_guard_base_charge_code` is self-activating per tenant, so a
//   tenant that has not declared an `is_base` code is still billed from that column and
//   dropping it from the payload would blank a live base on the next draft save
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
