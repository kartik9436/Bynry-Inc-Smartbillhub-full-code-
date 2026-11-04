// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-014 (auto-estimate a missing read — trailing-3 daily
//           average, max 2 consecutive, PER CHANNEL) · US-MET-015 (the staff
//           override/skip half: the clerk decides, the server refuses)
//           Screens: S25 (this is its "estimate a missing read" surface)
// Rules:    BR-MET-026 (daily_avg = Σ last-3 ACTUAL consumptions ÷ Σ their day
//           counts; estimate = daily_avg × days_in_period; NUMERIC(18,6)
//           unrounded; actuals only; ≥1 actual required; no history → no
//           estimate) · BR-MET-027 (the tenant's consecutive cap; beyond it a
//           field visit is FORCED) · BR-MET-028 (labelled with method +
//           consecutive number, status `estimated`, NO register value) ·
//           BR-MET-058 (PER CHANNEL — a TOU window never borrows another's
//           history) · BR-MET-062 (a missing `demand` value is NEVER estimated)
//           · BR-SHL-020 (the six A18 states) · BR-SHL-025 (a control this role
//           cannot use renders disabled WITH its reason) · BR-SHL-033 (dates
//           through the shared picker) · CLAUDE.md rule 3 (consumption ALWAYS
//           carries an explicit unit)
// ───────────────────────────────────────────────────────
// S25 → **Estimate a missing read**: the first screen that can reach the
// estimation engine.
//
// `apps/metering/estimation.py` and the `POST /reads/estimate` route shipped
// 2026-08-10 and 2026-08-11 respectively, correct to GT-9's digits, and NO
// SCREEN CALLED EITHER. A clerk with a meter that could not be read had no way
// to fill the gap, which means the bill run had no way to produce a bill for
// that customer at all. That is hard-won law 2 at feature scale, and it is
// what this screen fixes.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TWO THINGS THIS SCREEN MUST NEVER DO
// ══════════════════════════════════════════════════════════════════════════
// **1. It must never show a consumption without its unit (CLAUDE.md rule 3).**
// Not "618.000000". Not "618.000000 (kWh assumed)". The server returns `unit`
// on the estimate and on the refusal alike, and `EstimateFigure` below takes
// the unit as a REQUIRED string so an omission does not typecheck. A reading
// screen that drops the unit is the defect that rule exists for: 618 kWh and
// 618 CCF are different bills.
//
// **2. It must never render a refusal as a result.** `POST /reads/estimate`
// answers 200 with `estimated: false` and a reason when it will not estimate —
// "no history, a field visit is needed", "the consecutive cap is reached", "a
// demand peak is never estimated". Those are ANSWERS the clerk has to act on,
// which is why the server returns them as data rather than raising. A screen
// that renders them as an empty result, or worse as a 0.000000 consumption,
// turns a refusal into a number that will be billed. Every refusal here gets
// its own plain-language sentence and, where the rule forces one, the words
// "a field visit is needed".
//
// WHAT IS DELIBERATELY ABSENT
// ----------------------------
// There is no "override this estimate with my own figure" control, although
// US-MET-015 names a `manual_override` method. `estimate_missing_read` is the
// only write path the server publishes and it takes no override amount; the
// override would need its own endpoint and its own audit action. Offering the
// field over a route that ignores it is precisely the promise this codebase
// keeps getting bitten by, so the control is not drawn and this paragraph is
// the record of why.
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { READ_CHANNELS, estimateRead } from "@/api/endpoints";
import type { EstimateReadResult } from "@/api/endpoints";
import {
  DatePickerField,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatQuantity } from "@/components/UnitCell";
import type { Translator } from "@/features/tenancy/settingsShared";

import { useRegional } from "./meteringShared";
import type { RegionalProps } from "./meteringShared";

/**
 * ⛔ **THE ELEVEN `rd-est-*` CLASSES ARE GONE FROM `reads.css` (CR-054 W0 T3).**
 *
 * B14 rule 21 in full: a new screen, component or piece of UI is written in
 * Tailwind utilities and adds NO class to a stylesheet — and existing CSS
 * shrinks only as a migration phase takes it. This file was the LAST Reads file
 * NOT on `styles/route-b-migrated.txt`, which made it the one place in the
 * module where a utility compiles to nothing: the class lands in the DOM, so
 * `tsc`, eslint and every `toContain("flex")` assertion pass on a screen that
 * renders unstyled. It joins the list in THIS commit, with the classes deleted
 * and the G31 ceiling lowered by eleven in the same one — a ceiling nobody
 * tightens is a number nobody reads.
 *
 * Every declaration below is the token the stylesheet used, not a redesign:
 * `--space-N` is N × 4px and IS Tailwind's scale, so the numbers carry across
 * unchanged, and the two muted colours keep their exact `color-mix` percentages.
 */
