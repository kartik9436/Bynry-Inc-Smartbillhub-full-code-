// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-006 (EP-TEN-05 §Stories)  Screens: S8 (Settings → Regional, formats & fiscal calendar)
// Rules:    BR-TEN-020 (display-time transforms ONLY — storage stays UTC + NUMERIC(18,6) + CHAR(3);
//           nothing already issued is restated) · BR-TEN-021/BR-TEN-042 (currency forward-only, and LOCKED
//           once financial records exist → 409 BIZ-LOCKED) · BR-TEN-022 (the current-period card is
//           COMPUTED server-side, never stored) · BR-TEN-023/BR-TEN-038 (lock-closed-periods stores here;
//           enforcement — auto-post to the earliest open period, System-Admin reopen, audited — is the
//           ledger posting service's, W5) · BR-TEN-024 (sticky Save/Discard, atomic tab save) ·
//           BR-TEN-016 (audit `settings.regional_fiscal.updated`) · BR-SHL-023/BR-SHL-034 (ONE formatting
//           path — the live preview renders through DateCell/MoneyCell, never hand-formatted) ·
//           BR-SHL-033 (long lists searchable — and its THRESHOLD, which is why the eight-zone
//           timezone list is a plain dropdown; see DEF-082 at the control) ·
//           BR-TEN-081 (a typed posting DATE is midnight in the utility's OWN timezone —
//           PO 2026-08-12, OQ-153; this tab is where that timezone is chosen)
// ───────────────────────────────────────────────────────
// S8 → Regional, formats & fiscal calendar.
//
// Two things make this tab honest:
//   1. The LIVE PREVIEW is rendered by the shared formatters (formatDate /
//      formatMoney), not by preview-only code. What the user sees in the panel
//      is literally what every screen will render after Save — BR-SHL-034 makes
//      a second formatting path a merge-blocking violation, and this preview is
//      exactly where one would otherwise be written.
//   2. The CURRENCY LOCK is never predicted. This screen has no idea whether a
//      financial record exists; it offers the change, and when the server
//      refuses with 409 BIZ-LOCKED it renders that refusal, its `br_ref` and
//      its params (BR-TEN-042). US-TEN-006 TC-4's "warning modal" is the
//      PRE-lock case (BR-TEN-021, forward-only) — the confirm names the action
//      per BR-SHL-032 and the server still owns the verdict.
//
// The period card is displayed exactly as the server computes it (BR-TEN-022);
// no fiscal arithmetic is done here. The lock toggle only STORES its value —
// BR-TEN-038 (OQ-033 CLOSED) rules what a closed period does to a backdated
// money event, and that enforcement belongs to the ledger posting service in
// W5, so this screen states the rule and implies nothing further.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getRegionalSettings, saveRegionalSettings } from "@/api/endpoints";
import type { RegionalChanges, RegionalSettings } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { REGIONAL_DATE_FORMATS, formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { CheckboxField, SelectField, TextField, envelopeErrors } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { Kicker, Note } from "@/components/TextBits";
import { localeLabel } from "@/i18n";

import {
  Panel,
  PanelGrid,
  RefusalNotice,
  SaveBar,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal } from "./settingsShared";

// ── Option sets (mirrored from the server's own choice tuples) ─────────────
// Every list below is the server's validated vocabulary (apps/tenancy/
// services.py SEED_CURRENCIES / SEED_LANGUAGES / NUMBER_FORMATS / DATE_FORMATS
// / TIME_FORMATS / FIRST_DAYS_OF_WEEK / ACCOUNTING_METHODS / CLOSE_CADENCES).
// They are DATA (codes), not UI copy — a value the server would reject must
// never be offered.

export const CURRENCY_OPTIONS: readonly string[] = ["USD", "CAD", "MXN", "EUR", "GBP"];
// BR-SHL-041 (PO ruling 2026-08-10, picker mock-up): the offered set grew from
// six codes to twelve when the six new locales landed. It stays the server's
// SEED_LANGUAGES tuple verbatim — `en-US` is offered without a catalogue of its
// own (it falls back to `en`) exactly as it did before, and the five original
// codes keep their pre-expansion spelling until US-SHL-018 runs BR-SHL-042's
// re-tag over the stored values.
export const LANGUAGE_OPTIONS: readonly string[] = [
  "en",
  "en-US",
  "es",
  "es-MX",
  "de",
  "hi",
  "fr-FR",
  "id-ID",
  "it-IT",
  "ja-JP",
  "ko-KR",
  "pt-BR",
];
export const NUMBER_FORMAT_OPTIONS: readonly string[] = ["1,234.56", "1.234,56"];
// DEF-SHL-3964 — ONE list, and it lives next to the exhaustive `arrange()`
// switch it has to agree with (components/DateCell.tsx). This dropdown and the
// shell's runtime validation of `tenant_settings.date_format` now read the same
// array, so a format cannot be offered here that the renderer cannot draw.
export const DATE_FORMAT_OPTIONS: readonly RegionalDateFormat[] = REGIONAL_DATE_FORMATS;
export const TIME_FORMAT_OPTIONS: readonly string[] = ["12-hour", "24-hour"];
export const FIRST_DAY_OPTIONS: readonly string[] = ["sunday", "monday"];
/**
 * ⚠ **THE CONTROL THIS SET FED IS GONE — PO ruling, CR-008 #1, 2026-08-17.**
 * Asked whether revenue recognition should be *accrual on bill issue* or *cash
 * on payment*, the PO answered *"take it off"*, and the reason is measurable:
 * `tenants.accounting_method` was settable here and **read by nothing** — zero
 * readers in billing or ledger, so a utility switching it to *cash* changed
 * their books not at all while the screen implied they had.
 *
 * The COLUMN stays (dropping it is a migration with no caller and it may yet
 * mean something); the SELECT is deleted, and no second one is drawn on
 * Settings → Accounting either. The option list is kept, exported and unused
 * ON PURPOSE, so that the day the ledger honours a basis the vocabulary is
 * still the one the column was written with — and so this paragraph is what a
 * reader finds instead of a silently vanished feature.
 */
export const ACCOUNTING_METHOD_OPTIONS: readonly string[] = ["accrual", "cash"];
export const CLOSE_CADENCE_OPTIONS: readonly string[] = ["monthly", "quarterly"];

// A1 §S8 Regional: "8 US zones incl. Phoenix (no DST), Anchorage, Honolulu,
// Puerto Rico". IANA names — the server validates against ZoneInfo.
//
// This is the OFFERED set and it MIRRORS `apps/tenancy/selectors.TIMEZONE_
// CHOICES` name for name; `tests/test_def_082_tenant_timezone.py` reads this
// literal out of this file and fails if the two copies disagree, so the mirror
// is checked rather than promised (hard-won law 1). The server ACCEPTS more
// than this — any name ZoneInfo resolves — which is why timezoneOptions() below
// exists.
export const TIMEZONE_OPTIONS: readonly string[] = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Phoenix",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "America/Puerto_Rico",
];

