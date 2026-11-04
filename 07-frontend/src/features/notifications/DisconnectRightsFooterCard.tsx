// ── Trace ──────────────────────────────────────────────
// Story:    CR-007 (the disconnect notices — the platform writes the defaults,
//           PO ruling 2026-08-17)   Screens: S8 (Settings → Notifications)
// Rules:    BR-NOT-015 (the rights footer is a PLATFORM DEFAULT, VISIBLY MARKED
//           as one, overridable by a System Admin, and the override is AUDITED) ·
//           BR-NOT-014 (the footer prints on all three disconnection tiers) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-025 (a forbidden
//           control renders DISABLED with its reason, never hidden) ·
//           B14 (two button sizes; danger tier on destructive commits)
// ───────────────────────────────────────────────────────
// S8 → Notifications: THE FIVE SENTENCES A DISCONNECTION NOTICE CARRIES.
//
// ── WHY THIS CARD EXISTS AT ALL ───────────────────────────────────────────
// Until 2026-08-17 the three disconnect tiers were built, EMPTY, and refused
// every save by name — so no disconnection notice could be produced on any
// tenant. BR-NOT-015 said the platform ships a rights footer as a default and a
// System Admin may override it, and said in as many words that the default's
// SENTENCES were not that rule's to invent. Nobody had ruled who writes them.
//
// The PO then did, verbatim: *"we provide default option for all 5 you ahve
// mentioned; if Utility wants to over ride it let them do it; I can also give
// tick boxes if required to add 5"* … *"you build default langauge and let
// Utility user change it as they want"*. This card is the second half of that
// sentence — the part where the utility changes it.
//
// ── THE ONE THING THIS SCREEN MUST NEVER SOFTEN ───────────────────────────
// **A default is a starting point, not legal advice.** These five paragraphs
// tell a customer how to keep their water on. So:
//   · the standing notice sits ABOVE the clauses, not in a tooltip, and it says
//     the platform wrote them, that they are not the utility's regulator's
//     words, and that they must be reviewed against that regulator before a
//     notice goes out;
//   · every untouched clause carries a "Platform default" badge, and a replaced
//     one carries "Your wording", so the two are never confusable;
//   · **every one of those sentences is the SERVER's**, rendered verbatim. A
//     screen that worded them itself would drift from BR-NOT-015 the day the
//     rule changed — hard-won law 1, in a component.
//
// ── THE TICK BOXES ARE NOT COSMETIC ───────────────────────────────────────
// A utility in a state with no weather rule must be able to turn that clause
// OFF, rather than blank the text and hope: a blanked clause prints a heading
// with nothing under it, which reads exactly like wording somebody has not
// finished. OFF removes the clause from the letter entirely.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { getDisconnectRightsFooter, updateDisconnectRightsFooter } from "@/api/endpoints";
import type { DisconnectRightsFooter, RightsClauseChange } from "@/api/endpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";

import {
  ACTIONS,
  CLAUSE_EDITOR,
  CLAUSE_HEAD,
  CLAUSE_HEAD_LABEL,
  CLAUSE_ITEM,
  CLAUSE_LIST,
  CLAUSE_TEXT,
  CLAUSE_TITLE,
  BADGE,
  BADGE_MUTED,
  DESC,
  HINT,
  REASON_CLAMP,
} from "./notificationsKit";

import { Panel, apiErrorText, refusalOf } from "../tenancy/settingsShared";
import type { Refusal, Translator } from "../tenancy/settingsShared";

/** The cache key. Named once so the card and its mutation use one spelling —
 *  a second copy is how a save invalidates nothing and the screen keeps showing
 *  the wording the utility just replaced. */
export const rightsFooterKey = ["notifications", "rights-footer"] as const;

/**
 * Whether the Save control may fire for a clause, and WHY NOT when it may not.
 *
 * PURE and exported, so the rule is testable without a browser (the shape
 * `requeueBlockedReason` established on this tab). Returns `null` when the save
 * is allowed.
 */
export function clauseSaveBlockedReason(
  data: DisconnectRightsFooter,
  draft: string,
  original: string,
): string | null {
  if (!data.can_edit) {
    return data.cannot_edit_reason;
  }
  if (draft.trim() === "") {
    // The server refuses this too; saying it here as well means the person
    // finds out before they lose what they typed, not after.
    return "TICK_BOX_NOT_BLANK";
  }
  if (draft === original) {
    return "NO_CHANGE";
  }
  return null;
}

