// ── Trace ──────────────────────────────────────────────
// Change:   CR-056 W5 task 25 — **a customers screen: list, search, one
//           person's accounts.** CR-056 §4 measured the absence: *"you reach a
//           person only through the accounts linked to them"*, and
//           `apps/customers/api.py`'s own header said the same from the other
//           side — *"no story owns a customer LIST or DETAIL endpoint yet"*.
// Rules:    BR-CUS-054 (one customer, many accounts — the landlord case) ·
//           BR-CUS-089 (the identity-match tier is STORED with its confirmer) ·
//           BR-CUS-092(c) (LAST FOUR ONLY — the full identifier never reaches a
//           list response) · BR-SHL-010 (an undeclared capability is not
//           rendered) · BR-SHL-011 (the URL grammar) · B14 rule 19 (the search
//           prompt names what it matches) · rule 20 (ONE table type) · rule 21
//           (Tailwind utilities, no stylesheet class) · rule 31 (no database id
//           is the visible value of a field) · rule 32 (one sentence per
//           section; no rule id in clerk copy)
// Tests:    07-frontend/src/features/customers/CustomersListPage.test.tsx
// Impacts:  06-backend `GET /api/{tenant}/customers` (live, this change) ·
//           App.tsx + routing/screenIds.ts (the route)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS FILE IS ON `src/styles/route-b-migrated.txt`, AND IT HAS TO BE.**
// B14 rule 21 says new UI is written in Tailwind utilities and adds NO class to
// a stylesheet — and the migration clause is PER FILE. A utility written in a
// file that is not on that list is a class no stylesheet declares: it renders
// as **nothing at all**, and `tsc`, eslint and every `toContain("flex")`
// assertion pass on it because the class IS in the DOM (DEF-974, DEF-901).
// Same handover as `RateScheduleDetail.tsx`: nothing was migrated away, the
// file is simply written in utilities from its first commit, so `G31`'s rule
// ("a class must be declared by a .css file") is false for it and
// `routeBUtilities.test.ts` asks the stricter question instead.
//
// ⚠ **WHAT THIS SCREEN DOES NOT DRAW, EACH WITH ITS REASON (BR-SHL-010):**
//
//   * **No `Export`.** `POST /exports` registers no `customers` resource, so
//     the capability is not rendered. Not drawn disabled either: BR-SHL-025 is
//     for a control THIS ROLE cannot use, not one the product does not have.
//   * **No create button.** A customer is brought into existence INSIDE an
//     account create (`services.link_customer`, called from every account door
//     since CR-056 W3) — the number is allocated inside that transaction so one
//     can never exist unnumbered. A `+ New customer` here would need a second
//     door onto that write, which is a rule nobody has made. The empty state's
//     CTA therefore points at the account wizard, which is where a person
//     actually gets created.
//   * **No KPI strip.** The server publishes no customer roll-up, and a strip
//     of numbers this screen derived in the browser would be a second
//     derivation of figures the accounts screen already owns.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { PageHeader } from "@/components/PageHeader";
import { RowActions, RowAction, RowActionLink } from "@/components/RowActions";
import { EyeIcon, PencilIcon } from "@/components/icons";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { InlineLinkTo } from "@/components/Surfaces";
import { useTenantPath } from "@/routing/tenantPath";
import type { TenantPath } from "@/routing/tenantPath";

import { ACCOUNTS_ROUTE, DASHBOARD_ROUTE, accountDetailPath } from "./customersShared";
import { CustomerEditDialog } from "./CustomerEditDialog";
import { listCustomers } from "./customerEndpoints";
import type { CustomerRow } from "./customerEndpoints";

export const CUSTOMERS_ROUTE = "/customers";

/** The screen id `TableConfig` keys its column preference on.
 *
 * ⚠ **A1 ALLOCATES NO ID FOR THIS SCREEN AND NONE IS MINTED HERE.** B18 §12.2
 * records that the reserved band S61–S90 is EXHAUSTED and that the next free
 * ground is S115, which is the PO's to allocate. The string below is a
 * PREFERENCE KEY, not a claim that A1 declares the id — the same posture
 * `REQUESTS_TABLE_SCREEN` takes one screen over, and `routing/screenIds.ts`
 * carries the real finding on the route row. */
export const CUSTOMERS_TABLE_SCREEN = "CUS-01";

export const CUSTOMER_KIND_FILTER = "kind";

/** B14 rule 19 (DEF-510): the prompt names WHAT the server really matches.
 *
 * ⚠ And it says the phone is matched WHOLE, because that is a real limit a
 * clerk would otherwise meet as a bug. The column is encrypted, so it is
 * searched through a keyed index that can only answer *equal or not* — half a
 * number finds nobody. */
