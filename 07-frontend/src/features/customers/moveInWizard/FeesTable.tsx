// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.30 (lane MVI-WIZ-BILL) — the Billing step's Fees
//           table, from images 41 and 43: the plan's rows locked (deposit
//           first), *+ Add fee* searching the utility's one-time charge codes,
//           and the Total.
// Rules:    B14 rules 15 (row actions are icons), 20 (one table: the kit's
//           TableArray), 21, 31 (no id on screen), 33, 43, 44 · CLAUDE.md hard
//           rule 2 (every figure is rating's 4-place string, shown through
//           `MoneyCell`; the Total is `moneyMath.sumAmounts`, exact) ·
//           OQ-BIL-12788 CLOSED (a) — a move-in fee is NEVER taxed at move-in
// Server:   GET /move-ins/fees/quote (§9.MONEY) · GET /charges?q=&f.type=one_time
// Change:   CR-171-BRC10 lane RULINGS-2 — PO ruling (7) of 2026-10-05
//           (decision log *"A CLERK CAN STILL WAIVE THE DEPOSIT"*), verbatim:
//           *"(a). Clerks use it today, the server already supports it, and the
//           fix for 'waived deposit still billed' is already in place."* The
//           deposit row carries a **Waive deposit** row action (an icon, B14
//           rule 15) that asks a reason (`WaiveDepositModal`); a waived row
//           stays drawn — *Waived* with its reason — and adds nothing to the
//           Total. *Undo waive* puts it back. Images 41–44 draw no waive; the
//           ruling adds one, and the kit's row action is how (B14 rule 44).
// ───────────────────────────────────────────────────────
//
// ⚠ **NO *TAXABLE* COLUMN, ALTHOUGH IMAGES 41 AND 43 DRAW ONE.** The PO ruled
// on 2026-10-05 that a move-in fee is never taxed at move-in (`OQ-BIL-12788`
// (a): *"$25.00 (never taxed at move-in)"*), so the drawn *Yes* beside CONNECT
// would tell the clerk the opposite of the rule. Every row the server serves
// says `taxed_at_move_in: false`; a column that could only ever read *No* is a
// control claiming a fact the data does not hold. The details view's Billing
// tab made the same call (CR §13). A ruling beats a drawing.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { getCharges } from "@/api/endpoints";
import { getMoveInFeeQuote } from "@/api/moveInMoneyEndpoints";
import type { MoveFeeRow, MoveInMoneyQuery } from "@/api/moveInMoneyEndpoints";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { RollBackIcon, WaiveIcon } from "@/components/icons";
import { MoneyCell } from "@/components/MoneyCell";
import { startingAmount } from "@/components/moneyMath";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { CellStatic, CellText, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import type { Translator } from "@/features/tenancy/settingsShared";

import { addedAmount, feesTotal, rowKey } from "./billingModel";
import type { AddedFee, StepBillingOwn } from "./billingModel";

const SEARCH_PER = 20;

/** The waive's one field — a reason, required (the server refuses a waive
 *  without one: `customers.deposit.waiveReasonRequired`). */
const WAIVE_SCHEMA = z.object({ reason: z.string().trim().min(1) });

/** *Waive deposit*'s dialog: the reason, then the row is waived. Nothing is
 *  posted here — the waive travels with Complete (`billingPayload`). */
export function WaiveDepositModal(props: {
  t: Translator;
  onWaive: (reason: string) => void;
  onClose: () => void;
}) {
  const { t } = props;
  const [reason, setReason] = useState("");
  async function submit(): Promise<FormSubmitOutcome> {
    props.onWaive(reason.trim());
    props.onClose();
    return { ok: true };
  }
  return (
    <FormModal
      title={t("customers.moveIn.fees.waive")}
      schema={WAIVE_SCHEMA}
      values={{ reason }}
      submitLabel={t("customers.moveIn.fees.waiveSubmit")}
      onClose={props.onClose}
      onSubmit={submit}
    >
      <TextField
        id="reason"
        label={t("customers.deposit.field.waiveReason")}
        value={reason}
        onChange={setReason}
        required
      />
    </FormModal>
  );
}

/** One table row: a plan row the server served, or a row the clerk added. */
type FeeLine =
  | { key: string; plan: MoveFeeRow; added?: undefined }
  | { key: string; plan?: undefined; added: AddedFee };

/** Rating's refusal names, in the clerk's words (≤ 6, B14 rule 33). Literal
 *  keys, so the catalogue gates see every one. */
const REFUSAL_KEYS: Readonly<Record<string, string>> = {
  size_required: "customers.moveIn.fees.refusal.sizeRequired",
  size_not_recorded: "customers.moveIn.fees.refusal.sizeNotRecorded",
  size_not_priced: "customers.moveIn.fees.refusal.sizeNotPriced",
  no_price: "customers.moveIn.fees.refusal.noPrice",
  percent_has_no_basis: "customers.moveIn.fees.refusal.percentNoBasis",
  unknown_code: "customers.moveIn.fees.refusal.unknownCode",
  not_a_one_time_code: "customers.moveIn.fees.refusal.notOneTime",
  not_for_this_class: "customers.moveIn.fees.refusal.notForClass",
};

export function feeRefusalText(t: Translator, refusal: string): string {
  return t(REFUSAL_KEYS[refusal] ?? "customers.moveIn.fees.refusal.other");
}

/** The FEE cell of a plan row: `CONNECT · Connection · Residential`. */
function planLabel(row: MoveFeeRow, classLabel: string): string {
  return [row.code, row.name ?? null, classLabel === "" ? null : classLabel]
    .filter((part): part is string => part !== null && part !== "")
    .join(" · ");
}

/** *+ Add fee*'s cell: type a code or its name, pick one, and rating prices it. */
function FeeSearchCell(props: {
  row: AddedFee;
  query: MoveInMoneyQuery;
  client: ApiClient;
  t: Translator;
  onPicked: (next: AddedFee) => void;
}) {
  const { t } = props;
  const [term, setTerm] = useState(props.row.label);
  const search = useQuery({
    queryKey: ["charges", "move-in-fee", term],
    queryFn: () =>
      getCharges(
        { q: term, filters: { type: "one_time" }, page: 1, per: SEARCH_PER },
        props.client,
      ),
    enabled: term.trim().length >= 1 && props.row.code === "",
    retry: false,
  });
  const options = (search.data?.results ?? []).map((charge) => ({
    value: charge.code,
    label: `${charge.code} · ${charge.name}`,
  }));

  async function pick(code: string): Promise<void> {
    if (code === "") {
      props.onPicked({
        ...props.row,
        code: "",
        label: "",
        quoted: null,
        pricedBy: null,
        refusal: null,
      });
      return;
    }
    const label = options.find((option) => option.value === code)?.label ?? code;
    setTerm(label);
    try {
      const quote = await getMoveInFeeQuote({ ...props.query, code }, props.client);
      props.onPicked({
        ...props.row,
        code,
        label,
        quoted: quote.amount,
        pricedBy: quote.priced_by ?? null,
        refusal: quote.refusal,
        // DEF-RAT-9807 — an *entered when used* code's box starts at its
        // default (`BR-RAT-1054` AMENDED 2026-10-06); the clerk may change it.
        typed: quote.priced_by === "per_case" ? startingAmount(quote.default_amount) : props.row.typed,
      });
    } catch {
      props.onPicked({
        ...props.row,
        code,
        label,
        quoted: null,
        pricedBy: null,
        refusal: "quote_failed",
      });
    }
  }

  return (
    <RemoteSearchSelectField
      cell
      id={`fee-${props.row.key}`}
      label={t("customers.moveIn.fees.col.fee")}
      term={term}
      onTermChange={(next) => {
        setTerm(next);
        if (props.row.code !== "") void pick("");
      }}
      status={{
        idle: term.trim().length < 1,
        searching: search.isFetching,
        searched: search.isSuccess,
        failed: search.isError,
      }}
      options={options}
      value={props.row.code}
      onChange={(code) => void pick(code)}
      words={{
        tooShort: t("customers.moveIn.fees.search.tooShort"),
        searching: t("customers.moveIn.fees.search.searching"),
        failed: t("customers.moveIn.fees.search.failed"),
        noMatch: t("customers.moveIn.fees.search.noMatch"),
      }}
      placeholder={t("customers.moveIn.fees.search.placeholder")}
    />
  );
}

export function FeesTable(props: {
  own: StepBillingOwn;
  set: (next: StepBillingOwn) => void;
  /** The read's state — the table holds its body until the plan rows arrive. */
  status: "pending" | "failed" | "ready";
  query: MoveInMoneyQuery;
  currency: string;
  /** The customer class's name — `Residential`. */
  classLabel: string;
  client: ApiClient;
  t: Translator;
  tried: boolean;
}) {
  const { own, set, t } = props;
  const [waiving, setWaiving] = useState(false);
  const waived = (line: FeeLine) => line.plan?.kind === "deposit" && own.depositWaive !== null;
  const lines: FeeLine[] = [
    ...(own.planRows ?? []).map((plan) => ({ key: `plan-${plan.kind}-${plan.code}`, plan })),
    ...own.added.map((added) => ({ key: added.key, added })),
  ];

  function patchAdded(next: AddedFee): void {
    set({ ...own, added: own.added.map((row) => (row.key === next.key ? next : row)) });
  }

  const columns: TableArrayColumn<FeeLine>[] = [
    {
      key: "no",
      label: "#",
      cell: (_line, index) => <CellStatic name="no">{index + 1}</CellStatic>,
    },
    {
      key: "fee",
      label: t("customers.moveIn.fees.col.fee"),
      cell: (line) =>
        line.plan !== undefined ? (
          <span className="inline-flex items-center gap-2">
            <span className="font-semibold" data-cell="fee">
              {planLabel(line.plan, props.classLabel)}
            </span>
            {waived(line) && (
              <StatusPill tone="neutral">{t("customers.account.depositWaived")}</StatusPill>
            )}
          </span>
        ) : (
          <FeeSearchCell
            row={line.added}
            query={props.query}
            client={props.client}
            t={t}
            onPicked={patchAdded}
          />
        ),
    },
    {
      key: "from",
      label: t("customers.moveIn.fees.col.from"),
      cell: (line) =>
        line.plan !== undefined ? (
          <StatusPill tone="info">{t("customers.moveIn.fees.from.plan")}</StatusPill>
        ) : (
          <StatusPill tone="neutral">{t("customers.moveIn.fees.from.chargeCode")}</StatusPill>
        ),
    },
    {
      key: "amount",
      label: t("customers.moveIn.fees.col.amount"),
      numeric: true,
      cell: (line) => {
        if (line.plan !== undefined) {
          if (line.plan.amount !== null && waived(line)) {
            // Drawn, struck, and NOT in the Total (`chargedPlanRows`).
            return (
              <span className="text-neutral-700 line-through" data-deposit-waived="">
                <MoneyCell amount={line.plan.amount} currency={props.currency} />
              </span>
            );
          }
          return line.plan.amount === null ? (
            <span className="text-neutral-700">{feeRefusalText(t, line.plan.refusal ?? "")}</span>
          ) : (
            <MoneyCell amount={line.plan.amount} currency={props.currency} />
          );
        }
        const row = line.added;
        if (row.code === "") return <span aria-hidden="true" />;
        if (row.refusal !== null)
          return <span className="text-neutral-700">{feeRefusalText(t, row.refusal)}</span>;
        if (row.pricedBy === "per_case") {
          return (
            <CellText
              name="amount"
              label={t("customers.moveIn.fees.col.amount")}
              value={row.typed}
              onChange={(typed) => patchAdded({ ...row, typed })}
            />
          );
        }
        const amount = addedAmount(row);
        return amount === null ? (
          <span aria-hidden="true" />
        ) : (
          <MoneyCell amount={amount} currency={props.currency} />
        );
      },
    },
    {
      key: "note",
      label: t("customers.moveIn.fees.col.note"),
      cell: (line) =>
        line.plan !== undefined && waived(line) ? (
          <span className="text-neutral-700" data-waive-reason="">
            {own.depositWaive?.reason}
          </span>
        ) : line.plan !== undefined ? (
          <CellText
            name="note"
            label={t("customers.moveIn.fees.col.note")}
            value={own.planNotes[line.plan.code] ?? ""}
            placeholder={
              line.plan.kind === "deposit"
                ? t("customers.moveIn.fees.depositNote")
                : t("customers.moveIn.optional")
            }
            onChange={(note) =>
              set({
                ...own,
                planNotes: { ...own.planNotes, [(line.plan as MoveFeeRow).code]: note },
              })
            }
          />
        ) : (
          <CellText
            name="note"
            label={t("customers.moveIn.fees.col.note")}
            value={line.added.note}
            placeholder={t("customers.moveIn.optional")}
            onChange={(note) => patchAdded({ ...(line.added as AddedFee), note })}
          />
        ),
    },
  ];

  const emptyText =
    props.status === "pending"
      ? t("customers.moveIn.fees.loading")
      : props.status === "failed"
        ? t("customers.moveIn.fees.failed")
        : t("customers.moveIn.fees.empty");

  return (
    <>
      <TableArray<FeeLine>
        title={t("customers.moveIn.fees.title")}
        fact={t("customers.moveIn.fees.fact")}
        collection="move-in-fees"
        columns={columns}
        rows={props.status === "ready" ? lines : []}
        rowKey={(line) => line.key}
        emptyText={emptyText}
        cellError={(line, _index, column) =>
          props.tried &&
          column === "fee" &&
          line.added !== undefined &&
          addedAmount(line.added) === null
            ? t("customers.moveIn.fees.rowIncomplete")
            : undefined
        }
        footerCells={
          props.status === "ready"
            ? {
                fee: <span className="font-semibold">{t("customers.moveIn.fees.total")}</span>,
                amount: (
                  <span className="font-semibold" data-fees-total="">
                    <MoneyCell amount={feesTotal(own)} currency={props.currency} />
                  </span>
                ),
              }
            : undefined
        }
        onChange={(next) =>
          set({
            ...own,
            added: next
              .filter((line): line is { key: string; added: AddedFee } => line.added !== undefined)
              .map((l) => l.added),
          })
        }
        removeLabel={t("customers.moveIn.fees.remove")}
        rowRemoveBlocked={(line) =>
          line.plan !== undefined ? t("customers.moveIn.fees.planStays") : undefined
        }
        rowActions={(line) =>
          line.plan?.kind !== "deposit" || line.plan.amount === null ? undefined : (
            <RowActions>
              {waived(line) ? (
                <RowAction
                  label={t("customers.moveIn.fees.undoWaive")}
                  icon={<RollBackIcon />}
                  onClick={() => set({ ...own, depositWaive: null })}
                />
              ) : (
                <RowAction
                  label={t("customers.moveIn.fees.waive")}
                  /* The waive glyph, never the tick: beside an amount a tick
                     reads as "paid" (DEF-CUS-9778). */
                  icon={<WaiveIcon />}
                  onClick={() => setWaiving(true)}
                />
              )}
            </RowActions>
          )
        }
        actions={[
          {
            key: "add-fee",
            label: t("customers.moveIn.fees.add"),
            onClick: () =>
              set({
                ...own,
                added: [
                  ...own.added,
                  {
                    key: rowKey("fee"),
                    code: "",
                    label: "",
                    quoted: null,
                    pricedBy: null,
                    refusal: null,
                    typed: "",
                    note: "",
                  },
                ],
              }),
            blockedReason: props.status === "ready" ? undefined : emptyText,
          },
        ]}
        footerTrailing={
          <span className="text-base text-neutral-700">{t("customers.moveIn.fees.planStays")}</span>
        }
      />
      {waiving && (
        <WaiveDepositModal
          t={t}
          onWaive={(reason) => set({ ...own, depositWaive: { reason } })}
          onClose={() => setWaiving(false)}
        />
      )}
    </>
  );
}
