// ── Trace ──────────────────────────────────────────────
// Change:   CR-156-BRC10 wave B — the charge-code screens rebuilt from the 83
//           images in 05-prototype/charge-codes-2026-10-01/images (B14 rules 37,
//           42, 44). Screens: S9 Charge codes list · CHG-01 view · CHG-02 add/edit.
// Rulings:  decision log 2026-10-01, every row whose last column reads
//           "charge-code redesign": three kinds · free-codes-only picker · the
//           bill line fills in and stays editable · How it bills on step 1 · GL
//           in the side panel · steps Details · Pricing · Review · Effective
//           from (required) / Effective to · logical kill · flat amount as an
//           All-sizes row.
// Defects:  DEF-RAT-8713 (no "full amount" sentence on a base code) ·
//           DEF-RAT-8714 (a flat code reads as ONE amount, never "not priced
//           for this size") · DEF-RAT-8715 (step 3 reads back every step-1/2
//           setting) · DEF-RAT-8717 (sizes in size order) · DEF-RAT-8719 (the GL
//           account is the code's own, on every step).
// ───────────────────────────────────────────────────────
/**
 * THE CHARGE-CODE SCREENS' PURE HALF — the draft, what a save posts, and every
 * read-back the three screens share, so List, View and the wizard cannot
 * describe one code three ways.
 *
 * ⚠ **NO MONEY ARITHMETIC.** Every amount is a decimal STRING end to end
 * (hard rule 2); the only transformation here is moving a percent's decimal
 * point (`1.50` ↔ `0.0150`), done on the digits, never through a float.
 *
 * ⚠ **"ADD" CONFIGURES A CODE SETTINGS MINTED, IT DOES NOT CREATE ONE.** The
 * PO: *"code come from setting hence searchable drop down"*, and the picker
 * lists `charges` rows not yet in use. So the commit for a new charge code is
 * a `PATCH` of the picked row — a `POST` would collide with the code Settings
 * already holds (`rating.charges.duplicate_code`).
 */
import { CUSTOMER_CLASSES } from "@/api/endpoints";
import type { ChargeKind, ChargeRow, ChargeSizeAmount, ChargeSizeMinimum, LookupEntry } from "@/api/endpoints";

import { formatMoney } from "@/components/MoneyCell";
import { startingAmount } from "@/components/moneyMath";

import { compareSizeNames } from "./sizeOrder";

/** `9.00` → `$9.00`; an absent figure is `null` and the caller words it. */
export function dollars(display: string | null | undefined, currency = "USD"): string | null {
  if (display === null || display === undefined || display.trim() === "") return null;
  try {
    return formatMoney(display.trim(), currency);
  } catch {
    return display;
  }
}

/** The reserved size of a flat price (`apps/rating/constants.ALL_SIZES`). */
export const ALL_SIZES = "All sizes";

/** How the code is priced. `entered` is the drawing's *"Entered when used"*. */
export type PricedBy = "size" | "class" | "one" | "entered";

/** The charge types each kind offers, in the drawing's order. */
export const KIND_TYPES: Record<ChargeKind, readonly string[]> = {
  base: ["recurring"],
  plan: ["one_time", "recurring", "penalty", "refundable"],
  other: ["one_time", "recurring"],
};

export interface PriceDraftRow {
  /** A size class code, `ALL_SIZES`, or `""` for a row not chosen yet. */
  size: string;
  /** `null` = every class. */
  customerClass: string | null;
  amount: string;
  /** Penalty rows only — a real percent as typed (`1.50`), never a fraction. */
  percent: string;
  minimum: string;
}

export interface ChargeCodeDraft {
  kind: ChargeKind | "";
  /** `""` = Any service (plan and other only). */
  service: string;
  /** The picked Settings row (Add) or the code being edited. */
  chargeId: string;
  code: string;
  /** The bill line — fills in from the picked code and stays editable. */
  name: string;
  /** Base only: `""` = all classes, else ONE class (PO: "all or 1"), or
   * `STORED_CLASSES` for a stored scope of more than one (DEF-RAT-9176). */
  customerClass: string;
  /**
   * DEF-RAT-9176 — the base code's classes AS STORED, carried so a save that
   * did not touch the class field posts them back unchanged. The single-select
   * cannot state two classes; without this, an amount-only edit of the seeded
   * BASE-W (residential + municipal) posted `[]`, which the server reads as
   * EVERY class — refused against BASE-W-COM, or a silent widening.
   */
  storedClasses: string[];
  chargeType: string;
  pricedBy: PricedBy;
  /**
   * DEF-RAT-8834 — a PENALTY priced as one flat amount (the seeded NSF $30.00,
   * TAMPER $250.00), not as a percent and minimum. Read from the stored code on
   * Edit and kept, so opening one never turns its amount into a percent rule.
   */
  flatPenalty: boolean;
  taxable: boolean;
  autoApply: boolean;
  waivable: boolean;
  separateLine: boolean;
  /** DEF-CUS-9819 — *Application fee: Yes* (a one-time code only). */
  applicationFee: boolean;
  /** DEF-RAT-10739 (PO 2026-10-31 P7) — *NSF fee: Yes*: a bounce charges this
   *  code through the plan (a penalty code only). */
  nsfFee: boolean;
  /**
   * PO 2026-10-06 11 (a) — a PENALTY code's late-fee grace, as typed. `null`
   * = not stated yet: the form shows (and a save posts) Settings → Billing
   * defaults' grace, *"the starting value for new codes"*. `""` is a box the
   * clerk emptied, which is refused rather than snapping back to the default.
   */
  graceDays: string | null;
  /** `calendar` | `business`, or `""` for the Billing-defaults mode. */
  graceMode: string;
  rows: PriceDraftRow[];
  effectiveFrom: string;
  effectiveTo: string;
  reason: string;
}

