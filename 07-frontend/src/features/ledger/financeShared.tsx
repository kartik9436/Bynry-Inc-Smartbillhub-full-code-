// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-007 (S36 Revenue & AR — the tab strip, the basis labels and
//           the ONE way this app renders a figure the books would not state) ·
//           US-LED-009 (S59) · US-LED-010 (S60) — both import the same refusal
//           renderer, so a gap reads identically on all three screens
//           Screens: S36 · S59 · S60
// Rules:    BR-LED-016 (the S36 strip is dimension-derived) · BR-LED-007 (the
//           tie-out panel renders on S36; the COMPUTATION is US-LED-004 and is
//           not built, so nothing here says "in balance") · BR-REP-001 (every
//           money number labels its date basis) · BR-REP-002 (read-models over
//           journal-line dimensions — never a side-maintained number, and never
//           a client-side one) · BR-SHL-001 (the sidebar's own Finance paths) ·
//           BR-SHL-011 (the URL grammar) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-023 (one money formatting path) · BR-SHL-025 (a control this
//           deployment cannot honour renders disabled WITH its reason) ·
//           BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// The pieces S36, S59 and S60 are built from.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE THING THIS FILE EXISTS FOR: A NULL IS NOT A ZERO
// ══════════════════════════════════════════════════════════════════════════
// `apps/ledger/reporting.py` returns FOUR figures as `null` beside a named
// reason — collection %, DSO, the aging buckets and the collected tax basis —
// and its docstring says why in one line: *"A `None` figure with a named reason
// is a report a finance officer can act on. A plausible zero is not."*
//
// A screen can undo that in one character. `{kpis.collection_pct ?? 0}%` renders
// "0%" over a utility collecting perfectly well; `{aging?.total ?? "0.00"}`
// renders a clean set of books over a receivable nobody can age. So this module
// owns the rendering of an absent figure and every one of the three screens goes
// through it. There is no second path, and `AbsentFigure` takes a REASON as a
// required prop — a caller cannot render an absence without saying why.
//
// The reason is rendered from THIS app's catalogue, keyed on the server's stable
// `code`, and NEVER from the server's `detail` prose (TD-16/B8: the server sends
// keys, the UI renders language — a screen that printed `detail` would be
// English-only on a product with eleven catalogues). A code this app has no copy
// for falls back to a short sentence saying the books will not state the figure.
// ⚠ THAT FALLBACK USED TO NAME THE CODE AND THE BR REFERENCE, and this comment
// said so until 2026-09-01. It is B14 rule 31 — nothing internal is ever visible
// to a utility user — and the ids now live in the code comment beside each call
// site, where support and engineers still have every one of them.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS MODULE DELIBERATELY DOES NOT DO
// ══════════════════════════════════════════════════════════════════════════
//   · **No arithmetic on money, of any kind.** Not a sum, not a percentage, not
//     a difference. Every figure on these three screens is a decimal STRING the
//     server computed and `MoneyCell` formats (CLAUDE.md rule 2, BR-SHL-023).
//     The one number this file derives is a bucket's share of a total, and it
//     does not: the server serves `share_pct` or the column is absent.
//   · **No period arithmetic.** The tenant's accounting period is COMPUTED from
//     fiscal settings and never stored (BR-TEN-022), and `GET /shell/display`
//     serves it as `period` — a read every signed-in role may make, since
//     2026-09-06 (`DEF-SHL-4283`; the admin-only `GET /settings/regional`
//     served it before, and a Billing Clerk on Payments → Refunds got 403).
//     When that is null these screens say the
//     period is not configured rather than defaulting to the browser's calendar
//     month — a report headed "August" that is not the tenant's August is worse
//     than a report that will not run.
import type { ReactNode } from "react";

import { useQuery } from "@tanstack/react-query";

import { getPremises } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import type {
  CloseChecklistResponse,
  ExportPreviewResponse,
  LedgerUnavailable,
  PremisesRow,
} from "@/api/endpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import "./finance.css";
import { AbsentFigure } from "@/components/AbsentFigure";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";

// ── Permissions (A4, `apps/identity/models.A4_MATRIX`) ─────────────────────

/** A4 row "Finance / reconcile / export" — System Admin Full · Executive Full. */
export const FINANCE_PERMISSION = "finance_reconcile_export";

/** A4 row "Reports" — System Admin Full · Billing Clerk **Run** · Executive Full.
 *  Note the third cell: a Billing Clerk may RUN a report and that is not "View"
 *  and not "Full", so the report screens gate on `isDenied` only. Inventing a
 *  read-only posture for "Run" would lock a clerk out of a report A4 grants. */
