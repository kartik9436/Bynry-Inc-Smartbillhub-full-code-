// ── Trace ──────────────────────────────────────────────
// Story:    CR-142-BRC07 Phase 4 · `P4.15` — *"a landlord sees their own
//           account only"*.  Screen: CWP-078, `/{tenant}/portal/property`
// Change:   `CR-142-BRC07` `P4.14`/`P4.15` brief p016 (the task row) and
//           p070–p071 (report `R24c` *Statement · by premises*), read as
//           IMAGES per B14 rule 42.
// Rules:    **R24c LAW (ruled)** — *"In the customer portal a landlord sees
//           **their own master account only**: the $69.60, never Unit 3's
//           $100.00 (`P4.15`)"* · BR-CWP-016 (PO 2026-09-04, *"(a) no"*) ·
//           BR-CWP-015 (separate rows, totalled for information, NEVER
//           merged) · BR-CWP-047 (re-read, never cached) · BR-CWP-093
//           (nothing empty ever appears) · CLAUDE.md hard rule 2 (4 dp
//           stored, DISPLAY 2) · hard rule 8 (the address is WALKED) ·
//           B14 rule 20 (ONE table type) · rule 21 (Tailwind only; `portal/`
//           is a DIRECTORY entry on `route-b-migrated.txt`, so this file is
//           covered the day it is born) · rule 31 (no database id on screen) ·
//           rule 32 (one sentence per section) · rule 33 (RATIONALE is ZERO
//           WORDS on screen) · rule 35 (the catalogue writes the words) ·
//           rule 43 (a piece of UI is a COMPONENT) · rule 44 (our kit wins)
// Tests:    src/portal/premises/PremisesStatement.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getPremisesStatement` ·
//           src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ListPager } from "@/components/ListPager";
import { PageHeader } from "@/components/PageHeader";
import type { PageSize } from "@/components/tableTypes";

import { Card, usePortalPath } from "../components/primitives";
import { PortalScreen } from "../components/states";
import { PortalListTable } from "../components/listTable";
import { usePortalListWindow } from "../components/listWindow";
import { formatMoney } from "../signin/Enrol";
import {
  getPremisesStatement,
  type PremisesStatement,
  type PremisesStatementRow,
} from "../api/portalClient";

/**
 * `CWP-078` — one property, and ONLY the accounts this login holds at it.
 *
 * ⚠ **THE SCOPING IS THE SERVER'S AND THIS SCREEN CANNOT WIDEN IT.**
 * `apps/portal/premises_statement.py` never asks *what is at this premises*;
 * it asks *which of MY accounts are here*, starting from the session's own
 * set. So there is no state on this component that could show a neighbour's
 * balance, and a filter that could would be the bug — the same posture
 * `MyAccounts.tsx` records for `BR-CWP-016`.
 *
 * ⚠ **THE COMMON-AREA TILE IS DRAWN ONLY WHEN IT IS YOURS** (`BR-CWP-093`).
 * `common_areas` is `null` for a reader who holds no master account here, and
 * `null` is an ABSENT tile rather than a `$0.00` one: a zero would be a claim
 * about what this building's common areas cost, which is the owner's business
 * and is read by a tenant.
 *
 * ⚠ **`UNITS BILLED` IS NOT DRAWN.** p070's third KPI counts the BUILDING's
 * billed units and is the one figure on that drawing that is a fact about
 * other customers. The server does not send it; this comment is the record,
 * and the screen says nothing at all (B14 rule 33 — rationale is zero words).
 *
 * ⚠ **THE MASTER ROW IS MARKED AND NEVER MERGED** (`R24c`, verbatim: *"The
 * master account is a row like any other, marked, never merged"*). It sorts
 * last, under the units it serves, because a common-area row read first
 * invites the reading that it is the building's total.
 */
