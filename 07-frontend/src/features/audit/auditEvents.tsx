// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-645 (2026-08-24) — the PO walking the deployed v2.42.0:
//           "you are showing some database keys on audit screen". One cell read,
//           verbatim: `account.created · id: 01a01d9a-4609-7637-ad8d-0cbb1cf8d9cc;
//           name: Ana Alvarez; plan: — (+38 more)`.
// Story:    US-AUD-004 (S61 viewer) · US-AUD-005 (the row detail)
// Rules:    BR-AUD-003 (the standard payload: snapshot on create, changed fields on
//           update, before-only on a terminal action) · BR-AUD-006 (a masked value
//           renders exactly as stored — nothing here unmasks anything) ·
//           BR-AUD-009 (the S61 columns) · BR-AUD-010 (a per-entity Audit tab is a
//           WINDOW into the same rows, so both surfaces must read alike) ·
//           B14 rule 21 (Tailwind utilities, no stylesheet class — G31/route-B)
// ───────────────────────────────────────────────────────
//
// THE AUDIT EVENT, WRITTEN AS A SENTENCE.
//
// Four faults were in that one cell and each has its own answer here:
//
//   1. a raw 36-character UUID primary key   → identifiers are never rendered.
//   2. `account.created`, a machine code     → a per-event sentence, "Account opened".
//   3. `name:` / `plan:`, raw column names   → field labels in words.
//   4. `(+38 more)` — 38 things the reader   → the WHOLE set, fetched on expand
//      cannot see, and no way to see them       through the shared Disclosure.
//
// ⚠ WHY THE DETAIL IS FETCHED AND NOT PARSED. The list row carries `summary`,
// which the server builds by joining the first THREE fields and appending
// "(+N more)" (apps/audit/selectors.summarize). The remaining fields are not in
// that string at all, so no amount of client-side parsing can reach them — the
// only honest way to make the full set reachable is `GET /audit-log/{id}`,
// which serves the stored `before`/`after` whole. That is why this component
// holds a query instead of a regex, and why nothing here reads `row.summary`
// for anything except "does this event have a payload at all".
//
// ⚠ WHAT AN EVENT THIS FILE DOES NOT KNOW RENDERS, AND WHY IT IS NOT DERIVED
// FROM THE CODE. A new action code will appear here before its sentence does.
// It renders "Activity recorded" plus a muted "this event type is not described
// yet" — it does NOT print the code, and it does NOT humanise the code into
// "Widget frobnicated". `routesCyclesShared.frequencyKey` already ruled that
// shape in this repo: a word the vocabulary does not know is a FACT ABOUT THE
// DATA, and dressing it up "would quietly make an unruled ninth frequency look
// like a supported one". The expandable field list still renders in full for an
// unknown event, so an auditor still reads WHAT changed — only the verb is
// withheld, because inventing it is the thing we must not do. The code itself
// travels on `data-audit-action` for support, the way a BR-code travels on
// `data-br-ref` since DEF-322 — in the DOM, never in the text.
//
// ⚠ EVERY `t()` CALL HERE GOES THROUGH `auditText`, WHICH ALWAYS SUPPLIES THE
// ENGLISH. The keys below are new and are NOT yet in the eleven catalogues
// (this lane may not edit them; they are handed over in newkeys-M2.json). A
// missing key would otherwise render its own NAME on the screen — the exact
// defect G27 exists for — so the fallback is not a convenience, it is the
// guarantee. `t(key, { defaultValue })` is the pattern G27's own docstring
// names as correct for a key whose name is data.
//
// ⚠ NO STYLESHEET CLASS IS ADDED BY THIS FILE (B14 rule 21). It is registered
// in `styles/route-b-migrated.txt` so `routeBUtilities.test` asks the stricter,
// compiler-backed question of every utility below.
import { useQuery } from "@tanstack/react-query";
import { Fragment } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAuditEntry } from "@/api/endpoints";
import type { AuditEntry, AuditRow } from "@/api/endpoints";
import { Disclosure } from "@/components/Disclosure";
import type { Translator } from "@/features/tenancy/settingsShared";

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/**
 * Every string this file draws, with its English beside it.
 *
 * The catalogue keys do not exist yet (see the header). Passing `defaultValue`
 * on every call means a missing key renders the sentence, never the key name.
 */
export function auditText(
  t: Translator,
  key: string,
  english: string,
  params?: Record<string, unknown>,
): string {
  return t(key, { defaultValue: english, ...(params ?? {}) });
}

// ── 1 · the event vocabulary ───────────────────────────────────────────────
//
// EVERY CODE BELOW HAS AN EMITTER IN `06-backend`, found by walking the call
// sites of `core.audit.write_row` / `money_action` and each module's own
// `_audit()` wrapper with `ast`. Nothing is invented: an event with no emitter
// gets no sentence here, it gets the unknown state, because a sentence for an
// event that cannot happen is a claim about a product we do not have.
//
// Six codes are composed at runtime rather than written as literals —
// `apps/metering/import_runs.py` builds `f"{run.target}.created"` and three
// siblings over TARGETS = (premises, units, assets_meters, assets_submeters,
// assets_devices, accounts). Those 24 combinations are expanded at the bottom
// of this map from the same tuple, so the two stay in step by construction.
const IMPORT_TARGETS: Record<string, string> = {
  premises: "Premises",
  units: "Units",
  assets_meters: "Meters",
  assets_submeters: "Sub-meters",
  assets_devices: "Devices",
  accounts: "Accounts",
};

