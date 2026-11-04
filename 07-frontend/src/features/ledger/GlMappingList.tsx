// ── Trace ──────────────────────────────────────────────
// CR:       CR-197-BRC10 — GL mapping becomes ONE list (Settings › Accounting ›
//           GL mapping). Design source: the claude.ai artifact
//           https://claude.ai/artifact/Ue5p1oSzgQquUva1KZjf8Y (version 4),
//           rendered to images and built to the images (B14 rule 42; PO
//           2026-10-29 *"Build the product screens based on images not on the
//           content"*). Our kit decides spacing, sizes and components (rule 44).
// Rulings:  decision log 2026-10-29 — Q1–Q4 A (Disable only for charge,
//           adjustment, discount; Add maps existing items; new bills only;
//           four tabs stay) · types by accounting practice · the create links
//           live INSIDE the Add form · *"Mapped for, start"*.
// Rules:    BR-LED-800..803 · NFR-3 (server pages, search, filters) · B14
//           rules 15 (row actions are icons), 20 (one table type), 21
//           (Tailwind; on route-b-migrated.txt), 31 (no id on screen), 32/33
//           (copy), 43 (built as a component), 44 (our standard wins)
// Tests:    src/features/ledger/glMappingList.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// WHAT THE DRAWING SHOWS, top to bottom (the images, not the HTML text):
//   1. "GL mapping" + one-sentence description · "+ Add mapping" at the right
//   2. three chips — N mappings · N not mapped · N disabled — each a filter
//   3. the toolbar — Search · Type · Status · GL account
//   4. one table: Group · Type · Mapped for · Detail · GL account · Status ·
//      Actions (edit pencil, power icon); a disabled row is muted
//   5. the pager
//   Dialogs: Add (Type grouped, fully-mapped types greyed "(all mapped)";
//   Mapped for = only unmapped items, with ONE link to where that type's items
//   are created; GL account; "Applies to new bills and payments."), Edit (Type
//   and Mapped for read-only; GL account; new-bills sentence), Disable confirm.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { ChipRow, ChipToggle } from "@/components/Chip";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { FormModal, SearchSelectField, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PencilIcon, PowerIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { RefusalNotice, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  GL_MAPPING_GROUP_OF,
  GL_MAPPING_GROUPS,
  GL_MAPPING_STATUSES,
  GL_MAPPING_TYPES,
  glMappingAddOptions,
  glMappingEditOptions,
  glMappingKeys,
  listGlMappings,
  saveGlMapping,
  setGlMappingEnabled,
} from "./glMappingEndpoints";
import type { GlMappingRow, GlMappingStatus, GlMappingType } from "./glMappingEndpoints";

export const GL_MAPPING_SCREEN = "SET-11.map";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** Where a type's NEW items are created (PO 2026-10-29: the link lives INSIDE
 *  the Add form, one per type). Payment, balance and system types have none. */
export const GL_MAPPING_CREATE_LINKS: Partial<Record<GlMappingType, string>> = {
  service_revenue: "/settings/services",
  charge_code: "/plans-rates/charge-codes/new",
  discount: "/plans-rates/discounts/new",
  tax: "/plans-rates/taxes-fees",
  adjustment: "/settings/reference-data?list=reason_codes",
  bill_payment: "/settings/reference-data?list=payment_methods",
};

const STATUS_TONE: Record<GlMappingStatus, StatusTone> = {
  mapped: "success",
  not_mapped: "warning",
  disabled: "muted",
};

/** A disabled row reads muted, as the drawing draws it (walk 2026-10-29). */
function muted(row: GlMappingRow): string | undefined {
  return row.status === "disabled" ? "text-neutral-600" : undefined;
}

/** The Mapped-for words: the catalogue's own where the row is a role. */
export function mappedForText(row: GlMappingRow, t: Translate): string {
  return row.mapped_for_key ? t(row.mapped_for_key) : row.mapped_for;
}

/** The Detail words — never an id (B14 rule 31). */
export function detailText(row: GlMappingRow, t: Translate): string {
  if (!row.detail_key) {
    return row.detail ?? "";
  }
  const cls = row.detail_params.cls;
  return t(row.detail_key, {
    ...row.detail_params,
    cls: cls === null || cls === undefined ? t("glMapping.allClasses") : cls,
  });
}

