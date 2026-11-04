// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 (EP-TEN-07 SCOPE ADDENDUM — the S63–S71 rule-page cards; this is the
//           S71 card's per-authority table) · US-LED-014 (S41 dual-basis remittance — the
//           report that CONSUMES this setting and supplies its authority list)
//           Screens: S71 (Settings → Configure → Finance controls) · S41 (the consumer)
// Rules:    BR-LED-002 (BOTH bases always computed; a PER-AUTHORITY setting picks the one
//           each authority remits on) · BR-LED-013 (the remittance report's four columns) ·
//           BR-BIL-069 (each authority has its OWN 2200-nn liability account — so the
//           account IS the authority, and its CODE is this setting's key) ·
//           BR-TEN-022 (the accounting period is COMPUTED from fiscal settings, never
//           stored) · BR-SHL-035 (one Reference-data shell) · BR-TEN-024 (atomic per-page
//           save) · BR-SHL-020 (plain-language failure) · BR-SHL-025 (a control that cannot
//           act is disabled WITH its reason)
// ───────────────────────────────────────────────────────
// THE PER-AUTHORITY REMITTING-BASIS TABLE for
// `tax_remitting_basis_by_authority`.
//
// **Why this exists.** PO ruling 2026-08-12, verbatim: *"E Remit on what you
// BILLED, not what you collected - this is also correct"*, given alongside the
// allocation-sequence answer. Read together the two are one position: BOTH
// bases are lawful and WHICH applies is the customer's to set — which is what
// BR-LED-002 has said since it was confirmed, *"per-authority setting picks the
// remitting basis"*. The storage landed 2026-08-15 and
// `apps.ledger.reporting.remittance_by_authority` has read it ever since; no
// screen could set it. Hard-won law 2 again, and this file is the wiring.
//
// ══════════════════════════════════════════════════════════════════════════
// THERE IS NO DEFAULT, AND THAT IS THE RULE — NOT AN OMISSION
// ══════════════════════════════════════════════════════════════════════════
// The server seeds this map EMPTY and never fills it. LE-3 has State on
// COLLECTED and County on BILLED in the same month for the same tenant, so ANY
// seeded basis is wrong for one of them in its first month — hard-won law 3,
// where the unsafe option must be the one you type. This screen honours that in
// three ways that are each easy to get wrong:
//
//   1. an authority with no entry renders as **Not set** — a real, visible
//      state, never a pre-selected "billed" that a utility would scroll past;
//   2. clearing a choice DELETES the key rather than storing an empty string
//      (`withChoiceFor`), so "unset" survives the round trip;
//   3. the panel SAYS what happens if it is left unset, in words, above the
//      fold — the S41 report names that authority as still to be decided and
//      claims no filing figure for it.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THE AUTHORITY LIST COMES FROM — AND WHY IT IS NOT `GET /taxes`
// ══════════════════════════════════════════════════════════════════════════
// The setting is keyed by the authority's own **2200-nn GL account CODE**
// (BR-BIL-069, PO 2026-08-11: *"For each atheority have separate account and
// tagging"*), because the account IS the authority in the books.
//
// `GET /taxes` — the list Settings → Accounting already draws — carries the
// authority NAME and `liability_gl_account_id`, a **uuid**. It does not carry
// the account CODE, and `GET /ledger/accounts` (which would resolve one) is
// contracted at 11b §S56 and STILL UNSERVED, which is why that screen renders
// "mapped, unresolved" rather than a code. So a table built on `GET /taxes`
// could not produce this setting's key at all today. That is a fact about
// OQ-194's option (a), reported rather than argued: see the README.
//
// `GET /finance/taxes` — S41's own read, SERVED — returns one row per
// tax-payable account with `code`, `name` and the stored `remitting_basis`. It
// is the report that CONSUMES this setting, so the rows a utility chooses on
// here are exactly the rows they will read the choice back on. One list, not a
// third one to drift.
//
// **The period.** That endpoint requires `from`/`to` because a remittance table
// is always *for a period*. This screen has no period of its own, so it passes
// the tenant's OWN accounting period (BR-TEN-022 — computed from fiscal
// settings and served on `GET /settings/regional` as `current_period`), never a
// month off the browser's clock. **The row SET does not depend on the window**
// — `remittance_by_authority` lists every tax-payable account in the chart and
// only the MONEY columns, which this screen does not draw, are of the period —
// so the window here is a required argument and not a filter on what is shown.
// With no fiscal calendar configured the table says so and offers nothing,
// which is the honest state: a list of authorities this screen could not read
// is not an empty list of authorities.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getRemittanceByAuthority } from "@/api/endpoints";
import type { AuthorityRemittanceRow, CurrentPeriod } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { SelectField } from "@/components/FormModal";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { LoadingSkeleton } from "@/components/StateFrame";

