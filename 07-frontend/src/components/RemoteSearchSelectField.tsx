// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-6319 — Product Owner, looking at the Raise-a-refund form,
//          2026-09-23, verbatim: *"why to button - why cannot we have dropdown
//          search drectly for this - user has to do two clicks"*, and then,
//          having heard why it was built that way: *"fix it"*.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT; standalone code inside a
//          page is not reuse) · B14 rule 36 (the shared component kit is how
//          you comply — where the kit lacks a piece, ADD IT TO THE KIT) ·
//          B14 rule 8 (5+ options are searchable) · B14 rule 10 (the asterisk
//          is on the label) · B14 rule 31 (no database id is a visible value) ·
//          B14 rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 · an INSTRUCTION ≤ 6 per
//          sentence · RATIONALE is ZERO words on screen) · B14 rule 21 (this
//          file declares no class; it is listed in route-b-migrated.txt) ·
//          B14 rule 39 (a field is LABEL → INPUT → HELPER) ·
//          BR-SHL-020 (a PLATFORM failure says so, in plain language) ·
//          BR-SHL-012 (a screen says which state it is in) · IS-3 (search is
//          server-side, debounced 300 ms, from two characters) ·
//          IS-10 (the first Esc closes the list, not the modal)
// Impacts: features/payments/paymentsShared.tsx `AccountPickerFields` is the
//          first host. Any screen that must FIND a record on the server and
//          then choose one belongs here too — customers/accountFinder.tsx and
//          metering/OwnerAccount.tsx each hand-roll the same two fields today.
// Tests:   src/components/remoteSearchSelectField.dom.test.tsx (this file) ·
//          src/features/payments/accountSearch.dom.test.tsx (the hosts) ·
//          src/components/RemoteSearchSelectCell.dom.test.tsx (the `cell`
//          variant, added for the New Connect redesign 2026-09-28)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  ONE CONTROL, AND THE FIVE STATES STAY FIVE                              ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The kit already had a combobox — `SearchSelectField` in `FormModal.tsx` — and
// it is NOT this one. It filters a list the browser already holds, so it has
// exactly two things to say: here are the options, or `No matching options.`
// A search that runs on the SERVER has five, and four of them are not options:
//
//   too short   the clerk has typed below IS-3's minimum — nothing was asked
//   searching   the request is in flight
//   failed      THE SEARCH ITSELF could not run. A PLATFORM fact (BR-SHL-020),
//               the one support can act on, and the one thing here that is a
//               refusal rather than a note
//   no match    the search RAN and the answer was none — a fact about the TERM,
//               which is the half the clerk can fix by typing something else
//   matches     the rows, as options
//
// ⚠ **COLLAPSING `failed` AND `no match` INTO ONE EMPTY LIST IS THE REGRESSION
// THIS COMPONENT EXISTS TO AVOID, NOT A SIMPLIFICATION.** They look identical
// in a naive dropdown and they are opposite facts: one means the product is
// broken and one means the clerk mistyped. `DEF-3506` was reported because all
// four non-option states were drawn as one picture — *"unable to search
// account"* — and the repair that followed made them distinguishable by ADDING
// A SECOND CONTROL. That worked, and it cost a clerk two gestures to choose one
// account, which is what `DEF-PAY-6319` is. **The states are what mattered; the
// second control was only how they were reached.** Here they are drawn inside
// ONE panel under ONE control, each in its own visual register: the three
// ordinary ones as `Note`, the platform failure as `RefusalStrip` — the same
// two surfaces the two-field version used, in the same words.
//
// ⚠ **THE PANEL STATE IS A PURE FUNCTION, ON THE `popoverAnchor.ts` PRECEDENT.**
// jsdom does no layout and no gate in this repo reads rendered output (hard-won
// law 6), so the DECISION is pulled out of the DOM where it can be checked
// exhaustively — `remoteSearchPanel` below, and its table of six cases in the
// test file. The component keeps only what genuinely needs a DOM.
//
// ⚠ **AND IT DECLARES NO CLASS OF ITS OWN (B14 rule 21).** The three names it
// composes — `.search-select`, `.search-select-list`, `.field` — are already
// declared in `FormModal.css` for `SearchSelectField`, which is the point: two
// comboboxes in one product that look like two comboboxes is the fault rule 36
// names. Its own layout is Tailwind utilities and this file is listed in
// `src/styles/route-b-migrated.txt`.

