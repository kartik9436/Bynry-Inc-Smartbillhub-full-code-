// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane TEMPLATES — P3.26, images 44 (a
//           template's Overview) and 55 (the builder's Review)
// Rules:    rulings 7 (*"the details are not visible in the review"*), 8
//           (*"all details should be visible"*) and 9 (*"the ui is not easy to
//           understand"*) · B14 rule 43 (ONE component, the PlanSections
//           precedent) · rule 20 (the product's own table — `EditableTable`,
//           read-only) · rule 31 (no id is a visible value) · rule 33 · rule 37
//           (the drawing's figures are illustrations) · hard rule 3 (a
//           quantity and a reading carry their unit in their own column)
// Tests:    src/features/work/cr168Templates.dom.test.tsx
// Impacts:  TemplateBuilder.tsx (step 8) · TemplateDetailPage.tsx (Overview)
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE COMPONENT, TWO SCREENS, AND THAT IS THE WHOLE POINT OF P3.26.** The
// Review step was a seven-row COUNT table and the Overview a list of five
// counts — two answers to *what is in this template*, neither of them the rows.
// The PO said so twice on 24 Sep. Both screens now draw THIS, from the same
// `BuilderDraft` (`draftFromTemplate` turns the server's template into one), so
// what a clerk approves before Publish and what a supervisor reads afterwards
// cannot drift apart: there is nowhere for the second layout to live.
//
// ⚠ **THE OLD REVIEW'S NUMBERS ARE GONE ON PURPOSE.** `reviewSections()` counted
// Details as 4 and Signature as 3 so the panel would print the wireframe's 26 —
// a figure drawn as an illustration and built to as a fact (B14 rule 37). Each
// section here counts its own rows and nothing else.
//
// ⚠ **✎ EDIT GOES BACK TO THE STEP THAT OWNS THE SECTION; IT NEVER OPENS A
// SECOND EDITOR.** On Review it is a button that moves the wizard; on Overview
// it is a LINK to the builder at that step, so it opens in a new tab like any
// other address. The header panel has no ✎ — the drawing gives it none, and its
// four facts belong to step 1, whose own panel (Details) carries the pencil.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { EditableTable } from "@/components/EditableTable";
import type { EditableColumn } from "@/components/EditableTable";
import { Panel } from "@/components/Panel";
import { trimQuantity } from "@/components/UnitCell";
import { Dash, Fact, FactList } from "@/features/metering/meteringShared";

import type {
  BuilderDraft,
  HelpDraft,
  MaterialDraft,
  ReadingDraft,
  SafetyDraft,
  TaskDraft,
} from "./templateBuilderModel";
import { isVideoAddress, taskMinutes } from "./templateBuilderModel";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** The words for the ids a draft holds. A draft stores the service CODE and
 *  lookup ids; the summary prints NAMES (B14 rule 31), resolved by the screen
 *  that owns the lookups. */
export interface TemplateSummaryNames {
  service: string | null;
  jobType: string | null;
  skill: string | null;
  safetyKit: string | null;
  assetTypes: string[];
}

/** Where a section's ✎ Edit goes, by builder STEP NUMBER (1–7). */
export type TemplateSummaryEdit =
  | { kind: "jump"; onJump: (step: number) => void }
  | { kind: "link"; href: (step: number) => string };

export interface TemplateSummaryProps {
  draft: BuilderDraft;
  names: TemplateSummaryNames;
  /** Absent draws no pencils — a summary somebody may only read. */
  edit?: TemplateSummaryEdit;
}

/** The section ids, each with the builder step that owns it. */
export const SUMMARY_SECTIONS = [
  { id: "details", step: 1 },
  { id: "safety", step: 2 },
  { id: "tasks", step: 3 },
  { id: "materials", step: 4 },
  { id: "readings", step: 5 },
  { id: "help", step: 6 },
  { id: "signature", step: 7 },
] as const;

