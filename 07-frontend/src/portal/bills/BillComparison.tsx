// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-035 (EP-CWP-07) — why this bill is different, and the lines
//           must sum to the difference. Screen: CWP-030 (blueprint `P16`)
// Rules:    BR-CWP-046 (the component lines sum EXACTLY to the difference —
//           CONFIRMED) · BR-CWP-093 (nothing empty ever appears) · CLAUDE.md
//           hard rule 2 (DISPLAY 2) · hard rule 3 (a quantity with its unit) ·
//           B14 rule 21 · rule 31 · rule 32 (a stated absence, closed by
//           default) · rule 35 · rule 36
// Questions: OQ-CWP-1563 / OQ-CWP-1569 — BOTH CLOSED 2026-09-05, PO verbatim
//           *"(a) list every reason with its share"*. The breakdown IS drawn.
//           This header said it was unsigned and undrawn until 2026-09-06
//           (DEF-CWP-4207). Nothing here is waiting on a question.
// Defects:  DEF-CWP-4206 — the AGAINST LAST AUGUST panel drew for nobody,
//           because the seam asked for a 12-month window and the comparison
//           needs 13 months of reach. Fixed in billing_seam.py, not here.
// Tests:    src/portal/bills/BillComparison.dom.test.tsx
// Design:   CR-085 (c) — the wireframe for s32 foots the attribution list
//           with the difference itself, so the reader is never asked to add
//           the shares up. What it ALSO draws and this product cannot
//           compute is reported rather than invented: the per-cause
//           quantities (*60 kWh more, 800 against 740*), the period-length
//           line, the *prices did not change* claim, and the twelve-bill
//           lowest/average/highest strip.
// Impacts:  src/portal/api/portalClient.ts `getBillComparison`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";
import { useParams } from "react-router-dom";

import { Panel } from "@/components/Panel";
import {
  Card,
  KVList,
  SectionTitle,
  TotalRow,
  TwoCol,
  UsageBars,
  WhereNext,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState } from "../components/states";
import { formatMoney } from "../signin/Enrol";
import {
  getBillComparison,
  type PortalBillComparison,
  type PortalBillComponent,
} from "../api/portalClient";

/**
 * `CWP-030` — *why August cost `$3.74` more*.
 *
 * ⚠ **THE SIGN IS THE SERVER'S AND NOTHING HERE TAKES AN ABSOLUTE VALUE.** A
 * bill that FELL carries `-3.74` and reads *cost less*; stripped of its sign it
 * would be reported as a rise with a correct-looking figure. The staff account
 * screen records what that costs once already — a panel reading `272.30` where
 * the customer owed `222.30`.
 *
 * ⚠ **A FIRST BILL OFFERS NO COMPARISON AT ALL** — not one against zero.
 * *"$142.18 more than last month"* is arithmetically true and, to somebody who
 * has just moved in, a lie.
 *
 * ⚠ **THE BREAKDOWN IS DRAWN, AND THIS PARAGRAPH SAID THE OPPOSITE FOR FIVE
 * DAYS (`DEF-CWP-4207`).** Which reasons are listed, and which one is credited
 * when two things move at once, WAS a finance judgment a lane could not make —
 * and the PO made it on 2026-09-05: *"(a) list every reason with its share"*.
 * Every `(service, kind)` bucket that moved is named with its own amount, and
 * a bucket that did NOT move is listed too, reading *unchanged* rather than a
 * signed zero.
 *
 * ⚠ **THE ABSENCE BRANCH BELOW IS STILL LIVE AND IS NOT DEAD CODE.** It no
 * longer means *nobody has signed this*; it means `BR-CWP-046` refused —
 * the shares did not sum EXACTLY to the headline, so none are shown. Four
 * numbers that do not add up to the figure a customer is reading explain
 * nothing. It names no rule id on screen, because B14 rule 32 forbids an
 * internal code in customer-facing copy.
 */