import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import { stepActiveOption, useFieldError, FieldLabel } from "./FormModal";
import { FieldError, INVALID_INPUT_CLASS } from "./StateFrame";
import { StatusPill } from "./StatusPill";
import { RefusalStrip } from "./Surfaces";
import { Note } from "./TextBits";

/**
 * One row, as this control names it.
 *
 * ⚠ **`value` IS WHAT POSTS AND `label` IS ALL A CLERK EVER SEES (B14 rule
 * 31).** The host builds the label — it is the host that knows whether an
 * account is named by its number, its customer or neither — and this file never
 * reads, prints or falls back to the value.
 */
export interface RemoteOption {
  value: string;
  label: string;
  /**
   * ⚠ **THREE OPTIONAL WORDS BESIDE THE LABEL — ADDED 2026-10-04 FOR CR-168's
   * ASSIGN PICKER (image 12), AND THEY MOVE NOTHING EXISTING.** Image 12 draws
   * each candidate as *R. Patel · Technician* `Best fit` with its advice
   * right-aligned (*Meter I ✓ · NW · 1 job that day*). `label` stays what the
   * box shows once chosen; `kind` follows it, muted; `badge` is a pill; `aside`
   * sits at the right edge. An option carrying none of the three renders its
   * label exactly as before, so every existing host is byte-for-byte unchanged.
   */
  kind?: string;
  badge?: string;
  aside?: string;
  /** FB-033 — a WARNING pill beside the label (*Off duty since 16:10* in red).
   *  Words only: the option stays choosable. Absent → nothing renders. */
  alert?: string;
  alertTone?: "danger" | "warning";
}

/**
 * What the HOST's search hook knows, as four booleans rather than a shape this
 * file invents. `payments`' `AccountSearchState` is structurally this plus its
 * rows, so a host passes its own state straight in.
 */
export interface RemoteSearchStatus {
  /** Below the minimum length, or nothing typed at all — nothing was asked. */
  idle: boolean;
  /** The request is in flight. */
  searching: boolean;
  /** The search RAN, so no matches means "no such record". */
  searched: boolean;
  /** The search itself could not be run — a PLATFORM fact, never a term fact. */
  failed: boolean;
}

/** The five, plus the sixth that draws nothing at all. */
export type RemoteSearchPanel =
  | "silent"
  | "too-short"
  | "searching"
  | "failed"
  | "no-match"
  | "matches";

/**
 * WHICH OF THE SIX THE PANEL IS IN, from nothing but the facts.
 *
 * ⚠ **THE ORDER OF THESE TESTS IS THE RULE, NOT AN IMPLEMENTATION DETAIL.**
 * `failed` is asked FIRST so that a platform failure can never be read as
 * no-match, whatever else is true at the same moment — that is the whole of
 * BR-SHL-020 in one line, and it is the pair `DEF-PAY-6319`'s brief named as
 * the thing a naive combobox loses.
 */
export function remoteSearchPanel(
  status: RemoteSearchStatus,
  matchCount: number,
  typedSomething: boolean,
): RemoteSearchPanel {
  if (status.failed) {
    return "failed";
  }
  if (status.searching) {
    return "searching";
  }
  if (matchCount > 0) {
    return "matches";
  }
  if (status.searched) {
    return "no-match";
  }
  if (typedSomething) {
    return "too-short";
  }
  // Nothing typed and nothing asked: the field's own help line already says
  // what to type, and a panel repeating it would be a second sentence for one
  // fact (B14 rule 32).
  return "silent";
}

/**
 * The four sentences, IN THE HOST'S OWN WORDS.
 *
 * ⚠ **THE KIT DOES NOT OWN THESE STRINGS AND MUST NOT.** A catalogue is written
 * in its own language (B14 rule 35) and *"No account matches that"* is not the
 * sentence a meter search or a technician search would say. Passing them in is
 * also what let this component replace the two-field picker with **no change to
 * a single catalogue key** — the payments sentences that `DEF-3506` wrote are
 * the ones that still render.
 */
