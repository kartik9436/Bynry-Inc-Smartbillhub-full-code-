// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-001 (S9 Plans tab) · US-RAT-004 (S9 Rate schedules tab) · US-RAT-008 (S9
//           Charge codes) · US-RAT-009 (S9 Taxes & fees) · US-RAT-010 (S9 History)
//           Screens: S9, S10, S11, S12, S13
// Change:   CR-013 part 3 — RATING_TABS gains `discounts` (§18 row 10) in r10's own
//           position, and `discountStatusTone` for BR-RAT-072's four statuses.
//           ⚠ Rate changes is UNTOUCHED — that reconciliation is OQ-286.
// Rules:    BR-SHL-025 (server-authoritative RBAC — the gate is `GET /me/permissions`, and
//           hiding is convenience only) · BR-SHL-020 (plain-language failure, six A18 states) ·
//           BR-SHL-023 (ONE money formatter) · BR-SHL-034 (dates only via the shared formatter) ·
//           BR-RAT-024 (services ⊆ the tenant-enabled catalog; a disabled one renders
//           disabled, never hidden) · BR-RAT-030 (plan lifecycle) · BR-RAT-031 (schedule
//           status is DERIVED; there is no approval state) · BR-RAT-035 (deactivate-first)
// ───────────────────────────────────────────────────────
// The pieces every Plans & Rates surface composes: the tab vocabulary, the one
// RBAC read, the decimal-SHAPE guard, and the status→tone maps.
//
// The money law of this whole feature, stated once, here:
//
//   A rate is a decimal STRING from `/plans`, `/rate-schedules`, `/charges`,
//   `/taxes` and `/rate-changes`, and it stays a string until it is either
//   rendered by MoneyCell or posted back. This module therefore contains no
//   Number(), no parseFloat, no toFixed, no arithmetic — and `isDecimalShape`
//   is a SHAPE test, never a bounds test. Every bound (≥ 0, ≤ 100 %, tier
//   contiguity, window coverage, season coverage) belongs to the server, which
//   already enforces it and answers a B12 §3 envelope the screens render
//   verbatim. A client-side copy of those bounds would be a second, drifting
//   rulebook over money — exactly what CLAUDE.md #2 forbids.
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { LookupEntry, MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { TextField } from "@/components/FormModal";
import type { ButtonSize, ButtonVariant } from "@/components/buttonKit";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
// `CR-130-BRC07` §8.1 — the SERVER's unit-scope rule, imported rather than
// re-derived. `selectors.uom_scope_filter` is the law and this is that law
// already written once on the client; its own docstring says *"Change one,
// change both"*, so `scheduleUomOptions` LAYERS on it and never edits it.
import { activeUomOptions } from "@/features/tenancy/SettingsServicesTab";

/**
 * DEF-356 · the connection sizes a screen may OFFER — the tenant's own
 * `service_size_classes`, ACTIVE rows only.
 *
 * ⚠ **MOVED HERE 2026-08-28 (DEF-2190) AND RE-EXPORTED FROM `RateScheduleWizard`.**
 * Three surfaces now ask this one question — RAT-03's size matrix, CHG-02's
 * per-size amount table, and AST-05's connection-size picker — and two copies
 * of "which sizes may a person choose" is how one screen starts offering a size
 * another refuses. A DEACTIVATED size is not offered for a NEW row; it is not
 * erased from a row that already exists, which is `ChargeCodeAmount`'s own
 * retire-survival rule (*"a size Settings RETIRES must not vanish from a
 * schedule that already priced it"*) and the server honours the same union.
 */
export function activeSizeClasses(entries: readonly LookupEntry[]): LookupEntry[] {
  return entries.filter((entry) => entry.active);
}

/**
 * CR-065 · the sizes a screen may offer **for ONE utility service** — the
 * Product Owner's own words, 2026-09-02, sent with a screenshot of the Fire
 * rate schedule pricing *Electric CT-metered*: *"This is where we are setting
 * rates for fire  you should show only capacity for fire ."*
 *
 * THREE CLAUSES, AND EACH ONE IS A THING THAT WOULD OTHERWISE GO WRONG:
 *
 *   1. **ACTIVE only** — `activeSizeClasses`' rule, unchanged and reused rather
 *      than restated.
 *   2. **tagged to THIS service, OR untagged.** `null` on a size class means
 *      *"nobody has said"*, not *"belongs to nothing"*: `BR-TEN-071` forbids
 *      deleting a tenant's own row, so a size a utility added and nobody has
 *      tagged must keep appearing everywhere. This is the same union the server
 *      states once in `selectors.service_scope_filter`, and the server is where
 *      the WRITE is refused — this decides only what a picker OFFERS.
 *   3. **plus anything this schedule ALREADY PRICES.** Before today every screen
 *      offered all sixty sizes, so a schedule may hold a row for a size that
 *      belongs to another service. Dropping it from the table would hide a
 *      priced row while leaving it in the payload — the row would still be
 *      saved and nobody could see or delete it. It is the same argument as
 *      `ChargeCodeAmount`'s retire-survival rule (*"a size Settings RETIRES
 *      must not vanish from a schedule that already priced it"*), one axis
 *      along.
 *
 * An EMPTY `serviceCode` means the screen has not chosen a service yet, and
 * every active size is offered — a wizard on step 1 has nothing to filter by.
 */
export function sizeClassesForService(
  entries: readonly LookupEntry[],
  serviceCode: string,
  alreadyPriced: readonly string[] = [],
): LookupEntry[] {
  const priced = new Set(alreadyPriced);
  return activeSizeClasses(entries).filter((entry) => {
    if (serviceCode === "" || priced.has(entry.code)) {
      return true;
    }
    // `undefined` is "this list publishes no tag" and `null` is "nobody has
    // said"; both are offered, and they are different facts (see `LookupEntry`).
    return entry.service == null || entry.service.code === serviceCode;
  });
}

// ── Routing (the AppShell's own child paths — matched, never re-invented) ──

export const PLANS_RATES_ROUTE = "/plans-rates";
export const DASHBOARD_ROUTE = "/dashboard";

/**
 * Settings → Services, where a utility switches a service on (`DEF-RAT-5692`).
 *
 * `services` is an id in `SettingsPage.tsx`'s `SETTINGS_TABS` and is NOT in
 * `LEGACY_SETTINGS_TAB_PATHS`, so `settings/:tab` mounts it directly. It is
 * also one of the server's own `CHECKLIST_TARGETS`.
 *
 * ⚠ **A SECOND COPY OF A ROUTE IS HOW A LINK ROTS SILENTLY**, so
 * `servicesSettingsRoute.test.ts` asserts that `SETTINGS_TABS` still carries an
 * id spelled exactly this way. A tab renamed without that test would leave this
 * link opening a screen that says nothing is here, with `tsc` and every other
 * check green — hard-won law 2 in its other direction.
 */
export const SERVICES_SETTINGS_ROUTE = "/settings/services";

/**
 * The S9 tab set. The first four ids are a CONTRACT with `SHELL_NAV`'s
 * `plans-rates` children (AppShell.tsx) and with the S62 checklist's deep
 * links, so the sidebar sub-items land on the right tab instead of a tab frame
 * that re-defaults to Plans.
 *
 * `history` is the fifth: US-RAT-001 names "History → rate-change log view" as
 * an S9 exit and EP-RAT-04's capability matrix gives it a row, but BR-SHL-001's
 * ratified sidebar has only four children — so it is reachable from this tab
 * strip and is NOT added to the nav config. Reported, not resolved.
 */
export interface RatingTab {
  id: string;
  path: string;
  labelKey: string;
  /**
   * BR-SHL-044 (b): the guidance under the strip is per-TAB, so it belongs to
   * the tab rather than to the page. Absent on `history`, which the prototype
   * does not draw in the strip at all.
   */
  explainerKey?: string;
}

export const RATING_TABS: readonly RatingTab[] = [
  {
    id: "plans",
    path: PLANS_RATES_ROUTE,
    labelKey: "rating.tab.plans",
    // CR-167-BRC10 round 2 task 6 (DEF-RAT-9333) — NO explainer: images 01–03
    // draw none, as on every other tab. The key is retired from every catalogue.
  },
  {
    id: "rates",
    path: `${PLANS_RATES_ROUTE}/rates`,
    labelKey: "rating.tab.rates",
    // `DEF-RAT-8840` — NO explainer, as Charge codes: images 01–07 draw none,
    // and the sentence named five of the seven methods. Its key is retired
    // from every catalogue.
  },
  {
    id: "charge-codes",
    path: `${PLANS_RATES_ROUTE}/charge-codes`,
    labelKey: "rating.tab.chargeCodes",
    // CR-156-BRC10 wave B — NO explainer: the PO's list decision of 2026-10-01
    // drops *"the explanatory paragraph above the table"* (B14 rules 32/33;
    // images 01–05 draw none). The key is retired from every catalogue.
  },
  /**
   * CR-013 part 3, `09-screen-inventory.md` §18 **row 10** — *"the tab does not
   * exist; the 6 tables do"*. Placed HERE, between Charge codes and Taxes &
   * fees, because that is r10's own tab order (§1's table, read off the running
   * canvas).
   *
   * ⚠ **THIS MAKES SIX TABS WHERE THE DRAWING HAS FIVE, AND THAT IS AN OPEN
   * QUESTION FOR THE PRODUCT OWNER, NOT A THING THIS LANE DECIDED.** §18 states
   * it plainly: what is built is `Plans · Rate schedules · Charge codes ·
   * Taxes & fees · RATE CHANGES` and what r10 draws is `… · DISCOUNTS`.
   * `RateChangesTab` is real, wired, and has no counterpart in the drawing;
   * Discounts was the reverse until this commit. **Neither the addition nor the
   * removal is decided** — r10's rate detail carries a `Versions & filings` tab
   * which may be where rate changes belong, and *"building the Discounts tab
   * without ruling on Rate changes leaves the product with six tabs and the
   * drawing with five"*. Nothing here removes or moves Rate changes; the tab
   * count is REPORTED rather than quietly reconciled.
   */
  {
    id: "discounts",
    path: `${PLANS_RATES_ROUTE}/discounts`,
    labelKey: "rating.tab.discounts",
    // CR-166-BRC10 round 2 task 5 (D14, DEF-RAT-9290) — NO explainer: images
    // 01–04 draw none, and the PO's list approval says "no overlay paragraph".
    // The key is retired from every catalogue.
  },
  {
    id: "taxes-fees",
    path: `${PLANS_RATES_ROUTE}/taxes-fees`,
    labelKey: "rating.tab.taxesFees",
    // CR-165-BRC10 task 5 (P21, DEF-RAT-9274) — NO explainer: images 01–03
    // draw none, as Charge codes and Rate schedules. The key is retired from
    // every catalogue.
  },
  { id: "history", path: `${PLANS_RATES_ROUTE}/history`, labelKey: "rating.tab.history" },
];

// The strip the page draws, and the one entry that is NOT in it. History is a
// destination rather than another view of the same records, so the prototype
// gives it a top-right button; RATING_TABS keeps all five because routing,
// deep-links and the sidebar contract are still defined over the whole set.
export const HISTORY_TAB = RATING_TABS[RATING_TABS.length - 1];
export const RATING_TAB_STRIP: readonly RatingTab[] = RATING_TABS.filter(
  (tab) => tab.id !== "history",
);

export const DEFAULT_RATING_TAB = "plans";

// ── How a tab's own action reaches the page header (US-SHL-020 addendum r2) ──

/**
 * The two halves a Plans & Rates tab hands back to the frame.
 *
 * This exists because the four tabs do NOT own their actions the same way.
 * `+ New plan` and `+ New rate schedule` are pure navigation and could have
 * been static config; `+ New charge code` and `+ New tax or fee` open a modal
 * held in a `useState` INSIDE the tab body, which no config value written in
 * the frame can reach.
 *
 * So the tab renders itself and hands the frame two things — the button it
 * owns and the content it owns — and the frame decides where each one goes.
 * State stays where it is declared, the frame acquires none of it, and the
 * header still gets its button (BR-SHL-044 (a)).
 */
export interface RatingTabParts {
  /**
   * The tab's primary action, rendered by the frame into the page header's
   * ONE primary slot. Omitted by a tab that offers none — the row still
   * renders, so the title does not shift (BR-SHL-044 (c)).
   */
  action?: ReactNode;
  /** Everything below the header: the table, its refusals, its modals. */
  body: ReactNode;
}

/**
 * The `render()` addendum r2 names. Required rather than optional on purpose:
 * a tab that quietly forgot to hand its action up would put the button
 * nowhere, and the compiler is the only reviewer guaranteed to catch that.
 */
export type RatingTabRender = (parts: RatingTabParts) => ReactNode;

/** BR-SHL-011's spirit: an unknown tab segment falls back, it never errors. */
export function ratingTabFromParam(raw: string | undefined): string {
  if (raw === undefined) {
    return DEFAULT_RATING_TAB;
  }
  return RATING_TABS.some((tab) => tab.id === raw) ? raw : DEFAULT_RATING_TAB;
}

// ── RBAC (BR-SHL-025) ──────────────────────────────────────────────────────

/** The A4 row that governs every surface in this feature. */
export const PLANS_RATES_PERMISSION = "plans_rates";

// The A4 cell vocabulary, exactly as the server serves it (identity A4_MATRIX).
export const CELL_NONE = "—";
export const CELL_VIEW = "View";

/**
 * THE access read (BR-SHL-025): the caller's own `plans_rates` cell from
 * `GET /me/permissions`, copied verbatim. Returns null when the read has not
 * answered — and null means "hide nothing": every endpoint still enforces its
 * own gate, and its 403 is the real boundary. A4 gives Billing Clerk and
 * Executive "View" here (US-RAT-001 TC-6, US-RAT-011 TC-7), so this is what
 * turns every write control into disabled-with-reason for them.
 */
export function ratingAccess(permissions: MyPermissions | null | undefined): string | null {
  if (permissions === null || permissions === undefined) {
    return null;
  }
  return (
    permissions.permissions.find((row) => row.code === PLANS_RATES_PERMISSION)?.access ?? CELL_NONE
  );
}

/** "View" (or an unknown non-Full cell) = read-only. Unknown access = not locked. */
export function ratingIsReadOnly(access: string | null): boolean {
  return access !== null && access !== "Full";
}

/** BR-SHL-003: a surface the role cannot reach at all is not drawn. */
export function ratingIsDenied(access: string | null): boolean {
  return access === CELL_NONE;
}

// ── Decimal SHAPE (never a bound — see the module note above) ──────────────

const DECIMAL_SHAPE = /^-?\d+(\.\d+)?$/;

/**
 * True when `raw` is a canonical decimal string the server can parse. Empty is
 * "not entered" and is the caller's business, not this function's.
 *
 * A LEADING MINUS IS LEGAL on purpose: BR-RAT-043 makes a plan discount a
 * charge rule with a NEGATIVE amount, so a client-side sign check would make
 * the ratified discount mechanism unusable. Where a value must be ≥ 0 the
 * SERVER refuses it (`rating.below_minimum`) and the screen renders that.
 */
export function isDecimalShape(raw: string): boolean {
  return DECIMAL_SHAPE.test(raw.trim());
}

/** The one shape error key, or null. Blank never errors here (required-ness is the server's). */
export function decimalShapeError(raw: string): string | null {
  const value = raw.trim();
  if (value === "" || isDecimalShape(value)) {
    return null;
  }
  return "rating.error.notDecimal";
}

/**
 * A decimal string on its way OUT: trimmed, or undefined when nothing was
 * typed. It is never re-formatted — what the user typed is what posts, so an
 * untouched round trip is byte-identical.
 */
export function decimalOut(raw: string): string | undefined {
  const value = raw.trim();
  return value === "" ? undefined : value;
}

/** A server decimal on its way IN. Null renders as an empty input, never "0". */
export function decimalIn(value: string | null | undefined): string {
  return value ?? "";
}

// ── Status pills ───────────────────────────────────────────────────────────

/** BR-RAT-030. Note what is absent: no "awaiting approval" tone, because no such state exists. */
export function planStatusTone(status: string): StatusTone {
  if (status === "published") {
    return "success";
  }
  return status === SCHEDULE_STATUS_ARCHIVED ? "warning" : "neutral";
}

/** BR-RAT-031: the schedule pill is DERIVED (active | draft | archived). */
/**
 * The one spelling of a rate schedule's archived state (`DEF-RAT-5693`).
 *
 * `ScheduleCard.status` is DERIVED by the server — `selectors.schedule_state`
 * answers `archived` when `tariffs.deleted_at` is set, `active` when a version
 * is in force and `draft` otherwise — so the string below is a CONTRACT with
 * that function, not a local convention. It is named here rather than typed
 * into each consumer because two of them now ask the same question: the status
 * pill's tone, and the plan builder's picker.
 */
export const SCHEDULE_STATUS_ARCHIVED = "archived";

export function scheduleStatusTone(status: string): StatusTone {
  if (status === "active") {
    return "success";
  }
  return status === "archived" ? "warning" : "neutral";
}

/** IS-1 deactivate-first, shared by the charge and tax catalogs. */
export function activeStatusTone(status: string): StatusTone {
  return status === "active" ? "success" : "neutral";
}

/**
 * BR-RAT-072's four discount statuses — and the fourth is why this is not
 * `activeStatusTone` with a different name.
 *
 * ⚠ **`suspended_funding_exhausted` TAKES THE DANGER TONE, AND THE REASON IS
 * MONEY.** CR-013 part 3: a discount that has spent its budget *"is neither
 * Active nor Retired, and the difference decides whether next month's bill is
 * reduced"* — it is **the one status in the product a BILL RUN can set**, and
 * the only way a utility learns that a subsidy programme stopped paying out is
 * by seeing it on this row. Rendering it in the same neutral grey as `draft`
 * would hide a live money event inside a pill that reads as "nothing to see".
 * `retired` is a decision someone made, so it warns rather than alarms.
 */
export function discountStatusTone(status: string): StatusTone {
  if (status === "active") {
    return "success";
  }
  if (status === "suspended_funding_exhausted") {
    return "danger";
  }
  return status === "retired" ? "warning" : "neutral";
}

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/**
 * A server enum rendered through the catalog — and rendered OPAQUE (its own
 * raw token) when the catalog has no entry. A status this app has never heard
 * of is data, not a missing translation, and must never surface as a key.
 */
export function enumLabel(t: Translator, stem: string, value: string | null): string {
  if (value === null || value === "") {
    return "—";
  }
  return t(`${stem}.${value}`, { defaultValue: value });
}

export function RatingStatusPill(props: { tone: StatusTone; stem: string; value: string | null }) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  return <StatusPill tone={props.tone}>{enumLabel(translate, props.stem, props.value)}</StatusPill>;
}

