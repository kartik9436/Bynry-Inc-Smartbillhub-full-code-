// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the discount DETAILS page, built from
//           images 19–26 of 05-prototype/discounts-2026-10-03 (B14 rule 42).
// Defect:   DEF-RAT-9291 (D19–D34) · DEF-RAT-9310 (Duplicate held)
// Rules:    PO lifecycle rulings 2026-10-03 (1)–(4) · README point 6 (header
//           buttons follow the status; tabs Overview · Accounts · Plans ·
//           Audit; every entered value shown) · B14 rules 31, 33, 37 ·
//           BR-RAT-087 (the server's display strings)
// Tests:    src/features/rating/discountDetail/discountDetail.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * THE PURE HALF OF THE DISCOUNT DETAILS PAGE — what each status offers, every
 * fact the page shows, and the audit's words, worked out from the served row
 * with no React in it.
 *
 * ⚠ **THE EDIT DOOR IS ONE ADDRESS AND IT IS SPELLED ONCE, HERE.** The edit
 * lane (round 3 task 7) builds the form behind it in parallel. The address is
 * the one the tax pair agreed (`taxDetailModel.taxEditDoor`) on the discount's
 * own list route: `/plans-rates/discounts/:id/edit?change=info|change|correct`
 * — images 27–36's three cards (*Name and details · New value from a date ·
 * Fix a mistake*). Header *Edit* opens `change=info`. Today that address
 * mounts the old `DiscountWizard`, which ignores the parameter; the day task 7
 * lands it opens the drawn card. `discountDetail.dom.test.tsx` asserts the
 * literal address so the two halves cannot drift apart (hard-won law 2).
 *
 * ⚠ **"GRANTED THIS MONTH" AND AN ACCOUNT'S "THIS MONTH" ARE A DASH, AND NOTHING
 * EXPLAINS THE DASH.** The server serves both as `null` until `DEF-2430` /
 * `DEF-BIL-5341` record a grant at issue (decision log 2026-10-03). A `$0.00`
 * would be a figure pretending to be a fact; a sentence saying why would be
 * rationale, which B14 rule 33 puts at zero words on screen.
 */
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { Fact } from "@/components/FactBlock";
import { formatMoney } from "@/components/MoneyCell";
import type {
  DiscountAuditEntry,
  DiscountDetailRow,
  DiscountMoneyKey,
  DiscountOptionValue,
  DiscountVersionLine,
} from "@/api/discountDetailEndpoints";

import { DEFINITION_ROUTES } from "../definitionDetail";
import { localiseOptions, offScopePhrase } from "../discountForm/discountFormShared";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

