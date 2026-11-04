// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-008 (EP-CWP-03) TC-1 — a clerk moves the Elm St burst to
//           *crew on site*, and sets the stretch it affects.
//           Screens: none new — a SECTION of REQ-02, the service-request
//           detail (`R13`: screen numbers are the PO's;
//           `10-execution-plan.md` §0 row 22)
// Rules:    B14 rule 36 (the shared kit is how you comply — `Panel`,
//           `StatusPill`, `Button`, `TextField`, `PlainTable` are all the
//           staff kit's; nothing here is hand-rolled) · r10 rule 4 (`Verb ✓`
//           commits) · rule 6 (nothing here is the danger tier: moving a job
//           to *crew on site* is not a destructive commit) · rule 10 · rule 17
//           (an empty affected set says what is missing) · rule 20 (one table
//           type) · BR-CWP-012 · BR-CWP-027 (`premises_id` stays null until a
//           clerk resolves it) · B14 rule 31 (no id is a visible value)
// Tests:    07-frontend/src/features/customers/ServiceRequestInterruption.test.tsx
//           ⚠ This citation named a file that did not exist from the day it was
//           written until DEF-CWP-3743 (2026-09-04). The file exists now.
// Impacts:  06-backend/apps/customers/service_request_api.service_request_interruption
// ───────────────────────────────────────────────────────
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { WorkingButton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";

import type { InterruptionSection } from "./serviceRequestEndpoints";
import {
  getServiceRequestInterruption,
  openServiceRequestInterruption,
  patchServiceRequestInterruption,
} from "./serviceRequestEndpoints";

const TONE: Record<string, "warning" | "danger" | "success"> = {
  looking_into_it: "warning",
  crew_on_site: "danger",
  resolved: "success",
};

export function interruptionKey(requestId: string): readonly unknown[] {
  return ["service-request", requestId, "interruption"];
}

/** A number a clerk typed, or null. `""` is not `0`. */
export function houseNumber(raw: string): number | null {
  const trimmed = raw.trim();
  return /^\d{1,6}$/.test(trimmed) ? Number(trimmed) : null;
}

/**
 * ⚠ **ABSENT, NOT EMPTY.** A request that is neither a report nor attached to an
 * interruption answers 404 and this renders NOTHING — otherwise every move-in
 * and every new connect in the product would carry a blank *Interruption* frame.
 *
 * ⚠ **A REPORT WITH NO INTERRUPTION IS THE ORDINARY CASE SINCE `CR-072`, AND
 * THIS SECTION IS WHERE ONE IS OPENED.** A passer-by's form used to raise the
 * operational record itself; it does not any more, because a stranger cannot
 * settle whether something is an outage. So the section has two faces: a report
 * nobody has judged yet, with the commit that judges it (`BR-CWP-101`), and the
 * record itself once somebody has.
 */
export function ServiceRequestInterruption(props: { requestId: string; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [street, setStreet] = useState<string | null>(null);
  const [from, setFrom] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);

  const query = useQuery({
    queryKey: interruptionKey(props.requestId),
    queryFn: () => getServiceRequestInterruption(props.requestId, client),
    retry: false,
  });

  const mutate = useMutation({
    mutationFn: (body: Parameters<typeof patchServiceRequestInterruption>[1]) =>
      patchServiceRequestInterruption(props.requestId, body, client),
    onSuccess: (view) => {
      setRefusal(null);
      queryClient.setQueryData(interruptionKey(props.requestId), view);
    },
    onError: (error) => setRefusal(refusalText(t, error)),
  });

  const open = useMutation({
    mutationFn: (body: { interruption_id?: string }) =>
      openServiceRequestInterruption(props.requestId, body, client),
    onSuccess: (view) => {
      setRefusal(null);
      queryClient.setQueryData(interruptionKey(props.requestId), view);
    },
    onError: (error) => setRefusal(refusalText(t, error)),
  });

  const section: InterruptionSection | undefined = query.data;
  if (section === undefined) {
    return null;
  }
  const row = section.interruption;

  if (row === null) {
    // ⚠ NOT AN EMPTY FRAME — a report waiting on a judgment, and the judgment.
    const nearby = section.already_open_nearby;
    return (
      <Panel as="section" data-panel-name="interruption">
        <h3>{t("customers.serviceRequest.interruption.title")}</h3>
        <p className="m-0 mb-3 max-w-measure text-sm text-neutral-700" data-report-line="">
          {section.report.kind === null
            ? section.report.location_text
            : `${t(`portal.report.kind.${section.report.kind}`)} · ${section.report.location_text}`}
        </p>
        {/* B14 rule 32 — one sentence, and it says what the absence MEANS
            rather than that something is missing. */}
        <Note>{t("customers.serviceRequest.interruption.noneYet")}</Note>
        {refusal !== null ? <RefusalStrip>{refusal}</RefusalStrip> : null}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {nearby !== null ? (
            <WorkingButton
              working={open.isPending}
              onClick={() => open.mutate({ interruption_id: nearby.id })}
            >
              {t("customers.serviceRequest.interruption.attachTo", {
                reference: nearby.reference ?? nearby.location_text,
              })}
            </WorkingButton>
          ) : null}
          <Button
            variant={nearby === null ? "primary" : "secondary"}
            data-open-interruption=""
            disabled={open.isPending}
            onClick={() => open.mutate({})}
          >
            {t("customers.serviceRequest.interruption.openOne")}
          </Button>
        </div>
      </Panel>
    );
  }

  const streetValue = street ?? row.affected_area?.street ?? "";
  const fromValue = from ?? (row.affected_area?.from?.toString() ?? "");
  const toValue = to ?? (row.affected_area?.to?.toString() ?? "");

  return (
    <Panel as="section" data-panel-name="interruption">
      <h3>{t("customers.serviceRequest.interruption.title")}</h3>
      <p className="m-0 mb-3 max-w-measure text-sm text-neutral-700">
        <span className="font-semibold" data-interruption-reference="">
          {row.reference ?? "—"}
        </span>{" "}
        · {row.location_text} ·{" "}
        <StatusPill tone={TONE[row.status] ?? "warning"}>
          {t(`customers.serviceRequest.interruption.status.${row.status}`)}
        </StatusPill>
      </p>

      {/* The status control. r10 rule 4: `Verb ✓` commits. NOT the danger tier
          (rule 6) — this is a job moving forward, not something being cut off. */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {section.statuses
          .filter((one) => one !== row.status)
          .map((one) => (
            <Button
              key={one}
              variant="secondary"
              size="sm"
              data-move-to={one}
              disabled={mutate.isPending}
              onClick={() => mutate.mutate({ status: one })}
            >
              {t(`customers.serviceRequest.interruption.moveTo.${one}`)}
            </Button>
          ))}
      </div>

      <h3>{t("customers.serviceRequest.interruption.areaTitle")}</h3>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <TextField
          id="interruption-street"
          label={t("customers.serviceRequest.interruption.street")}
          value={streetValue}
          onChange={setStreet}
          required
        />
        <TextField
          id="interruption-from"
          label={t("customers.serviceRequest.interruption.from")}
          value={fromValue}
          onChange={setFrom}
          numeric
        />
        <TextField
          id="interruption-to"
          label={t("customers.serviceRequest.interruption.to")}
          value={toValue}
          onChange={setTo}
          numeric
        />
      </div>
      {refusal !== null ? <RefusalStrip>{refusal}</RefusalStrip> : null}
      <div className="mt-4 flex items-center gap-2">
        <WorkingButton
          working={mutate.isPending}
          onClick={() =>
            mutate.mutate({
              affected_area:
                streetValue.trim() === ""
                  ? null
                  : {
                      street: streetValue.trim(),
                      from: houseNumber(fromValue),
                      to: houseNumber(toValue),
                    },
            })
          }
        >
          {t("customers.serviceRequest.interruption.setArea")}
        </WorkingButton>
      </div>

      <div className="mt-4">
        {/* r10 rule 17 — an empty set says what is missing, and here that is a
            real state rather than a gap: an interruption can exist before we
            know who it touches (US-CWP-008 TC-3). */}
        {row.affected_premises.length === 0 ? (
          <Note>{t("customers.serviceRequest.interruption.noneAffected")}</Note>
        ) : (
          <>
            {/* ⚠ A LABEL AND A FIGURE, NOT A SENTENCE. *"2 address(es), 3
                unit(s)"* is English grammar leaking into eleven catalogues;
                a label beside a number needs no plural in any of them. */}
            <Note>
              {t("customers.serviceRequest.interruption.addresses")}{" "}
              <span className="font-semibold tabular-nums text-neutral-900">
                {row.affected_premises_count}
              </span>{" "}
              · {t("customers.serviceRequest.interruption.units")}{" "}
              <span className="font-semibold tabular-nums text-neutral-900">
                {row.affected_unit_count}
              </span>
            </Note>
            <PlainTable>
              <thead>
                <tr>
                  <th>{t("customers.serviceRequest.interruption.address")}</th>
                  <th>{t("customers.serviceRequest.interruption.postcode")}</th>
                </tr>
              </thead>
              <tbody>
                {row.affected_premises.map((one) => (
                  <tr key={one.id} data-affected={one.address_line}>
                    <td>{one.address_line}</td>
                    <td>{one.postal_code ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </>
        )}
      </div>
    </Panel>
  );
}
