// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.7 — *"7·1 redrawn: four KPI tiles · five ageing
//           cards as filters · full toolbar · sortable headers · paging · row
//           actions · selection toolbar. Five rule breaches on one screen
//           close."* Blueprint `05-prototype/06 Payments Page Blueprint.pdf`
//           **p081** (the drawing) and **p082** (the annotations and the
//           screen's own TASK/TODAY rows), read as IMAGES at 2.0 and 5.0
//           (B14 rule 42).
//           Screens: 7·1 Debtors (S34 · PAY-J) · 7·2 Debtor (the row's door)
// Rules:    B14 rule 12 (toolbar) · 13 (⇅ headers) · 14 (▦ chooser) · 15 (two
//           row actions + `…`) · 16 (the pagination footer) · 19 (this list's
//           own search prompt) · 31 (no database id on screen — including in
//           the address bar) · 32 (a description budget) · 33 (a LABEL ≤ 3
//           words) · 43 (a piece of UI is a COMPONENT) · BR-PAY-029 (AR high →
//           low) · BR-PAY-032 (days late is anchored on the OLDEST unpaid
//           bill) · BR-SHL-011 (the URL grammar) · BR-SHL-023 (one money path)
// Tests:    src/features/payments/debtorsTable.test.tsx
// ───────────────────────────────────────────────────────
/**
 * **THE DEBTOR LIST'S COLUMNS, TILES AND SEARCH — DECLARED, NOT DRAWN.**
 *
 * `DataTable` draws the chrome; this file says what the chrome is for. It is
 * its own module rather than four hundred more lines inside `OutstandingsTab`
 * for B14 rule 43's reason — a piece of UI is a component — and because a
 * column set is the one thing on a list that a test can check without a
 * browser.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ① FOUR TILES, NOT NINE — AND THE TWO THAT LEFT, LEFT ON RULES
 * ══════════════════════════════════════════════════════════════════════════
 * The drawing's four, in its order: **OWED · OVERDUE · OVER 60 DAYS · BEING
 * CHASED.** Annotation ② names why the third is there: *"the tail that decides
 * escalation, not the total"*. Annotation ③ names the fourth: *"what is
 * already in hand, so you can see what is left"*.
 *
 * **OVERDUE and OVER 60 DAYS ARE SUMS OF SERVED BANDS, ON THE BigInt GRID.**
 * `bucket_for(days_late)` puts each account in exactly ONE band, so the bands
 * partition the debt and adding them is exact rather than approximate. Nothing
 * here subtracts and nothing here touches a float — `sumDecimalStrings` scales
 * each string to six decimal places of integer, which is the same path the
 * selection total takes and the one `P4.20` exists to keep.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ TWO THINGS THE DRAWING DRAWS THAT THE SERVER DOES NOT SEND
 * ══════════════════════════════════════════════════════════════════════════
 * Both are FILED rather than invented (`DEF-PAY-6264`), because a column of
 * dashes and a count of zero are each a claim:
 *
 *   · **ADDRESS.** The drawing's fourth column reads *"12 Oak St Unit 1"*.
 *     `OutstandingRow` carries no address and hard rule 8 says every entity
 *     DERIVES one by walking to its premises — which is a join `P4.1` can make
 *     once, in SQL, and which this screen must not make 50 times over HTTP.
 *     **The column is absent, not empty.**
 *   · **THE ELIGIBLE COUNT.** The drawing's bulk bar reads *"2 can be sent · 1
 *     is on a medical hold"* and draws *Send notice 2*. The medical hold is
 *     `problems[]`' own declared absence on this read — *"the medical-hold
 *     column is unavailable"* — and no served field carries BR-PAY-017's other
 *     stop conditions per row. So the bar draws **no number and no sentence**,
 *     which `countedLabel` and the optional `eligibility` slot are both built
 *     for. A partial count would be the exact failure the blueprint warns
 *     about: a confirm that says *"Send 5 notices?"* when it will send two.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * NINE COLUMNS SURVIVE THE REDRAW BY BECOMING HIDEABLE, NOT BY BEING DELETED
 * ══════════════════════════════════════════════════════════════════════════
 * The table had fifteen columns and the drawing draws eight. **Nothing is
 * removed.** The drawn eight are `defaultVisible`; the other seven are in the
 * ▦ chooser, off by default — which is what rule 14 is FOR. A clerk who used
 * the autopay column still has it; a clerk opening the screen gets the drawing.
 *
 * ⚠ And the ACCOUNT column is `identity`, so it can never be hidden and it is
 * what a keyboard reaches. It is also **the row's one door**, and the door is
 * new: the blueprint's 7·2 row reads *"Doors: a row on 7·1. 1 door — there is
 * none today."*
 */
