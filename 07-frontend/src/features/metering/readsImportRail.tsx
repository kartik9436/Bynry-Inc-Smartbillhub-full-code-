// ── Trace ──────────────────────────────────────────────
// Change:   CR-042 — TWO write modes, on step 1, through ONE shared control
//           (PO 2026-08-27). SUPERSEDES CR-038 W7 task 3's three modes.
//           CR-038 W7 — ONE IMPORT RAIL. Tasks 4 (BR-MET-130's post path) and
//           5 (the co-sign) are unchanged.
// Story:    US-MET-007/008/009/010 (S28) · Screens: S28 on WFL-01.reads.1–.4
// Rules:    BR-MET-210 (two modes, that order, those words, step 1, ONE
//           control) · CR-038 R2 minus its withdrawn third mode (insert ·
//           insert & update; the modes NEVER edit a committed row) ·
//           CR-036 (g) (PO 2026-08-26:
//           "you need at step 1 or 2 itself - this is important decision how
//           you will process the data and upload it") · BR-MET-127 (a billed
//           read is REFUSED BY NAME and the rest of the batch posts) ·
//           BR-MET-130 (PO: "allow it" — an incomplete cycle posts once the
//           shortfall is SHOWN) · BR-MET-129 (a warned reading POSTS) ·
//           OQ-042 closure (co-sign: SysAdmin/Executive) · BR-SHL-020 (plain-
//           language absence) · BR-SHL-025 (a control you may not use renders
//           disabled WITH its reason) · B14 rule 21 (new UI is Tailwind
//           utilities and adds NO class to a stylesheet)
// Defect:   DEF-770 (the write mode had two controls and nothing said which
//           one won) — the reason this file offers it in exactly ONE place.
// ───────────────────────────────────────────────────────
// CR-038 W7 — the pieces the reads rail needed that no shared component had.
//
// **WHY A NEW FILE AND NOT MORE OF `UploadReadsWizard.tsx`.** That screen is
// not on `src/styles/route-b-migrated.txt`, so every class token it names must
// be declared by a stylesheet or G31 fails the merge at its ratchet of 0. B14
// rule 21 says the opposite about NEW UI — Tailwind utilities, and NO class
// added to a stylesheet. Both rules are satisfiable at once only by putting
// the new UI in a file written in utilities from its first line and listing it
// in the ledger, which is precisely what `demandShared.tsx` did for CR-038 W4
// and what the ledger's own note recommends: *"New UI in utilities, in one
// place, imported everywhere — rather than five screens each growing a badge."*
// So this file is BORN Route B; `routeBUtilities.test.ts` asks the compiler
// about each utility, and the wizard that imports these components adds no
// class token of its own.
//
// ⚠ **THE WRITE MODE IS OFFERED ONCE — DEF-770 IS WHY.** The premises importer
// shipped the control at stage 1 AND kept it at stage 4, and the PO found it:
// *"Write mode from this screen may not required . it is already added on step
// 1"*. The defect's own diagnosis is the useful part — the duplicate solved a
// problem the navigation had already solved, because `back()` always walked to
// stage 1. `WriteModeStated` below is the stage-4 half: it STATES the premise
// and offers a `Change it` that steps back to the stage that owns it.
//
// ⚠ **AND SINCE CR-042 IT IS OFFERED ONCE IN THE WHOLE PRODUCT, NOT ONCE PER
// RAIL.** The control moved to `components/workflow/WriteModeChoice.tsx`; what
// remains here is the two mounts and the reads consequence sentences. The
// reason is measured, not aesthetic: this rail and the ETL runner had separate
// catalogue keys for the same two options, and in eight of eleven languages
// they had drifted into different words. `replace` is withdrawn (OQ-418 closed
// by removal) — for reads it did nothing `insert & update` did not do, so
// nothing is lost here; that is NOT true on the other rail (OQ-580).
import type { ReactNode } from "react";

import { Button } from "@/components/Button";
import { PlainTable } from "@/components/Surfaces";
import { Kicker } from "@/components/TextBits";
import {
  DEFAULT_WRITE_MODE,
  WRITE_MODES,
  WriteModeField as SharedWriteModeField,
  WriteModeStated as SharedWriteModeStated,
  writeModeOptions,
} from "@/components/workflow";
import type { WriteModeId, WriteModeOption } from "@/components/workflow";
import type { ReadCycleCoverage } from "@/api/endpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * **THE TWO MODES, FOR READS — CR-042 / BR-MET-210.**
 *
 * ⚠ **THE CONTROL ITSELF NOW LIVES IN `components/workflow/WriteModeChoice`,
 * AND THAT IS THE POINT OF CR-042.** This rail drew its own radio cards with
 * its own caption and its own catalogue keys while the shared ETL runner drew a
 * segmented control with different keys — the same decision, two shapes, and in
 * eight of eleven languages two different sets of WORDS. PO 2026-08-27: *"in
 * all imports - we need 2 option on step 1 insert, insert & update; replace
 * option is not required"*. One control is the only fix that stays fixed.
 *
 * What stays here is the only thing that legitimately differs between rails:
 * **the consequence sentence**, because "already on file" means a reading at a
 * meter/date/register with BR-MET-127's billed refusal attached, and on the ETL
 * runner it means a record under the same reference. Flattening those into one
 * sentence would make the control lie on one of the two rails.
 *
 * ⛔ **`replace` IS WITHDRAWN (CR-042, OQ-418 closed by removal).** For reads it
 * did nothing `insert & update` did not do — *"supersedes a committed
 * duplicate"* and *"supersedes everything the file carries"* are the same set of
 * rows — so it is gone with nothing lost. **That is NOT the case on the other
 * rail**, where BR-MET-099 gave it real behaviour; see `import_runs.py` and
 * OQ-580 before assuming the two removals are the same removal.
 */
