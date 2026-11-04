// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-016 (EP-WRK-03) — the eight-step template builder.
//           Screens: Work-014 · Work-015 · Work-016 · Work-017
// Rules:    BR-WRK-011 (Publish is the ONE write; seven steps persist as a
//           DRAFT) · BR-WRK-009 (a bundle is ROWS, and `seq` is the order the
//           list is in) · BR-WRK-015 (a reading's unit is a column) ·
//           CLAUDE.md hard rule 2 (a quantity is a STRING client-side, never a
//           float) · hard rule 3 (a quantity carries its unit)
// Tests:    src/features/work/templateBuilderModel.test.ts
// Impacts:  src/features/work/TemplateBuilder.tsx (renders this) ·
//           src/features/work/workEndpoints.ts (what it posts)
// ───────────────────────────────────────────────────────
//
// THE BUILDER'S STATE, AND THE THREE THINGS IT DOES TO IT — kept out of the
// screen so each can be asserted without mounting anything, which is the same
// posture `commitPlanOf` takes in the New Connect wizard one module over.
//
// ⚠ **EVERY NUMBER A PERSON TYPES IS A STRING HERE.** Minutes, a planned
// quantity, a reading's min and max. Hard rule 2 says money and quantities are
// decimal text end to end and the server owns the parsing; a `number` in this
// file would be a parse in a browser, which is where a trailing zero and a
// locale separator go wrong. Minutes are the one place a number appears, and
// only at the boundary — `taskMinutes` sums them for the screen.
import { trimQuantity } from "@/components/UnitCell";

import type { TemplateBundle, TemplateDetail, TemplatePack } from "./workEndpoints";

export interface SafetyDraft {
  text: string;
  isMandatory: boolean;
}

export interface TaskDraft {
  title: string;
  /** A STRING, because a person typed it. `""` is *not estimated* and is
   *  lawful; `0` with *must do* on is ALSO lawful (`US-WRK-014` TC-4 — a
   *  mandatory zero-minute check is a real thing). */
  estMinutes: string;
  photoRequired: boolean;
  isMandatory: boolean;
  /** PO answer 3 (2026-10-04, decision log *"THREE WORK ANSWERS"* (3)): *"Add
   *  an instruction text box to each task, shown on the technician's phone."*
   *  Optional — `""` is *no instruction* and travels as `null`. Drawn as a
   *  second line under the task, on the builder, the summary and the job's
   *  checklist (CR-168 §5.7 S3). */
  instruction: string;
  /** FB-013 (`DEF-WRK-10641`, PO 2026-10-28) — *Check payment before this
   *  step*: the phone reads the account's money first and, on a FRESH read
   *  showing it cleared, stops the step (R18: the check is data on the step,
   *  `wot_tasks.money_fresh_minutes`). */
  moneyCheck: boolean;
  /** How fresh the figure must be, in minutes — a STRING (a person typed it);
   *  default 5 (R17), at least 1. Sent only when `moneyCheck` is on. */
  moneyMinutes: string;
  /** R111 — the utility's own charge code for a fee the step asks about
   *  (FF-61). `""` is *no fee question* and travels as `null`. */
  moneyChargeCode: string;
}

/** FB-028 (PO 2026-10-31) — the PO's own figure, on a template that turns the
 *  payment check on. A seeded default the utility edits, never signed law. */
export const RECONNECT_LIMIT_DEFAULT = "25.00";

/** The server's 4-place amount (`"25.0000"`) as the builder shows it: 2
 *  places (hard rule 2). Absent or unreadable reads as the default. */
export function limitText(stored: string | null | undefined): string {
  if (stored === null || stored === undefined || stored.trim() === "") return RECONNECT_LIMIT_DEFAULT;
  const match = /^(\d+)(?:\.(\d+))?$/.exec(stored.trim());
  if (!match) return RECONNECT_LIMIT_DEFAULT;
  const cents = `${match[2] ?? ""}00`.slice(0, 2);
  return `${match[1]}.${cents}`;
}

