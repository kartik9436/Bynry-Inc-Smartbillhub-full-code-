// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 (EP-TEN-07 §Stories + its SCOPE ADDENDUM — the S63–S71 rule-page cards) ·
//           US-MET-011 (S64 read-validation config — TC-7 "no value is hardcoded")
//           Screens: S64, S66, S69, S70, S71
// Rules:    BR-SHL-035 (a rule page is a CARD whose management view is a FORM — same shell,
//           so a new rule page is a config row, never a new screen) ·
//           BR-MET-020 · BR-MET-025 · BR-MET-026 · BR-MET-027 · BR-MET-052 (S64 fields) ·
//           BR-BIL-001 · BR-BIL-002 · BR-BIL-008 · BR-BIL-021 · BR-BIL-029 · BR-PAY-010 ·
//           BR-PAY-038 (S66 — the WITHIN-invoice class sequence, a tenant setting since
//           the PO's ruling of 2026-08-12) · BR-CUS-050 (S66 fields) · BR-BIL-017 (S69
//           fields) · BR-PAY-013 · BR-PAY-016 · BR-PAY-017 · BR-PAY-018 (S70 fields) ·
//           BR-PAY-019 · BR-BIL-013 · BR-BIL-014 · BR-BIL-018 · BR-REP-022 · BR-LED-002
//           (S71 — the per-authority remitting basis, same ruling) ·
//           BR-TEN-024 (atomic per-tab save)
// ───────────────────────────────────────────────────────
// THE FIELD LAW, client side. This file is the mirror of the backend's
// `apps/tenancy/settings_families.py` registry: which parameters each of the
// five rule pages has, what KIND each is, and which rule names it. It holds no
// DEFAULTS and no LIMITS — those are the server's (it seeds them, it refuses
// out-of-range values), and a second copy here would be a second source of
// truth that drifts. What lives here is only what a form must know to draw an
// input and to send the right JSON type back.
//
// Two consequences of the backend's own law, carried faithfully:
//
//  1. **Decimals are STRINGS, start to finish.** A decimal parameter arrives as
//     a canonical string ("1.5", "200"), sits in the draft as that same string,
//     and goes back as that same string. Nothing here calls Number() on one —
//     a percent that becomes a binary float is exactly the silent production
//     error CLAUDE.md #2 forbids, and rounding is not the client's to do.
//
//  2. **A choice set with ONE value is not a dropdown.** `est_method`,
//     `allocation_order`, `level_rounding` and `correction_approval_mode` each
//     accept exactly one value today, because their rule names one and finance
//     has ratified no second (B4 payments-allocation is still a PLACEHOLDER;
//     BR-BIL-014's threshold variant is v2). The view renders those as a FIXED
//     control that says so. Offering a second option would be this screen
//     answering a question the Product Owner has not answered.
//
// `nullable` means the rule NAMES the parameter but ratifies no value —
// `minimum_bill_amount` (BR-BIL-021) and `settle_up_month` (BR-BIL-017). Empty
// posts null, which means UNSET. It never means zero: a consuming engine must
// refuse rather than assume.
//
// ── THE TWO PARAMETERS OF 2026-08-12, MIRRORED 2026-08-15 ──────────────────
// The backend registry grew two parameters and two KINDS on 2026-08-12 from the
// PO's two rulings of that day, and this mirror did not — so the storage, the
// validation and the callers were all live while no screen could reach either
// setting. That is hard-won law 2 (*built is not wired*) and this file is half
// of the fix; `SettingsAllocationOrder.tsx` and `SettingsRemittingBasis.tsx`
// are the other half.
//
//  · `allocation_class_order` (S66) — CHOICE_SEQUENCE. PO verbatim: *"Cant we
//    give option to user to set the rule in settings; Im not sure how Utilities
//    are going to set settlement rules ; they might differ in case of HOA or
//    SUb metering ; better to let user set the sequence; we can give default
//    option and allow them to change the order"*.
//  · `tax_remitting_basis_by_authority` (S71) — CHOICE_MAP. PO verbatim: *"E
//    Remit on what you BILLED, not what you collected - this is also correct"*.
//
// THE NO-DEFAULTS LAW ABOVE BINDS BOTH OF THEM, and for the second one it is
// the RULE and not merely a convention: the server seeds the basis map EMPTY on
// purpose, because LE-3 has State on collected and County on billed in the same
// month, so any default is wrong for one authority in month one. Nothing here
// supplies one, and there is deliberately no "restore the shipped order" button
// for the sequence either — the shipped order lives once, on the server, and a
// copy here would be free to drift from it. Reordering is reversible because
// every move has an inverse move and Discard restores the server's own answer.