export const READ_WRITE_MODES = WRITE_MODES;
export type ReadWriteMode = WriteModeId;

/** hard-won law 3 — the safe option is the one you get without typing. */
export const DEFAULT_READ_WRITE_MODE: ReadWriteMode = DEFAULT_WRITE_MODE;

/**
 * The two options with the READS consequence sentences attached.
 *
 * The LABELS come from the shared key set (`workflow.writeMode.*`) so this
 * screen and the ETL runner can never again print two different words for one
 * mode; only the sentence under the choice is this rail's own.
 */
export function readWriteModeChoices(t: Translator): WriteModeOption[] {
  return writeModeOptions(t, {
    insert: t("metering.upload.writeMode.insertConsequence"),

    upsert: t("metering.upload.writeMode.upsertConsequence"),
  });
}

/**
 * ⚠ **STEP 1 — THE PREMISE, ASKED BEFORE ANYTHING IS READ (CR-036 (g)).**
 *
 * A thin mount of the shared control, kept as a named export so
 * `UploadReadsWizard` — which is NOT on Route B and may add no class token of
 * its own (B14 rule 21) — imports a component rather than a layout.
 */
export function WriteModeField(props: {
  value: ReadWriteMode;
  onChange: (next: ReadWriteMode) => void;
  disabled?: boolean;
  t: Translator;
}) {
  return (
    <SharedWriteModeField
      value={props.value}
      onChange={props.onChange}
      options={readWriteModeChoices(props.t)}
      disabled={props.disabled}
      idPrefix="reads"
      t={props.t}
    />
  );
}

/**
 * ⛔ **STEP 4 — THE MODE IS STATED, NOT OFFERED AGAIN (DEF-770).**
 *
 * PO, on the deployed v2.51.0: *"Write mode from this screen may not required .
 * it is already added on step 1"*. The shared control carries the reasoning and
 * the withdrawn-mode fallback; this is the reads mount of it.
 */
export function WriteModeStated(props: {
  value: ReadWriteMode;
  onChangeRequested: () => void;
  t: Translator;
}) {
  return (
    <SharedWriteModeStated
      value={props.value}
      options={readWriteModeChoices(props.t)}
      onChangeRequested={props.onChangeRequested}
      t={props.t}
    />
  );
}

/**
 * **BR-MET-130 — THE SHORTFALL, ON THE SCREEN WHERE THE POST HAPPENS.**
 *
 * PO 2026-08-26, verbatim: *"allow it"*, with the rule's own condition —
 * *"what is mandatory is the SHOWING"*. The worked case the PO was shown:
 * CY-001 holds 1,240 meters, the file carries 1,180, **60 unread**.
 *
 * ⚠ It NEVER blocks and it never nags. The rule is explicit that blocking the
 * other 1,180 customers' billing for the 60 *"helps nobody"*. What it does is
 * make the number impossible to miss on the last screen before the commit, and
 * say what happens to the missing meters (the chase list) so "post anyway" is
 * an informed choice rather than a shrug.
 *
 * ⚠ An absent coverage renders its REASON, never a zero (BR-SHL-020): a `0`
 * beside "not read" would read as *nothing is missing*, which is a different
 * claim from *this batch is not tagged with a cycle, so there is nothing to
 * compare it against*.
 */