/** What the template sends: the typed amount while any step checks payment
 *  (blank → the default), `null` when no step does. The server refuses
 *  anything that is not a non-negative amount, by name. */
export function reconnectLimitPayload(draft: { tasks: { moneyCheck: boolean }[]; reconnectLimit: string }): string | null {
  if (!draft.tasks.some((row) => row.moneyCheck)) return null;
  const typed = draft.reconnectLimit.trim();
  return typed === "" ? RECONNECT_LIMIT_DEFAULT : typed;
}

/** R17's five minutes — the bar a newly ticked payment check starts at. */
export const MONEY_CHECK_DEFAULT_MINUTES = "5";

/** The three money fields of a task row, from what the server stores. */
export function moneyFieldsOf(row: {
  money_fresh_minutes?: number | null;
  money_charge_code?: string | null;
}): Pick<TaskDraft, "moneyCheck" | "moneyMinutes" | "moneyChargeCode"> {
  const minutes = row.money_fresh_minutes;
  const on = typeof minutes === "number" && minutes >= 1;
  return {
    moneyCheck: on,
    moneyMinutes: on ? String(minutes) : MONEY_CHECK_DEFAULT_MINUTES,
    moneyChargeCode: row.money_charge_code ?? "",
  };
}

/** What a task row sends for its money check: both columns, NULL when off —
 *  so a template saved from the builder never loses a check it had
 *  (`DEF-WRK-10641`: the PUT replaces the rows, and these were not sent). */
export function moneyPayloadOf(row: TaskDraft): {
  money_fresh_minutes: number | null;
  money_charge_code: string | null;
} {
  if (!row.moneyCheck) return { money_fresh_minutes: null, money_charge_code: null };
  const minutes = Number.parseInt(row.moneyMinutes, 10);
  const code = row.moneyChargeCode.trim();
  return {
    money_fresh_minutes:
      Number.isFinite(minutes) && minutes >= 1 ? minutes : Number(MONEY_CHECK_DEFAULT_MINUTES),
    money_charge_code: code === "" ? null : code,
  };
}

export interface MaterialDraft {
  partId: string;
  partNo: string;
  name: string;
  plannedQty: string;
  unitOfMeasure: string;
}

export interface ReadingDraft {
  prompt: string;
  /** hard rule 3 — a COLUMN, never a word inside the prompt. Required: the
   *  server refuses a blank one by name (`US-WRK-014` TC-3). */
  unitOfMeasure: string;
  min: string;
  max: string;
  required: boolean;
  photoRequired: boolean;
  postsAsMeterRead: boolean;
}

/** The kinds a clerk can ADD (ruling 6, field map B9): a document, a phone
 *  number, a link to a video or web page. `note` is the kind before ruling 6;
 *  a stored note still reads and edits as itself, and is never offered new. */
export const HELP_KINDS_OFFERED = ["document", "phone", "link"] as const;

export interface HelpDraft {
  kind: string;
  label: string;
  /** WHERE TO FIND IT, in the kind's own terms — a shelf for a document with
   *  no file, a phone number, or (kind `link`) the https address. */
  ref: string;
  /** A held document (P3.14): the stored file's name and size, read back from
   *  the server. `""` / null when the document is a pointer, not a file. */
  fileName: string;
  fileBytes: number | null;
}

