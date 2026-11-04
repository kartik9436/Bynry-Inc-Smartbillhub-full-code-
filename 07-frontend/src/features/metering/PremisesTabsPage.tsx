// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-001 (S14 premises list) · US-MET-002 (S15 units list)
//           Change:  CR-023 P0 — "It has 3 tabs - Premises, Units and Imports"
//           Screens: S14 (PRM-01) · S15 (PRM-01U) · PRM-04 (no A1 id — reported)
// Rules:    BR-SHL-044 (the one page header: kicker · title · rollup · actions ·
//           tab strip · per-tab explainer — and the primary action is per-TAB) ·
//           BR-SHL-011 (list state is URL state) · BR-SHL-025 (server-authoritative
//           RBAC; a blocked control renders disabled WITH its reason) ·
//           BR-MET-034 (premises types are the tenant's Reference data) ·
//           B14 rule 2 (one page header) · B14 rule 21 (Tailwind, no new class)
// ───────────────────────────────────────────────────────
// CR-023 P0 — THE TAB SHELL.
//
// Before this, `/premises` and `/premises/units` were two ROUTES each drawing
// its own head, and r10 draws ONE page with three tabs. B15 §1 says the
// restructure IS the work: *"Restyling two pages leaves the tab strip, the
// shared head and the whole Imports tab unbuilt."*
//
// What is shared, and what changes with the tab (B15 §3, from r10's own markup
// at `SMARTBillHub.dc.html` line 630):
//
//   SHARED   `h1` reads **Premises** on ALL THREE TABS — the Units tab included.
//            one roll-up sentence, one tab strip.
//            ⚠ **THE FIRST HALF OF THAT LINE WAS REVERSED BY THE PRODUCT OWNER
//            ON 2026-09-10 AND IS LEFT STANDING ON PURPOSE.** It was signed, so
//            the next reader is owed the sight of it being overturned rather
//            than quietly edited away. Verbatim: *"Should the units list say
//            Units or Premises at the top? The drawing says Units with its own
//            subtitle. - t should say Unit"*. The heading now FOLLOWS THE
//            ACTIVE TAB, out of `PREMISES_TAB_STRIP`'s own `titleKey`, and the
//            Units tab draws the frame's subtitle where the roll-up would be —
//            between the title and the strip, which is where the frame draws
//            it. Premises and Imports are untouched.
//   PER TAB  the head ACTIONS. Premises → `↑ Import premises` + `+ New premise`.
//            Units → `↑ Import units` + `+ New unit`. Imports → `↑ Import
//            premises` and **NO primary at all**.
//
// ⚠ **`/premises/units` STILL RESOLVES, AND THAT IS A REQUIREMENT, NOT A
// COURTESY** (B15 §7, TC-24). There are live deep links and 857 lines of screen
// behind it, so the tab is a ROUTE rather than a `?tab=` param: every existing
// link, bookmark and `f.premises_id=` scoped URL keeps working byte for byte,
// and the three routes differ only in which body they mount.
//
// ⚠ **THE ROLL-UP REPLACED A KPI STRIP.** Those four counts used to be four
// KPI tiles under the header on the Premises tab only. r10 draws them as one
// sentence in the head, on every tab — and the 2026-08-10 conversion trailer
// had already reported the delta and left it ("placement delta reported, not
// changed"). CR-023 is the ask that closes it.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPremises } from "@/api/endpoints";
import { PageHeader } from "@/components/PageHeader";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { PremisesImportsTab } from "./PremisesImportsTab";
import { PremisesListPage } from "./PremisesListPage";
import { UnitsListPage } from "./UnitsListPage";
import {
  CELL_FULL,
  PREMISES_ADD_ROUTE,
  PREMISES_IMPORT_ROUTE,
  PREMISES_PERMISSION,
  PREMISES_TAB_IMPORTS,
  PREMISES_TAB_PREMISES,
  PREMISES_TAB_STRIP,
  PREMISES_TAB_UNITS,
  UNITS_ADD_ROUTE,
  UNITS_IMPORT_ROUTE,
  premisesHeadSecondary,
  premisesRollupLine,
  premisesStripTabs,
  useAccessCell,
} from "./meteringShared";
import type { RegionalProps } from "./meteringShared";

/**
 * The head's counts. `GET /premises` is the ONLY endpoint that serves this
 * roll-up, so the shell asks for it with the smallest page the shared table
 * vocabulary allows (`PAGE_SIZES` starts at 50) and reads `rollup` off the
 * envelope. On the Premises tab that is one extra request beside the list's
 * own; on Units and Imports it is the only way to fill a line r10 draws on all
 * three. Re-deriving the counts from whatever rows happened to be on screen
 * would be a different number with the same label, which is worse.
 */
export const premisesRollupQueryKey = ["premises", "rollup"] as const;