/**
 * `money` is a decimal that happens to be an AMOUNT — same string handling as
 * `decimal`, but the view may echo it through the shared money formatter. The
 * distinction is display-only; neither is ever parsed.
 *
 * `choice_sequence` is an ORDER over a closed set: the value is a PERMUTATION
 * of `choices` — every member present, each exactly once, and the SEQUENCE is
 * the setting. `choice_map` is a per-item choice, `{item key: one of choices}`,
 * where an item with no entry is UNSET and unset is a real state rather than a
 * default in disguise. Both mirror
 * `apps/tenancy/settings_families.{CHOICE_SEQUENCE,CHOICE_MAP}`.
 */
export type RuleParamKind =
  | "decimal"
  | "money"
  | "int"
  | "bool"
  | "choice"
  | "int_list"
  | "choice_sequence"
  | "choice_map";

export interface RuleParam {
  /** The server's own field name — the JSON key and the i18n key stem. */
  key: string;
  kind: RuleParamKind;
  /** The rule that NAMES this parameter (the server cites it back on refusal). */
  br: string;
  /** BR-BIL-017/021: the rule names the parameter but ratifies no value. */
  nullable?: boolean;
  /** kind "choice": the values ratified TODAY. One entry = a fixed control. */
  choices?: readonly string[];
  /** A trailing unit label key, where the parameter has a unit (CLAUDE.md #3). */
  unitKey?: string;
}

export interface RulePage {
  /** The Reference-data card code this page opens from (BR-SHL-035). */
  card: string;
  /** The endpoint slug — `GET|PUT /settings/{slug}`. */
  slug: string;
  /** The A1 screen id, for the frame's kicker. */
  screen: string;
  /** The module that owns the CONTENT (BR-TEN-031), for the frame header. */
  owner: string;
  params: readonly RuleParam[];
}

// ── The two closed sets the 2026-08-12 parameters range over ───────────────

/**
 * THE FOUR WITHIN-INVOICE LINE CLASSES (BR-PAY-038). MIRRORED from
 * `apps.payments.allocation.ALLOCATION_CLASSES` by way of
 * `apps.tenancy.settings_families.ALLOCATION_CLASS_SEQUENCE`.
 *
 * **This is the SET, not the tenant's order and not the shipped default.** The
 * server's tuple happens to be written in the shipped order because one tuple
 * serves as both there; reading THIS array as a default would be the second
 * copy this file's header forbids. What a tenant is actually on arrives in the
 * document, and what the product ships with lives on the server alone.
 */
export const ALLOCATION_CLASSES = ["usage_base", "taxes", "tenant_defined", "fees"] as const;

/** The document key the sequence lives under, greppable from both sides. */
export const ALLOCATION_CLASS_ORDER_KEY = "allocation_class_order";

/**
 * BR-LED-002's two remitting bases, MIRRORED from
 * `apps.tenancy.settings_families.REMITTING_BASES` (itself a mirror of
 * `apps.ledger.journal.REMITTING_BASES`). BOTH are always computed; this
 * setting picks the one each authority FILES on.
 */
export const REMITTING_BASES = ["billed", "collected"] as const;

/** The document key the per-authority map lives under. */
export const REMITTING_BASIS_KEY = "tax_remitting_basis_by_authority";

