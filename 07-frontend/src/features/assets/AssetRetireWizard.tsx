// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-008 (retire — terminal) — SHAPE amended at build: the S54
//           modal becomes r10's 3-step full-page wizard
//           Screens: S54 / AST-08 (`/assets/:assetId/retire`)
// Change:   CR-028 AST-W4 T3 (B16 §5.2 as amended — no flow is a modal — +
//           §10-D4/BR-AST-047: retire KEEPS step 3, computes book value,
//           records the operator's treatment, POSTS NOTHING).
// Rules:    BR-AST-021 (reason + date; optional same-tenant replacement;
//           closes the current assignment) · BR-AST-030 (TERMINAL — the info
//           box says so before the button) · BR-AST-032 (System Admin only —
//           server-enforced) · BR-AST-022's posture (a requested final read
//           that cannot be captured refuses the WHOLE retire) · BR-AST-047 /
//           §10-D4 (straight-line book value + recorded treatment; no journal
//           line, no GL account, ever) · §10-D7 ("Work R5") · B16 Item 3d
//           (non-measuring devices skip the final read; step 3 unchanged) ·
//           BR-SHL-018/019 (wizard nav + ONE transactional commit)
// ───────────────────────────────────────────────────────
// AST-08 — Retire an asset: Reason & final read → Replacement → Book value.
//
// Honest absences, stated rather than smoothed over:
//   · **"Bill the final read on the next cycle"** — r10 draws the checkbox;
//     no lawful billing hook exists for an assets flow to schedule a bill,
//     so it is OMITTED (reported).
//   · **"48 kWh · roughly $12.24"** — rating math outside rating; folded
//     into D2's omissions by B16 §7. OMITTED, stated here.
//   · **Carry-net-config / transfer-route** — no column or service exists
//     for either; OMITTED (reported). ⚠ The REPLACEMENT OPENING READ that
//     stood in this list is BUILT since 2026-10-17 (`DEF-AST-10182`, PO
//     ruling *"WHERE A USER ENTERS A METER READING"* gap 2): step 2 takes the
//     new meter's reading and read date through the shared
//     `MeterReadingEntry` — the same reading/date/Fetch piece every reading
//     screen mounts (PO, same day: *"use same code components"*) — and the
//     server records it with metering's `capture_opening_read`. Step 1's
//     final read uses the same piece, so BOTH meters can Fetch. No estimate,
//     by ruling.
//   · **Salvage estimate + "move to the yard"** — no salvage column and no
//     stock_location (D5 ruled counts-and-costs only); OMITTED.
//   · **The FINANCE callout ("appears in Cost & Margin…")** — omitted with
//     the rest of D3's finance sentences; the recorded pair is the future
//     link's source, and that is the whole of it.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { BOOK_VALUE_TREATMENTS, getAssets, retireAsset } from "@/api/endpoints";
import type { AssetDetail, AssetRow, BookValueTreatment } from "@/api/endpoints";
import { DatePickerField, SearchSelectField, SelectField } from "@/components/FormModal";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DateCell, todayInZone } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { WarningBox } from "@/components/WarningBox";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardExit } from "@/components/WizardFrame";
import { useToast } from "@/components/Toast";
import { Note } from "@/components/TextBits";
import { MeterReadingEntry, readDateProblem } from "@/features/metering/MeterReadingEntry";
import type { MeterReadingEntryValue } from "@/features/metering/MeterReadingEntry";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AssetFlowShell, RaiseWorkOrderCheckbox, assetFlowKicker } from "./AssetFlowPages";
import { raiseWorkOrderPath } from "./RaiseWorkOrderPage";
import type { AssetFlowPageProps } from "./AssetFlowPages";
import { RETIRE_REASON_VALUES } from "./AssetLifecycleModals";
import {
  ASSETS_ROUTE,
  assetDetailPath,
  isMeasuringCategory,
  useTranslator,
} from "./assetsShared";
import { ageParts } from "./AssetDetailPage";

