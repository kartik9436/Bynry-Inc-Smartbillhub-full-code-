// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-009 (EP-BIL-02 — the account-mapping page) · US-TEN-007 (the service rows it maps)
//           Screens: S8 (Settings → Accounting) · S56 (the same mapping, read-only, on Finance)
// Rules:    BR-BIL-067 (the seeded service→revenue account is a DEFAULT the tenant may override, and a
//           tenant is seeded ONLY the accounts for services it sells) · BR-BIL-069 (a tax line names its
//           AUTHORITY, each authority has its OWN liability account, and the tenant manages both) ·
//           BR-BIL-010 (mapping stamps per line at issue; edits never re-map history) ·
//           BR-TEN-026 (the GL row lives on tenant_services, which exists only while the service is ON) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH its reason) · BR-SHL-020 (plain-language
//           failure) · BR-TEN-016 (a GL re-point is audited server-side — `settings.service_gl.updated`)
// ───────────────────────────────────────────────────────
// S8 → Accounting: WHERE THE MONEY LANDS, and the bounds it lands within.
// THREE sections since 2026-08-16. The first two are one per ruling the PO made
// on 2026-08-11, and the screen exists because both rulings were built into the
// API and neither had a surface. The third arrived by the PO's CR-004 ruling of
// 2026-08-16 — *"this is moved to accounting tab"* — and is a MOVE, not a new
// build: S71 Finance controls used to open from a Reference-data card.
//
//   1. SERVICE REVENUE (BR-BIL-067) — *"A, you create an account, but allow
//      tenant user to override it - also note every Utility may not have all
//      the services."* Each enabled service shows the usage and base revenue
//      accounts it posts to and lets the tenant re-point either at an account
//      of their own. The write is `PUT /settings/services/<code>`, which has
//      accepted `revenue_account` / `base_revenue_account` since the OQ-115
//      lane landed — this file adds no route and no permission.
//
//   2. TAX AUTHORITY LIABILITY (BR-BIL-069) — *"For each atheority have
//      separate account and tagging; but also ensure you allow Use to manage
//      it since every utility may not have every account."* Each authority
//      shows its own 2200-series liability account, or the gap where it has
//      none — which is exactly what BR-BIL-010 will refuse a bill on.
//
//   3. FINANCE CONTROLS (S71) — CR-004 task C, PO 2026-08-16: *"this is moved
//      to accounting tab"*. The S71 rule page, rendered by the SAME
//      `RulePageView` and driven by the SAME `FINANCE_CONTROLS_PAGE` row in
//      settingsRulePages.ts it has always been driven by. Its old entry point —
//      the `finance_controls` card in referenceDataConfig.ts — is deleted, and
//      that deletion is the whole of the change: no field moved, no endpoint
//      moved, and `RULE_PAGES` still lists five pages including this one.
//
// ── WHY THIS TAB EXISTS AT ALL, and why it is HERE ─────────────────────────
// The PO closed OQ-106 with *"it will be done during GL code mapping in
// settings"*, so the configuration surface is a Settings screen and not a
// billing one. The prototype names the destination in its own words, twice —
// `05-prototype/UtilityBilling.html` lines 3714 and 3930 draw the Finance
// account-mapping panel READ-ONLY under "Edit in Settings → Accounting" — and
// that two-segment path is why this is a top-level tab rather than a fifth
// child of Configure. The prototype never DRAWS the tab it points at, so no A1
// screen id owns this surface; it is rendered under S8 (Settings) and reported
// as the missing A1 row rather than numbered here (CLAUDE.md: never renumber).
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ DEF-206 — THE PARAGRAPH THAT USED TO BE HERE EXPIRED, AND IS CORRECTED
// ══════════════════════════════════════════════════════════════════════════
// It said, in bold: *"`GET /ledger/accounts` IS NOT SERVED — apps/ledger/api.py
// is a one-line docstring and config/urls.py has no ledger include"*, and every
// consequence in this file followed from it: the tax picker rendered DISABLED,
// the service picker fell back to a partial list, and two whole sections were
// not drawn at all.
//
// **It has been served since 2026-08-16** — `apps/ledger/chart_api.py:482`
// mounts `ledger/accounts` (plus item, deactivate, reactivate and
// `ledger/gl-mappings`) and `config/urls.py:116` includes it. An absence claim
// that outlives the absence is hard-won law 1 in its most expensive direction:
// three screens went on refusing a control that would have worked, and the CR
// that measured it is the only reason anybody looked (CR-008, 2026-08-17).
//
// So the chart IS the picker now, for BOTH halves. `chartRouteAbsent` stays —
// as a defensive state with an honest sentence, not as a build flag — because
// a deployment that has not migrated is a real thing and a screen that assumes
// a route is a screen that renders a blank table when it is wrong.
//
// ── WHAT THIS TAB IS SINCE CR-008 (PO 2026-08-17) ─────────────────────────
// THREE SUB-TABS, which is what r10 SET-11 draws:
//   1. **Chart of accounts** — the accounts themselves. NOT a new build: the
//      panel is `features/ledger/ChartOfAccountsPanel`, which has been on
//      Finance → General Ledger since 2026-08-16 and is now ALSO here, where
//      the CR puts it. What is new is the CSV import beside it.
//   2. **GL mapping** — FIVE sections, not r10's four. The fifth is the PO's
//      ruling 9 (*"make it separate"*): adjustment reasons carry their own GL
//      account, so a billing-error credit and a goodwill credit can be told
//      apart in the books.
//   3. **Finance controls** — the same S71 rule page, plus the fiscal calendar
//      it belongs beside and the one sentence about who may reopen a period.
//
// ── WHAT CR-008 RULED OUT, so nobody rebuilds it ──────────────────────────
// **QuickBooks sync is NOT built and will not be** — PO 2026-08-17: *"we only
// need file no live integration"*. With it go the OAuth connection, the
// conflict resolution, the last-sync timestamp AND the *Synced vs Local* pill:
// **every account is local now**, so every account is editable and no row says
// "Read-only". The accrual/cash control is REMOVED (ruling 1) and is not
// redrawn here. The rounding-difference account is NOT built and nothing posts
// one (ruling 8). The three-way "who may reopen a period" chooser is NOT built
// (ruling 5) — System Admin is the only legal value and a picker with one legal
// value is decoration; the sentence says so instead.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { isApiError } from "@/api/client";
import type {
  GlAccountRef,
  LookupEntry,
  TaxRow,
  TenantServiceChanges,
  TenantServiceRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { useToast } from "@/components/Toast";
import { Kicker, Note } from "@/components/TextBits";
import { ChartOfAccountsPanel } from "@/features/ledger/ChartOfAccountsPanel";
import { GlMappingList } from "@/features/ledger/GlMappingList";
import { useTenantPath } from "@/routing/tenantPath";

import { AuthorityAccountsPanel } from "./SettingsAuthorityAccounts";
import { ChartImportModal } from "./SettingsChartImport";
import { RulePageView } from "./SettingsRulePageView";
import { FINANCE_CONTROLS_PAGE } from "./settingsRulePages";
import type { Translator } from "./settingsShared";

/**
 * The four GL designations section 3 is about — the ONLY four of the twelve
 * that a payment, an unapplied receipt or a held deposit ever resolves to.
 *
 * Named here rather than filtered by a substring, because "which pointers does
 * money coming IN use" is a fact about the posting service
 * (`apps/payments/ledger_seam.py`) and a substring match over designation names
 * would quietly gain or lose a row the day one is renamed.
 */
export const PAYMENT_DESIGNATIONS: readonly string[] = [
  "cash",
  "undeposited_funds",
  "customer_credit_balance",
  "deposit_liability",
];

/** Ruling 9's column off a lookup row, which types its extras as `unknown`. */
export function reasonGlAccountId(entry: LookupEntry): string | null {
  const value = entry.default_gl_account_id;
  return typeof value === "string" && value !== "" ? value : null;
}

/**
 * The tender's cash/clearing account (CR-008 second-set ruling 1, PO
 * 2026-08-17 *"Im good with all"*).
 *
 * ⚠ **A DIFFERENT COLUMN NAME ON PURPOSE.** Every other GL pointer on this
 * screen is the REVENUE side — where money a bill earns lands. This one is the
 * CASH side — where money a customer hands over lands. They are opposite legs
 * of the same transaction, and one shared name would let a reader map a tender
 * onto an income account with nothing objecting.
 */
export function tenderClearingAccountId(entry: LookupEntry): string | null {
  const value = entry.clearing_gl_account_id;
  return typeof value === "string" && value !== "" ? value : null;
}

// ── Pure pieces ────────────────────────────────────────────────────────────

/** The two GL fields `PUT /settings/services/<code>` accepts, and only those. */
export interface ServiceGlSelection {
  revenue_account: string | null;
  base_revenue_account: string | null;
}

/**
 * BR-BIL-067's override, as the payload the server already takes.
 *
 * Both fields are always sent, because the modal always shows both and a
 * tenant who blanks one MEANT to clear it. `null` clears; omitting would leave
 * the old pointer in place, and the two are different writes.
 */
export function serviceGlChanges(selection: ServiceGlSelection): TenantServiceChanges {
  return {
    revenue_account: selection.revenue_account,
    base_revenue_account: selection.base_revenue_account,
  };
}

/**
 * True when the API does not serve a chart of accounts AT ALL.
 *
 * `GET /ledger/accounts` is a collection route: a served list answers 200 with
 * an empty array when the tenant has no accounts — it never 404s. So a 404 is
 * not "no accounts", it is "no such resource", and this screen may say so.
 * Same reading as `listRouteAbsent` on `GET /invoices` before the billing lane
 * mounted it, and deliberately NOT a build flag (hard-won law 1).
 */
export function chartRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

export interface AccountPicker {
  accounts: GlAccountRef[];
  /** False = this is the partial fallback list, and the panel says so. */
  complete: boolean;
}

/**
 * What a tenant may re-point a service at.
 *
 * With the chart served, it is the chart. Without it, it is every DISTINCT
 * account the served service rows already point at — which is not a guess:
 * those refs come from `tenancy.selectors._account_ref` and are live accounts
 * of this tenant's own chart. For the water-only utility BR-BIL-067 works its
 * example on (seeded 4110 · 4115 · 4120 and nothing else) that fallback is in
 * fact the whole of their revenue chart; for a larger tenant it is a subset,
 * so the panel labels it as partial rather than implying completeness.
 */
export function accountPickerOptions(
  services: readonly TenantServiceRow[],
  chart: readonly GlAccountRef[] | undefined,
): AccountPicker {
  if (chart !== undefined) {
    return { accounts: [...chart], complete: true };
  }
  const seen = new Map<string, GlAccountRef>();
  for (const service of services) {
    for (const ref of [service.revenue_account, service.base_revenue_account]) {
      if (ref !== null && !seen.has(ref.id)) {
        seen.set(ref.id, ref);
      }
    }
  }
  return {
    accounts: [...seen.values()].sort((a, b) => a.code.localeCompare(b.code)),
    complete: false,
  };
}

/** `<select>` option labels are built the way the sibling UoM picker builds
 *  them (`SettingsServicesTab.activeUomOptions`) — two data values and a dash,
 *  never a catalogue string, because there is no word to translate. */
export function accountOptions(accounts: readonly GlAccountRef[]): {
  value: string;
  label: string;
}[] {
  return accounts.map((account) => ({
    value: account.id,
    label: `${account.code} — ${account.name}`,
  }));
}

export interface TaxAuthorityRow {
  taxId: string;
  taxName: string;
  /** BR-BIL-069's unit of account. Null when the tax has no jurisdiction. */
  authority: string | null;
  liabilityAccountId: string | null;
}

/**
 * BR-BIL-069's write, on the route that already takes it: `PATCH /taxes/{id}`
 * with `liability_gl_account_id` (`apps/rating/services.update_tax`, already
 * validated and already audited as `tax.updated`). No new endpoint, and no
 * second copy of the mapping — the column `rating.taxes` already carries IS
 * the map, which is why option B of OQ-116 was declined.
 */
export function taxGlChanges(accountId: string | null): Record<string, unknown> {
  return { liability_gl_account_id: accountId };
}

/**
 * BR-BIL-069: *"For each atheority have separate account."* The authority is
 * `jurisdiction.authority` and falls back to the jurisdiction's NAME, because
 * `authority` is nullable on a row a tenant may have typed before the column
 * meant anything — the name is the closest true statement, never a blank.
 *
 * Rows are NOT collapsed by authority. Two taxes of one authority may be
 * mapped independently today (`rating.taxes.liability_gl_account_id` is
 * per-tax), and a collapsed row would hide a disagreement between them.
 */
export function taxAuthorityRows(taxes: readonly TaxRow[]): TaxAuthorityRow[] {
  return taxes.map((tax) => ({
    taxId: tax.id,
    taxName: tax.name,
    authority: tax.jurisdiction?.authority ?? tax.jurisdiction?.name ?? null,
    liabilityAccountId: tax.liability_gl_account_id,
  }));
}

/** The account an id names, once the chart can answer. Null = cannot resolve. */
export function resolveAccount(
  accountId: string | null,
  accounts: readonly GlAccountRef[],
): GlAccountRef | null {
  if (accountId === null) {
    return null;
  }
  return accounts.find((account) => account.id === accountId) ?? null;
}

/** US-BIL-009 TC-2 has no client-side validation to do — the server owns
 *  ownership and liveness — so the schema only exists to satisfy FormModal. */
export function glSchema() {
  return z.object({ revenue_account: z.string(), base_revenue_account: z.string() });
}

// ── The tab ────────────────────────────────────────────────────────────────
/**
 * SET-11's three sub-tabs, in r10's own order.
 *
 * The ids are URL segments (`/settings/accounting/mapping`), the same mechanism
 * `CONFIGURE_SUB_TABS` uses one tab over — a strip inside the tab body, never a
 * second page header. `chart` is the default because it is the first thing r10
 * draws and because the mapping sections below are meaningless to a utility
 * that has not got its own accounts in yet.
 */
// CR-165-BRC10 round 2 — `authorities` (Settings › Accounting › Authority
// accounts, CR §7 item 1): the list every tax's *Account with the authority*
// picks from. Last, so no existing sub-tab moves.
export const ACCOUNTING_SUB_TABS = ["chart", "mapping", "controls", "authorities"] as const;
export type AccountingSubTab = (typeof ACCOUNTING_SUB_TABS)[number];
export const DEFAULT_ACCOUNTING_SUB_TAB: AccountingSubTab = "chart";

export function accountingSubTabFromParam(raw: string | undefined): AccountingSubTab {
  return ACCOUNTING_SUB_TABS.includes(raw as AccountingSubTab)
    ? (raw as AccountingSubTab)
    : DEFAULT_ACCOUNTING_SUB_TAB;
}

export interface AccountingTabProps {
  readOnly: boolean;
  client?: ApiClient;
  /** The `/settings/accounting/:sub` segment. Absent = the default sub-tab. */
  sub?: string;
}

export function AccountingTab(props: AccountingTabProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const active = accountingSubTabFromParam(props.sub);

  return (
    <div className="settings-tab">
      {/* DEF-RAT-10027 (PO 2026-10-09): Tax filing accounts is not a ledger
          screen, so it is not headed *GL code mapping*; every other sub-tab
          keeps the area's own eyebrow. */}
      <Kicker>
        {active === "authorities" ? t("settings.accounting.authorities.title") : t("settings.accounting.kicker")}
      </Kicker>
      <p className="settings-lede">{t("settings.accounting.lede")}</p>

      <div className="settings-tabs" role="tablist" aria-label={t("settings.tab.accounting")}>
        {ACCOUNTING_SUB_TABS.map((sub) => (
          <button
            key={sub}
            type="button"
            role="tab"
            aria-selected={sub === active}
            className={sub === active ? "active" : undefined}
            onClick={() => navigate(tenantPath(`/settings/accounting/${sub}`))}
          >
            {t(`settings.accounting.sub.${sub}`)}
          </button>
        ))}
      </div>

      {active === "chart" ? (
        <ChartPanel readOnly={props.readOnly} client={client} />
      ) : active === "controls" ? (
        <ControlsPanel readOnly={props.readOnly} client={client} />
      ) : active === "authorities" ? (
        <AuthorityAccountsPanel readOnly={props.readOnly} client={client} />
      ) : (
        <MappingPanel readOnly={props.readOnly} client={client} />
      )}
    </div>
  );
}

// ── Sub-tab 1 · the chart of accounts (a MOVE, plus the import) ────────────

/**
 * SET-11.coa. **Almost none of this is new, and saying so is the point.**
 *
 * `ChartOfAccountsPanel` has drawn the whole table — search, type filter chips,
 * the Used-by counts, Active pills, add/rename/deactivate/delete and the
 * designation re-point — on Finance → General Ledger since 2026-08-16. CR-008
 * puts that surface where a person configuring their books looks for it, so
 * this renders the SAME component rather than a second copy of a chart screen
 * that would drift from it within a week.
 *
 * What is genuinely new is the import beside it, and one absence: r10's
 * *"⇅ Sync from QuickBooks"* is NOT here, by the PO's ruling of 2026-08-17
 * (*"we only need file no live integration"*). The `Source` column with its
 * *Synced 🔒 / Local* pill goes with it — **every account is local**, which is
 * why every row is editable and none says "Read-only".
 *
 * ⚠ **THE PANEL IS ALSO STILL ON FINANCE, and that is deliberate rather than a
 * half-done move.** Finance → General Ledger reads it beside the journal it
 * explains; taking it away to satisfy the word "move" would remove a working
 * surface from the people who use it daily. One component, one behaviour, two
 * entry points — which is the shape the prototype itself draws when it puts
 * *"Edit in Settings → Accounting"* under a Finance panel.
 */
function ChartPanel(props: { readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const [importing, setImporting] = useState(false);
  const translate: Translator = (key, params) => t(key, params);

  return (
    <>
      <h3 className="settings-frame-title">{t("settings.accounting.chart.title")}</h3>
      <Note>{t("settings.accounting.chart.hint")}</Note>

      {/* ⚠ NOT A ROW ACTION, and it was wearing the row-actions container.
          This is the CHART PANEL's own import control — a panel-level command
          with no row under it — so B14 rule 15 does not reach it and it stays a
          word. The container is `.settings-frame-toolbar` now, which is what a
          panel action belongs in; leaving it in a row-actions box would have
          made it the one text control inside a converted product. */}
      <div className="settings-frame-toolbar">
        <Button
          variant="secondary"
          disabled={props.readOnly}
          // BR-SHL-025 — an Executive sees the control and the reason, never a
          // surface that quietly lacks it (DEF-196's shape).
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => setImporting(true)}
        >
          {t("settings.accounting.import.open")}
        </Button>
      </div>

      {/* `now` is a FUNCTION and not a value, by that panel's own contract
          (BR-TEN-043): a retirement stamps the instant of the CLICK, so a
          value captured at render would stamp the moment the page opened. */}
      <ChartOfAccountsPanel
        client={props.client}
        now={() => new Date().toISOString()}
        t={translate}
        // CHART ONLY. The same component draws the whole GL map on Finance;
        // here the map is the NEXT SUB-TAB and is editable, so drawing the
        // read-only copy underneath would say it all twice.
        sections="chart"
      />

      {importing && (
        <ChartImportModal
          client={props.client}
          onClose={() => setImporting(false)}
          onImported={(created) => {
            // The table below must not go on showing the chart as it was before
            // the file landed (hard-won law 2 — built is not wired).
            void queryClient.invalidateQueries({ queryKey: ["ledger", "chart"] });
            void queryClient.invalidateQueries({ queryKey: queryKeys.ledgerAccounts });
            fireToast(t("settings.accounting.import.toast", { count: created }));
          }}
        />
      )}
    </>
  );
}

// ── Sub-tab 2 · the GL map, as ONE list (CR-197-BRC10) ─────────────────────

/**
 * SET-11.map — **ONE list since 2026-10-29** (`CR-197-BRC10`, PO: *"we neeed to
 * create one single tabl on list view ; we should allow to user to add, edit,
 * update, disable"*). The seven tables that stood here (service revenue, tax
 * authorities, payments & deposits, ways of paying, charge codes, adjustment
 * reasons, discounts) are REPLACED by `GlMappingList`, which reads every row
 * from `GET /ledger/gl-mappings/rows` and writes each through the module that
 * owns it. Design source: https://claude.ai/artifact/Ue5p1oSzgQquUva1KZjf8Y v4.
 *
 * A deep link may open it filtered — `?type=charge_code&q=PENALTY` — which is
 * how Plans & Rates and the bill run's "no account" warning point here.
 */
function MappingPanel(props: { readOnly: boolean; client: ApiClient }) {
  const [params] = useSearchParams();
  const type = params.get("type") ?? "";
  const status = params.get("status") ?? "";
  const filters: Record<string, string> = {};
  if (type !== "") {
    filters.type = type;
  }
  if (status !== "") {
    filters.status = status;
  }
  return (
    <GlMappingList
      readOnly={props.readOnly}
      client={props.client}
      initialFilters={filters}
      initialQuery={params.get("q") ?? ""}
    />
  );
}

function ControlsPanel(props: { readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  return (
    <>
      <h3 className="settings-frame-title">{t("settings.reference.card.finance_controls")}</h3>
      <Note>{t("settings.reference.sample.finance_controls")}</Note>
      <RulePageView page={FINANCE_CONTROLS_PAGE} readOnly={props.readOnly} client={props.client} />

      <h3 className="settings-frame-title">{t("settings.accounting.fiscal.title")}</h3>
      <Note>{t("settings.accounting.fiscal.hint")}</Note>
      <Note>{t("settings.accounting.fiscal.reopen")}</Note>

      <h3 className="settings-frame-title">{t("settings.accounting.scope.title")}</h3>
      {/* r10's Scope card, verbatim in meaning: revenue only. The one expense
          this product ever posts is bad debt on a write-off. */}
      <Note>{t("settings.accounting.scope.body")}</Note>
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-009@0000000 (story+rules snapshot — EP-BIL-02; co-rules BR-BIL-067/069 landed 2026-08-11 after the packet was cut, so the hash is a placeholder and is reported)
// generated: 2026-08-11 by story-coder (S8 Accounting — the GL mapping screen BR-BIL-067's backend shipped without)
// amended:   2026-08-17 by story-coder (CR-008 SET-11) — THREE SUB-TABS (chart · mapping · controls), the chart panel MOVED here from Finance (same component, two entry points), its CSV import added, the GL map grown from two sections to FIVE (payments & deposits read from the served designations; charge codes read with BR-BIL-010's GAP banner; adjustment reasons → GL, new and editable only here per PO ruling 9), and DEF-206 CLOSED on this file: the "GET /ledger/accounts is not served" claim expired on 2026-08-16 and the tax picker it disabled is live.
// amended:   2026-08-16 by story-coder (CR-004 task C) — S71 Finance controls MOVES here from Settings → Configure → Reference data, on the PO's ruling of that day: *"this is moved to accounting tab"*, with r10 SET-04 drawing only Import mappings under its FINANCE heading. A MOVE of the entry point and nothing else: the `finance_controls` row leaves referenceDataConfig.ts, this tab renders `FINANCE_CONTROLS_PAGE` through the unchanged `RulePageView`, and settingsRulePages.ts (`RULE_PAGES`, `rulePageForCard`) is not touched, so the field law still lives in exactly one place.
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the test file's trailer — tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates 15 PASS / 0 FAIL / 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance, G15 i18n-parity across ELEVEN catalogues)
// amended:   2026-08-17 by story-coder (CR-008 SECOND-SET rulings 1 and 2) — section 3 gains the PER-TENDER table (`payment_methods.clearing_gl_account_id`, ruling 1), section 4 gains a per-charge EDITOR (ruling 2 made this the only editor, and taking the picker off Plans & Rates without adding one here would have left a late fee with none), and the tax section's copy is corrected: it said *"you can also set this on Plans and Rates … both places change the same account"*, which stopped being true the moment ruling 2 landed. Found by CLICKING, not by a gate — hard-won law 6.
// exceptions: [SUPERSEDED 2026-08-17 — the clause that stood here said r10's PER-TENDER cash/clearing mapping was NOT built and pointed at OQ-264. The PO ruled it the same afternoon (*"Im good with all"*) and it IS built. ⚠ WHAT REMAINS IS THE POSTING HALF, and OQ-264 stays OPEN for it: `post_payment_cleared` debits undeposited funds for every tender and `reconciliation.py` credits that same account when the bank confirms it, so a per-tender receipt leg without a matching reconciliation leg puts the trial balance out by the amount of every card payment. The screen says so in words rather than implying a posting that does not happen] · E4 [CR-008] the chart panel is on BOTH Finance → General Ledger and here; taking it off Finance to satisfy the word "move" would remove a working surface from the people who read it beside the journal · E2 [CR-008] the QuickBooks sync, the Synced/Local pill, the last-sync timestamp, the accrual/cash control, the rounding-difference account and the period-reopen role chooser are all NOT built, each by a PO ruling of 2026-08-17 rather than by deferral · E4 [2026-08-16, CR-004 task C] the Finance-controls section carries its OWN SaveBar, because `RulePageView` owns it — so this tab now has two independent saves (a GL re-point is a modal per row; the rule page is BR-TEN-024's one atomic PUT). That is the honest shape rather than a defect: the two write to different resources, on different routes, with different audit actions, and a single bar would have to pretend they commit together. Reported rather than unified, since unifying them means editing RulePageView, which serves the four other rule pages · E4 [2026-08-16] the heading reads "Finance controls" twice — once as this tab's section header and once as the `Panel` title RulePageView draws. That is UNCHANGED from before the move (SettingsFrame drew the card label above the same Panel), so it is carried faithfully rather than silently redesigned inside a move ticket · [SUPERSEDED 2026-08-17, DEF-206 — the two clauses that stood here said `GET /ledger/accounts` was CONTRACTED AND NOT SERVED and that the tax picker was therefore read-only. It has been served since 2026-08-16 (`apps/ledger/chart_api.py`, mounted at `config/urls.py:116`); the picker is live and the fallback list is now only the defensive path] · E4 no A1 screen id owns this surface: the prototype names "Settings → Accounting" twice (lines 3714, 3930) and never draws the tab, and US-BIL-009 declares screens [S56, S66] where S56 is the FINANCE tab; rendered under S8 and REPORTED (hard-won law 8) rather than renumbered · E4 this is a NINTH top-level Settings tab, eleven days after CR-001 reduced eleven to eight — placed top-level on the prototype's own two-segment wording; OQ-151 puts the placement to the PO and the alternative is a one-line move · [SUPERSEDED 2026-08-17 — both ARE drawn now, sections 3 and 4, off `GET /ledger/gl-mappings` and `GET /charges`]
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