const MUTED65 = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
const MUTED75 = "text-[color-mix(in_srgb,var(--color-text)_75%,transparent)]";

/** `.rd-est-outcome` — the panel both answers share. */
const OUTCOME = "mt-6 border-l-[3px] bg-surface p-4";
/** `.rd-est-made` / `.rd-est-refused` — the ONLY difference between them. */
const OUTCOME_MADE = "border-l-success-500";
const OUTCOME_REFUSED = "border-l-warning-500";
/** `.rd-est-outcome h3` — `text-h4` carries `--font-heading-weight` for us. */
const OUTCOME_TITLE = "m-0 mb-3 font-heading text-h4";
/** `.rd-est-facts` — the definition grid. */
const FACTS = "m-0 mb-3 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-2";
/**
 * `.rd-est-reason` / `.rd-est-fieldvisit` / `.rd-est-note` — one declaration.
 *
 * ⚠ **A PLAIN STRING, NOT A TEMPLATE LITERAL, AND THE LINTER IS RIGHT TO INSIST.**
 * Tailwind only generates what its scanner SEES, so a class name assembled in a
 * template is broken before anything renders — the utility never reaches the
 * stylesheet and the class sits inertly in the DOM. That is the same failure
 * mode as writing a utility in an unmigrated file, one layer down.
 *
 * ⚠ **`line-height` MOVES 1.55 → `leading-prose` (1.6), DELIBERATELY.** The
 * deleted CSS hand-picked 1.55, which matches no ruled step: the scale offers
 * `--leading-relaxed` (1.45) and `--leading-prose` (1.6, *"explainer + lede
 * paragraphs"*), and these three sentences are explainers. Taking the ruled step
 * is what a migration is FOR — a hand-picked value is how a scale acquires
 * fourteen near-identical neighbours. The visible change is 0.05 of a line.
 * (`customers.css` still carries a second hand-picked 1.55; out of scope here
 * and REPORTED rather than swept in.)
 */
const SENTENCE = "m-0 mb-2 max-w-measure text-sm leading-prose";

/**
 * **THE REGISTERS THIS DIALOG OFFERS — `READ_CHANNELS`, NOT A SECOND COPY OF IT
 * (`DEF-MET-5203`, high, and it is the reason this constant is now one line).**
 *
 * ⚠ **IT USED TO BE A HAND-WRITTEN FIVE AND THREE OF THEM DID NOT EXIST.** The
 * list read `["total", "peak", "mid_peak", "off_peak", "demand"]` while the
 * server's own vocabulary (`apps/metering/models.CHANNELS`) is `total · tou_on ·
 * tou_mid · tou_off · export · demand · generation`. So the dialog POSTED
 * `peak`, `mid_peak` and `off_peak`, which `POST /reads/estimate` refuses **by
 * name** — *"not a register on this meter"* — and of five choices exactly ONE,
 * Total consumption, could produce an estimate. A time-of-use meter short of
 * its mid-peak window before a bill run could not be estimated from this dialog
 * at all, which is the exact case the blueprint draws on screen twice.
 *
 * ⚠ **AND THE COMMENT ABOVE IT SAID THE LIST *WAS* THE SERVER'S** — hard-won
 * law 1 in one line: a comment claiming a guarantee is not the guarantee. So
 * the fix is not to correct three strings, it is to stop there being a second
 * list to correct (hard-won law 5). `READ_CHANNELS` is the client's ONE mirror
 * of `models.CHANNELS`, it is what the reads list, the upload wizard and the
 * quick-read modal already filter and sort by, and the register WORDS come from
 * `metering.reads.channel.*` — `BR-MET-170` (3)'s own vocabulary, which is what
 * every other screen in the module prints.
 *
 * ⚠ **NOTHING CAUGHT IT BECAUSE THE THREE WRONG WORDS RESOLVED IN ELEVEN
 * LANGUAGES.** Every key existed, the dropdown rendered three perfectly good
 * options, `tsc` passed and every test passed. A dropdown whose options all
 * translate proves the WORDS exist and never that the server accepts the
 * VALUES, which is why the guard below asserts against `READ_CHANNELS` rather
 * than against a list of its own.
 *
 * ⚠ **`demand` IS STILL OFFERED, DELIBERATELY, AND `BR-MET-062` STILL REFUSES
 * IT.** Hiding the option would leave a clerk with a missing demand peak no way
 * to find out why they cannot estimate it, and they would try again tomorrow.
 * The refusal (`metering.estimate.reason.demand_never_estimated`) explains
 * itself once, which is a better answer than a control that silently does not
 * exist — and the blueprint's own floor note says the same thing in five words:
 * *"A demand register is never estimated. Send someone out."*
 */
