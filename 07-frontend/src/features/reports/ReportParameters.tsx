// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · P2.6 (the class control) · P2.7 (real date
//          fields, and an inverted range refused AT THE CONTROL).
//          Built from `05-prototype/09 Reports Build Brief.pdf` p024 (2·1a's
//          slicer bar, notes ② and ③b), p025 (2·1b, the **To must not be
//          before From** message under the To field) and p011 (the task rows),
//          read as RENDERED IMAGES per B14 rule 42.
// Rules:   B14 rule 7 (a date field IS the date input, with its bounds) ·
//          B14 rule 33 (a FACT ≤ 6 words; an INSTRUCTION ≤ 6 words per
//          sentence; RATIONALE is zero words on screen) ·
//          B14 rule 43 (a piece of UI used twice is a COMPONENT) ·
//          B14 rule 44 (the drawing says WHAT and HOW ARRANGED; our kit says
//          HOW IT IS BUILT, and it wins) · BR-REP-006 (a filter enumerates the
//          LIVE vocabulary, never a hardcoded list) · BR-SHL-011 (the URL
//          grammar; an invalid value falls back, never errors).
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE TWO KEYSTROKES THAT COST TWO 422s, AND WHY THE FIX IS HERE          ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Walked on the running product on 2026-09-23 and again on 2026-09-26: on the
// billing register, typing **09/30** into *From* and then **09/01** into *To*
// sends TWO requests and collects TWO 422s — and the first of them is fired by
// a *From* with no *To* at all, before the clerk has finished. The screen then
// replaces the report with a server error panel, twice.
//
// **Neither request could ever have succeeded**, and both facts were knowable
// in the browser: `apps/reports/api._required_window` requires BOTH bounds and
// refuses `start > end`. So the refusal moves to the control —
// `reports.param.rangeInverted` under *To*, exactly where the drawing puts it
// on 2·1b — and `reportRunnable()` below is what the page's query is `enabled`
// on. **The outcome is a NUMBER: zero requests.**
//
// ⚠ **THE REFUSAL MUST GO AWAY AGAIN, AND THAT IS THE HALF THAT SHIPS BROKEN.**
// A message asserted in one direction only is how a defect shipped on this
// branch today: a refusal stayed on screen after the clerk had fixed it and ten
// browser cases passed, because not one of them asked whether a message had
// GONE. `rangeProblem` is a pure function of the two values with no memory at
// all, so there is nothing to leave behind — and the test asserts both
// directions.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHY THE CLASS CONTROL IS NEW AND THE READ IS NOT                        ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// `apps/reports/queries.ar_aging` has read `class` since the day it was
// written — `params.get("class") or params.get("f.class")` — and no control was
// ever drawn for it, so the capability existed, was tested, and could not be
// reached by anybody. That is hard-won law 2 in its plainest form: built is not
// wired.
//
// The vocabulary is `GET /lookups/account_types` and NOT a list in this file.
// BR-REP-006 is explicit, and `queries.parameter_vocabularies` says in its own
// docstring why the class list is deliberately absent from the report payload:
// *"a second read of one vocabulary is the drift BR-REP-006 exists to
// prevent"*.
//
// ⚠ **AND WHEN THAT READ ANSWERS NOTHING, NO CONTROL IS DRAWN.** A class select
// holding only *All classes* is a control that cannot filter — the mirror of
// the dead-control defect above, and worse than an absent one, because it
// promises.
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { DatePickerField } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { ReportQuery, ReportResponse } from "@/api/reportsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The reference list behind the consumer-class control (`account_types.code`
 *  — the exact column `customers.account_ids_of_class` filters on). */
export const ACCOUNT_CLASS_LIST = "account_types";

/**
 * Which filters the parameter bar offers for a report.
 *
 * ⚠ **OFFERING A CONTROL THE SERVER IGNORES MAKES A REPORT LOOK FILTERED**,
 * which is worse than one that is not — US-LED-009 §8's rule, applied
 * generally. `class` joins `ar_aging` here because the query has always read
 * it; it is NOT added to the register, whose `invoices` dataset declares the
 * filter but whose seam does not yet honour it.
 */
export const REPORT_FILTERS: Readonly<Record<string, readonly string[]>> = {
  ar_aging: ["asOf", "class", "service"],
  billing_register: ["window", "bill_type", "service"],
  revenue_by_service_rate: ["window"],
  payments_by_method: ["window", "purpose"],
  // `CR-184-BRC10` — a position at a date, exactly as the ageing is.
  receivables_over_90_by_service: ["asOf"],
};

