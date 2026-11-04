// ── Trace ──────────────────────────────────────────────
// Design:   04-docs/05-modules/07-billing/11-one-time-bill-redesign.md (PO-confirmed 2026-09-30)
// Contract: 04-docs/05-modules/07-billing/13-one-time-bill-api-contract.md
// Drawing:  05-prototype/one-time-bill-2026-09-30/*.png + inventory.md
// Plan:     12-one-time-bill-build-plan.md F2, F5, F13, F14
// ───────────────────────────────────────────────────────
/**
 * THE ONE-TIME BILL'S STATE, WITHOUT A DOM.
 *
 * Everything here is a pure function of the clerk's entries and the server's
 * preview, so the rules the drawing implies can be asserted exhaustively rather
 * than by clicking: which panels a kind shows (§2 and §4 of the design), what
 * the request body is, which problems stand on which field, how the due date
 * is derived and what the summary aside counts.
 *
 * ⚠ **NO LIST OF SERVICES LIVES HERE (skill §12).** The services, rates and
 * readings a bill has are the SERVER's rows; this file only groups and counts
 * what it was given, so an eleventh service needs no edit anywhere below.
 */
import type {
  OneTimeBillKind,
  OneTimeBillPreview,
  OneTimeBillReadingInput,
  OneTimeBillReadingRow,
  OneTimeBillRequest,
  OneTimeBillServiceRow,
} from "@/api/billingOpsEndpoints";
import { amountScale, scaledAmount, sumAmounts, unscaledAmount } from "@/components/moneyMath";

/** The six cards, in the drawn order. Their words live in the catalogue under
 *  `billing.oneTimeBill.kind.<kind>` and `…kindUse.<kind>`. */
export const ONE_TIME_BILL_KIND_ORDER: readonly OneTimeBillKind[] = [
  "interim",
  "first",
  "final",
  "backbill",
  "penalty",
  "fee",
];

/** Catch-up and penalty take a LIST of missed periods, never one window. */
export function takesPeriodList(kind: OneTimeBillKind): boolean {
  return kind === "backbill" || kind === "penalty";
}

/** Interim, first and final take one From / To window. */
export function takesWindow(kind: OneTimeBillKind): boolean {
  return kind === "interim" || kind === "first" || kind === "final";
}

/** A reason from Settings — catch-up and penalty. */
export function takesReason(kind: OneTimeBillKind): boolean {
  return takesPeriodList(kind);
}

/** The charge-code dropdown: required on a fee, optional on a penalty. */
export function chargeCodeRule(kind: OneTimeBillKind): "required" | "optional" | "absent" {
  if (kind === "fee") return "required";
  if (kind === "penalty") return "optional";
  return "absent";
}

/** Fee bills have no services, rates or readings — only the charge (§4). */
export function hasServiceSections(kind: OneTimeBillKind): boolean {
  return kind !== "fee";
}

export interface PeriodEntry {
  start: string;
  end: string;
}

/** Everything the clerk has entered. Strings throughout — money and readings
 *  are never floats client-side (CLAUDE.md rule 2). */
export interface OneTimeBillForm {
  kind: OneTimeBillKind;
  accountId: string;
  periodStart: string;
  periodEnd: string;
  periods: PeriodEntry[];
  reasonCode: string;
  chargeCode: string;
  /** DEF-RAT-8753 — the picked code is priced *entered when used*
   *  (`per_case`, CR-010 A2), so the clerk types its amount here. */
  chargeEntered?: boolean;
  /** The amount for a `per_case` code, as typed (a decimal string). */
  enteredAmount?: string;
  billDate: string;
  dueDays: string;
  /** Typed readings keyed by {@link readingKey}. */
  readings: Record<string, { value: string; readAt: string }>;
  /** DEF-BIL-8562 — interim meters the clerk asked to ESTIMATE, by asset id,
   *  with the service each belongs to. No value: the estimate is Meter Reads'. */
  estimates?: Record<string, string>;
  /** DEF-BIL-9077 — services whose in-period meter rollover the clerk
   *  accepted (`RolloverAccept`). */
  acceptedRollovers?: string[];
  /** DEF-BIL-10067 — the typed readings step 2's Continue already POSTED to
   *  Meter Reads, by {@link postedKey}, so a second Continue does not post the
   *  same reading twice. The typed values themselves stay in `readings`: the
   *  preview and the draft are priced on them (PO 2026-10-12, *"the draft is
   *  priced on the reading entered"*). */
  posted?: Record<string, string>;
}

