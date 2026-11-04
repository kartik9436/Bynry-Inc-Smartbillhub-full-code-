// ── Trace ──────────────────────────────────────────────
// Change:   CR-180-BRC10 (Fix a bill, revamped) — tasks F1–F10
// Drawing:  05-prototype/fix-a-bill-2026-10-12/*.png (read as images, B14 rule 42)
// Rulings:  decision log 2026-10-12 *FIX A BILL REVAMP* items 1–12
// Rules:    BR-BIL-014 (nothing is written before Send) · BR-BIL-041/042 (the
//           class is DERIVED; the strongest wins, R > C > D) · hard rule 2
// ───────────────────────────────────────────────────────
/**
 * THE FIX-A-BILL MODEL — pure, no React. What the four steps hold, what they
 * send, and what they derive. Every figure is the server's; this file decides
 * only SHAPE: which bills, which rows, which class.
 *
 * ## The two options and their four sub-options (items 1–3)
 *
 *   One customer — one bill · several months (ticked from that account's bills)
 *   Bulk         — a billing run (with *Only part of it*) · a price mistake
 *                  (From–To plus what was wrong)
 *
 * ## The one table (items 7, 10, 11)
 *
 * Every reason is a ROW TYPE of one *What was wrong* table. There is no
 * separate reason dropdown: *What happens* is derived from all the rows by
 * `BR-BIL-042`, re-price > credit only > reprint only, so a goodwill row beside
 * a reading row rides on the re-priced bill as a credit line.
 *
 * ⚠ **THE CLASS OF EACH REASON IS THE SERVER'S** (`GET /corrections/reasons`),
 * and so is the precedence (`classes`, in order). A reason the catalogue does
 * not serve is not offered — a row the server would refuse is a live screen
 * behind a dead control (hard-won law 2's mirror).
 */
import type { CorrectionCatalog, CorrectionItem, CorrectionScope } from "@/api/billingOpsEndpoints";

export type Translate = (key: string, params?: Record<string, unknown>) => string;

// ── Step 1 · Bills ─────────────────────────────────────────────────────────

export type FixOption = "one" | "bulk";
export type FixSub = "one_bill" | "several" | "run" | "price_mistake";

export const FIX_OPTIONS: readonly FixOption[] = ["one", "bulk"];

/** The sub-option dropdown's choices depend on the option (item 3). */
export const SUBS_BY_OPTION: Readonly<Record<FixOption, readonly FixSub[]>> = {
  one: ["one_bill", "several"],
  bulk: ["run", "price_mistake"],
};

export type PriceWrongKind = "rate" | "tax" | "charge";

export interface FixBillsForm {
  option: FixOption;
  sub: FixSub;
  accountId: string;
  /** The ticked (or the one radio-picked) bills of that account. */
  pickedIds: string[];
  runId: string;
  /** `""` the whole run · `service:<code>` · `plan:<id>`. */
  runPart: string;
  from: string;
  to: string;
  /** `<kind>:<id>` from the price-mistake list. */
  target: string;
}

export const EMPTY_BILLS_FORM: FixBillsForm = {
  option: "one",
  sub: "one_bill",
  accountId: "",
  pickedIds: [],
  runId: "",
  runPart: "",
  from: "",
  to: "",
  target: "",
};

export function chooseOption(form: FixBillsForm, option: FixOption): FixBillsForm {
  if (form.option === option) return form;
  return { ...EMPTY_BILLS_FORM, option, sub: SUBS_BY_OPTION[option][0] };
}

export function chooseSub(form: FixBillsForm, sub: FixSub): FixBillsForm {
  if (form.sub === sub) return form;
  // One bill keeps at most one of the ticked months; several keeps them all.
  const pickedIds = sub === "one_bill" ? form.pickedIds.slice(0, 1) : form.pickedIds;
  return { ...form, sub, pickedIds };
}

/** Radio for one bill, a tick for several. */
export function togglePicked(form: FixBillsForm, invoiceId: string): FixBillsForm {
  if (form.sub === "one_bill") return { ...form, pickedIds: [invoiceId] };
  const has = form.pickedIds.includes(invoiceId);
  return {
    ...form,
    pickedIds: has
      ? form.pickedIds.filter((id) => id !== invoiceId)
      : [...form.pickedIds, invoiceId],
  };
}