export const REPORTS_PERMISSION = "reports";

// ── Routes (the AppShell sidebar's own paths — SHELL_NAV `finance`) ────────
// TENANT-RELATIVE, like every route constant since path tenancy landed.
export const FINANCE_ROUTE = "/finance";

// ── The Finance tab strip (the prototype's own, line 3686) ────────────────
// FIVE tabs, in the prototype's order. The ratified sidebar declares four of
// their paths (`/finance`, `/finance/deposits`, `/finance/taxes`,
// `/finance/export`) and NOT the General-ledger one — reported rather than
// resolved here: dropping the tab would hide the S56 trial balance the
// prototype puts on this page, and adding a sidebar child is a ratified-nav
// change that belongs in the PO batch.
export const FINANCE_TAB_REVENUE = "revenue";
export const FINANCE_TAB_DEPOSITS = "deposits";
export const FINANCE_TAB_TAXES = "taxes";
export const FINANCE_TAB_GL = "gl";
export const FINANCE_TAB_EXPORT = "export";
// ⚠ A SIXTH TAB THE PROTOTYPE DOES NOT DRAW, added 2026-08-16 by the payments
// SURFACE lane and REPORTED rather than taken quietly.
//
// BR-PAY-020 is explicit that a write-off is *"INITIATED in Payments (S34/S35
// outstandings, operational), APPROVED + reported in Finance (Owner/Admin,
// bad-debt GL)"* — so the approval surface belongs in this area by rule. **The
// prototype draws no such screen anywhere**, which is why the two-person split
// stayed nominal: `GET /write-offs` was added for it and nothing called the
// route. The sidebar renders no submenus (PO 2026-08-10), so a page's tab strip
// IS how a sub-destination is reached, and a Finance-area screen with no tab is
// a screen only a typed URL can open.
//
// The precedent is directly above: this strip has carried FIVE tabs against
// FOUR ratified sidebar children since the Finance screens shipped, reported in
// the same way. The screen itself is payments-owned (US-PAY-012); only the tab
// lives here, because the tab strip is the Finance area's.
export const FINANCE_TAB_WRITE_OFFS = "write-offs";

// ⚠ A SEVENTH TAB, added 2026-08-16 by the surface-debt tails lane and REPORTED
// for the same reason as the sixth.
//
// **The prototype draws nothing for this capability at all** — it holds zero
// occurrences of *supplier*, *vendor* or *purchased power*, because it predates
// the PO's OQ-188 ruling of 2026-08-12 (*"we can make this system of record and
// capture Ap, AR both"*). EP-LED-06 assigns S73/S74 from the reserved block and
// puts their entry at **Finance → Cost of service**, marked PROVISIONAL.
//
// The sidebar renders no submenus (PO 2026-08-10), so a page's tab strip IS how
// a sub-destination is reached, and a Finance-area screen with no tab is a
// screen only a typed URL can open. **Whether S74 ultimately lives here or
// beside the S59/S60 reports is OQ-204 and is OPEN** — this tab is the epic's
// own provisional home and nothing here answers the question: the DOWNLOAD, the
// half OQ-204 actually blocks, renders disabled with its reason.
export const FINANCE_TAB_COST_OF_SERVICE = "cost-of-service";

