// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — ONE ORDER, TWO SHAPES,
//           built from images 03–11 (B14 rules 42, 44, 37): four tabs (ruling
//           12), the plan before completion and the record after it (rulings
//           15, 17), *Mark complete* and the office's ticks GONE (ruling 18),
//           *Accept ✓* on a completed job (P1.32), the hold dialog and *Resume*
//           (P4.3). The pieces are components under `orderPage/` (rule 43).
// Story:    US-WRK-033 (the work order detail) · US-WRK-032 (everything drawn
//           is the ORDER's own copy). Screen: Work-008 ↔ WRK-02
// Rules:    BR-WRK-008 (copy, never link) · BR-MET-110 (the field completes,
//           the office accepts) · B14 rules 2 (actions top right — ruling 16)
//           · 6 (danger tier) · 11 (a consequence before an irreversible
//           commit) · 21 (Tailwind; on `route-b-migrated.txt`) · 31 (no
//           database id is a visible value) · 33 (text caps)
// Tests:    OrderDetailPage.test.tsx · OrderDetailPage.dom.test.tsx ·
//           orderPage/orderPage.dom.test.tsx
// Impacts:  orderPage/* · OrdersPage.tsx (the row's 👁 opens this) ·
//           src/routing/screenIds.ts (WRK-02) · src/App.tsx (one route)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE BACK OFFICE NEVER COMPLETES A JOB; IT ONLY ACCEPTS** (ruling 18, PO
// 2026-09-24: *"back office cannot complete the job it can only accept it"*;
// `BR-MET-110`). Until CR-168 this page led its head with *Mark complete* and
// drew every safety line and task as a tick box the office could press — the
// before-walk closed WO-0037 from a desk with 0 of 3 required photographs
// (`DEF-WRK-9525`). Both are REMOVED, not disabled: a greyed button would still
// say the office may one day do it. The server refuses the same act on its own
// (lane SRV-1, `submit_field_result`) — this screen is the courtesy and the
// server is the rule (hard-won law 1).
//
// ⚠ **EVERYTHING THIS SCREEN DRAWS IS THE ORDER'S OWN COPY** (`BR-WRK-008`).
// Not one value is read through `template_id`, so publishing v3 of a template
// never changes what a job says it involved.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useWorkOrderStatusAnalytics } from "@/analytics";
import { apiHref } from "@/api/apiHref";
import { api, diagnosticOf, isApiError, refusalParams } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CustomFieldsView } from "@/components/CustomFields";
import { formatDate } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { acceptWorkOrder } from "@/features/customers/newConnectEndpoints";
import { detailTabFrom, useRegional } from "@/features/metering/meteringShared";
import type { DetailTab } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { WORK_ORDERS_ROUTE } from "./WorkShell";
import { dispatchStateTone, workOrderOutcomeTone, workOrderStateTone } from "./OrdersPage";
import {
  cancelWorkOrder,
  getCloseReadiness,
  getOrderAttachments,
  getOrderChecklist,
  getOrderSignature,
  getWorkOrder,
  getWorkOrderByNumber,
} from "./workEndpoints";
import { HoldDialog } from "./orderPage/HoldDialog";
import {
  OrderChecklistTab,
  OrderPartsTab,
  OrderPhotosPanel,
  checklistPhotos,
} from "./orderPage/OrderChecklist";
import { OrderHistoryTab } from "./orderPage/OrderHistory";
import { doorHangerPhoto, OrderOverview } from "./orderPage/OrderOverview";
import { duplicateOrder, getOrderHistory, resumeOrder } from "./orderPage/orderPageEndpoints";
import { SendBackDialog } from "./orderPage/SendBackDialog";
import { OrderFieldPanels } from "./field/OrderFieldPanels";
import { SendAlertDialog } from "./field/SendAlertDialog";
import type { OrderPageFields } from "./orderPage/orderPageEndpoints";
import { whenText, windowText } from "./orderPage/orderFormat";
import type { Regional } from "./orderPage/orderFormat";
import { closedBy, isAccepted, isStopped, orderShape } from "./orderPage/orderShape";
import type { OrderRow } from "./orderPage/orderShape";
import type { TechnicianAcceptance } from "./workEndpoints";
import { PhotoViewer } from "./orderPage/PhotoViewer";
import type { ViewerPhoto } from "./orderPage/PhotoViewer";

