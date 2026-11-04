// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-005 (S27 Cycles — the read-only operational view)
//           Screens: S27 · RDS-02C — the **Read cycles** tab of the Reads page
//           Blueprint: Meter Reads entry 15 (*Read cycles — the list*), drawn
//           2026-09-12/13 and read AS AN IMAGE (B14 rule 42), built 2026-09-14
// Change:   `CR-096-BRC02` · `R2` — PO 2026-09-12, verbatim: *"Cycle and Route —
//           we should say Read Cycles and within that we should show Routes and
//           their completion"*, and *"we will need a list view of read cycles
//           and we will need a detail view of read cycles"*.
// Rules:    BR-MET-010 (a cycle's route list DERIVES from route assignment) ·
//           BR-MET-011 **CONFIRMED-AS-NARROWED 2026-09-14** (all CRUD of a
//           cycle's DEFINITION stays in Settings; the reading WORK is writable
//           on an operational screen — this list writes neither) ·
//           BR-MET-057 (the cycle window drives expectations) · BR-MET-078
//           (nothing on this screen touches money) · BR-SHL-010 (only a DECLARED
//           capability renders) · BR-SHL-011 (the q / sort / dir / page / per /
//           f.<name> grammar) · BR-SHL-020 (the A18 states) · BR-SHL-034 (one
//           date formatter)
// B14:      rule 2 (ONE page header — the Reads page owns it; this file draws
//           none) · 12 (one toolbar row) · 13 (⇅ on the drawn headers) · 14 (the
//           ▦ chooser) · 16 (the pagination footer) · 17 (the empty state and
//           the action that fills it) · 19 (this list's own prompt) · 20 (one
//           table type) · 21 (Tailwind; this file adds no class to any
//           stylesheet and is listed in `styles/route-b-migrated.txt`) · 31 (no
//           database id on screen) · 33 (the copy caps) · 41 · 42
// NFR:      NFR-3 (universal server pagination — the breach this entry fixes) ·
//           NFR-5 (no hard caps)
// ───────────────────────────────────────────────────────
// **THE READ CYCLES TAB.** Entry 15's question, in the drawing's own words:
// *"Which cycles can I bill on Friday, and which are short?"*
//
// **WHAT THIS REPLACES, AND WHY IT IS AN `NFR-3` FIX RATHER THAN A RESTYLE.**
// The tab used to mount `CyclesOpsPage`, which read `getCycles()` — a walk of
// every page at a thousand a page — and then sliced the result in the browser.
// The drawing's own summary of the table controls: *"Search · filter · columns ·
// sort · server pager — all four, where today there are none and the pager runs
// in the browser over a fetch-everything read."* Every one of the four is on the
// SERVER here: the request state travels as `?q=`/`sort=`/`dir=`/`page=`/`per=`/
// `f.<name>=` (BR-SHL-011) and the answer is one page with its own `count`.
//
// ⚠ **THIS COMPONENT DRAWS NO PAGE HEADER, AND THAT IS B14 RULE 2 RATHER THAN
// AN OMISSION.** It is the BODY of a tab on `ReadsListPage`, which already
// renders the one `PageHeader` the drawing shows — *Reads*, with `+ Add
// reading`, `Estimate a missing read`, `Route sheet PDF` and `↑ Upload reads`.
// The component it replaces drew a SECOND head of its own underneath that one,
// which is rule 2's own breach; the drawing shows one.
//
// ⚠ **THERE IS NO PRIMARY ACTION ON THIS LIST AND THAT IS BY RULE, NOT BY
// OVERSIGHT.** The drawing says so in as many words — *"None on the list.
// BR-MET-011 puts every create, edit and delete in Settings, and this file
// imports no mutation wrapper at all."* Nothing here is disabled; it is ABSENT.
// `Manage in Settings →` is gone from this screen too: the drawing moves it into
// entry 20's header, beside the cycle it configures. The one way out of an EMPTY
// list is the empty state's own *Add a cycle in Settings →*, which is what the
// drawing puts there and what the screen lacked.
//
// ⛔ **TWO DRAWN COLUMNS ARE DELIBERATELY NOT BUILT — `DEF-MET-5206`, PO ruling
// 2026-09-14, verbatim: *"Settle first."***
// The drawing's callout ④ **Registers collected** and callout ⑤ **Window** are
// both computed from the cycle's CURRENT WINDOW, and **two derivations of that
// window give different answers**: measured on one day, the cycle row printed
// August while the completeness engine answered September. The blueprint states
// the consequence plainly — *"Build these two on the fork and you get a screen
// that disagrees with itself. It is a filed backend disagreement, not a design
// question… Everything else on this drawing is safe to build now."* So they are
// not declared on the capability row at all: not hidden, not disabled, ABSENT,
// so the ▦ chooser cannot offer a column that would print a figure from an
// unsettled fork. The `GET /cycles/{id}/chase-list` read that fed ④ goes with
// them, and so does the `Chase N meters` link — which the drawing moves into
// entry 20, where the meters it names are listed. **Nothing here picks a winner
// between the two derivations**, which is the whole point of not building them.
//
// ⚠ **THE REQUEST STATE IS LOCAL AND NOT IN THE URL, AND IT IS A CHOICE WITH A
// REASON.** BR-SHL-011's grammar is a grammar for ONE table per URL: `q`,
// `sort`, `dir`, `page` and `per` are unprefixed. This tab shares its address
// (`/:tenant/reads?tab=cycles`) with the All-reads table, which owns exactly
// those params — so writing ours into the same query string would carry a cycle
// search across to the readings list on a tab click, and a page number with it.
// The cost is that a filtered cycles view is not shareable by link; it is stated
// in the trailer as an exception rather than left to be discovered.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCyclesPage } from "@/api/endpoints";
import type { CycleRow } from "@/api/endpoints";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { ListExportButton } from "@/features/exports/ListExportButton";
import {
  CYCLE_FREQUENCY_WORDS,
  ChipList,
  effectiveStartDay,
  frequencyLabel,
  startWindowLabel,
} from "@/features/tenancy/routesCyclesShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

