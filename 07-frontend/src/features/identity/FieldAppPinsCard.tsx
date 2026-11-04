// ── Trace ──────────────────────────────────────────────
// Change:   CR-187-BRC10 — closes the build of OQ-FLD-12797 (decision log
//           2026-10-24 "FOUR PO ANSWERS ON THE FIELD APP'S OPEN QUESTIONS" (3))
// Screens:  S8 (Settings → Security) — the "Field app certificates" card
// Rules:    B14 rule 21 (Tailwind utilities, no stylesheet class) · rule 15
//           (row actions are icons) · rule 31's neighbour (the LABEL is the
//           visible value; the key's hash is shown smaller and copyable) ·
//           rule 33 (a heading ≤3 words, a fact ≤6, rationale ZERO) · rule 43
//           (a piece of UI is a COMPONENT) · BR-IDN-019 (System Admin edits,
//           Executive views) · BR-SHL-025 (a control that cannot act says why)
// ───────────────────────────────────────────────────────
// THE KEYS THE FIELD APP TRUSTS, KEPT HERE AND NOT IN THE APP.
//
// PO, 2026-10-24, verbatim: *"plese dont hardcode it use settings - security
// values set in staff portal"*. The worked example the ruling carries is the
// whole workflow this card exists for: the issuer renews in 2027; in December
// 2026 the office adds the new issuer's key here; every phone picks it up at
// its next sync; then the old key is deactivated. No app update.
//
// ⚠ **IT OWNS ITS READ AND ITS SAVE.** Not props from the tab: a card with an
// optional `pins` prop renders nothing the day a caller forgets it and every
// test still passes (hard-won law 2). It sits under the Audit log card, so
// the three cards, Save and the audit card the PO approved on 2026-09-29 keep
// their arrangement exactly.
//
// ⚠ **EVERY ACT SENDS THE WHOLE LIST.** Add and deactivate are both "the list
// as it should be", so the SERVER sees the result the phones would get and is
// the one judge of it — at least two active, unexpired keys, and at least one
// key that is active today kept active (`apps/identity/field_pins.py`). This
// card repeats none of those rules: a second copy here is a copy that drifts.
// It shows the server's refusal where the click was made.
//
// ⚠ **THE 60 IS THE SERVER'S.** `warning_days` and each row's `status` arrive
// on the wire, so which side of the line a date falls on is decided once.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getFieldAppPins, saveFieldAppPins } from "@/api/endpoints";
import type { FieldAppPin, FieldAppPinEdit, FieldAppPins } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome, ServerErrorEnvelope } from "@/components/FormModal";
import { CopyIcon, PowerIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { WarningBox } from "@/components/WarningBox";
import { RefusalNotice, apiErrorText } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";

const STATUS_TONE: Record<FieldAppPin["status"], StatusTone> = {
  valid: "success",
  expiring: "warning",
  expired: "danger",
  inactive: "muted",
};

/** The list as a PUT carries it — the server's derived fields left behind. */
export function pinEdits(pins: readonly FieldAppPin[]): FieldAppPinEdit[] {
  return pins.map((p) => ({
    spki_sha256: p.spki_sha256,
    label: p.label,
    not_after: p.not_after,
    active: p.active,
  }));
}

/** Is any ACTIVE key inside the server's warning window? */
export function hasExpiringPin(data: FieldAppPins): boolean {
  return data.pins.some((p) => p.status === "expiring");
}

/**
 * The refusal a clerk reads after a deactivate the server refused. The
 * envelope's own sentence is generic (*"Those keys can't be used"*); the
 * list-level field error says WHY (*"Keep at least 2 valid keys."*), so that
 * one wins when it is there.
 */
function refusalFor(error: unknown, t: (k: string, p?: Record<string, unknown>) => string): Refusal {
  if (isApiError(error)) {
    const listLevel = error.fieldErrors.find((f) => f.field === "pins");
    if (listLevel !== undefined) {
      return { message: t(listLevel.message_key, listLevel.params ?? {}), brRef: error.brRef };
    }
  }
  return { message: apiErrorText(error, t), brRef: isApiError(error) ? error.brRef : null };
}

// Shape only — the server is the judge of every rule (see the header).
const BASE64_32 = /^[A-Za-z0-9+/]{43}=$/;
const CALENDAR_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function addPinSchema(t: (k: string) => string) {
  return z.object({
    label: z.string().trim().min(1, t("errors.identity.pin_label_required")),
    spki_sha256: z.string().trim().regex(BASE64_32, t("errors.identity.pin_hash_invalid")),
    not_after: z.string().regex(CALENDAR_DATE, t("errors.identity.pin_date_invalid")),
  });
}

/**
 * The new row's server field errors arrive as `pins[<n>].<field>`; the form's
 * inputs are named `<field>`. Renamed here so each refusal lands UNDER the
 * input it is about rather than nowhere.
 */
export function remapNewPinErrors(envelope: ServerErrorEnvelope, index: number): ServerErrorEnvelope {
  const prefix = `pins[${index}].`;
  return {
    ...envelope,
    field_errors: (envelope.field_errors ?? []).map((f) =>
      f.field.startsWith(prefix) ? { ...f, field: f.field.slice(prefix.length) } : f,
    ),
  };
}

export interface FieldAppPinsCardProps {
  /** A4: an Executive VIEWS (BR-IDN-019). Every act is disabled with its reason. */
  readOnly: boolean;
  readOnlyReason: string;
  client: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

export function FieldAppPinsCard(props: FieldAppPinsCardProps) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const pinsQuery = useQuery({
    queryKey: queryKeys.fieldAppPins,
    queryFn: () => getFieldAppPins(props.client),
    retry: false,
  });

  const save = useMutation({
    mutationFn: (pins: FieldAppPinEdit[]) => saveFieldAppPins(pins, props.client),
    onSuccess: (saved: FieldAppPins) => {
      queryClient.setQueryData(queryKeys.fieldAppPins, saved);
      setRefusal(null);
      fireToast(t("settings.security.pins.saved"));
    },
    onError: (error: unknown) => setRefusal(refusalFor(error, (k, p) => t(k, p))),
  });

  const reason = props.readOnly ? props.readOnlyReason : null;

  return (
    <section
      data-field-app-pins-card=""
      className="bg-surface border-t-2 border-t-accent pt-6 px-4 pb-6 flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <h3 className="m-0 text-h5">{t("settings.security.pins.title")}</h3>
          <p className="m-0 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] max-w-[var(--desc-measure)]">
            {t("settings.security.pins.hint")}
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={props.readOnly || pinsQuery.data === undefined}
          title={reason ?? undefined}
          onClick={() => setAdding(true)}
        >
          {t("settings.security.pins.add")}
        </Button>
      </div>

      {pinsQuery.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : pinsQuery.data === undefined ? (
        <FailedWithRetry
          title={t("settings.security.pins.failed")}
          reason=""
          onRetry={() => void pinsQuery.refetch()}
        />
      ) : (
        <>
          {hasExpiringPin(pinsQuery.data) && (
            <WarningBox
              tone="soon"
              data-warning="field-app-pin-expiring"
              sentence={t("settings.security.pins.expiringWarning", {
                days: pinsQuery.data.warning_days,
              })}
            />
          )}
          {pinsQuery.data.source === "default" && (
            <p data-field-app-pins-default="" className="m-0 text-sm">
              {t("settings.security.pins.defaultSource")}
            </p>
          )}
          <RefusalNotice refusal={refusal} />
          {pinsQuery.data.pins.length === 0 ? (
            <p className="m-0 text-md">{t("settings.security.pins.empty")}</p>
          ) : (
            <PlainTable className="w-full">
              <thead>
                <tr>
                  <th scope="col">{t("settings.security.pins.colCertificate")}</th>
                  <th scope="col">{t("settings.security.pins.colExpires")}</th>
                  <th scope="col">{t("settings.security.pins.colStatus")}</th>
                  <th scope="col">{t("settings.security.pins.colActions")}</th>
                </tr>
              </thead>
              <tbody>
                {pinsQuery.data.pins.map((pin, index) => (
                  <tr key={pin.spki_sha256} data-field-app-pin={pin.status}>
                    <td>
                      <div className="flex flex-col gap-1">
                        {/* The LABEL is the visible value; the hash is the
                            evidence, smaller, in a mono face, copyable. */}
                        <span className="font-semibold">{pin.label}</span>
                        <code
                          data-pin-hash=""
                          className="text-xs font-mono break-all text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
                        >
                          {pin.spki_sha256}
                        </code>
                      </div>
                    </td>
                    <td>
                      <DateCell
                        value={pin.not_after}
                        timeZone={props.timeZone}
                        dateFormat={props.dateFormat}
                      />
                    </td>
                    <td>
                      <StatusPill tone={STATUS_TONE[pin.status]}>
                        {t(`settings.security.pins.status.${pin.status}`)}
                      </StatusPill>
                    </td>
                    <td>
                      <RowActions>
                        <RowAction
                          label={t("settings.security.pins.copy")}
                          icon={<CopyIcon />}
                          onClick={() => {
                            void navigator.clipboard?.writeText(pin.spki_sha256);
                            fireToast(t("settings.security.pins.copied"));
                          }}
                        />
                        <RowAction
                          label={
                            pin.active
                              ? t("settings.security.pins.deactivate")
                              : t("settings.security.pins.activate")
                          }
                          icon={<PowerIcon />}
                          danger={pin.active}
                          reason={reason}
                          working={save.isPending}
                          onClick={() => {
                            const next = pinEdits(pinsQuery.data.pins);
                            next[index] = { ...next[index], active: !pin.active };
                            save.mutate(next);
                          }}
                        />
                      </RowActions>
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          )}
        </>
      )}

      {adding && pinsQuery.data !== undefined && (
        <AddPinModal
          current={pinsQuery.data}
          client={props.client}
          dateFormat={props.dateFormat}
          onClose={() => setAdding(false)}
          onSaved={(saved) => {
            queryClient.setQueryData(queryKeys.fieldAppPins, saved);
            setRefusal(null);
            setAdding(false);
            fireToast(t("settings.security.pins.saved"));
          }}
        />
      )}
    </section>
  );
}

function AddPinModal(props: {
  current: FieldAppPins;
  client: ApiClient;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onSaved: (saved: FieldAppPins) => void;
}) {
  const { t } = useTranslation();
  const [label, setLabel] = useState("");
  const [hash, setHash] = useState("");
  const [notAfter, setNotAfter] = useState("");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    const index = props.current.pins.length;
    const next: FieldAppPinEdit[] = [
      ...pinEdits(props.current.pins),
      { spki_sha256: hash.trim(), label: label.trim(), not_after: notAfter, active: true },
    ];
    try {
      props.onSaved(await saveFieldAppPins(next, props.client));
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: remapNewPinErrors(formErrorEnvelope(error), index) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("settings.security.pins.addTitle")}
      schema={addPinSchema((k) => t(k))}
      values={{ label, spki_sha256: hash, not_after: notAfter }}
      submitLabel={t("settings.security.pins.add")}
      cancelLabel={t("settings.security.pins.cancel")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <TextField id="label" label={t("settings.security.pins.label")} value={label} onChange={setLabel} required />
      <TextField
        id="spki_sha256"
        label={t("settings.security.pins.hash")}
        value={hash}
        onChange={setHash}
        help={t("settings.security.pins.hashHelp")}
        required
      />
      <DatePickerField
        id="not_after"
        label={t("settings.security.pins.notAfter")}
        value={notAfter}
        onChange={setNotAfter}
        dateFormat={props.dateFormat}
        required
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-187-BRC10 · OQ-FLD-12797 (decision log 2026-10-24 item 3)
// generated: 2026-10-24 by lane PINS
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
