// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.06 — the request's three modals (images 18–20) and
//           Reopen (image 08): a title, ONE EFFECT line, at most one required
//           text, Cancel and the commit. Escape, Cancel and the backdrop close
//           (the kit's `ModalShell`).
// Rules:    PO v24 *"ask for more make it modal"* · B14 rule 6 (Decline is the
//           danger tier) · rule 33 (an EFFECT is a CONSEQUENCE: ≤ 6 words per
//           sentence) · rule 36/43 (`FormModal` + `ConsequenceBox`, no bespoke
//           dialog)
// Doors:    §9.REQ — approve `{"outcome": "move_in"}`; refuse `{reason,
//           reason_code: "other", message_to_applicant}` (J2); transitions
//           `request_info` with the text as reason and letter; reopen `{reason}`
//           (§9.FLOW). A refusal from the server lands IN the modal.
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import {
  approveServiceRequest,
  refuseServiceRequest,
  transitionServiceRequest,
} from "../serviceRequestEndpoints";
import { reopenRequest } from "./moveDetailEndpoints";

export type RequestModal = "approve" | "decline" | "askForMore" | "reopen";

const TEXT_SCHEMA = z.object({ text: z.string().trim().min(1) });
const NO_FIELDS = z.object({});

async function attempt(work: () => Promise<unknown>, done: () => void): Promise<FormSubmitOutcome> {
  try {
    await work();
    done();
    return { ok: true };
  } catch (error) {
    if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
    return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
  }
}

/** The one EFFECT line every modal opens with (images 18–20). */
function Effect(props: { sentence: string; name: string }) {
  const { t } = useTranslation();
  return (
    <ConsequenceBox
      tone="publish"
      tag={t("customers.moveDetail.effect")}
      title={props.sentence}
      body={null}
      data-consequence={props.name}
    />
  );
}

export function MoveRequestModal(props: {
  open: RequestModal;
  requestId: string;
  requestNo: string;
  applicant: string;
  onClose: () => void;
  onDone: (modal: RequestModal) => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [text, setText] = useState("");
  const done = () => props.onDone(props.open);

  if (props.open === "approve") {
    return (
      <FormModal
        title={t("customers.moveDetail.approve.title", { ref: props.requestNo })}
        schema={NO_FIELDS}
        values={{}}
        onClose={props.onClose}
        submitLabel={t("customers.moveDetail.action.approve")}
        onSubmit={() =>
          attempt(() => approveServiceRequest(props.requestId, undefined, client, "move_in"), done)
        }
      >
        <Effect sentence={t("customers.moveDetail.approve.effect")} name="move-approve" />
      </FormModal>
    );
  }

  const shape: Record<Exclude<RequestModal, "approve">, { title: string; effect: string; label: string; submit: string }> = {
    decline: {
      title: t("customers.moveDetail.decline.title", { ref: props.requestNo }),
      effect: t("customers.moveDetail.decline.effect"),
      label: t("customers.moveDetail.decline.reason"),
      submit: t("customers.moveDetail.decline.submit"),
    },
    askForMore: {
      title: t("customers.moveDetail.ask.title", { name: props.applicant }),
      effect: t("customers.moveDetail.ask.effect"),
      label: t("customers.moveDetail.ask.need"),
      submit: t("customers.moveDetail.ask.submit"),
    },
    reopen: {
      title: t("customers.moveDetail.reopen.title", { ref: props.requestNo }),
      effect: t("customers.moveDetail.reopen.effect"),
      label: t("customers.moveDetail.decline.reason"),
      submit: t("customers.moveDetail.action.reopen"),
    },
  };
  const copy = shape[props.open];
  const commit = (): Promise<unknown> => {
    const body = text.trim();
    if (props.open === "decline") {
      return refuseServiceRequest(
        props.requestId,
        { reason: body, reason_code: "other", message_to_applicant: body },
        client,
      );
    }
    if (props.open === "askForMore") {
      return transitionServiceRequest(props.requestId, "request_info", body, client, undefined, {
        message_to_applicant: body,
      });
    }
    return reopenRequest(props.requestId, body, client);
  };
  return (
    <FormModal
      title={copy.title}
      schema={TEXT_SCHEMA}
      values={{ text }}
      onClose={props.onClose}
      submitLabel={copy.submit}
      submitVariant={props.open === "decline" ? "danger" : "primary"}
      onSubmit={() => attempt(commit, done)}
    >
      <Effect sentence={copy.effect} name={`move-${props.open}`} />
      <div className="mt-4">
        <TextField id="text" label={copy.label} value={text} onChange={setText} required multiline />
      </div>
    </FormModal>
  );
}
