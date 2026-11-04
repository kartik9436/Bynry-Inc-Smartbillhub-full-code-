// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-26 · task 65 — "CS-26's screen, the bad-debt-by-reason
//           tab". The CR's own audit of 2026-09-02: *"seven finished backends
//           are shipping with no screen … the count stands at ONE: task 64, the
//           bad-debt report."* This is that one.
// Story:    US-PAY-012 (write-offs)   Screens: S36 (Finance · Revenue & AR)
// Rules:    BR-PAY-020 (payments owns the transaction record, ledger posts,
//           FINANCE REPORTS — the third verb, which had a read and no door) ·
//           BR-REP-001 (a money report labels its basis) · BR-TEN-043 (the
//           caller names the window; nothing reads a clock) · CLAUDE.md rule 2
//           (money 4dp, percentages 6dp, both DISPLAY 2, beside a CHAR(3)) ·
//           B14 rule 31 (no database id is the visible value of a field) ·
//           B14 rule 32 (one sentence a section; a stated absence is CLOSED) ·
//           B14 rule 34 (*In the books* is the phrase, everywhere)
// Tests:    07-frontend/src/features/payments/badDebtPanel.test.tsx
// ───────────────────────────────────────────────────────
// What did we give up on, why, and do the books agree — on a screen.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE ADDS NO CLASS AND NO TAILWIND UTILITY (B14 rule 21)
// ══════════════════════════════════════════════════════════════════════════
// `07-frontend/src/styles/route-b-migrated.txt` lists neither
// `features/payments/*` nor `features/ledger/*`, and the Product Owner has
// ruled that Finance and Payments migrate as their own separate work. A
// Tailwind utility written here would be a class NO stylesheet declares: it
// renders as nothing at all while `tsc`, eslint and every `toContain("flex")`
// assertion pass, because the class IS in the DOM (DEF-974). So every class
// below is one `payments.css` or `finance.css` already declares, and G31 —
// which sits at a ceiling of zero undeclared classes — is what holds it.
//
// ══════════════════════════════════════════════════════════════════════════
// THE WINDOW IS CHOSEN HERE AND IT IS NEVER READ FROM A CLOCK
// ══════════════════════════════════════════════════════════════════════════
// `GET /bad-debt` REQUIRES both dates and has no default, deliberately
// (BR-TEN-043, gate G6): a board pack produced at 23:58 and re-run at 00:02
// must be the same document. This panel therefore has to state a window — and
// it builds BOTH options out of facts the SERVER served:
//
//   · **This period** — the accounting period the Finance header is already
//     showing (`current_period.start` … `current_period.end`, BR-TEN-022).
//   · **Year to date** — the tenant's own financial-year start (`fy_start_month`
//     / `fy_start_day` from Settings → Regional) on or before that period's END,
//     through that same end date.
//
// Neither reads `new Date()`. The second exists because CS-26's question is a
// board's question — *"what did we write off this year?"* — and a by-month
// table over a single accounting period is a table with one row in it, which
// is the same criticism this screen already makes of a twelve-month chart drawn
// from one period's data.
//
// ⚠ **A TENANT WITH NO FISCAL YEAR CONFIGURED GETS ONE OPTION, NOT A GUESS.**
// `fy_start_month` is nullable and a calendar-year default computed here would
// be this screen inventing the tenant's financial year. The control then offers
// the period alone and the reason is stated where the choice would have been.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE SCREEN REFUSES TO DRAW
// ══════════════════════════════════════════════════════════════════════════
//   · **ONE RECONCILED NUMBER.** The server computes the books' write-off total
//     independently of this module's own rows and serves them side by side with
//     `agrees`. They are shown that way. Two readings that agree are evidence;
//     one number hiding a disagreement is how a control stops working.
//   · **A BY-SERVICE SPLIT.** `OQ-1300` is raised and unanswered — a write-off
//     is taken against an ACCOUNT at its whole balance and nothing attributes it
//     across electric, water and gas. The server names the gap on every result
//     and this screen states it rather than approximating it.
//   · **A ROUNDED SHARE THAT IS THEN SUMMED.** The share arrives at six decimals
//     and is DISPLAYED at two (hard rule 2). Nothing here adds displayed
//     percentages together — the total column is money, summed by the server.
import { useState } from "react";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getBadDebtAccounts, getBadDebtReport } from "@/api/bankRecEndpoints";
import type {
  BadDebtAccountRow,
  BadDebtReasonRow,
  BadDebtReport,
} from "@/api/bankRecEndpoints";
import { getRegionalSettings } from "@/api/endpoints";
import type { CurrentPeriod } from "@/api/endpoints";
import { AbsentFigure } from "@/components/AbsentFigure";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { InlineLink, PlainTable } from "@/components/Surfaces";
import { LoadingSkeleton } from "@/components/StateFrame";
import { queryKeys } from "@/api/queryClient";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { problemWords, writeOffReasonLabel } from "./paymentsShared";