import type { ReactNode } from "react";

import type { OutstandingRow, OutstandingsResponse } from "@/api/endpoints";
import type { KpiTile } from "@/components/KPIStrip";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import type { ClientTableSpec } from "@/components/clientTable";
import { RowActions, RowActionLink, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { EyeIcon, DollarIcon, NavAccountsIcon } from "@/components/icons";
import type { SortDirection, TableConfig } from "@/components/tableTypes";
import { accountDetailPath } from "@/features/customers/customersShared";
import { Dash } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  Money,
  bucketLabel,
  collectionTierLabel,
  planStatusLabel,
  sumDecimalStrings,
} from "./paymentsShared";

/**
 * Why the chased figure is not the bill total — CR-059 CS-38.
 *
 * `balance` has been NET of the account's credit since 2026-09-02 and this
 * screen showed only the net, so a **25.00** goodwill concession on a
 * **247.30** bill produced a row reading **222.30** that a clerk could not tell
 * from a bill of 222.30. The concession is posted to the books AND the customer
 * has been told about it in writing, which is what makes an invisible one a
 * correctness problem rather than a cosmetic one.
 *
 * ⚠ **IT DRAWS NOTHING WHEN NO CREDIT CAME OFF**, which is nearly every row —
 * a second figure under every balance would be noise on the one screen a clerk
 * scans fastest (B14 rule 32's budget).
 *
 * ⚠ **AND NOTHING WHEN `gross_balance` IS NULL.** A read that could not state
 * what the bills alone said is not the same as one that said they came to
 * exactly the net, and echoing `balance` back into this line would invent the
 * first from the second (DEF-127).
 *
 * No sign is written here and none is needed: the two figures are stated as
 * themselves, in the order a person asks about them — what the bills say, and
 * what came off.
 */
export function CreditApplied(props: {
  row: OutstandingRow;
  currency: string | null;
  t: Translator;
}) {
  const applied = props.row.credit_applied ?? null;
  const gross = props.row.gross_balance ?? null;
  if (applied === null || gross === null || isZeroDecimal(applied)) {
    return null;
  }
  return (
    <span className="pay-sub">
      {props.t("payments.outstandings.creditApplied")}{" "}
      <Money amount={applied} currency={props.currency} />
      {" · "}
      {props.t("payments.outstandings.billsSay")}{" "}
      <Money amount={gross} currency={props.currency} />
    </span>
  );
}

/**
 * Is this served decimal string exactly zero?
 *
 * String-wise and never `Number(...)`: `credit_applied` arrives as
 * `"0.0000"` on every account holding none, `parseFloat` is the shape of every
 * money defect this repository has logged, and the only question asked here is
 * whether every digit is a nought.
 */
export function isZeroDecimal(value: string): boolean {
  return /^-?0*(\.0*)?$/.test(value.trim());
}

/** BR-PAY-029 — AR high → low. The drawing's *Sort · Largest balance first*
 *  label was a static string standing in for a control; it is this now, and it
 *  is a ⇅ header a clerk can change (B14 rule 13). */
export const DEBTORS_DEFAULT_SORT: { sort: string; dir: SortDirection } = {
  sort: "balance",
  dir: "desc",
};

/** The four ageing bands that are NOT `current` — what *overdue* means here. */
const OVERDUE_BUCKETS = ["1-30", "31-60", "61-90", "90+"];
/** Annotation ② — *"the tail that decides escalation, not the total"*. */
const OVER_SIXTY_BUCKETS = ["61-90", "90+"];

/**
 * **THE SCREEN 7·2 ADDRESS, BUILT FROM THE ACCOUNT NUMBER.**
 *
 * The drawing's own address bar: `/{tenant}/payments/debtors/AC-2026-00001`.
 * B14 rule 31 names *"a primary or foreign key … an HTTP route"* among the
 * things a utility user never sees, and an address bar is a visible field —
 * which is the identical decision `CR-136-BRC07`'s `P2.6` took for the Counter
 * screens hours ago (*"a counter resolves by its CODE"*). The route is
 * widened to accept it server-side in the same commit.
 *
 * ⚠ **RETURNS `null` FOR AN ACCOUNT WITH NO NUMBER, AND THE ROW THEN DRAWS NO
 * DOOR.** Falling back to the id would put a uuid in the address bar of the
 * one screen this rule was written for. An account with no number says so in
 * words, exactly as the ACCOUNT cell already does.
 */