// ── Pure pieces ────────────────────────────────────────────────────────────

export interface RetireValues {
  reason: string;
  retire_date: string;
  final_read_value: string;
  final_read_date: string;
  /** The final reading in the box is the head-end's (Fetch), date included. */
  final_read_fetched: boolean;
  replaced_by: string;
  /** DEF-AST-10182 — the replacement's opening reading and its date. */
  opening_read_value: string;
  opening_read_date: string;
  opening_read_fetched: boolean;
  book_value_treatment: BookValueTreatment | "";
}

export function initialRetireValues(): RetireValues {
  return {
    reason: "",
    retire_date: "",
    final_read_value: "",
    final_read_date: "",
    final_read_fetched: false,
    replaced_by: "",
    opening_read_value: "",
    opening_read_date: "",
    opening_read_fetched: false,
    book_value_treatment: "",
  };
}

/** A book value exists exactly when the served valuation could compute one —
 *  the same fact the server's treatment requirement keys off. */
export function hasBookValue(asset: Pick<AssetDetail, "valuation">): boolean {
  return (asset.valuation.present_value ?? null) !== null;
}

/**
 * The date the replacement's opening reading is recorded on: the clerk's, or
 * the retire date (the exchange day) when they left it — the server's own
 * default (`_capture_replacement_opening_read`).
 */
export function openingReadDate(values: RetireValues, today: string): string {
  if (values.opening_read_date !== "") return values.opening_read_date;
  return values.retire_date !== "" ? values.retire_date : today;
}

export function retireStepValid(
  step: number,
  values: RetireValues,
  bookValue: boolean,
  /** Today in the tenant's zone — the opening read may not be after it. */
  today?: string,
): boolean {
  if (step === 1) {
    return values.reason !== ""; // BR-AST-021: reason is REQUIRED
  }
  if (step === 2 && values.replaced_by !== "" && values.opening_read_value.trim() !== "") {
    // DEF-AST-10182: a typed opening reading needs a lawful date — never in
    // the future (the server refuses the same, `replacement_opening_read_future`).
    return readDateProblem(openingReadDate(values, today ?? ""), { maxDate: today || undefined }) === null;
  }
  if (step === 3 && bookValue) {
    // D4: a computable book value makes the treatment radio non-skippable —
    // mirroring the server's own refusal.
    return values.book_value_treatment !== "";
  }
  return true;
}

/** The replacement picker: IN-INVENTORY assets of the same category
 *  (a compatible kind — an electric meter is not replaced by a cart). */
export function replacementOptions(
  rows: readonly AssetRow[] | undefined,
  retiring: Pick<AssetRow, "id">,
): { value: string; label: string }[] {
  return (rows ?? [])
    .filter((row) => row.behavior_class === "available" && row.id !== retiring.id)
    .map((row) => ({
      value: row.asset_no,
      label: [row.asset_no, row.type_name].filter((part) => part).join(" · "),
    }));
}

export interface RetirePayload {
  reason: string;
  retire_date?: string;
  replaced_by?: string;
  final_read_value?: string;
  final_read_date?: string;
  replacement_opening_read?: string;
  replacement_opening_read_date?: string;
  book_value_treatment?: string;
}

export function retirePayload(values: RetireValues): RetirePayload {
  const payload: RetirePayload = { reason: values.reason };
  if (values.retire_date !== "") {
    payload.retire_date = values.retire_date;
  }
  if (values.final_read_value.trim() !== "") {
    payload.final_read_value = values.final_read_value.trim();
    if (values.final_read_date !== "") {
      payload.final_read_date = values.final_read_date;
    }
  }
  if (values.replaced_by !== "") {
    payload.replaced_by = values.replaced_by;
    if (values.opening_read_value.trim() !== "") {
      payload.replacement_opening_read = values.opening_read_value.trim();
      if (values.opening_read_date !== "") {
        payload.replacement_opening_read_date = values.opening_read_date;
      }
    }
  }
  if (values.book_value_treatment !== "") {
    payload.book_value_treatment = values.book_value_treatment;
  }
  return payload;
}

