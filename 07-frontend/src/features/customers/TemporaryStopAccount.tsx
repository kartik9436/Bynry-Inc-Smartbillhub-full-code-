// ── Trace ──────────────────────────────────────────────
// Change:   CR-183-BRC10 T7 — a clerk starts a temporary stop from the account
//           page (a customer on the phone or at the counter), moves its dates,
//           or ends it today (PO rulings B1–B4, 2026-10-14).
// Rules:    BR-CUS-1120 · BR-CUS-1121 (the SERVER refuses outside the limits;
//           this window prints the figures it was given and checks nothing) ·
//           B14 rule 43 (one component file, mounted twice by the account page:
//           the status strip and the window) · rules 36/38/44 (the kit) ·
//           rule 31 (no id on screen) · rule 33 (labels ≤ 3 words, facts ≤ 6)
// Tests:    src/features/customers/TemporaryStopAccount.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { CheckboxField, DatePickerField, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import {
  changeTemporaryStop,
  endTemporaryStop,
  getAccountTemporaryStop,
  startTemporaryStop,
} from "./temporaryStopEndpoints";
import type { AccountTemporaryStop, TemporaryStopView } from "./temporaryStopEndpoints";

const NS = "customers.temporaryStop";
const SCHEMA = z.object({});

export function temporaryStopQueryKey(accountId: string): readonly unknown[] {
  return ["customers", "accounts", accountId, "temporary-stop"];
}

export function useAccountTemporaryStop(accountId: string, client: ApiClient = api) {
  return useQuery<AccountTemporaryStop>({
    queryKey: temporaryStopQueryKey(accountId),
    queryFn: () => getAccountTemporaryStop(accountId, client),
  });
}

async function outcomeOf(action: () => Promise<unknown>): Promise<FormSubmitOutcome> {
  try {
    await action();
    return { ok: true };
  } catch (error) {
    if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
    return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
  }
}

/** The one line under the account head while a stop is scheduled or on. */
export function TemporaryStopStrip(props: {
  accountId: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const query = useAccountTemporaryStop(props.accountId, props.client);
  const current = query.data?.current ?? null;
  if (current === null) return null;
  const date = (value: string) => formatDate(value, props.timeZone, props.dateFormat);
  return (
    <p
      className="mt-4 mb-0 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-divider px-3 py-2 text-md"
      data-temporary-stop-strip={current.status}
    >
      <span className="font-semibold">
        {current.status === "on_hold"
          ? t(`${NS}.strip.onHold`, {
              from: date(current.stop_from),
              to: current.restart_on === null ? "" : date(current.restart_on),
            })
          : t(`${NS}.strip.scheduled`, {
              from: date(current.stop_from),
              to: current.restart_on === null ? "" : date(current.restart_on),
            })}
      </span>
      <span className="text-neutral-700">{t(`${NS}.fact.baseOnly`)}</span>
      {current.shutoff_order_no !== null && (
        <span className="text-neutral-700">
          {t(`${NS}.strip.visits`, {
            shutoff: current.shutoff_order_no,
            turnon: current.turnon_order_no ?? "",
          })}
        </span>
      )}
    </p>
  );
}

/** The window: start a stop when none is live; change or end the live one. */
export function TemporaryStopModal(props: {
  accountId: string;
  accountLabel: string;
  today: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const query = useAccountTemporaryStop(props.accountId, props.client);
  if (query.data === undefined) return null;
  const current = query.data.current;
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: temporaryStopQueryKey(props.accountId) });
  return current === null ? (
    <StartStopForm {...props} limits={query.data.limits} refresh={refresh} t={t} />
  ) : (
    <ChangeStopForm {...props} current={current} refresh={refresh} t={t} />
  );
}

type FormProps = Parameters<typeof TemporaryStopModal>[0] & {
  refresh: () => Promise<unknown>;
  t: (key: string, params?: Record<string, unknown>) => string;
};

