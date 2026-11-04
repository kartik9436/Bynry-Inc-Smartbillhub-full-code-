// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 (EP-TEN-07 §Stories + SCOPE ADDENDUM — the S63–S71 rule-page cards) ·
//           US-MET-011 (S64 read-validation config — TC-7 "no value is hardcoded", TC-8 negative) ·
//           US-PAY-006 (S66's within-invoice class sequence) · US-LED-014 (S71's per-authority
//           remitting basis — the two controls added 2026-08-15)
//           Screens: S64, S66, S69, S70, S71 (all inside S8 → Reference data)
// Rules:    BR-SHL-035 (ONE Reference-data shell — a rule page is a card whose view is a FORM;
//           same back-link, header block, save bar, toast and audit line as a list card) ·
//           BR-TEN-024 (partial change set in, whole page out — one atomic save, one audit row) ·
//           BR-TEN-016 (the save is audited server-side) · BR-TEN-043 (event-time forward:
//           a new value governs what happens AFTER the save, nothing is re-run) ·
//           BR-SHL-017 (the shared field kit; per-field errors under their input) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-025 (a forbidden control renders
//           disabled WITH its reason) · BR-MET-020 (the page IS the config an engine reads) ·
//           BR-PAY-038 (S66's four within-invoice classes) · BR-LED-002 (S71's per-authority
//           remitting basis) · BR-TEN-022 (the accounting period is COMPUTED, never stored)
// ───────────────────────────────────────────────────────
// The ONE form body behind every rule page. Five cards, five endpoints, ONE
// component — which is what makes BR-SHL-035 a property of the code: a sixth
// rule page is a row in settingsRulePages.ts, and it opens in this same view,
// inside the same SettingsFrame the lookup lists use.
//
// The money law, stated where it bites (CLAUDE.md #2):
//   · a decimal arrives as a canonical STRING and is held as that string;
//   · nothing here calls Number() on one, and nothing rounds — the round trip
//     of an untouched field is byte-identical;
//   · where a parameter is an AMOUNT, the tenant's own currency (Regional
//     settings) lets the shared MoneyCell echo it read-only beside the input.
//     No currency on file means no echo — a bare "$" would be a guess.
//
// The refusal law: this screen validates NOTHING it cannot know. It holds no
// copy of the server's ranges, so every out-of-range value, unknown field and
// unratified enum is refused by the SERVER and rendered from the B12 §3
// envelope — under the offending input, with the rule the server cited.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getRegionalSettings, getRulePage, saveRulePage } from "@/api/endpoints";
import type { RuleDocument, RulePageSlug } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { CheckboxField, SelectField, TextField, envelopeErrors } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";

import { AllocationOrderField } from "./SettingsAllocationOrder";
import { RemittingBasisField } from "./SettingsRemittingBasis";
import {
  choiceIsFixed,
  draftFromDocument,
  ruleChanges,
  ruleIsDirty,
} from "./settingsRulePages";
import type { RuleDraft, RuleFieldValue, RuleParam, RulePage } from "./settingsRulePages";
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

// ── Pure pieces ────────────────────────────────────────────────────────────

/** The i18n key stem for a parameter's label/help — never display text. */
export function paramLabelKey(page: RulePage, param: RuleParam): string {
  return `settings.rules.${page.card}.${param.key}`;
}

/** A choice VALUE renders through the catalog too (no raw enum on screen). */
export function choiceLabelKey(param: RuleParam, value: string): string {
  return `settings.rules.choice.${param.key}.${value}`;
}

/**
 * BR-SHL-025's shape for a control the user may see but not change. A fixed
 * single-value choice is the same idea one level down: the control is present
 * and disabled, and the reason sits beside it.
 */
export function fixedChoiceValue(param: RuleParam): string {
  return param.choices?.[0] ?? "";
}