/**
 * ⚠ **ENTRY 20'S ADDRESS IS IMPORTED, NEVER RE-DECLARED HERE.**
 *
 * `readCycleDetailPath` lives in `meteringShared` beside `premisesDetailPath`
 * and `unitDetailPath`, because TWO screens build it: this list builds the link
 * and entry 20 mounts the route. A copy in either file is a copy the other has
 * to keep in step, which is hard-won law 5 in miniature and is how a row comes
 * to open nothing after somebody moves a route. The first draft of this file
 * declared its own three-line copy; it is gone.
 */
import {
  DASHBOARD_ROUTE,
  Dash,
  PREMISES_PERMISSION,
  isDenied,
  readCycleDetailPath,
  useRegional,
  useAccessCell,
} from "./meteringShared";
import type { RegionalProps } from "./meteringShared";

// ── Addresses ──────────────────────────────────────────────────────────────

/** Where a cycle's DEFINITION is edited. The empty state's only way out. */
export const SETTINGS_ROUTES_CYCLES = "/settings/reference-data/routes-cycles";

/**
 * Entry 15's own address: `/:tenant/reads?tab=cycles` — the tab that replaces
 * `/:tenant/reads/cycles`, *"which had no door"*. Built once here so the retired
 * address's redirect and any future link cannot spell it two ways.
 */
export const READ_CYCLES_TAB_PATH = "/reads?tab=cycles";

export const readCyclesQueryKey = ["cycles", "read-cycles"] as const;

/** `.met-qualifier` as a utility — the muted trailing fact inside a cell. */
const QUALIFIER = "text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** The OPERATIONAL status pill's tone (scheduled / in progress / billed). */
export function cycleStatusTone(status: string): "success" | "warning" | "neutral" {
  if (status === "in_progress") {
    return "warning";
  }
  if (status === "billed") {
    return "success";
  }
  return "neutral";
}