// ⚠ **THIS WAS AN EIGHTH TAB FROM 2026-09-01 UNTIL 2026-09-03, AND IT IS NOT A
// TAB ANY MORE.** The id is KEPT and exported, exactly as `FINANCE_TAB_WRITE_
// OFFS` above was kept when its tab folded: a tab id is what a still-routed
// screen and its tests name the destination by, and deleting it would be a
// rename dressed up as a cleanup.
//
// **THE COUNT WAS RULED BY THE PO, 2026-09-03, ASKED DIRECTLY, VERBATIM:
// *"C25 says six tabs. - this is correct."*** `CR-060` `C25` names its six —
// General Ledger · Revenue & AR · Deposits & Bank · Taxes & Remittances ·
// Costs · Close & Export — and **Refunds is not among them**, so the ruling
// settles that Refunds is not a tab. Removing this entry from `FINANCE_TABS`
// leaves exactly those six.
//
// **WHERE IT WENT WAS OURS TO DECIDE AND IT IS DECIDED** (law 13: *"a judgment
// call recorded in the decision log with its reasoning is the deliverable; a
// question is the failure to make one"*). **Refunds is a PANEL inside Revenue &
// AR**, beside the write-off queue, on `C25`'s own stated principle: write-offs
// folded into that tab *"where the receivable it gives up already lives"*, and
// **a refund gives back money the customer's ACCOUNT holds as credit, which is
// the same place.** `RefundsQueuePanel` draws it there.
//
// **THE ONE REAL COUNTER-ARGUMENT, RECORDED AS CONSIDERED AND DECLINED**, so
// the next reader does not re-open it: a refund cheque appears on the bank
// reconciliation as an outstanding cheque (`CS-14`), which argues for Deposits
// & Bank. Declined because that is the cheque CLEARING, which already lives in
// bank rec — exactly as a payment's deposit batch lives in Deposits & Bank
// while the payment itself lives in Revenue & AR. **Raising and approving a
// refund is an account-credit act.**
//
// ⚠ **`/finance/refunds` STAYS ROUTED and `RefundsPage` is not deleted.** What
// changed is where the STRIP sends you, not what the router accepts, so every
// link already in circulation keeps working. The page highlights
// `FINANCE_TAB_REVENUE` — the
// tab that owns its panel — because highlighting a tab the strip no longer
// draws would leave the whole strip looking unselected.
//
// Full reasoning, and why the two change requests collided without either being
// wrong: `12-governance/02-decision-log.md` 2026-09-03, and `CR-060` §0d.2.
export const FINANCE_TAB_REFUNDS = "refunds";

// ══════════════════════════════════════════════════════════════════════════
// CR-060 T10 / C12 — THE RESTRUCTURE, AND THE COUNT IS **SIX**
// ══════════════════════════════════════════════════════════════════════════
// **THE PO RULED THE COUNT, 2026-09-03, ASKED DIRECTLY, VERBATIM: *"C25 says
// six tabs. - this is correct."*** So the strip is `C25`'s six, in `C25`'s
// order, and this array is the whole of it:
//
//   General Ledger · Revenue & AR · Deposits & Bank · Taxes & Remittances ·
//   Costs · Close & Export
//
// ⚠ **THIS BLOCK SAID *"the strip is EIGHT and this lane ships SEVEN"* UNTIL
// 2026-09-03, AND IT IS RECORDED RATHER THAN QUIETLY DELETED**, because a
// reader who half-remembers the old paragraph needs to see that it was answered
// and not merely disagreed with. The argument was that `C25`'s *7 → 6* was
// arithmetic on the strip of the day the CR was written, that one fold of an
// eight-tab strip gives seven, and that Refunds does not fold. **The first half
// stands as history; the conclusion is superseded by the ruling above.** `C25`
// NAMES its six, Refunds is not among them, and the PO was asked that exact
// question and answered it — so the count is a target and not a subtraction.
//
// **WHERE REFUNDS WENT — DECIDED BY `C25`'s OWN STATED PRINCIPLE, NOT BY
// TASTE.** `C25` folds Write-offs into Revenue & AR *"where the receivable it
// gives up already lives"*. **A refund gives back money the customer's ACCOUNT
// holds as credit, and the credit position lives in Revenue & AR** — so
// Refunds sits beside Write-offs, on the same principle, in the same tab.
// `RefundsQueuePanel` (payments-owned, drawn by `RevenueArPage`) is that panel.
//
// **THE COUNTER-ARGUMENT, CONSIDERED AND DECLINED:** a refund cheque appears on
// the bank reconciliation as an outstanding cheque (`CS-14`), which argues for
// Deposits & Bank. That is the cheque CLEARING, which already lives in bank rec
// — exactly as a payment's deposit batch lives in Deposits & Bank while the
// payment itself lives in Revenue & AR. Raising and approving a refund is an
// account-credit act. Full reasoning: `02-decision-log.md` 2026-09-03.
//
// **THE ORDER IS THE CR's OWN** — *"the five tabs after it run in the order the
// month is actually worked"*: the books · who owes you · the bank · the tax ·
// what you bought · the close.
//
// **GENERAL LEDGER LEADS AND LANDS**, per the CR: *"opening on the trial
// balance means the first thing anyone sees is whether the month balances"*.
// So `gl` — not `revenue` — is the bare `/finance` path, and Revenue & AR takes
// a segment of its own. ⚠ `/finance/gl` STAYS MOUNTED: it is in tickets, in
// bookmarks and in this repo's own journeys, and a landing-tab change is not a
// reason to 404 a URL somebody saved.
//
// ⚠ **AND THE COUNT IS ASSERTED BY NAME, NOT ONLY BY LENGTH** — see
// `revenueAr.test.tsx`'s *"CR-060 C25 · the Finance strip is C25's SIX"*. A
// length assertion alone goes green on a seventh tab that replaced a sixth,
// which is how this strip reached eight without anything raising.
export const FINANCE_TABS = [
  // The label keys are the SIDEBAR's own for the four it declares, so a tab and
  // the nav item that lands on it can never read differently (BR-SHL-001).
  { id: FINANCE_TAB_GL, labelKey: "finance.tab.gl" },
  { id: FINANCE_TAB_REVENUE, labelKey: "shell.nav.finance.revenue" },
  { id: FINANCE_TAB_DEPOSITS, labelKey: "shell.nav.finance.deposits" },
  { id: FINANCE_TAB_TAXES, labelKey: "shell.nav.finance.taxes" },
  { id: FINANCE_TAB_COST_OF_SERVICE, labelKey: "finance.tab.costOfService" },
  { id: FINANCE_TAB_EXPORT, labelKey: "shell.nav.finance.export" },
] as const;