/** A money echo needs a currency; without one there is nothing honest to draw. */
export function moneyEcho(
  param: RuleParam,
  raw: string | boolean,
  currency: string | null,
): { amount: string; currency: string } | null {
  if (param.kind !== "money" || currency === null || currency === "") {
    return null;
  }
  const amount = String(raw).trim();
  return amount === "" ? null : { amount, currency };
}

// ── The view ───────────────────────────────────────────────────────────────

export interface RulePageViewProps {
  page: RulePage;
  readOnly: boolean;
  client?: ApiClient;
}

export function RulePageView(props: RulePageViewProps) {
  const { t } = useTranslation();
  const { page } = props;
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();

  const pageQuery = useQuery({
    queryKey: queryKeys.rulePage(page.slug),
    queryFn: () => getRulePage(page.slug as RulePageSlug, client),
  });

  // The tenant's currency, only so an AMOUNT can be echoed in the tenant's own
  // money format. It is a reference read that may legitimately fail (Regional
  // is System-Admin-only) — a failure simply means no echo, never a broken page.
  const regionalQuery = useQuery({
    queryKey: queryKeys.regionalSettings,
    queryFn: () => getRegionalSettings(client),
    staleTime: REFERENCE_STALE_MS,
  });
  const currency = regionalQuery.data?.currency ?? null;
  // BR-TEN-022: the accounting period is COMPUTED from the tenant's fiscal
  // settings and never stored, and the same Regional read serves it. The S71
  // per-authority table needs one to ask `GET /finance/taxes` for this tenant's
  // tax authorities; null means "no fiscal calendar configured", which that
  // control renders as itself rather than as an empty list of authorities.
  const period = regionalQuery.data?.current_period ?? null;

  const [edits, setEdits] = useState<RuleDraft | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const save = useMutation({
    mutationFn: (changes: Record<string, unknown>) =>
      saveRulePage(page.slug as RulePageSlug, changes, client),
    onSuccess: (saved: RuleDocument) => {
      // BR-TEN-024: the response IS the whole page, so it replaces the cache
      // rather than triggering a re-read of what we were just handed.
      queryClient.setQueryData(queryKeys.rulePage(page.slug), saved);
      setEdits(null);
      setFieldErrors({});
      setRefusal(null);
      fireToast(t("settings.rules.saved", { page: t(`settings.reference.card.${page.card}`) }));
    },
    onError: (error: unknown) => {
      // Every refusal class lands the same way: field errors under their
      // fields, the rest as the form-level line with the server's br_ref.
      if (isApiError(error)) {
        const mapped = envelopeErrors(formErrorEnvelope(error), (key, params) => t(key, params));
        setFieldErrors(mapped.fields);
      }
      setRefusal(refusalOf(error, t));
    },
  });

  if (pageQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  if (pageQuery.data === undefined) {
    if (isPermissionDenied(pageQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />; // A18 §6
    }
    return (
      <FailedWithRetry
        title={t("settings.rules.failedTitle")}
        reason={apiErrorText(pageQuery.error, t)}
        onRetry={() => void pageQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void pageQuery.refetch()}
      />
    );
  }

  const original = draftFromDocument(page, pageQuery.data as Record<string, RuleFieldValue>);
  const draft = edits ?? original;

  function patch(key: string, value: string | boolean): void {
    setEdits({ ...draft, [key]: value });
  }

  return (
    <div className="settings-tab">
      <Panel
        title={t(`settings.rules.${page.card}.title`)}
        hint={t(`settings.rules.${page.card}.hint`)}
        accent
      >
        {/* BR-SHL-035 still holds: ONE shell, ONE form, one save bar. The two
            parameters the PO's rulings of 2026-08-12 created are not typed into
            a text box — an ORDER is reordered and a per-item choice is a table
            — so each gets its own control INSIDE this form rather than a screen
            of its own. Everything else is still `RuleField`. */}
        {page.params.map((param) =>
          param.kind === "choice_sequence" ? (
            <AllocationOrderField
              key={param.key}
              page={page}
              param={param}
              value={draft[param.key]}
              error={fieldErrors[param.key]}
              readOnly={props.readOnly}
              currency={currency}
              onChange={(value) => patch(param.key, value)}
            />
          ) : param.kind === "choice_map" ? (
            <RemittingBasisField
              key={param.key}
              page={page}
              param={param}
              value={draft[param.key]}
              error={fieldErrors[param.key]}
              readOnly={props.readOnly}
              period={period}
              client={client}
              onChange={(value) => patch(param.key, value)}
            />
          ) : (
            <RuleField
              key={param.key}
              page={page}
              param={param}
              value={draft[param.key]}
              error={fieldErrors[param.key]}
              readOnly={props.readOnly}
              currency={currency}
              onChange={(value) => patch(param.key, value)}
            />
          ),
        )}
      </Panel>

      <RefusalNotice refusal={refusal} />

      <SaveBar
        saveLabel={t("settings.rules.save")}
        working={save.isPending}
        dirty={ruleIsDirty(page, draft, original)}
        readOnly={props.readOnly}
        readOnlyReason={t("settings.readOnlyReason")}
        onSave={() => {
          setRefusal(null);
          setFieldErrors({});
          // BR-TEN-024: only what changed. An untouched page posts `{}`.
          save.mutate(ruleChanges(page, draft, original));
        }}
        onDiscard={() => {
          setEdits(null);
          setFieldErrors({});
          setRefusal(null);
        }}
        // BR-TEN-043 said plainly: nothing already in flight is re-run.
        note={t("settings.rules.forwardNote")}
      />
    </div>
  );
}

function RuleField(props: {
  page: RulePage;
  param: RuleParam;
  value: string | boolean;
  error?: string;
  readOnly: boolean;
  currency: string | null;
  onChange: (value: string | boolean) => void;
}) {
  const { t } = useTranslation();
  const { param, page } = props;
  const label = t(paramLabelKey(page, param));
  const unit = param.unitKey === undefined ? "" : t(param.unitKey);
  // ⚠ **NO RULE ID ON SCREEN, AND NOTHING PUT IN ITS PLACE** — `DEF-TEN-6935`.
  // This line used to read `Set by BR-REP-018` on every rule field on every
  // Settings rule page, which B14 rule 32 clause 4 bans outright (no rule id or
  // internal code in clerk-facing copy). It survived every catalogue-grepping
  // check because the id is INTERPOLATED: the catalogue holds `Set by {{br}}`
  // and the id arrives from `param.br` at render time, so no grep for
  // `BR-`-shaped text in `en.json` could ever see it.
  //
  // It has no replacement, and that is the ruling rather than an omission.
  // *Who decided 200%?* is RATIONALE — why the product works this way — and
  // B14 rule 33 puts rationale at ZERO WORDS ON SCREEN. Answering it in six
  // words would still be rationale; answering it with the id was rationale a
  // clerk cannot act on. The answer lives where it has always lived: in
  // `param.br`, in this file, and in the module's `02-business-rules.md`.
  //
  // What is LEFT is fact: the unit the number is in, and whether the field may
  // be left empty. Both are things a clerk types against.
  const nullableNote = param.nullable === true ? t("settings.rules.unsetNote") : "";
  const help = [unit, nullableNote].filter((part) => part !== "").join(" · ");
  const helpOrNone = help === "" ? undefined : help;

  if (param.kind === "bool") {
    return (
      <div className="settings-rule-field">
        <CheckboxField
          id={param.key}
          label={label}
          checked={props.value === true}
          onChange={(checked) => !props.readOnly && props.onChange(checked)}
        />
        {helpOrNone !== undefined && <p className="field-help">{helpOrNone}</p>}
        {props.error !== undefined && (
          <RefusalStrip role="alert">
            {props.error}
          </RefusalStrip>
        )}
      </div>
    );
  }

  if (param.kind === "choice") {
    if (choiceIsFixed(param)) {
      // Exactly one value is ratified today. The control is present, fixed, and
      // SAYS the other values are not ratified — this screen never invents an
      // option finance has not signed (CLAUDE.md: never resolve an open question).
      const value = fixedChoiceValue(param);
      return (
        <div className="settings-rule-field">
          <TextField
            id={param.key}
            label={label}
            value={t(choiceLabelKey(param, value))}
            onChange={() => undefined}
            readOnly
            help={t("settings.rules.onlyRatified")}
            error={props.error}
          />
        </div>
      );
    }
    return (
      <div className="settings-rule-field">
        <SelectField
          id={param.key}
          label={label}
          value={String(props.value)}
          onChange={(value) => !props.readOnly && props.onChange(value)}
          options={(param.choices ?? []).map((choice) => ({
            value: choice,
            label: t(choiceLabelKey(param, choice)),
          }))}
          help={helpOrNone}
          error={props.error}
        />
      </div>
    );
  }

  // decimal · money · int · int_list — all held and sent as TEXT (rule 2).
  const echo = moneyEcho(param, props.value, props.currency);
  return (
    <div className="settings-rule-field">
      <TextField
        id={param.key}
        label={label}
        value={String(props.value)}
        onChange={(value) => !props.readOnly && props.onChange(value)}
        numeric={param.kind !== "int_list"}
        help={
          param.kind === "int_list"
            ? [t("settings.rules.listHelp"), help].filter((part) => part !== "").join(" · ")
            : helpOrNone
        }
        error={props.error}
      />
      {echo !== null && (
        // BR-SHL-023: the ONE money formatter renders the tenant's own format.
        // Display only — the string in the input is what actually posts.
        <p className="settings-rule-echo">
          <MoneyCell amount={echo.amount} currency={echo.currency} />
        </p>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07, whose SCOPE ADDENDUM adds the S63–S71 cards; co-packet EP-MET-04@34f14b6 for the S64 field law)
// generated: 2026-08-09 by story-coder v1 (W0 frontend integration lane — the five rule pages become real forms)
// amended:   2026-08-15 by story-coder (settings-screens lane) — this form now dispatches the two KINDS
//            the backend registry grew on 2026-08-12: `choice_sequence` → the S66 reorder control and its
//            live worked example (SettingsAllocationOrder.tsx), `choice_map` → the S71 per-authority
//            remitting-basis table (SettingsRemittingBasis.tsx). Both settings were stored, validated and
//            READ BY THEIR CALLERS with no way for a user to reach either — hard-won law 2. The Regional
//            read this file already made for the money echo now also yields `current_period`, which the
//            S71 table needs to ask `GET /finance/taxes` for the tenant's authorities (BR-TEN-022 — no
//            month is computed from the browser's clock).
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · [2026-08-15 settings-screens lane] see the lane report
// exceptions: E1 [2026-08-15] OQ-194 (where the per-authority basis control lives) is OPEN and this file mounts it on S71 Finance controls — option (b) — because the PO put GL configuration *"under Configure"* on 2026-08-12 and because option (a)'s surface has no account CODE to key the setting by. REPORTED, reversible as a component move; the reasoning is in SettingsRemittingBasis.tsx and features/tenancy/README.md · E3 the S63–S71 stories (US-TEN-013..017) are ALLOCATED but UNAUTHORED — this view is anchored on EP-TEN-07's scope addendum + 11b §2.3 + US-MET-011, and cites no story ID that does not exist — reported · E4 no client-side range check exists (the server owns the bounds and refuses), so a range refusal appears only AFTER a save attempt rather than as you type — deliberate, reported · E4 the money echo needs the tenant currency from `GET /settings/regional`, which is System-Admin-only; for an Executive that read 403s and the echo is simply absent — the input string is unaffected, reported · E3 `notice_tier_days` edits as a comma list because no ordered-list field exists in the shared kit (BR-SHL-017 designs none) — the order typed is the order posted, never re-sorted here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