/**
 * The zones to render given what this tenant HOLDS — mirrors
 * `apps/tenancy/selectors.timezone_options`.
 *
 * DEF-082 (PO 2026-08-12, "you did not fix time zone drop down in company
 * settings"): the shipped control offered a fixed eight and rendered EMPTY for
 * a utility whose stored zone was not one of them — measured at
 * `<input id="timezone" … value=""/>` for `America/Detroit`. A clock that is
 * set and invisible is worse than one that is unset, because the next save of
 * this tab reads as a deliberate choice of blank. A list of choices that cannot
 * express the current value is not a choice.
 */
export function timezoneOptions(stored: string): readonly string[] {
  return stored !== "" && !TIMEZONE_OPTIONS.includes(stored)
    ? [stored, ...TIMEZONE_OPTIONS]
    : TIMEZONE_OPTIONS;
}

export const MONTH_OPTIONS: readonly number[] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

// ── Pure pieces ────────────────────────────────────────────────────────────

export interface RegionalDraft {
  country: string;
  state: string;
  timezone: string;
  language: string;
  first_day_of_week: string;
  currency: string;
  number_format: string;
  date_format: string;
  time_format: string;
  fy_start_month: string; // held as a string: the <select> value, parsed on send
  fy_start_day: string;
  accounting_method: string;
  close_cadence: string;
  close_day: string;
  lock_closed_periods: boolean;
}