export const ESTIMATE_CHANNELS = READ_CHANNELS;

/**
 * Mirrors the server's own validation so the clerk is told before a round trip;
 * the server stays the authority (B8) and every refusal rendered here comes
 * back out of its envelope.
 */
export const estimateSchema = z.object({
  meter_no: z.string().trim().min(1).max(80),
  channel: z.string().trim().min(1),
  read_at: z.string().trim().min(1),
});

/**
 * A consumption and its unit, together, always.
 *
 * `unit` is a REQUIRED string rather than `string | null`, and that is the
 * whole point of the component: CLAUDE.md rule 3 says consumption always
 * carries an explicit unit, and a type that permits the omission is a rule
 * enforced by memory. When the server sends no unit the caller must render the
 * absence — see `UnitlessFigure` — never the bare number.
 */
export function EstimateFigure(props: { value: string; unit: string }) {
  return (
    <span className="whitespace-nowrap" data-cell="estimate-figure">
      {/* ⚠ **`BR-MET-144` — at most two decimals, trailing zeros TRIMMED, and
          the storage does not move.** This printed `412.000000` because it
          rendered the served decimal string raw, and `8.000000` is `8` rather
          than `8.00`: a currency's precision is a property of the currency,
          a quantity's is what the meter measured. `formatQuantity` is the ONE
          composer of that rule on the client and is what every other reads
          surface already uses — this does not choose a rounding, it stops this
          screen being the one that does not apply the signed one. (PO
          2026-09-14, on the same question for a reading: *"as drawn"*.) */}
      <span className="font-semibold tabular-nums" data-cell="estimate-value">
        {formatQuantity(props.value)}
      </span>{" "}
      <span className={`text-sm ${MUTED75}`} data-cell="estimate-unit">
        {props.unit}
      </span>
    </span>
  );
}

/**
 * What to render when the server sent a quantity and no unit.
 *
 * This should be impossible — `estimation.estimate` sets `unit` on every result
 * and `estimate_missing_read` falls back to the asset's own unit — so this
 * branch exists to make the impossible LOUD rather than to paper over it. The
 * number is deliberately NOT shown: an unlabelled consumption is the one thing
 * rule 3 forbids, and showing it with a warning beside it would still put a
 * figure on screen that a clerk could copy into a bill.
 */
export function UnitlessFigure(props: { reason: string }) {
  return (
    <span className="text-sm text-danger-700" role="note">
      {props.reason}
    </span>
  );
}

/**
 * The result panel: an estimate WITH its arithmetic, or a refusal WITH its
 * reason. One component for both, because they are the two halves of one
 * answer and splitting them is how a screen ends up rendering neither.
 */