export interface BuilderDraft {
  /** Step 1 — the header. */
  name: string;
  service: string;
  /** P3.12 (`DEF-WRK-9577`) — what the job is DONE TO: `per_premise`,
   *  `per_unit` or `per_asset`. `""` until asked: the builder never sent it, so
   *  every template it made saved as premises by the column's default. */
  scope: string;
  jobTypeId: string;
  assetTypeIds: string[];
  skillId: string;
  safetyKitId: string;
  crewSize: string;
  /** Step 1's four ticks — `wot_details`, *WHAT THE TECHNICIAN SEES ON THE JOB*. */
  showAccountSummary: boolean;
  showAssetCard: boolean;
  showAccessNotes: boolean;
  showAppointment: boolean;
  /** FB-023 F4 — Balance & payments: the phone hides the balance card and
   *  payment facts when off; a money step's stop still reads the balance. */
  showBalancePayments: boolean;
  /** FB-028 (PO 2026-10-31) — *Reconnect limit*: the most a customer may still
   *  owe for a technician to reconnect a job raised on site. Shown and sent
   *  only while a step checks payment; a STRING (a person typed it), 2 places
   *  shown, stored by the server to 4. Default `25.00`. */
  reconnectLimit: string;
  /** Step 7 — what the technician has to BRING BACK. `work/0005`. */
  signatureRequired: boolean;
  refusalReasonRequired: boolean;
  doorHangerOnNoAnswer: boolean;
  /** `DEF-WRK-10652` (PO 2026-10-29, rulings 3B and 4A) — what the CUSTOMER is
   *  asked to prepare (blank reads the utility's default), and whether this
   *  template's jobs send the customer any visit message at all. */
  prepInstructions: string;
  sendCustomerVisitMessages: boolean;
  /** Steps 2 to 6. The ORDER of each list is the `seq` the phone shows. */
  safety: SafetyDraft[];
  tasks: TaskDraft[];
  materials: MaterialDraft[];
  readings: ReadingDraft[];
  help: HelpDraft[];
  /** Which pack step 1 prefilled from, for the screen only. **Never stored**:
   *  a pack is prefill, not a link (`US-WRK-016` §5). */
  packCode: string;
}

export function emptyBuilderDraft(): BuilderDraft {
  return {
    name: "",
    service: "",
    scope: "",
    jobTypeId: "",
    assetTypeIds: [],
    skillId: "",
    safetyKitId: "",
    crewSize: "1",
    showAccountSummary: true,
    showAssetCard: true,
    showAccessNotes: true,
    showAppointment: true,
    showBalancePayments: true,
    reconnectLimit: RECONNECT_LIMIT_DEFAULT,
    // Hard-won law 3 — the SAFE option is the default and the unsafe one is
    // the one a person types. A template that says nothing about signatures
    // asks for one.
    signatureRequired: true,
    refusalReasonRequired: true,
    doorHangerOnNoAnswer: true,
    prepInstructions: "",
    sendCustomerVisitMessages: true,
    safety: [],
    tasks: [],
    materials: [],
    readings: [],
    help: [],
    packCode: "",
  };
}

/**
 * `Work-015`'s *TASKS — 7 STEPS · 45 MIN TOTAL*, and `Work-013`'s EST. cell.
 *
 * ⚠ **THIS IS THE FIGURE THE DISPATCHER SCHEDULES AGAINST**, which is what the
 * step's own consequence box says: *"Estimates that are wrong here make every
 * day's route wrong."* A blank estimate counts as nothing rather than breaking
 * the sum — a person part-way through step 3 still sees a true total of what
 * they have typed.
 */
export function taskMinutes(tasks: readonly TaskDraft[]): number {
  return tasks.reduce((total, task) => {
    const parsed = Number.parseInt(task.estMinutes, 10);
    return total + (Number.isFinite(parsed) && parsed > 0 ? parsed : 0);
  }, 0);
}

/** The three answers to *Done to*, in the order a template narrows: the
 *  whole property, one unit of it, one asset on it (`work_order_templates.scope`). */
export const TEMPLATE_SCOPES = ["per_premise", "per_unit", "per_asset"] as const;

/** An https address — the only kind a Link row takes (P3.25: *"an https-only
 *  address"*). A plain `http` page would open on the phone over an
 *  unencrypted connection, so it is refused rather than upgraded. */
export function isHttpsAddress(value: string): boolean {
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" && url.hostname.includes(".");
  } catch {
    return false;
  }
}

/** A video host the phone streams rather than opens (P3.25: *"a YouTube
 *  address badged ▶ Video"*). */
