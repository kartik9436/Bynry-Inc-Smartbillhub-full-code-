// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-003 (global search) — the results popover
//           Screens: shell chrome, on every authenticated screen
// Defect:   DEF-2423 — the box that accepted text and did nothing. This is what
//           it shows now.
// Rules:    BR-SHL-005 AS AMENDED 2026-09-05 by CR-073 (fifteen groups, ≤5
//           each, per-group "View all") · A18 §2 (no results) · A18 §4 (failed
//           + retry) ·
//           B14 rule 21 (NEW UI is Tailwind and adds NO class to a stylesheet) ·
//           B14 rule 31 (no database id is ever the visible value of a field) ·
//           B14 rule 32 (one sentence per section)
// Tests:    07-frontend/src/components/GlobalSearchResults.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS FILE IS ON `src/styles/route-b-migrated.txt` AND IT IS NOT A MIGRATED
// SCREEN — IT IS NEW UI (B14 rule 21).** The same handover
// `features/rating/RateScheduleDetail.tsx` and the twelve workflow-kit
// components made: written in Tailwind utilities from its first commit, so
// G31's rule ("a class must be declared by a .css file") is false for it on day
// one rather than after a migration, and `routeBUtilities.test.ts` — which can
// reach the compiler — asks the stricter question instead.
//
// **AND THAT IS WHY IT IS A SEPARATE FILE FROM `AppShell.tsx` AT ALL.**
// `AppShell.tsx` is NOT on that ledger, and the ledger says in as many words
// why it cannot be: it builds a class name at runtime, which Tailwind's scanner
// cannot see. A utility written inside AppShell emits no CSS and renders as
// NOTHING AT ALL, with `tsc`, eslint and every `toContain(...)` assertion
// passing on it. The alternative was new class names in `AppShell.css`, and
// G31's declared-class ceiling may fall and may never rise. So the popover
// lives here, AppShell renders it, and neither rule is bent.

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { SearchEntity, SearchGroup, SearchResultRow } from "@/api/endpoints";
import { resultPath, viewAllPath } from "@/routing/searchDestinations";

/** The heading over each group. One key per entity the server may send.
 *
 * ⚠ **`Record<SearchEntity, string>` IS THE GRIP**: extend the union in
 * `api/endpoints.ts` and forget this map and `tsc` refuses to build. That
 * protection holds only because the union is where a new group lands — the
 * server-to-union direction is pinned by a BACKEND test instead
 * (`test_cr073_search_work_rating.py`), because no TypeScript check can read
 * `core/search.py`. Both halves are stated in the union's own docstring. */
const GROUP_LABEL_KEY: Record<SearchEntity, string> = {
  premises: "shell.search.group.premises",
  units: "shell.search.group.units",
  assets: "shell.search.group.assets",
  master_accounts: "shell.search.group.masterAccounts",
  accounts: "shell.search.group.accounts",
  customers: "shell.search.group.customers",
  bills: "shell.search.group.bills",
  payments: "shell.search.group.payments",
  requests: "shell.search.group.requests",
  // CR-073, 2026-09-05 — Work's four and Plans & Rates' two.
  work_orders: "shell.search.group.workOrders",
  work_order_templates: "shell.search.group.workOrderTemplates",
  parts: "shell.search.group.parts",
  workforce: "shell.search.group.workforce",
  plans: "shell.search.group.plans",
  charges: "shell.search.group.charges",
};

export interface GlobalSearchResultsProps {
  /** The query these results answer. Rendered in the no-match sentence. */
  query: string;
  /** Groups IN SERVING ORDER, exactly as the server sent them. */
  groups: readonly SearchGroup[];
  status: "idle" | "loading" | "error" | "ready";
  /** A18 §4: a failure offers Retry rather than a dead popover. */
  onRetry: () => void;
  /** Closes the popover when the reader picks a row or a "View all". */
  onNavigate: () => void;
  /** Tenant-relative → absolute. The shell's own `useTenantPath`, passed in so
   *  this component needs no router context of its own to be unit-tested. */
  toHref: (path: string) => string;
  /** Money, formatted for DISPLAY by the caller (hard rule 2: two places at
   *  display, never re-rounded on the wire). Null where the row carries none. */
  formatMoney: (amount: string, currency: string) => string;
}

function RowLine(props: {
  row: SearchResultRow;
  entity: SearchEntity;
  toHref: (path: string) => string;
  onNavigate: () => void;
  formatMoney: (amount: string, currency: string) => string;
}) {
  const { row } = props;
  // ⚠ B14 rule 31 — `row.id` reaches the HREF and NOTHING ELSE. The visible
  // value is `label`, the B2 identifier a person quotes.
  const money =
    row.amount !== null && row.currency !== null
      ? props.formatMoney(row.amount, row.currency)
      : null;
  return (
    <li>
      <Link
        to={props.toHref(resultPath(props.entity, row.id, row.label))}
        onClick={props.onNavigate}
        className="flex items-baseline gap-2 px-3 py-1.5 no-underline text-inherit hover:bg-surface focus-visible:bg-surface"
      >
        <span className="font-medium tabular-nums shrink-0">{row.label}</span>
        {row.context !== null && (
          <span className="truncate opacity-70 min-w-0">{row.context}</span>
        )}
        {money !== null && (
          <span className="ml-auto tabular-nums shrink-0 opacity-70">{money}</span>
        )}
      </Link>
    </li>
  );
}