/** r10's own badge for the order detail — `01-overview.md` §6, Work-008 ↔ WRK-02. */
export const WORK_ORDER_DETAIL_SCREEN = "WRK-02";

/**
 * The address `Work-008` answers to. One constant, so the list, the drawer and
 * this screen cannot disagree about where an order opens (law 5).
 *
 * ⚠ **NO `/:tenant` HERE** (`DEF-WRK-4051`): `App.tsx` mounts every Work route
 * as a CHILD of a `:tenant` route, so a constant carrying the prefix becomes
 * `:tenant/:tenant/…` and matches nothing.
 */
export const WORK_ORDER_DETAIL_ROUTE = `${WORK_ORDERS_ROUTE}/:orderNo`;

/** The SCREEN-REGISTRY spelling, which DOES carry the tenant. */
export const WORK_ORDER_DETAIL_SCREEN_PATH = `/:tenant${WORK_ORDERS_ROUTE}/:orderNo`;

export function workOrderDetailPath(tenant: string, orderId: string): string {
  return `/${tenant}${WORK_ORDERS_ROUTE}/${orderId}`;
}

/**
 * ⚠ **THE HOLD MACHINERY, EMPTY AND KEPT** (CR-070 wave L). A control this
 * screen draws and has not wired is declared here with the ENDPOINT that
 * releases it; `OrderDetailPage.dom.test.tsx` fails the day a hold names an
 * endpoint on `ORDER_DETAIL_WIRED_ENDPOINTS`. Empty is a statement: every
 * control drawn on 03–11 that this round builds is live.
 *
 * ⚠ ***Send back…* (images 04 and 06) WAS NOT DRAWN, AND THAT WAS NOT A HOLD
 * — UNTIL `DEF-WRK-9675`.** This paragraph said it would land *"WITH its
 * endpoint, in the lane that builds it"*; lane SRV-2 built the endpoint in
 * 2.500.0 and was server-only, so the promise named a lane that never opened
 * this file and the door stayed shut for five rounds. A promise addressed to
 * another lane is a comment, not a plan (hard-won law 1). It is wired now
 * (lane FIX-8B) and on `ORDER_DETAIL_WIRED_ENDPOINTS` below.
 */
export const ORDER_DETAIL_HELD_CONTROLS: readonly {
  readonly control: string;
  readonly reasonKey: string;
  readonly releasedBy: string;
}[] = [] as const;

/**
 * ⚠ **EVERY ENDPOINT THIS SCREEN COMMITS TO, AS DATA.** The hold machinery
 * above asks *does this screen already CALL it*; this list is what makes that
 * answerable, and the dom suite asserts each entry is a path a button is
 * PROVED to reach.
 *
 * ⚠ **`POST …/field-result` LEFT THIS LIST WITH *Mark complete* (ruling 18).**
 * `orderPage.dom.test.tsx` fails if this screen ever posts it again.
 */
export const ORDER_DETAIL_WIRED_ENDPOINTS = [
  "POST /work-orders/{id}/hold",
  "POST /work-orders/{id}/resume",
  "POST /work-orders/{id}/cancel",
  "POST /work-orders/{id}/accept",
  // `DEF-WRK-9675` — *Send back…* on a finished job, before it is accepted.
  "POST /work-orders/{id}/send-back",
  // `DEF-WRK-9690` — *Duplicate*: the same job raised again (beta #28).
  "POST /work-orders/{id}/duplicate",
] as const;

/**
 * ⚠ **`Reassign…` IS A DOOR, NOT A COMMIT.** It opens `Work-021`, the screen
 * that owns the picker, the candidate list and the advice beside every name;
 * a second picker here would be a second place for those rules to be
 * forgotten.
 */
export const ORDER_DETAIL_REASSIGN_OPENS = "/work/orders/:orderNo/edit";