const IMPORT_VERBS: Record<string, string> = {
  created: "created by an import",
  updated: "updated by an import",
  deactivated_by_replace: "deactivated by a replacing import",
  rolled_back: "restored when an import was rolled back",
};

function importedEventSentences(): Record<string, string> {
  const built: Record<string, string> = {};
  for (const [target, noun] of Object.entries(IMPORT_TARGETS)) {
    for (const [verb, phrase] of Object.entries(IMPORT_VERBS)) {
      built[`${target}.${verb}`] = `${noun} ${phrase}`;
    }
  }
  return built;
}

/** action code → the sentence a person would say. */
export const AUDIT_EVENT_SENTENCES: Record<string, string> = {
  ...importedEventSentences(),

  // customers
  "account.activated": "Account activated",
  // DEF-PAY-6342 — `accounts.bad_address`, now written by customers alone.
  "account.bad_address.cleared": "Bad address cleared",
  "account.bad_address.flagged": "Bad address flagged",
  "account.bulk_imported": "Accounts imported in bulk",
  "account.closed": "Account closed",
  "account.created": "Account opened",
  "account.created_by_import": "Account opened by an import",
  "account.import_staged": "Account import staged for review",
  "account.master_created": "Master account opened",
  "account.moved_in": "Move-in recorded",
  // DEF-AUD-9727 (CR-171-BRC10) — the move-in's own acts, written by
  // customers' move_fees / move_in_flow / move_in_cancel; read on the move-in
  // details view's Audit tab and on this page.
  "move_in.fees_recorded": "Move-in fees recorded",
  "move_in.payment_taken": "Move-in payment taken",
  "move_in.opening_reads_entered": "Opening reads entered",
  "move_in_job.cancelled": "Move-in canceled",
  "account.nsf_recorded": "Returned payment recorded",
  "account.reversed_by_import": "Account import reversed",
  "account.updated": "Account details updated",
  "accounts.created_by_import": "Accounts opened by an import",
  "note.created": "Note added",
  "note.updated": "Note edited",
  "plan.changed": "Plan changed",
  "payment_plan.activated": "Payment plan started",
  "payment_plan.closed": "Payment plan closed",
  "payment_plan.closed_on_write_off": "Payment plan closed by a write-off",
  "payment_plan.proposed": "Payment plan proposed",
  "payment_plan.rows_written": "Payment plan instalments scheduled",
  "service_request.acknowledgement": "Request acknowledged to the customer",
  "service_request.address_resolved": "Request address confirmed",
  "service_request.approved": "Request approved",
  "service_request.category_set": "Request category set",
  "service_request.child_linked": "Follow-up request linked",
  "service_request.created": "Request created",
  "service_request.customer_linked": "Request linked to a customer",
  "service_request.document_attached": "Document attached to the request",
  "service_request.document_rejected": "Request document rejected",
  "service_request.document_requirement_set": "Required documents set for the request",
  "service_request.document_verified": "Request document verified",
  "service_request.fee_collected": "Request fee collected",
  "service_request.fee_quoted": "Request fee quoted",
  "service_request.fee_waived": "Request fee waived",
  "service_request.manually_closed": "Request closed by hand",
  "service_request.numbered": "Request numbered",
  "service_request.outcome_decided": "Request outcome decided",
  "service_request.parked": "Request put on hold",
  "service_request.refused": "Request refused",
  "service_request.resumed": "Request taken off hold",
  "service_request.services_set": "Services on the request set",
  "service_request.submitted": "Request submitted",
  "service_request.updated": "Request updated",

  // metering · assets
  "asset.assigned": "Meter or device assigned",
  "asset.bulk_assigned": "Meters or devices assigned in bulk",
  "asset.created": "Meter or device added",
  "asset.deleted": "Meter or device deleted",
  "asset.final_read_captured": "Final read captured",
  "asset.maintenance_logged": "Maintenance logged",
  "asset.pairing_review_flagged": "Meter pairing flagged for review",
  "asset.reassigned": "Meter or device reassigned",
  "asset.recreated_from_retired": "Meter or device re-created from a retired one",
  "asset.retired": "Meter or device retired",
  "asset.rolled_back_by_import": "Meter or device restored when an import was rolled back",
  "asset.sample_valuation_set": "Sample valuation set",
  "asset.status_changed": "Meter or device status changed",
  "asset.updated": "Meter or device updated",
  "assets.created_by_import": "Meters or devices added by an import",
  "assets.updated_by_import": "Meters or devices updated by an import",
  "cycle.created": "Billing cycle created",
  "cycle.deleted": "Billing cycle deleted",
  "cycle.updated": "Billing cycle updated",
  "import_run.extracted": "Import file read",
  "import_run.loaded": "Import loaded",
  "import_run.rolled_back": "Import rolled back",
  "import_run.row_fixed": "Import row corrected",
  "import_run.transformed": "Import rows prepared",
  "import_run.validated": "Import checked",
  "premises.created": "Premises added",
  "premises.deactivated": "Premises deactivated",
  // CR-089 wave D — the other half of BR-MET-1164's control. Without a
  // sentence here the audit row for a reactivation reads "Activity recorded".
  "premises.reactivated": "Premises put back in service",
  "premises.deleted": "Premises deleted",
  "premises.updated": "Premises updated",
  "read.billed_correction_opened": "Correction opened on a billed read",
  "read.dispute_cleared": "Read dispute cleared",
  "read.disputed": "Read disputed",
  "read.estimated": "Read estimated",
  "read.export_record_missing": "Read missing from an export",
  "read.final_read_captured": "Final read captured",
  "read.superseded": "Read replaced by a later one",
  "read_batch.discarded": "Batch of reads discarded",
  "read_batch.posted": "Batch of reads posted",
  "read_batch.staged": "Batch of reads staged",
  "read_batch.validated": "Batch of reads checked",
  "read_row.deleted": "Read removed from a batch",
  "read_row.dispositioned": "Read in a batch dealt with",
  "read_window.closed": "Reading window closed",
  "route.created": "Route created",
  "route.deactivated": "Route deactivated",
  "route.deleted": "Route deleted",
  "route.members_cascaded": "Route membership updated",
  "route.premises_order_changed": "Walk order changed",
  "route.updated": "Route updated",
  "unit.created": "Unit added",
  "unit.deactivated": "Unit deactivated",
  "unit.reactivated": "Unit put back in service",
  "unit.deleted": "Unit deleted",
  "unit.moved": "Unit moved",
  "unit.plan_assigned": "Plan assigned to a unit",
  "unit.plan_bulk_assigned": "Plans assigned to units in bulk",
  "unit.updated": "Unit updated",
  "unit_plan_assignment.backdated": "Unit plan assignment backdated",

  // rating
  "charge.created": "Charge code created",
  "charge.deleted": "Charge code deleted",
  "charge.updated": "Charge code updated",
  "discount.account_enrolled": "Account enrolled in a discount",
  "discount.created": "Discount created",
  "discount.enrolment_ended": "Discount enrolment ended",
  "discount.enrolment_verified": "Discount enrolment verified",
  "discount.funding_exhausted": "Discount funding used up",
  "discount.made_available_on_plan": "Discount offered on a plan",
  "discount.retired": "Discount retired",
  "discount.subsidy_granted": "Subsidy granted",
  // ⚠ These two are chosen by a TERNARY at the call site, which is why the
  // first sweep of literal arguments missed them and the LIVE seed found
  // them (`discount.version_approved`, 49 rows in the demo tenant).
  "discount.version_approved": "Discount version approved",
  "discount.version_self_approved": "Discount version approved by its author",
  "discount.version_activated": "Discount version activated",
  "discount.version_drafted": "Discount version drafted",
  "discount.version_submitted": "Discount version submitted for approval",
  "plan.archived": "Plan archived",
  "plan.created": "Plan created",
  "plan.deleted": "Plan deleted",
  "plan.published": "Plan published",
  "plan.updated": "Plan updated",
  "plan.version_created": "Plan version created",
  "rating.bulk_rate_update": "Rates updated in bulk",
  "tariff.activated": "Rate schedule activated",
  "tariff.archived": "Rate schedule archived",
  "tariff.created": "Rate schedule created",
  "tariff.draft_saved": "Rate schedule draft saved",
  "tariff.duplicated": "Rate schedule copied",
  "tariff.updated": "Rate schedule updated",
  "tariff.version_created": "Rate schedule version created",
  "tax.activated": "Tax activated",
  "tax.corrected": "Tax corrected",
  "tax.correction_created": "Tax correction created",
  "tax.created": "Tax created",
  "tax.deactivated": "Tax deactivated",
  "tax.reactivated": "Tax reactivated",
  "tax.updated": "Tax updated",
  "tax_exemption_category.created": "Tax exemption category created",
  "tax_exemption_certificate.recorded": "Tax exemption certificate recorded",
  "tax_exemption_certificate.revoked": "Tax exemption certificate revoked",
  "tax_jurisdiction.created": "Tax jurisdiction created",

  // billing
  "bill_run.catch_up_created": "Catch-up bill run created",
  "bill_run.created": "Bill run created",
  "bill_run.queue_row_resolved": "Bill run queue item resolved",
  "bill_run.release_authorised": "Bill run release authorised",
  "bill_run.released": "Bill run released",
  "budget.enrolled": "Budget billing started",
  "budget.overridden": "Budget billing amount overridden",
  "budget.releveled": "Budget billing amount re-levelled",
  "budget.removed": "Budget billing ended",
  "budget.settled": "Budget billing settled up",
  "correction.abandoned": "Correction abandoned",
  "correction.approved": "Correction approved",
  "correction.case_opened": "Correction case opened",
  "correction.document_reissued": "Corrected bill reissued",
  "correction.executed": "Correction applied",
  "correction.executed_batch": "Corrections applied in bulk",
  "invoice.drafted": "Bill drafted",
  "invoice.issued": "Bill issued",
  "template.archived": "Bill template archived",
  "template.created": "Bill template created",
  "template.published": "Bill template published",
  "template.draft_deleted": "Bill template draft deleted",
  "template.registered": "Bill template registered",
  "template.saved": "Bill template saved",
  "template.version_deleted": "Bill template version deleted",

  // payments · collections
  "account.opening_credit_imported": "Opening credit imported",
  "autopay_intent.recorded": "Autopay intent recorded",
  "bad_address.cleared": "Bad-address flag cleared",
  "bank_rec.confirmed": "Bank reconciliation confirmed",
  "bank_rec.resolved": "Bank reconciliation item resolved",
  "bank_statement.imported": "Bank statement imported",
  "batch.reconciled": "Deposit batch reconciled",
  "batch.unreconciled": "Deposit batch put back to unreconciled",
  "collection.restarted": "Collections started again",
  "collection.step": "Collections step taken",
  "credit.applied": "Credit applied",
  "delivery.held": "Delivery held",
  "delivery.released": "Delivery released",
  "delivery.requeued": "Delivery queued again",
  "delivery.returned": "Bill returned undelivered",
  "deposit_batch.created": "Deposit batch created",
  "deposit_batch.regrouped": "Deposit batch regrouped",
  "notice.generated": "Notice prepared",
  "notice.sent": "Notice sent",
  "payment.allocated": "Payment allocated",
  "payment.nsf": "Payment returned unpaid",
  "payment.recorded": "Payment recorded",
  "payment.reversed": "Payment reversed",
  "refund.approved": "Refund approved",
  "refund.cleared": "Refund cleared",
  "refund.issued": "Refund issued",
  "refund.requested": "Refund requested",
  "refund.voided": "Refund voided",
  "write_off.approved": "Write-off approved",
  "write_off.requested": "Write-off requested",

  // ledger
  "export.batch_created": "Export batch created",
  "journal.auto_forwarded": "Journal entry carried forward automatically",
  "journal.auto_reversed": "Journal entry reversed automatically",
  "journal.draft_deleted": "Journal draft deleted",
  "journal.draft_saved": "Journal draft saved",
  "journal.draft_updated": "Journal draft updated",
  "journal.posted": "Journal entry posted",
  "journal.reversed": "Journal entry reversed",
  "ledger_account.code_changed": "Ledger account code changed",
  "ledger_account.created": "Ledger account created",
  "ledger_account.deactivated": "Ledger account deactivated",
  "ledger_account.deleted": "Ledger account deleted",
  "ledger_account.export_code_updated": "Ledger account export code updated",
  "ledger_account.imported": "Ledger accounts imported",
  "ledger_account.reactivated": "Ledger account reactivated",
  "ledger_account.updated": "Ledger account updated",
  "period.closed": "Accounting period closed",
  "period.reopened": "Accounting period reopened",
  "supplier_invoice.captured": "Supplier invoice recorded",
  "supplier_invoice.updated": "Supplier invoice updated",
  "supplier_invoice.voided": "Supplier invoice voided",
  "tieout.drift_detected": "Ledger tie-out drift found",

  // identity
  "auth.lockout": "Sign-in locked after repeated failures",
  "auth.password_changed": "Password changed",
  "auth.password_reset": "Password reset",
  "auth.sign_in": "Signed in",
  "auth.sign_in_failed": "Sign-in failed",
  "auth.sign_out": "Signed out",
  "user.deactivated": "User deactivated",
  "user.email_changed": "User email changed",
  "user.invited": "User invited",
  "user.owner_provisioned": "Owner account created",
  "user.profile_updated": "User profile updated",
  "user.reactivated": "User reactivated",
  "user.removed": "User removed",
  "user.role_changed": "User role changed",

  // notifications
  "notification_rule.toggled": "Notification rule turned on or off",
  "notification_rule.updated": "Notification rule updated",
  "notification_sender.updated": "Notification sender updated",
  "notification_settings.updated": "Notification settings updated",
  "outbound_batch.dispatched": "Message batch sent",
  // ⚠ A CREDENTIAL DISCLOSURE, WHICH IS WHY IT IS AUDITED AT ALL. While a
  // utility has no provider connected for a channel, a message that nothing can
  // send may be READ from its queue row — including a portal sign-up code, and
  // that code is the whole of the portal's defence at the door. So who looked,
  // and at which message, is a fact the utility must be able to recover. The
  // code itself is deliberately NOT in the payload (see
  // `apps/notifications/unsent_preview.py`): `audit_log` outlives a ten-minute
  // code by years and a copy here would be a second, longer-lived secret.
  "outbound_message.body_disclosed": "Message content shown to staff",
  "outbound_message.queued": "Message queued to send",

  // tenancy · settings · platform
  "audit.exported": "Audit log exported",
  // ⚠ NAMED BY THE STORY, NOT BY AN EMITTER. `billing_settings.updated` is
  // EP-AUD-02 §4's own fixture and US-AUD-005 TC-1's worked example, and no
  // service in 06-backend writes it — the shipped code is
  // `settings.billing_defaults.updated` below. The divergence is REPORTED, not
  // reconciled here; the sentence exists because a ratified test case names it.
  "billing_settings.updated": "Billing settings updated",
  "checklist.item_marked_done": "Setup step marked done",
  "custom_field.created": "Custom field created",
  "custom_field.deactivated": "Custom field switched off",
  "custom_field.reactivated": "Custom field switched on",
  "custom_field.placement_changed": "Custom field moved",
  "custom_field.updated": "Custom field updated",
  "import_mapping.saved": "Import column mapping saved",
  "list.exported": "List exported",
  "reference.seeded": "Reference data set up",
  "reference.sweep_failed": "Reference data check failed",
  "report.exported": "Report exported",
  "sample.removed": "Sample data removed",
  "sample.seed_incomplete": "Sample data only partly set up",
  "sample.seeded": "Sample data set up",
  "settings.billing_defaults.updated": "Billing defaults updated",
  "settings.budget_billing.updated": "Budget billing settings updated",
  "settings.collections.updated": "Collections settings updated",
  "settings.company_logo.updated": "Company logo updated",
  "settings.company_logo.moved_to_store": "Company logo moved to storage",
  "settings.company_profile.updated": "Company profile updated",
  "settings.finance_controls.updated": "Finance controls updated",
  "settings.holiday.created": "Holiday added",
  "settings.holiday.deleted": "Holiday removed",
  "settings.holiday.updated": "Holiday updated",
  "settings.lookup.created": "Reference list entry added",
  "settings.lookup.deleted": "Reference list entry removed",
  "settings.lookup.updated": "Reference list entry updated",
  "settings.numbering.bulk_updated": "Numbering updated",
  "settings.numbering.caught_up": "Numbering caught up",
  "settings.numbering.updated": "Numbering updated",
  "settings.read_validation.updated": "Reading checks updated",
  "settings.read_validation.service_updated": "Reading checks updated for a service",
  "settings.regional_fiscal.updated": "Regional and fiscal settings updated",
  "settings.security_updated": "Security settings updated",
  "settings.service.disabled": "Service switched off",
  "settings.service.enabled": "Service switched on",
  "settings.service_gl.updated": "Service accounting codes updated",
  "settings.service_uom.updated": "Service unit of measure updated",
  "security.attempt_refused": "Blocked attempt recorded",
  "plan_service.base_charge_migrated": "Base charge moved onto a charge code",
  "monthly_usage.restated": "Monthly usage restated",
  "monthly_usage.stated": "Monthly usage stated",
  "monthly_usage.withdrawn": "Monthly usage withdrawn",
  "tenant.provision_failed": "Sign-up could not be completed",
  "tenant.provisioned": "Organisation set up",
};

