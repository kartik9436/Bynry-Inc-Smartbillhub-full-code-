// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — the Overview of one order,
//           images 03 (not completed) and 04 (completed).
// Tasks:    P1.2 (meter, unit, customer on the order) · P1.19 (the service by
//           its name) · P1.21 (Location and Customer are Overview panels; their
//           two tabs go — ruling 12) · P1.24 (the signature, viewable, ONLY on
//           a completed job — rulings 12 and 15) · P4.3 (a held job says why
//           and when)
// Rules:    hard rule 8 (the address is the premises', reached by walking) ·
//           B14 rule 31 (no database id is a visible value) · rule 32 (a
//           stated absence is closed — nobody signed renders NOTHING) · rule 43
//           (a piece of UI is a component)
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Panel } from "@/components/Panel";
import { InlineLinkTo } from "@/components/Surfaces";
import { RecordLink } from "@/components/RecordLink";
import { Dash, Fact, FactList } from "@/features/metering/meteringShared";
import { assetDetailPath, serviceLabel } from "@/features/assets/assetsShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import { premisesDetailPath, unitDetailPath } from "@/features/metering/meteringShared";
import { useTenant, useTenantPath } from "@/routing/tenantPath";
// A function import back into the page that mounts this one; it is only read
// at render time, so the cycle is harmless and the address stays in one place.
import { workOrderDetailPath } from "../OrderDetailPage";

import type { OrderChecklist } from "../workEndpoints";
import type { OrderPageFields } from "./orderPageEndpoints";
import { PhotoThumb } from "./PhotoViewer";
import type { ViewerPhoto } from "./PhotoViewer";
import { dueText, whenText } from "./orderFormat";
import type { Regional } from "./orderFormat";
import type { OrderRow } from "./orderShape";
import { closedBy, orderShape } from "./orderShape";

function Value(props: { children: ReactNode | null | undefined }) {
  return <>{props.children === null || props.children === undefined || props.children === "" ? <Dash /> : props.children}</>;
}

/** Record links (PO 2026-10-19): the value opens its record when the server
 *  served the id; otherwise it is plain text, and an empty one is a dash. */
function LinkedValue(props: { to: string | null; children: string | null | undefined }) {
  if (props.children === null || props.children === undefined || props.children === "") return <Dash />;
  return <RecordLink to={props.to}>{props.children}</RecordLink>;
}

/** FB-014 (DEF-FLD-10639, PO 2026-10-28): the phone's clock, said only past 5
 *  minutes. `offset_s` is server − phone, so a negative one is a fast phone. */
export function phoneClockOff(
  offsetS: number | null | undefined,
): { direction: "fast" | "slow"; minutes: number } | null {
  if (typeof offsetS !== "number" || Math.abs(offsetS) <= 5 * 60) return null;
  return { direction: offsetS < 0 ? "fast" : "slow", minutes: Math.round(Math.abs(offsetS) / 60) };
}