const SEARCH_PLACEHOLDER = "customers.customer.list.searchPlaceholder";

export function customersTableConfig(
  t: (key: string, params?: Record<string, unknown>) => string,
  cells: {
    identity: (row: CustomerRow) => JSX.Element;
    accounts: (row: CustomerRow) => JSX.Element;
    actions: (row: CustomerRow) => JSX.Element;
  },
): TableConfig<CustomerRow> {
  return {
    screenId: CUSTOMERS_TABLE_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["customer_no", "display_name", "external_ref", "phone"],
    searchPlaceholder: SEARCH_PLACEHOLDER,
    filters: [
      {
        name: CUSTOMER_KIND_FILTER,
        label: t("customers.customer.list.kind"),
        options: [
          { value: "person", label: t("customers.customer.kind.person") },
          { value: "company", label: t("customers.customer.kind.company") },
        ],
      },
    ],
    defaultSort: { sort: "display_name", dir: "asc" },
    columns: [
      {
        key: "customer_no",
        label: t("customers.customer.col.number"),
        identity: true,
        sortable: true,
        // ⚠ B14 rule 31 — the NUMBER, never `row.id`. A customer created before
        // CR-030 W0's backfill may carry none, and that is a real state: it
        // renders as a stated blank rather than as the database key.
        cell: (row) =>
          row.customer_no === null || row.customer_no === "" ? (
            <span className="text-neutral-700">{t("customers.customer.list.noNumber")}</span>
          ) : (
            <span className="tabular-nums">{row.customer_no}</span>
          ),
      },
      {
        key: "display_name",
        label: t("customers.customer.col.name"),
        sortable: true,
        cell: (row) => <span>{row.display_name}</span>,
      },
      {
        key: "kind",
        label: t("customers.customer.col.kind"),
        cell: (row) => (
          <span className="text-sm uppercase tracking-wide" data-customer-kind={row.kind}>
            {t(`customers.customer.kind.${row.kind}`, { defaultValue: row.kind })}
          </span>
        ),
      },
      { key: "identity", label: t("customers.customer.col.identity"), cell: cells.identity },
      {
        key: "accounts",
        label: t("customers.customer.col.accounts"),
        numeric: true,
        cell: cells.accounts,
      },
      { key: "actions", label: t("customers.customer.col.actions"), cell: cells.actions },
    ],
  };
}

/**
 * The IDENTITY cell — what is on file, and never what it is.
 *
 * `BR-CUS-092(c)`: *"every read path renders last four only and the full value
 * is never in a list response"*. The server sends `held` and `last4` and no
 * more, so there is nothing here that COULD leak a number.
 *
 * ⚠ **`held` AND `last4` ARE TWO FACTS AND BOTH ARE DRAWN.** *Nothing on file*
 * and *•••• 6789* read nothing alike, and a clerk deciding whether they can
 * recognise a returning customer needs to tell them apart at a glance.
 */
