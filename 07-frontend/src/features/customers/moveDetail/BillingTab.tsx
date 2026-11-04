// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.11 — the Billing tab (image 26): tiles, *Plan and
//           preferences*, *Fees* with its Total, *Payment and deposit*.
// Rules:    CLAUDE.md hard rule 2 (every amount displays 2 places, through
//           MoneyCell; nothing re-rounds) · B14 rule 33 (a fact the server
//           cannot answer says so in ≤ 6 words, its reason as `title`) ·
//           `OQ-BIL-12788` closed (a): no fee is taxed at move-in, so the drawn
//           *Taxable* column is not drawn — every row would read *No*.
// Data:     `GET /accounts/{id}` (plan, preferences, tax exemption) · the move's
//           `fee_lines` (§9.LIST, added by this lane), `tiles.fees`,
//           `money_taken`, `still_owed.carry_forward`.
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountDetail, getPayments } from "@/api/endpoints";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { PlainTable } from "@/components/Surfaces";

import { ExemptionSummary } from "../AccountTaxExemption";
import type { JobDetail } from "./moveDetailEndpoints";
import { Day, DetailGroup, EmptyLine, FactGrid, Stated } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";

export interface MoveFeeLineRow {
  seq: number;
  kind: string;
  source: string;
  code: string;
  description: string | null;
  amount: string | null;
  currency: string;
}

