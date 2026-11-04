// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-005 (chart of accounts on S56: seeded, tenant-customizable,
//           audit-locked in use — add · rename · re-point a designation ·
//           deactivate-first · never delete a referenced row) ·
//           US-LED-006 (the export codes qbo_ref / xero_ref, gaps rendered as
//           visible empty states) · US-LED-017 (the cost-of-service chart
//           section — TC-5: no surface presents an UNSIGNED code as signed)
//           Screens: S56 · S73
// Rules:    BR-LED-014 (the GL mapping the chart feeds) · BR-LED-015 (every
//           chart change audits) · BR-LED-037 (the cost section was PROPOSED
//           and unsigned until a finance re-sign via HUMAN-GUIDE §6 — TAKEN
//           2026-08-18, so the unsigned badge renders on nothing today and the
//           rule now governs any FUTURE unsigned row) · BR-LED-038 ·
//           BR-BIL-010 (service → revenue GL; a line that cannot resolve one
//           fails the WHOLE bill at issue) · BR-BIL-069 (one 2200-series
//           account per tax authority) · BR-REP-006 (filters enumerate the LIVE
//           vocabulary) · BR-SHL-011 (the URL grammar) · BR-SHL-020 (plain
//           language failure) · BR-SHL-025 (a control this deployment cannot
//           honour renders disabled WITH its reason) · IS-1 (deactivate-first) ·
//           CLAUDE.md rule 4 (financial records never delete)
// ───────────────────────────────────────────────────────
// The chart of accounts, and the map that says where each kind of money goes.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS
// ══════════════════════════════════════════════════════════════════════════
// US-LED-005 §1 makes the chart *"tenant-customizable (add accounts, edit
// names)"*, and until 2026-08-16 nobody could do either: the seed wrote
// twenty-four accounts at provisioning and there was no screen, no route and no
// service to change one. A utility that numbers receivables 1150 had a 1200 it
// could not touch, and the twelve GL designations — the pointers the posting
// service resolves EVERY entry through — could be read by code and by no human.
//
// ══════════════════════════════════════════════════════════════════════════
// THIS SCREEN READS. IT DOES NOT COMPUTE, AND IT HOLDS NO ACCOUNT NUMBER
// ══════════════════════════════════════════════════════════════════════════
// `apps/ledger/chart.py`'s whole subject is that code reads the DESIGNATION and
// never the number — a utility may renumber AR to 1150 or rename it entirely.
// So there is no account CODE anywhere in this file: which row is "the AR
// account" is a served fact, and the only codes on screen are the ones the
// server sent.
//
// ══════════════════════════════════════════════════════════════════════════
// THREE ABSENCES THAT ARE STATES, NOT ZEROES
// ══════════════════════════════════════════════════════════════════════════
//   · **A designation with no live account.** Retiring the account that carries
//     `accounts_receivable` leaves the designation unresolvable until another
//     row claims it. That is a REAL state — the tenant may be mid-swap — and it
//     renders as an absence with its reason, never as a blank cell.
//   · **`budget_variance` has no account and never had one.** Its account is an
//     addition to the ❄️ finance-signed chart that no agent may write, so the
//     row says *awaiting a finance signature* rather than looking like a
//     configuration mistake somebody should go and fix.
//   · **A reference count that could not be read.** Two of the four things that
//     can pin an account — a charge code and a tax authority — publish no
//     reverse lookup, so the server answers `answerable: false` and refuses the
//     delete. The screen says *"we cannot tell what points at this"* and offers
//     Deactivate, which loses nothing. Rendering an unanswerable read as "0
//     references" is the defect of this release in miniature.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS DIVERGES FROM `05-prototype/UtilityBilling.html` (law 6)
// ══════════════════════════════════════════════════════════════════════════
// The prototype's S56 *Account mapping* panel prints five hardcoded rows —
// `Electric usage & base → 4100 · Electric Revenue`, `Water usage & base →
// 4200 · Water Revenue`, `LATE / NSF / penalties → 4910 · Penalties & Fees`,
// `Tax collected → 2300 · Sales Tax Payable`, `Write-offs → 6100 · Bad Debt
// Expense` — under the note *"Edit in Settings → Accounting"*.
//
// **FOUR OF THOSE FIVE NAME AN ACCOUNT THE SIGNED CHART DOES NOT HAVE.** B5
// line 74 (❄️ finance-signed 2026-08-08) puts water revenue at **4110/4115**
// and makes **4200 the LATE-FEE revenue account**; there is no **4910** (fees
// are 4200 and 4210) and no **6100** (bad debt is **6900**, bank fees **6800**);
// and **2300 is the customer DEPOSIT liability**, while tax payable is the
// **2200 series, minted per authority** and seeded to nobody. Only the electric
// row is right. So the panel here is drawn from the LIVE map and the divergence
// is reported rather than ported.
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  createLedgerAccount,
  deleteLedgerAccount,
  getChartOfAccounts,
  getLedgerAccountUsage,
  getUserPreference,
  putUserPreference,
  setLedgerAccountActive,
  updateLedgerAccount,
} from "@/api/endpoints";
import type { LedgerAccountUsage, LedgerChartResponse, LedgerChartRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { formatMonthYear } from "@/components/DateCell";
// THE SIX SIBLING DIALOGS ON THIS SAME SCREEN ARE BUILT FROM THIS FRAME
// (`SettingsAccountingTab`: service GL, tax GL, reason GL, discount GL, charge
// GL, tender GL). The chart was the one inline form left. B14 rule 43 — a piece
// of UI is built as a COMPONENT; standalone code inside a page is not reuse.
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { ColumnChooser } from "@/components/ColumnChooser";
import type { ColumnChooserItem } from "@/components/ColumnChooser";
import { CountBadge } from "@/components/CountBadge";
import { moveColumnDown, moveColumnUp, toggleColumnVisible } from "@/components/DataTable";
import {
  columnPreferenceKey,
  columnsFromPreference,
  defaultVisibleColumns,
} from "@/components/tableTypes";
import type { TableConfig } from "@/components/tableTypes";
import { PencilIcon, PowerIcon, TrashIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { Note } from "@/components/TextBits";
import { Dash, ROLE_SYSTEM_ADMIN, useTenantRole } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import "./finance.css";

export const chartQueryKey = (filters: string) => ["ledger", "chart", filters] as const;

/**
 * ⚠ **KEPT AFTER THE PANELS IT FED WERE DELETED, AND ON PURPOSE (DEF-LED-6715).**
 * `GET /ledger/gl-mappings` is no longer read by this screen — the PO merged its
 * four panels into the one table on 2026-09-25 — but `SettingsAccountingTab`'s
 * Mapping sub-tab still invalidates this key after it saves a service's revenue
 * account, and that sub-tab is now the ONLY editor of that map. Removing the
 * export to tidy up would break a live save's refresh with `tsc` green on the
 * day the import was also deleted.
 */
export const glMappingsQueryKey = ["ledger", "gl-mappings"] as const;

// ── The one table's columns (Finance blueprint p024/p025 FIELDS) ───────────
/**
 * NINE COLUMNS, WHICH IS THE WHOLE CHANGE THE PO ASKED FOR.
 *
 * p025 note 1: *"Chart · was 'Chart of accounts & mapping'; **the mapping is
 * columns ④, not a second name**"*, and p024 draws the row as `Code · Name ·
 * Type · Designation · Category · QuickBooks · Xero · State · Actions`. The PO
 * said the same thing in their own words on 2026-09-25 — *"i will have 1 table
 * only and i will use columns to manage rest of the table"*.
 *
 * `code` is the IDENTITY column and cannot be hidden (BR-SHL-013): a chart row
 * with neither code nor name is not a row anybody can act on. **`actions` is
 * locked for a different reason** — it is not data, and a clerk who hides it
 * has hidden the only way to edit anything on this screen.
 *
 * The two package-code columns are OFF by default, which is p025's own note 4:
 * *"Behind `with_references=1`, so the columns are only fetched when shown"* —
 * the same judgment, one column family over. They are the two an admin turns on
 * when they are reconciling with their accounting package and nobody else ever
 * wants.
 */
export const CHART_COLUMNS: ColumnChooserItem[] = [
  { key: "code", label: "finance.coa.col.code", locked: true },
  { key: "name", label: "finance.coa.col.name" },
  { key: "type", label: "finance.coa.col.type" },
  { key: "designation", label: "finance.coa.col.designation" },
  { key: "category", label: "finance.coa.col.category" },
  { key: "qbo", label: "finance.map.col.qbo" },
  { key: "xero", label: "finance.map.col.xero" },
  { key: "status", label: "finance.coa.col.status" },
  { key: "actions", label: "finance.coa.col.actions", locked: true },
];

const CHART_DEFAULT_HIDDEN = new Set(["qbo", "xero"]);

/**
 * A `TableConfig` shaped only for what the KIT's pure transitions need.
 *
 * ⚠ **THIS SCREEN DOES NOT USE `DataTable` AND THIS IS NOT A STEP TOWARDS IT.**
 * The blueprint's *Components to use* table names `DataTable` for this list, and
 * converting a component mounted on TWO screens (Finance's Chart view and
 * Settings → Accounting → Chart of accounts) is a bigger change than the one the
 * PO reported — the maintenance process's step 3 is exactly about not widening
 * a fix into a redesign nobody asked for. What IS reused is everything reuse can
 * reach without that: `ColumnChooser` renders the menu, `toggleColumnVisible` /
 * `moveColumnUp` / `moveColumnDown` are the kit's own pure transitions, and
 * `columnPreferenceKey` keys the same `user_preferences` round trip every other
 * list uses — which is what stops this repeating `DEF-647`, where a column
 * chooser was built, unit-tested, green, and reset to its defaults on every
 * remount because nothing persisted it.
 */
const CHART_TABLE_CONFIG: TableConfig<LedgerChartRow> = {
  screenId: "S56.chart",
  columns: CHART_COLUMNS.map((column) => ({
    key: column.key,
    // `label` is HEADER COPY the kit expects pre-translated. Nothing here
    // renders it — this config exists only so the kit's pure transitions and
    // `columnPreferenceKey` can be reused — so the i18n KEY is what goes in,
    // and the screen translates for the menu and the `<th>`s itself.
    label: column.label,
    cell: () => null,
    identity: column.key === "code",
    locked: column.locked,
    defaultVisible: !CHART_DEFAULT_HIDDEN.has(column.key),
  })),
  getRowId: (row) => row.account_id,
  defaultSort: { sort: "code", dir: "asc" },
};

/**
 * The chosen column set, stored the way every other list's is (BR-SHL-013).
 *
 * Lifted out of `DataTable`'s private `useColumnPreference` rather than
 * imported, because that one is not exported and exporting it would be a change
 * to the shared table on a maintenance fix's authority. The BEHAVIOUR is copied
 * deliberately, including the two things that are easy to get wrong: a stored
 * value that arrives after the clerk has already touched the menu is DISCARDED,
 * and an unknown key reads as absent (BR-SHL-024) rather than as an error.
 */
function useChartColumns(): {
  visible: string[];
  update: (next: string[]) => void;
} {
  const [visible, setVisible] = useState<string[]>(() =>
    defaultVisibleColumns(CHART_TABLE_CONFIG),
  );
  const touched = useRef(false);
  const key = columnPreferenceKey(CHART_TABLE_CONFIG);

  useEffect(() => {
    if (key === null) {
      return;
    }
    let cancelled = false;
    void getUserPreference<unknown>(key)
      .then((stored) => {
        if (cancelled || touched.current || stored === null) {
          return;
        }
        setVisible(columnsFromPreference(stored, CHART_TABLE_CONFIG));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [key]);

  return {
    visible,
    update: (next: string[]) => {
      touched.current = true;
      setVisible(next);
      if (key !== null) {
        void putUserPreference(key, next).catch(() => undefined);
      }
    },
  };
}

/**
 * The Role filter's one value that is not a role: `needs-account`.
 *
 * ⚠ **IT SELECTS ROLES, NOT ACCOUNTS, AND THAT IS THE WHOLE REASON IT EXISTS.**
 * See `ChartTable`'s own header for what it renders and why a column could not
 * have carried it.
 */
export const ROLE_FILTER_NEEDS_ACCOUNT = "needs-account";
export const ROLE_FILTER_NONE = "none";

/**
 * The sentence a Delete control must carry, or null when the row may go.
 *
 * Pure and exported so the rule is testable without a browser, and so the two
 * refusals stay DIFFERENT: *"fourteen journal lines point at this"* is a fact a
 * clerk can act on, and *"we cannot tell what points at this"* is an admission
 * that must never be rendered as a comfortable zero (the DEF-127 shape).
 */
export function deleteBlockedReason(row: LedgerChartRow): string | null {
  const references = row.references;
  if (references === undefined) {
    return "finance.coa.delete.notChecked";
  }
  // REFERENCED FIRST, and the order is the fix rather than a preference. Both
  // conditions are usually true at once — something demonstrably points at the
  // account AND a reference kind could not be read — and answering
  // "we cannot tell" while listing what was found reads as a broken screen. The
  // ACTIONABLE fact wins the sentence; the caveat rides beside it as its own
  // note (`deleteCaveat`). Found by reading the rendered page (law 6).
  if (references.referenced) {
    return "finance.coa.delete.referenced";
  }
  if (!references.answerable) {
    return "finance.coa.delete.unanswerable";
  }
  return null;
}

/** The "and there is something we could not check" caveat, or null.
 *
 *  Separate from `deleteBlockedReason` because it is a SECOND fact, not an
 *  alternative to the first: an account may be pinned by fourteen journal lines
 *  AND have an unreadable charge-code reference, and a clerk needs both. */
export function deleteCaveat(row: LedgerChartRow): string | null {
  const references = row.references;
  if (references === undefined || references.answerable) {
    return null;
  }
  return references.referenced ? "finance.coa.delete.alsoUnreadable" : null;
}

/** The reference kinds that actually hold this row, in the server's own order.
 *  Per kind and never as one total: "3 references" tells nobody anything. */
export function holdingKinds(row: LedgerChartRow): string[] {
  const counts = row.references?.counts ?? {};
  return Object.keys(counts).filter((kind) => (counts[kind] ?? 0) > 0);
}

/**
 * THE WHOLE REFUSAL, FOR THE CONTROL'S TOOLTIP — refusal, then what holds the
 * row, then the caveat. `null` when the row may go.
 *
 * ⚠ **THIS USED TO BE COMPOSED INTO A `<p>` UNDER EVERY ROW, AND THAT IS THE
 * DEFECT (`DEF-LED-6170`, PO 2026-09-22: *"Too much text on this screen - GL
 * code mapping"*).** Measured in a browser on the demo tenant's real chart:
 * **129 rows, 224 notes, 3,980 words of body copy, a panel 14,043px tall.**
 * Every row is blocked — 110 unanswerable, 19 referenced — so the paragraph was
 * not an edge case a clerk met occasionally, it was the screen.
 *
 * **B14 rule 33 is what it breaks, and the rule is a CATEGORY rule rather than a
 * length one.** *"…so it will not be deleted"* and *"nothing is lost"* are
 * RATIONALE — why the product behaves as it does — and rule 33 puts rationale at
 * **zero words on screen**, in the code and the register instead. So it is
 * DELETED here rather than shortened; a *why* sentence cut to six words is the
 * same breach, terser.
 *
 * **What a clerk keeps: the refusal itself, ON the control** (BR-SHL-025 — a
 * control that cannot act is disabled WITH its reason), and the holding kinds
 * with it, because *"in use by journal lines"* is exactly what somebody about to
 * retire an account needs. Rule 33 takes it off the RESTING screen; it does not
 * take it out of the product.
 *
 * ⚠ **AND IT FIXES A DANGLING COLON NOBODY HAD SEEN.** The old
 * `delete.referenced` ended *"In use by:"* because the kinds were appended in
 * the paragraph — and the control's `title` got the bare string, so every
 * blocked row's tooltip read *"…never deleted. In use by:"* with nothing after
 * it. The kinds are composed HERE now, so the tooltip and the list cannot
 * disagree because there is only one of them.
 */
export function deleteRefusalText(row: LedgerChartRow, t: Translator): string | null {
  const blocked = deleteBlockedReason(row);
  if (blocked === null) {
    return null;
  }
  const kinds = holdingKinds(row).map((kind) =>
    t(`finance.coa.reference.${kind}`, { defaultValue: kind }),
  );
  const caveat = deleteCaveat(row);
  // ⚠ **THE KINDS GO IN PARENTHESES, AND THAT IS GRAMMAR RATHER THAN STYLE.**
  // Every `finance.coa.reference.*` value is lower case in all eleven
  // catalogues — *"journal lines"*, *"a role in the books"* — because it used
  // to be read as the tail of *"In use by:"*. The refusal is two sentences now,
  // so appending them bare produces *"Retire it instead. journal lines, a role
  // in the books."*: a sentence starting in lower case, in eleven languages.
  // A parenthetical is what they actually are — a qualifier on the refusal —
  // and it needs no catalogue re-casing and no per-language capitalisation
  // rule, which German and Japanese would not share anyway.
  const held = kinds.length > 0 ? `(${kinds.join(", ")})` : null;
  return [t(blocked), held, caveat === null ? null : t(caveat)]
    .filter((part): part is string => part !== null)
    .join(" ");
}

// ── The chart table (EP-LED-02's capability row) ───────────────────────────

export function ChartTable(props: {
  chart: LedgerChartResponse;
  t: Translator;
  /**
   * OPENS THE ADD DIALOG, AND IT LIVES UP HERE RATHER THAN UNDER THE TABLE
   * (`DEF-LED-6140`, PO 2026-09-22: *"give add button on top, not at bottom"*).
   *
   * ⚠ **THE REASON IS A MEASUREMENT, NOT A PREFERENCE.** This table draws one
   * row per chart line and a real utility's chart is long — 129 rows on the
   * demo tenant, which makes the panel **15,354px tall inside an 844px scroll
   * viewport**. The Add form used to sit BELOW all of it, so adding an account
   * began with about seventeen screenfuls of scrolling past rows the clerk did
   * not want. `.fin-panel-head` is already `justify-content: space-between`, so
   * the button needs no new class and no Tailwind utility — B14 rule 21 and
   * this file's place off `route-b-migrated.txt` both stay satisfied.
   *
   * REQUIRED, deliberately: an optional prop nothing passes is dead UI
   * (hard-won law 2), and a test that renders this table without an Add button
   * proves nothing about the door the PO asked for.
   */
  onAdd: () => void;
  onEdit: (row: LedgerChartRow) => void;
  onToggleActive: (row: LedgerChartRow) => void;
  onDelete: (row: LedgerChartRow) => void;
  /** The chosen column set, in display order. REQUIRED — an optional prop
   *  nothing passes is dead UI (hard-won law 2), and a default here would let a
   *  caller render nine columns while its own chooser says three. */
  visibleColumns: readonly string[];
  /** The Columns menu, rendered by the caller into this panel's head. */
  columnsControl: ReactNode;
  /**
   * ROLES WITH NO LIVE ACCOUNT — rendered INSTEAD of accounts when the clerk
   * picks *Needs an account* in the Role filter, and ignored otherwise.
   *
   * ⚠ **THIS IS THE ONE THING THE DELETED PANELS KNEW THAT A COLUMN CANNOT
   * CARRY (`DEF-LED-6715`), AND IT IS THE WHOLE RISK OF THAT DELETION.**
   * *What each kind of money lands in* listed every GL role and said, of each
   * one with no account: *"No live account has this role. Anything that needs
   * it will fail until one does."*
   *
   * ⚠ **THAT PANEL SENTENCE IS A RISK, NOT A GUARANTEE, AND THIS COMMENT
   * RESTATED IT AS ONE UNTIL 2026-09-25.** It said `BR-LED-796` *"refuses a
   * posting that needs an unfilled role, by name"*. **It does not.** Measured
   * in `apps/ledger/selectors.py`: `gl_account_for_designation` hands back
   * `None` for an unfilled role, and raises only when the designation NAME is
   * one it does not recognise. Whether a gap stops a posting or is quietly
   * worked around is therefore the CALLER's behaviour, caller by caller —
   * `BR-LED-796` is the worked case of one that must refuse.
   *
   * **Which makes this prop matter MORE rather than less.** If the gap were
   * fenced at the selector, a clerk would meet it as a named failure and could
   * act. It is not, so the only reliable place it surfaces before month end is
   * this screen.
   *
   * **An unfilled role has no account row**, so putting the roles in a COLUMN
   * of this table — which is what the PO asked for, correctly, for every other
   * panel — silently drops exactly the rows that carry the warning. So the
   * absence is a FILTER VALUE and a COUNT on the one table instead: the count
   * is beside the filter without opening it, and choosing the value lists the
   * roles themselves.
   *
   * B14 rule 32 makes a stated absence CLOSED by default, which is why this
   * renders on request and not on arrival, and rule 33 puts RATIONALE at zero
   * words on screen, which is why the panel's sentence did NOT come with it.
   * The screen says how many and which; why they matter is here, in the code,
   * and in `DEF-LED-6715`.
   */
  rolesNeedingAccount: readonly string[];
  /** True while the clerk has *Needs an account* chosen. */
  showingRoles: boolean;
}) {
  const { chart, t } = props;
  const shown = useMemo(() => new Set(props.visibleColumns), [props.visibleColumns]);
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.coa.title")}</h3>
        {props.columnsControl}
        <Button variant="primary" onClick={props.onAdd}>
          {t("finance.coa.add.open")}
        </Button>
      </div>
      {props.showingRoles ? (
        /* ONE ROW PER ROLE THAT NEEDS AN ACCOUNT, in the same table, under the
           same head. `Code`, `Name` and the rest are empty BY DEFINITION here —
           that absence IS the finding — so each renders a `Dash` rather than a
           blank cell, which is this file's own rule about never drawing a real
           state as a hole (see the THREE ABSENCES block at the top). */
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("finance.coa.col.designation")}</th>
              <th scope="col">{t("finance.coa.col.status")}</th>
            </tr>
          </thead>
          <tbody>
            {props.rolesNeedingAccount.map((role) => (
              <tr key={role}>
                {/* B14 rule 31 — the HUMAN name, never the stored code.
                    `DEF-LED-6612` is exactly this cell rendering
                    `accrued_expenses` on the panel this replaces; the
                    catalogue holds one key per member of the closed set. */}
                <td>{t(`finance.designation.${role}`, { defaultValue: role })}</td>
                <td>
                  <StatusPill tone="warning">{t("finance.coa.filter.roleNeedsAccount")}</StatusPill>
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      ) : (
        <>
      {chart.rows.length === 0 ? (
        <p className="fin-absent-reason" role="note">
          {t("finance.coa.empty")}
        </p>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              {CHART_COLUMNS.filter((column) => shown.has(column.key)).map((column) => (
                <th key={column.key} scope="col">
                  {t(column.label)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {chart.rows.map((row) => {
              const blocked = deleteRefusalText(row, t);
              return (
                <tr key={row.account_id}>
                  {/* `CR-196-BRC10` (PO 2026-10-29, (4)) — a changed code keeps
                      its old one beside it, *"formerly 4150"*. The class is the
                      one this table already uses for a quiet second line, so
                      no stylesheet grows (B14 rule 21). */}
                  {shown.has("code") && (
                    <td>
                      {row.code}
                      {row.former_code ? (
                        <>
                          {" "}
                          <span className="fin-absent-reason">
                            {t("finance.coa.formerly", { code: row.former_code })}
                          </span>
                        </>
                      ) : null}
                    </td>
                  )}
                  {/* ⚠ **THE NAME CELL HOLDS THE NAME AND NOTHING ELSE
                      (`DEF-LED-6170`).** A `<span>` carrying the unsigned note
                      sat here, and because both are inline with no separator
                      the PO's own paste of this screen reads **"Petty
                      cashProposed — finance has not approved this account
                      number yet."** — one run-on word, on all 94 unsigned rows
                      of the demo chart. Unsigned is a STATUS and this table has
                      a Status column; it is drawn there now. */}
                  {shown.has("name") && <td>{row.name}</td>}
                  {shown.has("type") && (
                    <td>{t(`finance.gl.type.${row.type}`, { defaultValue: row.type })}</td>
                  )}
                  {/* CR-061 statement (1) — the chart HEADING. An account
                      nobody has filed is named as UNCATEGORISED rather than
                      dashed away: on a database provisioned before 2026-09-02
                      that is every row, and a dash would read as "this account
                      has no heading and never will". */}
                  {/* CR-061 statement (1) — the chart HEADING. An account
                      nobody has filed is named as UNCATEGORISED rather than
                      dashed away: on a database provisioned before 2026-09-02
                      that is every row, and a dash would read as "this account
                      has no heading and never will". */}
                  {shown.has("designation") && (
                    <td>
                      {row.designation === null ? (
                        <Dash />
                      ) : (
                        t(`finance.designation.${row.designation}`, {
                          defaultValue: row.designation,
                        })
                      )}
                    </td>
                  )}
                  {/* ⚠ **CATEGORY FOLLOWS DESIGNATION, AND THE ORDER IS THE
                      HEADER'S (`DEF-LED-6715`).** The head is generated from
                      `CHART_COLUMNS` and the cells are written out here, so the
                      two are only in step because somebody keeps them in step —
                      and the first draft of this change did not: the header
                      said `Designation` over a cell holding the category, on
                      every row. `US-LED-005 · S56`'s existing cell-index case
                      is what caught it, which is the suite doing its job. */}
                  {shown.has("category") && (
                    <td>
                      {row.category === null
                        ? t("finance.coa.category.none")
                        : t(`finance.gl.category.${row.category}`, {
                            defaultValue: row.category,
                          })}
                    </td>
                  )}
                  {/* ⚠ **THE TWO PACKAGE-CODE COLUMNS REPLACE A WHOLE PANEL
                      (`DEF-LED-6715`).** *Codes your accounting package knows*
                      printed exactly these two values against exactly these
                      rows, one table lower down the same page. A gap is still a
                      VISIBLE empty state and not a blank cell (US-LED-006 TC-1):
                      `BR-LED-014` makes the ref required PER TARGET AT EXPORT,
                      so *not set* is what the S42 gate will refuse the month on.
                      The word is `finance.map.noRef`, unchanged, because a clerk
                      who learnt it on the old panel must read the same word here
                      (B14 rule 34). */}
                  {shown.has("qbo") && (
                    <td>
                      {row.qbo_ref ?? (
                        <span className="fin-absent-reason">{t("finance.map.noRef")}</span>
                      )}
                    </td>
                  )}
                  {shown.has("xero") && (
                    <td>
                      {row.xero_ref ?? (
                        <span className="fin-absent-reason">{t("finance.map.noRef")}</span>
                      )}
                    </td>
                  )}
                  {shown.has("status") && (
                    <td>
                    <StatusPill tone={row.status === "active" ? "success" : "neutral"}>
                      {t(`finance.coa.status.${row.status}`)}
                    </StatusPill>
                    {/* US-LED-017 TC-5 — an UNSIGNED code is never presented as
                        signed. The flag is the server's; this screen does not
                        decide which numbers finance approved.

                        ⚠ **A SECOND PILL AND NOT A SENTENCE (`DEF-LED-6170`).**
                        It used to be nine words of prose glued to the account
                        name. B14 rule 33 caps a LABEL at three words and allows
                        it no sentence at all, so what survives is the one word
                        that IS the status — and the reason it is proposed is a
                        RATIONALE, which rule 33 puts at zero words on screen.
                        The section note at the foot of this panel is the one
                        sentence rule 32's description budget allows, and it is
                        where *why* now lives for a clerk who wants it.

                        It carries NO `title` deliberately: a tooltip repeating
                        the missing sentence would be the same rationale, hidden
                        rather than removed. */}
                    {!row.finance_signed && (
                      <>
                        {/* ⚠ AN EXPLICIT SPACE, AND IT IS THE SAME BUG THIS
                            DEFECT IS ABOUT. `.pill` is `display: inline-flex`,
                            so two of them written adjacently in JSX render with
                            NO text node between them and their two backgrounds
                            touch — which is *"Petty cashProposed"* again, one
                            element up. A space costs nothing and adds no class,
                            which matters here: this file is not on
                            `src/styles/route-b-migrated.txt`, so a Tailwind
                            `gap-1` written in it is a class no stylesheet
                            declares and `G31` refuses it at merge. */}{" "}
                        <StatusPill tone="warning">{t("finance.coa.unsigned")}</StatusPill>
                      </>
                    )}
                    </td>
                  )}
                  {shown.has("actions") && (
                  <td>
                    <RowActions>
                      <RowAction
                        label={t("finance.coa.action.edit")}
                        icon={<PencilIcon />}
                        onClick={() => props.onEdit(row)}
                      />
                      <RowAction
                        label={t(
                          row.status === "active"
                            ? "finance.coa.action.deactivate"
                            : "finance.coa.action.reactivate",
                        )}
                        icon={<PowerIcon />}
                        onClick={() => props.onToggleActive(row)}
                      />
                      {/* BR-SHL-025 — DISABLED WITH ITS REASON, never hidden. A
                          row that cannot be deleted is the rule working, and a
                          clerk must be able to read why rather than hunt for a
                          control somebody removed.

                          ⚠ THE REASON USED TO LIVE ON A WRAPPING <span title>,
                          because a disabled <button> swallows hover on some
                          browsers and the tooltip never appeared. It is the
                          button's own `title` now: `RowAction` puts `reason`
                          there and the wrapper is gone, so there is one element
                          and one tooltip rather than two that can disagree. */}
                      <RowAction
                        label={t("finance.coa.action.delete")}
                        icon={<TrashIcon />}
                        danger
                        reason={blocked}
                        onClick={() => props.onDelete(row)}
                      />
                    </RowActions>
                    {/* ⚠ **A `<p>` REPEATING THAT REASON STOOD HERE UNTIL
                        `DEF-LED-6170`, AND IT WAS THE DEFECT** — recorded
                        rather than deleted quietly, because a screen that stops
                        saying something leaves no trace (hard-won law 1).

                        It was a DUPLICATE from the day it was written: the same
                        sentence was already on the control above, as
                        `RowAction`'s `reason` → `title`, which is BR-SHL-025's
                        mechanism. The paragraph put it a second time in the
                        resting page, once per row — **129 of them on the demo
                        tenant, 3,980 words of body copy in a panel 14,043px
                        tall.** Nothing refused is refused any less: the control
                        is still disabled, and it still says why.

                        ⚠ **WHAT IT COSTS, SO THE NEXT LANE DOES NOT PUT IT
                        BACK BY ACCIDENT:** a disabled `<button>` is out of the
                        tab order, so the reason is now reachable by pointer and
                        not by keyboard. That is not new — it is BR-SHL-025's
                        shape everywhere in this product — but it is worse here
                        than it was, and it is filed rather than absorbed. */}
                  </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </PlainTable>
      )}
      {chart.pending_finance_re_sign_cost.length > 0 && (
        // BR-LED-037 — the 5xxx cost accounts are a PROPOSAL. They are shown
        // (they are real accounts a capture can point at) and marked.
        //
        // ⚠ **ONE SENTENCE, AND THE FOURTEEN CODES ARE GONE (`DEF-LED-6170`).**
        // B14 rule 32 gives a section ONE sentence, and this note had two: the
        // second — *"They work, and no screen may call them approved"* — is a
        // statement of our own policy, which is RATIONALE and therefore zero
        // words on screen under rule 33. The codes went with it because they
        // are no longer the only way to find those rows: every unsigned account
        // now carries a **Proposed** pill in the Status column, so a list of
        // fourteen numbers a clerk would have to match by eye said nothing the
        // table was not already saying per row.
        <p className="fin-absent-reason" role="note">
          {t("finance.coa.costSection")}
        </p>
      )}
        </>
      )}
    </Panel>
  );
}

// ── The GL map — FOUR PANELS, DELETED 2026-09-25 (`DEF-LED-6715`) ─────────
//
// ⚠ **`GlMappingPanels` STOOD HERE AND IS GONE, WITH THE FOUR SECTIONS IT DREW
// UNDER THE CHART. RECORDED RATHER THAN DELETED QUIETLY, BECAUSE A SCREEN THAT
// STOPS SAYING SOMETHING LEAVES NO TRACE (hard-won law 1).**
//
// The PO, reading this screen in 2.351.90: *"i will have 1 table only and i
// will use columns to manage rest of the table"*, and of the panels: *"cant we
// merge it in charts - first table itself"*. The Finance blueprint had already
// ruled the same way and nobody had built it — p025 note 1, **CHANGED**:
// *"Chart · was 'Chart of accounts & mapping'; **the mapping is columns ④, not
// a second name**"*, and p024 draws ONE panel with nine columns.
//
// WHERE EACH PANEL WENT, AND WHY NOTHING WAS LOST:
//
//   · **What each kind of money lands in** (`finance.map.designations.*`) — it
//     printed `role → account`, and the table above it **already had a Role in
//     the books column** carrying the same fact per row. What it ALSO carried,
//     and what no column can, is a role with NO account: `ChartTable`'s
//     `rolesNeedingAccount` is that half, as a filter value and a count. See
//     that prop's own header — it is the one real risk in this deletion.
//
//   · **Where each service's revenue goes** (`GlServiceMapEditor`) — the PO,
//     2026-09-25: *"we are doing it in settings -> accounting -> Charts of
//     Accounts -> GL code mapping - it is already available user will do it
//     there"*. **Verified before deleting, not assumed:**
//     `features/tenancy/SettingsAccountingTab.tsx`'s `MappingPanel` draws
//     `settings.accounting.services.title` over every enabled service with its
//     usage and base-charge revenue accounts and a pencil per row, reading
//     `getTenantServices`. It is a DIFFERENT editor from `GlServiceMapEditor`,
//     which is why the grep that only looked under `features/ledger` said the
//     opposite earlier that day and was wrong.
//     ⚠ **`GlServiceMapEditor.tsx` WAS LEFT ON DISK, UNMOUNTED, AND IS NOW
//     DELETED (`DEF-GOV-10106`)** — the sibling lane it waited for had long
//     landed, and G40 counted it as dead UI (`DEF-LED-6715`'s register row).
//
//   · **Tax authorities** (`finance.map.taxes.*`) — `2200-01` and `2200-02`
//     **are rows in the chart**; the panel was a filtered view of the table
//     above it. The Role filter is that view now, which is p025's own reason
//     for wanting it: *"Designation is how 4·1 finds the tax accounts."*
//
//   · **Codes your accounting package knows** (`finance.map.export.*`) — two
//     values against the same rows. They are the QuickBooks and Xero COLUMNS,
//     off by default, editable from the row's pencil. `PATCH
//     /ledger/accounts/{id}` already took both; only the screen was missing.
//
// `gapSentence`, `GlMappingsResponse` and `getGlMappings` leave this file with
// them. `glMappingsQueryKey` does NOT — see its own note above.

// ── The cost-of-service boundary — REMOVED 2026-09-03 (DEF-2346) ───────────
//
// ⚠ **THIS SPACE HELD `CostOfServiceBoundary`, A PANEL THAT TOLD A CLERK COST
// OF SERVICE WAS "NOT BUILT" — ON THE SAME SCREEN WHOSE COSTS TAB CAPTURES
// SUPPLIER INVOICES.** It is recorded here rather than deleted quietly, because
// a screen that stops saying something leaves no trace and hard-won law 1 is
// about exactly that direction of drift.
//
// It rendered a heading, a five-questions sentence, three bullets, a ruling note
// and a "what does exist today" line, and by 2026-09-03 **three of its claims
// were false at once**:
//
//   1. *"Not built. Five questions have to be answered…"* — `App.tsx` mounts
//      `CostOfServicePage` at the cost-of-service route (S73 · S74) and
//      `FINANCE_TABS` carries the Costs tab, one click from this panel.
//      `apps/ledger/cost_api.py` serves the register, the capture, the
//      correction, the void, the bought-versus-billed comparison and its
//      download. CR-060 §0d calls them *"the two shipped cost screens"*.
//   2. *"Nothing records a supplier invoice yet."* — `POST /finance/cost-of-service`
//      records one and the register lists it.
//   3. *"the cost accounts … marked as awaiting a finance signature"* — all eight
//      were finance re-signed on 2026-08-18; both `PENDING_FINANCE_RE_SIGN`
//      tuples in `apps/ledger/chart.py` emptied that day.
//
// **The three questions it listed did not survive either.** Correcting a closed
// month is BUILT (`finance.cost.field.correctionReasonHelp` and
// `finance.cost.correctedButExported` are what a clerk now reads on the form
// itself). The unit mismatch is still real and is now stated ON THE ROW where it
// bites, as `finance.cost.problem.purchase_unit_does_not_match_billed_unit`,
// which is where a refusal belongs. And *"where should this live"* was answered
// by shipping it as a Finance tab — `OQ-204`'s second half is still formally
// open as a DOCS ratification, and a docs question is not a sentence a clerk
// needs to read.
//
// **WHY IT WAS REMOVED RATHER THAN REWORDED.** Rewording it would put a second
// description of the Costs tab on the chart view, and B14 rule 32 gives a screen
// one sentence per section — the PO having said *"too much content"* four times
// in twenty minutes on 2026-08-31. The feature is a click away and describes
// itself.
//
// **HOW IT SURVIVED SO LONG, which is the part worth keeping.** Its test asserted
// each sentence was PRESENT and never that it was TRUE, so the more carefully the
// absence was tested the more firmly it was pinned in place — and that test's own
// comment said *"a panel whose whole job is to say what is undecided must stop
// saying it the hour it is decided"*. It was right about the panel and could not
// check the thing it was right about.

// ── The panel the S56 tab mounts ───────────────────────────────────────────

// ── The two dialogs (DEF-LED-6140) ────────────────────────────────────────
//
// ⚠ **THIS SPACE USED TO BE TWO INLINE `<Panel>` FORMS AT THE BOTTOM OF THE
// PAGE, AND THE COST WAS MEASURED BEFORE IT WAS FIXED.** PO, 2026-09-22:
// *"you ahve given action at bottom, add and edit; make both actions a modal …
// on edit if youa re unable to save, then show the reason why youa re unable
// to save to user, currently it is not showing"*.
//
// **The reason WAS being shown. It was being shown 14,428px away.** Driven in
// Chromium at 1440x900 against a 129-row chart: the Save button the clerk
// presses sits at y=15,126 inside an 844px scroll viewport, and the panel's one
// refusal strip rendered at y=698 — seventeen screenfuls above, `inViewport:
// false`. Every test asserting that sentence is in the document passed, because
// it was. **A refusal belongs beside the control that produced it**, and a
// dialog is the only container that guarantees that however long the list gets.
//
// **NOTHING HERE IS A SEVENTH DIALOG (B14 rule 43).** `FormModal` is the frame
// the six sibling dialogs on this very screen already use — service GL, tax GL,
// reason GL, discount GL, charge GL, tender GL, all in `SettingsAccountingTab`
// — and it already owned everything needed: the refusal in the form-message
// slot beside the buttons, `envelopeErrors` routing each `field_error` under
// its own input, focus moved to the first bad field, and one submit in flight.
// The only thing missing was a caller.
//
// **AND THE CAPABILITY IS UNCHANGED.** These dialogs post exactly what the
// inline forms posted, to the same two endpoints, with the same fields. `code`
// and `type` are still not offered for edit — `update_account` does not accept
// them — so a number frozen by a posting stays frozen. This moved where a
// clerk types, not what they may type.
//
// ⚠ **AMENDED 2026-10-29 (`CR-196-BRC10`) — THE CODE IS OFFERED NOW.** The PO
// ruled a System Admin may change an account's code even when it is used, so
// the Edit dialog's Code is a field for them (read-only for everyone else) and
// a change goes through a confirmation first. `type` is still not offered.

const ADD_SCHEMA = z.object({
  // Mirrors the server's `_clean_code` / `_clean_name`, which refuse an empty
  // string with `ledger.chart.code_required` / `name_required` (B8: the client
  // schema mirrors the server's VAL codes rather than inventing its own). The
  // server is still the authority; this only saves a round trip.
  code: z.string().trim().min(1),
  name: z.string().trim().min(1),
  type: z.string().trim().min(1),
  category: z.string(),
});

const EDIT_SCHEMA = z.object({
  // `CR-196-BRC10` — the server's `_clean_code` refuses an empty code with
  // `ledger.chart.code_required`; this only saves a round trip.
  code: z.string().trim().min(1),
  name: z.string().trim().min(1),
  designation: z.string(),
  // ⚠ **NOT `.min(1)` — AN EMPTY REF IS A LAWFUL VALUE AND IS HOW ONE IS
  // CLEARED.** `PATCH /ledger/accounts/{id}` takes `null` for both, and a
  // required-field schema here would make the two columns one-way: settable
  // once and never correctable, which is worse than not offering them.
  qbo_ref: z.string(),
  xero_ref: z.string(),
});

/** `POST /ledger/accounts` — US-LED-005 TC-2's "a chart line a human typed". */
function AddAccountModal(props: {
  chart: LedgerChartResponse;
  client: ApiClient;
  t: Translator;
  onClose: () => void;
  onAdded: () => void;
}) {
  const { t } = useTranslation();
  const translate = props.t;
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  // The first served type, never a hardcoded "asset" — BR-REP-006 says a picker
  // enumerates the LIVE vocabulary, and the old inline form defaulted to a
  // literal that `chart_account_types()` is free to stop serving.
  const [type, setType] = useState(props.chart.types[0] ?? "");
  const [category, setCategory] = useState("");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await createLedgerAccount(
        {
          code,
          name,
          type,
          designation: null,
          // Empty is UNCATEGORISED and is lawful — an account a clerk has not
          // filed yet. The server refuses an unknown heading rather than
          // storing it, so nothing here has to validate.
          category: category === "" ? null : category,
        },
        props.client,
      );
      props.onAdded();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        // `formErrorEnvelope` keeps only the errors that NAME a field; the
        // whole-payload ones stay in the form-level message. Both render inside
        // this dialog, which is the entire point of DEF-LED-6140.
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={translate("finance.coa.add.title")}
      kicker={translate("finance.coa.title")}
      schema={ADD_SCHEMA}
      values={{ code, name, type, category }}
      submitLabel={translate("finance.coa.add.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* `id` IS THE SERVER'S FIELD NAME, and that is load-bearing rather than
          tidy: `useFieldError` keys off it, so `field: "code"` on a refusal only
          finds this box because the two spellings match. Rename one and the
          sentence silently falls back to the form-level line. */}
      <TextField
        id="code"
        label={translate("finance.coa.col.code")}
        value={code}
        onChange={setCode}
        required
        help={translate("finance.coa.add.help")}
        // DEF-TEN-4478 — a code is a record identifier, not a fact about the
        // person, so the browser's own fill is refused by name.
        autoComplete="off"
      />
      <TextField
        id="name"
        label={translate("finance.coa.col.name")}
        value={name}
        onChange={setName}
        required
      />
      <SelectField
        id="type"
        label={translate("finance.coa.col.type")}
        value={type}
        onChange={setType}
        required
        options={props.chart.types.map((value) => ({
          value,
          label: t(`finance.gl.type.${value}`, { defaultValue: value }),
        }))}
      />
      <SelectField
        id="category"
        label={translate("finance.coa.col.category")}
        value={category}
        onChange={setCategory}
        placeholder={translate("finance.coa.category.none")}
        options={props.chart.categories.map((value) => ({
          value,
          label: t(`finance.gl.category.${value}`, { defaultValue: value }),
        }))}
      />
    </FormModal>
  );
}

/**
 * Q2's warning, or `null` — `CR-196-BRC10` (PO 2026-10-29: *"Already exported
 * for Sep 2026. Re-exports will show the new code."*). An export outranks a
 * closed month: it is the one that has LEFT the building and will read
 * differently when it is sent again.
 */
export function codeChangeWarning(usage: LedgerAccountUsage, t: Translator): string | null {
  if (usage.exported_period !== null) {
    return t("finance.coa.code.exported", {
      period: formatMonthYear(usage.exported_period.start, "UTC"),
    });
  }
  if (usage.closed_period !== null) {
    return t("finance.coa.code.closedMonth", {
      period: formatMonthYear(usage.closed_period.start, "UTC"),
    });
  }
  return null;
}

/** The confirmation's whole consequence: the counts, what happens, and Q2's
 *  warning on its own line. B14 rule 33 — each sentence six words or fewer. */
export function codeChangeConsequence(usage: LedgerAccountUsage, t: Translator): string {
  const counts = t("finance.coa.code.usedOn", {
    bills: t("finance.coa.code.bills", { count: usage.bills }),
    payments: t("finance.coa.code.payments", { count: usage.payments }),
  });
  const lines = [`${counts} ${t("finance.coa.code.appliesEverywhere")}`];
  const warning = codeChangeWarning(usage, t);
  if (warning !== null) lines.push(warning);
  return lines.join("\n");
}

/** `PATCH /ledger/accounts/{id}` — the name, the role, the package refs, and
 *  (`CR-196-BRC10`, System Admin only) the CODE, behind a confirmation that
 *  counts what it touches. TYPE stays locked. */
function EditAccountModal(props: {
  row: LedgerChartRow;
  designations: readonly string[];
  client: ApiClient;
  t: Translator;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const translate = props.t;
  // `CR-196-BRC10` Q4 A — only a System Admin may change a code. A `null` role
  // means `/me/permissions` has not answered and the field is OFFERED
  // (BR-SHL-025); `services.change_account_code` is the boundary either way.
  const role = useTenantRole(props.client);
  const mayChangeCode = role === null || role === ROLE_SYSTEM_ADMIN;
  const [code, setCode] = useState(props.row.code);
  const [name, setName] = useState(props.row.name);
  const [designation, setDesignation] = useState(props.row.designation ?? "");
  /** The open confirmation, and the decision `handleSubmit` is waiting on. */
  const [confirming, setConfirming] = useState<LedgerAccountUsage | null>(null);
  const decide = useRef<((go: boolean) => void) | null>(null);
  // `DEF-LED-6715` — the two values the deleted *Codes your accounting package
  // knows* panel printed. They were always PATCHable; only the screen that
  // could set them was missing, which is why this is two fields and no new
  // endpoint.
  const [qboRef, setQboRef] = useState(props.row.qbo_ref ?? "");
  const [xeroRef, setXeroRef] = useState(props.row.xero_ref ?? "");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    const newCode = code.trim();
    const codeChanged = newCode !== props.row.code;
    try {
      if (codeChanged) {
        // (2) — the confirmation names what the change touches BEFORE it is
        // sent. The dialog settles this promise; the form keeps its one
        // submit in flight meanwhile, so nothing can be sent twice.
        const usage = await getLedgerAccountUsage(props.row.account_id, props.client);
        const go = await new Promise<boolean>((resolve) => {
          decide.current = resolve;
          setConfirming(usage);
        });
        decide.current = null;
        setConfirming(null);
        if (!go) {
          return { ok: false, error: { code: "", message_key: "finance.coa.code.kept" } };
        }
      }
      await updateLedgerAccount(
        props.row.account_id,
        {
          // Sent ONLY when it changed, so a clerk's rename never carries it.
          ...(codeChanged ? { code: newCode } : {}),
          name,
          designation: designation === "" ? null : designation,
          qbo_ref: qboRef.trim() === "" ? null : qboRef.trim(),
          xero_ref: xeroRef.trim() === "" ? null : xeroRef.trim(),
        },
        props.client,
      );
      props.onSaved();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={translate("finance.coa.edit.title", { code: props.row.code })}
      kicker={translate("finance.coa.title")}
      schema={EDIT_SCHEMA}
      values={{ code, name, designation, qbo_ref: qboRef, xero_ref: xeroRef }}
      submitLabel={translate("finance.coa.edit.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* `CR-196-BRC10` — the CODE is a field again, for a System Admin, even
          on a used account. `id` IS the server's field name, so `code_taken`
          and `tax_series_reserved` land under this box. Everyone else reads
          it locked, with the one fact that explains it. */}
      <TextField
        id="code"
        label={translate("finance.coa.col.code")}
        value={code}
        onChange={setCode}
        required
        readOnly={!mayChangeCode}
        help={mayChangeCode ? undefined : translate("finance.coa.edit.codeAdminOnly")}
        autoComplete="off"
      />
      <TextField
        id="name"
        label={translate("finance.coa.col.name")}
        value={name}
        onChange={setName}
        required
      />
      <SelectField
        id="designation"
        label={translate("finance.coa.col.designation")}
        value={designation}
        onChange={setDesignation}
        placeholder={translate("finance.coa.edit.noDesignation")}
        options={props.designations.map((value) => ({
          value,
          label: t(`finance.designation.${value}`, { defaultValue: value }),
        }))}
      />
      {/* THE SAME TWO LABELS THE DELETED PANEL USED (`finance.map.col.qbo` /
          `.xero`), unchanged — B14 rule 34's reasoning: a clerk who learnt a
          word on one surface must read the same word on the one that replaced
          it. `id` IS the server's field name, so a `field_error` lands under
          the box it names. */}
      <TextField
        id="qbo_ref"
        label={translate("finance.map.col.qbo")}
        value={qboRef}
        onChange={setQboRef}
      />
      <TextField
        id="xero_ref"
        label={translate("finance.map.col.xero")}
        value={xeroRef}
        onChange={setXeroRef}
      />
      {/* ⚠ **`readOnly`, NOT `disabled`, AND NOT A `FactRow` (PO 2026-09-22,
          change 7: the frozen sentence moves *"into the edit modal, where the
          fields it describes are"*).** These two were `FactRow`s under the old
          inline form — label-and-value, which reads as trivia beside a form. The
          kit's own note draws the line: `readOnly` is for a value the clerk may
          READ but not set — *"a frozen code"* is the example it gives — and it
          stays focusable and selectable, which matters because a clerk reading a
          number down the phone needs to select it. They are drawn as the FIELDS
          they are, locked, immediately above the sentence that says why. */}
      <TextField
        id="frozen_type"
        label={translate("finance.coa.col.type")}
        value={t(`finance.gl.type.${props.row.type}`, { defaultValue: props.row.type })}
        onChange={() => undefined}
        readOnly
      />
      {/* B14 rule 33 — the RATIONALE came out rather than being shortened.
          *"history is never restated"* is why the product works this way and is
          ZERO words on screen; it lives in `update_account`'s docstring, which
          is what a docstring is for. What is left is a fact and an instruction,
          six words each. */}
      <Note>{translate("finance.coa.edit.typeFrozen")}</Note>
      {confirming !== null && (
        <ConfirmDialog
          title={translate("finance.coa.code.confirmTitle", { code: code.trim() })}
          consequence={codeChangeConsequence(confirming, translate)}
          confirmLabel={translate("finance.coa.code.confirm")}
          // B14 rule 6 — every past entry and report reads the new code the
          // moment this is pressed, so it commits at the danger tier.
          confirmVariant="danger"
          working={false}
          onConfirm={() => decide.current?.(true)}
          onCancel={() => decide.current?.(false)}
        />
      )}
    </FormModal>
  );
}

export interface ChartOfAccountsPanelProps {
  client?: ApiClient;
  /** BR-TEN-043 — the instant a retirement is stamped with. Passed IN so a
   *  double-submitted control stamps one moment and a test can state it. */
  now: () => string;
  t: Translator;
  /**
   * ⚠ **ACCEPTED AND IGNORED SINCE 2026-09-25 (`DEF-LED-6715`), AND KEPT ON
   * PURPOSE FOR ONE COMMIT'S WORTH OF SAFETY.**
   *
   * It used to choose between the chart alone and the chart plus four GL-map
   * panels. **There are no panels any more** — the PO merged them into the one
   * table — so both values draw the same screen and `Settings → Accounting →
   * Chart of accounts` no longer needs to ask for half of it.
   *
   * It stays declared so the prop's two live callers (`SettingsAccountingTab`
   * and `chartDialogs.dom.test.tsx`) do not fail to compile in the window
   * between this commit and theirs. Removing it is a one-line change in each
   * and is filed rather than done here, because a lane is editing one of those
   * files right now.
   */
  sections?: "all" | "chart";
}

export function ChartOfAccountsPanel(props: ChartOfAccountsPanelProps) {
  const { t } = useTranslation();
  const translate = props.t;
  const client = props.client ?? api;
  const toast = useToast();
  const queryClient = useQueryClient();

  const [typeFilter, setTypeFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");
  const columns = useChartColumns();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<LedgerChartRow | null>(null);
  /**
   * ⚠ **THE ROW ACTIONS ONLY, SINCE `DEF-LED-6140`.** Add and Edit carry their
   * own refusals inside their dialogs now. Retire, Bring back and Delete are
   * row-level commands with no form, so their refusal still renders here.
   *
   * **That strip is one screen from the filters and can be one screen from the
   * ROW** — a delete refused on line 129 of a 129-row chart says so at the top
   * of the page. It is the same distance fault this defect was filed for, one
   * control family over, and it is FILED rather than fixed here
   * (`DEF-LED-6147`): widening this change to redesign three row actions the PO
   * did not report is what the maintenance process's step 3 forbids.
   */
  const [failure, setFailure] = useState<string | null>(null);

  /**
   * ⚠ **`needs-account` IS DELIBERATELY NOT IN THE QUERY, AND THIS WAS FOUND
   * BY LOOKING AT THE SCREEN (hard-won law 6).**
   *
   * It asks about ROLES, and the server says so by ignoring it — so sending it
   * is a round trip whose answer is the unfiltered chart. That would be merely
   * wasteful if it did not also change the query KEY: a new key means
   * `chart.data` is `undefined` while it resolves, the panel falls to its
   * loading skeleton, **and the count badge goes with it**. On the demo
   * tenant's 130 rows the whole screen blanked for over a second on a control
   * that needs no data it did not already have.
   *
   * Every unit case passed over it. The browser walk photographed a page of
   * grey bars where three role names should be — which is why a screenshot is
   * part of this defect's proof and a `toContain` is not.
   */
  const servedRole = roleFilter === ROLE_FILTER_NEEDS_ACCOUNT ? "" : roleFilter;
  const filterKey = `${typeFilter}|${categoryFilter}|${statusFilter}|${servedRole}|${search}`;
  const chart = useQuery({
    queryKey: chartQueryKey(filterKey),
    queryFn: () =>
      getChartOfAccounts(
        {
          q: search,
          type: typeFilter,
          category: categoryFilter,
          status: statusFilter,
          designation: servedRole,
          withReferences: true,
        },
        client,
      ),
    retry: false,
  });
  // ⚠ **`GET /ledger/gl-mappings` IS NO LONGER READ BY THIS SCREEN.** Its four
  // panels are gone (`DEF-LED-6715`), and a request whose answer nothing
  // renders is a request nobody should pay for — it was already written that
  // way for the Settings mount and is now true of both. The endpoint is still
  // served and still read by `SettingsAccountingTab`'s Mapping sub-tab.

  const designationOptions = useMemo(() => chart.data?.designations ?? [], [chart.data]);
  /**
   * ⚠ **SERVED, NEVER DERIVED FROM `chart.data.rows` — AND THAT IS NOT A
   * PREFERENCE.** A role with no live account HAS NO ROW HERE, so there is
   * nothing on this page to derive it from; working it out client-side would
   * always produce an empty list and the screen would report all-clear over a
   * real gap. `services.chart_of_accounts` resolves it through
   * `selectors.designation_map()`, which walks the whole designation tuple.
   *
   * It is read off the CURRENT response, so it stays true while the clerk
   * filters: the count is a fact about the tenant's chart, not about the rows
   * on screen, and the server computes it over the whole chart either way.
   */
  const rolesNeedingAccount = chart.data?.roles_needing_account ?? [];

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["ledger"] });
  };

  const report = (error: unknown, fallback: string) => {
    setFailure(isApiError(error) ? apiErrorText(error, translate) : t(fallback));
  };

  // `addAccount` and `saveEdit` USED TO LIVE HERE. They moved into
  // `AddAccountModal` and `EditAccountModal` with DEF-LED-6140, because a
  // refusal has to be rendered by whatever is holding the button that produced
  // it — and here that was a panel the clerk could not see.

  async function toggleActive(row: LedgerChartRow) {
    setFailure(null);
    try {
      const result = await setLedgerAccountActive(
        row.account_id,
        row.status !== "active",
        props.now(),
        client,
      );
      if (result.designation_now_unresolved != null) {
        // The hole is REPORTED the moment it opens, not discovered later on a
        // failed bill run.
        toast(
          t("finance.coa.designationDarkToast", {
            designation: t(`finance.designation.${result.designation_now_unresolved}`, {
              defaultValue: result.designation_now_unresolved,
            }),
          }),
        );
      } else {
        toast(t("finance.coa.savedToast"));
      }
      refresh();
    } catch (error) {
      report(error, "finance.coa.error.saveFailed");
    }
  }

  async function removeAccount(row: LedgerChartRow) {
    setFailure(null);
    try {
      await deleteLedgerAccount(row.account_id, client);
      toast(t("finance.coa.deletedToast"));
      refresh();
    } catch (error) {
      report(error, "finance.coa.error.deleteFailed");
    }
  }

  return (
    <>
      <div className="fin-params">
        <label className="fin-params-field">
          {t("finance.coa.filter.search")}
          <input
            className="input"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("finance.coa.filter.searchPlaceholder")}
          />
        </label>
        <label className="fin-params-field">
          {t("finance.coa.filter.type")}
          <select
            className="input"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <option value="">{t("finance.coa.filter.allTypes")}</option>
            {/* BR-REP-006 — the LIVE vocabulary, served with the list. */}
            {(chart.data?.types ?? []).map((value) => (
              <option key={value} value={value}>
                {t(`finance.gl.type.${value}`, { defaultValue: value })}
              </option>
            ))}
          </select>
        </label>
        <label className="fin-params-field">
          {t("finance.coa.filter.category")}
          <select
            className="input"
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
          >
            <option value="">{t("finance.coa.filter.allCategories")}</option>
            {/* BR-REP-006 — the LIVE vocabulary, served with the list. */}
            {(chart.data?.categories ?? []).map((value) => (
              <option key={value} value={value}>
                {t(`finance.gl.category.${value}`, { defaultValue: value })}
              </option>
            ))}
            {/* The UNCATEGORISED group is a real filter value, not an absent
                one: on a chart provisioned before 2026-09-02 it is the only
                group there is, and a picker that could not name it would leave
                a utility unable to find the rows it has to file. */}
            <option value="none">{t("finance.coa.category.none")}</option>
          </select>
        </label>
        <label className="fin-params-field">
          {t("finance.coa.filter.status")}
          <select
            className="input"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">{t("finance.coa.filter.allStatuses")}</option>
            <option value="active">{t("finance.coa.status.active")}</option>
            <option value="deactivated">{t("finance.coa.status.deactivated")}</option>
          </select>
        </label>
        {/* ⚠ **THE ROLE FILTER IS TWO THINGS AT ONCE, AND THE SECOND ONE IS WHY
            IT EXISTS (`DEF-LED-6715`).**

            As a FILTER it is Finance blueprint p025 note 3 — `f.designation`,
            marked **NOT SERVED** there and called *"the gap"*: *"Designation is
            how 4·1 finds the tax accounts and how the exporter finds cash — it
            is the load-bearing column and you cannot filter by it."* That is
            what replaces the deleted *Tax authorities* panel.

            As a DISCLOSURE its last value, *Needs an account*, is the only
            surviving trace of the deleted roles panel — the roles that have no
            live account at all, which no column can show because they have no
            row. The badge beside the label is the COUNT, so a clerk does not
            have to open the menu to learn there is something wrong; B14 rule 32
            keeps the LIST closed by default and rule 33 keeps the reason off
            the screen entirely.

            `CountBadge` renders nothing at zero, which is the behaviour this
            needs exactly: on a chart with every role filled there is no badge
            and no option, and the screen says nothing rather than reassuring
            anybody. */}
        <label className="fin-params-field">
          {/* ⚠ **ONE CHILD, NOT TWO, AND THE IMAGE IS WHY (`DEF-LED-6715`).**
              `.fin-params-field` is a COLUMN flex, so every child of it is a
              row — and the badge written as a sibling of the label text became
              a third row, pushing this one filter's `<select>` 20px below the
              other four. The DOM was correct and every assertion passed; it is
              only visible in a screenshot, which is B14 rule 44's case exactly:
              our spacing decides how a thing is built.

              A wrapping `<span>` is `display: inline`, so the word and the
              inline-flex badge share one line and the column flex sees ONE
              child. No new class and no Tailwind utility — which matters,
              because this file is deliberately off `route-b-migrated.txt` and
              `G31` refuses a utility written here. */}
          <span>
            {t("finance.coa.filter.role")}{" "}
            {rolesNeedingAccount.length > 0 && (
            <span data-testid="coa-unfilled-roles-count">
              {/* `accent`, and this is the caller the tone was built for: the
                  badge's own header says it is *"for a count that is itself the
                  reason to look"*. Every other count in the product is how many
                  are waiting; this one is how many things are BROKEN. */}
              <CountBadge
                count={rolesNeedingAccount.length}
                srLabel={t("finance.coa.filter.roleNeedsAccount")}
                tone="accent"
              />
            </span>
            )}
          </span>
          <select
            className="input"
            data-testid="coa-role-filter"
            value={roleFilter}
            onChange={(event) => setRoleFilter(event.target.value)}
          >
            <option value="">{t("finance.coa.filter.allRoles")}</option>
            {/* BR-REP-006 — the LIVE vocabulary, served with the list. */}
            {(chart.data?.designations ?? []).map((value) => (
              <option key={value} value={value}>
                {t(`finance.designation.${value}`, { defaultValue: value })}
              </option>
            ))}
            <option value={ROLE_FILTER_NONE}>{t("finance.coa.filter.roleNone")}</option>
            {rolesNeedingAccount.length > 0 && (
              <option value={ROLE_FILTER_NEEDS_ACCOUNT}>
                {t("finance.coa.filter.roleNeedsAccount")}
              </option>
            )}
          </select>
        </label>
      </div>

      {failure !== null && (
        <p className="fin-absent-reason" role="alert">
          {failure}
        </p>
      )}

      {chart.data === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <ChartTable
          chart={chart.data}
          t={translate}
          visibleColumns={columns.visible}
          rolesNeedingAccount={rolesNeedingAccount}
          showingRoles={roleFilter === ROLE_FILTER_NEEDS_ACCOUNT}
          columnsControl={
            // B14 rule 43 — the kit's own menu, not a second one written here.
            <ColumnChooser
              items={CHART_COLUMNS.map((column) => ({
                ...column,
                label: t(column.label),
              }))}
              visible={columns.visible}
              onToggle={(key) =>
                columns.update(toggleColumnVisible(columns.visible, key, CHART_TABLE_CONFIG))
              }
              onMoveUp={(key) => columns.update(moveColumnUp(columns.visible, key))}
              onMoveDown={(key) => columns.update(moveColumnDown(columns.visible, key))}
              onReset={() => columns.update(defaultVisibleColumns(CHART_TABLE_CONFIG))}
            />
          }
          onAdd={() => setAdding(true)}
          onEdit={(row) => setEditing(row)}
          onToggleActive={(row) => void toggleActive(row)}
          onDelete={(row) => void removeAccount(row)}
        />
      )}

      {/* ⚠ **TWO `<Panel>` FORMS STOOD HERE UNTIL `DEF-LED-6140`, AND THE
          SECOND ONE IS WHY THE PO COULD NOT READ A REFUSAL.** The Add form was
          drawn below the whole table and the Edit form below that, so on the
          demo tenant's 129-row chart they began at y=14,770 and y=14,999 — and
          the panel's only refusal strip is up beside the filters at y=698.
          Pressing Save on an edit the server refused therefore changed nothing
          a clerk could see.

          They are dialogs now. `FormModal` renders the refusal in the
          form-message slot between the fields and the buttons, and puts every
          `field_error` under the input it names, so the sentence is never more
          than a few hundred pixels from the control that caused it however long
          the chart grows.

          ⚠ **THE ADD DIALOG IS NOT MOUNTED UNTIL IT IS OPEN, AND THAT IS NOT A
          MICRO-OPTIMISATION.** It seeds its Type from `chart.types[0]`, so a
          dialog kept mounted across a refetch would hold the type the clerk
          chose at the moment the list first loaded. Mounting on open is what
          makes each dialog start from the CURRENT served vocabulary. */}
      {adding && chart.data !== undefined && (
        <AddAccountModal
          chart={chart.data}
          client={client}
          t={translate}
          onClose={() => setAdding(false)}
          onAdded={() => {
            setAdding(false);
            toast(t("finance.coa.addedToast"));
            refresh();
          }}
        />
      )}

      {editing !== null && (
        <EditAccountModal
          row={editing}
          designations={designationOptions}
          client={client}
          t={translate}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            toast(t("finance.coa.savedToast"));
            refresh();
          }}
        />
      )}

    </>
  );
}

export default ChartOfAccountsPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-005@e85081b (sources, in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-02-chart-mapping.md US-LED-005 + US-LED-006 · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.10 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-017 · 05-prototype/UtilityBilling.html lines 3714-3720)
// generated: 2026-08-16 by story-coder (the ledger surface lane — the chart was tenant-customizable by design and by nobody in practice)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the S56 chart test could not resolve `./ChartOfAccountsPanel` before this file existed. tsc✔ · eslint✔ · vitest✔ · vite build✔
// exceptions: (1) THE PROTOTYPE'S FIVE-ROW "Account mapping" PANEL IS NOT PORTED — four of its five rows name an account the ❄️ finance-signed chart does not have (4200 is LATE-FEE revenue not water, there is no 4910 or 6100, and 2300 is the deposit liability not tax payable), so the panel is drawn from the LIVE map and the divergence is REPORTED · (2) `type` is not offered for edit — US-LED-005 freezes it once posted against; ⚠ AMENDED 2026-10-29 (`CR-196-BRC10`): `code` IS offered, to a System Admin, behind a confirmation that counts the bills and payments it touches (it read "`code` and `type` are not offered for edit at all — US-LED-005 freezes both once posted against") · (3) DELETE renders DISABLED WITH ITS REASON and distinguishes "fourteen journal lines point at this" from "we cannot tell what points at this"; the second is the server's `answerable: false` and is never rendered as a zero · (4) the SERVICE→revenue write is not offered here: `tenant_services` is TENANCY's table and a cross-module write is forbidden, so the panel names `PATCH /settings/services/{code}` as the owner of that half · (5) ⚠ AMENDED 2026-09-03 (DEF-2346). This clause read "S73/S74 are BLOCKED on five open questions and NOTHING of them is built — the boundary panel states the blockage in plain language". BOTH SCREENS SHIPPED: App.tsx mounts CostOfServicePage, FINANCE_TABS carries the Costs tab, and apps/ledger/cost_api.py serves the register, the capture, the correction, the void and the bought-versus-billed comparison. The panel and its six strings are removed rather than reworded, because the feature is one click away and B14 rule 32 gives a screen one sentence per section. OQ-204's second half stays open as a DOCS ratification and no longer needs a sentence on a clerk's screen
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