export interface RemoteSearchWords {
  /** An INSTRUCTION — ≤ 6 words per sentence (B14 rule 33). */
  tooShort: string;
  /** A FACT — ≤ 6 words. */
  searching: string;
  /** A refusal — ≤ 6 words per sentence, and it names the PLATFORM. */
  failed: string;
  /** A FACT about the term — ≤ 6 words. */
  noMatch: string;
}

/**
 * `FormModal`'s `inputClass` and `describedBy` are private to that module and
 * are NOT imported here, deliberately: on the day this was written that file
 * carried 245 uncommitted lines of a sibling lane's work, and a pathspec commit
 * naming it would have published them (hard-won law 11, mechanism five). Two
 * joins of three strings are the cheaper of the two mistakes.
 *
 * ⚠ **IF A THIRD CALLER EVER NEEDS THEM, EXPORT `FormModal`'s AND DELETE THESE**
 * — two definitions of one string is what hard-won law 5 is about, and this is
 * a deliberate second one with a note on it rather than an unnoticed one.
 */
function fieldInputClass(invalid: boolean): string {
  return invalid ? `input ${INVALID_INPUT_CLASS}` : "input";
}

function fieldDescribedBy(id: string, hasHelp: boolean, hasError: boolean): string | undefined {
  const ids = [hasHelp ? `${id}-help` : null, hasError ? `${id}-error` : null].filter(
    (x): x is string => x !== null,
  );
  return ids.length > 0 ? ids.join(" ") : undefined;
}

/**
 * **A SERVER SEARCH AND ITS ANSWER, IN ONE CONTROL.**
 *
 * The clerk types in the field; the panel under it says which of the five
 * states they are in; arrow keys walk the matches and Enter takes one. One
 * gesture, and nothing about the five is lost.
 *
 * ⚠ **TYPING INVALIDATES THE PREVIOUS CHOICE, AND THAT IS A MONEY RULE.**
 * `onChange("")` fires on every keystroke that changes the box. A combobox that
 * keeps a stale id behind a changed search term is how a clerk posts money to
 * the account they were looking at a moment ago — the box says one thing and
 * the request carries another, and the screen looks correct while it happens.
 * It is asserted directly, in both test files, because it is the one property
 * here whose absence a person could not see.
 *
 * ⚠ **THE TERM IS THE HOST'S STATE AND THE DISPLAY IS DERIVED FROM IT.** There
 * is no second copy of the text in this file: what the input shows is the
 * chosen option's label when there is one and the host's term when there is
 * not. A local mirror of a controlled value is how the box and the state come
 * to disagree, which is the same fault as the stale id one level down.
 */
