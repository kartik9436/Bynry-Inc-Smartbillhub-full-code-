// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-010 (EP-IDN-04 §Stories)  Screens: S8 (Settings → Security)
// Change:   CR-155-BRC09 — the Settings → Security redesign, approved by the PO
//           on 2026-09-29. Drawing: `approved-auditcard-1440.png`.
// Rules:    B14 rule 21 (Tailwind utilities, no stylesheet class) ·
//           B14 rule 31 (no database id is ever the visible value of a field) ·
//           B14 rule 33 (a heading ≤3 words; a fact ≤6; rationale ZERO) ·
//           B14 rule 43 (a piece of UI is a COMPONENT) ·
//           B14 rule 17 (an empty list says what is missing) ·
//           BR-AUD-003 / BR-AUD-019 (the actor is a person, or a named
//           automation saying what it is) · BR-TEN-016 (the save is audited
//           SERVER-side; nothing here claims to write a row)
// ───────────────────────────────────────────────────────
// THE LAST FIVE CHANGES MADE ON THIS TAB, FULL WIDTH, UNDER SAVE.
//
// The PO asked for it here and nowhere else — verbatim, 2026-09-29: *"keep it
// here only in this screen"*, then *"i only need bigger real estate for audit
// logs - can you give a card layout for it"*. So this replaces the old Audit
// log PANEL, whose whole content was a `View audit log →` button sitting in a
// third of a row: a card that told a clerk nothing and cost a column.
//
// ⚠ **IT MUST BE ABLE TO SHOW NOTHING, AND THAT IS NOT A CORNER CASE.**
// `audit_log` is pruned on a retention schedule and no row type is exempt
// from it (CLAUDE.md hard rule 4, PO ruling 2026-09-23: *"when audit log is
// delete - it is deleted thats okay"*). A utility that has not touched this
// tab since the last prune has **zero** rows here, honestly, and a utility
// that changed one thing has **one**. So the card draws what it is given —
// five, three, one or none — and never pads, never invents and never leaves a
// blank rectangle. Five is the CEILING the server reads to, not a promise.
//
// ⚠ **AND IT SAYS NOTHING ABOUT RETENTION ON SCREEN.** B14 rule 33 puts
// rationale at zero words, and hard rule 4 spells out this exact trap: a
// screen that explains the retention policy breaks rule 33 while trying to be
// honest about it. `CorrectionRetentionNote` was DELETED from eleven
// catalogues for doing precisely that. The honest build is silence — the card
// simply never claims the list is complete.
//
// ⚠ **RULE 31, THREE TIMES OVER.** WHO is a person's name or a named
// automation, never a user id — `actorLabel` is the product's one answer to
// that and this card reuses it rather than writing a second. SETTING is the
// same catalogue string the control above it uses, keyed through
// `SECURITY_SETTING_LABEL_KEY`, never the column name. CHANGE is rendered by
// `securityValueLabel`, the same function that labels the dropdown's options
// — so `480 → 60` reads as the control reads it and can never be a raw
// integer. The row's own id is a React key and reaches no pixel.
//
// ── WHY THIS CARD IS UTILITIES AND NOT `<Panel>` ──────────────────────────
// The drawing puts `View all →` on the TITLE ROW, right-aligned. The kit's
// `Panel` (settingsShared.tsx) renders `<h3>{title}</h3>` and has no header
// action slot. B14 rule 36 says to ADD the missing piece to the kit — and
// doing that here would need a flex header row written in utilities inside
// `settingsShared.tsx`, which is NOT on `route-b-migrated.txt`: adding it
// hands that file's fifteen other screens' bespoke classes to the stricter
// `routeBUtilities.test.ts` in the same commit, for one header row. So the
// card is built here, from the same four tokens `.panel` uses
// (`--color-surface`, `--color-accent`, `--space-6`, `--space-4`), and this
// FILE goes on the ledger instead. B14 rule 44's divergence is stamped in
// `05-prototype/security-redesign-2026-09-29/DIVERGENCES.md`.
import type { ReactNode } from "react";

import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { actorLabel } from "@/features/audit/AuditLogPage";
import type { SecurityPolicyChange } from "@/api/endpoints";

import {
  SECURITY_SETTING_LABEL_KEY,
  securityValueLabel,
} from "@/features/identity/securityPolicyFields";
import type { SecuritySettingKey, Translator } from "@/features/identity/securityPolicyFields";

/** The five the card can name. A row for anything else is dropped rather than
 *  rendered as a column name — see `renderableChanges`. */
function isRenderable(field: string): field is SecuritySettingKey {
  return field in SECURITY_SETTING_LABEL_KEY;
}

/**
 * The rows this card can honestly draw.
 *
 * ⚠ **A ROW NAMING A SETTING THIS SCREEN DOES NOT HAVE IS DROPPED, NOT
 * PRINTED.** The alternative is rendering `keep_signed_in_grace_days` — a
 * column name — into the SETTING column the first time the server grows a
 * setting before this screen does, which is B14 rule 31's *"no internal code
 * in clerk-facing copy"* half arriving through the back door. Dropping is
 * visible (the card shows four rows where the log has five) and printing is
 * not.
 */
