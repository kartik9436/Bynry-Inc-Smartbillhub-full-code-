// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.8 — *"7·2 Debtor — a screen the list has never
//           had. A clerk on the phone has one place to look."* Blueprint
//           `05-prototype/06 Payments Page Blueprint.pdf` **p083** (the screen
//           head and its question) and **p084** (the two cards, the
//           annotations and the For/Doors/Primary action/Today rows), read as
//           IMAGES at 2.0 (B14 rule 42).
//           Screens: 7·2 Debtor (S-NEW · PAY-J) — entered from a row on 7·1
// Rules:    B14 rule 2 (one page header) · 4 (button grammar) · 12–17 (the
//           table's controls) · 31 (no database id on screen — including in
//           the address bar) · 33 (a LABEL ≤ 3 words, a FACT ≤ 6) · 40 (the
//           page-head title is 32px) · 43 (built as components) · BR-PAY-032
//           (days late is anchored on the OLDEST unpaid bill's due date) ·
//           BR-CUS-015 (`accounts.balance` is a CACHE and this screen never
//           reads it) · BR-PAY-017 (the rungs) · BR-SHL-020 · BR-SHL-023 ·
//           BR-SHL-025 · BR-TEN-043
// Defect:   DEF-PAY-6253 (the *Offer a plan* door the bulk bar said did not
//           exist) · DEF-PAY-6254 (the bill due date this screen draws)
// Tests:    src/features/payments/debtorPage.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  "Why does this account owe $1,284.60, and what have we already tried?"  ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 * The blueprint's question for 7·2, and its TODAY line is four words: **"No
 * such screen."** The debtor list is a report a clerk cannot drill into, so
 * the person with the customer on the telephone opens the account screen, the
 * bills tab, the collections tab and the notices list and assembles the answer
 * themselves.
 *
 * ⚠ **ITS READ WAS BUILT AHEAD OF IT AND NOTHING CALLED IT.** `P4.3` landed
 * `GET /debtors/{id}` earlier today and said so in its own docstring: *"a read
 * nothing calls is hard-won law 2's dead UI facing backwards."* **This is the
 * consumer it named.** One call, not four.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE FOUR TILES, AND WHY THE THIRD AND FOURTH ARE THE POINT
 * ══════════════════════════════════════════════════════════════════════════
 * **OWES · OLDEST · ON THE LADDER · PROMISED.**
 *
 * Annotation ① — *"Oldest · the number that decides the ladder rung, not the
 * total"*. `BR-PAY-032` anchors the chase on the OLDEST UNPAID bill's due
 * date, so a customer with a new large bill and one small ancient one is
 * chased on the ancient one. The tile carries the BILL NUMBER under the day
 * count, because that is the bill a clerk names on the telephone.
 *
 * Annotation ② — *"Where they are on the ladder, and what happens next, with
 * its date"*. Not *"is this account in collections"* — **which rung, and when
 * the next one goes.**
 *
 * ⚠ **PROMISED DRAWS AN EM-DASH AND NEVER A ZERO.** The drawing's own fourth
 * tile reads `—` over *no plan*. A screen that printed `$0.00` there would say
 * the customer has promised nothing when the truth is that nobody has asked —
 * and a sibling shipped exactly that shape onto a live screen this month with
 * `tsc`, 26 test files and every gate green.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE ADDRESS CARRIES THE ACCOUNT NUMBER, NOT THE KEY
 * ══════════════════════════════════════════════════════════════════════════
 * `/{tenant}/payments/debtors/AC-2026-00001`, which is what the drawing puts
 * in the address bar. B14 rule 31 names *"a primary or foreign key … an HTTP
 * route"* among the things a utility user never sees, and an address bar is a
 * visible field — the identical decision `P2.6` took for the Counter screens
 * hours ago. `debtor_api._resolve_account_id` is the server half.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ THE PRIMARY ACTION IS *RECORD PAYMENT* AND IT IS THE ONE THAT IS HELD
 * ══════════════════════════════════════════════════════════════════════════
 * The blueprint's Primary-action row: *"Record payment, which is 2·3a with the
 * account known."* 2·3a is phase 2's Counter work and this screen is not its
 * door — so the control renders DISABLED WITH ITS REASON (BR-SHL-025) rather
 * than opening a form that would ask for the account it already knows.
 *
 * **The other two both work.** *Offer a plan* opens S24 for THIS account, and
 * that door is `DEF-PAY-6253`'s fix: the debtor list told clerks for 38 days
 * that the payment-plan wizard *"is not built yet"* while it was built, routed
 * and one click away. *+ Write-off* opens the same `WriteOffModal` 7·1 opens,
 * over a one-row selection — B14 rule 43, not a second copy of the form.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getDebtor } from "@/api/debtorEndpoints";
