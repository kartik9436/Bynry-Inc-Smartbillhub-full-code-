// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 W9 task 3/4/8 — the FRONTEND half of the event-reads door.
//           The backend half landed 2026-08-26 (`metering.services
//           .commit_event_reads`, `customers.seams.commit_event_reads`,
//           `MOVE_IN_FIELDS + initial_reads`, `MOVE_OUT_FIELDS + final_reads`)
//           and NOTHING ON A SCREEN COLLECTED A READING — hard-won law 2 in
//           its exact shape, one door further along than DEF-786.
//           Screens: S19 (move-in step 3) · S20 (move-out step 2)
//           ⚠ NO STORY OWNS THE CAPTURE ITSELF — hard-won law 8. US-CUS-004/005
//           own the wizards and BR-CUS-021 names the reading, and no epic in
//           `04-docs/05-modules/03-customers/06-epics/` carries the control.
//           REPORTED by this lane, not invented into one.
// Rules:    BR-CUS-021 (VERBATIM, PO closure batch 2026-08-08): *"Initial reads
//           at new-account/move-in: per active meter, source AMI/manual/
//           estimate, prior-final prefill, committed via the metering service
//           (append-only BR-MET-017)"* ·
//           BR-MET-128 (VERBATIM, PO 2026-08-26): *"it will be as per event -
//           bascially we will ahve to create an record in reading that such
//           reading ahs been colelcted - and it is generated due to that event;
//           + plus the user"* — one context per wizard, and a transfer stores
//           ONE read serving both accounts ·
//           BR-MET-129 (VERBATIM, PO 2026-08-26): *"No if reading are colelcted
//           we have to store the reading, we can give the warning, but we cannot
//           reject the reading … otherwise, just tagging vacant and customer
//           using utility services - never will be captured - there can be fraud
//           also by people"* — warnings post with their flags; only errors refuse ·
//           BR-MET-026/027/058 (the estimate: disclosed method, capped at the
//           tenant's consecutive maximum, that register's OWN history) ·
//           DEF-495 / BR-RAT-081 (WHICH meters a reading is required for has no
//           reader — a stated absence, never a guess) ·
//           hard rule 3 (a quantity travels with its unit) ·
//           B14 rule 21 (Tailwind utilities only; NO stylesheet class is added)
// Tests:    07-frontend/src/features/customers/moveReadsCapture.test.tsx
// ───────────────────────────────────────────────────────
/**
 * **THE READING CONTROL BOTH MOVE WIZARDS WERE MISSING.**
 *
 * ════════════════════════════════════════════════════════════════════════════
 * WHY ONE COMPONENT AND NOT TWO
 * ════════════════════════════════════════════════════════════════════════════
 * A move-in's OPENING read and a move-out's FINAL read are the same act against
 * the same registers through the same door — `commit_event_reads`, differing
 * only in the `event` word stamped on the row. Two copies would drift, and the
 * one that drifted would be the one a clerk uses less. The `event` never
 * reaches this file at all: the wizard names it in its own payload key
 * (`initial_reads` / `final_reads`) and the SERVER decides the context, so a
 * screen cannot mislabel a reading.
 *
 * ════════════════════════════════════════════════════════════════════════════
 * ⛔ FOUR THINGS THIS CONTROL REFUSES TO DO
 * ════════════════════════════════════════════════════════════════════════════
 *  1. **INVENT A ROW.** A meter the clerk leaves blank never reaches the
 *     payload — not as `0`, not as `null`, not as an empty string. CR-038 W9
 *     task 3, verbatim: *"unread registers stay visible and nothing is
 *     invented"*. `eventReadRows` below is that rule as a pure function.
 *  2. **HIDE HOW OLD THE PREFILLED NUMBER IS.** ⚠ **THIS REFUSAL USED TO SAY
 *     THE OPPOSITE — that the box is NEVER prefilled — and that text was a
 *     comment explaining a behaviour this file no longer has (hard-won law 1).
 *     It is replaced rather than annotated.** The W9 lane read BR-CUS-021's
 *     *"prior-final prefill"* as ambiguous, built an EMPTY box with the prior
 *     read in the help line, and flagged that it had chosen (`OQ-394`).
 *     **The PO ruled the other way on 2026-08-27, verbatim: _"(a) Box opens
 *     with 42,864 in it"_.** BR-CUS-021 stands as written and the divergence
 *     is reversed here.
 *
 *     **So the cost the PO ruled WITH IN FRONT OF THEM is what this control
 *     now has to make visible.** A clerk in a hurry presses Next; an
 *     eight-day-old number closes the account, bills the final invoice and
 *     becomes what the next occupant is measured from — and those eight days
 *     bill as **zero**. Nothing on screen would say so if the box held a bare
 *     number. Therefore **the reading's DATE travels with the number on the
 *     control**, so what a person skims is *"Last read 42,864 kWh · read 8
 *     days ago"* and not *"42864.000000"*.
 *  3. **DECIDE WHICH METERS NEED A READING.** `tenant_services.metered`
 *     (BR-RAT-081) has no reader anywhere in the product (DEF-495), so a
 *     reading is OFFERED on every meter and REQUIRED on none, and the panel
 *     says so. Deriving it from the asset category would be a guess: a
 *     sub-meter is read and a cart is not, and only that declaration knows.
 *  4. **SEND A VALUE AND AN ESTIMATE FOR ONE REGISTER.** The door refuses the
 *     contradiction rather than picking (`metering.event_reads.value_and_
 *     estimate`), so the control makes it unreachable: ticking *"could not be
 *     read"* clears the value and locks the box.
 *
 * ════════════════════════════════════════════════════════════════════════════
 * TASK 8 — WHERE THE ESTIMATE IS OFFERED, AND WHAT IT PROMISES
 * ════════════════════════════════════════════════════════════════════════════
 * *"A missing event read routes through the EXISTING estimation service —
 * disclosed, capped at the configured consecutive maximum, per register. Never
 * a silent zero."*
 *
 * The offer is one checkbox per register: **the meter could not be read**. It
 * promises nothing about the outcome, and that is deliberate — the estimate may
 * legitimately REFUSE (no history · the consecutive cap · the `demand` channel ·
 * no validation config), and each refusal comes back AS DATA on the answer,
 * beside the meter. So the checkbox's own help line says the honest thing —
 * *"we will work one out if we can, and tell you if we cannot"* — and
 * `MoveReadsResult` renders whichever of the two happened, per register.
 */