/**
 * **THE FREQUENCY CELL — entry 15 folds three columns into one.**
 *
 * The drawing's redesign note, verbatim: *"Ten columns become nine: `Start day`
 * and `Days to complete` fold into **Frequency**, which is where a person reads
 * them anyway (`Monthly · day 1 · 3 days`)"*. Both facts stay on screen, in the
 * same row — this is a MOVE and not a removal, and the as-built table records it
 * as one.
 *
 * ⚠ **THE DAY IS THE EFFECTIVE ONE (OQ-340), NOT THE STORED ONE.** The engine
 * anchors on the first run's day whenever the two disagree and does not rewrite
 * the column, so the stored number can describe nothing the product does.
 * `effectiveStartDay` is the one place that decision is made, and this cell
 * reads through it rather than reaching for `start_day`.
 *
 * Composed from FRAGMENTS rather than one sentence per shape: `Daily`, `Weekly`
 * and `Fortnightly` carry no day-of-month at all (B17 §7), and a cycle with no
 * length yet has no third part. Two keys and a plural cover every combination;
 * five sentence templates would have covered the same ground and drifted apart.
 */
export function cycleFrequencyLine(cycle: CycleRow, t: Translator, dash: string): string {
  const parts: string[] = [frequencyLabel(cycle.frequency, t, dash)];
  const day = effectiveStartDay(cycle).day;
  if (day !== null) {
    parts.push(t("metering.cycles.freq.day", { day }));
  }
  const days = cycle.days_to_complete;
  if (days !== null) {
    parts.push(
      t(days === 1 ? "metering.cycles.freq.days.one" : "metering.cycles.freq.days.other", {
        count: days,
      }),
    );
  }
  return parts.join(" · ");
}

// ── The capability row ─────────────────────────────────────────────────────

export interface ReadCyclesTabProps extends RegionalProps {
  client?: ApiClient;
}

/**
 * **SEVEN COLUMNS, AND THE TWO THAT ARE MISSING ARE MISSING ON PURPOSE.**
 *
 * The drawing declares nine: Cycle · Routes · Frequency · Read window · Bill
 * date · Meters · **Registers collected** · **Window** · Status. The two in bold
 * are `DEF-MET-5206` and are not declared here at all — see the file's opening
 * note for the ruling and the measured disagreement behind it.
 *
 * ⚠ **EVERY `sortable` KEY IS ONE THE SERVER ANSWERS**, and the drawing puts a
 * ⇅ on exactly three headers: Cycle, Read window and Bill date.
 * `selectors.CYCLE_SORTS` gained `read_window` (an alias of `start_day`, so a
 * column headed *Read window* does not have to send `sort=start_day`) and
 * `bill_date` (derived per row, sorted on the built page) in the same commit as
 * this file. A column declaring a sort the server does not answer is a control
 * that looks as though it worked: `parse_list_params` discards the param, the
 * list comes back in its default order, and nothing anywhere says so.
 */