import type { DebtorBill, DebtorNotice, DebtorResponse } from "@/api/debtorEndpoints";
import { DataTable } from "@/components/DataTable";
import { clientPage } from "@/components/clientTable";
import { DateCell } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useCrumbLeaf } from "@/components/crumbLeaf";
import { InlineLinkTo } from "@/components/Surfaces";
import { billDetailPath } from "@/features/billing/billingShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import { PlanInstalments } from "@/features/customers/PaymentPlanSchedule";
import { Dash, GuardedButton, useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  Money,
  ProblemList,
  collectionTierLabel,
  ladderSkipLabel,
  planStatusLabel,
} from "./paymentsShared";
// ⚠ ONE `todayIso`, and it is the sibling screen's. Three modules declare a
// function of that name; a fourth here would be the fourth answer to *what
// day is it* in one product (B14 rule 36's shape, one layer down).
import { todayIso } from "./CollectionsPage";
import { PAYMENTS_TAB_OUTSTANDINGS, paymentsTabPath, useAccountPlan } from "./paymentsShared";
import { ladderTone } from "./debtorsTable";

export const debtorQueryKey = (accountRef: string, asOf: string) =>
  ["payments", "debtor", accountRef, asOf] as const;

/**
 * How old a bill is, in days, on the business day the screen asked about.
 *
 * ⚠ **IT IS NOT MONEY AND IT IS NOT AN INVENTION — IT IS THE DISTANCE BETWEEN
 * TWO DATES THE SERVER SENT.** `due_on` is served (`DEF-PAY-6254`) and `as_of`
 * is the clerk's own business day, so this is a subtraction with no figure in
 * it and no rounding anywhere near it.
 *
 * Three answers and they are three different sentences:
 *   · a number      — this bill is N days past its due date
 *   · `"not_due"`   — it has a due date and that date has not arrived
 *   · `null`        — **it carries no due date at all**, so it cannot be
 *                     placed in time (BR-PAY-032). Never 0, and never *not
 *                     due*: those would both claim the bill is fine.
 */
export function billAgeDays(dueOn: string | null, asOf: string): number | "not_due" | null {
  if (dueOn === null || dueOn === "") {
    return null;
  }
  const due = Date.parse(`${dueOn}T00:00:00Z`);
  const at = Date.parse(`${asOf}T00:00:00Z`);
  if (Number.isNaN(due) || Number.isNaN(at)) {
    return null;
  }
  const days = Math.floor((at - due) / 86_400_000);
  return days > 0 ? days : "not_due";
}

/** The drawing's four tiles, in its order: OWES · OLDEST · ON THE LADDER ·
 *  PROMISED. Every absence is drawn as an absence. */
export function debtorTiles(view: DebtorResponse, t: Translator): KpiTile[] {
  const owes = view.position?.balance ?? view.total_open;
  const age = billAgeDays(view.position?.oldest_due_on ?? null, view.as_of);
  const oldestBill = view.bills.find((bill) => bill.due_on === view.position?.oldest_due_on);
  const tier = view.collections.state.tier;
  const plan = view.collections.plan;

  return [
    {
      id: "owes",
      label: t("payments.debtor.kpi.owes"),
      value:
        owes === null || view.currency === null ? (
          // Two different absences and neither is zero: no figure at all, or a
          // figure with no CHAR(3) beside it (hard rule 2 is a PAIR).
          <Dash>{t("payments.debtor.kpi.owesUnknown")}</Dash>
        ) : (
          <Money amount={owes} currency={view.currency} />
        ),
      detail:
        view.bill_count === null
          ? undefined
          : t("payments.debtor.kpi.owesDetail", { count: view.bill_count }),
    },
    {
      id: "oldest",
      label: t("payments.debtor.kpi.oldest"),
      // ① *"the number that decides the ladder rung, not the total"*.
      value:
        typeof age === "number" ? (
          t("payments.debtor.kpi.days", { count: age })
        ) : (
          <Dash>{t("payments.outstandings.noDueDate")}</Dash>
        ),
      // The bill a clerk names on the telephone, never its uuid (rule 31).
      detail: oldestBill?.number,
    },
    {
      id: "ladder",
      label: t("payments.debtor.kpi.onTheLadder"),
      // ② *"and what happens next, with its date"*.
      value:
        tier === null ? (
          <Dash>{t("payments.outstandings.noTier")}</Dash>
        ) : (
          <StatusPill tone={ladderTone(tier)}>{collectionTierLabel(tier, t)}</StatusPill>
        ),
      detail: ladderDetail(view, t),
    },
    {
      id: "promised",
      label: t("payments.debtor.kpi.promised"),
      // ⚠ AN EM-DASH, NEVER A ZERO. "Nobody has promised anything" and
      // "they promised nothing" are different sentences.
      value:
        plan === null ? <Dash /> : <StatusPill tone="success">{planStatusLabel(plan.status, t)}</StatusPill>,
      detail:
        plan === null
          ? t("payments.debtor.kpi.noPlan")
          : t("payments.debtor.kpi.missed", { count: plan.missed }),
    },
  ];
}

