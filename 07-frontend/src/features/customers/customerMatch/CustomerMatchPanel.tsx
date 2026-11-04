// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.23 (lane MVI-WIZ-CUST, 2026-10-05) — the answer to
//           *Search customer ID* on the move-in's Customer step.
// Change:   CR-181-BRC10 F2 (lane REOPEN, 2026-10-13) — two weaker levels,
//           *Same name and phone* (`name_phone`) and *Lived here last*
//           (`last_occupant`). PO verbatim: *"Q1 C both"*.
// Change:   lane CF-1 (2026-10-18), task 4 — **THE STACKED MATCH CARDS ARE
//           REPLACED BY ONE RESULTS TABLE**, PO verbatim *"this is correct"* on
//           the design drawn at https://claude.ai/artifact/Ux4grKQ3jRhJ4S48P8zHwo
//           and captured as images 01, 10 and 11 of
//           `04-docs/05-modules/03-customers/wireframes/customer-forms-2026-10-18/`
//           (read as IMAGES, B14 rule 42). Decision log *"2026-10-18 — CUSTOMER
//           DATA AND UI CONSISTENT ACROSS THE CREATE SCREENS"*, *Same day, PO
//           confirmed two designs*: one table, strongest first, columns (open
//           arrow) · Match (one coloured icon; strength and what agreed in the
//           tooltip) · Customer (name + number) · Date of birth · Phone (last 4)
//           · Accounts (count · open) · Owed (red when due) · Actions (icons:
//           link, view customer, not them). The arrow opens the customer's
//           accounts; Link collapses the table to one *Linked* line with an
//           unlink icon; none linked → a new customer ID on complete.
// Rules:    PO ruling 2026-10-05 (*"if match based on our logic then we say
//           match if it is not then we dont say it"*) — the levels are the
//           SERVER's (`found`, `possible`, `name_phone`, `last_occupant`) and
//           nothing here invents one · BR-CUS-019 (advisory — the clerk
//           decides) · BR-CUS-092 (no identifier shown; the phone as its last
//           four) · B14 rules 15 (row actions are icons), 20 (one table type),
//           31 (the id is a handle), 33, 43, 44 · DEF-127 (the outstanding
//           figures are the ledger's, shown, never moved or summed here)
// Tests:    customerForm/customerMatchTable.dom.test.tsx ·
//           moveInWizard/StepCustomer.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ButtonLink } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { ChevronDownIcon, ChevronRightIcon, EyeIcon, HomeIcon, LinkIcon, UnlinkIcon } from "@/components/icons";
import { formatMoney } from "@/components/MoneyCell";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { useTenantPath } from "@/routing/tenantPath";
import type { Translator } from "@/features/tenancy/settingsShared";

import { accountDetailPath } from "../customersShared";
import type {
  CustomerSearchAccount,
  CustomerSearchResult,
  CustomerSearchRow,
} from "../customerEndpoints";

/** The customers list, which is the product's customer screen (there is no
 *  `/customers/{id}` page — `searchDestinations.ts`), searched for one number. */
const CUSTOMERS_LIST = "/customers";

/** The facts that agreed, in the clerk's words — *Name, date of birth and
 *  SSN match.* Built from the server's `agreed` codes, never its English
 *  `basis` (B14 rule 35: a catalogue speaks every language). */
export function agreedSentence(agreed: readonly string[], t: Translator, locale: string): string {
  const words = agreed.map((code) => t(`customers.moveIn.customer.match.fact.${code}`));
  if (words.length === 0) return "";
  let list: string;
  try {
    list = new Intl.ListFormat(locale, { type: "conjunction" }).format(words);
  } catch {
    list = words.join(", ");
  }
  const sentence = t("customers.moveIn.customer.match.agreed", { facts: list });
  return sentence.charAt(0).toLocaleUpperCase(locale) + sentence.slice(1);
}

function moneyOrNull(amount: string | null, currency: string | null, locale: string): string | null {
  if (amount === null || currency === null) return null;
  return formatMoney(amount, currency, locale);
}

/** A decimal string the ledger served is above zero (hard rule 2 — compared as
 *  text, never parsed into a float). */
function isDue(amount: string | null | undefined): boolean {
  if (amount === null || amount === undefined) return false;
  const trimmed = amount.trim();
  if (trimmed.startsWith("-")) return false;
  return /[1-9]/.test(trimmed);
}

/** Each level's word — one key per level (`CR-181-BRC10`). */
const VERDICT_WORD: Record<CustomerSearchRow["verdict"], string> = {
  found: "customers.moveIn.customer.match.found",
  possible: "customers.moveIn.customer.match.possible",
  name_phone: "customers.moveIn.customer.match.name_phone",
  last_occupant: "customers.moveIn.customer.match.last_occupant",
};