/** *Document* · *Phone* · *Link* — and *Note*, the kind before ruling 6. */
export function helpKindWord(kind: string, t: Translate): string {
  if (kind === "document") return t("work.builder.help.kind.document", { defaultValue: "Document" });
  if (kind === "phone") return t("work.builder.help.kind.phone", { defaultValue: "Phone" });
  if (kind === "link") return t("work.builder.help.kind.link", { defaultValue: "Link" });
  return t("work.builder.help.kind.note", { defaultValue: "Note" });
}

/** *Premises* · *Unit* · *Asset* — what the job is done to (P3.12). */
export function scopeWord(scope: string, t: Translate): string | null {
  if (scope === "per_premise") return t("work.template.scope.per_premise", { defaultValue: "Premises" });
  if (scope === "per_unit") return t("work.template.scope.per_unit", { defaultValue: "Unit" });
  if (scope === "per_asset") return t("work.template.scope.per_asset", { defaultValue: "Asset" });
  return null;
}

/** A file's size the way a person reads it — *412 KB*, *1.2 MB*. */
export function fileSizeWord(bytes: number | null, t: Translate): string | null {
  if (bytes === null || bytes < 0) return null;
  if (bytes < 1024 * 1024) {
    return t("work.builder.help.sizeKb", { count: Math.max(1, Math.round(bytes / 1024)), defaultValue: "{{count}} KB" });
  }
  return t("work.builder.help.sizeMb", { size: (bytes / (1024 * 1024)).toFixed(1), defaultValue: "{{size}} MB" });
}

/** *▶ Video · needs a signal* — the drawing's own badge (image 53). */
export function VideoBadge() {
  const { t } = useTranslation();
  return (
    <span className="mt-1 inline-block border border-accent px-1 text-sm font-semibold text-accent" data-video-badge="">
      {t("work.builder.help.videoBadge", { defaultValue: "▶ Video · needs a signal" })}
    </span>
  );
}

/** Where a help row is found — a held file's name and size, a phone number,
 *  an address (badged when it is a video), or the typed place. */
export function HelpWhere(props: { row: HelpDraft; t: Translate }) {
  const { row, t } = props;
  if (row.kind === "document" && row.fileName !== "") {
    const size = fileSizeWord(row.fileBytes, t);
    return (
      <span data-help-file="">
        <span className="font-semibold">{row.fileName}</span>
        {size === null ? null : <span className="text-neutral-700"> · {size}</span>}
      </span>
    );
  }
  if (row.ref === "") return <Dash />;
  if (row.kind === "link") {
    return (
      <span className="flex flex-col items-start">
        <span className="break-all">{row.ref}</span>
        {isVideoAddress(row.ref) ? <VideoBadge /> : null}
      </span>
    );
  }
  return <span>{row.ref}</span>;
}

function yes(value: boolean, t: Translate): ReactNode {
  return value ? t("work.template.summary.yes", { defaultValue: "Yes" }) : <Dash />;
}

function EditAction(props: { edit: TemplateSummaryEdit | undefined; step: number; section: string }) {
  const { t } = useTranslation();
  if (props.edit === undefined) return null;
  const label = t("work.template.summary.editSection", { section: props.section, defaultValue: "Edit {{section}}" });
  const text = t("work.template.summary.edit", { defaultValue: "✎ Edit" });
  const className =
    "bg-transparent p-0 text-sm font-semibold text-accent hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";
  if (props.edit.kind === "link") {
    return (
      <Link className={className} to={props.edit.href(props.step)} aria-label={label} data-summary-edit={props.step}>
        {text}
      </Link>
    );
  }
  const onJump = props.edit.onJump;
  return (
    <button type="button" className={className} aria-label={label} onClick={() => onJump(props.step)} data-summary-edit={props.step}>
      {text}
    </button>
  );
}

