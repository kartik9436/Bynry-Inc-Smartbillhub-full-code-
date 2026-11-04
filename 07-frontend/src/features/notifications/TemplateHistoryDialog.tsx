// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F5 — History (`07`, `08`, `09`, `15`)
// Rules:    CLAUDE.md hard rule 4 (history is never rewritten — an old wording
//           comes back as a NEW version) · BR-BIL-026 · BR-BIL-027 · PO ruling
//           A1 C (a legal notice's restore is *Send for approval*) · CR-049
//           task 8 (what changed, and whose letters stand on the old wording) ·
//           B14 rules 15 · 33 · 43
// ───────────────────────────────────────────────────────
// THE VERSION HISTORY, AS THE DRAWING DRAWS IT: a dialog with a table —
// Version · Status · Saved · Actions — and the chosen version's own wording
// rendered underneath.
//
// ⚠ **IT IS STILL `?view=history`.** The 2026-08-30 ruling made history *"a
// separate page"* so it could be linked and reloaded; the drawing makes it a
// dialog. The workspace opens THIS dialog from that address, so both hold
// (decision log 2026-10-29 *"screens lane"* (3)).
//
// ⚠ **PREVIEW RENDERS THAT VERSION'S OWN STORED WORDING** — the README beside
// the drawing names this as the mock-up's shortcut to avoid. It is the server's
// render of `version.body`, through the same route the live preview uses.
//
// ⚠ **NOTHING THE OLD HISTORY PAGE DID IS LOST (`CR-199-BRC10` §6 W14–W18):**
// open a version in the editor, publish a draft, copy an old one back as a new
// draft, the Changed cell and its change record, and the pinned-by count with
// its never-deleted mark.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import {
  previewTemplateBody,
  publishTemplateVersion,
  restoreTemplateVersion,
} from "@/api/endpoints";
import type { TemplateDetail, TemplateVersionRow, makeTemplateLiveAgain } from "@/api/endpoints";

