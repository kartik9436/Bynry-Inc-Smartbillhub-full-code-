// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-025 (S30 All-bills list — the capability row, the segments,
//           the bill-number rule) · US-BIL-026 (S30 bill detail — the pinned
//           document, the stamped lines, the A19 summary) · US-BIL-027 (void —
//           its state gate and its consequence message, both server-side)
//           Screens: S30 (entered from the AppShell sidebar → Billing, and from
//           the S21 Bills tab)
// Rules:    BR-BIL-004 (issued bills are immutable — this module offers no edit
//           affordance anywhere and no write wrapper exists) · BR-BIL-009 (a
//           void shows its plain-language consequence BEFORE confirm, computed
//           server-side) · BR-BIL-063 (every bill carries a number from the
//           moment it is drafted — PO 2026-08-11; a served null is still
//           rendered as a stated absence, never a blank) · BR-BIL-024 (the due date is derived at issue) ·
//           BR-BIL-026 (template + version pinned; the SERVER renders the
//           document forever) · BR-BIL-030 (the bill is LOCKED at issue: the
//           document renders from the frozen instance, not from live joins) ·
//           BR-CUS-040 (a reprint re-renders the ISSUED document, never
//           recomputes) · BR-SHL-010 (a capability not declared is not
//           rendered) · BR-SHL-011 (the URL grammar) · BR-SHL-020 (plain
//           language when something is absent) · BR-SHL-025 (a forbidden
//           control renders disabled WITH its reason)
// ───────────────────────────────────────────────────────
// The pieces S30 is built from. They live beside the screens so the honesty
// rules below are components rather than conventions the next billing screen
// could forget.
//
// FOUR THINGS THIS MODULE REFUSES TO DO:
//
//   1. **It never prints a blank where a bill number would be.** Every bill
//      now carries one, drafts included (BR-BIL-063, PO 2026-08-11 — this
//      module previously said the opposite, and DEF-033 is reversed with it).
//      But the field is SERVED and a served field can be null, and an empty
//      identity cell reads as a number that failed to render — so `BillNumber`
//      still renders a stated absence with its reason instead.
//
//   2. **It never derives past-due from the due date.** Past-due is
//      `issued ∧ unpaid ∧ due_date < today` (US-BIL-025 §5) — DERIVED, never
//      stored. Two of those three terms are not this lane's to read: "unpaid"
//      is the payments/ledger position (B1) and "today" is the tenant's clock
//      (BR-TEN-043). A browser comparing `due_date` to `Date.now()` would call
//      a PAID bill past-due. So the flag is the server's, and a null renders as
//      unknown, never as "not past due".
//
//   3. **It never opens `bill_payload`.** BR-BIL-030 freezes a complete
//      document instance at issue and BR-CUS-040 says a reprint re-renders THAT
//      instance — July's name and address, not today's. BR-BIL-026 puts the
//      render on the server (the pinned template version), so the detail screen
//      embeds `GET /invoices/{id}/document` and this module has no payload
//      parser. Stage 6 (assemble-document) is being authored in
//      `apps/billing/` right now; a second guess at its JSON keys here is how
//      two lanes ship one schema twice.
//
//   4. **It never claims the read API is missing.** The two routes S30 needs
//      are contracted (11b §2.8) and unserved today, and a hardcoded "not built
//      yet" string is a comment claiming a fact (hard-won law 1) that goes
//      stale the hour the route lands. `listRouteAbsent` DERIVES it from the
//      response instead: a collection route that answers 404 does not exist,
//      and the day it does the message stops appearing with nothing edited.
import type { ReactNode } from "react";

import { isApiError } from "@/api/client";
import { BILL_TYPES } from "@/api/endpoints";
import type { InvoiceRow } from "@/api/endpoints";
import type { StatusTone } from "@/components/StatusPill";
import type { Translator } from "@/features/tenancy/settingsShared";

// ── Permission (A4 / BR-IDN-014) ───────────────────────────────────────────
// A4 has ONE row for this surface — "Reads & Billing runs": System Admin Full ·
// Billing Clerk Full · Executive View. Declared once here so the list, the
// detail and the account's Bills tab cannot gate on three copies of the code.
export const BILLING_PERMISSION = "reads_billing_runs";

// ── Routes (the AppShell sidebar's own path — SHELL_NAV `billing`) ─────────
// TENANT-RELATIVE, like every route constant since path tenancy landed (PO
// 2026-08-10): the screen that navigates puts it through `tenantPath()`.

export const BILLING_ROUTE = "/billing";
export const DASHBOARD_ROUTE = "/dashboard";

/** The Budget Bills tab. */
export const BUDGET_TAB_ROUTE = `${BILLING_ROUTE}/budget`;