export function GlobalSearchResults(props: GlobalSearchResultsProps) {
  const { t } = useTranslation();

  // A18 §4 — a failed search says so and offers a retry. Never a silent empty
  // popover, which is indistinguishable from "nothing matched" and teaches a
  // user their record does not exist.
  if (props.status === "error") {
    return (
      <div
        role="status"
        className="absolute top-full right-0 z-50 mt-1 w-96 max-w-[calc(100vw-2rem)] border border-divider bg-bg p-3 text-sm shadow-lg"
      >
        <p className="m-0">{t("shell.search.failed")}</p>
        <button
          type="button"
          onClick={props.onRetry}
          className="mt-2 cursor-pointer border border-neutral-400 bg-transparent px-2 py-1 text-sm"
        >
          {t("shell.search.retry")}
        </button>
      </div>
    );
  }

  if (props.status === "loading") {
    return (
      <div
        role="status"
        className="absolute top-full right-0 z-50 mt-1 w-96 max-w-[calc(100vw-2rem)] border border-divider bg-bg p-3 text-sm opacity-70 shadow-lg"
      >
        {t("shell.search.searching")}
      </div>
    );
  }

  if (props.status === "idle") return null;

  // A18 §2 — "No results for '‹query›'." and no create action offered
  // (US-SHL-003 TC-8). One sentence, which is B14 rule 32's whole budget here.
  if (props.groups.length === 0) {
    return (
      <div
        role="status"
        className="absolute top-full right-0 z-50 mt-1 w-96 max-w-[calc(100vw-2rem)] border border-divider bg-bg p-3 text-sm shadow-lg"
      >
        {t("shell.search.noResults", { query: props.query })}
      </div>
    );
  }

  // ⚠ EVERY GROUP WITH A HIT RENDERS, AND THE POPOVER SCROLLS (this lane's
  // call, 12-governance/02-decision-log.md 2026-09-03). Nine groups at five
  // rows is 45 rows in the worst case, and the tempting answer — collapse the
  // groups, or cap the total — hides rows the ≤5 cap has already limited and
  // makes a clerk click to find out whether their record is there. In practice
  // an identifier matches one or two groups, because the groups are searched by
  // identifier and identifiers do not overlap. A `max-h` with scroll costs
  // nothing in the common case and stays honest in the rare one.
  //
  // ⚠ **CR-073 TOOK IT TO FIFTEEN GROUPS AND 75 ROWS, AND THE ANSWER WAS
  // MEASURED RATHER THAN ASSUMED** (2026-09-05, decision log). The reasoning
  // above SURVIVES the increase and the measurement is what says so: on the
  // demo tenant the worst real query reaches four groups, because identifiers
  // do not overlap and a term long enough to be typed is specific. Nothing is
  // capped and nothing is reordered — the order is signed, and a cap would hide
  // rows the ≤5 limit has already limited.
  return (
    <div
      className="absolute top-full right-0 z-50 mt-1 w-[28rem] max-w-[calc(100vw-2rem)] max-h-[70vh] overflow-y-auto border border-divider bg-bg text-sm shadow-lg"
    >
      {props.groups.map((group) => (
        <section key={group.entity} className="border-b border-divider last:border-b-0 py-2">
          {/* ⚠ A GROUP THIS BUNDLE HAS NO HEADING FOR STILL RENDERS ITS ROWS.
              The nine groups grew from four in one ruling and a tenth will
              arrive the same way, so a browser holding an older bundle is the
              normal state of a deploy — not an edge case. The fallback is the
              plain-words one the 2026-09-01 ruling requires: a label the
              product cannot fill says so in WORDS and never prints the machine
              value it happens to hold (B14 rule 31 / DEF-2417's class). */}
          <h2 className="m-0 px-3 pb-1 text-xs font-semibold uppercase tracking-wide opacity-60">
            {t(GROUP_LABEL_KEY[group.entity] ?? "shell.search.group.other")}
          </h2>
          <ul className="m-0 list-none p-0">
            {group.rows.map((row) => (
              <RowLine
                key={row.id}
                row={row}
                entity={group.entity}
                toHref={props.toHref}
                onNavigate={props.onNavigate}
                formatMoney={props.formatMoney}
              />
            ))}
          </ul>
          {/* BR-SHL-005's per-group "View all" — the module's own list with the
              query applied (BR-SHL-011's `q`). It is also the only thing that
              can answer "how many are there": nothing in this feature counts
              past the cap, and a list that counts properly is one click away.

              OMITTED, never rendered dead, for a group this bundle has no route
              for: a link to nowhere is the dead UI hard-won law 2 is about, and
              the rows above still open. */}
          {viewAllPath(group.entity, props.query) !== null && (
            <Link
              to={props.toHref(viewAllPath(group.entity, props.query) as string)}
              onClick={props.onNavigate}
              className="mt-1 inline-block px-3 text-xs underline"
            >
              {t("shell.search.viewAll", {
                group: t(GROUP_LABEL_KEY[group.entity] ?? "shell.search.group.other"),
              })}
            </Link>
          )}
        </section>
      ))}
    </div>
  );
}

export default GlobalSearchResults;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-003 (EP-SHL-01) + DEF-2423 + the PO ruling of 2026-09-03
// generated: 2026-09-03 by story-coder (universal-search lane)
// checklist: A✔ B✔ C✔ D✔ E✔(AppShell renders it; ShellWithSession feeds it) F✔ G✔ H=deferred(PO)
// exceptions: E3 the popover shows no total and no per-group count — nothing in
//         this feature counts matches beyond the ≤5 cap, and a "5 of 214" that
//         was only ever an estimate is worse than no number; "View all" opens
//         the list that counts properly · E3 `payments` and `customers` rows
//         open their module LIST filtered to the row's identifier, because
//         neither module has a detail route; REPORTED in searchDestinations.ts
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