export function glMappingTableConfig(
  t: Translate,
  actions: (row: GlMappingRow) => React.ReactNode,
  glAccounts: { id: string; code: string; name: string }[],
): TableConfig<GlMappingRow> {
  return {
    screenId: GL_MAPPING_SCREEN,
    getRowId: (row) => row.key,
    searchFields: ["mapped_for", "detail", "gl_account"],
    searchPlaceholder: "glMapping.search",
    filters: [
      {
        name: "type",
        label: t("glMapping.col.type"),
        options: GL_MAPPING_TYPES.map((type) => ({ value: type, label: t(`glMapping.type.${type}`) })),
      },
      {
        name: "status",
        label: t("glMapping.col.status"),
        options: GL_MAPPING_STATUSES.map((status) => ({ value: status, label: t(`glMapping.status.${status}`) })),
      },
      {
        name: "gl_account",
        label: t("glMapping.col.glAccount"),
        options: glAccounts.map((account) => ({ value: account.id, label: `${account.code} ${account.name}` })),
      },
    ],
    // The server orders by group and type; no header offers a sort it would
    // not honour (law 2's mirror).
    defaultSort: { sort: "type", dir: "asc" },
    columns: [
      {
        key: "group",
        label: t("glMapping.col.group"),
        cell: (row) => <span className="text-sm text-neutral-700">{t(`glMapping.group.${row.group}`)}</span>,
      },
      { key: "type", label: t("glMapping.col.type"), cell: (row) => <span className={muted(row)}>{t(`glMapping.type.${row.type}`)}</span> },
      {
        key: "mapped_for",
        label: t("glMapping.col.mappedFor"),
        identity: true,
        cell: (row) => <span className={muted(row)}>{mappedForText(row, t)}</span>,
      },
      { key: "detail", label: t("glMapping.col.detail"), cell: (row) => <span className={muted(row)}>{detailText(row, t)}</span> },
      {
        key: "gl_account",
        label: t("glMapping.col.glAccount"),
        cell: (row) =>
          row.account === null ? (
            <span className="font-semibold text-warning-700">{t("glMapping.status.not_mapped")}</span>
          ) : (
            <span className={muted(row)}>
              <span className="tabular-nums">{row.account.code}</span>{" "}
              <span className="text-neutral-700">{row.account.name}</span>
            </span>
          ),
      },
      {
        key: "status",
        label: t("glMapping.col.status"),
        cell: (row) => <StatusPill tone={STATUS_TONE[row.status]}>{t(`glMapping.status.${row.status}`)}</StatusPill>,
      },
      { key: "actions", label: t("glMapping.col.actions"), cell: actions },
    ],
  };
}

export interface GlMappingListProps {
  readOnly: boolean;
  client?: ApiClient; // test seam — screens never build their own transport
  /** A deep link's starting filters (Phase 3: *"account set on GL mapping"*). */
  initialFilters?: Record<string, string>;
  initialQuery?: string;
}