const PCT = "settings.rules.unit.percent";
const DAYS = "settings.rules.unit.days";
/** `DEF-CUS-10445` — weekends and the utility's holidays not counted. */
const WORKING_DAYS = "settings.rules.unit.workingDays";
const MONTHS = "settings.rules.unit.months";
const YEARS = "settings.rules.unit.years";
// `HOURS` lived here for `final_notice_hours`, which moved to SET-12D with the
// rest of the ladder (see COLLECTIONS_PAGE). The catalogue key itself is alive
// and is used by `features/notifications/NotificationRules.tsx` — a key with no
// call site is what G18 calls dead, and deleting it here would have deleted the
// label off the screen that now owns the field.
// (`KWH`/`KGAL` unit keys left with S64 — see the note below.)

// ── S64 · Read validation & estimation — NOT A ROW HERE ANY MORE ───────────
// CR-038 A1 (PO 2026-08-26) made S64 a PER-SERVICE surface: one panel per
// enabled utility service, each floor in the service's OWN unit, integrity
// rules shown locked, the fail-safe "no figure — rule skipped and reported"
// state rendered honestly. That shape cannot be a flat param list, so S64 is
// a dedicated view (`SettingsReadValidation.tsx`, still inside the same
// BR-SHL-035 Reference-data frame) over `GET/PUT /settings/read-validation
// [/{service}]`, which metering now serves from the stores the ENGINE reads.
// The old flat READ_VALIDATION_PAGE wrote a tenancy document the engine never
// read — the divergence the CR exists to close.

// ── S66 · Billing defaults (billing) ───────────────────────────────────────
export const BILLING_DEFAULTS_PAGE: RulePage = {
  card: "billing_defaults",
  slug: "billing-defaults",
  screen: "S66",
  owner: "billing",
  params: [
    { key: "late_pct", kind: "decimal", br: "BR-BIL-001", unitKey: PCT },
    { key: "late_min_amount", kind: "money", br: "BR-BIL-001" },
    { key: "late_grace_days", kind: "int", br: "BR-BIL-008", unitKey: DAYS },
    { key: "late_grace_mode", kind: "choice", br: "BR-BIL-002", choices: ["calendar", "business"] },
    // BR-BIL-021 names the fallback; no value is ratified, so empty = UNSET.
    { key: "minimum_bill_amount", kind: "money", br: "BR-BIL-021", nullable: true },
    { key: "overcharge_guardrail_pct", kind: "decimal", br: "BR-BIL-029", unitKey: PCT },
    // BR-PAY-010 fixes the default order; B4 §Payments still carries a
    // PLACEHOLDER for partial-payment allocation, so there is no second value.
    // NOTE the name: this is the BETWEEN-bill walk — which bill the money meets
    // — and is a different parameter from `allocation_class_order` below, the
    // WITHIN-bill sequence. The server keeps the two names apart for the same
    // reason: a refusal has to say which of BR-PAY-010's clauses it is about.
    { key: "allocation_order", kind: "choice", br: "BR-PAY-010", choices: ["oldest_invoice_first"] },
    // The WITHIN-invoice sequence — a tenant setting since the PO's ruling of
    // 2026-08-12 (see this file's header). All four classes, each exactly once;
    // the server refuses anything that is not a permutation, because an order
    // that dropped a class would stop allocating money to it while every bill
    // still footed.
    {
      key: ALLOCATION_CLASS_ORDER_KEY,
      kind: "choice_sequence",
      br: "BR-PAY-038",
      choices: ALLOCATION_CLASSES,
    },
    { key: "deposit_interest_rate_annual", kind: "decimal", br: "BR-CUS-050", unitKey: PCT },
    // CR-181-BRC10 Q4 (PO 2026-10-13, *"keep 5 years right now"*) — how long a
    // closed account may be reopened by a returning customer at move-in.
    { key: "reopen_within_years", kind: "int", br: "BR-CUS-1119", unitKey: YEARS },
    // CR-183-BRC10 B3 (PO 2026-10-14, *"No minimum, 12 months maximum, set in
    // Settings … also set min limit to 10 days for time being"*) — how short
    // and how long a temporary stop may be. Defaults 10 and 12 live on the
    // server (`settings_families.BILLING_DEFAULTS`).
    { key: "temporary_stop_min_days", kind: "int", br: "BR-CUS-1121", unitKey: DAYS },
    { key: "temporary_stop_max_months", kind: "int", br: "BR-CUS-1121", unitKey: MONTHS },
  ],
};