import type { EventReadsResult } from "@/api/endpoints";
import { useState } from "react";

import { formatQuantity, trimQuantity } from "@/components/UnitCell";
import { parkAgeDays } from "@/components/WizardFrame";
import type { Translator } from "@/features/tenancy/settingsShared";

import { groupsInOrder } from "./UnitAssetsPanel";
import type { UnitAssetRow, UnitAssets } from "./UnitAssetsPanel";

/** One register's draft, as the clerk left it. `meterNo` is the ASSET NUMBER,
 *  which is what the door resolves a meter by (`seams.meter_by_no`). */
export interface ReadDraftRow {
  meterNo: string;
  value: string;
  /** *"The meter could not be read"* — task 8's offer. */
  estimate: boolean;
  /**
   * `CR-122-BRC06` — **the day THIS register was read**, ISO, or `""` for
   * *"the day the flow is dated"*.
   *
   * The blueprint draws a `READ DATE` per row and argues for it in its own
   * caption: *"Every date opens on the move-in day, so a clerk who changes
   * nothing gets what the screen does today. The water meter was read three
   * days before the tenant moved in, and now it can say so."* That is the
   * whole feature — one shared date was a fiction whenever a walk-by round
   * took more than a day.
   *
   * ⚠ **`""` IS NOT A MISSING DATE, IT IS A DEFERRED ONE.** `_commit_event_reads`
   * fills an absent `read_at` with the flow's own event date, so an untouched
   * row keeps exactly the behaviour it had before this column existed. Sending
   * the event date explicitly on every row would look identical and would
   * silently freeze the date a clerk later changed on step 3.
   */
  readAt: string;
}

/** Keyed by asset id, so two meters with the same number cannot collide. */
export type ReadsDraft = Record<string, ReadDraftRow>;

/**
 * ⚠ **THE `meters` AND `sub_meters` GROUPS, AND THAT BOUNDARY IS THIS LANE'S
 * JUDGMENT — STATED, NOT SMUGGLED.** A reading is a REGISTER position, and
 * BR-AST-004's category is the only fact this payload carries about what a row
 * is. `behind_the_meter` holds devices that hang off a meter (a battery, an
 * inverter, a cart) and `unclassified` holds rows whose type resolved to
 * nothing at all — offering a reading box against either would ask a clerk to
 * key a number that has nowhere to go.
 *
 * It is a boundary and not a rule, because DEF-495 is the fact underneath: the
 * product cannot say which meters are read. Every row this list includes is
 * OFFERED and none is REQUIRED, so the cost of the boundary being slightly
 * wrong is a missing box, never an invented reading.
 */
