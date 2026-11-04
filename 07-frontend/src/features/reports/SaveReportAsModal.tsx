// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 5 task `P5.4`
//          (*"Screen 2·4 — Save as: name, category, visibility"*).
//          Outcome: *"The saved report appears under Mine in 1·1."*
//          Screens: 2·4 (A1 S47)
// Rules:   ⚠ **A `FormModal`, THE SHARED ONE — NEVER `WizardFrame`** (the task
//          row's own ⚠, and p34 callout ①: *"The report and its parameters are
//          already chosen — you are standing on them. Three fields do not need
//          a rail."*) · B14 rule 38 / 44 (where a drawing and our UI rules
//          disagree about how a FORM is built, the UI rules win — so the footer
//          is Cancel ghost then the filled commit, which is ours) · rule 33 (a
//          LABEL ≤ 3 words; the helper under *Visible to* is a FACT, six words
//          at most, and carries NO rationale) · rule 31 (no database id is ever
//          the visible value of a field — a report is NAMED here and the key is
//          never drawn) · rule 21 (Tailwind only) · rule 13 (two fields to a
//          row where two fit)
// Tests:   07-frontend/src/features/reports/saveReportAs.dom.test.tsx
// Impacts: ReportEditPanel.tsx (opens it) · ReportViewerPage.tsx ·
//          api/reportsEndpoints.ts (`saveReportDefinition`)
// ───────────────────────────────────────────────────────
//
// ⚠ **FOUR FIELDS, NOT THREE.** The task table says *"name, category,
// visibility"*; the DRAWING on p35 has Name · Group · Sub-group · Visible to,
// and its own FIELDS row says *"Four."* Counted off the rendered page, which is
// B14 rule 42 and the reason the summary is an index rather than the
// specification. Group and sub-group are two fields because the catalogue has
// two levels — six groups and nineteen sub-groups — and a report that picks a
// group without a sub-group lands under the group's own heading.
//
// ⚠ **THE NAME IS THE FIELD THE WHOLE FRAMEWORK TURNS ON** (p35 callout ①).
// Today a report's name lives in eleven locale JSON files, which a utility
// cannot edit — so until the name comes out of a ROW, nobody outside Bynry can
// author a report at all. This box is where that stops being true.
//
// ⚠ **THE BUTTON SAYS *Save as*, NOT *Save*, AND THE WORDING IS THE SAFETY**
// (p32's PRIMARY ACTION row). Editing a built-in never overwrites it:
// `tenant_id` is null on a platform row and copy-on-write is the rule
// (`P5.1`), so the commit that reaches this dialog is always a COPY. A button
// that said *Save* over a shipped report would be promising something the
// database refuses.
//
// ⚠ **PRIVATE IS THE DEFAULT AND IT IS A RULING, NOT A PREFERENCE**
// (`BR-REP-019`, brief §8, `P5.7`). *"A half-finished report appearing on a
// colleague's catalogue is how people stop saving."* The helper under the
// field says the fact — *Share it later.* — and says nothing about why, because
// rationale is ZERO WORDS ON SCREEN.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import { FormModal, SelectField, TextField } from "@/components/FormModal";

import type { ReportVisibility, SavedReportDefinition } from "@/api/reportsEndpoints";

/** One catalogue group with its sub-groups, as `GET /reports` serves them.
 *  ⚠ SERVED, never a literal in this file — `P1.5` asserts exactly that, and a
 *  hand-typed list here would not carry the categories a tenant added itself. */
export interface CatalogueGroup {
  code: string;
  name: string;
  sub_groups: { code: string; name: string }[];
}

/** The four fields, mirroring what the server refuses (B8).
 *
 *  ⚠ **THIS SCHEMA IS A CONVENIENCE AND NOT THE WALL.** The reserved names, the
 *  unknown column and the unlawful total are all refused SERVER-SIDE and are
 *  deliberately not restated here: a second validator is a second answer, and
 *  the one the form used would drift from the one the save used. What this
 *  catches is the empty name, so a clerk is not charged a round trip for it. */
function saveAsSchema() {
  return z.object({
    name: z.string().trim().min(1),
    group: z.string().min(1),
    sub_group: z.string().nullable(),
    visibility: z.enum(["private", "shared"]),
  });
}

/**
 * Screen 2·4 — **Save as**.
 *
 * `onSave` posts and returns the saved row. The caller navigates to
 * `saved.key`, which is the SERVER's answer: saving *Overdue 60+* twice gives
 * `overdue-60` and `overdue-60-2`, and a screen that slugged the name itself
 * would open the first after saving the second.
 */
