// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 11: the three POINTERS a read format is
//           chosen by — route → cycle → service (PO, verbatim: *"The template
//           is chosen automatically: route → cycle → service. A route can
//           override its cycle, and a cycle its service"*).
// Rules:    BR-MET-1212 (only a PUBLISHED format is pointed at; replacing =
//           moving a pointer) · B14 rule 31 (a format shows its NAME) · B14
//           rule 33 (labels ≤ 3 words, facts ≤ 6, no rationale) · B14 rule 43
//           (one component per piece, imported by every screen that shows it)
// Tests:    src/features/metering/readFormats.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// FOUR PIECES, AND EVERY SCREEN THAT POINTS AT A FORMAT IMPORTS THEM:
//
//   · `ReadFormatSelect` — the one dropdown of PUBLISHED formats (of a service,
//     or of every service where the target has none — a cycle).
//   · `CycleReadFormatPanel` — the Settings cycle page's *Read format* field.
//   · `RouteReadFormatPanel` — the Settings route page's field, and the
//     RESOLVED answer per service with where it came from.
//   · `RoutesReadFormatDialog` — one move for many routes (Settings → Routes).
//
// ⚠ **THE PICKER READS ONE PAGE OF 200.** The server refuses nothing about
// count (NFR-5) and a utility keeps a handful of formats per service; a picker
// over a paged list is the shape the template pickers in this product already
// take (`NewConnectUnitsStep`, `BuildRaiseOrderDialog`). A tenant with more
// than 200 published formats of one service would see the first 200 by most
// recent edit — stated here rather than hidden (hard-won law 1).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { useToast } from "@/components/Toast";
import { RefusalNotice, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";

import {
  getCycleReadFormat,
  getRouteReadFormat,
  getServiceDefaults,
  listReadFormats,
  readFormatKeys,
  setCycleReadFormat,
  setRoutesReadFormat,
} from "./readFormatsEndpoints";
import type { FormatSource, ReadFormatRow } from "./readFormatsEndpoints";

/** The picker's one page — see the file header. */
export const PICKER_PER = 200;

/** `""` in a select is "no format" — the pointer cleared, never a format id. */
const NONE = "";

/** The published formats a pointer may name, of `service` (null = every one). */
export function usePublishedFormats(service: string | null, client: ApiClient) {
  return useQuery({
    queryKey: readFormatKeys.published(service),
    queryFn: () =>
      listReadFormats(
        { status: "published", service: service ?? undefined, page: 1, per: PICKER_PER },
        client,
      ),
  });
}

/** The option's words: the name, and the service where several are offered. */
export function formatOptionLabel(row: ReadFormatRow, withService: boolean): string {
  return withService ? `${row.name} · ${row.service.name}` : row.name;
}

/**
 * The one dropdown. `current` keeps a pointer that is no longer offerable
 * (retired since, or beyond the first page) visible by NAME rather than
 * silently showing *No format* over a pointer that is set.
 */
export function ReadFormatSelect(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Null = formats of every service (a cycle carries no service). */
  service: string | null;
  current?: { id: string; name: string } | null;
  disabled?: boolean;
  labelHidden?: boolean;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const formats = usePublishedFormats(props.service, client);
  const rows = formats.data?.rows ?? [];
  const options = [
    { value: NONE, label: t("settings.readFormats.pointer.none") },
    ...rows.map((row) => ({ value: row.id, label: formatOptionLabel(row, props.service === null) })),
  ];
  if (
    props.current !== undefined &&
    props.current !== null &&
    !rows.some((row) => row.id === props.current?.id)
  ) {
    options.push({ value: props.current.id, label: props.current.name });
  }
  return (
    <SelectField
      id={props.id}
      label={props.label}
      value={props.value}
      onChange={props.onChange}
      options={options}
      labelHidden={props.labelHidden}
      disabled={props.disabled}
      help={props.disabled === true ? t("settings.readOnlyReason") : undefined}
    />
  );
}

/** The words for where a route's format came from (B14 rule 33: a fact). */
export function sourceKey(source: FormatSource): string {
  return source === null
    ? "settings.readFormats.source.none"
    : `settings.readFormats.source.${source}`;
}

/** Shared: a picker, a Save, and the refusal under them. */
function PointerEditor(props: {
  id: string;
  service: string | null;
  current: { id: string; name: string } | null;
  readOnly: boolean;
  client: ApiClient;
  save: (readFormatId: string | null) => Promise<unknown>;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const [value, setValue] = useState<string>(props.current?.id ?? NONE);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const mutation = useMutation({
    mutationFn: () => props.save(value === NONE ? null : value),
    onSuccess: () => {
      setRefusal(null);
      fireToast(t("settings.readFormats.pointer.saved"));
      props.onSaved();
    },
    onError: (error) => setRefusal(refusalOf(error, t)),
  });
  const unchanged = value === (props.current?.id ?? NONE);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-64 flex-1">
          <ReadFormatSelect
            id={props.id}
            label={t("settings.readFormats.pointer.title")}
            // The panel's own heading already says *Read format*; drawing it
            // twice is a label with nothing to add (B14 rule 33).
            labelHidden
            value={value}
            onChange={setValue}
            service={props.service}
            current={props.current}
            disabled={props.readOnly}
            client={props.client}
          />
        </div>
        <Button
          variant="secondary"
          disabled={props.readOnly || unchanged || mutation.isPending}
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => mutation.mutate()}
        >
          {t("settings.readFormats.pointer.save")}
        </Button>
      </div>
      <RefusalNotice refusal={refusal} />
    </div>
  );
}

