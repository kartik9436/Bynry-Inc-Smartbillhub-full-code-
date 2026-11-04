// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-071 (EP-CWP-12) — help and answers in the back office:
//           draft, translate, publish. Screens: CWP-071 · CWP-072
// Rules:    08-screen-layouts.md CWP-071 (T8 + T5: toolbar *All | Published |
//           Draft | Needs translating* · leading reorder handle · Question /
//           Topic / Status / Languages / Read this month · *The order here is
//           the order on the portal*) and CWP-072 (T8 + T6 + TwoCol: the form ·
//           LANGUAGES MiniTable · rail WHERE IT APPEARS + Panel.Warning
//           publishing is immediate) · BR-CWP-094 · B14 rule 15 (row actions
//           are ICONS) · rule 21 (this file goes on route-b-migrated.txt in
//           the commit that creates it) · rule 31 (no id is a visible value —
//           an answer is addressed by SLUG) · rule 32 (one sentence a section)
// Tests:    src/features/tenancy/SettingsPortalHelp.test.tsx
// Impacts:  src/api/publishedContentEndpoints.ts · SettingsCustomerPortalTab.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ A STAFF SCREEN with a CWP number, because the blueprint drew it — it lives
// in the staff app's Settings and never behind a customer login (EP-CWP-12).
//
// ⚠ THE BOUNDARY, ONCE AND ON NO SCREEN: `OQ-1398` — who keeps the answers
// current and in how many languages — is OPEN. This screen SHOWS which
// languages are missing and offers no workflow: nothing here assigns a
// translation, chases one, or promises that anybody will do it. A screen that
// implied otherwise would be answering an open question for the Product Owner.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  createHelpAnswer,
  getHelpAnswer,
  getHelpAnswers,
  publishHelpAnswer,
  reorderHelpAnswers,
  saveHelpAnswer,
} from "@/api/publishedContentEndpoints";
import type { AnswerStatus, HelpAnswerDetail, HelpAnswerRow } from "@/api/publishedContentEndpoints";
import { queryKeys } from "@/api/queryClient";
import { languageName } from "@/portal/components/languageName";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Panel } from "@/components/Panel";
import { FilterBar } from "@/components/FilterBar";
import { ChevronDownIcon, ChevronUpIcon, PencilIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Kicker, Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";

const STATUS_TONE: Record<AnswerStatus, "success" | "warning" | "neutral"> = {
  published: "success",
  draft: "warning",
  not_shown: "neutral",
};

/** The toolbar's four (08-screen-layouts.md CWP-071). */
const FILTERS = ["all", "published", "draft", "needs_translating"] as const;

const TOPICS = ["billing", "paying", "readings", "water", "moving"] as const;
/** ⚠ `null` is *the help list only* — the first option, and the default. */
const ALSO_SHOW = ["bill", "usage", "overdue"] as const;

/** The shared `Panel` — B14 rule 36: one component, one visual decision. The
 *  first draft of this file wrote its own bordered `<section>`, which is how
 *  four screens acquire four different panels. */

// ══ CWP-071 · the list ═════════════════════════════════════════════════════
//
// ⚠ **THE SHARED `DataTable`, NOT A HAND-ROLLED TABLE (B14 rule 36).** The
// first draft of this screen wrote its own `<table>`, its own filter buttons
// and no pagination footer at all — which is breach (c) of rule 36 in a new
// file, one day after the rule. The kit carries r10 rules 12 (toolbar), 13
// (sortable headers), 14 (column chooser), 16 (pagination footer) and 17
// (empty state) in one component; composing it is the only way to get all five
// right at once and keep them right when they change.
//
// ⚠ **THE REORDER CONTROLS ARE A LEADING COLUMN, NOT ROW ACTIONS.** r10 rule
// 15 caps the ACTIONS cell at two icons plus an overflow, and the wireframe
// draws reordering as its own leading `⋮⋮` handle column — so ↑/↓ live there
// (kit `Button size="row"`, the same geometry the column chooser's own reorder
// uses) and the actions cell holds one icon: ✎.

export function PortalHelpList(props: { readOnly: boolean; client?: ApiClient; onOpen: (slug: string) => void }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: "position",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  const [adding, setAdding] = useState(false);
  const query = useQuery({ queryKey: queryKeys.portalHelp, queryFn: () => getHelpAnswers(client) });
  const reorder = useMutation({
    mutationFn: (order: string[]) => reorderHelpAnswers(order, client),
    onSuccess: (rows) => queryClient.setQueryData(queryKeys.portalHelp, rows),
  });

  const all = query.data ?? [];

  /** Move one row by one place. The ORDER is what matters — the order here is
   *  the order on the portal (US-CWP-071 TC-5) — so the move is computed over
   *  the WHOLE list and never over the page a clerk happens to be looking at. */
  function move(slug: string, by: -1 | 1): void {
    const order = [...all].sort((a, b) => a.position - b.position).map((row) => row.slug);
    const from = order.indexOf(slug);
    const to = from + by;
    if (from < 0 || to < 0 || to >= order.length) return;
    order.splice(to, 0, ...order.splice(from, 1));
    reorder.mutate(order);
  }

  const reorderable = state.q === "" && state.sort === "position" && state.filters.status === undefined;
  const filtered = all
    .filter((row) => {
      const wanted = state.filters.status;
      if (wanted === undefined || wanted === "") return true;
      if (wanted === "needs_translating") return row.needs_translating > 0;
      return row.status === wanted;
    })
    .filter((row) => state.q === "" || row.question.toLowerCase().includes(state.q.toLowerCase()));
  const sorted = [...filtered].sort((a, b) => {
    const dir = state.dir === "desc" ? -1 : 1;
    if (state.sort === "reads") return (a.reads_this_month - b.reads_this_month) * dir;
    if (state.sort === "question") return a.question.localeCompare(b.question) * dir;
    return (a.position - b.position) * dir;
  });
  const from = (state.page - 1) * state.per;
  const rows = sorted.slice(from, from + state.per);

  const config: TableConfig<HelpAnswerRow> = {
    screenId: "CWP-071",
    getRowId: (row) => row.slug,
    searchFields: ["question"],
    searchPlaceholder: "settings.portalHelp.searchPlaceholder",
    defaultSort: { sort: "position", dir: "asc" },
    filters: [
      {
        name: "status",
        label: t("settings.reference.col.status"),
        options: FILTERS.filter((one) => one !== "all").map((one) => ({
          value: one,
          label: t(`settings.portalHelp.filter.${one}`),
        })),
      },
    ],
    columns: [
      {
        key: "order",
        label: t("settings.portalHelp.order"),
        cell: (row: HelpAnswerRow) => (
          //: B14 rule 15 — the glyph vocabulary is for TABLE ACTIONS (PO ruling
          //: 2026-08-20: *"not for buttons"*), and these two ARE table actions:
          //: one pair per row, moving that row in the list. They were a pair of
          //: ghost `Button`s carrying chevrons, which `G37` correctly refused.
          //: The kit's own `RowAction` is what rule 15 means, and this file was
          //: already using it eighty lines below.
          //:
          //: ⚠ **AND `reason` MAKES THE READ-ONLY CASE SAY SOMETHING, WHICH THE
          //: `disabled` PROP COULD NOT.** The old control was disabled for two
          //: different facts — read-only, and a filtered list that cannot be
          //: reordered — and its tooltip named only the second, so a clerk
          //: without permission got a dead control and no explanation.
          //: `RowAction`'s `reason` disables AND explains (`BR-SHL-025`), so
          //: the two are now told apart.
          <RowActions>
            <RowAction
              label={t("settings.portalHelp.moveUp")}
              icon={<ChevronUpIcon />}
              reason={
                props.readOnly
                  ? t("settings.readOnlyReason")
                  : reorderable
                    ? null
                    : t("settings.portalHelp.reorderInAll")
              }
              onClick={() => move(row.slug, -1)}
            />
            <RowAction
              label={t("settings.portalHelp.moveDown")}
              icon={<ChevronDownIcon />}
              reason={
                props.readOnly
                  ? t("settings.readOnlyReason")
                  : reorderable
                    ? null
                    : t("settings.portalHelp.reorderInAll")
              }
              onClick={() => move(row.slug, 1)}
            />
          </RowActions>
        ),
      },
      {
        key: "question",
        label: t("settings.portalHelp.column.question"),
        identity: true,
        sortable: true,
        cell: (row: HelpAnswerRow) => <span data-answer-row={row.slug}>{row.question}</span>,
      },
      {
        key: "topic",
        label: t("settings.portalHelp.column.topic"),
        cell: (row: HelpAnswerRow) => t(`portal.help.topic.${row.topic}`),
      },
      {
        key: "status",
        label: t("settings.reference.col.status"),
        cell: (row: HelpAnswerRow) => (
          <span data-answer-status={row.status}>
            <StatusPill tone={STATUS_TONE[row.status]}>
              {t(`settings.portalHelp.status.${row.status}`)}
            </StatusPill>
          </span>
        ),
      },
      {
        key: "languages",
        label: t("settings.portalHelp.column.languages"),
        cell: (row: HelpAnswerRow) => (
          // ⚠ `whitespace-nowrap` because B14 rule 36's own finding is a
          // column narrow enough to wrap `10 of 11` over two lines — and this
          // wave's walkthrough caught exactly that, on this cell.
          <span className="whitespace-nowrap" data-languages={row.slug}>
            {t("settings.portalHelp.languagesOf", {
              published: row.languages_published,
              total: row.languages_total,
            })}
          </span>
        ),
      },
      {
        // ⚠ THE COLUMN THAT MAKES THIS A TOOL AND NOT A CHORE: a question read
        // 1,204 times a month is a BILL DESIGN problem, not a help problem.
        key: "reads",
        label: t("settings.portalHelp.column.reads"),
        numeric: true,
        sortable: true,
        cell: (row: HelpAnswerRow) => (
          <span data-reads={row.slug}>
            {row.reads_this_month > 0 ? row.reads_this_month.toLocaleString() : "—"}
          </span>
        ),
      },
      {
        key: "actions",
        label: t("settings.reference.col.actions"),
        cell: (row: HelpAnswerRow) => (
          <RowActions>
            <RowAction
              icon={<PencilIcon />}
              label={t("settings.portalHelp.edit")}
              onClick={() => props.onOpen(row.slug)}
            />
          </RowActions>
        ),
      },
    ],
  };

  return (
    <div data-screen="CWP-071" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Kicker>{t("settings.portal.kicker")}</Kicker>
          <h2 className="settings-frame-title">{t("settings.portalHelp.title")}</h2>
          <p className="settings-frame-desc">{t("settings.portalHelp.subtitle")}</p>
        </div>
        {/* ⚠ ONE PRIMARY (B14 rule 4 / BR-SHL-044), AND IT IS LIVE — and until
            this commit it did not exist at all. The ONLY way to reach
            `create_answer` was the empty state's CTA, which is drawn only when
            a tenant has no answers: a utility that wrote one answer could
            never write a second. `DEF-CWP-3824`, and the sibling tips screen
            had the same pair of faults (`DEF-CWP-3820`). */}
        <Button
          disabled={props.readOnly}
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => setAdding(true)}
          data-action="new-answer"
        >
          {t("settings.portalHelp.addAnswer")}
        </Button>
      </header>
      <DataTable<HelpAnswerRow>
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
          title: t("settings.portalHelp.emptyTitle"),
          helper: t("settings.portalHelp.emptyHelper"),
          ctaLabel: t("settings.portalHelp.addAnswer"),
          // ⚠ `ctaReason` READ *"Writing answers arrives later"* AND ITS
          // ABSENCE IS THE FIX. R3 holds a control until its screen lands;
          // `create_answer` landed with wave D (`2.138.0`), routed, audited
          // and tested, and the sentence went on being displayed over it for
          // two days because releasing a control and landing the thing behind
          // it are two acts (`DEF-CWP-3824`). `G103` now fails a hold whose
          // symbol is served, so this exact sentence cannot come back.
          ctaReason: props.readOnly ? t("settings.readOnlyReason") : null,
          onCta: () => setAdding(true),
        }}
        filterBarSlot={<FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />}
      />
      <Note>{t("settings.portalHelp.orderIsPortalOrder")}</Note>
      {adding ? (
        <NewAnswerModal
          client={client}
          onClose={() => setAdding(false)}
          onCreated={(slug) => {
            setAdding(false);
            props.onOpen(slug);
          }}
        />
      ) : null}
    </div>
  );
}

