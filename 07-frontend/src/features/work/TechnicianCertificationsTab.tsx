// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — P3.48 / ruling 28 (*"here
//           certification tab wireframe is missing"*): Certifications as a
//           TABLE, with add and renew. Built from the IMAGE
//           `05-prototype/work-backoffice-2026-10-04/images/33-crews-one-technician-certifications.png`.
// Server:   `PUT /work/technicians/{slug}/certifications` — a REPLACE of the
//           whole set, so Add and Renew each send every row the person holds
//           with the one changed (`US-WRK-021` TC-5: a date in the past is
//           accepted, which is how a lapse is recorded truthfully).
// Rules:    PO answer 2 of 2026-10-04, *"(a) Warn only, the same as skills."*
//           (`BR-WRK-030` SUPERSEDED) — a run-out certification is a WARNING
//           pill and never the danger tone of a refusal · B14 rule 15 (a row
//           action is an icon with a name) · 17 · 20 (`PlainTable`, the kit's
//           non-paged table) · 33 · 43
// Tests:    src/features/work/crewsLane.dom.test.tsx · crews2Lane.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PROOF COLUMN — drawn since lane CREWS-2 (round 6), on lane SRV-4's
// server (`2.513.0`, `tenancy/0060`).** Until then this header said *"NO PROOF
// COLUMN"*: nothing stored a certificate's document, so the column could only
// ever hold a dash (law 2's dead UI). Now a row names its scan and opens it
// through our own content route (`openDocumentContent`, a navigation so the
// session cookie rides along); a row with none draws the dash image 33 draws.
// The scan is attached in the Add / Edit dialog — the drawing gives the row one
// action, *Edit*, and a separate upload control would be a second door to the
// same fact. A renewal keeps the scan (the server's rule), so the field is
// optional on Edit and replaces the file only when one is chosen.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { openDocumentContent } from "@/components/documents";
import { FileField } from "@/components/FileField";
import { DatePickerField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PencilIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { InlineLink, PlainTable } from "@/components/Surfaces";
import { useTenantRegional } from "@/components/TenantRegional";
import { Note } from "@/components/TextBits";
import { Dash } from "@/features/customers/customersShared";

import {
  PROOF_CONTENT_TYPES,
  PROOF_MAX_BYTES,
  setTechnicianCertifications,
  uploadCertificateProof,
} from "./crewsEndpoints";
import type { HeldCertification, TechnicianDetail } from "./workEndpoints";

const DAY = 24 * 60 * 60 * 1000;

/** Valid · expires in N days (≤ 30) · expired — against the SERVER's day. */
export function certificationStanding(
  expiresOn: string | null,
  today: string,
): { kind: "valid" | "expiring" | "expired" | "open"; days: number } {
  if (expiresOn === null) return { kind: "open", days: 0 };
  const days = Math.round((Date.parse(`${expiresOn}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / DAY);
  if (Number.isNaN(days)) return { kind: "open", days: 0 };
  if (days < 0) return { kind: "expired", days };
  if (days <= 30) return { kind: "expiring", days };
  return { kind: "valid", days };
}

export function ExpiryDate(props: { value: string | null }) {
  const regional = useTenantRegional();
  if (props.value === null) return <Dash />;
  if (regional === null) return <span className="tabular-nums">{props.value}</span>;
  return <DateCell value={props.value} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />;
}

type Editing = { mode: "add" } | { mode: "renew"; cert: HeldCertification } | null;

export function TechnicianCertificationsTab(props: { client: ApiClient; detail: TechnicianDetail }) {
  const { t } = useTranslation();
  const { detail } = props;
  const [editing, setEditing] = useState<Editing>(null);
  const today = detail.today?.on ?? new Date().toISOString().slice(0, 10);

  return (
    <Panel
      as="section"
      title={t("work.technician.certifications.title")}
      trailing={
        <Button variant="secondary" data-add-certification="" onClick={() => setEditing({ mode: "add" })}>
          {t("work.technician.certifications.add")}
        </Button>
      }
      data-technician-certifications=""
    >
      {detail.certifications.length === 0 ? (
        <Note>{t("work.technician.certifications.none")}</Note>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th>{t("work.technician.certifications.col.certification")}</th>
              <th>{t("work.technician.certifications.col.expires")}</th>
              <th>{t("work.technician.certifications.col.status")}</th>
              <th>{t("work.technician.certifications.col.proof")}</th>
              <th>
                <span className="sr-only">{t("work.technician.certifications.col.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {detail.certifications.map((cert) => {
              const standing = certificationStanding(cert.expires_on, today);
              return (
                <tr key={cert.certification_type_id} data-certification={standing.kind}>
                  <td>{cert.name ?? <Dash />}</td>
                  <td>
                    <ExpiryDate value={cert.expires_on} />
                  </td>
                  <td>
                    {standing.kind === "open" ? (
                      <Dash />
                    ) : (
                      <StatusPill tone={standing.kind === "valid" ? "success" : "warning"}>
                        {standing.kind === "expiring"
                          ? t("work.technician.certifications.standing.expiring", { count: standing.days })
                          : t(`work.technician.certifications.standing.${standing.kind}`)}
                      </StatusPill>
                    )}
                  </td>
                  <td data-certification-proof={cert.proof ? cert.proof.name : ""}>
                    {cert.proof ? (
                      <InlineLink
                        title={t("work.technician.certifications.openProof", { name: cert.proof.name })}
                        onClick={() => {
                          if (cert.proof) openDocumentContent(cert.proof.url, "view");
                        }}
                      >
                        {cert.proof.name}
                      </InlineLink>
                    ) : (
                      <Dash />
                    )}
                  </td>
                  <td>
                    <RowActions>
                      <RowAction
                        icon={<PencilIcon />}
                        label={t("work.technician.certifications.edit") /* image 33 draws ✎ Edit */}
                        onClick={() => setEditing({ mode: "renew", cert })}
                      />
                    </RowActions>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </PlainTable>
      )}
      {editing !== null && (
        <CertificationModal
          client={props.client}
          detail={detail}
          editing={editing}
          onClose={() => setEditing(null)}
        />
      )}
    </Panel>
  );
}

const certSchema = z.object({ type: z.string().min(1), expires: z.string().regex(/^\d{4}-\d{2}-\d{2}$/) });

/** The proof a clerk chose, refused HERE by kind or size so they hear it
 *  before the upload. A refusal names the message key; null is acceptable. */
export function proofFileRefusal(file: File | null): string | null {
  if (file === null) return null;
  const type = file.type.toLowerCase();
  if (!(PROOF_CONTENT_TYPES as readonly string[]).includes(type) && type !== "image/jpg") {
    return "work.technician.certifications.proofType";
  }
  if (file.size > PROOF_MAX_BYTES) return "work.technician.certifications.proofTooLarge";
  return null;
}

/** Add (a type the person does not hold yet) or Renew (a new expiry date),
 *  each with an optional scan of the certificate (image 33's PROOF). */
function CertificationModal(props: {
  client: ApiClient;
  detail: TechnicianDetail;
  editing: Exclude<Editing, null>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const regional = useTenantRegional();
  const { detail, editing } = props;
  const [type, setType] = useState(editing.mode === "renew" ? editing.cert.certification_type_id : "");
  const [expires, setExpires] = useState(editing.mode === "renew" ? (editing.cert.expires_on ?? "") : "");
  const [proof, setProof] = useState<File | null>(null);
  const proofRefusal = proofFileRefusal(proof);

  const typesQuery = useQuery({
    queryKey: ["lookups", "certification_types", "picker"],
    queryFn: () => getLookupEntries("certification_types", { per: 200 }, props.client),
    retry: false,
    enabled: editing.mode === "add",
  });
  const held = new Set(detail.certifications.map((cert) => cert.certification_type_id));
  const options = (typesQuery.data?.results ?? [])
    .filter((row) => row.active && !held.has(row.id))
    .map((row) => ({ value: row.id, label: row.name }));

  const save = useMutation({
    mutationFn: async () => {
      const rows = detail.certifications.map((cert) => ({
        certification_type_id: cert.certification_type_id,
        expires_on: cert.certification_type_id === type ? expires : cert.expires_on,
      }));
      if (editing.mode === "add") rows.push({ certification_type_id: type, expires_on: expires });
      const saved = await setTechnicianCertifications(detail.slug, rows, props.client);
      // The certificate row must exist before its scan can point at it, so the
      // upload follows the replace. A refused upload leaves the date saved and
      // the dialog open with the server's sentence.
      if (proof !== null) await uploadCertificateProof(detail.slug, type, proof, props.client);
      return saved;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["work"] }),
  });

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    if (proofRefusal !== null) {
      return {
        ok: false,
        error: { code: "", message_key: proofRefusal, field_errors: [{ field: "proof", message_key: proofRefusal }] },
      };
    }
    try {
      await save.mutateAsync();
      props.onClose();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  const renewing = editing.mode === "renew";
  return (
    <FormModal
      title={t(renewing ? "work.technician.certifications.renewTitle" : "work.technician.certifications.addTitle")}
      schema={certSchema}
      values={{ type, expires }}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t(renewing ? "work.technician.certifications.renewSubmit" : "work.technician.certifications.addSubmit")}
    >
      {renewing ? (
        <TextField
          id="certification"
          label={t("work.technician.certifications.col.certification")}
          value={editing.cert.name ?? ""}
          onChange={() => undefined}
          readOnly
        />
      ) : (
        <SelectField
          id="type"
          label={t("work.technician.certifications.col.certification")}
          value={type}
          onChange={setType}
          options={options}
          placeholder={t("work.technician.certifications.choose")}
          required
        />
      )}
      <DatePickerField
        id="expires"
        label={t("work.technician.certifications.col.expires")}
        value={expires}
        onChange={setExpires}
        dateFormat={regional?.dateFormat ?? "YYYY-MM-DD"}
        required
      />
      <FileField
        id="proof"
        label={t("work.technician.certifications.col.proof")}
        accept="application/pdf,image/png,image/jpeg"
        help={
          renewing && editing.cert.proof
            ? t("work.technician.certifications.proofOnFile", { name: editing.cert.proof.name })
            : t("work.technician.certifications.proofHelp")
        }
        onChange={setProof}
        fileName={proof?.name ?? null}
        error={proofRefusal === null ? undefined : t(proofRefusal)}
      />
    </FormModal>
  );
}

export default TechnicianCertificationsTab;