/**
 * §05 entry 25.1 `Enrol` — the one-at-a-time enrolment form.
 *
 * ⚠ **IT LIVES HERE AND NOT IN EITHER SCREEN, TO BREAK A CYCLE.** The tab draws
 * the door and the form reuses the tab's `budgetEligibilityKey`, so a constant
 * declared in either file would make the two import each other. `BILLING_ROUTE`
 * is already here for the same reason.
 *
 * THREE STATIC SEGMENTS, so React Router ranks it above `billing/:tab` and
 * `budget` is never read as a tab name — the ordering `billing/pending` and
 * `billing/print` already depend on.
 */
export const BUDGET_ENROL_ROUTE = `${BUDGET_TAB_ROUTE}/enrol`;

/**
 * §05 entry 25.2 `Settle-up forecast` — READ ONLY.
 *
 * Here for the same reason `BUDGET_ENROL_ROUTE` is: the tab draws the door and
 * the screen navigates back to the tab, so a constant in either file would make
 * the two import each other.
 *
 * THREE STATIC SEGMENTS, so React Router ranks it above `billing/:tab` — the
 * same ordering `billing/pending`, `billing/print` and the enrol form depend
 * on, and its test asserts the screen by ADDRESS because `DEF-CWP-3925`'s
 * hold-expiry test asserted one address while the router mounted another.
 */
export const BUDGET_FORECAST_ROUTE = `${BUDGET_TAB_ROUTE}/settle-up`;

/**
 * §05 entry 25.3 `Asks` — the queue of customers who asked from the portal.
 *
 * THREE STATIC SEGMENTS for the same reason `enrol` has them: React Router
 * ranks it above `billing/:tab`, so `budget` is never read as a tab name.
 *
 * ⚠ **AN ADDRESS AND NOT A PANEL, BECAUSE A DOOR A TEST CAN ASSERT IS THE ONLY
 * KIND THAT CANNOT ROT.** `DEF-CWP-3925` is what the alternative costs.
 */
export const BUDGET_ASKS_ROUTE = `${BUDGET_TAB_ROUTE}/asks`;

/** S30 detail. Deep-linkable; the id is the invoice's, never the bill number. */
export function billDetailPath(invoiceId: string): string {
  return `${BILLING_ROUTE}/bills/${encodeURIComponent(invoiceId)}`;
}

/**
 * The S30 list filtered to ONE account — the "All bills →" exit the prototype
 * puts on the account's Recent-bills panel. `f.account_id` is 11b §2.6's own
 * account-scoping of `GET /invoices`, expressed in BR-SHL-011's URL grammar so
 * the link is a normal shareable list URL rather than a second route.
 */
export function billsForAccountPath(accountId: string): string {
  return `${BILLING_ROUTE}?sort=issue_date&dir=desc&f.account_id=${encodeURIComponent(accountId)}`;
}

// ── The Billing page's SEVEN tabs (prototype line 2887's six, in its order,
//    plus Print bills) ───────────────────────────────────────────────────────
//
// ⚠ **SIX UNTIL 2026-09-14. THE SEVENTH IS A DATED PO RULING, NOT A DRAWING
// PREFERENCE** — 12-governance/02-decision-log.md, the fifteen of 2026-09-12,
// ruling #10, verbatim: *"We will need Print bills as tab at Billing level"*.
// The billing blueprint's entry 01 (p007, the REDESIGN) draws the strip seven
// wide with `Print bills` last, and every other §02 screen carries the same
// strip, so this one list is where that ruling lands for all of them.
//
// **`print` IS APPENDED AT POSITION 7 AND NOTHING IS RENUMBERED.** Its body is
// not a tab body: `/billing/print` is a STATIC route declared ABOVE
// `billing/:tab` in App.tsx, so the address the tab navigates to reaches
// `PrintBillsPage` and `billingTabFrom` never sees `print` from the router.
// That page carries this same strip with `print` selected, which is exactly
// how `run` already behaves — a tab whose body is its own route.
//
// ⚠ **THE HEADER BUTTON STAYS.** The drawing keeps `Pending queue`,
// `Print bills` and `Start a billing run →` in the header AND adds the tab; its
// own carry-over table marks those three `UNCHANGED ×3`. A tab is not a
// replacement for the button and removing it is not what was ruled.

export interface BillingTab {
  id: string;
  labelKey: string;
}

export const BILLING_TAB_ALL = "all";

export const BILLING_TABS: readonly BillingTab[] = [
  { id: BILLING_TAB_ALL, labelKey: "billing.tab.all" },
  { id: "run", labelKey: "billing.tab.run" },
  { id: "one-time", labelKey: "billing.tab.oneTime" },
  { id: "budget", labelKey: "billing.tab.budget" },
  { id: "fix", labelKey: "billing.tab.fix" },
  { id: "history", labelKey: "billing.tab.history" },
  { id: "print", labelKey: "billing.tab.print" },
];