export function GlMappingList(props: GlMappingListProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const translate: Translate = (key, params) => t(key, params);

  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<GlMappingRow | null>(null);
  const [disabling, setDisabling] = useState<GlMappingRow | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [glAccounts, setGlAccounts] = useState<{ id: string; code: string; name: string }[]>([]);

  const refresh = () => void queryClient.invalidateQueries({ queryKey: glMappingKeys.all });

  const switchMutation = useMutation({
    mutationFn: (arg: { row: GlMappingRow; enabled: boolean }) =>
      setGlMappingEnabled(arg.row.key, arg.enabled, client),
    onSuccess: (_result, arg) => {
      setDisabling(null);
      setRefusal(null);
      const name = mappedForText(arg.row, translate);
      fireToast(t(arg.enabled ? "glMapping.toast.enabled" : "glMapping.toast.disabled", { name }));
      refresh();
    },
    onError: (error) => {
      setDisabling(null);
      setRefusal(refusalOf(error, t));
    },
  });

  const config = useMemo(
    () =>
      glMappingTableConfig(
        translate,
        (row) => {
          const name = mappedForText(row, translate);
          const canSwitch = row.status === "disabled" ? row.can_enable : row.can_disable;
          const offReason =
            row.type === "discount" && row.status === "disabled"
              ? t("glMapping.reason.discountRetired")
              : t("glMapping.reason.switchedOffElsewhere");
          return (
            <RowActions>
              <RowAction
                label={t("glMapping.action.edit", { name })}
                icon={<PencilIcon />}
                reason={
                  props.readOnly
                    ? t("settings.readOnlyReason")
                    : row.status === "disabled"
                      ? t("glMapping.reason.enableFirst")
                      : null
                }
                onClick={() => {
                  setRefusal(null);
                  setEditing(row);
                }}
              />
              <RowAction
                label={t(row.status === "disabled" ? "glMapping.action.enable" : "glMapping.action.disable", { name })}
                icon={<PowerIcon />}
                working={switchMutation.isPending}
                reason={props.readOnly ? t("settings.readOnlyReason") : canSwitch ? null : offReason}
                onClick={() => {
                  setRefusal(null);
                  if (row.status === "disabled") {
                    switchMutation.mutate({ row, enabled: true });
                  } else {
                    setDisabling(row);
                  }
                }}
              />
            </RowActions>
          );
        },
        glAccounts,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, switchMutation.isPending, props.readOnly, glAccounts],
  );

  const [state, setState] = useState<TableRequestState>(() => ({
    ...defaultRequestState(config),
    q: props.initialQuery ?? "",
    filters: { ...(props.initialFilters ?? {}) },
  }));
  const listQuery = {
    q: state.q,
    type: state.filters.type ?? "",
    status: state.filters.status ?? "",
    gl_account: state.filters.gl_account ?? "",
    page: state.page,
    per: state.per,
  };
  const query = useQuery({
    queryKey: glMappingKeys.list(listQuery),
    queryFn: async () => {
      const page = await listGlMappings(listQuery, client);
      setGlAccounts(page.gl_accounts);
      return page;
    },
  });
  const counts = query.data?.counts;
  const status = state.filters.status ?? "";
  const pickStatus = (value: string) =>
    setState((prev) => ({ ...prev, page: 1, filters: { ...prev.filters, status: value } }));

  return (
    <section aria-label={t("glMapping.title")} className="flex flex-col gap-4" data-screen={GL_MAPPING_SCREEN}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="settings-frame-title">{t("glMapping.title")}</h3>
          <Note>{t("glMapping.lede")}</Note>
        </div>
        <Button
          variant="primary"
          disabled={props.readOnly}
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => {
            setRefusal(null);
            setAdding(true);
          }}
        >
          {t("glMapping.add")}
        </Button>
      </div>

      {counts !== undefined && (
        <ChipRow aria-label={t("glMapping.summary")}>
          <ChipToggle selected={status === ""} onClick={() => pickStatus("")}>
            {t("glMapping.count.total", { count: counts.total })}
          </ChipToggle>
          <ChipToggle selected={status === "not_mapped"} onClick={() => pickStatus("not_mapped")}>
            {t("glMapping.count.notMapped", { count: counts.not_mapped })}
          </ChipToggle>
          <ChipToggle selected={status === "disabled"} onClick={() => pickStatus("disabled")}>
            {t("glMapping.count.disabled", { count: counts.disabled })}
          </ChipToggle>
        </ChipRow>
      )}

      <RefusalNotice refusal={refusal} />

      <DataTable<GlMappingRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.results ?? []}
        totalRows={query.data?.count ?? null}
        loading={query.isPending}
        filterBarSlot={<FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />}
        error={query.isError ? { reason: t("glMapping.loadFailed"), onRetry: () => void query.refetch() } : null}
        empty={{ title: t("glMapping.empty.title"), helper: t("glMapping.empty.helper") }}
      />

      {adding && (
        <AddGlMappingDialog
          client={client}
          onClose={() => setAdding(false)}
          onSaved={(row) => {
            setAdding(false);
            fireToast(t("glMapping.toast.mapped", { name: mappedForText(row, translate) }));
            refresh();
          }}
        />
      )}
      {editing !== null && (
        <EditGlMappingDialog
          row={editing}
          client={client}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            fireToast(t("glMapping.toast.saved"));
            refresh();
          }}
        />
      )}
      {disabling !== null && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("glMapping.disable.title", { name: mappedForText(disabling, translate) })}
          consequence={t(
            disabling.type === "service_revenue" ? "glMapping.disable.overrideConsequence" : "glMapping.disable.consequence",
          )}
          confirmLabel={t("glMapping.disable.confirm")}
          working={switchMutation.isPending}
          onConfirm={() => switchMutation.mutate({ row: disabling, enabled: false })}
          onCancel={() => setDisabling(null)}
        />
      )}
    </section>
  );
}

async function outcome(work: () => Promise<unknown>): Promise<FormSubmitOutcome> {
  try {
    await work();
    return { ok: true };
  } catch (error) {
    if (isApiError(error)) {
      return { ok: false, error: formErrorEnvelope(error) };
    }
    return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
  }
}

function accountOptions(accounts: { id: string; code: string; name: string }[]) {
  return accounts.map((account) => ({
    value: account.id,
    label: `${account.code} ${account.name}`,
    search: `${account.code} ${account.name}`,
  }));
}

