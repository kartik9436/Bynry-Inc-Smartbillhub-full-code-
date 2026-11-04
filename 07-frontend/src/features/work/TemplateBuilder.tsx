// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-016 (EP-WRK-03) — *"the eight-step template builder the PO
//           designed and nobody built, with starter packs on step 1 that
//           prefill the rest"*. Screens: Work-014 (`wireframes/Work-014.png`)
//           · Work-015 · Work-016 · Work-017, template W3
// Rules:    BR-WRK-011 (Publish is the ONE write; seven steps of editing
//           persist as a DRAFT) · BR-WRK-008 (copy, never link — the
//           consequence box says it before the button) · BR-WRK-009 (rows,
//           not a blob) · BR-WRK-015 (a reading's unit is a column) ·
//           BR-MET-109 (the utility's own templates) · BR-SHL-019 (ONE
//           transactional commit, single-flighted by the frame) · B14 rules
//           1, 2, 3, 5, 6, 11, 17, 21, 31, 32 · CLAUDE.md hard rule 3
// Tests:    src/features/work/TemplateBuilder.test.tsx ·
//           src/features/work/templateBuilderModel.test.ts
// Impacts:  src/App.tsx (two routes) · src/routing/screenIds.ts (WRK-05.1–8)
//           · src/features/work/TemplatesPage.tsx (the `+ New template`
//           primary the hold released) · TemplateDetailPage.tsx (*Edit
//           template*) · src/features/work/workEndpoints.ts
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS IS THE SCREEN TWO HOLDS WERE WAITING FOR, AND LANDING IT IS HALF
// THE JOB.** Wave D wrote `+ New template` and *Edit template* as ABSENT, each
// with a test that goes RED the day this file exists — hard-won law 2's second
// shape (`DEF-CWP-3925`: a live screen behind a dead control). Both tests are
// rewritten in the same commit as this file, from *"there is no such button"*
// to *"the button goes HERE and opens THIS screen"*. A hold with no such test
// is a promise nobody is keeping; a hold whose test is deleted rather than
// inverted is worse.
//
// ⚠ **ONE WRITE REACHES A WORK ORDER AND IT IS THE LAST BUTTON** (`BR-WRK-011`).
// Steps 1 to 7 are a draft in this browser. *Save draft* persists the header
// and the six collections as ROWS a tab can lose without loss; *Publish
// template* saves them and then calls the one route that allocates `ST-{0000}`,
// sets the version and makes the template something New Connect step 6 will
// propose. Closing the tab at step 7 leaves NO published template
// (`US-WRK-016` TC-2) and no row at all unless *Save draft* was pressed.
//
// ⚠ **PRESSED TWICE QUICKLY, PUBLISH MAKES ONE VERSION** (`US-WRK-016` TC-4).
// Two guards, and they answer different halves: `WizardFrame` single-flights
// the commit so a second press never starts a second call (`BR-SHL-019`), and
// the SERVER answers the version that already exists when nothing in the
// bundle has changed since the last publish. A screen-only guard would leave a
// scripted double call making a v2 identical to v1.
//
// ⚠ **THE PACK IS PREFILL AND IS NEVER STORED.** Nothing on a template records
// which pack it came from; `packCode` lives in this component's state so step 1
// can show which tile is chosen, and dies with the tab. Confusing a PACK with
// the 24 seeded STARTERS would make a utility's edits vanish on the next
// provisioning sweep (`apps/work/packs/__init__.py` says the same thing from
// the other end).
//
// ⚠ **THE STEP-1 HELP LINE CARRIES NO `WM-04`.** `wireframes/Work-014.png`
// draws *"From the job type catalogue — WM-04"* and B14 rule 32 forbids a rule
// id in clerk-facing copy, so the sentence stands alone. The divergence is
// stamped in `08-screen-layouts.md`.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getLookupEntries, getTenantServices } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { ChipMultiSelect } from "@/components/ChipMultiSelect";
import { EditableTable } from "@/components/EditableTable";
import { CheckboxField, SelectField, TextField } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { Note } from "@/components/TextBits";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { useToast } from "@/components/Toast";
import { useTenantPath } from "@/routing/tenantPath";

import { WORK_ORDER_TEMPLATES_ROUTE } from "./WorkShell";
import { jobTypeChoices } from "./raise/raiseModel";
import { HelpWhere, TemplateSummary, VideoBadge, helpKindWord, scopeWord } from "./TemplateSummary";
import type { TemplateSummaryNames } from "./TemplateSummary";
import {
  createTemplateDraft,
  getRaiseOptions,
  getTemplate,
  getTemplatePacks,
  listParts,
  publishTemplate,
  replaceTemplateCollection,
  updateTemplateHeader,
  uploadHelpDocument,
} from "./workEndpoints";
import type { HelpDocumentStored, TemplateCollection, TemplatePack } from "./workEndpoints";
import {
  HELP_KINDS_OFFERED,
  MONEY_CHECK_DEFAULT_MINUTES,
  TEMPLATE_SCOPES,
  applyPack,
  clearPack,
  collectionPayloads,
  draftFromTemplate,
  emptyBuilderDraft,
  headerPayload,
  helpRowAddable,
  helpRowMissing,
  isHttpsAddress,
  isVideoAddress,
  step1Complete,
  taskMinutes,
} from "./templateBuilderModel";
import type { BuilderDraft } from "./templateBuilderModel";

/** r10's own badge for the template wizard. Its `sid()` emits
 *  `'WRK-05.' + (s.twStep || 1)` — a badge PER STEP, exactly like `ONB-04.n`
 *  on the signup wizard — so nothing here is minted (`g29`). */
export const TEMPLATE_BUILDER_SCREEN = "WRK-05";

/** `…/work/templates/new` — the builder, empty. */
export const WORK_TEMPLATE_NEW_ROUTE = `${WORK_ORDER_TEMPLATES_ROUTE}/new`;

/** Where *Edit template* on `Work-022` goes. ONE function, so the detail page
 *  and any later caller cannot disagree about the address (law 5). */
export function templateEditPath(templateId: string): string {
  return `${WORK_ORDER_TEMPLATES_ROUTE}/${templateId}/edit`;
}

const STEP_PARAM = "step";

/** The eight, in the drawing's own order and words (`Work-014`'s `Stepper`).
 *
 *  ⚠ `labelKey` is LITERAL on every row so `G18` can see the catalogue keys — a
 *  template key (`work.builder.step.${id}`) renders perfectly and is invisible
 *  to the gate, so all eight would report as dead entries the day they are
 *  translated. The New Connect wizard's own list carries the same note. */
export const TEMPLATE_BUILDER_STEPS = [
  { id: "details", labelKey: "work.builder.step.details", en: "Details" },
  { id: "safety", labelKey: "work.builder.step.safety", en: "Safety" },
  { id: "tasks", labelKey: "work.builder.step.tasks", en: "Tasks" },
  { id: "materials", labelKey: "work.builder.step.materials", en: "Materials" },
  { id: "readings", labelKey: "work.builder.step.readings", en: "Readings" },
  { id: "help", labelKey: "work.builder.step.help", en: "Help & support" },
  { id: "signature", labelKey: "work.builder.step.signature", en: "Signature" },
  { id: "review", labelKey: "work.builder.step.review", en: "Review" },
] as const;

type Translate = (key: string, params?: Record<string, unknown>) => string;