// ⚠ **TWO TABS ARE GONE FROM THIS ARRAY AND NEITHER SCREEN IS.**
//
// **Write-offs** (CR-060 §8b): *"Write-offs stops being a destination and
// becomes an approval panel inside Revenue & AR, where the receivable it gives
// up already lives."* `RevenueArPage`'s `WriteOffQueuePanel` has BEEN that panel
// since it shipped, so that one was the tab catching up with the screen rather
// than a move of code.
//
// **Refunds** (PO 2026-09-03, the ruling above): the same fold, on the same
// stated principle, and this one DID need the panel building —
// `RefundsQueuePanel` is it.
//
// **`/finance/refunds` stays routed** for the URLs already in circulation and
// highlights `FINANCE_TAB_REVENUE`. What changed is where the strip sends you,
// not what the router accepts.
//
// ⚠ **`/finance/write-offs` DID NOT STAY ROUTED, AND THIS LINE SAID IT DID
// UNTIL 2026-09-22 (`CR-135` P1.10).** Keeping it routed left the product with
// TWO write-off approval queues — this fold's panel and the standalone
// `WriteOffQueuePage` — answering one question, drifting from the first defect
// onwards. Nothing ever linked to the address, so nothing in circulation broke.
// The route, its screen-id row and its address constant all went together.

export type FinanceTabId = (typeof FINANCE_TABS)[number]["id"];

/** An unknown `:tab` falls back to the LANDING tab, never 404s (BR-SHL-011).
 *
 *  ⚠ The landing tab is `gl` from CR-060 T10 onward, and this function is the
 *  one place that decides it — a second literal anywhere would be a screen that
 *  highlights one tab while rendering another. */
export function financeTabFrom(tab: string | undefined): FinanceTabId {
  const found = FINANCE_TABS.find((candidate) => candidate.id === tab);
  return found?.id ?? FINANCE_TAB_GL;
}

/** The path a tab id navigates to. `gl` is the parent path itself (CR-060 T10).
 *
 *  ⚠ **`/finance/gl` ALSO RESOLVES and is deliberately not redirected**, so
 *  every saved link keeps working; this function decides where the STRIP sends
 *  you, not what the router accepts. */
export function financeTabPath(tab: FinanceTabId): string {
  return tab === FINANCE_TAB_GL ? FINANCE_ROUTE : `${FINANCE_ROUTE}/${tab}`;
}

// ── The refusal renderer (the whole point of this file) ────────────────────

/**
 * The catalogue sentence for one served gap.
 *
 * Keyed on the server's `code`, which is a stable identifier the read model
 * chose deliberately (`premises_and_unit_dimensions_never_stamped`, not a
 * number). The `defaultValue: ""` probe is how a code with no copy is detected
 * without i18next printing the raw key at a finance officer.
 *
 * ⚠ **THE FALLBACK USED TO PRINT `gap.code` AND `gap.br_ref` AT THE READER, AND
 * THAT IS B14 RULE 31 (2026-09-01).** A finance officer at a two-person utility
 * read *"The server named the reason
 * written_off_ytd_window_was_not_stated_by_the_caller and cited BR-TEN-022"* —
 * a server-side identifier and a rule number, both internal, on the screen the
 * PO photographed. The PO's own words for this family, 2026-08-19: *"you are
 * also adding internal content and BR codes on screen, that is not required; it
 * is application also available to Utility user."*
 *
 * **The provenance is NOT deleted, it moves off the reader's surface.** The
 * server still sends `code` and `br_ref` on the wire, they are still in the
 * network tab, in the response fixtures and in the code comment beside every
 * call site here — support and engineers keep every id they had. Only the
 * clerk's sentence changed, and it still says the one thing they need: the
 * books will not state this figure.
 */