// ── Small layout pieces shared by the five surfaces ────────────────────────

/** The service tags on a plan row / rate card (BR-RAT-024 vocabulary). */
/**
 * The SERVICES INCLUDED badge — r10's own, and it had to be DECLARED.
 *
 * ── WHY THIS REPLACED FULL-NAME CHIPS (PO, 2026-08-21) ────────────────────
 * The PO put our screen beside r10's: *"service included you are using full
 * name and proto using letter with color - why that issue can you fix it"*.
 * r10 is THE reference (PO ruling 2026-08-16), and it draws a **20px square
 * per service, the service's colour, the initial in the page background** —
 * `.svc-tag{width:20px;height:20px;background:var(--dot);color:var(--color-bg)
 * ;font-size:10px;font-weight:800}` with a 2px gap.
 *
 * ⚠ ONE STAMPED DIVERGENCE: r10 sets `font-size:10px` and this uses `text-xs`,
 * which is **11px**. B14 rule 5 ruled the type scale and 10px is not a step on
 * it (`--text-xs` is the smallest). A 1px arbitrary value would be the first
 * crack in a scale whose whole value is that it has no exceptions, and 11px in
 * a 20px square is the same badge to any eye. G34 is the gate that refuses the
 * alternative. Three services fit on one
 * line where three name chips wrapped to two and pushed every row taller.
 *
 * ⚠ **THE LETTER CANNOT BE DERIVED FROM THE NAME, AND THAT IS THE WHOLE
 * REASON THIS MAP EXISTS.** `name[0].toUpperCase()` is the obvious
 * implementation and it is wrong on SIX of our eleven services: **Sewer, Solar
 * and Storm water** all give `S`, **Trash and Thermal/Heat** both give `T`,
 * and **Broadband and Battery** both give `B`. (Fire, added by `CR-063` on
 * 2026-09-02, is the one newcomer that collides with nothing — `F` was free —
 * which is why it keeps a single character where the OQ-273 four took two.) A tenant selling sewer and
 * solar would see two identical badges differing only in hue — which is
 * exactly the failure the storm-water hollow dot was introduced to fix
 * (PlansRates.css, OQ-273): hue alone is not a distinction a reader can rely
 * on, and a deuteranope cannot use it at all.
 *
 * ⚠ **SIX LETTERS ARE r10's, VERBATIM. FOUR ARE THIS LANE'S.** r10 draws
 * `E · W · G · S · T · B` and names no badge for storm water, solar,
 * thermal/heat or battery — the four services OQ-273 added after r10 was
 * drawn. They take a two-character badge in the same square, which keeps the
 * distinction legible without changing the shape r10 ratified. If the PO
 * rules different letters, this map is the only place that changes.
 *
 * The colour is the token the ten-service palette already declares, so a
 * service's dot on one screen and its badge on another can never disagree.
 */