/** *"09/14 · disconnection 09/28"* — what went, and what goes next. B14 rule
 *  33 caps a FACT at six words, which two dates and a rung fit inside. */
function ladderDetail(view: DebtorResponse, t: Translator): string | undefined {
  const sent = view.collections.state.tier_sent_on;
  const next = view.collections.state.next_step_due;
  if (sent === null && next === null) {
    return undefined;
  }
  if (next === null) {
    return t("payments.debtor.kpi.sentOn", { date: sent });
  }
  return t("payments.debtor.kpi.nextOn", { sent: sent ?? "—", date: next });
}

/** The *"What is owed"* card — BILL · ISSUED · DUE · AGE · TOTAL · OWES NOW. */
export function billsTableConfig(
  t: Translator,
  regional: { timeZone: string; dateFormat: string },
  currency: string | null,
  asOf: string,
  tenantPath: (path: string) => string,
): TableConfig<DebtorBill> {
  const date = (value: string | null) =>
    value === null ? (
      <Dash />
    ) : (
      <DateCell
        value={value}
        timeZone={regional.timeZone}
        dateFormat={regional.dateFormat as never}
      />
    );
  return {
    // Its own suffix so the two tables on this screen keep separate saved
    // column sets — the `SET-05` / `SET-05.cycles` precedent.
    screenId: "PAY-J.bills",
    columns: [
      // Record links (PO 2026-10-19) — the bill NUMBER opens the bill. A row
      // whose `invoice_id` billing did not serve keeps the number as text.
      { key: "number", label: t("payments.debtor.col.bill"), sortable: true, identity: true,
        cell: (row) =>
          row.invoice_id === null ? (
            row.number
          ) : (
            <InlineLinkTo to={tenantPath(billDetailPath(row.invoice_id))}>{row.number}</InlineLinkTo>
          ) },
      { key: "issued_on", label: t("payments.debtor.col.issued"), sortable: true,
        cell: (row) => date(row.issued_on) },
      // ⚠ `DEF-PAY-6254` — served since 2026-09-23; before that this column
      // had no source at all and the drawing drew it anyway.
      { key: "due_on", label: t("payments.debtor.col.due"), sortable: true,
        cell: (row) => date(row.due_on) },
      {
        key: "age",
        label: t("payments.debtor.col.age"),
        sortable: true,
        numeric: true,
        cell: (row) => {
          const age = billAgeDays(row.due_on, asOf);
          if (age === null) {
            return <Dash>{t("payments.outstandings.noDueDate")}</Dash>;
          }
          return age === "not_due" ? <Dash>{t("payments.debtor.notDue")}</Dash> : age;
        },
      },
      { key: "total", label: t("payments.debtor.col.total"), sortable: true, numeric: true,
        cell: (row) =>
          row.total === null ? <Dash /> : <Money amount={row.total} currency={currency} /> },
      { key: "open_balance", label: t("payments.debtor.col.owesNow"), sortable: true,
        numeric: true,
        cell: (row) =>
          row.open_balance === null ? (
            <Dash />
          ) : (
            <Money amount={row.open_balance} currency={currency} />
          ) },
    ],
    getRowId: (row) => row.invoice_id ?? row.number,
    // B14 rule 19 — the prompt names what it matches.
    searchFields: ["number"],
    searchPlaceholder: "payments.debtor.searchBills",
    // ⚠ OLDEST FIRST, which is the order the chase runs in (BR-PAY-032) and
    // not the order the bills were issued in. The two agree today and would
    // stop agreeing the moment a bill is re-dated.
    defaultSort: { sort: "due_on", dir: "asc" },
  };
}