// ── S69 · Budget billing rules (billing) ───────────────────────────────────
export const BUDGET_BILLING_PAGE: RulePage = {
  card: "budget_billing",
  slug: "budget-billing",
  screen: "S69",
  owner: "billing",
  params: [
    { key: "eligibility_months", kind: "int", br: "BR-BIL-017", unitKey: MONTHS },
    { key: "level_rounding", kind: "choice", br: "BR-BIL-017", choices: ["whole_dollar"] },
    { key: "relevel_drift_pct", kind: "decimal", br: "BR-BIL-017", unitKey: PCT },
    { key: "relevel_cadence_months", kind: "int", br: "BR-BIL-017", unitKey: MONTHS },
    // BR-BIL-017 names the settle-up month but ratifies none — UNSET until the
    // tenant picks one. An empty field here is not "January".
    { key: "settle_up_month", kind: "int", br: "BR-BIL-017", nullable: true },
    { key: "drop_off_missed_payments", kind: "int", br: "BR-BIL-017" },
    { key: "override_bound_pct", kind: "decimal", br: "BR-BIL-017", unitKey: PCT },
  ],
};

// ── S70 · Collections & notices (payments) ─────────────────────────────────
export const COLLECTIONS_PAGE: RulePage = {
  card: "collections_notices",
  slug: "collections",
  screen: "S70",
  owner: "payments",
  params: [
    // ⚠ THE THREE LADDER TIMINGS MOVED TO SET-12D ON 2026-08-17 (CR-009,
    // BR-NOT-017). PO verbatim: *"we bring all internal external ntification
    // rule sat one place and they are part of notification settings"*. They
    // were `reminder_days_after_due` (3), `notice_tier_days` ([10, 5]) and
    // `final_notice_hours` (48), and they are edited now on Settings →
    // Notifications → Past-due reminder / Final disconnect notice.
    //
    // **THE STORE DID NOT MOVE AND MUST NOT.** All five ruled figures — those
    // three plus the $25.00 balance floor and the 25% partial-payment pause,
    // which have never had a screen anywhere (DEF-204, DEF-097) — stay in
    // `apps.tenancy.settings_families.COLLECTIONS`, where the live collections
    // engine reads them, and SET-12D writes them through this same
    // `PUT /settings/collections`. What changed is the DOOR, not the room: two
    // editors over one figure is the "second home for the same rule" CR-009
    // itself warned against, and the copy that drifts is the one a customer's
    // disconnect notice is scheduled from.
    //
    // The rows BELOW stay here deliberately. The PO's ruling enumerates five
    // figures and these are not among them: a payment-plan reminder cadence,
    // an NSF privilege count and paper suppression are collections POLICY that
    // this card has always owned. Moving them too would be this lane deciding
    // something nobody ruled.
    { key: "plan_reminder_days_before", kind: "int", br: "BR-PAY-016", unitKey: DAYS },
    { key: "plan_missed_notice_days_after", kind: "int", br: "BR-PAY-016", unitKey: DAYS },
    { key: "plan_void_after_misses", kind: "int", br: "BR-PAY-016" },
    { key: "nsf_privilege_n", kind: "int", br: "BR-PAY-013" },
    { key: "suppress_paper_on_bad_address", kind: "bool", br: "BR-PAY-018" },
  ],
};