/**
 * DEF-RAT-9176 — the class field's value for a stored scope of MORE THAN ONE
 * class. It is never a class code, so it cannot be posted as one: a save maps
 * it back to `storedClasses`. Picking *All classes* or one class replaces it,
 * which is the clerk changing the scope on purpose.
 */
export const STORED_CLASSES = "__stored_classes__";

/** What a save posts as `applies_to_customer_classes` (base only). */
export function classesToPost(draft: Pick<ChargeCodeDraft, "kind" | "customerClass" | "storedClasses">): string[] {
  if (draft.kind !== "base" || draft.customerClass === "") return [];
  if (draft.customerClass === STORED_CLASSES) {
    // Only a code read from the server can hold the marker; anything else
    // posts every class, exactly as "" does (and as Add always has).
    return draft.storedClasses.length > 1 ? [...draft.storedClasses] : [];
  }
  return [draft.customerClass];
}

export function emptyRow(size = "", customerClass: string | null = null): PriceDraftRow {
  return { size, customerClass, amount: "", percent: "", minimum: "" };
}

export function emptyDraft(): ChargeCodeDraft {
  return {
    kind: "",
    service: "",
    chargeId: "",
    code: "",
    name: "",
    customerClass: "",
    storedClasses: [],
    chargeType: "",
    pricedBy: "one",
    flatPenalty: false,
    taxable: false,
    autoApply: false,
    waivable: false,
    separateLine: true,
    applicationFee: false,
    nsfFee: false,
    graceDays: null,
    graceMode: "",
    rows: [emptyRow(ALL_SIZES)],
    effectiveFrom: "",
    effectiveTo: "",
    reason: "",
  };
}

/** The grace a form shows and a save posts: the typed one, else the default. */
export interface GraceDefault {
  days: number;
  mode: string;
}
export const GRACE_FALLBACK: GraceDefault = { days: 5, mode: "calendar" };

export function graceShown(
  draft: Pick<ChargeCodeDraft, "graceDays" | "graceMode">,
  fallback: GraceDefault | null | undefined,
): { days: string; mode: string } {
  const start = fallback ?? GRACE_FALLBACK;
  return {
    days: draft.graceDays === null ? String(start.days) : draft.graceDays,
    mode: draft.graceMode === "" ? start.mode : draft.graceMode,
  };
}

/** Whole days 0–30 (`BR-BIL-008`), as typed. */
export function graceDaysValid(days: string): boolean {
  const raw = days.trim();
  return /^\d{1,2}$/.test(raw) && Number(raw) <= 30;
}

/** DEF-BIL-10201 — a percent penalty row at 0% (or blank) with no minimum
 *  above zero charges $0.00 on every bill: meaningless, so refused. */
export function penaltyChargesNothing(row: Pick<PriceDraftRow, "percent" | "minimum"> | undefined): boolean {
  if (row === undefined) return false;
  const percent = row.percent.trim();
  const minimum = row.minimum.trim();
  const zero = (value: string) => value === "" || Number(value) === 0;
  return percent !== "" && zero(percent) && zero(minimum);
}

/** A penalty priced by a percent and a minimum — every penalty but a flat one (DEF-RAT-8834). */
export function isPercentPenalty(draft: Pick<ChargeCodeDraft, "chargeType" | "flatPenalty">): boolean {
  return draft.chargeType === "penalty" && !draft.flatPenalty;
}