/** Ruling 12, PO 2026-09-24: *"in overview tab only, no need of extra tabs"* —
 *  FOUR tabs; Location and Customer are panels on the Overview (P1.21). */
export const ORDER_DETAIL_TABS = ["overview", "checklist", "parts", "audit"] as const;

export type OrderDetailTabId = (typeof ORDER_DETAIL_TABS)[number];

/**
 * The SERVER's own sentence for a refusal, or a fallback. `BR-SHL-025` puts the
 * rule on the server, so the server is also where the WORDS live.
 */
function serverSentence(error: unknown, fallback: string, t?: TFunction): string {
  // ⚠ `DEF-WRK-9682` — the client throws an `ApiError` carrying the server's
  // `messageKey` and `params`, never `data.message`. Reading only `data` meant
  // every refusal (Accept over a job naming no meter, over photos uploading)
  // toasted the fallback. The KEY is the server's sentence, in the clerk's
  // language, when the catalogue has it.
  if (t !== undefined && isApiError(error) && error.messageKey) {
    const said = t(error.messageKey, refusalParams(error.params, error.traceId));
    // i18next answers the KEY itself for a key no catalogue has.
    if (said && said !== error.messageKey) return said;
  }
  const detail = (error as { data?: { message?: string; detail?: string } } | null)?.data;
  return detail?.message ?? detail?.detail ?? fallback;
}

/**
 * Is this address segment a database id, or the reference a person reads?
 * (`DEF-WRK-4518`) — a uuid goes straight to the id route; anything else is
 * resolved once through `GET /work-orders/by-number/{order_no}`.
 */
export function isOrderId(segment: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment);
}

type ViewerState = { list: "checklist" | "signature"; index: number } | null;