export function CycleShortfall(props: {
  /** ⛔ DEF-2440 — the SERVER's own field names. The three this used to declare
   *  (`expected` / `received` / `missing`) are sent by nothing, so every figure
   *  in the sentence below was `undefined` and printed as a blank. */
  coverage: ReadCycleCoverage | null;
  absentReason: string | null;
  t: Translator;
}) {
  const { t, coverage } = props;
  if (coverage === null) {
    return (
      <p className="mt-3 text-sm text-neutral-700" data-workflow="reads-coverage-absent">
        {t("metering.upload.coverage.absent", {
          defaultValue:
            "This batch has no cycle, so there is nothing to measure coverage against.",
        })}
      </p>
    );
  }
  // ⛔ **DEF-2732 — `received_in_batch + committed_before_batch` DOUBLE-COUNTS
  // A METER THAT IS IN BOTH, AND THE SENTENCE CONTRADICTED ITSELF ON SCREEN.**
  // This read `coverage.received_in_batch + coverage.committed_before_batch`,
  // which looks right and is not: a meter whose reading was committed BEFORE
  // this batch and appears in it again (a correction, a second register, a
  // re-upload) is counted by both counters. Measured in a browser on
  // 2026-08-31, stage 4 of a real batch on CY-002:
  //
  //     "This cycle expects 5 readings. This batch and the readings already
  //      on file cover 5. 1 have not been read."
  //
  // Five of five covered AND one unread, in one sentence, under BR-MET-130's
  // *"what is mandatory is the SHOWING"*. It is `expected − missing` that
  // answers "how many are covered", and it cannot double-count because the two
  // figures come from one set difference on the server.
  //
  // ⚠ Clamped at zero rather than trusted: the two are computed by different
  // paths, and a negative here would print as a negative. DEF-2440 was the
  // last version of this bug (three field names the server never sent) and it
  // was found the same way — by opening the screen.
  // ⛔ **AND THE SENTENCE CALLED A METER COUNT "readings" — A THIRD WRONG
  //   NUMBER IN THE SAME LINE.** It read *"This cycle expects {{expected}}
  //   readings"* over `expected_meters`, and `batch_cycle_coverage`'s own
  //   docstring says why that is not a synonym: *"Meters, not records, because
  //   the review step's question is 'which meters does this cycle still wait
  //   on'"*. On the seeded tenant CY-002 holds 5 METERS and BR-MET-057 expects
  //   **18 RECORDS** from them — a time-of-use meter owes four readings where a
  //   flat meter owes one — so *"expects 5 readings"* understated the cycle's
  //   real expectation by thirteen. It is DEF-2730's confusion (a meter count
  //   and a reading count are not the same kind of number) one screen over, and
  //   the fix is the same: name the unit the figure is actually in.
  const expected = coverage.expected_meters;
  const missing = coverage.missing_after_batch;
  const received = Math.max(0, expected - missing);
  const complete = missing <= 0;
  return (
    <div
      className={`mt-3 rounded-md border p-3 text-sm ${
        complete
          ? "border-neutral-300 text-neutral-700"
          : "border-warning-500 bg-warning-100 text-text"
      }`}
      data-workflow="reads-coverage"
    >
      <p className="font-semibold">
        {t("metering.upload.coverage.line", {
          expected,
          received,
          missing,
          // B14 rule 33 (RATIFIED 2026-08-30): a FACT is six words, and two
          // short sentences beat one long one. This was three sentences and
          // twenty-four words — *"it too much content we are publishing … high
          // cognative laod"*.
          defaultValue:
            "{{received}} of {{expected}} meters covered. {{missing}} meters still unread.",
        })}
      </p>
      {!complete && (
        <p className="mt-1">
          {t("metering.upload.coverage.allowed", {
            // BR-MET-130's *"you can post anyway"*, at B14 rule 33's six words
            // per sentence. What the second sentence used to spell out — read
            // late or estimated — is what a chase list IS; on screen that is
            // rationale, which the rule puts at zero words.
            defaultValue: "You can post anyway. Unread meters join the chase list.",
          })}
        </p>
      )}
    </div>
  );
}

/**
 * One row of CR-054 task 12's table: every meter in the batch whose plan
 * resolves to the SAME register model, tallied.
 *
 * Built by `registerGroups` in `UploadReadsWizard.tsx` — a pure function over
 * the stored rule outcomes, so it is provable without a browser and without a
 * network, and this file only draws it.
 */
export interface RegisterGroup {
  /** `time_of_use` · `demand` · `flat` … — `rating.model.*` in the catalogue. */
  planModel: string;
  /** Distinct meters on this model in this batch. */
  meters: number;
  /** How many of them are SHORT of the set their plan requires. */
  short: number;
  /** Registers the plan expects across those meters. */
  expects: number;
  /** Registers the file actually carried, counted against the expected set. */
  arrived: number;
  /** Registers not in the file. `expects - arrived` by construction. */
  missing: number;
  /** The distinct register names that are short — `tou_on`, `demand`, … */
  missingChannels: string[];
  /** The staged rows of the SHORT meters — what the two bulk actions act on. */
  rowNos: number[];
  /**
   * The SHORT meters themselves — asset id and issued number, one entry per
   * meter (the Reads→Work door, PO ruling 2026-09-14).
   *
   * ⚠ **NOT DERIVABLE FROM `rowNos`, WHICH IS WHY IT IS ITS OWN FIELD.** A row
   * number names a STAGED LINE of the file and a TOU meter short of three
   * windows has three of them; a visit is raised once per METER, at one address.
   * Counting rows would send a crew to the same door three times.
   *
   * ⚠ **THE `assetId` IS A UUID AND MUST NEVER REACH A SCREEN (B14 rule 31).**
   * It is the anchor the raise is keyed on. `meterNo` is the visible value.
   */
  shortMeters: { assetId: string; meterNo: string }[];
}

