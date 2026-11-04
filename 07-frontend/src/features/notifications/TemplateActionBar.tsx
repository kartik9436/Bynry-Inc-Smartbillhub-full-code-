// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F3 — ONE action bar (`02`, `03`, `05`, `09`, `13`)
// Rules:    B14 rules 2 · 4 · 5 · 33 · 43 · 44 · BR-SHL-025 (a control that
//           cannot act renders DISABLED WITH ITS REASON) · PO ruling A1 C (only
//           a legal notice needs approval)
// ───────────────────────────────────────────────────────
// THE WORKSPACE'S STATUS LINE AND ITS ONE ROW OF BUTTONS.
//
// PO defect #4 was *"earlier actions removed"*. The drawing answers it with ONE
// bar that keeps every action in one place, in this order:
//
//   View · Edit wording · Duplicate as variant · + New variant ‖ History ·
//   Send test · Save draft · Publish
//
// (a legal notice's Publish reads **Send for approval**, `13`). The status line
// above the buttons says which version a customer gets NOW and which one is on
// screen — *"Draft v4 · Published v3 goes out now"* — plus the variant the
// pickers chose and whether the screen is viewing or editing.
//
// ⚠ **THIS COMPONENT DECIDES NOTHING.** Every flag — may this role write, is
// there a draft to publish, can a test be queued — arrives as a prop computed
// from the server's payload by the workspace. A bar that worked out its own
// permissions would be a second place for BR-BIL-027 to drift.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { StatusPill } from "@/components/StatusPill";

/** One button of the bar: enabled, or disabled with the sentence that says why. */
export interface BarControl {
  /** `null` = the control acts; a string = it cannot, and this is why. */
  reason: string | null;
  onClick: () => void;
  working?: boolean;
}

export interface TemplateStatusFacts {
  /** The version on screen (the draft when there is one), or null for none. */
  shown: { version: number; status: string; restoredFrom?: number | null } | null;
  /** The version customers get now, or null when nothing is published. */
  live: number | null;
  /** `Email · English · All customers` — the variant the pickers chose. */
  variantLabel: string;
  needsApproval: boolean;
  /** The variant's own state when it is not live — *Deactivated*, *Not
   *  published* — the badge the old variant tab carried (`CR-199-BRC10` §6 W2). */
  variantState: string | null;
  editing: boolean;
}

function StatusLine(props: { facts: TemplateStatusFacts }) {
  const { t } = useTranslation();
  const { shown, live } = props.facts;
  const isDraft = shown?.status === "draft";
  /* ⚠ DEF-NOT-10689 — a version that is neither a draft nor published is
     ARCHIVED (a deactivated variant's only version). It goes out to nobody,
     so it never reads "Published" or "what customers get now". */
  const isArchived = shown !== null && !isDraft && shown.status !== "published";
  return (
    <p className="m-0 flex flex-wrap items-center gap-2 text-sm" data-testid="workspace-status">
      {shown === null ? (
        <StatusPill tone="neutral">{t("templates.workspace.nothingWritten")}</StatusPill>
      ) : isArchived ? (
        <StatusPill tone="neutral">
          {`${t("templates.workspace.standing.archived")} · v${shown.version}`}
        </StatusPill>
      ) : isDraft ? (
        <StatusPill tone="warning">
          {t("templates.workspace.draftVersion", { version: shown.version })}
        </StatusPill>
      ) : (
        <StatusPill tone="success">
          {shown.restoredFrom != null
            ? t("templates.workspace.publishedRestoredFrom", {
                version: shown.version,
                from: shown.restoredFrom,
              })
            : t("templates.workspace.publishedVersion", { version: shown.version })}
        </StatusPill>
      )}
      <span data-testid="workspace-status-sentence">
        {isDraft || isArchived
          ? live === null
            ? t("templates.workspace.notPublishedYet")
            : t("templates.workspace.liveGoesOut", { version: live })
          : shown === null
            ? null
            : t("templates.workspace.whatCustomersGet")}
      </span>
      <StatusPill tone="neutral">{props.facts.variantLabel}</StatusPill>
      {props.facts.variantState !== null && (
        <span data-testid="workspace-variant-state">
          <StatusPill tone="warning">{props.facts.variantState}</StatusPill>
        </span>
      )}
      {props.facts.needsApproval && (
        <StatusPill tone="danger">{t("templates.list.needsApproval")}</StatusPill>
      )}
      <span data-testid="workspace-mode">
        {props.facts.editing ? (
          <StatusPill tone="info">{t("templates.workspace.editing")}</StatusPill>
        ) : (
          <StatusPill tone="neutral">{t("templates.workspace.viewing")}</StatusPill>
        )}
      </span>
    </p>
  );
}

function BarButton(props: {
  control: BarControl;
  label: ReactNode;
  testId: string;
  variant?: "primary" | "secondary";
  pressed?: boolean;
}) {
  return (
    <Button
      variant={props.variant ?? "secondary"}
      disabled={props.control.reason !== null || props.control.working === true}
      title={props.control.reason ?? undefined}
      aria-pressed={props.pressed}
      onClick={props.control.onClick}
      data-testid={props.testId}
    >
      {props.label}
    </Button>
  );
}

export function TemplateActionBar(props: {
  facts: TemplateStatusFacts;
  view: BarControl;
  edit: BarControl;
  duplicate: BarControl;
  newVariant: BarControl;
  history: BarControl;
  /** `null` = this shape has nowhere a test could go, and the button is not drawn. */
  sendTest: BarControl | null;
  saveDraft: BarControl;
  publish: BarControl;
  /** Under the bar: the test-send reason note, a test's result — the facts
   *  that belong beside the control they qualify (BR-SHL-025). */
  notes?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <section
      className="flex flex-col gap-3 border border-divider bg-surface p-4"
      aria-label={t("templates.workspace.actions")}
      data-testid="workspace-action-bar"
    >
      <StatusLine facts={props.facts} />
      <div className="flex flex-wrap items-center gap-2">
        <BarButton
          control={props.view}
          label={t("templates.workspace.view")}
          testId="workspace-view"
          pressed={!props.facts.editing}
        />
        <BarButton
          control={props.edit}
          label={t("templates.workspace.editWording")}
          testId="edit-wording"
          pressed={props.facts.editing}
        />
        <BarButton
          control={props.duplicate}
          label={t("templates.workspace.duplicate")}
          testId="duplicate-variant"
        />
        <BarButton
          control={props.newVariant}
          label={t("templates.workspace.newVariant")}
          testId="new-variant"
        />
        {/* The drawing's divider between what changes the variant and what
            acts on its wording. Decorative, so hidden from a screen reader. */}
        <span className="mx-1 h-8 w-px bg-divider max-sm:hidden" aria-hidden="true" />
        <BarButton
          control={props.history}
          label={t("templates.workspace.history")}
          testId="history-link"
        />
        {props.sendTest !== null && (
          <BarButton
            control={props.sendTest}
            label={t("templates.workspace.sendTest")}
            testId="test-send"
          />
        )}
        <BarButton
          control={props.saveDraft}
          label={t("templates.workspace.saveDraft")}
          testId="editor-save"
        />
        <BarButton
          control={props.publish}
          variant="primary"
          label={
            props.facts.needsApproval
              ? t("templates.workspace.sendForApproval")
              : t("templates.workspace.publish")
          }
          testId="workspace-publish"
        />
      </div>
      {props.notes}
    </section>
  );
}