// ── The screen ─────────────────────────────────────────────────────────────

export function AssetRetireWizard(props: AssetFlowPageProps) {
  const client = props.client ?? api;
  const t = useTranslator();
  return (
    <AssetFlowShell
      client={client}
      regional={props}
      // Figures 36 / 38 / 40: kicker `METER · AMI · RETIRE`, title `W-5001`,
      // the status chip, the attention strip and the context line — screen
      // 08's five-slot header, which all three retire steps inherit from the
      // one shell.
      kicker={(asset) => assetFlowKicker(asset, t("assets.retire.kicker"))}
    >
      {(asset) => <RetireWizardBody asset={asset} client={client} pageProps={props} />}
    </AssetFlowShell>
  );
}

function RetireWizardBody(props: {
  asset: AssetDetail;
  client: ApiClient;
  pageProps: AssetFlowPageProps;
}) {
  const { asset, client } = props;
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const { dateFormat, timeZone } = useRegional(props.pageProps);
  /**
   * ⚠ **`props.today` IS PASSED BY TESTS AND BY NOTHING ELSE** — `App.tsx`
   * mounts this screen with no props at all, so before 2026-09-12 `today` was
   * `""`, `prefill` was `undefined`, and the field rendered EMPTY in the
   * shipped product against `BR-PAY-033`'s *"the UI ALWAYS proposes a
   * pre-filled default date"* (`DEF-MET-4991`, measured in Chromium at 1440 and
   * 1280). It also silently voided this lane's `max` bound, which is the sharp
   * end of it: a green unit test and a browser that disagreed, because the test
   * supplied the prop the router does not. The tenant's own zone, never UTC —
   * a `max` of *not in the future* must not refuse a clerk their own today.
   */
  const today = props.pageProps.today ?? todayInZone(timeZone);
  const measuring = isMeasuringCategory(asset.tab);
  const bookValue = hasBookValue(asset);

  const [values, setValues] = useState<RetireValues>(initialRetireValues);
  // A9 / BR-SHL-018: the step is URL state — a half-filled retire is linkable
  // and browser Back leaves the step, exactly the AddPremisesWizard pattern.
  const [searchParams, setSearchParams] = useSearchParams();
  const rawStep = Number(searchParams.get("step") ?? "1");
  const step = Number.isInteger(rawStep) ? Math.min(Math.max(1, rawStep), 3) : 1;
  function setStep(next: { step: number }): void {
    const params = new URLSearchParams(searchParams);
    params.set("step", String(next.step));
    setSearchParams(params, { replace: true });
  }

  /* The work-order pre-tick. FALSE by default: raising a meter-exchange job is
     a choice a clerk makes, and a default-on checkbox would put a van on the
     road for every meter a utility ever retires. */
  const [raiseWork, setRaiseWork] = useState(false);

  // Replacements come from the SAME tab (a compatible kind), Inventory only.
  const inventoryQuery = useQuery({
    queryKey: ["assets", "retire-replacement-picker", asset.tab],
    queryFn: () =>
      getAssets({ per: 500, filters: { tab: String(asset.tab), status: "inventory" } }, client),
    staleTime: 60 * 1000,
    retry: false,
  });

  /** The retire (exchange) date — what a reading's date opens on. */
  const retireOn = values.retire_date !== "" ? values.retire_date : today;
  const openingOn = openingReadDate(values, today);
  const replacement = (inventoryQuery.data?.results ?? []).find(
    (row) => row.asset_no === values.replaced_by,
  );

  const retire = useMutation({
    mutationFn: () => retireAsset(asset.id, retirePayload(values), client),
  });

  async function commit(): Promise<WizardCommitOutcome> {
    try {
      await retire.mutateAsync();
      fireToast(t("assets.toast.retired", { asset: asset.asset_no }));
      navigate(tenantPath(raiseWork ? raiseWorkOrderPath(asset.id) : ASSETS_ROUTE));
      return { ok: true };
    } catch (error) {
      // BR-SHL-020 — incl. the BR-AST-022 refusal when a final read was
      // entered and cannot be captured: the asset did NOT retire, and the
      // failed card says why with everything entered still on screen.
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  const steps = [
    {
      id: "reason",
      label: t("assets.retire.step.reason"),
      validate: () => retireStepValid(1, values, bookValue),
      content: (
        <div className="flex flex-col gap-4">
          {/* **RETIRING, NOT DELETING** — BR-AST-030's terminality, before the
              button. B14 rule 36: this was a HAND-ROLLED box beside a kit that
              already had one, which is the exact shape the rule exists to
              stop; it is now `ConsequenceBox`, the same piece screen 27 uses.
              Figures 35 and 36 both draw TWO paragraphs and the code had
              three — the notice, the terminal sentence, and the correction
              path. Rule 33 caps a CONSEQUENCE before an irreversible act at
              two sentences, so the box carries the two the drawing draws.

              ⚠ **THE THIRD IS NOT DELETED, AND DELETING IT WAS THE TEMPTING
              MOVE.** *"If this was a mistake, create the asset anew"* is the
              only next step a person has after a retire they regret, and an
              absence is invisible to every check this repo owns. It renders
              below the box instead — reported as the one place this screen
              does not match figure 36 exactly. */}
          <ConsequenceBox
            tone="check"
            title={t("assets.retire.noticeTitle")}
            body={
              <>
                {t("assets.retire.notice")}{" "}
                <strong>{t("assets.retire.terminal")}</strong>
              </>
            }
            data-consequence="assets-retire-notice"
          />
          <Note>{t("assets.retire.correctionPath")}</Note>
          <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
            <SelectField
              id="reason"
              label={t("assets.retire.reason")}
              required
              value={values.reason}
              placeholder={t("assets.retire.reasonPlaceholder")}
              options={RETIRE_REASON_VALUES.map((reason) => ({
                value: reason,
                label: t(`assets.retire.reason.${reason}`),
              }))}
              onChange={(value) => setValues({ ...values, reason: value })}
            />
            <DatePickerField
              id="retire_date"
              label={t("assets.retire.date")}
              value={values.retire_date}
              prefill={today === "" ? undefined : today}
              dateFormat={dateFormat}
              // B14 rule 7 / `DEF-MET-4974` — measured `min: null, max: null`
              // at 1280 and 1440 while the SERVER refused a retire date before
              // the install date (`services.py:1516`,
              // `assets.retire_before_install`, `VAL_RANGE`). The bound MIRRORS
              // that refusal and invents nothing; an asset with no install date
              // recorded has no floor, so it stays exactly as unbounded as it
              // was. NO `max`: retiring forward-dated is lawful and the server
              // accepts it.
              //
              // ⚠ **THE SENTENCE TRAVELS WITH THE BOUND, AND THAT IS THE WHOLE
              // LESSON OF THIS LANE.** A greyed-out calendar with no words is
              // the same defect as `DEF-MET-4973`'s greyed-out submit: a
              // refusal a person can see and cannot account for. The existing
              // help says what the date DOES; the second sentence says what it
              // may not be, and it renders only where the floor exists so it
              // can never state a bound that is not enforced.
              min={asset.install_date ?? undefined}
              onChange={(value) => setValues({ ...values, retire_date: value })}
              help={
                asset.install_date === null
                  ? t("assets.retire.dateHelp")
                  : `${t("assets.retire.dateHelp")} ${t("assets.retire.dateFloorHelp")}`
              }
            />
          </div>
          {/* B16 Item 3d: NO final read on a non-measuring device — a device
              stores no read, so the fields do not render at all. */}
          {measuring && (
            // ⚠ **THE SHARED READING PIECE — DEF-AST-10182 (PO 2026-10-17,
            // *"use same code components"* … *"for meter reading, date and
            // fetch"*).** The final reading, its date and Fetch are
            // `MeterReadingEntry`, the one component every reading screen
            // mounts. Fetch asks the head-end AS OF the retire date: the
            // reading on or last before it, never one taken after the meter
            // came out. The ids stay `final_read_value`/`final_read_date` — the
            // server's own field names.
            //
            // ⚠ **THE DATE IS STILL UNBOUNDED, DELIBERATELY** (`DEF-MET-4974`):
            // left as the retire date it may lawfully be forward-dated, so no
            // `maxDate` here. A date the clerk does not touch is not SENT, so
            // the server's own default (the retire date) still decides.
            <MeterReadingEntry
              meterNo={asset.asset_no}
              assetId={asset.id}
              unit={asset.unit}
              value={values.final_read_value}
              readDate={values.final_read_date !== "" ? values.final_read_date : retireOn}
              fetched={values.final_read_fetched}
              defaultReadDate={retireOn}
              asOf={retireOn}
              showFetch
              readingLabel={t("assets.retire.finalRead", { unit: asset.unit ?? t("assets.unitUnknown") })}
              dateLabel={t("assets.reassign.finalReadDate")}
              valueId="final_read_value"
              dateId="final_read_date"
              onChange={(next: MeterReadingEntryValue) =>
                setValues({
                  ...values,
                  final_read_value: next.value,
                  final_read_date: next.fetched || next.readDate !== retireOn ? next.readDate : "",
                  final_read_fetched: next.fetched,
                })
              }
              client={client}
              t={translate}
              timeZone={timeZone}
              dateFormat={dateFormat}
            />
          )}
          {/* OMITTED, stated: r10's "Bill the final read on the next cycle"
              checkbox (no lawful billing hook exists) and its "48 kWh ·
              roughly $12.24" line (rating math outside rating — B16 §7). */}
        </div>
      ),
    },
    {
      id: "replacement",
      label: t("assets.retire.step.replacement"),
      validate: () => retireStepValid(2, values, bookValue, today),
      content: (
        <div className="flex flex-col gap-5">
          <p className="m-0 text-base">{t("assets.retire.replacementLede")}</p>
          <SearchSelectField
            id="replaced_by"
            label={t("assets.retire.replacedBy")}
            value={values.replaced_by}
            options={replacementOptions(inventoryQuery.data?.results, asset)}
            placeholder={t("assets.retire.noReplacement")}
            // A different replacement is a different dial: its opening reading
            // never carries over from the meter picked before.
            onChange={(value) =>
              setValues({
                ...values,
                replaced_by: value,
                opening_read_value: "",
                opening_read_date: "",
                opening_read_fetched: false,
              })
            }
            help={t("assets.retire.replacedByHelp")}
          />
          {/* DEF-AST-10182 — the NEW meter's opening reading, its date and
              Fetch, through the same shared piece as step 1's final reading.
              Shown once a measuring replacement is named. The date opens on
              the retire date (the exchange day) and may not be after today;
              Fetch asks the head-end as of that day. No estimate (PO ruling).
              OMITTED, still stated: "carry the net-metering configuration" and
              "transfer the read route and sequence" (no column or service). */}
          {replacement !== undefined && isMeasuringCategory(replacement.tab) && (
            <MeterReadingEntry
              meterNo={replacement.asset_no}
              assetId={replacement.id}
              unit={replacement.unit}
              value={values.opening_read_value}
              readDate={openingOn}
              fetched={values.opening_read_fetched}
              defaultReadDate={retireOn}
              asOf={openingOn}
              showFetch
              maxDate={today === "" ? undefined : today}
              showDateError={values.opening_read_value.trim() !== ""}
              // Add asset's own words for the same reading (`AST-B-14`); the
              // unit is the box's affix, so the label does not repeat it.
              readingLabel={t("assets.add.openingRead")}
              valueId="replacement_opening_read"
              dateId="replacement_opening_read_date"
              onChange={(next: MeterReadingEntryValue) =>
                setValues({
                  ...values,
                  opening_read_value: next.value,
                  opening_read_date: next.fetched || next.readDate !== retireOn ? next.readDate : "",
                  opening_read_fetched: next.fetched,
                })
              }
              client={client}
              t={translate}
              timeZone={timeZone}
              dateFormat={dateFormat}
            />
          )}
          {/* r10's "Raise a meter-exchange work order for the swap" — LIVE
              since wave M. The retirement commits first; then the door opens
              on the asset that was just taken out. */}
          <RaiseWorkOrderCheckbox
            label={t("assets.retire.workOrder")}
            checked={raiseWork}
            onChange={setRaiseWork}
          />
          {measuring && asset.assigned && values.replaced_by === "" && (
            // r10's WARNING callout: leaving the seat unmetered.
            //
            // ⚠ **NEITHER FIGURE 37 NOR FIGURE 38 DRAWS THIS BAND**, and it is
            // KEPT rather than removed: it fires only on the state the step's
            // own lede warns about (a measuring, assigned asset with no
            // replacement chosen), so it is a live conditional the drawing
            // never caught rather than an element the drawing declined.
            // What changes is the CONTAINER — B14 rule 36: the kit's
            // `WarningBox`, not a hand-rolled div with its own border and
            // tint. `soon` is the amber tone: there is still time to pick a
            // replacement.
            <WarningBox
              tone="soon"
              sentence={t("assets.retire.unmeteredWarning", {
                unit: asset.assigned_to ?? "",
              })}
              data-warning="assets-retire-unmetered"
            />
          )}
        </div>
      ),
    },
    {
      id: "book_value",
      label: t("assets.retire.step.bookValue"),
      validate: () => retireStepValid(3, values, bookValue),
      content: (
        <BookValueStep
          asset={asset}
          values={values}
          onChange={setValues}
          bookValue={bookValue}
          regional={props.pageProps}
          t={translate}
        />
      ),
    },
  ];

  // ── `AST-B-28` — THE ESCAPE HATCH THIS WIZARD NEVER HAD ─────────────────
  //
  // Step 1 measured this footer as `["Continue"]` — one button. Figure 35 draws
  // a `Cancel` beside it and the document's own correction is better than the
  // finding: `WizardFrame` offers `Save & exit` and `Park` through an optional
  // `exit` prop, six wizards elsewhere pass it, and **this one passed none**.
  // So a System Admin three steps into retiring the wrong meter had `← Back`
  // and nothing that said *leave this*. That is hard-won law 2's family: not
  // dead UI, but a live affordance the screen declined to ask for — and nothing
  // can catch it, because an unset optional prop is what optional means.
  //
  // ✅ **`Save & exit` LEAVES QUIETLY AND WRITES NOTHING** (B19 §12.2), which is
  // exactly true here: nothing in this wizard writes until step 3's commit, so
  // there is nothing to undo. It returns to the ASSET rather than the registry,
  // because that is where the clerk came from — the header's own `← Asset`.
  //
  // ⛔ **`Park` IS REFUSED WITH ITS REASON** — the same two blockers the add
  // wizard's `exit` names in full: `wizard_parks.flow` is a database CHECK
  // constraint that does not admit `retire_asset`, and there is no Drafts home
  // on the Assets registry for a parked retire to appear on. A draft nothing
  // lists is a write nobody can read.
  //
  // ⚠ **AND BR-AST-030 WOULD GOVERN THE RESUME WHEN IT IS BUILT:** terminal is
  // terminal, so a draft of a retire that has since completed elsewhere must
  // refuse rather than offer to retire a retired asset. Written here because it
  // is the thing the next lane will need and would otherwise rediscover.
  const exit: WizardExit = {
    onSaveAndExit: () => navigate(tenantPath(assetDetailPath(asset.id))),
    parkBlockedReason: t("assets.wizard.parkBlocked"),
    parkOpen: false,
    onParkOpenChange: () => undefined,
    onPark: () =>
      Promise.resolve<WizardCommitOutcome>({
        ok: false,
        reason: t("assets.wizard.parkBlocked"),
      }),
    dateFormat,
    parkedAt: null,
  };

  return (
    <WizardFrame
      steps={steps}
      nav={{ step, reached: step }}
      onNavChange={setStep}
      exit={exit}
      commitLabel={t("assets.retire.commit", { asset: asset.asset_no })}
      // B14 rule 6 (DEF-718): RETIRE is rule 6's own second named example, and
      // this commit renders "Retire {asset} ✓". It rendered in the PRIMARY tier
      // until 2026-08-26 — see the E4 exception below, which reported exactly
      // this and pointed at the sweep that has now happened.
      commitVariant="danger"
      commitFailedTitle={t("assets.retire.commitFailed")}
      onCommit={commit}
      onCommitted={() => undefined /* commit() already navigated */}
    />
  );
}

// ── Step 3 — Book value (D4 / BR-AST-047) ──────────────────────────────────

function BookValueStep(props: {
  asset: AssetDetail;
  values: RetireValues;
  onChange: (values: RetireValues) => void;
  bookValue: boolean;
  regional: RegionalProps;
  t: Translator;
}) {
  const { timeZone, dateFormat } = useRegional(props.regional);
  const { asset, values, t } = props;
  const valuation = asset.valuation;
  if (!props.bookValue) {
    // The honest state: no purchase cost (or no life) recorded → no book
    // value to compute, no treatment demanded, nothing invented (D4).
    return (
      <div className="flex flex-col gap-4" data-book-value-absent="">
        <p className="m-0 text-base">{t("assets.retire.noBookValue")}</p>
        <Note>{t("assets.retire.noBookValueHelp")}</Note>
      </div>
    );
  }
  const currency = valuation.currency ?? "USD";
  const life = valuation.life_months ?? null;
  const age = valuation.age_months ?? null;
  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 text-base">{t("assets.retire.bookValueLede")}</p>
      {/* r10's Asset value box — every figure the SERVER's straight-line
          computation, none re-derived here. */}
      <div className="border border-divider bg-surface p-4 text-base leading-8" data-book-value="">
        <div className="mb-2 font-heading text-xs font-extrabold uppercase tracking-label">
          {t("assets.retire.assetValue")}
        </div>
        <div className="flex justify-between">
          <span>{t("assets.valuation.purchaseCost")}</span>
          <b>
            {valuation.purchase_cost !== null ? (
              <MoneyCell amount={valuation.purchase_cost} currency={currency} />
            ) : (
              "—"
            )}
          </b>
        </div>
        <div className="flex justify-between">
          <span>{t("assets.retire.ageAtRetirement")}</span>
          <b>
            {age !== null && life !== null
              ? t("assets.retire.ageOfLife", {
                  ...ageParts(age),
                  life: Math.floor(life / 12),
                })
              : "—"}
          </b>
        </div>
        <div className="flex justify-between">
          <span>{t("assets.retire.accumulatedDepreciation")}</span>
          <b>
            {valuation.accumulated_depreciation != null ? (
              <MoneyCell amount={valuation.accumulated_depreciation} currency={currency} />
            ) : (
              "—"
            )}
          </b>
        </div>
        <div className="flex justify-between">
          <span>{t("assets.retire.remainingBookValue")}</span>
          <b>
            {valuation.present_value != null ? (
              <MoneyCell amount={valuation.present_value} currency={currency} />
            ) : (
              "—"
            )}
          </b>
        </div>
        {valuation.warranty_end !== null && (
          <div className="flex justify-between">
            <span>{t("assets.valuation.coverEnds")}</span>
            <b>
              {/* BR-SHL-034: one formatter — a raw ISO date is measured drift. */}
              <DateCell
                value={valuation.warranty_end}
                timeZone={timeZone}
                dateFormat={dateFormat}
                monthYear
              />
              {valuation.warranty_covered === true &&
                ` · ${t("assets.retire.claimPossible")}`}
            </b>
          </div>
        )}
      </div>
      {/* D4: the treatment radio — RECORDED with the computed amount by
          retire, posted NOWHERE. r10's first option names GL 5400; the GL
          half is OMITTED (hard rule 5), the choice survives. */}
      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0" data-treatment="">
        <legend className="mb-1 p-0 font-heading font-semibold">
          {t("assets.retire.treatment")}
        </legend>
        {BOOK_VALUE_TREATMENTS.map((treatment) => (
          <label key={treatment} className="inline-flex cursor-pointer items-center gap-2 text-md">
            <input
              type="radio"
              name="book_value_treatment"
              value={treatment}
              checked={values.book_value_treatment === treatment}
              onChange={() => props.onChange({ ...values, book_value_treatment: treatment })}
            />
            <span>{t(`assets.retire.treatment.${treatment}`)}</span>
          </label>
        ))}
      </fieldset>
      {/* Both figures draw this as an accent-ruled box titled `RECORDED, NOT
          POSTED`; it was an 11px grey caption. B14 rule 11 + 36 — the kit's
          box, and the same title the log-repair screen now carries, so the
          product says one thing about "recorded here, not in the books".
          ⚠ The value box above and the treatment control below are NOT touched:
          the drawing's two-option `Write off | Carry forward` enum is not the
          ratified, server-enforced set, and the drawn three-row value box would
          lose `Age at retirement`. Both are rule-41 escalations with the PO. */}
      <ConsequenceBox
        tone="check"
        title={t("assets.maintenance.recordedNotPosted")}
        body={t("assets.retire.recordedNotPosted")}
        data-consequence="assets-retire-recorded"
      />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-008@e1a4db0 (EP-AST-03 retire story — SHAPE amended per the not-modal ruling) · CR-028@B16 (04-docs/02-decisions/16-cr028-assets-design.md §5.2 + §10-D4 + BR-AST-047 + Item 3d)
// generated: 2026-08-22 by the CR-028 AST-W4 lane (T3: the AST-08 3-step full-page wizard; the S54 modal retires from AssetLifecycleModals.tsx the same commit)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (AssetFlowPages.test.tsx — step-3 rendering both states, treatment gating, payload shape) · trace_lint✔ · [CONFIRMTIER 2026-08-26, DEF-718] tsc✔ eslint 0✔ vitest 2652 passed✔ — the retire commit's DANGER tier is asserted on RENDERED output in AssetLifecycle.test.tsx and was proved RED by dropping `commitVariant`
// exceptions: E3 "Bill the final read on the next cycle" OMITTED — no lawful billing hook exists for an assets flow to schedule a bill · E3 the "48 kWh · roughly $12.24" estimated-usage line OMITTED — rating math outside rating (B16 §7 folded it into D2's omissions) · E3 carry-net-config / transfer-route OMITTED — no column or service exists for either (the replacement OPENING READ is BUILT 2026-10-17, DEF-AST-10182) · E3 salvage estimate + move-to-yard OMITTED — no salvage column, no stock_location (D5) · E4 ✅ CLOSED 2026-08-26 by lane CONFIRMTIER (DEF-718) — the commit button rendered in the WizardFrame's PRIMARY tier where r10 draws btn-danger, because the frame owned the ✓ confirm and offered no danger tier; DEF-712 gave the frame an optional `commitVariant` and this wizard now declares `danger`, asserted on RENDERED output in AssetLifecycle.test.tsx · E4 r10's step-1 reason list (Upgraded to AMI · Premises demolished · Lost or stolen) differs from the RATIFIED BR-AST-021 catalog — the catalog wins, per the standing law that ratified rules beat prototype copy
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