/**
 * ⚖️ **CR-054 TASKS 12 AND 13 — THE REGISTER-COMPLETENESS TABLE, GROUPED BY
 * PLAN MODEL, WITH ITS TWO BULK ACTIONS.**
 *
 * ⚠ **EVERY FIGURE IN IT WAS ALREADY STORED AND NOTHING ON SCREEN GROUPED
 * THEM.** `validation.plan_register_completeness` has recorded `expected`,
 * `received`, `missing` and a human `summary` per (meter, date) since CR-038 W1,
 * and `PlanRegisterResolver` stamps the `plan_model` that produced the set. A
 * clerk could read *"expects total/tou_on/tou_mid/tou_off, file has total
 * only"* on one row and had no way at all to learn that it was true of nine
 * meters. Hard-won law 2 at screen scale, which is CR-054's own diagnosis of
 * itself.
 *
 * ⚠ **`EXPECTS · ARRIVED · SHORT` IS THE PO'S OWN QUESTION**, asked on
 * 2026-08-30: *"how do we mtch whether it matches with meter and it matches
 * with billing"*. The consequence is real and is stated where the shortfall is:
 * `apps/rating/pricing/models/demand.py` REFUSES an absent demand read by name
 * and `tou.py` refuses a priced window nothing measured, so an incomplete meter
 * produces **no bill**, and the cheap place to fix it is here rather than in the
 * bill run.
 *
 * ⚠ **THE TWO ACTIONS ARE ORDINARY DISPOSITIONS.** `Estimate all` and `Send
 * someone out` are `estimate` and `field_visit`, both of which
 * `dispositionsFor("warning")` already offers per row; this is the same write,
 * asked once. Nothing new is asked of the server and no rule is decided here —
 * BR-MET-049's shortfall stays a WARNING, because whether a clerk may post an
 * incomplete meter is Open 2 and unruled, and a hard stop invented at a call
 * site is exactly what the prime directive forbids.
 *
 * ⚠ **A GROUP WITH NO SHORTFALL GETS NO BUTTONS**, because there is nothing to
 * estimate and nobody to send out — a disabled pair would be two controls that
 * do nothing (hard-won law 2), and a live pair would let a clerk mark a
 * complete meter for a field visit by pressing the wrong row.
 */