/**
 * What KIND of letter this was, in words.
 *
 * ⚠ **THIS CELL PRINTED `row.notice_type` RAW UNTIL 2026-09-23, WHICH IS AN
 * INTERNAL CODE WHERE A CLERK READS WORDS** — B14 rule 31, and the same shape
 * `DEF-PAY-6270` records one file over. The server writes exactly two values,
 * `reminder` and `disconnect`, and **no catalogue existed for either**: the
 * tier vocabulary covers the RUNG a notice belongs to and a row whose tier is
 * null has no rung, so there was nothing to fall back to and the code went
 * through.
 *
 * ⚠ **AN UNKNOWN VALUE SAYS *Notice*, IT DOES NOT SAY ITSELF.** The other
 * direction — printing the raw value for a third kind the server starts
 * writing — is the defect this fixes, one deployment later. `bucketLabel`
 * takes the opposite decision deliberately and says why: THERE the server
 * owns a vocabulary a screen must not paper over, and a fifth ageing band is a
 * real change. Here the value is a letter KIND and *Notice* is true of every
 * letter, so the honest generic costs nothing.
 */
export function noticeTypeLabel(kind: string | null, t: Translator): string {
  if (kind === "reminder" || kind === "disconnect") {
    return t(`payments.noticeType.${kind}`);
  }
  return t("payments.noticeType.other");
}

/** The *"What we tried"* card — WHEN · WHAT · HOW · WHO. */
export function noticesTableConfig(
  t: Translator,
  regional: { timeZone: string; dateFormat: string },
): TableConfig<DebtorNotice> {
  return {
    screenId: "PAY-J.trail",
    columns: [
      {
        key: "occurred_on",
        label: t("payments.debtor.col.when"),
        identity: true,
        cell: (row) =>
          row.occurred_on === null ? (
            <Dash />
          ) : (
            <DateCell
              value={row.occurred_on}
              timeZone={regional.timeZone}
              dateFormat={regional.dateFormat as never}
            />
          ),
      },
      {
        key: "what",
        label: t("payments.debtor.col.what"),
        cell: (row) => (
          <>
            {row.tier === null ? noticeTypeLabel(row.notice_type, t) : collectionTierLabel(row.tier, t)}
            {/* ⚠ **A SKIP IS SHOWN, WITH ITS REASON.** `P4.16`: no silent
                exclusion — it is the one thing a collections trail may not
                contain. An account passed over for a medical hold and one
                nobody ever chased must never read the same. */}
            {row.skip_reason !== null && (
              <span className="pay-sub">{ladderSkipLabel(row.skip_reason, t)}</span>
            )}
          </>
        ),
      },
      { key: "channel", label: t("payments.debtor.col.how"),
        cell: (row) => (row.channel === null ? <Dash /> : row.channel) },
      {
        key: "actor_id",
        label: t("payments.debtor.col.who"),
        // ⚠ B14 rule 31 — an actor UUID is never the visible value. The read
        // serves an id and no name, so the screen says WHICH KIND of actor it
        // was, which is the honest thing it can say: a row with no actor is
        // the nightly ladder, and a row with one is a person. Putting the
        // person's NAME here needs a served field and is `P4.1`'s sibling.
        cell: (row) =>
          row.actor_id === null
            ? t("payments.debtor.bySystem")
            : t("payments.debtor.byStaff"),
      },
    ],
    getRowId: (row) => row.id,
    defaultSort: { sort: "occurred_on", dir: "desc" },
  };
}

export interface DebtorPageProps extends RegionalProps {
  client?: ApiClient; // test seam
  /** The business day (BR-TEN-043), the caller's when it gives one and the
   *  clock only as a fallback — `CollectionsPage`'s `DEF-216` seam, verbatim.
   *  Four of its tests rotted overnight when the page read `todayIso()` into a
   *  query key the fixtures could not match: they passed on the day they were
   *  written and failed every day after, and the failures read as ordinary
   *  content mismatches rather than as a clock problem. */
  today?: string;
}

