// ── Trace ──────────────────────────────────────────────
// Change:   CR-163-BRC10 item 1 · DEF-CUS-9177 (2026-10-02, lane NC-B) — the
//           New Connection detail's *Raise order* POSTed a "Meter set" order
//           with no form and no feedback. This is the form.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT, in the build kit) ·
//           rule 44 (our kit builds it: `FormModal`, `SelectField`,
//           `DatePickerField` — B14 rule 7) · rule 31 (ids are option VALUES, names are what is
//           read) · rule 33 (labels ≤ 3 words) · BR-WRK-006 (the build is the
//           anchor) · BR-WRK-008 (published templates only) · BR-SHL-025
// Tests:    src/features/work/buildRecord/BuildRaiseOrderDialog.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// FOUR CHOICES AND ONE RAISE. Job type is a PUBLISHED template of the tenant's
// own (`BR-WRK-008` — a draft has no version to copy, and the server refuses
// one anyway). Service is one of THIS BUILD's services, or none — a whole-build
// inspection stands on no single service, and a service the build does not
// carry is the defect `DEF-MET-9179` fixed at the commit. Unit is one of the
// build's units or *Whole build*. Target date is optional: an order with no
// date falls back to its priority's SLA, which is the raise door's own rule.
//
// ⚠ **THE TOAST NAMES THE ORDER THE SERVER MADE**, never one this screen
// assumed — `order_no` is read off the answer. A refusal stays in the dialog,
// in the server's own words (`FormModal`'s envelope handling), because a clerk
// whose role or the build's state refuses the raise must see why.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { raiseWorkOrder } from "@/features/customers/newConnectEndpoints";
import type { Translator } from "@/features/customers/newConnectShared";

import { listTemplates } from "../workEndpoints";

export interface RaiseOrderUnit {
  id: string;
  label: string;
}

const RAISE_SCHEMA = z.object({ template: z.string().min(1) }).passthrough();

/** The value the form posts — exported so a test asserts the BODY, not a call. */
export interface RaiseOrderChoice {
  templateId: string;
  templateName: string;
  service: string;
  unitId: string;
  targetDate: string;
}

export function raiseOrderBody(connectionId: string, choice: RaiseOrderChoice) {
  return {
    connection_id: connectionId,
    type: choice.templateName,
    template_id: choice.templateId,
    service: choice.service === "" ? null : choice.service,
    unit_id: choice.unitId === "" ? null : choice.unitId,
    // A unit pick is per-unit work; no unit is the build's own (premise) work.
    scope: choice.unitId === "" ? "per_premise" : "per_unit",
    // ⚠ **NOON, NOT A BARE DATE (found in the browser walk, 2026-10-02).** The
    // raise door reads a bare date as MIDNIGHT in the server's zone, and the
    // build's Work tab then printed *Due by 10/19* for a clerk who picked
    // 10/20 — the tenant's zone is behind UTC. Noon is the one instant that
    // stays on the picked calendar day in every zone a utility can be in
    // (UTC−11 … UTC+11); the day is what the clerk chose, not the hour.
    due_at: choice.targetDate === "" ? null : `${choice.targetDate}T12:00:00Z`,
  };
}

export function BuildRaiseOrderDialog(props: {
  t: Translator;
  connectionId: string;
  /** The build's own service CODES — `record.header.services`. */
  services: readonly string[];
  units: readonly RaiseOrderUnit[];
  /** The tenant's Regional format, for the date picker's echo (IS-8). */
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  onClose: () => void;
  /** Called with the server's `order_no` once the order exists. */
  onRaised: (orderNo: string | null) => void;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const [templateId, setTemplateId] = useState("");
  const [service, setService] = useState("");
  const [unitId, setUnitId] = useState("");
  const [targetDate, setTargetDate] = useState("");

  const templates = useQuery({
    queryKey: ["work", "templates", "raise-from-build"],
    queryFn: () => listTemplates({ per: 100 }, client),
    retry: false,
  });
  // PUBLISHED ONLY — `version` 0 is the draft state (`BR-WRK-011`).
  const published = useMemo(
    () => (templates.data?.results ?? []).filter((row) => (row.version ?? 0) >= 1),
    [templates.data],
  );
  const picked = published.find((row) => row.id === templateId) ?? null;

  const serviceName = (code: string) => t(`work.orders.service.${code}`, { defaultValue: code });

  async function submit(): Promise<FormSubmitOutcome> {
    if (picked === null) {
      return {
        ok: false,
        error: { code: "VAL-001", message_key: "customers.build.raise.pickJob" },
      };
    }
    try {
      const made = await raiseWorkOrder(
        raiseOrderBody(props.connectionId, {
          templateId: picked.id,
          templateName: picked.name,
          service,
          unitId,
          targetDate,
        }),
        client,
      );
      props.onRaised(made.order_no ?? null);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("customers.build.raise.title", { defaultValue: "Raise work order" })}
      schema={RAISE_SCHEMA}
      values={{ template: templateId }}
      submitLabel={t("customers.build.raise.submit", { defaultValue: "Raise order" })}
      onClose={props.onClose}
      onSubmit={submit}
    >
      <SelectField
        id="build-raise-template"
        label={t("customers.build.raise.job", { defaultValue: "Job type" })}
        required
        value={templateId}
        onChange={(next) => {
          setTemplateId(next);
          // The template's own service is OFFERED when — and only when — the
          // build carries it; the clerk can still change it.
          const row = published.find((one) => one.id === next);
          const own = row?.service?.code ?? "";
          setService(props.services.includes(own) ? own : "");
        }}
        options={[
          { value: "", label: t("customers.build.raise.pick", { defaultValue: "Choose…" }) },
          ...published.map((row) => ({ value: row.id, label: row.name })),
        ]}
      />
      <SelectField
        id="build-raise-service"
        label={t("customers.build.raise.service", { defaultValue: "Service" })}
        value={service}
        onChange={setService}
        options={[
          {
            value: "",
            label: t("customers.build.raise.noService", { defaultValue: "No service" }),
          },
          ...props.services.map((code) => ({ value: code, label: serviceName(code) })),
        ]}
      />
      <SelectField
        id="build-raise-unit"
        label={t("customers.build.raise.unit", { defaultValue: "Unit" })}
        value={unitId}
        onChange={setUnitId}
        options={[
          {
            value: "",
            label: t("customers.build.work.wholeBuild", { defaultValue: "Whole build" }),
          },
          ...props.units.map((unit) => ({ value: unit.id, label: unit.label })),
        ]}
      />
      <DatePickerField
        id="build-raise-date"
        label={t("customers.build.raise.date", { defaultValue: "Target date" })}
        value={targetDate}
        onChange={setTargetDate}
        dateFormat={props.dateFormat}
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-163-BRC10 item 1 · DEF-CUS-9177 · decision log 2026-10-02 (`56eb54ba9`)
// generated: 2026-10-02 by lane NC-B
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
