// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-008 (S56 trial balance) · US-LED-013 (the S56 journal list) ·
//           US-LED-014 (S41 dual-basis remittance) · US-LED-015 (S42 month
//           close) · US-LED-016 (S42/S43 export to accounting) — the four
//           Finance tabs that had no screen, sharing ONE page head
//           Screens: S41 · S42 · S43 · S56
// Rules:    BR-SHL-044 (one page header — a screen DECLARES a header, it never
//           draws one) · BR-SHL-001 (the sidebar's own Finance paths) ·
//           BR-SHL-011 (the URL grammar) · BR-TEN-022 (the accounting period is
//           COMPUTED from fiscal settings and never stored) · BR-REP-001 (every
//           money group labels its date basis)
// ───────────────────────────────────────────────────────
// The page head every Finance tab shares, and the period every one of them asks
// the server for.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS RATHER THAN A COPIED HEADER ON FOUR SCREENS
// ══════════════════════════════════════════════════════════════════════════
// DEF-021 was four page headers, each misplaced differently, found by a human
// walking the prototype — and G14 now asserts that no screen draws its own head.
// Four new Finance tabs landing at once is exactly the shape that produces a
// fifth variant, so the head is declared ONCE here and the tabs differ only in
// which body they render.
//
// `RevenueArPage` (S36) keeps its own call to `PageHeader` because its head
// carries a page-level secondary action the other tabs do not have. Both go
// through the SAME `FINANCE_TABS` array and the same `PeriodRollup`, so the
// strip and the period line cannot read differently on two tabs.
//
// ══════════════════════════════════════════════════════════════════════════
// THE PERIOD IS SERVED, NEVER COMPUTED HERE
// ══════════════════════════════════════════════════════════════════════════
// BR-TEN-022 makes the accounting period computed from the tenant's fiscal
// settings and never stored. `useFinancePeriod` is the ONE place these screens
// read it, and when it is null they say the period is not configured rather
// than defaulting to the browser's calendar month — a month-close screen headed
// "August" that is not the tenant's August would close the wrong month.
//
// ⚠ **IT READS `GET /shell/display`, NOT `GET /settings/regional`, AND THAT IS
// A DEFECT FIX RATHER THAN A PREFERENCE (`DEF-SHL-4283`, 2026-09-06).** This
// hook is imported by SEVEN screens and one of them — `Payments → Refunds` —
// is a Billing Clerk's screen by A4's `payments_record` row (Clerk **Full**),
// on the reasoning written into `RefundsPage` itself: *"a Billing Clerk RAISES
// refunds … gating the screen on the reconcile cell would shut out the very
// person the raise route is for."* `GET /settings/regional` is
// `SettingsReadAnyWriteSystemAdmin` — `{system_admin, executive}` — so for a
// clerk it answered `403 AUTH-002`, this hook returned null, and the Finance
// header read *"Set the fiscal year start to see the current period."* at a
// tenant whose fiscal year start is set. That is `DEF-SHL-4272` surviving in a
// narrower form: the shell's two boot reads were moved and these were not.
//
// `GET /shell/display` is read-only and open to every signed-in tenant role
// (`core.permissions.ShellDisplayRead`). It serves the card WITHOUT `close_by`
// — that field is `close_day` in another shape and stays admin-only — which is
// why the return type is `ShellDisplayPeriod` and not `CurrentPeriod`.
import type { ReactNode } from "react";

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getShellDisplay } from "@/api/endpoints";
import type { ShellDisplayPeriod } from "@/api/endpoints";
import { PageHeader } from "@/components/PageHeader";
import { queryKeys } from "@/api/queryClient";
import { PeriodRollup } from "@/features/ledger/RevenueArPage";
import type { Translator } from "@/features/tenancy/settingsShared";
import type { RegionalDateFormat } from "@/components/DateCell";
import { useTenantPath } from "@/routing/tenantPath";

import { FINANCE_TABS, financeTabFrom, financeTabPath } from "./financeShared";
import type { FinanceTabId } from "./financeShared";

import "./finance.css";

/**
 * The tenant's own accounting period, or null.
 *
 * Returned as `{ period, loading }` and not as a bare value, because "still
 * fetching" and "this tenant has no fiscal year" are two different screens: the
 * first is a skeleton, the second is a sentence telling somebody to open
 * Settings → Regional. Collapsing them would flash the sentence on every load.
 */
export function useFinancePeriod(client: ApiClient = api): {
  period: ShellDisplayPeriod | null;
  loading: boolean;
} {
  const query = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(client),
    retry: false,
  });
  return { period: query.data?.period ?? null, loading: query.isLoading };
}

/**
 * The Finance page head — title, the five-tab strip, the served period line.
 *
 * `explainer` is the ACTIVE tab's guidance sentence and is required, not
 * optional: a tab that shipped with no explanation of what it does is how S1
 * shipped half-missing (hard-won law 8), and an optional prop nothing passes is
 * the dead-UI shape G13 exists to catch.
 */
