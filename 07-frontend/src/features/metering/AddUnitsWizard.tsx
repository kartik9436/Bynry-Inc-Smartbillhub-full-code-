// ── Trace ──────────────────────────────────────────────
// Change:   CR-176-BRC10 — the Add units REDESIGN (PO go 2026-10-09, decision
//           log *"PO GO — BUILD THE ADD-UNITS REDESIGN"*), over CR-089 wave E.
// Defect:   DEF-MET-10035 — *Start numbering at* defaulted to 1 with Unit 1
//           taken; *Units to create: 0* beside How many; an unlabelled
//           *Not recorded* on the building card; too much text.
// Drawing:  05-prototype/add-units-redesign-2026-10-09/images/01–11 (built
//           from the images, B14 rule 42; our kit, spacing and tokens win over
//           the drawing's styling, rule 44; example data is illustration,
//           rule 37).
// Story:    US-MET-003 (guided add)  Screens: S16 (the add-units half)
// Rules:    CR-176 rules (1) next free start · (2) one count · (3) services
//           only from the building, all ticked · (4) building by search and
//           *Use this building* · (5) a common area is a choice at the start,
//           one unit, billed to the owner · (6) unit numbers from the series
//           unless *My own pattern* · BR-MET-1165 (a number the review shows is
//           TAKEN ON THE PRESS — never reserved by the preview) · BR-MET-005/031
//           (floors × per-floor, `{seq}`/`{floor}`) · BR-MET-007 (a plan at
//           creation, optional) · BR-MET-119 as amended 2026-09-25 ·
//           BR-MET-083(b) · BR-SHL-018/019 · B14 rules 21, 31, 32, 33, 43
// ───────────────────────────────────────────────────────
//
// ADDING UNITS TO A BUILDING. TWO STEPS, AND THE SECOND ONE WRITES.
//
// **What the redesign keeps from the screen it replaces, because each was a
// ruling:**
//   · the building is named first and stays on screen (CR-089 E3);
//   · `Floor` is FREE TEXT, never a list — `units.floor_label` holds `Ground`,
//     `G`, `Mezzanine`, `PH`, and the edit form shows what the create wrote
//     (decision log 2026-09-10);
//   · `Floor area` is on the add form (PO 2026-09-19) and is one value written
//     onto every unit the run creates;
//   · the plan picker shows EVERY plan with a search box, never narrowed to the
//     unit's services (PO 2026-09-10);
//   · `← Units` in the head, `Cancel` in the footer (PO 2026-09-19);
//   · nothing is written until the press: Continue STAGES through
//     `POST /premises/imports` (which writes nothing, `BR-MET-004`) and the
//     press re-stages the identical body and creates, all or none
//     (`skip_errors: false`);
//   · the review's labels are the SERVER's staging, and its numbers are what
//     the series will issue NEXT — never held (`BR-MET-1165`, `DEF-MET-4719`).
//
// **What the redesign changes, each from the 2026-10-09 go:**
//   · the building is found by search and confirmed with *Use this building*
//     (`PickBySearch`, the Owner pattern on Add a premise);
//   · *Start numbering at* starts at the first number from which the WHOLE run
//     is free, asked of the server (`GET /premises/{id}/units/next-free`), and
//     a taken number is named with *Use N*;
//   · ONE count — `total` below — drives the *Creates* box, the *These units*
//     card, Review and the button. The old *Units to create: 0* read a box that
//     started EMPTY while the drawing (and the clerk) meant one;
//   · *Units* / *A common area* is a choice at the top, and a common area is
//     one unit of the chosen kind, billed to the owner;
//   · the services are a dropdown of the building's own, ALL ticked to start;
//   · *Names & numbers* and *Plan & start* fold closed and say their choice;
//   · every sentence of explanation is gone (B14 rules 32/33).
//
// ⚠ **NO STYLESHEET CLASS IS ADDED BY THIS FILE (B14 rule 21).** It is on
// `styles/route-b-migrated.txt`.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  commitPremisesImport,
  getPremises,
  getPremisesLends,
  getPremisesUnitsNextFree,
  getUnitNumberPreview,
  getUnitPlanOptions,
  stagePremisesImport,
} from "@/api/endpoints";
import type { ImportRequest, ImportStage, PremisesLends, PremisesRow } from "@/api/endpoints";
import { CheckDropdown } from "@/components/CheckDropdown";
import { CustomFieldsAnswers, CustomFieldsInput, customFieldErrors } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Disclosure } from "@/components/Disclosure";
import {
  DatePickerField,
  FieldErrorsScope,
  SearchSelectField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PickBySearch } from "@/components/PickBySearch";
import type { PickCandidate } from "@/components/PickBySearch";
import { SegmentedControl } from "@/components/SegmentedControl";
import { ServiceChips } from "@/components/ServiceChips";
import { InlineLink, PlainTable, RefusalStrip } from "@/components/Surfaces";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { COMMON_AREA_KINDS, UNITS_ROUTE, useRegional } from "./meteringShared";
import type { RegionalProps } from "./meteringShared";
import { premisesOwnerAccount } from "./premisesOwnerContract";
import { planPickerOptions, UNIT_TYPES } from "./UnitsListPage";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** `?premises=` — the building carried in from wherever the clerk pressed. */
export const PREMISES_PARAM = "premises";
export const ADD_UNITS_STEP_PARAM = "step";
export const ADD_UNITS_STEP_COUNT = 2;

/** One floor unless somebody says otherwise. */
export const PLAIN_FLOORS = "1";

export type AddUnitsKind = "units" | "common";

export interface AddUnitsForm {
  premises_id: string;
  /** `CR-176` rule (5) — *Units* or *A common area*, chosen at the top. */
  kind: AddUnitsKind;
  /** In *Names & numbers*: a floors-times-units multiplier, meaningful only
   *  beside the `{floor}` token. */
  floors: string;
  /** *How many*. Starts at `"1"` — the drawing's and the clerk's default, and
   *  the fix for *Units to create: 0* beside a box that read empty. */
  units_per_floor: string;
  /** *Start numbering at*, as the clerk typed it. Read only once
   *  `seq_start_touched`; until then the screen uses the SERVER's next free
   *  number (`CR-176` rule 1). */
  seq_start: string;
  /** The clerk has typed a start. A box they emptied stays empty on screen
   *  (and the run then starts at the next free number) rather than refilling
   *  under their cursor. */
  seq_start_touched: boolean;
  /** `""` means the catalogue's default pattern (`Unit {seq}` in English). */
  label_pattern: string;
  unit_no_pattern: string;
  /** *Unit numbers*: the utility's series, or *My own pattern* (rule 6). */
  unit_no_source: "series" | "pattern";
  unit_type: string;
  /** *Floor* — free text; `""` is not recorded, a different fact from `"0"`. */
  floor_label: string;
  /** *Floor area (sq ft)* — one value onto every unit; `""` is not recorded. */
  square_feet: string;
  /** The common area's KIND — a `COMMON_AREA_KINDS` code, or `""`. */
  common_area: string;
  /** *Plan*: *When someone moves in* (`later`) or *Pick a plan now*. */
  plan_mode: "later" | "now";
  plan_id: string;
  plan_starts_mode: "on_create" | "chosen";
  plan_starts: string;
  /** `null` is *the clerk has not touched this*; the building's whole offer is
   *  then what the run takes (`resolvedUnitServices`). An array is the clerk's
   *  own answer, a deliberate empty one included. */
  services: string[] | null;
  custom_data?: CustomFieldValues;
  service_point_custom_data?: Record<string, CustomFieldValues>;
}