export function DisconnectRightsFooterCard(props: {
  client: ApiClient;
  readOnly: boolean;
  t: Translator;
  onRefusal: (refusal: Refusal | null) => void;
}) {
  const { t } = props;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  // Which clause's editor is open. One at a time, deliberately: five open
  // textareas of legal text on one settings card is a page nobody proof-reads.
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const footer = useQuery({
    queryKey: rightsFooterKey,
    queryFn: () => getDisconnectRightsFooter(props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const save = useMutation({
    mutationFn: (clauses: Record<string, RightsClauseChange>) =>
      updateDisconnectRightsFooter({ clauses }, props.client),
    onSuccess: async () => {
      props.onRefusal(null);
      setEditing(null);
      fireToast(t("notifications.rights.saved"));
      await queryClient.invalidateQueries({ queryKey: rightsFooterKey });
    },
    onError: (error: unknown) => props.onRefusal(refusalOf(error, t)),
  });

  if (footer.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  if (footer.error !== null || footer.data === undefined) {
    // The card fails ALONE rather than darkening the tab: a tenant whose rights
    // footer cannot be read must still be able to see the queue.
    return (
      <RefusalStrip role="note" data-testid="rights-footer-unavailable">
        {t("notifications.rights.unavailable", { reason: apiErrorText(footer.error, t) })}
      </RefusalStrip>
    );
  }

  const data = footer.data;
  const readOnly = props.readOnly || !data.can_edit;
  const working = save.isPending;

  return (
    <Panel title={t("notifications.rights.title")} hint={t("notifications.rights.hint")}>
      {/* ⚠ THE SENTENCE CR-007 FORBADE SOFTENING, AND IT IS THE SERVER'S.
          Above the clauses and never in a tooltip: it is the reason a System
          Admin is looking at this card at all. */}
      {/* ⚠ CR-048 wave H — this was the tallest refusal on the product:
          238 × 318px carrying 414 characters, in a 330px card, with
          `max-height: none`. The layout fix above took it to 819 × 97px on its
          own; the cap is what stops the next long sentence from doing it
          again. Nothing is truncated — see `REASON_CLAMP`'s note. */}
      <RefusalStrip role="note" className={REASON_CLAMP} data-testid="rights-platform-notice">
        {data.platform_default_notice}
      </RefusalStrip>

      {/* Where these five paragraphs actually print. A person switching a clause
          off is entitled to know which letters change. */}
      <p className={HINT} data-desc data-testid="rights-prints-on">
        {t("notifications.rights.printsOn", {
          letters: data.prints_on.map((row) => row.name).join(" · "),
        })}
      </p>

      {readOnly && (
        <RefusalStrip role="note" data-testid="rights-readonly">
          {data.cannot_edit_reason ?? t("notifications.rights.adminOnly")}
        </RefusalStrip>
      )}

      <ul className={CLAUSE_LIST} data-testid="rights-clauses">
        {data.clauses.map((clause) => {
          const open = editing === clause.code;
          return (
            <li
              key={clause.code}
              className={CLAUSE_ITEM}
              data-testid={`rights-clause-${clause.code}`}
            >
              <div className={CLAUSE_HEAD}>
                {/* THE TICK BOX. `disabled` rather than hidden (BR-SHL-025) so a
                    Billing Clerk can see which clauses their utility prints. */}
                <label className={CLAUSE_HEAD_LABEL}>
                  <input
                    type="checkbox"
                    checked={clause.enabled}
                    disabled={readOnly || working}
                    data-testid={`rights-toggle-${clause.code}`}
                    onChange={() => save.mutate({ [clause.code]: { enabled: !clause.enabled } })}
                  />
                  <span className={CLAUSE_TITLE}>{clause.title}</span>
                </label>
                {/* BR-NOT-015 (a) — the marking, in the SERVER's words, and it
                    flips when a utility takes the clause over. */}
                <span
                  className={clause.is_default ? BADGE_MUTED : BADGE}
                  data-badge
                  data-testid={`rights-source-${clause.code}`}
                >
                  {clause.source_label}
                </span>
              </div>

              <p className={DESC} data-desc>
                {clause.purpose}
              </p>

              {!clause.enabled && (
                <p className={HINT} data-desc data-testid={`rights-off-${clause.code}`}>
                  {t("notifications.rights.switchedOff")}
                </p>
              )}

              {open ? (
                <div className={CLAUSE_EDITOR}>
                  <textarea
                    value={draft}
                    rows={6}
                    aria-label={clause.title}
                    data-testid={`rights-editor-${clause.code}`}
                    onChange={(event) => setDraft(event.target.value)}
                  />
                  {/* The merge fields a clause MAY use, and the server's own
                      reason for why the list is what it is. Offering exactly
                      these means a clause cannot be typed that the save will
                      refuse. */}
                  <p className={HINT} data-desc data-testid={`rights-fields-${clause.code}`}>
                    {data.merge_fields.join("  ")}
                  </p>
                  <p className={HINT} data-desc>
                    {data.merge_fields_reason}
                  </p>
                  <div className={ACTIONS}>
                    <Button
                      variant="primary"
                      disabled={
                        working || clauseSaveBlockedReason(data, draft, clause.text) !== null
                      }
                      onClick={() => save.mutate({ [clause.code]: { text: draft } })}
                    >
                      {t("notifications.rights.save")}
                    </Button>
                    <Button variant="secondary" disabled={working} onClick={() => setEditing(null)}>
                      {t("notifications.rights.cancel")}
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <p className={CLAUSE_TEXT} data-testid={`rights-text-${clause.code}`}>
                    {clause.text}
                  </p>
                  <div className={ACTIONS}>
                    <Button
                      variant="secondary"
                      disabled={readOnly || working}
                      title={readOnly ? (data.cannot_edit_reason ?? undefined) : undefined}
                      data-testid={`rights-edit-${clause.code}`}
                      onClick={() => {
                        setEditing(clause.code);
                        setDraft(clause.text);
                      }}
                    >
                      {t("notifications.rights.edit")}
                    </Button>
                    {/* Only offered where there is something to go back TO. A
                        "restore default" on a clause that already IS the default
                        is a button that does nothing, which teaches a person to
                        distrust the ones that do. */}
                    {!clause.is_default && (
                      <Button
                        variant="secondary"
                        disabled={readOnly || working}
                        data-testid={`rights-restore-${clause.code}`}
                        onClick={() => save.mutate({ [clause.code]: { text: null } })}
                      >
                        {t("notifications.rights.restore")}
                      </Button>
                    )}
                  </div>
                  {!clause.is_default && (
                    <p className={HINT} data-desc data-testid={`rights-tenant-${clause.code}`}>
                      {data.tenant_wording_notice}
                    </p>
                  )}
                </>
              )}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
