// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 · AMENDMENT 1 — S64 "Read validation & estimation rules"
//           becomes a real page, per utility service (PO 2026-08-26, verbatim:
//           "we will ahev to set these rules in settings and take it from
//           there, we will provide default value to start with on all these
//           rules").   Screens: S64 (Settings → Reference data)
// Rules:    BR-MET-020 (no threshold hardcoded; a missing figure is SKIPPED
//           AND REPORTED — this screen renders that state honestly, never as
//           a zero) · BR-MET-025/026/027/052 (the figures' own rules) ·
//           BR-SHL-035 (same Reference-data frame; only the BODY differs) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH its reason)
//           · B14 rule 21 (Tailwind utilities — NO new stylesheet class; the
//           shared Panel/SaveBar/field kit carry their own declared classes) ·
//           CLAUDE.md rule 2 (decimals are STRINGS end to end; stored 6dp
//           rides the wire, display trims) · rule 3 (a floor carries its unit)
// Tests:    SettingsReadValidation.test.tsx
// Impacts:  GET /settings/read-validation · PUT /settings/read-validation ·
//           PUT /settings/read-validation/{service} (metering-served since
//           CR-038 A1; the flat tenancy family the old S64 form wrote never
//           reached the engine)
// ───────────────────────────────────────────────────────
//
// THE THREE HONESTY STATES, drawn per service (the server's `source`):
//  · "service"          — the service's own figures; editing saves ITS row.
//  · "tenant_fallback"  — electric/water with no row yet: the tenant-wide
//    figures govern, the panel says so, and saving gives the service its own.
//  · "none"             — no figure anywhere. The panel says "skipped and
//    reported" in as many words and offers the full form — every field
//    required, because the server has no ratified default to merge with.
//
// The INTEGRITY rules are listed and visibly locked with the sentence why: a
// utility cannot switch off "the meter must exist" or "a reading cannot run
// backwards". The list is SERVED (validation.INTEGRITY_RULES), so this screen
// and the engine cannot disagree about what is beyond editing.
//
// FORM VALIDATION here refuses nonsense the client can know structurally —
// hard bounds must contain flag bounds, percentages above zero, floors not
// negative — and the SERVER refuses the same and more (it is the authority;
// its refusals render under the fields from the B12 §3 envelope).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getMeteredServices,
  getReadValidationSettings,
  saveReadValidationGeneral,
  saveReadValidationService,
} from "@/api/endpoints";
import type {
  ReadValidationOverview,
  ReadValidationServiceEntry,
  RuleSwitches,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { CheckboxField, SelectField, TextField, envelopeErrors } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";

import { Disclosure } from "@/components/Disclosure";

import { ServiceTags } from "../rating/ratingShared";
import {
  Panel,
  RefusalNotice,
  SaveBar,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal } from "./settingsShared";

// ── pure pieces (provable without a browser) ───────────────────────────────

/** The S64 overview's ONE query key — invalidated after every panel save. */
export function readValidationKey(): readonly unknown[] {
  return queryKeys.rulePage("read-validation");
}

/**
 * "200.000000" → "200", "3.500000" → "3.5", "0.125000" → "0.125".
 * The wire carries the STORED 6dp scale (CLAUDE.md rule 2); an EDITOR shows
 * the same number without the noise. Pure string surgery — nothing here ever
 * becomes a float, and a value that is not a plain decimal passes untouched.
 */
export function trimDecimalString(value: string): string {
  if (!/^-?\d+\.\d+$/.test(value)) {
    return value;
  }
  return value.replace(/0+$/, "").replace(/\.$/, "");
}

/** Numeric equality for DIRTY detection only, as strings ("250" == "250.000"). */
export function sameFigure(a: string, b: string): boolean {
  return trimDecimalString(a.trim()) === trimDecimalString(b.trim());
}

/** The editable field set, in the order the panel draws them. */
export const SERVICE_FIGURE_FIELDS = [
  "high_pct",
  "high_abs_value",
  "high_abs_unit",
  "low_pct",
  "zero_scope",
  "days_flag_min",
  "days_flag_max",
  "days_hard_min",
  "days_hard_max",
  "mismatch_pct",
  "tou_sum_tolerance_pct",
] as const;

export type ServiceDraft = Record<(typeof SERVICE_FIGURE_FIELDS)[number], string>;

export const ZERO_SCOPES = ["active_non_vacant", "all", "off"] as const;

/**
 * CR-079 — THE SEVEN ESTIMATION METHODS, in the order the PO named them.
 *
 * PO 2026-09-07, verbatim: *"this should be drop down options - give 4 to 5
 * options here"*, then *"we are good with these + add last 6 month avg + Use
 * avg from plan"*. Until that day `est_method` accepted exactly one value and
 * this field was a read-only box carrying a sentence about our own decision
 * process — B14 rule 32's clearest breach on the product.
 *
 * ⚠ **`trailing_3_daily_avg` IS FIRST AND STAYS THE DEFAULT.** Changing how a
 * missing reading is estimated changes what a customer is billed, so it has to
 * be a choice somebody makes and never a side effect of a release. Nothing
 * migrates an existing tenant's row.
 *
 * ⚠ **TWO OF THE SEVEN HAVE NOTHING TO READ AND SAY SO** (`unavailable`).
 * `route_peer_average` needs a definition of a peer group that nobody has
 * given (OQ-MET-1761) and `plan_average` needs an average held on a rate plan,
 * which this product does not store (OQ-MET-1762). They are OFFERED, because
 * the PO ruled them in, and they are NOT SELECTABLE, because an admin picking
 * one would stop every estimate on the tenant — BR-SHL-025's posture exactly:
 * the control is disabled and it carries its reason.
 */
export const EST_METHODS = [
  { code: "trailing_3_daily_avg" },
  { code: "trailing_6_daily_avg" },
  { code: "trailing_12_daily_avg" },
  { code: "same_period_last_year" },
  { code: "repeat_last_actual" },
  { code: "route_peer_average", unavailable: true },
  { code: "plan_average", unavailable: true },
] as const;

export const EST_METHOD_CODES: readonly string[] = EST_METHODS.map((m) => m.code);

/**
 * The seeded default, and the one nothing moves (`CR-079`).
 *
 * ⚠ **THE SCREEN DOES NOT FALL BACK TO IT** — a tenant with no settings row
 * shows NO method, because the engine estimates nothing for such a tenant and a
 * screen that named a method would disagree with it silently. This constant is
 * what a NEW row is created with, on the server; it is exported so a test can
 * assert the default has not moved rather than trusting a string in a fixture.
 */
export const DEFAULT_EST_METHOD = "trailing_3_daily_avg";

/** The tenant-wide estimation panel's editable set. */
export interface GeneralDraft {
  est_method: string;
  est_max_consecutive: string;
}

/** True when the tenant's stored method is one this product can actually run. */
export function estMethodRunnable(code: string): boolean {
  return EST_METHODS.some((m) => m.code === code && !("unavailable" in m && m.unavailable));
}

/**
 * BR-MET-136 (PO 2026-08-26, verbatim: *"yes every rule that is enabled always
 * run - you ahve to keep default - all enabled"*): the switches this panel
 * SENDS — only the rules whose state actually moved.
 *
 * A partial change set, exactly like the figures above, for the same reason:
 * the server MERGES it, so naming one rule never re-enables the twelve the
 * admin did not touch. An empty result means "no switch moved" and the caller
 * omits the key entirely rather than sending `{}`, which would read as a
 * change to nothing and is one more thing for the server to decide about.
 */
export function switchChanges(draft: RuleSwitches, original: RuleSwitches): RuleSwitches {
  const out: RuleSwitches = {};
  for (const rule of Object.keys(draft)) {
    if (draft[rule] !== original[rule]) {
      out[rule] = draft[rule];
    }
  }
  return out;
}

/** True when any switch differs — half of the panel's DIRTY test. */
export function switchesMoved(draft: RuleSwitches, original: RuleSwitches): boolean {
  return Object.keys(switchChanges(draft, original)).length > 0;
}

/** The draft a panel opens with — the served figures, trimmed for editing. */
export function draftFromEntry(entry: ReadValidationServiceEntry): ServiceDraft {
  if (entry.source === "none") {
    const empty = Object.fromEntries(SERVICE_FIGURE_FIELDS.map((f) => [f, ""])) as ServiceDraft;
    empty.high_abs_unit = entry.unit_hint ?? "";
    empty.zero_scope = "";
    return empty;
  }
  return {
    high_pct: trimDecimalString(entry.high_pct),
    high_abs_value: trimDecimalString(entry.high_abs_value),
    high_abs_unit: entry.high_abs_unit,
    low_pct: trimDecimalString(entry.low_pct),
    zero_scope: entry.zero_scope,
    days_flag_min: String(entry.days_flag_min),
    days_flag_max: String(entry.days_flag_max),
    days_hard_min: String(entry.days_hard_min),
    days_hard_max: String(entry.days_hard_max),
    mismatch_pct: trimDecimalString(entry.mismatch_pct),
    tou_sum_tolerance_pct: trimDecimalString(entry.tou_sum_tolerance_pct),
  };
}

type Translator = (key: string, params?: Record<string, unknown>) => string;

/**
 * The structural nonsense this form refuses BEFORE asking the server (which
 * refuses it again — BR-SHL-025's defense in depth, pointed the other way):
 * percentages above zero, floors not negative, low within (0, 100], day
 * bounds at least 1, each window a real window, and the HARD window
 * containing the flag window. Returns per-field messages; empty = submit.
 */
export function serviceDraftProblems(draft: ServiceDraft, t: Translator): Record<string, string> {
  const problems: Record<string, string> = {};
  const num = (field: keyof ServiceDraft): number | null => {
    const raw = draft[field].trim();
    if (raw === "" || !/^-?\d+(\.\d+)?$/.test(raw)) {
      if (raw !== "") {
        problems[field] = t("metering.read_validation.bad_number");
      }
      return null;
    }
    return Number(raw); // comparison only — the STRING is what ships (rule 2)
  };
  const highPct = num("high_pct");
  if (highPct !== null && highPct <= 0) {
    problems.high_pct = t("metering.read_validation.pct_positive");
  }
  const touPct = num("tou_sum_tolerance_pct");
  if (touPct !== null && touPct <= 0) {
    problems.tou_sum_tolerance_pct = t("metering.read_validation.pct_positive");
  }
  const floor = num("high_abs_value");
  if (floor !== null && floor < 0) {
    problems.high_abs_value = t("metering.read_validation.floor_negative");
  }
  const mismatch = num("mismatch_pct");
  if (mismatch !== null && mismatch < 0) {
    problems.mismatch_pct = t("metering.read_validation.floor_negative");
  }
  const lowPct = num("low_pct");
  if (lowPct !== null && (lowPct <= 0 || lowPct > 100)) {
    problems.low_pct = t("metering.read_validation.low_pct_range");
  }
  const days = {
    days_flag_min: num("days_flag_min"),
    days_flag_max: num("days_flag_max"),
    days_hard_min: num("days_hard_min"),
    days_hard_max: num("days_hard_max"),
  };
  for (const [field, value] of Object.entries(days)) {
    if (value !== null && (value < 1 || !Number.isInteger(value))) {
      problems[field] = t("metering.read_validation.days_min_one");
    }
  }
  const { days_flag_min, days_flag_max, days_hard_min, days_hard_max } = days;
  if (days_flag_min !== null && days_flag_max !== null && days_flag_min >= days_flag_max) {
    problems.days_flag_max ??= t("settings.read_validation.day_window_inverted", {
      min: days_flag_min,
      max: days_flag_max,
    });
  }
  if (days_hard_min !== null && days_hard_max !== null && days_hard_min >= days_hard_max) {
    problems.days_hard_max ??= t("settings.read_validation.day_window_inverted", {
      min: days_hard_min,
      max: days_hard_max,
    });
  }
  if (
    days_flag_min !== null &&
    days_flag_max !== null &&
    days_hard_min !== null &&
    days_hard_max !== null &&
    !problems.days_flag_max &&
    !problems.days_hard_max &&
    (days_hard_min > days_flag_min || days_hard_max < days_flag_max)
  ) {
    problems.days_flag_min = t("settings.read_validation.soft_outside_hard", {
      soft: `${days_flag_min}–${days_flag_max}`,
      hard: `${days_hard_min}–${days_hard_max}`,
    });
  }
  return problems;
}

/** What a save sends: the CHANGED fields for an existing row, EVERYTHING for
 *  a create (the server requires the full set — no ratified default exists).
 *  Ints go as numbers, decimals as the typed strings (rule 2). */
export function serviceChanges(
  draft: ServiceDraft,
  original: ServiceDraft | null,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of SERVICE_FIGURE_FIELDS) {
    const value = draft[field].trim();
    if (original !== null && sameFigure(value, original[field])) {
      continue;
    }
    if (field.startsWith("days_")) {
      out[field] = Number.parseInt(value, 10);
    } else {
      out[field] = value;
    }
  }
  return out;
}

