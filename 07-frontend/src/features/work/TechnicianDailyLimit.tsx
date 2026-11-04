// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 §30, lane BOARDS — a technician's DAILY JOB LIMIT,
//           shown and edited on the technician's page (Work-024's Overview).
// Ruling:   PO answer (2) of 2026-10-05, verbatim: *"(b) Add a daily limit per
//           technician (default 6), editable on the technician's page."*
// Writes:   `PATCH /work/technicians/{slug} {daily_job_limit}` (`work/0038`)
// Rules:    ruling 2 (advice, never a block — nothing refuses a seventh job)
//           · NFR-5 (no upper bound) · B14 rule 21 (on route-b-migrated.txt)
//           · rule 33 (a label ≤ 3 words; no rationale on screen) · rule 38
//           (the form is our kit's `FormModal`) · rule 43 (a component, not
//           inline code in the page)
// Tests:    src/features/work/TechnicianDailyLimit.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Panel } from "@/components/Panel";

import { setTechnicianDailyLimit } from "./workEndpoints";
import type { TechnicianDetail } from "./workEndpoints";

/** A whole number, one or more, no ceiling — the server's own rule, and the
 *  server's own sentence (`work.technician.daily_limit_invalid`). */
export function dailyLimitSchema(message: string) {
  return z.object({ daily_job_limit: z.string().trim().regex(/^[1-9]\d*$/u, { message }) });
}

/** The Overview's panel: *Daily job limit · 6 jobs a day* and *Edit*. */
export function DailyLimitPanel(props: { client: ApiClient; detail: TechnicianDetail; onSaved: () => void }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const limit = props.detail.daily_job_limit;
  if (limit === undefined) return null;
  return (
    <Panel
      as="section"
      title={t("work.technician.dailyLimit.title")}
      data-technician-daily-limit=""
      trailing={
        <Button variant="secondary" size="sm" data-edit-daily-limit="" onClick={() => setEditing(true)}>
          {t("work.technician.dailyLimit.edit")}
        </Button>
      }
    >
      <p className="m-0 text-base" data-daily-limit-value={limit}>
        {t("work.technician.dailyLimit.value", { count: limit })}
      </p>
      {editing && (
        <DailyLimitModal
          client={props.client}
          detail={props.detail}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            props.onSaved();
          }}
        />
      )}
    </Panel>
  );
}

export function DailyLimitModal(props: {
  client: ApiClient;
  detail: TechnicianDetail;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [value, setValue] = useState(String(props.detail.daily_job_limit ?? ""));

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await setTechnicianDailyLimit(props.detail.slug, Number(value.trim()), props.client);
      props.onSaved();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("work.technician.dailyLimit.formTitle", { name: props.detail.name })}
      schema={dailyLimitSchema(t("work.technician.daily_limit_invalid"))}
      values={{ daily_job_limit: value }}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t("work.technician.dailyLimit.save")}
    >
      <TextField
        id="daily_job_limit"
        label={t("work.technician.dailyLimit.title")}
        value={value}
        onChange={setValue}
        numeric
        required
      />
    </FormModal>
  );
}

export default DailyLimitPanel;