export type RemoteSearchSelectFieldProps = {
  /** The id the FORM keys on — a server field error finds the control by it. */
  id: string;
  /** ≤ 3 words, no sentence (B14 rule 33). The field's name, not the search's. */
  label: string;
  /** What the clerk has typed. The HOST owns it; it is what the search reads. */
  term: string;
  onTermChange: (term: string) => void;
  status: RemoteSearchStatus;
  options: readonly RemoteOption[];
  /** The chosen value — `""` until one is picked. This is what posts. */
  value: string;
  onChange: (value: string) => void;
  words: RemoteSearchWords;
  required?: boolean;
  placeholder?: string;
  error?: string;
  /**
   * BR-SHL-025 — a control that CANNOT ACT, with its reason in `help`. The same
   * opt-in every other field in this kit carries; absent means usable.
   */
  disabled?: boolean;
  /**
   * The panel stays shut until the clerk focuses the box. Added 2026-10-04
   * for a host that holds options BEFORE anything is typed (the assign picker
   * lists everybody, best fit first): without it the list would open over the
   * page on load. Absent on every earlier host, whose options are empty until
   * a search runs, so for them nothing changes.
   */
  startClosed?: boolean;
  /**
   * ⚠ **THE SAME CONTROL, DRAWN INSIDE A TABLE CELL — OPT-IN, ADDED 2026-09-28
   * FOR THE NEW CONNECT REDESIGN, AND IT MOVES NOTHING EXISTING.**
   *
   * Four of the five drawn steps put a server search in a CELL rather than in
   * a form: `Work order` and `Template` on the units table
   * (`step3-units.png`, `step3a-add-row.png`, `step3b-add-work-order.png`),
   * `Charge` on the charges table (`step4-charges.png`) and `Template` on the
   * messages table (`step5-review.png`). A cell has no room for the three
   * things a FIELD is made of — B14 rule 39's LABEL → INPUT → HELPER — and the
   * column header is the only word near it.
   *
   * So `cell` drops the `field` wrapper, the `FieldLabel` and the help
   * paragraph, and the label becomes the input's `aria-label`. **It does NOT
   * drop the five states**: the panel under the box still says too-short,
   * searching, failed or no-match, because those four sentences are the whole
   * reason this component exists rather than a `<select>` (BR-SHL-020,
   * `DEF-3506`), and losing them in a cell would lose them on the screen where
   * a clerk types most.
   *
   * ⚠ **A CELL ERROR IS THE TABLE'S, NOT THIS CONTROL'S.** `EditableTable`'s
   * `cellError` draws the refusal under the cell so every column says it the
   * same way; a `FieldError` here would be a second spelling in the same row.
   * `error` still marks the input `aria-invalid`, which is the part a screen
   * reader needs.
   *
   * **WHY A PROP AND NOT A SECOND COMPONENT.** B14 rule 36: *"compose the kit;
   * where the kit lacks a piece, ADD IT TO THE KIT"*. Absent on both existing
   * call sites, which render byte-for-byte what they rendered before.
   */
} & (
  | {
      cell?: false;
      /** The HELPER, under the input (B14 rule 39). */
      help?: string;
    }
  | {
      cell: true;
      /**
       * ⚠ **NOT ACCEPTED IN A CELL, AND THE TYPE IS WHY RATHER THAN A
       * COMMENT.** A helper line has no room under a nine-column row, so a
       * cell would have to drop it — and a prop a component silently discards
       * is the absence nothing in this repo can see (`DEF-CUS-3653`). Refusing
       * it makes the caller decide where the sentence goes.
       */
      help?: undefined;
    }
);

function hasDetail(option: RemoteOption): boolean {
  return option.kind !== undefined || option.badge !== undefined || option.aside !== undefined || option.alert !== undefined;
}

/** Image 12's row: the name strong, its kind muted, a pill, the advice right. */
function OptionDetail(props: { option: RemoteOption }) {
  const option = props.option;
  return (
    <span className="flex items-baseline justify-between gap-4">
      <span className="flex flex-wrap items-baseline gap-2">
        <span className="font-semibold">{option.label}</span>
        {option.kind !== undefined && <span className="text-sm text-neutral-600">· {option.kind}</span>}
        {option.badge !== undefined && <StatusPill tone="success">{option.badge}</StatusPill>}
        {option.alert !== undefined && (
          <StatusPill tone={option.alertTone ?? "warning"}>
            {option.alert}
          </StatusPill>
        )}
      </span>
      {option.aside !== undefined && option.aside !== "" && (
        <span className="text-right text-sm text-neutral-600">{option.aside}</span>
      )}
    </span>
  );
}

