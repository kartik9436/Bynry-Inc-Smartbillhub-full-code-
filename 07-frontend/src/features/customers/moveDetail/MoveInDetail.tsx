// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.04 · P2.05 · P2.07–P2.13 — THE MOVE-IN DETAILS VIEW,
//           one screen for every status (images 03–29): back link, the name
//           and its reference, the status and date chips with the address,
//           the buttons the status draws (`moveInActionSlots`), More ▾, the
//           tabs, and each tab's body.
// Rules:    PO v24 *"this scren should be similar to details view with buttons
//           in it"*, v22 *"update details view button accrdongly"*, v18 (no
//           *Open account*; edit · approve · cancel · ask for more by status) ·
//           B14 rules 2 (one primary), 6 (danger tier), 31, 33, 36, 40 (32px
//           title — `PageHeader` carries it), 42 (built from the images), 43,
//           44 (our spacing and kit over the drawing's pixels)
// Screens:  S19.moveRecord — `/moves/:ref`, where `ref` is `SR-…` or `MVI-…`
// Data:     `GET /moves/{ref}` (CR-171 §9.LIST) and the doors in §9.REQ/§9.FLOW
// Tests:    MoveInDetail.dom.test.tsx · moveRecordActions.test.ts
// ───────────────────────────────────────────────────────
//
// ⚠ **EDIT ON A REQUEST OPENS THE ADD FORM (PO v22, *"on edit of Move in request
// use same form Add form"*).** The four-step form's edit mode is WIZ-REV's
// (P2.34); this screen opens it by the address the wizard already reads —
// `/move-ins/new?request=<id>` — plus `edit=1`, the one parameter P2.34 is to
// read (recorded in CR-171 §9.DETAIL). A draft's Edit resumes its park
// (`resumePath`, the one builder of `?parked=`).
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button, ButtonSummary } from "@/components/Button";
import { todayInZone } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import type { PageHeaderTab } from "@/components/PageHeader";
import { RowMenuAction } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useTenantPath } from "@/routing/tenantPath";

import { AccountCommunicationDialog } from "../AccountCommunicationDialog";
import { moveRegisterLabel, moveRegisterPath } from "../MoveRecordPage";
import { moveInActionSlots } from "../moveRecordActions";
import type { MoveInActionId, MoveInStatus } from "../moveRecordActions";
import { MOVE_IN_WIZARD_ROUTE } from "../moveShared";
import { resumePath } from "../parkedDrafts";
import { AccountTab } from "./AccountTab";
import type { MoveCoOwner } from "./AccountTab";
import { MoveAuditTab, RequestAuditTab } from "./AuditTab";
import { BillingTab } from "./BillingTab";
import type { MoveFeeLineRow } from "./BillingTab";
import { RequestDocumentsTab } from "./DocumentsTab";
import { MoveMessagesTab, RequestMessagesTab } from "./MessagesTab";
import { MoveActionModal } from "./MoveActionsModals";
import type { MoveModal } from "./MoveActionsModals";
import { isRequestDetail, resendTheAsk } from "./moveDetailEndpoints";
import type { JobDetail, MoveInDetail as MoveInDetailRecord } from "./moveDetailEndpoints";
import { Day, registerMeter } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";
import { MoveOverview } from "./MoveOverview";
import { MoveRequestModal } from "./MoveRequestModals";
import type { RequestModal } from "./MoveRequestModals";
import { RequestOverview } from "./RequestOverview";
import { UnitReadsTab } from "./UnitReadsTab";
import { MoveWorkTab } from "./WorkTab";

/** The tab ids, in drawn order — a request (images 03, 21–23) and a move-in
 *  (images 09, 24–29). */
export const REQUEST_TABS = ["overview", "documents", "messages", "audit"] as const;
export const MOVE_TABS = ["overview", "unit", "account", "billing", "work", "messages", "audit"] as const;
export const MOVE_DETAIL_TAB_PARAM = "tab";
/** The one parameter the four-step form's edit mode reads (P2.34). */
export const MOVE_IN_EDIT_PARAM = "edit";

/** The status chip's tone — images 03–17's colours, mapped onto the kit's. */
export const MOVE_IN_STATUS_TONE: Record<MoveInStatus, StatusTone> = {
  to_approve: "warning",
  waiting_on_customer: "warning",
  declined: "danger",
  not_started: "info",
  draft: "neutral",
  waiting_on_a_read: "warning",
  completed: "success",
  cancelled: "muted",
};