export function gapSentence(gap: LedgerUnavailable, t: Translator): string {
  const copy = t(`finance.gap.${gap.code}`, { defaultValue: "" });
  if (copy !== "") {
    return copy;
  }
  return t("finance.gap.unknown");
}

/**
 * True when a served decimal STRING is zero — `"0"`, `"0.00"`, `"0.000000"`,
 * `"-0.000000"`.
 *
 * Compared digit by digit rather than with `Number(amount) === 0`, because a
 * `Number()` here is the float CLAUDE.md rule 2 exists to keep out of money, in
 * the one place it looks harmless. The ledger serialises `NUMERIC(18,6)`, so a
 * cell that tested `amount === "0"` would print every real zero as a figure and
 * every zero-width column would look populated.
 */
export function isZeroAmount(amount: string): boolean {
  return /^-?0*(\.0*)?$/.test(amount.trim());
}

/** The gap whose `code` matches, or null. Screens name the gap they are
 *  rendering rather than dumping the whole list under every figure. */
export function gapFor(
  gaps: readonly LedgerUnavailable[] | undefined,
  code: string,
): LedgerUnavailable | null {
  return (gaps ?? []).find((gap) => gap.code === code) ?? null;
}

// ⚠ **`isFigureAbsent` AND `AbsentFigure` MOVED TO `components/AbsentFigure.tsx`
// ON 2026-09-24 (`P2.14`, Finance blueprint p014).** They were never Finance's:
// **28 render sites across 8 files in THREE features**, with
// `features/payments/BadDebtPanel.tsx` importing them as
// `@/features/ledger/financeShared` — a feature reaching across a boundary to
// borrow a renderer it has every right to own. B14 rule 43 makes a piece of UI
// used twice a COMPONENT, and rule 36 says that where the kit lacks a piece you
// ADD IT TO THE KIT. **Nothing about the rendering changed in the move.**
//
// ⚠ **THIS FILE RE-EXPORTS NEITHER, DELIBERATELY.** Two import paths for one
// component is the drift the move exists to remove, and a compatibility
// re-export is how a move never finishes. Every call site names the kit.

/**
 * The same absence as a block, for a whole panel the server could not fill.
 *
 * ⚠ **THIS ONE IS DELIBERATELY *NOT* A CLOSED `<details>`, AND THE REASON IS
 * WORTH READING BEFORE ANYONE "FINISHES" B14 RULE 32 HERE (2026-09-01).**
 * `AbsentFigure` became a disclosure that day and this component did not,
 * because the two are not the same thing wearing different sizes: **four of
 * this component's six call sites render a RUNTIME READ FAILURE, not a
 * permanent gap.** `RevenueArPage` passes `apiErrorText(query.error, t)` into
 * it for the tie-out panel and again for the write-off queue, and their titles
 * — *Subledger tie-out*, *Write-offs waiting for approval* — are the LIVE
 * panel's own headings, shared key for key. Closing those by default would
 * hide a failed read behind a heading that reads like a working section, which
 * is hard-won law 1 pointed straight at the reader.
 *
 * Rule 32's disclosure is for an absence sitting BESIDE the work. Where a whole
 * panel is the absence, use `AbsentFigure` inside an ordinary `Panel` — the
 * heading stays visible so the reader knows WHICH thing is missing, and the
 * sentence goes behind *Not available*. `RevenueArPage`'s twelve-month-chart
 * panel is the worked example.
 */
export function AbsentPanel(props: { title: string; reason: string; children?: ReactNode }) {
  return (
    <Panel className="fin-absent-panel">
      <h3>{props.title}</h3>
      <p className="fin-absent-reason" role="note">
        {props.reason}
      </p>
      {props.children}
    </Panel>
  );
}