// ── S71 · Finance controls (ledger) ────────────────────────────────────────
export const FINANCE_CONTROLS_PAGE: RulePage = {
  card: "finance_controls",
  slug: "finance-controls",
  screen: "S71",
  owner: "ledger",
  params: [
    { key: "bank_match_date_tolerance_days", kind: "int", br: "BR-PAY-019", unitKey: DAYS },
    // ── CR-008 #7 (PO 2026-08-17) — the AMOUNT half of the bank match ──────
    // *"Okay. We can take it as threshold from user"*. The server seeds it to
    // **0**, and 0 is not a placeholder: `abs(batch − line) <= 0` is exactly
    // the penny-exact `==` the matcher used before this parameter existed, so
    // a tenant who never touches it sees no change. The DEFAULT lives on the
    // server (this file holds no defaults and no limits, see the header).
    { key: "bank_match_amount_tolerance", kind: "money", br: "BR-PAY-019" },
    // ⚠ THE TWO WRITE-OFF FIGURES BELOW MEAN DIFFERENT THINGS, and their
    // labels are the only thing that keeps them apart on this page:
    //   write_off_threshold_amount          — BR-BIL-013's AUTOMATIC clear-out
    //     of a tiny residue on a FINAL bill ($5, capped $50). Its label was
    //     *"Small-balance write-off limit"* and is now the unambiguous
    //     sentence (CR-008 ruling 2).
    //   write_off_approval_threshold_amount — the MANUAL collections write-off
    //     (`apps/payments/writeoffs.py`). Seeded **0.00**, which means every
    //     write-off of every size still needs an approver, exactly as today.
    { key: "write_off_threshold_amount", kind: "money", br: "BR-BIL-013" },
    { key: "write_off_approval_threshold_amount", kind: "money", br: "BR-PAY-020" },
    { key: "dso_target_days", kind: "int", br: "BR-REP-022", unitKey: DAYS },
    // BR-BIL-014 (OQ-072 CLOSED) fixes v1 at "ALL corrections need System Admin
    // approval"; the threshold variant is v2 — one ratified value, fixed control.
    { key: "correction_approval_mode", kind: "choice", br: "BR-BIL-014", choices: ["all"] },
    { key: "back_bill_cap_months", kind: "int", br: "BR-BIL-018", unitKey: MONTHS },
    { key: "back_bill_theft_exempt", kind: "bool", br: "BR-BIL-018" },
    // The per-authority remitting basis — a tenant setting since the PO's
    // ruling of 2026-08-12 (see this file's header). NO DEFAULT, and that is
    // the rule rather than an omission: the map ships EMPTY, an authority with
    // no entry is UNSET, and the S41 report names the unset ones instead of
    // claiming a basis for them.
    {
      key: REMITTING_BASIS_KEY,
      kind: "choice_map",
      br: "BR-LED-002",
      choices: REMITTING_BASES,
    },
  ],
};

// ── S8 · Reports (tenancy) — `CR-142-BRC07` `P4.6` ─────────────────────────
//
// **TWO CARDS, ONE FAMILY, ONE ENDPOINT.** The drawing (p047 legend ④) gives
// *File retention* and *Default format* a card each, and the server keeps both
// in one `reports` family because `PUT /settings/reports` takes a PARTIAL
// change set: a form that knows one key posts one key and leaves the other
// alone. Two families would have been two jsonb columns for two values and a
// second audit action for one screen section.
//
// ⚠ **`default_download_format` HAS ONE RATIFIED VALUE AND THE HOLE IS
// SIGNED.** `apps/reports/models.FORMATS` is `("csv",)` because no PDF
// renderer is declared anywhere in this product. This file's header already
// names that shape — *"a choice set with ONE value is not a dropdown"* — and
// the view draws a fixed control that says so. `allocation_order` and
// `level_rounding` are the precedents.
export const REPORTS_RETENTION_PAGE: RulePage = {
  card: "file_retention",
  slug: "reports",
  screen: "S8",
  owner: "tenancy",
  params: [
    // BR-REP-018 CONFIRMED (PO 2026-08-08, IS-11): *"Generated files are
    // retained 3 days by default, tenant-configurable"*. The server holds the
    // default and the minimum of 1 — this file holds no defaults and no
    // limits, by its own header's rule.
    { key: "file_retention_days", kind: "int", br: "BR-REP-018", unitKey: DAYS },
  ],
};

export const REPORTS_FORMAT_PAGE: RulePage = {
  card: "default_format",
  slug: "reports",
  screen: "S8",
  owner: "tenancy",
  params: [
    { key: "default_download_format", kind: "choice", br: "BR-REP-018", choices: ["csv"] },
  ],
};

