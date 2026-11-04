// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-074 (EP-CWP-12) — service centres, and *hidden* is a state,
//           not a deletion. Screens: CWP-074 (a card in Reference data) ·
//           CWP-075 (the editor)
// Rules:    08-screen-layouts.md CWP-074 (T8 breadcrumb + T5: Centre (bold +
//           grey address; **hidden row greyed**) / Open / Takes / You can /
//           Status → WarningBar (hidden is a state) · InfoBar (holiday
//           calendar)) and CWP-075 (T8 + T6 + TwoCol: WHERE IT IS · WHAT A
//           CUSTOMER CAN DO HERE five checkboxes · rail OPENING HOURS 7 rows +
//           footer *Public holidays close it automatically.* · TAKES PAYMENT
//           BY ToggleChips · ON THE PORTAL) · BR-CWP-096 · B14 rule 6 (⚠ the
//           danger tier on *Remove*, and only there) · rule 9 (multi-select is
//           removable chips) · rule 21 · rule 32
// Defect:   DEF-CWP-3821 — `create_centre` shipped with wave D (`2.138.0`),
//           tested and routed, and NOTHING could reach it: *New centre* was a
//           disabled CTA over `onCta: () => undefined`, so a utility that had
//           never had a centre could never get its first one, and the visit
//           page (`BR-CWP-093`) could never exist. Hard-won law 2.
//           DEF-CWP-3822 — and this trace header carried the second one: its
//           Tests line named a same-named test file beside this one that has
//           never existed, which G95 skipped because a citation with no slash
//           in it resolves against no root.
// Tests:    src/features/tenancy/SettingsPortalContent.test.tsx ·
//           src/features/tenancy/SettingsPortalCreate.dom.test.tsx
// Impacts:  src/api/publishedContentEndpoints.ts · SettingsReferenceData.tsx
// ───────────────────────────────────────────────────────
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  createServiceCentre,
  deleteServiceCentre,
  getServiceCentre,
  getServiceCentres,
  saveServiceCentre,
} from "@/api/publishedContentEndpoints";
import type {
  CentreHourRow,
  ServiceCentreDetail,
  ServiceCentreRow,
} from "@/api/publishedContentEndpoints";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { ChipMultiSelect } from "@/components/ChipMultiSelect";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { PencilIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { Switch } from "@/components/Switch";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";

import { weekdayLabel } from "./serviceCentreWeek";

// ══ CWP-074 · the list, inside the Reference-data frame ════════════════════

export function ServiceCentresView(props: { readOnly: boolean; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  /** `undefined` = the list · `null` = a NEW centre · a string = that centre's
   *  editor. `CWP-074 → CWP-075`, one screen id per view (BR-SHL-035). */
  const [open, setOpen] = useState<string | null | undefined>(undefined);
  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: "position",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  const query = useQuery({ queryKey: queryKeys.serviceCentres, queryFn: () => getServiceCentres(client) });

  if (open !== undefined) {
    return (
      <ServiceCentreEditor
        slug={open}
        readOnly={props.readOnly}
        client={client}
        onBack={() => setOpen(undefined)}
      />
    );
  }
  const view = query.data;
  const all = view?.centres ?? [];
  const filtered = all
    .filter((row) => {
      const wanted = state.filters.shown;
      if (wanted === undefined || wanted === "") return true;
      return wanted === "shown" ? row.is_shown_to_customers : !row.is_shown_to_customers;
    })
    .filter(
      (row) =>
        state.q === "" ||
        row.name.toLowerCase().includes(state.q.toLowerCase()) ||
        row.address.toLowerCase().includes(state.q.toLowerCase()),
    );
  const sorted = [...filtered].sort((a, b) => {
    const dir = state.dir === "desc" ? -1 : 1;
    if (state.sort === "centre") return a.name.localeCompare(b.name) * dir;
    return (a.position - b.position) * dir;
  });
  const from = (state.page - 1) * state.per;
  const rows = sorted.slice(from, from + state.per);

  const config: TableConfig<ServiceCentreRow> = {
    screenId: "CWP-074",
    getRowId: (row) => row.slug,
    searchFields: ["name", "address"],
    searchPlaceholder: "settings.centres.searchPlaceholder",
    defaultSort: { sort: "position", dir: "asc" },
    filters: [
      {
        name: "shown",
        label: t("settings.reference.col.status"),
        options: [
          { value: "shown", label: t("settings.centres.status.onThePortal") },
          { value: "hidden", label: t("settings.centres.status.hidden") },
        ],
      },
    ],
    columns: [
      {
        key: "centre",
        label: t("settings.centres.column.centre"),
        identity: true,
        sortable: true,
        cell: (row: ServiceCentreRow) => (
          // ⚠ A CELL HOLDS A VALUE. The address is the row's second line and
          // not a sentence — `TableColumnConfig.render`'s own header says why.
          <span data-centre-row={row.slug} data-shown={row.is_shown_to_customers ? "yes" : "no"}>
            {row.name}
            <span className="block text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{row.address}</span>
          </span>
        ),
      },
      {
        key: "takes",
        label: t("settings.centres.column.takes"),
        cell: (row: ServiceCentreRow) =>
          row.payment_methods_accepted.length > 0
            ? row.payment_methods_accepted.map((one) => t(`portal.centre.method.${one}`)).join(" · ")
            : "—",
      },
      {
        key: "youCan",
        label: t("settings.centres.column.youCan"),
        numeric: true,
        cell: (row: ServiceCentreRow) =>
          t("settings.centres.actionsOf", {
            can: row.allowed_actions.length,
            total: view?.all_actions.length ?? 0,
          }),
      },
      {
        key: "status",
        label: t("settings.reference.col.status"),
        cell: (row: ServiceCentreRow) => (
          // ⚠ HIDDEN IS A STATE, NOT A DELETION (BR-CWP-096): the depot is off
          // the public page and still in this list, one control from returning.
          <StatusPill tone={row.is_shown_to_customers ? "success" : "neutral"}>
            {row.is_shown_to_customers
              ? t("settings.centres.status.onThePortal")
              : t("settings.centres.status.hidden")}
          </StatusPill>
        ),
      },
      {
        key: "actions",
        label: t("settings.reference.col.actions"),
        cell: (row: ServiceCentreRow) => (
          <RowActions>
            <RowAction
              icon={<PencilIcon />}
              label={t("settings.centres.edit")}
              onClick={() => setOpen(row.slug)}
            />
          </RowActions>
        ),
      },
    ],
  };

  return (
    <div data-screen="CWP-074" className="flex flex-col gap-4">
      {/* ⚠ ONE PRIMARY (B14 rule 4 / BR-SHL-044), and it is LIVE. The drawing
          says *+ New centre* **held**; that was true of the day it was drawn
          and stopped being true when `create_centre` landed —
          `08-screen-layouts.md` CWP-074 is amended and dated.
          ⚠ NO TITLE AND NO DESCRIPTION HERE: `SettingsFrame` already draws the
          card's kicker, title and one sentence (`SettingsReferenceData.tsx`),
          and a second would be B14 rule 32's description budget spent twice on
          one screen. The button is the whole of what this row adds. */}
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          disabled={props.readOnly}
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => setOpen(null)}
          data-action="new-centre"
        >
          {t("settings.centres.addCentre")}
        </Button>
      </div>
      <DataTable<ServiceCentreRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={view === undefined ? null : filtered.length}
        loading={query.isPending}
        error={
          query.isError
            ? { reason: refusalText(t, query.error), onRetry: () => void query.refetch() }
            : null
        }
        empty={{
          title: t("settings.centres.emptyTitle"),
          helper: t("settings.centres.emptyHelper"),
          ctaLabel: t("settings.centres.addCentre"),
          // ⚠ `ctaReason` IS GONE, and its absence is the fix. It read *"Adding
          // centres arrives later"* over an endpoint that had created one since
          // `2.138.0`, on the ONE screen where a stated absence is fatal: a
          // utility with no centres has no visit page (`BR-CWP-093`) and no way
          // to get its first one.
          ctaReason: props.readOnly ? t("settings.readOnlyReason") : null,
          onCta: () => setOpen(null),
        }}
        filterBarSlot={<FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />}
      />
      <Note>{t("settings.centres.hiddenIsAState")}</Note>
      <Note>{t("settings.centres.holidaysComeFromTheCalendar")}</Note>
    </div>
  );
}

// ══ CWP-075 · the editor ═══════════════════════════════════════════════════

function draftOf(row: ServiceCentreDetail): Draft {
  const { name, address, phone, directions_note, allowed_actions, payment_methods_accepted, is_shown_to_customers, hours } = row;
  return { name, address, phone, directions_note, allowed_actions, payment_methods_accepted, is_shown_to_customers, hours };
}

type Draft = Pick<
  ServiceCentreDetail,
  | "name"
  | "address"
  | "phone"
  | "directions_note"
  | "allowed_actions"
  | "payment_methods_accepted"
  | "is_shown_to_customers"
  | "hours"
>;

/** Seven closed days and nothing else. ⚠ **HIDDEN, AND THAT IS LAW 3** — the
 *  unsafe option (publishing an address a customer will drive to) is the one
 *  somebody has to type. `create_centre` defaults the same way, so the draft
 *  and the server agree rather than one of them being decorative. */
function blankCentre(): Draft {
  return {
    name: "",
    address: "",
    phone: null,
    directions_note: null,
    allowed_actions: [],
    payment_methods_accepted: [],
    is_shown_to_customers: false,
    hours: [0, 1, 2, 3, 4, 5, 6].map((day) => ({
      day_of_week: day,
      is_closed: true,
      opens_at: null,
      closes_at: null,
    })),
  };
}

export function ServiceCentreEditor(props: {
  /** `null` = a NEW centre. */
  slug: string | null;
  readOnly: boolean;
  client?: ApiClient;
  onBack: () => void;
}) {
  const { t, i18n } = useTranslation();
  const client = props.client ?? api;
  const language = i18n.language || "en";
  const queryClient = useQueryClient();
  const fireToast = useToast();
  // ⚠ Seeded from the cache as well as by the effect — see the same note on
  // the help editor: an effect never runs at `renderToStaticMarkup`.
  const creating = props.slug === null;
  const query = useQuery({
    queryKey: [...queryKeys.serviceCentres, props.slug ?? "new"],
    queryFn: () => getServiceCentre(props.slug ?? "", client),
    enabled: !creating,
  });
  /** ⚠ **THE TWO CLOSED SETS COME FROM THE LIST, NOT FROM A LITERAL HERE.**
   *  A new centre has no detail to read them off, and typing the five actions
   *  and four tenders into this file is the SignupWizard trap in CLAUDE.md's
   *  first paragraph — a sixth action would exist, be served, pass every test
   *  and never be offered. This is the same cache key the list already fills. */
  const listQuery = useQuery({
    queryKey: queryKeys.serviceCentres,
    queryFn: () => getServiceCentres(client),
    enabled: creating,
  });
  const [draft, setDraft] = useState<Draft | null>(() =>
    creating ? blankCentre() : query.data === undefined ? null : draftOf(query.data),
  );
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    if (query.data !== undefined && draft === null) {
      setDraft(draftOf(query.data));
    }
  }, [query.data, draft]);
  const save = useMutation({
    mutationFn: (next: Draft) =>
      creating ? createServiceCentre(next, client) : saveServiceCentre(props.slug ?? "", next, client),
    onSuccess: (data) => {
      queryClient.setQueryData([...queryKeys.serviceCentres, data.slug], data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.serviceCentres });
      fireToast(t("settings.centres.saved"));
      // ⚠ A CREATE ENDS ON THE LIST, and that is deliberate: the row it just
      // made is the thing worth seeing, carrying its HIDDEN pill, so the one
      // remaining act — showing it to customers — is in front of the clerk
      // rather than behind a back link.
      if (creating) props.onBack();
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteServiceCentre(props.slug ?? "", client),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.serviceCentres });
      props.onBack();
    },
  });

  if (draft === null || (!creating && query.isPending)) return <LoadingSkeleton variant="card" />;
  if (!creating && query.data === undefined) {
    return (
      <FailedWithRetry
        title={t("settings.centres.failedTitle")}
        reason={refusalText(t, query.error)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }
  /** The two closed sets, from whichever read has them. ⚠ An EMPTY set renders
   *  an empty chip picker rather than a wall of guesses — the honest shape
   *  while the list read is still in flight. */
  const allActions = query.data?.all_actions ?? listQuery.data?.all_actions ?? [];
  const allMethods = query.data?.all_payment_methods ?? listQuery.data?.all_payment_methods ?? [];

  function setHour(day: number, patch: Partial<CentreHourRow>): void {
    if (draft === null) return;
    setDraft({
      ...draft,
      hours: draft.hours.map((row) => (row.day_of_week === day ? { ...row, ...patch } : row)),
    });
  }

  return (
    <div data-screen="CWP-075" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Button variant="ghost" onClick={props.onBack} data-back="centres">
            ← {t("settings.centres.title")}
          </Button>
          <h2 className="settings-frame-title">
            {creating ? t("settings.centres.addCentre") : draft.name}
          </h2>
          <p className="settings-frame-desc">
            {draft.is_shown_to_customers
              ? t("settings.centres.status.onThePortal")
              : t("settings.centres.status.hidden")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {/* ⚠ B14 RULE 6: the danger tier, and ONLY here. Removing an address
              customers may have printed is the destructive act on this screen;
              hiding is not, and that is the point of the confirm's wording. */}
          {creating ? null : (
            <Button
              variant="danger"
              disabled={props.readOnly || remove.isPending}
              onClick={() => setConfirming(true)}
              data-action="remove"
            >
              {t("settings.centres.remove")}
            </Button>
          )}
          <Button
            onClick={() => save.mutate(draft)}
            disabled={
              props.readOnly ||
              save.isPending ||
              draft.name.trim() === "" ||
              draft.address.trim() === ""
            }
            data-action="save"
          >
            {t("settings.centres.save")}
          </Button>
        </div>
      </header>
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-col gap-4 md:col-span-8">
          <Panel as="section" title={t("settings.centres.whereItIs")}>
            <label className="block">
              <span className="mb-1 block text-md font-semibold">{t("settings.reference.col.name")}*</span>
              <input
                className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                value={draft.name}
                readOnly={props.readOnly}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                data-field="name"
              />
            </label>
            <label className="mt-4 block">
              <span className="mb-1 block text-md font-semibold">{t("settings.centres.field.address")}*</span>
              <input
                className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                value={draft.address}
                readOnly={props.readOnly}
                onChange={(e) => setDraft({ ...draft, address: e.target.value })}
                data-field="address"
              />
            </label>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <label className="block">
                <span className="mb-1 block text-md font-semibold">{t("settings.centres.field.phone")}</span>
                <input
                  className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                  value={draft.phone ?? ""}
                  readOnly={props.readOnly}
                  onChange={(e) => setDraft({ ...draft, phone: e.target.value })}
                  data-field="phone"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-md font-semibold">{t("settings.centres.field.directions")}</span>
                <textarea
                  className="min-h-24 w-full resize-y border border-field-border bg-bg px-3 py-2 text-md"
                  value={draft.directions_note ?? ""}
                  readOnly={props.readOnly}
                  onChange={(e) => setDraft({ ...draft, directions_note: e.target.value })}
                  data-field="directions_note"
                />
              </label>
            </div>
          </Panel>
          {/* ⚠ **CHIPS, NOT A WALL OF CHECKBOXES** — r10 rule 9, and B14 rule
              36 names the checkbox wall as a LIVE breach on the neighbouring
              screen. The kit's `ChipMultiSelect` is the one place that decision
              is made. */}
          <Panel as="section" title={t("settings.centres.whatACustomerCanDo")}>
            <ChipMultiSelect
              label={t("settings.centres.whatACustomerCanDo")}
              options={allActions.map((action) => ({
                value: action,
                label: t(`portal.centre.action.${action}`),
              }))}
              selected={draft.allowed_actions}
              onChange={(next) => setDraft({ ...draft, allowed_actions: next })}
              disabled={props.readOnly}
              reason={props.readOnly ? t("settings.readOnlyReason") : null}
              addLabel={t("settings.centres.addAction")}
              emptyLabel={t("settings.centres.noActions")}
              removeLabel={t("settings.centres.removeAction")}
              testKey="actions"
            />
            {/* ⚠ WHAT IS NOT CHOSEN IS AN ANSWER, not an omission — the
                customer's screen draws it as *cannot*, and that is what saves
                a wasted journey. */}
            <Note>{t("settings.centres.untickedIsAnAnswer")}</Note>
          </Panel>
        </div>
        <div className="col-span-12 flex flex-col gap-4 md:col-span-4">
          <Panel as="section" title={t("settings.centres.openingHours")}>
            <ul className="flex flex-col gap-2">
              {draft.hours.map((row) => (
                <li key={row.day_of_week} className="flex items-center gap-2" data-hour-row={row.day_of_week}>
                  <span className="w-24 shrink-0 font-semibold">
                    {weekdayLabel(row.day_of_week, language)}
                  </span>
                  <Switch
                    on={!row.is_closed}
                    label={weekdayLabel(row.day_of_week, language)}
                    onLabel={t("settings.centres.open")}
                    offLabel={t("settings.centres.closed")}
                    reason={props.readOnly ? t("settings.readOnlyReason") : null}
                    onChange={(on) => setHour(row.day_of_week, { is_closed: !on })}
                    testKey={`day-${row.day_of_week}`}
                  />
                  {!row.is_closed ? (
                    <>
                      <input
                        type="time"
                        className="h-9 w-24 border border-field-border bg-bg px-2 text-md"
                        value={row.opens_at ?? ""}
                        readOnly={props.readOnly}
                        onChange={(e) => setHour(row.day_of_week, { opens_at: e.target.value })}
                        aria-label={t("settings.centres.opensAt")}
                      />
                      <input
                        type="time"
                        className="h-9 w-24 border border-field-border bg-bg px-2 text-md"
                        value={row.closes_at ?? ""}
                        readOnly={props.readOnly}
                        onChange={(e) => setHour(row.day_of_week, { closes_at: e.target.value })}
                        aria-label={t("settings.centres.closesAt")}
                      />
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
            {/* ⚠ THE ONE SENTENCE THAT STOPS SOMEBODY TYPING THANKSGIVING IN. */}
            <p className="mt-3 text-md text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{t("settings.centres.holidaysAutomatic")}</p>
          </Panel>
          <Panel as="section" title={t("settings.centres.takesPaymentBy")}>
            <ChipMultiSelect
              label={t("settings.centres.takesPaymentBy")}
              options={allMethods.map((method) => ({
                value: method,
                label: t(`portal.centre.method.${method}`),
              }))}
              selected={draft.payment_methods_accepted}
              onChange={(next) => setDraft({ ...draft, payment_methods_accepted: next })}
              disabled={props.readOnly}
              reason={props.readOnly ? t("settings.readOnlyReason") : null}
              addLabel={t("settings.centres.addMethod")}
              emptyLabel={t("settings.centres.noMethods")}
              removeLabel={t("settings.centres.removeMethod")}
              testKey="methods"
            />
          </Panel>
          <Panel as="section" title={t("settings.centres.onThePortal")}>
            <div className="flex items-center justify-between gap-3">
              <span >{t("settings.centres.shownToCustomers")}</span>
              <Switch
                on={draft.is_shown_to_customers}
                label={t("settings.centres.shownToCustomers")}
                onLabel={t("settings.portal.on")}
                offLabel={t("settings.portal.off")}
                reason={props.readOnly ? t("settings.readOnlyReason") : null}
                onChange={(on) => setDraft({ ...draft, is_shown_to_customers: on })}
                testKey="shown"
              />
            </div>
            <p className="mt-2 text-md text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{t("settings.centres.hiddenIsAState")}</p>
          </Panel>
        </div>
      </div>
      {confirming ? (
        <ConfirmDialog
          title={t("settings.centres.removeTitle")}
          // ⚠ THE CONSEQUENCE IS THE POINT (US-CWP-074 TC-9): a printed
          // address does not stop existing when the row does, so the dialog
          // names that and offers hiding instead.
          consequence={t("settings.centres.removeWarning")}
          confirmLabel={t("settings.centres.remove")}
          // ⚠ B14 rule 6, AND THE PROP MUST STAND ALONE ON ITS LINE: the
          // call-site census in `ConfirmDialogTier.dom.test.tsx` reads this
          // file as TEXT, and a trailing comment here reads as an undeclared
          // tier. It said so by going red.
          confirmVariant="danger"
          working={remove.isPending}
          onConfirm={() => {
            setConfirming(false);
            remove.mutate();
          }}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
    </div>
  );
}