export function debtorDetailPath(accountNo: string | null): string | null {
  return accountNo === null || accountNo === ""
    ? null
    : `/payments/debtors/${encodeURIComponent(accountNo)}`;
}

/**
 * The drawing's four tiles, in its order.
 *
 * `currency === null` renders the stated absence the rest of this screen
 * renders: the server sends these amounts with no CHAR(3) code, and an
 * unlabelled figure on a collections screen is one a clerk acts on.
 */
export function debtorTiles(
  view: OutstandingsResponse,
  currency: string | null,
  t: Translator,
): KpiTile[] {
  const band = (buckets: string[]) => view.ageing.filter((tile) => buckets.includes(tile.bucket));
  const overdue = band(OVERDUE_BUCKETS);
  const overSixty = band(OVER_SIXTY_BUCKETS);
  const accountsIn = (tiles: typeof overdue) =>
    tiles.reduce((running, tile) => running + tile.accounts, 0);

  // ⚠ COUNTED OVER THE ROWS THE SERVER SENT, WHICH IS EVERY ROW TODAY. When
  // `P4.1` pages this list these two become a fold over a PAGE, which would be
  // a tile describing fifty accounts under a label that says all of them — so
  // `P4.1` owes `totals.being_chased` and `totals.on_a_plan`, and this comment
  // is where the next lane finds out. Named on the CR board's `P4.1` row too.
  const beingChased = view.rows.filter((row) => row.collection_tier !== null).length;
  const onAPlan = view.rows.filter((row) => row.plan_status !== null).length;

  const moneyTile = (id: string, label: string, amount: string | null, detail: ReactNode) =>
    currency === null || amount === null
      ? { id, label, value: <span className="cus-awaits">{t("payments.money.currencyUnavailable")}</span>, detail }
      : // BR-PAY-021: outstanding is judged on the POSTING date — money posted
        // by the due date has already left this list.
        { id, label, money: { amount, currency, basis: "posting" as const }, detail };

  return [
    moneyTile(
      "owed",
      t("payments.outstandings.kpi.owed"),
      view.totals.owed,
      t("payments.outstandings.kpi.owedDetail", { accounts: view.totals.accounts }),
    ),
    moneyTile(
      "overdue",
      t("payments.outstandings.kpi.overdue"),
      sumDecimalStrings(overdue.map((tile) => tile.amount)),
      t("payments.outstandings.kpi.owedDetail", { accounts: accountsIn(overdue) }),
    ),
    moneyTile(
      "over60",
      t("payments.outstandings.kpi.overSixty"),
      sumDecimalStrings(overSixty.map((tile) => tile.amount)),
      t("payments.outstandings.kpi.owedDetail", { accounts: accountsIn(overSixty) }),
    ),
    {
      id: "chased",
      label: t("payments.outstandings.kpi.beingChased"),
      value: beingChased,
      detail: t("payments.outstandings.kpi.beingChasedDetail", { count: onAPlan }),
    },
  ];
}

/**
 * How the browser searches, filters and sorts this list until `P4.1` lands.
 *
 * ⚠ **EVERY SORTABLE COLUMN HAS A BRANCH HERE, AND A KEY WITH NO BRANCH
 * RETURNS `null` RATHER THAN `undefined`.** `null` sorts last, consistently;
 * `row[key as keyof Row]` would return `undefined` for a mistyped key and sort
 * every row equal — a header that cycles, an arrow that moves, and a list that
 * never reorders. That is a check that cannot fail (hard-won law 7).
 */