// ── the view ───────────────────────────────────────────────────────────────

export interface ReadValidationRulesViewProps {
  readOnly: boolean;
  client?: ApiClient;
}

export function ReadValidationRulesView(props: ReadValidationRulesViewProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;

  const overviewQuery = useQuery({
    queryKey: readValidationKey(),
    queryFn: () => getReadValidationSettings(client),
  });

  // ── DEF-901: DOES THIS TENANT ACTUALLY METER THIS SERVICE? ──────────────
  // PO, on the live app: *"are these settings applicable to sewer"*. They were
  // not. This page drew a full threshold form per ENABLED service, and sewer
  // is priced as a percentage of the water usage charge (BR-RAT-015) and reads
  // no register at all — a high-use threshold, a days window, a zero-read rule
  // and a `Save Sewer thresholds` button, all of it configuration that can
  // never fire. Trash is the same shape: a flat per-cart charge, no meters.
  //
  // ⚠ **THE TEST IS THE TENANT'S OWN ESTATE, NEVER THE SERVICE CODE**
  // (BR-TEN-162). A utility that genuinely meters sewer exists, and on that
  // tenant `sewer` comes back in this list and the form appears. A hard-coded
  // set of "unmetered services" would be right on today's demo tenant and
  // wrong on the first customer who buys a sewer meter, with nothing objecting.
  //
  // A SEPARATE QUERY and not a field on the overview: the estate is the ASSET
  // module's fact, `apps/metering` does not own it, and keying it under
  // ["assets"] means fitting a meter invalidates it while saving a threshold
  // does not.
  const meteredQuery = useQuery({
    queryKey: queryKeys.meteredServices,
    queryFn: () => getMeteredServices(client),
  });

  if (overviewQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  if (overviewQuery.data === undefined) {
    if (isPermissionDenied(overviewQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />; // A18 §6
    }
    return (
      <FailedWithRetry
        title={t("settings.rules.failedTitle")}
        reason={apiErrorText(overviewQuery.error, t)}
        onRetry={() => void overviewQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void overviewQuery.refetch()}
      />
    );
  }
  const overview = overviewQuery.data;
  // BR-TEN-162 clause 3 — FAIL TOWARD SHOWING. `undefined` covers both "still
  // loading" and "the probe failed", and both mean the same thing here: we do
  // not know, so every form is drawn. Hiding configuration a tenant needs is
  // the expensive direction; showing configuration it does not need is noise.
  const metered = meteredQuery.data;

  // ── DEF-MET-4480 · THE PAGE IS SPLIT BEFORE IT IS DRAWN ─────────────────
  // A service the tenant METERS gets its threshold form. A service it sells
  // and does not meter gets NAMED on one shared line (see `UnmeteredLine`).
  // Nothing is silently dropped: every entry the server sent appears in
  // exactly one of the two, which is what `data-service-listed` lets a
  // walkthrough prove without reading our source.
  const isMetered = (code: string): boolean =>
    metered === undefined || metered.includes(code);
  const withMeters = overview.services.filter((entry) => isMetered(entry.service));
  const withoutMeters = overview.services.filter((entry) => !isMetered(entry.service));

  return (
    // `.settings-tab`'s own three declarations, as utilities (B14 r21: this
    // lane's new UI references no stylesheet class, not even a declared one).
    <div className="flex flex-col gap-4">
      {/* B14 rule 32 — ONE sentence for the page. It carried two until
          DEF-MET-4479; the second ("a reading already judged keeps the figures
          it was judged by") is true and is not what a clerk opens this screen
          to find out. */}
      <p className="max-w-measure text-sm text-neutral-700">
        {t("metering.readValidation.lede")}
      </p>

      <IntegrityPanel rules={overview.integrity_rules} />

      {/* ── DEF-MET-4480 · THE SILENCE, CLOSED ────────────────────────────
          REPRODUCED IN A BROWSER 2026-09-07: with no service switched on,
          `services` is `[]`, the map below draws nothing, and the page ends
          after the integrity chips looking finished. The Product Owner caught
          it only because they had seen the complete page minutes earlier.
          An empty list is a FACT about the tenant, so it is stated. */}
      {overview.services.length === 0 && (
        <Panel title={t("metering.readValidation.noServices.title")}>
          <p data-no-services="true" className="max-w-measure text-sm text-neutral-700">
            {t("metering.readValidation.noServices.body")}
          </p>
        </Panel>
      )}

      {withMeters.map((entry, index) => (
        <ServicePanel
          key={entry.service}
          entry={entry}
          // ⚠ THE FIRST SERVICE LANDS OPEN, THE REST COLLAPSED (DEF-900).
          // A tenant selling ten services otherwise opens on ten full
          // threshold forms — fourteen inputs each — and the one a clerk came
          // for is somewhere below nine they did not. Landing on ONE open
          // panel shows the shape of the page without making it a wall; the
          // rest are one click each.
          defaultOpen={index === 0}
          integrityRules={overview.integrity_rules}
          judgmentRules={overview.judgment_rules}
          readOnly={props.readOnly}
          client={client}
        />
      ))}

      <UnmeteredLine services={withoutMeters.map((entry) => entry.service)} />

      <GeneralPanel general={overview.general} readOnly={props.readOnly} client={client} />
    </div>
  );
}

// ── DEF-901, REGROUPED · the services with no meter, on ONE line ───────────
//
// DEF-901 gave every unmetered service its own collapsed panel carrying two
// sentences — *"You have no Sewer meters, so no Sewer reading is ever taken
// and these checks would never run. Fit a Sewer meter to a unit and this
// section fills in by itself."* — and that was right about the ABSENCE and
// wrong about the WEIGHT. A tenant selling eleven services and metering two
// got nine near-identical paragraphs, which is noise wearing honesty's
// clothes; B14 rule 32 asks for one sentence per section and a stated absence
// CLOSED by default, and nine open ones is the opposite of that.
//
// ⚠ **BR-TEN-162 CLAUSE 2 IS NOT WEAKENED — EVERY SERVICE IS STILL NAMED.**
// The clause exists because a silently missing section is indistinguishable
// from a broken page, and DEF-MET-4480 is that failure happening for real. So
// each service keeps its own `data-service-listed` marker here, and the
// walkthrough asserts the whole enabled set appears on the page one way or the
// other.
function UnmeteredLine(props: { services: readonly string[] }) {
  const { t } = useTranslation();
  if (props.services.length === 0) {
    return null;
  }
  return (
    <div
      data-unmetered-line="true"
      className="flex flex-col gap-1 border-t border-t-divider pt-4"
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {props.services.map((code) => (
          // The NAME is visible, not a tooltip on a letter — a clerk has to be
          // able to read which of their services this is about. `ServiceTags`
          // supplies the badge; the word beside it is this page's own.
          <span
            key={code}
            data-service-listed={code}
            data-metered="false"
            className="inline-flex items-center gap-1.5 text-sm text-neutral-700"
          >
            <ServiceTags services={[code]} />
            {t(`rating.service.${code}`, { defaultValue: code })}
          </span>
        ))}
      </div>
      {/* B14 rule 32 — ONE sentence for this stated absence, whether it covers
          one service or nine. DEF-901 wrote two sentences PER service. */}
      <p className="max-w-measure text-sm text-neutral-700">
        {t("metering.readValidation.notMetered.line")}
      </p>
    </div>
  );
}

// ── the locked integrity list ──────────────────────────────────────────────

function IntegrityPanel(props: { rules: string[] }) {
  const { t } = useTranslation();
  return (
    <Panel
      title={t("metering.readValidation.integrity.title")}
      hint={t("metering.readValidation.integrity.hint")}
    >
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {props.rules.map((rule) => (
          <li
            key={rule}
            data-integrity-rule={rule}
            className="inline-flex items-center gap-1.5 border border-divider px-2 py-1 text-sm text-neutral-700"
          >
            <span>{t(`metering.reads.status.${rule}`, { defaultValue: rule })}</span>
            {/* the lock is STATED, per rule, not merely implied by a missing
                input (BR-SHL-025's disabled-with-reason posture) */}
            <span className="text-xs uppercase tracking-wide text-neutral-600">
              {t("metering.readValidation.integrity.locked")}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── one service's thresholds ───────────────────────────────────────────────

function ServicePanel(props: {
  defaultOpen?: boolean;
  entry: ReadValidationServiceEntry;
  integrityRules: string[];
  judgmentRules: string[];
  readOnly: boolean;
  client: ApiClient;
}) {
  const { t } = useTranslation();
  const { entry } = props;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const serviceName = t(`rating.service.${entry.service}`, { defaultValue: entry.service });
  const isCreate = entry.source === "none";
  const original = isCreate ? null : draftFromEntry(entry);

  const [edits, setEdits] = useState<ServiceDraft | null>(null);
  const [creating, setCreating] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const draft = edits ?? original ?? draftFromEntry(entry);

  // BR-MET-136: the switch draft is SEPARATE state from the figure draft
  // because the two are independently dirty — an admin may turn a check off
  // without touching a single number, and that save must still be offered.
  const servedSwitches = entry.rule_enabled;
  const [switchEdits, setSwitchEdits] = useState<RuleSwitches | null>(null);
  const switches = switchEdits ?? servedSwitches;

  const save = useMutation({
    mutationFn: (changes: Record<string, unknown>) =>
      saveReadValidationService(entry.service, changes, props.client),
    onSuccess: () => {
      setEdits(null);
      setSwitchEdits(null);
      setCreating(false);
      setFieldErrors({});
      setRefusal(null);
      fireToast(t("metering.readValidation.saved", { service: serviceName }));
      // The PUT returns one service's row; the page is the whole picture —
      // re-read it rather than hand-stitch the cache.
      void queryClient.invalidateQueries({ queryKey: readValidationKey() });
    },
    onError: (error: unknown) => {
      if (isApiError(error)) {
        const mapped = envelopeErrors(formErrorEnvelope(error), (key, params) => t(key, params));
        setFieldErrors(mapped.fields);
      }
      setRefusal(refusalOf(error, t));
    },
  });

  // ⚠ **HOISTED SO A COLLAPSED PANEL CAN SAY IT HAS UNSAVED EDITS.**
  // Every save on this page is PER SERVICE — `PUT /settings/read-validation/
  // {service}` — so "Save Water thresholds" saves water and nothing else, and
  // an edit made in another panel is neither saved nor lost: that panel keeps
  // its own draft and its own Save button. What the page did NOT do was say
  // so. `Disclosure` unmounts a closed body, so collapsing a panel with edits
  // in it took the Save button away with the edits and left no sign either
  // existed. The header carries the word now (see `status` below).
  const dirty =
    isCreate ||
    switchesMoved(switches, servedSwitches) ||
    SERVICE_FIGURE_FIELDS.some(
      (field) => original !== null && !sameFigure(draft[field], original[field]),
    );

  function patch(field: keyof ServiceDraft, value: string): void {
    setEdits({ ...draft, [field]: value });
  }

  function toggleRule(rule: string, enabled: boolean): void {
    setSwitchEdits({ ...switches, [rule]: enabled });
  }

  function submit(): void {
    setRefusal(null);
    const problems = serviceDraftProblems(draft, (key, params) => t(key, params));
    if (isCreate) {
      for (const field of SERVICE_FIGURE_FIELDS) {
        if (draft[field].trim() === "") {
          problems[field] ??= t("metering.read_validation.create_incomplete");
        }
      }
    }
    setFieldErrors(problems);
    if (Object.keys(problems).length > 0) {
      return;
    }
    // BR-MET-136: only the switches that MOVED travel, on a create as much as
    // on an update. The served map is all-on for an unconfigured service, so
    // `moved` is exactly the checks this admin turned OFF — and the key is
    // omitted entirely when there are none. Sending the full map instead would
    // write thirteen explicit `true`s into the row: choices nobody made,
    // indistinguishable in storage from choices somebody did.
    const moved = switchChanges(switches, servedSwitches);
    save.mutate({
      ...serviceChanges(draft, original),
      ...(Object.keys(moved).length > 0 ? { rule_enabled: moved } : {}),
    });
  }

  // The ten-service badge is the EXISTING ServiceTags component, reused as-is
  // (PO 2026-08-26 mid-build reinforcement of B14 r21: this lane's new UI adds
  // no stylesheet class and no inline style — the badge's colour mechanics
  // stay where they already ship).
  //
  // ⚠ It used to be composed here as a `heading` element and handed to
  // `Panel title=`. `Disclosure` takes the badge as its own `leading` prop and
  // the name as `title`, so the wrapper span is gone rather than left unused —
  // the component draws the pairing, and a spare local would have been dead
  // code the linter is right to object to.

  // ── DEF-901 MOVED OUT OF THIS COMPONENT (DEF-MET-4479) ─────────────────
  // A service with no meters used to draw its own collapsed panel here with
  // two sentences in it. It is now one shared line above the estimation panel
  // — `UnmeteredLine` — because nine of these paragraphs is noise and B14 rule
  // 32 asks for one sentence per section. The parent decides: this component
  // is only ever handed a service the tenant actually meters.

  // ── the honest fail-safe state (BR-MET-020 / US-MET-011 TC-9) ────────────
  if (isCreate && !creating) {
    return (
      <Disclosure
        title={<span data-service-listed={entry.service}>{serviceName}</span>}
        leading={<ServiceTags services={[entry.service]} />}
        summary={t("metering.readValidation.service.hint", { service: serviceName })}
        defaultOpen={props.defaultOpen === true}
      >
        <p data-source="none" className="max-w-measure text-sm text-neutral-700">
          {t("metering.readValidation.source.none", { service: serviceName })}
        </p>
        {!props.readOnly && (
          <Button
            onClick={() => {
              setCreating(true);
              setEdits(draftFromEntry(entry));
            }}
          >
            {t("metering.readValidation.setUp", { service: serviceName })}
          </Button>
        )}
      </Disclosure>
    );
  }

  const prefix = `rv-${entry.service}`;
  return (
    // ── DEF-900: ONE COLLAPSIBLE PANEL PER SERVICE (PO 2026-08-27) ──────────
    // *"for each utilitu service you can make expand and collapse -
    // component"*. A tenant selling ten services rendered ten full threshold
    // forms end to end — fourteen inputs each — so reaching the one service a
    // clerk came to change meant scrolling past nine they did not. Closed by
    // default, which is `Disclosure`'s own documented posture.
    //
    // ⚠ THE EXISTING COMPONENT, NOT A NEW ONE. `Disclosure` already pairs
    // `aria-expanded` with `aria-controls` off a single `useId`, so the two
    // cannot drift apart the way two hand-written strings do. Reusing it is
    // B14 r21 honoured by having nothing to add.
    <Disclosure
      title={<span data-service-listed={entry.service}>{serviceName}</span>}
      leading={<ServiceTags services={[entry.service]} />}
      summary={t("metering.readValidation.service.hint", { service: serviceName })}
      // Shown CLOSED as well as open — the point of it.
      status={dirty && !props.readOnly ? t("metering.readValidation.unsaved") : undefined}
      defaultOpen={props.defaultOpen === true}
    >
      {entry.source === "tenant_fallback" && (
        <p data-source="tenant_fallback" className="max-w-measure text-sm text-neutral-700">
          {t("metering.readValidation.source.fallback", { service: serviceName })}
        </p>
      )}
      {/* ── DEF-MET-4479: THE TWO COLUMNS LINE UP BECAUSE NOTHING IN THIS
          GRID EXPLAINS ITSELF ANY MORE, AND THE OLD FIX COULD NOT WORK ──────
          DEF-900 tried `grid-rows-subgrid`: every field spans three shared
          rows, so labels sit on the label row, help on the help row and inputs
          on the input row. It cannot do that, and it is worth saying why so
          nobody reaches for it again. **Subgrid assigns children to tracks IN
          SOURCE ORDER.** A field WITH help has three children (label, help,
          input) and a field WITHOUT help has two (label, input) — so the
          second field's INPUT lands on the HELP row. The pair is misaligned by
          exactly the height of one help line.

          MEASURED IN A BROWSER on 2026-09-07, before this change, at 1440px:
          `rv-electric-days_hard_min` at y=1450 against `rv-electric-days_hard_max`
          at y=1398 — 52px apart, in one row. The rows whose two fields HAPPENED
          to have the same shape (both with help, or both without) lined up
          perfectly, which is why the old fix looked as though it worked.

          The cure is structural rather than another layout utility: **no field
          in this grid carries a help line at all**, so every `.field` has the
          same children and the inputs cannot disagree. That is also B14 rule
          32 — a screen gets one sentence per section, and this one carried
          four inside a single service. The unit the floor is expressed in is
          not commentary, so it rides the LABEL ("High-use floor (kWh)"),
          which honours hard rule 3 and costs no line; and the hard-window
          constraint is already stated by the refusal that fires when it is
          broken, at the moment it matters, under the field that broke it. */}
      <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
        <TextField
          id={`${prefix}-high_pct`}
          label={t("metering.readValidation.highPct")}
          value={draft.high_pct}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.high_pct}
          onChange={(value) => patch("high_pct", value)}
        />
        <TextField
          id={`${prefix}-low_pct`}
          label={t("metering.readValidation.lowPct")}
          value={draft.low_pct}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.low_pct}
          onChange={(value) => patch("low_pct", value)}
        />
        <TextField
          id={`${prefix}-high_abs_value`}
          // hard rule 3 — a floor carries its unit, in the LABEL rather than
          // in a sentence beneath it. With the unit not yet typed the label is
          // the bare noun and the field beside it is the one that asks for it.
          label={
            draft.high_abs_unit.trim() === ""
              ? t("metering.readValidation.highAbsValue")
              : t("metering.readValidation.highAbsValueUnit", { unit: draft.high_abs_unit.trim() })
          }
          value={draft.high_abs_value}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.high_abs_value}
          onChange={(value) => patch("high_abs_value", value)}
        />
        <TextField
          id={`${prefix}-high_abs_unit`}
          label={t("metering.readValidation.highAbsUnit")}
          value={draft.high_abs_unit}
          readOnly={props.readOnly}
          error={fieldErrors.high_abs_unit}
          onChange={(value) => patch("high_abs_unit", value)}
        />
        <SelectField
          id={`${prefix}-zero_scope`}
          label={t("metering.readValidation.zeroScope")}
          value={draft.zero_scope}
          options={ZERO_SCOPES.map((scope) => ({
            value: scope,
            // the ratified S64 choice copy, already translated — reused, not re-minted
            label: t(`settings.rules.choice.zero_scope.${scope}`),
          }))}
          placeholder={isCreate ? t("metering.readValidation.choose") : undefined}
          error={fieldErrors.zero_scope}
          // the RuleField posture: a read-only page's select swallows changes
          onChange={(value) => !props.readOnly && patch("zero_scope", value)}
        />
        <TextField
          id={`${prefix}-mismatch_pct`}
          label={t("metering.readValidation.mismatchPct")}
          value={draft.mismatch_pct}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.mismatch_pct}
          onChange={(value) => patch("mismatch_pct", value)}
        />
        <TextField
          id={`${prefix}-days_flag_min`}
          label={t("metering.readValidation.daysFlagMin")}
          value={draft.days_flag_min}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.days_flag_min}
          onChange={(value) => patch("days_flag_min", value)}
        />
        <TextField
          id={`${prefix}-days_flag_max`}
          label={t("metering.readValidation.daysFlagMax")}
          value={draft.days_flag_max}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.days_flag_max}
          onChange={(value) => patch("days_flag_max", value)}
        />
        <TextField
          id={`${prefix}-days_hard_min`}
          label={t("metering.readValidation.daysHardMin")}
          value={draft.days_hard_min}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.days_hard_min}
          onChange={(value) => patch("days_hard_min", value)}
        />
        <TextField
          id={`${prefix}-days_hard_max`}
          label={t("metering.readValidation.daysHardMax")}
          value={draft.days_hard_max}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.days_hard_max}
          onChange={(value) => patch("days_hard_max", value)}
        />
        <TextField
          id={`${prefix}-tou_sum_tolerance_pct`}
          label={t("metering.readValidation.touTolerancePct")}
          value={draft.tou_sum_tolerance_pct}
          numeric
          readOnly={props.readOnly}
          error={fieldErrors.tou_sum_tolerance_pct}
          onChange={(value) => patch("tou_sum_tolerance_pct", value)}
        />
      </div>

      <ChecksFieldset
        service={entry.service}
        serviceName={serviceName}
        judgmentRules={props.judgmentRules}
        integrityRules={props.integrityRules}
        switches={switches}
        readOnly={props.readOnly}
        onToggle={toggleRule}
      />

      <RefusalNotice refusal={refusal} />

      <SaveBar
        saveLabel={t("metering.readValidation.save", { service: serviceName })}
        working={save.isPending}
        dirty={dirty}
        readOnly={props.readOnly}
        readOnlyReason={t("settings.readOnlyReason")}
        onSave={submit}
        onDiscard={() => {
          setEdits(null);
          setSwitchEdits(null);
          setCreating(false);
          setFieldErrors({});
          setRefusal(null);
        }}
      />
    </Disclosure>
  );
}

