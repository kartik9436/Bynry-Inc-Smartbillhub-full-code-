// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-012 (accrual auto-reverse: day 1 of the next period, linked
//           both ways — TC-1 the mirror, TC-3 the Links column, TC-5 there is
//           no suppress path)
//           Screens: S56
// Rules:    BR-LED-005 (an accrual auto-reverses on day 1 of the NEXT period,
//           linked both ways) · BR-LED-006 (the close checklist asks the same
//           question) · BR-TEN-022 (the period comes from the tenant's fiscal
//           settings and is never stored) · BR-TEN-043 (event time is an INPUT)
//           · BR-SHL-020 (plain-language failure) · BR-SHL-023 (one money
//           formatting path) · CLAUDE.md rule 2 · rule 5
// Golden:   LE-4 — a Sep 30 accrual DR 1210 500.00 / CR 4100 500.00 takes an
//           Oct 1 mirror DR 4100 500.00 / CR 1210 500.00, and 1210 nets 0.00
// ───────────────────────────────────────────────────────
// The accruals that owe a mirror, and the button that posts them.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A HUMAN PRESSES THIS AT ALL
// ══════════════════════════════════════════════════════════════════════════
// BR-LED-005's reversal is a SWEEP, not a timer: an accrual whose day-1 mirror
// is due and missing gets one the next time the sweep runs. `apps/ledger/
// manual_je.run_accrual_auto_reversals` has been complete and LE-4-verified
// since 2026-08-15 and **this deployment has no job runner** (TD-17), so
// nothing was ever going to call it. Until something does, the honest surface
// is a button a finance officer presses during close, and this panel is it.
//
// It is safe to press twice, and that is a property of the engine rather than
// of this screen: the posting key is `journal_entry|<accrual id>|auto_reversed`
// — one string per accrual, forever — so a replay writes nothing and the second
// press reports `created: 0`.
//
// ══════════════════════════════════════════════════════════════════════════
// "DUE ON" IS THE TENANT'S CALENDAR, NOT THE BROWSER'S
// ══════════════════════════════════════════════════════════════════════════
// BR-LED-005 says *day 1 of the next PERIOD*, and BR-TEN-022 computes a period
// from the tenant's fiscal year and close cadence — a utility closing quarterly
// accrues into a quarter. Every date on this panel is the server's answer;
// nothing here adds a month to anything.
//
// ══════════════════════════════════════════════════════════════════════════
// A SKIPPED ROW IS REPORTED, NOT HIDDEN
// ══════════════════════════════════════════════════════════════════════════
// An accrual a human already reversed by hand cannot take a second mirror
// (`uq_journal_entries_reversal`). The sweep returns it with `skipped` set, and
// this panel prints the reason: a row that quietly disappeared from a close
// checklist is how somebody concludes the sweep is broken.
import { useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPendingAccruals, runAccrualAutoReversals } from "@/api/endpoints";
import type { AccrualSweepResult } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { MoneyCell } from "@/components/MoneyCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import "./finance.css";

export const accrualsQueryKey = (asOf: string) => ["ledger", "accruals", asOf] as const;

export interface AccrualsPanelProps {
  /** The tenant's own accounting day — the END of its current period. Its two
   *  callers reach it differently and both are correct: `GeneralLedgerPage`
   *  through `useFinancePeriod` and so `GET /shell/display`, `RevenueArPage`
   *  through its own `GET /settings/regional` (it needs `close_by`, which the
   *  shell read deliberately withholds — `DEF-SHL-4283`). Both compose the
   *  card from one selector, so they cannot disagree.
   *  Never `new Date()`: a sweep asked about the
   *  browser's today would run a different day for a clerk in Houston and a
   *  laptop still set to UTC (DEF-094's shape). */
  asOf: string;
  /** BR-TEN-043 — the instant the mirrors are stamped with, supplied by the
   *  caller so a double-click stamps one moment and a test can state it. */
  now: () => string;
  t: Translator;
  client?: ApiClient;
  locale?: string;
}