export const DEBTOR_TABLE_SPEC: ClientTableSpec<OutstandingRow> = {
  // B14 rule 19 — the prompt says WHAT is matched, and this is it.
  search: (row) => [row.account_no ?? "", row.customer_name ?? ""],
  filter: (row, name, value) => {
    if (name === "bad_address") {
      // Served server-side as `f.bad_address`; repeated here so the chip and
      // the request cannot disagree while both are live.
      return value === "only" ? row.bad_address : true;
    }
    if (name === "plan") {
      return value === "on" ? row.plan_status !== null : row.plan_status === null;
    }
    if (name === "ladder") {
      return value === "on" ? row.collection_tier !== null : row.collection_tier === null;
    }
    return true;
  },
  sortValue: (row, key) => {
    switch (key) {
      case "account_no":
        return row.account_no;
      case "customer_name":
        return row.customer_name;
      case "days_late":
        return row.days_late;
      case "last_payment_on":
        return row.last_payment_on;
      case "collection_tier":
        return row.collection_tier;
      case "balance":
        // A decimal string compares wrongly as text — "9.00" > "10.00" — so the
        // money grid is the sort key. `Number` is safe HERE and nowhere else on
        // this screen: it decides an ORDER and never reaches a rendered figure,
        // which still goes through `MoneyCell` as the served string.
        return Number(row.balance);
      case "open_bills":
        return row.open_bills;
      case "next_step_due":
        return row.next_step_due;
      case "plan_status":
        return row.plan_status;
      case "bucket":
        return row.bucket;
      default:
        return null;
    }
  },
};

/**
 * The column set, the filters and the row's two actions.
 *
 * `select` and `onToggle` are absent on the config a test builds to read the
 * COLUMNS, so the checkbox column is declared only where a screen can honour it
 * — BR-SHL-010's own rule, and the reason a list with no selection renders
 * byte-identical markup to one that never heard of it.
 */