/**
 * **CR-060 C12 — close readiness, on whatever tab a clerk lands on.**
 *
 * The change request's reason, in its own words: *"The five-item checklist only
 * appears once you are already on the Close screen deciding to close. A
 * one-person finance team wants to know on the 3rd what is still outstanding,
 * not on the 31st"* — so it belongs on the landing tab, which after the C12/T10
 * restructure is the trial balance.
 *
 * **IT IS THE SAME PAYLOAD, NOT A SECOND READ MODEL.** `GET
 * /finance/close-checklist` serves both surfaces (CR-060 §9), so the strip and
 * the Close screen can never disagree about what is outstanding — which is the
 * whole reason a second derivation is forbidden here (BR-REP-002).
 *
 * ⚖️ **CLOSED BY DEFAULT — B14 rule 32**, and this is exactly the case the rule
 * describes: an absence sitting BESIDE the work rather than being the work. The
 * summary line carries the only thing that must be visible — *how many of the
 * six are done* — and the list of what is outstanding is one click away. Its
 * markup is `AbsentFigure`'s, which is `billRunShared.RunGap`'s ratified shape
 * ported to a legacy `fin-*` file; the `<details>` deliberately carries NO
 * class, for the reason `AbsentFigure` records — `.fin-absent` is
 * `display: flex` and overriding `display` on a `<details>` stops the closed
 * state hiding its content in a real browser.
 *
 * ⚠ **THE SUMMARY MUST STATE THE GAP.** *"3 of 6 done"* is the whole of what a
 * closed disclosure shows, so a title that read *Close readiness* alone would
 * put us back where hard-won law 1 started — an absence that looks like nothing
 * at all.
 *
 * ⚠ **A READY MONTH RENDERS NOTHING**, and that is not a hidden state: there is
 * no gap to state, and a green strip on every tab for the twenty-nine days a
 * month is complete is the "too much content" the PO ruled against four times
 * in twenty minutes on 2026-08-31.
 */
export function CloseReadinessStrip(props: {
  checklist: CloseChecklistResponse;
  t: Translator;
}) {
  const { checklist, t } = props;
  const done = checklist.items.filter((item) => item.complete).length;
  if (checklist.items.length === 0 || checklist.incomplete.length === 0) {
    return null;
  }
  return (
    <details data-testid="close-readiness">
      <summary className="fin-absent-value">
        {t("finance.close.readiness", { done, total: checklist.items.length })}
      </summary>
      <ul className="fin-checklist">
        {checklist.items
          .filter((item) => !item.complete)
          .map((item) => (
            <li key={item.code} className="fin-checklist-item">
              <span className="fin-checklist-label">
                {t(`finance.close.item.${item.code}`, { defaultValue: item.code })}
              </span>
              {/* THREE states, not two (`ChecklistState`). `unknown` means no
                  register in the product can answer, and drawing it as a plain
                  "not done" would claim somebody looked. */}
              {item.state === "unknown" ? (
                <span className="fin-absent-reason" role="note">
                  {t("finance.close.itemUnknown")}
                </span>
              ) : null}
            </li>
          ))}
      </ul>
    </details>
  );
}

/**
 * A LABEL · VALUE row, which is how every fact line on these panels renders.
 *
 * Never a translated sentence with a money component spliced into it: a
 * fragment either side of a `<MoneyCell>` is the concatenated sentence B8
 * forbids, and it breaks outright in German and Hindi word order.
 */
