// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 11: Settings → Reads → Read formats,
//           the LIST, the *New format* dialog and the *Defaults by service*
//           panel. PO, verbatim: *"3. Settings → Reads; The template is chosen
//           automatically: route → cycle → service … we can set it once or we
//           can create another format for same service and replace it later"*,
//           and *"this is all user defined we dont have to provide anything
//           readymade"*.
// Rules:    BR-MET-1210 (nothing seeded — the empty state is the first thing a
//           utility sees) · BR-MET-1212 (a service default names a PUBLISHED
//           format) · NFR-3 (paged, filtered and searched by the server) · B14
//           rule 2 (one page header) · rule 15 (row actions are icons, two
//           visible) · rule 20 (one table type) · rule 21 (Tailwind; on
//           route-b-migrated.txt) · rule 31 (no database id is a visible
//           value) · rule 33 (copy caps; no rationale on screen)
// Tests:    src/features/metering/readFormats.dom.test.tsx
// Impacts:  App.tsx (route) · routing/screenIds.ts (SET-04.readFormats) ·
//           tenancy/referenceDataConfig.ts (the READS card that opens this)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS SCREEN HAS NO DRAWING.** MQ-033 was ruled on 2026-10-24 in chat and
// no blueprint page or r10 frame exists for it; the layout is the task's own
// (columns Name · Service · Status · Version · Used by · Updated) built from
// the kit, exactly as `LabourRatesPage` — the other Settings reference card
// that opens a screen of its own — is built. Reported to the coordinator.
//
// ⚠ **WHERE IT SITS.** *"Settings → Reads"* is the READS heading of Settings →
// Configure → Reference data (r10 SET-04 files cards under module headings;
// `read_methods` and `read_validation` already sit there). The card is a
// `kind: "link"` to this address, which is `BR-TEN-033`'s precedent for a card
// whose body is a screen with its own table.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { EyeIcon, RetireIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { RefusalNotice } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { ReadFormatSelect } from "./ReadFormatPointer";
import {
  createReadFormat,
  getServiceDefaults,
  listReadFormats,
  readFormatKeys,
  retireReadFormat,
  setServiceDefault,
} from "./readFormatsEndpoints";
import type { ReadFormatRow, ReadFormatStatus, ServiceDefaultRow, UsedBy } from "./readFormatsEndpoints";
import { readFormatRefusal } from "./readFormatsShared";

/** The badge: r10 builds a reference-card sub-id as `'SET-04.' + list`. */
export const READ_FORMATS_SCREEN = "SET-04.readFormats";

/** No `:tenant` segment — `App.tsx` registers `ROUTE.slice(1)` under one
 *  (`LabourRatesPage`'s `DEF-WRK-4051` note says why). */
export const READ_FORMATS_ROUTE = "/settings/reference-data/read-formats";
export const READ_FORMAT_DETAIL_ROUTE = "/settings/reference-data/read-formats/:formatId";

export function readFormatDetailPath(formatId: string): string {
  return `${READ_FORMATS_ROUTE}/${formatId}`;
}

/** The Configure grid this screen's card sits in. */
const REFERENCE_DATA_PATH = "/settings/reference-data";

type Translate = (key: string, params?: Record<string, unknown>) => string;

export function statusTone(status: ReadFormatStatus): StatusTone {
  if (status === "published") {
    return "success";
  }
  if (status === "draft") {
    return "warning";
  }
  return "muted";
}

/** *Routes 2 · Cycles 1 · Services 0* — or *Not used* when every count is 0. */
export function usedByText(used: UsedBy, t: Translate): string {
  if (used.routes === 0 && used.cycles === 0 && used.services === 0) {
    return t("settings.readFormats.notUsed");
  }
  return t("settings.readFormats.usedBy", { ...used });
}

/** The service filter's name. NOT `service`: that name is a MULTI-select in
 *  the kit (`MULTI_SELECT_FILTER_NAMES`) and this server takes one code. */
const SERVICE_FILTER = "for_service";
const STATUSES: readonly ReadFormatStatus[] = ["draft", "published", "retired"];