export function emptyAddUnitsForm(premisesId = ""): AddUnitsForm {
  return {
    premises_id: premisesId,
    kind: "units",
    floors: PLAIN_FLOORS,
    units_per_floor: "1",
    seq_start: "",
    seq_start_touched: false,
    label_pattern: "",
    unit_no_pattern: "",
    unit_no_source: "series",
    unit_type: "",
    floor_label: "",
    square_feet: "",
    common_area: "",
    plan_mode: "later",
    plan_id: "",
    plan_starts_mode: "on_create",
    plan_starts: "",
    services: null,
  };
}

/**
 * **What these units will take — `BR-MET-119` as amended, `CR-176` rule (3).**
 * The default is the WHOLE of the building's offer, resolved here rather than
 * stored so *nobody answered* and *the clerk chose these* stay apart; and it
 * NARROWS to the offer even for an explicit answer, so a tick left over from a
 * building the clerk changed away from never reaches the commit.
 */
export function resolvedUnitServices(
  chosen: readonly string[] | null,
  offer: readonly string[] | null,
  loaded: boolean,
): string[] | null {
  if (!loaded) {
    return chosen === null ? null : [...chosen];
  }
  const available = offer ?? [];
  if (chosen === null) {
    return [...available];
  }
  return available.filter((code) => chosen.includes(code));
}

/** A whole number ≥ 1, or `null`. */
function positive(raw: string): number | null {
  const value = Number(raw.trim());
  return Number.isInteger(value) && value >= 1 ? value : null;
}

/**
 * **THE ONE COUNT (`CR-176` rule 2).** *Creates*, *These units*, Review and the
 * button all read this. A common area is one row whatever the count box held.
 */
export function addUnitsTotal(form: AddUnitsForm): number {
  if (form.kind === "common") {
    return 1;
  }
  const floors = positive(form.floors);
  const perFloor = positive(form.units_per_floor);
  return floors === null || perFloor === null ? 0 : floors * perFloor;
}

/** `{seq}` / `{seq:00}` / `{floor}` — the server's grammar (`BR-MET-031`). */
const TOKEN_RE = /\{(seq|floor)(?::(0+))?\}/g;

export function renderTokens(pattern: string, floor: number, seq: number): string {
  return pattern.replace(TOKEN_RE, (_whole, name: string, pad: string | undefined) => {
    const value = String(name === "floor" ? floor : seq);
    return pad === undefined ? value : value.padStart(pad.length, "0");
  });
}

/** The labels (or own-pattern numbers) a run makes, in the server's order. */
export function runValues(pattern: string, floors: number, perFloor: number, start: number): string[] {
  const out: string[] = [];
  for (let floor = 1; floor <= floors; floor += 1) {
    for (let seq = start; seq < start + perFloor; seq += 1) {
      out.push(renderTokens(pattern, floor, seq));
    }
  }
  return out;
}

/** `Unit 2 to Unit 4`, `Unit 2`, or `—`. */
export function rangeText(values: readonly string[], t: Translator): string {
  if (values.length === 0) return "—";
  if (values.length === 1) return values[0];
  return t("metering.addUnits.review.numbersRange", { first: values[0], last: values[values.length - 1] });
}

/** The service-point answers for the services these units actually take. */
function pointAnswers(form: AddUnitsForm): Record<string, CustomFieldValues> | undefined {
  const taken = form.services ?? [];
  const out = Object.fromEntries(
    Object.entries(form.service_point_custom_data ?? {}).filter(
      ([code, answers]) => Object.keys(answers).length > 0 && taken.includes(code),
    ),
  );
  return Object.keys(out).length === 0 ? undefined : out;
}

/**
 * The staged/committed payload. ONE builder for BOTH calls — the commit
 * re-stages the identical body, so two builders could drift and the review
 * would then be a review of something else.
 *
 * `form` must already carry the RESOLVED start, pattern and services (the
 * wizard's `resolvedForm`).
 */
export function addUnitsRequest(form: AddUnitsForm, commonAreaLabel?: string): ImportRequest {
  // A common area is one unit with the FLAG (`BR-MET-101`) and the chosen name
  // as its label; the count is one and the label grammar does not apply.
  const asCommonArea = form.kind === "common" && commonAreaLabel !== undefined;
  return {
    kind: "units_pattern",
    pattern: {
      premises_id: form.premises_id,
      floors: asCommonArea ? 1 : Number(form.floors),
      units_per_floor: asCommonArea ? 1 : Number(form.units_per_floor),
      seq_start: asCommonArea ? 1 : Number(form.seq_start || "1"),
      label_pattern: asCommonArea ? commonAreaLabel : form.label_pattern,
      unit_no_pattern:
        form.unit_no_source !== "pattern" || form.unit_no_pattern === "" ? undefined : form.unit_no_pattern,
      unit_type: asCommonArea ? "common_area" : form.unit_type === "" ? undefined : form.unit_type,
      is_common_area: asCommonArea ? true : undefined,
      // Absent rather than empty: `""` would be a floor label that is the
      // empty string, which no screen can draw as an absence.
      floor_label: asCommonArea || form.floor_label === "" ? undefined : form.floor_label,
      square_feet: asCommonArea || form.square_feet === "" ? undefined : Number(form.square_feet),
      // ⚠ `null` stays ABSENT so the server inherits the address's offer; an
      // array — a deliberate empty one included — is the clerk's answer
      // (`DEF-MET-6796`). `services ?? []` here would post *nothing* on every
      // run the clerk never touched.
      services: form.services === null ? undefined : form.services,
      custom_data: Object.keys(form.custom_data ?? {}).length === 0 ? undefined : form.custom_data,
      service_point_custom_data: pointAnswers(form),
      plan:
        form.plan_mode !== "now" || form.plan_id === ""
          ? undefined
          : {
              plan_id: form.plan_id,
              // Absent is *the day each unit is created* — `_apply_unit_plan`
              // defaults to the tenant's today, so no second idea of today.
              effective_from:
                form.plan_starts_mode === "chosen" && form.plan_starts !== "" ? form.plan_starts : undefined,
            },
    },
    options: {
      // All or none: a clerk who has just READ three labels gets three or none.
      skip_errors: false,
      merge_duplicates: false,
    },
  };
}