export const READABLE_ASSET_GROUPS = ["meters", "sub_meters"] as const;

/** Every register a reading may be keyed against, in the panel's own order. */
export function readableAssets(assets: UnitAssets | undefined): UnitAssetRow[] {
  // ⚠ **`groups` IS GUARDED THOUGH THE TYPE SAYS IT CANNOT BE MISSING — DEF-757
  // IS WHY.** `UnitAssets.counts` was typed non-optional too, `tsc` was
  // satisfied, and a payload without it took the WHOLE move-in screen down with
  // `Cannot read properties of undefined (reading 'total')` — found by clicking
  // and by nothing else, because no unit test constructs a payload the type
  // forbids. This is the same shape one field along, so it is defended rather
  // than trusted.
  if (assets === undefined || !Array.isArray(assets.groups)) {
    return [];
  }
  return groupsInOrder(assets.groups)
    .filter((group) => (READABLE_ASSET_GROUPS as readonly string[]).includes(group.category))
    .flatMap((group) => group.assets)
    .filter((asset) => asset.asset_no !== null && asset.asset_no !== "");
}

/**
 * **THE WHOLE "NOTHING IS INVENTED" RULE, PURE — provable without a browser.**
 *
 * A row reaches the payload only when the clerk keyed a value OR asked for an
 * estimate. Blank stays blank: no `0`, no `null`, no empty string, no row.
 *
 * ⚠ An estimate row carries NO `value` even if one was typed before the box was
 * ticked. The door refuses the contradiction and the control prevents it, but a
 * pure function that could still emit it would be one refactor away from
 * emitting it.
 */
export function eventReadRows(draft: ReadsDraft): Record<string, unknown>[] {
  const rows: Record<string, unknown>[] = [];
  for (const row of Object.values(draft)) {
    if (row.meterNo === "") {
      continue;
    }
    // `CR-122-BRC06` — the row's OWN date, and only when the clerk set one.
    // An absent `read_at` takes the flow's event date server-side, which is
    // precisely the behaviour every row had before this column existed.
    const readAt = row.readAt.trim();
    // A date the clerk EMPTIED never travels: the screen holds Continue on it.
    const dated = readAt === "" || readAt === READ_DATE_CLEARED ? {} : { read_at: readAt };
    if (row.estimate) {
      rows.push({ meter_no: row.meterNo, estimate: true, ...dated });
      continue;
    }
    const value = row.value.trim();
    if (value === "") {
      continue; // ⛔ NOT a zero. An unread register stays unread.
    }
    rows.push({ meter_no: row.meterNo, value, ...dated });
  }
  return rows;
}

/**
 * `DEF-CUS-10165` — **a Read date the clerk EMPTIED**, which is not the same
 * as one never touched. `readAt: ""` already means *"the flow's own date"*
 * (deferred, so it follows a changed move-in date), so an emptied box needs
 * its own value or the box would refill itself with the move-in date while
 * the clerk is typing over it. Never sent (`eventReadRows` drops it) — the
 * step holds Continue on it as *Enter the read date.*
 */
export const READ_DATE_CLEARED = "-";

/**
 * `DEF-CUS-10165` — **every row DATED, for a flow whose read date is
 * required** (PO 2026-10-17: *"Move-in, step 1 (opening) - read date is
 * required"*). A row still deferring (`readAt: ""`) takes `eventDate` — the
 * date the screen SHOWED in its Read date box — so the server receives the
 * date the clerk saw and bounds it (after today, before the last reading)
 * rather than filling a default it does not check. An `eventDate` of `""`
 * leaves the row deferring, exactly as before.
 */
export function datedReadsDraft(draft: ReadsDraft, eventDate: string): ReadsDraft {
  if (eventDate === "") return draft;
  const out: ReadsDraft = {};
  for (const [key, row] of Object.entries(draft)) {
    out[key] = row.readAt.trim() === "" ? { ...row, readAt: eventDate } : row;
  }
  return out;
}

/** The `initial_reads` / `final_reads` key, or nothing at all.
 *
 *  ⚠ **AN EMPTY CAPTURE OMITS THE KEY RATHER THAN SENDING `[]`.** The server
 *  refuses an empty list on purpose (`customers.event_reads.rows_required`) —
 *  *"a wizard that sent readings must learn what happened to every one"* — and
 *  a move with no readings at all is perfectly lawful. Sending `[]` would turn
 *  the lawful case into a refusal. */