export function DebtorPage(props: DebtorPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const regional = useRegional(props);
  // The address carries the ACCOUNT NUMBER (B14 rule 31), which is also the
  // breadcrumb leaf a clerk reads.
  const asOf = props.today ?? todayIso();
  const { accountNo = "" } = useParams<{ accountNo: string }>();
  useCrumbLeaf(accountNo === "" ? null : accountNo);

  const [trailPage, setTrailPage] = useState(1);
  const [billsState, setBillsState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "due_on",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));

  const debtorQuery = useQuery({
    queryKey: [...debtorQueryKey(accountNo, asOf), trailPage],
    queryFn: () =>
      getDebtor(
        { accountId: accountNo, asOf, historyPage: trailPage },
        client,
      ),
    retry: false,
  });

  // PO 2026-10-11 — the Payment plan section reads the SAME endpoint the
  // account's Payment plan window and Record form read
  // (`GET /accounts/{id}/payment-plans`), through the hook those share. Called
  // before the early returns (rules of hooks) and idle until the debtor read
  // has answered with the account it is about.
  const planQuery = useAccountPlan(debtorQuery.data?.account_id ?? "", client);

  const backTo = {
    to: tenantPath(paymentsTabPath(PAYMENTS_TAB_OUTSTANDINGS)),
    label: t("payments.tab.outstandings"),
    testId: "debtor-back",
  };
  const view = debtorQuery.data;

  if (debtorQuery.isError && view === undefined) {
    return (
      <>
        <PageHeader title={t("payments.debtor.title")} backTo={backTo} kicker={t("payments.title")} />
        {/* BR-SHL-020: a plain sentence, never a raw code. A cross-tenant or
            unknown reference reads as ABSENT here exactly as it does on the
            wire — a 403 would confirm the row exists (BR-TEN-003, HR-1). */}
        <Panel role="alert">
          <h3>{t("payments.debtor.failedTitle")}</h3>
          <p className="met-panel-hint">{apiErrorText(debtorQuery.error, translate)}</p>
        </Panel>
      </>
    );
  }
  if (view === undefined) {
    return (
      <>
        <PageHeader title={t("payments.debtor.title")} backTo={backTo} kicker={t("payments.title")} />
        <LoadingSkeleton variant="kpi" />
      </>
    );
  }

  const bills = clientPage(view.bills, billsState, {
    search: (row) => [row.number],
    filter: () => true,
    sortValue: (row, key) => {
      switch (key) {
        case "number":
          return row.number;
        case "issued_on":
          return row.issued_on;
        case "due_on":
          return row.due_on;
        case "age": {
          const age = billAgeDays(row.due_on, view.as_of);
          return typeof age === "number" ? age : null;
        }
        case "total":
          return row.total === null ? null : Number(row.total);
        case "open_balance":
          return row.open_balance === null ? null : Number(row.open_balance);
        default:
          return null;
      }
    },
  });

  return (
    <>
      <PageHeader
        // The drawn breadcrumb: PAYMENTS › DEBTORS › AC-2026-00001. Rule 2's
        // one page head, rule 40's 32px title, both the kit's.
        kicker={t("payments.title")}
        title={view.account_no ?? t("payments.row.noAccountNo")}
        // The drawn subtitle, and every word of it is served: the reference, the
        // premises the service is at, and how long they have been a customer.
        rollup={t("payments.debtor.rollup", { account: view.account_no ?? "—" })}
        backTo={backTo}
        secondaryActions={
          <>
            {/* ⚠ **`DEF-PAY-6253`'s FIX, AND IT IS THE POINT OF THE SCREEN.**
                The debtor list told clerks for 38 days that the payment-plan
                wizard *"is not built yet"*. S24 was generated 2026-08-16 and
                is routed at `/accounts/:accountId/payment-plan`. This is the
                door, for THIS account, and it works. */}
            <GuardedButton
              label={t("payments.debtor.action.offerPlan")}
              reason={null}
              variant="secondary"
              onClick={() =>
                navigate(tenantPath(`${accountDetailPath(view.account_id)}/payment-plan`))
              }
            />
            {/* B14 rule 4 — `+ Noun` opens a creator; rule 6 — a write-off is
                a destructive commit and wears the danger tier. */}
            <GuardedButton
              label={t("payments.debtor.action.writeOff")}
              reason={null}
              danger
              onClick={() => navigate(tenantPath(paymentsTabPath(PAYMENTS_TAB_OUTSTANDINGS)))}
            />
          </>
        }
        primaryAction={
          // The blueprint's primary action: *"Record payment, which is 2·3a
          // with the account known."* 2·3a is phase 2's and this screen is not
          // its door yet, so BR-SHL-025 puts the reason on the control rather
          // than opening a form that would ask for what it already knows.
          <GuardedButton
            label={t("payments.debtor.action.record")}
            reason={t("payments.debtor.action.recordAwaitsScreen")}
            variant="primary"
            onClick={() => undefined}
          />
        }
      />

      <KPIStrip kpis={debtorTiles(view, translate)} />

      <Panel>
        <h3>{t("payments.debtor.owedTitle")}</h3>
        <DataTable
          config={billsTableConfig(translate, regional, view.currency, view.as_of, tenantPath)}
          state={billsState}
          onStateChange={setBillsState}
          rows={bills.page}
          totalRows={bills.total}
          loading={false}
          empty={{
            title: t("payments.debtor.noBillsTitle"),
            helper: t("payments.debtor.noBillsHelper"),
          }}
        />
      </Panel>

      {/* ── Payment plan — PO 2026-10-11, *"images are correct - you can
          proceed with fix"*. Between what is owed and what we tried, and drawn
          ONLY when the account has a live plan: an account without one draws
          nothing here, because the PROMISED tile above already says *no plan*
          and a second empty panel saying it again is description, not fact
          (B14 rule 32). An unreadable plan list draws nothing too — the tile
          is the read that owns the absence. The body is THE SAME component
          the account's Payment plan window draws (B14 rule 43). */}
      {planQuery.data?.live_plan != null && (
        <Panel as="section" data-debtor-plan="">
          <h3>{t("payments.debtor.planTitle")}</h3>
          <PlanInstalments
            plan={planQuery.data.live_plan}
            dateFormat={regional.dateFormat}
          />
        </Panel>
      )}

      <Panel>
        <h3>{t("payments.debtor.triedTitle")}</h3>
        {/* ⚠ **THE TRAIL PAGES ON THE SERVER AND THE OTHER TABLE DOES NOT, AND
            THAT ASYMMETRY IS THE READ'S OWN RULE.** Three of the four things
            this screen draws are bounded by the ACCOUNT; the notice trail
            grows for ever, because every send AND every skip appends and the
            ladder runs nightly (J4 step 2). So it is the one taken with
            `LIMIT`/`OFFSET` in the database, and `history_count` is a real
            `COUNT(*)` rather than the length of what was built. */}
        <DataTable
          config={noticesTableConfig(translate, regional)}
          state={{
            q: "",
            sort: "occurred_on",
            dir: "desc",
            page: view.history_page,
            per: (view.history_limit as never) ?? DEFAULT_PAGE_SIZE,
            filters: {},
          }}
          onStateChange={(next) => setTrailPage(next.page)}
          rows={view.history}
          totalRows={view.history_count}
          loading={false}
          empty={{
            title: t("payments.debtor.noTrailTitle"),
            helper: t("payments.debtor.noTrailHelper"),
          }}
        />
      </Panel>

      {/* Each entry names something the product genuinely cannot answer. A
          screen that drops them is the comment that claims a guarantee
          (hard-won law 1). */}
      <ProblemList problems={view.problems} title={t("payments.problems.title")} />
    </>
  );
}