function StartStopForm(props: FormProps & { limits: AccountTemporaryStop["limits"] }) {
  const { t } = props;
  const [stopFrom, setStopFrom] = useState(props.today);
  const [restartOn, setRestartOn] = useState("");
  const [reason, setReason] = useState("");
  const [fieldVisit, setFieldVisit] = useState(false);
  const date = (value: string) => formatDate(value, props.timeZone, props.dateFormat);
  return (
    <FormModal
      title={t(`${NS}.start.title`)}
      kicker={props.accountLabel}
      schema={SCHEMA}
      values={{}}
      submitLabel={t(`${NS}.start.submit`)}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await outcomeOf(() =>
          startTemporaryStop(
            props.accountId,
            {
              stop_from: stopFrom,
              restart_on: restartOn,
              ...(reason.trim() !== "" ? { reason: reason.trim() } : {}),
              field_visit_needed: fieldVisit,
            },
            props.client,
          ),
        );
        if (outcome.ok) {
          await props.refresh();
          props.onDone(t(`${NS}.toast.started`));
        }
        return outcome;
      }}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <DatePickerField
          id="temporary-stop-start-from"
          label={t(`${NS}.field.stopFrom`)}
          value={stopFrom}
          onChange={setStopFrom}
          dateFormat={props.dateFormat}
          min={props.today}
          required
        />
        <DatePickerField
          id="temporary-stop-start-restart"
          label={t(`${NS}.field.restartOn`)}
          value={restartOn}
          onChange={setRestartOn}
          dateFormat={props.dateFormat}
          required
        />
      </div>
      <p className="m-0 text-sm text-neutral-700" data-temporary-stop-limits="">
        {t(`${NS}.fact.limits`, { min: props.limits.min_days, max: props.limits.max_months })}
      </p>
      <TextField
        id="temporary-stop-start-reason"
        label={t(`${NS}.field.reason`)}
        value={reason}
        onChange={setReason}
      />
      <CheckboxField
        id="temporary-stop-start-visit"
        label={t(`${NS}.field.fieldVisit`)}
        checked={fieldVisit}
        onChange={setFieldVisit}
      />
      <ConsequenceBox
        tone="check"
        title={t(`${NS}.consequence.title`)}
        body={t(`${NS}.consequence.body`, { date: stopFrom === "" ? "" : date(stopFrom) })}
        data-consequence="temporary-stop-start"
      />
    </FormModal>
  );
}

function ChangeStopForm(props: FormProps & { current: TemporaryStopView }) {
  const { t, current } = props;
  const started = current.status === "on_hold";
  const [stopFrom, setStopFrom] = useState(current.stop_from);
  const [restartOn, setRestartOn] = useState(current.restart_on ?? "");
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState<string | null>(null);
  return (
    <FormModal
      title={t(`${NS}.change.title`)}
      kicker={props.accountLabel}
      schema={SCHEMA}
      values={{}}
      submitLabel={t(`${NS}.change.submit`)}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await outcomeOf(() =>
          changeTemporaryStop(
            current.id,
            started ? { restart_on: restartOn } : { stop_from: stopFrom, restart_on: restartOn },
            props.client,
          ),
        );
        if (outcome.ok) {
          await props.refresh();
          props.onDone(t(`${NS}.toast.changed`));
        }
        return outcome;
      }}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <DatePickerField
          id="temporary-stop-change-from"
          label={t(`${NS}.field.stopFrom`)}
          value={stopFrom}
          onChange={setStopFrom}
          dateFormat={props.dateFormat}
          disabled={started}
          required
        />
        <DatePickerField
          id="temporary-stop-change-restart"
          label={t(`${NS}.field.restartOn`)}
          value={restartOn}
          onChange={setRestartOn}
          dateFormat={props.dateFormat}
          required
        />
      </div>
      <div className="flex flex-wrap items-center gap-3" data-temporary-stop-end="">
        <Button
          variant="danger"
          size="sm"
          disabled={ending}
          onClick={() => {
            setEnding(true);
            setEndError(null);
            void endTemporaryStop(current.id, props.client)
              .then(async () => {
                await props.refresh();
                props.onDone(t(`${NS}.toast.ended`));
              })
              .catch((error: unknown) => {
                setEndError(
                  isApiError(error) ? t(error.messageKey) : t("api.error.unexpected"),
                );
              })
              .finally(() => setEnding(false));
          }}
        >
          {t(`${NS}.change.endNow`)}
        </Button>
        <span className="text-sm text-neutral-700">
          {t(started ? `${NS}.change.endFacts` : `${NS}.change.cancelFacts`)}
        </span>
      </div>
      {endError !== null && (
        <p className="m-0 text-sm text-danger-700" role="alert">
          {endError}
        </p>
      )}
    </FormModal>
  );
}
