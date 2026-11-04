/**
 * PlatformTextsPanel — texts PROVIDED BY THE PLATFORM, on S142 (`CR-198-BRC10`).
 *
 * PO 2026-10-29, ruling 4B: one shared platform Twilio account. A utility does
 * not connect it, so this panel replaces the connect story with three facts
 * and one act — the brief's own words: *"shows texts as provided by the
 * platform with status, last error and a Test send"*.
 *
 *   Status · Sender · Delivery reports · Last text · Last error   (FactBlock)
 *   Phone number [          ]  [Send test ✓]                       (one act)
 *
 * ⚠ **NO SECRET CAN REACH THIS COMPONENT** — `PlatformTexts` has no field that
 * could hold one; the sender is a masked tail. ⚠ No drawing exists for this
 * card; it is built from the ruling's sentence with the kit (`Panel`,
 * `FactBlock`, `TextField`, `Button`) and our UI standard (B14 rule 44).
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getPlatformTexts, sendPlatformTestText } from "@/api/integrationsEndpoints";
import type { PlatformTestResult, PlatformTexts } from "@/api/integrationsEndpoints";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import { TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { useRegional } from "@/features/metering/meteringShared";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** The Status fact: one word for ready, else the FIRST thing to fix. */
export function platformStatusText(state: PlatformTexts, t: Translate): string {
  if (state.configured) {
    return t("integrations.platformSms.status.ready");
  }
  const first = state.problems[0];
  return first === undefined
    ? t("integrations.platformSms.status.notSetUp")
    : t(`integrations.platformSms.problem.${first}`);
}

export function platformSenderText(state: PlatformTexts, t: Translate): string {
  if (state.sender_kind === null || state.sender_hint === null) {
    return "—";
  }
  return t(`integrations.platformSms.sender.${state.sender_kind}`, { hint: state.sender_hint });
}

export function PlatformTextsPanel(props: { providerKey: string; client: ApiClient; readOnly: boolean }) {
  const { t } = useTranslation();
  const { timeZone, dateFormat } = useRegional({});
  const [to, setTo] = useState("");
  const [result, setResult] = useState<PlatformTestResult | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const read = useQuery({
    queryKey: ["integrations", props.providerKey, "platform"],
    queryFn: () => getPlatformTexts(props.client, props.providerKey),
  });
  const test = useMutation({
    mutationFn: () => sendPlatformTestText(props.client, props.providerKey, to),
    onSuccess: (answer) => {
      setProblem(null);
      setResult(answer);
      void read.refetch();
    },
    onError: (error) => {
      setResult(null);
      setProblem(refusalText(t, error));
    },
  });

  if (read.isLoading) {
    return (
      <Panel title={t("integrations.platformSms.title")} data-platform-texts="loading">
        <p className="m-0 text-sm text-neutral-600">{t("integrations.platformSms.loading")}</p>
      </Panel>
    );
  }
  if (read.isError || read.data === undefined) {
    return (
      <Panel title={t("integrations.platformSms.title")} data-platform-texts="failed">
        <p className="m-0 text-sm text-danger-700" role="alert">
          {t("integrations.platformSms.readFailed")}
        </p>
      </Panel>
    );
  }
  const state = read.data;
  const when = (iso: string | null) => (iso === null ? "—" : formatDate(iso, timeZone, dateFormat, true));

  return (
    <Panel title={t("integrations.platformSms.title")} data-platform-texts={state.configured ? "ready" : "not_set_up"}>
      <div className="flex flex-col gap-4">
        <FactBlock
          name="platform-texts"
          facts={[
            { id: "status", label: t("integrations.platformSms.fact.status"), value: platformStatusText(state, t) },
            { id: "sender", label: t("integrations.platformSms.fact.sender"), value: platformSenderText(state, t) },
            {
              id: "reports",
              label: t("integrations.platformSms.fact.reports"),
              value: t(state.callbacks ? "integrations.platformSms.reports.on" : "integrations.platformSms.reports.off"),
            },
            { id: "lastSent", label: t("integrations.platformSms.fact.lastSent"), value: when(state.last_sent_at) },
            {
              id: "lastError",
              label: t("integrations.platformSms.fact.lastError"),
              value: state.last_error ?? t("integrations.platformSms.noError"),
            },
          ]}
        />
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            test.mutate();
          }}
        >
          <div className="w-64">
            <TextField
              id="platform-test-to"
              label={t("integrations.platformSms.testTo")}
              value={to}
              onChange={setTo}
              disabled={props.readOnly}
            />
          </div>
          <Button
            type="submit"
            variant="primary"
            disabled={props.readOnly || test.isPending || to.trim() === ""}
            title={props.readOnly ? t("settings.readOnlyReason") : undefined}
            data-testid="platform-test-send"
          >
            {t("integrations.platformSms.sendTest")}
          </Button>
        </form>
        {result !== null && (
          <p
            className={`m-0 text-sm ${result.ok ? "text-success-700" : "text-danger-700"}`}
            role="status"
            data-platform-test={result.ok ? "ok" : "failed"}
          >
            {result.sentence_key !== undefined ? t(result.sentence_key) : result.sentence}
            {result.provider_text !== null && !result.ok && (
              <span className="block text-neutral-600">{result.provider_text}</span>
            )}
          </p>
        )}
        {problem !== null && (
          <p className="m-0 text-sm text-danger-700" role="alert">
            {problem}
          </p>
        )}
      </div>
    </Panel>
  );
}