export function emptyForm(kind: OneTimeBillKind, today: string): OneTimeBillForm {
  return {
    kind,
    accountId: "",
    periodStart: "",
    periodEnd: "",
    periods: [{ start: "", end: "" }],
    reasonCode: "",
    chargeCode: "",
    billDate: today,
    dueDays: "",
    readings: {},
  };
}

/** One row's typing slot. A catch-up meter appears once per period, so the
 *  period is part of the key; a first bill's move-in value is a second slot on
 *  the same meter. */
export function readingKey(
  row: Pick<OneTimeBillReadingRow, "asset_id" | "period_index">,
  role: OneTimeBillReadingInput["role"],
): string {
  return `${row.asset_id}|${role}|${row.period_index ?? ""}`;
}

/** Whole days, zero or more — `0` is lawful (contract §2). */
export function parseDueDays(raw: string): number | null {
  const trimmed = raw.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  return Number(trimmed);
}

/** Calendar arithmetic on a `YYYY-MM-DD` string — no time zone, no clock. */
export function addDays(date: string, days: number): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (match === null) return null;
  const utc = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + days);
  return new Date(utc).toISOString().slice(0, 10);
}

/** The due date the Dates panel shows: bill date + days to pay, or null
 *  (drawn `—`) when either half cannot be read. */
export function derivedDueDate(form: Pick<OneTimeBillForm, "billDate" | "dueDays">): string | null {
  const days = parseDueDays(form.dueDays);
  if (days === null || form.billDate === "") return null;
  return addDays(form.billDate, days);
}

/** The readings the clerk has typed, as §2's `readings` list. */
export function typedReadings(
  form: OneTimeBillForm,
  rows: readonly OneTimeBillReadingRow[],
): OneTimeBillReadingInput[] {
  const out: OneTimeBillReadingInput[] = [];
  for (const row of rows) {
    for (const role of ["current", "move_in", "last_period"] as const) {
      const typed = form.readings[readingKey(row, role)];
      if (typed === undefined || typed.value.trim() === "") continue;
      const readAt = typed.readAt !== "" ? typed.readAt : (row.current.read_at ?? "");
      out.push({ asset_id: row.asset_id, read_at: readAt, value: typed.value.trim(), role });
    }
  }
  return out;
}

/** DEF-BIL-8562 — the meters the clerk asked to estimate, as `estimate` rows. */
export function estimateReadings(
  form: OneTimeBillForm,
  rows: readonly OneTimeBillReadingRow[],
): OneTimeBillReadingInput[] {
  if (form.kind !== "interim") return [];
  const asked = form.estimates ?? {};
  return rows
    .filter((row) => asked[row.asset_id] !== undefined && row.current.value === null)
    .map((row) => ({
      asset_id: row.asset_id,
      read_at: row.current.read_at ?? "",
      value: "",
      role: "estimate" as const,
      service: asked[row.asset_id],
    }));
}

/** §2's request body, built from the form. Empty required values travel as
 *  `null` so the server names every problem in one pass (A3). */