export interface DiscountRegional {
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

/** A value the server did not send — never a zero, never blank. */
export const DASH = "—";

// ── The edit door ─────────────────────────────────────────────────────────

/** The three ways into the edit form (README point 7). */
export const DISCOUNT_EDIT_CHANGES = ["info", "change", "correct"] as const;
export type DiscountEditChange = (typeof DISCOUNT_EDIT_CHANGES)[number];

export const DISCOUNT_EDIT_CHANGE_PARAM = "change";

/** `/plans-rates/discounts/<id>/edit?change=<change>` — the agreed door. */
export function discountEditDoor(discountId: string, change: DiscountEditChange): string {
  return `${DEFINITION_ROUTES.discount.listRoute}/${encodeURIComponent(discountId)}/edit?${DISCOUNT_EDIT_CHANGE_PARAM}=${change}`;
}

// ── Tabs ──────────────────────────────────────────────────────────────────

/** README point 6: Overview · Accounts · Plans · Audit. */
export const DISCOUNT_DETAIL_TABS = ["overview", "accounts", "plans", "audit"] as const;
export type DiscountDetailTab = (typeof DISCOUNT_DETAIL_TABS)[number];

/** An unknown or old tab name falls back to Overview; `versions` — the old
 *  page's history tab — opens Audit so links already sent keep working. */
export function discountDetailTabFrom(raw: string | null): DiscountDetailTab {
  if (raw === "versions") return "audit";
  return (DISCOUNT_DETAIL_TABS as readonly string[]).includes(raw ?? "") ? (raw as DiscountDetailTab) : "overview";
}

// ── What each status offers (README point 6; images 19, 23, 24, 26) ────────

export type HeaderAct = "edit" | "submit" | "approve" | "sendBack";

/**
 * The header's buttons, left to right, the LAST one primary.
 *
 *   Active / Scheduled  Edit                       (image 19)
 *   Draft               Edit · Submit for approval (image 24)
 *   Waiting approval    Send back · Approve        (image 26)
 *   Ended / Retired     nothing but More ▾
 *
 * ⚠ **WAITING APPROVAL: APPROVE IS THE PRIMARY, THOUGH IMAGE 26 PAINTS SEND
 * BACK RED.** The drawing decides WHAT is there; which button carries the
 * primary tier is how it is built (B14 rule 44) — one primary, and it is the
 * act that moves the work forward, as *Submit for approval* is on a draft.
 * Recorded in CR-166 §13.
 */
export function headerActs(status: string, type?: string | null): HeaderAct[] {
  // PO ruling 2026-10-03: a usage allowance is never made live, and the server
  // refuses to submit one (`type_not_priceable`) — so its draft offers Edit only.
  if (status === "draft") return type === "usage_allowance" ? ["edit"] : ["edit", "submit"];
  if (status === "waiting_approval") return ["sendBack", "approve"];
  if (status === "active" || status === "scheduled") return ["edit"];
  return [];
}

/** Retire ends something that prices now or will. */
export function retireOffered(status: string): boolean {
  return status === "active" || status === "scheduled";
}

/** The draft version a *Delete draft* would throw away, if there is one. */
export function draftVersion(versions: readonly DiscountVersionLine[]): DiscountVersionLine | null {
  return versions.find((row) => row.status === "draft") ?? null;
}

// ── Labels ────────────────────────────────────────────────────────────────

/** A platform code in the catalogue's words — the form's own map, so the two
 *  screens cannot name one code two ways. An unknown code shows as itself. */
function word(
  list: "type" | "scope" | "enrollment" | "verification" | "lapse" | "period" | "out",
  value: string | null | undefined,
  t: Translator,
): string {
  if (value === null || value === undefined || value === "") return DASH;
  return localiseOptions(list, [{ value, label: value }], t)[0]?.label ?? value;
}

/** A per-utility list value: the utility's own label (never translated). */
export function optionLabel(value: DiscountOptionValue | string | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  if (typeof value === "string") return value.trim() === "" ? DASH : value;
  return value.label.trim() === "" ? DASH : value.label;
}

function text(value: string | null | undefined): string {
  return value === null || value === undefined || value.trim() === "" ? DASH : value;
}

function yesNo(value: boolean | null | undefined, t: Translator): string {
  if (value === null || value === undefined) return DASH;
  return value ? t("rating.discountForm.yes") : t("rating.discountForm.no");
}

function day(value: string | null | undefined, regional: DiscountRegional): string {
  return value === null || value === undefined || value === ""
    ? DASH
    : formatDate(value, regional.timeZone, regional.dateFormat);
}

export function typeWord(row: Pick<DiscountDetailRow, "type">, t: Translator): string {
  return word("type", row.type, t);
}

/** `08/01/2026 – no end`, or `08/01/2026 – 12/31/2026`. */
export function windowText(
  from: string | null | undefined,
  to: string | null | undefined,
  regional: DiscountRegional,
  noEnd: string,
): string | null {
  if (from === null || from === undefined || from === "") return null;
  return `${day(from, regional)} – ${to === null || to === undefined || to === "" ? noEnd : day(to, regional)}`;
}

/** The header line's place: `Percentage · 08/01/2026 – no end`. */
export function headerPlace(row: DiscountDetailRow, regional: DiscountRegional, t: Translator): string {
  const window = windowText(row.effective_from, row.effective_to, regional, t("rating.taxDetail.noEnd"));
  return [row.type === null ? null : typeWord(row, t), window].filter((part): part is string => part !== null).join(" · ");
}

/** *Next: 12% from 01/01/2027* — only when a later approved version exists. */
export function nextShown(row: DiscountDetailRow): boolean {
  const next = row.scheduled_next;
  return next !== null && next !== undefined && typeof next.effective_from === "string" && next.effective_from !== "";
}

// ── The four tiles (image 19) ─────────────────────────────────────────────

export interface DiscountTileFigures {
  value: string;
  valueDetail: string;
  offered: string;
  receiving: string;
  granted: string;
}

export function tileFigures(row: DiscountDetailRow, t: Translator): DiscountTileFigures {
  // The scope's own in-sentence phrase (DEF-RAT-9316); a code with none reads
  // its list word inside `summary.off`, never lowercased.
  const scope = word("scope", row.applies_to, t);
  const phrase = offScopePhrase(row.applies_to, t);
  return {
    value: row.value_display ?? DASH,
    valueDetail: phrase ?? (scope === DASH ? "" : t("rating.discountForm.summary.off", { scope })),
    offered: row.offered_to === null || row.offered_to === undefined ? DASH : String(row.offered_to),
    receiving: row.receiving === null || row.receiving === undefined ? DASH : String(row.receiving),
    granted: row.granted_this_month === null || row.granted_this_month === undefined ? DASH : row.granted_this_month,
  };
}

// ── The two fact grids ────────────────────────────────────────────────────

/**
 * A money figure WITH its symbol and its thousands separator — `$2,383.00`,
 * never `$2383.00` (`DEF-RAT-9311`).
 *
 * ⚠ **THROUGH THE ONE SHARED FORMATTER (`formatMoney`, BR-SHL-023), NEVER A
 * SECOND PATH.** The stored decimal string and the row's own currency go in;
 * the shared formatter is the place that knows half-up, two places and the
 * grouping. The server's `money_display` (D27) carries the symbol but no
 * separator, so it is the FALLBACK — used only when the stored amount or the
 * currency did not arrive — and the bare `*_display` after it.
 */
export function money(row: DiscountDetailRow, key: DiscountMoneyKey): string | null {
  const raw = (row as unknown as Record<string, string | null | undefined>)[key];
  const currency = (row as unknown as { currency?: string | null }).currency;
  if (typeof raw === "string" && raw !== "" && typeof currency === "string" && currency !== "") {
    return formatMoney(raw, currency);
  }
  const shown = row.money_display?.[key];
  if (shown !== undefined) return shown;
  const bare = (row as unknown as Record<string, string | null | undefined>)[`${key}_display`];
  return bare ?? null;
}

function capsText(row: DiscountDetailRow): string {
  const one = (key: DiscountMoneyKey) => money(row, key) ?? DASH;
  return [one("cap_per_bill"), one("cap_per_year"), one("cap_lifetime")].join(" · ");
}

function stackingText(row: DiscountDetailRow, t: Translator): string {
  if (row.stacking_precedence === undefined) return DASH;
  const stacks = row.stacks_with_others === true ? t("rating.discountDetail.stacksWithOthers") : t("rating.discountDetail.stacksAlone");
  return `${row.stacking_precedence} · ${stacks}`;
}

function appliesText(row: DiscountDetailRow, t: Translator): string {
  const scope = word("scope", row.applies_to, t);
  const services = row.applies_to_services ?? [];
  const named = row.applies_to_charge_codes ?? [];
  if (row.applies_to === "one_service" && row.applies_to_service) {
    return `${scope} · ${t(`rating.service.${row.applies_to_service}`, { defaultValue: row.applies_to_service })}`;
  }
  if (row.applies_to === "specific_services" && services.length > 0) {
    return `${scope} · ${services.map((code) => t(`rating.service.${code}`, { defaultValue: code })).join(", ")}`;
  }
  if (row.applies_to === "named_codes" && named.length > 0) {
    return `${scope} · ${named.join(", ")}`;
  }
  return scope;
}

/** *Details* — everything step 1 of the form takes (image 19). */
export function detailsFacts(row: DiscountDetailRow, t: Translator): Fact[] {
  return [
    { id: "code", label: t("rating.discountForm.field.code"), value: text(row.code) },
    { id: "label", label: t("rating.discountForm.field.label"), value: text(row.name) },
    { id: "type", label: t("rating.discountForm.field.type"), value: typeWord(row, t) },
    { id: "owner", label: t("rating.discountForm.field.owner"), value: optionLabel(row.program_owner ?? row.programme_owner) },
    { id: "funding", label: t("rating.discountForm.field.funding"), value: text(row.funding_source) },
    { id: "assistance", label: t("rating.discountForm.field.assistance"), value: yesNo(row.report_in_assistance_filing, t) },
    { id: "value", label: t("rating.discountForm.review.value"), value: row.value_display ?? DASH },
    { id: "currency", label: t("rating.discountForm.field.currency"), value: text(row.currency) },
    { id: "applies", label: t("rating.discountForm.field.appliesTo"), value: appliesText(row, t) },
    { id: "caps", label: t("rating.discountForm.review.caps"), value: capsText(row) },
    { id: "floor", label: t("rating.discountForm.field.floor"), value: money(row, "bill_floor_amount") ?? DASH },
    { id: "stacking", label: t("rating.discountForm.field.stacking"), value: stackingText(row, t) },
    { id: "exclusivity", label: t("rating.discountForm.field.exclusivity"), value: optionLabel(row.exclusivity_group) },
  ];
}

function recertifyText(row: DiscountDetailRow, t: Translator): string {
  const months = row.recertification_months;
  if (months === null || months === undefined) {
    return row.recertification_months === null ? t("rating.discountWizard.lapse.never_expires") : DASH;
  }
  return `${months} ${t("rating.discountForm.unit.months")}`;
}

function noticeGraceText(row: DiscountDetailRow, t: Translator): string {
  const daysWord = t("rating.discountForm.unit.days");
  const one = (value: number | null | undefined) =>
    value === null || value === undefined ? DASH : `${value} ${daysWord}`;
  if (row.recertification_months === null) return DASH;
  return `${one(row.recertification_notice_days)} · ${one(row.recertification_grace_days)}`;
}

function budgetText(row: DiscountDetailRow, t: Translator): string {
  const cap = money(row, "budget_cap");
  if (cap === null || cap === undefined) return t("rating.discountForm.noCeiling");
  const period = word("period", row.budget_period, t);
  return period === DASH ? cap : `${cap} · ${period}`;
}

/** *Eligibility* — everything step 2 of the form takes (image 19). */
export function eligibilityFacts(row: DiscountDetailRow, t: Translator, regional: DiscountRegional): Fact[] {
  return [
    { id: "who", label: t("rating.discountForm.field.who"), value: optionLabel(row.eligibility) },
    { id: "enrollment", label: t("rating.discountForm.field.enrollment"), value: word("enrollment", row.enrolment_mode, t) },
    { id: "verification", label: t("rating.discountForm.field.verification"), value: word("verification", row.verification, t) },
    {
      id: "proofBefore",
      label: t("rating.discountForm.review.proofBefore"),
      value: yesNo(row.proof_before_first_reduction, t),
    },
    { id: "recertify", label: t("rating.discountForm.field.recertify"), value: recertifyText(row, t) },
    { id: "noticeGrace", label: t("rating.discountForm.review.noticeGrace"), value: noticeGraceText(row, t) },
    { id: "lapse", label: t("rating.discountForm.field.lapse"), value: word("lapse", row.lapse_behaviour, t) },
    { id: "starts", label: t("rating.discountForm.field.starts"), value: day(row.effective_from, regional) },
    {
      id: "ends",
      label: t("rating.discountForm.field.ends"),
      value:
        row.effective_from === null
          ? DASH
          : row.effective_to === null || row.effective_to === undefined
            ? t("rating.discountForm.noEnd")
            : day(row.effective_to, regional),
    },
    { id: "budget", label: t("rating.discountForm.review.budget"), value: budgetText(row, t) },
    { id: "budgetLeft", label: t("rating.discountDetail.budgetLeft"), value: money(row, "budget_remaining") ?? DASH },
    { id: "budgetOut", label: t("rating.discountForm.field.budgetOut"), value: word("out", row.exhaustion_behaviour, t) },
  ];
}

// ── The versions table ────────────────────────────────────────────────────

/**
 * What a version row's STATUS reads. Since ruling 1 an approved version is
 * stored `active` with its start date, so *Scheduled* (start not yet come) and
 * *Ended* (its window closed) are read from the dates, exactly as the server
 * derives a discount's own status.
 */
export function versionStatus(row: DiscountVersionLine, today: string): string {
  if (row.status === "pending_approval") return "waiting_approval";
  if (row.status !== "active") return row.status;
  if (row.effective_from !== null && row.effective_from > today) return "scheduled";
  if (row.effective_to !== null && row.effective_to !== undefined && row.effective_to < today) return "ended";
  return "active";
}

// ── The Audit tab ─────────────────────────────────────────────────────────

/** The WHAT column's word for each action the server writes. */
const ACTION_KEYS: Readonly<Record<string, string>> = {
  "discount.created": "rating.taxDetail.audit.action.created",
  // DEF-RAT-9310 — written on the COPY, naming the discount it came from.
  "discount.duplicated": "rating.discountDetail.audit.action.duplicated",
  "discount.updated": "rating.taxDetail.audit.action.updated",
  "discount.details_updated": "rating.taxDetail.audit.action.updated",
  "discount.gl_account_updated": "rating.taxDetail.audit.action.updated",
  "discount.version_drafted": "rating.discountDetail.audit.action.drafted",
  "discount.new_value": "rating.discountDetail.audit.action.newValue",
  "discount.version_updated": "rating.taxDetail.audit.action.updated",
  "discount.version_submitted": "rating.discountDetail.audit.action.submitted",
  "discount.version_approved": "rating.discountDetail.audit.action.approved",
  "discount.version_self_approved": "rating.discountDetail.audit.action.approved",
  "discount.version_sent_back": "rating.discountDetail.audit.action.sentBack",
  "discount.version_corrected": "rating.taxDetail.audit.action.corrected",
  "discount.correction_created": "rating.taxDetail.audit.action.correctionCreated",
  "discount.version_draft_discarded": "rating.discountDetail.audit.action.draftDeleted",
  "discount.retired": "rating.taxDetail.audit.action.retired",
  "discount.funding_exhausted": "rating.discountDetail.audit.action.fundingExhausted",
  "discount.made_available_on_plan": "rating.taxDetail.audit.action.attached",
  "discount.removed_from_plan": "rating.taxDetail.audit.action.detached",
  "discount.account_enrolled": "rating.discountDetail.audit.action.enrolled",
  "discount.enrolment_verified": "rating.discountDetail.audit.action.verified",
  "discount.enrolment_ended": "rating.discountDetail.audit.action.enrolmentEnded",
  "discount.automatic_enrolments_synced": "rating.discountDetail.audit.action.automatic",
  "discount.subsidy_granted": "rating.discountDetail.audit.action.granted",
};

export function auditWhat(action: string, t: Translator): string {
  const key = ACTION_KEYS[action];
  return key === undefined ? action : t(key);
}

/** The field labels the CHANGE column names — the form's own words. */
const FIELD_KEYS: Readonly<Record<string, string>> = {
  name: "rating.discountForm.field.label",
  code: "rating.discountForm.field.code",
  programme_owner: "rating.discountForm.field.owner",
  program_owner: "rating.discountForm.field.owner",
  funding_source: "rating.discountForm.field.funding",
  // `value` is the STORED magnitude (six places) and is never printed; the
  // `value_display` beside it on the same row names the same change.
  value_display: "rating.discountForm.review.value",
  effective_from: "rating.discountForm.field.starts",
  effective_to: "rating.discountForm.field.ends",
  recertification_notice_days: "rating.discountForm.field.notice",
  recertification_grace_days: "rating.discountForm.field.grace",
  recertification_months: "rating.discountForm.field.recertify",
  status: "rating.taxDetail.audit.field.status",
  enrolment_mode: "rating.discountForm.field.enrollment",
  verification_method: "rating.discountForm.field.verification",
  eligibility_summary: "rating.discountForm.field.who",
  exclusivity_group: "rating.discountForm.field.exclusivity",
  stacking_precedence: "rating.discountForm.field.stacking",
  bill_floor_amount_display: "rating.discountForm.field.floor",
  budget_cap_display: "rating.discountForm.field.budgetCap",
  ended_on: "rating.discountForm.field.ends",
};

/** Keys that move with every write and say nothing a clerk did. */
const QUIET_FIELDS = new Set([
  "version",
  "version_no",
  "updated_at",
  "created_at",
  "submitted_at",
  "approved_at",
  "reason",
  "change_reason",
  "correction_reason",
  "end_reason",
  "stored_status",
  "version_status",
  "version_submitted",
]);

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function auditValue(field: string, value: unknown, t: Translator, regional: DiscountRegional): string {
  if (value === null || value === undefined || value === "") {
    if (field === "effective_to") return t("rating.discountForm.noEnd");
    return DASH;
  }
  if (typeof value === "object" && !Array.isArray(value) && "label" in (value as Record<string, unknown>)) {
    return String((value as { label: unknown }).label);
  }
  if (Array.isArray(value)) return value.length === 0 ? DASH : value.map(String).join(", ");
  // A version's stored `pending_approval` reads as the page's own word.
  const raw = field === "status" && value === "pending_approval" ? "waiting_approval" : String(value);
  if (field === "status") return t(`rating.discounts.status.${raw}`, { defaultValue: t(`rating.status.${raw}`, { defaultValue: raw }) });
  if (ISO_DAY.test(raw)) return formatDate(raw, regional.timeZone, regional.dateFormat);
  return raw;
}

/**
 * The CHANGE column: each field that moved as *Notice: 0 → 30*; an enrolment
 * names the ACCOUNT NUMBER (the server swaps the id for it — B14 rule 31); a
 * plan link names the plan.
 */
export function auditChange(entry: DiscountAuditEntry, t: Translator, regional: DiscountRegional): string {
  const after = entry.after ?? {};
  const before = entry.before;
  if (typeof after.plan === "string") return after.plan;
  if (typeof after.from_code === "string") return after.from_code;
  if (typeof after.account === "string" && (entry.action.includes("enrol") || before === null)) {
    return after.account;
  }
  if (before === null) {
    const parts = ["status", "value_display", "eligibility"]
      .filter((field) => field in after && after[field] !== null && after[field] !== undefined)
      .map((field) => auditValue(field, after[field], t, regional));
    return parts.length === 0 ? DASH : parts.join(" · ");
  }
  const fields = Object.keys(after).filter((field) => !QUIET_FIELDS.has(field) && FIELD_KEYS[field] !== undefined);
  if (fields.length === 0) return DASH;
  return fields
    .map((field) => {
      const label = t(FIELD_KEYS[field] ?? field);
      return `${label}: ${auditValue(field, before[field], t, regional)} → ${auditValue(field, after[field], t, regional)}`;
    })
    .join(" · ");
}

/** WHO — the actor's NAME; an unnamed job reads *System*. */
export function auditWho(entry: DiscountAuditEntry, t: Translator): string {
  const name = entry.actor?.name ?? null;
  return name === null || name.trim() === "" ? t("rating.taxDetail.audit.system") : name;
}