/**
 * The filters a report built on a DATASET offers when its KEY names none —
 * a utility's own report, saved from the builder under a key of its choosing.
 *
 * ⚠ **`CR-184-BRC10`: WITHOUT THIS A CUSTOM RECEIVABLES REPORT HAD NO AS-OF
 * BOX.** `REPORT_FILTERS` is keyed by report, and a report a clerk builds has
 * a key nobody typed here — so the position date could not be changed from
 * the screen at all. Keyed by the dataset's CODE, never by a list of its
 * reports, so every report built on it inherits the control.
 */
export const DATASET_FILTERS: Readonly<Record<string, readonly string[]>> = {
  receivables: ["asOf"],
};

/** What the parameter bar offers: the report's own list, else its dataset's. */
export function offeredFilters(key: string, dataset?: string): readonly string[] {
  return REPORT_FILTERS[key] ?? (dataset === undefined ? undefined : DATASET_FILTERS[dataset]) ?? [];
}

/**
 * What is wrong with the window the clerk has typed, as a message KEY — or
 * null when there is nothing wrong with it.
 *
 * Three states and they are NOT the same:
 *   · nothing typed yet, or half typed — **no message.** A clerk who has filled
 *     *From* and not yet reached *To* has made no mistake, and a red sentence
 *     while they are still typing is the screen shouting at a half-finished
 *     thought. It is still not RUNNABLE, which is a different question.
 *   · both typed, inverted — **the message**, under *To*, where the drawing
 *     puts it.
 *   · both typed, in order — **no message**, and the report runs.
 */
export function rangeProblem(from: string, to: string): string | null {
  if (from === "" || to === "") {
    return null;
  }
  return from > to ? "reports.param.rangeInverted" : null;
}

/**
 * May this report be RUN with the parameters as they stand?
 *
 * ⚠ **THIS IS THE FUNCTION THE `enabled` FLAG READS, AND IT IS THE WHOLE OF
 * `P2.10`.** `false` means the page issues no request at all — not a request
 * whose failure is handled prettily.
 *
 * ⚠ **AN EMPTY WINDOW IS RUNNABLE, AND GETTING THAT WRONG BROKE TWO REPORTS
 * FOR TEN MINUTES.** The first draft required both bounds always, which is what
 * the brief's sentence sounds like — and the billing register and payments by
 * method then opened onto NOTHING, because a clerk arriving from the catalogue
 * has typed no dates at all. `apps/reports/queries._checked_window` falls back
 * to the TENANT's accounting period (BR-TEN-022), which is the whole reason
 * those two reports have ever opened with no parameters. Only
 * `apps/reports/api._required_window` — the account ledger and by-premises
 * path — demands both, and neither of those renders here.
 *
 * So the three states are: **empty → run** (the tenant's period), **half typed
 * → do not run** (this is the request that used to fire while the clerk was
 * still typing), **inverted → do not run**.
 *
 * A report on a POSITION (`asOf`) is always runnable: absent, the server uses
 * the tenant's period END, which is the day the AR tie-out is struck and the
 * only date that makes the two figures comparable.
 */
export function reportRunnable(key: string, query: ReportQuery, dataset?: string): boolean {
  const offered = offeredFilters(key, dataset);
  if (!offered.includes("window")) {
    return true;
  }
  const from = query.from ?? "";
  const to = query.to ?? "";
  if (from === "" && to === "") {
    return true;
  }
  return from !== "" && to !== "" && from <= to;
}

/**
 * The slicer bar: the definition's own parameters, side by side.
 *
 * ⚠ **THE DRAWING PUTS FOUR SLICERS AND A `+ Filter · 9 more` ON THIS ROW AND
 * ONLY THE FIRST PART IS THIS LANE'S.** The `+ Filter` panel, the applied-filter
 * chips and the Route slicer are `P2.26`/`P2.17` (lane REP-P2-MODEL, derived
 * from the dataset's declared dimensions). They are NOT drawn here as inert
 * furniture: the brief's own finding is that *"thirteen chips on screen is a
 * worse screen, not a better one"*, and a `+ Filter` button over a panel that
 * does not exist is the dead control this phase is removing.
 */