export function isVideoAddress(value: string): boolean {
  if (!isHttpsAddress(value)) return false;
  const host = new URL(value.trim()).hostname.replace(/^www\./u, "").replace(/^m\./u, "");
  return host === "youtube.com" || host === "youtu.be" || host === "vimeo.com";
}

/** Whether a help row may be ADDED: it needs words, and a link needs an https
 *  address. A document or a phone may name no place yet. */
export function helpRowAddable(kind: string, label: string, ref: string): boolean {
  if (label.trim() === "") return false;
  if (kind === "link") return isHttpsAddress(ref);
  return true;
}

/**
 * FB-031 (DEF-FLD-10805) — what a help row is MISSING for a technician to use
 * it: a document with no uploaded file, or a phone with no number. The
 * builder marks the row (*No file*, *No number*) and the server refuses to
 * publish an empty one (`templates_svc._refuse_empty_help`). A typed label on
 * a document row is not a file and reads *No file* too.
 */
export function helpRowMissing(row: { kind: string; ref: string; fileName: string }): "noFile" | "noNumber" | null {
  if (row.kind === "document" && row.fileName === "") return "noFile";
  if (row.kind === "phone" && !/\d/u.test(row.ref)) return "noNumber";
  return null;
}

/**
 * A pack, poured into an empty draft. **Steps 2 to 6 arrive filled and every
 * row stays editable** (`US-WRK-016` §1 and TC-1).
 *
 * ⚠ **THE HEADER IS NOT TOUCHED.** A pack knows nothing about this utility's
 * services, job types, skills or kits, and prefilling a SERVICE would be the
 * pack deciding what a clerk is authoring. Only the collections travel, plus
 * `packCode`, which the screen shows and nothing stores.
 */
export function applyPack(draft: BuilderDraft, pack: TemplatePack): BuilderDraft {
  return {
    ...draft,
    packCode: pack.code,
    showAccountSummary: pack.bundle.details.show_account_summary ?? true,
    showAssetCard: pack.bundle.details.show_asset_card ?? true,
    showAccessNotes: pack.bundle.details.show_access_notes ?? true,
    showAppointment: pack.bundle.details.show_appointment ?? true,
    showBalancePayments: pack.bundle.details.show_balance_payments ?? true,
    safety: pack.bundle.safety.map((row) => ({
      text: row.text,
      isMandatory: row.is_mandatory,
    })),
    tasks: pack.bundle.tasks.map((row) => ({
      title: row.title,
      estMinutes: String(row.est_minutes),
      photoRequired: row.photo_required,
      isMandatory: row.is_mandatory,
      instruction: row.instruction ?? "",
      ...moneyFieldsOf(row),
    })),
    materials: pack.bundle.materials.map((row) => ({
      partId: row.part_id,
      partNo: row.part_no,
      name: row.name,
      plannedQty: trimQuantity(row.planned_qty),
      unitOfMeasure: row.unit_of_measure,
    })),
    readings: pack.bundle.readings.map((row) => ({
      prompt: row.prompt,
      unitOfMeasure: row.unit_of_measure,
      min: trimQuantity(row.min ?? ""),
      max: trimQuantity(row.max ?? ""),
      required: row.required,
      photoRequired: row.photo_required,
      postsAsMeterRead: row.posts_as_meter_read,
    })),
    help: pack.bundle.help.map((row) => ({
      kind: row.kind,
      label: row.label,
      ref: row.ref ?? "",
      fileName: "",
      fileBytes: null,
    })),
  };
}

/** *Start empty* — the fourth tile. Everything the packs would have filled goes
 *  back to nothing, and the header the clerk has already typed stays. */
export function clearPack(draft: BuilderDraft): BuilderDraft {
  return {
    ...draft,
    packCode: "EMPTY",
    safety: [],
    tasks: [],
    materials: [],
    readings: [],
    help: [],
  };
}

/** An existing template, poured back into the builder — what *Edit template*
 *  on `Work-022` opens with. */