export interface AuditEventSentence {
  /** The sentence to draw. Never a code, never a payload. */
  text: string;
  /** False when this file has no sentence for the action — see the header. */
  known: boolean;
}

/** The Action cell's sentence, for BOTH surfaces (BR-AUD-010: one reading). */
export function auditEventSentence(action: string, t: Translator): AuditEventSentence {
  const code = (action ?? "").trim();
  const english = AUDIT_EVENT_SENTENCES[code];
  if (english === undefined) {
    return { text: auditText(t, "audit.event.unknown", "Activity recorded"), known: false };
  }
  return { text: auditText(t, `audit.event.${code}`, english), known: true };
}

// ── 2 · what may never reach the screen ────────────────────────────────────

/**
 * A stored UUID — the primary key the PO photographed. UNANCHORED on purpose:
 * `"migrated from 01a01d9a-…"` leaks exactly as much as the bare key does.
 */
export const UUID_SHAPED =
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

/**
 * ⚠ AND OUR OWN ID GRAMMAR, WHICH IS THE SECOND THING IN THESE PAYLOADS.
 * `account_detail_dict` stores `"plan_snapshot_unavailable": "BR-CUS-029"`, so
 * a rule id is a VALUE here, not a label — the one place G28's catalogue sweep
 * can never look. CLAUDE.md's grammar: US-/EP-/BR-<MOD>-### · OQ/GT/TC/IS/ADR.
 *
 * ANCHORED, unlike the UUID above, and the asymmetry is deliberate: a whole
 * value that IS a rule id is an internal reference, while a sentence that
 * happens to mention one is a message whose meaning would be destroyed by
 * dropping it. Hiding real recorded data is its own defect on an audit trail.
 */
