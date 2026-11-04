// ── Trace ──────────────────────────────────────────────
// Change:   CR-173-BRC10 — a connection's named field GROUP as its own panel
//           with its own save. New World / Logos's *Send to City folder* is the
//           first: Server · Port · User name · Password · Folder · Server key,
//           and **Test connection**.
// Rules:    PO 2026-10-07, verbatim: *"this is okay"* over the six-item table
//           (decision log *"PO APPROVED — THE SEND TO CITY FOLDER SECTION"*) ·
//           *"this is tenant/utility data and should be handled from screen
//           itself"* · BR-INT-043 (the field slot is a closed vocabulary of
//           KINDS, no provider branch) · BR-INT-003 (the password is typed
//           once; the screen holds only `••••` + last four) · B14 rules 21
//           (Tailwind, no stylesheet class), 31, 33, 35, 38 (one labelled row
//           per field), 43 (a component, not code inside a page), 44
// Tests:    src/features/integrations/FieldGroupPanel.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ NO VENDOR IS NAMED IN THIS FILE. The group's fields, their order, their
// kinds and their English fallbacks come off the manifest (`ProviderCard.fields`
// where `group` matches); the title and the sentences come from the catalogue
// under `integrations.group.<group>.*`. A second connector with a folder to send
// to declares the same group word and gets this panel with no code.
//
// ⚠ THE PANEL IS NOT A SECOND COPY OF THE DETAILS FORM. The connection's own
// Save (PATCH) keeps a grouped field's stored value whatever it is sent
// (`services.ungrouped`), so the two forms cannot overwrite each other.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import {
  getFieldGroup,
  resendFieldGroupDay,
  saveFieldGroup,
  testFieldGroup,
} from "@/api/fileDropEndpoints";
import type { FieldGroupTest, FieldGroupView, ResendResult } from "@/api/fileDropEndpoints";
import type { ManifestField, ProviderCard } from "@/api/integrationsEndpoints";
import { Button } from "@/components/Button";
import { OutcomeCard } from "@/components/OutcomeCard";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";

import { RENDER, fieldLabel } from "./ConnectModal";

/** The groups a card declares, in first-appearance order. */
export function fieldGroups(card: ProviderCard): string[] {
  const seen: string[] = [];
  for (const one of card.fields) {
    if (one.group && !seen.includes(one.group)) seen.push(one.group);
  }
  return seen;
}

const ROW = "grid grid-cols-[160px_1fr] items-baseline gap-3 py-2";

