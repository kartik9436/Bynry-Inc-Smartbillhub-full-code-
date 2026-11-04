// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 · US-TEN-010 · US-TEN-011 (EP-TEN-07 §Stories) · US-MET-011 (S64's field law)
//           Screens: S8 (Reference data), S63 (Holiday calendar), S64, S66, S69, S70, S71 (rule cards)
//           AMENDED 2026-08-15 (tenant custom-fields lane): US-TEN-014 (EP-TEN-09 — the "custom" card body routes to CustomFieldsView
//           inside the SAME SettingsFrame, BR-SHL-035)
// Rules:    BR-SHL-035 (ONE shell for EVERY Reference-data item — card grid → management view in the same
//           frame, same "← Reference data" return, same header block, same save/confirm/toast, same audit
//           line; a rule page is a card whose view is a FORM, never a differently-shaped screen) ·
//           BR-TEN-029 (counts and Used-by computed LIVE) · BR-TEN-030 (codes unique per tenant,
//           case-insensitive; a code FREEZES once Used-by > 0) · BR-TEN-031 (the OWNING module validates
//           and writes) · BR-TEN-033 (the templates card is navigation only) · BR-TEN-034 (audit-lock:
//           delete blocked while Used-by > 0, deactivate always allowed — server-enforced) ·
//           BR-TEN-036/BR-TEN-037 (seeded + tenant-extensible; tax jurisdictions tenant-entered) ·
//           BR-TEN-039 · BR-TEN-041 (the rule cards) · BR-SHL-032 (confirms name the action) ·
//           BR-SHL-033 (date picker; long lists searchable) · BR-SHL-034 (dates via the shared formatter) ·
//           BR-SHL-010/011 (capability-row config; URL grammar) · IS-3 (server-side search, 300 ms, 2 chars)
//           AMENDED 2026-08-17 (CR-004 task A3): BR-TEN-078 — the OPT-IN Utility-service column. It renders
//           only for a card declaring `serviceScoped`; `null` is the VALUE "All services".
//           AMENDED 2026-09-02 (CR-065, DEF-3341): `uoms` is no longer the only one. BR-TEN-078 is
//           SUPERSEDED FOR `service_size_classes` ALONE by the PO's ruling of that day — *"in Setting a
//           capacity needs to tags to utility services"* — so two cards declare it and a THIRD still
//           needs a ruling of its own.
// ───────────────────────────────────────────────────────
// S8 → Reference data. BR-SHL-035 is the whole architecture of this file:
//
//   ReferenceDataTab
//     └── no ?list      → the CARD GRID (US-TEN-009)
//     └── ?list=<code>  → SettingsFrame  ← the ONE shell
//                           ├── kind "list"  → LookupListView   (US-TEN-010/011)
//                           ├── kind "rules" → a FORM body      (S63…S71)
//                           └── no endpoint  → the honest state
//
// There is exactly ONE list-management view and exactly ONE frame. A new card
// is a row in referenceDataConfig.ts — never a new screen — which is what makes
// "same UI structure" a property of the code rather than a promise.
//
// Everything destructive routes through the server's own verdict: `Used by` is
// recomputed live (BR-TEN-029), the 🔒 delete state is a hint, and a delete
// that races an attach still fails on the server's fresh count (US-TEN-011
// TC-5). This file never decides that a row is safe to delete.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  createHoliday,
  createLookupEntry,
  deleteHoliday,
  deleteLookupEntry,
  getHolidays,
  getLookupCards,
  getLookupEntries,
  getReferenceFixtureGap,
  getTenantServices,
  setLookupEntryActive,
  updateLookupEntry,
} from "@/api/endpoints";
import type { Holiday, LookupEntry } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { useRegional } from "@/features/metering/meteringShared";
import {
  DatePickerField,
  FormModal,
  SegmentedField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { Kicker, Note } from "@/components/TextBits";
import { useTenantPath } from "@/routing/tenantPath";

// CR-161-BRC10 W4 — aliased: this file now also imports the RENDERER from
// `@/components/CustomFields`, and the slot-pairing test reads every
// renderer tag in such a file as a placed screen.
import { CustomFieldsView as CustomFieldsManagement } from "./SettingsCustomFields";
import {
  CustomFieldsInput,
  customDataChanges,
  useCustomFieldColumns,
} from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import {
  REFERENCE_CARDS,
  REFERENCE_GROUP_ORDER,
  referenceCard,
  referenceCardViews,
} from "./referenceDataConfig";
import type { ReferenceCard, ReferenceCardView } from "./referenceDataConfig";
import { PushByPriorityToggle } from "./PushByPriorityToggle";
import { ReadValidationRulesView } from "./SettingsReadValidation";
import { ServiceCentresView } from "./SettingsServiceCentres";
import { RulePageView } from "./SettingsRulePageView";
import { rulePageForCard } from "./settingsRulePages";
import {
  ArrivesWith,
  RefusalNotice,
  SettingsDenied,
  SettingsFrame,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal, Translator } from "./settingsShared";
import { SizeClassCapacityField, capacityText, capacityUomFor, trimCapacity } from "./SizeClassCapacity";
import { PauseIcon, PencilIcon, PlayIcon, PowerIcon, TrashIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { Button } from "@/components/Button";

// ── Pure pieces ────────────────────────────────────────────────────────────

export const LIST_PARAM = "list";

/** BR-SHL-011's spirit: an unknown `?list` falls back to the grid, never errors. */
export function openCardFrom(params: URLSearchParams): ReferenceCard | null {
  const code = params.get(LIST_PARAM);
  return code === null ? null : referenceCard(code);
}

/**
 * BR-TEN-034: `Used by > 0` → hard delete is BLOCKED (deactivate instead).
 * The server re-checks at commit; this only decides which control is drawn.
 */
export function deleteIsLocked(entry: LookupEntry): boolean {
  return entry.used_by > 0 || entry.is_system;
}

/**
 * WHY a delete is locked — the two reasons are different sentences to a user.
 *
 * DEF-188: `is_system` was missing from `deleteIsLocked` entirely, so a
 * platform-seeded row offered an ENABLED Delete whose confirm said "Nothing
 * references it, so nothing else changes" — and the server then refused with
 * 409 `settings.lookups.system_row_not_deletable` (BR-TEN-036), a key that
 * existed in ZERO of the eleven catalogues, so the user read the raw key. The
 * screen promised the opposite of what happened and then failed in developer
 * language.
 *
 * `used_by` is checked FIRST because it is the more specific fact: a seeded row
 * that is ALSO referenced should say how many records reference it, which is
 * the sentence that tells the user what to do instead (deactivate).
 */
export function deleteLockReason(entry: LookupEntry): "referenced" | "system" | null {
  if (entry.used_by > 0) {
    return "referenced";
  }
  return entry.is_system ? "system" : null;
}

/**
 * BR-TEN-030: the code freezes once the entry is referenced. Name and detail
 * stay editable — renaming display text never rewrites history, because
 * documents stamp values at issue (BR-TEN-017).
 */
export function codeIsFrozen(entry: LookupEntry): boolean {
  return entry.used_by > 0;
}

/** Renders an owner-supplied detail cell without asserting a type it may not have. */
/**
 * DEF-TEN-8754 — the detail cell a person reads: the stored code turned into its
 * catalogue label when the card names a prefix, the code itself otherwise.
 */
export function detailLabel(
  entry: LookupEntry,
  column: { field: string; valueLabelKeyPrefix?: string },
  t: (key: string) => string,
): string {
  const raw = detailText(entry, column.field);
  if (column.valueLabelKeyPrefix === undefined || raw === "") {
    return raw;
  }
  const key = `${column.valueLabelKeyPrefix}${raw}`;
  const label = t(key);
  return label === key ? raw : label;
}

export function detailText(entry: LookupEntry, field: string | undefined): string {
  if (field === undefined) {
    return "";
  }
  const value = entry[field];
  return value === null || value === undefined ? "" : String(value);
}

/** BR-MET-066b — one row's Parent cell. Top-level rows read as an em dash;
 *  nothing here computes the hierarchy, it renders what the server serialized. */
export function parentText(entry: LookupEntry): string {
  const name = entry.parent_name;
  return typeof name === "string" && name !== "" ? name : "—";
}

/**
 * BR-MET-066c — one TOP-LEVEL row's *"3 sub-areas"*, r10 SET-04's own card
 * text, or `""` for a row that has none and for every non-hierarchical list.
 *
 * ⚠ **THIS TEXT ONCE LIVED INSIDE THE SEEDED NAMES AND WAS RIGHTLY DELETED.**
 * `reference_sweep`'s V1.0.0.1 entry records why: CR-010 cleaned *"the four
 * area names of r10's '· N sub-areas' counts, which claimed sub-areas no
 * tenant has."* A count baked into a NAME is an assertion nobody can check and
 * nothing can update. This one is the server's `sub_area_count`, computed per
 * row, so it says two when there are two and disappears when a tenant deletes
 * the last one.
 *
 * A SUB-AREA never shows a count even though its own is always 0: depth is
 * exactly two, so *"NE · 0 sub-areas"* would advertise a level that does not
 * exist (BR-MET-066b).
 */
export function subAreaCountText(
  entry: LookupEntry,
  translate: Translator,
  countKey = "settings.reference.subAreaCount",
): string {
  if (entry.is_sub_area === true) {
    return "";
  }
  const count = entry.sub_area_count;
  if (typeof count !== "number" || count <= 0) {
    return "";
  }
  return translate(countKey, { count });
}

/**
 * `DEF-TEN-4478` — which of a self-parented list's two levels a row already is,
 * so EDITING opens the chooser on the truth instead of on the default.
 *
 * `is_sub_area` is asked FIRST because it is the server's own verdict
 * (`row.parent_id is not None`), computed per row and always published on this
 * list. `parent_code` is the fallback for a payload that carried the code and
 * not the flag; both are read because a row that has a parent by either
 * account is a sub-area, and opening its editor on *Area* would invite a person
 * to save a promotion they never asked for.
 */
export function entryIsSubLevel(entry: LookupEntry | null): boolean {
  if (entry === null) {
    return false;
  }
  if (entry.is_sub_area === true) {
    return true;
  }
  return typeof entry.parent_code === "string" && entry.parent_code.trim() !== "";
}

/** BR-MET-066b — the rows offerable as a PARENT: top level, and never the row
 *  being edited. Both refusals exist on the server (`settings.areas.parent_self`,
 *  `settings.areas.parent_is_sub_area`); this keeps the dropdown from offering
 *  a choice that is certain to be refused, which is a control that lies. */
export function parentOptionsFor(
  entries: readonly LookupEntry[],
  editingId: string | null,
): LookupEntry[] {
  return entries.filter(
    (entry) => entry.is_sub_area !== true && entry.active && entry.id !== editingId,
  );
}

/**
 * CR-004 task A3 — one row's **Utility service** cell, for a card that declares
 * `serviceScoped`. ⚠ **TWO CARDS DECLARE IT SINCE 2026-09-02** — `uoms` and
 * `service_size_classes` — and this sentence said `uoms` alone for the rest of
 * that day (`DEF-3341`). `BR-TEN-078` is SUPERSEDED FOR THAT ONE LIST by the
 * PO's `CR-065` ruling and stands everywhere else; the declared set is pinned
 * in `SettingsReferenceData.test.tsx`, which is where a third card would have
 * to be argued for.
 *
 * THREE states, because `service` is optional AND nullable and those are two
 * different facts (see `LookupEntry` in endpoints.ts):
 *
 *   · `null`      → "All services". A UNIT EVERY SERVICE MAY USE — the value
 *                   the server stores, not a missing one. `month` is this.
 *   · `{id,code}` → that service, by name. The label comes from the shared
 *                   `rating.service.*` catalog because it carries all TEN
 *                   platform codes. ⚠ **THIS NOTE WAS THE DEFECT REPORT AND IT
 *                   SAT HERE BEING TRUE (DEF-763, filed 2026-08-26).** It read
 *                   "`metering.service.*` has six and would print `storm_water`
 *                   raw at a user" — correct, unfiled, and four other screens
 *                   were doing exactly that. A comment noticing a gap is a note,
 *                   never a plan (hard-won law 1). Every call site now reads
 *                   this namespace and `serviceNamespace.test.ts` keeps it one.
 *                   The code itself is the `defaultValue`, so a service the
 *                   catalog has never heard of degrades to its code rather than
 *                   to a key.
 *   · absent      → "" . The row published no scope at all, which on a card
 *                   that DECLARES one means the server sent something this
 *                   screen cannot describe. Writing "All services" there would
 *                   assert a permission nobody granted, so the cell says
 *                   nothing instead — the only honest rendering of "unknown".
 *
 * Pure: takes `t`, touches no hook, so the three branches are testable without
 * rendering a table.
 */
export function serviceScopeText(entry: LookupEntry, t: Translator): string {
  if (entry.service === undefined) {
    return "";
  }
  if (entry.service === null) {
    return t("settings.reference.allServices");
  }
  const code = entry.service.code;
  return t(`rating.service.${code}`, { defaultValue: code });
}

/**
 * `DEF-TEN-4478` — the ONE client-side rule about a parent, and it is not a
 * copy of the server's.
 *
 * The server owns DEPTH (`settings.areas.parent_self`,
 * `settings.areas.parent_is_sub_area`, `settings.areas.has_sub_areas`) and this
 * screen has never held a second copy of it — see `lookupSchema` below, which
 * leaves `parent_code` unconstrained on purpose.
 *
 * What the server CANNOT know is what the person said they were making. Blank
 * and a code are both perfectly legal writes: blank makes an area, a code makes
 * a sub-area, and the API is right to accept either. So a chooser set to
 * *Sub-area* with an empty picker would post a legal request that creates the
 * OTHER thing — the screen would promise a sub-area and quietly make an area,
 * with no error anywhere. That is a form-consistency rule, it belongs to the
 * form, and this is it.
 */
export interface ParentRequirement {
  /** Message shown under the picker when the sub level is chosen and it is empty. */
  message: string;
}

/**
 * `CR-162-BRC10` — the premises-type row's ACCOUNT TYPE as the column reads it:
 * *Master account*, *Regular account*, or *Not answered* for a utility's own
 * type from before the setting existed (the master rule then counts homes).
 */
export function accountKindText(entry: LookupEntry, t: Translator): string {
  const answer = entry.account_kind;
  if (answer === "master") {
    return t("settings.reference.accountKind.master", { defaultValue: "Master account" });
  }
  if (answer === "regular") {
    return t("settings.reference.accountKind.regular", { defaultValue: "Regular account" });
  }
  return t("settings.reference.accountKind.unanswered", { defaultValue: "Not answered" });
}

/**
 * `CR-187-BRC10` (PO answer 9, 2026-10-21) — the three ways an assignment at a
 * work priority may ring on the technician's phone, least to most urgent. The
 * SERVER owns the set (`work.priorities.push_kind_unknown`); this is the order
 * the choice draws them in.
 */
export const PUSH_KINDS = ["new_job", "urgent_assignment", "emergency"] as const;

/** A work-priority row's push kind as the column reads it. A token the server
 *  adds later falls back to itself, never hidden (B14 rule 31). */
export function pushKindText(entry: LookupEntry, t: Translator): string {
  const answer = typeof entry.push_kind === "string" ? entry.push_kind : "new_job";
  return t(`settings.reference.pushKind.${answer}`, { defaultValue: answer });
}

export function lookupSchema(
  t: Translator,
  parentRequired?: ParentRequirement,
  accountKindRequired?: boolean,
) {
  const base = z.object({
    code: z
      .string()
      .trim()
      .min(1, t("settings.reference.codeRequired"))
      .max(60, t("settings.reference.tooLong", { max: 60 })),
    name: z
      .string()
      .trim()
      .min(1, t("settings.reference.nameRequired"))
      .max(60, t("settings.reference.tooLong", { max: 60 })),
    detail: z.string(),
    // BR-MET-066b — optional and unconstrained here on purpose: the two-level
    // cap is the SERVER's rule (settings.areas.parent_self /
    // parent_is_sub_area / has_sub_areas) and a second copy in a zod schema is
    // the copy that drifts. Client validation on this form is UX only.
    parent_code: z.string().optional(),
    // CR-065 — optional and unconstrained for BR-MET-066b's reason, one field
    // along: whether a service is one THIS tenant has enabled is the SERVER's
    // rule (BR-TEN-026, `settings.lookups.service_unknown`), and blank is a
    // real answer meaning the size is offered on every service.
    service: z.string().optional(),
    // CR-162-BRC10 — "master" | "regular" | "" (not chosen). Required on the
    // one card that asks it; the server refuses a blank too.
    account_kind: z.string().optional(),
    // DEF-RAT-10220 — the server owns the rule (> 0, ≤ 4 decimals) and its
    // refusal lands under the field; a second copy here is the one that drifts.
    capacity: z.string().optional(),
  });
  if (parentRequired === undefined && accountKindRequired !== true) {
    return base;
  }
  return base.superRefine((values, ctx) => {
    if (accountKindRequired === true && (values.account_kind ?? "") === "") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["account_kind"],
        message: t("metering.lookups.account_kind_required", {
          defaultValue: "Choose the account type.",
        }),
      });
    }
    if (parentRequired === undefined) {
      return;
    }
    if ((values.parent_code ?? "").trim() === "") {
      // The `path` is load-bearing: `collectFormErrors` drops an issue with an
      // empty path, so a refinement without one validates nothing and reports
      // nothing — a check incapable of failing (hard-won law 7).
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["parent_code"],
        message: parentRequired.message,
      });
    }
  });
}