const SERVICE_BADGES: Readonly<Record<string, { letter: string; token: string }>> = {
  // r10's six, taken from its own markup and its own `--dot` values.
  electric: { letter: "E", token: "--color-service-electric" },
  water: { letter: "W", token: "--color-service-water" },
  gas: { letter: "G", token: "--color-service-gas" },
  sewer: { letter: "S", token: "--color-service-sewer" },
  trash: { letter: "T", token: "--color-service-trash" },
  broadband: { letter: "B", token: "--color-service-broadband" },
  // The four OQ-273 added after r10 was drawn. Two characters, same square.
  storm_water: { letter: "St", token: "--color-service-storm-water" },
  solar: { letter: "So", token: "--color-service-solar" },
  thermal_heat: { letter: "Th", token: "--color-service-thermal-heat" },
  battery: { letter: "Ba", token: "--color-service-battery" },
  // CR-063 — the ELEVENTH service. **`F` is free**: the eleven letters are
  // E · W · G · S · T · B · St · So · Th · Ba · F, and no other service begins
  // with one. So fire keeps a SINGLE character, which is r10's shape, and needs
  // no two-character badge.
  //
  // ⚠ **THE HUE IS THE HARD PART AND THE ANSWER IS A SHAPE, NOT A NEW RED.**
  // Fire's obvious colour is red and red is taken twice over — `#ec3013` is
  // electric's dot AND the brand accent, and `tokens.css` records that
  // constraint in its own words. OQ-273's answer ratified the fill variant as a
  // GENERAL rule rather than a one-off (*"any service family that outgrows safe
  // hue separation gets a SHAPE variant"*), and storm water is the precedent:
  // it took a HOLLOW dot when it joined water's blue family. Fire is the
  // newcomer to electric's warm family and takes the same treatment — a deeper
  // red plus the ring — so a deuteranope reads ring-versus-disc at any size
  // instead of being asked to separate two reds at 6px.
  fire: { letter: "F", token: "--color-service-fire" },
};