export function EstimateOutcome(props: { result: EstimateReadResult; t: Translator }) {
  const { result, t } = props;

  if (!result.estimated) {
    // A REFUSAL IS AN ANSWER. It gets the same visual weight as a success and a
    // sentence the clerk can act on, keyed off the server's own reason code.
    // An unknown code falls back to the code itself rather than to silence —
    // a reason nobody translated is still a reason (BR-SHL-020).
    const reason = result.reason ?? "unknown";
    return (
      <div className={`${OUTCOME} ${OUTCOME_REFUSED}`} role="note">
        <h3 className={OUTCOME_TITLE}>{t("metering.estimate.refusedTitle")}</h3>
        <p className={SENTENCE}>
          {t(`metering.estimate.reason.${reason}`, { defaultValue: reason })}
        </p>
        {/* BR-MET-026 / BR-MET-027: two of the refusals FORCE a field visit,
            and the server says which by sending `forced_disposition`. It is
            said in words because "no history" alone does not tell a clerk what
            to do next. */}
        {result.detail?.forced_disposition === "field_visit" && (
          <p className={`${SENTENCE} font-semibold text-warning-700`}>
            {t("metering.estimate.fieldVisit")}
          </p>
        )}
      </div>
    );
  }

  // BR-MET-028: an estimate carries a consumption and NO register value, and
  // the row is labelled with its method and its consecutive number. All three
  // facts are on screen, because a clerk approving a bill needs to know this
  // figure was computed rather than read off a dial.
  const unit = result.unit;
  return (
    <div className={`${OUTCOME} ${OUTCOME_MADE}`} role="note">
      <h3 className={OUTCOME_TITLE}>{t("metering.estimate.madeTitle")}</h3>
      <dl className={FACTS}>
        <dt className={`text-xs uppercase tracking-label ${MUTED65}`}>
          {t("metering.estimate.consumption")}
        </dt>
        <dd className="m-0 text-base">
          {result.consumption === null ? (
            <UnitlessFigure reason={t("metering.estimate.noFigure")} />
          ) : unit === null || unit === "" ? (
            // Rule 3, enforced at the point of render. See UnitlessFigure.
            <UnitlessFigure reason={t("metering.estimate.noUnit")} />
          ) : (
            <EstimateFigure value={result.consumption} unit={unit} />
          )}
        </dd>

        <dt className={`text-xs uppercase tracking-label ${MUTED65}`}>
          {t("metering.estimate.method")}
        </dt>
        {/* ⚠ **B14 rule 31 — this printed `trailing_3_daily_avg` at a clerk.**
            *Nothing internal is ever visible to a utility user*, and an enum
            code is named in that rule by example. The product already holds the
            seven method NAMES the Settings screen offers
            (`settings.rules.choice.est_method.*`, eleven catalogues), so this
            renders the same word the person who CHOSE the method saw — one
            vocabulary, not a second one written for this panel. A code nobody
            has named still falls back to itself rather than to silence: a
            method nobody translated is still a method (BR-SHL-020). */}
        <dd className="m-0 text-base">
          {result.estimation_method == null || result.estimation_method === ""
            ? t("metering.estimate.methodUnknown")
            : t(`settings.rules.choice.est_method.${result.estimation_method}`, {
                defaultValue: result.estimation_method,
              })}
        </dd>

        <dt className={`text-xs uppercase tracking-label ${MUTED65}`}>
          {t("metering.estimate.consecutive")}
        </dt>
        <dd className="m-0 text-base">
          {result.consecutive_estimate_no === null
            ? t("metering.estimate.consecutiveUnknown")
            : result.consecutive_estimate_no}
        </dd>

        <dt className={`text-xs uppercase tracking-label ${MUTED65}`}>
          {t("metering.estimate.channel")}
        </dt>
        {/* B14 rule 31 again, and it is the Q7 register trap's read-back half:
            this printed `tou_mid`. The clerk must be able to check that the
            estimate landed on the register they meant, and `tou_mid` is not a
            word this product uses anywhere else — `BR-MET-170` (3)'s *Mid-peak*
            is. An estimate written against the wrong register is PERMANENT
            (`supersede_read` takes only a value and a reason; migration 0007's
            trigger freezes the channel), so the one place it can still be
            caught is here, on the way out. */}
        <dd className="m-0 text-base">
          {result.channel == null || result.channel === ""
            ? t("metering.estimate.channelUnknown")
            : t(`metering.reads.channel.${result.channel}`, { defaultValue: result.channel })}
        </dd>
      </dl>
      {/* BR-MET-028 again, said out loud: no register reading was stored, so
          nobody should look for one on the read detail. */}
      <p className={SENTENCE}>{t("metering.estimate.noRegister")}</p>
      {/* BR-MET-029: the estimate is corrected by register arithmetic at the
          next ACTUAL read. Stating it here is what stops an estimate being
          treated as final. */}
      <p className={SENTENCE}>{t("metering.estimate.trueUpNote")}</p>
    </div>
  );
}

export interface EstimateReadModalProps extends RegionalProps {
  client?: ApiClient;
  onClose: () => void;
}