export function FinanceHeader(props: {
  activeTab: FinanceTabId;
  explainer: string;
  period: ShellDisplayPeriod | null;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  actions?: ReactNode;
  /**
   * ⚠ **A TAB THAT NAMES ITS OWN JOB IN THE PAGE HEAD — ADDED 2026-09-24 FOR
   * `P5.9` (Finance blueprint p067).**
   *
   * Every Finance tab drew the word *Finance* over a period rollup, and the
   * Product Owner's report of 6·1 was *"as user i dont understand this screen
   * at all"*. The blueprint's answer is in the head: **Close September**, and
   * under it *September is open. 3 things left.* — the month, and what is left
   * of it. p069 draws the same shape for 6·2 Export (*Export* over *Closed
   * through August 2026.*), so this serves `P4.12` as well.
   *
   * ⚠ **OPTIONAL, AND ABSENT MEANS EXACTLY WHAT IT MEANT BEFORE.** Five tabs
   * pass neither and render `shell.nav.finance` over `PeriodRollup`, byte for
   * byte. An optional prop nothing passes is dead UI (G13, hard-won law 2);
   * this one has a caller in the same commit.
   */
  title?: string;
  rollup?: ReactNode;
}) {
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  return (
    <PageHeader
      title={props.title ?? props.t("shell.nav.finance")}
      rollup={
        props.rollup ?? (
        <PeriodRollup
          period={props.period}
          t={props.t}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
        )
      }
      secondaryActions={props.actions}
      tabs={FINANCE_TABS.map((tab) => ({
        id: tab.id,
        label: props.t(tab.labelKey),
        // ⚠ **AN EMPTY STRING MEANS *THIS TAB STATES ITS JOB IN ITS HEAD*, AND
        // IT IS NOT THE SAME AS NOT PASSING ONE** (2026-09-24, `P5.9`).
        //
        // `PageHeader` draws the paragraph whenever `explainer !== undefined`,
        // so `""` would render an EMPTY `<p>` — a gap under the strip on one
        // tab and not the others. The prop stays REQUIRED, which is this
        // file's own recorded exception (*"an optional guidance prop is
        // exactly the unwired-prop shape G13 exists to catch"*); what a tab
        // may now do is pass a deliberate blank.
        //
        // 6·1 Close is the first to. Its explainer read *"One summary journal
        // entry per month — not one per bill. Close the month first; a closed
        // period is the only thing the accounting package receives."* — 28
        // words of RATIONALE, which B14 rule 33 puts at ZERO words on screen,
        // over a head that now says the month and what is left of it. The
        // drawing on p067 has no paragraph there at all.
        explainer:
          tab.id === props.activeTab && props.explainer !== "" ? props.explainer : undefined,
      }))}
      activeTabId={props.activeTab}
      tabsLabel={props.t("finance.tabsLabel")}
      onTabSelect={(tab) => navigate(tenantPath(financeTabPath(financeTabFrom(tab.id))))}
    />
  );
}

/**
 * A period-shaped body wrapper: the three states every Finance tab shares.
 *
 * Rendering `children` only once a period exists is what keeps a screen from
 * asking the server for a window it does not have — the DEF-095 failure mode
 * one layer up, where a report ran against bounds nobody chose.
 */
export function FinanceBody(props: {
  period: ShellDisplayPeriod | null;
  loading: boolean;
  t: Translator;
  children: ReactNode;
}) {
  if (props.loading) {
    return <p className="fin-absent-reason">{props.t("finance.loading")}</p>;
  }
  if (props.period === null) {
    return (
      <div className="settings-arrives" role="note">
        <h3>{props.t("settings.regional.currentPeriod")}</h3>
        <p>{props.t("settings.regional.noPeriod")}</p>
      </div>
    );
  }
  return <>{props.children}</>;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-015@7e1e359 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md US-LED-008 · EP-LED-04 US-LED-013 · EP-LED-05 US-LED-014/015/016 · 09-ledger/02-business-rules.md · 08-qa/01-e2e/journeys/J19-month-end-close.md · 05-prototype/UtilityBilling.html lines 3686-3960 · 12-governance/10-defect-log.csv DEF-112)
// generated: 2026-08-15 by story-coder (DEF-112 lane — the frontend half four ledger stories each recorded as `E=deferred(no-frontend-half)`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the S42/S56/S41 test files failed to resolve their screen modules before these files existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) `RevenueArPage` still calls `PageHeader` itself rather than this component — its head carries a page-level secondary action the four new tabs do not have, and rewriting another lane's shipped screen to share a frame is churn this lane did not need. Both use the SAME `FINANCE_TABS` and `PeriodRollup`, so the strip cannot read differently on two tabs · (2) `explainer` is REQUIRED, not optional: an optional guidance prop is exactly the unwired-prop shape G13 exists to catch
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