/**
 * **THE ELEVEN, IN SEED ORDER** — Electric · Water · Gas · Sewer · Trash · Storm
 * water · Solar · Broadband · Thermal/Heat · Battery · Fire (`BR-RAT-024`
 * CONFIRMED-AS-AMENDED 2026-09-02; `CR-063` appended `fire` at position 11 and
 * renumbered nothing).
 *
 * ⚠ **THIS IS THE ORDER, AND `SERVICE_BADGES` ABOVE IS THE MEMBERSHIP — THEY
 * ARE TWO DIFFERENT FACTS AND THE TEST CHECKS THEY AGREE.** The badge map is
 * keyed by insertion for the palette's sake (r10's six, then OQ-273's four,
 * then fire), which puts broadband sixth; the SEED order puts it eighth. So a
 * screen listing services cannot just take `Object.keys(SERVICE_BADGES)` and a
 * lane adding a twelfth service must touch both — which is the point of
 * asserting the list rather than deriving it.
 *
 * ⚠ **HARD-WON LAW 2 IS WHY THIS IS EXPORTED AT ALL.** The front end typed the
 * service list out by hand in two places — `SignupWizard.tsx`'s tick-list and
 * the badge map here — so an eleventh service *did not appear on screen on its
 * own and failed SILENTLY*: the row exists, the API serves it, `tsc` and every
 * test pass, and the screen simply never offers it. The plan wizard's step 2
 * was a third such copy (five tick-boxes for a list of eleven) until `CR-087`
 * D1; it reads this now.
 */
export const SERVICE_CODES: readonly string[] = [
  "electric",
  "water",
  "gas",
  "sewer",
  "trash",
  "storm_water",
  "solar",
  "broadband",
  "thermal_heat",
  "battery",
  "fire",
];

/**
 * ── THE TENANT'S OWN SERVICES · BR-RAT-024 · `DEF-RAT-5691` / `DEF-RAT-5692` ──
 *
 * `GET /settings/services` serves ONE ROW PER ACTIVE PLATFORM SERVICE — all
 * eleven, on every tenant — with `enabled` saying which of them this utility
 * has switched on. **Four screens read that payload and none of them read the
 * flag**, so a utility with two services switched on was offered all eleven
 * everywhere it could filter or pick.
 *
 * PO ruling 2026-09-17, verbatim: *"in filter - we should only show activated
 * Utility services and not all that are available; same is the case in plan -
 * only activated utility services shouel ddiplayed"*.
 *
 * ⚠ **WHY THIS IS ONE FUNCTION AND NOT FOUR `.filter()` CALLS.** The Plans,
 * Rate schedules, Charge codes and Taxes & fees tabs each wrote the same
 * three-line `.map()` over `servicesQuery.data`, and **all four were wrong in
 * the same way** — which is what a copied expression does. A named function is
 * the thing that cannot drift, and `activatedServices.test.ts` is its contract.
 *
 * ⚠ **NOT `SERVICE_CODES`, WHICH IS THE PLATFORM CATALOGUE.** That list is the
 * eleven this product knows how to bill and is deliberately hand-written (see
 * its own note above). It is not a statement about any tenant, and reaching for
 * it here is how the plan wizard came to offer nine services the server
 * refuses.
 *
 * ⚠ **AN ABSENT PAYLOAD YIELDS NOTHING, NEVER EVERYTHING.** While the query is
 * in flight, or after it has failed, the honest answer is *we cannot say* — and
 * a filter is better empty for a moment than populated with values that cannot
 * match a row. `?? []` rather than a fallback to the catalogue, deliberately.
 */
export function activatedServices(
  rows: readonly TenantServiceRow[] | undefined,
): readonly TenantServiceRow[] {
  return (rows ?? []).filter((row) => row.enabled);
}

/**
 * The same set as the `{ value, label }` pairs a `TableFilterConfig` and the
 * field kit both take. The LABEL is the server's `name` — the tenant's own word
 * for the service — never a code and never a key looked up here, so a utility
 * that renames Water keeps its name in the filter it just used.
 */
export function activatedServiceOptions(
  rows: readonly TenantServiceRow[] | undefined,
): { value: string; label: string }[] {
  return activatedServices(rows).map((row) => ({ value: row.service, label: row.name }));
}

/**
 * ── `CR-130-BRC07` · THE TWO WAYS A PERCENTAGE CAN BE TAKEN ────────────────
 *
 * The WIRE values, never shown to a clerk (B14 rule 32 — no internal code in
 * clerk-facing copy). The words a person reads are
 * `rating.percentOfService.basisKind.*`.
 *
 * `usage` is FIRST and is the default, and both facts are deliberate. It is
 * what every percent schedule in the product does today — `CR-081` re-signed
 * six ❄️ FROZEN figures onto it on 2026-09-08 — and `CR-130-BRC07` §2 says
 * every stored schedule is migrated to it BY NAME rather than by default, so
 * no live bill moves. A control whose default was the other value would offer
 * to change a sewer bill by being opened.
 */