export function BillingTab(props: {
  record: JobDetail & { fee_lines?: MoveFeeLineRow[] };
  regional: Regional;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const accountId = props.record.facts.details.account?.id ?? null;
  const account = useQuery({
    queryKey: ["move-detail-account", accountId ?? ""],
    enabled: accountId !== null,
    queryFn: () => getAccountDetail(accountId ?? "", client),
  });
  // What was paid — the account's own payments (`GET /payments?f.account_id`,
  // the S21 Payments tab's read). The record's `tiles.fees.paid` is not served
  // (§9.LIST names it P1.13's), so the payments ledger is read instead of a
  // figure being derived here; its `totals.amount` is the server's own sum.
  const payments = useQuery({
    queryKey: ["move-detail-payments", accountId ?? ""],
    enabled: accountId !== null,
    queryFn: () => getPayments({ filters: { account_id: accountId ?? "" }, sort: "posted_at", dir: "asc", per: 50 }, client),
  });
  const paid = payments.data ?? null;
  const fees = props.record.tiles.fees;
  const lines = props.record.fee_lines ?? [];
  const money = props.record.money_taken;
  const currency = fees.currency ?? money.currency ?? "USD";
  const notRecorded = t("customers.moveDetail.absent.notRecorded");
  const amount = (value: string | null | undefined, absence?: Parameters<typeof Stated>[0]["absence"]) =>
    value ? <MoneyCell amount={value} currency={currency} /> : <Stated absence={absence} label={notRecorded} />;
  const a = account.data;
  const plan = a?.unit_plan ?? props.record.facts.details.plan;
  const onOff = (on: boolean | null | undefined) =>
    on === null || on === undefined ? notRecorded : on ? t("customers.moveDetail.on") : t("customers.moveDetail.off");

  const awaiting = money.awaiting_clearance?.value ?? null;
  const notCleared = (value: string) => (
    <span data-not-cleared="">
      {t("customers.moveDetail.notClearedYet", {
        amount: formatMoney(value, currency),
      })}
    </span>
  );

  const kpis: KpiTile[] = [
    {
      id: "fees",
      label: t("customers.moveDetail.tile.fees"),
      value: amount(fees.total, fees.unavailable),
      detail: lines.length > 0 ? t("customers.moveDetail.tile.feeLines", { count: lines.length }) : undefined,
    },
    {
      id: "paid",
      label: t("customers.moveDetail.tile.paid"),
      value:
        paid === null ? (
          "…"
        ) : paid.totals.amount !== null ? (
          <MoneyCell amount={paid.totals.amount} currency={paid.totals.currency ?? currency} />
        ) : (
          <Stated label={notRecorded} />
        ),
      detail:
        paid !== null && paid.results.length > 0
          ? [paid.results[0].method_name, paid.results[0].confirmation].filter(Boolean).join(" ")
          : undefined,
    },
    {
      id: "deposit",
      label: t("customers.moveDetail.tile.depositTaken"),
      value: amount(money.taken.value, money.taken.unavailable),
      // `DEF-CUS-9755` — a check in the drawer is said as such, never as money
      // still to collect; it counts as paid for the first bill (`DEF-BIL-9751`,
      // PO 2026-10-06) and is still not cleared, which is what this says.
      detail: awaiting ? (
        notCleared(awaiting)
      ) : money.taken_on ? (
        <Day value={money.taken_on} regional={props.regional} />
      ) : undefined,
    },
    {
      id: "stillToCollect",
      label: t("customers.moveDetail.tile.stillToCollect"),
      value: amount(money.still_to_collect.value, money.still_to_collect.unavailable),
    },
  ];

  return (
    <div className="flex flex-col gap-6" data-move-tab="billing">
      <KPIStrip kpis={kpis} />
      <DetailGroup title={t("customers.moveDetail.section.planPreferences")} name="plan">
        {accountId === null ? (
          <EmptyLine>{t("customers.moveDetail.absent.noAccountYet")}</EmptyLine>
        ) : (
          <FactGrid
            name="move-plan"
            facts={[
              {
                id: "plan",
                label: t("customers.moveDetail.fact.plan"),
                value: plan?.name ? (
                  <span>
                    {plan.name}
                    {plan.version !== null && plan.version !== undefined
                      ? ` · ${t("customers.moveDetail.planVersion", { n: plan.version })}`
                      : ""}
                    {plan.since ? (
                      <>
                        {" · "}
                        {t("customers.moveDetail.planSince")} <Day value={plan.since} regional={props.regional} />
                      </>
                    ) : null}
                  </span>
                ) : (
                  <Stated label={t("customers.moveDetail.absent.noPlan")} />
                ),
              },
              {
                id: "tax",
                label: t("customers.moveDetail.fact.tax"),
                // `DEF-CUS-9775` — the certificate the move-in recorded, read
                // with the blanket flag (ruling (A) leaves the flag false).
                value: !a ? (
                  "…"
                ) : (
                  <ExemptionSummary
                    facts={a}
                    taxed={t("customers.moveDetail.taxed")}
                    renderDate={(iso) => <Day value={iso} regional={props.regional} />}
                  />
                ),
              },
              { id: "paperless", label: t("customers.moveDetail.fact.paperless"), value: a ? onOff(a.paperless) : "…" },
              { id: "autopay", label: t("customers.moveDetail.fact.autopay"), value: a ? onOff(a.autopay) : "…" },
              {
                id: "texts",
                label: t("customers.moveDetail.fact.textReminders"),
                value: a ? onOff(a.sms_reminders) : "…",
              },
              {
                id: "language",
                label: t("customers.account.field.preferredLanguage"),
                value: a?.preferred_language ?? notRecorded,
              },
            ]}
          />
        )}
      </DetailGroup>
      <DetailGroup title={t("customers.moveDetail.tile.fees")} name="fees">
        {lines.length === 0 ? (
          <EmptyLine>{t("customers.moveDetail.fees.none")}</EmptyLine>
        ) : (
          <PlainTable data-move-fees="">
            <thead>
              <tr>
                <th>{t("customers.moveDetail.col.fee")}</th>
                <th>{t("customers.moveDetail.col.from")}</th>
                <th>{t("customers.moveDetail.col.amount")}</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => (
                <tr key={line.seq}>
                  <td>{[line.code, line.description].filter(Boolean).join(" · ")}</td>
                  <td>{t(`customers.moveDetail.feeSource.${line.source}`, { defaultValue: line.source })}</td>
                  <td>
                    {line.amount ? <MoneyCell amount={line.amount} currency={line.currency} /> : ""}
                  </td>
                </tr>
              ))}
              <tr>
                <td className="font-semibold">{t("customers.moveDetail.fees.total")}</td>
                <td />
                <td className="font-semibold">
                  {fees.total ? <MoneyCell amount={fees.total} currency={currency} /> : ""}
                </td>
              </tr>
            </tbody>
          </PlainTable>
        )}
      </DetailGroup>
      <DetailGroup title={t("customers.moveDetail.section.paymentDeposit")} name="payment">
        <FactGrid
          name="move-payment"
          facts={[
            {
              id: "paid",
              label: t("customers.moveDetail.tile.paid"),
              value:
                paid !== null && paid.results.length > 0 ? (
                  <span className="flex flex-col">
                    {paid.results.map((row) => (
                      <span key={row.id}>
                        <MoneyCell amount={row.amount} currency={row.currency} />
                        {" · "}
                        {[row.method_name, row.confirmation].filter(Boolean).join(" ")}
                        {" · "}
                        <Day value={row.posted_at} regional={props.regional} />
                      </span>
                    ))}
                  </span>
                ) : (
                  <Stated label={t("customers.moveDetail.absent.nothingPaid")} />
                ),
            },
            {
              id: "receipt",
              label: t("customers.moveDetail.fact.receipt"),
              value:
                paid !== null && paid.results.length > 0
                  ? paid.results.map((row) => row.payment_no).filter(Boolean).join(", ")
                  : <Stated label={t("customers.moveDetail.absent.nothingPaid")} />,
            },
            {
              id: "required",
              label: t("customers.moveDetail.fact.depositRequired"),
              value: amount(money.required.value, money.required.unavailable),
            },
            {
              id: "taken",
              label: t("customers.moveDetail.fact.depositTaken"),
              value: money.taken.value ? (
                <span>
                  <MoneyCell amount={money.taken.value} currency={currency} />
                  {money.taken_on ? (
                    <>
                      {" · "}
                      <Day value={money.taken_on} regional={props.regional} />
                    </>
                  ) : null}
                  {awaiting ? (
                    <>
                      {" · "}
                      {notCleared(awaiting)}
                    </>
                  ) : null}
                </span>
              ) : (
                <Stated absence={money.taken.unavailable} label={notRecorded} />
              ),
            },
            {
              id: "still",
              label: t("customers.moveDetail.tile.stillToCollect"),
              value: amount(money.still_to_collect.value, money.still_to_collect.unavailable),
            },
            {
              id: "carried",
              label: t("customers.moveDetail.fact.carriedOver"),
              value:
                props.record.still_owed.carry_forward.value ?? (
                  <Stated
                    absence={props.record.still_owed.carry_forward.unavailable}
                    label={t("customers.moveDetail.absent.noneFound")}
                  />
                ),
            },
          ]}
        />
      </DetailGroup>
    </div>
  );
}
