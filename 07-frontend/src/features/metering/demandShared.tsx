// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-007/008 (S28 steps 2 and 4) · US-MET-012 (S25 reads list) ·
//           US-MET-013 (S29 read detail) · US-AST-005 (S50 Reads tab)
//           Screens: S25 · S28 · S29 · S50 · S21 (Meters / Usage tabs)
// Rules:    BR-MET-051 (*"Demand: manual demand-register value at cycle read +
//           reset noted; ratchet off (BR-RAT proposal stands)"*, PO RD-4,
//           CONFIRMED) · BR-MET-049 (*"demand → +demand record"*) ·
//           BR-MET-059 (the channel model — extensible by a VALUE) ·
//           BR-MET-062 (a missing demand value is NEVER estimated — a peak
//           drives kW dollars) · BR-SHL-025 (a control you may not use renders
//           disabled WITH its reason) · B14 rule 21 (new UI is Tailwind
//           utilities and adds NO class to a stylesheet)
//           CLAUDE.md hard rule 3 (a quantity never travels without its unit)
// ───────────────────────────────────────────────────────
// CR-038 W4 — the demand pieces every read surface shares.
//
// WHY THIS FILE EXISTS AT ALL, rather than three copies of a badge:
//
// **kW is not kWh, and five screens put the two in one table.** A `demand`
// record is a maximum DEMAND — the highest rate of draw in the cycle — while
// every other channel on the same meter is a quantity CONSUMED. Rating prices
// them differently (`demand_rate_per_kw` beside `energy_rate_per_kwh`), and a
// column that added them would print a number with no meaning at all. The
// reads list, the read page, the asset's Reads tab and the account's Meters
// tab all draw demand rows and energy rows in one table today, and not one of
// them said which was which.
//
// ✅ **BOTH WARNINGS THAT USED TO STAND HERE ARE CLOSED — BR-MET-143, PO
// 2026-08-27, closing OQ-391 and DEF-797.** They are restated rather than
// deleted, because what they described was real and shipped, and a later
// reader meeting `PeakQuantity` is entitled to know what moved.
//
// **1 · THE QUANTITY.** This file said: *"the committed row still carries a
// `consumption`, because `_post_row` runs BR-MET-019's `(current − prior) ×
// multiplier` for every channel … on a demand register that subtraction
// produces the DIFFERENCE BETWEEN TWO PEAKS, which nothing bills"* — so
// `PeakQuantity` rendered `current_value` and the delta was REPORTED. It has
// now been FIXED at the write: `validation.compute_consumption` gives a
// maximum register BR-MET-051's own figure, *"manual demand-register VALUE at
// cycle read"*, scaled by the meter's multiplier. So `consumption` on a demand
// row IS the peak that is billed, and that is what these components render —
// the server's stored figure, never a client-side re-derivation (BR-MET-056).
// `current_value` stays on the read detail as the RAW register beside it.
//
// **2 · THE UNIT.** This file said it would not invent `kW` because no signed
// rule stated a demand read's unit, and it was right not to. The PO has now
// stated it: *"A demand reading carries kW - we have to match utility service
// unit and meter reading unit"*. The unit is recorded per REGISTER, so the
// server sends `kW` on this row and `kWh` on the energy row of the same meter,
// and these components still print exactly what the server sent.
//
// ⚠ **AND THE PEAK BADGE STILL EARNS ITS PLACE.** The unit says the quantity
// is POWER; the badge says the figure is a MAXIMUM rather than a total, which
// no unit string can carry — and it is the badge, not the unit, that stops a
// reader adding this row to the one above it.
//
// EVERY CLASS IN THIS FILE IS A TAILWIND UTILITY (B14 rule 21). The file is
// listed in `src/styles/route-b-migrated.txt` so `routeBUtilities.test.ts`
// asks the compiler about each one; that is also what lets the four
// NON-migrated screens below import these pieces and add no class token of
// their own, keeping G31 at its ceiling.
import type { ReadImportBatchRow } from "@/api/endpoints";
import { formatQuantity } from "@/components/UnitCell";
import { Button } from "@/components/Button";
import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * BR-MET-059's demand register, named ONCE.
 *
 * The server answers `is_peak` on every read it serves and that flag is what
 * the read surfaces use. This constant exists for the two payloads that carry
 * a `channel` and no flag — `AssetReadRow` (assets' own serialiser, another
 * module's file) — so those screens still ask one shared question instead of
 * spelling the comparison inline. When assets serves its own flag, the callers
 * move to it and this goes.
 */
export const READ_CHANNEL_DEMAND = "demand";

export function isPeakChannel(channel: string | null | undefined): boolean {
  return channel === READ_CHANNEL_DEMAND;
}

/**
 * The marker itself: three letters that stop a reader adding this row to the
 * one above it. Deliberately NOT a `StatusPill` — A12 §Semantic tokens says a
 * tone carries STATUS meaning and never decoration, and "this is the demand
 * register" is a fact about the register, not about the health of the read.
 */
export function PeakBadge(props: { t: Translator }) {
  return (
    <span
      className="inline-flex items-center rounded-sm bg-info-100 px-1 text-xs font-semibold uppercase tracking-label text-info-700"
      title={props.t("metering.reads.peak.why")}
      data-cell="peak"
    >
      {props.t("metering.reads.peak.badge")}
    </span>
  );
}

/**
 * A peak WITH its unit and its marker (hard rule 3 + the note at the top).
 *
 * `quantity` is the demand register's own value as a decimal STRING, never a
 * number. A peak whose value or unit did not arrive renders the absence and
 * says why — BR-MET-062 forbids estimating a demand value, so a missing one is
 * a field visit and never a figure this screen fills in.
 */
export function PeakQuantity(props: {
  quantity: string | null;
  unit: string | null;
  t: Translator;
}) {
  const { t } = props;
  if (props.quantity === null || props.unit === null) {
    return (
      <span className="inline-flex items-center gap-1" data-cell="peak-absent">
        <PeakBadge t={t} />
        <span title={t("metering.reads.peak.absentWhy")}>
          {t("metering.reads.peak.absent")}
        </span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap" data-cell="peak">
      <PeakBadge t={t} />
      {/* ⚠ **BR-MET-144 THROUGH THE ONE CLIENT COMPOSER (DEF-1120).** This
          printed `props.quantity` verbatim, so a demand peak read
          `412.000000 kW` where the reads list — which renders the server's
          composed string — read `412 kW`. Two renderings of one figure, and
          only one of them obeyed the rule. `formatQuantity` is lawful here
          rather than a server sibling because this component is HANDED its
          unit (BR-SHL-250: composed by the side that holds the unit). */}
      <span className="tabular-nums">{formatQuantity(props.quantity)}</span>
      <span className="text-sm">{props.unit}</span>
    </span>
  );
}

/**
 * **BR-MET-143 — A STAGED ROW'S REGISTER READING, WITH THE UNIT IT WILL POST
 * IN.** S28 step 4, the review table.
 *
 * ⚠ **A UNIT A PERSON CANNOT SEE IS A UNIT NOBODY CAN CHECK.** Until
 * 2026-08-27 the review step printed a staged `value` as a bare number, and
 * the comment beside it explained why: *"consumption is computed at commit
 * from the meter and carries the meter's unit, and CLAUDE.md rule 3 does not
 * allow a quantity to be printed without one."* The reasoning was sound and
 * the consequence was that a clerk approving 1,180 rows read `412` with
 * nothing beside it — so DEF-797's wrong unit (`kWh` on a kW register,
 * **$154.00** where the correct charge was **$4,532.00**) was uncheckable at
 * the one moment a person looks at a reading before it becomes an issued
 * document.
 *
 * The server now sends `unit` on the staged row — the REGISTER's unit, the
 * very string `_post_row` will stamp — so the number can carry it. `null` is
 * still an absence and is rendered as one: an unknown meter has no UoM to
 * read. Rule 3 is satisfied by the TRUE unit or by a stated blank, never by a
 * plausible one.
 *
 * Tailwind utilities only (B14 rule 21); it lives here so the NON-migrated
 * S28 wizard can import it and add no class token of its own.
 */
export function StagedRegisterValue(props: {
  value: string | null;
  unit: string | null;
  t: Translator;
}) {
  const { t } = props;
  if (props.value === null) {
    return <span title={t("metering.upload.review.noRegisterWhy")}>—</span>;
  }
  return (
    <span className="inline-flex items-center justify-end gap-1 whitespace-nowrap">
      <span className="tabular-nums">{props.value}</span>
      {props.unit === null ? (
        <span className="text-sm" title={t("metering.reads.unitUnknownWhy")}>
          {t("metering.reads.unitUnknown")}
        </span>
      ) : (
        <span className="text-sm">{props.unit}</span>
      )}
    </span>
  );
}

/** BR-MET-051's reset, once it is recorded: shown wherever the read is. */
export function DemandResetChip(props: { t: Translator }) {
  return (
    <span
      className="inline-flex items-center rounded-sm bg-warning-100 px-1 text-xs font-semibold text-warning-700"
      title={props.t("metering.reads.demandReset.why")}
      data-cell="demand-reset"
    >
      {props.t("metering.reads.demandReset.noted")}
    </span>
  );
}

// ── S28 step 4 — the reset controls (BR-MET-051) ────────────────────────────

/** What `POST /read-batches/{id}/demand-reset` reported, rendered per row. */
export interface DemandResetReport {
  noted: number[];
  skipped: { row_no: number; reason: string }[];
}

/**
 * The BULK control. A technician who resets a fleet of demand registers on one
 * visit says so ONCE, about the visit — which is why this exists beside the
 * per-row toggle rather than instead of it.
 *
 * BR-SHL-025: with no demand row in the batch the button renders DISABLED with
 * its reason, rather than vanishing — a clerk uploading a water file should
 * learn that the control is not for them, not wonder where it went.
 */
export function DemandResetBulkControl(props: {
  rows: readonly ReadImportBatchRow[];
  busy: boolean;
  report: DemandResetReport | null;
  onNote: () => void;
  t: Translator;
}) {
  const { t } = props;
  const peaks = props.rows.filter((row) => row.is_peak);
  const outstanding = peaks.filter((row) => !row.demand_reset_noted);
  const none = peaks.length === 0;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="ghost"
        disabled={none || props.busy}
        title={none ? t("metering.upload.review.demandResetNone") : undefined}
        onClick={props.onNote}
      >
        {props.busy
          ? t("metering.upload.review.demandResetSaving")
          : t("metering.upload.review.demandResetAll", { count: outstanding.length })}
      </Button>
      {none && (
        <span className="text-sm">{t("metering.upload.review.demandResetNone")}</span>
      )}
      {props.report !== null && (
        // Per ROW, never a bare count: a bulk action whose answer is one number
        // cannot be checked by the person who clicked it.
        <span className="text-sm" data-cell="demand-reset-report">
          {t("metering.upload.review.demandResetDone", {
            noted: props.report.noted.length,
            rows: props.report.noted.join(", "),
            skipped: props.report.skipped.length,
          })}
        </span>
      )}
    </div>
  );
}

/**
 * One row's reset toggle, offered only where the SERVER says the row is the
 * demand register (`is_peak`). The server refuses any other row by name, so
 * this is the screen agreeing with the rule rather than guarding it.
 */
export function DemandResetRowToggle(props: {
  row: ReadImportBatchRow;
  busy: boolean;
  onToggle: (row: ReadImportBatchRow, noted: boolean) => void;
  t: Translator;
}) {
  const { t, row } = props;
  if (!row.is_peak) {
    return null;
  }
  return (
    <label className="inline-flex items-center gap-1 text-sm">
      <input
        type="checkbox"
        checked={row.demand_reset_noted}
        disabled={props.busy}
        onChange={(event) => props.onToggle(row, event.target.checked)}
      />
      {t("metering.upload.review.demandResetRow")}
    </label>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-038 W4 (BR-MET-051 · BR-MET-049 · CLAUDE.md hard rule 3)
// generated: 2026-08-26 by the CR-038 W4 demand lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 the PEAK is rendered from `current_value` and never from
//   `consumption` — BR-MET-019's delta runs on every channel and on a demand
//   register it is the difference between two peaks, which nothing bills;
//   REPORTED · E3 the unit on a peak is the METER's (an energy UoM) because
//   `_post_row` stamps `unit=asset.unit` for every channel and no signed rule
//   states a demand read's unit; `kW` is NOT invented here and an OQ is owed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