/** Where *Edit* goes, per status (images 04, 06, 10, 11). `null` = no door. */
export function moveInEditPath(record: MoveInDetailRecord): string | null {
  if (record.status === "draft") {
    return record.park_id ? resumePath({ id: record.park_id, flow: "move_in" }) : null;
  }
  const requestId = record.request?.id ?? null;
  if (requestId === null) return null;
  return `${MOVE_IN_WIZARD_ROUTE}?request=${encodeURIComponent(requestId)}&${MOVE_IN_EDIT_PARAM}=1`;
}

/** Where *Start* goes on a Not started move-in (image 09): the four-step form
 *  opened FROM the job's request — the door that closes the job
 *  (`move_in_jobs` §3). */
export function moveInStartPath(record: MoveInDetailRecord): string | null {
  const requestId = record.request?.id ?? null;
  return requestId === null ? null : `${MOVE_IN_WIZARD_ROUTE}?request=${encodeURIComponent(requestId)}`;
}

const REQUEST_MODALS: Partial<Record<MoveInActionId, RequestModal>> = {
  approve: "approve",
  decline: "decline",
  askForMore: "askForMore",
  reopen: "reopen",
};
const MOVE_MODALS: Partial<Record<MoveInActionId, MoveModal>> = {
  changeDate: "changeDate",
  enterOpeningRead: "enterOpeningRead",
  cancel: "cancel",
  discardDraft: "discardDraft",
  addWorkOrder: "addWorkOrder",
};

/** The button's word, with B14's grammar marks: `Verb ✓` commits, `Verb…`
 *  asks first. The catalogue carries the mark. */
function actionKey(id: MoveInActionId): string {
  return `customers.moveDetail.action.${id}`;
}

function DateChip(props: { record: MoveInDetailRecord; regional: Regional }) {
  const { t } = useTranslation();
  const r = props.record;
  const parts: ReactNode[] = [];
  const day = (iso: string | null | undefined) => <Day value={iso} regional={props.regional} />;
  if (isRequestDetail(r)) {
    if (r.chips.requested_on) parts.push(<>{t("customers.moveDetail.chip.requested")} {day(r.chips.requested_on)}</>);
    if (r.chips.moves_in_on) parts.push(<>{t("customers.moveDetail.chip.movesIn")} {day(r.chips.moves_in_on)}</>);
  } else {
    const step = r.step;
    if (r.status === "draft" && step !== null && typeof step === "object" && step.reached !== null) {
      parts.push(<>{t("customers.moveDetail.chip.step", { n: step.reached, of: step.of })}</>);
    }
    if (r.effective_on) {
      const committed = r.state === "completed";
      parts.push(
        <>
          {t(committed ? "customers.moveDetail.chip.movedIn" : "customers.moveDetail.chip.movesIn")}{" "}
          {day(r.effective_on)}
        </>,
      );
    }
  }
  if (parts.length === 0) return null;
  return (
    <StatusPill tone="neutral">
      <span data-move-date-chip="">
        {parts.map((part, index) => (
          <span key={index}>
            {index > 0 ? " · " : null}
            {part}
          </span>
        ))}
      </span>
    </StatusPill>
  );
}

/** `More ▾` — the kit's summary button over `RowMenuAction`s (as Plans' head). */
function MoreMenu(props: {
  items: readonly MoveInActionId[];
  danger: ReadonlySet<MoveInActionId>;
  onPress: (id: MoveInActionId) => void;
}) {
  const { t } = useTranslation();
  const menu = useRef<HTMLDetailsElement | null>(null);
  if (props.items.length === 0) return null;
  return (
    <details ref={menu} className="relative inline-flex" data-move-more="">
      <ButtonSummary variant="secondary" className="list-none [&::-webkit-details-marker]:hidden">
        {t("customers.moveDetail.more")} <span aria-hidden="true">▾</span>
      </ButtonSummary>
      <div className="absolute right-0 top-[calc(100%+var(--space-1))] z-40 flex min-w-48 flex-col border border-divider bg-surface py-1 shadow-md">
        {props.items.map((id) => (
          <RowMenuAction
            key={id}
            label={t(actionKey(id))}
            icon={null}
            danger={props.danger.has(id)}
            testId={`move-more-${id}`}
            onClick={() => {
              if (menu.current !== null) menu.current.open = false;
              props.onPress(id);
            }}
          />
        ))}
      </div>
    </details>
  );
}