function splitTarget(target: string): { kind: PriceWrongKind; id: string } | null {
  const at = target.indexOf(":");
  if (at <= 0) return null;
  const kind = target.slice(0, at);
  if (kind !== "rate" && kind !== "tax" && kind !== "charge") return null;
  return { kind, id: target.slice(at + 1) };
}

/**
 * The scope the server resolves — or `null` while step 1 is not answered
 * enough to ask. `withPicked` adds the picked bills on One customer; the
 * account's whole list is asked WITHOUT them (contract A1).
 */
export function scopeOf(form: FixBillsForm, withPicked = true): CorrectionScope | null {
  if (form.option === "one") {
    if (form.accountId === "") return null;
    if (!withPicked) return { scope_kind: "account", account_id: form.accountId };
    if (form.pickedIds.length === 0) return null;
    return { scope_kind: "account", account_id: form.accountId, invoice_ids: [...form.pickedIds] };
  }
  if (form.sub === "run") {
    if (form.runId === "") return null;
    const scope: CorrectionScope = { scope_kind: "run", bill_run_id: form.runId };
    if (form.runPart.startsWith("service:")) scope.service_code = form.runPart.slice(8);
    if (form.runPart.startsWith("plan:")) scope.plan_id = form.runPart.slice(5);
    return scope;
  }
  const target = splitTarget(form.target);
  if (form.from === "" || form.to === "" || target === null || form.from > form.to) return null;
  return {
    scope_kind: "price_mistake",
    period_start: form.from,
    period_end: form.to,
    wrong_kind: target.kind,
    wrong_id: target.id,
  };
}

/** Why step 1's Continue refuses — a catalogue KEY, or `null`. */
export function billsRefusalKey(form: FixBillsForm): string | null {
  if (form.option === "one") {
    if (form.accountId === "") return "billing.fixBill.refuse.pickAccount";
    if (form.pickedIds.length === 0) {
      return form.sub === "one_bill"
        ? "billing.fixBill.refuse.pickBill"
        : "billing.fixBill.refuse.tickBills";
    }
    return null;
  }
  if (form.sub === "run") return form.runId === "" ? "billing.fixBill.refuse.pickRun" : null;
  if (form.from === "" || form.to === "") return "billing.fixBill.refuse.pickDates";
  if (form.from > form.to) return "billing.fixBill.refuse.datesOrder";
  if (splitTarget(form.target) === null) return "billing.fixBill.refuse.pickWrong";
  return null;
}

// ── Step 2 · Fix: the reasons ──────────────────────────────────────────────

/** The README's order, grouped by class (item 10). */
export const REASON_GROUPS: readonly { cls: string; reasons: readonly string[] }[] = [
  {
    cls: "restatement",
    reasons: [
      "wrong_read",
      "wrong_plan",
      "wrong_rate",
      "wrong_tax",
      "missed_charge",
      "charge_billed_in_error",
      "wrong_discount",
      "wrong_deposit",
      "wrong_period_or_service",
      "theft_restated",
    ],
  },
  { cls: "credit_only", reasons: ["goodwill"] },
  {
    cls: "document",
    reasons: [
      "customer_name",
      "service_or_mailing_address",
      "premises_or_unit_label",
      "meter_number_or_read_dates",
      "template_or_language",
    ],
  },
];

export const REASON_ORDER: readonly string[] = REASON_GROUPS.flatMap((group) => group.reasons);

/** Bulk offers these; a price mistake the same without the reprint (README). */
export const BULK_RUN_REASONS: readonly string[] = [
  "wrong_plan",
  "wrong_rate",
  "wrong_tax",
  "missed_charge",
  "charge_billed_in_error",
  "wrong_discount",
  "template_or_language",
];
export const PRICE_MISTAKE_REASONS: readonly string[] = BULK_RUN_REASONS.filter(
  (reason) => reason !== "template_or_language",
);

export const REPRINT_REASONS: readonly string[] = REASON_GROUPS[2].reasons;