import { basisMapFromDraft, basisMapToDraft, withChoiceFor } from "./settingsRulePages";
import type { RuleParam, RulePage } from "./settingsRulePages";
import { apiErrorText } from "./settingsShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** A basis VALUE renders through the catalog too (no raw enum on screen). */
export function basisLabelKey(param: RuleParam, value: string): string {
  return `settings.rules.choice.${param.key}.${value}`;
}

/** The query key's period segment. "" when there is no period to read one for. */
export function periodKeyOf(period: CurrentPeriod | null): string {
  return period === null ? "" : `${period.start}|${period.end}`;
}

/**
 * The authorities this tenant has NOT chosen a basis for, by account code.
 *
 * Read off the DRAFT rather than off the server's `remitting_basis` column, so
 * the count answers *what you are about to save*, not *what you saved last
 * time*. Both are true statements and only one of them is useful while editing.
 */
export function unsetAuthorities(
  rows: readonly AuthorityRemittanceRow[],
  chosen: Record<string, string>,
): string[] {
  return rows.filter((row) => (chosen[row.code] ?? "") === "").map((row) => row.code);
}

/**
 * The authorities set to COLLECTED — the basis this product cannot compute yet.
 *
 * **CR-060 C19 / task T7e: warn where the basis is CHOSEN, not where it is
 * filed.** Both bases are lawful and the choice is the customer's (BR-LED-002),
 * but only one of them is currently *answerable*: the collected figure asks how
 * much tax sits inside the payments received, and `allocations` records a
 * payment, an invoice and an amount — **not which charge classes the money
 * met**. So `GET /finance/taxes` correctly returns the collected column ABSENT
 * with its reason rather than showing the billed figure, which would have a
 * utility remit tax on money nobody has paid.
 *
 * Today a tenant makes that choice here and finds out in a **filing month**.
 * This is the same fact, said at the moment of choosing. It is a WARNING and
 * not a refusal: the choice is legitimate, it is recorded, and it starts
 * producing a figure the day the per-class breakdown lands (C19 / task T7d).
 *
 * Read off the DRAFT for the same reason `unsetAuthorities` is — it answers
 * *what you are about to save*, which is the useful one while editing.
 */
export function collectedAuthorities(
  rows: readonly AuthorityRemittanceRow[],
  chosen: Record<string, string>,
): string[] {
  return rows.filter((row) => (chosen[row.code] ?? "") === "collected").map((row) => row.code);
}

// ── The field ──────────────────────────────────────────────────────────────