export function MoveInDetail(props: {
  record: MoveInDetailRecord;
  refKey: string;
  regional: Regional;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const client = props.client ?? api;
  const record = props.record;
  const isRequest = isRequestDetail(record);
  const tabIds: readonly string[] = isRequest ? REQUEST_TABS : MOVE_TABS;
  const asked = searchParams.get(MOVE_DETAIL_TAB_PARAM);
  const activeTab = asked !== null && tabIds.includes(asked) ? asked : "overview";
  const [requestModal, setRequestModal] = useState<RequestModal | null>(null);
  const [moveModal, setMoveModal] = useState<MoveModal | null>(null);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["move-record"] });
    void queryClient.invalidateQueries({ queryKey: ["move-ins"] });
  };
  const resend = useMutation({
    mutationFn: () => resendTheAsk(record.request?.id ?? "", client),
    onSuccess: () => {
      setNotice(t("customers.moveDetail.notice.resent"));
      refresh();
    },
    onError: () => setNotice(t("customers.moveDetail.notice.failed")),
  });

  const job = isRequest ? null : (record as JobDetail);
  const accountId = job?.facts.details.account?.id ?? null;
  const moveNo = record.move_no ?? record.reference ?? props.refKey;
  const slots = moveInActionSlots(record.status, record.actions);

  const onTab = (id: string) => {
    const next = new URLSearchParams(searchParams);
    if (id === "overview") next.delete(MOVE_DETAIL_TAB_PARAM);
    else next.set(MOVE_DETAIL_TAB_PARAM, id);
    setSearchParams(next, { replace: true });
  };

  const press = (id: MoveInActionId) => {
    setNotice(null);
    const requestModalId = REQUEST_MODALS[id];
    if (requestModalId !== undefined) return setRequestModal(requestModalId);
    const moveModalId = MOVE_MODALS[id];
    if (moveModalId !== undefined) return setMoveModal(moveModalId);
    if (id === "resendAsk") return resend.mutate();
    if (id === "sendMessage") return setSending(true);
    if (id === "print") return window.print();
    const to = id === "edit" ? moveInEditPath(record) : id === "start" ? moveInStartPath(record) : null;
    if (to !== null) navigate(tenantPath(to));
  };

  /** A button exists only where it can act — Edit/Start with no door, or
   *  Send a message with no account, are not drawn (law 2's mirror). */
  const live = (id: MoveInActionId): boolean => {
    if (id === "edit") return moveInEditPath(record) !== null;
    if (id === "start") return moveInStartPath(record) !== null;
    if (id === "sendMessage") return accountId !== null;
    if (id === "resendAsk" || REQUEST_MODALS[id] !== undefined) return record.request?.id !== undefined;
    return true;
  };

  const button = (id: MoveInActionId | null, tier: "primary" | "secondary") =>
    id === null || !live(id) ? null : (
      <Button
        key={id}
        variant={tier}
        onClick={() => press(id)}
        disabled={id === "resendAsk" && resend.isPending}
        data-testid={`move-action-${id}`}
        data-action={id}
      >
        {t(actionKey(id))}
      </Button>
    );

  const tabs: PageHeaderTab[] = tabIds.map((id) => {
    const count = record.tab_counts[id] ?? null;
    return {
      id,
      label: t(`customers.moveDetail.tab.${id}`),
      count: count !== null && count !== undefined && count > 0 ? `· ${count}` : undefined,
    };
  });

  const regional = props.regional;
  // The registers still to read, by METER number — exactly the rows the
  // record names unread. The chip and these rows read ONE server definition
  // (a meter's first read on/after the move-in date, `DEF-CUS-9726`), so the
  // screen never second-guesses them.
  const unreadRegisters = Array.from(
    new Set(
      (job?.opening_reads.rows ?? [])
        .filter((row) => row.how !== "read")
        .map((row) => registerMeter(row.register)),
    ),
  );

  return (
    <div className="p-6" data-screen="move-in-detail" data-status={record.status}>
      <PageHeader
        backTo={{
          to: tenantPath(moveRegisterPath("move_in", moveNo)),
          label: moveRegisterLabel("move_in", moveNo, t),
        }}
        title={record.title ?? moveNo}
        titleAfter={
          <span className="ms-4 align-middle text-base font-semibold text-neutral-600" data-move-reference="">
            {record.reference ?? record.move_no}
          </span>
        }
        status={
          <span className="flex flex-wrap items-center gap-2">
            <StatusPill tone={MOVE_IN_STATUS_TONE[record.status]}>
              <span data-move-status={record.status}>{t(`customers.moveDetail.status.${record.status}`)}</span>
            </StatusPill>
            <DateChip record={record} regional={regional} />
            {record.address_line ? (
              <span className="text-sm text-neutral-600" data-move-where="">
                {record.address_line}
              </span>
            ) : null}
          </span>
        }
        secondaryActions={
          <>
            {button(slots.secondary, "secondary")}
            {button(slots.primary, "primary")}
            <MoreMenu items={slots.more.filter(live)} danger={slots.danger} onPress={press} />
          </>
        }
        tabs={tabs}
        activeTabId={activeTab}
        tabsLabel={t("customers.moveDetail.tabsLabel")}
        onTabSelect={(tab) => onTab(tab.id)}
      />

      {notice !== null ? (
        <p className="mb-4 text-base text-neutral-700" role="status" data-move-notice="">
          {notice}
        </p>
      ) : null}

      {isRequest ? (
        <>
          {activeTab === "overview" && <RequestOverview record={record} regional={regional} onTab={onTab} />}
          {activeTab === "documents" && record.request && (
            <RequestDocumentsTab requestId={record.request.id} regional={regional} client={client} />
          )}
          {activeTab === "messages" && record.request && (
            <RequestMessagesTab requestId={record.request.id} regional={regional} client={client} />
          )}
          {activeTab === "audit" && record.request && (
            <RequestAuditTab requestId={record.request.id} regional={regional} client={client} />
          )}
        </>
      ) : job !== null ? (
        <>
          {activeTab === "overview" && <MoveOverview record={job} regional={regional} onTab={onTab} client={client} />}
          {activeTab === "unit" && (
            <UnitReadsTab
              unitId={job.facts.details.unit?.id ?? null}
              readings={job.opening_reads.rows}
              regional={regional}
              client={client}
            />
          )}
          {activeTab === "account" && (
            <AccountTab
              accountId={accountId}
              coOwners={(job as JobDetail & { co_owners?: MoveCoOwner[] }).co_owners ?? []}
              regional={regional}
              client={client}
            />
          )}
          {activeTab === "billing" && (
            <BillingTab record={job as JobDetail & { fee_lines?: MoveFeeLineRow[] }} regional={regional} client={client} />
          )}
          {activeTab === "work" && <MoveWorkTab accountId={accountId} regional={regional} client={client} />}
          {activeTab === "messages" && (
            <MoveMessagesTab
              accountId={accountId}
              regional={regional}
              onSend={accountId !== null && record.status !== "cancelled" ? () => setSending(true) : null}
              client={client}
            />
          )}
          {activeTab === "audit" && <MoveAuditTab accountId={accountId} regional={regional} client={client} />}
        </>
      ) : null}

      {requestModal !== null && record.request ? (
        <MoveRequestModal
          open={requestModal}
          requestId={record.request.id}
          requestNo={record.request.request_no ?? record.reference ?? ""}
          applicant={record.title ?? ""}
          client={client}
          onClose={() => setRequestModal(null)}
          onDone={(done) => {
            setRequestModal(null);
            setNotice(t(`customers.moveDetail.notice.${done}`));
            refresh();
          }}
        />
      ) : null}
      {moveModal !== null ? (
        <MoveActionModal
          open={moveModal}
          moveNo={moveNo}
          parkId={record.park_id ?? null}
          unreadRegisters={unreadRegisters}
          unitId={job?.facts.details.unit?.id ?? null}
          moveInDate={job?.facts.details.moved_in_on ?? null}
          regional={regional}
          client={client}
          onClose={() => setMoveModal(null)}
          onDone={(done) => {
            setMoveModal(null);
            if (done === "discardDraft") {
              navigate(tenantPath(moveRegisterPath("move_in", moveNo)));
              return;
            }
            setNotice(t(`customers.moveDetail.notice.${done}`));
            refresh();
          }}
        />
      ) : null}
      {sending && accountId !== null ? (
        <AccountCommunicationDialog
          accountId={accountId}
          today={todayInZone(regional.timeZone)}
          dateFormat={regional.dateFormat}
          onClose={() => {
            setSending(false);
            void queryClient.invalidateQueries({ queryKey: ["move-detail-messages"] });
          }}
        />
      ) : null}
    </div>
  );
}