export function requestBody(
  form: OneTimeBillForm,
  rows: readonly OneTimeBillReadingRow[] = [],
): OneTimeBillRequest {
  const body: OneTimeBillRequest = {
    account_id: form.accountId,
    kind: form.kind,
    bill_date: form.billDate === "" ? null : form.billDate,
    due_days: parseDueDays(form.dueDays),
  };
  if (takesWindow(form.kind)) {
    body.period_start = form.periodStart;
    body.period_end = form.periodEnd;
  }
  if (takesPeriodList(form.kind)) {
    body.sub_periods = form.periods.map((p) => ({ period_start: p.start, period_end: p.end }));
  }
  if (takesReason(form.kind)) {
    body.reason_code = form.reasonCode;
  }
  if (chargeCodeRule(form.kind) !== "absent" && form.chargeCode !== "") {
    body.charge_code = form.chargeCode;
    // DEF-RAT-8753 — only for a code priced *entered when used*; the server
    // refuses a typed amount beside any other code (BR-BIL-020).
    if (form.kind === "fee" && form.chargeEntered === true && (form.enteredAmount ?? "").trim() !== "") {
      body.entered_amount = (form.enteredAmount ?? "").trim();
    }
  }
  const readings = [...typedReadings(form, rows), ...estimateReadings(form, rows)];
  if (readings.length > 0) {
    body.readings = readings;
  }
  if ((form.acceptedRollovers ?? []).length > 0) {
    body.accepted_rollovers = [...(form.acceptedRollovers ?? [])];
  }
  return body;
}

/** What the clerk decided on step 2 that the DRAFT records (contract §6, DB2
 *  and DB3): a final bill's settlement path — only when the server offered it
 *  for this remainder — a penalty's evidence text and a fee's note. Kept off
 *  the preview body on purpose: none of them moves a figure, and typing a note
 *  must not re-price the bill on every keystroke. */
export function draftExtras(
  kind: OneTimeBillKind,
  choices: { settlementPath: string; evidence: string; note: string },
  offeredPaths: readonly string[] = [],
): Pick<OneTimeBillRequest, "settlement_path" | "evidence" | "note"> {
  const extras: Pick<OneTimeBillRequest, "settlement_path" | "evidence" | "note"> = {};
  if (kind === "final" && offeredPaths.includes(choices.settlementPath)) {
    extras.settlement_path = choices.settlementPath as OneTimeBillRequest["settlement_path"];
  }
  if (kind === "penalty" && choices.evidence.trim() !== "") {
    extras.evidence = choices.evidence.trim();
  }
  if (kind === "fee" && choices.note.trim() !== "") {
    extras.note = choices.note.trim();
  }
  return extras;
}

// ── Problems ────────────────────────────────────────────────────────────────

/** One problem, on its field. `messageKey` is the catalogue key the field
 *  shows; the server's own keys (`billing.oneTime.err.*`) arrive the same way. */
export interface Problem {
  field: string;
  messageKey: string;
  params?: Record<string, unknown>;
}

/**
 * DEF-BIL-8330 — problems that are FACTS ABOUT THE ACCOUNT, not about what was
 * typed (PO 2026-09-30, option A: *"you have to show the message /warning to
 * user - A · Refuse until the account has a cycle"*). A first bill for an
 * account on no billing cycle is refused on the account field with the
 * server's own key. Unlike `clientProblems` these show the moment the account
 * is picked — nothing the clerk types can fix them, so holding them until
 * Continue (DEF-BIL-8289) would only hide a dead end. `cycle_name` is
 * `undefined` while the card is being read and `null` for no cycle.
 */
export function accountProblems(
  kind: OneTimeBillKind,
  account: { cycle_name?: string | null } | null,
): Problem[] {
  // PO 2026-10-01 — a FINAL bill too: *"show warning and A · Refuse until the
  // account has a cycle (same as first bill)"*. And an INTERIM bill (PO
  // 2026-10-01, *"A · Cut down (10/30)"*, BR-BIL-1066): its base is cut down
  // over the account's own cycle, so with no cycle there is nothing to divide
  // by. The server's `KINDS_NEEDING_A_CYCLE` is the same three kinds.
  const needsACycle = kind === "first" || kind === "final" || kind === "interim";
  if (!needsACycle || account === null || account.cycle_name !== null) return [];
  return [{ field: "account_id", messageKey: "billing.oneTime.err.noBillingCycle" }];
}