export function RemittingBasisField(props: {
  page: RulePage;
  param: RuleParam;
  value: string | boolean;
  error?: string;
  readOnly: boolean;
  period: CurrentPeriod | null;
  client?: ApiClient;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  const { param, page, period } = props;
  const client = props.client ?? api;
  const chosen = basisMapFromDraft(props.value);

  const authoritiesQuery = useQuery({
    queryKey: queryKeys.remittanceByAuthority(periodKeyOf(period)),
    queryFn: () =>
      getRemittanceByAuthority(
        // Non-null by `enabled` below; stated rather than asserted away.
        { from: period?.start ?? "", to: period?.end ?? "" },
        client,
      ),
    enabled: period !== null,
    staleTime: REFERENCE_STALE_MS,
    // A period the server refuses is not a flaky network; retrying only delays
    // the honest answer (the same posture the finance screens take).
    retry: false,
  });

  const rows = authoritiesQuery.data?.rows ?? [];
  const unset = unsetAuthorities(rows, chosen);
  const collected = collectedAuthorities(rows, chosen);

  function choose(code: string, basis: string): void {
    props.onChange(basisMapToDraft(withChoiceFor(chosen, code, basis)));
  }

  return (
    <div className="settings-rule-field">
      <h4 className="settings-example-title">
        {t(`settings.rules.${page.card}.${param.key}`)}
      </h4>
      {/* `DEF-TEN-6935` — the rule id that used to close this line is gone and
          nothing replaces it: B14 rule 32 clause 4 bans it, and rule 33 puts
          the *why* it was answering at zero words on screen. */}
      <p className="field-help">{t("settings.rules.basis.help")}</p>
      {/* Said BEFORE the table, not discovered after a save. There is no
          default and there is not going to be one; this is what "unset" costs
          and what it buys. */}
      <Note>{t("settings.rules.basis.unsetWarning")}</Note>

      {props.error !== undefined && (
        <RefusalStrip role="alert">
          {props.error}
        </RefusalStrip>
      )}

      {period === null ? (
        // BR-TEN-022: no fiscal calendar, no period, no authority list. Named,
        // never a silently empty table.
        <p className="settings-warning" role="status">
          {t("settings.rules.basis.periodMissing")}
        </p>
      ) : authoritiesQuery.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : authoritiesQuery.data === undefined ? (
        // BR-SHL-020: the server's own words, and an explicit statement that
        // nothing already saved has moved — a failed READ is not a lost choice.
        <p className="settings-warning" role="status">
          {`${t("settings.rules.basis.failed")} ${apiErrorText(authoritiesQuery.error, t)}`}
        </p>
      ) : rows.length === 0 ? (
        <Note>{t("settings.rules.basis.empty")}</Note>
      ) : (
        <>
          <table className="settings-table" aria-label={t("settings.rules.basis.tableLabel")}>
            <thead>
              <tr>
                <th>{t("settings.rules.basis.colAuthority")}</th>
                <th>{t("settings.rules.basis.colBasis")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const value = chosen[row.code] ?? "";
                return (
                  <tr key={row.account_id}>
                    <td>
                      <span className="cell-num">{row.code}</span> {row.name}
                      {value === "" && (
                        // The unset state, ON the row a person is reading —
                        // not only in a count underneath the table.
                        <span className="settings-locked"> {t("settings.rules.basis.unset")}</span>
                      )}
                    </td>
                    <td>
                      <SelectField
                        id={`${param.key}-${row.code}`}
                        label={`${t("settings.rules.basis.colBasis")} — ${row.name}`}
                        value={value}
                        onChange={(next) => !props.readOnly && choose(row.code, next)}
                        options={(param.choices ?? []).map((choice) => ({
                          value: choice,
                          label: t(basisLabelKey(param, choice)),
                        }))}
                        // The leading empty option IS "Not set", so clearing a
                        // choice is as reachable as making one.
                        placeholder={t("settings.rules.basis.unset")}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {unset.length > 0 && (
            <Note>
              {t("settings.rules.basis.unsetCount", {
                count: unset.length,
                codes: unset.join(", "),
              })}
            </Note>
          )}
          {/* CR-060 C19 / task T7e — said HERE, where the basis is chosen,
              rather than in a filing month where it is discovered. One
              sentence, no rule id and no internal code (B14 rule 32); the
              authorities are named by the account number a clerk already reads
              in the table above. It is a warning and not a refusal — the choice
              is lawful and is saved. */}
          {collected.length > 0 && (
            <Note>
              {t("settings.rules.basis.collectedNotComputable", {
                count: collected.length,
                codes: collected.join(", "),
                defaultValue:
                  "We cannot work out the collected figure yet, so the {{codes}} return will show" +
                  " no amount until we can. Your choice is saved and nothing else changes.",
              })}
            </Note>
          )}
        </>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07, whose SCOPE ADDENDUM adds the S63–S71 cards; co-packet EP-LED-05@0000000 for US-LED-014's dual-basis table, a PLACEHOLDER hash because BR-LED-002's per-authority setting only acquired storage on 2026-08-15 — reported, not invented)
// generated: 2026-08-15 by story-coder (settings-screens lane — the S71 per-authority table the PO's ruling of 2026-08-12 asked for and the 2026-08-15 backend lane left without a screen)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — the write is the existing PUT /settings/finance-controls and the read is the served GET /finance/taxes; this lane adds no route) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report — tsc✔ eslint --max-warnings 0✔ vitest✔ (PROVED RED first: with a `?? "billed"` standing in for the unset state the table pre-selected a basis for every authority and the unset assertions failed) · run_gates 19 PASS / 1 FAIL (G8 on another lane's apps/billing/backbill.py — this lane's baseline, unchanged)
// exceptions: E1 **OQ-194 is OPEN and this file implements one of its two options.** The question is where the control LIVES: (a) an extra column on the Settings → Accounting tax table, or (b) its own control on Finance controls beside the storage. This lane built (b), for two reasons it did not decide: the PO ruled on 2026-08-12 that GL configuration lives *"under Configure"* (OQ-151) and Finance controls is under Configure while Accounting is a top-level tab, and — the fact that settles it in code rather than in taste — option (a) is NOT IMPLEMENTABLE TODAY, because the Accounting table has no account CODE to key the setting by and `GET /ledger/accounts` is still unserved. REPORTED for the PO to close or overturn; moving it later is a component move, not a data change · E3 the authority list is read from `GET /finance/taxes`, a PERIOD report, because it is the only served read that carries the 2200-nn account codes this setting is keyed by. The row set does not vary with the window (the money columns do, and this screen draws none) — stated in the header, not assumed · E4 with no fiscal calendar on Settings → Company → Regional there is no period, so the table cannot be drawn and says so; a tenant in that state cannot set a basis until the calendar is set — REPORTED · E3 there is no DOM in this suite (the project's posture), so the choice is proved at the pure functions and through renderToStaticMarkup over a seeded cache, not at the pointer
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