export function debtorsTableConfig(
  t: Translator,
  regional: { timeZone: string; dateFormat: RegionalDateFormat },
  currency: string | null,
  tenantPath: (path: string) => string,
  selection?: { selected: readonly string[]; onToggle: (accountId: string) => void },
): TableConfig<OutstandingRow> {
  const columns: TableConfig<OutstandingRow>["columns"] = [];

  if (selection !== undefined) {
    columns.push({
      key: "select",
      label: t("payments.outstandings.col.select"),
      locked: true,
      cell: (row) => (
        <input
          type="checkbox"
          aria-label={t("payments.outstandings.selectRow", {
            account: row.account_no ?? t("payments.row.noAccountNo"),
          })}
          checked={selection.selected.includes(row.account_id)}
          onChange={() => selection.onToggle(row.account_id)}
        />
      ),
    });
  }

  columns.push(
    {
      key: "account_no",
      label: t("payments.col.account"),
      sortable: true,
      identity: true,
      cell: (row) => {
        const href = debtorDetailPath(row.account_no);
        // ⚠ B14 rule 31 — an account with no number is SAID, never patched up
        // with its uuid, and it opens no door because the door is built from
        // the number.
        return href === null ? (
          <Dash>{t("payments.row.noAccountNo")}</Dash>
        ) : (
          <InlineLinkTo to={tenantPath(href)}>{row.account_no}</InlineLinkTo>
        );
      },
    },
    { key: "customer_name", label: t("payments.col.customer"), sortable: true,
      cell: (row) =>
        row.customer_name !== null ? row.customer_name : <Dash>{t("payments.row.noCustomer")}</Dash>,
    },
    {
      // ⑦ *"Oldest · days, not a balance — the ladder runs on age."*
      key: "days_late",
      label: t("payments.outstandings.col.oldest"),
      sortable: true,
      numeric: true,
      cell: (row) =>
        // BR-PAY-032: null days late is NOT zero — no unpaid bill on this
        // account carries a due date, so it cannot be placed in time. The
        // balance still counts and `problems[]` names the case.
        row.days_late !== null ? row.days_late : <Dash>{t("payments.outstandings.noDueDate")}</Dash>,
    },
    {
      key: "last_payment_on",
      label: t("payments.outstandings.col.lastPaid"),
      sortable: true,
      cell: (row) =>
        row.last_payment_on !== null ? (
          <DateCell value={row.last_payment_on} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />
        ) : (
          <Dash>{t("payments.outstandings.neverPaid")}</Dash>
        ),
    },
    {
      // ⑧ *"Ladder · which rung, as a pill rather than a sentence."* B14 rule
      // 33 caps a LABEL at three words, which is what a pill holds.
      key: "collection_tier",
      label: t("payments.outstandings.col.ladder"),
      sortable: true,
      cell: (row) =>
        row.collection_tier !== null ? (
          <StatusPill tone={ladderTone(row.collection_tier)}>
            {collectionTierLabel(row.collection_tier, t)}
          </StatusPill>
        ) : (
          <Dash>{t("payments.outstandings.noTier")}</Dash>
        ),
    },
    {
      key: "plan_status",
      label: t("payments.outstandings.col.plan"),
      sortable: true,
      cell: (row) =>
        row.plan_status !== null ? (
          <StatusPill tone="success">{planStatusLabel(row.plan_status, t)}</StatusPill>
        ) : (
          <Dash />
        ),
    },
    {
      key: "balance",
      label: t("payments.outstandings.col.owed"),
      sortable: true,
      numeric: true,
      cell: (row) => (
        <>
          <Money amount={row.balance} currency={currency} />
          {/* CR-059 CS-38 — why this figure is not the bill total. Drawn only
              where credit actually came off, so the column stays one figure on
              the thousands of rows that hold none. */}
          <CreditApplied row={row} currency={currency} t={t} />
        </>
      ),
    },
    // ── The seven that the drawing does not draw. Kept, hidden by default,
    //    reachable through ▦ (B14 rule 14). Nothing is deleted.
    { key: "bucket", label: t("payments.outstandings.col.age"), sortable: true,
      defaultVisible: false, cell: (row) => bucketLabel(row.bucket, t) },
    { key: "open_bills", label: t("payments.outstandings.col.openBills"), sortable: true,
      numeric: true, defaultVisible: false },
    { key: "notice_summary", label: t("payments.outstandings.col.noticeHistory"),
      defaultVisible: false,
      cell: (row) =>
        row.notice_summary !== null ? row.notice_summary : <Dash>{t("payments.outstandings.noNotices")}</Dash> },
    { key: "next_step_due", label: t("payments.outstandings.col.nextStep"), sortable: true,
      defaultVisible: false,
      cell: (row) =>
        row.next_step_due !== null ? (
          <DateCell value={row.next_step_due} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />
        ) : (
          <Dash />
        ) },
    {
      // BR-PAY-015: ENROLMENT state, and nothing else. The prototype's "Retry
      // autopay" row action is superseded — v1 is capture-only.
      key: "autopay", label: t("payments.outstandings.col.autopay"), defaultVisible: false,
      cell: (row) =>
        row.autopay ? (
          <StatusPill tone="neutral">{t("payments.outstandings.autopayOn")}</StatusPill>
        ) : (
          <Dash>{t("payments.outstandings.autopayOff")}</Dash>
        ),
    },
    {
      // ⚠ **VISIBLE BY DEFAULT, AND THE DRAWING DOES NOT DRAW IT.** `BR-PAY-018`
      // is signed and says bad address is **a column AND a filter**; the
      // blueprint's 7·1 draws eight columns and this is not among them. B14
      // rule 41 hands a drawing that contradicts a signed rule to the PO
      // rather than to a lane, so the RULE is followed and the divergence is
      // reported. Hiding it behind `▦` would leave the rule technically alive
      // and practically invisible, which is the worse of the two readings —
      // a clerk posting a notice to an address the post office has already
      // returned is the failure the rule exists to prevent.
      key: "bad_address", label: t("payments.outstandings.col.badAddress"),
      cell: (row) =>
        row.bad_address ? (
          <StatusPill tone="danger">{t("payments.outstandings.badAddressFlag")}</StatusPill>
        ) : (
          <Dash />
        ) },
    {
      // ⑨ *"Row actions · 👁 Detail then overflow — there are none at all
      //    today."* B14 rule 15: icons with tooltips, max two visible.
      key: "actions",
      label: t("payments.outstandings.col.actions"),
      locked: true,
      cell: (row) => {
        const href = debtorDetailPath(row.account_no);
        return (
          <RowActions>
            {href !== null && (
              <RowActionLink
                icon={<EyeIcon />}
                label={t("payments.outstandings.action.openDebtor")}
                to={tenantPath(href)}
              />
            )}
            <RowActionsMore label={t("table.rowActions.more")}>
              <RowMenuAction
                icon={<NavAccountsIcon />}
                label={t("payments.outstandings.action.openAccount")}
                onClick={() => {
                  window.location.assign(tenantPath(accountDetailPath(row.account_id)));
                }}
              />
              <RowMenuAction
                icon={<DollarIcon />}
                label={t("payments.outstandings.action.plan")}
                reason={null}
                onClick={() => {
                  // ⚠ `DEF-PAY-6253` — S24 IS BUILT, ROUTED AND REACHABLE, and
                  // the bulk bar told clerks for 38 days that it was not. This
                  // is the door the drawing puts on a ROW, and it works.
                  window.location.assign(
                    tenantPath(`${accountDetailPath(row.account_id)}/payment-plan`),
                  );
                }}
              />
            </RowActionsMore>
          </RowActions>
        );
      },
    },
  );

  return {
    screenId: "S34",
    columns,
    getRowId: (row) => row.account_id,
    searchFields: ["account_no", "customer_name"],
    // B14 rule 19 — this list's OWN prompt, naming what it matches.
    searchPlaceholder: "payments.outstandings.searchPlaceholder",
    filters: [
      {
        name: "bad_address",
        label: t("payments.outstandings.badAddressFilter"),
        options: [{ value: "only", label: t("payments.outstandings.badAddressOnly") }],
      },
      {
        name: "ladder",
        label: t("payments.outstandings.col.ladder"),
        options: [
          { value: "on", label: t("payments.outstandings.filter.onTheLadder") },
          { value: "off", label: t("payments.outstandings.filter.notChased") },
        ],
      },
      {
        name: "plan",
        label: t("payments.outstandings.col.plan"),
        options: [
          { value: "on", label: t("payments.outstandings.filter.onAPlan") },
          { value: "off", label: t("payments.outstandings.filter.noPlan") },
        ],
      },
    ],
    defaultSort: DEBTORS_DEFAULT_SORT,
  };
}