/** What `POST …/make-live-again` answers. */
export type MakeLiveOutcome = Awaited<ReturnType<typeof makeTemplateLiveAgain>>;
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ModalShell } from "@/components/FormModal";
import { CommitIcon, EyeIcon, PencilIcon, RollBackIcon } from "@/components/icons";
import { RowAction, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { LoadingSkeleton } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { apiErrorText, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { ChangeRecordDetail, ChangedCell } from "./TemplateDetail";
import type { DesignerKind } from "./TemplateDetail";
import { PreviewStage } from "./TemplateLivePreview";

/** Which of the three histories a version has. */
export function versionStanding(
  version: TemplateVersionRow,
): "draft" | "live" | "earlier" | "archived" {
  if (version.status === "draft") return "draft";
  if (version.status === "published") return "live";
  /* ⚠ DEF-NOT-10687 — the platform's seeded v1 carries no publish time, and
     the server counts it as published before (it offers Make live again on
     it). The words follow the server, so the row cannot read "Archived" beside
     a button that makes it live. */
  return version.published_at !== null || version.can_make_live_again === true
    ? "earlier"
    : "archived";
}

function VersionPreview(props: {
  code: string;
  client: ApiClient;
  data: TemplateDetail;
  kind: DesignerKind;
  version: TemplateVersionRow;
}) {
  const { t } = useTranslation();
  const rendered = useQuery({
    queryKey: ["template-version-preview", props.code, props.version.id],
    queryFn: () =>
      previewTemplateBody(
        props.code,
        {
          body: props.version.body,
          subject: props.version.subject,
          version: props.version.version,
          body_format: props.version.body_format,
        },
        props.client,
      ),
  });
  return (
    <section className="flex flex-col gap-2 bg-bg p-4" data-testid="history-preview">
      <h4 className="m-0 font-heading text-base font-semibold">v{props.version.version}</h4>
      {rendered.isPending ? (
        <LoadingSkeleton variant="card" />
      ) : rendered.error !== null || rendered.data === undefined ? (
        <RefusalStrip role="note" data-testid="history-preview-refused">
          {apiErrorText(rendered.error, t)}
        </RefusalStrip>
      ) : (
        <PreviewStage kind={props.kind} data={props.data} preview={rendered.data} />
      )}
    </section>
  );
}

export function TemplateHistoryDialog(props: {
  data: TemplateDetail;
  kind: DesignerKind;
  code: string;
  client: ApiClient;
  readOnly: boolean;
  needsApproval: boolean;
  /** The server's *make this earlier version live again* write
   *  (`POST …/make-live-again`, `CR-199-BRC10` §5). The row's action is drawn
   *  only where the server says the version can be (`can_make_live_again`);
   *  every other non-draft row keeps *Restore* (a copy as a draft), which is
   *  what the screen has always offered. */
  makeLiveAgain: (versionId: string) => Promise<MakeLiveOutcome>;
  onOpenVersion: (id: string) => void;
  onRefusal: (refusal: Refusal | null) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [openChangeId, setOpenChangeId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<TemplateVersionRow | null>(null);
  const live = props.data.versions.find((version) => version.status === "published") ?? null;
  const blocked = props.readOnly ? (props.data.cannot_edit_reason ?? "") : null;
  /** A legal notice's restore asks for approval (PO ruling A1 C) — the row's
   *  own flag when the server serves it, the template's otherwise. */
  const needsApprovalFor = (version: TemplateVersionRow) =>
    version.make_live_again_needs_approval ?? props.needsApproval;

  async function settle() {
    await queryClient.invalidateQueries({ queryKey: ["template-catalog"] });
  }
  const publish = useMutation({
    mutationFn: (id: string) => publishTemplateVersion(props.code, id, props.client),
    onSuccess: async (version) => {
      props.onRefusal(null);
      fireToast(t("templates.detail.published", { version: version.version }));
      await settle();
    },
    onError: (error: unknown) => props.onRefusal(refusalOf(error, t)),
  });
  const restore = useMutation({
    mutationFn: (id: string) => restoreTemplateVersion(props.code, id, props.client),
    onSuccess: async (version) => {
      props.onRefusal(null);
      fireToast(version.detail);
      await settle();
    },
    onError: (error: unknown) => props.onRefusal(refusalOf(error, t)),
  });
  const makeLive = useMutation({
    mutationFn: (id: string) => props.makeLiveAgain(id),
    onSuccess: async (outcome) => {
      props.onRefusal(null);
      fireToast(
        outcome.outcome === "sent_for_approval"
          ? t("templates.workspace.sentForApproval", { version: outcome.restored_from_version })
          : t("templates.workspace.liveAgain", { version: outcome.restored_from_version }),
      );
      await settle();
    },
    onError: (error: unknown) => props.onRefusal(refusalOf(error, t)),
  });

  const previewing = props.data.versions.find((version) => version.id === previewId) ?? null;

  /* `08` — the confirm TAKES THE HISTORY'S PLACE rather than opening over it:
     a dialog is never opened from inside a dialog. Cancel brings the table
     back; confirming closes both, and the status line then reads *Published
     vN (restored from v1)* (`09`). */
  if (confirming !== null) {
    const approval = needsApprovalFor(confirming);
    return (
      <ConfirmDialog
        title={t(
          approval
            ? "templates.workspace.approvalConfirmTitle"
            : "templates.workspace.liveAgainTitle",
          { version: confirming.version },
        )}
        consequence={
          approval
            ? t("templates.workspace.approvalConsequence")
            : t("templates.workspace.liveAgainConsequence", {
                version: confirming.version,
                live: live?.version ?? confirming.version,
              })
        }
        confirmLabel={
          approval
            ? t("templates.workspace.sendForApproval")
            : t("templates.workspace.makeLiveAgain")
        }
        working={makeLive.isPending}
        onConfirm={() => {
          const id = confirming.id;
          makeLive.mutate(id, {
            onSettled: () => {
              setConfirming(null);
              props.onClose();
            },
          });
        }}
        onCancel={() => setConfirming(null)}
      />
    );
  }

  return (
    <ModalShell title={t("templates.workspace.history")} onClose={props.onClose} size="wide">
      <div className="modal-body flex flex-col gap-4" data-testid="version-history-page">
        <div className="max-w-full overflow-x-auto">
          <table className="settings-table" data-testid="version-history">
            <thead>
              <tr>
                <th>{t("templates.detail.version")}</th>
                <th>{t("templates.detail.status")}</th>
                {props.kind === "contract" && <th>{t("templates.detail.effectiveFrom")}</th>}
                <th>{t("templates.workspace.saved")}</th>
                <th>{t("templates.detail.changed")}</th>
                <th>{t("templates.column.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {props.data.versions.map((version) => {
                const standing = versionStanding(version);
                return (
                  <tr key={version.id} data-testid={`version-${version.version}`}>
                    <td>v{version.version}</td>
                    <td>
                      <span className="flex flex-col gap-0.5">
                        <span
                          data-testid={
                            standing === "live" ? `version-live-${version.version}` : undefined
                          }
                        >
                          {t(`templates.workspace.standing.${standing}`)}
                        </span>
                        {/* CLAUDE.md rule 4 — the count of messages standing on
                            this wording, and what that protects, only when it
                            really is protected (`CR-199-BRC10` §6 W18). */}
                        {version.pinned_by > 0 && (
                          <span
                            className="text-sm"
                            data-testid={`version-pinned-${version.version}`}
                          >
                            {t("templates.detail.pinnedCount", {
                              count: version.pinned_by,
                              formatted: version.pinned_by.toLocaleString(),
                            })}
                            {!version.deletable && (
                              <span data-testid={`version-locked-${version.version}`}>
                                {" "}
                                {t("templates.detail.pinnedKept")}
                              </span>
                            )}
                          </span>
                        )}
                      </span>
                    </td>
                    {props.kind === "contract" && (
                      <td data-testid={`version-effective-${version.version}`}>
                        {version.effective_from ?? t("templates.detail.noEffectiveDate")}
                      </td>
                    )}
                    {/* The drawing's *"Oct 13 · Gaurav"* / *"Platform default"*.
                        The author's NAME is served only once the variants lane
                        serves it (`author_name`); `author_label` is a user id
                        and never drawn (B14 rule 31). A version nobody is on
                        record for says so in two words rather than a blank,
                        which would read as "nobody wrote this"; the rule id of
                        that absence rides `data-br-ref` (DEF-335). */}
                    <td
                      data-testid={`version-trail-${version.version}`}
                      data-br-ref={version.change_note_br_ref}
                    >
                      {version.updated_at.slice(0, 10)}
                      {version.author_name != null && version.author_name !== "" ? (
                        <> · {version.author_name}</>
                      ) : (
                        version.author_recorded !== true && (
                          <> · {t("templates.workspace.platformDefault")}</>
                        )
                      )}
                    </td>
                    <td>
                      <ChangedCell
                        kind={props.kind}
                        version={version}
                        open={openChangeId === version.id}
                        onToggle={() =>
                          setOpenChangeId(openChangeId === version.id ? null : version.id)
                        }
                      />
                    </td>
                    <td>
                      <RowActions>
                        <RowAction
                          label={t("templates.workspace.previewVersion", {
                            version: version.version,
                          })}
                          icon={<EyeIcon />}
                          pressed={previewId === version.id}
                          onClick={() => setPreviewId(previewId === version.id ? null : version.id)}
                          testId={`preview-version-${version.version}`}
                        />
                        {standing === "draft" && (
                          /* Publishing a draft is the System Admin's act —
                             for a legal notice it IS the approval (PO ruling
                             A1 C), so the word stays *Publish*. */
                          <RowAction
                            label={t("templates.detail.publish")}
                            icon={<CommitIcon />}
                            reason={blocked}
                            working={publish.isPending}
                            onClick={() => publish.mutate(version.id)}
                            testId={`publish-${version.version}`}
                          />
                        )}
                        {standing !== "draft" &&
                          standing !== "live" &&
                          (version.can_make_live_again === true ? (
                            <RowAction
                              label={
                                needsApprovalFor(version)
                                  ? t("templates.workspace.sendForApproval")
                                  : t("templates.workspace.makeLiveAgain")
                              }
                              icon={<RollBackIcon />}
                              reason={blocked}
                              working={makeLive.isPending}
                              onClick={() => setConfirming(version)}
                              testId={`make-live-${version.version}`}
                            />
                          ) : (
                            <RowAction
                              label={t("templates.detail.restore")}
                              icon={<RollBackIcon />}
                              hint={t("templates.detail.restoreTitle", {
                                version: version.version,
                              })}
                              reason={blocked}
                              working={restore.isPending}
                              onClick={() => restore.mutate(version.id)}
                              testId={`restore-${version.version}`}
                            />
                          ))}
                        <RowActionsMore
                          label={t("templates.workspace.moreForVersion", {
                            version: version.version,
                          })}
                        >
                          <RowMenuAction
                            label={t("templates.detail.openInEditor", { version: version.version })}
                            icon={<PencilIcon />}
                            onClick={() => props.onOpenVersion(version.id)}
                            testId={`open-version-${version.version}`}
                          />
                          {(standing === "live" ||
                            (standing !== "draft" && version.can_make_live_again === true)) && (
                            <RowMenuAction
                              label={t("templates.detail.restore")}
                              icon={<RollBackIcon />}
                              reason={blocked}
                              onClick={() => restore.mutate(version.id)}
                              testId={`restore-${version.version}`}
                            />
                          )}
                        </RowActionsMore>
                      </RowActions>
                    </td>
                  </tr>
                );
              })}
              {props.data.versions.length === 0 && (
                <tr>
                  <td colSpan={props.kind === "contract" ? 6 : 5} data-testid="version-empty">
                    {t("templates.detail.noVersions")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {openChangeId !== null && (
          <ChangeRecordDetail
            code={props.code}
            versionId={openChangeId}
            client={props.client}
            onClose={() => setOpenChangeId(null)}
            kind={props.kind}
          />
        )}
        {previewing !== null && (
          <VersionPreview
            code={props.code}
            client={props.client}
            data={props.data}
            kind={props.kind}
            version={previewing}
          />
        )}
      </div>
      <div className="modal-foot">
        <Button variant="secondary" onClick={props.onClose} data-testid="history-back">
          {t("templates.workspace.close")}
        </Button>
      </div>
    </ModalShell>
  );
}
