// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.08 — a move-in's Overview, every status from Not
//           started to Cancelled (images 09–17): four tiles that open their
//           tab, the *Details* grid, and *Still open*.
// Rules:    B14 rule 42 · rule 37 · rule 31 · rule 33 (a tile that cannot be
//           counted says so in ≤ 6 words, with the server's reason as `title`)
// Data:     `GET /moves/{MVI-…}` — `tiles`, `facts.details`, `still_open`
//           (CR-171 §9.LIST); the Messages tile reads the account's outbound
//           queue, the door §9.FLOW names for *Send a message*.
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getOutbound } from "@/api/endpoints";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { premisesDetailPath, unitDetailPath } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { accountDetailPath } from "../customersShared";
import { serviceRequestPath } from "../serviceRequestShared";
import type { JobDetail } from "./moveDetailEndpoints";
import { Day, DetailGroup, EmptyLine, FactGrid, LinkedValue, Stated, UnitValue, useServiceNames } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";

/** The account's queued messages — one read for the tile and the tab. */
export function useAccountMessages(accountId: string | null, page = 1, per = 25, client: ApiClient = api) {
  return useQuery({
    queryKey: ["move-detail-messages", accountId ?? "", page, per],
    enabled: accountId !== null,
    queryFn: () => getOutbound({ page, per, filters: { account_id: accountId ?? "" } }, client),
  });
}

