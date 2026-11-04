// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-005 (S32 Payments summary: today, method mix MTD, failed,
//           collections, and the two needs-attention chips)
//           Screens: S32 (AppShell sidebar → Payments → Summary)
// Rules:    BR-PAY-027 (every figure is a read-model over the rows the S33
//           capability row serves — counts tie to the lists EXACTLY) ·
//           BR-PAY-021 (Today is money POSTED today; the method mix is money
//           CLEARED this month — two different dates, on purpose) ·
//           BR-PAY-015 (autopay capture intents are a CHIP; there is no retry
//           and no charging path anywhere in v1) · BR-PAY-018 (the
//           returned-mail needs-attention chip) · BR-PAY-020 (write-offs YTD) ·
//           BR-REP-011 (DSO is reports' — served null with its reason) ·
//           BR-TEN-043 (`as_of` is asked for, never taken from a clock) ·
//           BR-SHL-012 (the A18 states) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-023 (one money formatting path) · BR-SHL-025 (a control this
//           deployment cannot honour renders DISABLED WITH its reason)
// ───────────────────────────────────────────────────────
// S32 — the five panels, every figure tied to a list a clerk can open.
//
// `apps/payments/summary.py` shipped on 2026-08-15 holding no stored aggregate
// anywhere, which is US-PAY-005 §1's own requirement — and the tab in front of
// it rendered the *awaiting* panel. This is the caller.
//
// ══════════════════════════════════════════════════════════════════════════
// THE AVERAGE IS THE WHOLE POINT OF THIS SCREEN'S HONESTY
// ══════════════════════════════════════════════════════════════════════════
// `today.average` is **null on a zero count**, and null is rendered as the A18
// zero-state sentence — never as `$0.00`. A utility that took no money today
// did not take an average payment of nothing; a 0.00 in an average tile is a
// claim about a division that never happened. The same rule governs a method
// share in an empty month (`share: null`) and the DSO tile.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS SCREEN DIVERGES FROM `05-prototype/UtilityBilling.html`
// ══════════════════════════════════════════════════════════════════════════
//   · **The Failed panel offers no "Retry".** The prototype's two Retry links
//     are superseded by BR-PAY-015: v1 is capture-only, no charging path
//     exists, and a Retry that quietly opened a NEW recording under the old
//     label would be a second payment wearing a retry's clothes. The panel
//     routes to a fresh recording (US-PAY-001) and to the account, and says so.
//   · **The Collections panel prints no DSO.** The prototype's "DSO: 18.4 days
//     · target 15" is BR-REP-011's figure and reports own the read.
//   · **There are no header actions** (Import lockbox · Post adjustment · Issue
//     credit). US-PAY-003's staged import is unbuilt and blocked on OQ-131; the
//     adjustment and credit family is US-CUS-013's. BR-SHL-010 keeps an
//     undeclared capability unrendered.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPaymentsSummary } from "@/api/endpoints";
import type { MethodMixRow, PaymentsSummaryResponse } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import {InlineLinkAnchor, PlainTable} from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { accountDetailPath } from "@/features/customers/customersShared";
import { Dash, useRegional } from "@/features/metering/meteringShared";
import { formatPercentFigure } from "@/components/PercentCell";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { BulkMarkReturnedModal, ReturnedMailOutcome } from "./returnedMail";
import { SummaryFiguresBar } from "./summaryFiguresBar";
import type { MarkReturnedOutcome } from "./returnedMail";
import {
  Money,
  ProblemList,
  paymentStatusLabel,
  paymentStatusTone,
  sumDecimalStrings,
} from "./paymentsShared";

import "./payments.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const summaryQueryKey = (asOf: string) => ["payments", "summary", asOf] as const;

/**
 * The share column, as a percentage the screen may print.
 *
 * `null` means the month cleared no money at all, so no share is defined — a
 * bucket of an empty denominator has no percentage and "0%" would be a claim
 * about a division that never happened (the same rule as the average).
 */
export function methodShareText(row: MethodMixRow, t: Translator): string | null {
  return row.share === null
    ? null
    : t("payments.summary.share", { share: formatPercentFigure(row.share) });
}

/**
 * Σ of the served shares — US-PAY-005 TC-2's *"Σ = 100%"*, rendered.
 *
 * The tie-out is on screen rather than only in a backend test because that is
 * the one place a clerk can see it. It is an EXACT sum of the served 1-decimal
 * strings (BigInt, never a float), so a month whose rounded shares add to 99.9
 * shows 99.9 — the real figure, not a hardcoded 100.0.
 */