// ── S8 · Accounts → Service requests (tenancy) — `DEF-CUS-10445` ────────────
//
// PO 2026-10-22: the acknowledgement's target date is the customer's preferred
// date and, with none, *"Default 15 days"* after the request — a SETTING, not a
// constant (*"don't do any hardcoding"*). WORKING days, and the same number
// opens a new request's Connection date (ruled 2026-09-22 as *"15 working
// days"*). The 15 and the minimum of 0 are the server's
// (`settings_families.SERVICE_REQUESTS`); this file holds neither.
export const SERVICE_REQUESTS_PAGE: RulePage = {
  card: "service_requests",
  slug: "service-requests",
  screen: "S8",
  owner: "tenancy",
  params: [
    {
      key: "service_request_default_target_days",
      kind: "int",
      br: "BR-CUS-079",
      unitKey: WORKING_DAYS,
    },
  ],
};

export const RULE_PAGES: readonly RulePage[] = [
  BILLING_DEFAULTS_PAGE,
  BUDGET_BILLING_PAGE,
  COLLECTIONS_PAGE,
  FINANCE_CONTROLS_PAGE,
  REPORTS_RETENTION_PAGE,
  REPORTS_FORMAT_PAGE,
  SERVICE_REQUESTS_PAGE,
];

/** The rule page a Reference-data card opens, or null when it is not one. */
export function rulePageForCard(cardCode: string): RulePage | null {
  return RULE_PAGES.find((page) => page.card === cardCode) ?? null;
}

// ── Draft ↔ document (pure — provable without a browser or a network) ──────

/**
 * The editing shape. Everything is a STRING except booleans, because that is
 * what an <input> holds — and because keeping a decimal as the server's own
 * string all the way through is the only way it survives untouched.
 */
export type RuleDraft = Record<string, string | boolean>;

/** The value union the server serves and accepts (endpoints.RuleValue). */
export type RuleFieldValue =
  | string
  | number
  | boolean
  | number[]
  | string[]
  | Record<string, string>
  | null;

/**
 * BR-SHL-035's form body needs one draft per page. A decimal string is copied
 * VERBATIM — `String()` on "1.500000" is "1.500000", and it is never routed
 * through Number(), so what the server stored is what the user sees and what
 * goes back if untouched.
 */
export function draftFromDocument(
  page: RulePage,
  document: Record<string, RuleFieldValue>,
): RuleDraft {
  const draft: RuleDraft = {};
  for (const param of page.params) {
    const value = document[param.key];
    if (param.kind === "bool") {
      draft[param.key] = value === true;
      continue;
    }
    if (param.kind === "int_list") {
      // The ladder edits as the plain list a person would write.
      draft[param.key] = Array.isArray(value) ? value.join(", ") : "";
      continue;
    }
    if (param.kind === "choice_sequence") {
      draft[param.key] = Array.isArray(value) ? sequenceToDraft(value as string[]) : "";
      continue;
    }
    if (param.kind === "choice_map") {
      draft[param.key] = basisMapToDraft(asChoiceMap(value));
      continue;
    }
    // null (UNSET) renders as an empty field, never as "0" or "null".
    draft[param.key] = value === null || value === undefined ? "" : String(value);
  }
  return draft;
}

// ── choice_sequence: the ORDER, held in the draft as its own text ──────────
//
// A RuleDraft holds strings, because that is what an <input> holds — and the
// two 2026-08-12 parameters are not typed into an input at all. They are still
// held as text here, and DELIBERATELY: `ruleIsDirty` and `ruleChanges` compare
// draft values with `!==`, which is exact on a string and meaningless on the
// object it would otherwise be (two equal orders would compare unequal and the
// page would post a change nobody made). So each is CANONICALLY encoded — the
// sequence as its members in order, the map with its keys sorted — and a
// round trip through the encoding is the identity.

/** `["usage_base","taxes"] → "usage_base,taxes"`. Order IS the value. */
export function sequenceToDraft(order: readonly string[]): string {
  return order.join(",");
}

/** The inverse. An empty draft is an empty order, never a guessed one. */
export function sequenceFromDraft(raw: string | boolean): string[] {
  return String(raw)
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item !== "");
}

/**
 * One step of the reorder control: the member at `index` swaps with its
 * neighbour `delta` places away. Out-of-range moves return the order UNCHANGED
 * rather than wrapping — the first row's "up" and the last row's "down" are
 * disabled in the view, and a no-op here is what makes that safe rather than
 * merely tidy.
 *
 * A swap is its own inverse, which is the whole of "reversible": there is no
 * separate undo to build and no client-side copy of the shipped order to
 * restore from (see this file's header).
 */