export function renderableChanges(
  rows: SecurityPolicyChange[],
): (SecurityPolicyChange & { field: SecuritySettingKey })[] {
  return rows.filter(
    (row): row is SecurityPolicyChange & { field: SecuritySettingKey } => isRenderable(row.field),
  );
}

export interface SecurityAuditCardProps {
  title: string;
  hint: string;
  /** Where `View all →` goes — the S61 viewer, tenant-scoped. */
  viewAllTo: string;
  viewAllLabel: string;
  rows: SecurityPolicyChange[] | undefined;
  isPending: boolean;
  /** Non-null when the read failed; the card says so instead of showing zero
   *  rows. **A failed read is not an empty log** and must never be drawn as
   *  one — that is the difference between "nothing happened" and "we could not
   *  find out", and only one of them is true. */
  failure: string | null;
  onRetry: () => void;
  emptyText: string;
  columns: { when: string; who: string; setting: string; change: string };
  /** The tenant-zone renderer — a `<DateCell>`, never a string this file
   *  builds. BR-SHL-034: an instant is formatted in one place. */
  formatWhen: (iso: string) => ReactNode;
  t: Translator;
}

export function SecurityAuditCard(props: SecurityAuditCardProps) {
  const rows = props.rows === undefined ? [] : renderableChanges(props.rows);
  return (
    <section
      data-security-audit-card=""
      className="bg-surface border-t-2 border-t-accent pt-6 px-4 pb-6 flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <h3 className="m-0 text-h5">{props.title}</h3>
          <p className="m-0 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] max-w-[var(--desc-measure)]">
            {props.hint}
          </p>
        </div>
        {/* B14 rule 4: `Verb →` navigates. It is a real router link, so a
            middle-click opens the log in a tab like every other address in
            the product — and its destination is asserted by a test, which is
            hard-won law 2's mirror ("nothing asks whether a refusal is still
            true") answered before it can go stale. */}
        <InlineLinkTo to={props.viewAllTo} className="font-semibold underline">
          {props.viewAllLabel}
        </InlineLinkTo>
      </div>

      {props.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : props.failure !== null ? (
        // No `onCancel` and no `onDownloadReport`: both are optional now and a
        // no-op handler is a live control that does nothing (`DEF-INT-5562`,
        // `DEF-SHL-6377`). Retry is the only act a failed read has.
        <FailedWithRetry title={props.failure} reason="" onRetry={props.onRetry} />
      ) : rows.length === 0 ? (
        // B14 rule 17. It states what is missing in five words and offers no
        // "action that fills it", because the action that fills it is changing
        // a setting above — which the clerk is already standing in front of.
        <p data-security-audit-empty="" className="m-0 text-md">
          {props.emptyText}
        </p>
      ) : (
        <PlainTable className="w-full">
          <thead>
            <tr>
              <th scope="col">{props.columns.when}</th>
              <th scope="col">{props.columns.who}</th>
              <th scope="col">{props.columns.setting}</th>
              <th scope="col">{props.columns.change}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} data-security-audit-row="">
                <td>{props.formatWhen(row.changed_at)}</td>
                {/* `actorLabel` takes the ROW because it reads `row.actor`;
                    the shape is the product's one audit actor and this card
                    does not re-implement it (a second implementation is how
                    "Product upgrade" would become a user id on one screen). */}
                <td>{actorLabel({ actor: row.actor } as Parameters<typeof actorLabel>[0], props.t)}</td>
                <td>{props.t(SECURITY_SETTING_LABEL_KEY[row.field])}</td>
                <td>
                  {/* The drawn treatment: the old value struck through, the
                      new value bold, an arrow between. Both go through the
                      SAME formatter the dropdowns use. */}
                  <s className="text-[color-mix(in_srgb,var(--color-text)_55%,transparent)] no-underline line-through">
                    {securityValueLabel(row.field, row.before, props.t)}
                  </s>{" "}
                  <span aria-hidden="true">→</span>{" "}
                  <strong className="font-semibold">
                    {securityValueLabel(row.field, row.after, props.t)}
                  </strong>
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-155-BRC09 (SEC-REDESIGN lane) · US-IDN-010@493ea2f
// generated: 2026-09-29 by lane SEC-REDESIGN, built from
//   05-prototype/security-redesign-2026-09-29/approved-auditcard-1440.png
// exceptions: the READ behind this card (`GET /settings/security-policy/audit`)
//   is the SERVER lane's and is not on the branch at the time of writing. The
//   card renders its failure state against a server that does not serve it
//   yet — deliberately, because drawing zero rows for a read that never
//   answered would say "nothing has changed" when the truth is "we could not
//   find out". Reported.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