/** *Add mapping* — maps an EXISTING item that has no account yet (Q2 A). */
export function AddGlMappingDialog(props: {
  client: ApiClient;
  onClose: () => void;
  onSaved: (row: GlMappingRow) => void;
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const translate: Translate = (key, params) => t(key, params);
  const [type, setType] = useState("");
  const [key, setKey] = useState("");
  const [accountId, setAccountId] = useState("");

  const options = useQuery({
    queryKey: glMappingKeys.add(type),
    queryFn: () => glMappingAddOptions(type, props.client),
  });
  const open = new Map((options.data?.types ?? []).map((entry) => [entry.type, entry.open]));
  const typeGroups = GL_MAPPING_GROUPS.map((group) => ({
    label: t(`glMapping.group.${group}`),
    options: GL_MAPPING_TYPES.filter((each) => GL_MAPPING_GROUP_OF[each] === group).map((each) => {
      const label = t(`glMapping.type.${each}`);
      const full = options.data !== undefined && (open.get(each) ?? 0) === 0;
      return { value: each, label: full ? t("glMapping.add.allMapped", { type: label }) : label, disabled: full };
    }),
  }));
  const items = type === "" ? [] : (options.data?.items ?? []);
  const link = type === "" ? undefined : GL_MAPPING_CREATE_LINKS[type as GlMappingType];

  async function submit(): Promise<FormSubmitOutcome> {
    return outcome(async () => {
      const row = await saveGlMapping({ act: "add", key, account_id: accountId }, props.client);
      props.onSaved(row);
    });
  }

  return (
    <FormModal
      title={t("glMapping.add.title")}
      schema={z.object({
        type: z.string().min(1, t("glMapping.add.typeRequired")),
        key: z.string().min(1, t("glMapping.add.itemRequired")),
        account: z.string().min(1, t("glMapping.add.accountRequired")),
      })}
      values={{ type, key, account: accountId }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("glMapping.save")}
    >
      <SelectField
        id="type"
        label={t("glMapping.col.type")}
        value={type}
        onChange={(value) => {
          setType(value);
          setKey("");
          setAccountId("");
        }}
        options={[]}
        groups={typeGroups}
        placeholder={t("glMapping.add.chooseType")}
        required
      />
      <div className="flex flex-col gap-1">
        <SelectField
          id="key"
          label={t("glMapping.col.mappedFor")}
          value={key}
          onChange={(value) => {
            setKey(value);
            setAccountId("");
          }}
          options={items.map((row) => ({
            value: row.key,
            label: `${mappedForText(row, translate)} · ${detailText(row, translate)}`,
          }))}
          placeholder={t(type === "" ? "glMapping.add.chooseTypeFirst" : "glMapping.add.chooseItem")}
          help={t("glMapping.add.onlyUnmapped")}
          disabled={type === ""}
          required
        />
        {link !== undefined && (
          <InlineLinkTo to={tenantPath(link)} className="self-start text-sm">
            {t(`glMapping.link.${type}`)}
          </InlineLinkTo>
        )}
      </div>
      <SearchSelectField
        id="account"
        label={t("glMapping.col.glAccount")}
        value={accountId}
        onChange={setAccountId}
        options={key === "" ? [] : accountOptions(options.data?.accounts ?? [])}
        placeholder={t(key === "" ? "glMapping.add.chooseItemFirst" : "glMapping.chooseAccount")}
        disabled={key === ""}
        dropdown
        required
      />
      <Note>{t("glMapping.add.appliesToNew")}</Note>
    </FormModal>
  );
}

/** *Edit mapping* — a new account for one row; issued bills keep theirs. */
export function EditGlMappingDialog(props: {
  row: GlMappingRow;
  client: ApiClient;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const [accountId, setAccountId] = useState(props.row.account?.id ?? "");
  const options = useQuery({
    queryKey: glMappingKeys.edit(props.row.key),
    queryFn: () => glMappingEditOptions(props.row.key, props.client),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    return outcome(() => saveGlMapping({ act: "edit", key: props.row.key, account_id: accountId }, props.client)).then(
      (result) => {
        if (result.ok) {
          props.onSaved();
        }
        return result;
      },
    );
  }

  return (
    <FormModal
      title={t("glMapping.edit.title")}
      schema={z.object({ account: z.string().min(1, t("glMapping.add.accountRequired")) })}
      values={{ account: accountId }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("glMapping.save")}
    >
      <TextField id="type" label={t("glMapping.col.type")} value={t(`glMapping.type.${props.row.type}`)} onChange={() => undefined} readOnly />
      <TextField
        id="mappedFor"
        label={t("glMapping.col.mappedFor")}
        value={`${mappedForText(props.row, translate)} · ${detailText(props.row, translate)}`}
        onChange={() => undefined}
        readOnly
      />
      <SearchSelectField
        id="account"
        label={t("glMapping.col.glAccount")}
        value={accountId}
        onChange={setAccountId}
        options={accountOptions(options.data?.accounts ?? [])}
        placeholder={t("glMapping.chooseAccount")}
        dropdown
        required
      />
      <Note>{t("glMapping.edit.newOnly")}</Note>
    </FormModal>
  );
}