export const RULE_ID_SHAPED =
  /^(?:US|EP|BR)-[A-Z]{3}-\d{2,5}$|^(?:OQ|GT|TC|IS|ADR|DEF|CR)-\d{1,5}$/;

/** True when this value is an internal reference a utility must never read. */
export function isInternalReference(value: unknown): boolean {
  if (typeof value !== "string") {
    return false;
  }
  const text = value.trim();
  return UUID_SHAPED.test(text) || RULE_ID_SHAPED.test(text);
}

/**
 * Keys that exist to be read by US, not by a clerk — dropped whole.
 *
 * ⚠ THIS IS THE `data-br-ref` REMEDY, NOT A NEW ONE (DEF-322, then DEF-2377).
 * G28 already ruled that `br_ref` is a MACHINE field which is SUPPOSED to hold a
 * rule id — *"a gate that demanded `br_ref` contain no rule id would be asking
 * the field to stop being itself"* — and that the fix is to stop RENDERING it
 * rather than to empty it. `job` is the same case one rule further back:
 * BR-AUD-003 requires a system job be NAMED in the payload, so
 * `"job": "payments.refund"` is the standard being obeyed, and the Actor column
 * already tells a person "System job" in words. Both stay in the stored record
 * for support and neither reaches a sentence a clerk reads.
 *
 * `06-backend` writes both; `10-scripts/gates/g71_audit_payload_prose.py` exempts
 * exactly these two names and cites this constant as the reason it may.
 */