import "./payments.css";

export const badDebtQueryKey = (start: string, end: string) =>
  ["payments", "bad-debt", start, end] as const;

export const badDebtAccountsQueryKey = (start: string, end: string, reason: string) =>
  ["payments", "bad-debt", "accounts", start, end, reason] as const;

/** Which window the reader has asked for. Two, and both are SERVED facts. */
export type BadDebtWindowId = "period" | "year";

/**
 * The tenant's financial-year start on or before `end` — arithmetic, not a clock.
 *
 * `end` is the accounting period's own end date (BR-TEN-022, served); `month`
 * and `day` are the tenant's `fy_start_month` / `fy_start_day` from Settings →
 * Regional. A financial year starting 1 July means the year-to-date window for
 * a period ending 2026-03-31 opens on **2025-07-01**, not on 2026-07-01 — so the
 * candidate is stepped back a year when it falls after the end date.
 *
 * Exported because a date rule that lives inside a component is a date rule
 * nothing can test on its own.
 */
export function fiscalYearStartOnOrBefore(end: string, month: number, day: number): string {
  const year = Number(end.slice(0, 4));
  const pad = (value: number) => String(value).padStart(2, "0");
  const candidate = `${year}-${pad(month)}-${pad(day)}`;
  // String comparison is exact on ISO dates and needs no Date object — which
  // also means no timezone can move the boundary by a day.
  return candidate <= end ? candidate : `${year - 1}-${pad(month)}-${pad(day)}`;
}

/** The window a choice resolves to, or null when this tenant cannot offer it. */
export function badDebtWindow(
  choice: BadDebtWindowId,
  period: CurrentPeriod,
  fyStartMonth: number | null,
  fyStartDay: number | null,
): { start: string; end: string } | null {
  if (choice === "period") {
    return { start: period.start, end: period.end };
  }
  if (fyStartMonth === null || fyStartDay === null) {
    // NOT a calendar-year fallback. Guessing the tenant's financial year would
    // put a figure under a heading nobody agreed to, and the heading is the
    // half a board reads.
    return null;
  }
  return {
    start: fiscalYearStartOnOrBefore(period.end, fyStartMonth, fyStartDay),
    end: period.end,
  };
}

/**
 * Every reason the database allows, in the order the report served them, with
 * the unused ones drawn at zero.
 *
 * The server sends `reasons` for exactly this: *"so a screen can render a zero
 * row rather than silently dropping a category nobody used this year."* A
 * category missing from a board's table reads as a category that does not
 * exist, and *"we wrote off nothing for bankruptcy"* is an answer.
 */
export function reasonRowsWithZeros(report: BadDebtReport): BadDebtReasonRow[] {
  const served = new Map(report.by_reason.map((row) => [row.reason, row]));
  const zeros = report.reasons
    .filter((reason) => !served.has(reason))
    .map((reason) => ({
      reason,
      written_off: "0.0000",
      reversed: "0.0000",
      net: "0.0000",
      // A share of nothing is null, never 0.000000 — the server's own posture.
      share_percent: null,
      count: 0,
      currency: report.currency,
    }));
  return [...report.by_reason, ...zeros];
}

/** Six decimals in, two out (hard rule 2's *"DISPLAY 2"*). `null` stays null:
 *  a share of nothing is not zero percent, and `0.00 %` would be a claim. */
export function sharePercentDisplay(share: string | null): string | null {
  if (share === null) {
    return null;
  }
  const value = Number(share);
  if (Number.isNaN(value)) {
    return null;
  }
  return `${value.toFixed(2)}%`;
}

// ── the panel ─────────────────────────────────────────────────────────────

