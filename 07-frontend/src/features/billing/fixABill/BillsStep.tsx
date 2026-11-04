// ── Trace ──────────────────────────────────────────────
// Change:  CR-180-BRC10 — F1–F2, step 1 *Bills*
// Drawing: 05-prototype/fix-a-bill-2026-10-12/01 (one bill), 02 (account search
//          open), 03 (several months), 04 (a billing run), 05 (a price mistake)
// Rulings: decision log 2026-10-12 *FIX A BILL REVAMP* items 1–3
// Rules:   B14 rules 31 (no id on screen), 33, 43, 44 · NFR-3 (server pages) ·
//          hard rule 2 (every total is the SERVER's — nothing is summed here)
// ───────────────────────────────────────────────────────
/**
 * STEP 1 — WHICH BILLS. Two option cards, then a dropdown whose choices depend
 * on the option, then the panel that option needs, then the bills it covers.
 * Each piece is a component (B14 rule 43); the page composes them.
 *
 * ⚠ **THE PICKED TOTAL IS ASKED, NOT ADDED.** *"1 picked · $232.70"* is the
 * server's `totals` for the picked ids (contract A1), because summing money in
 * a browser is a second arithmetic path (B4).
 */
import type { ReactNode } from "react";

import type { AccountRow, BillRunHistoryRow } from "@/api/endpoints";
import type {
  CorrectionFixOptions,
  CorrectionScopeBillV2,
  CorrectionScopeExcluded,
  CorrectionScopeResolutionV2,
  OneTimeBillAccount,
} from "@/api/billingOpsEndpoints";
import { AccountCombobox } from "@/components/AccountCombobox";
import type { RemoteSearchStatus } from "@/components/RemoteSearchSelectField";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";
import { DatePickerField, SelectField } from "@/components/FormModal";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";

import { accountOption, accountStatusTone } from "../oneTimeBill/AccountStep";
import { OTB_TABLE, OtbPanel, PanelAside, TableScroll } from "../oneTimeBill/oneTimeBillShared";

import { FIX_OPTIONS, SUBS_BY_OPTION, periodLabel } from "./fixABillModel";
import type { FixBillsForm, FixOption, FixSub, Translate } from "./fixABillModel";
import { Band, money } from "./fixABillShared";
import type { FixFmt } from "./fixABillShared";

// ── The two option cards (image 01) ────────────────────────────────────────

const CARD =
  "flex min-w-0 flex-col items-start gap-1 border bg-surface px-4 py-4 text-left " +
  "cursor-pointer focus-visible:outline-2 focus-visible:outline-accent";
const CARD_REST = "border-divider border-t-2 border-t-transparent";
const CARD_CHOSEN = "border-accent border-t-2 border-t-accent";

