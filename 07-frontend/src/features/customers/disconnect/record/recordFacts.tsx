// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — the DISCONNECT CASE RECORD's shared row primitives
//           (blueprint p143). B14 rule 43, PO verbatim: *"make them coponents
//           - dont write stand alone code , engineer it"*.
// Rules:    B14 rule 33 (RATIONALE is ZERO WORDS ON SCREEN — the server's
//           `detail` is WHY a fact is missing and never reaches the page body)
//           · rule 21 (Tailwind utilities; this directory is on
//           `styles/route-b-migrated.txt`) · CLAUDE.md rule 2 (money displays
//           at 2 decimals)
// ───────────────────────────────────────────────────────
/**
 * One drawn fact — label left, value RIGHT, a hairline between rows.
 *
 * ⚠ **THE MARKUP IS `TransferRecordPage.TransferFactRow`'s, CHARACTER FOR
 * CHARACTER**, which is `MoveRecordPage.Fact`'s before it. Three record
 * screens with one row shape cannot drift into three; a fourth opinion about
 * what a fact row looks like is what B14 rule 36 exists to stop.
 *
 * ⚠ **THE HAIRLINE IS `border-b` ON THE ROW WITH `last:border-0`, NOT A GAP.**
 * A `divide-y` on the parent is equivalent right up until one row is
 * conditionally absent — which is what a case at an early tier does to this
 * page.
 */
import type { ReactNode } from "react";

import { MoneyCell } from "@/components/MoneyCell";

import type { DisconnectAbsence, DisconnectFact, DisconnectMoney } from "./disconnectRecordEndpoints";

export function FactRow(props: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-neutral-200 py-3 last:border-0">
      <dt className="text-sm text-neutral-600">{props.label}</dt>
      <dd className="text-sm font-medium text-right text-neutral-900">{props.children}</dd>
    </div>
  );
}

/**
 * A stated absence, drawn as the quiet half of a row.
 *
 * ⚠ **THE SHORT LABEL IS WHAT A CLERK READS AND THE SERVER'S SENTENCE IS THE
 * `title` — B14 rule 33.** The `detail` explains WHY a fact is missing, which
 * is RATIONALE and is zero words on screen. It stays in the payload and on the
 * attribute so anybody debugging can reach it.
 *
 * ⚠ **THIS IS THE ONE PLACE IN THIS DIRECTORY WHERE A REASON RIDES ON A
 * `title`, AND THE DISTINCTION IS DELIBERATE.** A REFUSAL — why a control
 * cannot be pressed — is VISIBLE TEXT here and always (`CutRefusal` below,
 * `BR-SHL-025`, and the Approve dialog's ratified pattern), because a touch or
 * keyboard user never sees a tooltip and a refusal has to be READ. An ABSENCE
 * is different: the screen has already said the thing is missing, in three
 * words, and the sentence underneath is the rationale rule 33 keeps off the
 * page.
 */
export function Absent(props: { absence: DisconnectAbsence; label: string }) {
  return (
    <span className="text-neutral-600 font-normal" title={props.absence.detail}>
      {props.label}
    </span>
  );
}

/** A fact row that draws whichever arm the server filled. */
export function Fact(props: {
  label: string;
  fact: DisconnectFact<unknown> | undefined;
  absentLabel: string;
  render: (value: never) => ReactNode;
}) {
  const fact = props.fact;
  // ⚠ **AN ABSENT FIELD IS NOT AN ABSENT FACT.** A payload that carries no
  // `raised_by` at all — an older server, a field added since — must still say
  // something a clerk can read, and the only honest thing is the same short
  // label the server's own absence would carry.
  if (fact === undefined || (fact.value === null && fact.unavailable === null)) {
    return (
      <FactRow label={props.label}>
        <span className="text-neutral-600 font-normal">{props.absentLabel}</span>
      </FactRow>
    );
  }
  return (
    <FactRow label={props.label}>
      {fact.unavailable ? (
        <Absent absence={fact.unavailable} label={props.absentLabel} />
      ) : (
        props.render(fact.value as never)
      )}
    </FactRow>
  );
}

/**
 * One money row.
 *
 * ⚠ **A FIGURE OR A SENTENCE, AND NEVER A ZERO STANDING IN FOR EITHER.**
 * `DEF-127`: a fabricated `$0.00` *"looks exactly like a settled account"*, and
 * on a page that previews taking a household's supply away it would look like
 * a household nobody should be cutting.
 */