export function readsPayloadPart(key: string, draft: ReadsDraft): Record<string, unknown> {
  const rows = eventReadRows(draft);
  return rows.length === 0 ? {} : { [key]: rows };
}

/**
 * **BR-CUS-021's `"prior-final prefill"`, AS THE BOX'S OPENING VALUE.**
 *
 * PO ruling 2026-08-27, verbatim: *"(a) Box opens with 42,864 in it"* — closes
 * `OQ-394` and reverses the W9 lane's divergence.
 *
 * ⚠ **TRIMMED, NOT REFORMATTED, AND THE DIFFERENCE MATTERS.** The wire carries
 * BR-MET-019's `NUMERIC(18,6)`, so the register position arrives as
 * `42864.000000`. `trimQuantity` removes the six storage zeros and touches no
 * significant digit (DEF-646's rule, one derivation — see `UnitCell`), giving
 * `42864`. It does **not** group: `42,864` in an input would reach the server
 * as part of the decimal the clerk submits. The GROUPED form is what the help
 * line shows, because that one is read and never posted.
 *
 * A register with no committed read seeds `""`, which `eventReadRows` skips —
 * so refusal 1 survives the prefill: an unread register is still never invented.
 */
export function priorFinalValue(asset: UnitAssetRow): string {
  const raw = asset.last_read?.current_value ?? null;
  return raw === null ? "" : trimQuantity(raw);
}

/**
 * Every readable register seeded with its prior final — the draft a wizard
 * OPENS with, which is the same object the payload is built from.
 *
 * ⚠ **ONE DERIVATION ON PURPOSE.** The box the clerk sees and the row that
 * reaches `final_reads` read the SAME draft entry. A component that merely
 * DISPLAYED the prior read while the draft stayed empty would show `42,864`,
 * take a Next, and post nothing — the ruling's exact failure with a friendlier
 * face.
 */
export function prefilledReadsDraft(assets: UnitAssets | undefined): ReadsDraft {
  const draft: ReadsDraft = {};
  for (const asset of readableAssets(assets)) {
    draft[asset.id] = {
      meterNo: asset.asset_no ?? "",
      value: priorFinalValue(asset),
      estimate: false,
      // Empty = the flow's event date. See `ReadDraftRow.readAt`.
      readAt: "",
    };
  }
  return draft;
}

/**
 * **THE PREFILL UNDER WHATEVER THE CLERK HAS ACTUALLY TYPED.**
 *
 * ⚠ **DERIVED, NOT SEEDED BY AN EFFECT — AND THE FIRST DRAFT OF THIS FILE GOT
 * IT WRONG.** The obvious build is a `useEffect` that writes
 * `prefilledReadsDraft` into state once the assets land. It renders correctly
 * and it has a hole: `useEffect` runs AFTER paint, so for one frame the box
 * shows `42,864` while the state the payload is built from is still `{}`. A
 * submit in that frame posts NOTHING while the screen shows a number — the
 * exact failure `prefilledReadsDraft`'s own docstring warns about, rebuilt as a
 * race instead of a bug. It is also invisible to every test here, because
 * `renderToStaticMarkup` runs no effects at all and would have shown green.
 *
 * So there is no effect and no seeded state. The prior finals are the FLOOR and
 * the clerk's entries are laid over them, which means the value on screen and
 * the value in the payload are the same expression at every instant, including
 * the first.
 *
 * A cleared box is respected: `withReadDraft` writes an entry the moment a
 * register is touched, so `""` typed by a person overrides the seed — spreading
 * `typed` LAST is what makes deleting a number mean deleting it.
 */
export function effectiveReadsDraft(
  assets: UnitAssets | undefined,
  typed: ReadsDraft,
): ReadsDraft {
  return { ...prefilledReadsDraft(assets), ...typed };
}

/**
 * The MOVE-OUT's reads state, with `OQ-394`'s prefill already in it.
 *
 * ⚠ **THE MOVE-IN NO LONGER CALLS THIS (PO 2026-09-23, `DEF-CUS-6362`).** Both
 * move wizards did, so the prefill could not ship on one and not the other.
 * The PO then approved an EMPTY move-in box with the last reading in its own
 * column, so the two now differ ON PURPOSE and by ruling: BR-CUS-021 carries
 * the amendment, and `MoveInWizard` holds a plain `useState<ReadsDraft>({})`.
 */
