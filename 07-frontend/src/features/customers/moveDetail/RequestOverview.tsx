// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.05 — a move-in REQUEST's Overview (image 03): four
//           tiles (Move-in date · Services · Documents · Unit), then the
//           *Request* and *Who* grids, three across.
// Rules:    B14 rule 42 (built from the image) · rule 37 (its figures are
//           illustrations) · rule 31 (numbers shown, ids in hrefs) · rule 33
// Data:     `GET /moves/{SR-…}` — `tiles`, `facts.request`, `facts.who`
//           (CR-171 §9.LIST). Nothing here is derived that the server serves.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { premisesDetailPath, unitDetailPath } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import type { RequestDetail } from "./moveDetailEndpoints";
import { Day, DetailGroup, FactGrid, LinkedValue, Stated, UnitValue, useServiceNames } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";

export function RequestOverview(props: {
  record: RequestDetail;
  regional: Regional;
  onTab: (tab: string) => void;
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const services = useServiceNames();
  const { tiles, facts } = props.record;
  const request = facts.request;
  const who = facts.who;
  const notGiven = t("customers.moveDetail.absent.notGiven");
  const dash = (value: string | null | undefined) => (value ? value : <Stated label={notGiven} />);

  const docsTotal = tiles.documents.outstanding?.params?.total ?? null;
  const docsVerified = tiles.documents.outstanding?.params?.verified ?? null;

  const kpis: KpiTile[] = [
    {
      id: "moveInDate",
      label: t("customers.moveDetail.tile.moveInDate"),
      value: tiles.move_in_date.value ? (
        <Day value={tiles.move_in_date.value} regional={props.regional} />
      ) : (
        t("customers.moveDetail.absent.notChosen")
      ),
      detail: t("customers.moveDetail.tile.requested"),
    },
    {
      id: "services",
      label: t("customers.moveDetail.tile.services"),
      value: String(tiles.services.count),
      detail: services(tiles.services.codes) || undefined,
    },
    {
      id: "documents",
      label: t("customers.moveDetail.tile.documents"),
      value:
        docsTotal !== null && docsVerified !== null
          ? t("customers.moveDetail.tile.xOfY", { x: docsVerified, y: docsTotal })
          : String(tiles.documents.attached),
      detail:
        docsTotal !== null
          ? t("customers.moveDetail.tile.verified")
          : t("customers.moveDetail.tile.attached"),
      press: { onPress: () => props.onTab("documents"), pressed: false },
    },
    {
      id: "unit",
      label: t("customers.moveDetail.tile.unit"),
      value:
        tiles.unit.vacant === null
          ? t("customers.moveDetail.absent.notRecorded")
          : tiles.unit.vacant
            ? t("customers.moveDetail.unit.vacant")
            : t("customers.moveDetail.unit.occupied"),
      // `DEF-CUS-9763` — image 03's caption is the unit NUMBER.
      detail: tiles.unit.unit_no ?? tiles.unit.unit_label ?? undefined,
    },
  ];

  const plan = request.plan;
  const type = request.customer_type;
  const matched = who.matched;

  return (
    <div className="flex flex-col gap-6" data-move-overview="request">
      <KPIStrip kpis={kpis} label={t("customers.moveDetail.tilesLabel")} />
      <DetailGroup title={t("customers.moveDetail.section.request")} name="request">
        <FactGrid
          name="move-request"
          facts={[
            { id: "request", label: t("customers.moveDetail.fact.request"), value: request.request_no },
            {
              id: "from",
              label: t("customers.moveDetail.fact.from"),
              value: (
                <span>
                  {request.channel
                    ? t(`customers.serviceRequest.channel.${request.channel}`, { defaultValue: notGiven })
                    : notGiven}
                  {request.submitted_on ? (
                    <>
                      {" · "}
                      <Day value={request.submitted_on} regional={props.regional} />
                    </>
                  ) : null}
                </span>
              ),
            },
            {
              id: "moveInDate",
              label: t("customers.moveDetail.tile.moveInDate"),
              value: request.move_in_date ? (
                <Day value={request.move_in_date} regional={props.regional} />
              ) : (
                <Stated label={t("customers.moveDetail.absent.notChosen")} />
              ),
            },
            {
              id: "unit",
              label: t("customers.moveDetail.fact.unit"),
              value: request.unit ? (
                <UnitValue to={tenantPath(unitDetailPath(request.unit.id))} unit={request.unit} />
              ) : (
                <Stated label={t("customers.moveDetail.absent.noUnit")} />
              ),
            },
            {
              id: "building",
              label: t("customers.moveDetail.fact.building"),
              value: request.building ? (
                <LinkedValue
                  to={request.building.id ? tenantPath(premisesDetailPath(request.building.id)) : null}
                  label={request.building.premise_no}
                  rest={request.building.address}
                />
              ) : (
                <Stated label={t("customers.moveDetail.absent.noUnit")} />
              ),
            },
            {
              id: "unitIs",
              label: t("customers.moveDetail.fact.unitIs"),
              value:
                request.unit_is_vacant === null
                  ? <Stated label={t("customers.moveDetail.absent.notRecorded")} />
                  : request.unit_is_vacant
                    ? t("customers.moveDetail.unit.vacant")
                    : t("customers.moveDetail.unit.occupied"),
            },
            {
              id: "services",
              label: t("customers.moveDetail.tile.services"),
              value: dash(services(request.services.map((s) => s.code))),
            },
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
              id: "customerType",
              label: t("customers.moveDetail.fact.customerType"),
              value: dash([type.account_type_name, type.account_subtype].filter(Boolean).join(" · ")),
            },
          ]}
        />
      </DetailGroup>
      <DetailGroup title={t("customers.moveDetail.section.who")} name="who">
        <FactGrid
          name="move-who"
          facts={[
            {
              id: "kind",
              label: t("customers.moveDetail.fact.personOrCompany"),
              value: t(`customers.moveDetail.kind.${who.kind}`),
            },
            { id: "name", label: t("customers.moveDetail.fact.name"), value: dash(who.name) },
            {
              id: "matched",
              label: t("customers.moveDetail.fact.matched"),
              value: matched ? (
                <span>{[matched.customer_no, matched.name].filter(Boolean).join(" · ")}</span>
              ) : (
                t(
                  who.matched_absence?.code === "no_existing_customer"
                    ? "customers.moveDetail.matched.none"
                    : "customers.moveDetail.matched.notSearched",
                )
              ),
            },
            { id: "email", label: t("customers.moveDetail.fact.email"), value: dash(who.email) },
            { id: "phone", label: t("customers.moveDetail.fact.phone"), value: dash(who.phone) },
            {
              id: "mailing",
              label: t("customers.moveDetail.fact.mailing"),
              value: who.mailing_same
                ? t("customers.moveDetail.mailing.same")
                : dash(
                    [who.mailing?.line1, who.mailing?.city, who.mailing?.state, who.mailing?.postal_code]
                      .filter(Boolean)
                      .join(", "),
                  ),
            },
          ]}
        />
      </DetailGroup>
    </div>
  );
}