export function readFormatsTableConfig(
  t: Translate,
  services: readonly ServiceDefaultRow[],
  cells: {
    name: (row: ReadFormatRow) => React.ReactNode;
    updated: (row: ReadFormatRow) => React.ReactNode;
    actions: (row: ReadFormatRow) => React.ReactNode;
  },
): TableConfig<ReadFormatRow> {
  return {
    screenId: READ_FORMATS_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["name"],
    searchPlaceholder: "settings.readFormats.search",
    filters: [
      {
        name: SERVICE_FILTER,
        label: t("settings.readFormats.col.service"),
        options: services.map((row) => ({ value: row.service.code, label: row.service.name })),
      },
      {
        name: "status",
        label: t("settings.readFormats.col.status"),
        options: STATUSES.map((code) => ({ value: code, label: t(`settings.readFormats.status.${code}`) })),
      },
    ],
    // The server orders newest edit first and sorts by nothing else, so no
    // header offers a sort it would not honour (law 2's mirror).
    defaultSort: { sort: "updated_at", dir: "desc" },
    columns: [
      { key: "name", label: t("settings.readFormats.col.name"), identity: true, cell: cells.name },
      {
        key: "service",
        label: t("settings.readFormats.col.service"),
        cell: (row) => <span>{row.service.name}</span>,
      },
      {
        key: "status",
        label: t("settings.readFormats.col.status"),
        cell: (row) => (
          <StatusPill tone={statusTone(row.status)}>
            {t(`settings.readFormats.status.${row.status}`)}
          </StatusPill>
        ),
      },
      {
        key: "version",
        label: t("settings.readFormats.col.version"),
        cell: (row) =>
          row.current_version === null ? (
            row.draft_version_id === null ? (
              <Dash />
            ) : (
              <span>{t("settings.readFormats.draftOnly")}</span>
            )
          ) : (
            <span className="tabular-nums">
              {t(
                row.draft_version_id === null
                  ? "settings.readFormats.versionNo"
                  : "settings.readFormats.versionWithDraft",
                { n: row.current_version.version_no },
              )}
            </span>
          ),
      },
      {
        key: "used_by",
        label: t("settings.readFormats.col.usedBy"),
        cell: (row) => <span>{usedByText(row.used_by, t)}</span>,
      },
      { key: "updated_at", label: t("settings.readFormats.col.updated"), cell: cells.updated },
      { key: "actions", label: t("settings.reference.col.actions"), cell: cells.actions },
    ],
  };
}

export interface ReadFormatsPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function ReadFormatsPage(props: ReadFormatsPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const { timeZone, dateFormat } = useRegional(props);
  const translate: Translate = (key, params) => t(key, params);

  const [creating, setCreating] = useState(false);
  const [retiring, setRetiring] = useState<ReadFormatRow | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const servicesQuery = useQuery({
    queryKey: readFormatKeys.defaults,
    queryFn: () => getServiceDefaults(client),
  });
  const services = useMemo(() => servicesQuery.data ?? [], [servicesQuery.data]);

  const config = useMemo(
    () =>
      readFormatsTableConfig(translate, services, {
        name: (row) => (
          <Link className="text-accent underline" to={tenantPath(readFormatDetailPath(row.id))}>
            {row.name}
          </Link>
        ),
        updated: (row) =>
          row.updated_at === null ? (
            <Dash />
          ) : (
            <DateCell value={row.updated_at} timeZone={timeZone} dateFormat={dateFormat} />
          ),
        actions: (row) => (
          <RowActions>
            <RowAction
              label={t("settings.readFormats.action.open", { name: row.name })}
              icon={<EyeIcon />}
              onClick={() => navigate(tenantPath(readFormatDetailPath(row.id)))}
            />
            <RowAction
              label={t("settings.readFormats.action.retire")}
              icon={<RetireIcon />}
              danger
              reason={
                row.status === "published" ? null : t(`settings.readFormats.cannotRetire.${row.status}`)
              }
              onClick={() => {
                setRefusal(null);
                setRetiring(row);
              }}
            />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, services, timeZone, dateFormat, tenantPath],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const listQuery = {
    service: state.filters[SERVICE_FILTER] ?? "",
    status: state.filters.status ?? "",
    q: state.q,
    page: state.page,
    per: state.per,
  };
  const query = useQuery({
    queryKey: readFormatKeys.list(listQuery),
    queryFn: () => listReadFormats(listQuery, client),
  });

  const retireMutation = useMutation({
    mutationFn: (row: ReadFormatRow) => retireReadFormat(row.id, client),
    onSuccess: () => {
      setRetiring(null);
      fireToast(t("settings.readFormats.retire.done"));
      void queryClient.invalidateQueries({ queryKey: readFormatKeys.all });
    },
    onError: (error) => {
      setRetiring(null);
      setRefusal(readFormatRefusal(error, t));
    },
  });

  const newButton = (
    <Button variant="primary" onClick={() => setCreating(true)}>
      {t("settings.readFormats.new")}
    </Button>
  );

  return (
    <section aria-label={t("settings.readFormats.title")} className="flex flex-col gap-4">
      <PageHeader
        backTo={{ to: tenantPath(REFERENCE_DATA_PATH), label: t("settings.configure.subTab.referenceData") }}
        kicker={t("settings.readFormats.kicker")}
        title={t("settings.readFormats.title")}
        rollup={t("settings.readFormats.description")}
        primaryAction={newButton}
      />

      <RefusalNotice refusal={refusal} />

      <DataTable<ReadFormatRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        filterBarSlot={
          <FilterBar filters={offerableFilters(config.filters ?? [])} state={state} onStateChange={setState} />
        }
        error={
          query.isError
            ? { reason: t("settings.readFormats.loadFailed"), onRetry: () => void query.refetch() }
            : null
        }
        empty={{
          title: t("settings.readFormats.empty.title"),
          helper: t("settings.readFormats.empty.helper"),
          ctaLabel: t("settings.readFormats.new"),
          ctaVariant: "secondary",
          onCta: () => setCreating(true),
        }}
      />

      <ServiceDefaultsPanel rows={services} loading={servicesQuery.isPending} client={client} />

      {creating && (
        <NewReadFormatDialog
          services={services}
          client={client}
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setCreating(false);
            void queryClient.invalidateQueries({ queryKey: readFormatKeys.all });
            navigate(tenantPath(readFormatDetailPath(id)));
          }}
        />
      )}

      {retiring !== null && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("settings.readFormats.retire.title", { name: retiring.name })}
          consequence={t("settings.readFormats.retire.consequence")}
          confirmLabel={t("settings.readFormats.retire.confirm")}
          working={retireMutation.isPending}
          onConfirm={() => retireMutation.mutate(retiring)}
          onCancel={() => setRetiring(null)}
        />
      )}
    </section>
  );
}

