// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W1 T1.10 (B18 §5.9.4: "The Imports tab (S81) [shot: ACC-02]"
//           — KPI strip, run table, `↺` rollback and `🔧` fix rows).
//           Screens: S81.
//           ⚠ AMENDED 2026-09-22 by `CR-135` `P1.5`: the 500-line body that
//           stood here IS the kit's `ImportRunsList` now, and this file is one
//           of its two callers.
// Story:    US-CUS-019 (bulk account upload) — the run HISTORY half of it.
// Rules:    BR-MET-096 (ONE ETL runner, `target` parameterised — so this tab is
//           the ONE `GET /imports` filtered to `accounts`, never a second run
//           list) · BR-MET-090 (a run's figures are what it RECORDED) ·
//           BR-CUS-047 (migration order: premises → units + plans → assets →
//           ACCOUNTS) · BR-SHL-025 (disabled-with-reason) · B14 rule 4 ·
//           rule 15 · rule 21 · rule 43 (a piece of UI is a COMPONENT)
// Impacts:  AccountsListPage.tsx (mounts this on ?tab=imports) ·
//           components/workflow/ImportRunsList.tsx (the body this now calls)
// ───────────────────────────────────────────────────────
// S81 — the Imports tab of the Accounts page.
//
// ⚠ **THIS FILE WAS 515 LINES AND IS NOW ITS CONFIGURATION.** Its own trailer
// carried this sentence from the day it was written: *"this IS the third
// consumer AST-04 named as its extraction trigger, and that is REPORTED rather
// than taken here"*. The payments blueprint asked for the extraction in terms
// on 2026-09-22 — *"Three copies of this list exist … Payments is a fourth
// caller, not a fourth implementation"* — so it was taken, and this copy is the
// one that moved into the kit, because it is the one whose two known defects
// (`DEF-CUS-5009`'s row actions, `DEF-CUS-5061`'s server scope) are fixed.
//
// **NOT ONE PIXEL MOVES.** The component is this body verbatim; what stayed
// here is the accounts-shaped half — the four tile labels, the rollback
// callout, the empty state and the ONE import entry, which lives in the page
// header (B18 §5.9.4's *"build one"*, because `[shot]` draws two and B14 rule 4
// allows one primary per page). `AccountImportsTab.test.tsx` is unchanged and
// is the proof of that promise.
//
// ⚠ **WHY THE KPI STRIP HAS FOUR TILES AND `[shot]` DRAWS FIVE.** Four of
// r10's five are MEASUREMENTS this screen can take from the served run list —
// `RUNS`, `ROWS LOADED`, `REJECTED`, `LAST RUN`. The fifth, `ROLLBACK WINDOW ·
// 30 days · unbilled accounts only`, is not a measurement of this tenant at
// all: it is policy, `ImportRunRow` carries no rollback point, and typing `30`
// into a tile would be a figure no endpoint answered. So it renders as r10's
// own CALLOUT SENTENCE above the table, where its load-bearing half can be said
// in words: **an account that has already been billed is kept, because hard
// rule 4 forbids deleting an issued invoice.** The window is a courtesy; that
// is law.
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { ImportRunsList } from "@/components/workflow";

import { ACCOUNT_IMPORT_TARGET } from "./AccountImportWorkflow";

/** The ONE target this tab lists. A one-option Target filter would change
 *  nothing, so the scope is SENT to the server rather than drawn as a choice. */
const ACCOUNT_TARGETS = [ACCOUNT_IMPORT_TARGET] as const;

export interface AccountImportsTabProps {
  /** BR-SHL-025: null = allowed; a string disables the controls WITH it. */
  writeBlockedReason: string | null;
  /** Open the account import workflow — the ONE entry, owned by the page
   *  header (B18 §5.9.4's "build one"). The empty state's CTA calls it too. */
  onImport: () => void;
  client?: ApiClient;
}

export function AccountImportsTab(props: AccountImportsTabProps) {
  const { t } = useTranslation();

  return (
    <ImportRunsList
      targets={ACCOUNT_TARGETS}
      // S81 is A1's own id for this tab (B18 §4's screen table).
      screenId="S81"
      cacheScope="accounts"
      empty={{
        title: t("customers.imports.empty.title"),
        helper: t("customers.imports.empty.helper"),
        ctaLabel: t("customers.accounts.action.import"),
      }}
      rollbackConsequence={(loaded) => t("customers.imports.rollback.consequence", { loaded })}
      kpiCopy={{
        runs: t("customers.imports.kpi.runs"),
        runsDetail: t("customers.imports.kpi.runsDetail"),
        rowsLoaded: t("customers.imports.kpi.rowsLoaded"),
        rowsLoadedDetail: t("customers.imports.kpi.rowsLoadedDetail"),
        rejected: t("customers.imports.kpi.rejected"),
        rejectedDetail: t("customers.imports.kpi.rejectedDetail"),
        lastRun: t("customers.imports.kpi.lastRun"),
      }}
      // B18 §5.9.4's ROLLBACK constraint, in words rather than as a tile — see
      // the file header. The billed half is hard rule 4 and holds on day one as
      // firmly as on day thirty (`customers.services.rollback_from_import`
      // answers `kept_billed` and keeps the account).
      callout={{ text: t("customers.imports.rollbackCallout"), tracks: "BR-MET-099" }}
      writeBlockedReason={props.writeBlockedReason}
      onImport={props.onImport}
      client={props.client}
    />
  );
}

export default AccountImportsTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030/B18@2026-08-23 §5.9.4 (S81) · US-CUS-019 · BR-MET-090/096 · BR-CUS-047 · W1 T1.10 · AMENDED by CR-135 P1.5
// generated: 2026-08-24 by the CR-030 W1 lane · REDUCED TO A CALLER 2026-09-22 by LANE P1-C
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (AccountImportsTab.test.tsx, unchanged) · g31 (still listed in route-b-migrated.txt) · g37 (the row actions are the kit's now) · g38 (no new stated absence)
// exceptions: E2 the extraction AST-04 named as its third-consumer trigger is now TAKEN, in `components/workflow/ImportRunsList.tsx`; PRM-04 and AST-04 have not moved onto it and CR-135's decision row says why · E3 the KPI strip draws FOUR of r10's five tiles: `ROLLBACK WINDOW · 30 days` is policy, not a served figure, so it renders as the callout SENTENCE above the table · E3 the `REJECTED` tile omits r10's `2 still open` sub-line: `run_list` serves a rejected COUNT and nothing about how many remain unfixed · E3 every KPI shows the quiet dash unless the list both arrived and is under the window cap · E3 `Fix rows` stays disabled-with-reason: the runner's inline fix (PATCH /imports/{run}/rows/{n}) lives on the workflow's own stage 3
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