// ── BR-MET-136 · which checks run for this service ─────────────────────────

/**
 * The per-service ON/OFF list — BR-MET-136, PO 2026-08-26 verbatim: *"yes every
 * rule that is enabled always run - you ahve to keep default - all enabled"*.
 *
 * TWO KINDS OF ROW, AND THE DIFFERENCE IS DRAWN, NOT IMPLIED.
 *
 * A JUDGMENT rule is a checkbox: the utility may retire a check that does not
 * fit their business, and every one arrives checked because that is the
 * ratified default.
 *
 * An INTEGRITY rule is NOT a disabled checkbox. A greyed-out control with no
 * explanation reads as "broken" or "not your permission level", and BR-SHL-025's
 * whole posture is that a control a user cannot act on must state WHY. So the
 * seven render as a distinct LOCKED row — a padlock, the rule's name, the words
 * "Always runs", and one sentence of reason underneath the group — with no
 * input element at all. There is nothing to click, so there is nothing to
 * wonder about.
 *
 * Both lists are SERVED (`validation.INTEGRITY_RULES` / `JUDGMENT_RULES`), never
 * spelled here: a screen that listed the rules itself would disagree with the
 * engine the first time a rule is added, and disagree silently.
 *
 * B14 rule 21: Tailwind utilities only — this component adds no class to any
 * stylesheet, and `CheckboxField` brings its own already-declared markup.
 */
