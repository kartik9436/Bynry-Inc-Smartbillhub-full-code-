// ── Trace ──────────────────────────────────────────────
// Change:  CR-180-BRC10 — F3, step 2 *Fix*: the ONE "What was wrong" table
// Drawing: 05-prototype/fix-a-bill-2026-10-12/06, 08, 09, 10, 11, 12, 13, 14, 15
// Rulings: decision log 2026-10-12 *FIX A BILL REVAMP* items 4, 5, 6, 7, 10, 11
// Rules:   BR-BIL-042 (What happens is DERIVED, the strongest class wins) ·
//          B14 rules 15 (icons for row actions), 31, 33, 43 · hard rule 2
// ───────────────────────────────────────────────────────
/**
 * ONE TABLE HOLDS EVERY REASON (item 10). Columns: *What was wrong* (the
 * reasons grouped re-price · credit only · reprint only) · Item · Billed /
 * change · Should be · Apply to · a bin icon. There is no separate reason
 * dropdown: *What happens* is derived from all the rows (`strongestClass`).
 *
 * Each reason draws its own inputs — the PO, *"every case"* (item 5): a reading
 * takes the correct reading, a plan takes the plan AND its version (item 6), a
 * reprint takes the new value. The lists are the server's (`GET
 * /corrections/options`, contract A2); the billed value beside each row is the
 * server's too. Nothing here is a hand-typed list of a tenant's things.
 */
import type { ReactNode } from "react";

import type { CorrectionCatalog, CorrectionFixOptions } from "@/api/billingOpsEndpoints";
import { Button } from "@/components/Button";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { TrashIcon } from "@/components/icons";
import { RowAction } from "@/components/RowActions";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";

import {
  OTB_TABLE,
  OtbPanel,
  PanelAside,
  TableScroll,
  serviceName,
} from "../oneTimeBill/oneTimeBillShared";

import {
  REASON_GROUPS,
  REPRINT_FIELDS,
  REPRINT_REASONS,
  classOf,
  newRow,
  reasonsFor,
  rowComplete,
  strongestClass,
  withReason,
} from "./fixABillModel";
import type { FixRow, FixSub, RowDefaults, Translate } from "./fixABillModel";
import { Band, ClassPill, money, percent, plainNumber } from "./fixABillShared";
import type { BandTone, FixFmt } from "./fixABillShared";

/** One bill an *Apply to* chip can name. */
export interface ApplyBill {
  id: string;
  month: string;
}

/** Where each *Not done here* bullet goes (item 4). */
export interface NotHereLinks {
  cancel: string;
  oneTime: string;
  payments: string;
  account: string;
}

const NOT_HERE: readonly { code: string; link: keyof NotHereLinks }[] = [
  { code: "bill_should_not_exist", link: "cancel" },
  { code: "period_never_billed", link: "oneTime" },
  { code: "payment_on_wrong_bill", link: "payments" },
  { code: "master_data_only", link: "account" },
];

// ── What happens (derived) ─────────────────────────────────────────────────

const HAPPENS_TONE: Record<string, BandTone> = {
  restatement: "info",
  credit_only: "success",
  document: "neutral",
};

export function WhatHappens(props: { cls: string | null; t: Translate }) {
  if (props.cls === null) return null;
  return (
    <Band tone={HAPPENS_TONE[props.cls] ?? "neutral"} hook="what-happens">
      <strong>
        {props.t("billing.fixBill.happens.label", {
          cls: props.t(`billing.fixBill.class.${props.cls}`),
        })}
      </strong>
      <span>{props.t(`billing.fixBill.happens.${props.cls}`)}</span>
    </Band>
  );
}

// ── Not done here ──────────────────────────────────────────────────────────