export function OrderDetailPage(props: { client?: ApiClient }) {
  const client = props.client ?? api;
  const regional: Regional = useRegional({});
  const { t } = useTranslation();
  const { orderNo = "" } = useParams();
  const tenantPath = useTenantPath();
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();

  // ⚠ ONE RESOLVE, THEN EVERY CALL BY ID (`DEF-WRK-4518`).
  const order = useQuery({
    queryKey: queryKeys.workOrder(orderNo),
    queryFn: () =>
      isOrderId(orderNo) ? getWorkOrder(orderNo, client) : getWorkOrderByNumber(orderNo, client),
  });
  const row = order.data as OrderRow | undefined;
  // CR-169-BRC10 — `work_order_status_changed`, from the record this screen
  // already holds: every act that moves the status is counted here, once.
  useWorkOrderStatusAnalytics(row?.id, row?.dispatch_state);
  const orderId = row?.id;
  const ready = orderId !== undefined;
  const completed = row !== undefined && orderShape(row) === "completed";

  const checklist = useQuery({
    queryKey: queryKeys.workOrderChecklist(orderId ?? orderNo),
    queryFn: () => getOrderChecklist(orderId as string, client),
    enabled: ready,
  });
  const history = useQuery({
    queryKey: queryKeys.workOrderAudit(orderId ?? orderNo),
    queryFn: () => getOrderHistory(orderId as string, client),
    enabled: ready,
  });
  // ⚠ RULING 15 — the record, the photographs and the signature belong to the
  // COMPLETED job only, so on an open job they are not even fetched.
  const readiness = useQuery({
    queryKey: ["work", "order", orderId ?? orderNo, "close-readiness"],
    queryFn: () => getCloseReadiness(orderId as string, client),
    enabled: ready && completed,
  });
  const attachments = useQuery({
    queryKey: ["work", "order", orderId ?? orderNo, "attachments"],
    queryFn: () => getOrderAttachments(orderId as string, client),
    enabled: ready && completed,
  });
  const signatureRead = useQuery({
    queryKey: ["work", "order", orderId ?? orderNo, "signature"],
    queryFn: () => getOrderSignature(orderId as string, client),
    // The row carries `signature` once lane SRV-1 serves it (P1.23); until
    // then the older read answers who signed and when, without the mark.
    enabled: ready && completed && row?.signature === undefined,
  });

  const tabs: DetailTab[] = ORDER_DETAIL_TABS.map((id) => ({
    id,
    label: t(`work.order.tabs.${id}`),
  }));
  const activeTab = detailTabFrom(params.get("tab"), tabs);

  function selectTab(tab: DetailTab) {
    const next = new URLSearchParams(params);
    next.set("tab", tab.id);
    setParams(next, { replace: true });
  }

  // The resolve is keyed on the ADDRESS SEGMENT and everything else on the
  // RESOLVED ID, so both are invalidated (`DEF-WRK-4518`).
  function afterCommit() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.workOrder(orderNo) });
    if (orderId !== undefined) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.workOrder(orderId) });
    }
    void queryClient.invalidateQueries({ queryKey: queryKeys.workOrderAudit(orderId ?? orderNo) });
  }

  const [holding, setHolding] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [confirmAccept, setConfirmAccept] = useState(false);
  const [sendingBack, setSendingBack] = useState(false);
  const [confirmDuplicate, setConfirmDuplicate] = useState(false);
  // CR-187-BRC10 (US-WRK-057) — *Send alert…*, an open job's handset alert.
  const [alerting, setAlerting] = useState(false);
  const [viewer, setViewer] = useState<ViewerState>(null);

  const resume = useMutation({
    mutationFn: () => resumeOrder(orderId as string, client),
    onSuccess: () => {
      afterCommit();
      toast(t("work.order.resume.done"));
    },
    onError: (error: unknown) => toast(serverSentence(error, t("work.order.resume.refused"), t)),
  });

  const cancel = useMutation({
    mutationFn: () => cancelWorkOrder(orderId as string, client),
    onSuccess: () => {
      setConfirmCancel(false);
      afterCommit();
      toast(t("work.order.cancel.done"));
    },
    onError: (error: unknown) => {
      setConfirmCancel(false);
      toast(serverSentence(error, t("work.order.cancel.refused"), t));
    },
  });

  // P1.32 — the office's ONE act on a completed job. It is a money path (cost
  // lines, meter reads; proved on PostgreSQL by the server's own suite), so it
  // confirms first and names what it does (B14 rule 11).
  const accept = useMutation({
    mutationFn: () => acceptWorkOrder(orderId as string, client),
    onSuccess: () => {
      setConfirmAccept(false);
      afterCommit();
      toast(t("work.order.accept.done"));
    },
    onError: (error: unknown) => {
      setConfirmAccept(false);
      toast(serverSentence(error, t("work.order.accept.refused"), t));
    },
  });

  // `DEF-WRK-9690` (beta #28) — the same job raised again, unassigned, on the
  // same place; the new order opens so the dispatcher can assign it.
  const duplicate = useMutation({
    mutationFn: () => duplicateOrder(orderId as string, client),
    onSuccess: (made) => {
      setConfirmDuplicate(false);
      void queryClient.invalidateQueries({ queryKey: ["work"] });
      toast(t("work.order.duplicate.done", { order: made.order_no ?? "" }));
      navigate(tenantPath(`/work/orders/${made.order_no ?? made.id}`));
    },
    onError: (error: unknown) => {
      setConfirmDuplicate(false);
      toast(serverSentence(error, t("work.order.duplicate.refused"), t));
    },
  });

  // ── A18 §3/§4 — loading and failed are their own states, never dashes ──
  if (order.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (row === undefined) {
    const notFound = isApiError(order.error) && order.error.status === 404;
    return (
      <div data-screen={WORK_ORDER_DETAIL_SCREEN}>
        <PageHeader
          kicker={t("work.order.kicker")}
          title={t("work.order.titleUnnumbered")}
          backTo={{ to: tenantPath("/work/orders"), label: t("work.tabs.orders") }}
        />
        <FailedWithRetry
          title={t("work.order.failedTitle")}
          reason={notFound ? t("work.order.notFound", { order: orderNo }) : t("work.order.unreadable")}
          onRetry={() => void order.refetch()}
          onDownloadReport={() => undefined}
          onCancel={() => navigate(tenantPath("/work/orders"))}
          diagnostic={diagnosticOf(order.error)}
        />
      </div>
    );
  }

  // B14 rule 31 — the visible reference is `WO-0043`, never the uuid.
  const reference = row.order_no ?? null;
  const list = checklist.data;
  const photos = completed ? checklistPhotos(list, attachments.data ?? [], t) : [];
  const signature: OrderPageFields["signature"] =
    row.signature !== undefined
      ? row.signature
      : signatureRead.data
        ? {
            printed_name: signatureRead.data.printed_name,
            signed_at: signatureRead.data.signed_at,
            refused: signatureRead.data.refused,
            decline_reason: signatureRead.data.decline_reason,
            captured_by: null,
            image_url: null,
            door_hanger_attachment_id: signatureRead.data.door_hanger_attachment_id,
            door_hanger_uploading: signatureRead.data.door_hanger_uploading,
          }
        : null;
  // `DEF-WRK-10635` — a refusal's *View* opens its door-hanger photograph.
  const hanger = doorHangerPhoto(signature, t);
  const signaturePhotos: ViewerPhoto[] = hanger
    ? [hanger]
    : signature && signature.image_url
      ? [
          {
            key: "signature",
            title: t("work.order.signature.title"),
            attachmentId: null,
            url: signature.image_url,
            takenBy: signature.captured_by?.name ?? null,
            takenAt: signature.signed_at,
            forText: signature.printed_name ?? t("work.order.signature.title"),
          },
        ]
      : [];
  const viewerPhotos = viewer?.list === "signature" ? signaturePhotos : photos;
  const openPhoto = (key: string) => {
    const index = photos.findIndex((photo) => photo.key === key);
    if (index >= 0) setViewer({ list: "checklist", index });
  };

  return (
    <div data-screen={WORK_ORDER_DETAIL_SCREEN} data-order-shape={completed ? "completed" : "open"}>
      <PageHeader
        kicker={t("work.order.kicker")}
        title={
          reference === null
            ? t("work.order.titleUnnumbered")
            : row.type
              ? t("work.order.title", { order: reference, type: row.type })
              : // `DEF-WRK-9638` — a job the server names nothing reads its
                // number alone, never a dangling separator or a placeholder.
                reference
        }
        backTo={{ to: tenantPath("/work/orders"), label: t("work.tabs.orders") }}
        rollup={<MetaLine row={row} completed={completed} regional={regional} />}
        status={<StatusPills row={row} completed={completed} />}
        // Ruling 16 / B14 rule 2 — the page's actions sit top right, through
        // the head's own slot; the destructive one LAST and in the danger tier.
        secondaryActions={
          <HeadActions
            row={row}
            completed={completed}
            resuming={resume.isPending}
            onReassign={() => navigate(tenantPath(`/work/orders/${orderId as string}/edit`))}
            onHold={() => setHolding(true)}
            onResume={() => resume.mutate()}
            onCancel={() => setConfirmCancel(true)}
            onAccept={() => setConfirmAccept(true)}
            onSendBack={() => setSendingBack(true)}
            onDuplicate={() => setConfirmDuplicate(true)}
            // CR-168-BRC10 P6.3 (lane SRV-5) — the job on paper, opened in the
            // browser's own PDF viewer; its print button prints it.
            onPrint={() =>
              window.open(
                apiHref(tenantPath(`/work-orders/${orderId as string}/print`)),
                "_blank",
                "noopener",
              )
            }
          />
        }
        tabs={tabs}
        activeTabId={activeTab}
        onTabSelect={selectTab}
        tabsLabel={t("work.order.tabsLabel")}
      />

      {activeTab === "overview" && (
        <>
          <OrderOverview
            row={row}
            list={list}
            regional={regional}
            signature={signature}
            onViewSignature={() => setViewer({ list: "signature", index: 0 })}
          />
          {/* CR-161-BRC10 W4 — the utility's OWN work-order fields, read-only. */}
          <CustomFieldsView
            entity="work_orders"
            screen="WORK_DETAIL"
            values={row.custom_data ?? {}}
            formatDate={(iso) => formatDate(iso, regional.timeZone, regional.dateFormat)}
            client={client}
          />
          {/* CR-187-BRC10 (US-WRK-059, US-WRK-057) — *From the field*: what
              the field said (a completed job only), every reopen or follow-on,
              and *Send alert…* on an OPEN job somebody holds (an alert rings
              the holder's handset; the server refuses a crew-only job by name).
              Below the drawn groups, never in the drawn head (rule 41). */}
          <OrderFieldPanels
            orderId={orderId as string}
            completed={completed}
            client={client}
            timeZone={regional.timeZone}
            dateFormat={regional.dateFormat}
            onAlert={
              !completed && !isStopped(row) && row.technician ? () => setAlerting(true) : undefined
            }
          />
        </>
      )}
      {activeTab === "checklist" && (
        <>
          <OrderChecklistTab
            orderId={orderId as string}
            shape={completed ? "completed" : "open"}
            list={list}
            readiness={readiness.data}
            photos={photos}
            onOpenPhoto={openPhoto}
            regional={regional}
          />
          {/* DEF-FLD-10640 (FB-015) — every photograph of the completed job,
              the job-level ones included, which no checklist row carries. */}
          <OrderPhotosPanel
            orderId={orderId as string}
            photos={photos}
            onOpenPhoto={openPhoto}
            regional={regional}
          />
        </>
      )}
      {activeTab === "parts" && <OrderPartsTab list={list} />}
      {activeTab === "audit" && <OrderHistoryTab rows={history.data?.rows ?? []} regional={regional} />}

      {viewer !== null && viewerPhotos.length > 0 && (
        <PhotoViewer
          orderId={orderId as string}
          photos={viewerPhotos}
          index={Math.min(viewer.index, viewerPhotos.length - 1)}
          onIndex={(index) => setViewer({ list: viewer.list, index })}
          onClose={() => setViewer(null)}
          regional={regional}
        />
      )}
      {holding && (
        <HoldDialog
          orderId={orderId as string}
          orderNo={reference ?? ""}
          timeZone={regional.timeZone}
          dateFormat={regional.dateFormat}
          client={client}
          onClose={() => setHolding(false)}
          onHeld={() => {
            setHolding(false);
            afterCommit();
            toast(t("work.order.hold.done"));
          }}
        />
      )}
      {confirmCancel && (
        <ConfirmDialog
          title={t("work.order.cancel.title", { order: reference ?? "" })}
          consequence={t("work.order.cancel.consequence")}
          confirmLabel={t("work.order.cancel.confirm")}
          cancelLabel={t("work.order.cancel.keep")}
          confirmVariant="danger"
          working={cancel.isPending}
          onConfirm={() => cancel.mutate()}
          onCancel={() => setConfirmCancel(false)}
        />
      )}
      {sendingBack && (
        <SendBackDialog
          orderId={orderId as string}
          orderNo={reference ?? ""}
          client={client}
          onClose={() => setSendingBack(false)}
          onSent={() => {
            setSendingBack(false);
            afterCommit();
            toast(t("work.order.sendBack.done"));
          }}
        />
      )}
      {alerting && (
        <SendAlertDialog
          orderId={orderId as string}
          orderNo={reference ?? ""}
          client={client}
          onClose={() => setAlerting(false)}
          onSent={() => {
            setAlerting(false);
            toast(t("work.field.alertDone"));
          }}
        />
      )}
      {confirmDuplicate && (
        <ConfirmDialog
          title={t("work.order.duplicate.title", { order: reference ?? "" })}
          consequence={t("work.order.duplicate.consequence")}
          confirmLabel={t("work.order.duplicate.confirm")}
          cancelLabel={t("work.order.accept.back")}
          working={duplicate.isPending}
          onConfirm={() => duplicate.mutate()}
          onCancel={() => setConfirmDuplicate(false)}
        />
      )}
      {confirmAccept && (
        <ConfirmDialog
          title={t("work.order.accept.title", { order: reference ?? "" })}
          consequence={t("work.order.accept.consequence")}
          confirmLabel={t("work.order.accept.confirm")}
          cancelLabel={t("work.order.accept.back")}
          working={accept.isPending}
          onConfirm={() => accept.mutate()}
          onCancel={() => setConfirmAccept(false)}
        />
      )}
    </div>
  );
}