/**
 * **THIS WAS A FULL PAGE AT `/reads/estimate` AND IT IS A DIALOG NOW
 * (DEF-897).** PO, on the live app at v2.61.1: *"this can be modal - instead of
 * page"*.
 *
 * ⚠ **NO B14 RULE WAS BROKEN, AND THAT IS THE FINDING.** B14's twenty-nine
 * rules cover tables, buttons, icons, danger tiers and descriptions and say
 * nothing about a form's CONTAINER — so this screen shipped as a route while
 * its three siblings on S25 (Add reading, Route sheet, Upload reads) were
 * modals, and every gate stayed green, because no gate in this repo reads
 * rendered output to notice that three of four actions open a dialog and the
 * fourth navigates away. The general rule is proposed to the PO as **OQ-540**
 * rather than minted here: *a form that does not leave the user's current
 * context — no multi-step wizard, no record of its own, no URL worth sharing —
 * opens in a dialog.* Three fields, one outcome, returns to the list it was
 * launched from: this is that form.
 *
 * ⚠ **THE OUTCOME STAYS INSIDE THE DIALOG, AND THAT IS DELIBERATE.** The two
 * things this screen must never do (see the header of this file) are unchanged
 * by the container: a refusal is an ANSWER and gets the same weight as a
 * success, and a consumption is never shown without its unit. Both live in
 * `EstimateOutcome`, which is rendered as a CHILD of the form — so the clerk
 * reads the answer over the inputs that produced it, and can estimate the next
 * meter without re-opening anything. `FormModal` does not close on a successful
 * submit (the consumer owns that), which is exactly the behaviour this needs.
 *
 * ⚠ **`collectFormErrors` IS GONE FROM THIS COMPONENT, NOT DUPLICATED.**
 * `FormModal` runs the SAME `estimateSchema` over the same values before it
 * posts and refuses with the errors under their fields (US-SHL-009 TC-1). Two
 * validators over one form is two places for the rule to drift.
 */