export function moveInSequence(
  order: readonly string[],
  index: number,
  delta: number,
): string[] {
  const target = index + delta;
  if (index < 0 || index >= order.length || target < 0 || target >= order.length) {
    return [...order];
  }
  const next = [...order];
  next[index] = order[target];
  next[target] = order[index];
  return next;
}

// ── choice_map: the per-item choice, held in the draft as canonical JSON ───

function asChoiceMap(value: RuleFieldValue): Record<string, string> {
  if (value === null || value === undefined || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  const out: Record<string, string> = {};
  for (const [item, choice] of Object.entries(value as Record<string, unknown>)) {
    if (typeof choice === "string") {
      out[item] = choice;
    }
  }
  return out;
}

/** Canonical JSON — KEYS SORTED, so two equal maps encode byte-identically. */
export function basisMapToDraft(map: Record<string, string>): string {
  const sorted: Record<string, string> = {};
  for (const item of Object.keys(map).sort()) {
    sorted[item] = map[item];
  }
  return JSON.stringify(sorted);
}

/** The inverse. Unparseable text is an EMPTY map — never a partial one. */
export function basisMapFromDraft(raw: string | boolean): Record<string, string> {
  const text = String(raw).trim();
  if (text === "") {
    return {};
  }
  try {
    return asChoiceMap(JSON.parse(text) as RuleFieldValue);
  } catch {
    return {};
  }
}

/**
 * Set — or CLEAR — one item's choice.
 *
 * An empty `choice` DELETES the key rather than storing `""` or `null`. That is
 * the server's own shape (`apps/tenancy/settings_families` refuses a null value
 * inside the map, precisely so that "absent" and "null" cannot become two
 * spellings of one state), and it is what makes "unset" survive a save: a
 * tenant who clears an authority's basis gets the report saying that authority
 * is still to be decided, which is the honest answer.
 */
export function withChoiceFor(
  map: Record<string, string>,
  item: string,
  choice: string,
): Record<string, string> {
  const next = { ...map };
  if (choice === "") {
    delete next[item];
  } else {
    next[item] = choice;
  }
  return next;
}

/**
 * Text → the JSON type the server expects, WITHOUT deciding anything:
 *
 *  · decimal/money — the trimmed string, exactly as typed. No parse, no round.
 *  · int — a clean integer becomes a number; anything else is sent AS TYPED so
 *    the server's own `settings.param_not_integer` explains it. Silently
 *    coercing "25.5" to 25 would change a threshold behind the user's back.
 *  · int_list — the same rule, per item, in the order written (BR-PAY-017's
 *    ladder is ordered; this never sorts it).
 *  · choice_sequence — the members in the order the tenant put them. Nothing
 *    here checks that it is a permutation: the server owns that refusal
 *    (`settings.param_not_permutation`) and a second copy of the check would
 *    be a second copy of the rule.
 *  · choice_map — the item→choice map, items with no choice simply absent.
 *  · empty + nullable — null, meaning UNSET (never zero).
 */
export function ruleFieldValue(param: RuleParam, raw: string | boolean): RuleFieldValue {
  if (param.kind === "bool") {
    return raw === true;
  }
  if (param.kind === "choice_sequence") {
    return sequenceFromDraft(raw);
  }
  if (param.kind === "choice_map") {
    // An EMPTY map is a legitimate value (nothing chosen yet) and is posted as
    // `{}` — never as null, which the server would read as "required".
    return basisMapFromDraft(raw);
  }
  const text = String(raw).trim();
  if (param.kind === "int_list") {
    return text
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item !== "")
      .map((item) => asIntegerOrText(item)) as number[];
  }
  if (text === "") {
    // A non-nullable blank is still sent as null: the server answers
    // `settings.param_required` and names the rule, which beats this screen
    // inventing a value or refusing to ask.
    return null;
  }
  if (param.kind === "int") {
    return asIntegerOrText(text);
  }
  return text; // decimal / money / choice — the string, untouched
}