export function draftFromTemplate(row: TemplateDetail): BuilderDraft {
  const bundle: TemplateBundle = row.bundle;
  const details = bundle.details;
  return {
    name: row.name,
    service: row.service?.code ?? "",
    scope: row.scope ?? "",
    jobTypeId: row.job_type?.id ?? "",
    assetTypeIds: bundle.asset_types.map((one) => one.asset_type_id),
    skillId: row.skill?.id ?? "",
    safetyKitId: row.safety_kit?.id ?? "",
    crewSize: String(row.crew_size ?? 1),
    showAccountSummary: details?.show_account_summary ?? true,
    showAssetCard: details?.show_asset_card ?? true,
    showAccessNotes: details?.show_access_notes ?? true,
    showAppointment: details?.show_appointment ?? true,
    showBalancePayments: details?.show_balance_payments ?? true,
    reconnectLimit: limitText(details?.reconnect_limit),
    signatureRequired: details?.signature_required ?? true,
    refusalReasonRequired: details?.refusal_reason_required ?? true,
    doorHangerOnNoAnswer: details?.door_hanger_on_no_answer ?? true,
    prepInstructions: details?.prep_instructions ?? "",
    sendCustomerVisitMessages: details?.send_customer_visit_messages ?? true,
    safety: bundle.safety.map((one) => ({ text: one.text, isMandatory: one.is_mandatory })),
    tasks: bundle.tasks.map((one) => ({
      title: one.title,
      estMinutes: String(one.est_minutes),
      photoRequired: one.photo_required,
      isMandatory: one.is_mandatory,
      instruction: one.instruction ?? "",
      ...moneyFieldsOf(one),
    })),
    materials: bundle.materials.map((one) => ({
      partId: one.part_id,
      partNo: one.part_no,
      name: one.name,
      plannedQty: trimQuantity(one.planned_qty),
      unitOfMeasure: one.unit_of_measure,
    })),
    readings: bundle.readings.map((one) => ({
      prompt: one.prompt,
      unitOfMeasure: one.unit_of_measure,
      min: trimQuantity(one.min ?? ""),
      max: trimQuantity(one.max ?? ""),
      required: one.required,
      photoRequired: one.photo_required,
      postsAsMeterRead: one.posts_as_meter_read,
    })),
    help: bundle.help.map((one) => ({
      kind: one.kind,
      label: one.label,
      // A link's address is its `link`; every other kind's place is `ref`.
      ref: (one.kind === "link" ? (one.link ?? one.ref) : one.ref) ?? "",
      fileName: one.file?.name ?? "",
      fileBytes: one.file?.bytes ?? null,
    })),
    packCode: "",
  };
}

/** What `POST`/`PATCH /work/templates` is sent. */
export function headerPayload(draft: BuilderDraft): {
  name: string;
  service: string;
  scope?: string;
  type_id: string | null;
  skill_id: string | null;
  safety_kit_id: string | null;
  crew_size: number;
  est_duration_minutes: number | null;
} {
  const minutes = taskMinutes(draft.tasks);
  const crew = Number.parseInt(draft.crewSize, 10);
  return {
    name: draft.name.trim(),
    service: draft.service,
    // P3.12 — sent only once answered. Absent leaves the column alone, so an
    // unanswered draft cannot overwrite a template's real scope with a blank.
    ...(draft.scope === "" ? {} : { scope: draft.scope }),
    // An empty picker is a real answer — *not chosen* — and `null` is how the
    // column says so. `""` would be a lookup id nothing matches.
    type_id: draft.jobTypeId === "" ? null : draft.jobTypeId,
    skill_id: draft.skillId === "" ? null : draft.skillId,
    safety_kit_id: draft.safetyKitId === "" ? null : draft.safetyKitId,
    crew_size: Number.isFinite(crew) && crew >= 1 ? crew : 1,
    // ⚠ **THE HEADER'S ESTIMATE IS THE SUM OF THE TASKS AND IS NEVER TYPED
    // TWICE.** `Work-013`'s EST. cell and `Work-015`'s panel caption are the
    // same figure; a second field for it would be a second answer to one
    // question, which the 2026-09-05 ruling names as how a figure drifts.
    est_duration_minutes: minutes === 0 ? null : minutes,
  };
}