export function MoveOverview(props: {
  record: JobDetail;
  regional: Regional;
  onTab: (tab: string) => void;
  client?: ApiClient;
}) {
  const { t, i18n } = useTranslation();
  const tenantPath = useTenantPath();
  const services = useServiceNames();
  const { tiles } = props.record;
  const d = props.record.facts.details;
  const accountId = d.account?.id ?? null;
  const messages = useAccountMessages(accountId, 1, 1, props.client);
  const notYet = t("customers.moveDetail.absent.notYet");

  const kpis: KpiTile[] = [
    {
      id: "openingReads",
      label: t("customers.moveDetail.tile.openingReads"),
      value:
        tiles.opening_reads.unavailable !== null || tiles.opening_reads.taken === null ? (
          <Stated
            absence={tiles.opening_reads.unavailable}
            label={t(`customers.moveDetail.readsAbsent.${tiles.opening_reads.unavailable?.code ?? "none"}`, {
              defaultValue: notYet,
            })}
          />
        ) : (
          t("customers.moveDetail.tile.xOfY", { x: tiles.opening_reads.taken, y: tiles.opening_reads.of })
        ),
      detail: tiles.opening_reads.recorded_on ? (
        <span className="inline-flex gap-1">
          {t("customers.moveDetail.tile.recorded")}
          <Day value={tiles.opening_reads.recorded_on} regional={props.regional} />
        </span>
      ) : undefined,
      press: { onPress: () => props.onTab("unit"), pressed: false },
    },
    {
      id: "fees",
      label: t("customers.moveDetail.tile.fees"),
      value:
        tiles.fees.total !== null ? (
          <MoneyCell amount={tiles.fees.total} currency={tiles.fees.currency ?? "USD"} />
        ) : (
          <Stated
            absence={tiles.fees.unavailable}
            label={tiles.fees.unavailable ? notYet : t("customers.moveDetail.tile.noFees")}
          />
        ),
      detail:
        tiles.fees.lines > 0 ? t("customers.moveDetail.tile.feeLines", { count: tiles.fees.lines }) : undefined,
      press: { onPress: () => props.onTab("billing"), pressed: false },
    },
    {
      id: "workOrders",
      label: t("customers.moveDetail.tile.workOrders"),
      value:
        tiles.work_orders.open === null ? (
          <Stated absence={tiles.work_orders.unavailable} label={t("customers.moveDetail.absent.notReadable")} />
        ) : (
          t("customers.moveDetail.tile.open", { count: tiles.work_orders.open })
        ),
      detail:
        tiles.work_orders.raised !== null
          ? t("customers.moveDetail.tile.raised", { count: tiles.work_orders.raised })
          : undefined,
      press: { onPress: () => props.onTab("work"), pressed: false },
    },
    {
      id: "messages",
      label: t("customers.moveDetail.tile.messages"),
      value:
        accountId === null ? (
          <Stated label={notYet} />
        ) : messages.data ? (
          t("customers.moveDetail.tile.queued", { count: messages.data.count })
        ) : (
          "…"
        ),
      press: { onPress: () => props.onTab("messages"), pressed: false },
    },
  ];

  const plan = d.plan;
  return (
    <div className="flex flex-col gap-6" data-move-overview="move">
      <KPIStrip kpis={kpis} label={t("customers.moveDetail.tilesLabel")} />
      <DetailGroup title={t("customers.moveDetail.section.details")} name="details">
        <FactGrid
          name="move-details"
          facts={[
            { id: "moveNo", label: t("customers.moveDetail.fact.moveIn"), value: d.move_no ?? <Stated label={notYet} /> },
            {
              id: "fromRequest",
              label: t("customers.moveDetail.fact.fromRequest"),
              value: d.from_request ? (
                <InlineLinkTo to={tenantPath(serviceRequestPath(d.from_request.id))}>
                  {d.from_request.request_no}
                </InlineLinkTo>
              ) : (
                <Stated label={t("customers.moveDetail.absent.noRequest")} />
              ),
            },
            {
              id: "movedInOn",
              label: t("customers.moveRecord.fact.movedInOn"),
              value: d.moved_in_on ? (
                <Day value={d.moved_in_on} regional={props.regional} />
              ) : (
                <Stated label={t("customers.moveDetail.absent.notChosen")} />
              ),
            },
            {
              id: "customer",
              label: t("customers.moveDetail.fact.customer"),
              value: d.customer?.name ? (
                <span>{[d.customer.customer_no, d.customer.name].filter(Boolean).join(" · ")}</span>
              ) : (
                <Stated label={notYet} />
              ),
            },
            {
              id: "account",
              label: t("customers.moveDetail.fact.account"),
              value: d.account ? (
                <InlineLinkTo to={tenantPath(accountDetailPath(d.account.id))}>{d.account.account_no}</InlineLinkTo>
              ) : (
                <Stated label={notYet} />
              ),
            },
            // CR-181-BRC10 F3 — this move-in REOPENED the account; the
            // clerk's balance choice and the figure the books held at Complete.
            ...(props.record.reopened
              ? [
                  {
                    id: "reopen",
                    label: t("customers.moveIn.reopen.title"),
                    value: (
                      <span data-move-reopened={props.record.reopened.account_no}>
                        {t("customers.moveIn.reopen.reopened", { account: props.record.reopened.account_no })}
                        {props.record.reopened.balance_choice === "carry" &&
                        props.record.reopened.balance_at_complete !== null ? (
                          <>
                            {" · "}
                            {t("customers.moveIn.reopen.carried", {
                              amount: formatMoney(
                                props.record.reopened.balance_at_complete,
                                props.record.reopened.currency ?? "USD",
                                i18n.language,
                              ),
                            })}
                          </>
                        ) : props.record.reopened.balance_choice === "pay_first" ? (
                          <>
                            {" · "}
                            {t("customers.moveIn.reopen.paidFirst")}
                          </>
                        ) : null}
                      </span>
                    ),
                  },
                ]
              : []),
            {
              id: "plan",
              label: t("customers.moveDetail.fact.plan"),
              value: plan?.name ? (
                <span>
                  {plan.name}
                  {plan.version !== null ? ` · ${t("customers.moveDetail.planVersion", { n: plan.version })}` : ""}
                </span>
              ) : (
                <Stated label={t("customers.moveDetail.absent.noPlan")} />
              ),
            },
            {
              id: "unit",
              label: t("customers.moveDetail.fact.unit"),
              value: d.unit ? (
                <UnitValue to={tenantPath(unitDetailPath(d.unit.id))} unit={d.unit} />
              ) : (
                <Stated label={t("customers.moveDetail.absent.noUnit")} />
              ),
            },
            {
              id: "building",
              label: t("customers.moveDetail.fact.building"),
              value: d.building ? (
                <LinkedValue
                  to={d.building.id ? tenantPath(premisesDetailPath(d.building.id)) : null}
                  label={d.building.premise_no}
                  rest={d.building.address}
                />
              ) : (
                <Stated label={t("customers.moveDetail.absent.noUnit")} />
              ),
            },
            {
              id: "services",
              label: t("customers.moveDetail.tile.services"),
              value: services((d.services ?? []).map((s) => s.code)) || <Stated label={notYet} />,
            },
            {
              id: "fromAccount",
              label: t("customers.moveRecord.fact.fromAccount"),
              value: d.from_account?.value ?? (
                <Stated absence={d.from_account?.unavailable} label={t("customers.moveDetail.absent.firstOccupant")} />
              ),
            },
            {
              id: "earliest",
              label: t("customers.moveRecord.fact.earliestStart"),
              value: d.earliest_legal_start?.value ? (
                <Day value={d.earliest_legal_start.value} regional={props.regional} />
              ) : (
                <Stated
                  absence={d.earliest_legal_start?.unavailable}
                  label={t("customers.moveDetail.absent.noEarlierTenancy")}
                />
              ),
            },
            {
              id: "committedBy",
              label: t("customers.moveRecord.fact.committedBy"),
              value: d.committed_by?.value?.name ? (
                <span>
                  {d.committed_by.value.name}
                  {d.committed_by.value.at ? (
                    <>
                      {" · "}
                      <Day value={d.committed_by.value.at} regional={props.regional} />
                    </>
                  ) : null}
                </span>
              ) : (
                <Stated absence={d.committed_by?.unavailable} label={notYet} />
              ),
            },
          ]}
        />
      </DetailGroup>
      <DetailGroup title={t("customers.moveDetail.section.stillOpen")} name="still-open">
        {props.record.still_open.length === 0 ? (
          <EmptyLine>{t("customers.moveDetail.stillOpen.none")}</EmptyLine>
        ) : (
          <PlainTable data-still-open="">
            <thead>
              <tr>
                <th>{t("customers.moveDetail.col.item")}</th>
                <th>{t("customers.moveDetail.col.state")}</th>
              </tr>
            </thead>
            <tbody>
              {props.record.still_open.map((row, index) =>
                row.kind === "work_order" ? (
                  <tr key={`wo-${row.order.order_no}`}>
                    <td>
                      <InlineLinkTo to={tenantPath(`/work/orders/${encodeURIComponent(row.order.order_no)}`)}>
                        {row.order.order_no}
                      </InlineLinkTo>
                    </td>
                    <td>
                      <StatusPill tone="warning">{t("customers.moveDetail.stillOpen.workOpen")}</StatusPill>
                    </td>
                  </tr>
                ) : (
                  <tr key={`read-${row.register ?? index}`}>
                    <td>
                      {t("customers.moveDetail.stillOpen.openingRead")} · {row.register}
                    </td>
                    <td>
                      <StatusPill tone="neutral">{t("customers.moveDetail.stillOpen.notRead")}</StatusPill>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </PlainTable>
        )}
      </DetailGroup>
    </div>
  );
}