/** One review row per unit: the SERVER's label, the preview's number. */
export interface ReviewRow {
  label: string;
  unitNo: string | null;
  errors: { column?: string; code?: string }[];
}

export function reviewRows(stage: ImportStage | undefined, numbers: string[]): ReviewRow[] {
  return (stage?.rows ?? []).map((row, index) => ({
    label: String((row.data as Record<string, unknown>)?.label ?? ""),
    // Past the five the preview prints the number is NOT KNOWN here — `null`,
    // never counted on from the last one (the allocator is the server's).
    unitNo: numbers[index] ?? null,
    errors: (row.errors ?? []) as { column?: string; code?: string }[],
  }));
}

/** `101 Silver Creek Rd · P-00001 · Silver Creek, TX 78611` — the address
 *  leads and the number follows it (frame §3). */
export function buildingLine(lends: PremisesLends | undefined): string {
  if (lends === undefined) {
    return "";
  }
  const p = lends.premises;
  const place = [[p.city, p.state].filter((part) => part).join(", "), p.postal_code]
    .filter((part) => part)
    .join(" ");
  return [p.address_line, p.premise_no, place].filter((part) => part).join(" · ");
}

/** A premises row as the building search lists it. Never its id on screen. */
export function buildingCandidate(row: Pick<PremisesRow, "id" | "address_line" | "premise_no" | "city" | "state" | "postal_code">): PickCandidate {
  const place = [[row.city, row.state].filter((part) => part).join(", "), row.postal_code]
    .filter((part) => part)
    .join(" ");
  return {
    id: row.id,
    title: row.address_line ?? "",
    meta: [row.premise_no, place].filter((part) => part).join(" · "),
  };
}

/** `RT-001 · CY-001`, several joined with ` / `, or `""`. */
function routeText(lends: PremisesLends | undefined): string {
  return (lends?.routes ?? [])
    .map((route) => [route.code, route.cycle_code].filter((part) => part !== null && part !== "").join(" · "))
    .join(" / ");
}

/** The services a unit takes, in the clerk's words, or `—`. */
function servicesText(codes: readonly string[] | null, t: Translator): string {
  return codes === null || codes.length === 0
    ? "—"
    : codes.map((code) => t(`rating.service.${code}`, { defaultValue: code })).join(" · ");
}

/**
 * Three columns, then the rail across both, the step and its footer on the
 * left and *These units* on the right — the device the Discounts redesign
 * lays its frame out with (`DISCOUNT_FORM_LAYOUT`), by the `data-wizard` hooks
 * the frame already renders. The frame's own refusal line is hidden: every
 * refusal here is said on its field.
 */
const ADD_UNITS_LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_320px] gap-x-5 items-start " +
  "[&_[data-wizard=frame]]:contents " +
  "[&_[data-wizard=rail]]:col-span-2 [&_[data-wizard=rail]]:row-start-1 " +
  "[&_[data-wizard=rail]]:mb-5 [&_[data-wizard=rail]]:border [&_[data-wizard=rail]]:bg-surface " +
  "[&_[data-wizard=content]]:col-start-1 [&_[data-wizard=content]]:row-start-2 " +
  "[&_[data-wizard=content]]:mb-0 " +
  "[&_[data-wizard=actions]]:col-start-1 [&_[data-wizard=actions]]:row-start-3 " +
  "[&_[data-wizard=actions]]:mt-5 [&_[data-wizard=actions]]:border-t " +
  "[&_[data-wizard=actions]]:border-divider [&_[data-wizard=actions]]:pt-4 " +
  "[&_[data-wizard=blocked]]:hidden";

/** A form section: a box with its heading inside. */
const SECTION_HEADING = "m-0 mb-4 font-heading text-h4";
/** Three fields in a row, as the PO ruled (*"all 3 in 1 line"*, *"2 or 3 rows"*). */
const TRIO = "grid grid-cols-3 gap-x-4 gap-y-5";

// ── The screen ─────────────────────────────────────────────────────────────

export interface AddUnitsWizardProps extends RegionalProps {
  client?: ApiClient;
}

