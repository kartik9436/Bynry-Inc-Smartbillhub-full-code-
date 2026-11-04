// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-073 (EP-CWP-12) — tips: one slot, in season, and the page
//           closes up when there is none. Screens: CWP-073 (the list AND its
//           editor — see the amendment note above `PortalTipEditor`)
// Defect:   DEF-CWP-3820 — `create_tip`, `update_tip` and `delete_tip` shipped
//           with wave D (`2.138.0`), tested and routed, and NOTHING could reach
//           them: the only control was a disabled *New tip* over
//           `onCta: () => undefined`, and the on/off switch was the whole of
//           what a clerk could change. Hard-won law 2, with the label on.
//           DEF-CWP-3822 — and this trace header carried the second one: its
//           Tests line named a same-named test file beside this one that has
//           never existed. G95 could not see it, because a citation with no
//           slash in it resolves against no root and was simply skipped.
// Rules:    08-screen-layouts.md CWP-073 (T8 + T5 then TwoEqual: toolbar with
//           filters · grey right *One tip per screen at a time* · reorder
//           handle / Tip / Where it shows / When / Status · footer *Top of the
//           list wins where two match* → Panel **A TIP IS NOT AN ANSWER** ·
//           Panel **SEASONAL TIPS**) · BR-CWP-095 · **B14 rule 36** (the
//           captured pack gives layout and detail; r10 gives the visual style;
//           the SHARED KIT is how you comply — so this screen composes
//           `DataTable`, `FilterBar`, `Panel`, `StatusPill` and `Switch` and
//           hand-rolls none of them) · r10 rules 12, 13, 16, 17 (all five
//           carried by `DataTable`) · B14 rule 21 · rule 32
// Tests:    src/features/tenancy/SettingsPortalContent.test.tsx ·
//           src/features/tenancy/SettingsPortalCreate.dom.test.tsx
// Impacts:  src/api/publishedContentEndpoints.ts · SettingsCustomerPortalTab.tsx
//           · 06-backend/apps/tenancy/published_content_api.py (the tips GET
//           now carries `all_screens` and `word_guidance`)
// ───────────────────────────────────────────────────────
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { createTip, deleteTip, getTips, reorderTips, saveTip } from "@/api/publishedContentEndpoints";
import type { TipRow, TipsView } from "@/api/publishedContentEndpoints";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { ChevronDownIcon, ChevronUpIcon, PencilIcon, TrashIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { Switch } from "@/components/Switch";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Kicker, Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { TipBar } from "@/portal/components/content";

import { RefusalNotice, refusalOf } from "./settingsShared";

const FILTERS = ["showing_now", "seasonal"] as const;

/** 1…12. The NAMES come from `Intl` in the reader's own language (B14 rule 35);
 *  only the numbers are ours. */
const MONTH_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;

/** *June to September*, or *all year* — the MONTH NAMES come from `Intl` in the
 *  reader's own language and the frame from the catalogue (B14 rule 35). */
function seasonText(row: TipRow, language: string, t: TFunction): string {
  if (row.month_from === null || row.month_to === null) return t("settings.portalTips.allYear");
  const month = (n: number) =>
    new Intl.DateTimeFormat(language, { month: "long" }).format(new Date(2024, n - 1, 1));
  return t("settings.portalTips.monthRange", { from: month(row.month_from), to: month(row.month_to) });
}

export function PortalTipsList(props: { readOnly: boolean; client?: ApiClient }) {
  const { t, i18n } = useTranslation();
  const client = props.client ?? api;
  const language = i18n.language || "en";
  const queryClient = useQueryClient();
  /** `undefined` = the list · `null` = a NEW tip · a string = that tip's
   *  editor. The editor REPLACES the list in the same segment: one screen id
   *  per view, one back link (BR-SHL-035), which is what `CWP-071 → CWP-072`
   *  and `CWP-074 → CWP-075` both already do. */
  const [open, setOpen] = useState<string | null | undefined>(undefined);
  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: "position",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  const query = useQuery({ queryKey: queryKeys.portalTips, queryFn: () => getTips(client) });
  /** ⚠ A write answers with the ROWS; the two closed sets cannot move, so the
   *  result is MERGED into the cached view rather than replacing it. Replacing
   *  it would empty `all_screens` and leave the editor's picker with nothing to
   *  offer — a silent, tsc-clean way to lose the six. */
  const mergeRows = (rows: TipRow[]) =>
    queryClient.setQueryData(queryKeys.portalTips, (old: TipsView | undefined) =>
      old === undefined ? old : { ...old, tips: rows },
    );
  const update = useMutation({
    mutationFn: (args: { id: string; is_on: boolean }) => saveTip(args.id, { is_on: args.is_on }, client),
    onSuccess: mergeRows,
  });
  const reorder = useMutation({
    mutationFn: (order: string[]) => reorderTips(order, client),
    onSuccess: mergeRows,
  });

  if (open !== undefined) {
    return (
      <PortalTipEditor
        tipId={open}
        readOnly={props.readOnly}
        client={client}
        onBack={() => setOpen(undefined)}
      />
    );
  }

  const all = query.data?.tips ?? [];

  function move(id: string, by: -1 | 1): void {
    const order = [...all].sort((a, b) => a.position - b.position).map((row) => row.id);
    const from = order.indexOf(id);
    const to = from + by;
    if (from < 0 || to < 0 || to >= order.length) return;
    order.splice(to, 0, ...order.splice(from, 1));
    reorder.mutate(order);
  }

  const reorderable = state.q === "" && state.sort === "position" && state.filters.showing === undefined;
  const filtered = all
    .filter((row) => {
      const wanted = state.filters.showing;
      if (wanted === undefined || wanted === "") return true;
      if (wanted === "showing_now") return row.showing_today;
      return row.month_from !== null || row.month_to !== null;
    })
    .filter((row) => state.q === "" || row.text.toLowerCase().includes(state.q.toLowerCase()));
  const sorted = [...filtered].sort((a, b) => {
    const dir = state.dir === "desc" ? -1 : 1;
    if (state.sort === "tip") return a.text.localeCompare(b.text) * dir;
    return (a.position - b.position) * dir;
  });
  const from = (state.page - 1) * state.per;
  const rows = sorted.slice(from, from + state.per);

  const config: TableConfig<TipRow> = {
    screenId: "CWP-073",
    getRowId: (row) => row.id,
    searchFields: ["text"],
    searchPlaceholder: "settings.portalTips.searchPlaceholder",
    defaultSort: { sort: "position", dir: "asc" },
    filters: [
      {
        name: "showing",
        label: t("settings.reference.col.status"),
        options: FILTERS.map((one) => ({ value: one, label: t(`settings.portalTips.filter.${one}`) })),
      },
    ],
    columns: [
      {
        key: "order",
        label: t("settings.portalTips.order"),
        // ⚠ **`RowAction`, NOT A `Button` WEARING A GLYPH** (B14 rule 15, PO
        // ruling 2026-08-20: *"the rule-15 glyph vocabulary is for TABLE
        // ACTIONS, not for buttons"* — `G37` names the breach by file and
        // line). These two ARE table actions; they were drawn as plain
        // buttons, which also meant a greyed chevron said nothing about WHY
        // it was grey. `reason` is the other half of the rule (BR-SHL-025).
        cell: (row: TipRow) => {
          const held = props.readOnly
            ? t("settings.readOnlyReason")
            : reorderable
              ? null
              : t("settings.portalTips.reorderHeld");
          return (
            <RowActions>
              <RowAction
                icon={<ChevronUpIcon />}
                label={t("settings.portalTips.moveUp")}
                reason={held}
                onClick={() => move(row.id, -1)}
              />
              <RowAction
                icon={<ChevronDownIcon />}
                label={t("settings.portalTips.moveDown")}
                reason={held}
                onClick={() => move(row.id, 1)}
              />
            </RowActions>
          );
        },
      },
      {
        key: "tip",
        label: t("settings.portalTips.column.tip"),
        identity: true,
        sortable: true,
        cell: (row: TipRow) => (
          <span data-tip-row={row.target_screen} data-showing={row.showing_today ? "yes" : "no"}>
            {row.text}
            {/* ⚠ ACCEPTED AND FLAGGED, never refused (US-CWP-073 TC-7): the
                fifteen-word guidance is ON THE SCREEN, not in a policy
                document nobody reads. `words`, not `count` — i18next reads
                `count` as a plural selector. */}
            {row.word_count > row.word_guidance ? (
              <StatusPill tone="warning">
                <span data-too-long={row.word_count}>
                  {t("settings.portalTips.tooLong", {
                    words: row.word_count,
                    guidance: row.word_guidance,
                  })}
                </span>
              </StatusPill>
            ) : null}
          </span>
        ),
      },
      {
        key: "where",
        label: t("settings.portalTips.column.where"),
        cell: (row: TipRow) => (
          <StatusPill tone="info">{t(`settings.portalTips.screen.${row.target_screen}`)}</StatusPill>
        ),
      },
      {
        key: "when",
        label: t("settings.portalTips.column.when"),
        cell: (row: TipRow) => (
          <span data-season="">
            {seasonText(row, language, t)}
            {/* ⚠ TWO INDEPENDENT REASONS, both shown (TC-3): a tip that is off
                AND out of season says so twice, because turning it on would
                still show nothing. */}
            {!row.in_season ? (
              <StatusPill tone="neutral">
                <span data-out-of-season="">{t("settings.portalTips.outOfSeason")}</span>
              </StatusPill>
            ) : null}
          </span>
        ),
      },
      {
        key: "status",
        label: t("settings.reference.col.status"),
        cell: (row: TipRow) => (
          <Switch
            on={row.is_on}
            label={row.text}
            onLabel={t("settings.portal.on")}
            offLabel={t("settings.portal.off")}
            disabled={update.isPending}
            reason={props.readOnly ? t("settings.readOnlyReason") : null}
            onChange={(on) => update.mutate({ id: row.id, is_on: on })}
            testKey={row.target_screen}
          />
        ),
      },
      {
        key: "actions",
        label: t("settings.reference.col.actions"),
        cell: (row: TipRow) => (
          <RowActions>
            <RowAction
              icon={<PencilIcon />}
              label={t("settings.portalTips.edit")}
              onClick={() => setOpen(row.id)}
            />
            {/* ⚠ B14 rule 6 colours the glyph and NOTHING else here — the
                destructive commit itself is behind the editor's confirm, which
                is where the consequence can be stated in a sentence. */}
            <RowAction
              icon={<TrashIcon />}
              danger
              label={t("settings.portalTips.remove")}
              reason={props.readOnly ? t("settings.readOnlyReason") : null}
              onClick={() => setOpen(row.id)}
            />
          </RowActions>
        ),
      },
    ],
  };

  return (
    <div data-screen="CWP-073" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Kicker>{t("settings.portal.kicker")}</Kicker>
          <h2 className="settings-frame-title">{t("settings.portalTips.title")}</h2>
          <p className="settings-frame-desc">{t("settings.portalTips.subtitle")}</p>
        </div>
        {/* ⚠ ONE PRIMARY (B14 rule 4 / BR-SHL-044), and it is LIVE. The drawing
            says *held*; that was true of the day it was drawn and is not true
            now — `08-screen-layouts.md` CWP-073 is amended and dated. */}
        <Button
          disabled={props.readOnly}
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => setOpen(null)}
          data-action="new-tip"
        >
          {t("settings.portalTips.addTip")}
        </Button>
      </header>
      <DataTable<TipRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={query.data === undefined ? null : filtered.length}
        loading={query.isPending}
        error={
          query.isError
            ? { reason: refusalText(t, query.error), onRetry: () => void query.refetch() }
            : null
        }
        empty={{
          title: t("settings.portalTips.emptyTitle"),
          helper: t("settings.portalTips.emptyHelper"),
          ctaLabel: t("settings.portalTips.addTip"),
          // ⚠ `ctaReason` IS GONE, and its absence is the fix. It read *"Writing
          // tips arrives later"* over an endpoint that had accepted a tip since
          // `2.138.0` — an honest sentence that had stopped being true.
          ctaReason: props.readOnly ? t("settings.readOnlyReason") : null,
          onCta: () => setOpen(null),
        }}
        filterBarSlot={<FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />}
      />
      <Note>{t("settings.portalTips.topOfListWins")}</Note>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Panel as="section" title={t("settings.portalTips.notAnAnswer")}>
          <p>{t("settings.portalTips.notAnAnswerSentence")}</p>
        </Panel>
        <Panel as="section" title={t("settings.portalTips.seasonal")}>
          <p>{t("settings.portalTips.seasonalSentence")}</p>
        </Panel>
      </div>
    </div>
  );
}
// ══ CWP-073 · the editor ═══════════════════════════════════════════════════
//
// ⚠ **THE DRAWING SAYS `+ New tip` **held** AND IT IS NO LONGER TRUE — read the
// amendment, not the drawing** (`08-screen-layouts.md` CWP-073, amended
// 2026-09-04). *Held* was an honest note about the day it was drawn: wave D
// landed the list, and `create_tip`, `update_tip` and `delete_tip` shipped with
// it — tested, routed, and reachable by nothing at all. A disabled button over
// a working endpoint is hard-won law 2 with the label on. The three row icons
// the drawing DOES draw live (`✎ 👁 −`) are here as two: ✎ and −, with 👁 folded
// into the editor as a LIVE preview, because the thing being previewed is one
// sentence and `CWP-070` already establishes that this product previews as you
// type rather than in a separate window.

