// ── Trace ──────────────────────────────────────────────
// Change:   CR-187-BRC10 — PO answer 9 of 2026-10-21, as CORRECTED the same day:
//           an automatic urgent / emergency push is an OPTION. Seeded OFF.
// Screen:   Settings → Reference data → Work priorities (the card whose rows
//           carry each priority's push kind)
// Endpoint: GET · POST /work/settings/push {push_by_priority}
// Rules:    B14 rule 43 (a piece of UI is a component) · rule 33 (a label is
//           ≤ 3 words; rationale is zero words on screen) · BR-SHL-025 (a
//           control that cannot be used says why)
// ───────────────────────────────────────────────────────
//
// ONE switch above the priorities table. ON: an assignment rings as its
// priority's push kind (the "Phone alert" column). OFF: every assignment rings
// as a new job and only a dispatcher's explicit choice sends urgent or
// emergency. The server owns the rule and the gate (System Admin writes);
// this draws the answer it serves and nothing else.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { Switch } from "@/components/Switch";

export interface PushSettings {
  push_by_priority: boolean;
}

export const PUSH_SETTINGS_KEY = ["work", "settings", "push"] as const;

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export async function fetchPushSettings(client: ApiClient = api): Promise<PushSettings> {
  return requireData(await client.get<PushSettings>("/work/settings/push"));
}

export async function savePushSettings(
  value: boolean,
  client: ApiClient = api,
): Promise<PushSettings> {
  return requireData(
    await client.post<PushSettings>("/work/settings/push", { push_by_priority: value }),
  );
}

export function PushByPriorityToggle(props: { readOnly: boolean; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: PUSH_SETTINGS_KEY,
    queryFn: () => fetchPushSettings(client),
    retry: false,
  });
  const save = useMutation({
    mutationFn: (value: boolean) => savePushSettings(value, client),
    onSuccess: (answer) => queryClient.setQueryData(PUSH_SETTINGS_KEY, answer),
  });
  if (query.data === undefined) {
    return null;
  }
  const on = save.isPending ? save.variables === true : query.data.push_by_priority;
  return (
    <div className="settings-frame-toolbar" data-push-by-priority={on ? "on" : "off"}>
      <span id="push-by-priority-label">{t("settings.reference.pushByPriority.label")}</span>
      <Switch
        on={on}
        label={t("settings.reference.pushByPriority.label")}
        onLabel={t("settings.reference.pushByPriority.on")}
        offLabel={t("settings.reference.pushByPriority.off")}
        disabled={save.isPending}
        reason={props.readOnly ? t("settings.readOnlyReason") : null}
        onChange={(next) => save.mutate(next)}
        testKey="push_by_priority"
      />
    </div>
  );
}