function clampStep(raw: string | null): number {
  const parsed = Number(raw ?? "1");
  if (!Number.isInteger(parsed)) return 1;
  return Math.min(Math.max(1, parsed), TEMPLATE_BUILDER_STEPS.length);
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 1 · DETAILS — the packs, the header, and what the technician sees
// ══════════════════════════════════════════════════════════════════════════

/**
 * `Work-014`'s tile text — *7 tasks · 3 parts · 3 readings*.
 *
 * It borrows `Work-013`'s CONTENTS keys rather than minting a sentence of its
 * own: the two say the same thing about the same three collections, the
 * existing keys already carry `_one`/`_other` in all eleven catalogues, and a
 * single key holding three raw numbers cannot pluralise any of them.
 */
export function packSummary(pack: TemplatePack, t: Translate): string {
  return [
    t("work.templates.contents.tasks", { count: pack.tasks, defaultValue: "{{count}} tasks" }),
    t("work.templates.contents.parts", { count: pack.parts, defaultValue: "{{count}} parts" }),
    t("work.templates.contents.readings", {
      count: pack.readings,
      defaultValue: "{{count}} readings",
    }),
  ].join(" · ");
}

/** `Work-014`'s tile — a title and a one-line count. The count comes from the
 *  SERVER, which counts the pack's own rows; nothing here adds up. */
export function PackCard(props: {
  name: string;
  summary: string;
  chosen: boolean;
  onChoose: () => void;
  testKey: string;
}) {
  return (
    /* ⚠ **THE KIT'S `Button`, NOT A `<button>` OF ITS OWN** (B14 rule 36, and
       `G86` refuses the hand-rolled form by name). A pack tile IS a control a
       person presses; what it needs on top of the kit is LAYOUT — a column
       rather than a row, left-aligned, and a minimum width so four tiles wrap
       together — and `className` is the slot the kit publishes for exactly
       that. The CHOSEN state is the accent border, which the kit's own
       `border-accent` token supplies rather than a colour written here. */
    <Button
      variant="secondary"
      onClick={props.onChoose}
      data-pack={props.testKey}
      aria-pressed={props.chosen}
      className={
        props.chosen
          ? "min-w-[180px] flex-1 flex-col items-start text-left border-accent"
          : "min-w-[180px] flex-1 flex-col items-start text-left"
      }
    >
      <span className="block font-semibold">{props.name}</span>
      <span className="block text-sm font-normal text-neutral-700">{props.summary}</span>
    </Button>
  );
}

function DetailsStep(props: {
  draft: BuilderDraft;
  onPatch: (next: Partial<BuilderDraft>) => void;
  packs: TemplatePack[];
  services: { value: string; label: string }[];
  jobTypes: {
    options: { value: string; label: string }[];
    groups: { label: string; options: { value: string; label: string }[] }[];
  };
  skills: { value: string; label: string }[];
  kits: { value: string; label: string }[];
  assetTypes: { value: string; label: string }[];
  t: Translate;
}) {
  const { t } = props;
  return (
    <>
      <h3 className="font-heading text-h5 m-0 mb-1">
        {t("work.builder.details.title", { defaultValue: "What job is this template for?" })}
      </h3>
      <Note className="mb-4 max-w-measure">
        {t("work.builder.details.sentence", {
          defaultValue:
            "Start from a ready-made pack — it prefills safety, tasks, materials, readings and help. Everything stays editable.",
        })}
      </Note>

      <Panel as="section" title={t("work.builder.packs.title", { defaultValue: "Start from a pack" })}>
        <div className="flex flex-wrap gap-3" data-packs="">
          {props.packs.map((pack) => (
            <PackCard
              key={pack.code}
              testKey={pack.code}
              name={pack.name}
              /* ⚠ **THE SAME THREE KEYS `Work-013`'s CONTENTS CELL USES**, and
                 that is the 2026-09-05 ruling applied to a sentence: does this
                 product already answer this question somewhere? It does —
                 `contentsSentence` on the list — and those keys already carry
                 `_one`/`_other` in all eleven catalogues. One sentence with
                 three raw numbers in it could not pluralise at all: a pack with
                 one part would read *"1 parts"* in every language that
                 distinguishes them. */
              summary={packSummary(pack, t)}
              chosen={props.draft.packCode === pack.code}
              onChoose={() => props.onPatch(applyPack(props.draft, pack))}
            />
          ))}
          {/* The fourth tile. It is a real choice and not the absence of one:
              a utility that knows its own job wants a blank sheet, and the
              drawing gives it equal weight. */}
          <PackCard
            testKey="EMPTY"
            name={t("work.builder.packs.empty", { defaultValue: "Start empty" })}
            summary={t("work.builder.packs.emptySummary", { defaultValue: "Write your own" })}
            chosen={props.draft.packCode === "EMPTY"}
            onChoose={() => props.onPatch(clearPack(props.draft))}
          />
        </div>
        {/* A pack names parts by NUMBER and this utility may not hold them.
            Saying which is missing beats offering one row fewer in silence. */}
        {props.packs.some((pack) => pack.unresolved_parts.length > 0) && (
          <Note className="mt-3 max-w-measure" data-packs-missing="">
            {t("work.builder.packs.missingParts", {
              defaultValue:
                "Some packs name parts your register does not hold yet: {{parts}}. Add them under Parts and the pack will bring them in.",
              parts: [
                ...new Set(props.packs.flatMap((pack) => pack.unresolved_parts)),
              ].join(", "),
            })}
          </Note>
        )}
      </Panel>

      <Panel as="section" title={t("work.builder.header.title", { defaultValue: "This template" })}>
        <TextField
          id="wtb_name"
          label={t("work.builder.field.name", { defaultValue: "Name" })}
          value={props.draft.name}
          onChange={(name) => props.onPatch({ name })}
          required
        />
        <SelectField
          id="wtb_service"
          label={t("work.builder.field.service", { defaultValue: "Service" })}
          value={props.draft.service}
          onChange={(service) => props.onPatch({ service })}
          options={props.services}
          placeholder={t("work.builder.field.choose", { defaultValue: "Choose one" })}
          required
        />
        {/* P3.12 (`DEF-WRK-9577`) — asked, never defaulted. The builder never
            sent `scope`, so every template it made saved as premises by the
            column's default, and a meter template was offered on the account
            door. Placed beside Service because the two together decide which
            raise doors offer the template (B18 §8.2). Image 48 does not draw
            it; the summary's *Done to* (images 44, 55) is the same fact. */}
        <SelectField
          id="wtb_scope"
          label={t("work.builder.field.scope", { defaultValue: "Done to" })}
          value={props.draft.scope}
          onChange={(scope) => props.onPatch({ scope })}
          options={TEMPLATE_SCOPES.map((scope) => ({ value: scope, label: scopeWord(scope, t) ?? scope }))}
          placeholder={t("work.builder.field.choose", { defaultValue: "Choose one" })}
          required
        />
        <SelectField
          id="wtb_type"
          label={t("work.builder.field.jobType", { defaultValue: "Job type" })}
          value={props.draft.jobTypeId}
          onChange={(jobTypeId) => props.onPatch({ jobTypeId })}
          // `DEF-WRK-9582`'s builder half — the two-level picker lane RAISE
          // built: a heading with sub-types is a group, its sub-types the
          // options (`jobTypeChoices`, one function for both screens).
          options={props.jobTypes.options}
          groups={props.jobTypes.groups}
          placeholder={t("work.builder.field.choose", { defaultValue: "Choose one" })}
          /* ⚠ B14 rule 32 — the drawing writes *"From the job type catalogue —
             WM-04"* and a rule id never reaches clerk-facing copy. */
          help={t("work.builder.field.jobTypeHelp", {
            defaultValue: "From the job type catalogue.",
          })}
        />
        <ChipMultiSelect
          label={t("work.builder.field.assetTypes", { defaultValue: "Applies to asset types" })}
          options={props.assetTypes}
          selected={props.draft.assetTypeIds}
          onChange={(assetTypeIds) => props.onPatch({ assetTypeIds })}
          addLabel={t("work.builder.field.addAssetType", { defaultValue: "Add an asset type…" })}
          emptyLabel={t("work.builder.field.noAssetTypes", { defaultValue: "Any asset type" })}
          removeLabel={t("work.builder.field.removeAssetType", { defaultValue: "Remove" })}
          testKey="asset-types"
        />
        <SelectField
          id="wtb_skill"
          label={t("work.builder.field.skill", { defaultValue: "Skill needed" })}
          value={props.draft.skillId}
          onChange={(skillId) => props.onPatch({ skillId })}
          options={props.skills}
          placeholder={t("work.builder.field.anySkill", { defaultValue: "No particular skill" })}
        />
        <TextField
          id="wtb_crew"
          label={t("work.builder.field.crewSize", { defaultValue: "Crew size" })}
          value={props.draft.crewSize}
          onChange={(crewSize) => props.onPatch({ crewSize })}
          numeric
        />
        <SelectField
          id="wtb_kit"
          label={t("work.builder.field.safetyKit", { defaultValue: "Safety kit" })}
          value={props.draft.safetyKitId}
          onChange={(safetyKitId) => props.onPatch({ safetyKitId })}
          options={props.kits}
          placeholder={t("work.builder.field.noKit", { defaultValue: "No kit named" })}
        />
      </Panel>

      <Panel
        as="section"
        title={t("work.builder.sees.title", { defaultValue: "What the technician sees on the job" })}
      >
        <div className="flex flex-wrap gap-x-6 gap-y-2" data-sees="">
          <CheckboxField
            id="wtb_sees_account"
            label={t("work.builder.sees.account", { defaultValue: "Account & premise summary" })}
            checked={props.draft.showAccountSummary}
            onChange={(showAccountSummary) => props.onPatch({ showAccountSummary })}
          />
          <CheckboxField
            id="wtb_sees_asset"
            label={t("work.builder.sees.asset", { defaultValue: "Asset card — meter ID, last read" })}
            checked={props.draft.showAssetCard}
            onChange={(showAssetCard) => props.onPatch({ showAssetCard })}
          />
          <CheckboxField
            id="wtb_sees_access"
            label={t("work.builder.sees.access", { defaultValue: "Access notes & hazards" })}
            checked={props.draft.showAccessNotes}
            onChange={(showAccessNotes) => props.onPatch({ showAccessNotes })}
          />
          <CheckboxField
            id="wtb_sees_appointment"
            label={t("work.builder.sees.appointment", {
              defaultValue: "Appointment window & customer phone",
            })}
            checked={props.draft.showAppointment}
            onChange={(showAppointment) => props.onPatch({ showAppointment })}
          />
          {/* FB-023 F4 (PO 2026-10-31) — hides the phone's balance card and
              payment facts; never the disconnect step's cleared-balance stop. */}
          <CheckboxField
            id="wtb_sees_balance"
            label={t("work.builder.sees.balance", { defaultValue: "Balance & payments" })}
            checked={props.draft.showBalancePayments}
            onChange={(showBalancePayments) => props.onPatch({ showBalancePayments })}
          />
        </div>
      </Panel>

      {/* `DEF-WRK-10652` (PO 2026-10-29, rulings 3B and 4A) — what the
          CUSTOMER hears about this template's jobs. The switch is OFF on the
          seeded disconnect and reconnect templates: the disconnect notices
          speak for those visits. Blank preparation text uses the utility's
          default; the reason is in the code, not on screen (B14 rule 33). */}
      <Panel
        as="section"
        title={t("work.builder.customer.title", { defaultValue: "Customer messages" })}
      >
        <div className="flex max-w-measure flex-col gap-3" data-customer-messages="">
          <CheckboxField
            id="wtb_customer_messages"
            label={t("work.builder.customer.send", { defaultValue: "Send customer visit messages" })}
            checked={props.draft.sendCustomerVisitMessages}
            onChange={(sendCustomerVisitMessages) => props.onPatch({ sendCustomerVisitMessages })}
          />
          <TextField
            id="wtb_prep_instructions"
            label={t("work.builder.customer.prep", { defaultValue: "Preparation instructions" })}
            value={props.draft.prepInstructions}
            onChange={(prepInstructions) => props.onPatch({ prepInstructions })}
            multiline
            help={t("work.builder.customer.prepHelp", {
              defaultValue: "Shown in customer visit messages. Blank uses the utility default.",
            })}
          />
        </div>
      </Panel>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEPS 2–6 · THE FIVE COLLECTIONS — each an EditableTable with an add row
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY ADDED ROW EDITS IN PLACE — RULING 5 (24 Sep), `DEF-WRK-9565` and
// `9566`.** *"if the users adds a task and then need to correct it there is not
// edit available there"*, widened the same day to Safety, Materials, Readings
// and Help. Until `2.504.0` thirteen cells across the five steps were plain
// text after *+ Add*, so a typo meant delete and retype. Twelve are now boxes
// and a picked value (a part, a help kind) is the same list its add row uses.
// ⚠ **ONE CELL STAYS READ-ONLY ON PURPOSE: a material's UNIT.** It arrives with
// the part (hard rule 3); a box for it would let *2 each* of a part sold by the
// metre be typed, which is a second answer to a question the register owns.
//
// `PUT …/{collection}` already replaces the whole collection, so editing a row
// is an edit of the draft in memory and *Save draft* / *Publish* send it — no
// endpoint, no migration (P3.13).

/** The accessible names every `EditableTable` row control needs, in one place
 *  so five tables cannot disagree. */
function rowLabels(t: Translate): {
  moveUp: string;
  moveDown: string;
  remove: string;
  position: string;
} {
  return {
    moveUp: t("work.builder.row.up", { defaultValue: "Move up" }),
    moveDown: t("work.builder.row.down", { defaultValue: "Move down" }),
    remove: t("work.builder.row.remove", { defaultValue: "Remove" }),
    position: t("work.builder.row.position", { defaultValue: "row" }),
  };
}

/** *Task 2*, *Quantity 1* — a cell box's accessible name: its column and the
 *  row number the `#` column prints. */
function cellName(t: Translate, column: string, index: number): string {
  return t("work.builder.row.cell", { column, row: index + 1, defaultValue: "{{column}} {{row}}" });
}

/** Replace row `index` of a list with `patch` applied — the one edit every
 *  in-place box makes. */
function patchRow<Row>(rows: Row[], index: number, patch: Partial<Row>): Row[] {
  return rows.map((row, i) => (i === index ? { ...row, ...patch } : row));
}

const BOX = "border border-divider bg-surface px-2 py-1 text-base";

/** A box fills its cell unless the caller names a width — `w-full` beside a
 *  width class is decided by stylesheet order, not by the caller, which is how
 *  the Minutes boxes once stretched across the table. */
function boxWidth(className: string | undefined): string {
  return className !== undefined && /(^|\s)(w-|max-w-)/u.test(className) ? "" : "w-full";
}

/** One text box — in an add row (the placeholder is what a person reads) or in
 *  a row being edited (the value is). A one-line row has no space for the
 *  shared `TextField`'s label block, so the label is the accessible name. */
function CellInput(props: {
  id?: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  numeric?: boolean;
  placeholder?: string;
  className?: string;
}) {
  return (
    <input
      id={props.id}
      className={`${BOX} ${boxWidth(props.className)} ${props.numeric === true ? "text-right tabular-nums" : ""} ${props.className ?? ""}`}
      aria-label={props.label}
      placeholder={props.placeholder ?? props.label}
      inputMode={props.numeric === true ? "decimal" : undefined}
      value={props.value}
      onChange={(event) => props.onChange(event.target.value)}
    />
  );
}

/** One native select inside a table row or an add row, with the chevron the
 *  kit's selects carry (B14 rule 3). */
function CellSelect(props: {
  id?: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  className?: string;
}) {
  return (
    <select
      id={props.id}
      className={`${BOX} ${boxWidth(props.className)} ${props.className ?? ""}`}
      aria-label={props.label}
      value={props.value}
      onChange={(event) => props.onChange(event.target.value)}
    >
      {props.placeholder === undefined ? null : <option value="">{props.placeholder}</option>}
      {props.options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

function AddButton(props: { collection: string; disabled: boolean; onAdd: () => void; t: Translate }) {
  return (
    <Button variant="secondary" size="sm" disabled={props.disabled} data-add={props.collection} onClick={props.onAdd}>
      {props.t("work.builder.add", { defaultValue: "+ Add" })}
    </Button>
  );
}

function StepHead(props: { title: string; sentence: string }) {
  return (
    <>
      <h3 className="font-heading text-h5 m-0 mb-1">{props.title}</h3>
      <Note className="mb-4 max-w-measure">{props.sentence}</Note>
    </>
  );
}

function SafetyStep(props: {
  draft: BuilderDraft;
  onPatch: (next: Partial<BuilderDraft>) => void;
  t: Translate;
}) {
  const { t } = props;
  const [text, setText] = useState("");
  const set = (index: number, patch: Partial<BuilderDraft["safety"][number]>) =>
    props.onPatch({ safety: patchRow(props.draft.safety, index, patch) });
  const check = t("work.builder.safety.col.text", { defaultValue: "Check" });
  return (
    <>
      <StepHead
        title={t("work.builder.safety.title", { defaultValue: "What has to be checked first?" })}
        sentence={t("work.builder.safety.sentence", {
          defaultValue: "Every line here has to be ticked on the phone before the task list opens.",
        })}
      />
      <EditableTable
        data-collection="safety"
        caption={t("work.builder.safety.caption", {
          defaultValue: "Safety — {{count}}",
          count: props.draft.safety.length,
        })}
        rows={props.draft.safety}
        rowKey={(_row, index) => `safety-${index}`}
        onChange={(safety) => props.onPatch({ safety })}
        emptyText={t("work.builder.safety.empty", {
          defaultValue: "No safety checks yet. Add the first one below.",
        })}
        labels={rowLabels(t)}
        columns={[
          {
            key: "text",
            label: check,
            cell: (row, index) => (
              <CellInput label={cellName(t, check, index)} value={row.text} onChange={(value) => set(index, { text: value })} />
            ),
          },
          {
            key: "mandatory",
            label: t("work.builder.safety.col.mustDo", { defaultValue: "Must do" }),
            cell: (row, index) => (
              <CheckboxField
                id={`wtb_safety_mandatory_${index}`}
                label={t("work.builder.safety.col.mustDo", { defaultValue: "Must do" })}
                checked={row.isMandatory}
                onChange={(isMandatory) => set(index, { isMandatory })}
              />
            ),
          },
        ]}
        addRow={
          <>
            <CellInput
              id="wtb_safety_new"
              label={t("work.builder.safety.add", { defaultValue: "Add a safety check…" })}
              value={text}
              onChange={setText}
              className="w-full max-w-xl"
            />
            <AddButton
              collection="safety"
              t={t}
              disabled={text.trim() === ""}
              onAdd={() => {
                props.onPatch({ safety: [...props.draft.safety, { text: text.trim(), isMandatory: true }] });
                setText("");
              }}
            />
          </>
        }
      />
    </>
  );
}

function TasksStep(props: {
  draft: BuilderDraft;
  onPatch: (next: Partial<BuilderDraft>) => void;
  t: Translate;
}) {
  const { t } = props;
  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState("");
  const total = taskMinutes(props.draft.tasks);
  const set = (index: number, patch: Partial<BuilderDraft["tasks"][number]>) =>
    props.onPatch({ tasks: patchRow(props.draft.tasks, index, patch) });
  const task = t("work.builder.tasks.col.task", { defaultValue: "Task" });
  const mins = t("work.builder.tasks.col.minutes", { defaultValue: "Minutes" });
  const instruction = t("work.builder.tasks.instruction", { defaultValue: "Instruction" });
  const moneyMinutes = t("work.builder.tasks.moneyMinutes", { defaultValue: "Fresh minutes" });
  const feeCode = t("work.builder.tasks.moneyFeeCode", { defaultValue: "Fee charge code" });
  return (
    <>
      <StepHead
        title={t("work.builder.tasks.title", { defaultValue: "What are the steps?" })}
        sentence={t("work.builder.tasks.sentence", {
          defaultValue: "In the order a technician does them. Each one appears as a tick box on the phone.",
        })}
      />
      <EditableTable
        data-collection="tasks"
        caption={t("work.builder.tasks.caption", {
          defaultValue: "Tasks — {{count}} steps · {{minutes}} min total",
          count: props.draft.tasks.length,
          minutes: total,
        })}
        rows={props.draft.tasks}
        rowKey={(_row, index) => `task-${index}`}
        onChange={(tasks) => props.onPatch({ tasks })}
        emptyText={t("work.builder.tasks.empty", {
          defaultValue: "No steps yet. Add the first one below.",
        })}
        labels={rowLabels(t)}
        columns={[
          {
            key: "title",
            label: task,
            // PO answer 3 — the instruction is a SECOND LINE under its task
            // (CR-168 §5.7 S3, round 1's field-map judgment): the same place
            // the job's checklist and the summary draw it, so a clerk writes it
            // where it will be read.
            cell: (row, index) => (
              <span className="flex flex-col gap-1">
                <CellInput label={cellName(t, task, index)} value={row.title} onChange={(value) => set(index, { title: value })} />
                <CellInput
                  label={cellName(t, instruction, index)}
                  placeholder={t("work.builder.tasks.instructionPlaceholder", { defaultValue: "Add an instruction…" })}
                  value={row.instruction}
                  onChange={(value) => set(index, { instruction: value })}
                  className="text-sm"
                />
                {/* FB-013 (`DEF-WRK-10641`) — the check's two answers, a third
                    line under its task, only while *Check payment* is ticked. */}
                {row.moneyCheck ? (
                  // DEF-WRK-10645 — each box carries its word VISIBLY; a
                  // placeholder vanishes once filled and left "5" and
                  // "CC-RECON" saying nothing about which box was which.
                  <span className="flex flex-wrap items-center gap-3" data-money-check={index}>
                    <span className="flex items-center gap-2 text-sm text-neutral-600">
                      {moneyMinutes}
                      <CellInput
                        label={cellName(t, moneyMinutes, index)}
                        placeholder={moneyMinutes}
                        value={row.moneyMinutes}
                        onChange={(value) => set(index, { moneyMinutes: value })}
                        numeric
                        className="w-28 text-sm"
                      />
                    </span>
                    <span className="flex items-center gap-2 text-sm text-neutral-600">
                      {feeCode}
                      <CellInput
                        label={cellName(t, feeCode, index)}
                        placeholder={feeCode}
                        value={row.moneyChargeCode}
                        onChange={(value) => set(index, { moneyChargeCode: value })}
                        className="w-40 text-sm"
                      />
                    </span>
                  </span>
                ) : null}
              </span>
            ),
          },
          {
            key: "minutes",
            numeric: true,
            label: mins,
            cell: (row, index) => (
              <CellInput
                label={cellName(t, mins, index)}
                value={row.estMinutes}
                onChange={(value) => set(index, { estMinutes: value })}
                numeric
                className="w-20"
              />
            ),
          },
          {
            key: "photo",
            label: t("work.builder.tasks.col.photo", { defaultValue: "Photo" }),
            cell: (row, index) => (
              <CheckboxField
                id={`wtb_task_photo_${index}`}
                label={t("work.builder.tasks.col.photoRequired", { defaultValue: "Photo required" })}
                checked={row.photoRequired}
                onChange={(photoRequired) => set(index, { photoRequired })}
              />
            ),
          },
          {
            key: "mandatory",
            label: t("work.builder.tasks.col.mustDo", { defaultValue: "Must do" }),
            cell: (row, index) => (
              <CheckboxField
                id={`wtb_task_mandatory_${index}`}
                label={t("work.builder.tasks.col.mustDo", { defaultValue: "Must do" })}
                checked={row.isMandatory}
                onChange={(isMandatory) => set(index, { isMandatory })}
              />
            ),
          },
          {
            // FB-013 — *Check payment before this step* (R18: data on the step).
            key: "payment",
            label: t("work.builder.tasks.col.payment", { defaultValue: "Payment" }),
            cell: (row, index) => (
              <CheckboxField
                id={`wtb_task_money_${index}`}
                label={t("work.builder.tasks.col.checkPayment", { defaultValue: "Check payment" })}
                checked={row.moneyCheck}
                onChange={(moneyCheck) => set(index, { moneyCheck })}
              />
            ),
          },
        ]}
        addRow={
          <>
            <CellInput
              id="wtb_task_new"
              label={t("work.builder.tasks.add", { defaultValue: "Add a task…" })}
              value={title}
              onChange={setTitle}
              className="w-full max-w-md"
            />
            <CellInput
              id="wtb_task_minutes"
              label={t("work.builder.tasks.addMinutes", { defaultValue: "Minutes" })}
              value={minutes}
              onChange={setMinutes}
              numeric
              className="w-28"
            />
            <AddButton
              collection="tasks"
              t={t}
              disabled={title.trim() === ""}
              onAdd={() => {
                props.onPatch({
                  tasks: [
                    ...props.draft.tasks,
                    {
                      title: title.trim(),
                      estMinutes: minutes.trim(),
                      photoRequired: false,
                      isMandatory: true,
                      instruction: "",
                      moneyCheck: false,
                      moneyMinutes: MONEY_CHECK_DEFAULT_MINUTES,
                      moneyChargeCode: "",
                    },
                  ],
                });
                setTitle("");
                setMinutes("");
              }}
            />
          </>
        }
      />
      {/* FB-028 (PO 2026-10-31) — the Reconnect limit lives on the template,
          shown only while a step checks payment; a raised reconnect's step is
          enabled on the phone at or below it. Not a Work setting. */}
      {props.draft.tasks.some((row) => row.moneyCheck) ? (
        <div className="mt-3 max-w-xs" data-reconnect-limit="">
          <TextField
            id="wtb_reconnect_limit"
            label={t("work.builder.tasks.reconnectLimit", { defaultValue: "Reconnect limit" })}
            value={props.draft.reconnectLimit}
            onChange={(reconnectLimit) => props.onPatch({ reconnectLimit })}
            numeric
          />
        </div>
      ) : null}
      <div className="mt-3">
        <ConsequenceBox
          tone="check"
          data-consequence="tasks"
          title={t("work.builder.tasks.consequenceTitle", {
            defaultValue: "{{minutes}} minutes total is what the dispatcher schedules against.",
            minutes: total,
          })}
          body={t("work.builder.tasks.consequenceBody", {
            defaultValue: "Estimates that are wrong here make every day's route wrong.",
          })}
        />
      </div>
    </>
  );
}

function MaterialsStep(props: {
  draft: BuilderDraft;
  onPatch: (next: Partial<BuilderDraft>) => void;
  parts: { id: string; part_no: string; name: string; unit_of_measure: string }[];
  t: Translate;
}) {
  const { t } = props;
  const [partId, setPartId] = useState("");
  const [qty, setQty] = useState("1");
  const set = (index: number, patch: Partial<BuilderDraft["materials"][number]>) =>
    props.onPatch({ materials: patchRow(props.draft.materials, index, patch) });
  const partLabel = t("work.builder.materials.col.part", { defaultValue: "Part" });
  const qtyLabel = t("work.builder.materials.col.qty", { defaultValue: "Quantity" });
  const partOptions = props.parts.map((part) => ({ value: part.id, label: `${part.part_no} · ${part.name}` }));
  return (
    <>
      <StepHead
        title={t("work.builder.materials.title", { defaultValue: "What does the job use?" })}
        sentence={t("work.builder.materials.sentence", {
          defaultValue: "Planned quantities the technician records against. They come from your parts register.",
        })}
      />
      <EditableTable
        data-collection="materials"
        caption={t("work.builder.materials.caption", {
          defaultValue: "Materials — {{count}}",
          count: props.draft.materials.length,
        })}
        rows={props.draft.materials}
        rowKey={(_row, index) => `material-${index}`}
        onChange={(materials) => props.onPatch({ materials })}
        emptyText={t("work.builder.materials.empty", {
          defaultValue: "No parts planned. Some jobs use none.",
        })}
        labels={rowLabels(t)}
        columns={[
          {
            key: "part",
            label: partLabel,
            // The add row's own list. A part the register no longer offers
            // (retired since the template was written) stays as itself rather
            // than silently becoming the first option.
            cell: (row, index) => (
              <CellSelect
                label={cellName(t, partLabel, index)}
                value={row.partId}
                options={
                  partOptions.some((one) => one.value === row.partId)
                    ? partOptions
                    : [{ value: row.partId, label: `${row.partNo} · ${row.name}` }, ...partOptions]
                }
                onChange={(value) => {
                  const part = props.parts.find((one) => one.id === value);
                  if (part === undefined) return;
                  set(index, {
                    partId: part.id,
                    partNo: part.part_no,
                    name: part.name,
                    unitOfMeasure: part.unit_of_measure,
                  });
                }}
              />
            ),
          },
          {
            key: "qty",
            numeric: true,
            label: qtyLabel,
            cell: (row, index) => (
              <CellInput
                label={cellName(t, qtyLabel, index)}
                value={row.plannedQty}
                onChange={(value) => set(index, { plannedQty: value })}
                numeric
                className="w-24"
              />
            ),
          },
          {
            /* CLAUDE.md hard rule 3 — the unit travels WITH the quantity, in
               its own column, taken from the part and NEVER typed (P3.13's one
               read-only cell). */
            key: "unit",
            label: t("work.builder.materials.col.unit", { defaultValue: "Unit" }),
            cell: (row) => <span>{row.unitOfMeasure}</span>,
          },
        ]}
        addRow={
          <>
            <CellSelect
              id="wtb_material_part"
              label={t("work.builder.materials.add", { defaultValue: "Add a part…" })}
              placeholder={t("work.builder.materials.add", { defaultValue: "Add a part…" })}
              value={partId}
              onChange={setPartId}
              options={partOptions}
              className="w-full max-w-sm"
            />
            <CellInput id="wtb_material_qty" label={qtyLabel} value={qty} onChange={setQty} numeric className="w-28" />
            <AddButton
              collection="materials"
              t={t}
              disabled={partId === ""}
              onAdd={() => {
                const part = props.parts.find((one) => one.id === partId);
                if (part === undefined) return;
                props.onPatch({
                  materials: [
                    ...props.draft.materials,
                    {
                      partId: part.id,
                      partNo: part.part_no,
                      name: part.name,
                      plannedQty: qty.trim() === "" ? "1" : qty.trim(),
                      unitOfMeasure: part.unit_of_measure,
                    },
                  ],
                });
                setPartId("");
                setQty("1");
              }}
            />
          </>
        }
      />
    </>
  );
}

function ReadingsStep(props: {
  draft: BuilderDraft;
  onPatch: (next: Partial<BuilderDraft>) => void;
  t: Translate;
}) {
  const { t } = props;
  const [prompt, setPrompt] = useState("");
  const [unit, setUnit] = useState("");
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const set = (index: number, patch: Partial<BuilderDraft["readings"][number]>) =>
    props.onPatch({ readings: patchRow(props.draft.readings, index, patch) });
  const promptLabel = t("work.builder.readings.col.prompt", { defaultValue: "Prompt" });
  const unitLabel = t("work.builder.readings.col.unit", { defaultValue: "Unit" });
  const minLabel = t("work.builder.readings.col.min", { defaultValue: "Min" });
  const maxLabel = t("work.builder.readings.col.max", { defaultValue: "Max" });
  return (
    <>
      <StepHead
        title={t("work.builder.readings.title", { defaultValue: "What has to be measured?" })}
        sentence={t("work.builder.readings.sentence", {
          defaultValue:
            "Each reading has an accepted range. An out-of-range entry flags on the phone and on the completed order — it is never refused.",
        })}
      />
      <EditableTable
        data-collection="readings"
        caption={t("work.builder.readings.caption", {
          defaultValue: "Readings — {{count}}",
          count: props.draft.readings.length,
        })}
        rows={props.draft.readings}
        rowKey={(_row, index) => `reading-${index}`}
        onChange={(readings) => props.onPatch({ readings })}
        emptyText={t("work.builder.readings.empty", {
          defaultValue: "Nothing is measured on this job.",
        })}
        labels={rowLabels(t)}
        // ⚠ A blank unit is refused by the server by name (`US-WRK-014` TC-3;
        // hard rule 3), so emptying one in place says so on the cell rather
        // than at Publish, two steps later.
        cellError={(row, _index, key) =>
          key === "unit" && row.unitOfMeasure.trim() === ""
            ? t("work.builder.readings.unitNeeded", { defaultValue: "Needs a unit." })
            : undefined
        }
        columns={[
          {
            key: "prompt",
            label: promptLabel,
            cell: (row, index) => (
              <CellInput label={cellName(t, promptLabel, index)} value={row.prompt} onChange={(value) => set(index, { prompt: value })} />
            ),
          },
          {
            /* ⚠ THE UNIT IS ITS OWN COLUMN AND NEVER A WORD IN THE PROMPT —
               CLAUDE.md hard rule 3 and `BR-WRK-015`. */
            key: "unit",
            label: unitLabel,
            cell: (row, index) => (
              <CellInput
                label={cellName(t, unitLabel, index)}
                value={row.unitOfMeasure}
                onChange={(value) => set(index, { unitOfMeasure: value })}
                className="w-20"
              />
            ),
          },
          {
            key: "min",
            numeric: true,
            label: minLabel,
            cell: (row, index) => (
              <CellInput label={cellName(t, minLabel, index)} value={row.min} onChange={(value) => set(index, { min: value })} numeric className="w-24" />
            ),
          },
          {
            key: "max",
            numeric: true,
            label: maxLabel,
            cell: (row, index) => (
              <CellInput label={cellName(t, maxLabel, index)} value={row.max} onChange={(value) => set(index, { max: value })} numeric className="w-24" />
            ),
          },
          {
            key: "photo",
            label: t("work.builder.readings.col.photo", { defaultValue: "Photo" }),
            cell: (row, index) => (
              <CheckboxField
                id={`wtb_reading_photo_${index}`}
                label={t("work.builder.readings.col.photoRequired", { defaultValue: "Photo required" })}
                checked={row.photoRequired}
                onChange={(photoRequired) => set(index, { photoRequired })}
              />
            ),
          },
          {
            key: "posts",
            label: t("work.builder.readings.col.posts", { defaultValue: "Becomes a meter read" }),
            cell: (row, index) => (
              <span className="flex items-center gap-2">
                <CheckboxField
                  id={`wtb_reading_posts_${index}`}
                  label={t("work.builder.readings.col.postsLabel", { defaultValue: "Becomes a meter read" })}
                  checked={row.postsAsMeterRead}
                  onChange={(postsAsMeterRead) => set(index, { postsAsMeterRead })}
                />
                <StatusPill tone={row.postsAsMeterRead ? "success" : "muted"}>
                  {row.postsAsMeterRead
                    ? t("work.builder.readings.posts.yes", { defaultValue: "Yes — posts on approval" })
                    : t("work.builder.readings.posts.no", { defaultValue: "No — recorded only" })}
                </StatusPill>
              </span>
            ),
          },
        ]}
        addRow={
          <>
            <CellInput id="wtb_reading_prompt" label={t("work.builder.readings.add", { defaultValue: "Prompt…" })} value={prompt} onChange={setPrompt} className="w-full max-w-xs" />
            <CellInput id="wtb_reading_unit" label={unitLabel} value={unit} onChange={setUnit} className="w-28" />
            <CellInput id="wtb_reading_min" label={minLabel} value={min} onChange={setMin} numeric className="w-24" />
            <CellInput id="wtb_reading_max" label={maxLabel} value={max} onChange={setMax} numeric className="w-24" />
            <AddButton
              collection="readings"
              t={t}
              /* ⚠ BOTH, NOT JUST THE PROMPT — a reading with no unit is refused
                 by the server (`US-WRK-014` TC-3); the sentence is below. */
              disabled={prompt.trim() === "" || unit.trim() === ""}
              onAdd={() => {
                props.onPatch({
                  readings: [
                    ...props.draft.readings,
                    {
                      prompt: prompt.trim(),
                      unitOfMeasure: unit.trim(),
                      min: min.trim(),
                      max: max.trim(),
                      required: true,
                      photoRequired: false,
                      postsAsMeterRead: false,
                    },
                  ],
                });
                setPrompt("");
                setUnit("");
                setMin("");
                setMax("");
              }}
            />
          </>
        }
      />
      <Note className="mt-2 max-w-measure" data-readings-unit-rule="">
        {t("work.builder.readings.unitRule", {
          defaultValue: "A reading needs a unit — it is a column, not part of the prompt.",
        })}
      </Note>
      <div className="mt-3">
        <ConsequenceBox
          tone="check"
          data-consequence="readings"
          title={t("work.builder.readings.consequenceTitle", {
            defaultValue: "Becomes a meter read turns a note into billing data.",
          })}
          body={t("work.builder.readings.consequenceBody", {
            defaultValue:
              "When it is on, what the technician captures posts to the meter's read history once a supervisor accepts the job — dated to when the work was finished, not when it was approved.",
          })}
        />
      </div>
    </>
  );
}

/** What a help document may be (SRV-3: PDF, PNG or JPG, at most 10 MB). */
const HELP_FILE_TYPES = "application/pdf,image/png,image/jpeg";

/** *Choose a file* / *Replace* — the kit's button over a hidden file input, so
 *  the control a person presses looks like every other button (B14 rule 36). */
function FilePick(props: { label: string; name: string; working: boolean; onFile: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={input}
        type="file"
        className="hidden"
        accept={HELP_FILE_TYPES}
        aria-label={props.name}
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file !== undefined) props.onFile(file);
        }}
      />
      <Button variant="secondary" size="sm" disabled={props.working} onClick={() => input.current?.click()} data-help-file-pick="">
        {props.label}
      </Button>
    </>
  );
}

/** The kinds a row's own picker offers: the three a clerk can add, plus the
 *  row's own kind when it is the retired `note`, so a stored note still reads
 *  as itself rather than as whichever option happens to come first. */
function helpKindOptions(current: string, t: Translate): { value: string; label: string }[] {
  const kinds: string[] = [...HELP_KINDS_OFFERED];
  if (current !== "" && !kinds.includes(current)) kinds.push(current);
  return kinds.map((kind) => ({ value: kind, label: helpKindWord(kind, t) }));
}

function HelpStep(props: {
  draft: BuilderDraft;
  onPatch: (next: Partial<BuilderDraft>) => void;
  /** P3.14 — store a document and answer what the help row keeps. Saves the
   *  draft first when it has no row yet, because the upload is template-scoped. */
  onUpload: (file: File) => Promise<HelpDocumentStored>;
  t: Translate;
}) {
  const { t } = props;
  const [uploading, setUploading] = useState<number | "new" | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  async function upload(file: File, into: number | "new"): Promise<void> {
    setUploading(into);
    setUploadError(null);
    try {
      const stored = await props.onUpload(file);
      const held = { ref: stored.ref, fileName: stored.name, fileBytes: stored.bytes };
      if (into === "new") {
        props.onPatch({
          help: [
            ...props.draft.help,
            { kind: "document", label: label.trim() === "" ? stored.name : label.trim(), ...held },
          ],
        });
        setLabel("");
        setRef("");
      } else {
        props.onPatch({ help: patchRow(props.draft.help, into, held) });
      }
    } catch (error) {
      setUploadError(apiErrorText(error, t));
    } finally {
      setUploading(null);
    }
  }
  const chooseFile = t("work.builder.help.chooseFile", { defaultValue: "Choose a file" });
  const replace = t("work.builder.help.replace", { defaultValue: "Replace" });
  const [kind, setKind] = useState<string>("document");
  const [label, setLabel] = useState("");
  const [ref, setRef] = useState("");
  const set = (index: number, patch: Partial<BuilderDraft["help"][number]>) =>
    props.onPatch({ help: patchRow(props.draft.help, index, patch) });
  const kindLabel = t("work.builder.help.col.kind", { defaultValue: "Kind" });
  const whatLabel = t("work.builder.help.col.label", { defaultValue: "What it is" });
  const whereLabel = t("work.builder.help.col.ref", { defaultValue: "Where to find it" });
  return (
    <>
      <StepHead
        title={t("work.builder.help.title", { defaultValue: "What can the technician reach for?" })}
        // ⚠ P3.25 — IN THE SAME COMMIT AS THE LINK KIND. The old sentence
        // promised *"available with no signal"*, which a video cannot keep.
        sentence={t("work.builder.help.sentenceLinks", {
          defaultValue: "Carried on the phone. Documents work with no signal; links need one.",
        })}
      />
      <EditableTable
        data-collection="help"
        caption={t("work.builder.help.caption", {
          defaultValue: "Help & support — {{count}}",
          count: props.draft.help.length,
        })}
        rows={props.draft.help}
        rowKey={(_row, index) => `help-${index}`}
        onChange={(help) => props.onPatch({ help })}
        emptyText={t("work.builder.help.empty", { defaultValue: "Nothing attached yet." })}
        labels={rowLabels(t)}
        cellError={(row, _index, key) => {
          if (key !== "ref") return undefined;
          if (row.kind === "link" && !isHttpsAddress(row.ref)) {
            return t("work.builder.help.httpsNeeded", { defaultValue: "Use an https address." });
          }
          // FB-031 — the starter pack's empty rows, marked before Publish refuses them.
          const missing = helpRowMissing(row);
          if (missing === "noFile") return t("work.builder.help.noFile", { defaultValue: "No file" });
          if (missing === "noNumber") return t("work.builder.help.noNumber", { defaultValue: "No number" });
          return undefined;
        }}
        columns={[
          {
            key: "kind",
            label: kindLabel,
            cell: (row, index) => (
              <CellSelect
                label={cellName(t, kindLabel, index)}
                value={row.kind}
                options={helpKindOptions(row.kind, t)}
                onChange={(value) => set(index, { kind: value })}
                className="w-36"
              />
            ),
          },
          {
            key: "label",
            label: whatLabel,
            cell: (row, index) => (
              <CellInput label={cellName(t, whatLabel, index)} value={row.label} onChange={(value) => set(index, { label: value })} />
            ),
          },
          {
            key: "ref",
            label: whereLabel,
            cell: (row, index) =>
              row.kind === "document" && row.fileName !== "" ? (
                // A held file: its name and size, and *Replace* (image 53).
                <span className="flex items-center gap-2">
                  <HelpWhere row={row} t={t} />
                  <FilePick
                    label={replace}
                    name={cellName(t, replace, index)}
                    working={uploading !== null}
                    onFile={(file) => void upload(file, index)}
                  />
                </span>
              ) : (
                <span className="flex flex-col items-start gap-1">
                  <span className="flex w-full items-center gap-2">
                    <CellInput label={cellName(t, whereLabel, index)} value={row.ref} onChange={(value) => set(index, { ref: value })} />
                    {row.kind === "document" ? (
                      <FilePick
                        label={chooseFile}
                        name={cellName(t, chooseFile, index)}
                        working={uploading !== null}
                        onFile={(file) => void upload(file, index)}
                      />
                    ) : null}
                  </span>
                  {row.kind === "link" && isVideoAddress(row.ref) ? <VideoBadge /> : null}
                </span>
              ),
          },
        ]}
        addRow={
          <>
            <CellSelect
              id="wtb_help_kind"
              label={kindLabel}
              value={kind}
              onChange={setKind}
              options={helpKindOptions("", t)}
              className="w-36"
            />
            <CellInput id="wtb_help_label" label={whatLabel} value={label} onChange={setLabel} className="w-full max-w-xs" />
            <CellInput
              id="wtb_help_ref"
              label={whereLabel}
              placeholder={
                kind === "link"
                  ? t("work.builder.help.linkPlaceholder", { defaultValue: "Paste an https address" })
                  : kind === "phone"
                    ? t("work.builder.help.phonePlaceholder", { defaultValue: "Phone number" })
                    : whereLabel
              }
              value={ref}
              onChange={setRef}
              className="w-full max-w-xs"
            />
            {kind === "document" ? (
              <FilePick label={chooseFile} name={chooseFile} working={uploading !== null} onFile={(file) => void upload(file, "new")} />
            ) : null}
            <AddButton
              collection="help"
              t={t}
              disabled={!helpRowAddable(kind, label, ref)}
              onAdd={() => {
                props.onPatch({
                  help: [
                    ...props.draft.help,
                    { kind, label: label.trim(), ref: ref.trim(), fileName: "", fileBytes: null },
                  ],
                });
                setLabel("");
                setRef("");
              }}
            />
          </>
        }
      />
      {uploadError !== null && (
        <Note className="mt-2 max-w-measure text-danger-700" data-help-upload-error="">
          {uploadError}
        </Note>
      )}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 7 · SIGNATURE — what the technician has to bring back (image 54: Keep)
// ══════════════════════════════════════════════════════════════════════════

function SignatureStep(props: {
  draft: BuilderDraft;
  onPatch: (next: Partial<BuilderDraft>) => void;
  t: Translate;
}) {
  const { t } = props;
  return (
    <>
      <StepHead
        title={t("work.builder.signature.title", { defaultValue: "How does the job close?" })}
        sentence={t("work.builder.signature.sentence", {
          defaultValue: "What the technician has to bring back before the job counts as done.",
        })}
      />
      <Panel as="section" title={t("work.builder.signature.panel", { defaultValue: "Closing the job" })}>
        <div className="flex flex-col gap-2" data-signature="">
          <CheckboxField
            id="wtb_sig_required"
            label={t("work.builder.signature.required", { defaultValue: "The customer signs on the phone" })}
            checked={props.draft.signatureRequired}
            onChange={(signatureRequired) => props.onPatch({ signatureRequired })}
          />
          <CheckboxField
            id="wtb_sig_reason"
            label={t("work.builder.signature.reason", { defaultValue: "If they refuse, the technician records why" })}
            checked={props.draft.refusalReasonRequired}
            onChange={(refusalReasonRequired) => props.onPatch({ refusalReasonRequired })}
          />
          <CheckboxField
            id="wtb_sig_hanger"
            label={t("work.builder.signature.hanger", { defaultValue: "If nobody is in, leave a card and photograph it" })}
            checked={props.draft.doorHangerOnNoAnswer}
            onChange={(doorHangerOnNoAnswer) => props.onPatch({ doorHangerOnNoAnswer })}
          />
        </div>
      </Panel>
      <div className="mt-3">
        <ConsequenceBox
          tone="check"
          data-consequence="signature"
          title={t("work.builder.signature.consequenceTitle", { defaultValue: "A signature is evidence the visit happened." })}
          body={t("work.builder.signature.consequenceBody", {
            defaultValue:
              "Turn it off only where nobody is expected to be there — a meter pit in the street, a main in a field.",
          })}
        />
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 8 · REVIEW — the template summary (P3.26), the change note, the one write
// ══════════════════════════════════════════════════════════════════════════

function ReviewStep(props: {
  draft: BuilderDraft;
  names: TemplateSummaryNames;
  /** The version standing today; 0 is a draft never published. */
  version: number;
  ordersRaised: number;
  changeNote: string;
  onChangeNote: (value: string) => void;
  onJumpTo: (step: number) => void;
  t: Translate;
}) {
  const { t } = props;
  return (
    <>
      <StepHead
        title={t("work.builder.review.title", { defaultValue: "Review" })}
        sentence={t("work.builder.review.sentence", {
          defaultValue: "This is what a technician will see when a job is raised from this template.",
        })}
      />
      {/* Rulings 7 and 9 — every row, one panel per section, and ✎ Edit goes
          back to the step that owns it. The SAME component the template's
          Overview draws (B14 rule 43). */}
      <TemplateSummary draft={props.draft} names={props.names} edit={{ kind: "jump", onJump: props.onJumpTo }} />
      {/* P3.15 (`DEF-WRK-9568`) — a NEW version is asked what changed, and the
          answer is what the Versions tab's WHAT CHANGED column reads. A first
          publish is not asked: nothing came before it to have changed. */}
      {props.version >= 1 && (
        <div className="mt-4 max-w-xl">
          <TextField
            id="wtb_change_note"
            label={t("work.builder.review.changeNote", { defaultValue: "What changed" })}
            value={props.changeNote}
            onChange={props.onChangeNote}
          />
        </div>
      )}
      <div className="mt-3">
        {/* B14 rule 11 and `BR-WRK-008` — *copy, never link*, said BEFORE the
            button. The count is the server's. */}
        <ConsequenceBox
          tone="publish"
          data-consequence="publish"
          title={t("work.builder.review.consequenceTitle", { defaultValue: "Publishing affects new work orders only." })}
          body={
            props.ordersRaised > 0
              ? t("work.builder.review.consequenceRaised", {
                  defaultValue: "The {{count}} orders already raised keep exactly what they were given — nothing in the field changes.",
                  count: props.ordersRaised,
                })
              : t("work.builder.review.consequenceNone", {
                  defaultValue: "No orders have been raised from this template yet.",
                })
          }
        />
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE COMPONENT
// ══════════════════════════════════════════════════════════════════════════

export interface TemplateBuilderProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function TemplateBuilder(props: TemplateBuilderProps) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const routeParams = useParams();

  /** `undefined` on `…/new`, a uuid on `…/{id}/edit`. */
  const editingId = routeParams.templateId ?? null;

  const step = clampStep(searchParams.get(STEP_PARAM));
  const nav: WizardNavState = { step, reached: step };
  function setStep(next: WizardNavState): void {
    const query = new URLSearchParams(searchParams);
    query.set(STEP_PARAM, String(next.step));
    setSearchParams(query, { replace: true });
  }

  const [draft, setDraft] = useState<BuilderDraft>(emptyBuilderDraft);
  /** The row this builder is writing into. Null until *Save draft* or
   *  *Publish* creates one — which is `BR-WRK-011` in a variable: seven steps
   *  of editing and no row at all. */
  const [templateId, setTemplateId] = useState<string | null>(editingId);
  const [savedNote, setSavedNote] = useState<string | null>(null);
  /** P3.15 — what a new version changed, sent with Publish. */
  const [changeNote, setChangeNote] = useState("");
  function patch(next: Partial<BuilderDraft>): void {
    setDraft((current) => ({ ...current, ...next }));
    setSavedNote(null);
  }

  const packsQuery = useQuery({
    queryKey: ["work-template-packs"],
    queryFn: () => getTemplatePacks(client),
  });
  const servicesQuery = useQuery({
    queryKey: ["work-builder-services"],
    queryFn: () => getTenantServices(client),
  });
  // The raise's own source for job types (`GET /work/raise-options`): the
  // utility's ACTIVE types WITH their heading, which is what the two-level
  // picker needs and what the flat lookup list could not say.
  const typesQuery = useQuery({
    queryKey: ["work-builder-raise-options"],
    queryFn: () => getRaiseOptions(client),
  });
  const skillsQuery = useQuery({
    queryKey: ["work-builder-skills"],
    queryFn: () => getLookupEntries("work_skills", { per: 200 }, client),
  });
  const kitsQuery = useQuery({
    queryKey: ["work-builder-kits"],
    queryFn: () => getLookupEntries("work_safety_kits", { per: 200 }, client),
  });
  const assetTypesQuery = useQuery({
    queryKey: ["work-builder-asset-types"],
    queryFn: () => getLookupEntries("asset_types", { per: 200 }, client),
  });
  const partsQuery = useQuery({
    queryKey: ["work-builder-parts"],
    queryFn: () => listParts({ per: 200 }, client),
  });
  const existingQuery = useQuery({
    queryKey: ["work-template-edit", editingId],
    queryFn: () => getTemplate(editingId ?? "", client),
    enabled: editingId !== null,
  });

  // ⚠ **HYDRATE ONCE, AND ONLY FROM THE FIRST ANSWER.** A refetch after an edit
  // would overwrite what a person has typed since — the same trap a controlled
  // form falls into whenever a query key changes underneath it.
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    if (existingQuery.data !== undefined && !hydrated) {
      setDraft(draftFromTemplate(existingQuery.data));
      setHydrated(true);
    }
  }, [existingQuery.data, hydrated]);

  const services = useMemo(
    () =>
      (servicesQuery.data ?? [])
        .filter((row) => row.enabled !== false)
        .map((row) => ({
          value: row.service,
          label: t(`rating.service.${row.service}`, { defaultValue: row.name }),
        })),
    [servicesQuery.data, t],
  );
  const options = (rows: { id: string; name: string }[] | undefined) =>
    (rows ?? []).map((row) => ({ value: row.id, label: row.name }));
  const jobTypes = useMemo(() => jobTypeChoices(typesQuery.data?.types ?? []), [typesQuery.data]);

  /** The summary prints NAMES; the draft holds codes and ids (B14 rule 31).
   *  Each name falls back to what the template itself was read with, so a
   *  type or kit retired since it was chosen still reads as itself. */
  const summaryNames: TemplateSummaryNames = useMemo(() => {
    const found = (rows: { id: string; name: string }[] | undefined, id: string) =>
      id === "" ? null : (rows ?? []).find((row) => row.id === id)?.name ?? null;
    const existing = existingQuery.data;
    return {
      service: services.find((row) => row.value === draft.service)?.label ?? existing?.service?.name ?? null,
      jobType:
        draft.jobTypeId === ""
          ? null
          : (typesQuery.data?.types ?? []).find((row) => row.id === draft.jobTypeId)?.name ??
            (existing?.job_type?.id === draft.jobTypeId ? existing.job_type.name : null),
      skill: found(skillsQuery.data?.results, draft.skillId) ?? (existing?.skill?.id === draft.skillId ? existing.skill.name : null),
      safetyKit:
        found(kitsQuery.data?.results, draft.safetyKitId) ??
        (existing?.safety_kit?.id === draft.safetyKitId ? existing.safety_kit.name : null),
      assetTypes: draft.assetTypeIds
        .map((id) => found(assetTypesQuery.data?.results, id))
        .filter((name): name is string => name !== null),
    };
  }, [draft, services, typesQuery.data, skillsQuery.data, kitsQuery.data, assetTypesQuery.data, existingQuery.data]);

  /**
   * Persist the draft: the header, then the seven collections.
   *
   * ⚠ **NOTHING HERE REACHES A WORK ORDER** (`BR-WRK-011`). These are draft
   * rows; `publish` is the one write that makes a version an order can be
   * raised from. The header goes first because the collections hang off its id.
   */
  async function persist(): Promise<string> {
    const header = headerPayload(draft);
    const id =
      templateId === null
        ? (await createTemplateDraft(header, client)).id
        : (await updateTemplateHeader(templateId, header, client)).id;
    setTemplateId(id);
    const payloads = collectionPayloads(draft);
    for (const collection of [
      "details",
      "safety",
      "tasks",
      "materials",
      "readings",
      "help",
      "asset-types",
    ] as TemplateCollection[]) {
      await replaceTemplateCollection(id, collection, payloads[collection], client);
    }
    return id;
  }

  async function saveDraft(): Promise<void> {
    try {
      await persist();
      setSavedNote(
        t("work.builder.savedDraft", {
          defaultValue: "Saved as a draft. Nothing is raised from a draft.",
        }),
      );
    } catch (error) {
      setSavedNote(apiErrorText(error, translate));
    }
  }

  /**
   * The ONE write (`BR-WRK-011`), single-flighted by the frame (`BR-SHL-019`).
   *
   * ⚠ **IT SAVES AND THEN PUBLISHES, AND THAT IS TWO CALLS AND ONE WRITE THAT
   * MATTERS.** The bundle has to be in the database before there is anything
   * to version. The frame guarantees a second press does not start a second
   * run; the SERVER guarantees that a second publish with nothing changed
   * answers the version that already exists (`created: false`), which is the
   * half a screen cannot promise.
   */
  async function runCommit(): Promise<WizardCommitOutcome> {
    try {
      const id = await persist();
      const published = await publishTemplate(id, changeNote.trim() === "" ? null : changeNote.trim(), client);
      fireToast(
        published.created
          ? t("work.builder.publishedToast", {
              defaultValue: "{{name}} published as version {{version}}.",
              name: published.name,
              version: published.version,
            })
          : t("work.builder.alreadyPublishedToast", {
              defaultValue: "Nothing had changed — version {{version}} still stands.",
              version: published.version,
            }),
      );
      navigate(tenantPath(`${WORK_ORDER_TEMPLATES_ROUTE}/${id}`));
      return { ok: true };
    } catch (error) {
      // BR-SHL-020 — the server's own refusal, in its own words, with every
      // answer still on screen (A18 §4).
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  const stepContent: Record<number, React.ReactNode> = {
    1: (
      <DetailsStep
        draft={draft}
        onPatch={patch}
        packs={packsQuery.data ?? []}
        services={services}
        jobTypes={jobTypes}
        skills={options(skillsQuery.data?.results)}
        kits={options(kitsQuery.data?.results)}
        assetTypes={options(assetTypesQuery.data?.results)}
        t={translate}
      />
    ),
    2: <SafetyStep draft={draft} onPatch={patch} t={translate} />,
    3: <TasksStep draft={draft} onPatch={patch} t={translate} />,
    4: (
      <MaterialsStep
        draft={draft}
        onPatch={patch}
        parts={partsQuery.data?.results ?? []}
        t={translate}
      />
    ),
    5: <ReadingsStep draft={draft} onPatch={patch} t={translate} />,
    6: (
      <HelpStep
        draft={draft}
        onPatch={patch}
        onUpload={async (file) => uploadHelpDocument(templateId ?? (await persist()), file, client)}
        t={translate}
      />
    ),
    7: <SignatureStep draft={draft} onPatch={patch} t={translate} />,
    8: (
      <ReviewStep
        draft={draft}
        names={summaryNames}
        version={existingQuery.data?.version ?? 0}
        ordersRaised={existingQuery.data?.orders_raised ?? 0}
        changeNote={changeNote}
        onChangeNote={setChangeNote}
        onJumpTo={(target) => setStep({ step: target, reached: step })}
        t={translate}
      />
    ),
  };

  const steps: WizardStep[] = TEMPLATE_BUILDER_STEPS.map((spec, index) => ({
    id: spec.id,
    label: t(spec.labelKey, { defaultValue: spec.en }),
    content: stepContent[index + 1],
    // ⚠ ONLY STEP 1 REFUSES, AND IT REFUSES WITH A SENTENCE (DEF-936). Every
    // other step may legitimately be empty: `US-WRK-015` TC-5 publishes a
    // template with no tasks and no readings, because some jobs are a visit
    // and a signature.
    validate:
      index === 0
        ? () =>
            step1Complete(draft) ||
            t("work.builder.needsNameServiceScope", {
              defaultValue: "Name it, pick a service, say what it is done to.",
            })
        : () => true,
  }));

  return (
    <div data-template-builder="" data-screen={TEMPLATE_BUILDER_SCREEN}>
      <PageHeader
        kicker={t("work.builder.kicker", { defaultValue: "Work · Templates" })}
        title={
          editingId === null
            ? t("work.builder.titleNew", { defaultValue: "New template" })
            : t("work.builder.titleEdit", { defaultValue: "Edit template" })
        }
        backTo={{
          to: tenantPath(WORK_ORDER_TEMPLATES_ROUTE),
          label: t("work.templates.title", { defaultValue: "Work order templates" }),
        }}
      />
      {/* `BR-WRK-011` on the screen where it binds — every step's footer says
          it, exactly as `Work-014`'s `NoteBar` draws it. */}
      <Note className="mb-3 max-w-measure" data-draft-notice="">
        {t("work.builder.nothingWritten", {
          defaultValue:
            "Step {{step}} of {{of}} · nothing is saved to a work order until you publish. Editing a published template never changes work already in the field.",
          step,
          of: TEMPLATE_BUILDER_STEPS.length,
        })}
      </Note>
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setStep}
        commitLabel={t("work.builder.publish", { defaultValue: "Publish template" })}
        commitFailedTitle={t("work.builder.publishFailed", {
          defaultValue: "The template was not published.",
        })}
        onCommit={runCommit}
        onCommitted={() => undefined}
        secondaryActions={
          <Button variant="secondary" data-save-draft="" onClick={() => void saveDraft()}>
            {t("work.builder.saveDraft", { defaultValue: "Save draft" })}
          </Button>
        }
      />
      {savedNote !== null && (
        <Note className="mt-2 max-w-measure" data-saved-note="">
          {savedNote}
        </Note>
      )}
    </div>
  );
}

export default TemplateBuilder;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-016@2b08ba9f (EP-WRK-03) · 10-execution-plan.md wave E task E1 · 08-screen-layouts.md §13.1 · 09-component-inventory.md W3 · wireframes/Work-014.png … Work-017.png · J60 steps 6–9
// generated: 2026-09-05 by the CR-070 wave E build lane
// checklist: A✔ B✔ C✔ D✔ E✔(two routes in App.tsx; `+ New template` and `Edit template` point here) F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work · G31 (this file is on src/styles/route-b-migrated.txt) · G13 · G15 (every string is a catalogue key with a defaultValue) · G29 (WRK-05.1–8, r10's own per-step badge)
// exceptions: E3 the eleven locale catalogues are NOT edited by this lane (dispatch constraint); every string carries a `defaultValue` so the screen renders correct English until the keys land, and the key set is written out in `scratchpad/lane-WE-keys.json` · E3 `Delete` is NOT rendered on step 8 — the drawing draws it disabled with a note, and a DRAFT that has never been published has nothing to delete; deleting a PUBLISHED template is `Work-022`'s control and it already exists there (`BR-WRK-012`)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