export function readCyclesTableConfig(
  t: Translator,
  deps: {
    dash: string;
    tenantPath: (segment: string) => string;
    timeZone: string;
    dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  },
): TableConfig<CycleRow> {
  const { dash, tenantPath, timeZone, dateFormat } = deps;
  return {
    screenId: "RDS-02C",
    getRowId: (row) => row.id,
    // Entry 15 callout ② — *"Search · cycle code and route code"*. The server
    // matches all three (`cycles_queryset`: code, name, route code), and rule
    // 19's prompt below names what it matches — a prompt claiming a field the
    // query does not match is the one failure CR-041's amendment says no
    // source-reading check can ever catch.
    searchFields: ["code", "name", "route"],
    searchPlaceholder: "metering.cycles.searchPlaceholder",
    filters: [
      {
        name: "frequency",
        label: t("settings.cycles.col.frequency"),
        options: CYCLE_FREQUENCY_WORDS.map((word) => ({
          value: word,
          label: t(`settings.cycles.frequency.${word.toLowerCase()}`),
        })),
      },
      {
        // ⚠ **`f.status` IS THE LIFECYCLE, AND THE STATUS COLUMN IS NOT.**
        // `CycleRow.status` is the OPERATIONAL progress of the current period
        // (scheduled / in progress / billed) and is derived, so it is neither
        // filterable nor sortable; `lifecycle_status` is the stored draft /
        // active / inactive column the server filters on. Labelling this chip
        // *Status* would put a filter and a column of the same name over two
        // different facts, which is the quietest way to make a control wrong.
        name: "status",
        label: t("metering.cycles.filter.lifecycle"),
        options: (["draft", "active", "inactive"] as const).map((code) => ({
          value: code,
          label: t(`settings.routes.status.${code}`),
        })),
      },
    ],
    defaultSort: { sort: "code", dir: "asc" },
    // ⚠ **THE WHOLE ROW OPENS ENTRY 20** — the drawing's own words, *"The row is
    // the target; it opens entry 20"*. `DataTable` activates the identity cell's
    // own `<a>` rather than navigating itself, so the row and the link can never
    // disagree about where they go and the keyboard target stays the link.
    rowHref: (row) => tenantPath(readCycleDetailPath(row.id)),
    columns: [
      {
        key: "code",
        label: t("metering.cycles.col.cycle"),
        identity: true,
        sortable: true,
        cell: (row) => (
          <Link
            className="text-accent underline"
            to={tenantPath(readCycleDetailPath(row.id))}
            title={t("metering.ops.openDetail", { code: row.code })}
          >
            {row.code}
          </Link>
        ),
      },
      {
        // BR-MET-010 — exactly the routes assigned to this cycle, derived and
        // never a second stored list. A route CODE is the reader's own word for
        // it, so B14 rule 31 is satisfied by showing it rather than an id.
        key: "routes",
        label: t("metering.cycles.col.routes"),
        cell: (row) => <ChipList items={row.routes} empty={<Dash />} />,
      },
      {
        key: "frequency",
        label: t("metering.cycles.col.frequency"),
        cell: (row) => cycleFrequencyLine(row, t, dash),
      },
      {
        key: "read_window",
        label: t("metering.cycles.col.window"),
        sortable: true,
        cell: (row) =>
          row.window_start !== null && row.window_end !== null ? (
            <span className="whitespace-nowrap">
              <DateCell value={row.window_start} timeZone={timeZone} dateFormat={dateFormat} />
              {" – "}
              <DateCell value={row.window_end} timeZone={timeZone} dateFormat={dateFormat} />
            </span>
          ) : (
            // No dated window: the day-of-month shape the three schedule fields
            // derive, and the dash only when there is nothing to shape at all.
            startWindowLabel(row, dash)
          ),
      },
      {
        key: "bill_date",
        label: t("metering.cycles.col.billDate"),
        sortable: true,
        cell: (row) =>
          row.bill_date === null ? (
            <Dash />
          ) : (
            <span className="whitespace-nowrap">
              <DateCell value={row.bill_date} timeZone={timeZone} dateFormat={dateFormat} />
              {row.due_date !== null && (
                <span className={QUALIFIER}>
                  {" "}
                  {t("metering.cycles.due")}{" "}
                  <DateCell value={row.due_date} timeZone={timeZone} dateFormat={dateFormat} />
                </span>
              )}
            </span>
          ),
      },
      {
        // Callout ③ — `cycle.expected`, UNCHANGED, and *"now the only meter
        // count on the row"*. It used to be read beside a Collected column
        // counting READINGS, which is what made the old quotient meaningless
        // (DEF-2730: three cycles drew a full bar reading 100% at 300, 500 and
        // 400 percent).
        key: "expected",
        label: t("metering.cycles.col.meters"),
        numeric: true,
      },
      {
        // The OPERATIONAL status of the current period. ⚠ **THIS IS ALSO WHERE
        // THE DOMAIN STATE *before the window opens* SURVIVES ON THIS SCREEN**:
        // the drawing states that condition in three places and two of them are
        // ④ and ⑤, which `DEF-MET-5206` holds. `scheduled` is served from the
        // committed-read count alone and touches neither derivation of the
        // window, so it is the half of that state this list may honestly show
        // today.
        key: "status",
        label: t("metering.cycles.col.status"),
        cell: (row) => (
          <StatusPill tone={cycleStatusTone(row.status)}>
            {t(`metering.cycles.status.${row.status}`, { defaultValue: row.status })}
          </StatusPill>
        ),
      },
    ],
  };
}