/** The editor's own draft. `id === null` is a tip that does not exist yet. */
interface TipDraft {
  text: string;
  target_screen: string;
  month_from: number | null;
  month_to: number | null;
  is_on: boolean;
}

const NEW_TIP: TipDraft = {
  text: "",
  target_screen: "portal_home",
  month_from: null,
  month_to: null,
  // ⚠ Hard-won law 3: a new tip is OFF. The unsafe option — putting an
  // unreviewed sentence in front of every customer on that screen — is the one
  // somebody has to type.
  is_on: false,
};

function draftOfTip(row: TipRow): TipDraft {
  return {
    text: row.text,
    target_screen: row.target_screen,
    month_from: row.month_from,
    month_to: row.month_to,
    is_on: row.is_on,
  };
}

/** The count the fifteen-word guidance is measured against. ⚠ It is the SAME
 *  arithmetic the server does (`len(row.text.split())`), so the flag a clerk
 *  sees while typing and the flag on the list after saving cannot disagree. */
export function tipWordCount(text: string): number {
  return text.split(/\s+/).filter((one) => one !== "").length;
}

export function PortalTipEditor(props: {
  /** `null` = a NEW tip. */
  tipId: string | null;
  readOnly: boolean;
  client?: ApiClient;
  onBack: () => void;
}) {
  const { t, i18n } = useTranslation();
  const client = props.client ?? api;
  const language = i18n.language || "en";
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const query = useQuery({ queryKey: queryKeys.portalTips, queryFn: () => getTips(client) });
  const view = query.data;
  const row =
    props.tipId === null ? undefined : (view?.tips ?? []).find((one) => one.id === props.tipId);
  // ⚠ Seeded from the cache as well as by the effect — an effect never runs at
  // `renderToStaticMarkup`, which is what 200+ suites in this repo render with.
  const [draft, setDraft] = useState<TipDraft | null>(() =>
    props.tipId === null ? { ...NEW_TIP } : row === undefined ? null : draftOfTip(row),
  );
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    if (draft === null && row !== undefined) setDraft(draftOfTip(row));
  }, [row, draft]);

  const save = useMutation({
    mutationFn: (next: TipDraft) =>
      props.tipId === null ? createTip(next, client) : saveTip(props.tipId, next, client),
    onSuccess: (rows) => {
      queryClient.setQueryData(queryKeys.portalTips, (old: TipsView | undefined) =>
        old === undefined ? old : { ...old, tips: rows },
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.portalTips });
      fireToast(t("settings.portalTips.saved"));
      props.onBack();
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteTip(props.tipId ?? "", client),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.portalTips });
      props.onBack();
    },
  });

  if (query.isPending || draft === null) return <LoadingSkeleton variant="card" />;
  if (view === undefined) {
    return (
      <FailedWithRetry
        title={t("settings.portalTips.failedTitle")}
        reason={refusalText(t, query.error)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  const guidance = view.word_guidance;
  const words = tipWordCount(draft.text);
  const seasonal = draft.month_from !== null || draft.month_to !== null;
  const months = MONTH_NUMBERS.map((n) => ({
    value: String(n),
    label: new Intl.DateTimeFormat(language, { month: "long" }).format(new Date(2024, n - 1, 1)),
  }));

  function setSeasonal(on: boolean): void {
    if (draft === null) return;
    // ⚠ A season is a PAIR or it is nothing. Half a range would let a tip
    // stop appearing for a reason the screen never shows — the two-reasons
    // rule (US-CWP-073 TC-3) read backwards.
    setDraft(on ? { ...draft, month_from: 6, month_to: 9 } : { ...draft, month_from: null, month_to: null });
  }

  return (
    <div data-screen="CWP-073-editor" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Button variant="ghost" onClick={props.onBack} data-back="tips">
            ← {t("settings.portalTips.title")}
          </Button>
          <h2 className="settings-frame-title">
            {props.tipId === null ? t("settings.portalTips.addTip") : t("settings.portalTips.editTitle")}
          </h2>
          <p className="settings-frame-desc">{t("settings.portalTips.editSubtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {props.tipId === null ? null : (
            // ⚠ B14 RULE 6: the danger tier, and only here. A tip is the one
            // record on these four screens with no *hidden* to prefer over
            // removal — `Showing` IS that state — so the switch below is the
            // gentler act and this button is the destructive one.
            <Button
              variant="danger"
              disabled={props.readOnly || remove.isPending}
              onClick={() => setConfirming(true)}
              data-action="remove"
            >
              {t("settings.portalTips.remove")}
            </Button>
          )}
          <Button
            onClick={() => save.mutate(draft)}
            disabled={props.readOnly || save.isPending || draft.text.trim() === ""}
            data-action="save"
          >
            {t("settings.portalTips.save")}
          </Button>
        </div>
      </header>
      <RefusalNotice refusal={save.isError ? refusalOf(save.error, t) : null} />
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-col gap-4 md:col-span-8">
          <Panel as="section" title={t("settings.portalTips.theTip")}>
            <label className="block">
              <span className="mb-1 block text-md font-semibold">{t("settings.portalTips.column.tip")}*</span>
              <textarea
                className="min-h-24 w-full resize-y border border-field-border bg-bg px-3 py-2 text-md"
                value={draft.text}
                readOnly={props.readOnly}
                onChange={(e) => setDraft({ ...draft, text: e.target.value })}
                data-field="text"
              />
            </label>
            {/* ⚠ **US-CWP-073 TC-7 SAYS *IN THE EDITOR*, AND THIS IS THAT
                LINE.** A thirty-word tip is ACCEPTED — nothing here refuses it,
                and `Save` stays live — and it is FLAGGED while it is being
                typed, because *"the rule is on the screen, not in a policy
                document nobody reads"*. The list flags it too; this is where a
                clerk can still do something about it. */}
            {words > guidance ? (
              <StatusPill tone="warning">
                <span data-editor-too-long={words}>
                  {t("settings.portalTips.tooLong", { words, guidance })}
                </span>
              </StatusPill>
            ) : (
              <p className="mt-2 text-md text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]" data-editor-words={words}>
                {t("settings.portalTips.wordsSoFar", { words, guidance })}
              </p>
            )}
          </Panel>
          <Panel as="section" title={t("settings.portalTips.column.where")}>
            <label className="block">
              <span className="mb-1 block text-md font-semibold">{t("settings.portalTips.column.where")}*</span>
              {/* ⚠ **THE SIX COME FROM THE SERVER** (`all_screens`). Typing
                  them out here is the SignupWizard trap in CLAUDE.md's first
                  paragraph: a seventh screen would exist in the database, be
                  served by the API, pass `tsc` and every test, and never once
                  be offered to a clerk. */}
              <select
                className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                value={draft.target_screen}
                disabled={props.readOnly}
                onChange={(e) => setDraft({ ...draft, target_screen: e.target.value })}
                data-field="target_screen"
              >
                {view.all_screens.map((screen) => (
                  <option key={screen} value={screen}>
                    {t(`settings.portalTips.screen.${screen}`)}
                  </option>
                ))}
              </select>
            </label>
            <Note>{t("settings.portalTips.onePerScreen")}</Note>
          </Panel>
          <Panel as="section" title={t("settings.portalTips.column.when")}>
            <div className="flex items-center justify-between gap-3">
              <span>{t("settings.portalTips.seasonalRange")}</span>
              <Switch
                on={seasonal}
                label={t("settings.portalTips.seasonalRange")}
                onLabel={t("settings.portalTips.filter.seasonal")}
                offLabel={t("settings.portalTips.allYear")}
                reason={props.readOnly ? t("settings.readOnlyReason") : null}
                onChange={setSeasonal}
                testKey="seasonal"
              />
            </div>
            {seasonal ? (
              <div className="mt-4 grid grid-cols-2 gap-4">
                <label className="block">
                  <span className="mb-1 block text-md font-semibold">{t("settings.portalTips.monthFrom")}</span>
                  <select
                    className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                    value={String(draft.month_from ?? 1)}
                    disabled={props.readOnly}
                    onChange={(e) => setDraft({ ...draft, month_from: Number(e.target.value) })}
                    data-field="month_from"
                  >
                    {months.map((one) => (
                      <option key={one.value} value={one.value}>
                        {one.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1 block text-md font-semibold">{t("settings.portalTips.monthTo")}</span>
                  <select
                    className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                    value={String(draft.month_to ?? 12)}
                    disabled={props.readOnly}
                    onChange={(e) => setDraft({ ...draft, month_to: Number(e.target.value) })}
                    data-field="month_to"
                  >
                    {months.map((one) => (
                      <option key={one.value} value={one.value}>
                        {one.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}
            {/* ⚠ A WRAPPING RANGE IS LAWFUL AND THE SCREEN SAYS SO — December
                to February is the fixture's freeze tip, and `month_from >
                month_to` is how the year is crossed. */}
            <Note>{t("settings.portalTips.seasonalSentence")}</Note>
          </Panel>
        </div>
        <div className="col-span-12 flex flex-col gap-4 md:col-span-4">
          <Panel as="section" title={t("settings.reference.col.status")}>
            <div className="flex items-center justify-between gap-3">
              <span>{t("settings.portalTips.showing")}</span>
              <Switch
                on={draft.is_on}
                label={t("settings.portalTips.showing")}
                onLabel={t("settings.portal.on")}
                offLabel={t("settings.portal.off")}
                reason={props.readOnly ? t("settings.readOnlyReason") : null}
                onChange={(on) => setDraft({ ...draft, is_on: on })}
                testKey="tip-on"
              />
            </div>
            <p className="mt-2 text-md text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
              {t("settings.portalTips.offIsAState")}
            </p>
          </Panel>
          {/* ⚠ **THE PREVIEW IS THE CUSTOMER'S OWN COMPONENT, NOT A DRAWING OF
              IT.** `TipBar` is what `CWP-033` and the rest render; importing it
              is the same posture `CWP-070` takes with `FrontPageView`, and it
              means the preview cannot drift from the real thing by being
              maintained separately. An empty tip previews as NOTHING, which is
              `BR-CWP-093` visible in the editor: the slot closes up. */}
          <Panel as="section" title={t("settings.portalTips.preview")}>
            {draft.text.trim() === "" ? (
              <p className="text-md text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]" data-preview-empty="">
                {t("settings.portalTips.previewEmpty")}
              </p>
            ) : (
              <TipBar
                tip={{ text: draft.text, target_screen: draft.target_screen }}
                dismissLabel={t("settings.portalTips.dismiss")}
                onDismiss={undefined}
              />
            )}
          </Panel>
        </div>
      </div>
      {confirming ? (
        <ConfirmDialog
          title={t("settings.portalTips.removeTitle")}
          consequence={t("settings.portalTips.removeWarning")}
          confirmLabel={t("settings.portalTips.remove")}
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
