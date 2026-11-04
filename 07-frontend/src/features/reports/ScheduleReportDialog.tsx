// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.4`. Drawing
//          p34 (screen `2·3`), read as an IMAGE per B14 rule 42: the three
//          fields, their order, the footer and the door are taken from that
//          page and not from a task summary.
// Rules:   B14 rule 44 (the drawing says WHAT is on screen and HOW ARRANGED;
//          our UI standard says how it is BUILT, and wins) · rule 38 (where a
//          drawing and our UI rules disagree about how a FORM is built, the UI
//          rules win — 44's worked case) · rule 43 (a piece of UI is a
//          COMPONENT) · rule 33 (LABEL ≤ 3 words · FACT ≤ 6 words · RATIONALE
//          is ZERO WORDS ON SCREEN) · rule 31 (no database id on screen) ·
//          rule 9 / B14 rule 13 (the kit's multi-select, never a wall of
//          checkboxes) · rule 21 (Tailwind utilities only) · BR-REP-020
//          CONFIRMED (internal staff only)
// Tests:   07-frontend/src/features/reports/scheduleDialog.dom.test.tsx
// Impacts: ReportViewerPage.tsx (the Schedule button — the ONE door) ·
//          api/scheduleEndpoints.ts · ScheduledTab.tsx (where the row lands)
// ───────────────────────────────────────────────────────
//
// SCREEN `2·3` — ONE DIALOG, THREE FIELDS. NOT A WIZARD.
//
// ════════════════════════════════════════════════════════════════════════════
// WHY THIS IS A `FormModal` AND NOT A `WizardFrame`
// ════════════════════════════════════════════════════════════════════════════
// p34 callout ①, verbatim: *"The dialog · `FormModal`, the shared one · ⚠ NOT
// `WizardFrame`. The report and its parameters are already chosen — you are
// standing on them. Three fields do not need a rail."* The brief's own task
// line says the same and flags it as a CORRECTION of an earlier answer in the
// same document: *"A three-step rail over three fields is ceremony."*
//
// The three fields are **How often · Format · Send to**. The report, its
// parameters and its name are INHERITED from the screen behind — which is what
// makes three the right number and what makes `4·1` have no *+ New schedule*
// button (p40: a create control there *"would need a report picker that 2·3
// gets for free"*).
//
// ════════════════════════════════════════════════════════════════════════════
// `Format` IS A SELECT WITH ONE OPTION, AND THAT IS A SIGNED HOLE
// ════════════════════════════════════════════════════════════════════════════
// p34 callout ③: *"Format · SIGNED with a deliberate hole — CSV only, because
// **no PDF renderer is declared anywhere in the product**. Adding PDF here puts
// a control on screen that produces nothing."* `apps/reports/exports.py` has
// carried the same sentence since 2026-08-16 and `DownloadButton`'s `pdf` prop
// is passed by nothing for the same reason.
//
// ⚠ **THE OPTIONS COME FROM THE SERVER'S `formats`, NOT FROM A CONSTANT HERE.**
// The day a renderer lands, the server publishes a second value and this
// control grows it — with no edit to this file. A hardcoded `["csv"]` would be
// the hand-typed list that made an eleventh service invisible on the sign-up
// screen (B14 rule 2's worked case), aimed at a signed hole.
//
// ════════════════════════════════════════════════════════════════════════════
// `Send to` IS THE KIT'S CHIP MULTI-SELECT OVER SERVED USERS — `BR-REP-020`
// ════════════════════════════════════════════════════════════════════════════
// ⚠ **THERE IS NO TEXT INPUT ON THIS SCREEN AT ALL.** `BR-REP-020` is
// CONFIRMED: recipients are internal staff; external ones arrive at W6 with an
// explicit confirm step because an external send means data leaves the tenant.
// The brief states the consequence for this screen in one sentence — *"A
// free-text email box here breaks a signed ruling"* — so the control is a
// picker over `staff`, which the server serves and this file never invents.
//
// ⚠ **`ChipMultiSelect` AND NOT A COLUMN OF CHECKBOXES** (B14 rule 9). A
// utility of ten to twenty staff is a list a person scans; a wall of tick
// boxes is what the rule exists to refuse.
//
// ════════════════════════════════════════════════════════════════════════════
// THE FOOTER IS OURS AND NOT THE DRAWING'S — B14 rule 38
// ════════════════════════════════════════════════════════════════════════════
// p34 callout ⑤: *"Footer order · Cancel ghost, then the filled commit · B14
// rule 38 — where a drawing and our UI rules disagree about how a form is
// built, the UI rules win."* `FormModal` owns that footer, so this file passes
// a label and nothing else. The commit is `primary` and NOT the danger tier:
// it creates a row, and the row can be deleted.
//
// ⚠ **THERE IS NO SENTENCE ON THIS SCREEN EXPLAINING WHY EXTERNAL RECIPIENTS
// ARE ABSENT.** That is RATIONALE, and B14 rule 33 puts rationale at ZERO
// WORDS ON SCREEN. It lives here and in `BR-REP-020`.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { Cadence, ScheduleFormat, SchedulePage } from "@/api/scheduleEndpoints";
import { createSchedule } from "@/api/scheduleEndpoints";
import { ChipMultiSelect } from "@/components/ChipMultiSelect";
import { FieldLabel, FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { useToast } from "@/components/Toast";

/**
 * The client-side mirror of the server's three refusals (B8: the schema
 * mirrors the VAL codes, it does not replace them).
 *
 * ⚠ **`recipients` IS `.min(1)` AND THAT IS A RULE RATHER THAN A FORM
 * CONVENTION.** A schedule with nobody on it produces a file every month and
 * tells no one — which looks exactly like the product working.
 * `schedules.resolve_recipients` refuses the same case on the server; this is
 * the half that says so before the round trip.
 */
const SCHEDULE_SCHEMA = z.object({
  cadence: z.string().min(1),
  format: z.string().min(1),
  recipients: z.array(z.string()).min(1),
});

export function ScheduleReportDialog(props: {
  /** The report being scheduled — its KEY, from the screen behind. */
  definitionKey: string;
  /** What that screen is currently showing. Frozen into the schedule. */
  params: Record<string, unknown>;
  /** The vocabularies and the staff list, SERVED. See the header. */
  options: Pick<SchedulePage, "cadences" | "formats" | "staff">;
  onClose: () => void;
  /** Fired after a successful commit so the caller can refresh `4·1`. */
  onCreated?: () => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const client = props.client ?? api;
  // The first option of each SERVED vocabulary, never a literal. An empty
  // vocabulary leaves the field empty and the schema refuses the commit, which
  // is the honest behaviour for a server that published nothing.
  const [cadence, setCadence] = useState<string>(props.options.cadences[0] ?? "");
  const [format, setFormat] = useState<string>(props.options.formats[0] ?? "");
  const [recipients, setRecipients] = useState<string[]>([]);

  async function commit(): Promise<FormSubmitOutcome> {
    try {
      await createSchedule(
        {
          definition_key: props.definitionKey,
          cadence: cadence as Cadence,
          format: format as ScheduleFormat,
          recipients,
          params: props.params,
        },
        client,
      );
    } catch (problem) {
      // `SettingsUsersTab`'s shape, deliberately: a B12 §3 envelope is handed
      // to `FormModal`'s own loop — which renders `field_errors` against the
      // fields and focuses the first — and anything else is a TRANSPORT fault
      // that gets the kit's generic sentence. A second copy of the envelope
      // grammar here is what drifts.
      if (isApiError(problem)) {
        return { ok: false, error: formErrorEnvelope(problem) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
    toast(t("reports.schedule.created"));
    props.onCreated?.();
    props.onClose();
    return { ok: true };
  }

  return (
    <FormModal
      title={t("reports.schedule.title")}
      schema={SCHEDULE_SCHEMA}
      values={{ cadence, format, recipients }}
      onSubmit={commit}
      onClose={props.onClose}
      submitLabel={t("reports.schedule.commit")}
    >
      {/* ① How often — the four SIGNED cadences, as WORDS (p40 ①: *"never a
          cron string"*). The labels are the catalogue's, in eleven languages;
          the VALUES are the server's machine tokens. */}
      <SelectField
        id="schedule-cadence"
        label={t("reports.schedule.cadence")}
        value={cadence}
        onChange={setCadence}
        required
        options={props.options.cadences.map((value) => ({
          value,
          label: t(`reports.schedule.cadence.${value}`),
        }))}
      />
      {/* ② Format — one option today, on purpose. See this file's header. */}
      <SelectField
        id="schedule-format"
        label={t("reports.schedule.format")}
        value={format}
        onChange={setFormat}
        required
        options={props.options.formats.map((value) => ({
          value,
          label: t(`reports.schedule.format.${value}`),
        }))}
      />
      {/* ③ Send to — this tenant's own users, and nothing else.
          ⚠ `ChipMultiSelect` has no `label` slot of `FieldLabel`'s shape, so
          the label is rendered beside it the way the kit's other composed
          fields do. `required` is TRUE here and the schema enforces it. */}
      <div className="field">
        <FieldLabel htmlFor="schedule-recipients" label={t("reports.schedule.sendTo")} required />
        <ChipMultiSelect
          label={t("reports.schedule.sendTo")}
          testKey="schedule-recipients"
          options={props.options.staff.map((person) => ({
            value: person.id,
            label: person.name,
          }))}
          selected={recipients}
          onChange={setRecipients}
          addLabel={t("reports.schedule.addRecipient")}
          emptyLabel={t("reports.schedule.noRecipients")}
          removeLabel={t("reports.schedule.removeRecipient")}
        />
      </div>
    </FormModal>
  );
}

export default ScheduleReportDialog;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.4 (05-prototype/09 Reports Build Brief.pdf p34, read as an image per B14 rule 42)
// screens: 2·3
// generated: 2026-09-27 by lane REP-P4
// checklist: A=n/a(the backend half is schedules_api.py) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — scheduleDialog.dom.test.tsx was run before this file existed and reported `Cannot find module './ScheduleReportDialog'`. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) `Format` is a select with ONE option — a SIGNED hole (p34 ③), served rather than hardcoded so a PDF renderer's arrival needs no edit here · (2) no sentence explains the absence of external recipients: that is RATIONALE and B14 rule 33 puts it at zero words on screen
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