export interface BadDebtPanelProps {
  t: Translator;
  locale?: string;
  client?: ApiClient;
  /** The tenant's accounting period, served (BR-TEN-022). Never a clock. */
  period: CurrentPeriod;
}

export function BadDebtPanel(props: BadDebtPanelProps) {
  const { t, period } = props;
  const client = props.client ?? api;
  const [choice, setChoice] = useState<BadDebtWindowId>("period");
  const [openReason, setOpenReason] = useState<string | null>(null);

  // The SAME query key `RevenueArPage` — the only screen that mounts this panel
  // — already uses, so this costs no extra request: react-query serves it from
  // the cache that screen filled.
  //
  // ⚠ **THIS IS ONE OF EXACTLY TWO PLACES LEFT READING THE ADMIN-ONLY SETTINGS
  // ENDPOINT, AND IT IS A STATED HOLD (`DEF-SHL-4283`, 2026-09-06).** Seven
  // screens moved to `GET /shell/display` that day because a Billing Clerk
  // reaches them and `GET /settings/regional` answers a clerk `403 AUTH-002`.
  // This panel cannot: it needs `fy_start_month` / `fy_start_day`, the RAW
  // fiscal-year anchor, and `/shell/display` carries the computed period card
  // and not the configuration behind it. **The hold is safe because of WHERE
  // this panel is mounted, not because of what it reads** — `RevenueArPage`
  // (S36) gates on A4's `finance_reconcile_export` cell, `{System Admin,
  // Executive}`, which is exactly the pair `SettingsReadAnyWriteSystemAdmin`
  // serves. Mount this panel on a clerk-reachable screen and it breaks the same
  // way the report did.
  // **SO THE HOLD HAS AN EXPIRY TEST, IN THE SAME COMMIT** (hard-won law 2's
  // mirror): `src/api/adminOnlyReads.test.ts` fails the day this component is
  // rendered anywhere but `RevenueArPage`, and names the file.
  const regional = useQuery({
    queryKey: queryKeys.regionalSettings,
    queryFn: () => getRegionalSettings(client),
    retry: false,
  });
  const fyStartMonth = regional.data?.fy_start_month ?? null;
  const fyStartDay = regional.data?.fy_start_day ?? null;
  const yearWindow = badDebtWindow("year", period, fyStartMonth, fyStartDay);
  const window = badDebtWindow(choice, period, fyStartMonth, fyStartDay) ?? {
    start: period.start,
    end: period.end,
  };

  const report = useQuery({
    queryKey: badDebtQueryKey(window.start, window.end),
    queryFn: () => getBadDebtReport({ start: window.start, end: window.end }, client),
    retry: false,
  });

  const accounts = useQuery({
    queryKey: badDebtAccountsQueryKey(window.start, window.end, openReason ?? ""),
    queryFn: () =>
      getBadDebtAccounts(
        { start: window.start, end: window.end, reason: openReason ?? undefined },
        client,
      ),
    // Only when a reader has asked which accounts are behind a figure. A drill
    // -down fetched eagerly is a second read of the same rows on every load.
    enabled: openReason !== null,
    retry: false,
  });

  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("payments.badDebt.title")}</h3>
      </div>
      {/* B14 rule 32 — ONE sentence for this section, and it is the one thing a
          reader has to know to trust the figure: which date decided the month. */}
      <p className="pay-absent" role="note">
        {t("payments.badDebt.explainer")}
      </p>

      <div className="pay-toolbar">
        <div className="seg" role="group" aria-label={t("payments.badDebt.window.label")}>
          <button
            type="button"
            className={choice === "period" ? "seg-opt active" : "seg-opt"}
            aria-pressed={choice === "period"}
            onClick={() => {
              setChoice("period");
              setOpenReason(null);
            }}
          >
            {t("payments.badDebt.window.period")}
          </button>
          {/* The year option is DRAWN ONLY when the tenant has a financial year
              to draw it from. It is not disabled-with-a-reason here because the
              reason belongs to Settings → Regional and is stated below, once. */}
          {yearWindow !== null && (
            <button
              type="button"
              className={choice === "year" ? "seg-opt active" : "seg-opt"}
              aria-pressed={choice === "year"}
              onClick={() => {
                setChoice("year");
                setOpenReason(null);
              }}
            >
              {t("payments.badDebt.window.year")}
            </button>
          )}
        </div>
      </div>
      {yearWindow === null && (
        <AbsentFigure
          label={t("payments.badDebt.window.year")}
          reason={t("payments.badDebt.window.noFiscalYear")}
        />
      )}

      {report.isError ? (
        <p className="pay-absent" role="note">
          {apiErrorText(report.error, t)}
        </p>
      ) : report.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : report.data.count === 0 ? (
        <p className="pay-absent" role="note">
          {t("payments.badDebt.empty")}
        </p>
      ) : report.data.currency === null ? (
        // More than one currency in one window. The server serves no currency
        // and names the fault; a total across two currencies is a number that
        // is true of neither, so nothing is drawn in its place.
        <p className="pay-absent" role="note">
          {t("payments.badDebt.mixedCurrency")}
        </p>
      ) : (
        <BadDebtTables
          report={report.data}
          t={t}
          locale={props.locale}
          openReason={openReason}
          onOpenReason={setOpenReason}
          accountRows={accounts.data === undefined ? null : accounts.data.rows}
          accountsPending={accounts.isPending && openReason !== null}
        />
      )}

      {report.data !== undefined && (
        <BadDebtCaveats problems={report.data.problems} t={t} />
      )}
    </Panel>
  );
}

