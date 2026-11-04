// ── Trace ──────────────────────────────────────────
// Change:   the DISCONNECT WIZARD REBUILD of 2026-09-25 — **STEP 2 OF FOUR,
//           `Check`**, built from `Step2Check.png` and `MasterStep2.png` AS
//           IMAGES (B14 rule 42).
// Rules:    **BR-CUS-1096** (PO 2026-09-25, verbatim: *"so please show the
//           warining - but dont stop clark from doing his work; we have to tell
//           there is an issue but we ant stop them"*) · **BR-CUS-1098 (b)** (an
//           OCCUPANT's protection does not block a cut of the MASTER account;
//           PO: *"Warn and let them proceed — consistent with your two
//           rulings"*) · BR-CUS-101 · BR-CUS-039 · B14 rules 20, 21, 31, 32,
//           33, 34, 43, 44
// Tests:    ../../DisconnectWizard.test.tsx
// ─────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · NOTHING ON THIS STEP STOPS ANYTHING — `BR-CUS-1096`, AND IT IS A REVERSAL
// ══════════════════════════════════════════════════════════════════════════
// **The five-step step 2 was built to a rule that has been withdrawn.** It
// refused: `disconnects.schedule_cut` → `_require_running` → `halt_reason`
// returns `HALT_PROTECTED` and the schedule is refused, and the screen carried
// the drawn sentence *"Recording one stops the cut."*
//
// **The PO ruled on 2026-09-25 that a protection WARNS and never refuses.** No
// override is offered **because there is nothing to override**, and the middle
// path — proceed, but type a reason — was **put to them and DECLINED**, as was
// refusing outright. *"we ant stop them"* rules out a typed reason, a
// tick-to-acknowledge and a supervisor. **Friction before proceeding has now
// been declined four times across the five rulings of this principle; a fifth
// proposal is the principle applying again rather than a question to raise**
// (CLAUDE.md hard-won law 13).
//
// ⚠ **THE SERVER STILL REFUSES AND THAT IS NOT THIS SCREEN'S TO HIDE.**
// `BR-CUS-1096`'s own row says so: *"the rule is CONFIRMED and the wiring is
// owed; nothing in this repository implements it yet."* The backend half is
// lane CUTPATH's (`apps/customers/disconnects.py`). This step no longer BLOCKS,
// which is what it owns; if the server refuses, the frame's commit failure
// carries the server's own sentence and the entered state is preserved. **A
// screen that pretended the schedule would succeed would be hard-won law 1 —
// a comment claiming a guarantee is not the guarantee.**
//
// ⚠ **AND THE RECORD IS THE ONLY PROTECTION THAT REMAINS, WHICH IS PART OF THE
// RULE RATHER THAN A SECOND ONE.** The product must capture, asking the clerk
// for nothing: which protections were in force, that the warning was shown, who
// proceeded and when. Three of those four are the server's. What this step adds
// is the fourth thing a clerk can only supply themselves — the MARK, and the
// note beside it.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · TEN QUESTIONS, THREE ANSWERS, AND NOW A CLERK'S OWN CHECKLIST — ITEM 3.4
// ══════════════════════════════════════════════════════════════════════════
// `protection_check` answers three of the ten (medical, payment plan, weather
// moratorium) and serves a fourth — dispute — as `outcome: "unavailable"`. Six
// are unbuilt (`DEF-691` / `BR-CUS-101`), and **each missing one is a household
// that can be cut when it should not be.**
//
// The old screen printed all ten as a read-only table with `— not checked` in
// six rows and **no way for a clerk to record having asked anybody**. Under
// this rebuild the table is the CLERK'S OWN CHECKLIST: they may add a check,
// remove one, and mark each **Recorded · Checked · Not required**.
//
// ⚠ **NOTHING IS MANDATORY AND `Continue` DOES NOT LOOK AT THIS TABLE.** A
// blank mark means nobody has got to it, which is true and is worth being able
// to say. Requiring a mark would be friction before proceeding, which is what
// the PO declined four times.
//
// ⚠ **AND THE DRAWN `All clear` CHIP IS STILL NEVER RENDERED.** It is a summary
// of ten findings over a product that holds three, and a green chip over seven
// unasked questions is the single most dangerous sentence this wizard could
// draw. The table reports what was checked and what was not, per row.
import { useMemo } from "react";