/**
 * The head's buttons, by shape (ruling 15). Open: *Reassign… · Put on hold… ·
 * Cancel order* — *Resume* in place of the hold once held (P4.3). Completed and
 * not yet accepted: *Send back… · Accept ✓* (images 04/06, P4.14, P1.32).
 * Accepted or cancelled: nothing that acts on THIS job any more.
 *
 * *Print* leads every shape (P6.3) and *Duplicate* follows it on every shape
 * (`DEF-WRK-9690`): copying a job raises a NEW one, so a finished, accepted or
 * cancelled job may still be the thing a dispatcher wants done again.
 */
function HeadActions(props: {
  row: OrderRow;
  completed: boolean;
  resuming: boolean;
  onReassign: () => void;
  onHold: () => void;
  onResume: () => void;
  onCancel: () => void;
  onAccept: () => void;
  onSendBack: () => void;
  onDuplicate: () => void;
  onPrint: () => void;
}) {
  const { t } = useTranslation();
  // P6.3 — *Print* on every shape of the order: a stopped or accepted job is
  // still a sheet a depot or a customer may want on paper.
  const print = (
    <>
      <Button variant="secondary" onClick={props.onPrint} data-action="print">
        {t("work.order.actions.print")}
      </Button>
      <Button variant="secondary" onClick={props.onDuplicate} data-action="duplicate">
        {t("work.order.actions.duplicate")}
      </Button>
    </>
  );
  if (isStopped(props.row)) return print;
  if (props.completed) {
    if (isAccepted(props.row)) return print;
    // PO 2026-10-04, (a): while REQUIRED photos are still uploading, the page
    // says how many and Accept is unavailable; it returns on its own once the
    // last one lands (the server refuses an accept meanwhile, by any route).
    const uploading = props.row.photos_uploading ?? 0;
    return (
      <>
        {print}
        {uploading > 0 ? (
          <span className="self-center text-sm text-warning-700" data-photos-uploading={uploading}>
            {t("work.order.photos_uploading", { count: uploading })}
          </span>
        ) : null}
        {/* `DEF-WRK-9675` — images 04/06: *Send back…* beside *Accept ✓*. */}
        <Button variant="secondary" onClick={props.onSendBack} data-action="send-back">
          {t("work.order.actions.sendBack")}
        </Button>
        <Button variant="primary" onClick={props.onAccept} data-action="accept" disabled={uploading > 0}>
          {t("work.order.actions.accept")}
        </Button>
      </>
    );
  }
  const held = props.row.dispatch_state === "on_hold";
  return (
    <>
      {print}
      {/* P1.27 (the order page's half) — *Assign…* on a job nobody holds,
          *Reassign…* once somebody does; both open the edit page. */}
      <Button variant="secondary" onClick={props.onReassign} data-action={props.row.technician ? "reassign" : "assign"}>
        {props.row.technician ? t("work.order.actions.reassign") : t("work.order.actions.assign")}
      </Button>
      {held ? (
        <Button variant="secondary" disabled={props.resuming} onClick={props.onResume} data-action="resume">
          {t("work.order.actions.resume")}
        </Button>
      ) : (
        <Button variant="secondary" onClick={props.onHold} data-action="hold">
          {t("work.order.actions.hold")}
        </Button>
      )}
      <Button variant="danger" onClick={props.onCancel} data-action="cancel">
        {t("work.order.actions.cancel")}
      </Button>
    </>
  );
}