export function draftFromRegional(settings: RegionalSettings): RegionalDraft {
  return {
    country: settings.country ?? "",
    state: settings.state ?? "",
    timezone: settings.timezone ?? "",
    language: settings.language ?? "",
    first_day_of_week: settings.first_day_of_week ?? "",
    currency: settings.currency ?? "",
    number_format: settings.number_format ?? "",
    date_format: settings.date_format ?? "",
    time_format: settings.time_format ?? "",
    fy_start_month: settings.fy_start_month === null ? "" : String(settings.fy_start_month),
    fy_start_day: settings.fy_start_day === null ? "" : String(settings.fy_start_day),
    accounting_method: settings.accounting_method ?? "",
    close_cadence: settings.close_cadence ?? "",
    close_day: settings.close_day ?? "",
    lock_closed_periods: settings.lock_closed_periods,
  };
}

const TEXT_FIELDS = [
  "country",
  "state",
  "timezone",
  "language",
  "first_day_of_week",
  "currency",
  "number_format",
  "date_format",
  "time_format",
  "accounting_method",
  "close_cadence",
  "close_day",
] as const;

/** BR-TEN-024: the PUT carries only what changed — nothing else is touched. */
export function regionalChanges(draft: RegionalDraft, original: RegionalDraft): RegionalChanges {
  const changes: Record<string, unknown> = {};
  for (const field of TEXT_FIELDS) {
    if (draft[field] !== original[field]) {
      changes[field] = draft[field].trim() === "" ? null : draft[field].trim();
    }
  }
  for (const field of ["fy_start_month", "fy_start_day"] as const) {
    if (draft[field] !== original[field]) {
      changes[field] = draft[field] === "" ? null : Number.parseInt(draft[field], 10);
    }
  }
  if (draft.lock_closed_periods !== original.lock_closed_periods) {
    changes.lock_closed_periods = draft.lock_closed_periods;
  }
  return changes as RegionalChanges;
}

export function regionalIsDirty(draft: RegionalDraft, original: RegionalDraft): boolean {
  return Object.keys(regionalChanges(draft, original)).length > 0;
}

/**
 * BR-TEN-021: a currency change is forward-only and needs the explicit warning
 * (US-TEN-006 TC-4). This predicate only asks "is the user changing it" — it
 * never predicts whether the server will LOCK the change (BR-TEN-042).
 */
export function currencyIsChanging(draft: RegionalDraft, original: RegionalDraft): boolean {
  return draft.currency !== original.currency && original.currency !== "";
}

/** The date format is a closed set; anything else falls back to the ISO form. */
export function asDateFormat(value: string): RegionalDateFormat {
  return DATE_FORMAT_OPTIONS.includes(value as RegionalDateFormat)
    ? (value as RegionalDateFormat)
    : "YYYY-MM-DD";
}

/**
 * IS-8 number format → the Intl locale the ONE money formatter takes. Only the
 * two formats the server accepts are mapped; anything else uses the seed.
 */
export function localeForNumberFormat(numberFormat: string): string {
  return numberFormat === "1.234,56" ? "de-DE" : "en-US";
}

// The live preview's fixed sample (US-TEN-006 TC-1 renders exactly this row).
// A calendar date + a decimal STRING amount — never a float, never a Date built
// from "now", so the preview is stable and testable.
export const PREVIEW_DATE = "2026-08-08";
export const PREVIEW_AMOUNT = "1234.56";

// ── The tab ────────────────────────────────────────────────────────────────

export interface RegionalTabProps {
  readOnly: boolean;
  client?: ApiClient;
}