export function OptionCards(props: {
  value: FixOption;
  onChange: (option: FixOption) => void;
  t: Translate;
  disabled?: boolean;
}) {
  return (
    <div
      className="grid grid-cols-2 gap-2 max-sm:grid-cols-1"
      role="group"
      aria-label={props.t("billing.fixBill.option.label")}
    >
      {FIX_OPTIONS.map((option) => {
        const chosen = option === props.value;
        return (
          <button
            key={option}
            type="button"
            className={`${CARD} ${chosen ? CARD_CHOSEN : CARD_REST}`}
            aria-pressed={chosen}
            disabled={props.disabled === true}
            data-fix-option={option}
            onClick={() => props.onChange(option)}
          >
            <span className="font-heading text-md font-semibold text-text">
              {props.t(`billing.fixBill.option.${option}`)}
            </span>
            <span className="text-sm text-neutral-700">
              {props.t(`billing.fixBill.option.${option}Use`)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** *What are you fixing* — the cards, then the dropdown of that option's
 *  sub-options (items 1–3). */
export function WhatPanel(props: {
  form: FixBillsForm;
  onOption: (option: FixOption) => void;
  onSub: (sub: FixSub) => void;
  t: Translate;
  locked: boolean;
}) {
  const { t, form } = props;
  return (
    <OtbPanel id="what" title={t("billing.fixBill.what.title")}>
      <OptionCards value={form.option} onChange={props.onOption} t={t} disabled={props.locked} />
      <div className="mt-4 max-w-sm">
        <SelectField
          id="fix-sub"
          label={t(
            form.option === "one"
              ? "billing.fixBill.sub.labelOne"
              : "billing.fixBill.sub.labelBulk",
          )}
          value={form.sub}
          onChange={(value) => props.onSub(value as FixSub)}
          options={SUBS_BY_OPTION[form.option].map((sub) => ({
            value: sub,
            label: t(`billing.fixBill.sub.${sub}`),
          }))}
          required
          disabled={props.locked}
        />
      </div>
    </OtbPanel>
  );
}

// ── Customer (images 01–02) ────────────────────────────────────────────────

export function CustomerPanel(props: {
  t: Translate;
  fmt: FixFmt;
  dateWords: (iso: string | null) => string;
  term: string;
  onTermChange: (term: string) => void;
  search: RemoteSearchStatus;
  matches: readonly AccountRow[];
  chosen: {
    id: string;
    name: string | null;
    account_no: string | null;
    tone?: string | null;
  } | null;
  onChoose: (row: AccountRow | null) => void;
  facts: OneTimeBillAccount | null;
  /** Opened from an account or a bill: the account is fixed, not searched. */
  locked: boolean;
}) {
  const { t, chosen, facts } = props;
  const label = (key: string) => t(`billing.oneTimeBill.account.${key}`);
  const list: Fact[] =
    chosen === null
      ? []
      : [
          { id: "customer", label: label("customer"), value: facts?.name ?? chosen.name ?? "—" },
          {
            id: "account",
            label: label("number"),
            value: facts?.account_no ?? chosen.account_no ?? "—",
          },
          { id: "address", label: label("address"), value: facts?.address ?? "—" },
          { id: "plan", label: label("plan"), value: facts?.plan ?? "—" },
          {
            id: "status",
            label: label("status"),
            value:
              facts === null ? (
                "—"
              ) : (
                <StatusPill tone={accountStatusTone(chosen.tone ?? null)}>
                  {facts.status_name}
                </StatusPill>
              ),
          },
          {
            id: "balance",
            label: label("balance"),
            value:
              facts === null
                ? "—"
                : money(facts.balance, { ...props.fmt, currency: facts.currency }),
          },
          { id: "cycle", label: label("cycle"), value: facts?.cycle_name ?? "—" },
          {
            id: "last-bill",
            label: label("lastBill"),
            value: props.dateWords(facts?.last_bill_on ?? null),
          },
        ];
  return (
    <OtbPanel id="customer" title={t("billing.fixBill.customer.title")}>
      {!props.locked && (
        <AccountCombobox
          id="fix-account"
          label={label("find")}
          required
          term={props.term}
          onTermChange={props.onTermChange}
          status={props.search}
          options={props.matches.map((row) => accountOption(row, t))}
          value={chosen?.id ?? ""}
          selectedName={chosen === null ? "" : `${chosen.name ?? ""} · ${chosen.account_no ?? ""}`}
          onChange={(option) =>
            props.onChoose(
              option === null
                ? null
                : (props.matches.find((row) => row.id === option.value) ?? null),
            )
          }
          words={{
            tooShort: label("tooShort"),
            searching: label("searching"),
            failed: label("failed"),
            noMatch: label("noMatch"),
          }}
          placeholder={label("placeholder")}
          help={label("help")}
        />
      )}
      {list.length > 0 && (
        <div className="mt-4">
          <FactBlock name="fix-account" facts={list} columns={4} />
        </div>
      )}
    </OtbPanel>
  );
}

// ── Pick the bill / Tick the bills (images 01, 03) ─────────────────────────

/** `Nov 2026 is a draft. Fix it in its bill run.` — one line per bill a scope
 *  left out, in words (never the code). */
function ExcludedWords(props: {
  excluded: readonly CorrectionScopeExcluded[];
  t: Translate;
  language: string;
}) {
  if (props.excluded.length === 0) return null;
  return (
    <Band tone="info" hook="excluded">
      {props.excluded.map((one) => (
        <span key={one.invoice_id}>
          {props.t(`billing.fixBill.excluded.${one.code === "draft" ? "draft" : "openCase"}`, {
            month: periodLabel(one.period_end.slice(0, 7), props.language),
          })}
        </span>
      ))}
    </Band>
  );
}

function BillState(props: { row: CorrectionScopeBillV2; t: Translate }) {
  const paid = props.row.bill_status === "paid";
  return (
    <StatusPill tone={paid ? "success" : "info"}>
      {props.t(`billing.fixBill.billStatus.${paid ? "paid" : "issued"}`)}
    </StatusPill>
  );
}

export function AccountBillsPanel(props: {
  t: Translate;
  fmt: FixFmt;
  language: string;
  span: (start: string, end: string) => string;
  several: boolean;
  resolution: CorrectionScopeResolutionV2 | null;
  picked: readonly string[];
  pickedTotals: CorrectionScopeResolutionV2 | null;
  onToggle: (invoiceId: string) => void;
  locked: boolean;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
}) {
  const { t, resolution } = props;
  const rows = resolution?.results ?? [];
  const totals = props.pickedTotals?.totals ?? null;
  const currency = totals?.currency ?? rows[0]?.currency ?? props.fmt.currency;
  const fmt = { ...props.fmt, currency };
  return (
    <OtbPanel
      id="bills"
      title={t(
        props.several ? "billing.fixBill.bills.tickTitle" : "billing.fixBill.bills.pickTitle",
      )}
      aside={
        resolution === null ? undefined : (
          <PanelAside>{t("billing.fixBill.bills.sent", { count: resolution.count })}</PanelAside>
        )
      }
    >
      {resolution === null ? null : rows.length === 0 ? (
        <p className="m-0 text-base text-neutral-700">{t("billing.fixBill.bills.none")}</p>
      ) : (
        <TableScroll>
          <PlainTable className={OTB_TABLE} data-fix-bills="">
            <thead>
              <tr>
                <th scope="col">
                  <span className="sr-only">{t("billing.fixBill.bills.choose")}</span>
                </th>
                <th scope="col">{t("billing.fixBill.col.bill")}</th>
                <th scope="col">{t("billing.fixBill.col.period")}</th>
                <th scope="col" data-num="">
                  {t("billing.fixBill.col.amount")}
                </th>
                <th scope="col" data-num="">
                  {t("billing.fixBill.col.paid")}
                </th>
                <th scope="col">{t("billing.fixBill.col.state")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const chosen = props.picked.includes(row.invoice_id);
                return (
                  <tr key={row.invoice_id} className={chosen ? "bg-accent-100" : undefined}>
                    <td>
                      <input
                        type={props.several ? "checkbox" : "radio"}
                        name="fix-bill"
                        value={row.invoice_id}
                        checked={chosen}
                        disabled={props.locked}
                        aria-label={row.invoice_no ?? t("billing.fixBill.bills.noNumber")}
                        onChange={() => props.onToggle(row.invoice_id)}
                        className="h-4 w-4 accent-accent"
                      />
                    </td>
                    <td>{row.invoice_no ?? "—"}</td>
                    <td>{props.span(row.period_start, row.period_end)}</td>
                    <td data-num="">{money(row.amount, { ...fmt, currency: row.currency })}</td>
                    <td data-num="">{money(row.paid, { ...fmt, currency: row.currency })}</td>
                    <td>
                      <BillState row={row} t={t} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr data-total="" data-fix-picked-total="">
                <td />
                <td>{t("billing.fixBill.bills.picked", { count: props.picked.length })}</td>
                <td />
                <td data-num="">{totals === null ? "—" : money(totals.amount, fmt)}</td>
                <td data-num="">{totals === null ? "—" : money(totals.paid, fmt)}</td>
                <td />
              </tr>
            </tfoot>
          </PlainTable>
        </TableScroll>
      )}
      {resolution !== null && resolution.count > props.per && (
        <ListPager
          total={resolution.count}
          page={props.page}
          per={props.per}
          onPage={props.onPage}
          onPer={props.onPer}
        />
      )}
      <ExcludedWords excluded={resolution?.excluded ?? []} t={t} language={props.language} />
    </OtbPanel>
  );
}

// ── Billing run (image 04) ─────────────────────────────────────────────────

export function RunPanel(props: {
  t: Translate;
  language: string;
  runs: readonly BillRunHistoryRow[];
  runId: string;
  onRun: (runId: string) => void;
  part: string;
  onPart: (part: string) => void;
  services: readonly { code: string; name: string }[];
  plans: CorrectionFixOptions["plans"];
  locked: boolean;
}) {
  const { t } = props;
  return (
    <OtbPanel id="run" title={t("billing.fixBill.run.title")}>
      <div className="grid grid-cols-[2fr_1fr] gap-4 max-sm:grid-cols-1">
        <SelectField
          id="fix-run"
          label={t("billing.fixBill.run.run")}
          value={props.runId}
          onChange={props.onRun}
          placeholder={t("billing.fixBill.run.placeholder")}
          options={props.runs.map((run) => ({
            value: run.id,
            label: t("billing.fixBill.run.option", {
              // DEF-BIL-10090 — a run with no cycle (a one-time run) is named
              // by its run number, never by an empty string.
              cycle:
                run.cycle_name || run.cycle_code || run.run_no || t("billing.tab.oneTime"),
              month:
                run.period_end === null
                  ? ""
                  : periodLabel(run.period_end.slice(0, 7), props.language),
              count: run.bills_issued,
            }),
          }))}
          required
          disabled={props.locked}
        />
        <SelectField
          id="fix-run-part"
          label={t("billing.fixBill.run.part")}
          value={props.part}
          onChange={props.onPart}
          options={[
            { value: "", label: t("billing.fixBill.run.whole") },
            ...props.services.map((service) => ({
              value: `service:${service.code}`,
              label: t("billing.fixBill.run.serviceOnly", { service: service.name }),
            })),
            ...props.plans.map((plan) => ({
              value: `plan:${plan.id}`,
              label: t("billing.fixBill.run.planOnly", { plan: plan.name }),
            })),
          ]}
          disabled={props.locked || props.runId === ""}
        />
      </div>
    </OtbPanel>
  );
}

// ── The price mistake (image 05) ───────────────────────────────────────────

export function PriceMistakePanel(props: {
  t: Translate;
  dateFormat: RegionalDateFormat;
  form: FixBillsForm;
  onChange: (changes: Partial<FixBillsForm>) => void;
  targets: CorrectionFixOptions["price_targets"];
  locked: boolean;
}) {
  const { t, form } = props;
  return (
    <OtbPanel id="price" title={t("billing.fixBill.price.title")}>
      <div className="grid grid-cols-3 gap-4 max-md:grid-cols-1">
        <DatePickerField
          id="fix-from"
          label={t("billing.fixBill.price.from")}
          value={form.from}
          onChange={(from) => props.onChange({ from })}
          dateFormat={props.dateFormat}
          max={form.to === "" ? undefined : form.to}
          required
          disabled={props.locked}
        />
        <DatePickerField
          id="fix-to"
          label={t("billing.fixBill.price.to")}
          value={form.to}
          onChange={(to) => props.onChange({ to })}
          dateFormat={props.dateFormat}
          min={form.from === "" ? undefined : form.from}
          required
          disabled={props.locked}
        />
        <SelectField
          id="fix-target"
          label={t("billing.fixBill.price.wrong")}
          value={form.target}
          onChange={(target) => props.onChange({ target })}
          placeholder={t("billing.fixBill.price.wrongPlaceholder")}
          options={props.targets.map((target) => ({
            value: `${target.kind}:${target.id}`,
            label: `${t(`billing.fixBill.price.kind.${target.kind}`)} · ${target.label}`,
          }))}
          required
          disabled={props.locked}
        />
      </div>
      <Band tone="warning" role="note">
        {t("billing.fixBill.price.fixFirst")}
      </Band>
    </OtbPanel>
  );
}

// ── An opened case's bills (read-only) ─────────────────────────────────────

/** Step 1 of a case that already exists — opened by its approver, or after
 *  Send: the bills it holds, nothing to choose. */
export function CaseBillsPanel(props: {
  t: Translate;
  fmt: FixFmt;
  span: (start: string, end: string) => string;
  bills: readonly {
    invoice_id: string;
    invoice_no: string | null;
    account_no: string | null;
    customer_name: string | null;
    period_start: string;
    period_end: string;
    was_total: string;
  }[];
  count: number;
}) {
  const { t } = props;
  return (
    <OtbPanel
      id="case-bills"
      title={t("billing.fixBill.covered.title")}
      aside={<PanelAside>{t("billing.fixBill.compare.aside", { count: props.count })}</PanelAside>}
    >
      <TableScroll>
        <PlainTable className={OTB_TABLE} data-fix-case-bills="">
          <thead>
            <tr>
              <th scope="col">{t("billing.fixBill.col.account")}</th>
              <th scope="col">{t("billing.fixBill.col.customer")}</th>
              <th scope="col">{t("billing.fixBill.col.bill")}</th>
              <th scope="col">{t("billing.fixBill.col.period")}</th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.amount")}
              </th>
            </tr>
          </thead>
          <tbody>
            {props.bills.map((bill) => (
              <tr key={bill.invoice_id}>
                <td>{bill.account_no ?? "—"}</td>
                <td>{bill.customer_name ?? "—"}</td>
                <td>{bill.invoice_no ?? "—"}</td>
                <td>{props.span(bill.period_start, bill.period_end)}</td>
                <td data-num="">{money(bill.was_total, props.fmt)}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
    </OtbPanel>
  );
}

// ── Bills it covers (images 04–05) ─────────────────────────────────────────

/** `Left out: 2 already in an open case · 1 draft.` */
function LeftOut(props: { excluded: readonly CorrectionScopeExcluded[]; t: Translate }) {
  const open = props.excluded.filter((one) => one.code !== "draft").length;
  const drafts = props.excluded.length - open;
  if (props.excluded.length === 0) return null;
  const parts: ReactNode[] = [];
  if (open > 0) parts.push(props.t("billing.fixBill.leftOut.openCase", { count: open }));
  if (drafts > 0) parts.push(props.t("billing.fixBill.leftOut.draft", { count: drafts }));
  return (
    <Band tone="warning" hook="left-out">
      <strong>{props.t("billing.fixBill.leftOut.label")}</strong>
      <span>{parts.join(" · ")}</span>
    </Band>
  );
}

export function CoveredBillsPanel(props: {
  t: Translate;
  fmt: FixFmt;
  resolution: CorrectionScopeResolutionV2 | null;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
}) {
  const { t, resolution } = props;
  if (resolution === null) return null;
  const totals = resolution.totals;
  const fmt = { ...props.fmt, currency: totals.currency ?? props.fmt.currency };
  return (
    <OtbPanel
      id="covered"
      title={t("billing.fixBill.covered.title")}
      aside={
        <PanelAside>
          {t("billing.fixBill.covered.aside", {
            bills: totals.bills,
            accounts: totals.accounts ?? resolution.count,
          })}
        </PanelAside>
      }
    >
      <TableScroll>
        <PlainTable className={OTB_TABLE} data-fix-covered="">
          <thead>
            <tr>
              <th scope="col">{t("billing.fixBill.col.account")}</th>
              <th scope="col">{t("billing.fixBill.col.customer")}</th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.amount")}
              </th>
              <th scope="col">{t("billing.fixBill.col.state")}</th>
            </tr>
          </thead>
          <tbody>
            {resolution.results.map((row) => (
              <tr key={row.invoice_id}>
                <td>{row.account_no ?? "—"}</td>
                <td>{row.customer_name ?? "—"}</td>
                <td data-num="">{money(row.amount, { ...fmt, currency: row.currency })}</td>
                <td>
                  <BillState row={row} t={t} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr data-total="">
              <td>{t("billing.fixBill.covered.all", { count: totals.bills })}</td>
              <td />
              <td data-num="">{money(totals.amount, fmt)}</td>
              <td>
                {totals.paid === null
                  ? ""
                  : t("billing.fixBill.covered.paid", { amount: money(totals.paid, fmt) })}
              </td>
            </tr>
          </tfoot>
        </PlainTable>
      </TableScroll>
      <ListPager
        total={resolution.count}
        page={props.page}
        per={props.per}
        onPage={props.onPage}
        onPer={props.onPer}
      />
      <LeftOut excluded={resolution.excluded ?? []} t={t} />
    </OtbPanel>
  );
}