export function RegisterCompleteness(props: {
  groups: readonly RegisterGroup[];
  busy: boolean;
  onEstimate: (group: RegisterGroup) => void;
  onFieldVisit: (group: RegisterGroup) => void;
  t: Translator;
}) {
  const { t } = props;
  if (props.groups.length === 0) {
    // ⚠ NOT SILENCE, AND NOT "all complete" EITHER. An empty list here means the
    // rule reached no verdict on any meter — no plan, or rating could not answer
    // — and `RuleResultsTable` above names it as an unavailable rule with the
    // server's own reason. Saying "every meter is complete" would be the DEF-075
    // posture inverted: an absence of evidence printed as evidence of absence.
    return null;
  }
  return (
    <div className="mt-4" data-reads="register-completeness">
      <Kicker as="div" className="mb-1.5 block">
        {t("metering.upload.registers.caption")}
      </Kicker>
      <div className="w-full overflow-x-auto">
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("metering.units.col.plan")}</th>
              <th scope="col" className="[&&]:text-right">
                {t("metering.routes.col.meters")}
              </th>
              <th scope="col" className="[&&]:text-right">
                {t("metering.upload.registers.col.expects")}
              </th>
              <th scope="col" className="[&&]:text-right">
                {t("metering.upload.registers.col.arrived")}
              </th>
              <th scope="col" className="[&&]:text-right">
                {t("metering.upload.registers.col.short")}
              </th>
              <th scope="col">{t("metering.upload.col.action")}</th>
            </tr>
          </thead>
          <tbody>
            {props.groups.map((group) => (
              <tr
                key={group.planModel === "" ? "unstated" : group.planModel}
                data-reads-plan={group.planModel}
                data-reads-short={group.short}
              >
                <td>
                  {group.planModel === ""
                    ? t("metering.upload.registers.planUnstated")
                    : t(`rating.model.${group.planModel}`, { defaultValue: group.planModel })}
                </td>
                <td className="[&&]:text-right tabular-nums">{group.meters}</td>
                <td className="[&&]:text-right tabular-nums">{group.expects}</td>
                <td className="[&&]:text-right tabular-nums">{group.arrived}</td>
                <td className="[&&]:text-right tabular-nums">{group.missing}</td>
                <td>
                  {/* ⚖️ **THE SHORT REGISTERS, BY NAME, IN THE DECISION CELL
                      (`CR-096-BRC02`).** The blueprint draws them here — *"On-peak
                      · Mid-peak · Off-peak"* beside the actions — and they were
                      under the SHORT figure. **Naming them is the whole point:**
                      a clerk deciding whether to estimate needs to know WHICH
                      windows are missing, because on a demand or time-of-use
                      plan the units differ per register and that is the wrong-
                      register trap Q7 puts first.
                      ⚠ **ABOVE the controls, never among them** — B14's row-of-
                      controls rule: a row of controls holds only things a person
                      can press, and a register name is a FACT. */}
                  {group.missing > 0 && (
                    <p className="mb-2 text-xs" data-reads="short-registers">
                      {group.missingChannels
                        .map((channel) =>
                          t(`metering.reads.channel.${channel}`, { defaultValue: channel }),
                        )
                        .join(" · ")}
                    </p>
                  )}
                  {group.short > 0 && (
                    <span className="flex flex-wrap gap-2">
                      <Button
                        variant="ghost"
                        disabled={props.busy}
                        onClick={() => props.onEstimate(group)}
                      >
                        {t("metering.upload.registers.estimateAll")}
                      </Button>
                      <Button
                        variant="ghost"
                        disabled={props.busy}
                        onClick={() => props.onFieldVisit(group)}
                      >
                        {t("metering.upload.disposition.field_visit")}
                      </Button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </div>
    </div>
  );
}

/**
 * **BR-MET-127 ON THE RECEIPT — the readings the upload REFUSED, by name.**
 *
 * The rule's own words: *"A Replace (or Insert & update) row whose existing
 * read is BILLED is refused with the read named and the reason ('billed —
 * correct it through the billed-correction door'); the refusal is a row
 * outcome, never a batch failure; nothing bulk ever opens a money correction."*
 *
 * ⚠ **THIS IS THE DEF-659 LESSON APPLIED TO A SECOND FIGURE.** That defect was
 * a batch answering `posted` over rows that did not land. A batch that posts
 * 1,179 of 1,180 and prints only the 1,179 is the same failure one row wide:
 * the clerk walks away and one customer's correction is never made. So the
 * refused rows are listed, each naming its reading, and the count is stated
 * even when the list is truncated.
 */
export function RefusedBilledRows(props: {
  rows: readonly { row_no: number; existing_read?: string | null; reason: string }[];
  total: number;
  t: Translator;
}) {
  const refused = props.rows.filter((row) => row.reason === "billed_read_refused");
  if (refused.length === 0) return null;
  return (
    <div
      className="mt-4 rounded-md border border-warning-500 bg-warning-100 p-3 text-sm text-text"
      data-workflow="reads-refused-billed"
    >
      <p className="font-semibold">
        {props.t("metering.upload.refusedBilled.title", {
          count: props.total,
          defaultValue:
            "{{count}} reading(s) were not changed because a bill has already been issued from them.",
        })}
      </p>
      <p className="mt-1 text-neutral-700">
        {props.t("metering.upload.refusedBilled.why", {
          defaultValue:
            "A correction to a billed reading changes money, so it is never made as a side effect of an upload. Open each one and correct it deliberately.",
        })}
      </p>
      <ul className="mt-2 list-disc pl-5">
        {refused.map((row) => (
          <li key={row.row_no}>
            {props.t("metering.upload.refusedBilled.row", {
              row: row.row_no,
              read: row.existing_read ?? "—",
              defaultValue: "Row {{row}} — {{read}}",
            })}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * **THE CORRECTIONS THIS BATCH MADE — `superseded_reads`.**
 *
 * `posted_reads: 41` answers two completely different events identically: 41
 * readings ADDED and 41 readings CORRECTED. On a correction upload the second
 * number is the one the clerk came for.
 */
export function SupersededSummary(props: { count: number; mode: ReadWriteMode; t: Translator }) {
  if (props.count === 0) return null;
  return (
    <p className="mt-2 text-sm text-text" data-workflow="reads-superseded">
      {props.t("metering.upload.superseded.line", {
        count: props.count,
        defaultValue:
          "{{count}} reading(s) already on file were corrected. Each old reading is kept and closed, pointing at the new one.",
      })}
    </p>
  );
}

/**
 * ⛔ **THE CO-SIGN — a control that, until CR-038 W7, could not have existed.**
 *
 * S28's own docstring said so, verbatim: *"No supervisor co-sign toggle. OQ-042
 * closed it as a tenant setting (default ON) and no endpoint serves that
 * setting — `read_batch_dict` returns `cosigned_by` and nothing writes it.
 * Drawing the checkbox would offer a control that changes nothing."* That was
 * the right call then (hard-won law 2) and it is why the writer had to land
 * first. It has.
 *
 * TWO honest states and no third:
 *  · already co-signed → who and when, as a fact, with no control;
 *  · not co-signed → the action, ENABLED only for a role OQ-042 names
 *    (SysAdmin/Executive) and otherwise disabled WITH its reason (BR-SHL-025).
 *
 * ⚠ **AND IT SAYS THAT IT DOES NOT BLOCK THE POST**, because that is the truth
 * and the server says so in the payload (`cosign_blocks_post: false`). OQ-042's
 * *"blocks when enabled"* half needs a tenant toggle whose home is the S64
 * settings document another lane owns — DEF-815. A control that implied a block
 * that does not happen would be a worse lie than the missing control was.
 */
export function CosignPanel(props: {
  cosignedBy: string | null;
  cosignedAt: string | null;
  blocksPost: boolean;
  mayCosign: boolean;
  busy: boolean;
  onCosign: () => void;
  formatWhen: (iso: string) => ReactNode;
  t: Translator;
}) {
  const { t } = props;
  const signed = props.cosignedBy !== null;
  return (
    <div
      className="mt-4 rounded-md border border-neutral-300 p-3 text-sm"
      data-workflow="reads-cosign"
    >
      <p className="font-semibold text-text">
        {t("metering.upload.cosign.title", { defaultValue: "Supervisor co-sign" })}
      </p>
      {signed ? (
        <p className="mt-1 text-text" data-workflow="reads-cosign-given">
          {t("metering.upload.cosign.given", { defaultValue: "Co-signed" })}
          {props.cosignedAt !== null && <> · {props.formatWhen(props.cosignedAt)}</>}
        </p>
      ) : (
        <>
          <p className="mt-1 text-neutral-700">
            {props.blocksPost
              ? t("metering.upload.cosign.required", {
                  defaultValue: "This batch must be co-signed before it can be posted.",
                })
              : t("metering.upload.cosign.optional", {
                  defaultValue:
                    "Optional. A co-sign records that a second person reviewed this batch; it does not hold the post.",
                })}
          </p>
          <div className="mt-2">
            <Button
              variant="secondary"
              disabled={!props.mayCosign || props.busy}
              onClick={props.onCosign}
            >
              {t("metering.upload.cosign.action", { defaultValue: "Co-sign this batch" })}
            </Button>
          </div>
          {!props.mayCosign && (
            <p className="mt-1 text-neutral-700" data-workflow="reads-cosign-denied">
              {t("metering.upload.cosign.denied", {
                defaultValue:
                  "Only a System Admin or an Executive can co-sign a read batch, and it cannot be your own signature twice.",
              })}
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CR-054 W4 · PARTIAL POSTING ON SCREEN (tasks 15, 17 and 25)
// ══════════════════════════════════════════════════════════════════════════

/**
 * ⚖️ **CR-054 TASK 15 — THE ALL-OR-NOTHING BANNER BECOMES A STATEMENT OF WHAT
 * WILL HAPPEN.**
 *
 * ⛔ **WHAT STOOD HERE WAS A REFUSAL, AND ON 2026-08-30 IT BECAME FALSE.**
 * Stage 3 rendered `metering.upload.review.errorsBlock` in a `RefusalStrip`:
 * *"1 error row(s) still need a decision before this batch can post."* — read
 * in a browser at 2.94.0, beside a `Load →` button the screen had disabled.
 * `services.commit_read_batch` stopped raising `errors_need_resolution` that
 * same day (BR-MET-940), so the sentence described a refusal the server no
 * longer makes and the fence kept the clerk from ever reaching the behaviour
 * the PO asked for.
 *
 * The PO's ruling, verbatim: *"all or nothing will not work - we accept what is
 * correct and rejct what i not correct - then create csv file at loading stage
 * itself so that suer can see all cases thata re rejcted"*.
 *
 * ⚠ **IT IS NOT A REFUSAL STRIP AND MUST NOT BECOME ONE AGAIN.** A refusal
 * strip carries `role="alert"` and the danger tier, and both are claims: that
 * something is blocked, and that the operator must act before continuing.
 * Neither is true. This is a `role="status"` statement of consequence, in the
 * warning tier only while rows will actually be held.
 *
 * ⚠ **THE HELD COUNT IS NOT A THREAT, IT IS AN OFFER** — hence the download
 * beside it, which is the ruling's own second half and the reason this panel
 * takes the file callbacks rather than leaving them to the receipt.
 */
export function PostSplitStatement(props: {
  /** From `postSplit()` — the server's own row facts, bucketed the way
   *  `read_rejects.would_hold` buckets them. */
  willPost: number;
  willHold: number;
  /** How many of the held are errors NOBODY HAS DECIDED — the count the old
   *  refusal was about. Stated as a fact, never as a gate. */
  unresolvedErrors: number;
  /** False when the rows on screen do not add up to the batch's own row count
   *  — the screen then says it cannot state the split rather than printing a
   *  number that is wrong (DEF-016's failure mode, and law 1: a figure that
   *  claims a guarantee it does not have is worse than an absence). */
  reconciles: boolean;
  /** `null` while the rejects file cannot be asked for — the batch has not
   *  been validated, so the server would refuse (BR-SHL-025: the control is
   *  drawn disabled WITH its reason, never as a live button that 409s). */
  onDownload: (() => void) | null;
  downloading: boolean;
  downloadError: string | null;
  t: Translator;
}) {
  const { t } = props;
  const holding = props.willHold > 0;
  return (
    <div
      role="status"
      data-reads="post-split"
      data-reads-hold={props.willHold}
      className={`mt-3 rounded-md border p-3 text-sm ${
        holding ? "border-warning-500 bg-warning-100 text-text" : "border-neutral-300 text-text"
      }`}
    >
      <p className="font-semibold">
        {!props.reconciles
          ? t("metering.upload.split.unknown", {
              defaultValue:
                "The rows on this screen do not add up to the batch, so the split cannot be stated. Run the rules again.",
            })
          : holding
            ? // ⚠ **"1 rows will post" — THE PLURAL BUG THE BLUEPRINT NAMES
              // (`CR-096-BRC02`, its own stage-3 note).** This read
              // `{{post}} rows will post` with no plural form at all, so every
              // single-row batch printed the broken grammar on the last screen
              // before an irreversible click. `count` is i18next's plural
              // selector — the ONE variable it inspects — so the row count is
              // passed as `count` and `hold` rides beside it.
              //
              // ⚠ **AND THE SENTENCE IS TWO SENTENCES NOW.** It ran to twelve
              // words (*"…and you can download them"*) over a download control
              // sitting directly beneath it. B14 rule 33: an instruction caps
              // at six words per sentence, and *two sentences of six beat one
              // sentence of twelve*.
              t("metering.upload.split.line", {
                count: props.willPost,
                hold: props.willHold,
              })
            : t("metering.upload.split.all", { count: props.willPost })}
      </p>
      {props.reconciles && props.unresolvedErrors > 0 && (
        <p className="mt-1" data-reads="post-split-unresolved">
          {t("metering.upload.split.unresolved", {
            count: props.unresolvedErrors,
            defaultValue:
              "{{count}} of them carry an error nobody has decided. Giving each one a decision here is cheaper than correcting the file later.",
          })}
        </p>
      )}
      {holding && (
        <RejectsDownload
          count={props.willHold}
          onDownload={props.onDownload}
          downloading={props.downloading}
          error={props.downloadError}
          where="review"
          t={t}
        />
      )}
    </div>
  );
}

/**
 * ⚖️ **CR-054 TASK 17 — THE REJECTS FILE, OFFERED TWICE.**
 *
 * Once at stage 3, beside the statement above, and once on the stage-5 receipt.
 * They are two different moments and both need it: the PO asked for the file
 * *"at loading stage itself"*, and `DEF-2487`'s finding one importer over is
 * that hanging the only download off the receipt makes it unreachable exactly
 * when a commit has just gone wrong.
 *
 * ⛔ **IT IS NOT LABELLED "YOUR FILE BACK", AND `DEF-2672` IS WHY.** The account
 * importer's failures file IS the operator's original row byte for byte;
 * `read_import.parse_csv` keeps only the nine mapped targets, so the reads
 * version comes back on the PUBLISHED template's headers, carrying the values
 * the clerk typed for the columns reads uses and nothing else. It re-uploads
 * without being re-mapped — which is what the clerk actually needs — but any
 * copy promising their own spreadsheet would be false, so the sentence below
 * says what it really is.
 *
 * ⚠ **DISABLED WITH ITS REASON, NEVER HIDDEN (BR-SHL-025).** `results.csv`
 * refuses a batch that has not reached `validated`, and the server's own
 * refusal keys for it (`metering.import.not_checked_no_download` and
 * `…not_loaded_no_download`) say *"run"* and *"loaded"* where reads says
 * *"batch"* and *"posted"* — the two sentences CR-054's backend lane recorded
 * as OWED and could not write. Rather than render somebody else's noun at a
 * clerk, this offers nothing to press until the state is right and says why in
 * the reads vocabulary (`DEF-2733`).
 */
export function RejectsDownload(props: {
  count: number;
  onDownload: (() => void) | null;
  downloading: boolean;
  error: string | null;
  /** `review` before the commit, `receipt` after — the two moments say
   *  different things because one is a forecast and the other is a fact. */
  where: "review" | "receipt";
  t: Translator;
}) {
  const { t } = props;
  return (
    <div className="mt-2" data-reads={`rejects-${props.where}`}>
      <Button
        variant="secondary"
        disabled={props.onDownload === null || props.downloading}
        onClick={() => props.onDownload?.()}
      >
        {props.downloading
          ? t("metering.upload.rejects.downloading", { defaultValue: "Building the file…" })
          : props.where === "review"
            ? t("metering.upload.rejects.downloadReview", {
                count: props.count,
                defaultValue: "Download the {{count}} rows that will not post",
              })
            : t("metering.upload.rejects.downloadReceipt", {
                count: props.count,
                defaultValue: "Download the {{count}} rows that were not filed",
              })}
      </Button>
      <p className="mt-1 text-neutral-700">
        {t("metering.upload.rejects.note", {
          defaultValue:
            "It comes back on the standard template's columns — the values you typed, plus why each row failed and how to fix it. It is not the spreadsheet you uploaded. Correct those cells and upload it again.",
        })}
      </p>
      {props.onDownload === null && (
        <p className="mt-1 text-neutral-700" data-reads="rejects-unavailable">
          {t("metering.upload.rejects.notYet", {
            defaultValue: "Run the rules first — nothing has been judged yet, so there is no list.",
          })}
        </p>
      )}
      {props.error !== null && (
        <p className="mt-1 text-danger-700" role="alert">
          {props.error}
        </p>
      )}
    </div>
  );
}

/**
 * ⚖️ **CR-054 TASK 25 — A READ DATE OFF THE STATED MONTH, ON A TIERED PLAN.**
 *
 * **THE SIGNED RULE, VERBATIM (B4.4, ❄️ FROZEN — quoted, never recomputed):**
 * tier thresholds *"reset each bill"*, and for short/long periods the tier
 * *"thresholds scale with the prorated period"*.
 *
 * **WHY THIS IS WORTH A WARNING AND A WRONG DATE ELSEWHERE IS NOT.** On a flat
 * tariff a mistyped read date moves the period and the money moves with it,
 * visibly. On a TIERED tariff it silently re-cuts every boundary: CR-054's own
 * worked illustration is a 0–1,000 tier becoming 0–500 over fifteen days of
 * thirty, so the same consumption lands in a different tier at a different
 * price and **the bill still looks plausible**. Nothing downstream can catch
 * it, because nothing downstream knows what date was meant.
 *
 * ⚠ **WHAT IT COMPARES AGAINST IS THE CLERK'S OWN STATEMENT, NOT A GUESS.**
 * The reading month is chosen by hand at stage 1 and the reading sheet
 * pre-fills every date inside it — so a tiered row dated outside that month is
 * an EDIT, which is exactly the event CR-054 asks to flag (*"the sheet
 * pre-fills the date precisely so this edit is rare; this flags it when it
 * happens"*). No heuristic, no threshold and no majority vote: two dates, one
 * of which the clerk typed at stage 1.
 *
 * ⚠ **IT IS A WARNING AND NEVER A GATE.** A route genuinely walked across a
 * month boundary is a real thing, and BR-MET-940 has just removed the last
 * place this screen refused anything. Whether such a row should be refused is
 * not a lane's call (prime directive) — it is stated, and the clerk decides.
 */
export function TieredDateWarning(props: {
  /** Row numbers whose meter is on a tiered plan and whose read date falls
   *  outside the batch's stated reading month. */
  rowNos: readonly number[];
  /** `YYYY-MM-DD` as chosen at stage 1, rendered as the month it names. */
  statedMonth: string;
  t: Translator;
}) {
  const { t } = props;
  if (props.rowNos.length === 0) return null;
  const shown = props.rowNos.slice(0, 12);
  return (
    <div
      role="status"
      data-reads="tiered-date-warning"
      data-reads-rows={props.rowNos.length}
      className="mt-3 rounded-md border border-warning-500 bg-warning-100 p-3 text-sm text-text"
    >
      <p className="font-semibold">
        {t("metering.upload.tieredDate.title", {
          count: props.rowNos.length,
          month: props.statedMonth.slice(0, 7),
          defaultValue:
            "{{count}} row(s) on a tiered tariff are dated outside {{month}}, the reading month you chose.",
        })}
      </p>
      <p className="mt-1">
        {t("metering.upload.tieredDate.why", {
          defaultValue:
            "A tiered tariff's bands are cut to the length of the period, so a wrong date reprices every band and the bill still looks right. A 0–1,000 band becomes 0–500 over fifteen days of thirty.",
        })}
      </p>
      <p className="mt-1" data-reads="tiered-date-rows">
        {t("metering.upload.tieredDate.rows", {
          rows: shown.join(", "),
          defaultValue: "Rows: {{rows}}",
        })}
        {props.rowNos.length > shown.length && " …"}
      </p>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-038 W7 tasks 3/4/5 (CR-038 R1+R2 · CR-036 (g) · BR-MET-127 · BR-MET-130 · BR-MET-129 · OQ-042 closure · B14 rules 9/10/21 · BR-SHL-020 · BR-SHL-025) · AMENDED 2026-08-31 by the CR-054 W4 lane (tasks 15/17/25 + DEF-2732)
// generated: 2026-08-26 by the CR-038 W7 one-rail lane
// checklist: A✔ B✔ C✔(ReadsImportRail.dom.test.tsx, 17 cases) D✔(the server halves are apps/metering/write_modes.py + services.cosign_read_batch) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: vitest 488 passed/26 todo over src/features/metering + src/components/workflow + src/styles + src/api · eslint src clean · tsc --noEmit clean (it was RED on the branch tip — DEF-816) · G31 unmoved by this file (BORN Route B, in the ledger) · G27 19→17 components after this lane's eleven-catalogue fan-in · G15 unmoved at 1115 (every new key is translated) · three RED proofs quoted in the lane report
// exceptions: E3 `replace`'s caution says the mode does exactly what `insert & update` does TODAY and names the open question (OQ-418) rather than implying an out-of-file behaviour the server does not have — the BR-MET-099 "a control whose name is a lie" posture, applied honestly · E3 `CosignPanel` states that the co-sign does NOT hold the post, from the server's own `cosign_blocks_post` flag, because OQ-042's "blocks when enabled" half is unbuilt (DEF-815 — its tenant toggle's home is the S64 settings document a concurrent lane owns) · E4 the write mode is drawn as three radio CARDS rather than the shared SegmentedField because each mode owes a consequence sentence and a segmented control has nowhere to put one; the control vocabulary (role="radiogroup" over native radios) is unchanged
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