export function RemoteSearchSelectField(props: RemoteSearchSelectFieldProps) {
  const contextError = useFieldError(props.id);
  const error = props.error ?? contextError;

  const [active, setActive] = useState(-1);
  // Escape, a blur and a pick each put the panel away. Typing and focusing
  // bring it back — so the panel follows the clerk rather than the query.
  const [dismissed, setDismissed] = useState(props.startClosed === true);

  const options = props.options;
  const panel = remoteSearchPanel(props.status, options.length, props.term.trim().length > 0);
  const open = panel !== "silent" && !dismissed && props.disabled !== true;

  // ⚠ **THE HIGHLIGHT IS DROPPED WHENEVER THE MATCHES CHANGE, AND THAT IS A
  // MONEY RULE TOO.** An index means nothing across two different lists: keep
  // it and the clerk who pressed ↓↓ before the next answer arrived hits Enter
  // on a row that is not the one they were looking at. The identity is the
  // values, not the length — two lists of five are not the same five.
  const optionKey = options.map((option) => option.value).join("|");
  const lastKey = useRef(optionKey);
  useEffect(() => {
    if (lastKey.current !== optionKey) {
      lastKey.current = optionKey;
      setActive(-1);
    }
  }, [optionKey]);

  const activeOption = open && active >= 0 && active < options.length ? options[active] : null;
  const listId = `${props.id}-listbox`;
  // ⚠ The INDEX, never the value. `aria-activedescendant` puts its target in an
  // `id` attribute, and the values here are database keys (B14 rule 31); an
  // index says the same thing to a screen reader and puts no key in the DOM.
  const optionDomId = (index: number): string => `${props.id}-opt-${index}`;

  function pick(option: RemoteOption): void {
    props.onChange(option.value);
    setActive(-1);
    setDismissed(true);
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      // A keyboard-navigable list, not caret movement.
      event.preventDefault();
      setDismissed(false);
      setActive(stepActiveOption(active, event.key === "ArrowDown" ? 1 : -1, options.length));
    } else if (event.key === "Enter" && activeOption !== null) {
      // Picking an option must not submit the form.
      event.preventDefault();
      pick(activeOption);
    } else if (event.key === "Escape" && open) {
      // IS-10: the FIRST Esc closes the panel only — it must not bubble to
      // ModalShell and close the whole modal. The next Esc does.
      event.stopPropagation();
      setActive(-1);
      setDismissed(true);
    }
    // Tab is deliberately untouched: the browser moves focus, the blur below
    // puts the panel away, and nothing is chosen that the clerk did not choose.
  }

  const sentence: string | null =
    panel === "too-short"
      ? props.words.tooShort
      : panel === "searching"
        ? props.words.searching
        : panel === "failed"
          ? props.words.failed
          : panel === "no-match"
            ? props.words.noMatch
            : null;

  // In a cell the column header is the only word near the box, and a column
  // header does not name a form control to a screen reader — so the label
  // becomes the accessible name instead of a rendered `<label>`.
  const inCell = props.cell === true;

  return (
    // ⚠ NO CLASS IN CELL MODE, AND THAT IS THE RIGHT ANSWER RATHER THAN A
    // SHORTCUT. `.field` styles only `> label`, and there is no label here;
    // `.search-select` inside already carries the `position: relative` the
    // panel needs. Inventing `.search-select-cell` would add a class to a
    // stylesheet, which B14 rule 21 forbids, and writing it as a utility would
    // declare a rule that does nothing.
    <div className={inCell ? undefined : "field"} data-search-cell={inCell ? "" : undefined}>
      {!inCell && (
        <FieldLabel htmlFor={props.id} label={props.label} required={props.required === true} />
      )}
      <div className="search-select">
        <input
          id={props.id}
          type="text"
          aria-label={inCell ? props.label : undefined}
          // BR-SHL-033: the ARIA combobox pattern over a listbox.
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={activeOption !== null ? optionDomId(active) : undefined}
          // DEF-TEN-4478: the browser's own fill writes the DOM and fires no
          // React event, and this box's text is a lookup term, never a fact
          // about the person typing it.
          autoComplete="off"
          className={fieldInputClass(error !== undefined)}
          // The chosen row's label at rest, the clerk's term while searching.
          // One value, derived — never a second copy of the text.
          value={options.find((option) => option.value === props.value)?.label ?? props.term}
          placeholder={props.placeholder}
          disabled={props.disabled === true}
          aria-required={props.required === true ? true : undefined}
          aria-invalid={error !== undefined ? true : undefined}
          // ⚠ BOTH FLAGS ARE GATED ON `inCell`, because a cell renders neither
          // the helper nor the error and an `aria-describedby` pointing at an
          // id that is not in the document is a name a screen reader cannot
          // resolve — worse than no name at all.
          aria-describedby={fieldDescribedBy(
            props.id,
            !inCell && props.help !== undefined,
            !inCell && error !== undefined,
          )}
          onChange={(event) => {
            props.onTermChange(event.target.value);
            // ⚠ **TYPING INVALIDATES THE PREVIOUS CHOICE.** See this
            // component's own note: a stale id behind a changed box is money on
            // the wrong account.
            props.onChange("");
            setDismissed(false);
          }}
          onFocus={() => setDismissed(false)}
          // DEF-WRK-9608 — after a pick or an Esc the focus never leaves the
          // box, so a click must reopen the list as a focus would.
          onClick={() => setDismissed(false)}
          onBlur={() => setDismissed(true)}
          onKeyDown={handleKeyDown}
        />
        {/* The panel stays in the DOM (hidden when closed) so the combobox
            wiring is inspectable and testable without a live browser — the
            spelling `SearchSelectField` already uses. `data-panel-state` is the
            one machine-readable name for which of the six it is in; it is an
            attribute and not a word on screen (B14 rule 33: RATIONALE is zero
            words on screen, and the state's NAME is rationale). */}
        <div className="search-select-list" data-panel-state={panel} hidden={!open}>
          <ul role="listbox" id={listId} aria-label={props.label} className="m-0 list-none p-0">
            {options.map((option, index) => (
              <li
                key={option.value}
                id={optionDomId(index)}
                role="option"
                aria-selected={option.value === props.value}
                // A WHOLE LITERAL PER BRANCH, never a stem with an
                // interpolation glued to it: this file is in the Route B
                // ledger, and `routeBUtilities.test.ts` refuses a name that
                // only exists at runtime because Tailwind's scanner cannot see
                // one. Both names are `FormModal.css`'s.
                className={index === active ? "search-select-opt active" : "search-select-opt"}
                // Keep focus in the input so onBlur cannot swallow the click.
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => pick(option)}
                data-option-detail={hasDetail(option) ? "" : undefined}
              >
                {hasDetail(option) ? <OptionDetail option={option} /> : option.label}
              </li>
            ))}
          </ul>
          {sentence !== null &&
            (panel === "failed" ? (
              /* ⚠ **A REFUSAL, AND THE ONLY ONE OF THE FOUR.** BR-SHL-020: THE
                 PLATFORM failed, which is the sentence support can act on. It
                 keeps the red strip it had as a separate field, so the
                 difference from the note below is visible and not only
                 readable. `role="alert"` is why it is also AUDIBLE. */
              <RefusalStrip role="alert" data-panel-message={panel}>
                {sentence}
              </RefusalStrip>
            ) : (
              /* ⛔ NOT A REFUSAL. Too short, still looking, or "no record of
                 yours looks like that" — all three are facts the clerk can act
                 on by typing, and none of them is the product failing. */
              <Note className="px-3 py-2" role="status" data-panel-message={panel}>
                {sentence}
              </Note>
            ))}
        </div>
      </div>
      {/* ⚠ **A CELL HAS NEITHER, AND BOTH ABSENCES ARE DELIBERATE.** B14 rule
          39's helper line under a nine-column row would be a paragraph inside
          a 120px cell, and the refusal belongs to `EditableTable`'s `cellError`
          so every column of the row says it the same way. The input above
          still carries `aria-invalid` and `aria-describedby`, so nothing a
          screen reader needs is dropped — only the two things a cell has no
          room to draw. */}
      {!inCell && props.help !== undefined && (
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {!inCell && error !== undefined && (
        <FieldError id={`${props.id}-error`} message={error} />
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-PAY-6319 (PO on the Raise-a-refund form, 2026-09-23 — "why to button … user has to do two clicks", then "fix it") · DEF-3506 (the five states, and why they exist) · B14 rules 8, 10, 21, 31, 33, 36, 39, 43 · IS-3 · IS-10 · BR-SHL-012 · BR-SHL-020 · BR-SHL-025 · BR-SHL-033
// generated: 2026-09-23 by lane ACCOUNT-COMBO
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: (1) `fieldInputClass` and `fieldDescribedBy` are deliberate second copies of two private `FormModal.tsx` helpers — that file held 245 uncommitted lines of a sibling lane when this was written, and importing them would have required committing it (hard-won law 11, mechanism five). Named in a docstring with the condition for deleting them · (2) the four sentences are the HOST's, not this file's, so no catalogue key moved in the commit that replaced the two-field picker
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