/** *Defaults by service* — one row per ENABLED service, a published format of
 *  that service or none. The pick saves at once; a refusal stays on the row. */
export function ServiceDefaultsPanel(props: {
  rows: readonly ServiceDefaultRow[];
  loading: boolean;
  client: ApiClient;
}) {
  const { t } = useTranslation();
  return (
    <Panel as="section" title={t("settings.readFormats.defaults.title")} data-read-format="defaults">
      {props.loading ? null : (
        <div className="flex flex-col gap-3">
          {props.rows.map((row) => (
            <ServiceDefaultRowView key={row.service.code} row={row} client={props.client} />
          ))}
        </div>
      )}
    </Panel>
  );
}

function ServiceDefaultRowView(props: { row: ServiceDefaultRow; client: ApiClient }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const { row } = props;
  const mutation = useMutation({
    mutationFn: (id: string | null) => setServiceDefault(row.service.code, id, props.client),
    onSuccess: (rows) => {
      setRefusal(null);
      queryClient.setQueryData(readFormatKeys.defaults, rows);
      void queryClient.invalidateQueries({ queryKey: readFormatKeys.all });
      fireToast(t("settings.readFormats.pointer.saved"));
    },
    onError: (error) => setRefusal(readFormatRefusal(error, t)),
  });
  return (
    <div className="grid items-center gap-2 sm:grid-cols-3" data-service={row.service.code}>
      <span className="font-semibold">{row.service.name}</span>
      <div className="sm:col-span-2">
        <ReadFormatSelect
          id={`default-${row.service.code}`}
          label={t("settings.readFormats.defaults.label", { service: row.service.name })}
          labelHidden
          value={row.read_format?.id ?? ""}
          onChange={(value) => mutation.mutate(value === "" ? null : value)}
          service={row.service.code}
          current={row.read_format}
          disabled={mutation.isPending}
          client={props.client}
        />
        <RefusalNotice refusal={refusal} />
      </div>
    </div>
  );
}

/** *New format* — a name and a service; it opens the builder on an empty draft. */
export function NewReadFormatDialog(props: {
  services: readonly ServiceDefaultRow[];
  client: ApiClient;
  onClose: () => void;
  onCreated: (formatId: string) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [service, setService] = useState("");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const created = await createReadFormat({ name: name.trim(), service }, props.client);
      props.onCreated(created.id);
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
      title={t("settings.readFormats.create.title")}
      schema={z.object({
        name: z.string().trim().min(1, t("settings.readFormats.create.nameRequired")),
        service: z.string().min(1, t("settings.readFormats.create.serviceRequired")),
      })}
      values={{ name, service }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("settings.readFormats.create.submit")}
    >
      <TextField id="name" label={t("settings.readFormats.col.name")} value={name} onChange={setName} required />
      <SelectField
        id="service"
        label={t("settings.readFormats.col.service")}
        value={service}
        onChange={setService}
        required
        placeholder={t("settings.readFormats.create.pickService")}
        options={props.services.map((row) => ({ value: row.service.code, label: row.service.name }))}
      />
    </FormModal>
  );
}