export function useReadsDraft(
  assets: UnitAssets | undefined,
): [ReadsDraft, (draft: ReadsDraft) => void] {
  const [typed, setTyped] = useState<ReadsDraft>({});
  return [effectiveReadsDraft(assets, typed), setTyped];
}

/**
 * HOW OLD the prefilled number is, in whole days — `null` when the read has no
 * date on record.
 *
 * ⚠ **`parkAgeDays` IS REUSED RATHER THAN REWRITTEN.** It already counts whole
 * days off the UTC instants and clamps a future timestamp to `0`, and its own
 * docstring says why a local getter meeting a date-only string is how an
 * off-by-one day is born. A second copy here would be a second answer to
 * *"how old is this?"*, and the one that drifted would be the one closing
 * accounts.
 */
export function priorReadAgeDays(asset: UnitAssetRow, now: Date): number | null {
  return parkAgeDays(asset.last_read?.read_at ?? null, now);
}

/** *"read 8 days ago"* — the half of the help line the PO's cost lives in. */
export function priorReadAgeLabel(asset: UnitAssetRow, now: Date, t: Translator): string {
  const days = priorReadAgeDays(asset, now);
  if (days === null) {
    return t("customers.move.capture.age.unknown", {
      defaultValue: "read on a date we do not hold",
    });
  }
  if (days === 0) {
    return t("customers.move.capture.age.today", { defaultValue: "read today" });
  }
  if (days === 1) {
    return t("customers.move.capture.age.yesterday", { defaultValue: "read yesterday" });
  }
  return t("customers.move.capture.age.days", {
    defaultValue: "read {{count}} days ago",
    count: days,
  });
}

/**
 * The whole provenance sentence that travels WITH the number on the control.
 *
 * *"Last read 42,864 kWh · read 8 days ago"* — and NOTHING ELSE.
 *
 * ⚠ **THE `since the one before` CONSUMPTION CLAUSE WAS DROPPED HERE, ON
 * PURPOSE.** This line used to carry it, and it now sits beside a number the
 * clerk is about to ACCEPT rather than beside one they are about to type. The
 * ruling's whole safety depends on *"read 8 days ago"* being SKIMMED, and a
 * third clause is what a skim loses. `UnitAssetsPanel` above still shows the
 * consumption for anyone who wants it.
 *
 * ⚠ **THE UNIT IS SHOWN WHEN THE SERVER SENDS ONE AND NEVER INVENTED** (hard
 * rule 3). `_last_read_position` may serve a position without a unit; a made-up
 * `kWh` on a water meter is worse than a bare figure, so the bare figure is
 * what renders in that case and the absence is visible.
 */
export function priorReadLine(asset: UnitAssetRow, now: Date, t: Translator): string {
  const read = asset.last_read;
  if (read === null || read.current_value === null) {
    return t("customers.move.capture.noPrior", {
      defaultValue: "No earlier reading on record for this register.",
    });
  }
  const grouped = formatQuantity(read.current_value);
  return t("customers.move.capture.prior", {
    defaultValue: "Last read {{value}} · {{age}}",
    value: read.unit === null || read.unit === "" ? grouped : `${grouped} ${read.unit}`,
    age: priorReadAgeLabel(asset, now, t),
  });
}

/** The draft with one register changed — the wizards hold the state. */
export function withReadDraft(
  draft: ReadsDraft,
  assetId: string,
  meterNo: string,
  change: Partial<Omit<ReadDraftRow, "meterNo">>,
): ReadsDraft {
  const current = draft[assetId] ?? { meterNo, value: "", estimate: false, readAt: "" };
  const next = { ...current, meterNo, ...change };
  // Ticking *"could not be read"* CLEARS the value: the two never travel
  // together, and a hidden value is worse than a refused one.
  return { ...draft, [assetId]: next.estimate ? { ...next, value: "" } : next };
}

/** The server's `event_reads` answer. ⚠ Typed ONCE, in `api/endpoints.ts` with
 *  every other wire shape — a second copy here would be hard-won law 5, and the
 *  copy that drifted would be the one a screen reads. */
export type EventReadsAnswer = EventReadsResult;

/**
 * **WHAT WAS ACTUALLY CAPTURED, ON THE DONE SCREEN.**
 *
 * ⚠ **THE ESTIMATE REFUSALS ARE THE REASON THIS COMPONENT EXISTS.** A posted
 * count alone would let a clerk leave believing three meters were handled when
 * one of them came back *"no history — field visit"*. BR-MET-129's warnings are
 * shown for the same reason: the reading POSTED and something was flagged on
 * it, and *"posted, nothing said"* is how a flag never gets worked.
 */