/**
 * What the report does not cover, CLOSED by default.
 *
 * **B14 rule 32** — *"a stated absence CLOSED by default"* — and this is the
 * shape `RunGap` and `AbsentFigure` both take: the heading stays in plain sight
 * so a reader knows there is something they have not been told, and the
 * sentences sit behind the disclosure rather than becoming four paragraphs on a
 * finance screen. The Product Owner said it four times in twenty minutes:
 * *"too much content - desctiption is too much for clark to read"*.
 *
 * The CODE is rendered through the catalogue and the server's English `detail`
 * is never printed (B8 — the server sends codes, the UI renders language), so
 * a caveat reads in the reader's own language in all eleven catalogues.
 */
export function BadDebtCaveats(props: {
  problems: readonly { code: string }[];
  t: Translator;
}) {
  if (props.problems.length === 0) {
    return null;
  }
  // ⚠ **THIS LIST PRINTED A RAW DOTTED KEY AT A FINANCE READER (`DEF-PAY-6328`).**
  // `t()` on a missing key returns the KEY, because `i18n` is configured
  // `keySeparator: false` — so a caveat code this catalogue has no words for
  // rendered as the literal text `payments.problem.<code>`. `problemWords` is
  // the one answer to that, shared with `ProblemList`: words, or nothing. It is
  // IMPORTED rather than written out again, which is B14 rule 43 — the reason
  // this family had five renderers and three different fallback behaviours.
  const lines = props.problems
    .map((problem) => ({ code: problem.code, words: problemWords(props.t, problem.code) }))
    .filter((line): line is { code: string; words: string } => line.words !== null);
  if (lines.length === 0) {
    return null;
  }
  return (
    <details>
      <summary className="fin-absent-value">{props.t("payments.badDebt.notCovered")}</summary>
      <ul className="fin-gap-list">
        {lines.map((line) => (
          <li key={line.code}>{line.words}</li>
        ))}
      </ul>
    </details>
  );
}

/**
 * The report's two cuts, its drill-down and its tie-out.
 *
 * ⚠ **THE DRILL-DOWN TAKES THE SERVER'S ROWS WHOLE, `account_id` INCLUDED, AND
 * THAT IS DELIBERATE.** An earlier draft mapped the id away in the panel so
 * this component "could not print one" — which sounds safer and is weaker: the
 * rule-31 guarantee then lived in a mapping nothing tested, and a test asserting
 * a uuid is absent from markup that never held one cannot fail. `WriteOffQueue
 * Table` takes the same shape for the same reason, and its own cell carries the
 * comment: the cell read `account_no ?? account_id` and printed a raw uuid to a
 * finance user (`DEF-2580`). The id is HERE, in the props, and the assertion
 * that it never reaches the markup is therefore a real one.
 */