export function OrderOverview(props: {
  row: OrderRow;
  list: OrderChecklist | undefined;
  regional: Regional;
  /** The signature's own sign-off line from `GET …/signature`, read when the
   *  order row does not yet carry `signature` (lane SRV-1 serves it). */
  signature: OrderPageFields["signature"];
  onViewSignature: () => void;
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const tenant = useTenant();
  const row = props.row;
  const unit = row.location?.unit ?? null;
  const premisesId = row.location?.premises?.id ?? row.premise?.id ?? null;
  const accountId = row.account?.id ?? null;
  const completed = orderShape(row) === "completed";
  const details = props.list?.details ?? null;
  const asset = row.location?.asset ?? null;
  const hold = row.dispatch_state === "on_hold" ? row.hold ?? null : null;
  const closer = closedBy(row);
  const labourTime = row.closed?.labour_time ?? null;
  const phoneClock = phoneClockOff(row.closed?.device_clock?.offset_s);
  return (
    <div className="flex flex-col" data-order-overview={completed ? "completed" : "open"}>
      <Panel title={t("work.order.overview.title")}>
        <FactList>
          <Fact label={t("work.order.overview.type")}>
            <Value>{row.type}</Value>
          </Fact>
          {/* P1.2 — the meter the job is for. Only where the job HAS an asset:
              a leak at a kerb box has none, and a dash there would read as a
              meter nobody recorded. */}
          {asset !== null && (
            <Fact label={t("work.order.overview.meter")}>
              <LinkedValue to={asset.id ? tenantPath(assetDetailPath(asset.id)) : null}>{asset.asset_no}</LinkedValue>
            </Fact>
          )}
          <Fact label={t("work.order.overview.service")}>
            {row.service ? serviceLabel(row.service, t) : <Dash />}
          </Fact>
          <Fact label={t("work.order.overview.raisedBy")}>
            {row.source ? t(`work.orders.source.${row.source}`) : <Dash />}
          </Fact>
          {/* `DEF-WRK-9624` — the failed-outcome chain, both ways, by number. */}
          {row.follows ? (
            <Fact label={t("work.order.overview.follows")}>
              <InlineLinkTo to={workOrderDetailPath(tenant, row.follows.order_no)} data-follows={row.follows.order_no}>
                {row.follows.order_no}
              </InlineLinkTo>
            </Fact>
          ) : null}
          {row.follow_ups && row.follow_ups.length > 0 ? (
            <Fact label={t("work.order.overview.followUp")}>
              <span className="inline-flex flex-wrap gap-2">
                {row.follow_ups.map((one) => (
                  <InlineLinkTo key={one.order_no} to={workOrderDetailPath(tenant, one.order_no)} data-follow-up={one.order_no}>
                    {one.order_no}
                  </InlineLinkTo>
                ))}
              </span>
            </Fact>
          ) : null}
          <Fact label={t("work.order.overview.templateVersion")}>
            {props.list?.template_version === null || props.list?.template_version === undefined ? (
              <Dash />
            ) : (
              t("work.order.overview.versionValue", { version: props.list.template_version })
            )}
          </Fact>
          {hold !== null && (
            <>
              <Fact label={t("work.order.overview.heldFor")}>
                <Value>{hold.reason?.name}</Value>
              </Fact>
              <Fact label={t("work.order.overview.backOn")}>
                <Value>{whenText(hold.expected_return_on, props.regional)}</Value>
              </Fact>
            </>
          )}
          {completed ? (
            <>
              <Fact label={t("work.order.overview.outcome")}>
                {row.outcome ? t(`work.orders.outcome.${row.outcome}`) : <Dash />}
              </Fact>
              <Fact label={t("work.order.overview.closedBy")}>
                <Value>
                  {[closer.name, whenText(closer.at, props.regional)].filter(Boolean).join(" · ")}
                </Value>
              </Fact>
              {/* `DEF-WRK-4127` — the two times the labour is priced from,
                  shown where the office accepts or sends the job back. A close
                  that carried none shows neither (rule 32: absence is closed). */}
              {labourTime ? (
                <>
                  <Fact label={t("work.order.overview.arrived")}>
                    <Value>{whenText(labourTime.arrived_at, props.regional)}</Value>
                  </Fact>
                  <Fact label={t("work.order.overview.finished")}>
                    <Value>{whenText(labourTime.finished_at, props.regional)}</Value>
                  </Fact>
                </>
              ) : null}
              {/* FB-014 (PO 2026-10-28) — the phone's clock was off by more
                  than 5 minutes; the times above are already on ours. */}
              {phoneClock ? (
                <Fact label={t("work.order.overview.phoneClock")}>
                  <Value>
                    {t(
                      phoneClock.direction === "fast"
                        ? "work.order.overview.phoneClockFast"
                        : "work.order.overview.phoneClockSlow",
                      { minutes: phoneClock.minutes },
                    )}
                  </Value>
                </Fact>
              ) : null}
            </>
          ) : (
            // `DEF-WRK-9677` — a job raised with no priority has no `due_at`
            // of its own, and the server still measures it: the raise plus
            // the tenant's default target (`sla.due_at`, `target: default`,
            // PO answer (1) of 2026-10-04). Due shows the date the job is
            // measured against, never a dash beside a promise the server keeps.
            <Fact label={t("work.order.overview.due")}>
              <Value>{dueText(row.due_at ?? row.sla?.due_at ?? null, props.regional)}</Value>
            </Fact>
          )}
        </FactList>
      </Panel>

      <Panel title={t("work.order.location.title")}>
        <FactList>
          {/* Hard rule 8 — the address is the PREMISES', reached by walking. */}
          <Fact label={t("work.order.location.address")}>
            <LinkedValue to={premisesId ? tenantPath(premisesDetailPath(premisesId)) : null}>
              {row.location?.address ?? row.premise?.address}
            </LinkedValue>
          </Fact>
          {/* `DEF-WRK-9671` — a meter in the warehouse stands on no premises;
              where its asset carries a location note, that is where it is. It
              is never written as the Address above (hard rule 8). */}
          {row.stored_at ? (
            <Fact label={t("work.order.location.storedAt")}>
              <Value>{row.stored_at}</Value>
            </Fact>
          ) : null}
          <Fact label={t("work.order.location.unit")}>
            <LinkedValue to={unit?.id ? tenantPath(unitDetailPath(unit.id)) : null}>{unit?.label}</LinkedValue>
          </Fact>
          <Fact label={t("work.order.location.area")}>
            <Value>{row.area?.name}</Value>
          </Fact>
          <Fact label={t("work.order.location.gateCode")}>
            <Value>{details?.gate_code}</Value>
          </Fact>
          <Fact label={t("work.order.location.accessNotes")}>
            <Value>{details?.access_notes}</Value>
          </Fact>
        </FactList>
      </Panel>

      <Panel title={t("work.order.customer.title")}>
        <FactList>
          <Fact label={t("work.order.customer.account")}>
            <LinkedValue to={accountId ? tenantPath(accountDetailPath(accountId)) : null}>
              {row.customer?.account_no ?? row.account?.account_no}
            </LinkedValue>
          </Fact>
          <Fact label={t("work.order.customer.holder")}>
            {/* `DEF-WRK-9678` — images 03/04: *Ana Alvarez · C-00001*. */}
            <Value>
              {[row.customer?.name, row.customer?.customer_no].filter(Boolean).join(" · ") || null}
            </Value>
          </Fact>
          <Fact label={t("work.order.customer.phone")}>
            <Value>{row.customer?.phone}</Value>
          </Fact>
        </FactList>
      </Panel>

      {completed && props.signature !== null && props.signature !== undefined && (
        <SignaturePanel
          orderId={row.id}
          signature={props.signature}
          regional={props.regional}
          onView={props.onViewSignature}
        />
      )}
    </div>
  );
}

/**
 * `DEF-WRK-10635` — a refusal's door-hanger photograph as the viewer's one
 * picture, or null when there is none (yet). The attachment's id builds the
 * link through `photoSrc` and is never shown (B14 rule 31). The page's viewer
 * and the panel's thumbnail read this ONE function, so they cannot disagree.
 */
export function doorHangerPhoto(
  sig: OrderPageFields["signature"],
  t: (key: string) => string,
): ViewerPhoto | null {
  if (!sig || !sig.refused || !sig.door_hanger_attachment_id) return null;
  return {
    key: "door-hanger",
    title: t("work.order.signature.doorHanger"),
    attachmentId: sig.door_hanger_attachment_id,
    takenBy: sig.captured_by?.name ?? null,
    takenAt: sig.signed_at,
    forText: sig.decline_reason || t("work.order.signature.refused"),
  };
}

/**
 * P1.24 — the mark at a size a person can judge, who signed, when, who took
 * it; *View* opens it in the photo viewer. A refusal shows its reason instead
 * (`BR-WRK-046`: signed OR refused, never both), and its door-hanger photo —
 * or *Photo uploading* while the phone's bytes are on their way
 * (`DEF-WRK-10635`; the server's `door_hanger_uploading`, `DEF-WRK-10625`).
 */
function SignaturePanel(props: {
  orderId: string;
  signature: NonNullable<OrderPageFields["signature"]>;
  regional: Regional;
  onView: () => void;
}) {
  const { t } = useTranslation();
  const sig = props.signature;
  const hanger = doorHangerPhoto(sig, t);
  return (
    <Panel title={t("work.order.signature.title")}>
      <div className="flex flex-wrap items-start gap-6" data-signature="">
        {hanger !== null ? (
          <div className="flex flex-col gap-2">
            <PhotoThumb orderId={props.orderId} photo={hanger} onOpen={props.onView} />
            <button
              type="button"
              className="self-start text-sm font-semibold text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
              onClick={props.onView}
            >
              {t("work.order.signature.view")}
            </button>
          </div>
        ) : sig.refused && sig.door_hanger_uploading ? (
          <span className="text-sm text-warning-700" data-door-hanger="uploading">
            {t("work.order.signature.hangerUploading")}
          </span>
        ) : null}
        {!sig.refused && sig.image_url ? (
          <div className="flex flex-col gap-2">
            <img
              src={sig.image_url}
              alt={t("work.order.signature.markAlt")}
              className="h-28 w-80 border border-divider bg-bg object-contain"
            />
            <button
              type="button"
              className="self-start text-sm font-semibold text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
              onClick={props.onView}
            >
              {t("work.order.signature.view")}
            </button>
          </div>
        ) : null}
        <FactList>
          {sig.refused ? (
            <Fact label={t("work.order.signature.refused")}>
              <Value>{sig.decline_reason}</Value>
            </Fact>
          ) : (
            <Fact label={t("work.order.signature.signedBy")}>
              <Value>{sig.printed_name}</Value>
            </Fact>
          )}
          <Fact label={t("work.order.signature.when")}>
            <Value>{whenText(sig.signed_at, props.regional)}</Value>
          </Fact>
          <Fact label={t("work.order.signature.takenBy")}>
            <Value>{sig.captured_by?.name}</Value>
          </Fact>
        </FactList>
      </div>
    </Panel>
  );
}