function Section(props: {
  id: string;
  step: number;
  title: string;
  section: string;
  edit: TemplateSummaryEdit | undefined;
  children: ReactNode;
}) {
  return (
    <Panel
      as="section"
      title={props.title}
      trailing={<EditAction edit={props.edit} step={props.step} section={props.section} />}
      data-summary-section={props.id}
    >
      {props.children}
    </Panel>
  );
}

function ReadTable<Row>(props: {
  name: string;
  columns: EditableColumn<Row>[];
  rows: Row[];
  rowKey: (row: Row, index: number) => string;
  empty: string;
}) {
  return (
    <EditableTable<Row>
      readOnly
      caption=""
      reorderable={false}
      columns={props.columns}
      rows={props.rows}
      rowKey={props.rowKey}
      emptyText={props.empty}
      data-collection={`summary-${props.name}`}
    />
  );
}

/**
 * The template, every row of it — a header panel and one panel per section in
 * the builder's order, each with its real rows in the product's own table.
 */
export function TemplateSummary(props: TemplateSummaryProps) {
  const { t } = useTranslation();
  const tr: Translate = (key, params) => t(key, params);
  const { draft, names, edit } = props;
  const minutes = taskMinutes(draft.tasks);
  const crew = Number.parseInt(draft.crewSize, 10);
  const step = (id: string) => SUMMARY_SECTIONS.find((s) => s.id === id)?.step ?? 1;
  const word = (key: string, en: string) => tr(key, { defaultValue: en });

  const sees = [
    draft.showAccountSummary ? word("work.builder.sees.account", "Account & premise summary") : null,
    draft.showAssetCard ? word("work.builder.sees.asset", "Asset card — meter ID, last read") : null,
    draft.showAccessNotes ? word("work.builder.sees.access", "Access notes & hazards") : null,
    draft.showAppointment ? word("work.builder.sees.appointment", "Appointment window & customer phone") : null,
    draft.showBalancePayments ? word("work.builder.sees.balance", "Balance & payments") : null,
  ].filter((one): one is string => one !== null);

  const safetyColumns: EditableColumn<SafetyDraft>[] = [
    { key: "text", label: word("work.builder.safety.col.text", "Check"), cell: (row) => row.text },
    { key: "mustDo", label: word("work.builder.safety.col.mustDo", "Must do"), cell: (row) => yes(row.isMandatory, tr) },
  ];
  const taskColumns: EditableColumn<TaskDraft>[] = [
    {
      key: "task",
      label: word("work.builder.tasks.col.task", "Task"),
      // PO answer 3 — the instruction is a SECOND LINE under its task (CR-168
      // §5.7 S3), the same shape the job's checklist draws.
      cell: (row) => (
        <span className="flex flex-col">
          <span>{row.title}</span>
          {row.instruction.trim() === "" ? null : (
            <span className="mt-1 text-sm text-neutral-700" data-task-instruction="">
              {row.instruction}
            </span>
          )}
        </span>
      ),
    },
    {
      key: "minutes",
      numeric: true,
      label: word("work.builder.tasks.col.minutes", "Minutes"),
      cell: (row) => (row.estMinutes === "" ? <Dash /> : row.estMinutes),
    },
    { key: "photo", label: word("work.builder.tasks.col.photo", "Photo"), cell: (row) => yes(row.photoRequired, tr) },
    { key: "mustDo", label: word("work.builder.tasks.col.mustDo", "Must do"), cell: (row) => yes(row.isMandatory, tr) },
  ];
  const materialColumns: EditableColumn<MaterialDraft>[] = [
    { key: "part", label: word("work.builder.materials.col.part", "Part"), cell: (row) => `${row.partNo} · ${row.name}` },
    {
      key: "qty",
      numeric: true,
      label: word("work.builder.materials.col.qty", "Quantity"),
      cell: (row) => trimQuantity(row.plannedQty),
    },
    { key: "unit", label: word("work.builder.materials.col.unit", "Unit"), cell: (row) => row.unitOfMeasure },
  ];
  const readingColumns: EditableColumn<ReadingDraft>[] = [
    { key: "prompt", label: word("work.builder.readings.col.prompt", "Prompt"), cell: (row) => row.prompt },
    { key: "unit", label: word("work.builder.readings.col.unit", "Unit"), cell: (row) => row.unitOfMeasure || <Dash /> },
    {
      key: "min",
      numeric: true,
      label: word("work.builder.readings.col.min", "Min"),
      cell: (row) => (row.min === "" ? <Dash /> : trimQuantity(row.min)),
    },
    {
      key: "max",
      numeric: true,
      label: word("work.builder.readings.col.max", "Max"),
      cell: (row) => (row.max === "" ? <Dash /> : trimQuantity(row.max)),
    },
    { key: "photo", label: word("work.builder.readings.col.photo", "Photo"), cell: (row) => yes(row.photoRequired, tr) },
    {
      key: "posts",
      label: word("work.builder.readings.col.posts", "Becomes a meter read"),
      cell: (row) => yes(row.postsAsMeterRead, tr),
    },
  ];
  const helpColumns: EditableColumn<HelpDraft>[] = [
    { key: "kind", label: word("work.builder.help.col.kind", "Kind"), cell: (row) => helpKindWord(row.kind, tr) },
    { key: "label", label: word("work.builder.help.col.label", "What it is"), cell: (row) => row.label },
    { key: "ref", label: word("work.builder.help.col.ref", "Where to find it"), cell: (row) => <HelpWhere row={row} t={tr} /> },
  ];

  const sectionName = (id: string, en: string) => word(`work.builder.step.${id}`, en);
  const counted = (key: string, en: string, count: number, extra?: Record<string, unknown>) =>
    tr(key, { count, defaultValue: en, ...extra });

  return (
    <div className="flex flex-col gap-4" data-testid="template-summary" data-template-summary="">
      <Panel as="section" title={draft.name === "" ? word("work.template.summary.unnamed", "Unnamed template") : draft.name} data-summary-section="header">
        <FactList>
          <Fact label={word("work.template.summary.service", "Service")}>{names.service ?? <Dash />}</Fact>
          <Fact label={word("work.template.summary.doneTo", "Done to")}>{scopeWord(draft.scope, tr) ?? <Dash />}</Fact>
          <Fact label={word("work.template.summary.time", "Estimated time")}>
            {minutes === 0 ? <Dash /> : tr("work.templates.minutes", { count: minutes, defaultValue: "{{count}} min" })}
          </Fact>
          <Fact label={word("work.template.summary.crew", "Crew")}>
            {tr("work.template.crew", { count: Number.isFinite(crew) && crew >= 1 ? crew : 1, defaultValue: "{{count}} technician" })}
          </Fact>
        </FactList>
      </Panel>

      <Section id="details" step={step("details")} title={sectionName("details", "Details")} section={sectionName("details", "Details")} edit={edit}>
        <FactList>
          <Fact label={word("work.template.summary.jobType", "Job type")}>{names.jobType ?? <Dash />}</Fact>
          <Fact label={word("work.template.summary.assetTypes", "Asset types")}>
            {names.assetTypes.length === 0 ? <Dash /> : names.assetTypes.join(", ")}
          </Fact>
          <Fact label={word("work.template.summary.skill", "Skill needed")}>{names.skill ?? <Dash />}</Fact>
          <Fact label={word("work.template.summary.safetyKit", "Safety kit")}>{names.safetyKit ?? <Dash />}</Fact>
          <Fact label={word("work.template.summary.sees", "Technician sees")}>
            {sees.length === 0 ? word("work.template.summary.seesNothing", "Nothing checked") : sees.join(", ")}
          </Fact>
          {/* `DEF-WRK-10652` — what the customer hears, read back. */}
          <Fact label={word("work.template.summary.customerMessages", "Customer messages")}>
            {yes(draft.sendCustomerVisitMessages, tr)}
          </Fact>
          <Fact label={word("work.template.summary.prep", "Preparation")}>
            {draft.prepInstructions.trim() === ""
              ? word("work.template.summary.prepDefault", "Utility default")
              : draft.prepInstructions.trim()}
          </Fact>
        </FactList>
      </Section>

      <Section
        id="safety"
        step={step("safety")}
        title={counted("work.template.summary.safetyTitle", "Safety · {{count}}", draft.safety.length)}
        section={sectionName("safety", "Safety")}
        edit={edit}
      >
        <ReadTable
          name="safety"
          columns={safetyColumns}
          rows={draft.safety}
          rowKey={(row, index) => `${index}-${row.text}`}
          empty={word("work.template.summary.safetyEmpty", "No safety checks.")}
        />
      </Section>

      <Section
        id="tasks"
        step={step("tasks")}
        title={
          minutes === 0
            ? counted("work.template.summary.tasksTitle", "Tasks · {{count}}", draft.tasks.length)
            : counted("work.template.summary.tasksTitleMinutes", "Tasks · {{count}} · {{minutes}} min", draft.tasks.length, { minutes })
        }
        section={sectionName("tasks", "Tasks")}
        edit={edit}
      >
        <ReadTable
          name="tasks"
          columns={taskColumns}
          rows={draft.tasks}
          rowKey={(row, index) => `${index}-${row.title}`}
          empty={word("work.template.summary.tasksEmpty", "No tasks.")}
        />
      </Section>

      <Section
        id="materials"
        step={step("materials")}
        title={counted("work.template.summary.materialsTitle", "Materials · {{count}}", draft.materials.length)}
        section={sectionName("materials", "Materials")}
        edit={edit}
      >
        <ReadTable
          name="materials"
          columns={materialColumns}
          rows={draft.materials}
          rowKey={(row, index) => `${index}-${row.partId}`}
          empty={word("work.template.summary.materialsEmpty", "No parts planned.")}
        />
      </Section>

      <Section
        id="readings"
        step={step("readings")}
        title={counted("work.template.summary.readingsTitle", "Readings · {{count}}", draft.readings.length)}
        section={sectionName("readings", "Readings")}
        edit={edit}
      >
        <ReadTable
          name="readings"
          columns={readingColumns}
          rows={draft.readings}
          rowKey={(row, index) => `${index}-${row.prompt}`}
          empty={word("work.template.summary.readingsEmpty", "Nothing is measured.")}
        />
      </Section>

      <Section
        id="help"
        step={step("help")}
        title={counted("work.template.summary.helpTitle", "Help · {{count}}", draft.help.length)}
        section={sectionName("help", "Help")}
        edit={edit}
      >
        <ReadTable
          name="help"
          columns={helpColumns}
          rows={draft.help}
          rowKey={(row, index) => `${index}-${row.label}`}
          empty={word("work.template.summary.helpEmpty", "No help attached.")}
        />
      </Section>

      <Section id="signature" step={step("signature")} title={sectionName("signature", "Signature")} section={sectionName("signature", "Signature")} edit={edit}>
        <FactList>
          <Fact label={word("work.template.summary.signs", "Customer signs")}>{yes(draft.signatureRequired, tr)}</Fact>
          <Fact label={word("work.template.summary.refusal", "Refusal reason")}>{yes(draft.refusalReasonRequired, tr)}</Fact>
          <Fact label={word("work.template.summary.card", "Card if nobody is in")}>{yes(draft.doorHangerOnNoAnswer, tr)}</Fact>
        </FactList>
      </Section>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §8 R4 TEMPLATES · images 44, 55 · P3.26
// generated: 2026-10-04 by lane TEMPLATES
// checklist: A✔ B✔ C✔ D✔ E✔(TemplateBuilder step 8, TemplateDetailPage Overview) F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work/cr168Templates.dom.test.tsx · routeBUtilities (on src/styles/route-b-migrated.txt)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