export function BillComparisonView(props: { number?: string }) {
  const { t } = useTranslation();
  const params = useParams();
  const path = usePortalPath();
  const number = props.number ?? params.number ?? "";
  const [view, setView] = useState<PortalBillComparison | null>(null);
  const [failed, setFailed] = useState(false);
  // ⚠ **R-10's `Try again` RE-RUNS THE READ RATHER THAN LOOKING LIKE IT DOES.**
  const [attempt, setAttempt] = useState(0);
  // The bill this page is about — the way out of every failed branch, and the
  // address lane 8's *See the whole bill* door points at.
  const billHref = path(`/bills/${encodeURIComponent(number)}`);

  useEffect(() => {
    let live = true;
    setView(null);
    setFailed(false);
    getBillComparison(number)
      .then((answer) => {
        if (live) setView(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [number, attempt]);

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5) — the shared
  // `components/PageHeader.tsx`, never a second one. It REPLACES the local
  // `back` element this file used to build: a bordered-looking link in its own
  // `<div className="mb-3">` above the card is exactly what delta X5 objects
  // to. `data-back="bill"` travels with it, because the suite selects on it.
  const head = (
    <span data-back="bill">
      <PageHeader
        kicker={t("portal.kicker.bills")}
        title={t("portal.billWhy.title")}
        backTo={{
          to: path(`/bills/${encodeURIComponent(number)}`),
          label: t("portal.billWhy.backToBill", { number }),
        }}
      />
    </span>
  );

  // ⚠ **THREE STATES, THREE SENTENCES, ONE CARD — R-22 AS THE PO RULED IT**
  // (2026-09-11: *"differntiate it using text message"*). They were three
  // hand-rolled `Card`s each holding one grey `<p>`; `PortalState` keeps the
  // one picture and puts the kind in the DOM so the difference is checkable by
  // something other than a reader.
  if (failed) {
    return (
      <PortalScreen screen="CWP-030" head={head}>
        <PortalState
          kind="failed"
          testId="bill-comparison"
          sentence={t("portal.billWhy.couldNotRead")}
          // R-10 — the way out beside the message, never a page away.
          waysOut={[
            {
              label: t("portal.state.tryAgain"),
              onClick: () => setAttempt((n) => n + 1),
              tone: "primary",
              testKey: "retry",
            },
            { label: t("portal.bills.seeWholeBill"), to: billHref, testKey: "bill" },
          ]}
        />
      </PortalScreen>
    );
  }
  if (!view) {
    return (
      <PortalScreen screen="CWP-030" head={head}>
        <PortalState
          kind="loading"
          testId="bill-comparison"
          sentence={t("portal.billWhy.reading")}
        />
      </PortalScreen>
    );
  }

  // TC-5 — no comparison at all, and no difference figure anywhere on the page.
  //
  // ⚠ **THE HEADING WAS DRAWN TWICE HERE — `DEF-CWP-4862`.** The head above
  // renders `PageHeader title={portal.billWhy.title}` on every branch, and this
  // branch then opened its card with a `SectionTitle` holding the SAME string:
  // *Why is this bill different?* in 40px type, and *Why is this bill
  // different?* again immediately under it. It arrived when the head moved out
  // of the success branch — the section title had been this branch's only
  // heading and nobody looked at it afterwards, which is the whole shape of
  // hard-won law 12. The card now carries the sentence and nothing else, and it
  // is the `empty` kind: *there is nothing to compare this with* is an absence,
  // not a failure, and `data-portal-state` says which.
  if (!view.compared) {
    return (
      <PortalScreen screen="CWP-030" head={head}>
        <PortalState kind="empty" testId="bill-comparison" sentence={t("portal.billWhy.firstBill")}>
          <span data-no-comparison="" />
        </PortalState>
      </PortalScreen>
    );
  }

  return (
    <PortalScreen screen="CWP-030" head={head}>
      <TwoCol
        main={
          <Card testId="bill-comparison">
            <SectionTitle>{t("portal.billWhy.againstLastMonth")}</SectionTitle>
            {/* ⚠ THE HEADLINE, AND IT IS THE HALF THAT DEFLECTS THE CALL. Plain
                subtraction of two stored totals — no unsigned rule is involved
                in it, which is why it ships while the breakdown waits. */}
            <p className="text-body text-neutral-700" data-direction={view.direction ?? ""}>
              {t(`portal.billWhy.headline.${view.direction}`, {
                amount: formatMoney(stripSign(view.difference_display), null),
              })}
            </p>
            <KVList
              rows={[
                {
                  key: "prior",
                  label: t("portal.billWhy.lastMonth", { number: view.prior_number }),
                  value: (
                    <span data-figure="prior_total">
                      {formatMoney(view.prior_total_display ?? "0", null)}
                    </span>
                  ),
                },
                {
                  key: "current",
                  label: t("portal.billWhy.thisMonth", { number: view.number }),
                  value: (
                    <span data-figure="total">{formatMoney(view.total_display, null)}</span>
                  ),
                },
              ]}
            />
            <TotalRow
              testKey="difference"
              signed={
                view.direction === "cost_more"
                  ? "up"
                  : view.direction === "cost_less"
                    ? "down"
                    : "flat"
              }
              label={t("portal.billWhy.difference")}
              // ⚠ THE SIGN TRAVELS. `formatMoney` renders a leading minus for a
              // negative figure and this adds the `+` a rise needs, so a
              // customer never has to work out which way it went.
              value={
                <span data-figure="difference">
                  {signedMoney(view.difference_display ?? "0")}
                </span>
              }
            />
            {view.components_available ? (
              <div className="mt-3" data-components="">
                <SectionTitle>{t("portal.billWhy.whatMoved")}</SectionTitle>
                <KVList
                  rows={view.components.map((row) => ({
                    key: row.code,
                    label: reasonWord(t, row),
                    value: (
                      <span data-component={row.code}>
                        {/* ⚠ **A SHARE THAT DID NOT MOVE READS `unchanged`,
                            NOT `+$0.00`.** *Trash cart charge unchanged* is one
                            of the four lines the PO ruled on, and a signed zero
                            is a machine's way of writing the same fact. */}
                        {isZero(row.amount_display)
                          ? t("portal.billWhy.unchanged")
                          : signedMoney(row.amount_display)}
                      </span>
                    ),
                  }))}
                />
                {/* ⚠ **THE PARTS ARE FOOTED, AND THE FOOT IS THE SERVER'S OWN
                    DIFFERENCE RATHER THAN A SUM OF THE ROWS ABOVE IT.** The
                    drawing closes this list with *Total difference +$14.80*,
                    and its reason is the whole screen: *"the customer is never
                    asked to subtract … the parts add to it"*. A list of shares
                    with nothing under it leaves the reader adding four signed
                    figures to check they reach the headline they have already
                    read at the top of the page.
                    ⚠ **NOTHING IS ADDED HERE.** `BR-CWP-046` is what makes
                    this honest: the shares are served ONLY when they sum
                    exactly to the difference, so re-printing the served
                    difference under them states the total without the browser
                    doing money arithmetic to get it (hard rule 2). Summing the
                    rows instead would be a second implementation of the one
                    figure this page exists to explain, free to disagree with
                    the ledger. */}
                <TotalRow
                  testKey="components-total"
                  signed={
                    view.direction === "cost_more"
                      ? "up"
                      : view.direction === "cost_less"
                        ? "down"
                        : "flat"
                  }
                  label={t("portal.billWhy.totalDifference")}
                  value={
                    <span data-figure="components_total">
                      {signedMoney(view.difference_display ?? "0")}
                    </span>
                  }
                />
              </div>
            ) : (
              // ⚠ **THIS BRANCH IS NO LONGER THE NORMAL CASE AND IS NOT DEAD
              // EITHER** (`DEF-CWP-3968`). It stood for a decomposition nobody
              // had signed; the PO signed it on 2026-09-05 — *"(a) list every
              // reason with its share"* — so the panel above is what a customer
              // now reads. What is left here is `BR-CWP-046`: shares that do
              // not sum EXACTLY to the headline are not served at all, because
              // four numbers that do not add up explain nothing.
              //
              // ⚠ **A STATED ABSENCE, CLOSED BY DEFAULT** (B14 rule 32), and it
              // is the honest one: an empty list drawn as a panel would read as
              // *"nothing moved"*, which is a different and false statement.
              <p className="mt-3 text-body text-neutral-600" data-components-absent="">
                {t("portal.billWhy.breakdownPending")}
              </p>
            )}
          </Card>
        }
        rail={<LastYearPanel view={view} />}
      />
      {/* ⚠ **THE SCREEN EXPLAINED A BILL AND OFFERED NO WAY TO ACT ON IT —
          `DEF-CWP-4213`.** The only control on the page was the back link in
          the head. A customer who has just read *this bill cost $14.80 more
          than last month* wants one of two things next: the bill itself, line
          by line, or somebody to look at it. Both are addresses this product
          already serves, and neither had a door from here.
          ⚠ **THE FIRST ONE IS ALSO THE DOOR LANE 8 ASKED FOR BY NAME** —
          `CPB-08` joins a usage month to the bill line that produced it, and
          the words are shared (`portal.bills.seeWholeBill`) so the Usage screen
          and this one cannot end up with two phrasings of *open the bill*. */}
      <WhereNext
        mark="bill-why"
        doors={[
          { key: "bill", label: t("portal.bills.seeWholeBill"), to: `/bills/${encodeURIComponent(number)}` },
          {
            key: "query",
            label: t("portal.billDetail.queryThisBill"),
            to: `/bills/${encodeURIComponent(number)}/dispute`,
          },
        ]}
      />
    </PortalScreen>
  );
}

/** **AGAINST LAST AUGUST** — the same month a year ago, per service.
 *
 *  ⚠ **THE PANEL IS ABSENT WHEN THERE IS NOTHING TO COMPARE** (`BR-CWP-093`):
 *  an account under a year old has no point last August, and a panel headed
 *  *against last August* over nothing invites the question of what belongs in
 *  it. The unit rides on every figure (hard rule 3) — the server drops any
 *  service whose months do not agree on one rather than serving bare numbers. */
function LastYearPanel(props: { view: PortalBillComparison }) {
  const { t } = useTranslation();
  const rows = props.view.against_last_year;
  if (rows.length === 0) return null;
  return (
    <Panel as="aside" title={t("portal.billWhy.againstLastYear")}>
      {/* ⚠ **THE TWO-BAR CHART THE DRAWING PUTS HERE — audit row D6,
          `DEF-CWP-3981`.** `08-screen-layouts.md` opens this panel with *a
          tiny two-bar chart with mono labels*, and the panel drew figures
          only. On this screen the picture IS the explanation: *why did August
          cost more* is answered by two bars of different heights far faster
          than by a sentence containing four numbers.

          ⚠ **ONE CHART PER SERVICE AND NEVER ONE FOR TWO** (hard rule 3).
          Gallons and therms share a month and nothing else, so a combined
          chart would be arithmetic this screen is forbidden to do; the drawing
          shows one because the drawn account has one measured service.

          ⚠ **`UsageBars`, NOT A CHART DRAWN HERE** (B14 rule 36). It is the
          kit's consumption chart, the unit rides on its axis, and it marks the
          taller bar — which is the whole point of the comparison. The month
          names come from the labels the server sends (`2025-08`), through the
          same `Intl` formatter `CWP-033` uses. */}
      {rows.map((row) => (
        <div key={`chart-${row.service ?? "service"}`} data-year-chart={row.service ?? ""}>
          <UsageBars
            testId={`year-${row.service ?? "service"}`}
            unit={row.unit}
            bars={[
              {
                month: row.last_year_label,
                quantity: row.last_year,
                quantityDisplay: row.last_year,
                absent: false,
                estimated: row.last_year_estimated,
              },
              {
                month: row.this_year_label,
                quantity: row.this_year,
                quantityDisplay: row.this_year,
                absent: false,
                estimated: row.this_year_estimated,
              },
            ]}
            axisLabel={t("portal.usage.axis", { unit: row.unit })}
            caption={t("portal.billWhy.chartCaption", {
              service: t(`rating.service.${row.service}`, {
                defaultValue: row.service_name ?? row.service ?? "",
              }),
              unit: row.unit,
            })}
            emptyLabel={t("portal.usage.noReadingsYet")}
            barTitle={(bar) =>
              t(bar.estimated ? "portal.usage.barEstimated" : "portal.usage.bar", {
                month: bar.month,
                value: bar.quantityDisplay ?? "",
                unit: row.unit,
              })
            }
          />
        </div>
      ))}
      <KVList
        rows={rows.map((row) => ({
          key: row.service ?? "service",
          // The catalogue's existing service words, not a portal-only copy.
          label: t(`rating.service.${row.service}`, {
            defaultValue: row.service_name ?? row.service ?? "",
          }),
          value: (
            <span data-year-compare={row.service ?? ""}>
              {t("portal.billWhy.thenNow", {
                then: `${row.last_year} ${row.unit}`,
                now: `${row.this_year} ${row.unit}`,
              })}
            </span>
          ),
        }))}
      />
      {/* B14 rule 32 — ONE sentence, and it is the one that answers the
          question before the customer telephones to ask it. */}
      <p className="text-base text-neutral-600" data-jump-hint="">
        {t("portal.billWhy.aJumpIsUsually")}
      </p>
    </Panel>
  );
}

/**
 * **WHAT MOVED, IN A CUSTOMER'S WORDS** — `DEF-CWP-3968`.
 *
 * ⚠ **THE CODE IS NEVER SHOWN.** `water_usage` is a handle for a test and a
 * log; B14 rule 32 keeps internal codes off a customer's screen, and rule 35
 * says the sentence is written in the catalogue's own language rather than
 * translated out of an identifier.
 *
 * ⚠ **THE SERVICE WORD IS `rating.service.*`, THE ONE THE PRODUCT ALREADY
 * HAS** — the same lookup the bill itself makes for its headings. A second set
 * of portal-only words for *Water* would be two names for one thing, which is
 * how they start disagreeing (law 5).
 *
 * ⚠ **THE DIRECTION IS IN THE FIGURE, NOT IN THE LABEL.** The blueprint draws
 * whole sentences — *You used more water* — and the amount column already
 * carries a signed figure with its own arrow, so stating the direction again
 * in the label would be one fact twice inside a row B14 rule 32 budgets at
 * one. REPORTED as a divergence from the drawing rather than settled silently.
 */
function reasonWord(
  t: (key: string, options?: Record<string, unknown>) => string,
  row: PortalBillComponent,
): string {
  if (row.service === null) {
    return t(`portal.billWhy.billReason.${row.kind}`, {
      defaultValue: t("portal.billWhy.billReason.other"),
    });
  }
  const service = t(`rating.service.${row.service}`, { defaultValue: row.service });
  return t(`portal.billWhy.reason.${row.kind}`, {
    service,
    defaultValue: t("portal.billWhy.reason.other", { service }),
  });
}

/** A 2dp money string that is zero — `0.00`, `-0.00`, `0`.
 *
 *  ⚠ **STRING COMPARISON, NOT `Number`.** Hard rule 2 keeps money off floats in
 *  a browser as much as in the database. */
function isZero(amount: string | null): boolean {
  return amount === null || /^-?0*\.?0*$/.test(amount.trim());
}

/** `+$8.83` · `$0.00` · `-$9.38`. ⚠ **THE SIGN IS PRESERVED AND A RISE IS
 *  MARKED.** `formatMoney` already renders a leading minus; what a customer
 *  cannot infer is that an unmarked figure went UP, so the `+` is added. */
export function signedMoney(amount: string): string {
  const money = formatMoney(amount, null);
  return Number(amount) > 0 ? `+${money}` : money;
}

/** The headline reads *"cost $3.74 more"*, so the sentence carries the
 *  direction and the figure does not repeat it. ⚠ This is the ONLY place a sign
 *  is dropped, it is dropped from a figure whose direction is stated in the
 *  same sentence, and it is never done to a component or to the total. */
function stripSign(amount: string | undefined): string {
  return (amount ?? "0").replace("-", "");
}