/**
 * DEF-BIL-10088 — the FIELD a reprint row changes (contract §2: *item = the
 * field*), per reason, as the server's `correction_items.REPRINT_FIELDS`
 * holds them. The first is the preset; a reason with two offers both. Sending
 * the reason itself was refused for every reason but Customer name.
 */
export const REPRINT_FIELDS: Readonly<Record<string, readonly string[]>> = {
  customer_name: ["customer_name"],
  service_or_mailing_address: ["mailing_address", "service_address"],
  premises_or_unit_label: ["premises_label", "unit_label"],
  meter_number_or_read_dates: ["meter_number", "read_dates"],
  template_or_language: ["language", "message"],
};

/** The reasons a sub-option offers, in the drawn order, that the server serves. */
export function reasonsFor(sub: FixSub, catalog: Pick<CorrectionCatalog, "reasons">): string[] {
  const served = new Set(catalog.reasons.map((reason) => reason.code));
  const allowed =
    sub === "run"
      ? BULK_RUN_REASONS
      : sub === "price_mistake"
        ? PRICE_MISTAKE_REASONS
        : REASON_ORDER;
  return REASON_ORDER.filter((reason) => allowed.includes(reason) && served.has(reason));
}

export function classOf(
  reason: string,
  catalog: Pick<CorrectionCatalog, "reasons">,
): string | null {
  return catalog.reasons.find((one) => one.code === reason)?.correction_class ?? null;
}

/**
 * `BR-BIL-042` across every row: the strongest class present, in the
 * server's own precedence (`catalog.classes`, strongest first). `null` while
 * the table is empty.
 */
export function strongestClass(
  rows: readonly Pick<FixRow, "reason">[],
  catalog: Pick<CorrectionCatalog, "reasons" | "classes">,
): string | null {
  const present = new Set(
    rows.map((row) => classOf(row.reason, catalog)).filter((c) => c !== null),
  );
  return catalog.classes.find((klass) => present.has(klass.code))?.code ?? null;
}

// ── Step 2 · Fix: the rows ─────────────────────────────────────────────────

export interface FixRow {
  /** Screen-only key for React; never sent, never shown. */
  uid: string;
  reason: string;
  item: string;
  act: "" | "add" | "remove";
  value: string;
  value2: string;
  /** The bills it applies to; `null` = every bill in the scope. */
  applyTo: string[] | null;
}

/** What a new row starts from — the billed values the server served (A2). */
export interface RowDefaults {
  billIds: readonly string[];
  bulk: boolean;
  billed?: { plan_id: string | null; deposit: string | null } | null;
  /** The scope's meters (contract A2). Where there is exactly one, a
   *  reading row starts on it — there is nothing else it could mean. */
  meterIds?: readonly string[];
}

let uidCounter = 0;
function nextUid(): string {
  uidCounter += 1;
  return `row-${uidCounter}`;
}

/** The item a reason preloads, where there is only one honest answer. */
function presetItem(reason: string, defaults: RowDefaults): string {
  if (reason === "wrong_plan") return defaults.billed?.plan_id ?? "";
  if ((reason === "wrong_read" || reason === "theft_restated") && defaults.meterIds?.length === 1) {
    return defaults.meterIds[0];
  }
  if (reason === "wrong_deposit") return "DEP";
  if (reason === "goodwill") return "credit";
  if (REPRINT_REASONS.includes(reason)) return REPRINT_FIELDS[reason]?.[0] ?? reason;
  return "";
}

export function newRow(reason: string, defaults: RowDefaults): FixRow {
  // Goodwill is a concession on ONE month (image 09: Oct only); every other
  // row starts on every picked bill. Bulk rows always apply to every bill.
  const applyTo = defaults.bulk
    ? null
    : reason === "goodwill" && defaults.billIds.length > 1
      ? [defaults.billIds[defaults.billIds.length - 1]]
      : [...defaults.billIds];
  return {
    uid: nextUid(),
    reason,
    item: presetItem(reason, defaults),
    act: reason === "missed_charge" ? "add" : reason === "charge_billed_in_error" ? "remove" : "",
    value: reason === "missed_charge" ? "1" : "",
    value2: "",
    applyTo,
  };
}