/** How many of a customer's accounts are open — the server's count when it
 *  sent one, else the rows it drew (a parked link carries neither). */
function openCount(row: CustomerSearchRow): number | null {
  const accounts = row.accounts;
  if (accounts === null) return null;
  if (typeof accounts.open_count === "number") return accounts.open_count;
  return accounts.rows.filter((account) => account.closed_at === null).length;
}

/** The match column's one coloured icon, with the strength and what agreed
 *  in its tooltip AND its accessible name (image 01). */
function MatchMark(props: { row: CustomerSearchRow; t: Translator; locale: string }) {
  const { row, t } = props;
  const strong = row.verdict === "found";
  const lived = row.verdict === "last_occupant" || row.last_occupant === true;
  const words = [
    t(VERDICT_WORD[row.verdict]),
    row.verdict !== "last_occupant" && row.last_occupant === true
      ? t("customers.moveIn.customer.match.last_occupant")
      : null,
    agreedSentence(row.agreed, t, props.locale),
  ].filter((part): part is string => part !== null && part !== "");
  const label = words.join(" · ");
  return (
    <span
      className="inline-flex items-center gap-1.5"
      role="img"
      aria-label={label}
      title={label}
      data-match-mark={row.verdict}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-2.5 w-2.5 rounded-full ${strong ? "bg-success-700" : "bg-warning-700"}`}
      />
      {lived ? (
        <span aria-hidden="true" className="inline-flex text-info-700" data-match-lived-here="">
          <HomeIcon />
        </span>
      ) : null}
    </span>
  );
}

function AccountsSubTable(props: {
  accounts: NonNullable<CustomerSearchRow["accounts"]>;
  t: Translator;
  locale: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { accounts, t, locale } = props;
  const tenantPath = useTenantPath();
  const currency = accounts.currency;
  const state = (account: CustomerSearchAccount) =>
    account.closed_at !== null
      ? t("customers.moveIn.customer.match.closedOn", {
          date: formatDate(account.closed_at, props.timeZone, props.dateFormat),
        })
      : account.status_name;
  const address = (account: CustomerSearchAccount) =>
    account.address === null
      ? "—"
      : [account.address.line1, account.address.unit_label].filter((part) => part).join(" · ");
  if (accounts.rows.length === 0) {
    return (
      <p className="m-0 text-sm text-neutral-700" data-match-summary="">
        {t("customers.moveIn.customer.match.accounts", { count: accounts.count })}
      </p>
    );
  }
  return (
    <PlainTable className="bg-neutral-100" data-match-accounts="">
      <thead>
        <tr>
          <th scope="col">{t("customers.moveIn.customer.match.col.account")}</th>
          <th scope="col">{t("customers.moveIn.customer.match.col.address")}</th>
          <th scope="col">{t("customers.moveIn.customer.match.col.state")}</th>
          <th scope="col" className="text-right">
            {t("customers.moveIn.customer.match.col.outstanding")}
          </th>
        </tr>
      </thead>
      <tbody>
        {accounts.rows.map((account) => {
          const owed = moneyOrNull(account.outstanding, currency, locale);
          return (
            <tr key={account.id} data-match-account={account.account_no}>
              <td>
                <InlineLinkTo to={tenantPath(accountDetailPath(account.id))}>
                  {account.account_no}
                </InlineLinkTo>
              </td>
              <td>{address(account)}</td>
              <td>{state(account)}</td>
              <td className="text-right tabular-nums">
                {owed === null
                  ? "—"
                  : isDue(account.outstanding)
                    ? t("customers.moveIn.customer.match.due", { amount: owed })
                    : owed}
              </td>
            </tr>
          );
        })}
      </tbody>
    </PlainTable>
  );
}

/** *Accounts* — `2 · 0 open`, or `0`. */
function accountsCell(row: CustomerSearchRow, t: Translator): string {
  if (row.accounts === null) return "—";
  const count = row.accounts.count;
  if (count === 0) return "0";
  const open = openCount(row);
  return open === null
    ? String(count)
    : t("customers.moveIn.customer.match.countOpen", { count, open });
}

/** The phone as its last four — `•••-0182` (BR-CUS-092: no full number). */
function phoneCell(row: CustomerSearchRow): string {
  return row.phone_last4 ? `•••-${row.phone_last4}` : "—";
}

/** The one-line *Linked* state (image 11) — who, by number and name, the
 *  level and what agreed, an unlink icon, and what their accounts owe. */
function LinkedLine(props: {
  row: CustomerSearchRow;
  onUnlink: () => void;
  t: Translator;
  locale: string;
}) {
  const { row, t, locale } = props;
  const accounts = row.accounts;
  const owedTotal = accounts === null ? null : moneyOrNull(accounts.outstanding_total, accounts.currency, locale);
  const facts = [
    row.display_name,
    row.customer_no,
    t(VERDICT_WORD[row.verdict]),
    agreedSentence(row.agreed, t, locale),
  ].filter((part): part is string => part !== null && part !== "");
  return (
    <div
      className="mt-4 flex flex-col gap-2 border border-success-700 bg-success-100 p-4"
      data-customer-match="linked"
      data-match-block="linked"
    >
      <div className="flex flex-wrap items-center gap-3">
        <StatusPill tone="success">{t("customers.moveIn.customer.match.linked")}</StatusPill>
        <span className="font-heading font-semibold" data-match-customer="">
          {facts.join(" · ")}
        </span>
        <span className="ml-auto">
          <RowAction
            label={t("customers.moveIn.customer.match.unlink")}
            icon={<UnlinkIcon />}
            danger
            onClick={props.onUnlink}
          />
        </span>
      </div>
      {accounts === null ? null : (
        <p className="m-0 text-sm text-neutral-700" data-match-summary="">
          {owedTotal === null
            ? t("customers.moveIn.customer.match.accounts", { count: accounts.count })
            : t("customers.moveIn.customer.match.accountsOwed", {
                count: accounts.count,
                amount: owedTotal,
              })}
        </p>
      )}
    </div>
  );
}

/**
 * The search's answer, as every create screen draws it.
 *
 * ⚠ **THE LINK IS THE CLERK'S, AND IT IS REMEMBERED BY THE HOST, NOT HERE**
 * (`linkedId`, `dismissed`): a step unmounts on the way forward, and a *Not
 * them* held in local state would ask the same question again on Back —
 * `NewConnectOwnerMatch`'s own lesson. Only which row's accounts are OPEN is
 * local: losing it on Back costs one click.
 */
export function CustomerMatchPanel(props: {
  result: CustomerSearchResult | null;
  pending: boolean;
  failed: boolean;
  linkedId: string | null;
  /** The linked customer as it was when linked — drawn even when no search
   *  has run this session (a resumed draft). */
  linkedRow: CustomerSearchRow | null;
  dismissed: readonly string[];
  onLink: (row: CustomerSearchRow) => void;
  onUnlink: () => void;
  onNotThem: (row: CustomerSearchRow) => void;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t: i18nT, i18n } = useTranslation();
  const t: Translator = (key, params) => i18nT(key, params);
  const locale = i18n.language;
  const tenantPath = useTenantPath();
  const [open, setOpen] = useState<readonly string[]>([]);

  if (props.linkedId !== null && props.linkedRow !== null) {
    return <LinkedLine row={props.linkedRow} onUnlink={props.onUnlink} t={t} locale={locale} />;
  }
  if (props.pending) {
    return (
      <p className="mt-4 mb-0 text-sm text-neutral-700" data-customer-match="pending">
        {t("states.loading")}
      </p>
    );
  }
  if (props.failed) {
    return (
      <p role="alert" className="field-error mt-4 mb-0" data-customer-match="failed">
        {t("customers.moveIn.customer.match.failed")}
      </p>
    );
  }
  const result = props.result;
  if (result === null) return null;
  if (result.result === null) {
    return (
      <p className="mt-4 mb-0 text-sm text-neutral-700" data-customer-match="nothing">
        {t("customers.moveIn.customer.match.needMore")}
      </p>
    );
  }
  const shown = result.customers.filter((row) => !props.dismissed.includes(row.id));
  if (shown.length === 0) {
    // `new` — or every customer our rule showed was *Not them*: either way a
    // new customer number is given at Complete.
    return (
      <div
        className="mt-4 flex items-center gap-3 border border-divider bg-surface p-4"
        data-customer-match="new"
      >
        <StatusPill tone="info">{t("customers.moveIn.customer.match.new")}</StatusPill>
        <span>{t("customers.moveIn.customer.match.newLine")}</span>
      </div>
    );
  }
  const toggle = (id: string) =>
    setOpen((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));
  const anyLived = shown.some((row) => row.verdict === "last_occupant" || row.last_occupant === true);
  const anyPossible = shown.some((row) => row.verdict !== "found");

  return (
    <div
      className="mt-4 flex flex-col gap-3 border border-divider bg-surface p-4"
      data-customer-match={result.result}
    >
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="font-heading font-semibold" data-match-count="">
          {t("customers.moveIn.customer.match.count", { count: shown.length })}
        </span>
        <span className="text-sm text-neutral-700">{t("customers.moveIn.customer.match.strongestFirst")}</span>
      </div>
      <PlainTable data-match-table="">
        <thead>
          <tr>
            <th scope="col">
              <span className="sr-only">{t("customers.moveIn.customer.match.col.open")}</span>
            </th>
            <th scope="col">{t("customers.moveIn.customer.match.col.match")}</th>
            <th scope="col">{t("customers.moveIn.customer.match.col.customer")}</th>
            <th scope="col">{t("customers.moveIn.customer.match.col.dob")}</th>
            <th scope="col">{t("customers.moveIn.customer.match.col.phone")}</th>
            <th scope="col">{t("customers.moveIn.customer.match.col.accounts")}</th>
            <th scope="col" className="text-right">
              {t("customers.moveIn.customer.match.col.owed")}
            </th>
            <th scope="col">{t("customers.moveIn.customer.match.col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((row) => {
            const isOpen = open.includes(row.id);
            const accounts = row.accounts;
            const owed =
              accounts === null || accounts.count === 0
                ? null
                : moneyOrNull(accounts.outstanding_total, accounts.currency, locale);
            // Two customers may share a name — that is the case a search
            // exists for — so every row control is named by name AND number.
            const name = row.customer_no ? `${row.display_name} · ${row.customer_no}` : row.display_name;
            return [
              <tr key={row.id} data-match-row={row.verdict} data-match-customer-no={row.customer_no ?? ""}>
                <td>
                  <RowAction
                    label={t(
                      isOpen
                        ? "customers.moveIn.customer.match.hideAccounts"
                        : "customers.moveIn.customer.match.showAccounts",
                      { name },
                    )}
                    icon={isOpen ? <ChevronDownIcon /> : <ChevronRightIcon />}
                    pressed={isOpen}
                    reason={accounts === null ? t("customers.moveIn.customer.match.noAccountsRead") : null}
                    onClick={() => toggle(row.id)}
                  />
                </td>
                <td>
                  <MatchMark row={row} t={t} locale={locale} />
                </td>
                <td>
                  <div className="font-heading font-semibold" data-match-customer="">
                    {row.display_name}
                  </div>
                  {row.customer_no ? (
                    <div className="text-sm text-neutral-700">{row.customer_no}</div>
                  ) : null}
                </td>
                <td className="tabular-nums">
                  {row.date_of_birth ? formatDate(row.date_of_birth, props.timeZone, props.dateFormat) : "—"}
                </td>
                <td className="tabular-nums" data-match-phone="">
                  {phoneCell(row)}
                </td>
                <td className="tabular-nums" data-match-accounts-count="">
                  {accountsCell(row, t)}
                </td>
                <td className="text-right tabular-nums" data-match-owed="">
                  {owed === null ? (
                    "—"
                  ) : isDue(accounts?.outstanding_total) ? (
                    <StatusPill tone="danger">{owed}</StatusPill>
                  ) : (
                    owed
                  )}
                </td>
                <td>
                  <RowActions>
                    <RowAction
                      label={t("customers.moveIn.customer.match.linkName", { name })}
                      icon={<LinkIcon />}
                      testId={`match-link-${row.customer_no ?? row.verdict}`}
                      onClick={() => props.onLink(row)}
                    />
                    {row.customer_no ? (
                      <ButtonLink
                        variant="ghost"
                        size="row"
                        aria-label={t("customers.moveIn.customer.match.view", { name })}
                        title={t("customers.moveIn.customer.match.view", { name })}
                        to={`${tenantPath(CUSTOMERS_LIST)}?q=${encodeURIComponent(row.customer_no)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-match-view=""
                      >
                        <EyeIcon />
                      </ButtonLink>
                    ) : null}
                    <RowAction
                      label={t("customers.moveIn.customer.match.notThemName", { name })}
                      icon={<span aria-hidden="true">✕</span>}
                      danger
                      onClick={() => props.onNotThem(row)}
                    />
                  </RowActions>
                </td>
              </tr>,
              isOpen && accounts !== null ? (
                <tr key={`${row.id}-accounts`} data-match-accounts-row={row.customer_no ?? ""}>
                  <td />
                  <td colSpan={7}>
                    <AccountsSubTable
                      accounts={accounts}
                      t={t}
                      locale={locale}
                      timeZone={props.timeZone}
                      dateFormat={props.dateFormat}
                    />
                  </td>
                </tr>
              ) : null,
            ];
          })}
        </tbody>
      </PlainTable>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-neutral-700" data-match-legend="">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full bg-success-700" />
          {t("customers.moveIn.customer.match.found")}
        </span>
        {anyPossible ? (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full bg-warning-700" />
            {t("customers.moveIn.customer.match.possible")}
          </span>
        ) : null}
        {anyLived ? (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-flex text-info-700">
              <HomeIcon />
            </span>
            {t("customers.moveIn.customer.match.last_occupant")}
          </span>
        ) : null}
        <span className="ml-auto" data-match-none="">
          {t("customers.moveIn.customer.match.noneOfThese")}
        </span>
      </div>
    </div>
  );
}