/** BR-SHL-011's spirit: an unknown tab falls back to the first, never errors. */
export function billingTabFrom(raw: string | undefined): string {
  return BILLING_TABS.some((tab) => tab.id === raw) ? (raw as string) : BILLING_TAB_ALL;
}

// ── Status vocabulary (A5 + the prototype's segments) ──────────────────────

/**
 * The prototype's segment strip: All · Draft · Issued · Paid · Past-due ·
 * Corrected (line 2894). Five of the six are `invoices.status` values; PAST-DUE
 * is the derived one and travels as a filter VALUE because only the server can
 * answer it (see refusal 2 in the file header).
 *
 * REPORTED, not worked around: `void` is a real status (A5 / r10 lifecycle) and
 * the prototype gives it NO segment, so this list cannot filter to voided bills.
 * A void row still renders with its own pill under "All". Adding a seventh
 * segment would be inventing a capability the ratified row does not declare
 * (BR-SHL-010).
 */
export const BILL_STATUS_SEGMENTS = ["draft", "issued", "paid", "past_due", "corrected"] as const;

/**
 * The bill_type filter's option set — r10 #12's six values, re-exported from
 * the API contract rather than re-typed, so a seventh type added server-side
 * cannot be missing from the filter because someone forgot a second list.
 */
export const BILL_TYPE_VALUES = BILL_TYPES;

/**
 * The pill tone. Past-due outranks the stored status because it is the thing
 * the clerk is looking for: an issued-and-overdue bill is a `danger`, an issued
 * one is neutral until then. Void and corrected are terminal READINGS of a bill
 * that was issued, so neither is a success.
 */
export function billStatusTone(status: string, pastDue: boolean | null): StatusTone {
  if (pastDue === true) {
    return "danger";
  }
  if (status === "paid") {
    return "success";
  }
  if (status === "corrected") {
    return "warning";
  }
  if (status === "void") {
    return "danger";
  }
  return "neutral"; // draft, issued — and any value this catalog does not know
}

/**
 * The pill label. Invoice statuses are NOT tenant-extensible (the ledger and
 * the immutability triggers are written against the five), so unlike an account
 * status the catalog IS the answer — with the raw code as the last resort so a
 * server that grew a value still renders it rather than an empty pill.
 */
export function billStatusLabel(
  row: Pick<InvoiceRow, "status" | "past_due">,
  t: Translator,
): string {
  if (row.past_due === true) {
    return t("billing.bills.status.past_due");
  }
  return t(`billing.bills.status.${row.status}`, { defaultValue: row.status });
}

/** r10 #12 — the six bill types. Same posture: catalog, code as last resort. */
export function billTypeLabel(billType: string, t: Translator): string {
  return t(`billing.bills.type.${billType}`, { defaultValue: billType });
}

/** True for the statuses past which nothing may be edited (BR-BIL-004). */
export function isLockedBill(status: string): boolean {
  return status !== "draft";
}

// ── The bill number (BR-BIL-022 source/format · BR-BIL-063 timing) ─────────

/**
 * EVERY bill carries a number, drafts included (BR-BIL-063, PO ruling
 * 2026-08-11: *"Give a running number always even for Draft; if not use thats
 * okay we will lose it; its okay; dont over complicate, keep it simple."*).
 *
 * THIS COMPONENT USED TO SAY THE OPPOSITE, and the reversal is worth reading
 * before anyone "corrects" it back. It rendered a stated absence — "No number
 * yet" with its reason — on the reading that the series is consumed at issue.
 * That reading was cited to BR-BIL-022, which names only where a number comes
 * from and what it looks like and is silent on WHEN one is allocated; the
 * timing had never been a numbered rule at all (it lived in an epic field-map
 * row). The PO settled it the other way, weighing the wasted numbers against
 * simplicity, and DEF-033 — logged here against the prototype for showing
 * numbered draft rows — is REVERSED: the prototype was right.
 *
 * The absence branch is KEPT, and not as dead code. The number is served, and
 * a served field can be null: an older row written under the previous reading,
 * a partial response, a bug upstream. Rendering "" or "—" in the identity
 * column would read as a value that failed to load. The row still opens either
 * way, because a draft is exactly what a clerk needs to look at.
 */
export function BillNumber(props: { row: InvoiceRow; t: Translator; children?: ReactNode }) {
  if (props.row.invoice_no !== null && props.row.invoice_no !== "") {
    return (
      <span className="[font-feature-settings:'tnum']">
        {props.children ?? props.row.invoice_no}
      </span>
    );
  }
  return (
    <span
      className="cursor-help border-b border-dotted border-b-[color-mix(in_srgb,var(--color-text)_35%,transparent)] text-sm italic text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]"
      title={props.t("billing.bills.noNumberWhy")}
    >
      {props.t("billing.bills.noNumber")}
    </span>
  );
}