/** A row whose reason changed keeps only where it applies — unless it had no
 *  reason yet, when the new reason's own starting bills apply. */
export function withReason(row: FixRow, reason: string, defaults: RowDefaults): FixRow {
  const fresh = newRow(reason, defaults);
  return { ...fresh, uid: row.uid, applyTo: row.reason === "" ? fresh.applyTo : row.applyTo };
}

const DECIMAL = /^-?\d+(\.\d+)?$/;

/** Whether a row says enough to be priced. A half-typed row is not sent. */
export function rowComplete(row: FixRow): boolean {
  if (row.applyTo !== null && row.applyTo.length === 0) return false;
  switch (row.reason) {
    case "wrong_read":
    case "theft_restated":
    case "wrong_deposit":
    case "goodwill":
      return row.item !== "" && DECIMAL.test(row.value.trim());
    case "wrong_tax":
      return row.item !== "" && DECIMAL.test(row.value.trim());
    case "missed_charge":
      return row.item !== "" && DECIMAL.test(row.value.trim());
    case "wrong_plan":
    case "wrong_rate":
      return row.item !== "" && row.value !== "";
    case "charge_billed_in_error":
      return row.item !== "";
    case "wrong_discount":
      return row.item !== "" && row.act !== "";
    case "wrong_period_or_service":
      return row.item !== "" && row.value !== "" && row.value2 !== "" && row.value <= row.value2;
    default:
      return (
        REPRINT_REASONS.includes(row.reason) &&
        (REPRINT_FIELDS[row.reason] ?? [row.reason]).includes(row.item) &&
        row.value.trim() !== ""
      );
  }
}

/** The rows as the contract's ITEMs — complete rows only. A row on every
 *  bill of the scope is sent as `bill_ids: null`. */
export function itemsOf(rows: readonly FixRow[], allBillIds: readonly string[]): CorrectionItem[] {
  return rows.filter(rowComplete).map((row) => {
    const everyBill =
      row.applyTo === null ||
      (row.applyTo.length === allBillIds.length &&
        allBillIds.every((id) => row.applyTo?.includes(id)));
    const item: CorrectionItem = {
      reason: row.reason,
      item: row.item,
      bill_ids: everyBill ? null : [...(row.applyTo ?? [])],
    };
    if (row.act !== "") item.act = row.act;
    if (row.value.trim() !== "") item.value = row.value.trim();
    if (row.value2 !== "") item.value2 = row.value2;
    return item;
  });
}

/** Why step 2's Continue refuses — a key, or `null`. */
export function fixRefusalKey(rows: readonly FixRow[]): string | null {
  if (rows.length === 0) return "billing.fixBill.refuse.addCorrection";
  if (!rows.every(rowComplete)) return "billing.fixBill.refuse.finishRows";
  return null;
}

// ── Shared words ───────────────────────────────────────────────────────────

/** `Oct` — a bill's month, short, in the clerk's language (UTC: a period end
 *  is a calendar date, never an instant). */
export function monthLabel(isoDay: string, language: string): string {
  const date = new Date(`${isoDay}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return isoDay;
  try {
    return new Intl.DateTimeFormat(language, { month: "short", timeZone: "UTC" }).format(date);
  } catch {
    return isoDay.slice(0, 7);
  }
}

/** `Oct 2026` from a `YYYY-MM` posting period. */
export function periodLabel(yyyyMm: string, language: string): string {
  const date = new Date(`${yyyyMm}-01T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return yyyyMm;
  try {
    return new Intl.DateTimeFormat(language, {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(date);
  } catch {
    return yyyyMm;
  }
}

/** The sign of a decimal string, for colour and the up/down words — read off
 *  the string, never parsed to a float (hard rule 2). */
export function signOf(amount: string | null | undefined): "up" | "down" | "flat" {
  if (amount === null || amount === undefined) return "flat";
  const trimmed = amount.trim();
  if (!/[1-9]/.test(trimmed)) return "flat";
  return trimmed.startsWith("-") ? "down" : "up";
}

/** `-11.38` → `11.38`, for a sentence that already says which way it went. */
export function unsigned(amount: string): string {
  return amount.trim().replace(/^[-+]/, "");
}