// ── The screens ────────────────────────────────────────────────────────────

/**
 * **Entry 14 + entry 15 — the two retired addresses keep working.**
 *
 * `/:tenant/reads/routes` (entry 14, RETIRED as a screen by the PO ruling of
 * 2026-09-12) and `/:tenant/reads/cycles` (entry 15's old doorless address)
 * both land on the Read cycles tab. The blueprint asks for exactly this —
 * *"Kept and redirected to the Read cycles tab, the way the retired drawer's
 * `?read=` links are. There are tickets with these URLs in them."*
 *
 * ⛔ **BUILT AND NOT YET MOUNTED, AND THE HOLD IS ENTRY 14's OWN CONDITION.**
 * The drawing retires Routes *"as a screen"* and says in the same breath where
 * its contents go: *"Every column survives, inside the cycle it belongs to —
 * see entry 20."* Redirecting `/:tenant/reads/routes` BEFORE entry 20's Routes
 * section exists would do the half the ruling does not authorise — it would
 * lose the nine columns rather than move them, and it would take the only door
 * to entry 21 (the route detail, `reads/routes/:routeId`) with it, whose own
 * lane is building it now.
 *
 * ⚠ **SO THE HOLD CARRIES ITS OWN EXPIRY TEST, IN THIS COMMIT** — hard-won law
 * 2's amendment, *"when you write a hold, write the test that fires when the
 * hold expires."* `ReadCyclesTab.test.tsx` asserts that `App.tsx` does NOT yet
 * mount `reads/cycles/:cycleId`; the day entry 20 lands that case goes RED and
 * names this function. A hold with no such test is a promise nobody is keeping,
 * and `CR-068` R3's controls rotted for exactly that reason.
 */
export function RedirectToReadCycles() {
  const tenantPath = useTenantPath();
  return <Navigate to={tenantPath(READ_CYCLES_TAB_PATH)} replace />;
}