export function NotDoneHere(props: {
  catalog: Pick<CorrectionCatalog, "routed_elsewhere">;
  links: NotHereLinks;
  t: Translate;
}) {
  const served = new Set(props.catalog.routed_elsewhere.map((one) => one.code));
  const items = NOT_HERE.filter((one) => served.has(one.code));
  if (items.length === 0) return null;
  return (
    <div className="mt-5">
      <h4 className="m-0 font-heading text-base font-semibold">
        {props.t("billing.fixBill.notHere.title")}
      </h4>
      <ul className="m-0 mt-2 list-disc pl-5 text-base text-neutral-700" data-fix-not-here="">
        {items.map((one) => (
          <li key={one.code} className="mt-1">
            {props.t(`billing.fixBill.notHere.${one.code}`)}
            {" → "}
            <InlineLinkTo to={props.links[one.link]}>
              {props.t(`billing.fixBill.notHere.link.${one.link}`)}
            </InlineLinkTo>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── The cells of one row ───────────────────────────────────────────────────

interface CellContext {
  t: Translate;
  fmt: FixFmt;
  language: string;
  dateFormat: RegionalDateFormat;
  dateWords: (iso: string | null) => string;
  options: CorrectionFixOptions | null;
  n: number;
  locked: boolean;
}

function Quiet(props: { children: ReactNode }) {
  return <span className="text-neutral-700">{props.children}</span>;
}

/** A select inside a table cell — the kit's field, its label kept for a
 *  screen reader and hidden on screen (the column head says it). */
function CellSelect(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
  disabled: boolean;
}) {
  return (
    <SelectField
      id={props.id}
      label={props.label}
      labelHidden
      value={props.value}
      onChange={props.onChange}
      options={props.options}
      placeholder={props.placeholder}
      disabled={props.disabled}
    />
  );
}

function CellInput(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  numeric?: boolean;
  disabled: boolean;
}) {
  return (
    <TextField
      id={props.id}
      label={props.label}
      labelHidden
      value={props.value}
      onChange={props.onChange}
      numeric={props.numeric}
      disabled={props.disabled}
    />
  );
}

/** Item · Billed / change · Should be — per reason. */
function rowCells(
  row: FixRow,
  patch: (changes: Partial<FixRow>) => void,
  ctx: CellContext,
): [ReactNode, ReactNode, ReactNode] {
  const { t, options, n } = ctx;
  const id = (part: string) => `fix-row-${n}-${part}`;
  const itemLabel = `${t("billing.fixBill.col.item")} ${n}`;
  const shouldLabel = `${t("billing.fixBill.col.shouldBe")} ${n}`;
  const choose = t("billing.fixBill.fix.choose");
  const meters = options?.meters ?? [];
  const meter = meters.find((one) => one.asset_id === row.item) ?? null;
  const meterSelect = (
    <CellSelect
      id={id("item")}
      label={itemLabel}
      value={row.item}
      onChange={(item) => patch({ item })}
      options={meters.map((one) => ({
        value: one.asset_id,
        label:
          one.service_code === null
            ? one.label
            : `${one.label} · ${t(`rating.service.${one.service_code}`, { defaultValue: one.service_code })}`,
      }))}
      placeholder={choose}
      disabled={ctx.locked}
    />
  );
  const amountInput = (
    <CellInput
      id={id("value")}
      label={shouldLabel}
      value={row.value}
      onChange={(value) => patch({ value })}
      numeric
      disabled={ctx.locked}
    />
  );
  switch (row.reason) {
    case "wrong_read":
    case "theft_restated":
      return [
        meterSelect,
        row.reason === "wrong_read" ? (
          <Quiet>
            {meter?.billed_reading == null
              ? "—"
              : t("billing.fixBill.billed.reading", {
                  value: plainNumber(meter.billed_reading, ctx.language),
                })}
          </Quiet>
        ) : (
          <Quiet>{t("billing.fixBill.billed.assessed")}</Quiet>
        ),
        <span className="flex items-center gap-2">
          {amountInput}
          {meter?.unit != null && <Quiet>{meter.unit}</Quiet>}
        </span>,
      ];
    case "wrong_plan":
    case "wrong_rate": {
      const list =
        row.reason === "wrong_plan" ? (options?.plans ?? []) : (options?.rate_schedules ?? []);
      const chosen = list.find((one) => one.id === row.item) ?? null;
      return [
        <CellSelect
          id={id("item")}
          label={itemLabel}
          value={row.item}
          onChange={(item) => patch({ item, value: "" })}
          options={list.map((one) => ({ value: one.id, label: one.name }))}
          placeholder={choose}
          disabled={ctx.locked}
        />,
        <Quiet>{t("billing.fixBill.billed.useVersion")}</Quiet>,
        <CellSelect
          id={id("value")}
          label={shouldLabel}
          value={row.value}
          onChange={(value) => patch({ value })}
          options={(chosen?.versions ?? []).map((version) => ({
            value: version.id,
            label:
              version.effective_from === null
                ? version.label
                : t("billing.fixBill.fix.versionFrom", {
                    version: version.label,
                    date: ctx.dateWords(version.effective_from),
                  }),
          }))}
          placeholder={choose}
          disabled={ctx.locked || chosen === null}
        />,
      ];
    }
    case "wrong_tax": {
      const billedRate =
        row.item === ""
          ? null
          : (options?.billed?.tax_rates[row.item] ??
            options?.taxes.find((tax) => tax.code === row.item)?.rate ??
            null);
      return [
        <CellSelect
          id={id("item")}
          label={itemLabel}
          value={row.item}
          onChange={(item) => patch({ item })}
          options={(options?.taxes ?? []).map((tax) => ({ value: tax.code, label: tax.name }))}
          placeholder={choose}
          disabled={ctx.locked}
        />,
        <Quiet>
          {billedRate === null
            ? "—"
            : t("billing.fixBill.billed.value", { value: percent(billedRate, ctx.language) })}
        </Quiet>,
        <span className="flex items-center gap-2">
          {amountInput}
          <Quiet>%</Quiet>
        </span>,
      ];
    }
    case "missed_charge":
      return [
        <CellSelect
          id={id("item")}
          label={itemLabel}
          value={row.item}
          onChange={(item) => patch({ item })}
          options={(options?.charge_codes ?? []).map((code) => ({
            value: code.code,
            label:
              code.amount === null
                ? `${code.code} · ${code.name}`
                : `${code.code} · ${code.name} · ${money(code.amount, ctx.fmt)}`,
          }))}
          placeholder={choose}
          disabled={ctx.locked}
        />,
        <Quiet>{t("billing.fixBill.billed.add")}</Quiet>,
        <span className="flex items-center gap-2">
          {amountInput}
          <Quiet>×</Quiet>
        </span>,
      ];
    case "charge_billed_in_error":
      return [
        <CellSelect
          id={id("item")}
          label={itemLabel}
          value={row.item}
          onChange={(item) => patch({ item })}
          options={(options?.bill_lines ?? []).map((one) => ({ value: one.key, label: one.label }))}
          placeholder={choose}
          disabled={ctx.locked}
        />,
        <Quiet>{t("billing.fixBill.billed.remove")}</Quiet>,
        <Quiet>—</Quiet>,
      ];
    case "wrong_discount":
      return [
        <CellSelect
          id={id("item")}
          label={itemLabel}
          value={row.item}
          onChange={(item) => patch({ item })}
          options={(options?.discounts ?? []).map((one) => ({
            value: one.id,
            label: one.version_label === null ? one.name : `${one.name} · ${one.version_label}`,
          }))}
          placeholder={choose}
          disabled={ctx.locked}
        />,
        <CellSelect
          id={id("act")}
          label={`${t("billing.fixBill.col.billed")} ${n}`}
          value={row.act}
          onChange={(act) => patch({ act: act as FixRow["act"] })}
          options={[
            { value: "add", label: t("billing.fixBill.billed.add") },
            { value: "remove", label: t("billing.fixBill.billed.remove") },
          ]}
          placeholder={choose}
          disabled={ctx.locked}
        />,
        <Quiet>—</Quiet>,
      ];
    case "wrong_deposit":
      return [
        <span>{t("billing.fixBill.fix.deposit")}</span>,
        <Quiet>
          {t("billing.fixBill.billed.value", {
            value: money(options?.billed?.deposit ?? null, ctx.fmt),
          })}
        </Quiet>,
        amountInput,
      ];
    case "goodwill":
      return [
        <span>{t("billing.fixBill.fix.credit")}</span>,
        <Quiet>{t("billing.fixBill.billed.amount")}</Quiet>,
        amountInput,
      ];
    case "wrong_period_or_service": {
      const services = [
        ...new Set(
          meters.map((one) => one.service_code).filter((code): code is string => code !== null),
        ),
      ];
      return [
        <CellSelect
          id={id("item")}
          label={itemLabel}
          value={row.item}
          onChange={(item) => patch({ item })}
          options={[
            { value: "dates", label: t("billing.fixBill.fix.dates") },
            ...services.map((code) => ({
              value: code,
              label: t(`rating.service.${code}`, { defaultValue: code }),
            })),
          ]}
          placeholder={choose}
          disabled={ctx.locked}
        />,
        <Quiet>{t("billing.fixBill.billed.period")}</Quiet>,
        <span className="flex items-center gap-2">
          <DatePickerField
            id={id("from")}
            label={`${shouldLabel} ${t("billing.fixBill.price.from")}`}
            labelHidden
            value={row.value}
            onChange={(value) => patch({ value })}
            dateFormat={ctx.dateFormat}
            disabled={ctx.locked}
          />
          <DatePickerField
            id={id("to")}
            label={`${shouldLabel} ${t("billing.fixBill.price.to")}`}
            labelHidden
            value={row.value2}
            onChange={(value2) => patch({ value2 })}
            dateFormat={ctx.dateFormat}
            disabled={ctx.locked}
          />
        </span>,
      ];
    }
    default: {
      if (!REPRINT_REASONS.includes(row.reason))
        return [<Quiet>—</Quiet>, <Quiet>—</Quiet>, <Quiet>—</Quiet>];
      const current = options?.billed?.fields[row.reason] ?? null;
      const fields = REPRINT_FIELDS[row.reason] ?? [];
      return [
        fields.length > 1 ? (
          <CellSelect
            id={id("item")}
            label={itemLabel}
            value={row.item}
            onChange={(item) => patch({ item })}
            options={fields.map((field) => ({
              value: field,
              label: t(`billing.fixBill.field.${field}`),
            }))}
            placeholder={choose}
            disabled={ctx.locked}
          />
        ) : (
          <span>{t(`billing.fixBill.reason.${row.reason}`)}</span>
        ),
        <Quiet>
          {current === null ? "—" : t("billing.fixBill.billed.was", { value: current })}
        </Quiet>,
        <CellInput
          id={id("value")}
          label={shouldLabel}
          value={row.value}
          onChange={(value) => patch({ value })}
          disabled={ctx.locked}
        />,
      ];
    }
  }
}

/** *Apply to* — the one bill's month, month chips for several, or every bill. */
function ApplyTo(props: {
  row: FixRow;
  bills: readonly ApplyBill[];
  onChange: (applyTo: string[] | null) => void;
  t: Translate;
  locked: boolean;
}) {
  const { row, bills } = props;
  if (row.applyTo === null) return <Quiet>{props.t("billing.fixBill.apply.every")}</Quiet>;
  if (bills.length <= 1) return <Quiet>{bills[0]?.month ?? ""}</Quiet>;
  const chosen = row.applyTo;
  return (
    <span className="flex flex-wrap gap-2" data-fix-apply="">
      {bills.map((bill) => {
        const on = chosen.includes(bill.id);
        return (
          <label
            key={bill.id}
            className={`inline-flex cursor-pointer items-center gap-1.5 border px-2 py-1 text-sm ${on ? "border-accent" : "border-divider"}`}
          >
            <input
              type="checkbox"
              checked={on}
              disabled={props.locked}
              className="h-4 w-4 accent-accent"
              onChange={() =>
                props.onChange(
                  on
                    ? chosen.filter((id) => id !== bill.id)
                    : bills.map((b) => b.id).filter((id) => id === bill.id || chosen.includes(id)),
                )
              }
            />
            {bill.month}
          </label>
        );
      })}
    </span>
  );
}

// ── The panel ──────────────────────────────────────────────────────────────

export function WhatWasWrongPanel(props: {
  t: Translate;
  fmt: FixFmt;
  language: string;
  dateFormat: RegionalDateFormat;
  dateWords: (iso: string | null) => string;
  sub: FixSub;
  catalog: CorrectionCatalog;
  options: CorrectionFixOptions | null;
  rows: readonly FixRow[];
  onRows: (rows: FixRow[]) => void;
  bills: readonly ApplyBill[];
  defaults: RowDefaults;
  links: NotHereLinks;
  locked: boolean;
  /**
   * Q3 (decision log 2026-10-13) — the preview's warnings: a Wrong plan row
   * whose plan bills one of the account's services at $0.00. `position` is
   * the row's place among the FINISHED rows (the ones sent), 1-based.
   */
  planWarnings?: readonly { position: number; service_code: string; amount: string }[];
}) {
  const { t, catalog, rows } = props;
  const offered = reasonsFor(props.sub, catalog);
  // The server numbers the rows it was SENT — only finished ones.
  const sentPosition = new Map<string, number>();
  rows.filter(rowComplete).forEach((row, index) => sentPosition.set(row.uid, index + 1));
  const groups = REASON_GROUPS.map((group) => ({
    label: t(`billing.fixBill.class.${group.cls}`),
    options: group.reasons
      .filter((reason) => offered.includes(reason))
      .map((reason) => ({ value: reason, label: t(`billing.fixBill.reason.${reason}`) })),
  })).filter((group) => group.options.length > 0);
  const cls = strongestClass(
    rows.filter((row) => row.reason !== ""),
    catalog,
  );

  function patchRow(uid: string, changes: Partial<FixRow>): void {
    props.onRows(rows.map((row) => (row.uid === uid ? { ...row, ...changes } : row)));
  }

  return (
    <OtbPanel
      id="what-was-wrong"
      title={t("billing.fixBill.fix.title")}
      aside={<PanelAside>{t("billing.fixBill.fix.count", { count: rows.length })}</PanelAside>}
    >
      <WhatHappens cls={cls} t={t} />
      <div className="mt-3">
        <TableScroll>
          <PlainTable className={OTB_TABLE} data-fix-rows="">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">{t("billing.fixBill.col.reason")}</th>
                <th scope="col">{t("billing.fixBill.col.item")}</th>
                <th scope="col">{t("billing.fixBill.col.billed")}</th>
                <th scope="col">{t("billing.fixBill.col.shouldBe")}</th>
                <th scope="col">{t("billing.fixBill.col.applyTo")}</th>
                <th scope="col">
                  <span className="sr-only">{t("billing.fixBill.fix.remove")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const n = index + 1;
                const [item, billed, should] = rowCells(
                  row,
                  (changes) => patchRow(row.uid, changes),
                  {
                    t,
                    fmt: props.fmt,
                    language: props.language,
                    dateFormat: props.dateFormat,
                    dateWords: props.dateWords,
                    options: props.options,
                    n,
                    locked: props.locked,
                  },
                );
                return (
                  <tr key={row.uid} data-fix-row={row.reason}>
                    <td className="text-neutral-700">{n}</td>
                    <td>
                      <SelectField
                        id={`fix-row-${n}-reason`}
                        label={`${t("billing.fixBill.col.reason")} ${n}`}
                        labelHidden
                        value={row.reason}
                        onChange={(reason) =>
                          props.onRows(
                            rows.map((one) =>
                              one.uid === row.uid ? withReason(one, reason, props.defaults) : one,
                            ),
                          )
                        }
                        options={[]}
                        groups={groups}
                        placeholder={t("billing.fixBill.fix.choose")}
                        disabled={props.locked}
                      />
                      <div className="mt-1">
                        <ClassPill
                          cls={row.reason === "" ? null : classOf(row.reason, catalog)}
                          t={t}
                        />
                      </div>
                    </td>
                    <td>{row.reason === "" ? null : item}</td>
                    <td>{row.reason === "" ? null : billed}</td>
                    <td>
                      {row.reason === "" ? null : should}
                      {(props.planWarnings ?? [])
                        .filter((one) => one.position === sentPosition.get(row.uid))
                        .map((one) => (
                          <p
                            key={one.service_code}
                            className="m-0 mt-1 text-sm text-warning-700"
                            role="note"
                            data-fix-plan-zero={one.service_code}
                          >
                            {t("billing.fixBill.planZero", {
                              service: serviceName(one.service_code, t),
                              amount: money(one.amount, props.fmt),
                            })}
                          </p>
                        ))}
                    </td>
                    <td>
                      <ApplyTo
                        row={row}
                        bills={props.bills}
                        onChange={(applyTo) => patchRow(row.uid, { applyTo })}
                        t={t}
                        locked={props.locked}
                      />
                    </td>
                    <td>
                      <RowAction
                        label={t("billing.fixBill.fix.remove")}
                        icon={<TrashIcon />}
                        danger
                        reason={props.locked ? t("billing.fixBill.fix.locked") : null}
                        onClick={() => props.onRows(rows.filter((one) => one.uid !== row.uid))}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </PlainTable>
        </TableScroll>
      </div>
      {!props.locked && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => props.onRows([...rows, newRow("", props.defaults)])}
          >
            {t("billing.fixBill.fix.add")}
          </Button>
          <Note as="span" className="text-sm">
            {t("billing.fixBill.fix.baseNote")}
          </Note>
        </div>
      )}
      <NotDoneHere catalog={catalog} links={props.links} t={t} />
    </OtbPanel>
  );
}