/** Image 04's pills, in the drawing's order: the dispatch status, the field
 *  state, then on a completed job the outcome and whether a person has
 *  accepted it — *Complete · Completed · Passed · Awaiting approval*.
 *
 *  ⚠ `DEF-WRK-9681` REVERSES `DEF-WRK-9643`. That fix dropped the dispatch
 *  pill on a completed job as a repetition, citing rule 37 (a drawn figure is
 *  an illustration). Rule 37 is about FIGURES; a chip is a control the drawing
 *  places, and rule 41 builds the drawn shape EXACTLY. The two axes are two
 *  facts the server keeps (where the crew is · what the field did), and the
 *  drawing shows both. Our judgment, recorded in the decision log
 *  (*"CR-168 ROUND 8 · FIX-8B"*); the PO was not asked (law 13). */
function StatusPills(props: { row: OrderRow; completed: boolean }) {
  const { t } = useTranslation();
  const row = props.row;
  return (
    <>
      {/* A finished job reads *Complete* on the dispatch axis whatever a seeded
          or older row still carries there (`DEF-WRK-9526`: finished demo jobs
          once read *Scheduled*) — the field closing it IS the crew being done. */}
      <StatusPill tone={dispatchStateTone(props.completed ? "complete" : row.dispatch_state)}>
        {t(`work.orders.dispatch.${props.completed ? "complete" : row.dispatch_state}`)}
      </StatusPill>{" "}
      <StatusPill tone={workOrderStateTone(row.state)}>{t(`work.orders.state.${row.state}`)}</StatusPill>
      {props.completed && row.outcome ? (
        <>
          {" "}
          <StatusPill tone={workOrderOutcomeTone(row.outcome)}>
            {t(`work.orders.outcome.${row.outcome}`)}
          </StatusPill>
        </>
      ) : null}
      {props.completed ? (
        <>
          {" "}
          <StatusPill tone={isAccepted(row) ? "success" : "warning"}>
            {isAccepted(row) ? t("work.order.approval.accepted") : t("work.order.approval.awaiting")}
          </StatusPill>
        </>
      ) : null}
    </>
  );
}