export function FieldGroupPanel(props: { card: ProviderCard; group: string; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const { card, group } = props;
  const fields: ManifestField[] = card.fields.filter((one) => one.group === group);
  const queryKey = ["integrations", "group", card.key, group];
  const view = useQuery<FieldGroupView>({
    queryKey,
    queryFn: () => getFieldGroup(card.key, group, client),
  });

  const [values, setValues] = useState<Record<string, string> | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [tested, setTested] = useState<FieldGroupTest | null>(null);
  const [resendDay, setResendDay] = useState("");
  const [resendReason, setResendReason] = useState("");
  const [resent, setResent] = useState<ResendResult | null>(null);

  // Seeded ONCE from the server, then the clerk's own; a refetch never
  // overwrites half-typed input. The password box always starts empty.
  useEffect(() => {
    if (view.data === undefined || values !== null) return;
    setValues({ ...view.data.settings });
  }, [view.data, values]);

  function takeRefusal(error: unknown): void {
    if (!isApiError(error)) {
      setRefusal(t("integrations.group.failed"));
      setFieldErrors({});
      return;
    }
    const perField: Record<string, string> = {};
    for (const one of error.fieldErrors) {
      if (one.field !== null) perField[one.field] = t(one.message_key, one.params ?? {});
    }
    setFieldErrors(perField);
    setRefusal(refusalText(t, error));
  }

  const save = useMutation({
    mutationFn: () => saveFieldGroup(card.key, group, values ?? {}, client),
    onSuccess: (fresh) => {
      queryClient.setQueryData(queryKey, fresh);
      setValues({ ...fresh.settings });
      setFieldErrors({});
      setRefusal(null);
      setSaved(true);
      setTested(null);
    },
    onError: (error) => {
      setSaved(false);
      takeRefusal(error);
    },
  });

  const test = useMutation({
    mutationFn: () => testFieldGroup(card.key, group, client),
    onSuccess: (result) => {
      setTested(result);
      void queryClient.invalidateQueries({ queryKey });
      void queryClient.invalidateQueries({ queryKey: ["integrations"] });
      if (result.server_key_captured && result.server_key !== null) {
        setValues((current) => ({ ...(current ?? {}), sftp_host_key: result.server_key ?? "" }));
      }
    },
    onError: (error) => takeRefusal(error),
  });

  const resend = useMutation({
    mutationFn: () => resendFieldGroupDay(card.key, group, resendDay, resendReason, client),
    onSuccess: (result) => {
      setResent(result);
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (error) => takeRefusal(error),
  });

  const title = t(`integrations.group.${group}.title`);
  if (view.isLoading || values === null) {
    return (
      <Panel as="section" title={title} data-field-group={group}>
        <LoadingSkeleton variant="card" />
      </Panel>
    );
  }
  const hint = view.data?.password_hint ?? null;

  return (
    <Panel as="section" title={title} data-field-group={group}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setSaved(false);
          save.mutate();
        }}
      >
        {fields.map((field) => (
          <div key={field.name} className={ROW} data-field={field.name} data-kind={field.kind}>
            <label className="text-sm font-semibold" htmlFor={`field-${field.name}`}>
              {fieldLabel(t, card, field)}
            </label>
            <div>
              {RENDER[field.kind](
                {
                  card,
                  field,
                  value: values[field.name] ?? "",
                  error: fieldErrors[field.name],
                  mode: "connect",
                  replacing: false,
                  readOnly: false,
                  onChange: (name, value) => {
                    setSaved(false);
                    setValues((current) => ({ ...(current ?? {}), [name]: value }));
                  },
                  onStartOAuth: () => undefined,
                },
                t,
              )}
              {fieldErrors[field.name] !== undefined && (
                <p className="mt-1 text-sm text-danger-700" data-field-error={field.name}>
                  {fieldErrors[field.name]}
                </p>
              )}
              {field.kind === "secret" && hint !== null && (
                <p className="mt-1 text-sm text-neutral-600" data-password-hint="">
                  {t("integrations.group.passwordSaved", { hint })}{" "}
                  {t("integrations.group.passwordKeep")}
                </p>
              )}
              {field.kind === "secret" && hint === null && (
                <p className="mt-1 text-sm text-neutral-600" data-secret-help="">
                  {t("integrations.group.passwordStored")}
                </p>
              )}
            </div>
          </div>
        ))}

        <div className={ROW}>
          <div />
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" variant="primary" disabled={save.isPending} data-group-save="">
              {t("integrations.group.save")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={test.isPending || !view.data?.set_up}
              onClick={() => {
                setRefusal(null);
                setTested(null);
                test.mutate();
              }}
              data-group-test=""
            >
              {test.isPending ? t("integrations.group.testing") : t("integrations.group.test")}
            </Button>
            {saved && (
              <span className="text-sm text-success-700" data-group-saved="">
                {t("integrations.group.saved")}
              </span>
            )}
          </div>
        </div>
      </form>

      {refusal !== null && (
        <p className="mt-2 text-sm text-danger-700" role="alert" data-group-refusal="">
          {refusal}
        </p>
      )}

      {tested !== null && (
        <div className="mt-3" data-group-test-result={tested.ok ? "ok" : "refused"}>
          <OutcomeCard tone={tested.ok ? "success" : "danger"}>
            <span>{tested.sentence}</span>
            {tested.server_key_captured && tested.server_key !== null && (
              <span className="block text-sm">
                {t("integrations.group.keySaved")}{" "}
                <span className="font-mono" data-server-key="">
                  {tested.server_key}
                </span>
              </span>
            )}
          </OutcomeCard>
        </div>
      )}

      {/* ── Send a day again — a person's deliberate act, with a reason ──── */}
      {view.data?.set_up && (
        <form
          className="mt-4 border-t border-divider pt-3"
          data-group-resend=""
          onSubmit={(event) => {
            event.preventDefault();
            setResent(null);
            setRefusal(null);
            resend.mutate();
          }}
        >
          <div className={ROW}>
            <label className="text-sm font-semibold" htmlFor="group-resend-day">
              {t("integrations.group.resendDay")}
            </label>
            <input
              id="group-resend-day"
              type="date"
              className="input w-full"
              value={resendDay}
              onChange={(event) => setResendDay(event.target.value)}
            />
          </div>
          <div className={ROW}>
            <label className="text-sm font-semibold" htmlFor="group-resend-reason">
              {t("integrations.group.resendReason")}
            </label>
            <input
              id="group-resend-reason"
              type="text"
              className="input w-full"
              value={resendReason}
              onChange={(event) => setResendReason(event.target.value)}
            />
          </div>
          <div className={ROW}>
            <div />
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="submit"
                variant="secondary"
                disabled={resend.isPending || resendDay === "" || resendReason.trim() === ""}
              >
                {t("integrations.group.resend")}
              </Button>
              {resent !== null && (
                <span
                  className={resent.done ? "text-sm text-success-700" : "text-sm text-danger-700"}
                  data-group-resent={resent.done ? "ok" : "refused"}
                >
                  {resent.sentence}
                </span>
              )}
            </div>
          </div>
        </form>
      )}
    </Panel>
  );
}