export default DebtorPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/06 Payments Page Blueprint.pdf p083 (the head, the question, the drawn actions) + p084 (the two cards, annotations ①②③ and the For/Doors/Primary action/Today/To build/Rules rows), read as IMAGES at 2.0 · 06-backend/apps/payments/debtor_read.py (the payload, field for field) · CR-138-BRC07 §3 P4.3/P4.8
// generated: 2026-09-23 by LANE P4-SCREENS-A
// checklist: A✔ B✔(GET /debtors/{ref} — this is its first caller) C✔ D✔ E✔(routed in App.tsx and opened from a 7·1 row) F✔ G✔ H=n/a
// exceptions: (1) the PRIMARY action *Record payment* renders DISABLED WITH ITS REASON — the blueprint calls it *"2·3a with the account known"* and 2·3a is phase 2's; a live button onto a form that re-asks for the account would be worse than a stated absence · (2) the *+ Write-off* control returns to 7·1 rather than opening `WriteOffModal` here: that modal takes an `OutstandingRow[]` and this screen holds a `DebtorResponse`, so opening it would mean either a second copy of the form (B14 rule 43) or a shape this read does not serve — REPORTED rather than half-built · (3) the WHO column says WHICH KIND of actor rather than a name: the read serves `actor_id` and no name, and rule 31 forbids the id · (4) the subtitle draws the account reference alone; the drawing also draws the premises and *"customer since 03/2024"* and this read serves neither, which is the same served-shape gap as 7·1's ADDRESS column (DEF-PAY-6264) · (5) the bills card pages in the BROWSER through `clientPage` — the read serves every open bill of one account, which is bounded by the account and is not an `NFR-3` breach; only the trail is unbounded and only the trail pages in SQL
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