export function MoneyRow(props: {
  label: string;
  money: DisconnectMoney | undefined;
  absentLabel: string;
  /** Drawn after the figure — p143's `· raised at the cut`. */
  suffix?: ReactNode;
}) {
  const money = props.money;
  const served = money !== undefined && money.unavailable === null && money.stored !== null;
  return (
    <FactRow label={props.label}>
      {served ? (
        <span>
          {/* CLAUDE.md rule 2 — 4 decimals stored, 2 displayed. `MoneyCell`
              owns that formatting for all ~137 screens and this one adds no
              second opinion about it. */}
          <MoneyCell amount={money!.stored!} currency={money!.currency ?? "USD"} />
          {props.suffix ? <span className="text-neutral-600"> {props.suffix}</span> : null}
        </span>
      ) : money?.unavailable ? (
        <Absent absence={money.unavailable} label={props.absentLabel} />
      ) : (
        <span className="text-neutral-600 font-normal">{props.absentLabel}</span>
      )}
    </FactRow>
  );
}

/**
 * **THE REFUSAL BESIDE A CONTROL THAT CANNOT BE PRESSED — VISIBLE TEXT.**
 *
 * ⚠ **NEVER A `title`.** `BR-SHL-025` and the Approve dialog's ratified
 * pattern (`serviceRequestDecisions.tsx`): *"a touch or keyboard user never
 * sees a tooltip, and the whole point is that the refusal is READ."* p143
 * draws `Mark as cut` greyed and a greyed button with nothing beside it is a
 * clerk standing at a counter with no idea what to do next.
 *
 * ⚠ **THE WORDS ARE THE SERVER'S**, rendered through the catalogue by code.
 * This component states no rule of its own — it cannot, because it does not
 * know which of eight preconditions failed.
 */
export function Refusal(props: { id: string; children: ReactNode; testId?: string }) {
  return (
    <p
      id={props.id}
      role="status"
      data-testid={props.testId}
      className="text-sm font-semibold text-neutral-900"
    >
      {props.children}
    </p>
  );
}

/**
 * **THE DAYS NOBODY HAS BILLED** — PO ruling 2026-09-21, ruling 1's other half.
 *
 * A cut may now be COMPLETED with no final bill, and a `disconnected` account
 * leaves the bill run, so no ordinary run will ever pick those days up. The PO
 * ruled WHO raises the bill; they did not rule that the days stop mattering —
 * *"the unbilled days must remain visible to somebody"* — and this row is
 * where they stay visible.
 *
 * ⚠ **A COMPONENT AND NOT TWO COPIES (B14 rule 43).** The record panel draws
 * it as a standing fact and `FinishCutDialog` draws it before a clerk commits;
 * a second opinion about how a date range renders is exactly what that rule
 * exists to stop.
 *
 * ⚠ **IT RENDERS NOTHING WHEN THERE IS NOTHING TO SAY**, which is the ordinary
 * case: the server derives the window on every read, so the row disappears on
 * its own the day billing's single-bill workflow raises the bill. Nothing here
 * caches it and nothing clears a flag.
 *
 * ⚠ **THE WINDOW HAS NO DATES WHEN BILLING COULD NOT BE ASKED AT ALL** — the
 * server sends `unbilled_days_not_readable` for that, and it is NOT the same
 * claim as *nothing is unbilled*. The label then says the days are not known
 * rather than printing a range nobody computed.
 *
 * B14 rule 33: the label is three words and the value is a FACT; the server's
 * `detail` is RATIONALE and rides the `title`, never the page body.
 */
export function UnbilledDaysRow(props: {
  days: (DisconnectAbsence & { from?: string; to?: string; days?: number }) | null | undefined;
  label: string;
  unknownLabel: string;
  render: (from: string, to: string, days: number) => ReactNode;
  testId?: string;
}) {
  const stated = props.days;
  if (stated === null || stated === undefined) {
    return null;
  }
  const known =
    typeof stated.from === "string" &&
    typeof stated.to === "string" &&
    typeof stated.days === "number";
  return (
    <FactRow label={props.label}>
      <span
        data-testid={props.testId}
        data-unbilled-days={known ? String(stated.days) : "unknown"}
        title={stated.detail}
      >
        {known
          ? props.render(stated.from as string, stated.to as string, stated.days as number)
          : props.unknownLabel}
      </span>
    </FactRow>
  );
}