/**
 * `+ New answer` — two fields and a draft (IS-1: a quick add is a modal, a
 * guided form is a page). The ANSWER TEXT is not asked for here: it is written
 * per language on `CWP-072`, which is where the language table lives, so the
 * modal ends by opening the editor on the row it just made.
 *
 * ⚠ **IT MINTS NO NEW COPY.** Every label is a key the eleven catalogues
 * already hold — `addAnswer`, `field.question`, `field.topic`,
 * `portal.help.topic.*` — because a door is best named after the thing it
 * opens (the shape `WhereNext` already took), and because a new sentence here
 * would be eleven translations for a form that says what the editor says.
 */
function NewAnswerModal(props: {
  client: ApiClient;
  onClose: () => void;
  onCreated: (slug: string) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState("");
  const [topic, setTopic] = useState<string>(TOPICS[0]);
  const schema = z.object({
    question: z.string().trim().min(1, t("settings.portalHelp.field.question")),
  });
  return (
    <FormModal
      title={t("settings.portalHelp.addAnswer")}
      kicker={t("settings.portal.kicker")}
      schema={schema}
      values={{ question }}
      submitLabel={t("settings.portalHelp.addAnswer")}
      onClose={props.onClose}
      onSubmit={async () => {
        const made = await createHelpAnswer({ question, topic }, props.client);
        void queryClient.invalidateQueries({ queryKey: queryKeys.portalHelp });
        props.onCreated(made.slug);
        return { ok: true };
      }}
    >
      <TextField
        id="question"
        label={t("settings.portalHelp.field.question")}
        value={question}
        onChange={setQuestion}
        required
      />
      <SelectField
        id="topic"
        label={t("settings.portalHelp.field.topic")}
        value={topic}
        onChange={setTopic}
        options={TOPICS.map((one) => ({ value: one, label: t(`portal.help.topic.${one}`) }))}
      />
    </FormModal>
  );
}

// ══ CWP-072 · the editor ═══════════════════════════════════════════════════

export function PortalHelpEditor(props: {
  slug: string;
  readOnly: boolean;
  client?: ApiClient;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const query = useQuery({
    queryKey: [...queryKeys.portalHelp, props.slug],
    queryFn: () => getHelpAnswer(props.slug, client),
  });
  // ⚠ SEEDED FROM THE CACHE AS WELL AS BY THE EFFECT. An effect alone never
  // runs at `renderToStaticMarkup`, so a draft that waited for one would be a
  // skeleton the test suite cannot see past — wave A's Branding screen records
  // the same trap in the same words.
  const [draft, setDraft] = useState<{ question: string; topic: string; also: string; body: string } | null>(() =>
    query.data === undefined
      ? null
      : {
          question: query.data.question,
          topic: query.data.topic,
          also: query.data.also_show_on_screen ?? "",
          body: query.data.body,
        },
  );
  useEffect(() => {
    if (query.data !== undefined && draft === null) {
      setDraft({
        question: query.data.question,
        topic: query.data.topic,
        also: query.data.also_show_on_screen ?? "",
        body: query.data.body,
      });
    }
  }, [query.data, draft]);
  const save = useMutation({
    mutationFn: (next: NonNullable<typeof draft>) =>
      saveHelpAnswer(
        props.slug,
        {
          question: next.question,
          topic: next.topic,
          also_show_on_screen: next.also === "" ? null : next.also,
          variants: { en: next.body },
        },
        client,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData([...queryKeys.portalHelp, props.slug], data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.portalHelp });
      fireToast(t("settings.portalHelp.saved"));
    },
  });
  const publish = useMutation({
    mutationFn: (status: AnswerStatus) => publishHelpAnswer(props.slug, status, client),
    onSuccess: (data) => {
      queryClient.setQueryData([...queryKeys.portalHelp, props.slug], data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.portalHelp });
      fireToast(t("settings.portalHelp.published"));
    },
  });

  if (query.isPending || draft === null) return <LoadingSkeleton variant="card" />;
  if (query.data === undefined) {
    return (
      <FailedWithRetry
        title={t("settings.portalHelp.failedTitle")}
        reason={refusalText(t, query.error)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }
  const data: HelpAnswerDetail = query.data;
  return (
    <div data-screen="CWP-072" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Button variant="ghost" onClick={props.onBack} data-back="help">
            ← {t("settings.portalHelp.title")}
          </Button>
          <h2 className="settings-frame-title">{data.question}</h2>
          <p className="settings-frame-desc">
            {t(`settings.portalHelp.status.${data.status}`)}
            {data.last_changed_by ? ` · ${t("settings.portalHelp.lastChangedBy", { who: data.last_changed_by })}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => save.mutate(draft)}
            disabled={props.readOnly || save.isPending}
            data-action="save"
          >
            {t("settings.portalHelp.save")}
          </Button>
          <Button
            onClick={() => publish.mutate(data.status === "published" ? "not_shown" : "published")}
            disabled={props.readOnly || publish.isPending}
            data-action="publish"
          >
            {data.status === "published"
              ? t("settings.portalHelp.unpublish")
              : t("settings.portalHelp.publish")}
          </Button>
        </div>
      </header>
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-col gap-4 md:col-span-8">
          <section className="border border-divider bg-bg p-4">
            <label className="block">
              <span className="mb-1 block text-md font-semibold">
                {t("settings.portalHelp.field.question")}*
              </span>
              <input
                className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                value={draft.question}
                readOnly={props.readOnly}
                onChange={(e) => setDraft({ ...draft, question: e.target.value })}
                data-field="question"
              />
            </label>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <label className="block">
                <span className="mb-1 block text-md font-semibold">
                  {t("settings.portalHelp.field.topic")}
                </span>
                <select
                  className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                  value={draft.topic}
                  disabled={props.readOnly}
                  onChange={(e) => setDraft({ ...draft, topic: e.target.value })}
                  data-field="topic"
                >
                  {TOPICS.map((one) => (
                    <option key={one} value={one}>
                      {t(`portal.help.topic.${one}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-md font-semibold">
                  {t("settings.portalHelp.field.alsoShowOn")}
                </span>
                <select
                  className="h-11 w-full border border-field-border bg-bg px-3 text-md"
                  value={draft.also}
                  disabled={props.readOnly}
                  onChange={(e) => setDraft({ ...draft, also: e.target.value })}
                  data-field="also_show_on_screen"
                >
                  <option value="">{t("settings.portalHelp.alsoShowOn.none")}</option>
                  {ALSO_SHOW.map((one) => (
                    <option key={one} value={one}>
                      {t(`settings.portalHelp.alsoShowOn.${one}`)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="mt-4 block">
              <span className="mb-1 block text-md font-semibold">
                {t("settings.portalHelp.field.answer")}*
              </span>
              <textarea
                className="min-h-40 w-full resize-y border border-field-border bg-bg px-3 py-2 text-md"
                value={draft.body}
                readOnly={props.readOnly}
                onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                data-field="body"
              />
            </label>
          </section>
          <Panel as="section" title={t("settings.portalHelp.languages")}>
            <table className="w-full text-md" data-language-table="">
              <thead>
                <tr className="text-left text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
                  <th className="py-2" scope="col">{t("settings.portalHelp.column.language")}</th>
                  <th className="py-2" scope="col">{t("settings.reference.col.status")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                {data.variants.map((row) => (
                  <tr key={row.locale} data-variant={row.locale}>
                    <td className="py-2 font-semibold">{languageName(row.locale)}</td>
                    <td className="py-2">
                      <span data-variant-status={row.status}>
                        <StatusPill tone={row.status === "published" ? "success" : "warning"}>
                          {t(`settings.portalHelp.variant.${row.status}`)}
                        </StatusPill>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* ⚠ THE BOUNDARY, SAID PLAINLY AND WITHOUT PROMISING ANYTHING.
                OQ-1398 is open; this sentence states what the state MEANS and
                offers no workflow. */}
            <p className="mt-3 text-md text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{t("settings.portalHelp.languagesNote")}</p>
          </Panel>
        </div>
        <div className="col-span-12 flex flex-col gap-4 md:col-span-4">
          <Panel as="section" title={t("settings.portalHelp.whereItAppears")}>
            <dl>
              <div className="flex justify-between gap-3 border-b border-divider py-2">
                <dt className="text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{t("settings.portalHelp.where.helpPage")}</dt>
                <dd className="font-semibold">{t(`settings.portalHelp.status.${data.status}`)}</dd>
              </div>
              <div className="flex justify-between gap-3 border-b border-divider py-2">
                <dt className="text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{t("settings.portalHelp.where.alsoOn")}</dt>
                <dd className="font-semibold" data-where-also="">
                  {data.also_show_on_screen
                    ? t(`settings.portalHelp.alsoShowOn.${data.also_show_on_screen}`)
                    : t("settings.portalHelp.alsoShowOn.none")}
                </dd>
              </div>
              <div className="flex justify-between gap-3 py-2">
                <dt className="text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{t("settings.portalHelp.where.reads")}</dt>
                <dd className="font-semibold tabular-nums" data-editor-reads="">
                  {data.reads_this_month.toLocaleString()}
                </dd>
              </div>
            </dl>
          </Panel>
          {/* ⚠ US-CWP-071 TC-9: publishing changes what customers read STRAIGHT
              AWAY and there is no approval step — and the screen says so. The
              server sends the fact; this panel does not assume it. */}
          {data.publish_is_immediate && !data.has_approval_step ? (
            <Panel as="section" accent title={t("settings.portalHelp.beforeYouPublish")}>
              <p data-publish-warning="">{t("settings.portalHelp.publishWarning")}</p>
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}