export const MACHINE_FIELDS: ReadonlySet<string> = new Set(["br_ref", "job"]);

/**
 * True when the FIELD is an identifier, whatever it holds.
 *
 * `id` goes first and unconditionally: DEF-645's fault (1) is that the row is
 * already ON that record, so its own key adds nothing and costs trust. A
 * `*_id` key is the same thing pointing sideways — `unit_id` names a record
 * this screen cannot open and whose value is a key.
 */
export function isIdentifierField(key: string, value: unknown): boolean {
  return (
    key === "id" ||
    key.endsWith("_id") ||
    MACHINE_FIELDS.has(key) ||
    isInternalReference(value)
  );
}

// ── 2b · what the row is ABOUT ─────────────────────────────────────────────

/**
 * The entity types worth saying properly. Everything else is humanised, exactly
 * as `FIELD_LABELS` and `humaniseFieldKey` already work one section below — this
 * map exists for the plurals the server stores (`invoices`, `payment_plans`) and
 * for the handful whose mechanical reading is wrong, not for all 91 of them.
 */
const ENTITY_LABELS: Record<string, string> = {
  account_budget_status: "Budget billing",
  account_import_batch: "Account import",
  account_note: "Account note",
  asset_monthly_usage: "Monthly usage",
  audit_log: "Audit entry",
  autopay_capture_intent: "Autopay charge",
  bank_rec_match_set: "Bank match",
  bank_statement_import: "Bank statement import",
  bill_run_exclusions: "Bill run exclusion",
  bill_template_versions: "Bill layout version",
  bill_templates: "Bill layout",
  correction_cases: "Correction",
  delivery_return_events: "Returned delivery",
  discount_enrolment: "Discount enrolment",
  invoice_document_instances: "Bill document",
  invoices: "Bill",
  invoice: "Bill",
  ledger_account_import: "Chart of accounts import",
  lookup_entry: "List entry",
  notification_template: "Message template",
  payment_plan_installments: "Payment plan instalment",
  payment_plans: "Payment plan",
  plan_discount_rule: "Plan discount rule",
  premises_owner: "Premises owner",
  rate_change_batch: "Scheduled rate change",
  read_import_batch: "Reading import",
  read_import_row: "Imported reading",
  read_validation_service_settings: "Reading checks",
  read_validation_settings: "Reading checks",
  service_request_document_requirement: "Required document",
  stored_document: "Stored document",
  tenant: "Utility",
  tenant_membership: "Team member",
  tenant_service: "Utility service",
  tenant_settings: "Settings",
  tie_out: "Tie-out",
  unit_plan_assignment: "Unit plan",
  wizard_park: "Park",
};