/** Which settings a kind or type FIXES (step 1's disabled dropdowns). */
export function fixedFor(draft: Pick<ChargeCodeDraft, "kind" | "chargeType">): {
  service: boolean;
  charged: boolean;
  taxable: boolean;
  autoApply: boolean;
} {
  const base = draft.kind === "base";
  const penaltyOrDeposit = draft.chargeType === "penalty" || draft.chargeType === "refundable";
  return {
    service: false,
    // B4.3: a base is on every bill; a deposit is taken once, at move-in.
    charged: base || draft.chargeType === "refundable",
    // B4.2: a penalty and a deposit are never in the tax base.
    taxable: penaltyOrDeposit,
    // DEF-RAT-9805 — a ONE-TIME code never applies itself: the bill run reads
    // `auto_apply` only beside `recurring` (BR-RAT-117), so a Yes here did
    // nothing. Shown as No, locked, and the server refuses Yes by field.
    autoApply: base || draft.chargeType === "one_time",
  };
}

/** The drawing's *Charged* words for a type. */
export function chargedKey(chargeType: string): string {
  switch (chargeType) {
    case "recurring":
      return "rating.chargeCode.charged.everyBill";
    case "penalty":
      return "rating.chargeCode.charged.event";
    case "refundable":
      return "rating.chargeCode.charged.moveIn";
    default:
      return "rating.chargeCode.charged.once";
  }
}

/** A kind's own setting values, applied when the kind or type changes. */
export function withKindDefaults(draft: ChargeCodeDraft): ChargeCodeDraft {
  const next = { ...draft };
  if (next.kind === "") return next;
  if (!KIND_TYPES[next.kind].includes(next.chargeType)) {
    next.chargeType = KIND_TYPES[next.kind][0];
  }
  if (next.kind === "base") {
    next.autoApply = true;
  }
  if (next.chargeType === "one_time") {
    next.autoApply = false; // DEF-RAT-9805 — see `fixedFor`
  }
  if (next.chargeType === "penalty" || next.chargeType === "refundable") {
    next.taxable = false;
  }
  if (next.kind !== "plan" && next.pricedBy === "class") {
    next.pricedBy = "one";
  }
  if (next.chargeType === "penalty" && next.pricedBy !== "class") {
    // A penalty is one percent and minimum for every class, or one pair PER
    // class (DEF-RAT-8753, images 61 · 67 · 77) — never by size, never entered.
    next.pricedBy = "one";
  }
  if (next.kind !== "other" && next.pricedBy === "entered") {
    // *Entered when used* is an Other code's pricing (images 41 · 64 · 70).
    next.pricedBy = "one";
  }
  return next;
}

// ── sizes ───────────────────────────────────────────────────────────────

/**
 * A size's FAMILY — its name with every number taken out, so `Trash 35-gallon
 * cart` and `Trash 96-gallon cart` are one family and `Trash 2-yard dumpster`
 * another. Exported for its test.
 */
