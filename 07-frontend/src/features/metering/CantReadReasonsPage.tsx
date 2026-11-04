// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10609 — no screen managed the can't-read reasons.
// Ruling:   decision log 2026-10-26 — PO, verbatim: *"yes do it"*, to ONE list
//           of can't-read reasons for route readings AND job readings, managed
//           in Settings → Configure → Reference data → Readings next to Read
//           formats; the utility adds, renames and reorders; a starting reason
//           is switched off, never deleted; an own reason is deleted only if
//           never used, otherwise switched off.
// Rules:    NFR-3 (paged, searched and filtered by the server) · BR-SHL-025 (a
//           control that cannot act is disabled WITH its reason) · B14 rules 2
//           (one page header), 15 (row actions are icons, two visible, then
//           `…`), 20 (one table type), 21 (Tailwind; on route-b-migrated.txt),
//           31 (a reason's code is never drawn), 33 (copy caps) and 43 (built
//           as components)
// Tests:    src/features/metering/cantReadReasons.dom.test.tsx
// Impacts:  App.tsx (route) · routing/screenIds.ts (SET-04.cantReadReasons) ·
//           tenancy/referenceDataConfig.ts (the READS card that opens this)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS SCREEN HAS NO DRAWING.** It was ruled in chat on 2026-10-26 and no
// blueprint page or r10 frame exists for it; it is built from the kit exactly
// as its neighbour `ReadFormatsPage` is (the other READS card that opens a
// screen of its own): Name · Type · Status · Used · Actions.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { ChevronDownIcon, ChevronUpIcon, PencilIcon, PowerIcon, TrashIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { RefusalNotice, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  addCantReadReason,
  cantReadReasonKeys,
  deleteCantReadReason,
  listCantReadReasons,
  moveCantReadReason,
  updateCantReadReason,
} from "./cantReadReasonsEndpoints";
import type { CantReadReasonRow } from "./cantReadReasonsEndpoints";

/** The badge: r10 builds a reference-card sub-id as `'SET-04.' + list`. */
export const CANT_READ_REASONS_SCREEN = "SET-04.cantReadReasons";

/** No `:tenant` segment — `App.tsx` registers `ROUTE.slice(1)` under one. */
export const CANT_READ_REASONS_ROUTE = "/settings/reference-data/cant-read-reasons";

const REFERENCE_DATA_PATH = "/settings/reference-data";

type Translate = (key: string, params?: Record<string, unknown>) => string;

const STATUSES = ["active", "inactive"] as const;

export function cantReadReasonsTableConfig(
  t: Translate,
  actions: (row: CantReadReasonRow) => React.ReactNode,
): TableConfig<CantReadReasonRow> {
  return {
    screenId: CANT_READ_REASONS_SCREEN,
    getRowId: (row) => row.code,
    searchFields: ["name"],
    searchPlaceholder: "settings.cantReadReasons.search",
    filters: [
      {
        name: "status",
        label: t("settings.cantReadReasons.col.status"),
        options: STATUSES.map((code) => ({ value: code, label: t(`settings.cantReadReasons.status.${code}`) })),
      },
    ],
    // The server orders by the phone's order and sorts by nothing else, so no
    // header offers a sort it would not honour (law 2's mirror).
    defaultSort: { sort: "sort_order", dir: "asc" },
    columns: [
      { key: "name", label: t("settings.cantReadReasons.col.name"), identity: true, cell: (row) => <span>{row.name}</span> },
      {
        key: "type",
        label: t("settings.cantReadReasons.col.type"),
        cell: (row) => (
          <span>{t(row.is_system ? "settings.cantReadReasons.type.starting" : "settings.cantReadReasons.type.own")}</span>
        ),
      },
      {
        key: "status",
        label: t("settings.cantReadReasons.col.status"),
        cell: (row) => (
          <StatusPill tone={row.active ? "success" : "muted"}>
            {t(`settings.cantReadReasons.status.${row.active ? "active" : "inactive"}`)}
          </StatusPill>
        ),
      },
      {
        key: "used",
        label: t("settings.cantReadReasons.col.used"),
        cell: (row) => <span className="tabular-nums">{row.used}</span>,
      },
      { key: "actions", label: t("settings.reference.col.actions"), cell: actions },
    ],
  };
}

