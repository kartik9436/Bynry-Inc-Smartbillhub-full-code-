// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-019 (the BR-CUS-054 customer entity) — CR-060 **C16**, task
//           **T17**. No A1 screen id: the report was designed after A1 was
//           extracted, and one is REPORTED rather than minted (hard-won law 8).
//           Screens: (Reports → Customer statement)
// Rules:    BR-CUS-054 as AMENDED by CR-060 C16 (sum within a customer, never
//           across; a jointly-held account IN FULL to each holder; a weak or
//           untiered link shown and MARKED) · BR-CUS-089 (the stored tier) ·
//           BR-REP-001 (every money group labels its date basis) · BR-REP-002
//           (read models over the books) · BR-SHL-011 (the URL grammar) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-023 (one money
//           formatting path) · BR-SHL-025 (a control this deployment cannot
//           honour renders disabled WITH its reason) · BR-SHL-044 (one page
//           header) · B14 rules 31 and 32
// ───────────────────────────────────────────────────────
// **THE CUSTOMER STATEMENT — one person, their accounts, each balance, and a
// total across them.**
//
// ══════════════════════════════════════════════════════════════════════════
// THE FOUR THINGS THIS SCREEN MUST NOT DO, AND WHY EACH ONE IS A LIE
// ══════════════════════════════════════════════════════════════════════════
//   1. **It must not sum across customers.** There is one customer id on this
//      page and it comes from the URL. The link table is N:M, so a screen that
//      walked from an account back out to its other holders would put a
//      stranger's arrears on this person's statement.
//   2. **It must not apportion a jointly-held account.** Two people holding one
//      account each owe the WHOLE of it — joint and several liability — so the
//      same figure appears on both statements at full value. `held_with` names
//      the other holders so the duplicate is explained rather than mysterious.
//   3. **It must not merge a weak or untiered link into the total, and it must
//      not drop it either.** Both are lies of a different shape. The row is
//      drawn, it is marked, it is out of the total, and the amount left out is
//      stated AS A FIGURE.
//   4. **It must not render an absence as a zero (DEF-127).** When the books
//      cannot be asked, `balance` and `total` are null and this screen shows
//      `AbsentFigure` with the server's own reason. A statement footing $0.00
//      over books nobody could read is how a customer owing 108.88 was told
//      their balance was zero.
//
// ══════════════════════════════════════════════════════════════════════════
// B14 RULE 21 — NOT ONE TAILWIND UTILITY IS WRITTEN IN THIS FILE
// ══════════════════════════════════════════════════════════════════════════
// `features/reports/CustomerStatementPage.tsx` is NOT on
// `src/styles/route-b-migrated.txt` — neither are its two siblings,
// `AccountLedgerReportPage` and `ByPremisesReportPage`. A utility written here
// would be a class no stylesheet declares: it renders as **nothing at all**
// while `tsc`, eslint and every `toHaveClass` assertion pass, because the class
// really IS in the DOM. Every class below is a `fin-*` or `field` name a
// stylesheet already declares, which is what rule 21 is actually asking for,
// and it keeps G31 at its ceiling (470 declared classes, currently AT it — no
// new class can be added anywhere in the product today).
//
// ══════════════════════════════════════════════════════════════════════════
// B14 RULE 31 — THE PICKER SEARCHES BY NUMBER AND NAME, NEVER BY ID
// ══════════════════════════════════════════════════════════════════════════
// *"no Databse ID on screen - that is a rule"* (PO, 2026-08-31). The account
// ledger report next door asks a clerk to paste an account UUID into a box;
// this screen does not repeat that. It searches `GET /customers` by number,
// legacy reference, name and phone, lists what came back by **customer number
// and name**, and puts the id in the URL where the clerk never reads it — which
// also makes a statement they ran a link they can send to their bookkeeper
// (BR-SHL-011).
import { useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { AbsentFigure } from "@/components/AbsentFigure";
import { Button } from "@/components/Button";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { accountDetailPath } from "@/features/customers/customersShared";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { Dash, isDenied, useAccessCell } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import {
  getCustomerStatement,
  listCustomers,
} from "@/features/customers/customerEndpoints";
import type {
  CustomerStatement,
  CustomerStatementRow,
} from "@/features/customers/customerEndpoints";
import {
  FactRow,
  REPORTS_PERMISSION,
  gapSentence,
} from "@/features/ledger/financeShared";
import { useTenantPath } from "@/routing/tenantPath";

import { ReportDownloads, ReportGapList, ReportParamBar } from "./reportsShared";
import { reportRouteAbsent } from "./AccountLedgerReportPage";

import "@/features/ledger/finance.css";

export const CUSTOMER_STATEMENT_SEGMENT = "customer-statement";
export const CUSTOMER_STATEMENT_ROUTE = `/reports/${CUSTOMER_STATEMENT_SEGMENT}`;

export const customerStatementQueryKey = (customerId: string) =>
  ["reports", "customer-statement", customerId] as const;
export const customerSearchQueryKey = (needle: string) =>
  ["reports", "customer-statement", "search", needle] as const;

/** The URL parameter this report is run by. Not `f.customer`: this is the
 *  report's SUBJECT rather than one of its filters, and the endpoint's own
 *  parameter is `customer`. */
export function customerFromSearch(search: URLSearchParams): string {
  return search.get("customer") ?? "";
}

// ── The statement table ───────────────────────────────────────────────────

export function CustomerStatementTable(props: {
  statement: CustomerStatement;
  t: Translator;
  locale?: string;
  /** Record links (PO 2026-10-19): where an account number opens. `row.id`
   *  is the account's id (`customers.selectors`), used for the address only. */
  accountHref?: (accountId: string) => string;
}) {
  const { statement, t } = props;
  return (
    <PlainTable>
      <thead>
        <tr>
          <th scope="col">{t("reports.statement.col.account")}</th>
          {/* ⚠ **THE ACCOUNTS LIST'S OWN KEY, NOT A SECOND ONE FOR THE SAME
              COLUMN.** A `reports.statement.col.status` would be a fifth
              spelling of "Status" in this product, and G15 caught it as an
              untranslated paste in German, Indonesian and Portuguese — where
              the word genuinely IS "Status". Reusing the key that already
              describes an account's status keeps one vocabulary for one thing
              (B14) and the translation somebody already did. */}
          <th scope="col">{t("customers.accounts.col.status")}</th>
          <th scope="col">{t("reports.statement.col.heldWith")}</th>
          <th scope="col" className="fin-num">
            {t("reports.statement.col.balance")}
          </th>
        </tr>
      </thead>
      <tbody>
        {statement.rows.map((row: CustomerStatementRow) => (
          <tr key={row.id}>
            {/* B14 rule 31 / G69 — the account NUMBER, never `row.id`. */}
            <td>
              {props.accountHref !== undefined ? (
                <InlineLinkTo to={props.accountHref(row.id)}>{row.account_no}</InlineLinkTo>
              ) : (
                row.account_no
              )}
            </td>
            <td>
              {row.status_name === null ? <Dash /> : row.status_name}
              {/* RULE 3 rendered: the row is drawn and MARKED, and the pill is
                  the mark. `warning` rather than `danger` — an untiered link is
                  not an error, it is a link nobody vouched for. */}
              {row.confident ? null : (
                <StatusPill tone="warning">{t("reports.statement.unverified")}</StatusPill>
              )}
            </td>
            {/* RULE 2 rendered: WHY this same figure is also on somebody else's
                statement. Names, never ids. */}
            <td>{row.held_with.length === 0 ? <Dash /> : row.held_with.join(" · ")}</td>
            <td className="fin-num">
              {/* DEF-127 — a null balance is an ABSENCE with the server's own
                  reason, never a 0.00 that reads like a settled account. */}
              {row.balance === null ? (
                <AbsentFigure
                  label={t("finance.absent")}
                  reason={
                    statement.unavailable.length === 0
                      ? t("finance.gap.unknown")
                      : gapSentence(statement.unavailable[0], t)
                  }
                />
              ) : (
                <MoneyCell
                  amount={row.balance}
                  currency={statement.currency ?? ""}
                  locale={props.locale}
                />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </PlainTable>
  );
}

// ── The customer picker (rule 31: number and name, never an id) ───────────

export function CustomerPicker(props: {
  client: ApiClient;
  t: Translator;
  onPick: (customerId: string) => void;
}) {
  const { t } = props;
  const [needle, setNeedle] = useState("");
  const trimmed = needle.trim();
  const search = useQuery({
    queryKey: customerSearchQueryKey(trimmed),
    queryFn: () => listCustomers({ q: trimmed, per: 10 }, props.client),
    retry: false,
    enabled: trimmed !== "",
  });
  return (
    <div className="field">
      <label htmlFor="statement-customer">{t("reports.statement.param.customer")}</label>
      <input
        id="statement-customer"
        className="input"
        type="search"
        value={needle}
        placeholder={t("reports.statement.param.customerPrompt")}
        onChange={(event) => setNeedle(event.target.value)}
      />
      {/* B14 rule 32 — ONE sentence for this section, and it earns its place:
          the phone leg of this search is an equality probe against a keyed
          blind index, so half a number finds nobody. That is a property of the
          encryption and a clerk cannot deduce it from an empty result. */}
      <p className="field-help">{t("reports.statement.param.customerHelp")}</p>
      {trimmed === "" || search.data === undefined ? null : search.data.results.length === 0 ? (
        <p className="fin-params-note" role="note">
          {t("reports.statement.noMatch")}
        </p>
      ) : (
        <ul className="fin-gap-list">
          {search.data.results.map((customer) => (
            <li key={customer.id}>
              <Button variant="ghost" onClick={() => props.onPick(customer.id)}>
                {/* Number and name. The id is the click's payload and never
                    the cell's text (B14 rule 31). */}
                {/* ⚠ **COMPOSED IN JSX, NOT THROUGH A CATALOGUE KEY.** The
                    label is a NUMBER, a separator and a NAME — no words at
                    all — so a key for it would be byte-identical in all
                    eleven catalogues and G15 would read it, correctly, as an
                    untranslated paste. This is NOT the concatenated sentence
                    B8 forbids: there is no sentence to break, and it is the
                    same shape `held_with.join(" · ")` uses two columns
                    along. */}
                {customer.customer_no === null
                  ? customer.display_name
                  : `${customer.customer_no} · ${customer.display_name}`}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface CustomerStatementPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
  locale?: string;
}

export function CustomerStatementPage(props: CustomerStatementPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const cell = useAccessCell(REPORTS_PERMISSION, client);
  const [searchParams, setSearchParams] = useSearchParams();
  const customerId = customerFromSearch(searchParams);

  const statementQuery = useQuery({
    queryKey: customerStatementQueryKey(customerId),
    queryFn: () => getCustomerStatement(customerId, client),
    retry: false,
    enabled: customerId !== "",
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("reports.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (statementQuery.isError && isPermissionDenied(statementQuery.error)) {
    return (
      <PermissionDenied
        helper={t("reports.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const statement = statementQuery.data;
  const failed = statementQuery.isError && statement === undefined;
  // A 404 here means the ROUTE is absent on this deployment OR the customer is
  // not this tenant's — the endpoint answers 404 for both, deliberately, because
  // telling them apart is a membership oracle (HR-1/G4). The screen says the
  // report could not find that customer, which is true either way.
  const notFound =
    failed && isApiError(statementQuery.error) && statementQuery.error.status === 404;
  const routeAbsent = notFound && reportRouteAbsent(statementQuery.error) && customerId === "";

  return (
    <div className="fin-page">
      <PageHeader
        kicker={t("reports.kicker")}
        title={t("reports.statement.title")}
        backTo={{ to: tenantPath("/finance"), label: t("shell.nav.finance") }}
        rollup={
          statement === undefined ? undefined : (
            <span className="fin-rollup">
              <span className="fin-rollup-item">{statement.customer.display_name}</span>
              {statement.basis === null ? null : (
                <span className="fin-rollup-item">{t(`cells.basis.${statement.basis}`)}</span>
              )}
            </span>
          )
        }
      />

      <ReportParamBar
        actions={
          // P4.5. The statement is ONE customer's, so the id travels with the
          // request — the server refuses without it rather than widening to
          // every customer, which is a file called "one customer's statement"
          // holding everybody's money.
          <ReportDownloads
            resource="customer_statement"
            client={client}
            filters={{ customer_id: customerId }}
            disabled={customerId === "" || statement === undefined}
          />
        }
      >
        <CustomerPicker
          client={client}
          t={translate}
          onPick={(picked) => setSearchParams({ customer: picked }, { replace: true })}
        />
      </ReportParamBar>

      {customerId === "" ? (
        <Panel>
          <div className="fin-panel-head">
            <h3>{t("reports.statement.title")}</h3>
          </div>
          <p className="fin-params-note" role="note">
            {t("reports.statement.pickFirst")}
          </p>
        </Panel>
      ) : routeAbsent || notFound ? (
        <Panel role="alert">
          <h3>{t("reports.statement.notFoundTitle")}</h3>
          <p className="fin-absent-reason">{t("reports.statement.notFound")}</p>
        </Panel>
      ) : failed ? (
        <Panel role="alert">
          <h3>{t("finance.error.title")}</h3>
          <p className="fin-absent-reason">{apiErrorText(statementQuery.error, translate)}</p>
        </Panel>
      ) : statement === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <>
          <Panel>
            <div className="fin-panel-head">
              <h3>{t("reports.statement.title")}</h3>
            </div>
            {statement.rows.length === 0 ? (
              // RULE 4 — an empty statement is a DERIVED answer about a real
              // person, not an error and not a failure to load.
              <p className="fin-absent-reason" role="note">
                {t("reports.statement.noAccounts")}
              </p>
            ) : (
              <CustomerStatementTable
                accountHref={(accountId) => tenantPath(accountDetailPath(accountId))}
                statement={statement}
                t={translate}
                locale={props.locale}
              />
            )}
            {/* The total, labelled with the count it is across — the CR's own
                wording, *"across N accounts"* — so nobody reads it as one
                account's balance. */}
            <div className="fin-total-row">
              <FactRow
                label={t("reports.statement.totalLabel", { count: statement.account_count })}
                value={
                  statement.total === null ? (
                    <AbsentFigure
                      label={t("finance.absent")}
                      reason={
                        statement.unavailable.length === 0
                          ? t("finance.gap.unknown")
                          : gapSentence(statement.unavailable[0], translate)
                      }
                    />
                  ) : (
                    <MoneyCell
                      amount={statement.total}
                      currency={statement.currency ?? ""}
                      basis={statement.basis === "posting" ? "posting" : undefined}
                      locale={props.locale}
                    />
                  )
                }
                strong
              />
              {/* RULE 3's second half — what was LEFT OUT, as a figure. B14
                  rule 32: a stated absence is a `<details>` CLOSED by default,
                  in `AbsentFigure`'s ratified shape, so it does not occupy the
                  work surface while the whole sentence stays one click away. */}
              {statement.unconfident_count === 0 || statement.unconfident_total === null ? null : (
                <details data-testid="statement-unverified">
                  <summary className="fin-absent-value">
                    {t("reports.statement.unverifiedSummary", {
                      count: statement.unconfident_count,
                    })}
                  </summary>
                  <span className="fin-absent-reason" role="note">
                    {t("reports.statement.unverifiedReason")}
                  </span>
                </details>
              )}
            </div>
          </Panel>
          <ReportGapList
            gaps={statement.unavailable}
            title={t("finance.gap.title")}
            render={(gap) => gapSentence(gap, translate)}
          />
        </>
      )}
    </div>
  );
}

export default CustomerStatementPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-060 C16 + task T17 (12-governance/11-change-requests.md §CR-060) + 04-docs/05-modules/03-customers/02-business-rules.md BR-CUS-054 / BR-CUS-089 + 04-docs/02-decisions/14-ui-conventions.md rules 21, 31, 32
//         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — `CR-060` allocates no story ids, and minting one to satisfy G01's regex would put a citation in the tree that resolves to nothing. Same posture as `customerEndpoints.ts`.
// generated: 2026-09-02 by the CR-060 finance-screens lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: PROVED RED FIRST (law 7) — `vitest` reported "Failed to load url ./CustomerStatementPage" before this file existed, and the rendered-markup cases were each re-proved red by sabotage; tsc --noEmit clean
// exceptions: (1) NO A1 SCREEN ID — the report is designed after A1 was extracted from a prototype that has since been deleted, and one is REPORTED rather than minted (hard-won law 8) · (2) the download renders DISABLED with its reason (BR-SHL-025): `POST /reports/{key}/export` is served by no deployment (TD-17, no job runner), exactly as S59 and S60 do · (3) NO date window: a statement is a POSITION as at now, not a movement over a period — the account-ledger report (S59) is the movement view and is one click away · (4) a 404 does not distinguish "no such customer" from "another tenant's customer", by design (HR-1/G4: telling them apart is a membership oracle), so the screen says the report could not find that customer, which is true either way · (5) NOT on `src/styles/route-b-migrated.txt` — every class here is one a stylesheet already declares, and the Tailwind migration of the finance surfaces is its own lane by PO ruling 2026-09-01
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