export function PremisesStatementView(props: {
  /** The account the shell's switcher is on. ⚠ **NOT A PREMISES ID, AND NOT IN
   *  THE ADDRESS BAR** (B14 rule 31, as `portalRoutes.tsx` reads it): the
   *  server walks this account to its property (hard rule 8), and a stranger
   *  has no id to supply because this one came out of their own session. */
  accountId: string;
  from: string;
  to: string;
}) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const list = usePortalListWindow({ sort: { key: "unit", dir: "asc" } });
  const [data, setData] = useState<PremisesStatement | null>(null);
  const [busy, setBusy] = useState(true);
  const request = list.request;

  // ⚠ **RE-READ ON EVERY MOUNT AND EVERY WINDOW CHANGE** (`BR-CWP-047`). Not
  // behind a query cache, for `MyAccountsPage`'s stated reason: these are live
  // balances, and a statement showing Tuesday's figures on Thursday is what
  // the rule exists for.
  useEffect(() => {
    let live = true;
    setBusy(true);
    void getPremisesStatement(props.accountId, { from: props.from, to: props.to }, request)
      .then((answer) => {
        if (live) setData(answer);
      })
      .finally(() => {
        if (live) setBusy(false);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, props.from, props.to, request]);

  // ⚠ **THE ONE PAGE HEAD, BUILT ONCE ABOVE THE BRANCHES (`DEF-CWP-9131`).**
  // Until 2026-10-02 this screen opened with a Card and an eleven-pixel
  // `SectionTitle` — no `<h1>`, no way back — which is `DEF-CWP-4000`'s shape
  // exactly, and `pageHeadCensus.test.ts` named it from the day it landed. The
  // title is the property's ADDRESS (hard rule 8: walked, never a database id —
  // B14 rule 31), and the way back is the account the switcher is on, which is
  // where the door to this screen is.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.accounts")}
      title={data?.address ?? t("portal.property.unnamed")}
      backTo={{
        to: path("/account"),
        label: t("portal.yourAccount.title"),
        testId: "property-back",
      }}
    />
  );

  if (data === null)
    return (
      <PortalScreen screen="CWP-078" head={head}>
        {null}
      </PortalScreen>
    );

  return (
    // A LITERAL `data-screen` on the success branch, as `usage/Usage.tsx`
    // records: three source scanners (the page-head census, G100, G103) find a
    // portal screen by this exact string and none of them reads a `screen=` prop.
    <div data-screen="CWP-078">
      {head}
      <Card testId="premises-statement">
        <StatementTiles data={data} />

        {/* The phone. `max-md:flex`, never `md:hidden` — this theme is
            DESKTOP-FIRST and `G107` refuses the min-width form by name.
            ⚠ G107 has been RED on four portal files since 2026-09-08
            (`a2aa63cfb`, `e83971d55`); this lane did not cause that and did
            not join it. ONE SOURCE FOR BOTH HALVES: each renders `data.rows`,
            so a figure cannot be true at 1280 and absent at 390. */}
        <div className="mt-3 hidden flex-col gap-3 max-md:flex" data-statement-cards="">
          {data.rows.map((row) => (
            <StatementCard key={row.id} row={row} />
          ))}
          <ListPager
            total={data.count}
            page={data.page}
            per={data.per as PageSize}
            onPage={list.setPage}
            onPer={list.setPer}
          />
        </div>

        <div className="mt-3 max-md:hidden">
          <PortalListTable<PremisesStatementRow>
            screen="CWP-078"
            caption={t("portal.property.caption")}
            rows={data.rows}
            rowKey={(row) => row.id}
            empty={
              <p className="mt-2 text-body text-neutral-600" data-statement-empty="">
                {t("portal.property.caption")}
              </p>
            }
            server={list.window({
              total: data.count,
              page: data.page,
              per: data.per as PageSize,
              populated: data.account_count > 0,
              busy,
            })}
            columns={[
              {
                key: "unit",
                label: t("portal.property.colUnit"),
                sortable: true,
                sortValue: (row) => row.unit_label,
                cell: (row) => <UnitCell row={row} />,
              },
              {
                key: "charges",
                label: t("portal.property.colCharges"),
                align: "right",
                cell: (row) => <Money value={row.charges} mark={`charges-${row.id}`} />,
              },
              {
                key: "credits",
                label: t("portal.property.colCredits"),
                align: "right",
                cell: (row) => <Money value={row.credits} negative mark={`credits-${row.id}`} />,
              },
              {
                key: "balance",
                label: t("portal.property.colClosing"),
                align: "right",
                sortable: true,
                sortValue: (row) => Number(row.closing),
                cell: (row) => <Money value={row.closing} mark={`closing-${row.id}`} />,
              },
            ]}
          />
        </div>

        {/* ⚠ **A TOTAL OF WHAT IS YOURS, AND THERE IS NO CONTROL NEAR IT**
            (`BR-CWP-015`): each account is billed on its own, and a single
            button beside this figure would promise a merged payment this
            product does not make. It is the WHOLE SET's, never the page's. */}
        <p className="mt-3 text-body font-semibold" data-statement-total="">
          {t("portal.property.total")}{" "}
          <span className="tabular-nums">{formatMoney(data.totals.closing, null)}</span>
        </p>
      </Card>
    </div>
  );
}