export function EstimateReadModal(props: EstimateReadModalProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  // IS-8 / BR-SHL-034: the tenant's own date format, through the ONE helper
  // every metering screen uses — the picker must not show a US order to a
  // tenant that writes DD/MM/YYYY.
  const { dateFormat } = useRegional(props);

  const [meterNo, setMeterNo] = useState("");
  const [channel, setChannel] = useState<string>("total");
  const [readAt, setReadAt] = useState("");

  const estimate = useMutation({
    mutationFn: () => estimateRead({ meter_no: meterNo, channel, read_at: readAt }, client),
  });

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await estimate.mutateAsync();
      // ⚠ `ok: true` DOES NOT MEAN "an estimate was made". `POST /reads/estimate`
      // answers 200 for BOTH outcomes and the refusal is data, not an error —
      // so what this reports to the frame is only *the request was answered*.
      // Which of the two answers came back is rendered by `EstimateOutcome`
      // below, and the dialog stays open either way.
      return { ok: true };
    } catch (error) {
      // A18 §4 — a TRANSPORT failure (the request never got an answer) is a
      // different thing from a refusal, and the two are rendered differently on
      // purpose: one is retried, the other is acted on. B12 §3: the server's
      // envelope is authoritative and renders itself.
      return { ok: false, error: error as never };
    }
  }

  return (
    <FormModal
      title={t("metering.estimate.title")}
      kicker={t("metering.estimate.kicker")}
      schema={estimateSchema}
      values={{ meter_no: meterNo, channel, read_at: readAt }}
      submitLabel={t("metering.estimate.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* ⚠ **THE 25-WORD LEDE IS GONE (`MR-14`, blueprint entry 18).** It read
          *"When a meter could not be read, this works out the consumption from
          that meter's own recent actual readings. It never guesses a rate and
          it never rounds."* — which is RATIONALE, and B14 rule 33 caps
          rationale at ZERO words on screen. It is not shortened, it is removed:
          why the product works this way belongs in the code and the register,
          and shortening rationale to six words keeps the breach and makes it
          terser. What it explained is above this line. */}
      <TextField
        id="meter_no"
        label={t("metering.estimate.meterNo")}
        value={meterNo}
        onChange={setMeterNo}
        required
      />
      {/* BR-MET-058: the channel is EXPLICIT and required. An estimate that
          silently defaulted to `total` on a TOU meter would borrow the wrong
          history, which is the one thing that rule forbids. */}
      <SelectField
        id="channel"
        label={t("metering.estimate.channelLabel")}
        value={channel}
        onChange={setChannel}
        required
        // `BR-MET-170` (3)'s own words — *Total register · On-peak · Mid-peak ·
        // Off-peak · Demand · Export · Generation* — the same seven strings the
        // reads list, the chase panel and the upload wizard print. A second set
        // of register words is a second thing to keep in step (`DEF-MET-5203`
        // was a second set of register CODES).
        options={ESTIMATE_CHANNELS.map((code) => ({
          value: code,
          label: t(`metering.reads.channel.${code}`, { defaultValue: code }),
        }))}
      />
      {/* ⚠ **THE PERIOD SENTENCE MOVES ONTO THE FIELD IT IS ABOUT, AND LOSES
          ITS SECOND HALF (`MR-31`, blueprint entry 18).** It was a `Note` under
          the form reading *"The length of the period is worked out from this
          meter's last actual reading. You do not enter it, so the calculation
          cannot be nudged."* — 25 words, of which the second sentence was
          addressed to a reader who is not the clerk. B14 rule 39 puts a helper
          under ITS OWN input (label → input → helper), so it is the date
          field's `help` rather than a paragraph after the form, and rule 33
          caps a fact at six words. The absent `days_in_period` input is one of
          the few places in this module where a fact about an ABSENCE is
          deliberately on screen: the server derives the denominator and a clerk
          typing a different number would silently move a signed calculation. */}
      <DatePickerField
        id="read_at"
        label={t("metering.estimate.readAt")}
        value={readAt}
        onChange={setReadAt}
        dateFormat={dateFormat}
        required
        help={t("metering.estimate.readAtHelp")}
      />

      {estimate.data !== undefined && <EstimateOutcome result={estimate.data} t={translate} />}
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-014@feddf11 (story+rules snapshot — EP-MET-05, co-story US-MET-015; OQ-003 CLOSED, math signed)
// generated: 2026-08-16 by story-coder (unreachable-screens lane — G23/DEF-112 surface debt) · AMENDED 2026-08-27 (DEF-897 — the PAGE becomes a DIALOG: `EstimateReadPage.tsx` → `EstimateReadModal.tsx`, `/reads/estimate` and its App.tsx route and screenIds row are gone, and `.rd-est-lede`/`.rd-est-form`/`.rd-est-actions` are deleted from reads.css with the G31 ceiling lowered 509 → 505 in the same commit. Every rule this screen enforces is untouched: rule 3 through `EstimateFigure`/`UnitlessFigure`, and a refusal rendered as an ANSWER through `EstimateOutcome`, which is now a child of the form so the clerk reads the answer over the inputs that produced it)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — not a 🔒 path: this screen authors no figure, no threshold and no key; it renders quantities the signed engine computed and never rounds, prices or re-derives one)
// gates: see the lane report
// exceptions: (0) [DEF-897 2026-08-27] the CONTAINER is a dialog and NO B14 rule names one — B14 covers tables, buttons, icons, danger tiers and descriptions and says nothing about when a form is a modal and when it is a page. The general rule is PROPOSED to the PO as B14 rule 30 via OQ-540 rather than minted by this lane, which is what B14's own closing section requires · (1) NO OVERRIDE CONTROL although US-MET-015 §5 names a `manual_override` method — `POST /reads/estimate` accepts no override amount and no other write route exists, so the field is not drawn over a route that would ignore it. REPORTED as the story's remaining half · (2) `days_in_period` is NOT offered as an input although the service accepts it: the server derives it from the prior actual (or the last standing estimate) and a clerk typing a different number would silently change a signed calculation's denominator. The note on screen says the period is derived · (3) the meter is identified by METER NUMBER typed free-hand rather than through a picker: BR-SHL-033 asks for a searchable select on any long list and no role-safe endpoint lists a tenant's meters for a Billing Clerk (`GET /assets` is registry-scoped) — REPORTED rather than rendering an empty dropdown · (4) `source` on the row this writes is `estimated`, which is OUTSIDE the module's declared READ_SOURCES enum (`ami | manual | import`) — a pre-existing backend divergence this screen surfaces and does not fix; carried into the lane report
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