export function holidaySchema(t: Translator) {
  return z.object({
    date: z.string().min(1, t("settings.reference.holidays.dateRequired")),
    label: z
      .string()
      .trim()
      .min(1, t("settings.reference.holidays.labelRequired"))
      .max(80, t("settings.reference.tooLong", { max: 80 })),
  });
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface ReferenceDataTabProps {
  readOnly: boolean;
  client?: ApiClient;
  // IS-8: the tenant's date format for the S63 calendar. It arrives with the
  // US-SHL-013 formatting-service wiring; DateCell REQUIRES one, so the seed
  // format stands in rather than a hand-rolled format inside this screen.
  dateFormat?: RegionalDateFormat;
}

export function ReferenceDataTab(props: ReferenceDataTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [searchParams, setSearchParams] = useSearchParams();
  const open = openCardFrom(searchParams);

  function openCard(code: string | null): void {
    const next = new URLSearchParams(searchParams);
    if (code === null) {
      next.delete(LIST_PARAM);
      // Leaving a list drops its own view state with it (BR-SHL-011).
      for (const key of ["q", "page", "per", "sort", "dir"]) {
        next.delete(key);
      }
    } else {
      next.set(LIST_PARAM, code);
    }
    setSearchParams(next, { replace: true });
  }

  if (open === null) {
    return <ReferenceCardGrid client={client} onOpen={openCard} />;
  }

  // BR-SHL-035: ONE frame. Everything below differs only in its BODY.
  return (
    <SettingsFrame
      onBack={() => openCard(null)}
      backLabel={t("settings.reference.back")}
      kicker={t(`settings.reference.owner.${open.owner}`)}
      title={t(open.labelKey)}
      description={t(open.sampleKey)}
    >
      <ReferenceCardBody
        card={open}
        readOnly={props.readOnly}
        client={client}
        dateFormat={props.dateFormat}
      />
    </SettingsFrame>
  );
}

function ReferenceCardBody(props: {
  card: ReferenceCard;
  readOnly: boolean;
  client: ApiClient;
  dateFormat?: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const { card } = props;
  // DEF-SHL-3964 — HOISTED, and it was `props.dateFormat ?? "MM/DD/YYYY"` inside
  // `if (card.kind === "rules")`. `useRegional` reads a context, so a call in a
  // branch is a hook whose presence depends on which card is open.
  const { dateFormat } = useRegional(props);
  if (card.arrivesWithKey !== undefined) {
    return <ArrivesWith title={t(card.labelKey)} message={t(card.arrivesWithKey)} />;
  }
  if (card.kind === "link") {
    // BR-TEN-033: the card navigates; opened directly it says where to go.
    return (
      <ArrivesWith
        title={t(card.labelKey)}
        message={t("settings.reference.arrivesWith.templates")}
      />
    );
  }
  if (card.kind === "custom") {
    // EP-TEN-09 in the SAME frame (BR-TEN-047 / BR-SHL-035): card → table →
    // FormModal, with the same "← Reference data" return and the same audit
    // line. The body differs because the RESOURCE differs; the shell does not.
    return <CustomFieldsManagement readOnly={props.readOnly} client={props.client} />;
  }
  if (card.kind === "rules") {
    if (card.code === "holidays") {
      return (
        <HolidayCalendarView
          readOnly={props.readOnly}
          client={props.client}
          dateFormat={dateFormat}
        />
      );
    }
    if (card.code === "service_centres") {
      // CWP-074 → CWP-075, in the SAME frame (BR-SHL-035): the card's own
      // back link returns to the grid and the editor's returns to the list.
      return <ServiceCentresView readOnly={props.readOnly} client={props.client} />;
    }
    if (card.code === "read_validation") {
      // S64 — CR-038 A1 (PO 2026-08-26): per utility service, so it stopped
      // being a flat param list. Same frame, same back-link (BR-SHL-035);
      // only the BODY differs, exactly the holidays posture above.
      return <ReadValidationRulesView readOnly={props.readOnly} client={props.client} />;
    }
    // BR-SHL-035: the S66–S71 pages are the SAME card in the SAME frame —
    // only the body is a form. ONE component serves all four (RulePageView),
    // driven by settingsRulePages.ts, so a fifth is config and not a screen.
    const rulePage = rulePageForCard(card.code);
    if (rulePage !== null) {
      return <RulePageView page={rulePage} readOnly={props.readOnly} client={props.client} />;
    }
    return (
      <ArrivesWith title={t(card.labelKey)} message={t("settings.reference.arrivesWith.rules")} />
    );
  }
  return <LookupListView card={card} readOnly={props.readOnly} client={props.client} />;
}

// ── US-TEN-009 the card grid ───────────────────────────────────────────────

function ReferenceCardGrid(props: { client: ApiClient; onOpen: (code: string) => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();

  const cardsQuery = useQuery({
    queryKey: queryKeys.lookupCards,
    queryFn: () => getLookupCards(props.client),
    staleTime: REFERENCE_STALE_MS,
  });

  if (cardsQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (cardsQuery.data === undefined) {
    if (isPermissionDenied(cardsQuery.error)) {
      // US-TEN-009 TC-5: Settings is System Admin-only.
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.reference.failedTitle")}
        reason={apiErrorText(cardsQuery.error, t)}
        onRetry={() => void cardsQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void cardsQuery.refetch()}
      />
    );
  }

  const views = referenceCardViews(cardsQuery.data);

  return (
    <div className="settings-tab">
      <Kicker>{t("settings.reference.kicker")}</Kicker>
      {/* The grid intro states the lock rule up front (BR-TEN-029/034). */}
      <p className="settings-lede">{t("settings.reference.lede")}</p>
      {/* r10 SET-04 files the cards under module headings. A heading renders
          only when it HAS cards: the grid is server-driven (`GET /lookups`
          omits any list whose owning module has not registered a handler), so
          a hard-coded heading would sooner or later sit above nothing and read
          as a broken screen. Empty sections disappear instead. */}
      {REFERENCE_GROUP_ORDER.map((group) => {
        const inGroup = views.filter((view) => view.card.group === group);
        if (inGroup.length === 0) {
          return null;
        }
        return (
          <section key={group} className="lookup-group">
            <h3 className="lookup-group-heading">{t(`settings.reference.group.${group}`)}</h3>
            <div className="lookup-grid">
              {inGroup.map((view) => (
                <ReferenceCardTile
                  key={view.card.code}
                  view={view}
                  onOpen={() => {
                    if (view.card.kind === "link" && view.card.target !== undefined) {
                      navigate(tenantPath(view.card.target)); // BR-TEN-033
                      return;
                    }
                    props.onOpen(view.card.code);
                  }}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

/**
 * ⚠ DEF-336 — THE BADGE HAS THREE STATES AND USED TO HAVE TWO.
 *
 * The PO photographed SET-04: the whole BILLING section — Billing defaults,
 * Budget billing rules, Document & message templates — drew a bare chevron and
 * no number, while READS showed 5 and PAYMENTS showed 7. Next to WORK's honest
 * "Not set up yet" that reads as missing configuration, to the one person who
 * can act on it.
 *
 * Two separate causes, and neither was a lost row:
 *
 *   1. `card.kind !== "list"` threw the count away BEFORE looking at it, so
 *      `custom_fields` — which the server has always counted — could never show
 *      its number either.
 *   2. Everything that is not a list collapsed into `"›"`, with no words at all.
 *      A blank says nothing, and a person reads nothing as "nothing here".
 *
 * So: a count the server took is rendered whatever the card's kind is, and the
 * two countless cases are SAID rather than left blank — using the server's own
 * report vocabulary (`uncounted` is DEF-026's, not a fourth state minted here).
 * The long sentence rides `title`, where it does not have to fit a badge.
 */
export function badgeFor(view: ReferenceCardView, t: Translator): { text: string; title?: string } {
  if (view.count !== null) {
    return { text: `${view.count} ›` };
  }
  if (view.state === "uncounted") {
    // The list IS set up — the seed-run ledger proves the rows — and this
    // screen cannot take the count. Saying "not set up yet" here would be false.
    return {
      text: t("settings.reference.uncounted"),
      title: t("settings.reference.uncountedWhy"),
    };
  }
  if (view.card.kind === "list") {
    // Rendering 0 would claim the list is empty, which is a different statement.
    return { text: t("settings.reference.noEntries") };
  }
  if (view.card.kind === "link") {
    // Navigation only (BR-TEN-033) — tenancy stores nothing for it, so the
    // count belongs to the screen it opens and the badge says where.
    return {
      text: t("settings.reference.opensElsewhere"),
      title: t("settings.reference.opensElsewhereWhy"),
    };
  }
  return {
    text: t("settings.reference.settingsCard"),
    title: t("settings.reference.settingsCardWhy"),
  };
}

function ReferenceCardTile(props: { view: ReferenceCardView; onOpen: () => void }) {
  const { t } = useTranslation();
  const { card } = props.view;
  // BR-TEN-029: the count is computed live by the server; this only decides
  // which of the three things a person reads in the badge slot.
  const badge = badgeFor(props.view, t);
  return (
    <button type="button" className="lookup-card" onClick={props.onOpen}>
      <span className="n">{t(card.labelKey)}</span>
      <span className="c">{t(card.sampleKey)}</span>
      <span className="v" title={badge.title} data-card-state={props.view.state}>
        {badge.text}
      </span>
    </button>
  );
}

/* B14 rule 15 — row actions are ICONS with tooltips, never text links, and the
   label survives as BOTH `title` and `aria-label`: an icon with no accessible
   name passes a text-absence check and is unusable without a mouse.

   ⚠ THE GLYPHS MOVED TO `components/icons.tsx` ON 2026-08-20 AND ARE NOT
   REDRAWN HERE. They were drawn locally in this file, identically to two other
   files, until DEF-348 counted four copies of the pencil alone. PO ruling that
   day: "Tailwind, CSS, STylesheet, UI COmponents - we should ahve only one
   reference point not two". */

// ── US-TEN-010/011 — THE ONE config-driven list-management view ────────────

interface LookupRow extends LookupEntry {
  _rowKey: string;
}

function lookupTableConfig(
  card: ReferenceCard,
  t: Translator,
  renderActions: (row: LookupRow) => JSX.Element,
): TableConfig<LookupRow> {
  const columns: TableConfig<LookupRow>["columns"] = [
    // BR-SHL-013: the identity column can never be hidden.
    { key: "code", label: t("settings.reference.col.code"), sortable: true, identity: true },
    {
      key: "name",
      label: t("settings.reference.col.name"),
      sortable: true,
      // BR-MET-066c — r10 SET-04 renders `North district · 3 sub-areas` on the
      // NAME. ⚠ **`is_sub_area`, `parent_code`, `parent_name` and
      // `sub_area_count` are the SELF-PARENTED WIRE CONTRACT, not area
      // vocabulary** — every hierarchical handler publishes those four names
      // whatever its own two levels are called, and the words a person reads
      // come from the card's `hierarchical` block instead. Renaming the keys
      // per list would give one shared view N payload shapes to sniff. It is a cell renderer rather than a column so a flat list is
      // untouched: `subAreaCountText` returns "" for every row of every list
      // that publishes no `sub_area_count`, and a column of blanks reads as
      // "no value" where the truth is "not a question we ask of this list"
      // (the same argument the `serviceScoped` column makes below).
      cell: (row) => {
        const suffix = subAreaCountText(
          row as unknown as LookupEntry,
          t,
          card.hierarchical?.countKey,
        );
        return (
          <>
            {row.name}
            {suffix === "" ? null : (
              <span className="ml-1.5 opacity-60">{`· ${suffix}`}</span>
            )}
          </>
        );
      },
    },
  ];
  // CR-004 task A3 · r10 SET-04 draws Code · Name · **Utility service** · Used
  // by · Status · Actions, so the column goes here, third, where the design puts
  // it. It renders ONLY for a card that declares `serviceScoped` (BR-TEN-078,
  // superseded for `service_size_classes` alone on 2026-09-02 — two cards, not
  // one, DEF-3341): a list whose rows publish no scope would draw a column
  // of blanks, and a blank column reads as "no value" rather than "not a
  // question we ask of this list". Not sortable — the server sorts `code` and
  // `name` (the B9 row), and offering a sort the API cannot honour is a control
  // that silently does nothing.
  if (card.serviceScoped === true) {
    columns.push({
      key: "service",
      label: t("settings.reference.col.service"),
      cell: (row) => serviceScopeText(row, t),
    });
  }
  // DEF-RAT-10220 — "Capacity", drawn only on the card whose rows carry one.
  if (card.capacity === true) {
    columns.push({
      key: "capacity",
      label: t("settings.reference.col.capacity"),
      cell: (row) => <span data-capacity={String(row.capacity ?? "")}>{capacityText(row)}</span>,
    });
  }
  // CR-162-BRC10 — "Account type", drawn only on the card that asks it.
  if (card.accountKind === true) {
    columns.push({
      key: "account_kind",
      label: t("settings.reference.col.accountKind", { defaultValue: "Account type" }),
      cell: (row) => (
        <span data-account-kind={String(row.account_kind ?? "unanswered")}>
          {accountKindText(row, t)}
        </span>
      ),
    });
  }
  // CR-187-BRC10 — "Phone alert", drawn only on the work-priority card.
  if (card.pushKind === true) {
    columns.push({
      key: "push_kind",
      label: t("settings.reference.col.pushKind", { defaultValue: "Phone alert" }),
      cell: (row) => (
        <span data-push-kind={String(row.push_kind ?? "new_job")}>{pushKindText(row, t)}</span>
      ),
    });
  }
  // BR-MET-066b · DEF-221 — a two-level list has to SHOW the second level, or
  // "Areas & sub-areas" is a table of areas with three rows that look identical
  // to the rest and no way to tell which is which. The value is the server's
  // own `parent_name`; an em dash means top level. CR-010 widened this to the
  // cross-list tree (`parentList` — account sub-types under account types):
  // same column, same server key, the label alone is the card's own.
  const parentColumnLabelKey = card.parentList?.labelKey ?? card.hierarchical?.parentLabelKey;
  if (parentColumnLabelKey !== undefined) {
    columns.push({
      key: "parent_name",
      label: t(parentColumnLabelKey),
      cell: (row) => <>{parentText(row)}</>,
    });
  }
  if (card.detailField !== undefined) {
    const field = card.detailField.field;
    columns.push({
      key: field,
      label: t(card.detailField.labelKey),
      cell: (row) => (card.detailField === undefined ? "" : detailLabel(row, card.detailField, t)),
    });
  }
  columns.push(
    {
      key: "used_by",
      label: t("settings.reference.col.usedBy"),
      sortable: true,
      numeric: true,
    },
    {
      key: "active",
      label: t("settings.reference.col.status"),
      cell: (row) =>
        // DEF-CUS-9808 — an active row the utility has stopped offering on new
        // accounts says so; `Inactive` still wins, it is the stronger state.
        card.legacyToggle === true && row.active && row.legacy === true ? (
          <StatusPill tone="warning">{t("settings.reference.notOffered")}</StatusPill>
        ) : (
          <StatusPill tone={row.active ? "success" : "neutral"}>
            {t(row.active ? "settings.reference.active" : "settings.reference.inactive")}
          </StatusPill>
        ),
    },
    {
      key: "actions",
      label: t("settings.reference.col.actions"),
      cell: renderActions,
    },
  );
  return {
    screenId: `S8.${card.code}`,
    columns,
    getRowId: (row) => row.id,
    // The B9 row declares Code + Name search (IS-3, server-side).
    searchFields: ["code", "name"],
    // B14 rule 19 (DEF-510). Every reference card is served by the shared lookup
    // framework, whose search is `Q(code__icontains) | Q(name__icontains)`
    // (`apps/*/lookups.py`, four copies of the same two-leg predicate), so ONE
    // prompt is correct for all of them and it names the two columns the table
    // draws first.
    //
    // ⚠ **DEF-510's ROW SAID THIS SCREEN STAYS ON THE DEFAULT DELIBERATELY, AND
    // CR-041 REVERSES THAT** — see `SettingsCustomFields` for the full reasoning
    // and the B14-over-r10 precedent it rests on.
    //
    // ⚠ **AND THE PROMPT NAMES FIELDS, NOT THE CARD.** Rule 19's grammar is
    // "Search {entities}…", and the genuinely best prompt here would name the
    // card a clerk is standing in — *"Search units of measure…"*. It cannot be
    // written: `searchPlaceholder` is a KEY and `DataTable` renders it with
    // `t(key)` and NO params, so there is nowhere to put `card.name`. Naming the
    // fields is what this config can honestly promise; interpolating the card
    // name is a change to the shared component and is NOT smuggled in here.
    searchPlaceholder: "settings.reference.searchPlaceholder",
    defaultSort: { sort: "code", dir: "asc" },
  };
}

type PendingDelete = { entry: LookupEntry } | null;

// ── DEF-902: A LIST OLDER THAN THE PLATFORM FIXTURE SAYS SO ────────────────
/**
 * BR-TEN-161. PO, on the live app at v2.61.1: *"in this setting - unable to
 * see sub areas"*.
 *
 * `lookup_defaults.json` at `V2.48.0.2` ships **seven** area rows with their
 * parent wiring. Silver Creek Water shows **four**. The fixture, the two-level
 * depth cap and the Add-entry dialog's own *"Choose a parent to make this a
 * sub-area of it"* are ALL correct and shipped — the tenant was provisioned
 * BEFORE the fixture grew, and nothing re-offers a reference list to a tenant
 * that already has one. **The PO ratified those three names that same morning
 * (OQ-432) and then could not see them**, which is hard-won law 4 in its data
 * form: a template change never reaches a host that already has one.
 *
 * ⚠ **THIS DELIVERS NOTHING, AND THAT IS THE DESIGN.** BR-TEN-160 keeps
 * delivery in the sweep, which re-offers STRUCTURAL lists only under OQ-088's
 * closed ruling; whether it should also re-offer a discretionary list the
 * tenant demonstrably already holds is **OQ-550**, routed to the PO. Until
 * then the product SAYS what is missing rather than leaving a person to be
 * told — and `sweep_delivers` decides which sentence, SERVED rather than
 * assumed here so the copy cannot drift from the policy.
 *
 * Renders nothing at all when the list is current, when the read fails, or
 * while it loads: a notice is a statement of fact, and there is no fact yet.
 */
function FixtureGapNotice(props: { listCode: string; client: ApiClient }) {
  const { t } = useTranslation();
  const gapQuery = useQuery({
    queryKey: queryKeys.lookupFixtureGap(props.listCode),
    queryFn: () => getReferenceFixtureGap(props.listCode, props.client),
    staleTime: REFERENCE_STALE_MS,
  });
  const gap = gapQuery.data;
  if (gap === undefined || gap.missing.length === 0) {
    return null;
  }
  // Named, never counted — BR-TEN-161(a). A count alone would have told the PO
  // nothing they could not already see on the screen they were looking at.
  const names = gap.missing.map((row) => `${row.name} (${row.code})`).join(", ");
  return (
    <p
      data-fixture-gap={String(gap.missing.length)}
      role="status"
      className="m-0 max-w-measure border border-divider px-3 py-2 text-sm text-neutral-700"
    >
      {t("settings.reference.behind.body", {
        count: gap.missing.length,
        names,
        version: gap.fixture_version,
      })}{" "}
      {t(gap.sweep_delivers ? "settings.reference.behind.sweep" : "settings.reference.behind.repair")}
    </p>
  );
}

function LookupListView(props: { card: ReferenceCard; readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  const { card, client } = props;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  // BR-SHL-011: q/page/per live in the URL alongside ?list, so a filtered list
  // view is shareable and a reload lands where the user was.
  const state: TableRequestState = {
    q: searchParams.get("q") ?? "",
    sort: "code",
    dir: "asc",
    page: Math.max(1, Number.parseInt(searchParams.get("page") ?? "1", 10) || 1),
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  };
  function setState(next: TableRequestState): void {
    const params = new URLSearchParams(searchParams);
    if (next.q === "") {
      params.delete("q");
    } else {
      params.set("q", next.q);
    }
    if (next.page > 1) {
      params.set("page", String(next.page));
    } else {
      params.delete("page");
    }
    setSearchParams(params, { replace: true });
  }

  const entriesQuery = useQuery({
    queryKey: queryKeys.lookupEntries(card.code, state.q, state.page, state.per),
    queryFn: () =>
      getLookupEntries(card.code, { q: state.q, page: state.page, per: state.per }, client),
  });

  const [editing, setEditing] = useState<LookupEntry | null>(null);
  const [adding, setAdding] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  // CR-161-BRC10 W4 — an area's own fields as COLUMNS of the Areas list
  // (`AREA_LIST`, *Show as column*). There is no Area page; this list is the
  // nearest page that exists. Appended for the `areas` card only.
  const areaColumns = useCustomFieldColumns<LookupRow>({
    entity: "areas",
    screen: "AREA_LIST",
    valuesOf: (row) => [{ values: row.custom_data ?? {} }],
    client,
  });
  const baseConfig = lookupTableConfig(card, t, rowActions);
  const tableConfig =
    card.code === "areas" && areaColumns.length > 0
      ? {
          ...baseConfig,
          // Before the row actions, which stay the last column.
          columns: [
            ...baseConfig.columns.filter((column) => column.key !== "actions"),
            ...areaColumns,
            ...baseConfig.columns.filter((column) => column.key === "actions"),
          ],
        }
      : baseConfig;

  function refresh(): void {
    void queryClient.invalidateQueries({ queryKey: ["lookups"] });
  }

  const toggleActive = useMutation({
    mutationFn: (input: { entry: LookupEntry; active: boolean }) =>
      setLookupEntryActive(card.code, input.entry.id, input.active, client),
    onSuccess: (_saved, input) => {
      refresh();
      setRefusal(null);
      fireToast(
        t(input.active ? "settings.reference.reactivated" : "settings.reference.deactivated", {
          code: input.entry.code,
        }),
      );
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  // DEF-CUS-9808 — stop / restart offering a row on new accounts (`legacy`).
  const toggleOffered = useMutation({
    mutationFn: (input: { entry: LookupEntry; legacy: boolean }) =>
      updateLookupEntry(card.code, input.entry.id, { legacy: input.legacy }, client),
    onSuccess: (_saved, input) => {
      refresh();
      setRefusal(null);
      fireToast(
        t(input.legacy ? "settings.reference.stoppedOffering" : "settings.reference.offeredAgain", {
          code: input.entry.code,
        }),
      );
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  const removeEntry = useMutation({
    mutationFn: (entry: LookupEntry) => deleteLookupEntry(card.code, entry.id, client),
    onSuccess: (_void, entry) => {
      refresh();
      setPendingDelete(null);
      setRefusal(null);
      fireToast(t("settings.reference.deleted", { code: entry.code }));
    },
    onError: (error: unknown) => {
      // BR-TEN-034 / US-TEN-011 TC-4 + TC-5: the server's fresh Used-by count
      // is what refuses, and its 409 is what the user reads.
      setPendingDelete(null);
      setRefusal(refusalOf(error, t));
    },
  });

  if (entriesQuery.data === undefined && entriesQuery.isError) {
    if (isPermissionDenied(entriesQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.reference.failedTitle")}
        reason={apiErrorText(entriesQuery.error, t)}
        onRetry={() => void entriesQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void entriesQuery.refetch()}
      />
    );
  }

  const rows: LookupRow[] = (entriesQuery.data?.results ?? []).map((entry) => ({
    ...entry,
    _rowKey: entry.id,
  }));

  function rowActions(row: LookupRow): JSX.Element {
    const locked = deleteIsLocked(row);
    // BR-TEN-029 has no storage on this list (no active column), so the server
    // answers 409 rather than recording nothing. BR-SHL-025: the control stays
    // visible and DISABLED WITH ITS REASON — never a live button that always
    // fails, and never a silently missing one.
    const deactivateReason =
      card.deactivateUnsupportedKey === undefined ? null : t(card.deactivateUnsupportedKey);
    return (
      <RowActions>
        <RowAction
          label={t("settings.reference.edit")}
          icon={<PencilIcon />}
          reason={props.readOnly ? t("settings.readOnlyReason") : null}
          onClick={() => setEditing(row)}
        />
        <RowAction
          label={t(row.active ? "settings.reference.deactivate" : "settings.reference.reactivate")}
          icon={<PowerIcon />}
          reason={
            deactivateReason ?? (props.readOnly ? t("settings.readOnlyReason") : null)
          }
          working={toggleActive.isPending}
          onClick={() => toggleActive.mutate({ entry: row, active: !row.active })}
        />
        {card.legacyToggle === true && (
          <RowAction
            label={t(row.legacy === true ? "settings.reference.offerAgain" : "settings.reference.stopOffering")}
            icon={row.legacy === true ? <PlayIcon /> : <PauseIcon />}
            reason={props.readOnly ? t("settings.readOnlyReason") : null}
            working={toggleOffered.isPending}
            onClick={() => toggleOffered.mutate({ entry: row, legacy: row.legacy !== true })}
          />
        )}
        {locked ? (
          // BR-TEN-034: 🔒 disabled WITH the reason (BR-SHL-025) — deactivate
          // is offered instead. The server enforces the same refusal.
          // `.settings-locked` is gone with it: the kit already writes
          // `disabled:cursor-not-allowed` and `disabled:opacity-45`, so the
          // class was a third statement of a thing stated twice.
          <RowAction
            label={t("settings.reference.deleteLocked")}
            icon={<TrashIcon />}
            reason={
              deleteLockReason(row) === "system"
                ? t("settings.reference.systemLockTooltip")
                : t("settings.reference.lockTooltip", { count: row.used_by })
            }
            danger
            onClick={() => undefined}
          />
        ) : (
          <RowAction
            label={t("settings.reference.delete")}
            icon={<TrashIcon />}
            reason={props.readOnly ? t("settings.readOnlyReason") : null}
            danger
            onClick={() => setPendingDelete({ entry: row })}
          />
        )}
      </RowActions>
    );
  }

  return (
    <>
      <div className="settings-frame-toolbar">
        <Button
          variant="primary"
          disabled={props.readOnly}
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => setAdding(true)}
        >
          {t("settings.reference.addEntry")}
        </Button>
      </div>

      {/* BR-TEN-031: this card mints CODES; the money lives on the owner's own
          screen. Saying so beats a user typing a rate into a field that will be
          refused as an unknown one. */}
      {card.codeNameOnlyKey !== undefined && (
        <Note>{t(card.codeNameOnlyKey)}</Note>
      )}
      {card.deactivateUnsupportedKey !== undefined && (
        <Note>{t(card.deactivateUnsupportedKey)}</Note>
      )}

      {/* DEF-902 / BR-TEN-161 — above the table, because it is a statement
          ABOUT the table: the rows below are not all the rows the platform
          ships. Passed for EVERY list, not a per-card opt-in: a card that had
          to declare itself gappable would be silent on the next list to grow,
          which is the defect repeating (hard-won law 2). */}
      <FixtureGapNotice listCode={card.code} client={client} />

      {/* CR-187-BRC10 — the option the "Phone alert" column depends on. */}
      {card.pushKind === true && <PushByPriorityToggle readOnly={props.readOnly} client={client} />}

      <RefusalNotice refusal={refusal} />

      <DataTable<LookupRow>
        config={tableConfig}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={entriesQuery.data?.count ?? null}
        loading={entriesQuery.isPending}
        empty={{
          title: t("settings.reference.emptyTitle", { list: t(card.labelKey) }),
          helper: t("settings.reference.emptyHelper"),
          ctaLabel: t("settings.reference.addEntry"),
          onCta: () => setAdding(true),
        }}
      />

      {/* r10 SET-04's closing line is the FRAME's: SettingsFrame already ends
          every card with `settings.auditLine` — the identical sentence. A
          second copy here rendered it twice, one above the other, on every
          list detail (DEF-596, CR-028 debt sweep 2026-08-22). One frame, one
          line; the test pins exactly one occurrence. */}

      {(adding || editing !== null) && (
        <LookupEntryModal
          card={card}
          entry={editing}
          client={client}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onSaved={(entry, created) => {
            setAdding(false);
            setEditing(null);
            refresh();
            fireToast(
              t(created ? "settings.reference.added" : "settings.reference.updated", {
                code: entry.code,
              }),
            );
          }}
        />
      )}

      {pendingDelete !== null && (
        // BR-SHL-032: the button names the action; IS-6 states the consequence.
        <ConfirmDialog
          // B14 rule 6 (DEF-718): delete a reference-data entry.
          confirmVariant="danger"
          title={t("settings.reference.deleteTitle", { code: pendingDelete.entry.code })}
          consequence={t("settings.reference.deleteBody", {
            code: pendingDelete.entry.code,
            name: pendingDelete.entry.name,
          })}
          confirmLabel={t("settings.reference.deleteAction", { code: pendingDelete.entry.code })}
          working={removeEntry.isPending}
          onConfirm={() => removeEntry.mutate(pendingDelete.entry)}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </>
  );
}

/** The ONE add/edit modal — the same one for every list (US-TEN-010). */
function LookupEntryModal(props: {
  card: ReferenceCard;
  entry: LookupEntry | null;
  client: ApiClient;
  onClose: () => void;
  onSaved: (entry: LookupEntry, created: boolean) => void;
}) {
  const { t } = useTranslation();
  const { card, entry } = props;
  const detailField = card.detailField;
  const [code, setCode] = useState(entry?.code ?? "");
  const [name, setName] = useState(entry?.name ?? "");
  const [detail, setDetail] = useState(
    detailField === undefined ? "" : detailText(entry ?? ({} as LookupEntry), detailField.field),
  );
  // BR-MET-066b · DEF-221 — the control that turns "Areas & sub-areas" from a
  // title into a feature. Blank = a top-level row. CR-010: `parentList` is the
  // cross-list form of the same control — the picker's rows come from ANOTHER
  // list (account sub-types pick among the platform account types) and blank
  // is not an option the server accepts there (`customers.lookups.
  // parent_required`) — the refusal lands under this select.
  const parentList = card.parentList;
  // DEF-TEN-4478 — the SELF-PARENTED list's two levels, and the reason only it
  // gets a chooser: here blank and a code are BOTH legal writes that make
  // different things, so there is a question to ask. On a `parentList` card the
  // parent is required and there is exactly one answer, so asking would be
  // theatre.
  const levels = card.hierarchical;
  const hierarchical = levels !== undefined || parentList !== undefined;
  const parentSourceList = parentList?.code ?? card.code;
  const [parentCode, setParentCode] = useState(
    typeof entry?.parent_code === "string" ? entry.parent_code : "",
  );
  // The chooser's own state, seeded from the row so EDITING opens on what the
  // row already is (a sub-area opens as *Sub-area*, with its parent shown).
  // `is_sub_area` is the server's own verdict rather than a re-derivation from
  // `parent_code`, which the payload may omit.
  const [level, setLevel] = useState<"top" | "sub">(entryIsSubLevel(entry) ? "sub" : "top");
  // Its own fetch, unpaged and unfiltered, rather than the list view's rows: the
  // parent choices must not depend on which page the user is on or what they
  // typed in the search box.
  const parentsQuery = useQuery({
    queryKey: ["lookups", parentSourceList, "parents"],
    queryFn: () => getLookupEntries(parentSourceList, { per: 200 }, props.client),
    enabled: hierarchical,
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const parentOptions = parentOptionsFor(parentsQuery.data?.results ?? [], entry?.id ?? null);
  // CR-065 · BR-TEN-078 as superseded 2026-09-02 — the row's UTILITY SERVICE.
  // The column was drawn from CR-004 and nothing could ever SET it, which is
  // hard-won law 2 on a form: read-only, correct, and not the feature. The PO
  // asked for the other half in as many words — *"in Setting a capacity needs
  // to tags to utility services ."*
  const serviceScoped = card.serviceScoped === true;
  const [serviceCode, setServiceCode] = useState(entry?.service?.code ?? "");
  // The tenant's ENABLED services, which is what the server will accept
  // (BR-TEN-026): offering a service they do not sell would draw a choice the
  // write refuses.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(props.client),
    enabled: serviceScoped,
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const serviceOptions = (servicesQuery.data ?? []).filter((row) => row.enabled);
  // DEF-RAT-10220 — the capacity, asked only when the chosen service SUMS
  // (its `capacity_uom` from the server; no service is named here).
  const capacityUom = card.capacity === true ? capacityUomFor(servicesQuery.data ?? [], serviceCode) : null;
  const [capacity, setCapacity] = useState<string>(
    typeof entry?.capacity === "string" ? trimCapacity(entry.capacity) : "",
  );
  const frozen = entry !== null && codeIsFrozen(entry);
  // CR-162-BRC10 — the ACCOUNT TYPE: Master or Regular, NO default (hard-won
  // law 3). An edit opens on the row's own answer; a utility's own type from
  // before the setting existed opens unanswered.
  const accountKind = card.accountKind === true;
  const [accountKindAnswer, setAccountKindAnswer] = useState<string>(
    entry?.account_kind === "master" || entry?.account_kind === "regular"
      ? String(entry.account_kind)
      : "",
  );
  // CR-187-BRC10 — how an assignment at this priority rings. An edit opens on
  // the row's own answer; a new priority opens on the server's default.
  const pushKind = card.pushKind === true;
  const [pushKindAnswer, setPushKindAnswer] = useState<string>(
    typeof entry?.push_kind === "string" ? entry.push_kind : "new_job",
  );
  // CR-161-BRC10 W4 — an AREA's own fields (`AREA_FORM`). Only the `areas`
  // card draws them; an edit sends only what changed.
  const isAreas = card.code === "areas";
  const storedCustomData: CustomFieldValues = entry?.custom_data ?? {};
  const [customData, setCustomData] = useState<CustomFieldValues>(storedCustomData);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    const payload: Record<string, unknown> = { name: name.trim() };
    // BR-TEN-030: a frozen code is not even SENT — the server would refuse it
    // with 409 BIZ-IMMUTABLE, and sending it would look like an attempt.
    if (!frozen) {
      payload.code = code.trim();
    }
    // BR-TEN-031: a code+name-only list REFUSES every other field as unknown,
    // so its detail value is never sent — it is the owner's to set on S12/S13.
    if (detailField !== undefined && card.codeNameOnlyKey === undefined) {
      payload[detailField.field] = detail.trim();
    }
    // BR-MET-066b — ALWAYS sent for a hierarchical list, empty string included:
    // the handler reads an absent `parent_code` as "leave it alone" and an empty
    // one as "promote this row back to top level", and both are things a person
    // does on this form.
    //
    // DEF-TEN-4478: on a self-parented list the CHOOSER decides, not the
    // picker. Choosing *Area* sends an empty parent even if a code is still
    // sitting in state from a moment on the other segment — which is also what
    // makes a browser-filled picker harmless, because a value nobody chose can
    // no longer change what gets made.
    if (hierarchical) {
      payload.parent_code = levels !== undefined && level === "top" ? "" : parentCode;
    }
    // ALWAYS sent for a scoped list, empty string included: the handler reads an
    // absent `service` as "leave it alone" and an empty one as "clear the tag",
    // and clearing is a real thing a person does on this form.
    if (serviceScoped) {
      payload.service = serviceCode;
    }
    // DEF-RAT-10220 — sent as typed (a string, never a float) whenever the
    // field is drawn; the server refuses blank, zero and a fifth decimal.
    if (capacityUom !== null) {
      payload.capacity = capacity.trim();
    }
    // CR-162-BRC10 — never sent blank (the schema has already refused that,
    // and the server would too).
    if (accountKind && accountKindAnswer !== "") {
      payload.account_kind = accountKindAnswer;
    }
    // CR-187-BRC10 — always sent on the work-priority card; never blank.
    if (pushKind) {
      payload.push_kind = pushKindAnswer;
    }
    // CR-161-BRC10 W4 — ALWAYS sent from this dialog for an area (`{}`
    // included): the server reads the key as "typed on the area form", so a
    // required field binds here and never on the seeder or the sweep.
    if (isAreas) {
      payload.custom_data = entry === null ? customData : customDataChanges(storedCustomData, customData);
    }
    try {
      const saved =
        entry === null
          ? await createLookupEntry(card.code, payload, props.client)
          : await updateLookupEntry(card.code, entry.id, payload, props.client);
      props.onSaved(saved, entry === null);
      return { ok: true };
    } catch (error) {
      // BR-TEN-031: the OWNING module's validation comes back as field errors
      // in the B12 §3 envelope and lands under the offending input.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  // DEF-TEN-4478 — the title FOLLOWS the chooser. "Add to Areas & sub-areas" is
  // true of both halves of this card and therefore tells a person nothing about
  // which one they are making; "Add a sub-area" is the whole point.
  const genericTitleKey =
    entry === null ? "settings.reference.addTitle" : "settings.reference.editTitle";
  // The narrowing is written INSIDE each expression rather than hoisted into a
  // `const isSub = levels !== undefined && level === "sub"`: a boolean does not
  // carry the narrowing, so every read of a `levels.*` key behind one would need
  // a non-null assertion, and an assertion is a claim no compiler is checking.
  const parentRequirement =
    levels !== undefined && level === "sub" ? { message: t(levels.parentRequiredKey) } : undefined;
  // The picker's four keys resolved ONCE, from whichever tree this card is —
  // rather than four `??` chains ending in `""`, which would draw an unlabelled
  // control instead of failing. `undefined` here means "do not draw it at all",
  // which for a self-parented card is what the *Area* segment means.
  const parentPicker: {
    labelKey: string;
    placeholderKey: string;
    noneAvailableKey: string;
    helpKey?: string;
  } | undefined =
    parentList !== undefined
      ? {
          labelKey: parentList.labelKey,
          placeholderKey: parentList.placeholderKey,
          noneAvailableKey: parentList.noneAvailableKey,
          helpKey: parentList.helpKey,
        }
      : levels !== undefined && level === "sub"
        ? {
            labelKey: levels.parentLabelKey,
            placeholderKey: levels.parentPlaceholderKey,
            noneAvailableKey: levels.parentNoneAvailableKey,
          }
        : undefined;
  const levelTitleKey =
    levels === undefined
      ? undefined
      : entry === null
        ? level === "sub"
          ? levels.addSubTitleKey
          : levels.addTopTitleKey
        : level === "sub"
          ? levels.editSubTitleKey
          : levels.editTopTitleKey;

  return (
    <FormModal
      title={
        levelTitleKey === undefined
          ? t(genericTitleKey, { list: t(card.labelKey) })
          : t(levelTitleKey)
      }
      kicker={t(`settings.reference.owner.${card.owner}`)}
      schema={lookupSchema(t, parentRequirement, accountKind)}
      values={{
        code,
        name,
        detail,
        parent_code: parentCode,
        service: serviceCode,
        account_kind: accountKindAnswer,
        capacity,
      }}
      submitLabel={t(
        entry === null ? "settings.reference.addSubmit" : "settings.reference.editSubmit",
      )}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* DEF-TEN-4478 — the answer to *"there is not differnt whether Im
          addding area or sub areas"*: the choice is a CONTROL, above the fields
          it governs, and the title above it moves with it. It replaces the help
          sentence that used to explain what leaving a dropdown blank meant —
          B14 rule 32, one fewer sentence rather than one more.
          It is FIRST because it governs everything under it — a person who
          reads the fields before the question has already started filling
          in a form whose shape has not been decided. */}
      {levels !== undefined && (
        <SegmentedField
          id="level"
          label={t(levels.chooseKey)}
          value={level}
          options={[
            { value: "top", label: t(levels.topKey) },
            { value: "sub", label: t(levels.subKey) },
          ]}
          onChange={(chosen) => setLevel(chosen === "sub" ? "sub" : "top")}
        />
      )}
      {/* DEF-TEN-4478 — a lookup CODE is a record identifier, never a fact
          about the person filling the form, so there is nothing here a browser
          profile could correctly know. Refusing the fill by name is the only
          half of that defect the app can prevent rather than survive. */}
      <TextField
        id="code"
        label={t("settings.reference.col.code")}
        value={code}
        onChange={setCode}
        required
        autoComplete="off"
        // BR-TEN-030: read-only once used, with the reason beside it.
        help={frozen ? t("settings.reference.codeFrozen", { count: entry.used_by }) : undefined}
        placeholder={frozen ? undefined : t("settings.reference.codePlaceholder")}
      />
      <TextField
        id="name"
        label={t("settings.reference.col.name")}
        value={name}
        onChange={setName}
        required
        autoComplete="off"
      />
      {/* BR-MET-066b · DEF-221 — only top-level rows are offered: the server
          refuses a grandchild by name and offering the choice anyway is a
          control that lies. Depth stays enforced in ONE place, the server.
          DEF-TEN-4478: on a self-parented list this is drawn only under the SUB
          segment, where it is the one thing still to say — so it no longer has
          to explain that its own blank means something else. */}
      {parentPicker !== undefined && (
        <SelectField
          id="parent_code"
          label={t(parentPicker.labelKey)}
          value={parentCode}
          placeholder={t(parentPicker.placeholderKey)}
          options={parentOptions.map((row) => ({ value: row.code, label: row.name }))}
          onChange={setParentCode}
          // True of BOTH trees now: a cross-list row has always needed a parent
          // (`customers.lookups.parent_required`) and a row drawn under the SUB
          // segment has just said it is one. The mark is the promise the schema
          // and the server both keep.
          required
          help={
            parentOptions.length === 0
              ? t(parentPicker.noneAvailableKey)
              : parentPicker.helpKey === undefined
                ? undefined
                : t(parentPicker.helpKey)
          }
        />
      )}
      {/* CR-065 — blank is a real answer and the placeholder says which one it
          is: an untagged size shows on EVERY service's rate schedule, which is
          how every one of them behaved before this list carried a tag. */}
      {serviceScoped && (
        <SelectField
          id="service"
          label={t("settings.reference.col.service")}
          value={serviceCode}
          placeholder={t("settings.reference.serviceNone")}
          options={serviceOptions.map((row) => ({ value: row.service, label: row.name }))}
          onChange={setServiceCode}
          help={t("settings.reference.serviceHelp")}
        />
      )}
      {capacityUom !== null && (
        <SizeClassCapacityField uom={capacityUom} value={capacity} onChange={setCapacity} t={t} />
      )}
      {accountKind && (
        <div data-field="account_kind">
          <SegmentedField
            id="account_kind"
            label={t("settings.reference.col.accountKind", { defaultValue: "Account type" })}
            value={accountKindAnswer}
            required
            options={[
              {
                value: "master",
                label: t("settings.reference.accountKind.master", { defaultValue: "Master account" }),
              },
              {
                value: "regular",
                label: t("settings.reference.accountKind.regular", {
                  defaultValue: "Regular account",
                }),
              },
            ]}
            onChange={setAccountKindAnswer}
          />
          {entry !== null && (
            <p className="m-0 mt-1 text-sm text-neutral-700" data-account-kind-note="">
              {t("settings.reference.accountKind.fromNowOn", {
                defaultValue: "Applies to new premises only.",
              })}
            </p>
          )}
        </div>
      )}
      {pushKind && (
        <div data-field="push_kind">
          <SegmentedField
            id="push_kind"
            label={t("settings.reference.col.pushKind", { defaultValue: "Phone alert" })}
            value={pushKindAnswer}
            options={PUSH_KINDS.map((kind) => ({
              value: kind,
              label: t(`settings.reference.pushKind.${kind}`, { defaultValue: kind }),
            }))}
            onChange={setPushKindAnswer}
          />
        </div>
      )}
      {detailField !== undefined && card.codeNameOnlyKey === undefined && (
        <TextField
          id={detailField.field}
          label={t(detailField.labelKey)}
          value={detail}
          onChange={setDetail}
          // The allowed values are the OWNING module's law (BR-TEN-031); its
          // refusal names them in the envelope params rather than this screen
          // keeping a second, drifting copy of the choice set.
          help={t("settings.reference.detailHelp")}
        />
      )}
      {/* charge codes / tax jurisdictions: the owner accepts code + name and
          refuses everything else, so the detail column is READ-only here and
          the modal says where its value is set (S12 / S13). */}
      {card.codeNameOnlyKey !== undefined && (
        <p className="field-help">{t(card.codeNameOnlyKey)}</p>
      )}
      {/* CR-161-BRC10 W4 — the utility's OWN area fields. Nothing at all when
          none is placed on this dialog; a refusal lands under its control
          through FormModal's `custom_data.<key>` path. */}
      {isAreas && (
        <CustomFieldsInput
          entity="areas"
          screen="AREA_FORM"
          values={customData}
          onChange={setCustomData}
          client={props.client}
        />
      )}
    </FormModal>
  );
}

// ── S63 Holiday calendar — a RULE card in the SAME frame (BR-SHL-035) ──────

function HolidayCalendarView(props: {
  readOnly: boolean;
  client: ApiClient;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Holiday | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const holidaysQuery = useQuery({
    queryKey: queryKeys.holidays,
    queryFn: () => getHolidays(props.client),
  });

  const removeHoliday = useMutation({
    mutationFn: (holiday: Holiday) => deleteHoliday(holiday.id, props.client),
    onSuccess: (_void, holiday) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.holidays });
      // The close-by date is computed from the holiday set (BR-TEN-022).
      void queryClient.invalidateQueries({ queryKey: queryKeys.regionalSettings });
      setPendingDelete(null);
      fireToast(t("settings.reference.holidays.removed", { label: holiday.label }));
    },
    onError: (error: unknown) => {
      setPendingDelete(null);
      setRefusal(refusalOf(error, t));
    },
  });

  if (holidaysQuery.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  if (holidaysQuery.data === undefined) {
    if (isPermissionDenied(holidaysQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.reference.failedTitle")}
        reason={apiErrorText(holidaysQuery.error, t)}
        onRetry={() => void holidaysQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void holidaysQuery.refetch()}
      />
    );
  }

  const holidays = holidaysQuery.data;

  return (
    <>
      <div className="settings-frame-toolbar">
        <Button
          variant="primary"
          disabled={props.readOnly}
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => setAdding(true)}
        >
          {t("settings.reference.holidays.add")}
        </Button>
      </div>

      <RefusalNotice refusal={refusal} />

      {holidays.length === 0 ? (
        <Note>{t("settings.reference.holidays.empty")}</Note>
      ) : (
        <table className="settings-table">
          <thead>
            <tr>
              <th>{t("settings.reference.holidays.date")}</th>
              <th>{t("settings.reference.holidays.label")}</th>
              <th>{t("settings.reference.col.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {holidays.map((holiday) => (
              <tr key={holiday.id}>
                <td>
                  {/* BR-SHL-034: every displayed date goes through DateCell. A
                      holiday is a CALENDAR date, so no timezone shifts it. */}
                  <DateCell value={holiday.date} timeZone="UTC" dateFormat={props.dateFormat} />
                </td>
                <td>{holiday.label}</td>
                <td>
                  <Button
                    variant="ghost"
                    className="settings-danger"
                    disabled={props.readOnly}
                    title={props.readOnly ? t("settings.readOnlyReason") : undefined}
                    onClick={() => setPendingDelete(holiday)}
                  >
                    {t("settings.reference.delete")}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {adding && (
        <HolidayModal
          client={props.client}
          dateFormat={props.dateFormat}
          onClose={() => setAdding(false)}
          onSaved={(holiday) => {
            setAdding(false);
            void queryClient.invalidateQueries({ queryKey: queryKeys.holidays });
            void queryClient.invalidateQueries({ queryKey: queryKeys.regionalSettings });
            fireToast(t("settings.reference.holidays.added", { label: holiday.label }));
          }}
        />
      )}

      {pendingDelete !== null && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): remove a holiday.
          confirmVariant="danger"
          title={t("settings.reference.holidays.removeTitle", { label: pendingDelete.label })}
          consequence={t("settings.reference.holidays.removeBody")}
          confirmLabel={t("settings.reference.holidays.removeAction")}
          working={removeHoliday.isPending}
          onConfirm={() => removeHoliday.mutate(pendingDelete)}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </>
  );
}

function HolidayModal(props: {
  client: ApiClient;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onSaved: (holiday: Holiday) => void;
}) {
  const { t } = useTranslation();
  const [date, setDate] = useState("");
  const [label, setLabel] = useState("");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const saved = await createHoliday({ date, label: label.trim() }, props.client);
      props.onSaved(saved);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("settings.reference.holidays.addTitle")}
      kicker={t("settings.reference.owner.tenancy")}
      schema={holidaySchema(t)}
      values={{ date, label }}
      submitLabel={t("settings.reference.holidays.addSubmit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* BR-SHL-033: a date field is always a DATE PICKER with manual entry. */}
      <DatePickerField
        id="date"
        label={t("settings.reference.holidays.date")}
        value={date}
        onChange={setDate}
        dateFormat={props.dateFormat}
        required
      />
      <TextField
        id="label"
        label={t("settings.reference.holidays.label")}
        value={label}
        onChange={setLabel}
        required
      />
    </FormModal>
  );
}

/** Exported for the packet's tests: how many cards the ONE list view serves. */
export const REFERENCE_CARD_COUNT = REFERENCE_CARDS.length;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07; co-stories US-TEN-010/011@178c282; co-packet EP-MET-04@34f14b6 for S64's field law)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-09 by story-coder (frontend integration lane: rule pages become forms in this same frame; the four dark catalog cards render through this same list view) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane) · AMENDED 2026-08-17 by story-coder (CR-004 task A3 — `serviceScopeText` + the third column in `lookupTableConfig`, drawn only for a card that declares `serviceScoped`; three states, because ABSENT and `null` are different facts)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E3 account statuses/types still have no `GET /lookups` card (the customers module owns no tables) — those cards state that instead of faking entries · E4 [CLOSED 2026-09-05, DEF-SHL-3964] the tenant's date format IS served to screens now — `ShellWithSession` publishes it and `useRegional` reads it, so the S63 calendar renders the tenant's own format and the seed fallback that used to sit here is gone · E3 `tax_jurisdictions` cannot be deactivated at all (no active column on the owning table): the control renders disabled WITH the server's own reason and the view states it — the backend reported the missing column, this lane does not invent a workaround · E4 charge codes / tax jurisdictions accept CODE + NAME only, so their detail column is read-only in the list and absent from the modal — the money fields belong to S12/S13 and are refused as unknown by the owner
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