export function MoveReadsResult(props: { answer: EventReadsAnswer | undefined; t: Translator }) {
  const { t, answer } = props;
  if (answer === undefined) {
    return null;
  }
  const refused = answer.estimates.filter((row) => row.estimated === false);
  const estimated = answer.estimates.filter((row) => row.estimated === true);
  return (
    <div data-move-reads-result={answer.event}>
      <p data-move-reads-posted={answer.posted_reads}>
        {t("customers.move.captured.posted", {
          defaultValue: "{{count}} reading(s) recorded against this move.",
          count: answer.posted_reads,
        })}
      </p>
      {estimated.length > 0 && (
        <ul data-move-reads-estimated={estimated.length}>
          {estimated.map((row) => (
            <li key={`${row.meter_no}-${row.channel}`} className="text-sm">
              {t("customers.move.captured.estimated", {
                defaultValue: "{{meter}} — estimated {{amount}} {{unit}} ({{method}})",
                meter: row.meter_no,
                amount: row.consumption ?? "",
                unit: row.unit ?? "",
                method: row.estimation_method ?? "",
              })}
            </li>
          ))}
        </ul>
      )}
      {refused.length > 0 && (
        // ⛔ NOT a zero, and not silence: the register has no reading and the
        // clerk has to know which one and why.
        <ul data-move-reads-refused={refused.length}>
          {refused.map((row) => (
            <li key={`${row.meter_no}-${row.channel}`} className="text-sm text-warning-700">
              {t(`customers.move.captured.refused.${row.reason ?? "unknown"}`, {
                defaultValue: t("customers.move.captured.refusedFallback", {
                  defaultValue:
                    "{{meter}} — no reading was recorded and none could be worked out. Send someone to read it.",
                  meter: row.meter_no,
                }),
                meter: row.meter_no,
              })}
            </li>
          ))}
        </ul>
      )}
      {answer.warnings.length > 0 && (
        // BR-MET-129: the reading POSTED and travels with its flags.
        <p className="text-sm text-warning-700" data-move-reads-warned={answer.warnings.length}>
          {t("customers.move.captured.warned", {
            defaultValue:
              "{{count}} reading(s) were recorded with something flagged on them. They are on the Meter Reads list to work through.",
            count: answer.warnings.length,
          })}
        </p>
      )}
    </div>
  );
}

// ⚠ **`MoveReadsStepSection` IS DELETED (`DEF-CUS-6362`, PO 2026-09-23).** It
// drew the grouped inventory and this capture as two tables on the move-in's
// step 3; the move-in now mounts ONE table, `MoveInReadingsTable`. The capture
// above is still the move-out's.

/**
 * `CR-122-BRC06` — **put a parked draft's readings back, distrusting every
 * one of them.**
 *
 * A draft is JSON that left this app days ago (`wizardPark.ts` §3 argues the
 * posture in full, and `BR-SHL-048 (b)` rules it: *"a draft is RE-VALIDATED at
 * execution and never trusted from the park"*). So this reads the shape it
 * knows and silently drops anything else: a row that is not an object, a
 * `meterNo` that is not a string, a `value` that arrived as a number.
 *
 * ⚠ **IT KEEPS ROWS FOR REGISTERS THAT MAY NO LONGER EXIST, DELIBERATELY.** A
 * meter can be changed while a draft sits parked. Filtering against today's
 * asset list here would silently delete a clerk's typing on the way back in;
 * leaving the row costs nothing, because `MoveReadsCapture` renders one row per
 * register it can actually see and the server resolves by meter number and
 * refuses what it cannot find — by name, with everything still on screen.
 */
export function hydrateReadsDraft(raw: unknown): ReadsDraft {
  const draft: ReadsDraft = {};
  if (raw === null || typeof raw !== "object") {
    return draft;
  }
  for (const [assetId, value] of Object.entries(raw as Record<string, unknown>)) {
    if (value === null || typeof value !== "object") {
      continue;
    }
    const row = value as Record<string, unknown>;
    const meterNo = typeof row.meterNo === "string" ? row.meterNo : "";
    if (meterNo === "") {
      continue;
    }
    draft[assetId] = {
      meterNo,
      value: typeof row.value === "string" ? row.value : "",
      estimate: row.estimate === true,
      readAt: typeof row.readAt === "string" ? row.readAt : "",
    };
  }
  return draft;
}