/** What each `PUT /work/templates/{id}/{collection}` is sent. The LIST ORDER is
 *  the `seq`, which the server assigns — a caller never sends one. */
export function collectionPayloads(draft: BuilderDraft): {
  details: Record<string, boolean | string | null>;
  safety: Record<string, unknown>[];
  tasks: Record<string, unknown>[];
  materials: Record<string, unknown>[];
  readings: Record<string, unknown>[];
  help: Record<string, unknown>[];
  "asset-types": Record<string, unknown>[];
} {
  return {
    details: {
      show_account_summary: draft.showAccountSummary,
      show_asset_card: draft.showAssetCard,
      show_access_notes: draft.showAccessNotes,
      show_appointment: draft.showAppointment,
      show_balance_payments: draft.showBalancePayments,
      // FB-028 — only with a payment check; blank with one is the default.
      reconnect_limit: reconnectLimitPayload(draft),
      signature_required: draft.signatureRequired,
      refusal_reason_required: draft.refusalReasonRequired,
      door_hanger_on_no_answer: draft.doorHangerOnNoAnswer,
      // `DEF-WRK-10652` — ALWAYS sent, so a save carries what the editor
      // shows. Blank is `null`: *use the utility's default*.
      prep_instructions: draft.prepInstructions.trim() === "" ? null : draft.prepInstructions.trim(),
      send_customer_visit_messages: draft.sendCustomerVisitMessages,
    },
    safety: draft.safety.map((row) => ({ text: row.text, is_mandatory: row.isMandatory })),
    tasks: draft.tasks.map((row) => ({
      title: row.title,
      est_minutes: row.estMinutes === "" ? 0 : Number.parseInt(row.estMinutes, 10),
      photo_required: row.photoRequired,
      is_mandatory: row.isMandatory,
      instruction: row.instruction.trim() === "" ? null : row.instruction.trim(),
      ...moneyPayloadOf(row),
    })),
    materials: draft.materials.map((row) => ({
      part_id: row.partId,
      planned_qty: row.plannedQty,
      unit_of_measure: row.unitOfMeasure,
    })),
    readings: draft.readings.map((row) => ({
      prompt: row.prompt,
      unit_of_measure: row.unitOfMeasure,
      // `""` is *not bounded*, which is a different fact from `0`. A range the
      // utility did not set must not become a range of zero.
      min: row.min === "" ? null : row.min,
      max: row.max === "" ? null : row.max,
      required: row.required,
      photo_required: row.photoRequired,
      posts_as_meter_read: row.postsAsMeterRead,
    })),
    // ⚠ A LINK TRAVELS AS `link` (CR-168 §7.3; SRV-3 checks it is https and
    // stores it). A held document travels as the `ref` its upload answered.
    help: draft.help.map((row) =>
      row.kind === "link"
        ? { kind: row.kind, label: row.label, link: row.ref.trim() }
        : { kind: row.kind, label: row.label, ref: row.ref === "" ? null : row.ref },
    ),
    "asset-types": draft.assetTypeIds.map((id) => ({ asset_type_id: id })),
  };
}

/** Step 1's own gate: a template needs a name, a service and what it is done
 *  to (P3.12 — asked, never defaulted) before anything
 *  below it means anything. Everything else is optional — `US-WRK-015` TC-5
 *  publishes a template with no tasks and no readings, because some jobs are a
 *  visit and a signature. */
export function step1Complete(draft: BuilderDraft): boolean {
  return draft.name.trim() !== "" && draft.service !== "" && draft.scope !== "";
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-016@2b08ba9f (EP-WRK-03) · 10-execution-plan.md wave E task E1 · 08-screen-layouts.md §13.1 · J60 steps 6–9
// generated: 2026-09-05 by the CR-070 wave E build lane
// checklist: A✔ B✔ C✔ D✔ E✔(TemplateBuilder.tsx) F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work/templateBuilderModel.test.ts
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