/** The problems the screen can see without asking — the same keys the server
 *  answers with, so a problem reads identically whichever side found it. */
export function clientProblems(form: OneTimeBillForm): Problem[] {
  const problems: Problem[] = [];
  if (form.accountId === "") {
    problems.push({ field: "account_id", messageKey: "billing.oneTime.err.accountRequired" });
  }
  if (takesWindow(form.kind)) {
    if (form.periodStart === "") {
      // A first bill's From IS the move-in date and the field says so; the
      // problem names it the same way, on that field (PO report, 2.411.4 —
      // "Enter the period." over an empty Move-in date was a dead end).
      problems.push({
        field: "period_start",
        messageKey:
          form.kind === "first" ? "billing.oneTime.err.moveInRequired" : "billing.oneTime.err.periodRequired",
      });
    }
    if (form.periodEnd === "") {
      problems.push({ field: "period_end", messageKey: "billing.oneTime.err.periodRequired" });
    } else if (form.periodStart !== "" && form.periodEnd < form.periodStart) {
      problems.push({ field: "period_end", messageKey: "billing.oneTime.err.periodEndsBeforeStart" });
    } else if (form.kind === "first" && form.periodStart !== "" && form.periodEnd <= form.periodStart) {
      // DEF-BIL-8288 — a first bill's From IS the move-in date, so To on the
      // same day bills the move-in day alone. The server asks the same
      // question with the same key (`one_time_answer.problems_in`).
      problems.push({ field: "period_end", messageKey: "billing.oneTime.err.toNotAfterMoveIn" });
    }
  }
  if (takesPeriodList(form.kind)) {
    form.periods.forEach((period, index) => {
      if (period.start === "") {
        problems.push({
          field: `sub_periods[${index}].period_start`,
          messageKey: "billing.oneTime.err.periodRequired",
        });
      }
      if (period.end === "") {
        problems.push({
          field: `sub_periods[${index}].period_end`,
          messageKey: "billing.oneTime.err.periodRequired",
        });
      } else if (period.start !== "" && period.end < period.start) {
        problems.push({
          field: `sub_periods[${index}].period_end`,
          messageKey: "billing.oneTime.err.periodEndsBeforeStart",
        });
      }
    });
  }
  if (takesPeriodList(form.kind)) {
    // DEF-BIL-8322 — two periods that share a day, named on the From of the
    // one that starts inside the other; the ORDER typed is not a problem (the
    // server takes them in date order). The server asks the same question
    // with the same key.
    const sound = form.periods
      .map((period, index) => ({ ...period, index }))
      .filter((period) => period.start !== "" && period.end !== "" && period.end >= period.start)
      .sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : a.end < b.end ? -1 : 1));
    let latestEnd: string | null = null;
    for (const period of sound) {
      if (latestEnd !== null && period.start <= latestEnd) {
        problems.push({
          field: `sub_periods[${period.index}].period_start`,
          messageKey: "billing.oneTime.err.periodOverlaps",
        });
      }
      if (latestEnd === null || period.end > latestEnd) latestEnd = period.end;
    }
  }
  if (takesReason(form.kind) && form.reasonCode === "") {
    problems.push({ field: "reason_code", messageKey: "billing.oneTime.err.reasonRequired" });
  }
  if (chargeCodeRule(form.kind) === "required" && form.chargeCode === "") {
    problems.push({ field: "charge_code", messageKey: "billing.oneTime.err.chargeRequired" });
  }
  if (form.kind === "fee" && form.chargeEntered === true && (form.enteredAmount ?? "").trim() === "") {
    problems.push({ field: "entered_amount", messageKey: "billing.oneTime.err.amountRequired" });
  }
  if (form.billDate === "") {
    problems.push({ field: "bill_date", messageKey: "billing.oneTime.err.billDateRequired" });
  }
  if (form.dueDays.trim() === "") {
    problems.push({ field: "due_days", messageKey: "billing.oneTime.err.dueDaysRequired" });
  } else if (parseDueDays(form.dueDays) === null) {
    problems.push({ field: "due_days", messageKey: "billing.oneTime.err.dueDaysInvalid" });
  }
  return problems;
}