export function RegionalTab(props: RegionalTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();

  const settingsQuery = useQuery({
    queryKey: queryKeys.regionalSettings,
    queryFn: () => getRegionalSettings(client),
  });

  const [edits, setEdits] = useState<RegionalDraft | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [confirmCurrency, setConfirmCurrency] = useState(false);

  const save = useMutation({
    mutationFn: (changes: RegionalChanges) => saveRegionalSettings(changes, client),
    onSuccess: (saved: RegionalSettings) => {
      queryClient.setQueryData(queryKeys.regionalSettings, saved);
      // DEF-SHL-4272 — the app shell draws the date format, the time zone and the language from `GET /shell/display`,
      // its OWN key. Saving here must invalidate it or the sidebar and every
      // date on screen keep the value that was just replaced until a reload.
      void queryClient.invalidateQueries({ queryKey: queryKeys.shellDisplay });
      void queryClient.invalidateQueries({ queryKey: queryKeys.checklist });
      // Formats feed every screen — the numbering preview reads the tenant TZ.
      void queryClient.invalidateQueries({ queryKey: queryKeys.numberSeries });
      setEdits(null);
      setFieldErrors({});
      setRefusal(null);
      setConfirmCurrency(false);
      fireToast(t("settings.regional.saved"));
    },
    onError: (error: unknown) => {
      if (isApiError(error)) {
        const mapped = envelopeErrors(formErrorEnvelope(error), (key, params) => t(key, params));
        setFieldErrors(mapped.fields);
      }
      // BR-TEN-042: 409 BIZ-LOCKED renders HERE, with the server's own reason
      // and the currency it kept — the screen never invents the lock text.
      setRefusal(refusalOf(error, t));
      setConfirmCurrency(false);
    },
  });

  if (settingsQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (settingsQuery.data === undefined) {
    if (isPermissionDenied(settingsQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.regional.failedTitle")}
        reason={apiErrorText(settingsQuery.error, t)}
        onRetry={() => void settingsQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void settingsQuery.refetch()}
      />
    );
  }

  const server = settingsQuery.data;
  const original = draftFromRegional(server);
  const draft = edits ?? original;
  function patch(change: Partial<RegionalDraft>): void {
    setEdits({ ...draft, ...change });
  }

  function commit(): void {
    save.mutate(regionalChanges(draft, original));
  }

  function handleSave(): void {
    setRefusal(null);
    if (currencyIsChanging(draft, original)) {
      // BR-TEN-021 / US-TEN-006 TC-4: state what survives before committing.
      setConfirmCurrency(true);
      return;
    }
    commit();
  }

  const dateFormat = asDateFormat(draft.date_format);
  const locale = localeForNumberFormat(draft.number_format);
  const period = server.current_period;

  return (
    <div className="settings-tab">
      <PanelGrid>
        <Panel title={t("settings.regional.location")} hint={t("settings.regional.locationHint")} accent>
          <TextField
            id="country"
            label={t("settings.regional.country")}
            value={draft.country}
            onChange={(v) => patch({ country: v })}
            error={fieldErrors.country}
          />
          <TextField
            id="state"
            label={t("settings.regional.state")}
            value={draft.state}
            onChange={(v) => patch({ state: v })}
            help={t("settings.regional.stateHelp")}
            error={fieldErrors.state}
          />
          {/* DEF-082 — A DROP-DOWN, and deliberately not the type-ahead this
              shipped as on 2026-08-09. BR-SHL-033 mandates SearchSelectField
              PAST LONG_LIST_THRESHOLD (10); this list is EIGHT, so the rule
              points the other way, and the signed prototype draws a `<select>`
              (UtilityBilling.html 4517). The difference is not cosmetic: the
              type-ahead is a text box that opens nothing on a click and shows
              nothing until you type, which is why the PO reported the control
              as absent while it was on the screen in front of them.

              The help line is the whole reason the field matters — BR-TEN-081,
              in the words of the person choosing the value. */}
          <SelectField
            id="timezone"
            label={t("settings.regional.timezone")}
            value={draft.timezone}
            onChange={(v) => patch({ timezone: v })}
            options={timezoneOptions(draft.timezone).map((zone) => ({
              value: zone,
              label: zone,
            }))}
            help={t("settings.regional.timezoneHelp")}
            placeholder={t("settings.regional.choose")}
            error={fieldErrors.timezone}
          />
          <SelectField
            id="language"
            label={t("settings.regional.language")}
            value={draft.language}
            onChange={(v) => patch({ language: v })}
            options={LANGUAGE_OPTIONS.map((code) => ({
              value: code,
              // BR-SHL-041's registry is the native-label source for the six
              // locales added 2026-08-11. The six pre-expansion codes still
              // carry `settings.regional.language.<code>` catalogue entries
              // from before the registry existed and are honoured first, so no
              // copy already on screen changes here; `defaultValue` is what
              // stops i18next printing the raw key for a code that has no such
              // entry — the exact failure G15 was written for.
              label: t(`settings.regional.language.${code}`, { defaultValue: localeLabel(code) }),
            }))}
            placeholder={t("settings.regional.choose")}
            error={fieldErrors.language}
          />
          <SelectField
            id="first_day_of_week"
            label={t("settings.regional.firstDay")}
            value={draft.first_day_of_week}
            onChange={(v) => patch({ first_day_of_week: v })}
            options={FIRST_DAY_OPTIONS.map((day) => ({
              value: day,
              label: t(`settings.regional.day.${day}`),
            }))}
            placeholder={t("settings.regional.choose")}
            error={fieldErrors.first_day_of_week}
          />
        </Panel>

        <Panel title={t("settings.regional.formats")} hint={t("settings.regional.formatsHint")}>
          <SelectField
            id="currency"
            label={t("settings.regional.currency")}
            value={draft.currency}
            onChange={(v) => patch({ currency: v })}
            options={CURRENCY_OPTIONS.map((code) => ({ value: code, label: code }))}
            help={t("settings.regional.currencyHelp")}
            error={fieldErrors.currency}
          />
          <SelectField
            id="number_format"
            label={t("settings.regional.numberFormat")}
            value={draft.number_format}
            onChange={(v) => patch({ number_format: v })}
            options={NUMBER_FORMAT_OPTIONS.map((f) => ({ value: f, label: f }))}
            placeholder={t("settings.regional.choose")}
            error={fieldErrors.number_format}
          />
          <SelectField
            id="date_format"
            label={t("settings.regional.dateFormat")}
            value={draft.date_format}
            onChange={(v) => patch({ date_format: v })}
            options={DATE_FORMAT_OPTIONS.map((f) => ({ value: f, label: f }))}
            placeholder={t("settings.regional.choose")}
            error={fieldErrors.date_format}
          />
          {/* ⚠ **DEF-753 — THE ONE FORMAT THAT BEHAVES DIFFERENTLY IN THE TWO
              DIRECTIONS, SAID OUT LOUD AT THE MOMENT IT IS CHOSEN.** Screens and
              bills write this month name through `Intl` in the tenant's own
              language (`25-Okt-26` for a German utility); the CSV IMPORTER reads
              it with `%b` in the C locale, which accepts English abbreviations
              only, so that same file is refused row by row. Refusing is safe —
              nothing is mis-dated, and guessing month names in eleven languages
              is what BR-MET-117 forbids — but a utility that met it got 9,881
              rejections and no reason. Drawn only when this format is selected;
              the other six are digits and have no such trap. */}
          {draft.date_format === "DD-MMM-YY" && (
            <p className="field-help" data-tracks="DEF-753">
              {t("settings.regional.dateFormat.monthNamesEnglishOnly", {
                defaultValue:
                  "Screens and bills show this month name in your own language. CSV imports are different: they read ENGLISH month names only (Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec), so a file written 25-Okt-26 or 25-mars-26 is refused row by row. Choose a numeric format if your files use month names in another language.",
              })}
            </p>
          )}
          <SelectField
            id="time_format"
            label={t("settings.regional.timeFormat")}
            value={draft.time_format}
            onChange={(v) => patch({ time_format: v })}
            options={TIME_FORMAT_OPTIONS.map((f) => ({
              value: f,
              label: t(`settings.regional.time.${f}`),
            }))}
            placeholder={t("settings.regional.choose")}
            error={fieldErrors.time_format}
          />
          {/* BR-SHL-034: the preview goes through the SHARED formatters, so it
              cannot drift from what the rest of the app will render. */}
          <div className="settings-preview">
            <Kicker>{t("settings.regional.preview")}</Kicker>
            <p className="settings-preview-line">
              <b>{formatDate(PREVIEW_DATE, draft.timezone === "" ? "UTC" : draft.timezone, dateFormat)}</b>
              {" · "}
              <b>{formatMoney(PREVIEW_AMOUNT, draft.currency === "" ? "USD" : draft.currency, locale)}</b>
            </p>
            <p className="settings-preview-note">
              {t("settings.regional.previewNote", {
                day:
                  draft.first_day_of_week === ""
                    ? t("settings.regional.unset")
                    : t(`settings.regional.day.${draft.first_day_of_week}`),
                zone: draft.timezone === "" ? t("settings.regional.unset") : draft.timezone,
              })}
            </p>
          </div>
        </Panel>

        <Panel title={t("settings.regional.fiscal")} hint={t("settings.regional.fiscalHint")}>
          <SelectField
            id="fy_start_month"
            label={t("settings.regional.fyStartMonth")}
            value={draft.fy_start_month}
            onChange={(v) => patch({ fy_start_month: v })}
            options={MONTH_OPTIONS.map((month) => ({
              value: String(month),
              label: t(`settings.regional.month.${month}`),
            }))}
            placeholder={t("settings.regional.choose")}
            error={fieldErrors.fy_start_month}
          />
          <TextField
            id="fy_start_day"
            label={t("settings.regional.fyStartDay")}
            value={draft.fy_start_day}
            onChange={(v) => patch({ fy_start_day: v })}
            numeric
            error={fieldErrors.fy_start_day}
          />
          {/* The accrual/cash SELECT stood here until 2026-08-17 and was
              REMOVED by PO ruling (CR-008 #1, *"take it off"*): nothing in the
              product read the value. See ACCOUNTING_METHOD_OPTIONS above. */}
          <SelectField
            id="close_cadence"
            label={t("settings.regional.closeCadence")}
            value={draft.close_cadence}
            onChange={(v) => patch({ close_cadence: v })}
            options={CLOSE_CADENCE_OPTIONS.map((c) => ({
              value: c,
              label: t(`settings.regional.cadence.${c}`),
            }))}
            placeholder={t("settings.regional.choose")}
            error={fieldErrors.close_cadence}
          />
          <TextField
            id="close_day"
            label={t("settings.regional.closeDay")}
            value={draft.close_day}
            onChange={(v) => patch({ close_day: v })}
            help={t("settings.regional.closeDayHelp")}
            error={fieldErrors.close_day}
          />

          {/* BR-TEN-022: the card is the SERVER's computation, rendered. */}
          <div className="settings-preview">
            <Kicker>{t("settings.regional.currentPeriod")}</Kicker>
            {period === null ? (
              <p className="settings-preview-note">{t("settings.regional.noPeriod")}</p>
            ) : (
              <>
                <p className="settings-preview-line">
                  <b>
                    {t("settings.regional.periodLabel", {
                      fy: period.fy_label,
                      period: period.period,
                    })}
                  </b>
                  {" — "}
                  {formatDate(period.start, "UTC", dateFormat)}
                  {" – "}
                  {formatDate(period.end, "UTC", dateFormat)}
                </p>
                <p className="settings-preview-note">
                  {period.close_by === null
                    ? t(`settings.regional.periodStatus.${period.status}`)
                    : t("settings.regional.periodCloses", {
                        status: t(`settings.regional.periodStatus.${period.status}`),
                        date: formatDate(period.close_by, "UTC", dateFormat),
                      })}
                </p>
              </>
            )}
          </div>

          <CheckboxField
            id="lock_closed_periods"
            label={t("settings.regional.lockClosed")}
            checked={draft.lock_closed_periods}
            onChange={(checked) => patch({ lock_closed_periods: checked })}
          />
          {/* BR-TEN-038 (OQ-033 CLOSED): the toggle STORES the value; the
              enforcement it drives lives in the ledger posting service (W5).
              The line names the ruled behaviour instead of leaving the user to
              guess what "lock" will do. */}
          <Note>{t("settings.regional.lockClosedRule")}</Note>
        </Panel>
      </PanelGrid>

      <RefusalNotice refusal={refusal} />

      {confirmCurrency && (
        // BR-SHL-032: the button names the action; never "OK".
        <ConfirmDialog
          title={t("settings.regional.currencyConfirmTitle")}
          consequence={t("settings.regional.currencyConfirmBody", {
            from: original.currency,
            to: draft.currency,
          })}
          confirmLabel={t("settings.regional.currencyConfirmAction", { to: draft.currency })}
          working={save.isPending}
          onConfirm={commit}
          onCancel={() => setConfirmCurrency(false)}
        />
      )}

      <SaveBar
        saveLabel={t("settings.regional.save")}
        working={save.isPending}
        dirty={regionalIsDirty(draft, original)}
        readOnly={props.readOnly}
        readOnlyReason={t("settings.readOnlyReason")}
        onSave={handleSave}
        onDiscard={() => {
          setEdits(null);
          setFieldErrors({});
          setRefusal(null);
        }}
        // BR-TEN-020, in the user's words.
        note={t("settings.regional.noRestatement")}
      />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-006@0733260 (story+rules snapshot hash — EP-TEN-05)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-11 by story-coder v1 (eleven-locale lane — LANGUAGE_OPTIONS grows to BR-SHL-041's twelve accepted codes and the picker label falls back to the locale registry so a new code can never print its raw key) · AMENDED 2026-08-15 by story-coder v1 (DEF-082 tenant-timezone lane — the Timezone control becomes a real `<select>` and always contains the tenant's STORED zone; the BR-TEN-081 help line lands beside it)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope) · [DEF-082 lane 2026-08-15] the three timezone assertions were shown RED on the SHIPPED markup first (law 7): `expected 'for="timezone">Timezone</label><div c…' to contain '<select id="timezone"'`, and for a tenant holding America/Detroit the control rendered `<input id="timezone" … value=""/>` — a clock that was set and invisible. tsc✔ eslint --max-warnings 0✔ vitest 947 passed / 185 todo across 65 files✔ (pre-lane baseline 936 passed / 5 FAILED across 64 — those five were the concurrent DEF-088 money-decimals lane's and cleared while this lane ran; nothing was dropped). run_gates 19 PASS / 1 FAIL / 0 SKIP on both runs, and the FAIL was a DIFFERENT other-lane file each time (G8 on apps/billing/backbill.py, then G7 on apps/ledger/migrations/0006 once that lane landed) — neither file is touched by this lane. Every gate that could see this lane's work is green: G1/G2/G3/G10/G11/G13/G14/G15/G18/G19/G20 PASS, with G15 holding 3542 keys across all 11 catalogues and G18 finding a call site for the new key and none for the retired one
// exceptions: E2 US-TEN-006 TC-6 expects "Español — coming soon" DISABLED (IS-8 v1.1), but the shipped server accepts en/en-US/es/es-MX/de/hi/fr-FR/id-ID/it-IT/ja-JP/ko-KR/pt-BR and eleven catalogs ship (BR-SHL-041, 2026-08-11) — the offered set is the server's validated tuple and the IS-8 v1-English-only note is reported, not enforced client-side · E4 the fiscal "Close by" control is a free-text field (the server parses "3rd business day"/"5 days"); the prototype's three-option select would refuse values the server accepts — divergence reported · [DEF-082 2026-08-15] TIMEZONE_OPTIONS stays A1 §S8's EIGHT US zones rather than the whole IANA list the defect row's fix line names: A1 ratifies eight, the product is US-only, and a ~600-entry picker is a spec change rather than a defect fix. What the eight could NOT do — express a zone a tenant already holds — is fixed by timezoneOptions() instead. Widening the offered set is REPORTED for the PO, not taken here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