export function FactRow(props: { label: string; value: ReactNode; strong?: boolean }) {
  return (
    <div className={props.strong === true ? "fin-fact fin-fact-strong" : "fin-fact"}>
      <span className="fin-fact-label">{props.label}</span>
      <span className="fin-fact-value">{props.value}</span>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE PROPERTY FILTER — Finance blueprint `P2.3` (p014, p023)
// ══════════════════════════════════════════════════════════════════════════
//
// **The blueprint's own filter-criteria table for the Balance screen (p023)
// reads `Property · premises · the tenant's premises · api.py:395 →
// reporting.py:730 · SERVED`.** It has been served since `CR-060` C24 landed on
// 2026-09-03, `getTrialBalance` has sent it as `f.premises` since the same day,
// and **the screen carried a panel saying it did not exist** (`DEF-LED-6499`).
// This is the control that panel was standing in for.
//
// ⚠ **IT IS A SERVER SEARCH AND NOT A DROPDOWN, AND THAT IS `NFR-3`/`NFR-5`
// RATHER THAN TASTE.** A `<select>` of the tenant's premises is an unpaginated
// list of a table that scales with the tenant: correct at T7's 3,000
// connections and **13× short at T5's 40,000** — the exact shape
// `DEF-PAY-4221` records, and the exact excuse (*"one row per debtor at a
// utility under 3,000 connections"*) CLAUDE.md names as already breached in
// four places. A filter control is not the place to add a fifth.
//
// ⚠ **AND IT IS THE KIT'S CONTROL, NOT A NEW ONE (B14 rules 36 and 43).**
// `RemoteSearchSelectField` already draws the five states a server search has —
// too short · searching · failed · no match · matches — and keeps `failed`
// (the PLATFORM broke, BR-SHL-020) distinct from `no match` (the clerk
// mistyped). Those two look identical in a naive dropdown and are opposite
// facts; `DEF-3506` was filed because they had been drawn as one picture.

/** Below the minimum, in flight, ran, or could not run. Mirrors the payments
 *  picker's state exactly, so the two searches cannot drift in their meaning. */
export interface PremisesSearchState {
  matches: readonly PremisesRow[];
  idle: boolean;
  searching: boolean;
  searched: boolean;
  failed: boolean;
}

/** IS-3: a server search starts at two characters, never on the first keystroke. */
const PREMISES_SEARCH_MIN_CHARS = 2;

const PREMISES_SEARCH_IDLE: PremisesSearchState = {
  matches: [],
  idle: true,
  searching: false,
  searched: false,
  failed: false,
};

/**
 * The tenant's premises, searched on the SERVER.
 *
 * ⚠ **`q` IS THE TRIMMED TERM AND THE ENABLED GATE READS THE SAME STRING** —
 * `DEF-3506`'s mechanical half, kept here on purpose: one `trimmed` local feeds
 * both, so the gate and the request can never disagree about what was asked.
 * It rides in `queryKey` too, so re-typing a term already searched is answered
 * from cache without a second request.
 */
export function usePremisesSearch(
  term: string,
  client: ApiClient,
  keyPrefix: string,
): PremisesSearchState {
  const trimmed = term.trim();
  const enabled = trimmed.length >= PREMISES_SEARCH_MIN_CHARS;
  const query = useQuery({
    queryKey: ["finance", keyPrefix, "premises-search", trimmed],
    queryFn: () => getPremises({ q: trimmed, per: 50 }, client),
    enabled,
    retry: false,
  });
  if (!enabled) {
    return PREMISES_SEARCH_IDLE;
  }
  return {
    matches: query.data?.results ?? [],
    idle: false,
    searching: query.isPending,
    searched: query.isSuccess,
    failed: query.isError,
  };
}

/**
 * One property, as the filter names it.
 *
 * ⚠ **THE DATABASE ID IS NEVER THE LABEL (B14 rule 31).** A row with neither a
 * premise number nor an address gets the catalogue's own words for that state;
 * printing the uuid would put a key on screen, which the PO ruled out on
 * 2026-08-31 — *"no Databse ID on screen - that is a rule"*. The id is the
 * VALUE, which is what the filter sends and what nobody reads.
 */
export function premisesFilterLabel(row: PremisesRow, t: Translator): string {
  const address = row.address_line ?? row.name;
  if (row.premise_no !== null && address !== null) {
    return `${row.premise_no} — ${address}`;
  }
  return row.premise_no ?? address ?? t("finance.gl.premisesFilter.unnamed");
}

/**
 * The property filter, as one control.
 *
 * Composed rather than written out, so the screen that hosts it declares no
 * markup of its own — B14 rule 43, which was ratified after *"use it"* turned
 * out to mean 120 lines inline in a 4,186-line page. A second Finance screen
 * that needs to filter by property imports this; it does not copy it.
 */
export function PremisesFilterField(props: {
  term: string;
  onTermChange: (term: string) => void;
  search: PremisesSearchState;
  /** The chosen premises id — `""` is "every property", not "none". */
  value: string;
  onChange: (premisesId: string) => void;
  t: Translator;
}) {
  const { t } = props;
  return (
    <RemoteSearchSelectField
      // The name the SERVER knows this filter by, so a field error finds it.
      id="f.premises"
      label={t("finance.gl.premisesFilter.label")}
      placeholder={t("finance.gl.premisesFilter.placeholder")}
      term={props.term}
      onTermChange={props.onTermChange}
      status={props.search}
      options={props.search.matches.map((row) => ({
        value: row.id,
        label: premisesFilterLabel(row, t),
      }))}
      value={props.value}
      onChange={props.onChange}
      words={{
        tooShort: t("finance.gl.premisesFilter.tooShort"),
        searching: t("finance.gl.premisesFilter.searching"),
        // BR-SHL-020 — THE PLATFORM failed. The only one of the four support
        // can act on, and the only one drawn as a refusal.
        failed: t("finance.gl.premisesFilter.failed"),
        // ⛔ NOT a refusal: the search RAN and matched nothing. A fact about the
        // term, which is the half the clerk can fix by typing something else.
        noMatch: t("finance.gl.premisesFilter.noMatch"),
      }}
    />
  );
}


// ── BR-LED-039's payable side, carried SEPARATELY (`P4.12`) ───────────────
//
// ⚠ **THIS LIVED INSIDE `CloseExportPage.ExportSummaryTable` UNTIL
// 2026-09-24.** That component was the GL summary as a `PlainTable`, and 6·2
// draws the same five columns as a `DataTable` with a toolbar, a ▦ chooser and
// a ↓ — so the table went and this did not, because p070 draws no cost row and
// dropping a figure off a live screen on a drawing's SILENCE is not a decision
// a lane may take. It is here rather than in `ExportView` so neither page has
// to import the other (B14 rule 43).

export function ExportCostSection(props: {
  section: ExportPreviewResponse["cost_section"];
  t: Translator;
  locale?: string;
}) {
  const { section, t } = props;
  if (section.entries === 0 && section.settled.count === 0) {
    return null;
  }
  return (
    // BR-LED-039 / US-LED-021 TC-7 — the payable side, carried SEPARATELY. Its
    // total is NOT inside the balanced footer and the label says so, so a
    // reader cannot add it to a balance it is not part of.
    <div className="fin-cost-section">
      {section.entries > 0 && (
        <FactRow
          label={t("finance.export.costTotal", { count: section.entries })}
          value={
            <MoneyCell
              amount={section.cost_total}
              currency={section.currency}
              locale={props.locale}
            />
          }
        />
      )}
      {/* CR-060 T6c / DEF-3380 — a settled purchase is NOT in the figure above,
          because entering a paid-on date posts DR cost / CR cash and it is
          already inside the balanced totals. Said rather than left silent: a
          clerk who reconciled this figure last month would otherwise watch it
          shrink with no explanation on the screen. B14 rule 32 — a stated
          absence is a disclosure CLOSED by default, and `AbsentFigure` is this
          directory's ratified shape for one. */}
      {section.settled.count > 0 && (
        <AbsentFigure
          label={t("finance.export.costSettled", { count: section.settled.count })}
          reason={t("finance.export.costSettledReason")}
        />
      )}
      {section.unavailable.map((gap) => (
        <p key={gap.code} className="fin-absent-reason" role="note">
          {gapSentence(gap, t)}
        </p>
      ))}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-007@a1f04c9 (story+rules snapshot — EP-LED-03 US-LED-007 lead; co-packets US-LED-009 · US-LED-010, same epic; 09-ledger/02-business-rules.md; 12-reports/02-business-rules.md; 11b §1 + §2.10 + §2.11)
// generated: 2026-08-11 by story-coder (W5 finance SCREENS lane — the three read models `apps/ledger/reporting.py` shipped with no way for a human to see them)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔ — see the lane report for the measured output
// amended:   2026-09-01 by the finance-copy lane (S36 content defects the PO photographed at v2.123.0) — B14 rule 32: `AbsentFigure` is now a `<details>` CLOSED by default, following `RunGap`'s ratified shape, so a stated absence keeps its whole sentence and stops occupying the work surface. `AbsentPanel` is NOT converted and its docstring says why: four of its six call sites carry a runtime read failure rather than a permanent gap, and a closed disclosure over a failed read hides an error behind a heading that looks like a working section. B14 rule 31: `gapSentence`'s fallback no longer interpolates the server's `code` or `br_ref` — the ids stay on the wire and in the code comments beside the call sites. NEITHER element carries a class: `.fin-absent` is `display:flex` and overriding `display` on a `<details>` breaks the closed state in real browsers, and this directory is not on `src/styles/route-b-migrated.txt` so a Tailwind utility here would emit no CSS at all.
// exceptions: (1) the Finance tab strip renders FIVE tabs where the ratified sidebar declares FOUR child paths — the prototype's "General ledger" tab has no sidebar entry, and dropping it would hide the S56 trial balance the design puts on this page. Reported, not resolved here · (2) the "Deposits & Bank" tab drops the prototype's "(3 unmatched)" count: it is a live aggregate over a read model that does not exist, and a hardcoded 3 would be a claim about a tenant's bank reconciliation · (3) `AbsentFigure.reason` is REQUIRED rather than optional on purpose — an optional reason is how a plausible zero gets rendered
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