export interface CantReadReasonsPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function CantReadReasonsPage(props: CantReadReasonsPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const translate: Translate = (key, params) => t(key, params);

  // `null` = closed; `"new"` = add; a row = rename that row.
  const [naming, setNaming] = useState<CantReadReasonRow | "new" | null>(null);
  const [deleting, setDeleting] = useState<CantReadReasonRow | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const refresh = () => void queryClient.invalidateQueries({ queryKey: cantReadReasonKeys.all });
  const fail = (error: unknown) => setRefusal(refusalOf(error, t));

  const switchMutation = useMutation({
    mutationFn: (row: CantReadReasonRow) => updateCantReadReason(row.code, { active: !row.active }, client),
    onSuccess: (row) => {
      setRefusal(null);
      fireToast(t(row.active ? "settings.cantReadReasons.switchedOn" : "settings.cantReadReasons.switchedOff"));
      refresh();
    },
    onError: fail,
  });
  const moveMutation = useMutation({
    mutationFn: (arg: { row: CantReadReasonRow; direction: "up" | "down" }) =>
      moveCantReadReason(arg.row.code, arg.direction, client),
    onSuccess: () => {
      setRefusal(null);
      refresh();
    },
    onError: fail,
  });
  const deleteMutation = useMutation({
    mutationFn: (row: CantReadReasonRow) => deleteCantReadReason(row.code, client),
    onSuccess: () => {
      setDeleting(null);
      setRefusal(null);
      fireToast(t("settings.cantReadReasons.deleted"));
      refresh();
    },
    onError: (error) => {
      setDeleting(null);
      fail(error);
    },
  });

  const config = useMemo(
    () =>
      cantReadReasonsTableConfig(translate, (row) => (
        <RowActions>
          <RowAction
            label={t("settings.cantReadReasons.action.rename", { name: row.name })}
            icon={<PencilIcon />}
            onClick={() => {
              setRefusal(null);
              setNaming(row);
            }}
          />
          <RowAction
            label={t(row.active ? "settings.cantReadReasons.action.off" : "settings.cantReadReasons.action.on")}
            icon={<PowerIcon />}
            working={switchMutation.isPending}
            onClick={() => switchMutation.mutate(row)}
          />
          <RowActionsMore label={t("table.rowActions.more")}>
            <RowMenuAction
              label={t("settings.cantReadReasons.action.up")}
              icon={<ChevronUpIcon />}
              onClick={() => moveMutation.mutate({ row, direction: "up" })}
            />
            <RowMenuAction
              label={t("settings.cantReadReasons.action.down")}
              icon={<ChevronDownIcon />}
              onClick={() => moveMutation.mutate({ row, direction: "down" })}
            />
            <RowMenuAction
              label={t("settings.cantReadReasons.action.delete")}
              icon={<TrashIcon />}
              danger
              reason={row.is_system ? t("settings.cantReadReasons.cannotDelete") : null}
              onClick={() => {
                setRefusal(null);
                setDeleting(row);
              }}
            />
          </RowActionsMore>
        </RowActions>
      )),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, switchMutation.isPending],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const listQuery = { status: state.filters.status ?? "", q: state.q, page: state.page, per: state.per };
  const query = useQuery({
    queryKey: cantReadReasonKeys.list(listQuery),
    queryFn: () => listCantReadReasons(listQuery, client),
  });

  const addButton = (
    <Button variant="primary" onClick={() => setNaming("new")}>
      {t("settings.cantReadReasons.new")}
    </Button>
  );

  return (
    <section aria-label={t("settings.cantReadReasons.title")} className="flex flex-col gap-4">
      <PageHeader
        backTo={{ to: tenantPath(REFERENCE_DATA_PATH), label: t("settings.configure.subTab.referenceData") }}
        kicker={t("settings.readFormats.kicker")}
        title={t("settings.cantReadReasons.title")}
        rollup={t("settings.cantReadReasons.description")}
        primaryAction={addButton}
      />

      <RefusalNotice refusal={refusal} />

      <DataTable<CantReadReasonRow>
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
            ? { reason: t("settings.cantReadReasons.loadFailed"), onRetry: () => void query.refetch() }
            : null
        }
        empty={{
          title: t("settings.cantReadReasons.empty.title"),
          helper: t("settings.cantReadReasons.empty.helper"),
          ctaLabel: t("settings.cantReadReasons.new"),
          ctaVariant: "secondary",
          onCta: () => setNaming("new"),
        }}
      />

      {naming !== null && (
        <CantReadReasonNameDialog
          row={naming === "new" ? null : naming}
          client={client}
          onClose={() => setNaming(null)}
          onSaved={() => {
            setNaming(null);
            setRefusal(null);
            fireToast(t("settings.cantReadReasons.saved"));
            refresh();
          }}
        />
      )}

      {deleting !== null && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("settings.cantReadReasons.delete.title", { name: deleting.name })}
          consequence={t("settings.cantReadReasons.delete.consequence")}
          confirmLabel={t("settings.cantReadReasons.delete.confirm")}
          working={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </section>
  );
}

/** *Add reason* / *Rename* — one field, the name. The code is the server's. */
export function CantReadReasonNameDialog(props: {
  row: CantReadReasonRow | null;
  client: ApiClient;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState(props.row?.name ?? "");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      if (props.row === null) {
        await addCantReadReason(name.trim(), props.client);
      } else {
        await updateCantReadReason(props.row.code, { name: name.trim() }, props.client);
      }
      props.onSaved();
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
      title={t(props.row === null ? "settings.cantReadReasons.create.title" : "settings.cantReadReasons.rename.title")}
      schema={z.object({ name: z.string().trim().min(1, t("settings.cantReadReasons.create.nameRequired")) })}
      values={{ name }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("settings.cantReadReasons.create.submit")}
    >
      <TextField id="name" label={t("settings.cantReadReasons.col.name")} value={name} onChange={setName} required />
    </FormModal>
  );
}