/** The Settings cycle page's *Read format* — the cycle's own pointer. */
export function CycleReadFormatPanel(props: {
  cycleId: string;
  readOnly: boolean;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: readFormatKeys.cycle(props.cycleId),
    queryFn: () => getCycleReadFormat(props.cycleId, client),
  });
  return (
    <Panel as="section" title={t("settings.readFormats.pointer.title")} data-read-format="cycle">
      {query.data === undefined ? (
        query.isError ? (
          <RefusalNotice refusal={refusalOf(query.error, t)} />
        ) : null
      ) : (
        <PointerEditor
          // Re-keyed on the stored answer so a save elsewhere re-seeds the picker.
          key={query.data.read_format?.id ?? "none"}
          id="cycle-read-format"
          service={null}
          current={query.data.read_format}
          readOnly={props.readOnly}
          client={client}
          save={(id) => setCycleReadFormat(props.cycleId, id, client)}
          onSaved={() => void queryClient.invalidateQueries({ queryKey: readFormatKeys.all })}
        />
      )}
    </Panel>
  );
}

/**
 * The Settings route page's *Read format*: the route's OWN pointer, and under
 * it what each of the route's services actually resolves to and from where
 * (`GET routes/{id}/read-format`).
 */
export function RouteReadFormatPanel(props: {
  routeId: string;
  /** The route's head service — the picker offers that service's formats. */
  service: string | null;
  readOnly: boolean;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: readFormatKeys.route(props.routeId),
    queryFn: () => getRouteReadFormat(props.routeId, client),
  });
  // B14 rule 31 — the resolution names a service by CODE; the screen shows
  // the catalogue's NAME, read from the same per-service list the defaults
  // panel draws.
  const services = useQuery({
    queryKey: readFormatKeys.defaults,
    queryFn: () => getServiceDefaults(client),
  });
  const serviceName = (code: string): string =>
    services.data?.find((row) => row.service.code === code)?.service.name ?? "";
  const resolution = query.data;
  const own =
    resolution?.route_read_format_id == null
      ? null
      : (resolution.results.find(
          (row) => row.read_format?.id === resolution.route_read_format_id,
        )?.read_format ?? {
          id: resolution.route_read_format_id,
          name: t(sourceKey("route")),
        });
  return (
    <Panel as="section" title={t("settings.readFormats.pointer.title")} data-read-format="route">
      {resolution === undefined ? (
        query.isError ? (
          <RefusalNotice refusal={refusalOf(query.error, t)} />
        ) : null
      ) : (
        <div className="flex flex-col gap-3">
          <PointerEditor
            key={resolution.route_read_format_id ?? "none"}
            id="route-read-format"
            service={props.service}
            current={own === null ? null : { id: own.id, name: own.name }}
            readOnly={props.readOnly}
            client={client}
            save={(id) => setRoutesReadFormat([props.routeId], id, client)}
            onSaved={() => void queryClient.invalidateQueries({ queryKey: readFormatKeys.all })}
          />
          <ul className="m-0 flex list-none flex-col gap-1 p-0" aria-label={t("settings.readFormats.resolved")}>
            {resolution.results.map((row) => (
              <li key={row.service} className="text-base" data-source={row.source ?? "none"}>
                <b>{serviceName(row.service)}</b>{" "}
                {/* The format's own NAME and where it came from, joined by the
                    product's separator — no sentence, so no catalogue key. */}
                {row.read_format === null
                  ? t(sourceKey(null))
                  : `${row.read_format.name} · ${t(sourceKey(row.source))}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}

/** One move for many routes — Settings → Routes' selection bar opens it. */
export function RoutesReadFormatDialog(props: {
  routeIds: string[];
  /** The selection's services; one shared service narrows the picker to it. */
  services: string[];
  onClose: () => void;
  onDone: (updated: number) => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [value, setValue] = useState<string>(NONE);
  const service = props.services.length === 1 ? (props.services[0] ?? null) : null;

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const answer = await setRoutesReadFormat(props.routeIds, value === NONE ? null : value, client);
      props.onDone(answer.updated);
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
      title={t("settings.readFormats.bulk.title")}
      schema={z.object({ read_format_id: z.string() })}
      values={{ read_format_id: value }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("settings.readFormats.bulk.submit")}
    >
      <ReadFormatSelect
        id="read_format_id"
        label={t("settings.readFormats.pointer.title")}
        value={value}
        onChange={setValue}
        service={service}
        client={client}
      />
    </FormModal>
  );
}