/** Both sides' problems, one per field — the first to name a field wins, so a
 *  field never shows two sentences. Order follows the screen top to bottom. */
export function mergeProblems(...lists: readonly (readonly Problem[])[]): Problem[] {
  const seen = new Set<string>();
  const merged: Problem[] = [];
  for (const list of lists) {
    for (const problem of list) {
      if (seen.has(problem.field)) continue;
      seen.add(problem.field);
      merged.push(problem);
    }
  }
  return merged;
}

/** The problem standing on one field, if any. */
export function problemFor(problems: readonly Problem[], field: string): Problem | undefined {
  return problems.find((problem) => problem.field === field);
}

/**
 * The summary line for one problem. It says WHICH field, where the field's own
 * message cannot: *"Ends before it starts."* under a To box is enough, but in a
 * list at the top of the page it becomes *"The period ends before it starts."*
 * or *"Period 2 ends before it starts."* — exactly as drawn.
 */
export function summaryLine(problem: Problem): { key: string; params?: Record<string, unknown> } {
  if (problem.messageKey === "billing.oneTime.err.periodEndsBeforeStart") {
    const match = /^sub_periods\[(\d+)\]/.exec(problem.field);
    if (match !== null) {
      return {
        key: "billing.oneTimeBill.problem.subPeriodEndsBeforeStart",
        params: { n: Number(match[1]) + 1 },
      };
    }
    return { key: "billing.oneTimeBill.problem.periodEndsBeforeStart" };
  }
  return { key: problem.messageKey, params: problem.params };
}

// ── The summary aside ───────────────────────────────────────────────────────

export interface ServiceCounts {
  billed: number;
  notInService: number;
  notTaken: number;
}

/** The aside's three service counts, read off the server's rows. */
export function serviceCounts(services: readonly OneTimeBillServiceRow[] | null): ServiceCounts {
  const counts: ServiceCounts = { billed: 0, notInService: 0, notTaken: 0 };
  for (const row of services ?? []) {
    if (row.status === "not_in_service") counts.notInService += 1;
    else if (row.status === "not_taken") counts.notTaken += 1;
    else counts.billed += 1;
  }
  return counts;
}

/** How many printed lines the bill has — the aside's `Lines`. */
export function lineCount(preview: OneTimeBillPreview | null): number | null {
  if (preview === null) return null;
  return preview.bill.groups.reduce((sum, group) => sum + group.lines.length, 0);
}

/** The bill's tax, summed across its tax lines as a decimal string. */
export function taxTotal(preview: OneTimeBillPreview | null): string | null {
  if (preview === null) return null;
  return sumAmounts(preview.bill.tax.map((line) => line.amount));
}

// ── The steps ───────────────────────────────────────────────────────────────

/** The four rail cells, in order. One word each (PO 2026-09-30, *"i need 1
 *  word step name not 2"*); the label stays `Services` on a Fee bill too. */
export const ONE_TIME_BILL_STEPS = ["account", "services", "review", "send"] as const;
export type OneTimeBillStep = (typeof ONE_TIME_BILL_STEPS)[number];

/** Which readings rows a clerk types into, and in which role (§4 of the
 *  design). Penalty takes none; catch-up only the last period. */
export function editableRoles(
  kind: OneTimeBillKind,
  row: OneTimeBillReadingRow,
  lastPeriodIndex: number | null,
): OneTimeBillReadingInput["role"][] {
  if (kind === "interim" || kind === "final") return ["current"];
  if (kind === "first") return row.previous.on_file ? ["current"] : ["move_in", "current"];
  if (kind === "backbill") {
    return row.period_index !== null && row.period_index === lastPeriodIndex ? ["last_period"] : [];
  }
  return [];
}

