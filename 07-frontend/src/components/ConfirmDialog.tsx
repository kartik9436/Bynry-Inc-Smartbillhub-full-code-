// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-009 (EP-SHL-03 §Stories)  Screens: S8, S22, S31.3, S35, S54, S63 (every destructive/money confirm per 13a)
// Rules:    IS-6 (modal → explicit confirm → toast → audit_log) · IS-10 (dialog a11y) — B9 conformance standards;
//           no BR-SHL row mints the confirm pattern itself (flagged in the packet report, not resolved here)
// ───────────────────────────────────────────────────────
// FE-04 ConfirmDialog (B13 §1): THE one destructive-action confirm with
// consequence messaging. It composes the ONE modal shell (FormModal.tsx) and
// StateFrame's WorkingButton — never redefines either. The dialog only asks;
// the consumer commits in onConfirm, and only a COMMITTED action fires its A13
// toast and writes audit_log (CLAUDE.md rule 7 — the toast is never the
// record). Deletes stay deactivate-first per IS-1; a referenced record's
// delete is blocked server-side regardless of what this dialog asked.
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ModalShell, TextField } from "./FormModal";
import { WorkingButton } from "./StateFrame";
import type { CommitTier } from "./StateFrame";

import { Button } from "@/components/Button";

export function ConfirmDialog(props: {
  title: string; // what's about to happen, e.g. "Write off 3 balances?"
  // IS-6 consequence messaging: plain language naming what changes, to what,
  // and how much — e.g. "This writes off $412.55 across 3 accounts."
  consequence: string;
  confirmLabel: ReactNode; // explicit verb copy from the consumer's catalog — never "OK"
  working: boolean; // true while the consumer's commit is in flight (A18 §3)
  /**
   * B14 rule 6's danger tier, for a DESTRUCTIVE confirm — DEF-718.
   *
   * ⚠ **THIS DIALOG IS RULE 6's LARGEST SURFACE AND COULD NOT OBEY IT UNTIL
   * 2026-08-26.** Its own header calls it "THE one destructive-action confirm"
   * and its worked example is *"Write off 3 balances?"* — rule 6's fourth named
   * example — yet it composed `WorkingButton` and passed NO tier, so thirty
   * call sites that delete, retire, archive, deactivate and roll back all
   * committed through a button styled exactly like Save. DEF-712 landed the
   * tier on `WorkingButton`; this prop is the half that reaches the confirms.
   *
   * It is OPTIONAL and absent means `primary`, so a confirm that is NOT rule
   * 6's subject renders byte-for-byte what it rendered before. **That is the
   * point, not an implementation convenience:** a tier that appears on every
   * dialog carries no information, so a confirm in front of a CREATION, a
   * PUBLISH or a SEND leaves this absent deliberately, and the audit of which
   * is which is in DEF-718's row.
   *
   * A polymorphic call site — one dialog serving `deactivate` and `reactivate`,
   * or `publish` and `archive` — computes it from the action rather than
   * pinning it, because half of those actions are not destructive.
   */
  confirmVariant?: CommitTier;
  /**
   * Type-the-name, for a confirm where the WRONG object would be a disaster —
   * CR-069 wave E, `US-INT-025`. When set, the confirm button stays disabled
   * until the reader has typed this exact word, and the field is labelled with
   * it so nobody has to go and find it.
   *
   * ⚠ **IT IS OPTIONAL AND ABSENT MEANS NO FIELD AT ALL, WHICH IS THE POINT
   * AND NOT AN IMPLEMENTATION CONVENIENCE — the same shape `confirmVariant`
   * took for DEF-718.** A friction that appears on every dialog stops being
   * read; put it only where the reader could plausibly be looking at the wrong
   * row. Every one of the thirty existing call sites renders byte-for-byte
   * what it rendered before.
   *
   * It is a SECOND look, never a security control: the API refuses the same
   * request for its own reasons, and a dialog cannot be the thing that stops
   * it. `US-INT-025` TC-5 is the refusal that actually protects the row.
   */
  typeToConfirm?: string;
  /**
   * The words on the button that backs out — absent reads the kit's *Cancel*,
   * so every existing caller renders byte-for-byte as before. A drawing that
   * names the way back in the act's own words (*Keep waiting*, `CR-168`
   * image 22) passes them here rather than hand-rolling a second dialog.
   */
  cancelLabel?: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [typed, setTyped] = useState("");
  const gate = props.typeToConfirm ?? null;
  // Trimmed and case-insensitive: the check is "does this person know which
  // row they are on", not "can this person type".
  const unlocked = gate === null || typed.trim().toLowerCase() === gate.toLowerCase();
  return (
    // IS-10 Esc/✕/backdrop close come with the shell; alertdialog announces
    // the interruption to AT.
    <ModalShell title={props.title} onClose={props.onCancel} role="alertdialog">
      <div className="modal-body">
        {/* CR-018 Route B: `.confirm-consequence` (ConfirmDialog.css, deleted)
            ported value for value — margin:0 / --text-md (14px) / line-height
            1.55, which is the body leading token. */}
        <p className="m-0 text-md leading-body whitespace-pre-line">{props.consequence}</p>
        {gate !== null && (
          <div className="mt-3">
            <TextField
              id="confirm-type-the-name"
              label={t("confirm.typeToConfirm", { name: gate })}
              value={typed}
              onChange={setTyped}
            />
          </div>
        )}
      </div>
      <div className="modal-foot">
        <Button
          variant="ghost"
          // While the commit is in flight the dialog can't be backed out of —
          // the action is already happening; the button state says so.
          disabled={props.working}
          onClick={props.onCancel}
        >
          {props.cancelLabel ?? t("confirm.cancel")}
        </Button>
        {/* A18 §3: disabled + "Working…" while committing — double-clicks are
            harmless at the surface; idempotency stays the module's (IS-6). */}
        <WorkingButton
          working={props.working}
          variant={props.confirmVariant}
          disabled={!unlocked}
          onClick={props.onConfirm}
        >
          {props.confirmLabel}
        </WorkingButton>
      </div>
    </ModalShell>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-009@b9eb83e (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-26 by lane CONFIRMTIER (DEF-718 — an OPTIONAL `confirmVariant?: CommitTier`, so B14 rule 6's danger tier can reach a CONFIRM at all; absent = primary, so a non-destructive confirm is byte-for-byte unchanged)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 54/54✔ (7 todo this packet — browser/journey/consumer scope) · [CONFIRMTIER 2026-08-26] tsc✔ eslint 0✔ vitest 2652 passed / 1 skipped / 198 todo across 151 files✔ · G13✔ G26✔ G31✔ G35✔ (2.49.1) G37✔ G40✔ · TEN mutations proved RED first in a scratchpad copy: hard-coded primary · dropped pass-through · unconditional danger · removed `disabled={props.working}` · a pinned call site losing its tier · an unclassified NEW call site · a flipped polymorphic expression · a dropped wizard declaration · an EXTRA class appended to every kit button (the DEF-182 substring hole — the whole-value assertion catches it) · single-flight and A18 §4 failure-with-state-preserved removed from the shared frame
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