export const PERCENT_BASIS_USAGE = "usage";
export const PERCENT_BASIS_CHARGE = "charge";
export const PERCENT_BASIS_KINDS: readonly string[] = [
  PERCENT_BASIS_USAGE,
  PERCENT_BASIS_CHARGE,
];

/**
 * ── `CR-130-BRC07` §3 · **Based on** IS ASKED OF THE SERVER, NOT DERIVED HERE
 *
 * ⚠ **THIS FILE HELD A `basisServiceOptions()` THAT DERIVED THE LIST FROM
 * `/settings/services`, AND IT IS DELETED RATHER THAN KEPT AS A FALLBACK.**
 * Wave A landed `GET /rate-schedules/percent-basis-options` and its own
 * appendix (A.2) states the reason in the words both lanes have to agree on:
 * *"It exists so the derivation is not written a second time in TSX … hard-won
 * law 2 is precisely about the front end keeping its own copy of that list."*
 *
 * The two copies AGREED, clause for clause — enabled · not this service ·
 * meters a quantity — which is exactly what makes keeping both dangerous: two
 * derivations that agree today are two that can disagree tomorrow, and the one
 * on the SCREEN is the one no test in this repo can watch go wrong. A fallback
 * would be the same hazard wearing a smaller name, so there is none: while the
 * query is in flight the card says so (`ArrivesWithField`), which is this
 * step's own house pattern for a list that has not arrived.
 *
 * `getPercentBasisOptions` in `@/api/endpoints` is the one call.
 */

/**
 * ── `CR-130-BRC07` §8.3(1) · THE UNIT **THIS UTILITY** MEASURES THIS SERVICE IN
 *
 * `billed_uom`, else `primary_uom`, else nothing. That order is the SERVER's
 * own and is not re-decided here: `rating.selectors.uom_gate_for` reads
 * `billed or register`, and `tenancy.selectors.service_billed_uoms` says why —
 * a NULL `billed_uom` means *the register's own unit is what is billed*, never
 * *unconfigured*.
 *
 * `null` out means the utility has declared nothing at all, which is a real and
 * ordinary state and must not be read as a declaration of anything.
 */
export function declaredUnitFor(
  rows: readonly TenantServiceRow[] | undefined,
  serviceCode: string,
): string | null {
  const code = serviceCode.trim().toLowerCase();
  const row = (rows ?? []).find((one) => one.service.trim().toLowerCase() === code);
  if (row === undefined) {
    return null;
  }
  for (const candidate of [row.billed_uom, row.primary_uom]) {
    if (typeof candidate === "string" && candidate.trim() !== "") {
      return candidate;
    }
  }
  return null;
}

/** One unit as step 1 offers it. `reason` is why it cannot be picked, or
 *  `"offered"`. The WORDS are the caller's, so this stays testable without a
 *  browser or an i18n bundle — `activeUomOptions`' own doctrine. */
export interface ScheduleUomOption {
  value: string;
  /** `activeUomOptions`' raw `"code — name"`, unwrapped by any reason. */
  label: string;
  reason: "offered" | "out_of_scope" | "not_declared";
}

/**
 * ── `CR-130-BRC07` §8.3(1)(3) · STEP 1's UNIT PICKER, NARROWED TO WHAT THIS
 * UTILITY SAID IT MEASURES ─────────────────────────────────────────────────
 *
 * **PO, verbatim, 2026-09-22:** *"when you show the unit of measure while
 * setting the rates, please use unit of measurement set in the settings for
 * that utility. you are not applying filter to it and showing all unit of
 * measurements."*
 *
 * ⚠ **THE FILTER WAS NOT MISSING — IT HAD NOTHING TO FILTER ON, AND THIS IS A
 * SECOND LAYER RATHER THAN A CHANGE TO THE FIRST.** `activeUomOptions` applies
 * the SERVER's rule (`selectors.uom_scope_filter`) verbatim and its docstring
 * says *"Change one, change both"* — so it is called, not edited. Measured in a
 * browser on the seeded water+sewer utility: of 28 seeded units **seven carry
 * no service scope**, and a Sewer schedule was therefore offered eight —
 * `EDU · MMBtu · ccf · day · kW · kW-DC · kgal · month` — all eight selectable
 * and none preselected, while `tenant_services` already said `kgal`.
 *
 * ⚠ **AND THE SCOPES THEMSELVES CANNOT BE NARROWED, WHICH IS WHY THIS LAYER
 * EXISTS AT ALL.** `tenancy.services._derive_uom_service_scope` NULLs any unit
 * more than one service claims, on purpose — one nullable column cannot say
 * *"water or gas"* — and `kgal`, `ccf` and `kW` are each claimed by two or
 * three. Scoping `kgal` to water would refuse the very sewer schedule this
 * change request is about. The judgment and its figures are in the decision log
 * of 2026-09-22.
 *
 * **Three rules, in this order:**
 *
 *  1. the scope mirror decides who is in the list at all — unchanged;
 *  2. a unit the SCOPE excluded stays `out_of_scope` — that is the existing
 *     `alreadySaved` escape hatch and it is untouched (§8.3(5));
 *  3. where this utility HAS declared a unit, every other unit becomes
 *     `not_declared` — **present and unselectable, never absent**, which is
 *     `FieldOption`'s own doctrine: *"Present and unselectable beats absent
 *     (the user would never learn it exists) and beats selectable (they would
 *     only learn on submit)."*
 *
 * ⚠ **A UTILITY THAT HAS DECLARED NOTHING KEEPS TODAY'S LIST, ENTIRELY.** There
 * is no narrowing to do and inventing one would be choosing a unit on their
 * behalf. That is the `?? []`-never-the-catalogue instinct one function up.
 *
 * ⚠ **AND NOTHING IS RE-ADMITTED.** If the declared unit is not in the scoped
 * list — which `_apply_service_uom` refuses to create, so it cannot arise
 * through the product — the list is returned unnarrowed rather than having the
 * declared unit added back. Adding it would be this screen overruling the write
 * path, and `resolve_uom` would refuse it on save anyway.
 *
 * Pure: no hooks, no `t`, no DOM.
 */
export function scheduleUomOptions(
  entries: readonly LookupEntry[],
  serviceCode: string,
  declared: string | null,
  alreadySaved: readonly (string | null | undefined)[] = [],
): ScheduleUomOption[] {
  const scoped = activeUomOptions(entries, serviceCode, alreadySaved).map((option) => ({
    value: option.value,
    label: option.label,
    reason: (option.outOfScope ? "out_of_scope" : "offered") as ScheduleUomOption["reason"],
  }));
  const wanted = (declared ?? "").trim().toLowerCase();
  if (wanted === "") {
    return scoped;
  }
  const present = scoped.some(
    (option) => option.reason === "offered" && option.value.toLowerCase() === wanted,
  );
  if (!present) {
    return scoped;
  }
  return scoped.map((option) =>
    option.reason === "offered" && option.value.toLowerCase() !== wanted
      ? { ...option, reason: "not_declared" }
      : option,
  );
}

/** The badge map's own keys — exported so a test can prove the ordered list
 *  above and the badge table hold the SAME eleven, rather than drifting into
 *  two lists that each look complete. */
export const SERVICE_BADGE_CODES: readonly string[] = Object.keys(SERVICE_BADGES);