import { SelectField, TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { WarningBox } from "@/components/WarningBox";

import { DisconnectTableArray } from "../DisconnectTableArray";
import type { DisconnectArrayColumn } from "../DisconnectTableArray";
import { CHECK_MARKS } from "../disconnectDraft";
import type { CheckMark, DisconnectCheckRow, DisconnectDraft } from "../disconnectDraft";
import { PROTECTION_CHECKS } from "../../transferDisconnectShared";
import type { ProtectionCheckResult, ProtectionCheckRow } from "../../transferDisconnectEndpoints";
import type { Translator } from "../../transferDisconnectShared";

/** `protection_check`'s vocabulary mapped onto `PROTECTION_CHECKS`' codes, so
 *  the screen can put the server's answer in the row the clerk is reading.
 *  ⚠ **DERIVED FROM THE SERVER'S OWN NAMES, NEVER RE-SPELLED.** The two lists
 *  were minted apart and `DEF-CUS-6023` is what a re-spelling costs: two of
 *  five cut reasons were refused on the reason string alone because the front
 *  end asserted its own copy back to itself. */
const SERVER_CHECK_CODE: Readonly<Record<string, string>> = {
  medical: "medical_certificate",
  payment_plan: "payment_plan",
  moratorium: "weather_moratorium",
  dispute: "dispute",
};

export interface CheckStepProps {
  draft: DisconnectDraft;
  onPatch: (next: Partial<DisconnectDraft>) => void;
  t: Translator;
  /** `GET /accounts/{id}/protections`, or `null` while it has not answered. */
  answers: ProtectionCheckResult | null;
  /** `BR-CUS-1098` — the master variant splits the owner's own checks from the
   *  occupants who hold one. */
  master: boolean;
  occupants: number | null;
  /** The occupying accounts that hold a protection.
   *  ⛔ **EMPTY ON EVERY ACCOUNT TODAY** — see this file's §4. */
  occupantProtections: readonly OccupantProtection[];
  /** Who the marks are recorded against, for the `BY` column. The server writes
   *  the real one; this is what the screen shows the clerk about their own
   *  session. */
  actor: string;
}

/** One row of the master variant's `Occupants who hold a protection`. */
export interface OccupantProtection {
  /** The unit's LABEL, never its id (B14 rule 31). */
  unit: string;
  occupant: string;
  protection: string;
  /** `true` where the protection is live, which is what the drawing draws in
   *  the danger tone. */
  inForce: boolean;
}

export function CheckStep(props: CheckStepProps) {
  const t = props.t;

  const answerFor = useMemo(() => {
    const byCode = new Map<string, ProtectionCheckRow>();
    for (const row of props.answers?.checks ?? []) {
      byCode.set(row.check, row);
    }
    return byCode;
  }, [props.answers]);

  const inForce = props.answers?.protections_in_force ?? [];

  const available = useMemo(() => {
    const onTable = new Set(props.draft.checks.map((row) => row.code));
    return PROTECTION_CHECKS.filter((check) => !onTable.has(check.code));
  }, [props.draft.checks]);

  function setRows(rows: DisconnectCheckRow[]): void {
    props.onPatch({ checks: rows });
  }

  function patchRow(index: number, next: Partial<DisconnectCheckRow>): void {
    setRows(props.draft.checks.map((row, i) => (i === index ? { ...row, ...next } : row)));
  }

  const columns: DisconnectArrayColumn<DisconnectCheckRow>[] = [
    {
      key: "check",
      label: t("customers.disconnect.check.colCheck", { defaultValue: "Check" }),
      cell: (row) => (
        <span className="font-semibold">
          {t(`customers.disconnect.protection.${row.code}`, {
            defaultValue: labelOf(row.code),
          })}
        </span>
      ),
    },
    {
      key: "answer",
      label: t("customers.disconnect.check.colAnswer", { defaultValue: "Answer" }),
      cell: (row) => <Answer row={row} answer={answerFor.get(SERVER_CHECK_CODE[row.code] ?? row.code)} t={t} />,
    },
    {
      key: "mark",
      label: t("customers.disconnect.check.colMark", { defaultValue: "Mark" }),
      cell: (row, index) => (
        <SelectField
          id={`disconnect-mark-${row.code}`}
          labelHidden
          label={t("customers.disconnect.check.colMark", { defaultValue: "Mark" })}
          value={row.mark}
          placeholder={t("customers.disconnect.check.pickMark", { defaultValue: "Not marked" })}
          onChange={(value) => patchRow(index, { mark: value as CheckMark })}
          options={CHECK_MARKS.map((mark) => ({
            value: mark.code,
            label: t(`customers.disconnect.mark.${mark.code}`, { defaultValue: mark.en }),
          }))}
        />
      ),
    },
    {
      key: "by",
      label: t("customers.disconnect.check.colBy", { defaultValue: "By" }),
      // ⚠ **BLANK UNTIL THERE IS A MARK.** A name and a date beside an unmarked
      // row would say somebody had looked at it, which is the claim this whole
      // step exists to make carefully.
      cell: (row) => (
        <span className="text-neutral-700">
          {row.mark === ""
            ? "—"
            : t("customers.disconnect.check.byNow", {
                defaultValue: "{{actor}} · today",
                actor: props.actor,
              })}
        </span>
      ),
    },
  ];

  const occupantColumns: DisconnectArrayColumn<OccupantProtection>[] = [
    {
      key: "unit",
      label: t("customers.disconnect.check.colUnit", { defaultValue: "Unit" }),
      cell: (row) => <span className="font-semibold">{row.unit}</span>,
    },
    {
      key: "occupant",
      label: t("customers.disconnect.check.colOccupant", { defaultValue: "Occupant" }),
      cell: (row) => <span>{row.occupant}</span>,
    },
    {
      key: "protection",
      label: t("customers.disconnect.check.colProtection", { defaultValue: "Protection" }),
      cell: (row) => (
        <span className={row.inForce ? "font-semibold text-danger-700" : undefined}>
          {row.protection}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6" data-step="check">
      {/* ⚠ **THE WARNING SAYS WHAT IS TRUE AND THEN SAYS THE CLERK MAY GO ON.**
          Two sentences of four and five words — B14 rule 33's *two sentences of
          six beat one sentence of twelve*. Not one word of WHY. */}
      {inForce.length > 0 && (
        <WarningBox
          tone="now"
          data-warning="protection-in-force"
          sentence={
            <strong>
              {t("customers.disconnect.check.warning", {
                defaultValue: "A protection is in force. You may continue.",
              })}
            </strong>
          }
        />
      )}
      {props.master && props.occupantProtections.length > 0 && (
        <WarningBox
          tone="now"
          data-warning="occupant-protection"
          sentence={
            <strong>
              {t("customers.disconnect.check.occupantWarning", {
                defaultValue: "{{count}} occupants hold a protection. You may continue.",
                count: props.occupantProtections.length,
              })}
            </strong>
          }
        />
      )}

      <DisconnectTableArray<DisconnectCheckRow>
        title={
          props.master
            ? t("customers.disconnect.check.owner", { defaultValue: "The owner" })
            : t("customers.disconnect.check.title", { defaultValue: "What was checked" })
        }
        // A FACT about what this table does, six words, and not a word about
        // the ruling that makes it true.
        fact={t("customers.disconnect.check.blocksNothing", {
          defaultValue: "Nothing here blocks the cut",
        })}
        columns={columns}
        rows={props.draft.checks}
        rowKey={(row) => row.code}
        onChange={setRows}
        removeLabel={t("customers.disconnect.check.removeCheck", {
          defaultValue: "Remove this check",
        })}
        emptyText={t("customers.disconnect.check.noChecks", {
          defaultValue: "No check listed. Add one below.",
        })}
        addLabel={t("customers.disconnect.check.addCheck", { defaultValue: "+ Add a check" })}
        onAdd={() => {
          const next = available[0];
          if (next === undefined) return;
          setRows([...props.draft.checks, { code: next.code, mark: "" }]);
        }}
        addBlockedReason={
          available.length > 0
            ? undefined
            : t("customers.disconnect.check.allAdded", {
                defaultValue: "Every check is already listed.",
              })
        }
        addFact={t("customers.disconnect.check.moreAvailable", {
          defaultValue: "{{count}} more available",
          count: available.length,
        })}
        collection="checks"
      >
        {/* ⚠ **`What happened` IS KEPT — ITEM 3.13.** The five-step wizard drew
            this box and threw away what the clerk typed: nothing held it and
            nothing sent it. It is draft data now and it travels with the
            schedule. On the master variant the drawing puts it under the
            OCCUPANTS table; it is one box either way and it lives with the
            checks, so a clerk types their note in one place. */}
        {!props.master && <WhatHappened draft={props.draft} onPatch={props.onPatch} t={t} />}
      </DisconnectTableArray>

      {props.master && (
        <DisconnectTableArray<OccupantProtection>
          title={t("customers.disconnect.check.occupants", {
            defaultValue: "Occupants who hold a protection",
          })}
          fact={
            props.occupants === null
              ? undefined
              : t("customers.disconnect.check.ofOccupants", {
                  defaultValue: "{{held}} of {{all}}",
                  held: props.occupantProtections.length,
                  all: props.occupants,
                })
          }
          readOnly
          columns={occupantColumns}
          rows={props.occupantProtections}
          rowKey={(row) => row.unit}
          emptyText={t("customers.disconnect.check.noOccupantData", {
            defaultValue: "Occupant protections are not shown yet.",
          })}
          collection="occupant-protections"
        >
          <WhatHappened draft={props.draft} onPatch={props.onPatch} t={t} />
        </DisconnectTableArray>
      )}

      {props.answers === null && (
        <Panel as="section" data-panel="checks-loading">
          <p className="m-0 text-base text-neutral-700">
            {t("customers.disconnect.check.loading", { defaultValue: "Checking the account…" })}
          </p>
        </Panel>
      )}
    </div>
  );
}

/** The `What happened` box. One `TextField`, multiline, with the drawn fact
 *  under it — *Kept on the case.* FOUR WORDS, and it is a FACT rather than
 *  rationale: it says where the note goes, not why the box exists. */
function WhatHappened(props: {
  draft: DisconnectDraft;
  onPatch: (next: Partial<DisconnectDraft>) => void;
  t: Translator;
}) {
  return (
    <div className="mt-4">
      <TextField
        id="disconnect-what-happened"
        label={props.t("customers.disconnect.check.whatHappened", {
          defaultValue: "What happened",
        })}
        value={props.draft.whatHappened}
        multiline
        onChange={(value) => props.onPatch({ whatHappened: value })}
        help={props.t("customers.disconnect.check.keptOnCase", {
          defaultValue: "Kept on the case.",
        })}
      />
    </div>
  );
}

/**
 * The `ANSWER` cell — the server's finding, in the screen's own words.
 *
 * ⚠ **THREE-VALUED, AND THE THIRD VALUE IS THE IMPORTANT ONE.** `outcome:
 * "unavailable"` means the product CANNOT answer, which is not `pass`. A cell
 * that folded the two together would report a clean check on a question nobody
 * asked, on the step that authorises taking away somebody's supply.
 *
 * ⚠ **AND A CHECK THE PRODUCT DOES NOT HOLD AT ALL READS *Your own check***,
 * which is the truth and is three words: the clerk asked somebody, and the
 * product is recording that they did. It is not `— not checked`, which reads as
 * a failure of the product rather than as a question that belongs to a person.
 */
function Answer(props: { row: DisconnectCheckRow; answer: ProtectionCheckRow | undefined; t: Translator }) {
  const t = props.t;
  const answer = props.answer;
  if (answer === undefined || answer.outcome === "unavailable") {
    return (
      <span className="text-neutral-700">
        {t("customers.disconnect.check.ownCheck", { defaultValue: "Your own check" })}
      </span>
    );
  }
  if (answer.outcome === "fail") {
    // IN FORCE. The danger tone is the drawing's and it is the one cell on this
    // step that carries it.
    return (
      <span className="font-semibold text-danger-700" data-answer="in-force">
        {answer.expires_on === null
          ? t("customers.disconnect.check.onFile", { defaultValue: "On file" })
          : t("customers.disconnect.check.onFileTo", {
              defaultValue: "On file · to {{date}}",
              date: answer.expires_on,
            })}
      </span>
    );
  }
  return (
    <span data-answer="clear">
      {t("customers.disconnect.check.noneInForce", { defaultValue: "None in force" })}
    </span>
  );
}

function labelOf(code: string): string {
  return PROTECTION_CHECKS.find((check) => check.code === code)?.en ?? code;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the disconnect wizard rebuild, 2026-09-25 · `Step2Check.png` ·
//         `MasterStep2.png` · blueprint p137 · **BR-CUS-1096** ·
//         **BR-CUS-1098 (b)** · BR-CUS-101 · BR-CUS-039 · DEF-691 ·
//         B14 rules 20, 21, 31, 32, 33, 34, 42, 43, 44
// generated: 2026-09-25 by lane WIZARD
// exceptions:
//   E1 ⛔ **THE SERVER STILL REFUSES A PROTECTED SCHEDULE.** `BR-CUS-1096` is
//      CONFIRMED and unwired; `halt_reason` → `HALT_PROTECTED` still blocks
//      `schedule_cut`. This step no longer blocks, which is its half; the
//      server's half is lane CUTPATH's and is REPORTED rather than worked
//      around. A refusal reaches the clerk through the frame's commit failure,
//      carrying the server's own sentence, with every entered value preserved.
//   E1 ⛔ **`OccupantProtection[]` IS EMPTY ON EVERY ACCOUNT TODAY.**
//      `BR-CUS-1098` requires a row per OCCUPYING account that holds a
//      protection, and `protection_check` answers for ONE account. Walking a
//      master's occupants would be N calls from a browser, which is a read the
//      server owes. The table renders its stated absence rather than an empty
//      list that reads as *nobody is protected* — which on this step is the
//      most expensive thing a screen could imply.
//   E3 **blueprint p137's `Or stop the ladder without a protection` radios and
//      its `Record a protection` form are NOT drawn here.** Neither is on the
//      new drawing; the blueprint's own banner says *"NONE OF THIS IS OPERABLE
//      ON THE SHIPPED SCREEN"*, so nothing live is removed. Stopping a ladder
//      by hand is an act on the CASE and belongs on the case record (lane
//      CUTPATH); `POST /accounts/{id}/protections` is still mounted and still
//      has no door, which is unchanged by this rebuild and is REPORTED.
//   E3 **the drawn `All clear` chip is never rendered** — ten checks drawn,
//      three answered, one `unavailable`.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