/**
 * Which rung reads as which tone.
 *
 * ⚠ **THE FOUR NAMES ARE `ladder.LADDER_RUNGS`' OWN, MATCHED EXACTLY — NOT BY
 * SUBSTRING.** The first draft of this asked whether the rung "contains
 * `notice`" and returned `neutral` for **three of the four real rungs**,
 * because `first_10_day` and `second_5_day` contain no such word: a second
 * notice and a 48-hour final both drew the grey pill a clerk reads as
 * ordinary. It was found by the case below and by nothing else.
 *
 * **A rung this deployment does not know falls to `neutral` rather than
 * guessing a tier** — the same reasoning `ageingTone` gives one screen over.
 * The failure of a wrong tone is that a final notice looks routine, so the
 * safe default is the one that looks like nothing rather than the one that
 * looks urgent.
 */
export function ladderTone(tier: string): "neutral" | "warning" | "danger" {
  // BR-PAY-017's four, in the order they escalate.
  switch (tier) {
    case "friendly":
      return "neutral";
    case "first_10_day":
    case "second_5_day":
      return "warning";
    case "final_48_hour":
      return "danger";
    default:
      return "neutral";
  }
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/06 Payments Page Blueprint.pdf p081 (drawing) + p082 (annotations ①–⑨ and the screen's For/Doors/Primary action/Table controls/Today/To build rows), read as IMAGES at 2.0 and 5.0 · CR-138-BRC07 §3 P4.7 · 04-docs/02-decisions/14-ui-conventions.md rules 12/13/14/15/16/19/31/32/33/43
// generated: 2026-09-23 by LANE P4-SCREENS-A
// checklist: A✔ B✔(GET /outstandings, unchanged) C✔ D=n/a E✔(OutstandingsTab renders it) F✔ G✔ H=n/a
// exceptions: (1) the drawing's ADDRESS column is ABSENT, not empty — `OutstandingRow` carries no address and hard rule 8 makes it a walk to the premises, which is a join `P4.1` makes once in SQL and this screen must not make fifty times over HTTP (DEF-PAY-6264) · (2) the bulk bar's ELIGIBLE COUNT and its *"1 is on a medical hold"* sentence are absent for the same reason and are filed on the same row: the medical hold is this read's OWN declared absence and no served field carries BR-PAY-017's other stop conditions per row; a partial count is the *"Send 5 notices?"* failure the blueprint warns about · (3) seven of the fifteen columns become `defaultVisible: false` rather than being deleted — the drawing's eight are the default view and rule 14's chooser holds the rest · (4) `Number(row.balance)` decides a SORT ORDER and never reaches a rendered figure, which still goes through `MoneyCell` as the served decimal string (BR-SHL-023) · (5) BEING CHASED and its *on a plan* detail are folded over the rows the server sent, which is every row today; `P4.1` owes `totals.being_chased` and `totals.on_a_plan` or those two tiles start describing a page
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
