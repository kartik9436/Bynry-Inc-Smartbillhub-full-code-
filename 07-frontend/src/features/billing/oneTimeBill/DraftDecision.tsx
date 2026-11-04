// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-BIL-10068 (OTB-6) — a one-time DRAFT could be neither approved
//          nor cancelled from its own page, so it blocked every new one-time
//          bill for its period.
// Ruling:  PO 2026-10-12 (decision log "ONE-TIME BILL ACROSS A MID-PERIOD RATE
//          CHANGE"): *"a draft gets Approve and Cancel"*; *"Cancel deletes the
//          draft"* with an audit row, its number not reused.
// Rules:   BR-BIL-058 (the five release confirmations — the one-time Send
//          card's own, PO 2026-09-30 option B) · BR-BIL-1045 / DEF-BIL-9255
//          (`POST /billing/runs/{id}/discard`) · B14 rules 6 (danger tier on a
//          destructive confirm), 33 (copy caps), 43 (a component)
// ───────────────────────────────────────────────────────
/**
 * **Approve** and **Cancel draft** for a ONE-TIME draft's detail page.
 *
 * Neither invents a path. **Approve** is the one-time Send — `POST
 * /billing/one-time/{run_id}/send` — with the SAME five confirmations and the
 * SAME delivery choice the wizard's Send card asks (`SendConfirmations`,
 * `DeliveryPanel`, mounted here, not copied), so a bill approved from its
 * page and one sent from the wizard are one event. **Cancel draft** is the
 * existing discard (`runs.discard_run`): the draft and its lines go, the run
 * stays `abandoned` with `bill_run.discarded` in `audit_log`, the period is
 * free again and the number is never handed out twice.
 */
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { sendOneTime } from "@/api/billingOpsEndpoints";
import type { OneTimeBillDelivery } from "@/api/billingOpsEndpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ModalShell } from "@/components/FormModal";
import type { Translator } from "@/components/FormModal";
import { WorkingButton } from "@/components/StateFrame";

import { emptyGateState, releaseConfirmations } from "../billRunShared";
import type { GateState } from "../billRunShared";
import { discardBillRun } from "../billRunEndpoints";

import { DeliveryPanel } from "./ReviewStep";
import { SendConfirmations, allConfirmed } from "./SendConfirmations";

export function DraftDecision(props: {
  runId: string;
  /** Why the clerk may not write, or null — BR-SHL-025's read-only cell. */
  blockedReason: string | null;
  client?: ApiClient;
  /** A sentence for the clerk (a toast). */
  onMessage: (message: string) => void;
  /** The bill changed (issued or gone): the page re-reads it. */
  onDone: (outcome: "approved" | "cancelled") => void;
  refusalOf: (error: unknown) => string;
  t: Translator;
}) {
  const { t } = props;
  const [asking, setAsking] = useState<"approve" | "cancel" | null>(null);
  const [working, setWorking] = useState(false);
  const [confirmations, setConfirmations] = useState<GateState>(emptyGateState);
  const [delivery, setDelivery] = useState<OneTimeBillDelivery>("email");
  const disabled = props.blockedReason !== null;

  async function approve(): Promise<void> {
    setWorking(true);
    try {
      await sendOneTime(
        props.runId,
        {
          confirmations: releaseConfirmations(confirmations),
          delivery,
          sent_at: new Date().toISOString(),
        },
        props.client,
      );
      setAsking(null);
      props.onMessage(t("billing.bill.approve.done"));
      props.onDone("approved");
    } catch (error) {
      props.onMessage(props.refusalOf(error));
    } finally {
      setWorking(false);
    }
  }

  async function cancel(): Promise<void> {
    setWorking(true);
    try {
      await discardBillRun(props.runId, props.client);
      setAsking(null);
      props.onMessage(t("billing.bill.cancelDraft.done"));
      props.onDone("cancelled");
    } catch (error) {
      props.onMessage(props.refusalOf(error));
    } finally {
      setWorking(false);
    }
  }

  return (
    <>
      <Button
        variant="primary"
        disabled={disabled}
        title={props.blockedReason ?? undefined}
        onClick={() => setAsking("approve")}
        data-bil="approve-draft"
      >
        {t("billing.bill.action.approve")}
      </Button>
      <Button
        disabled={disabled}
        title={props.blockedReason ?? undefined}
        onClick={() => setAsking("cancel")}
        data-bil="cancel-draft"
      >
        {t("billing.bill.action.cancelDraft")}
      </Button>
      {asking === "cancel" && (
        <ConfirmDialog
          title={t("billing.bill.cancelDraft.title")}
          consequence={t("billing.bill.cancelDraft.consequence")}
          confirmLabel={t("billing.bill.action.cancelDraft")}
          cancelLabel={t("billing.bill.cancelDraft.keep")}
          confirmVariant="danger"
          working={working}
          onConfirm={() => void cancel()}
          onCancel={() => setAsking(null)}
        />
      )}
      {asking === "approve" && (
        <ModalShell title={t("billing.bill.approve.title")} onClose={() => setAsking(null)}>
          <div className="modal-body flex flex-col gap-4">
            <p className="m-0 text-md leading-body">{t("billing.bill.approve.consequence")}</p>
            <SendConfirmations
              state={confirmations}
              onChange={(id, checked) => setConfirmations((was) => ({ ...was, [id]: checked }))}
              t={t}
            />
            <DeliveryPanel value={delivery} onChange={setDelivery} t={t} />
          </div>
          <div className="modal-foot">
            <Button variant="ghost" disabled={working} onClick={() => setAsking(null)}>
              {t("billing.bill.cancelDraft.keep")}
            </Button>
            <WorkingButton working={working} disabled={!allConfirmed(confirmations)} onClick={() => void approve()}>
              {t("billing.bill.approve.confirm")}
            </WorkingButton>
          </div>
        </ModalShell>
      )}
    </>
  );
}