/**
 * WHAT THE ROW IS ABOUT, IN WORDS — never the id (B14 rule 31, DEF-2378).
 *
 * ⚠ WHY THIS IS A TYPE AND NOT A NAME, AND IT WAS CHECKED BEFORE IT WAS
 * ACCEPTED. The audit list serves `entity_type` + `entity_id` and nothing else
 * (`apps/audit/selectors.audit_row`), and it is a read ACROSS EVERY MODULE — 91
 * distinct entity types today, owned by ten modules, with no shared name column
 * between them. The one cross-module lookup the server already makes is
 * `actor_names`, a single bulk read of ONE table. Resolving a name per row would
 * be a lookup per entity type per page, against tables `apps/audit` may not
 * query (B1, BR-TEN-013) — and it would still answer nothing for a HARD-DELETED
 * record, which US-AUD-005 TC-6 says must keep rendering. So the honest cell is
 * the KIND of record, and the id travels on `title` and `data-audit-entity-id`
 * for support, the way a rule id has travelled on `data-br-ref` since DEF-322.
 */
export function auditEntityLabel(entityType: string, t: Translator): string {
  const type = (entityType ?? "").trim();
  if (type === "") {
    return auditText(t, "audit.entity.unknown", "Record");
  }
  const known = ENTITY_LABELS[type];
  return known === undefined
    ? auditText(t, `audit.entity.${type}`, humaniseFieldKey(type))
    : auditText(t, `audit.entity.${type}`, known);
}

// ── 3 · field labels, in words ─────────────────────────────────────────────

/** The names worth saying properly. Everything else is humanised below. */
const FIELD_LABELS: Record<string, string> = {
  account_no: "Account number",
  account_subtype: "Account subtype",
  account_type: "Account type",
  bad_address: "Bad address",
  closed_at: "Closed",
  code: "Code",
  credit_tier: "Credit tier",
  currency: "Currency",
  custom_data: "Custom fields",
  customer_no: "Customer number",
  deposit_on_file: "Deposit on file",
  deposit_received_on: "Deposit received",
  email: "Email",
  kind: "Kind",
  name: "Name",
  nsf_count: "Returned payments",
  opened_at: "Opened",
  phone: "Phone",
  plan: "Plan",
  preferred_language: "Preferred language",
  premise: "Premises",
  reason: "Reason",
  service_agreements: "Services",
  status: "Status",
  status_behavior_class: "Status behaviour",
  status_name: "Status",
  tax_exempt: "Tax exempt",
  tax_exempt_expires: "Tax exemption expires",
  tax_exempt_ref: "Tax exemption reference",
  unit_label: "Unit",
};

/**
 * A key with no entry above, said in words.
 *
 * ⚠ THIS IS NOT "print the column name". `service_point_id` never reaches here
 * (it is an identifier field and is dropped); what does reach here is
 * `read_window_closes_on` → "Read window closes on". The transformation is
 * mechanical and lossless, and it is the difference between DEF-645's `plan:`
 * and a label — but the good wording lives in FIELD_LABELS above, and a key
 * that reads badly belongs there, not in a cleverer humaniser.
 */