/** The badge for one service code. Exported so a test can assert the ELEVEN are
 *  distinct rather than trusting the table above to stay that way. */
export function serviceBadge(code: string): { letter: string; token: string } {
  return (
    SERVICE_BADGES[code] ?? {
      // A service this map does not know is a tenant-added code. It gets the
      // first two characters and the neutral token — VISIBLE and readable,
      // never blank, and never silently sharing another service's colour.
      letter: code.slice(0, 2).replace(/^./, (c) => c.toUpperCase()),
      token: "--color-neutral-500",
    }
  );
}

export function ServiceTags(props: { services: readonly string[] }) {
  const { t } = useTranslation();
  if (props.services.length === 0) {
    return <span className="rating-empty">{t("rating.plans.noServices")}</span>;
  }
  return (
    // B14 rule 21 — new UI is Tailwind only; no stylesheet class is added for
    // this. `gap-0.5` is r10's 2px, `w-5 h-5` its 20px.
    <span className="inline-flex flex-wrap gap-0.5 items-center">
      {props.services.map((code) => {
        const badge = serviceBadge(code);
        const name = t(`rating.service.${code}`, { defaultValue: code });
        return (
          <span
            key={code}
            // The full name is NOT dropped, it moves to the tooltip and to the
            // accessible name. A letter alone is not something a screen reader
            // can announce usefully, and B14 does not trade legibility for
            // density.
            title={name}
            aria-label={name}
            role="img"
            className="inline-flex w-5 h-5 items-center justify-center font-heading font-extrabold text-xs leading-none text-bg"
            style={{ background: `var(${badge.token})` }}
          >
            {badge.letter}
          </span>
        );
      })}
    </span>
  );
}

/**
 * A field this app cannot offer because the endpoint behind it does not exist
 * yet. It renders the control's LABEL and states what it waits for — never an
 * invented option list, and never a silently missing field.
 *
 * `tracks` — the OQ or DEF that keeps this absence open — is the same mechanism
 * `ArrivesWith` carries and exists for the same reason (DEF-445 / DEF-421: a
 * stated absence that cites nothing outlives its reason and no gate notices).
 * Read that component's docstring for the whole of it; G38 counts the notes
 * that cite nothing, ratcheted.
 */
export function ArrivesWithField(props: { label: string; message: string; tracks?: string }) {
  return (
    <div
      className="rating-arrives"
      role="note"
      {...(props.tracks !== undefined ? { "data-tracks": props.tracks } : {})}
    >
      <span className="rating-arrives-label">{props.label}</span>
      <p>{props.message}</p>
    </div>
  );
}

/** The `/settings/accounting/mapping` sub-tab — CR-008's ONE editor of a GL
 *  code. A constant rather than a literal in three files, so the day the
 *  route moves it moves once. */
export const GL_MAPPING_ROUTE = "/settings/accounting/mapping";

/** BR-SHL-025: a forbidden control is present and disabled, WITH its reason. */
export function GuardedButton(props: {
  readOnly: boolean;
  readOnlyReason: string;
  onClick: () => void;
  /**
   * The button VARIANT from the shared kit. Defaults to the secondary most
   * guarded controls use.
   *
   * ⚠ CR-018 PHASE 4a CHANGED THIS FROM `className` TO `variant`, and it is the
   * same change metering's GuardedButton took in Phase 3 — for the same reason.
   * a raw class string handed this component a CLASS STRING to
   * concatenate: a string it could not check, from a caller who could have
   * typed `btn-primry` and had tsc, eslint and every gate pass. The prop is a
   * union of five names now and a wrong one does not compile.
   *
   * It is also why six sites were the only ones the Phase 4a codemod could not
   * take: the class was not on a `<button>` at all, it was an argument.
   */
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  disabled?: boolean;
  children: ReactNode;
}) {
  const variant = props.variant ?? "secondary";
  const size = props.size ?? "default";
  if (props.readOnly) {
    return (
      <Button
        variant={variant}
        size={size}
        className={props.className}
        disabled
        title={props.readOnlyReason}
      >
        {props.children}
      </Button>
    );
  }
  return (
    <Button
      variant={variant}
      size={size}
      className={props.className}
      disabled={props.disabled === true}
      onClick={props.onClick}
    >
      {props.children}
    </Button>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-001@6304a38 (story+rules snapshot hash — EP-RAT-01 lead story; co-packets EP-RAT-02@0b56fac · EP-RAT-03@7d1a8ef · EP-RAT-04@f69a661)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S9–S13)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope)
// exceptions: E2 the S9 History tab is NOT in BR-SHL-001's ratified sidebar child list (which names four Plans & Rates children) although US-RAT-001 names History as an S9 exit and EP-RAT-04's matrix gives it a capability row — it is reachable from the S9 tab strip only, and `SHELL_NAV` is left untouched; reported, not resolved
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ═══════════════════════════════════════════════════════════════════════════
// WHAT A TIER LADDER IS ABOUT — QUANTITY, OR CONNECTION SIZE (DEF-2364)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **THE FIRE SCHEDULE DREW SEVEN BARS AND CAPTIONED EVERY ONE OF THEM
 * `0 connection and above` (PO, 2026-09-03).** They were the six fire-line
 * diameters at `$12` / `$30` / `$60` / `$100` / `$160` / `$230` plus the
 * every-other-size fallback at `$0` — six prices a utility bills real money on,
 * and the screen said the same seven meaningless words over each of them.
 *
 * **THE CAUSE IS THAT `RateTier` CARRIES TWO DIFFERENT AXES AND THREE SCREENS
 * ONLY EVER DREW ONE.** `from_qty`/`to_qty` is a usage band — water's
 * `0–5 kgal`, `5–15 kgal`. `size_class` is a connection size (`DEF-433`). A
 * capacity service prices BY SIZE and not by usage at all, so every one of its
 * tiers is legitimately `from 0, open-ended` and the band caption degenerates
 * to one sentence repeated per row. Nothing was broken: the renderer was
 * answering a question this ladder does not ask.
 *
 * ⚠ **AND IT IS NOT A FIRE PROBLEM — IT IS EVERY PER-SIZE SCHEDULE**, which is
 * what the PO said in the same breath: *"This might be the case for all Rate
 * Schedule changes."* r10's own Residential Water prices 2" differently from
 * every other size, so it has both axes at once and needs both captions.
 *
 * So a ladder is one of three shapes, and the caller draws the columns the
 * shape calls for rather than assuming From/To:
 *
 *   "quantity"           no tier names a size. Water's `0–5 kgal`. The
 *                        From/To/Rate table, exactly as it has always been.
 *   "size"               sizes are named AND no tier bounds usage — every tier
 *                        is `from 0, open-ended`. Fire. The band says nothing
 *                        at all, so the columns are Size and Price.
 *   "size-and-quantity"  both. r10's 2" water. Size AND the usage band.
 */
export type TierLadderShape = "quantity" | "size" | "size-and-quantity";

/** A tier as far as this module is concerned — the two axes and nothing else. */
export interface LadderTier {
  size_class: string | null;
  from_qty: string | null;
  to_qty: string | null;
}