export function BadDebtTables(props: {
  report: BadDebtReport;
  t: Translator;
  locale?: string;
  openReason: string | null;
  onOpenReason: (reason: string | null) => void;
  accountRows: readonly BadDebtAccountRow[] | null;
  accountsPending: boolean;
}) {
  const { report, t } = props;
  const currency = report.currency ?? "";
  return (
    <>
      <div className="pay-table-scroll">
        <PlainTable className="fin-table">
          <thead>
            <tr>
              <th scope="col">{t("payments.badDebt.col.reason")}</th>
              <th scope="col" className="fin-num">
                {t("payments.badDebt.col.writtenOff")}
              </th>
              <th scope="col" className="fin-num">
                {t("payments.badDebt.col.putBack")}
              </th>
              <th scope="col" className="fin-num">
                {t("payments.badDebt.col.net")}
              </th>
              <th scope="col" className="fin-num">
                {t("payments.badDebt.col.share")}
              </th>
            </tr>
          </thead>
          <tbody>
            {reasonRowsWithZeros(report).map((row) => {
              const share = sharePercentDisplay(row.share_percent);
              return (
                <tr key={row.reason}>
                  <td>
                    {/* The drill-down CS-26's own task row asks for: *"the bar's
                        own rows come from GET /bad-debt/accounts?f.reason=…"*.
                        A share of 72% is not actionable on its own and the first
                        question a reviewer asks a chart is which accounts. */}
                    <InlineLink
                      type="button"
                      aria-expanded={props.openReason === row.reason}
                      onClick={() =>
                        props.onOpenReason(props.openReason === row.reason ? null : row.reason)
                      }
                    >
                      {writeOffReasonLabel(row.reason, t)}
                    </InlineLink>
                  </td>
                  <td className="fin-num">
                    <MoneyCell amount={row.written_off} currency={currency} locale={props.locale} />
                  </td>
                  <td className="fin-num">
                    <MoneyCell amount={row.reversed} currency={currency} locale={props.locale} />
                  </td>
                  <td className="fin-num">
                    <MoneyCell amount={row.net} currency={currency} locale={props.locale} />
                  </td>
                  {/* A share of nothing renders as a stated absence, never as
                      `0.00%` — the server sends null for exactly that reason. */}
                  <td className="fin-num">
                    {share ?? <span className="pay-absent">{t("payments.badDebt.noShare")}</span>}
                  </td>
                </tr>
              );
            })}
            <tr className="fin-total-row">
              <td>{t("payments.badDebt.total")}</td>
              <td className="fin-num">
                <MoneyCell
                  amount={report.written_off}
                  currency={currency}
                  locale={props.locale}
                />
              </td>
              <td className="fin-num">
                <MoneyCell amount={report.reversed} currency={currency} locale={props.locale} />
              </td>
              <td className="fin-num">
                <MoneyCell amount={report.net} currency={currency} locale={props.locale} />
              </td>
              <td className="fin-num" />
            </tr>
          </tbody>
        </PlainTable>
      </div>

      {props.openReason !== null && (
        <div className="pay-table-scroll">
          {props.accountsPending || props.accountRows === null ? (
            <LoadingSkeleton variant="table" />
          ) : props.accountRows.length === 0 ? (
            <p className="pay-absent" role="note">
              {t("payments.badDebt.noAccounts")}
            </p>
          ) : (
            <PlainTable className="fin-table">
              <thead>
                <tr>
                  <th scope="col">{t("payments.badDebt.col.account")}</th>
                  <th scope="col">{t("payments.badDebt.col.decided")}</th>
                  <th scope="col" className="fin-num">
                    {t("payments.badDebt.col.amount")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {props.accountRows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {/* B14 rule 31 — the NUMBER, and a stated absence where the
                          account has none. There is no `?? row.account_id`
                          fallback here and there must never be one: that exact
                          fallback printed a raw uuid to a finance user one
                          screen along (`DEF-2580`). */}
                      {row.account_no ?? (
                        <span className="pay-absent">
                          {t("payments.writeOffQueue.noAccountNo")}
                        </span>
                      )}
                      {/* A reversing row is a correction, not a second write-off.
                          Saying so is what stops a reader adding it to the one
                          above it — the double-count the server nets away. */}
                      {row.reverses_write_off_id !== null && (
                        <span className="pay-sub">{t("payments.badDebt.putBackRow")}</span>
                      )}
                    </td>
                    <td>{row.approved_on ?? ""}</td>
                    <td className="fin-num">
                      <MoneyCell
                        amount={row.amount}
                        currency={row.currency}
                        locale={props.locale}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          )}
        </div>
      )}

      <BadDebtByMonth report={report} t={t} locale={props.locale} />
      <BadDebtTieOut report={report} t={t} locale={props.locale} />
    </>
  );
}

/** CS-26's second cut. Chronological — a trend read backwards is not a trend. */
export function BadDebtByMonth(props: {
  report: BadDebtReport;
  t: Translator;
  locale?: string;
}) {
  const { report, t } = props;
  const currency = report.currency ?? "";
  return (
    <div className="pay-table-scroll">
      <PlainTable className="fin-table">
        <thead>
          <tr>
            <th scope="col">{t("payments.badDebt.col.month")}</th>
            <th scope="col" className="fin-num">
              {t("payments.badDebt.col.writtenOff")}
            </th>
            <th scope="col" className="fin-num">
              {t("payments.badDebt.col.putBack")}
            </th>
            <th scope="col" className="fin-num">
              {t("payments.badDebt.col.net")}
            </th>
          </tr>
        </thead>
        <tbody>
          {report.by_month.map((row) => (
            <tr key={row.period}>
              <td>{row.period}</td>
              <td className="fin-num">
                <MoneyCell amount={row.written_off} currency={currency} locale={props.locale} />
              </td>
              <td className="fin-num">
                <MoneyCell amount={row.reversed} currency={currency} locale={props.locale} />
              </td>
              <td className="fin-num">
                <MoneyCell amount={row.net} currency={currency} locale={props.locale} />
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

/**
 * The books' own answer, beside this module's — never folded into one figure.
 *
 * **B14 rule 34** gives this one pair of words: money held here is *Recorded*
 * and money that has reached the general ledger is *In the books*. The label is
 * that phrase, in all eleven catalogues, and nothing here invents a synonym.
 */
export function BadDebtTieOut(props: { report: BadDebtReport; t: Translator; locale?: string }) {
  const { report, t } = props;
  if (!report.ledger.available || report.ledger.net === null) {
    // A reported state, never a zero: *"the books could not be read"* and *"the
    // books say nothing was written off"* are opposite answers.
    return (
      <AbsentFigure
        label={t("payments.badDebt.inTheBooks")}
        reason={t("payments.badDebt.booksUnavailable")}
      />
    );
  }
  return (
    <p className="fin-fact">
      <span className="fin-fact-label">{t("payments.badDebt.inTheBooks")}</span>
      <span className="fin-fact-value">
        <MoneyCell
          amount={report.ledger.net}
          currency={report.currency ?? ""}
          locale={props.locale}
        />
      </span>
      <span className="fin-fact-label">
        {report.ledger.agrees
          ? t("payments.badDebt.booksAgree")
          : t("payments.badDebt.booksDiffer")}
      </span>
    </p>
  );
}

export default BadDebtPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-059 §8 CS-26 · §10 P10 · §11 task 65 (sources: 12-governance/11-change-requests.md CR-059 §8 CS-26 + §11b's *"count the SCREENS"* · 06-backend/apps/payments/bad_debt.py + writeoffs_api.py, read field for field · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-020 · 04-docs/02-decisions/14-ui-conventions.md rules 21/31/32/34)
// generated: 2026-09-03 by the CR-059 W11 bad-debt-screen lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — badDebtPanel.test.tsx could not resolve this module before it existed; the verbatim failure is in the lane report. tsc✔ · vitest✔ · vite build✔ · run_gates✔ (no gate moved from its baseline)
// exceptions: (1) NO NEW CLASS AND NO TAILWIND UTILITY — neither `features/payments/*` nor `features/ledger/*` is on `route-b-migrated.txt` and the PO has ruled those migrate as their own work; a utility here would render as nothing at all (DEF-974) · (2) NO BY-SERVICE CUT — `OQ-1300` is raised and unanswered; the server names the gap on every result and this screen states it rather than approximating it · (3) THE TWO TOTALS ARE NEVER RECONCILED INTO ONE NUMBER — the ledger's figure is computed independently and shown beside this module's, because one number hiding a disagreement is how a control stops working · (4) NO CALENDAR-YEAR FALLBACK when the tenant has configured no financial year: the year-to-date option is not drawn and the reason is stated once, because guessing a financial year puts a figure under a heading nobody agreed to
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
