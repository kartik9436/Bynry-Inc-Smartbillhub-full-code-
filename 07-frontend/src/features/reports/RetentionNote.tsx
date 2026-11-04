// ── Trace ──────────────────────────────────────────────
// Change:  `CR-142-BRC07` `P5.12` — *"A door to the retention setting"*. The
//          retention line on `5·1 History` links to Settings → Configure →
//          Reference data → Reports, FOR AN ADMIN ONLY. Drawing p017 (the
//          Phase 5 task table), p047 (screen `E·2`) and p048 (its DOORS row),
//          read as IMAGES per B14 rule 42.
// Rules:   B14 rule 33 (a FACT is ≤ 6 words; a LABEL is ≤ 3 words; RATIONALE
//          is ZERO WORDS ON SCREEN) · rule 43 (a piece of UI is built as a
//          COMPONENT — 120 lines inline in a page is not reuse) · rule 21
//          (Tailwind utilities; this file adds no stylesheet class) · rule 31
//          (no database id on screen) · BR-REP-018 (retention, tenant-
//          configurable) · CLAUDE.md hard-won law 2 AND ITS MIRROR.
// Tests:   07-frontend/src/features/reports/retentionDoor.dom.test.tsx
// Impacts: ReportRunsPage.tsx (mounts this in place of its own <p>) ·
//          apps/reports/api.report_runs (serves `retention_days`) ·
//          features/tenancy/SettingsReferenceData (`?list=file_retention` is
//          the address this opens)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  p048's DOORS row, verbatim:                                            ║
// ║  *"a retention setting nobody can find from the screen it governs is a  ║
// ║   setting nobody uses. P5.12 puts a link on 5·1 History's retention     ║
// ║   line, for an admin only, so the fact and the control are one click    ║
// ║   apart. The line itself stays six words (rule 33); a link is not       ║
// ║   rationale."*                                                          ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// ⚠ **THE NUMBER IS SERVED, NOT TYPED.** Until `P4.6` the sentence was
// *"Files are kept for 3 days."* in all eleven catalogues, over a constant no
// tenant could change. Retention is a tenant setting now, so a hardcoded three
// would be a false sentence on every utility that moved it — and a FALSE fact
// in six words is worse than a long true one. `GET /reports/history` carries
// `retention_days`, computed by the same helper that decides whether a run's
// file has expired, so the sentence and the expiry cannot disagree.
//
// ⚠ **THE LINK IS WITHHELD FROM A CLERK, AND NOTHING EXPLAINS WHY.** A4 gives
// Settings to System Admin; a Billing Clerk following this link would meet a
// 403 on the form behind it, which is hard-won law 2's mirror — a live control
// over a refusal. So the clerk sees the FACT and no link, which is exactly
// what the task table's OUTCOME column asks for: *"a clerk sees the fact and
// no link"*. There is no tooltip saying so: why a control is absent is
// RATIONALE, and rule 33 puts rationale at zero words on screen.
//
// ⚠ **IT IS DISABLED-BY-ABSENCE RATHER THAN A GREYED CONTROL, AND THAT IS THE
// OPPOSITE CALL FROM `ScheduleDoor`.** There the control is drawn inert so a
// returning clerk learns the product has one; here the thing behind the door
// is not the clerk's to have at all, ever, on any tenant. A permanently inert
// control teaches nothing and is one more dead thing to keep true.
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ROLE_SYSTEM_ADMIN, useTenantRole } from "@/features/metering/meteringShared";

/** The Reference-data card this opens — `?list=` is the grid's own deep link. */
export const RETENTION_CARD = "file_retention";

/** Where the control lives. Built here rather than concatenated at the call
 *  site, so one file knows the address and a rename moves one line. */
export function retentionSettingHref(tenant: string): string {
  return `/${tenant}/settings/reference-data/reference-data?list=${RETENTION_CARD}`;
}

export function RetentionNote(props: {
  /** The tenant segment this screen is already standing on. */
  tenant: string;
  /** `GET /reports/history` → `retention_days`. Null while the page loads —
   *  the sentence is NOT drawn over a guess. */
  days: number | null;
}): JSX.Element | null {
  const { t } = useTranslation();
  const role = useTenantRole();
  if (props.days === null) {
    return null;
  }
  return (
    <p className="mt-4 text-sm text-neutral-600" data-retention-note>
      {t("reports.history.retention", { days: props.days })}
      {role === ROLE_SYSTEM_ADMIN ? (
        <>
          {" "}
          <Link
            to={retentionSettingHref(props.tenant)}
            className="underline"
            data-retention-door
          >
            {t("reports.history.retentionDoor")}
          </Link>
        </>
      ) : null}
    </p>
  );
}