/** True when this tier puts no bound on usage: from the bottom, open at the top. */
function boundsNoUsage(tier: LadderTier): boolean {
  // `from_qty` arrives as a decimal STRING and this module does no arithmetic
  // (see the money law at the top of this file), so "is it zero" is asked of
  // the shapes a server actually sends — "0", "0.0", "0.000000" — and never by
  // parsing it into a float.
  const from = (tier.from_qty ?? "0").trim();
  const startsAtZero = from === "" || /^0(\.0*)?$/.test(from);
  return startsAtZero && tier.to_qty === null;
}

export function tierLadderShape(tiers: readonly LadderTier[]): TierLadderShape {
  if (!tiers.some((tier) => tier.size_class !== null)) {
    return "quantity";
  }
  return tiers.every(boundsNoUsage) ? "size" : "size-and-quantity";
}

/**
 * The size a row is FOR, or the fallback's own words.
 *
 * `null` is not "unknown" and must never render as a dash: it is the group that
 * prices **every size the others do not name**, which is a real and billable
 * answer (`DEF-433`). Fire's `$0.00` every-other-size row is exactly this, and
 * `sample_data.fire_schedule_payload` explains why a stored zero there is a
 * price rather than an omission.
 */
export function tierSizeLabel(
  tier: LadderTier,
  t: (key: string) => string,
): string {
  return tier.size_class ?? t("rating.tier.everyOtherSize");
}

/**
 * ⚠ **THE STEP'S SECOND, THIRD AND FOURTH PARAGRAPHS GO IN HERE, CLOSED
 * (B14 rule 32, PO 2026-09-03).** Walking Plans & Rates the Product Owner said
 * *"too much content"* on four consecutive screens — the same complaint that
 * ratified the rule on 2026-08-31, in the same words: *"desctiption is too much
 * for clark to read"*.
 *
 * **NOTHING IS DELETED BY MOVING IT HERE, AND THAT IS THE POINT.** Every
 * sentence a lane wrote to stop the next reader filing a gap as a bug is still
 * in the DOM, still found by `Ctrl-F`, still cited by `G38`. It is simply not
 * the first thing a clerk meets. A `<details>` is the right primitive because
 * **being closed is what it IS** — the copy cannot leak back onto the screen
 * through a prop nobody passes, which is how it got there in the first place.
 *
 * The pattern is `RunGap`'s, which rule 32's own status note singles out as
 * *"structurally a `<details>` and holds by construction"*.
 */
export function MoreAbout(props: { children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <details className="mt-3">
      {/* ⚠ NO `text-help` HERE, AND THE GUARD IS WHY (CLAUDE.md DEF-974). It
          reads like a size utility and no stylesheet declares it, so it
          compiles to NOTHING while `tsc`, eslint and every `toContain` pass
          on it — the class IS in the DOM. `routeBUtilities` caught it before
          this shipped. This is the dashboard disclosure's own class list. */}
      <summary className="cursor-pointer text-xs text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
        {t("rating.rate.moreAbout")}
      </summary>
      <div className="mt-2 flex flex-col gap-2">{props.children}</div>
    </details>
  );
}

/**
 * A stored decimal on its way into an EDITABLE money field, without the
 * trailing zeros nobody typed (`DEF-2361`).
 *
 * ⚠ **THE PRODUCT OWNER FOUND `0.000000` IN THE CHARGE CODE'S AMOUNT BOX AND
 * `12.000000` IN THE FIRE SCHEDULE'S PER-SIZE PRICE (2026-09-03).** Six places
 * is the PERCENTAGE precision (CLAUDE.md hard rule 2 — money 4, percentages 6,
 * both DISPLAY 2); the column is `NUMERIC(18,6)` for historical reasons, and
 * `decimalIn` handed its bytes straight to an `<input>`.
 *
 * **THIS IS NOT `formatMoney` AND MUST NOT BECOME IT.** A display formatter
 * rounds to two places, and rounding a number somebody is about to edit and
 * post back would silently rewrite it — `8.2900` typed as a rate would come
 * back `8.29`, and on a schedule that is a different price. So this only ever
 * removes ZEROS beyond the second place, which cannot change the value:
 *
 *     "0.000000"  -> "0.00"     "12.000000" -> "12.00"
 *     "8.290000"  -> "8.29"     "8.295000"  -> "8.295"   (kept — it is a digit)
 *     ""          -> ""         null        -> ""        (never "0")
 *
 * A field is left EXACTLY as the server sent it whenever trimming would lose
 * anything at all, which is what makes this safe to use on an input.
 *
 * ⚠ **DO NOT CALL THIS FROM `draftFromCharge` OR `sizeLadders`, WHICH IS THE
 * OBVIOUS PLACE AND THE WRONG ONE.** Those fill the boxes that get
 * **re-posted**, and two tests say so by name — *"the round trip is
 * byte-identical — nothing is parsed or re-formatted"* and *"a stored row
 * round-trips into the draft at STORED precision, not display precision"*, the
 * second carrying the comment `// what will be re-posted` on the assertion
 * itself. Trimming there rewrites a stored value on every save, **including
 * saves where nobody touched the box.** It was wired there on 2026-09-03, six
 * tests went red, and it was backed out (`DEF-2361`).
 *
 * **ITS ONE CALLER IS `MoneyTextField` BELOW**, which is the display half of a
 * display-value / draft-value split: the box SHOWS this, the draft KEEPS the
 * server's bytes, and the two only converge when a person actually types. Read
 * that component before adding a second call site.
 *
 * ⚠ **THE CITATION ABOVE SAID `DEF-2365` IN BOTH PLACES UNTIL 2026-09-03
 * (`DEF-2357`), AND `DEF-2365` IS A REAL DEFECT ABOUT A DIFFERENT SCREEN** — a
 * stale sentence on the ledger Costs page. It resolved, so a reader who
 * followed it got a plausible wrong answer rather than nothing, which is
 * CLAUDE.md's `DEF-2804` hazard one module over.
 *
 * ⚠ **AND THIS DOCSTRING SAID *proved* FOR A DAY WHILE NO TEST ANYWHERE NAMED
 * THIS FUNCTION (`DEF-2358`, hard-won law 1).** It is proved now, by the five
 * examples written out above.
 *
 * ⚠ **THE CITATION THEN NAMED `ratingShared.test.tsx`, WHICH DOES NOT EXIST —
 * corrected 2026-09-19 while migrating the discount wizard onto this component
 * (`DEF-RAT-5791`).** The assertions are real and always were; they live in
 * `moneyBoxes.dom.test.tsx`, beside the component they exist for. This is
 * `DEF-2358`'s own shape one turn on: the first version claimed a proof that
 * did not exist, and the fix pointed at a filename that did not either. A
 * reader who opened the named file found nothing and could reasonably have
 * concluded the function was still unproved. **Name the file you can open.**
 */
export function moneyIn(value: string | null | undefined): string {
  const raw = (value ?? "").trim();
  if (!/^-?\d+\.\d+$/.test(raw)) {
    return raw; // no decimal point, or not a plain decimal — hand it back untouched
  }
  const [whole, fraction] = raw.split(".");
  const kept = fraction.replace(/0+$/, "");
  return `${whole}.${kept.padEnd(2, "0")}`;
}