export function AddUnitsWizard(props: AddUnitsWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);
  const [searchParams, setSearchParams] = useSearchParams();

  const [form, setForm] = useState<AddUnitsForm>(() =>
    emptyAddUnitsForm(searchParams.get(PREMISES_PARAM) ?? ""),
  );
  const [stage, setStage] = useState<ImportStage | undefined>(undefined);
  const [refusal, setRefusal] = useState<string | null>(null);
  // Field-level marks: the client's own (after Continue) and the server's.
  const [marks, setMarks] = useState<Record<string, string>>({});
  const [customErrors, setCustomErrors] = useState<Record<string, string>>({});

  const stepRaw = Number(searchParams.get(ADD_UNITS_STEP_PARAM) ?? "1");
  const step = Number.isInteger(stepRaw) ? Math.min(Math.max(1, stepRaw), ADD_UNITS_STEP_COUNT) : 1;
  function setStep(next: WizardNavState): void {
    const params = new URLSearchParams(searchParams);
    params.set(ADD_UNITS_STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  const defaultPattern = t("metering.addUnits.labelPatternDefault");
  const pattern = form.label_pattern.trim() === "" ? defaultPattern : form.label_pattern.trim();
  const floors = positive(form.floors) ?? 1;
  const perFloor = positive(form.units_per_floor);
  const isCommon = form.kind === "common";
  const total = addUnitsTotal(form);
  const commonAreaLabel = form.common_area === "" ? null : t(`metering.commonAreas.kind.${form.common_area}`);

  const lendsQuery = useQuery({
    queryKey: ["premises", "lends", form.premises_id],
    queryFn: () => getPremisesLends(form.premises_id, client),
    enabled: form.premises_id !== "",
  });
  const lends = lendsQuery.data;

  // `CR-176` rule (1). Asked with the clerk's start only once they typed one;
  // before that the run starts at the answer, which by construction clashes
  // with nothing.
  const typedStart = form.seq_start_touched ? positive(form.seq_start) : null;
  const nextFreeQuery = useQuery({
    queryKey: ["premises", "units-next-free", form.premises_id, perFloor, floors, pattern, typedStart],
    queryFn: () =>
      getPremisesUnitsNextFree(
        form.premises_id,
        { count: perFloor ?? 1, floors, labelPattern: pattern, start: typedStart ?? undefined },
        client,
      ),
    enabled: form.premises_id !== "" && !isCommon && perFloor !== null,
  });
  const nextFree = nextFreeQuery.data?.next_free ?? null;
  const takenNow = typedStart === null ? [] : (nextFreeQuery.data?.taken ?? []);
  const start = typedStart ?? nextFree ?? 1;

  const plansQuery = useQuery({
    queryKey: ["plans", "unit-plan-picker"],
    queryFn: () => getUnitPlanOptions({ per: 200 }, client),
  });
  const planOptions = planPickerOptions(plansQuery.data?.results);
  const planLabel =
    form.plan_mode === "now" ? (planOptions.find((option) => option.value === form.plan_id)?.label ?? null) : null;

  // The numbers, asked for the run's size; asking reserves nothing (BR-MET-1165).
  const numbersQuery = useQuery({
    queryKey: ["units", "number-preview", total],
    queryFn: () => getUnitNumberPreview(total, client),
    enabled: total > 0 && form.unit_no_source === "series",
  });

  const services = resolvedUnitServices(form.services, lends?.premises.services_available ?? null, lends !== undefined);
  const resolvedForm: AddUnitsForm = { ...form, services, seq_start: String(start), label_pattern: pattern };

  // What this run makes, before Continue: client-rendered from the same
  // grammar the server uses. Review replaces the labels with the server's.
  const labels = isCommon
    ? commonAreaLabel === null
      ? []
      : [commonAreaLabel]
    : perFloor === null
      ? []
      : runValues(pattern, floors, perFloor, start);
  const unitNumbers =
    form.unit_no_source === "pattern" && form.unit_no_pattern.trim() !== ""
      ? isCommon
        ? [renderTokens(form.unit_no_pattern.trim(), 1, 1)]
        : perFloor === null
          ? []
          : runValues(form.unit_no_pattern.trim(), floors, perFloor, start)
      : numbersQuery.data === undefined || numbersQuery.data.series_missing
        ? []
        : [numbersQuery.data.numbers[0], numbersQuery.data.last ?? numbersQuery.data.numbers[0]].filter(
            (value, index, all): value is string => value !== undefined && all.indexOf(value) === index,
          );

  const typeText = isCommon
    ? t("metering.units.type.common_area")
    : form.unit_type === ""
      ? "—"
      : t(`metering.units.type.${form.unit_type}`, { defaultValue: form.unit_type });
  const planText = form.plan_mode === "now" ? (planLabel ?? "—") : t("metering.addUnits.plan.later");
  const startsText =
    form.plan_starts_mode === "chosen" && form.plan_starts !== ""
      ? formatDate(form.plan_starts, timeZone, dateFormat)
      : t("metering.addUnits.startsCreated");

  const stageMutation = useMutation({
    mutationFn: () => stagePremisesImport(addUnitsRequest(resolvedForm, commonAreaLabel ?? undefined), client),
    onMutate: () => setCustomErrors({}),
    onSuccess: (result) => {
      setStage(result);
      setRefusal(null);
    },
    onError: (error: unknown) => {
      setStage(undefined);
      const fieldMarks: Record<string, string> = {};
      if (isApiError(error)) {
        for (const fe of error.fieldErrors ?? []) {
          if (fe.field === "seq_start" || fe.field === "services") {
            fieldMarks[fe.field] = apiErrorText({ ...error, fieldErrors: [] }, translate);
          }
        }
        setCustomErrors(customFieldErrors(error.fieldErrors, translate));
      }
      setMarks(fieldMarks);
      setRefusal(Object.keys(fieldMarks).length > 0 ? null : apiErrorText(error, translate));
    },
  });

  async function commit(): Promise<WizardCommitOutcome> {
    try {
      const result = await commitPremisesImport(addUnitsRequest(resolvedForm, commonAreaLabel ?? undefined), client);
      const created = result.summary?.created ?? 0;
      if (created === 0) {
        return { ok: false, reason: t("metering.addUnits.commit.nothingCreated") };
      }
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  /** Continue's client-side checks, each said on its own field. */
  function detailsMarks(): Record<string, string> {
    const out: Record<string, string> = {};
    if (form.premises_id === "") {
      out.premises_search = t("metering.addUnits.error.pickBuilding");
    }
    if (isCommon) {
      if (form.common_area === "") out.common_area = t("metering.addUnits.error.commonArea");
    } else {
      if (perFloor === null) out.units_per_floor = t("metering.addUnits.error.howMany");
    }
    return out;
  }

  const rows = reviewRows(stage, form.unit_no_source === "series" ? (numbersQuery.data?.numbers ?? []) : unitNumbers);
  const street = lends?.premises.address_line ?? "";

  const summary = (
    <TheseUnitsCard
      kind={form.kind}
      total={total}
      building={lends}
      labels={step === 2 && rows.length > 0 ? rows.map((row) => row.label) : labels}
      unitNumbers={unitNumbers}
      typeText={typeText}
      services={lends === undefined ? null : services}
      planText={planText}
      t={translate}
    />
  );

  const steps: WizardStep[] = [
    {
      id: "details",
      label: t("metering.addUnits.step.building"),
      content: (
        <div className="flex flex-col gap-5">
          <Panel as="section" aria-labelledby="add-units-building">
            <h2 id="add-units-building" className={SECTION_HEADING}>
              {t("metering.addUnits.building.premise")}
            </h2>
            <PremiseSearch
              premisesId={form.premises_id}
              lends={lends}
              client={client}
              t={translate}
              onUse={(id) => {
                setForm({ ...form, premises_id: id, services: null, seq_start: "", seq_start_touched: false });
                setMarks({});
              }}
              onChange={() => setForm({ ...form, premises_id: "", services: null, seq_start: "", seq_start_touched: false })}
              onActivity={() =>
                setMarks((was) => {
                  if (!("premises_search" in was)) return was;
                  const next = { ...was };
                  delete next.premises_search;
                  return next;
                })
              }
            />
            {lends !== undefined && (
              <div className="mt-5">
                <CheckDropdown
                  id="services"
                  mode="every"
                  label={t("metering.units.col.services")}
                  allLabel={t("metering.addUnits.services.all")}
                  placeholder={t("metering.addUnits.services.none")}
                  options={(lends.premises.services_available ?? []).map((code) => ({
                    value: code,
                    label: t(`rating.service.${code}`, { defaultValue: code }),
                  }))}
                  selected={services ?? []}
                  onChange={(next) => setForm({ ...form, services: next })}
                  help={t("metering.addUnits.services.help")}
                />
              </div>
            )}
          </Panel>

          <Panel as="section" aria-labelledby="add-units-what">
            <h2 id="add-units-what" className={SECTION_HEADING}>
              {t("metering.addUnits.whatToAdd")}
            </h2>
            <SegmentedControl
              purpose="choice"
              label={t("metering.addUnits.whatToAdd")}
              segments={[
                { id: "units", label: t("metering.addUnits.kind.units") },
                { id: "common", label: t("metering.addUnits.kind.common") },
              ]}
              active={form.kind}
              onSelect={(id: string) => {
                setForm({ ...form, kind: id === "common" ? "common" : "units" });
                setMarks({});
              }}
            />
            <div className="mt-5">
              {isCommon ? (
                <div className="max-w-sm">
                  <SelectField
                    id="common_area"
                    label={t("metering.units.field.commonArea")}
                    required
                    value={form.common_area}
                    placeholder={t("metering.addUnits.commonArea.choose")}
                    options={COMMON_AREA_KINDS.map((code) => ({
                      value: code,
                      label: t(`metering.commonAreas.kind.${code}`),
                    }))}
                    onChange={(value) => setForm({ ...form, common_area: value })}
                    help={t("metering.addUnits.commonArea.billed")}
                  />
                </div>
              ) : (
                <UnitsFields
                  form={form}
                  onChange={(patch) => {
                    setForm({ ...form, ...patch });
                    if ("seq_start" in patch || "units_per_floor" in patch) {
                      setMarks((was) => {
                        const next = { ...was };
                        delete next.seq_start;
                        if ("units_per_floor" in patch) delete next.units_per_floor;
                        return next;
                      });
                    }
                  }}
                  start={start}
                  nextFree={form.premises_id === "" ? null : nextFree}
                  taken={takenNow}
                  labels={labels}
                  unitNumbers={unitNumbers}
                  t={translate}
                />
              )}
            </div>
          </Panel>

          <NamesAndNumbers form={form} pattern={pattern} defaultPattern={defaultPattern} onChange={(patch) => setForm({ ...form, ...patch })} t={translate} />

          <PlanAndStart
            form={form}
            planOptions={planOptions}
            planLabel={planLabel}
            dateFormat={dateFormat}
            timeZone={timeZone}
            onChange={(patch) => setForm({ ...form, ...patch })}
            t={translate}
          />

          {/* `CR-161-BRC10` W3 — the tenant's own unit fields, then one block
              per service the units take. Nothing at all for a tenant with none. */}
          <FieldErrorsScope errors={customErrors}>
            <CustomFieldsInput
              entity="units"
              screen="UNIT_ADD"
              values={form.custom_data ?? {}}
              onChange={(custom_data) => setForm({ ...form, custom_data })}
              client={client}
            />
            {(services ?? []).map((code) => (
              <CustomFieldsInput
                entity="service_points"
                screen="UNIT_ADD"
                key={code}
                heading={t(`rating.service.${code}`, { defaultValue: code })}
                values={form.service_point_custom_data?.[code] ?? {}}
                onChange={(answers) =>
                  setForm({
                    ...form,
                    service_point_custom_data: { ...(form.service_point_custom_data ?? {}), [code]: answers },
                  })
                }
                client={client}
              />
            ))}
          </FieldErrorsScope>
          {refusal !== null && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
        </div>
      ),
      validate: async () => {
        const local = detailsMarks();
        if (takenNow.length > 0 && !isCommon) {
          local.seq_start = t("metering.addUnits.startAtTaken", { count: takenNow.length, labels: takenNow.join(", ") });
        }
        setMarks(local);
        if (Object.keys(local).length > 0) {
          return t("metering.addUnits.error.fixFirst");
        }
        const staged = await stageMutation.mutateAsync().catch(() => undefined);
        return staged === undefined ? t("metering.addUnits.refuse.staged") : true;
      },
    },
    {
      id: "review",
      label: t("metering.addUnits.step.review"),
      content: (
        <div className="flex flex-col gap-5">
          <ReviewStep
            form={form}
            lends={lends}
            rows={rows}
            total={total}
            start={start}
            services={services}
            unitNumbers={unitNumbers}
            typeText={typeText}
            planText={planText}
            startsText={startsText}
            commonAreaLabel={commonAreaLabel}
            seriesMissing={numbersQuery.data?.series_missing === true}
            onEdit={() => setStep({ step: 1, reached: 2 })}
            t={translate}
          />
          <CustomFieldsAnswers entity="units" screen="UNIT_ADD" values={form.custom_data ?? {}} client={client} />
          {(services ?? []).map((code) => (
            <CustomFieldsAnswers
              key={code}
              entity="service_points"
              screen="UNIT_ADD"
              heading={t(`rating.service.${code}`, { defaultValue: code })}
              values={form.service_point_custom_data?.[code] ?? {}}
              client={client}
            />
          ))}
          {street !== "" && (
            <p className="m-0 bg-info-100 px-3 py-3 text-base text-info-700" data-add-units-outcome="">
              {isCommon
                ? t("metering.addUnits.review.createsCommon", { street })
                : t("metering.addUnits.review.creates", { count: total, street })}
            </p>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5" data-screen="add-units">
      <PageHeader
        title={t("metering.addUnits.title")}
        backTo={{ to: tenantPath(UNITS_ROUTE), label: t("metering.units.title") }}
      />
      <FieldErrorsScope errors={marks}>
        <div className={ADD_UNITS_LAYOUT} data-add-units-layout="">
          <WizardFrame
            steps={steps}
            nav={{ step, reached: step }}
            onNavChange={setStep}
            doneMark="tick"
            backAtStart
            cancel={
              step === 1
                ? { label: t("metering.addUnits.cancel"), onCancel: () => navigate(tenantPath(UNITS_ROUTE)) }
                : undefined
            }
            // `CR-176` rule (2) — the button says the one count.
            commitLabel={isCommon ? t("metering.addUnits.createCommon") : t("metering.addUnits.create", { count: total })}
            commitFailedTitle={t("metering.addUnits.commitFailed")}
            onCommit={commit}
            onCommitted={() => navigate(tenantPath(UNITS_ROUTE))}
          />
          <div className="col-start-2 row-start-2 row-span-2 self-start">{summary}</div>
        </div>
      </FieldErrorsScope>
    </div>
  );
}

// ── The building: search, look, use (`CR-176` rule 4) ──────────────────────

function PremiseSearch(props: {
  premisesId: string;
  lends: PremisesLends | undefined;
  client: ApiClient;
  t: Translator;
  onUse: (premisesId: string) => void;
  onChange: () => void;
  onActivity: () => void;
}) {
  const { t } = props;
  const chosen: PickCandidate | null =
    props.premisesId === ""
      ? null
      : props.lends === undefined
        ? { id: props.premisesId, title: "" }
        : buildingCandidate({ ...props.lends.premises });
  return (
    <PickBySearch
      id="premises_search"
      label={t("metering.units.col.premise")}
      required
      placeholder={t("metering.addUnits.building.placeholder")}
      findLabel={t("metering.addUnits.find")}
      noMatchLabel={t("metering.addUnits.building.noMatch")}
      search={async (q) => {
        const page = await getPremises({ q, per: 10 }, props.client);
        return (page.results ?? []).map(buildingCandidate);
      }}
      chosen={chosen}
      onUse={(candidate) => props.onUse(candidate.id)}
      onChange={props.onChange}
      onActivity={props.onActivity}
      renderCard={(candidate) => <PremiseFacts premisesId={candidate.id} client={props.client} t={t} />}
      useLabel={t("metering.addUnits.building.use")}
      selectedLabel={t("metering.addUnits.building.selected")}
      changeLabel={t("metering.addUnits.building.changeBuilding")}
    />
  );
}

/**
 * The building card's body — EVERY value labelled (`DEF-MET-10035`: a bare
 * *Not recorded* with no label). Type · Status · Units today · Route and cycle
 * · Owner · Services. The owner is the building's MASTER ACCOUNT
 * (`BR-MET-1181`), `—` when there is none. Its own query, shared by key with
 * the wizard's, so a building being LOOKED AT reads the same facts as the one
 * chosen.
 */
export function PremiseFacts(props: { premisesId: string; client: ApiClient; t: Translator }) {
  const { t } = props;
  const query = useQuery({
    queryKey: ["premises", "lends", props.premisesId],
    queryFn: () => getPremisesLends(props.premisesId, props.client),
  });
  const lends = query.data;
  if (lends === undefined) {
    return null;
  }
  return <PremiseFactsGrid lends={lends} t={t} />;
}

export function PremiseFactsGrid(props: { lends: PremisesLends; t: Translator }) {
  const { t, lends } = props;
  const p = lends.premises;
  const owner = premisesOwnerAccount(p);
  const route = routeText(lends);
  const unitsToday =
    lends.units_today === 0
      ? "0"
      : `${lends.units_today} · ${lends.unit_labels.join(", ")}${lends.unit_labels_truncated ? ", …" : ""}`;
  const facts: [string, string, ReactNode][] = [
    ["type", t("metering.premises.col.type"), p.premises_type_name ?? "—"],
    ["status", t("metering.premises.col.status"), t(`metering.premises.status.${p.status}`, { defaultValue: p.status })],
    ["units", t("metering.addUnits.lends.unitsToday"), unitsToday],
    ["route", t("metering.addUnits.lends.route"), route === "" ? "—" : route],
    ["owner", t("metering.premises.filter.owner"), owner === null ? "—" : (owner.name ?? owner.account_no)],
    [
      "services",
      t("metering.units.col.services"),
      (p.services_available ?? []).length === 0 ? "—" : <ServiceChips services={p.services_available} t={t} />,
    ],
  ];
  return (
    <dl className="m-0 grid grid-cols-2 gap-x-5 gap-y-3" data-building-facts="">
      {facts.map(([id, label, value]) => (
        <div key={id} data-building-fact={id}>
          <dt className="text-sm text-neutral-700">{label}</dt>
          <dd className="m-0 mt-0.5 font-semibold">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

// ── What to add · Units ──────────────────────────────────────────────────────

export function UnitsFields(props: {
  form: AddUnitsForm;
  onChange: (patch: Partial<AddUnitsForm>) => void;
  /** The start the run will use — typed, or the server's next free. */
  start: number;
  nextFree: number | null;
  /** Labels of THIS run already on file (only once the clerk typed a start). */
  taken: string[];
  labels: string[];
  unitNumbers: string[];
  t: Translator;
}) {
  const { t, form } = props;
  const takenText =
    props.taken.length === 0
      ? undefined
      : t("metering.addUnits.startAtTaken", { count: props.taken.length, labels: props.taken.join(", ") });
  return (
    <div className={TRIO}>
      <TextField
        id="units_per_floor"
        label={t("metering.addUnits.review.howMany")}
        required
        numeric
        value={form.units_per_floor}
        onChange={(value) => props.onChange({ units_per_floor: value })}
      />
      <div>
        <TextField
          id="seq_start"
          label={t("metering.addUnits.startAt")}
          numeric
          value={form.seq_start_touched ? form.seq_start : String(props.start)}
          onChange={(value) => props.onChange({ seq_start: value, seq_start_touched: true })}
          help={props.nextFree === null ? undefined : t("metering.addUnits.nextFree", { n: props.nextFree })}
          error={takenText}
        />
        {takenText !== undefined && props.nextFree !== null && (
          <InlineLink
            className="mt-1 font-semibold"
            data-use-next-free=""
            onClick={() => props.onChange({ seq_start: String(props.nextFree), seq_start_touched: true })}
          >
            {t("metering.addUnits.useStart", { n: props.nextFree })}
          </InlineLink>
        )}
      </div>
      <SelectField
        id="unit_type"
        label={t("metering.addUnits.unitType")}
        value={form.unit_type}
        placeholder={t("metering.addUnits.unitTypeAny")}
        options={UNIT_TYPES.map((code) => ({
          value: code,
          label: t(`metering.units.type.${code}`, { defaultValue: code }),
        }))}
        onChange={(value) => props.onChange({ unit_type: value })}
      />
      {/* `Floor` is FREE TEXT (decision log 2026-09-10): the column already
          holds `Ground`, `G`, `PH`, and a list would make them unselectable. */}
      <TextField
        id="floor_label"
        label={t("metering.addUnits.floor")}
        value={form.floor_label}
        placeholder={t("metering.addUnits.floorPlaceholder")}
        onChange={(value) => props.onChange({ floor_label: value })}
      />
      <TextField
        id="square_feet"
        label={t("metering.addUnits.floorAreaSqFt")}
        numeric
        value={form.square_feet}
        onChange={(value) => props.onChange({ square_feet: value })}
      />
      <div className="field" data-add-units-creates="">
        <p className="m-0 mb-1.5 text-base font-semibold">{t("metering.addUnits.creates")}</p>
        <div className="border border-divider bg-neutral-100 px-3 py-2">
          <p className="m-0 font-semibold">{rangeText(props.labels, t)}</p>
          <p className="m-0 text-sm text-neutral-700">{rangeText(props.unitNumbers, t)}</p>
        </div>
      </div>
    </div>
  );
}

// ── Names & numbers (rule 6) ────────────────────────────────────────────────

export function NamesAndNumbers(props: {
  form: AddUnitsForm;
  pattern: string;
  defaultPattern: string;
  onChange: (patch: Partial<AddUnitsForm>) => void;
  t: Translator;
}) {
  const { t, form } = props;
  const isCommon = form.kind === "common";
  const source =
    form.unit_no_source === "pattern" ? t("metering.addUnits.unitNumbersMine") : t("metering.addUnits.unitNumbersSeries");
  return (
    <Disclosure
      variant="panel"
      title={t("metering.addUnits.names.title")}
      value={isCommon ? source : `${source} · ${props.pattern}`}
    >
      <div className={TRIO}>
        {!isCommon && (
          <TextField
            id="floors"
            label={t("metering.addUnits.floors")}
            numeric
            value={form.floors}
            onChange={(value) => props.onChange({ floors: value })}
            help={t("metering.addUnits.floorsRepeat")}
          />
        )}
        {!isCommon && (
          <TextField
            id="label_pattern"
            label={t("metering.wizard.pattern.labelPattern")}
            value={form.label_pattern}
            placeholder={props.defaultPattern}
            onChange={(value) => props.onChange({ label_pattern: value })}
            help={t("metering.addUnits.tokens")}
          />
        )}
        <SelectField
          id="unit_no_source"
          label={t("metering.addUnits.unitNumbers")}
          value={form.unit_no_source}
          options={[
            { value: "series", label: t("metering.addUnits.unitNumbersSeries") },
            { value: "pattern", label: t("metering.addUnits.unitNumbersMine") },
          ]}
          onChange={(value) => props.onChange({ unit_no_source: value === "pattern" ? "pattern" : "series" })}
        />
      </div>
      {form.unit_no_source === "pattern" && (
        <div className="mt-5">
          <TextField
            id="unit_no_pattern"
            label={t("metering.addUnits.unitNoPattern")}
            value={form.unit_no_pattern}
            onChange={(value) => props.onChange({ unit_no_pattern: value })}
          />
        </div>
      )}
    </Disclosure>
  );
}

// ── Plan & start (BR-MET-007; all plans with a search, PO 2026-09-10) ────────

export function PlanAndStart(props: {
  form: AddUnitsForm;
  planOptions: { value: string; label: string }[];
  planLabel: string | null;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  onChange: (patch: Partial<AddUnitsForm>) => void;
  t: Translator;
}) {
  const { t, form } = props;
  const planState = form.plan_mode === "now" ? (props.planLabel ?? "—") : t("metering.addUnits.planStart.later");
  const startState =
    form.plan_starts_mode === "chosen" && form.plan_starts !== ""
      ? t("metering.addUnits.planStart.fromDate", { date: formatDate(form.plan_starts, props.timeZone, props.dateFormat) })
      : t("metering.addUnits.planStart.fromCreation");
  return (
    <Disclosure variant="panel" title={t("metering.addUnits.planStart.title")} value={`${planState} · ${startState}`}>
      <div className="flex flex-col gap-5">
        <div className="field">
          <p className="m-0 mb-1.5 text-base font-semibold">{t("metering.units.col.plan")}</p>
          <SegmentedControl
            purpose="choice"
            label={t("metering.units.col.plan")}
            segments={[
              { id: "later", label: t("metering.addUnits.plan.later") },
              { id: "now", label: t("metering.addUnits.plan.now") },
            ]}
            active={form.plan_mode}
            onSelect={(id: string) =>
              props.onChange(
                id === "now"
                  ? { plan_mode: "now" }
                  : { plan_mode: "later", plan_id: "", plan_starts_mode: "on_create", plan_starts: "" },
              )
            }
          />
        </div>
        {form.plan_mode === "now" && (
          <>
            <SearchSelectField
              id="plan_id"
              label={t("metering.units.col.plan")}
              value={form.plan_id}
              placeholder={t("metering.addUnits.plan.placeholder")}
              options={props.planOptions}
              onChange={(value) => props.onChange({ plan_id: value })}
              help={t("metering.addUnits.plan.noPlan")}
            />
            <div className="grid grid-cols-2 gap-x-4">
              <SelectField
                id="plan_starts_mode"
                label={t("metering.addUnits.starts")}
                value={form.plan_starts_mode}
                options={[
                  { value: "on_create", label: t("metering.addUnits.startsCreated") },
                  { value: "chosen", label: t("metering.addUnits.startsChosen") },
                ]}
                onChange={(value) =>
                  props.onChange({
                    plan_starts_mode: value === "chosen" ? "chosen" : "on_create",
                    plan_starts: value === "chosen" ? form.plan_starts : "",
                  })
                }
              />
              {form.plan_starts_mode === "chosen" && (
                <DatePickerField
                  id="plan_starts"
                  label={t("metering.addUnits.startsDate")}
                  value={form.plan_starts}
                  dateFormat={props.dateFormat}
                  onChange={(value) => props.onChange({ plan_starts: value })}
                />
              )}
            </div>
          </>
        )}
      </div>
    </Disclosure>
  );
}

// ── These units (the right-hand card) ──────────────────────────────────────

export function TheseUnitsCard(props: {
  kind: AddUnitsKind;
  total: number;
  building: PremisesLends | undefined;
  labels: string[];
  unitNumbers: string[];
  typeText: string;
  services: string[] | null;
  planText: string;
  t: Translator;
}) {
  const { t } = props;
  const route = routeText(props.building);
  const facts: [string, string, string][] = [
    ["labels", t("metering.addUnits.summary.labels"), rangeText(props.labels, t)],
    ["numbers", t("metering.addUnits.unitNumbers"), rangeText(props.unitNumbers, t)],
    ["type", t("metering.units.col.type"), props.typeText],
    ["services", t("metering.units.col.services"), servicesText(props.services, t)],
    ["plan", t("metering.units.col.plan"), props.planText],
    ["route", t("metering.premises.field.route"), route === "" ? "—" : route],
  ];
  return (
    <Panel as="aside" aria-label={t("metering.addUnits.summary.kicker")} data-these-units="">
      <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {t("metering.addUnits.summary.kicker")}
      </p>
      <p className="m-0 mt-3 font-heading text-metric-lg font-semibold" data-these-units-count="">
        {props.kind === "common" ? t("metering.addUnits.summary.commonArea") : t("metering.addUnits.summary.units", { count: props.total })}
      </p>
      <p className="m-0 mt-2 text-lead text-neutral-700">
        {props.building === undefined
          ? t("metering.addUnits.summary.noBuilding")
          : [props.building.premises.address_line, props.building.premises.premise_no].filter((part) => part).join(" · ")}
      </p>
      <dl className="m-0 mt-4 flex flex-col gap-2 border-t border-divider pt-4">
        {facts.map(([id, label, value]) => (
          <div key={id} className="flex items-baseline justify-between gap-3 text-base" data-these-units-fact={id}>
            <dt className="text-neutral-700">{label}</dt>
            <dd className="m-0 text-right font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

// ── Step 2 · Review ─────────────────────────────────────────────────────────

/** Exported for the conformance suite: step 2's rows come from a staging POST
 *  held in component state, so only rendering the step directly lets its
 *  groups and columns be read. */
export function ReviewStep(props: {
  form: AddUnitsForm;
  lends: PremisesLends | undefined;
  rows: ReviewRow[];
  total: number;
  start: number;
  services: string[] | null;
  unitNumbers: string[];
  typeText: string;
  planText: string;
  startsText: string;
  commonAreaLabel: string | null;
  seriesMissing: boolean;
  onEdit: () => void;
  t: Translator;
}) {
  const { t, form } = props;
  const isCommon = form.kind === "common";
  const dash = (text: string) => (text === "" ? "—" : text);
  const labels = props.rows.map((row) => row.label);
  const numbers = props.rows.map((row) => row.unitNo).filter((n): n is string => n !== null);
  const groups: [string, [string, string][]][] = [
    [
      t("metering.addUnits.review.building"),
      [
        [t("metering.addUnits.review.building"), dash(buildingLine(props.lends))],
        [t("metering.addUnits.lends.unitsToday"), props.lends === undefined ? "—" : String(props.lends.units_today)],
        [t("metering.addUnits.lends.route"), dash(routeText(props.lends))],
        [t("metering.units.col.services"), servicesText(props.services, t)],
      ],
    ],
    isCommon
      ? [
          t("metering.units.field.commonArea"),
          [
            [t("metering.units.field.commonArea"), props.commonAreaLabel ?? "—"],
            [t("metering.addUnits.review.billedTo"), t("metering.addUnits.review.theOwner")],
          ],
        ]
      : [
          t("metering.units.title"),
          [
            [t("metering.addUnits.review.howMany"), t("metering.addUnits.review.howManyValue", { count: props.total, start: props.start })],
            [t("metering.addUnits.unitType"), props.typeText],
            [t("metering.addUnits.floor"), dash(form.floor_label)],
            [
              t("metering.units.field.floorArea"),
              form.square_feet === "" ? "—" : t("metering.units.sqFt", { value: Number(form.square_feet).toLocaleString() }),
            ],
          ],
        ],
    [
      t("metering.addUnits.names.title"),
      [
        [t("metering.addUnits.summary.labels"), rangeText(labels, t)],
        [t("metering.addUnits.unitNumbers"), rangeText(numbers.length > 0 ? numbers : props.unitNumbers, t)],
      ],
    ],
    [
      t("metering.addUnits.planStart.title"),
      [
        [t("metering.units.col.plan"), props.planText],
        [t("metering.addUnits.starts"), props.startsText],
      ],
    ],
  ];
  return (
    <>
      <Panel as="section" aria-labelledby="add-units-check">
        <h2 id="add-units-check" className={SECTION_HEADING}>
          {t("metering.addUnits.review.check")}
        </h2>
        {props.seriesMissing && <RefusalStrip role="alert">{t("metering.addUnits.review.noSeries")}</RefusalStrip>}
        <div className="border border-divider">
          <PlainTable>
            <tbody>
              {groups.map(([group, rows]) => [
                <tr key={`g-${group}`} data-review-group={group}>
                  <th
                    colSpan={2}
                    scope="colgroup"
                    className="bg-neutral-200 text-left text-sm font-semibold uppercase tracking-kicker"
                  >
                    {group}
                  </th>
                </tr>,
                ...rows.map(([label, value]) => (
                  <tr key={`${group}-${label}`} data-review-row="">
                    <th scope="row" className="w-48 bg-neutral-100 font-normal text-neutral-700">
                      {label}
                    </th>
                    <td>
                      {value}{" "}
                      <InlineLink className="ml-2 text-sm" onClick={props.onEdit}>
                        {t("metering.action.edit")}
                      </InlineLink>
                    </td>
                  </tr>
                )),
              ])}
            </tbody>
          </PlainTable>
        </div>
      </Panel>

      <Panel as="section" aria-labelledby="add-units-will-create">
        <h2 id="add-units-will-create" className={SECTION_HEADING}>
          {t("metering.addUnits.review.willCreate")}
        </h2>
        <div className="max-h-96 overflow-y-auto border border-divider" data-consequence-panel="units">
          <PlainTable>
            <thead>
              <tr>
                <th>{t("metering.addUnits.review.col.label")}</th>
                <th>{t("metering.addUnits.review.col.unitNumber")}</th>
                <th>{t("metering.units.col.type")}</th>
                <th>{t("metering.units.col.plan")}</th>
                <th>{t("metering.addUnits.review.col.starts")}</th>
              </tr>
            </thead>
            <tbody>
              {props.rows.map((row, index) => (
                <tr key={`${row.label}-${index}`}>
                  <td>{row.label}</td>
                  <td className="font-mono">{row.unitNo ?? props.unitNumbers[index] ?? "—"}</td>
                  <td>{props.typeText}</td>
                  <td>{props.planText}</td>
                  <td>{t("metering.addUnits.review.startsVacant")}</td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      </Panel>
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-176-BRC10 (redesign) over CR-089 wave E
// generated: 2026-10-09 by the ADD-UNITS lane (CR-176-BRC10)
// checklist: A✔ B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// exceptions: the staging call is `POST /premises/imports`, the v1 stateless
//   contract — the commit sends the identical body a second time, which is what
//   makes "nothing is written until the press" literally true · the building
//   search placeholder keeps its PO-ruled words (`DEF-MET-4804`) over the
//   drawing's · *Starts* shows only under *Pick a plan now*, because it is the
//   plan's start and a date with no plan would be a control with no effect
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