export function AccrualsPanel(props: AccrualsPanelProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const toast = useToast();
  const queryClient = useQueryClient();
  const [sweep, setSweep] = useState<AccrualSweepResult | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const pending = useQuery({
    queryKey: accrualsQueryKey(props.asOf),
    queryFn: () => getPendingAccruals(props.asOf, client),
    retry: false,
  });

  async function run() {
    setBusy(true);
    setFailure(null);
    try {
      const result = await runAccrualAutoReversals(
        { as_of: props.asOf, posted_at: props.now() },
        client,
      );
      setSweep(result);
      toast(t("finance.accruals.sweptToast", { count: result.created }));
      void queryClient.invalidateQueries({ queryKey: ["ledger"] });
    } catch (error) {
      setFailure(
        isApiError(error)
          ? apiErrorText(error, props.t)
          : t("finance.accruals.error.sweepFailed"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.accruals.title")}</h3>
      </div>
      <p className="fin-absent-reason" role="note">
        {t("finance.accruals.help")}
      </p>

      {pending.data === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : pending.data.rows.length === 0 ? (
        // An EMPTY list is a real and good answer here — every accrual that owed
        // a mirror has one — so it says that rather than drawing an empty table
        // that reads as a broken screen.
        <p className="fin-absent-reason" role="note">
          {t("finance.accruals.none", { asOf: props.asOf })}
        </p>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("finance.journal.col.number")}</th>
              <th scope="col">{t("finance.journal.col.date")}</th>
              <th scope="col">{t("finance.journal.col.memo")}</th>
              <th scope="col">{t("finance.accruals.col.dueOn")}</th>
              <th scope="col">{t("finance.journal.col.status")}</th>
            </tr>
          </thead>
          <tbody>
            {pending.data.rows.map((row) => (
              <tr key={row.entry_id}>
                {/* A posted entry with no JE- number means this tenant has no
                    journal number series seeded — the list says so on its own
                    `unavailable` channel; here the dash is that fact, never a
                    missing value invented as blank. */}
                <td>{row.je_number ?? "—"}</td>
                <td>{row.entry_date ?? ""}</td>
                <td>{row.memo ?? ""}</td>
                <td>{row.reversal_due_on}</td>
                <td>
                  <StatusPill tone="warning">{t("finance.accruals.overdue")}</StatusPill>
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}

      <div className="fin-params-actions">
        <Button
          variant="primary"
          data-testid="accruals-sweep"
          disabled={busy || (pending.data?.count ?? 0) === 0}
          onClick={() => void run()}
        >
          {busy ? t("states.working") : t("finance.accruals.run")}
        </Button>
      </div>

      {sweep !== null && (
        <div className="fin-notes">
          <p className="fin-absent-reason" role="note">
            {t("finance.accruals.sweepSummary", {
              created: sweep.created,
              considered: sweep.considered,
            })}
          </p>
          {sweep.rows.map((row) => (
            <p key={row.accrual_entry_id} className="fin-absent-reason" role="note">
              {row.skipped !== null
                ? t("finance.accruals.skipped", { reason: row.skipped })
                : t("finance.accruals.mirrored", { date: row.entry_date ?? row.due_on })}
              {sweep.currency !== null && (
                <>
                  {" "}
                  <MoneyCell
                    amount={row.amount}
                    currency={sweep.currency}
                    locale={props.locale}
                  />
                </>
              )}
              {row.date_note != null && ` ${t("finance.accruals.forwarded")}`}
            </p>
          ))}
        </div>
      )}

      {failure !== null && (
        <p className="fin-absent-reason" role="alert">
          {failure}
        </p>
      )}
    </Panel>
  );
}

export default AccrualsPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-011@eec4f0e (co-packet US-LED-012, same sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md · 09-ledger/02-business-rules.md BR-LED-005 · 09-ledger/08-worked-examples.md LE-4 · 04-docs/01-spec/11b-api-audit.md §2.10)
// generated: 2026-08-16 by story-coder (the ledger surface lane — BR-LED-005's sweep was complete, LE-4-verified and callable by nothing)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint✔ · vitest✔ · vite build✔ — the sweep's idempotence is proved on live Postgres in tests/test_us_led_011_journal_api.py (a second press reports created: 0)
// exceptions: (1) the sweep is HUMAN-triggered because this deployment has no job runner (TD-17); it is idempotent by posting key, so the button and a future scheduler cannot double-post · (2) `as_of` and `posted_at` are both the CALLER's (BR-TEN-043) — a panel that read the browser clock could not be asked about a day the host was down · (3) a SKIPPED row is printed with its reason: an accrual a human already reversed by hand cannot take a second mirror, and a row that vanished from a close checklist is how somebody concludes the sweep is broken
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