/** True when step 2 can continue on its readings: every row the kind needs is
 *  typed and none is refused. Penalty and fee need none. */
export function readingsReady(
  form: OneTimeBillForm,
  preview: OneTimeBillPreview | null,
): boolean {
  if (preview === null || preview.readings === null) return true;
  const rows = preview.readings.rows;
  if (rows.some((row) => row.status === "refused")) return false;
  const last = lastPeriodIndex(rows);
  for (const row of rows) {
    // DEF-BIL-8562 — an estimated meter needs no reading typed.
    if (form.kind === "interim" && (form.estimates ?? {})[row.asset_id] !== undefined) continue;
    for (const role of editableRoles(form.kind, row, last)) {
      const typed = form.readings[readingKey(row, role)];
      // What Meter Reads already holds for this slot: the move-in value once
      // it is on file, otherwise the row's new/end reading.
      const onFile = role === "move_in" ? (row.previous.on_file ? row.previous.value : null) : row.current.value;
      if ((typed === undefined || typed.value.trim() === "") && onFile === null) return false;
    }
  }
  return true;
}

export function lastPeriodIndex(rows: readonly OneTimeBillReadingRow[]): number | null {
  let last: number | null = null;
  for (const row of rows) {
    if (row.period_index !== null && (last === null || row.period_index > last)) {
      last = row.period_index;
    }
  }
  return last;
}

/** DEF-BIL-10067 — one typed reading's identity for {@link OneTimeBillForm.posted}. */
export function postedKey(reading: Pick<OneTimeBillReadingInput, "asset_id" | "role" | "read_at">): string {
  return `${reading.asset_id}|${reading.role}|${reading.read_at}`;
}

/** DEF-BIL-10067 — the typed readings Continue has NOT yet posted at this
 *  value. Until 2026-10-12 Continue cleared what was typed once it was posted,
 *  so the preview after it and the draft were priced on whatever Meter Reads
 *  counted for that date — the committed 8.0 over the clerk's 4.6. The typed
 *  values now stay on the request, and this keeps them from posting twice. */
export function unpostedReadings(
  typed: readonly OneTimeBillReadingInput[],
  posted: Record<string, string> | undefined,
): OneTimeBillReadingInput[] {
  return typed.filter((reading) => (posted ?? {})[postedKey(reading)] !== reading.value);
}

/** DEF-BIL-10067 (a) — a cut service's usage SHARES as the Rates table shows
 *  them: two places each, half-up, and the LAST part takes the remainder, so
 *  the shown parts add back to the shown whole — the engine's own rule for the
 *  stored shares (`midperiod._share`). 373.333333 + 133.333333 + 293.333334
 *  showed 373.33 + 133.33 + 293.33 = 799.99 against an 800 kWh read; it shows
 *  373.33 + 133.33 + 293.34 = 800. Exact decimal arithmetic, never a float.
 *  A list with a missing or unreadable share is returned unchanged. */
export function footingShares(quantities: readonly (string | null)[]): (string | null)[] {
  if (quantities.length < 2 || quantities.some((q) => q === null)) return [...quantities];
  try {
    const known = quantities as readonly string[];
    const scale = Math.max(2, ...known.map((q) => amountScale(q)));
    const step = 10n ** BigInt(scale - 2);
    const toTwo = (value: bigint): bigint => {
      const negative = value < 0n;
      const magnitude = negative ? -value : value;
      let whole = magnitude / step;
      if ((magnitude % step) * 2n >= step) whole += 1n;
      return negative ? -whole : whole;
    };
    const values = known.map((q) => scaledAmount(q, scale));
    const total = toTwo(values.reduce((sum, value) => sum + value, 0n));
    const shown = values.slice(0, -1).map(toTwo);
    shown.push(total - shown.reduce((sum, value) => sum + value, 0n));
    return shown.map((value) => unscaledAmount(value, 2));
  } catch {
    return [...quantities];
  }
}