export function methodMixShareTotal(rows: readonly MethodMixRow[]): string | null {
  const shares = rows.map((row) => row.share);
  if (shares.length === 0 || shares.some((share) => share === null)) {
    return null;
  }
  return sumDecimalStrings(shares as string[]);
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface SummaryTabProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /** BR-TEN-043: the business day. REQUIRED on the wire, held by the page and
   *  shown on screen — the API reads no clock and neither does this screen. */
  asOf: string;
  onAsOfChange: (next: string) => void;
  /** The tenant's CHAR(3), read off the payments list (see
   *  `paymentsDisplayCurrency`). This body carries none of its own. */
  currency: string | null;
  /** Where the Collections panel's "Open outstandings →" goes. */
  onOpenOutstandings: () => void;
  /** Where the Failed panel's "Record a payment" goes (US-PAY-001 — a NEW row,
   *  never an edit and never a charge). */
  onRecordPayment: () => void;
}

export function SummaryTab(props: SummaryTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);

  // US-PAY-016 — S35's bulk mark, opened from the chip that counts its queue.
  const [markingStack, setMarkingStack] = useState(false);
  const [outcome, setOutcome] = useState<MarkReturnedOutcome | null>(null);

  const summaryQuery = useQuery({
    queryKey: summaryQueryKey(props.asOf),
    queryFn: () => getPaymentsSummary({ asOf: props.asOf }, client),
    retry: false,
  });

  const view: PaymentsSummaryResponse | undefined = summaryQuery.data;
  const failed = summaryQuery.isError && view === undefined;

  return (
    <div className="pay-summary">
      {/* The README's first rule: `as_of` is REQUIRED and is never defaulted
          silently in the client. Today is proposed into the field and the
          clerk can ask for any other business day. */}
      {/* ⚠ THE BAND IS A COMPONENT SINCE 2026-09-23 (`DEF-PAY-6335`, B14 rule
          43), AND THE PO HAD TO REPORT IT TWICE TO GET THERE. First, on
          2026-09-03: *"why Figures for ... and Automatic payments lined up ...
          Mark returned post - why these are in two differnt lines - again
          layout issue"* — answered by moving the chips INSIDE `.pay-toolbar`,
          which was right. Then, on 2026-09-23: *"these detailsa re not aligned
          on ui - Figures for*"*, because `.pay-toolbar` is `align-items:
          flex-end` and this field is FOUR lines tall (label, input, help, the
          IS-8 format echo), so the counters bottom-aligned to the echo and sat
          46px below the input. `summaryFiguresBar.tsx` carries the whole band
          and the reasoning; what matters HERE is that `.pay-toolbar` is shared
          by five other payments screens, so this screen may not fix itself by
          editing it. */}
      <SummaryFiguresBar
        asOf={props.asOf}
        onAsOfChange={props.onAsOfChange}
        dateFormat={dateFormat}
        // null until the read answers — the counters are not drawn over a
        // figure the server has not stated. The field still is: the business
        // day is the clerk's to type either way.
        chips={view?.chips ?? null}
        onMarkReturnedPost={() => {
          setOutcome(null);
          setMarkingStack(true);
        }}
      />

      {outcome !== null && <ReturnedMailOutcome outcome={outcome} />}
      {markingStack && (
        <BulkMarkReturnedModal
          // BR-TEN-043: the business day this tab is ALREADY showing, and
          // the clerk types over it. No clock is read anywhere on the path.
          proposedDate={props.asOf}
          dateFormat={dateFormat}
          client={props.client}
          onClose={() => setMarkingStack(false)}
          onMarked={(result) => {
            setOutcome(result);
            setMarkingStack(false);
            // The chip counts the open queue, so it is re-read from the
            // server rather than decremented here: the count is the number
            // of UNRESOLVED accounts, not the number of pieces marked, and
            // subtracting one from the other is how a screen starts lying.
            void summaryQuery.refetch();
          }}
        />
      )}

      {failed ? (
        <Panel role="alert">
          <h3>{t("payments.summary.failedTitle")}</h3>
          <p className="met-panel-hint">{apiErrorText(summaryQuery.error, translate)}</p>
          <Button
            variant="secondary"
            onClick={() => void summaryQuery.refetch()}
          >
            {t("states.failed.retry")}
          </Button>
        </Panel>
      ) : view === undefined ? (
        <LoadingSkeleton variant="card" />
      ) : (
        <>
          <div className="pay-summary-grid">
            <div>
              {/* TODAY — money POSTED on `as_of` (BR-PAY-021's record-entered
                  side). Ties to S33 filtered `posted_at = as_of` exactly,
                  because it is the same query. */}
              <Panel accent>
                <h3>{t("payments.summary.todayTitle")}</h3>
                <p className="pay-today-amount">
                  <Money amount={view.today.amount} currency={props.currency} />
                </p>
                <dl className="met-facts">
                  <div>
                    <dt>{t("payments.summary.todayCount")}</dt>
                    <dd>{view.today.count}</dd>
                  </div>
                  <div>
                    <dt>{t("payments.summary.todayAverage")}</dt>
                    <dd>
                      {/* **null, NEVER $0.00.** A day with no payments has no
                          average, and rendering one would state something
                          false (A18 zero-state; the README's third rule). */}
                      {view.today.average !== null ? (
                        <Money amount={view.today.average} currency={props.currency} />
                      ) : (
                        <span className="cus-awaits">{t("payments.summary.noAverage")}</span>
                      )}
                    </dd>
                  </div>
                </dl>
              </Panel>

              {/* METHOD MIX — money CLEARED this month (BR-PAY-021's
                  money-received side). A different date from Today, and
                  US-PAY-005 TC-1/TC-2 name them separately. */}
              <Panel>
                <h3>{t("payments.summary.mixTitle")}</h3>
                <p className="met-panel-hint">{t("payments.summary.mixBasis")}</p>
                {view.method_mix.length === 0 ? (
                  <p className="met-panel-hint">{t("payments.summary.mixEmpty")}</p>
                ) : (
                  <>
                    <PlainTable>
                      <thead>
                        <tr>
                          <th scope="col">{t("payments.col.method")}</th>
                          <th scope="col">{t("payments.col.amount")}</th>
                          <th scope="col">{t("payments.summary.col.count")}</th>
                          <th scope="col">{t("payments.summary.col.share")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {view.method_mix.map((row) => (
                          <tr key={row.method ?? "none"}>
                            <td>
                              {/* A payment with no instrument (a credit, an
                                  adjustment) is its OWN bucket — folding it
                                  into another method's share would overstate
                                  that method, and B2 leaves the column
                                  nullable for exactly this. */}
                              {row.method_name !== null ? (
                                row.method_name
                              ) : (
                                <Dash>{t("payments.row.noMethod")}</Dash>
                              )}
                            </td>
                            <td className="pay-num">
                              <Money amount={row.amount} currency={props.currency} />
                            </td>
                            <td className="pay-num">{row.count}</td>
                            <td className="pay-num">
                              {methodShareText(row, translate) ?? (
                                <span className="cus-awaits">
                                  {t("payments.summary.noShare")}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr>
                          <td colSpan={3}>{t("payments.summary.shareTotal")}</td>
                          <td className="pay-num">
                            {(() => {
                              const total = methodMixShareTotal(view.method_mix);
                              return total === null ? (
                                <span className="cus-awaits">
                                  {t("payments.summary.noShare")}
                                </span>
                              ) : (
                                // Hard rule 2: the SUM is exact; the print is
                                // two places (`DEF-PAY-9644`).
                                t("payments.summary.share", { share: formatPercentFigure(total) })
                              );
                            })()}
                          </td>
                        </tr>
                      </tfoot>
                    </PlainTable>
                  </>
                )}
              </Panel>
            </div>

            <div>
              {/* FAILED — `payments.status = failed`, with the reversing row's
                  reason. ROUTE-TO ONLY: BR-PAY-015 makes v1 capture-only, so
                  there is no Retry and no charging path anywhere for this panel
                  to call. "Record a payment" opens US-PAY-001 — a NEW row. */}
              <Panel>
                <h3>{t("payments.summary.failedPanelTitle", { count: view.failed.length })}</h3>
                {/* B14 rule 33 — the whole of BR-PAY-015's reasoning used to be
                    printed here in thirty words. The RULE is in this file's own
                    Rules block and in the comment above this panel; the line on
                    screen says what a clerk may and may not do, in two short
                    sentences, which is the half they act on. */}
                <p className="met-panel-hint">{t("payments.summary.noRetry")}</p>
                {view.failed.length === 0 ? (
                  <p className="met-panel-hint">{t("payments.summary.noFailures")}</p>
                ) : (
                  <ul className="pay-failed-rows">
                    {view.failed.map((row) => (
                      <li key={row.payment_id}>
                        <span className="pay-id">
                          {row.payment_no ?? t("payments.row.noNumber")}
                        </span>
                        <Money amount={row.amount} currency={props.currency} />
                        <StatusPill tone={paymentStatusTone(row.status)}>
                          {paymentStatusLabel(row.status, translate)}
                        </StatusPill>
                        <span className="met-muted">
                          {row.reason !== null
                            ? t(`payments.reversalReason.${row.reason}`)
                            : t("payments.summary.noReason")}
                        </span>
                        <DateCell
                          value={row.posted_at}
                          timeZone={timeZone}
                          dateFormat={dateFormat}
                        />
                        <InlineLinkAnchor
 href={tenantPath(accountDetailPath(row.account_id))}
                        >
                          {t("payments.summary.openAccount")}
                        </InlineLinkAnchor>
                      </li>
                    ))}
                  </ul>
                )}
                <Button variant="secondary"  onClick={props.onRecordPayment}>
                  {t("payments.action.record")}
                </Button>
              </Panel>

              {/* COLLECTIONS — taken from the S34 read-model rather than
                  counted again, so this panel and S34 cannot disagree
                  (US-PAY-005 TC-4). */}
              <Panel>
                <h3>{t("payments.summary.collectionsTitle")}</h3>
                <dl className="met-facts">
                  <div>
                    <dt>{t("payments.outstandings.accountsOwing")}</dt>
                    <dd>{view.collections.accounts_owing}</dd>
                  </div>
                  <div>
                    <dt>{t("payments.outstandings.totalOwed")}</dt>
                    <dd>
                      <Money amount={view.collections.total_owed} currency={props.currency} />
                    </dd>
                  </div>
                  <div>
                    <dt>{t("payments.summary.writeOffsYtd")}</dt>
                    <dd>
                      <Money amount={view.collections.write_offs_ytd} currency={props.currency} />
                    </dd>
                  </div>
                  <div>
                    {/* The prototype prints "DSO: 18.4 days · target 15".
                        BR-REP-011 owns the formula and reports own the read —
                        the rule id stays here and never on the tile (B14 rule
                        31). The tile says where the figure IS, in five words,
                        rather than explaining why a second implementation of a
                        finance formula would be free to disagree with the first
                        (B14 rule 33: rationale is zero words on screen). */}
                    <dt>{t("payments.outstandings.kpi.dso")}</dt>
                    <dd>
                      <span className="cus-awaits">
                        {t("payments.outstandings.dsoUnavailable")}
                      </span>
                    </dd>
                  </div>
                </dl>
                <Button
                  variant="secondary"
                  onClick={props.onOpenOutstandings}
                >
                  {t("payments.summary.openOutstandings")}
                </Button>
              </Panel>
            </div>
          </div>

          {/* The README's fourth rule — the same `problems[]` S34 carries,
              because this summary delegates its collections figures to that
              read-model rather than counting debtors twice.

              ⚠ **B14 RULE 32 IS ONLY HALF-MET HERE, AND THE MISSING HALF IS
              NAMED RATHER THAN LEFT TO LOOK FINISHED (2026-09-01).** The PO
              photographed this panel beside S36's: a heading over bullet
              paragraphs. The HEADING and the two bullets this screen always
              carries are now inside the rule-33 budget. The DISCLOSURE half —
              rule 32's "a stated absence is a `<details>` CLOSED by default" —
              is NOT done, because `ProblemList` draws its own `<h3>` and lives
              in `paymentsShared.tsx`, which S34 Collections shares and which
              this lane does not own. Wrapping it here would print the heading
              twice. It needs one change in `ProblemList` itself, in the lane
              that owns it, and the remaining ~18 `payments.problem.*` bullets
              want the same shortening in the same commit. */}
          <ProblemList problems={view.problems} title={t("payments.problems.title")} />
        </>
      )}
    </div>
  );
}

export default SummaryTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-005@3c9f5a1 (story+rules snapshot — EP-PAY-01 US-PAY-005; 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-027/021/015/018/020; 07-frontend/src/features/payments/README.md §2026-08-15)
// generated: 2026-08-15 by story-coder (payments FRONTEND visible-half lane — the S32 tab the read-model shipped without)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report — tsc✔ · eslint --max-warnings 0✔ · vitest✔ (RED-PROVED FIRST) · run_gates✔
// exceptions: (1) NO "Retry" ANYWHERE on the Failed panel — BR-PAY-015 makes v1 capture-only and no charging path exists; the panel routes to a fresh US-PAY-001 recording (a NEW row) and to the account · (2) NO DSO FIGURE — BR-REP-011 is reports' and the tile renders the reason · (3) NO HEADER ACTIONS (Import lockbox · Post adjustment · Issue credit): US-PAY-003 is unbuilt and blocked on OQ-131, and the adjustment/credit family is US-CUS-013's (BR-SHL-010) · (4) the served body carries NO currency code and the tenant's CHAR(3) is read off `GET /payments` — REPORTED · (5) the method-mix share TOTAL is summed in the browser, exactly, on the served 1-decimal strings with BigInt: it renders the real figure (99.9 stays 99.9), never a hardcoded 100.0
// amended:   2026-09-01 by the finance-copy lane (live content defects the PO photographed at v2.123.0 — S36 primarily, this screen for "the same pattern"). Copy only; no figure, no refusal and no control changed. `payments.summary.asOfHelp` and `payments.summary.noRetry` drop their rationale to the code comments beside them (B14 rule 33), the DSO absence says where the figure IS instead of why it is not here, and `payments.problems.title` is a three-word heading. REPORTED, NOT DONE: the `problems[]` panel is not yet a closed `<details>` — that is `ProblemList` in `paymentsShared.tsx`, shared with S34 and outside this lane.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