/**
 * The line under the title (P1.2) — address · unit · account · customer ·
 * meter · priority · holder · the window (open) or *Closed …* (completed).
 * Every leg is a value the server sent; a missing one is simply not a leg.
 */
function MetaLine(props: { row: OrderRow; completed: boolean; regional: Regional }) {
  const { t } = useTranslation();
  const row = props.row;
  const bits: string[] = [];
  const address = row.location?.address ?? row.premise?.address ?? null;
  if (address) bits.push(address);
  if (row.location?.unit?.label) bits.push(row.location.unit.label);
  const accountNo = row.customer?.account_no ?? row.account?.account_no ?? null;
  if (accountNo) bits.push(accountNo);
  if (row.customer?.name) bits.push(row.customer.name);
  if (row.location?.asset?.asset_no) bits.push(row.location.asset.asset_no);
  if (row.priority?.name) bits.push(row.priority.name);
  // P4.1 — the technician, and whether they took the job (*D. Ortiz ·
  // Accepted*); nothing more when nobody holds it.
  bits.push(row.technician?.name ?? t("work.order.unassigned"));
  const acceptance = (row as { technician_acceptance?: TechnicianAcceptance | null }).technician_acceptance;
  // `DEF-WRK-9624` — the technician's taking of the job is an OPEN job's fact.
  // Once the field has closed it, *Not accepted yet* beside the office's
  // *Accepted* pill read as a contradiction about two different acceptances.
  if (row.technician && acceptance && !props.completed) {
    bits.push(t(`work.orders.acceptance.${acceptance.state}`));
  }
  if (props.completed) {
    const closed = whenText(closedBy(row).at, props.regional);
    if (closed) bits.push(t("work.order.closedAt", { when: closed }));
    // `BR-WRK-061`, PO 2026-10-04: a close whose best fix missed the tenant's
    // precision is accepted and FLAGGED here, where the office accepts it.
    if (row.closed?.location && row.closed.location.precise === false) {
      bits.push(t("work.order.locationNotPrecise"));
    }
  } else {
    const slot = windowText(row.window_start, row.window_end, props.regional);
    if (slot) bits.push(slot);
  }
  return <span data-metaline="">{bits.join(" · ")}</span>;
}