export function sizeFamily(name: string): string {
  return name
    .replace(/\d[\d,]*(?:\.\d+)?(?:\s*\/\s*\d+)?[¼½¾]?|[¼½¾]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

/**
 * **SIZE ORDER, FAMILY BY FAMILY** (`DEF-RAT-8717`; coordinator 2026-10-01 on
 * the trash table: *"carts first, then dumpsters … smallest first within
 * each"*, which is how image 19 lists them). Families keep the order they are
 * SERVED in (the server serves by code, so CART-… before DUMP-…), and within a
 * family the size the name states decides (`sizeOrder.compareSizeNames`), so
 * fire reads 2″ … 12″ and never 10″, 12″, 2″. Stable for anything that ties.
 */
export function sortBySizeFamily<T>(items: readonly T[], nameOf: (item: T) => string): T[] {
  const rank = new Map<string, number>();
  for (const item of items) {
    const family = sizeFamily(nameOf(item));
    if (!rank.has(family)) rank.set(family, rank.size);
  }
  return items
    .map((item, index) => ({ item, index, family: rank.get(sizeFamily(nameOf(item))) ?? 0 }))
    .sort(
      (a, b) =>
        a.family - b.family || compareSizeNames(nameOf(a.item), nameOf(b.item)) || a.index - b.index,
    )
    .map((entry) => entry.item);
}

/** The service's sizes in SIZE order (DEF-RAT-8717 — never by code text). */
export function sizesFor(
  entries: readonly LookupEntry[],
  service: string,
): LookupEntry[] {
  const live = entries.filter((entry) => entry.active);
  const scoped =
    service === ""
      ? live
      : live.filter((entry) => entry.service == null || entry.service.code === service);
  return sortBySizeFamily(scoped, (entry) => entry.name);
}

/**
 * A size code's clerk-facing label: the tenant's NAME for it (`Water 5/8"`).
 *
 * ⚠ **IT RETURNED THE CODE UNTIL 2.481.5 (`DEF-RAT-9321`)** — *"its code, as
 * the drawing prints it"* — and the Size picker listed `W-58, W-34, W-1 …`.
 * PO, on Ottumwa's `BASE-W-FIRE`: *"sizes should be user friendly language -
 * youa re showing internal codes"*. A drawn figure is an illustration (B14
 * rule 37) and a code is never a field's visible value (rule 31's spirit).
 * The CODE is still what a row stores and posts. A code the list no longer
 * holds keeps its stored text rather than going blank.
 */
export function sizeLabel(code: string, entries: readonly LookupEntry[]): string {
  return entries.find((entry) => entry.code === code)?.name ?? code;
}

/** `DEF-RAT-9322` — a priced row's key is the PAIR (size, class), as the
 *  server's (`_validate_size_amounts`, CR-087 A1): `W-1` for every class and
 *  `W-1` for Commercial are two lawful rows; the same pair twice is not. */
export function sizeRowKey(row: Pick<PriceDraftRow, "size" | "customerClass">): string {
  return `${row.size}|${row.customerClass ?? ""}`;
}

/** The first size a draft lists twice for the same class, or `null`. */
export function sizeListedTwice(rows: readonly PriceDraftRow[]): PriceDraftRow | null {
  const seen = new Set<string>();
  for (const row of rows) {
    if (row.size === "") continue;
    const key = sizeRowKey(row);
    if (seen.has(key)) return row;
    seen.add(key);
  }
  return null;
}

/** Rows in the size order of `entries` (unknown sizes keep their place, last). */
export function rowsInSizeOrder<T extends { size: string }>(
  rows: readonly T[],
  entries: readonly LookupEntry[],
): T[] {
  const nameOf = (code: string) => entries.find((entry) => entry.code === code)?.name ?? code;
  return sortBySizeFamily(rows, (row) => nameOf(row.size));
}

// ── from a stored code ──────────────────────────────────────────────────

/** `"1.50%"` → `"1.50"`; the server formats, the screen only strips the sign. */
function percentFromDisplay(display: string | null): string {
  return display === null ? "" : display.replace("%", "").trim();
}

/** `per_case` — the amount is entered when the fee is used (DEF-RAT-8753). */
export const PER_CASE = "per_case";

function pricedByOf(row: ChargeRow, inForce: ChargeSizeAmount[]): PricedBy {
  if (row.amount_rule === PER_CASE) return "entered";
  if (row.amount_rule === "percent" || row.amount_rule === "percent_with_minimum") {
    return (row.class_terms ?? []).length > 0 ? "class" : "one";
  }
  if (inForce.some((price) => price.size_class !== ALL_SIZES)) return "size";
  if (inForce.some((price) => price.customer_class !== null)) return "class";
  if (row.amount === null && inForce.length === 0) return "entered";
  return "one";
}

export function draftFromCharge(row: ChargeRow, entries: readonly LookupEntry[]): ChargeCodeDraft {
  const kind: ChargeKind | "" = row.kind ?? (row.is_base ? "base" : "");
  const inForce = row.size_amounts ?? [];
  const pricedBy = pricedByOf(row, inForce);
  let rows: PriceDraftRow[];
  const penaltyByClass = pricedBy === "class" && (row.class_terms ?? []).length > 0;
  if (pricedBy === "entered") {
    // DEF-RAT-9807 — the code's optional DEFAULT (`BR-RAT-1054` AMENDED
    // 2026-10-06) is its *All sizes* amount; one row holds it, blank when
    // there is none, so an untouched Edit posts back exactly what it read.
    rows = [{ ...emptyRow(ALL_SIZES), amount: startingAmount(row.amount) }];
  } else if (penaltyByClass) {
    // In the tenant's class order (Residential first, as images 61 and 77
    // draw), not the server's alphabetical one.
    rows = inClassOrder(row.class_terms ?? []).map((terms) => ({
      ...emptyRow(ALL_SIZES, terms.customer_class),
      percent: percentFromDisplay(terms.percent_display ?? null),
      minimum: terms.min_amount_display ?? "",
    }));
  } else if (pricedBy === "class") {
    rows = inClassOrder(inForce).map((price) => ({
      ...emptyRow(price.size_class, price.customer_class),
      amount: price.amount_display ?? "",
    }));
  } else if (pricedBy === "size") {
    rows = rowsInSizeOrder(
      inForce.map((price) => ({
        ...emptyRow(price.size_class, price.customer_class),
        amount: price.amount_display ?? "",
      })),
      entries,
    );
  } else {
    rows = [
      {
        ...emptyRow(ALL_SIZES),
        amount: row.amount_display ?? "",
        percent: percentFromDisplay(row.percent_display),
        minimum: row.min_amount_display ?? "",
      },
    ];
  }
  const classes = row.applies_to_customer_classes ?? [];
  // The live statement's own end, so re-sending it unchanged moves no price.
  const flatRow = (row.prices ?? []).find(
    (price) =>
      price.killed !== true && price.size_class === ALL_SIZES && price.customer_class === null,
  );
  const liveEnd =
    inForce[0]?.effective_to ?? flatRow?.effective_to ?? row.class_terms?.[0]?.effective_to ?? null;
  // The kind's fixed settings apply to the BASELINE too, so a stored base with
  // `auto_apply` off does not read as a change the clerk never made.
  return withKindDefaults({
    kind,
    service: row.service ?? "",
    chargeId: row.id,
    code: row.code,
    name: row.name,
    // DEF-RAT-9176 — two or more stored classes read as the stored scope,
    // never as "" (= every class), so an edit that leaves the field alone
    // posts exactly what it read.
    customerClass:
      kind !== "base" || classes.length === 0 ? "" : classes.length === 1 ? classes[0] : STORED_CLASSES,
    storedClasses: kind === "base" ? [...classes] : [],
    chargeType: row.charge_type ?? "",
    pricedBy,
    // DEF-RAT-8834 — a stored penalty that is NOT a percent rule is a flat amount.
    flatPenalty:
      row.charge_type === "penalty" &&
      row.amount_rule !== "percent" &&
      row.amount_rule !== "percent_with_minimum" &&
      pricedBy === "one",
    taxable: row.taxable_default,
    autoApply: row.auto_apply,
    waivable: row.waivable,
    separateLine: row.separate_line,
    applicationFee: row.is_application_fee === true,
    nsfFee: row.is_nsf_fee === true,
    graceDays: row.grace_days === null || row.grace_days === undefined ? null : String(row.grace_days),
    graceMode: row.grace_mode ?? "",
    rows,
    // Edit asks for the date the CHANGE starts; the stored start is not it.
    effectiveFrom: "",
    effectiveTo: liveEnd ?? "",
    reason: "",
  });
}

// ── what a save posts ───────────────────────────────────────────────────

/** `"1.50"` → `"0.0150"` by moving the decimal point on the digits. */
export function percentToFraction(percent: string): string {
  const raw = percent.trim();
  if (!/^\d+(\.\d+)?$/.test(raw)) return raw;
  const [whole, frac = ""] = raw.split(".");
  const digits = (whole.padStart(3, "0") + frac).replace(/^0+(?=\d)/, "");
  const padded = digits.padStart(frac.length + 3, "0");
  const point = padded.length - frac.length - 2;
  return `${padded.slice(0, point)}.${padded.slice(point)}`.replace(/^0+(?=\d)/, "") || "0";
}

export function chargePayload(
  draft: ChargeCodeDraft,
  editing: boolean,
  graceDefault: GraceDefault | null = null,
): Record<string, unknown> {
  const kind = draft.kind === "" ? null : draft.kind;
  const payload: Record<string, unknown> = {
    kind,
    is_base: kind === "base",
    name: draft.name.trim(),
    charge_type: draft.chargeType,
    service: draft.service === "" ? null : draft.service,
    applies_to_customer_classes: classesToPost(draft),
    taxable_default: draft.taxable,
    auto_apply: draft.autoApply,
    waivable: draft.waivable,
    separate_line: draft.separateLine,
    // DEF-CUS-9819 — only a one-time code may be the application fee.
    is_application_fee: draft.chargeType === "one_time" && draft.applicationFee,
    // DEF-RAT-10739 — only a penalty code may be the NSF fee.
    is_nsf_fee: draft.chargeType === "penalty" && draft.nsfFee,
    effective_from: draft.effectiveFrom === "" ? null : draft.effectiveFrom,
    effective_to: draft.effectiveTo === "" ? null : draft.effectiveTo,
  };
  if (draft.pricedBy === "entered") {
    // DEF-RAT-8753 — *Entered when used*: the clerk enters the amount when the
    // fee is raised (CR-010 A2). DEF-RAT-9807 — it may carry ONE optional
    // default the clerk starts from (`BR-RAT-1054` AMENDED 2026-10-06); blank
    // posts `null`, exactly as before.
    const fallback = draft.rows[0]?.amount.trim() ?? "";
    payload.amount_rule = PER_CASE;
    payload.percent = null;
    payload.min_amount = null;
    payload.amount = fallback === "" ? null : fallback;
    payload.size_amounts = [];
  } else if (draft.chargeType === "penalty" && draft.pricedBy === "class") {
    // DEF-RAT-8753 — one percent and minimum PER CLASS (images 61 · 67 · 77).
    const rows = draft.rows.filter((row) => row.customerClass);
    payload.amount_rule = rows.every((row) => row.minimum.trim() !== "") ? "percent_with_minimum" : "percent";
    payload.percent = null;
    payload.min_amount = null;
    payload.amount = null;
    payload.size_amounts = [];
    payload.class_terms = rows.map((row) => ({
      customer_class: row.customerClass,
      percent: row.percent.trim() === "" ? null : percentToFraction(row.percent),
      min_amount: row.minimum.trim() === "" ? null : row.minimum.trim(),
    }));
  } else if (isPercentPenalty(draft)) {
    const row = draft.rows[0] ?? emptyRow(ALL_SIZES);
    payload.amount_rule = row.minimum.trim() === "" ? "percent" : "percent_with_minimum";
    payload.percent = row.percent.trim() === "" ? null : percentToFraction(row.percent);
    payload.min_amount = row.minimum.trim() === "" ? null : row.minimum.trim();
    payload.amount = null;
    payload.size_amounts = [];
    // Back to one pair for every class: the per-class rows close.
    payload.class_terms = [];
  } else {
    payload.amount_rule = "flat";
    payload.percent = null;
    payload.min_amount = null;
    if (draft.pricedBy === "size" || draft.pricedBy === "class") {
      payload.amount = null;
      payload.size_amounts = draft.rows
        .filter((row) => row.size !== "" && (draft.pricedBy === "size" || row.customerClass))
        .map((row) => ({
          size_class: draft.pricedBy === "class" ? ALL_SIZES : row.size,
          // DEF-RAT-9322 — a sized row keeps the class it was read with. It was
          // forced to null, so W-1 every class + W-1 Commercial posted as two
          // every-class W-1 rows (refused) and a Commercial-only row widened.
          customer_class: draft.pricedBy === "class" ? row.customerClass : (row.customerClass ?? null),
          amount: row.amount.trim() === "" ? null : row.amount.trim(),
        }));
    } else {
      const amount = draft.rows[0]?.amount.trim() ?? "";
      payload.amount = amount === "" ? null : amount;
      payload.size_amounts = [];
    }
  }
  // PO 2026-10-06 11 (a) — only a penalty carries a grace; the shown one posts.
  if (draft.chargeType === "penalty") {
    const grace = graceShown(draft, graceDefault);
    payload.grace_days = grace.days.trim();
    payload.grace_mode = grace.mode;
  } else {
    payload.grace_days = null;
    payload.grace_mode = null;
  }
  if (editing) payload.reason = draft.reason.trim();
  return payload;
}

// ── read-backs shared by List, View and the wizard ─────────────────────

/** How many price cells a draft holds, and how many carry a figure. */
export function pricedCount(draft: ChargeCodeDraft): { rows: number; cells: number; priced: number } {
  if (draft.pricedBy === "entered") return { rows: 0, cells: 0, priced: 0 };
  const rows = draft.rows.filter((row) => row.size !== "" || draft.pricedBy !== "size");
  if (draft.chargeType === "penalty" && draft.pricedBy === "class") {
    // Two cells a row — the percent and the minimum (image 61: "4 of 4 priced").
    return {
      rows: rows.length,
      cells: rows.length * 2,
      priced: rows.reduce(
        (sum, row) => sum + (row.percent.trim() === "" ? 0 : 1) + (row.minimum.trim() === "" ? 0 : 1),
        0,
      ),
    };
  }
  if (isPercentPenalty(draft)) {
    const row = rows[0] ?? emptyRow(ALL_SIZES);
    return {
      rows: 1,
      cells: 2,
      priced: (row.percent.trim() === "" ? 0 : 1) + (row.minimum.trim() === "" ? 0 : 1),
    };
  }
  return {
    rows: rows.length,
    cells: rows.length,
    priced: rows.filter((row) => row.amount.trim() !== "").length,
  };
}

/** The *Priced by* words for a draft (wizard) — i18n key + params. */
export function pricedByWords(
  draft: Pick<ChargeCodeDraft, "kind" | "pricedBy" | "customerClass"> & { storedClasses?: readonly string[] },
  assetKey: string | null,
): { key: string; params: Record<string, unknown> } {
  if (draft.pricedBy === "entered") return { key: "rating.chargeCode.pricedBy.entered", params: {} };
  if (draft.pricedBy === "class") return { key: "rating.chargeCode.pricedBy.byClass", params: {} };
  if (draft.kind === "base") {
    // DEF-RAT-9176 — a stored scope of two or more classes is "N classes".
    const count = draft.storedClasses?.length ?? 0;
    const some = draft.customerClass === STORED_CLASSES && count > 1;
    const cls = some ? "some" : draft.customerClass === "" ? "every" : "one";
    const params: Record<string, unknown> = some ? { count } : {};
    if (draft.pricedBy === "size" && assetKey !== null) {
      return { key: `rating.chargeCode.pricedBy.base.${cls}BySize`, params: { ...params, asset: assetKey } };
    }
    return { key: `rating.chargeCode.pricedBy.base.${cls}`, params };
  }
  if (draft.pricedBy === "size") return { key: "rating.chargeCode.pricedBy.bySize", params: {} };
  return { key: "rating.chargeCode.pricedBy.one", params: {} };
}

/** The list's *Priced by* cell for a stored code. */
export function listPricedBy(row: ChargeRow): { key: string; params: Record<string, unknown> } {
  if (row.amount_rule === PER_CASE) return { key: "rating.chargeCode.pricedBy.entered", params: {} };
  if (row.amount_rule === "percent" || row.amount_rule === "percent_with_minimum") {
    if ((row.class_terms ?? []).length > 0) return { key: "rating.chargeCode.pricedBy.byClass", params: {} };
    return { key: "rating.chargeCode.pricedBy.percent", params: {} };
  }
  const range = row.price_range ?? null;
  if (range === null) return { key: "rating.chargeCode.pricedBy.entered", params: {} };
  if (range.priced_by === "size") {
    return row.kind === "base"
      ? { key: "rating.chargeCode.pricedBy.sizes", params: { count: range.rows } }
      : { key: "rating.chargeCode.pricedBy.bySize", params: {} };
  }
  if (range.priced_by === "customer_class") {
    return { key: "rating.chargeCode.pricedBy.byClass", params: {} };
  }
  return { key: "rating.chargeCode.pricedBy.one", params: {} };
}

/** The two ends of a range, `$9.00 – $40.00`. Glyphs only, so no catalogue
 *  key: a "translation" could only copy the dash (G15 counts it untranslated). */
export function rangeText(low: string, high: string): string {
  return `${low} – ${high}`;
}

/**
 * The list's Amount cell: a range for a sized code, the one figure for a flat
 * one, the server's percent for a percent code — `null` when nothing is priced.
 */
export function listAmount(
  row: ChargeRow,
  t: (key: string, params?: Record<string, unknown>) => string,
): string | null {
  const terms = (row.class_terms ?? [])
    .map((one) => one.percent_display ?? null)
    .filter((one): one is string => one !== null);
  if (terms.length > 0) {
    // DEF-RAT-8753 — a penalty by class: the range of its percents.
    // Ordered on the digits (no arithmetic on a figure, hard rule 2).
    const sorted = [...terms].sort((a, b) => a.localeCompare(b, "en", { numeric: true }));
    const low = sorted[0];
    const high = sorted[sorted.length - 1];
    return low === high ? low : rangeText(low, high);
  }
  if (row.amount_rule === "percent_with_minimum") {
    return t("rating.chargeCode.amount.percentMin", {
      percent: row.percent_display ?? "",
      min: dollars(row.min_amount_display) ?? "",
    });
  }
  if (row.amount_rule === "percent") return row.percent_display;
  const range = row.price_range ?? null;
  if (range === null) return null;
  const low = dollars(range.low_display) ?? range.low_display;
  const high = dollars(range.high_display) ?? range.high_display;
  return low === high ? low : rangeText(low, high);
}

/** One line of step 3's *What changes* table on Edit. */
export interface DraftChange {
  item: string;
  now: string | null;
  next: string | null;
}

/**
 * Edit's *What changes* — every field and price that differs between the
 * stored code and the draft, as the clerk reads them. `label` turns a field
 * key into words; `money` formats a stored figure the way the screen prints.
 */
export function draftChanges(
  before: ChargeCodeDraft,
  after: ChargeCodeDraft,
  words: {
    field: (key: string) => string;
    yesNo: (value: boolean) => string;
    type: (value: string) => string;
    money: (value: string) => string;
    notPriced: string;
    priceItem: (row: PriceDraftRow) => string;
    /** A class scope in class NAMES (`[]` = all classes), never codes. */
    classes: (codes: string[]) => string;
    /** PO 2026-10-06 11 (a) — a grace in words (`5 calendar days`). */
    grace?: (days: string, mode: string) => string;
  },
  graceDefault: GraceDefault | null = null,
): DraftChange[] {
  const out: DraftChange[] = [];
  if (before.name.trim() !== after.name.trim()) {
    out.push({ item: words.field("billLine"), now: before.name, next: after.name.trim() });
  }
  if (before.chargeType !== after.chargeType) {
    out.push({
      item: words.field("type"),
      now: words.type(before.chargeType),
      next: words.type(after.chargeType),
    });
  }
  // DEF-RAT-9209 — a base code's class scope, compared as a save POSTS it: an
  // untouched two-class scope (the stored marker) is no change, and picking
  // all or one class is shown, old scope → new.
  const scopeBefore = classesToPost(before);
  const scopeAfter = classesToPost(after);
  if (after.kind === "base" && [...scopeBefore].sort().join("|") !== [...scopeAfter].sort().join("|")) {
    out.push({
      item: words.field("customerClass"),
      now: words.classes(scopeBefore),
      next: words.classes(scopeAfter),
    });
  }
  const flags: [keyof ChargeCodeDraft, string][] = [
    ["taxable", "taxed"],
    ["autoApply", "auto"],
    ["waivable", "waive"],
    ["separateLine", "ownLine"],
    ["applicationFee", "applicationFee"],
    ["nsfFee", "nsfFee"],
  ];
  for (const [field, key] of flags) {
    if (before[field] !== after[field]) {
      out.push({
        item: words.field(key),
        now: words.yesNo(before[field] as boolean),
        next: words.yesNo(after[field] as boolean),
      });
    }
  }
  if (after.chargeType === "penalty" && words.grace !== undefined) {
    const old = graceShown(before, graceDefault);
    const now = graceShown(after, graceDefault);
    if (old.days.trim() !== now.days.trim() || old.mode !== now.mode) {
      out.push({
        item: words.field("grace"),
        now: before.chargeType === "penalty" ? words.grace(old.days.trim(), old.mode) : null,
        next: words.grace(now.days.trim(), now.mode),
      });
    }
  }
  const keyOf = (row: PriceDraftRow) => `${row.size}|${row.customerClass ?? ""}`;
  const was = new Map(before.rows.map((row) => [keyOf(row), row]));
  for (const row of after.rows) {
    if (row.size === "" && after.pricedBy === "size") continue;
    const old = was.get(keyOf(row));
    const figure = (value: string) => (value.trim() === "" ? words.notPriced : words.money(value));
    if (isPercentPenalty(after)) {
      const nowText = old === undefined ? null : `${old.percent}% · ${figure(old.minimum)}`;
      const nextText = `${row.percent}% · ${figure(row.minimum)}`;
      if (nowText !== nextText) out.push({ item: words.priceItem(row), now: nowText, next: nextText });
      continue;
    }
    const nowValue = old === undefined ? words.notPriced : figure(old.amount);
    const nextValue = figure(row.amount);
    if (old === undefined || old.amount.trim() !== row.amount.trim()) {
      if (nowValue !== nextValue) out.push({ item: words.priceItem(row), now: nowValue, next: nextValue });
    }
  }
  const kept = new Set(after.rows.map(keyOf));
  for (const row of before.rows) {
    if (!kept.has(keyOf(row)) && row.size !== "") {
      out.push({
        item: words.priceItem(row),
        now: row.amount.trim() === "" ? words.notPriced : words.money(row.amount),
        next: null,
      });
    }
  }
  return out;
}

/**
 * DEF-RAT-8752 — a base size's *Minimum* cell (images 11 · 51), read off the
 * rate schedules: one figure, `$4.24 – $6.00` where the schedules differ, and
 * `null` (a dash) where none floors the size or only some do — the reason is
 * the server's `state`, never words on screen (B14 rule 33).
 */
export function floorText(
  minimums: Record<string, ChargeSizeMinimum> | undefined,
  size: string,
): string | null {
  const one = minimums?.[size];
  if (one === undefined) return null;
  const low = dollars(one.low_display);
  const high = dollars(one.high_display);
  if (one.state === "one") return low;
  if (one.state === "range" && low !== null && high !== null) return rangeText(low, high);
  return null;
}

/** Rows priced by customer class in the tenant's class order — Residential
 *  first, as images 27, 31, 61 and 77 draw — never the server's alphabetical
 *  one. Every-class (`null`) first; an unknown class keeps its place, last. */
export function inClassOrder<T extends { customer_class: string | null }>(rows: readonly T[]): T[] {
  const drawn: readonly string[] = CUSTOMER_CLASSES;
  const rank = (code: string | null) => {
    if (code === null) return -1;
    const index = drawn.indexOf(code);
    return index < 0 ? drawn.length : index;
  };
  return rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => rank(a.row.customer_class) - rank(b.row.customer_class) || a.index - b.index)
    .map((entry) => entry.row);
}

/** Does any schedule floor any size of this base code? The Minimum column is
 *  drawn only then (image 11 draws it for water; 07 and 19 do not for fire
 *  and trash, whose schedules state no minimum). */
export function hasFloors(minimums: Record<string, ChargeSizeMinimum> | undefined): boolean {
  return Object.values(minimums ?? {}).some((one) => one.state !== "none");
}

/** The asset word for a service — catalogue key, never a hand-typed label. */
export function assetKeyFor(service: string, hasSizes: boolean): string | null {
  if (!hasSizes) return null;
  return `rating.chargeCode.asset.${service === "" ? "meter" : service}`;
}