/**
 * The three figures at the head — and the fourth only when it is yours.
 *
 * ⚠ **A COMPONENT AND NOT 40 LINES INLINE** (B14 rule 43, ratified 2026-09-20
 * after *"use it"* turned out to mean 120 lines importable by nothing). Both
 * widths read these figures and only one of them can be on screen.
 */
function StatementTiles(props: { data: PremisesStatement }) {
  const { t } = useTranslation();
  const { data } = props;
  return (
    <dl className="mt-3 flex flex-wrap gap-6" data-statement-tiles="">
      <Tile label={t("portal.property.tileAccounts")} value={String(data.account_count)} />
      <Tile
        label={t("portal.property.tileCharges")}
        value={formatMoney(data.totals.charges, null)}
      />
      {/* ABSENT, never `$0.00` — see the view's docstring and `BR-CWP-093`. */}
      {data.common_areas === null ? null : (
        <Tile
          label={t("portal.property.tileCommon")}
          value={formatMoney(data.common_areas, null)}
          mark="tile-common"
        />
      )}
      <Tile
        label={t("portal.property.tileClosing")}
        value={formatMoney(data.totals.closing, null)}
      />
    </dl>
  );
}

function Tile(props: { label: string; value: string; mark?: string }) {
  return (
    <div className="flex flex-col" data-tile={props.mark ?? ""}>
      <dt className="text-table-header font-bold uppercase tracking-table-header text-neutral-600">
        {props.label}
      </dt>
      <dd className="text-metric-sm font-bold tabular-nums">{props.value}</dd>
    </div>
  );
}

/**
 * The unit's LABEL, and underneath it what kind of account this row is.
 *
 * ⚠ **A UNIT REFINES A PREMISES BY LABEL** (hard rule 8) — `Unit 3`, never a
 * second address. A master account has no unit at all, so the screen words
 * that absence itself rather than printing an empty cell.
 */
function UnitCell(props: { row: PremisesStatementRow }) {
  const { t } = useTranslation();
  const { row } = props;
  return (
    <span className="flex flex-col">
      <span className="font-semibold">
        {row.is_master ? t("portal.property.common") : (row.unit_label ?? "—")}
      </span>
      <span className="text-table-header text-neutral-600">
        {row.is_master ? t("portal.property.kindMaster") : t("portal.property.kindRegular")}
      </span>
    </span>
  );
}

function Money(props: { value: string; negative?: boolean; mark?: string }) {
  // Hard rule 2 — stored at 4 decimals, DISPLAYED at 2. `formatMoney` is the
  // one place that rounds, which is why this component does no arithmetic.
  const shown = formatMoney(props.value, null);
  return (
    <span className="tabular-nums" data-money={props.mark ?? ""}>
      {props.negative && Number(props.value) !== 0 ? `−${shown}` : shown}
    </span>
  );
}

/**
 * One account of yours at this property, on a phone.
 *
 * ⚠ **THE SAME STACK `MyAccounts.tsx` USES, AND FOR ITS MEASURED REASON**
 * (`DEF-CWP-4905`): a four-money-column table inside a 350px column puts the
 * closing balance past the right-hand edge behind a sideways scroll a customer
 * has no reason to look for. Every figure is LABELLED, so a card with no
 * column heads still says what each number is.
 */
function StatementCard(props: { row: PremisesStatementRow }) {
  const { t } = useTranslation();
  const { row } = props;
  return (
    <div className="flex flex-col gap-2 border border-neutral-200 p-3" data-statement-card={row.id}>
      <UnitCell row={row} />
      <div className="flex flex-wrap items-end justify-between gap-2">
        <Figure label={t("portal.property.colCharges")} value={row.charges} />
        <Figure label={t("portal.property.colCredits")} value={row.credits} negative />
        <Figure label={t("portal.property.colClosing")} value={row.closing} strong />
      </div>
    </div>
  );
}

function Figure(props: { label: string; value: string; negative?: boolean; strong?: boolean }) {
  return (
    <span className="flex flex-col">
      <span className="text-table-header font-bold uppercase tracking-table-header text-neutral-600">
        {props.label}
      </span>
      <span className={props.strong ? "text-metric-sm font-bold tabular-nums" : "tabular-nums"}>
        <Money value={props.value} negative={props.negative} />
      </span>
    </span>
  );
}
