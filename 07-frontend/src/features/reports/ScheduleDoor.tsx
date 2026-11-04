// ── Trace ──────────────────────────────────────────────
// Change:  `DEF-REP-6913` — `ScheduleReportDialog` was built, tested and
//          mounted by NOTHING, so a person could not schedule a report in this
//          product at all. This is the DOOR. Drawing p034 (screen `2·3`) and
//          p028 (`2·1e`, which draws the header action row), read as IMAGES
//          per B14 rule 42.
// Rules:   B14 rule 43 (a piece of UI is built as a COMPONENT — standalone
//          code inside a page is not reuse) · rule 33 (a LABEL is ≤ 3 words
//          and RATIONALE is ZERO WORDS ON SCREEN) · rule 5 (two button tiers)
//          · rule 21 (Tailwind utilities, no stylesheet class — this file
//          adds no class at all) · CLAUDE.md hard-won law 2 AND ITS MIRROR
//          · BR-REP-020 CONFIRMED (internal staff only).
// Tests:   07-frontend/src/features/reports/scheduleDoor.dom.test.tsx
// Impacts: ReportViewerPage.tsx (mounts this in `secondaryActions`) ·
//          ScheduledTab.tsx (where the new row lands, via the shared key)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  ONE DOOR, AND IT IS DISABLED OVER A REFUSAL                            ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// p034's DOORS row, verbatim: *"One: the Schedule button on 2·1. ⚠ It is
// **disabled** where the report cannot be produced — you cannot schedule a
// refusal (see 2·1d)."* Both halves are load-bearing and they pull opposite
// ways, which is why the drawing says which wins:
//
//   · **ONE door.** `4·1` has no *+ New schedule* button, because a create
//     control there *"would need a report picker that 2·3 gets for free"*
//     (p040). You schedule the report you are standing on.
//   · **DISABLED, not absent.** A report that cannot be produced still draws
//     the control so that a returning clerk learns the product has one — but
//     it cannot be pressed, because scheduling a refusal produces an empty
//     file every month for ever and looks exactly like the product working.
//     That is CLAUDE.md hard-won law 2's MIRROR: a live screen behind a dead
//     control is the more expensive half, and the cure is that the refusal is
//     TRUE rather than that the control is hidden.
//
// ⚠ **THERE IS NO TOOLTIP EXPLAINING THE DISABLED STATE.** Why a control is
// absent or inert is RATIONALE, and B14 rule 33 puts rationale at ZERO WORDS
// ON SCREEN. The report's own unavailable panel is already saying, in six
// words, that the report cannot be produced; a second sentence on the button
// would be the same fact twice and the rule's worked case.
//
// ════════════════════════════════════════════════════════════════════════════
// THE OPTIONS ARE FETCHED WHEN THE DOOR IS OPENED, NOT WHEN THE SCREEN LOADS
// ════════════════════════════════════════════════════════════════════════════
// The dialog's three fields are SERVED — the two signed vocabularies and this
// tenant's staff — and they arrive on `GET /reports/schedules`, which is also
// `4·1`'s list. Fetching it on every report view would put a second request on
// a screen whose whole job is one expensive read, for a dialog most visits
// never open. So the query is `enabled` only once the button has been pressed.
//
// ⚠ **`per: 1` BECAUSE THE ROWS ARE NOT WANTED, ONLY THE VOCABULARIES.** The
// envelope carries `cadences`, `formats` and `staff` beside the page, and this
// screen needs exactly those. It is NOT `per: 0`: `_positive_int` falls back on
// a non-positive value, so nought would quietly fetch the default page.
//
// ⚠ **THE QUERY KEY IS THE ONE `ScheduledTab` ALREADY USES**, so committing a
// schedule here invalidates the list there rather than leaving `4·1` showing a
// world without the row a person just created.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getSchedules } from "@/api/scheduleEndpoints";
import { Button } from "@/components/Button";

import { ScheduleReportDialog } from "./ScheduleReportDialog";

export const SCHEDULES_QUERY_KEY = "report-schedules";

export function ScheduleDoor(props: {
  /** The report being scheduled — its KEY, from the screen this sits on. */
  definitionKey: string;
  /** What that screen is currently showing. Frozen into the schedule. */
  params: Record<string, unknown>;
  /** True where the report cannot be produced — p034's DOORS row. */
  disabled?: boolean;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const client = props.client ?? api;
  const [open, setOpen] = useState(false);

  const options = useQuery({
    queryKey: [SCHEDULES_QUERY_KEY, "options"],
    queryFn: () => getSchedules({ per: 1 }, client),
    enabled: open,
  });

  return (
    <>
      {/* ⚠ **SECONDARY, AND THE DRAWING AGREES.** p028 draws the `2·1` action
          row as *Schedule · Edit · Save as* with only the last one filled, and
          B14 rule 5 allows exactly one primary tier per screen. The FILLED
          commit lives inside the dialog, on *Schedule it*, which is where the
          act that writes a row actually happens. */}
      <Button variant="secondary" disabled={props.disabled} onClick={() => setOpen(true)}>
        {t("reports.schedule.door")}
      </Button>
      {/* ⚠ **RENDERED ONLY WHEN THE OPTIONS ARE IN HAND.** A dialog opened over
          an empty `cadences` would draw two empty selects and an empty picker,
          and its schema would then refuse the commit — a form that cannot be
          completed and does not say so. Waiting is the honest state. */}
      {open && options.data !== undefined ? (
        <ScheduleReportDialog
          definitionKey={props.definitionKey}
          params={props.params}
          options={options.data}
          client={client}
          onClose={() => setOpen(false)}
          onCreated={() => {
            // `4·1` is where the row lands (p034 ④). Invalidating the family
            // rather than one key means the tab refetches whatever page and
            // filter it happens to be sitting on.
            void queryClient.invalidateQueries({ queryKey: [SCHEDULES_QUERY_KEY] });
          }}
        />
      ) : null}
    </>
  );
}

export default ScheduleDoor;

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-REP-6913 (05-prototype/09 Reports Build Brief.pdf p028 + p034, read as images per B14 rule 42)
// screens: 2·1 (the door) → 2·3 (the dialog)
// generated: 2026-09-27 by lane REP-DOOR
// checklist: A=n/a(no backend change here) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — scheduleDoor.dom.test.tsx was run against ReportViewerPage before this file existed and reported `Unable to find an accessible element with the role "button" and name "reports.schedule.door"` three times.
// exceptions: (1) the disabled state carries NO tooltip and NO sentence — that is rationale, and B14 rule 33 puts rationale at zero words on screen · (2) the options query is `enabled` on open rather than on mount, so a report view that never schedules pays no second request
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