export interface PremisesTabsPageProps extends RegionalProps {
  /** Which tab this ROUTE mounts. Never read from a query param — see above. */
  tab: string;
  client?: ApiClient;
}

export function PremisesTabsPage(props: PremisesTabsPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();

  const cell = useAccessCell(PREMISES_PERMISSION, client);
  // BR-SHL-025: "Full" writes; anything else renders the control disabled WITH
  // the reason. The server refuses regardless — this only saves a round trip.
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("metering.rbac.readOnly");

  const rollupQuery = useQuery({
    queryKey: premisesRollupQueryKey,
    queryFn: () => getPremises({ per: 50 }, client),
    retry: false,
  });

  const goto = (route: string): void => navigate(tenantPath(route));

  /** This route's own row in the strip — where its heading and its one line
   *  under the heading are declared. */
  const headTab = PREMISES_TAB_STRIP.find((entry) => entry.id === props.tab);

  return (
    <div className="met-page">
      <PageHeader
        // ⚠ **THE KICKER WAS NEVER PASSED, SO THE HEAD DREW NONE** — the
        // blueprint draws `PREMISES & UNITS` above `Premises` on the property
        // list, `PageHeader` has held a `kicker` prop the whole time, and the
        // string was already in all eleven catalogues under `metering.kicker`
        // (it was being handed to `tabsLabel` below as the strip's accessible
        // name and nowhere else). Built is not wired, one prop over.
        // `Kicker` uppercases in CSS, so the catalogue keeps sentence case and
        // the screen reads `PREMISES & UNITS`.
        kicker={t("metering.kicker")}
        // ⚠ **PER TAB SINCE 2026-09-10 (PO ruling) — see the header of this
        // file for the signed sentence it reverses.** The title and the line
        // under it are read off the strip's own declaration rather than written
        // out here, so a fourth tab cannot arrive with a heading nobody
        // decided.
        title={t(headTab?.titleKey ?? "metering.premises.title")}
        rollup={
          headTab?.subtitleKey === undefined
            ? premisesRollupLine(translate, rollupQuery.data?.rollup)
            : t(headTab.subtitleKey)
        }
        secondaryActions={premisesHeadSecondary({
          t: translate,
          activeTabId: props.tab,
          writeBlockedReason,
          onImportPremises: () => goto(PREMISES_IMPORT_ROUTE),
          onImportUnits: () => goto(UNITS_IMPORT_ROUTE),
        })}
        tabs={premisesStripTabs({
          t: translate,
          writeBlockedReason,
          onNewPremise: () => goto(PREMISES_ADD_ROUTE),
          onNewUnit: () => goto(UNITS_ADD_ROUTE),
        })}
        activeTabId={props.tab}
        tabsLabel={t("metering.kicker")}
        onTabSelect={(tab) => {
          const target = PREMISES_TAB_STRIP.find((entry) => entry.id === tab.id);
          if (target !== undefined) {
            navigate(tenantPath(target.path));
          }
        }}
      />

      {/* Each body draws its own toolbar, table and dialogs and NO head of its
          own — B14 rule 2 and BR-SHL-044: one page header per screen, and this
          is one screen now. */}
      {props.tab === PREMISES_TAB_PREMISES && <PremisesListPage client={props.client} />}
      {props.tab === PREMISES_TAB_UNITS && (
        <UnitsListPage
          client={props.client}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      )}
      {props.tab === PREMISES_TAB_IMPORTS && (
        <PremisesImportsTab
          writeBlockedReason={writeBlockedReason}
          onImportPremises={() => goto(PREMISES_IMPORT_ROUTE)}
          onImportUnits={() => goto(UNITS_IMPORT_ROUTE)}
        />
      )}
    </div>
  );
}

export default PremisesTabsPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-001 + US-MET-002 (CR-023 P0 — B15 §1/§3, the PO's five r10
//         screenshots of PRM-01 / PRM-01U / PRM-04, 2026-08-21)
// generated: 2026-08-21 by the CR-023 P0-P2 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest PremisesPage.test.tsx / UnitsPage.test.tsx✔ · g31 (no new
//         stylesheet class — the segment reuses the declared `.seg`/`.seg-opt`)
//         · g36 (no breakpoint written here) · g37 (no row action here)
// exceptions: E2 the head's SECONDARY action is computed by the PAGE rather than
//         declared per tab, because `PageHeaderTab` carries `primaryAction` and
//         no secondary slot; `components/**` is another lane's territory this
//         session, so the per-tab secondary is assembled here and handed to
//         `PageHeader.secondaryActions`. Reported, not changed · E2 the Imports
//         tab's head has NO primary — that is r10's own drawing (`prem_showPremises`
//         is false there), not an omission · E3 the roll-up query is a second
//         `GET /premises` on the Premises tab: no endpoint serves the counts
//         alone, and re-deriving them from the rows on screen would publish a
//         different number under the same label
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