export function IdentityCell(props: {
  row: CustomerRow;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { identity } = props.row;
  const marks: string[] = [];
  if (identity.ssn_last4) marks.push(`•••• ${identity.ssn_last4}`);
  if (identity.driving_licence_last4) marks.push(`•••• ${identity.driving_licence_last4}`);
  // CR-056 W2b — the COMPANY half. A business is identified by its Tax ID and
  // by nothing else, so before this line every company row read *Nothing on
  // file* however completely it had been identified.
  if (identity.tax_id_last4) marks.push(`•••• ${identity.tax_id_last4}`);
  if (marks.length === 0) {
    return (
      <span className="text-sm text-neutral-700" data-identity="none">
        {props.t("customers.customer.list.identityNone")}
      </span>
    );
  }
  return (
    <span className="tabular-nums text-sm" data-identity="held">
      {marks.join(" · ")}
    </span>
  );
}

/**
 * The ACCOUNTS cell — the count, and the numbers behind it.
 *
 * This is the landlord case made visible and it is the whole reason
 * `customer_accounts` is N:M (BR-CUS-054, US-CUS-019 TC-2: one reference on
 * three rows → ONE customer row). A person with no account at all is a real
 * state and reads as one.
 */
export function AccountsCell(props: {
  row: CustomerRow;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  return (
    <span className="tabular-nums" data-account-count={props.row.account_count}>
      {props.row.account_count}
    </span>
  );
}

/**
 * ONE ROW OPENS INTO THE ACCOUNTS THAT PERSON HOLDS — the third thing task 25
 * asks for, and the landlord case made visible (BR-CUS-054's N:M link).
 *
 * ⚠ **A SECOND TABLE TYPE IS NOT INVENTED FOR IT (B14 rule 20).** The
 * disclosure returns a `data-table`, so the row height, the header size and the
 * cell padding are the ones every other list in the product uses.
 *
 * ⚠ **EXPORTED, AND THAT IS WHAT MAKES IT TESTABLE FOR THE RIGHT REASON.** A
 * collapsed first paint renders none of this, so asserting the account numbers
 * against the page markup would pass on a screen whose disclosure is broken and
 * fail on one that works. The test calls this function — the same one the table
 * calls when a clerk opens a row.
 */
export function renderCustomerAccounts(
  row: CustomerRow,
  t: (key: string, params?: Record<string, unknown>) => string,
  // Record links (PO 2026-10-19): each account number opens that account.
  // REQUIRED, so a caller cannot draw the numbers as dead text by omission.
  path: TenantPath,
): JSX.Element {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>{t("customers.customer.col.accountNo")}</th>
          <th>{t("customers.customer.col.accountKind")}</th>
          <th>{t("customers.customer.col.accountStatus")}</th>
          <th>{t("customers.customer.col.matchedOn")}</th>
        </tr>
      </thead>
      <tbody>
        {row.accounts.map((entry) => (
          <tr key={entry.id}>
            <td className="tabular-nums">
              <InlineLinkTo to={path(accountDetailPath(entry.id))}>{entry.account_no}</InlineLinkTo>
            </td>
            <td>
              {t(`customers.customer.accountKind.${entry.kind}`, { defaultValue: entry.kind })}
            </td>
            <td>{entry.status_name ?? ""}</td>
            {/* ⚠ **A BLANK HERE IS A REAL STATE AND IT SAYS SO.** Every link an
                import wrote carries no tier — a legacy reference is a
                reconciliation key, not identity — and a bare empty cell would
                read as data we lost. */}
            <td>
              {entry.match_basis === null || entry.match_basis === "" ? (
                <span className="text-neutral-700">
                  {t("customers.customer.list.notMatched")}
                </span>
              ) : (
                entry.match_basis
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function customersQueryKey(state: TableRequestState): readonly unknown[] {
  return [
    "customers",
    state.q,
    state.page,
    state.per,
    state.sort,
    state.dir,
    state.filters[CUSTOMER_KIND_FILTER] ?? "",
  ];
}

export interface CustomersListPageProps extends RegionalProps {
  client?: ApiClient;
}

export function CustomersListPage(props: CustomersListPageProps) {
  const { t } = useTranslation();
  const translate = (key: string, params?: Record<string, unknown>): string => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const [params, setParams] = useSearchParams();
  // IS-8 / BR-SHL-023 — the date of birth renders in the TENANT's format, from
  // the one regional path every other date-bearing screen uses.
  const { dateFormat } = useRegional(props);
  // `BR-CUS-1054` — the row whose pencil is open. `null` is closed.
  const [editing, setEditing] = useState<CustomerRow | null>(null);

  const config = useMemo(
    () =>
      customersTableConfig(translate, {
        identity: (row) => <IdentityCell row={row} t={translate} />,
        accounts: (row) => <AccountsCell row={row} t={translate} />,
        actions: (row) => (
          <RowActions>
            {/* ⚠ **THE ROW OPENS AN ACCOUNT, NOT A CUSTOMER DETAIL SCREEN, AND
                THAT IS A STATED LIMIT RATHER THAN AN OVERSIGHT.** There is no
                customer detail SCREEN in this product — task 25 asks for the
                list, the search and one person's accounts, and the third is
                what the expanded row below serves. A person with no account has
                nothing to open, so the action is drawn disabled WITH its reason
                (BR-SHL-025) instead of onto a dead route. */}
            {row.accounts.length > 0 ? (
              <RowActionLink
                label={translate("customers.customer.action.openAccount")}
                icon={<EyeIcon />}
                to={tenantPath(accountDetailPath(row.accounts[0].id))}
              />
            ) : (
              <RowActionLink
                label={translate("customers.customer.action.openAccount")}
                icon={<EyeIcon />}
                to={tenantPath(ACCOUNTS_ROUTE)}
                reason={translate("customers.customer.action.noAccounts")}
              />
            )}
            {/* ⚠ **`BR-CUS-1054` — UNTIL 2026-09-13 THIS PENCIL DID NOT EXIST
                AND NEITHER DID THE ENDPOINT UNDER IT.** `GET /customers/{id}`
                was read-only, so a misspelt name, a wrong telephone number and
                a wrong email could not be corrected anywhere in the product.
                B14 rule 15: an ICON with a tooltip, never a text link. */}
            <RowAction
              label={translate("customers.customer.action.edit")}
              icon={<PencilIcon />}
              testId={`customer-edit-${row.id}`}
              onClick={() => setEditing(row)}
            />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  const state = parseTableParams(params, config);
  function onStateChange(next: TableRequestState): void {
    setParams(serializeTableParams(next, config), { replace: true });
  }

  const listQuery = useQuery({
    queryKey: customersQueryKey(state),
    queryFn: () =>
      listCustomers(
        {
          q: state.q,
          page: state.page,
          per: state.per,
          sort: state.sort,
          dir: state.dir,
          kind: state.filters[CUSTOMER_KIND_FILTER],
        },
        client,
      ),
  });

  return (
    <div>
      <PageHeader
        kicker={t("customers.customer.list.kicker")}
        title={t("customers.customer.list.title")}
        backTo={{
          to: tenantPath(DASHBOARD_ROUTE),
          label: t("customers.customer.list.back"),
        }}
      />

      <DataTable<CustomerRow>
        config={{
          ...config,
          // ⚠ **ONE ROW OPENS INTO THE ACCOUNTS THAT PERSON HOLDS**, which is
          // the third thing task 25 asks for. A second table type is not
          // invented for it (B14 rule 20): the disclosure returns a
          // `data-table`, so the row height, the header size and the cell
          // padding are the ones every other list in the product uses.
          renderExpanded: (row) => renderCustomerAccounts(row, translate, tenantPath),
        }}
        state={state}
        onStateChange={onStateChange}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isLoading}
        error={
          listQuery.isError
            ? {
                reason: t("customers.customer.list.loadFailed"),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={onStateChange} />
        }
        empty={{
          title: t("customers.customer.list.emptyTitle"),
          helper: t("customers.customer.list.emptyHelper"),
          ctaLabel: t("customers.customer.list.emptyCta"),
          onCta: () => navigate(tenantPath(ACCOUNTS_ROUTE)),
        }}
      />

      {/* ⚠ **MOUNTED, NOT MERELY IMPORTED** (CLAUDE.md hard-won law 2). A dialog
          behind a prop nothing passes renders nothing, every test passes, and
          the feature does not exist — which is what `G13` is for. The refetch
          is what makes a corrected phone findable in the box straight away. */}
      {editing === null ? null : (
        <CustomerEditDialog
          row={editing}
          t={translate}
          dateFormat={dateFormat}
          client={props.client}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void listQuery.refetch();
          }}
        />
      )}
    </div>
  );
}
// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-056 W5 task 25 (12-governance/11-change-requests.md §CR-056)
//         + BR-CUS-054 + BR-CUS-089 + BR-CUS-092(c) + BR-SHL-010/011
//         + B14 rules 19, 20, 21, 31, 32
//         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — `CR-056` allocates no story ids, and minting one to satisfy `G01`'s regex would put a citation in the tree that resolves to nothing. Same posture as `apps/customers/close_out.py`, which writes its DEF id instead
// generated: 2026-08-31 by the CR-056 W2/W3/W5 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc --noEmit clean · eslint --max-warnings 0 clean · vitest CustomersListPage.test.tsx 9/9 · src/features/customers 627 passed · routeBUtilities.test.ts 10/10 · G31 PASS (0 undeclared classes) · G13 PASS
// exceptions: E3 no `Export` control — `POST /exports` registers no `customers` resource, so BR-SHL-010 keeps the capability unrendered; not drawn disabled either, because BR-SHL-025 is for a control THIS ROLE cannot use rather than one the product does not have · E3 no `+ New customer` primary: a customer is brought into existence INSIDE an account create (the number is allocated in that transaction so one can never exist unnumbered), and a second door onto that write is a rule nobody has made — the empty state's CTA points at the account wizard instead · E3 no KPI strip: the server publishes no customer roll-up, and a strip this screen derived in the browser would be a second derivation of figures the accounts screen owns · E3 no customer DETAIL screen: task 25 asks for the list, the search and one person's accounts, and the third is the expanded row · E3 THE SCREEN DRAWS NO VISIBLE ID TAG — A1's reserved band S61–S90 is exhausted and S115 is the PO's to allocate, and r10 draws no customers surface at all; the finding is on the `routing/screenIds.ts` row rather than resolved by minting a number
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