// ── The read API's own state, DERIVED (refusal 4 in the file header) ───────

/**
 * True when the API does not serve a bills LIST at all.
 *
 * `GET /invoices` is a collection route: a served list endpoint answers 200
 * with zero results when nothing matches — it never 404s. So a 404 from it is
 * not "no bills", it is "no such resource", and S30 is allowed to say so.
 *
 * This is deliberately NOT a build flag. `apps/billing/api.py` carries no
 * `urlpatterns` and `config/urls.py` has no billing include today, and a
 * constant recording that fact would be a comment claiming a guarantee — stale
 * the hour the other lane registers the route. Reading it off the response
 * makes the message disappear by itself.
 */
export function listRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/** The detail's 404 is ambiguous by design (HR-1) — see `billing.bill.notFound`. */
export function detailNotFound(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

// ── Line grouping (US-BIL-007 / the prototype's per-service bill layout) ───

/**
 * The prototype's bill groups its lines by service and puts "Taxes & fees" last
 * (line 5380). The GROUPING is display; the ORDER WITHIN a group is the
 * server's and is never re-sorted here, because the engine emitted the lines in
 * the order the document prints them and a client-side sort would silently
 * re-order a tiered usage block.
 *
 * A line with no service falls into the trailing group rather than into a
 * group of its own: taxes carry an authority, not a service, and every fee and
 * adjustment belongs beside them at the foot of the bill.
 */
export const LINE_GROUP_OTHER = "__other__";
/**
 * A DISCOUNT with no service (a whole-bill discount) is not a tax or a fee, so
 * it gets a group of its own, headed *Discounts*, after the services and
 * before *Taxes & fees* (`DEF-BIL-9339`: Senior −$7.20 printed under *Taxes &
 * fees* on a bill that charged no tax). A discount scoped to one service still
 * sits with that service.
 */
export const LINE_GROUP_DISCOUNTS = "__discounts__";

export function groupLinesByService<L extends { service: string | null; kind: string }>(
  lines: readonly L[],
): { service: string; lines: L[] }[] {
  const groups: { service: string; lines: L[] }[] = [];
  for (const line of lines) {
    const key =
      line.service !== null && line.kind !== "tax"
        ? line.service
        : line.kind === "discount"
          ? LINE_GROUP_DISCOUNTS
          : LINE_GROUP_OTHER;
    const existing = groups.find((group) => group.service === key);
    if (existing === undefined) {
      groups.push({ service: key, lines: [line] });
    } else {
      existing.lines.push(line);
    }
  }
  // The trailing groups are trailing even when a tax line arrived first:
  // services, then discounts, then taxes & fees.
  const trailing = [LINE_GROUP_DISCOUNTS, LINE_GROUP_OTHER];
  return [
    ...groups.filter((group) => !trailing.includes(group.service)),
    ...groups.filter((group) => group.service === LINE_GROUP_DISCOUNTS),
    ...groups.filter((group) => group.service === LINE_GROUP_OTHER),
  ];
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-025@f4c9d21 (story+rules snapshot — EP-BIL-07 lead story; co-packets US-BIL-026/027 same epic · US-BIL-007 EP-BIL-02 · billing 02-business-rules · 07-billing/03-field-map §2)
// generated: 2026-08-11 by story-coder (W3 billing FRONTEND lane — S30, the screens the billing TABLES landed without)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — GET /invoices is contracted 11b §2.8 and unserved; this lane is frontend-only and 06-backend is another lane's) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 738 passed / 174 todo across 53 files✔ (702 passed / 168 todo across 51 files was the pre-lane baseline — this lane adds 36 passing + 6 todo across 2 new files and dropped nothing) · vite build✔ · run_gates 15 PASS · 0 FAIL · 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance and G15 i18n-parity included; 5 locales × 2628 keys, identical sets)
// exceptions: E3 `BILL_STATUS_SEGMENTS` carries the prototype's five named segments and NOT `void`: the ratified capability row declares the prototype's strip, and BR-SHL-010 forbids rendering a capability that row does not declare. Void rows still render their pill under "All" — reported, not invented · E3 past-due is a SERVED boolean, never computed here: two of its three terms (unpaid, today) belong to payments/ledger and the tenant clock · E3 there is no `bill_payload` parser anywhere in this module — BR-BIL-026 puts the render on the server and stage 6 is being authored in another lane · E4 `listRouteAbsent` derives the read API's absence from a 404 on a COLLECTION route rather than from a build flag, so the message self-heals (hard-won law 1)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
