// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F2–F7 — the template workspace (SET-10, redrawn)
//           `02`–`18`, `20`, `22`
// Rules:    BR-NOT-001 · BR-NOT-005 · BR-BIL-026 · BR-BIL-027 · BR-SHL-011 ·
//           BR-SHL-025 · PO rulings A1 C · A2 A · A3 A · A4 B · B (2026-10-29)
//           · B14 rules 2 · 15 · 31 · 32 · 33 · 36 · 41 · 42 · 43 · 44
// ───────────────────────────────────────────────────────
// ONE TEMPLATE, AS THE REDESIGN DRAWS IT:
//
//   ← Templates
//   TEMPLATE · BILLING
//   Bill ready                               (32px, the kit's page head)
//   Sent when a bill is issued. · Last edited …
//   [Channel ▾] [Language ▾] [Customers ▾]
//   Sent in each customer's preferred language … · English · 9,120 customers
//   ┌ status line · View · Edit wording · Duplicate · + New variant ‖ History ·
//   │ Send test · Save draft · Publish
//   └
//   [warnings: a placeholder that can't be filled · a bare link]
//   ┌ Wording ──────────────┐ ┌ Preview ───────────────┐
//   └───────────────────────┘ └────────────────────────┘
//   Variant (Deactivate · the way back)
//
// ⚠ **THIS IS A REDESIGN OF A LIVE SCREEN, SO IT IS MAINTENANCE** — and PO
// defect #4 was *"earlier actions removed"*. Every action the screen offered
// on 2026-10-29 is listed in `CR-199-BRC10` §6 with where it now lives, and
// `templateNothingRemoved.dom.test.tsx` asserts each one by its control.
//
// ⚠ **EVERY PIECE IS A COMPONENT (B14 rule 43)** — the pickers, the bar, the
// wording pane, the placeholder picker, the preview, the variant form and the
// history are each their own file. This one only holds the template's state
// and wires them together; it draws nothing a component does not.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import {
  createTemplateVariant,
  getTemplateDetail,
  getTemplateLanguageCounts,
  getTemplateVariantOptions,
  makeTemplateLiveAgain,
  publishTemplateVersion,
  queueTemplateTest,
  saveTemplateDraft,
} from "@/api/endpoints";
import type {
  TemplateBodyFormat,
  TemplateCatalogRow,
  TemplateDetail,
  TemplateTestResult,
  TemplateVariantOptions,
  TemplateVariantRow,
  TemplateWordingIssue,
} from "@/api/endpoints";
import { WarningBox } from "@/components/WarningBox";
import { queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { Panel, RefusalNotice, apiErrorText, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { languageName } from "@/portal/components/languageName";
import {
  ControlNote,
  HeadMeta,
  PlatformDefaultOffer,
  VARIANT_STATE_KEY,
  VariantLifecycle,
  designerKind,
  variantStateOf,
  editorSource,
  previewSurfaces,
} from "./TemplateDetail";
import { TemplateActionBar } from "./TemplateActionBar";
import type { BarControl } from "./TemplateActionBar";
import { TemplateHistoryDialog } from "./TemplateHistoryDialog";
import { TemplateLivePreview, useLivePreview } from "./TemplateLivePreview";
import { TemplateVariantDialog } from "./TemplateVariantDialog";
import { TemplateVariantPickers } from "./TemplateVariantPickers";
import type { PickerOption } from "./TemplateVariantPickers";
import { TemplateWordingPane } from "./TemplateWordingPane";
import type { RichSyntax } from "./TemplateWordingPane";
import { testResultSentence } from "./testResultSentence";
import { DESIGNER_FRAME } from "./notificationsKit";
import {
  WORKSPACE_DIALOG_PARAM,
  WORKSPACE_EDIT,
  WORKSPACE_HISTORY,
  WORKSPACE_MODE_PARAM,
  WORKSPACE_VIEW_PARAM,
  workspaceDialogOf,
} from "./templateWorkspaceParams";
import type { WorkspaceDialog } from "./templateWorkspaceParams";

/** CR-199-BRC10 §5b (`BR-NOT-1042`) — the ONE closed markup the server stores
 *  and renders: `**bold**` · `[label](target)` · `[[label|target]]` · `- item`.
 *  The toolbar writes exactly these and nothing else; the server parses them
 *  and never accepts HTML. Spelt here once, from the contract. */
export const RICH_SYNTAX: RichSyntax = {
  bold: (text) => `**${text}**`,
  link: (text, href) => `[${text}](${href})`,
  button: (text, href) => `[[${text}|${href}]]`,
  listItem: (text) => `- ${text}`,
};

/** BR-NOT-001's four consumer categories plus the mandatory `default` — the
 *  Customers axis ONLY while `variant-options` has not answered (or refused).
 *  The served list is the utility's own customer classes (`CR-199-BRC10` §5). */
export const CUSTOMER_CATEGORIES = [
  "default",
  "residential",
  "commercial",
  "industrial",
  "government",
] as const;

export interface WorkspaceAxes {
  channels: PickerOption[];
  languages: PickerOption[];
  customers: PickerOption[];
  channelLabel: string;
  /** The utility's own language, named — where an unwritten one falls back. */
  utilityLanguage: string | null;
}

/** A language value as a person reads it: `default` is the utility's own. */
function languageLabel(
  value: string,
  options: TemplateVariantOptions | undefined,
  t: (key: string, vars?: Record<string, unknown>) => string,
): string {
  const served = options?.languages.find((row) => row.value === value);
  const code = served?.code ?? (value === "default" ? null : value);
  return code === null || code === ""
    ? t("templates.workspace.defaultLanguage")
    : languageName(code);
}

/** The three pickers' options: the channels from the catalogue page, the
 *  languages and customer classes from `variant-options` (PO rulings A3 A,
 *  A4 B), each language marked *not written yet* where THIS customer category
 *  has no variant in it (`18`). */
export function workspaceAxes(
  data: TemplateDetail,
  code: string,
  surfaces: readonly TemplateCatalogRow[],
  options: TemplateVariantOptions | undefined,
  customer: string,
  t: (key: string, vars?: Record<string, unknown>) => string,
  /** The language of the variant already open, so a link to it still shows. */
  current = "",
): WorkspaceAxes {
  const channelWord = (channel: string | null) =>
    t(`templates.channel.${channel ?? "pdf_print"}`, { defaultValue: channel ?? "" });
  const channels =
    surfaces.length > 0
      ? surfaces.map((row) => ({ value: row.code, label: channelWord(row.channel) }))
      : [{ value: code, label: channelWord(data.channel) }];

  /* ⚠ DEF-NOT-10676 — THE SWITCHED-ON LANGUAGES AND NOTHING ELSE (PO A4 B).
     The platform seeds every class in twelve languages, so adding each
     variant's language here offered thirteen on an English utility — and the
     seeded `en-US` variant read "American English" a second time beside the
     utility's own. Only the variant ALREADY OPEN may add its language, so a
     link to it still shows what it is; never one whose code is the utility's. */
  const values: string[] = [];
  for (const row of options?.languages ?? []) values.push(row.value);
  const ownCode = options?.languages.find((row) => row.is_utility_language)?.code ?? null;
  if (current !== "" && !values.includes(current) && current !== ownCode) values.push(current);
  const languages = values.map((value) => {
    const label = languageLabel(value, options, t);
    const written = data.variants.some(
      (variant) => variant.language === value && variant.category === customer,
    );
    return {
      value,
      label: written ? label : t("templates.workspace.notWrittenYet", { language: label }),
    };
  });

  const customers: PickerOption[] =
    options !== undefined && options.categories.length > 0
      ? options.categories.map((row) => ({ value: row.value, label: row.label }))
      : CUSTOMER_CATEGORIES.map((key) => ({
          value: key,
          label:
            key === "default"
              ? t("templates.workspace.allCustomers")
              : t(`templates.audience.${key}`),
        }));

  const own = options?.languages.find((row) => row.is_utility_language) ?? null;
  return {
    channels,
    languages,
    customers,
    channelLabel:
      channels.find((option) => option.value === code)?.label ?? channelWord(data.channel),
    utilityLanguage: own === null ? null : languageLabel(own.value, options, t),
  };
}

/** A language value's name, for the dialogs and the variant label. */
export function workspaceLanguageName(
  value: string,
  options: TemplateVariantOptions | undefined,
  t: (key: string, vars?: Record<string, unknown>) => string,
): string {
  return languageLabel(value, options, t);
}

export function TemplateWorkspace(props: {
  code: string;
  client: ApiClient;
  readOnly: boolean;
  readOnlyReason: string | null;
  /** DEF-212 (2): the selected variant is URL state, held by SET-09. */
  variantId: string | null;
  onSelectVariant: (id: string) => void;
  onBack: () => void;
  /** CR-048 E5 — this notice's OTHER channels, from the catalogue page the list
   *  holds. Required, not optional: an optional prop nothing passes is the dead
   *  UI shape G13 exists for (hard-won law 2). */
  surfaces: readonly TemplateCatalogRow[];
  onOpenSurface: (code: string) => void;
}) {
  const { t } = useTranslation();
  const detail = useQuery({
    queryKey: queryKeys.templateDetail(props.code, props.variantId),
    queryFn: () => getTemplateDetail(props.code, props.variantId, props.client),
  });
  const [openVersionId, setOpenVersionId] = useState<string | null>(null);

  if (detail.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (detail.error !== null || detail.data === undefined) {
    return (
      <FailedWithRetry
        title={t("templates.detail.failedTitle")}
        reason={apiErrorText(detail.error, t)}
        onRetry={() => void detail.refetch()}
        onDownloadReport={() => undefined}
        onCancel={props.onBack}
      />
    );
  }
  const data = detail.data;
  const selected = props.variantId ?? data.selected_variant;
  return (
    /* Keyed on the variant and the version in the editor: the wording a person
       is typing belongs to ONE version of ONE variant, and switching either
       starts the box again from that version's own words (DEF-212 (1)). */
    <WorkspaceBody
      key={`${props.code}:${selected ?? "none"}:${openVersionId ?? "auto"}`}
      {...props}
      data={data}
      selectedVariantId={selected}
      openVersionId={openVersionId}
      onOpenVersion={setOpenVersionId}
    />
  );
}

function WorkspaceBody(props: {
  code: string;
  client: ApiClient;
  readOnly: boolean;
  readOnlyReason: string | null;
  onSelectVariant: (id: string) => void;
  onBack: () => void;
  surfaces: readonly TemplateCatalogRow[];
  onOpenSurface: (code: string) => void;
  data: TemplateDetail;
  selectedVariantId: string | null;
  openVersionId: string | null;
  onOpenVersion: (id: string | null) => void;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const { data } = props;
  const readOnly = props.readOnly || !data.can_edit;
  const kind = designerKind(data);
  const surfaces = previewSurfaces(data, kind);
  /* CR-199-BRC10 §5 — the utility's customer classes, its switched-on
     languages, the taken combinations and whether this is a legal notice.
     Read by every role; a refusal leaves the pickers on what the variants
     themselves say, never on a list made up here. */
  const variantOptions = useQuery({
    queryKey: ["template-catalog", "variant-options", props.code],
    queryFn: () => getTemplateVariantOptions(props.code, props.client),
    retry: false,
  });
  const options = variantOptions.data;
  /* `16` — how many customers read each language (`GET /template-languages`,
     §5c). A regional code receives its base language's wording (`es-MX` gets
     `es` when only `es` is written), so it counts toward the base's variant. */
  const languageCounts = useQuery({
    queryKey: ["template-catalog", "language-counts"],
    queryFn: () => getTemplateLanguageCounts(props.client),
    retry: false,
  });
  function readersOf(value: string): { label: string; count: number } | null {
    const counts = languageCounts.data;
    if (counts === undefined || value === "") return null;
    const base = (code: string | null) => (code ?? "").split("-")[0];
    const target = value === "default" ? null : base(value);
    const count = counts.languages
      .filter((row) =>
        target === null ? row.value === "default" : row.value !== "default" && base(row.value) === target,
      )
      .reduce((sum, row) => sum + row.accounts, 0);
    return { label: workspaceLanguageName(value, options, t), count };
  }
  const variant = data.variants.find((row) => row.id === props.selectedVariantId) ?? null;
  const customerValue = variant?.category ?? "default";
  const languageValue = variant?.language ?? "";
  const axes = workspaceAxes(data, props.code, props.surfaces, options, customerValue, t, languageValue);

  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [testResult, setTestResult] = useState<TemplateTestResult | null>(null);
  const [startLanguage, setStartLanguage] = useState<string | null>(null);

  // ── URL state: editing, which dialog is up, the history ──────────────────
  const editing = params.get(WORKSPACE_MODE_PARAM) === WORKSPACE_EDIT && data.variants.length > 0;
  const dialog = workspaceDialogOf(params.get(WORKSPACE_DIALOG_PARAM));
  const historyOpen = params.get(WORKSPACE_VIEW_PARAM) === WORKSPACE_HISTORY;
  /** ONE write for several params: two `setParams` in one tick would each
   *  start from the same old query string and the second would undo the
   *  first. The history is a place (a Back press closes it), so opening or
   *  closing it pushes; everything else replaces. */
  function writeParams(changes: Record<string, string | null>) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [name, value] of Object.entries(changes)) {
          if (value === null) next.delete(name);
          else next.set(name, value);
        }
        return next;
      },
      { replace: !(WORKSPACE_VIEW_PARAM in changes) },
    );
  }
  const writeParam = (name: string, value: string | null) => writeParams({ [name]: value });
  const setEditing = (on: boolean) => writeParam(WORKSPACE_MODE_PARAM, on ? WORKSPACE_EDIT : null);
  const openDialog = (which: WorkspaceDialog | null) => writeParam(WORKSPACE_DIALOG_PARAM, which);

  // ── The wording in the box ───────────────────────────────────────────────
  const source = editorSource(data.versions, props.openVersionId);
  const [body, setBody] = useState(source?.body ?? "");
  const [subject, setSubject] = useState(source?.subject ?? "");
  /* CR-199-BRC10 §5b — Rich / Plain. Offered only where the server lists
     `rich` for this class (email); the version's own format is where the box
     starts. */
  const richOffered = (data.body_formats ?? []).includes("rich");
  const startFormat: TemplateBodyFormat = source?.body_format ?? "plain";
  const [format, setFormat] = useState<TemplateBodyFormat>(startFormat);
  const dirty =
    body !== (source?.body ?? "") || subject !== (source?.subject ?? "") || format !== startFormat;
  const bodyFormat = richOffered ? format : undefined;
  const live = useLivePreview({
    code: props.code,
    client: props.client,
    body,
    subject,
    version: source?.version ?? 0,
    bodyFormat,
    initial: data.preview,
    initialError: data.preview_unavailable,
    dirty,
  });

  const draft = data.versions.find((row) => row.status === "draft") ?? null;
  const published = data.versions.find((row) => row.status === "published") ?? null;
  const labelOf = (options: readonly PickerOption[], value: string) =>
    options.find((option) => option.value === value)?.label ?? value;
  const variantLabel = [
    axes.channelLabel,
    languageValue === "" ? "" : workspaceLanguageName(languageValue, options, t),
    labelOf(axes.customers, customerValue),
  ]
    .filter((part) => part !== "")
    .join(" · ");
  /* PO ruling A1 C — only a legal notice needs approval. The flag is the
     SERVER's; nothing here decides which templates are legal. */
  const approval = options?.needs_approval === true;

  async function settle() {
    await queryClient.invalidateQueries({ queryKey: ["template-catalog"] });
  }

  const save = useMutation({
    mutationFn: () =>
      saveTemplateDraft(
        props.code,
        {
          variant: props.selectedVariantId as string,
          body,
          subject: subject || null,
          body_format: bodyFormat,
        },
        props.client,
      ),
    onSuccess: async (version) => {
      setRefusal(null);
      fireToast(t("templates.detail.saved", { version: version.version }));
      await settle();
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  /* Publish: an unsaved change is saved as the new draft FIRST, then that
     draft is published — the two writes this screen has always made, in the
     order the drawing's one button implies (`11`).

     ⚠ **A LEGAL NOTICE STOPS AT THE DRAFT (PO ruling A1 C, `13`).** Its button
     reads *Send for approval*: the wording is saved as a draft and the live
     version keeps going out until a System Admin publishes the draft from
     History — that publish IS the approval. The server serves no separate
     approval queue; decision log 2026-10-29 *"screens lane"* (9). */
  const publish = useMutation({
    mutationFn: async () => {
      let target = draft;
      if (dirty || target === null) {
        target = await saveTemplateDraft(
          props.code,
          {
            variant: props.selectedVariantId as string,
            body,
            subject: subject || null,
            body_format: bodyFormat,
          },
          props.client,
        );
      }
      if (approval) {
        return { version: target, published: false };
      }
      return {
        version: await publishTemplateVersion(props.code, target.id, props.client),
        published: true,
      };
    },
    onSuccess: async ({ version, published: isLive }) => {
      setRefusal(null);
      fireToast(
        isLive
          ? t("templates.detail.published", { version: version.version })
          : t("templates.workspace.sentForApproval", { version: version.version }),
      );
      writeParams({ [WORKSPACE_DIALOG_PARAM]: null, [WORKSPACE_MODE_PARAM]: null });
      await settle();
    },
    onError: (error: unknown) => {
      openDialog(null);
      setRefusal(refusalOf(error, t));
    },
  });

  const queueTest = useMutation({
    mutationFn: () => queueTemplateTest(props.code, props.client),
    onSuccess: (result) => {
      setRefusal(null);
      setTestResult(result);
      openDialog(null);
    },
    onError: (error: unknown) => {
      openDialog(null);
      setRefusal(refusalOf(error, t));
    },
  });

  /* `18` — a language nobody has written yet: the server makes its variant
     and copies the utility-language wording into it as the first DRAFT
     (`new-variant`, `start_from: "published"` with no source — CR-199-BRC10
     §5). Nothing is published. */
  const startFrom = useMutation({
    mutationFn: (language: string) =>
      createTemplateVariant(
        props.code,
        { language, category: customerValue, start_from: "published" },
        props.client,
      ),
    onSuccess: async (made) => {
      setRefusal(null);
      setStartLanguage(null);
      await settle();
      props.onSelectVariant(made.variant.id);
    },
    onError: (error: unknown) => {
      setStartLanguage(null);
      setRefusal(refusalOf(error, t));
    },
  });

  function pickVariant(language: string, customer: string): TemplateVariantRow | null {
    return (
      data.variants.find((row) => row.language === language && row.category === customer) ?? null
    );
  }
  function onLanguage(language: string) {
    const found = pickVariant(language, customerValue);
    if (found !== null) {
      props.onSelectVariant(found.id);
      return;
    }
    setStartLanguage(language);
  }
  function onCustomer(customer: string) {
    const found = pickVariant(languageValue, customer);
    if (found !== null) {
      props.onSelectVariant(found.id);
      return;
    }
    openDialog("new");
  }

  // ── The bar ──────────────────────────────────────────────────────────────
  const writeBlock = readOnly ? (data.cannot_edit_reason ?? props.readOnlyReason ?? "") : null;
  const noVariant = data.variants.length === 0 ? t("templates.detail.noVariants") : null;
  const ctl = (reason: string | null, onClick: () => void, working = false): BarControl => ({
    reason,
    onClick,
    working,
  });
  const view = ctl(editing ? null : "", () => setEditing(false));
  const edit = ctl(writeBlock ?? noVariant ?? (editing ? "" : null), () => setEditing(true));
  const duplicate = ctl(writeBlock ?? noVariant, () => openDialog("duplicate"));
  const newVariant = ctl(writeBlock, () => openDialog("new"));
  const history = ctl(null, () => writeParam(WORKSPACE_VIEW_PARAM, WORKSPACE_HISTORY));
  /* ⚠ ABSENT ON THE IN-APP SHAPE, NOT DISABLED (`DEF-NOT-4475`): there is no
     address, inbox or handset for a test of a banner drawn inside this
     product, so there is nothing to offer. */
  const sendTest =
    kind === "in_app"
      ? null
      : ctl(
          data.can_test_send ? null : data.test_send_reason,
          () => openDialog("send-test"),
          queueTest.isPending,
        );
  /* ── What the server's render found in the wording (`17`) ──────────────
     An unknown placeholder BLOCKS the save (PO ruling A2 A — the server
     refuses it too); a link placeholder used as bare text only WARNS. Both are
     drawn in the catalogue's own words, by `message_key`. */
  const errors = live.preview?.errors ?? [];
  const warnings = live.preview?.warnings ?? [];
  const issueText = (issue: TemplateWordingIssue) => t(issue.message_key, issue.params);
  const blockedByWording = errors.length > 0 ? issueText(errors[0]) : null;
  const saveDraft = ctl(
    !editing ? "" : (writeBlock ?? noVariant ?? blockedByWording),
    () => save.mutate(),
    save.isPending,
  );
  const publishCtl = ctl(
    !editing
      ? ""
      : (writeBlock ??
          noVariant ??
          blockedByWording ??
          (dirty || draft !== null ? null : t("templates.workspace.nothingToPublish"))),
    () => openDialog("publish"),
    publish.isPending,
  );
  const publishVersion =
    dirty || draft === null ? (data.versions[0]?.version ?? 0) + 1 : draft.version;

  // ── The legacy render problems, kept beside the named findings ──────────
  const problems = live.preview?.problems ?? [];

  const offer =
    data.variants.length === 0 ? (
      <PlatformDefaultOffer
        data={data}
        code={props.code}
        client={props.client}
        readOnly={readOnly}
        onCreated={(id) => {
          props.onSelectVariant(id);
        }}
        onRefusal={setRefusal}
      />
    ) : null;

  return (
    <div className="flex flex-col gap-6" data-testid="template-detail-page">
      <PageHeader
        backTo={{
          label: t("templates.detail.back").replace(/^←\s*/, ""),
          onClick: props.onBack,
          testId: "template-back",
        }}
        kicker={`${t("templates.detail.kicker")} · ${t(`templates.category.${data.category}`, {
          defaultValue: data.category,
        })}`}
        title={data.name}
        titleAs="h2"
        rollup={<HeadMeta data={data} />}
      />

      <TemplateVariantPickers
        channels={axes.channels}
        channel={props.code}
        onChannel={(code) => {
          if (code !== props.code) props.onOpenSurface(code);
        }}
        languages={axes.languages}
        language={languageValue}
        onLanguage={onLanguage}
        customers={axes.customers}
        customer={customerValue}
        onCustomer={onCustomer}
        readers={readersOf(languageValue)}
        fallbackLanguage={axes.utilityLanguage}
      />

      <TemplateActionBar
        facts={{
          shown:
            source === undefined
              ? null
              : {
                  version: source.version,
                  status: source.status,
                  restoredFrom: source.restored_from_version ?? null,
                },
          live: published?.version ?? null,
          variantLabel,
          needsApproval: approval,
          variantState: (() => {
            if (variant === null) return null;
            const state = variantStateOf(variant, data.versions);
            return state === "live" ? null : t(VARIANT_STATE_KEY[state]);
          })(),
          editing,
        }}
        view={view}
        edit={edit}
        duplicate={duplicate}
        newVariant={newVariant}
        history={history}
        sendTest={sendTest}
        saveDraft={saveDraft}
        publish={publishCtl}
        notes={
          <>
            {kind !== "in_app" && (
              <ControlNote
                label={data.test_send_label}
                reason={data.test_send_reason}
                testId="test-send-reason"
              />
            )}
            {testResult !== null && (
              <p className="m-0 text-sm" role="status" data-testid="test-send-result">
                {testResultSentence(testResult, t)}
              </p>
            )}
          </>
        }
      />

      <RefusalNotice refusal={refusal} />
      {readOnly && (
        <RefusalStrip role="note" data-testid="detail-readonly">
          {data.cannot_edit_reason ?? props.readOnlyReason}
        </RefusalStrip>
      )}
      {data.body_unavailable !== null && (
        <RefusalStrip role="note" data-testid="detail-no-body">
          {data.body_unavailable}
        </RefusalStrip>
      )}
      {/* `17` — what the server's render found in the wording: a placeholder
          that cannot be filled (red, blocks the save) and a link placeholder
          used as bare text (amber, a warning). Each in the catalogue's words. */}
      {(errors.length > 0 || warnings.length > 0 || problems.length > 0) && (
        <ul className="m-0 flex list-none flex-col gap-2 p-0" data-testid="wording-problems">
          {errors.map((issue, index) => (
            <li key={`error:${issue.code}:${index}`} data-problem={issue.code}>
              <WarningBox tone="now" sentence={issueText(issue)} data-warning="wording-error" />
            </li>
          ))}
          {warnings.map((issue, index) => (
            <li key={`warning:${issue.code}:${index}`} data-problem={issue.code}>
              <WarningBox tone="soon" sentence={issueText(issue)} data-warning="wording-warning" />
            </li>
          ))}
          {problems.map((problem) => (
            <li key={`${problem.code}:${problem.detail}`}>
              <RefusalStrip role="alert" data-problem={problem.code}>
                {problem.detail}
              </RefusalStrip>
            </li>
          ))}
        </ul>
      )}

      <div className={DESIGNER_FRAME} data-testid="designer-frame">
        <TemplateWordingPane
          data={data}
          kind={kind}
          body={body}
          subject={subject}
          onBody={setBody}
          onSubject={setSubject}
          editing={editing && !readOnly}
          preview={live.preview}
          format={
            richOffered
              ? {
                  value: format,
                  syntax: RICH_SYNTAX,
                  onChange: (next) => {
                    /* Rich → Plain keeps the WORDS and drops the markup: the
                       server's own `plain_source` of what is in the box, never
                       a client-side strip of it. */
                    if (next === "plain" && live.preview?.plain_source != null) {
                      setBody(live.preview.plain_source);
                    }
                    setFormat(next);
                  },
                }
              : null
          }
        />
        <TemplateLivePreview
          data={data}
          kind={kind}
          surfaces={surfaces}
          preview={live.preview}
          error={live.error}
          selectedVariantId={props.selectedVariantId}
          offer={offer}
        />
      </div>

      {data.variants.length > 0 && (
        <Panel title={t("templates.workspace.variant")}>
          <VariantLifecycle
            data={data}
            selected={props.selectedVariantId}
            readOnly={readOnly}
            code={props.code}
            client={props.client}
            onRefusal={setRefusal}
          />
        </Panel>
      )}

      {(dialog === "new" || dialog === "duplicate") && (
        <TemplateVariantDialog
          mode={dialog}
          client={props.client}
          channels={axes.channels}
          channel={props.code}
          languages={axes.languages}
          language={languageValue === "" ? (axes.languages[0]?.value ?? "default") : languageValue}
          customers={axes.customers}
          customer={customerValue}
          startFrom={
            options === undefined
              ? []
              : options.start_from
                  .filter((kind_) => kind_ !== "variant" || variant !== null)
                  .map((kind_) => ({
                    value: kind_,
                    label:
                      kind_ === "variant"
                        ? t("templates.workspace.startFromVariant", {
                            version: published?.version ?? source?.version ?? 1,
                          })
                        : t(`templates.workspace.startFromOption.${kind_}`),
                  }))
          }
          sourceVariant={variant?.id ?? null}
          utilityLanguagesOnly={options !== undefined}
          onClose={() => openDialog(null)}
          onRefusal={setRefusal}
          onCreated={(code, made) => {
            openDialog(null);
            if (code === props.code) props.onSelectVariant(made.id);
            else props.onOpenSurface(code);
          }}
        />
      )}
      {dialog === "send-test" && (
        <ConfirmDialog
          title={t("templates.workspace.sendTestTitle")}
          consequence={data.test_send_reason}
          confirmLabel={t("templates.workspace.sendTest")}
          working={queueTest.isPending}
          onConfirm={() => queueTest.mutate()}
          onCancel={() => openDialog(null)}
        />
      )}
      {dialog === "publish" && (
        <ConfirmDialog
          title={t(
            approval
              ? "templates.workspace.approvalConfirmTitle"
              : "templates.workspace.publishTitle",
            {
              version: publishVersion,
            },
          )}
          consequence={
            approval
              ? t("templates.workspace.approvalConsequence")
              : t("templates.workspace.publishConsequence")
          }
          confirmLabel={
            approval ? t("templates.workspace.sendForApproval") : t("templates.workspace.publish")
          }
          working={publish.isPending}
          onConfirm={() => publish.mutate()}
          onCancel={() => openDialog(null)}
        />
      )}
      {startLanguage !== null && (
        <ConfirmDialog
          title={t("templates.workspace.startLanguageTitle", {
            language: workspaceLanguageName(startLanguage, options, t),
          })}
          consequence={t("templates.workspace.startLanguageConsequence", {
            language: axes.utilityLanguage ?? t("templates.workspace.defaultLanguage"),
          })}
          confirmLabel={t("templates.workspace.startFromLanguage", {
            language: axes.utilityLanguage ?? t("templates.workspace.defaultLanguage"),
          })}
          cancelLabel={t("templates.workspace.notNow")}
          working={startFrom.isPending}
          onConfirm={() => startFrom.mutate(startLanguage)}
          onCancel={() => setStartLanguage(null)}
        />
      )}
      {historyOpen && (
        <TemplateHistoryDialog
          data={data}
          kind={kind}
          code={props.code}
          client={props.client}
          readOnly={readOnly}
          needsApproval={approval}
          makeLiveAgain={(versionId) => makeTemplateLiveAgain(props.code, versionId, props.client)}
          onOpenVersion={(id) => {
            writeParams({ [WORKSPACE_VIEW_PARAM]: null, [WORKSPACE_MODE_PARAM]: WORKSPACE_EDIT });
            props.onOpenVersion(id);
          }}
          onRefusal={setRefusal}
          onClose={() => writeParam(WORKSPACE_VIEW_PARAM, null)}
        />
      )}
    </div>
  );
}