export function humaniseFieldKey(key: string): string {
  const words = key.replace(/_/g, " ").trim();
  if (words === "") {
    return "";
  }
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function auditFieldLabel(key: string, t: Translator): string {
  const known = FIELD_LABELS[key];
  return known === undefined
    ? auditText(t, `audit.field.${key}`, humaniseFieldKey(key))
    : auditText(t, `audit.field.${key}`, known);
}

// ── 4 · values ─────────────────────────────────────────────────────────────

const VALUE_LIMIT = 80;

/**
 * One stored value as a person reads it. Never JSON, never an id.
 *
 * BR-AUD-006: a masked value renders exactly as stored — this formats, it
 * never unmasks and never reaches for the value behind a mask.
 */
export function formatAuditValue(value: unknown, t: Translator): string {
  if (value === null || value === undefined || value === "") {
    return auditText(t, "audit.value.notSet", "Not set");
  }
  if (typeof value === "boolean") {
    return value
      ? auditText(t, "audit.value.yes", "Yes")
      : auditText(t, "audit.value.no", "No");
  }
  // ⚠ THE PARAM IS `n`, NOT `count`, AND THAT IS DELIBERATE. `count` is
  // i18next's plural trigger, so it would send this key looking for
  // `audit.value.count_one` / `_other` — per-language key sets, which is
  // exactly the drift DEF-224 ruled against here. The wording carries no
  // inflection, so it needs no plural.
  if (Array.isArray(value)) {
    return value.length === 0
      ? auditText(t, "audit.value.none", "None")
      : auditText(t, "audit.value.count", "{{n}} recorded", { n: value.length });
  }
  if (typeof value === "object") {
    const size = Object.keys(value as Record<string, unknown>).length;
    return size === 0
      ? auditText(t, "audit.value.none", "None")
      : auditText(t, "audit.value.count", "{{n}} recorded", { n: size });
  }
  const text = String(value);
  return text.length <= VALUE_LIMIT ? text : `${text.slice(0, VALUE_LIMIT - 1)}…`;
}

// ── 5 · the changed set ────────────────────────────────────────────────────

export interface AuditFieldRow {
  key: string;
  label: string;
  /** null when there was no previous value to show (a create snapshot). */
  before: string | null;
  after: string;
}

export interface AuditFieldSet {
  fields: AuditFieldRow[];
  /** How many fields were dropped because they held an internal reference. */
  hiddenReferences: number;
}

type Payload = Record<string, unknown> | null;

/**
 * BR-AUD-003 read literally, the same three shapes `summarize()` reads on the
 * server — but WITHOUT its three-field cut, and with identifiers removed.
 */
export function auditFieldSet(before: Payload, after: Payload, t: Translator): AuditFieldSet {
  const beforeMap = before !== null && typeof before === "object" ? before : null;
  const afterMap = after !== null && typeof after === "object" ? after : null;
  const fields: AuditFieldRow[] = [];
  let hiddenReferences = 0;

  const push = (key: string, previous: unknown, next: unknown, withBefore: boolean): void => {
    if (isIdentifierField(key, next) || isIdentifierField(key, previous)) {
      hiddenReferences += 1;
      return;
    }
    fields.push({
      key,
      label: auditFieldLabel(key, t),
      before: withBefore ? formatAuditValue(previous, t) : null,
      after: formatAuditValue(next, t),
    });
  };

  if (beforeMap === null && afterMap !== null) {
    // create: the snapshot.
    for (const [key, value] of Object.entries(afterMap)) {
      push(key, undefined, value, false);
    }
  } else if (afterMap === null && beforeMap !== null) {
    // terminal: before-only. The row still says what the value WAS.
    for (const [key, value] of Object.entries(beforeMap)) {
      push(key, value, undefined, true);
    }
  } else if (beforeMap !== null && afterMap !== null) {
    // update: changed fields only, in the server's own key order.
    const keys = [
      ...Object.keys(beforeMap),
      ...Object.keys(afterMap).filter((key) => !(key in beforeMap)),
    ];
    for (const key of keys) {
      if (JSON.stringify(beforeMap[key]) !== JSON.stringify(afterMap[key])) {
        push(key, beforeMap[key], afterMap[key], true);
      }
    }
  }
  return { fields, hiddenReferences };
}

// ── 6 · the rendered pieces ────────────────────────────────────────────────

/** The changed set as a definition list. Used by the tab AND the S61 drawer. */
export function AuditFieldList(props: { set: AuditFieldSet; t: Translator }) {
  const { set, t } = props;
  if (set.fields.length === 0) {
    return (
      <p className={`m-0 text-sm ${MUTED}`} data-audit="no-fields">
        {set.hiddenReferences > 0
          ? auditText(
              t,
              "audit.details.onlyReferences",
              "Only internal record links were recorded for this event, so there is nothing readable to show.",
            )
          : auditText(t, "audit.details.noFields", "No values were recorded for this event.")}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <dl className="m-0 grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3 gap-y-1 text-sm [&_dd]:m-0 [&_dt]:font-heading [&_dt]:font-semibold">
        {set.fields.map((field) => (
          // A Fragment, not a wrapper element: `<dl>` is a grid here, and any
          // real element between it and its `<dt>`/`<dd>` would take the grid
          // cell instead of the pair.
          <Fragment key={field.key}>
            <dt>{field.label}</dt>
            <dd data-audit-field={field.key}>
              {field.before === null ? (
                field.after
              ) : (
                <>
                  <span className={MUTED}>{field.before}</span>
                  <span aria-hidden="true" className={MUTED}>
                    {" → "}
                  </span>
                  <span>{field.after}</span>
                </>
              )}
            </dd>
          </Fragment>
        ))}
      </dl>
      {set.hiddenReferences > 0 && (
        <p className={`m-0 text-sm ${MUTED}`}>
          {auditText(
            t,
            "audit.details.hiddenReferences",
            "Internal record links are not shown.",
          )}
        </p>
      )}
    </div>
  );
}

function AuditEventDetail(props: { entryId: string; client: ApiClient; t: Translator }) {
  const { t } = props;
  // Only ever runs when a reader has OPENED this row: Disclosure unmounts its
  // body when closed, so a 25-row tab makes no requests until asked. That is
  // also why the static-render tests never reach the network.
  const entryQuery = useQuery({
    queryKey: ["audit-log", "entry", props.entryId] as const,
    queryFn: () => getAuditEntry(props.entryId, props.client),
    retry: false,
  });

  if (entryQuery.isPending) {
    return (
      <p className={`m-0 text-sm ${MUTED}`}>
        {auditText(t, "audit.details.loading", "Reading the recorded values…")}
      </p>
    );
  }
  const entry: AuditEntry | undefined = entryQuery.data;
  if (entry === undefined) {
    return (
      <p className={`m-0 text-sm ${MUTED}`} role="alert">
        {auditText(
          t,
          "audit.details.failed",
          "The recorded values could not be read. The full audit log still has this entry.",
        )}
      </p>
    );
  }
  return <AuditFieldList set={auditFieldSet(entry.before, entry.after, t)} t={t} />;
}

/** The sentence alone — S61 draws it in its own Action column. */
export function AuditEventSentenceText(props: { row: AuditRow; t: Translator }) {
  const { row, t } = props;
  const sentence = auditEventSentence(row.action, t);
  return (
    <span data-audit-action={row.action}>
      {sentence.text}
      {!sentence.known && (
        <>
          {" · "}
          <span className={`text-sm ${MUTED}`}>
            {auditText(t, "audit.event.undescribed", "this event type is not described yet")}
          </span>
        </>
      )}
    </span>
  );
}

/**
 * The recorded values, in words, behind one expand — S61's Summary column.
 *
 * ⚠ THIS IS WHAT REPLACES `(+38 more)`. The server's summary string is read for
 * ONE bit of information — is there a payload at all — and is never drawn; the
 * fields come from `GET /audit-log/{id}`, whole, on expand.
 */
export function AuditEventChanges(props: { row: AuditRow; t: Translator; client?: ApiClient }) {
  const { row, t } = props;
  if ((row.summary ?? "").trim() === "") {
    return (
      <span className={`text-sm ${MUTED}`} data-audit="empty">
        {auditText(t, "audit.details.noFields", "No values were recorded for this event.")}
      </span>
    );
  }
  return (
    <Disclosure
      variant="row"
      title={auditText(t, "audit.details.title", "What changed")}
    >
      <AuditEventDetail entryId={row.id} client={props.client ?? api} t={t} />
    </Disclosure>
  );
}

export function AuditEventCell(props: { row: AuditRow; t: Translator; client?: ApiClient }) {
  const { row, t } = props;
  const client = props.client ?? api;
  const sentence = auditEventSentence(row.action, t);
  const undescribed = sentence.known ? undefined : (
    <span className={`text-sm ${MUTED}`}>
      {auditText(t, "audit.event.undescribed", "this event type is not described yet")}
    </span>
  );
  // `summary` is the server's own answer to "is there a payload at all" — the
  // only thing this component reads it for. Its CONTENT is what DEF-645 is
  // about and is never drawn.
  const hasPayload = (row.summary ?? "").trim() !== "";

  if (!hasPayload) {
    return (
      <span data-audit-action={row.action}>
        {sentence.text}
        {undescribed !== undefined && <> · {undescribed}</>}
      </span>
    );
  }
  return (
    <div data-audit-action={row.action}>
      <Disclosure variant="row" title={sentence.text} summary={undescribed}>
        <AuditEventDetail entryId={row.id} client={client} t={t} />
      </Disclosure>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-645 (12-governance/10-defect-log.csv) + US-AUD-004/005 · BR-AUD-003/006/009/010
// generated: 2026-08-24 by the DEF-645 lane (M2)
// checklist: A✔ B✔ C=n/a(no API change — the presenter reads two endpoints that already exist) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ (this lane's files; a sibling lane's ServiceRequestDetailPage.tsx is red in the shared tree) · eslint --max-warnings 0✔ · vitest 2293 passed / 1 skipped / 188 todo across 134 files✔ (the whole suite, green) · routeBUtilities✔ (proved RED first with a planted `itmes-center`) · G28✔ G31✔ G32 G37✔ unchanged by this lane · browser walkthrough in Chromium on the seeded stack (S21 Audit tab collapsed + expanded, S61 list + drawer)
// exceptions: [DEF-2378 lane 2026-09-02] ⚠ THE E3 BELOW IS CLOSED AND IS KEPT AS
//   THE RECORD OF WHAT REPORTING-INSTEAD-OF-FILING COSTS. It read: "the S61
//   ENTITY column still renders `entity_type · entity_id`, which is a stored id
//   on a live tenant … Reported to the PO rather than changed here." Nine days
//   later the Product Owner reported that cell from a live deployment in the
//   words "DB Keys are displayed". A lane exception is not a defect row and
//   nothing tracked it; the rule it names, B14 rule 31, was already ratified.
//   The cell now says WHAT THE RECORD IS (`auditEntityLabel`) and the id travels
//   on `title` and `data-audit-entity-id`. G69 clause 2 keeps it that way.
// gates: [DEF-2377/2378 lane 2026-09-02] tsc✔ · eslint --max-warnings 0✔ · vitest auditEvents.test.tsx 22 passed✔ (this lane adds 4) · run_gates 56 PASS / 13 FAIL / 3 SKIP, the same thirteen as the pre-lane baseline · G69✔ G71✔ G28✔ G31✔ G44✔ · the DEF-2377 suite keeps its OWN red proof: `proves the guard bites` feeds the presenter the exact sentence the Product Owner photographed and asserts it still trips the rule-id and table-name patterns
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