/** **The Read cycles tab's body.** Mounted by `ReadsListPage` on `?tab=cycles`. */
export function ReadCyclesTab(props: ReadCyclesTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);
  const cell = useAccessCell(PREMISES_PERMISSION, client);
  const dash = t("settings.unwiredCount");

  const config = useMemo(
    () => readCyclesTableConfig(translate, { dash, tenantPath, timeZone, dateFormat }),
    // `translate` and `tenantPath` are fresh closures on every render; the memo
    // keys on the values they read instead, exactly as `SettingsRoutesCyclesTab`
    // does and for the same reason — a new config per keystroke rebuilds the
    // column set under the chooser the user is holding open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, dash, timeZone, dateFormat],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  // ⚠ **NFR-3 — THE SERVER PAGES, SEARCHES, FILTERS AND SORTS.** What this
  // replaced was `getCycles()`, which walks every page at 1,000 a page and hands
  // the browser the whole list to slice: correct at three thousand connections
  // and 13× short of the top of the ICP.
  const listQuery = useQuery({
    queryKey: [...readCyclesQueryKey, JSON.stringify(state)],
    queryFn: () => getCyclesPage(state, client),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("metering.ops.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (listQuery.data === undefined && isPermissionDenied(listQuery.error)) {
    return (
      <PermissionDenied
        helper={t("metering.ops.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  return (
    <DataTable<CycleRow>
      config={config}
      state={state}
      onStateChange={setState}
      rows={listQuery.data?.rows ?? []}
      totalRows={listQuery.data?.total ?? null}
      loading={listQuery.isPending}
      // A18 §4 / BR-SHL-020 — the reason in plain language, and Retry re-issues
      // the identical query because the request state is untouched by a failure.
      error={
        listQuery.isError && listQuery.data === undefined
          ? {
              reason: apiErrorText(listQuery.error, translate),
              onRetry: () => void listQuery.refetch(),
            }
          : null
      }
      // The drawing's empty state — and its second half is what this screen
      // LACKED: the list could be empty with no way out of it, on a screen whose
      // whole create path is in Settings by rule.
      empty={{
        title: t("metering.cycles.empty"),
        helper: t("metering.cycles.emptyHelper"),
        ctaLabel: t("metering.cycles.emptyCta"),
        ctaReason: null,
        // B14 rule 4 — the page header above already owns this screen's primary.
        ctaVariant: "secondary",
        onCta: () => navigate(tenantPath(SETTINGS_ROUTES_CYCLES)),
      }}
      filterBarSlot={
        <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
      }
      // IS-9 — and it carries the table's LIVE request state now, so the file is
      // the list the clerk is looking at (BR-SHL-011). It posted an EMPTY state
      // until this entry, because the tab had no request state to post.
      downloadSlot={<ListExportButton resource="cycles" state={state} client={client} />}
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: Meter Reads blueprint entries 14 + 15 · CR-096-BRC02 · US-MET-005
// generated: 2026-09-14 by the Meter Reads entries 14+15 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (ReadCyclesTab.test.tsx)
// exceptions:
//   E3 [DEF-MET-5206, PO 2026-09-14 *"Settle first."*] entry 15's callouts ④ `Registers collected` and ⑤ `Window` are NOT BUILT and are not declared on the capability row. Both derive from the cycle's current window and two derivations of it disagree — measured on one day, the cycle row printed August while the completeness engine answered September. The `GET /cycles/{id}/chase-list` read that fed ④ leaves this screen with it, and the `Chase N meters` link goes to entry 20, where the meters it names are listed.
//   E3 the request state is LOCAL rather than URL state: this tab shares `/:tenant/reads` with the All-reads table, which owns BR-SHL-011's unprefixed `q`/`sort`/`dir`/`page`/`per`. A filtered cycles view is therefore not shareable by link. Stated, not hidden.
//   E3 the row's target is entry 20 (`/:tenant/reads/cycles/:cycleId`), whose SCREEN is a sibling lane's. `ReadCyclesTab.test.tsx` asserts the address this file builds and reports, by name, whether `App.tsx` mounts it yet — law 2's hold-expiry clause rather than a promise nobody is keeping.
//   E4 `bill_date` sorts on the BUILT page (`CYCLE_SORTS["bill_date"] = None`) because it is derived per row and is not a column. That is still a whole-list sort — `cycles_page` builds every row before `_page` slices one — and a cycle with no bill date sorts LAST on asc and FIRST on desc, which is the reverse's own behaviour and not a second rule.
//   E4 ⚠ **A CORRECTION TO THIS TRAILER'S OWN FIRST DRAFT, WHICH WAS WRONG IN THE DIRECTION THAT MATTERS.** It read *"the `/cycles` endpoint is gated `RoutesConfigAccess` (BR-MET-035b, System Admin only) … a Billing Clerk opening the tab meets the permission state"*. `RoutesConfigAccess` is **READ for any tenant role and WRITE for System Admin only** — its own docstring says why, in as many words: *"the S26/S27 ops tabs read these same endpoints (BR-MET-011), and a Billing Clerk must be able to see which route a premises is on. What they may not do is change it."* So a Billing Clerk opens this tab and sees the list, which is what entry 15's audience row (*"the person deciding whether a cycle can be billed"*) requires. The claim was written from the permission class's NAME and not from its body, which is hard-won law 1 pointing the other way: a comment claiming a RESTRICTION that does not exist is as false as one claiming a guarantee, and it would have sent the next lane to the PO for a widening nobody needs.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