export function ReportParameters(props: {
  reportKey: string;
  /** The dataset the report is built on — the fallback for a key
   *  `REPORT_FILTERS` does not name (`DATASET_FILTERS`). */
  dataset?: string;
  query: ReportQuery;
  onChange: (next: Partial<ReportQuery>) => void;
  vocab: ReportLibraryVocabularies | undefined;
  /** IS-8 — the TENANT's date format and zone, never the browser's. */
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** Today in the TENANT's zone, `YYYY-MM-DD`. The caller derives it because a
   *  `new Date()` in here would read the BROWSER's clock. */
  today: string;
  t: Translator;
  client?: ApiClient;
}) {
  const { t, query, reportKey } = props;
  const offered = offeredFilters(reportKey, props.dataset);
  const from = query.from ?? "";
  const to = query.to ?? "";
  const problem = rangeProblem(from, to);

  // BR-REP-006 — the live list, from the read S18's customer-type select
  // already uses. `retry: false`: a Billing Clerk who cannot read the lookup
  // gets one refusal rather than three, and the control is then absent.
  const classesQuery = useQuery({
    queryKey: queryKeys.lookupEntries(ACCOUNT_CLASS_LIST, "", 1, 100),
    queryFn: () => getLookupEntries(ACCOUNT_CLASS_LIST, { page: 1, per: 100 }, props.client ?? api),
    retry: false,
    enabled: offered.includes("class"),
  });
  const classes = (classesQuery.data?.results ?? []).filter((entry) => entry.active);

  return (
    <>
      {offered.includes("window") && (
        <>
          <DatePickerField
            id="rep-from"
            label={t("reports.param.from")}
            value={from}
            dateFormat={props.dateFormat}
            todayValue={props.today}
            // B14 rule 7 — the bound the message promises is the bound the
            // field carries. A `max` of the other end makes the picker itself
            // refuse the inverted range before a key is pressed.
            max={to === "" ? undefined : to}
            onChange={(value) => props.onChange({ from: value })}
          />
          <DatePickerField
            id="rep-to"
            label={t("reports.param.to")}
            value={to}
            dateFormat={props.dateFormat}
            todayValue={props.today}
            min={from === "" ? undefined : from}
            // The refusal, AT the control, in the place 2·1b draws it.
            error={problem === null ? undefined : t(problem)}
            onChange={(value) => props.onChange({ to: value })}
          />
        </>
      )}
      {offered.includes("asOf") && (
        <DatePickerField
          id="rep-asof"
          label={t("reports.param.asOf")}
          value={to}
          dateFormat={props.dateFormat}
          todayValue={props.today}
          // ⚠ THE ZONE IS NAMED. A position at a date means nothing without
          // saying whose midnight — and it is the TENANT's, which is the only
          // place on this screen a clerk can learn that. Six words, a FACT.
          help={t("reports.param.asOfHelp", { zone: props.timeZone })}
          onChange={(value) => props.onChange({ to: value })}
        />
      )}
      {offered.includes("class") && classes.length > 0 && (
        <div className="field">
          <label htmlFor="rep-class">{t("reports.param.class")}</label>
          <select
            id="rep-class"
            className="input"
            value={query.class ?? ""}
            onChange={(event) => props.onChange({ class: event.target.value })}
          >
            <option value="">{t("reports.param.allClasses")}</option>
            {classes.map((entry) => (
              <option key={entry.code} value={entry.code}>
                {entry.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {offered.includes("bill_type") && (
        <div className="field">
          <label htmlFor="rep-bill-type">{t("reports.param.billType")}</label>
          <select
            id="rep-bill-type"
            className="input"
            value={query.bill_type ?? ""}
            onChange={(event) => props.onChange({ bill_type: event.target.value })}
          >
            <option value="">{t("reports.param.allBillTypes")}</option>
            {(props.vocab?.bill_types ?? []).map((value) => (
              <option key={value} value={value}>
                {t(`reports.value.bill_type.${value}`, { defaultValue: value })}
              </option>
            ))}
          </select>
        </div>
      )}
      {offered.includes("purpose") && (
        <div className="field">
          <label htmlFor="rep-purpose">{t("reports.param.purpose")}</label>
          <select
            id="rep-purpose"
            className="input"
            value={query.purpose ?? ""}
            onChange={(event) => props.onChange({ purpose: event.target.value })}
          >
            <option value="">{t("reports.param.allPurposes")}</option>
            {(props.vocab?.purposes ?? []).map((value) => (
              <option key={value} value={value}>
                {t(`reports.value.purpose.${value}`, { defaultValue: value })}
              </option>
            ))}
          </select>
        </div>
      )}
      {offered.includes("service") && (
        <div className="field">
          <label htmlFor="rep-service">{t("reports.param.service")}</label>
          <select
            id="rep-service"
            className="input"
            value={query.service ?? ""}
            onChange={(event) => props.onChange({ service: event.target.value })}
          >
            {/* BR-REP-006 — the TENANT's ENABLED services. A two-service
                utility sees two options; the prototype's hardcoded trio appears
                nowhere in this file. */}
            <option value="">{t("reports.param.allServices")}</option>
            {(props.vocab?.services ?? []).map((service) => (
              <option key={service.code} value={service.code}>
                {service.name}
              </option>
            ))}
          </select>
        </div>
      )}
    </>
  );
}

/** What the library call already carries for this bar (BR-REP-006). Typed here
 *  rather than imported so this file names exactly what it reads. */
export interface ReportLibraryVocabularies {
  services?: { code: string; name: string }[];
  bill_types?: string[];
  purposes?: string[];
}

export type { ReportResponse };