function ChecksFieldset(props: {
  service: string;
  serviceName: string;
  judgmentRules: string[];
  integrityRules: string[];
  switches: RuleSwitches;
  readOnly: boolean;
  onToggle: (rule: string, enabled: boolean) => void;
}) {
  const { t } = useTranslation();
  const ruleName = (rule: string): string =>
    t(`metering.reads.status.${rule}`, { defaultValue: rule });
  const offCount = props.judgmentRules.filter((rule) => props.switches[rule] === false).length;

  return (
    <fieldset data-checks-for={props.service} className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className="p-0 text-sm font-medium text-neutral-900">
        {t("metering.readValidation.checks.title")}
      </legend>
      <p className="max-w-measure text-sm text-neutral-700">
        {t("metering.readValidation.checks.hint")}
      </p>

      <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        {props.judgmentRules.map((rule) => {
          const enabled = props.switches[rule] !== false;
          return (
            <div key={rule} data-rule={rule} data-rule-enabled={String(enabled)}>
              {props.readOnly ? (
                // A view-only page states the setting rather than offering an
                // input the reader cannot use (BR-SHL-025).
                <p className="text-md text-neutral-700">
                  {ruleName(rule)} —{" "}
                  {enabled
                    ? t("metering.readValidation.checks.on")
                    : t("metering.readValidation.checks.off")}
                </p>
              ) : (
                <CheckboxField
                  id={`rv-${props.service}-rule-${rule}`}
                  label={ruleName(rule)}
                  checked={enabled}
                  onChange={(checked) => props.onToggle(rule, checked)}
                />
              )}
            </div>
          );
        })}
      </div>

      {offCount > 0 && (
        // A switched-off check does not vanish from a reading either — it says
        // so on the read (BR-MET-136's trailing clause). Said here too, so the
        // admin turning it off knows what a clerk will see.
        <p data-checks-off-count={offCount} className="max-w-measure text-sm text-neutral-700">
          {t("metering.readValidation.checks.offNotice", {
            count: offCount,
            service: props.serviceName,
          })}
        </p>
      )}

      <p className="text-sm font-medium text-neutral-900">
        {t("metering.readValidation.checks.lockedTitle")}
      </p>
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {props.integrityRules.map((rule) => (
          <li
            key={rule}
            data-locked-rule={rule}
            className="inline-flex items-center gap-1.5 border border-divider bg-neutral-100 px-2 py-1 text-sm text-neutral-700"
          >
            {/* the LOCK is a word, not a greyed-out input: a disabled control
                with no explanation reads as "broken" or "not your permission
                level" (BR-SHL-025). No icon is minted for it — the shared set
                has no padlock, and adding one to a shared file for a label is
                a bigger change than the label. */}
            <span className="text-xs font-medium uppercase tracking-wide text-neutral-600">
              {t("metering.readValidation.checks.lockedTag")}
            </span>
            <span>{ruleName(rule)}</span>
            <span className="text-xs uppercase tracking-wide text-neutral-600">
              {t("metering.readValidation.integrity.locked")}
            </span>
          </li>
        ))}
      </ul>
      <p className="max-w-measure text-sm text-neutral-700">
        {t("metering.readValidation.checks.lockedReason")}
      </p>
    </fieldset>
  );
}