export function SaveReportAsModal(props: {
  /** What the panel is holding, so the dialog opens on it rather than blank. */
  initialName: string;
  initialGroup: string;
  initialSubGroup: string | null;
  initialVisibility?: ReportVisibility;
  groups: CatalogueGroup[];
  onSave: (values: {
    name: string;
    group: string;
    sub_group: string | null;
    visibility: ReportVisibility;
  }) => Promise<SavedReportDefinition>;
  onSaved: (saved: SavedReportDefinition) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState(props.initialName);
  const [group, setGroup] = useState(props.initialGroup);
  const [subGroup, setSubGroup] = useState<string | null>(props.initialSubGroup);
  // BR-REP-019. Absent means PRIVATE — never the column's default.
  const [visibility, setVisibility] = useState<ReportVisibility>(
    props.initialVisibility ?? "private",
  );

  const subGroups = props.groups.find((one) => one.code === group)?.sub_groups ?? [];

  return (
    <FormModal
      title={t("reports.saveAs.title")}
      // ⚠ A FACT under the title, four words: *"A copy you own."* The second
      // half the drawing carries — *"The built-in report is untouched."* — is
      // RATIONALE and is not drawn (rule 33). It lives in this file's docstring
      // and in `apps/reports/definitions.py`, which is where a reason belongs.
      kicker={t("reports.saveAs.subtitle")}
      schema={saveAsSchema()}
      values={{ name: name.trim(), group, sub_group: subGroup, visibility }}
      submitLabel={t("reports.edit.save")}
      onSubmit={async () => {
        // ⚠ **THE SERVER'S REFUSAL HAS TO BE RETURNED, NOT THROWN, OR THE
        // CLERK SEES NOTHING (`DEF-REP-6865`).** `FormModal` renders a refusal
        // from the `{ ok: false, error }` it is handed; an exception escaping
        // this callback is an unhandled rejection, the dialog stays open, and
        // the Save button simply appears to do nothing. That is the shape the
        // refusal catalogue exists to prevent, arriving one layer up from the
        // missing key it usually arrives as. Walked in a browser on
        // 2026-09-27: naming a report *History* was refused correctly by the
        // server, with the right key and the right params, and the screen said
        // NOT ONE WORD.
        try {
          const saved = await props.onSave({
            name: name.trim(),
            group,
            sub_group: subGroup,
            visibility,
          });
          props.onSaved(saved);
          return { ok: true };
        } catch (error) {
          if (isApiError(error)) {
            return { ok: false, error: formErrorEnvelope(error) };
          }
          return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
        }
      }}
      onClose={props.onClose}
    >
      <TextField
        id="name"
        label={t("reports.saveAs.name")}
        value={name}
        onChange={setName}
        required
      />
      <SelectField
        id="group"
        label={t("reports.saveAs.group")}
        value={group}
        onChange={(next) => {
          setGroup(next);
          // A sub-group belongs to a group; keeping it across a change would
          // file the report under a heading its parent does not have.
          setSubGroup(null);
        }}
        options={props.groups.map((one) => ({ value: one.code, label: one.name }))}
        // `DEF-SHL-10751` — a report with no group opens with "", and with no
        // placeholder the box showed the first group while holding none.
        placeholder={t("reports.input.choose")}
        required
      />
      <SelectField
        id="sub_group"
        label={t("reports.saveAs.subGroup")}
        value={subGroup ?? ""}
        onChange={(next) => setSubGroup(next === "" ? null : next)}
        options={subGroups.map((one) => ({ value: one.code, label: one.name }))}
        // `DEF-SHL-10751` — none chosen is legal here, and without a leading
        // empty option the box SHOWED the first sub-group while saving none.
        placeholder={t("reports.input.choose")}
        // ⚠ Not `required`: a report may sit directly under its group. The
        // drawing shows one chosen; `BR-REP-019`'s table allows none.
      />
      <SelectField
        id="visibility"
        label={t("reports.saveAs.visibleTo")}
        value={visibility}
        onChange={(next) => setVisibility(next as ReportVisibility)}
        options={[
          { value: "private", label: t("reports.saveAs.visibility.private") },
          { value: "shared", label: t("reports.saveAs.visibility.shared") },
        ]}
        // Three words, a FACT, and no reason (rule 33).
        help={t("reports.saveAs.shareLater")}
        required
      />
    </FormModal>
  );
}

export default SaveReportAsModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 5 `P5.4` (05-prototype/09 Reports Build Brief.pdf p16 the task row, p35 screen 2·4, read as IMAGES per B14 rule 42)
// screens: 2·4 (A1 S47)
// generated: 2026-09-27 by lane REP-P5
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — see saveReportAs.dom.test.tsx's own gates line. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) the task table says three fields and the DRAWING says four; the drawing is the specification (B14 rule 42) and the extra one is Sub-group · (2) the client schema deliberately does NOT restate the reserved names, the column check or the additivity refusal — those are the server's wall, and a second validator is a second answer · (3) the drawing's *"The built-in report is untouched"* is not drawn: it is rationale, which rule 33 puts at zero words on screen
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