/**
 * The display-value / draft-value split of {@link MoneyTextField}, as a hook so
 * a bare table-cell input can carry it too (`DEF-RAT-9119` — the rate
 * schedule's Pricing step printed a stored minimum as `15.000000`). `shown` is
 * `moneyIn(value)` until this box emits, then the person's own bytes while the
 * draft still holds them; `emit` is the input's change handler. The draft is
 * never rewritten, so an untouched save posts the stored bytes.
 */
export function useMoneyBox(
  value: string,
  onChange: (value: string) => void,
): { shown: string; emit: (next: string) => void } {
  const [typed, setTyped] = useState<string | null>(null);
  const editing = typed !== null && typed === value;
  return {
    shown: editing ? typed : moneyIn(value),
    emit: (next) => {
      setTyped(next);
      onChange(next);
    },
  };
}

/**
 * **A MONEY BOX THAT SHOWS TWO PLACES AND POSTS THE STORED BYTES — the
 * display-value / draft-value split (`DEF-2361`).**
 *
 * ⚠ **THE PRODUCT OWNER SAW `0.000000` IN THE CHARGE CODE'S AMOUNT BOX AND
 * `12.000000` IN THE FIRE SCHEDULE'S PER-SIZE PRICES AND SAID *"decimal"*
 * (2026-09-03).** Six places is the PERCENTAGE precision (CLAUDE.md hard rule
 * 2 — money 4, percentages 6, both DISPLAY 2). The columns are
 * `NUMERIC(18,6)` for historical reasons and the draft loaders hand their
 * bytes straight to an `<input>`.
 *
 * **WHY THIS IS A COMPONENT AND NOT A CALL TO `moneyIn` IN THE DRAFT LOADER.**
 * The draft is *what will be re-posted*. Trim it and every save rewrites a
 * stored value — **including a save where nobody touched the box**, which is a
 * silent edit to a price on a schedule. So the two values are kept apart:
 *
 *     draft value    the server's exact bytes, `12.000000`, until a person types
 *     display value  `moneyIn` of that, `12.00`, which is what the box shows
 *
 * **THE ONE PIECE OF STATE IS `typed`, AND IT IS COMPARED BY VALUE RATHER THAN
 * TRUSTED.** `typed` holds the last string this box EMITTED. The box is in
 * editing mode only while that string is still what the draft holds, so:
 *
 *   · nobody typed          → `typed` is null       → shows `moneyIn(value)`
 *   · a person typed        → draft === typed       → shows their bytes, untrimmed
 *   · the draft moved on    → draft !== typed       → falls back to `moneyIn(value)`
 *
 * That last line is the load-bearing one. A parent that resets the draft, loads
 * a different row, or refuses the edit puts the box back into display mode with
 * no effect to write and no stale state to clear — and because the guard is the
 * VALUE and not a mounted flag, a React instance reused across two rows of the
 * per-size table cannot carry one row's keystrokes onto another.
 *
 * ⚠ **THE MID-TYPING CASE IS WHY `moneyIn` MAY NOT BE APPLIED TO `typed`.**
 * `moneyIn("12.0")` is `"12.00"` — correct for a stored value, and it would
 * fight a person half way through typing `12.05` by pushing two zeros in after
 * their first keystroke. While they are typing, their bytes pass through
 * untouched, which is also what makes *what the user typed is what posts* true.
 *
 * **NOT A DISPLAY FORMATTER.** `formatMoney` rounds to two places; this only
 * ever removes zeros beyond the second, so a rate of `8.295000` still shows
 * `8.295` and still posts `8.295000`.
 *
 * ⚠ **THIS PARAGRAPH ENDED *"A percentage box does NOT use this — six places is
 * correct there, by the same hard rule"* UNTIL 2026-09-19 (`DEF-RAT-5791`), AND
 * IT CONFLATED STORAGE WITH DISPLAY.** Hard rule 2 stores money to 4 and
 * percentages to 6 and **DISPLAYS BOTH AT 2** — six places is correct in the
 * COLUMN, never in the box. The Product Owner read `0.500000` in the discount
 * wizard's percentage field and said so, which is `DEF-2361`'s own complaint one
 * screen over. A percentage box SHOULD use this, and the discount wizard's now
 * does: `moneyIn` is lossless, so `0.062500` still shows `0.0625` and a genuine
 * six-place percentage keeps every significant digit. The sentence had made the
 * one wrong reading sound ratified.
 */
export function MoneyTextField(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  help?: string;
  error?: string;
  readOnly?: boolean;
  /**
   * ⚠ **ADDED 2026-09-10 (`CR-087` charge-code conformance), AND IT IS B14
   * RULE 36's OWN REMEDY RATHER THAN A CONVENIENCE.** Rule 10 — *"required
   * fields carry the asterisk on the label"* — was UNMEETABLE on every money
   * box in Plans & Rates: this component wraps `TextField`, `TextField` has
   * accepted `required` since it was written (it draws the asterisk through
   * `FieldLabel` and sets `aria-required`), and this wrapper simply never
   * declared the prop or passed it on. So the charge wizard's `Amount *`, the
   * rate wizard's and the plan wizard's were all drawn required and built
   * without a marker, and no check in this repo could see it — the same shape
   * as `WorkingButton`'s missing `variant` in B14's own DEF-712 amendment: a
   * rule that cannot be obeyed renders into the same green as a rule nobody
   * has got to yet.
   *
   * **OPTIONAL, so nothing existing moves.** Absent means exactly what it
   * meant before — no asterisk, no `aria-required` — and the four call sites
   * that do not pass it render byte-for-byte what they rendered yesterday.
   */
  required?: boolean;
  /** The label is announced and not drawn, for a money box in a table cell
   *  whose COLUMN HEADER is already the label (`DEF-RAT-5734`). Passed straight
   *  through to `TextField`; absent renders exactly what it rendered before. */
  labelHidden?: boolean;
}) {
  const box = useMoneyBox(props.value, props.onChange);
  return (
    <TextField
      id={props.id}
      label={props.label}
      labelHidden={props.labelHidden}
      value={box.shown}
      onChange={box.emit}
      numeric
      required={props.required}
      help={props.help}
      readOnly={props.readOnly}
      error={props.error}
    />
  );
}

/**
 * `DEF-RAT-9112` — is the viewport narrower than 1440? The 1280 laptop leaves a
 * list 960px, and the rate-schedule and charge-code lists need 1048px and
 * 1089px with every column showing, so below 1440 each starts with its two
 * lowest-value columns behind the Columns picker (decision log 2026-10-02).
 * At 1440 and wider nothing changes. `matchMedia` absent (a test without one)
 * reads as wide, which is the layout every existing test was written against.
 */
export const NARROW_LIST_QUERY = "(max-width: 1439px)";

export function useNarrowList(): boolean {
  const read = () =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia(NARROW_LIST_QUERY).matches
      : false;
  const [narrow, setNarrow] = useState(read);
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(NARROW_LIST_QUERY);
    const changed = () => setNarrow(media.matches);
    media.addEventListener?.("change", changed);
    return () => media.removeEventListener?.("change", changed);
  }, []);
  return narrow;
}

/** The reference list behind the customer-class pickers (rate schedule and
 *  charge code wizards). It lived in `PlanWizard.tsx` until CR-167-BRC10
 *  round 3 task 8 retired that file; moved here unchanged. */
export const ACCOUNT_TYPES_LIST = "account_types";