// ── the tenant-wide estimation panel ───────────────────────────────────────

function GeneralPanel(props: {
  general: ReadValidationOverview["general"];
  readOnly: boolean;
  client: ApiClient;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  // ⚠ **A TENANT WITH NO SETTINGS ROW SHOWS NO METHOD — NOT THE DEFAULT.**
  // The engine refuses EVERY estimate for such a tenant
  // (`validation_config_missing`, BR-MET-020), so a screen that fell back to
  // `DEFAULT_EST_METHOD` here would print a method the product is not running
  // as though it were. The old read-only box printed an em dash for exactly
  // this; a `<select>` has no em dash, so it takes the empty value and the
  // panel's one sentence says what is happening instead. `general.present` is
  // SERVED precisely so the screen never has to guess this.
  const original: GeneralDraft = {
    est_method: props.general.est_method ?? "",
    est_max_consecutive:
      props.general.est_max_consecutive === null ? "" : String(props.general.est_max_consecutive),
  };
  const [edits, setEdits] = useState<GeneralDraft | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const draft = edits ?? original;

  const save = useMutation({
    mutationFn: (changes: Record<string, unknown>) =>
      saveReadValidationGeneral(changes, props.client),
    onSuccess: () => {
      setEdits(null);
      setFieldErrors({});
      setRefusal(null);
      fireToast(t("metering.readValidation.generalSaved"));
      void queryClient.invalidateQueries({ queryKey: readValidationKey() });
    },
    onError: (error: unknown) => {
      if (isApiError(error)) {
        const mapped = envelopeErrors(formErrorEnvelope(error), (key, params) => t(key, params));
        setFieldErrors(mapped.fields);
      }
      setRefusal(refusalOf(error, t));
    },
  });

  function submit(): void {
    setRefusal(null);
    const problems: Record<string, string> = {};
    const raw = draft.est_max_consecutive.trim();
    if (!/^\d+$/.test(raw) || Number.parseInt(raw, 10) < 1) {
      problems.est_max_consecutive = t("metering.read_validation.est_max_min_one");
    }
    // The two methods with nothing to read cannot be stored: an admin picking
    // one would stop every estimate on the tenant. The `<option>` is disabled
    // so a mouse cannot reach it; this is the same refusal one layer in, and
    // the server refuses it a third time (BR-SHL-025's defense in depth).
    if (draft.est_method === "") {
      // "you have not picked one" is a different refusal from "we cannot run
      // that one", and telling a person the wrong one of the two is worse than
      // telling them nothing.
      problems.est_method = t("metering.read_validation.est_method_choice");
    } else if (!estMethodRunnable(draft.est_method)) {
      problems.est_method = t("metering.read_validation.est_method_not_available");
    }
    setFieldErrors(problems);
    if (Object.keys(problems).length > 0) {
      return;
    }
    save.mutate({
      est_method: draft.est_method,
      est_max_consecutive: Number.parseInt(raw, 10),
    });
  }

  // B14 rule 32 — this panel gets ONE sentence, and it is the one that changes:
  // what the CHOSEN method actually does. The static two-sentence hint above it
  // is gone, and so is the sentence that told a clerk about our Product Owner
  // and our own decision process (`estMethodFixed`), which was the clearest
  // breach of rule 32 in the product and became false the day this dropdown
  // landed.
  const chosen = draft.est_method;

  return (
    <Panel title={t("metering.readValidation.general.title")}>
      {/* ── CR-079 · THE METHOD IS A CHOICE (PO 2026-09-07) ────────────────
          *"this should be drop down options - give 4 to 5 options here"*, then
          *"we are good with these + add last 6 month avg + Use avg from plan"*.
          Seven, in the order they were named, with today's method FIRST and
          still the default: changing how a missing reading is estimated
          changes what a customer is billed, so it is a choice somebody makes
          and never a side effect of a release. Nothing migrates a stored row. */}
      <SelectField
        id="rv-est_method"
        label={t("metering.readValidation.estMethod")}
        value={chosen}
        placeholder={chosen === "" ? t("metering.readValidation.choose") : undefined}
        options={EST_METHODS.map((method) => ({
          value: method.code,
          label: t(`settings.rules.choice.est_method.${method.code}`, {
            defaultValue: method.code,
          }),
          // BR-SHL-025 — a control that cannot act is disabled WITH its
          // reason, and the reason is the line under the select.
          disabled: "unavailable" in method && method.unavailable,
        }))}
        error={fieldErrors.est_method}
        onChange={(value) =>
          !props.readOnly && setEdits({ ...draft, est_method: value })
        }
      />
      {/* The ONE sentence: when a person would pick the method they are
          looking at. Seven methods with no guidance is a worse screen than
          one method. */}
      <p data-est-method-when={chosen} className="max-w-measure text-sm text-neutral-700">
        {chosen === ""
          ? t("metering.readValidation.noEstimation")
          : t(`metering.readValidation.estMethodWhen.${chosen}`, { defaultValue: "" })}
      </p>
      {/* The consequence rides the LABEL rather than a sentence beneath it —
          "before a reading is required" IS what happens on the next one, and
          it costs this section none of its rule-32 budget. */}
      <TextField
        id="rv-est_max_consecutive"
        label={t("metering.readValidation.estMaxConsecutive")}
        value={draft.est_max_consecutive}
        numeric
        readOnly={props.readOnly}
        error={fieldErrors.est_max_consecutive}
        onChange={(value) => setEdits({ ...draft, est_max_consecutive: value })}
      />

      <RefusalNotice refusal={refusal} />

      <SaveBar
        saveLabel={t("metering.readValidation.generalSave")}
        working={save.isPending}
        dirty={
          draft.est_max_consecutive.trim() !== original.est_max_consecutive ||
          draft.est_method !== original.est_method
        }
        readOnly={props.readOnly}
        readOnlyReason={t("settings.readOnlyReason")}
        onSave={submit}
        onDiscard={() => {
          setEdits(null);
          setFieldErrors({});
          setRefusal(null);
        }}
      />
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-038 Amendment 1 (12-governance/11-change-requests.md, 2026-08-26)
// generated: 2026-08-26 by the CR-038 A1 S64 lane
// checklist: A✔ B✔ C✔ (SettingsReadValidation.test.tsx) D✔ (the three
//         metering endpoints) E✔ F✔ G✔ H=deferred(not a 🔒 path — every figure
//         is READ from and WRITTEN to tenant config; no key or rounding rule
//         is authored here)
// gates: npx vitest run src/features/tenancy/SettingsReadValidation.test.tsx —
//         output quoted in the lane report; G31: zero new stylesheet classes
//         (Tailwind utilities + the shared kit's already-declared classes)
// exceptions: `Panel.title` receives a ReactNode (the service badge + name) —
//         Panel already types `title: ReactNode`; the ten-service badge map is
//         ratingShared's, reused rather than copied
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