const CLEAN_INTEGER = /^-?\d+$/;

// A clean integer rides as a number; anything else rides as the raw text so the
// SERVER refuses it in its own words. Typed as number for the list payload —
// the escape hatch is deliberate and narrow (see ruleFieldValue's docstring).
function asIntegerOrText(text: string): number {
  return (CLEAN_INTEGER.test(text) ? Number.parseInt(text, 10) : text) as number;
}

/**
 * BR-TEN-024: the PUT carries only what the user actually changed — a partial
 * change set, and the response is the whole page again. An untouched page
 * therefore sends `{}` and cannot silently rewrite a threshold.
 */
export function ruleChanges(
  page: RulePage,
  draft: RuleDraft,
  original: RuleDraft,
): Record<string, unknown> {
  const changes: Record<string, unknown> = {};
  for (const param of page.params) {
    if (draft[param.key] !== original[param.key]) {
      changes[param.key] = ruleFieldValue(param, draft[param.key]);
    }
  }
  return changes;
}

export function ruleIsDirty(page: RulePage, draft: RuleDraft, original: RuleDraft): boolean {
  return page.params.some((param) => draft[param.key] !== original[param.key]);
}

/**
 * A choice set with exactly one ratified value renders as a FIXED control. The
 * view says the other values are not ratified rather than drawing a dropdown
 * that can only pick what is already picked.
 */
export function choiceIsFixed(param: RuleParam): boolean {
  return param.kind === "choice" && (param.choices?.length ?? 0) <= 1;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07, whose SCOPE ADDENDUM adds the S63–S71 cards; co-packet EP-MET-04@34f14b6 for the S64 field law)
// generated: 2026-08-09 by story-coder v1 (W0 frontend integration lane — the five rule pages)
// amended:   2026-08-15 by story-coder (settings-screens lane) — the client mirror catches up with the
//            backend registry's 2026-08-12 growth: two KINDS (`choice_sequence`, `choice_map`) and the
//            two parameters the PO's two rulings of that day created — `allocation_class_order` on S66
//            and `tax_remitting_basis_by_authority` on S71. Both were stored, validated and READ BY
//            THEIR CALLERS from 2026-08-15 with no screen behind either, which is hard-won law 2.
//            The draft encoding is canonical on purpose (sequence = members in order, map = JSON with
//            keys SORTED) so BR-TEN-024's change-set comparison stays exact on a string.
// checklist: A✔ B✔ C✔ D=deferred(pure config — the endpoint half is api/endpoints.ts) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · [2026-08-15 settings-screens lane] see the lane report: tsc✔ eslint✔ vitest✔ run_gates 19 PASS / 1 FAIL (G8, another lane's apps/billing/backbill.py — this lane's baseline, unchanged)
// exceptions: E3 the S63–S71 stories (US-TEN-013..017) are ALLOCATED but UNAUTHORED, so this file is anchored on EP-TEN-07's scope addendum + 11b §2.3 + US-MET-011 for S64 and cites no story ID that does not exist — reported · E4 no default or range limit is duplicated here: the server seeds and refuses, and a second copy would drift (a range refusal therefore only appears AFTER a save attempt) — deliberate, reported · E2 the overcharge guardrail sits on S66 here because that is where 11b §2.3 and the backend registry put it, while the EP-TEN-07 addendum lists it under S71 — same divergence the backend reported, not re-decided · E4 [2026-08-15] a THIRD backend parameter is still unmirrored and is REPORTED rather than added: `back_bill_segment_estimate_source` (S71, BR-BIL-018 as amended by OQ-191, PO ruling 2026-08-12 *"B is correct; and if required give option C also as backup"*) has been in `apps/tenancy/settings_families.FINANCE_CONTROLS` since 2026-08-12 and appears in no `RulePage` here, so a tenant cannot choose between `day_weighted` and `metering`. It is the same unwired class this lane exists to close and is left alone deliberately: `apps/billing/backbill.py` — the engine that reads it — belongs to a lane running concurrently, and two lanes adding the same client mirror row is how one of them gets silently dropped. FLAGGED for that lane or the next one
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
