// ── Trace ──────────────────────────────────────────────
// Design:  04-docs/05-modules/07-billing/11-one-time-bill-redesign.md §1 — PO
//          2026-09-30, verbatim: *"this si searchable dropdown"*
// Drawing: 05-prototype/one-time-bill-2026-09-30/1440-02-Interim-1-account-dropdown-open.png
//          (inventory.md §2.1)
// Plan:    12-one-time-bill-build-plan.md F4 — "a kit component"
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT) · rule 36 (compose the
//          kit) · rule 31 (no database id on screen) · rule 21 (utilities only;
//          this file is on route-b-migrated.txt) · IS-3 (server search, from two
//          characters) · IS-10 (the first Esc closes the list)
// Tests:   src/components/AccountCombobox.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * **FIND AN ACCOUNT BY TYPING, AND TELL TWO ALIKE NAMES APART.**
 *
 * The drawing's account picker is a searchable dropdown whose options carry
 * FOUR facts, not one label: the name (with the typed text picked out), the
 * account's status as a pill, and a second line of account number · address.
 * Two customers called *Maria Alvarez* are told apart only by that second line,
 * so it is not decoration — an option without it is one a clerk can pick
 * without knowing whose bill they are raising.
 *
 * ⚠ **IT IS BUILT ON `RemoteSearchSelectField`'s MACHINERY, NOT BESIDE IT.**
 * The five panel states (too short · searching · failed · no match · matches)
 * are that component's `remoteSearchPanel`, imported and not re-derived, and
 * the keyboard walk is the kit's own `stepActiveOption`. What this adds is the
 * richer option, which `RemoteSearchSelectField`'s one-string `label` cannot
 * carry. Widening that component's option type would have moved its four live
 * hosts, which rule 36 says an addition must not do.
 *
 * ⚠ **TYPING INVALIDATES THE CHOICE** — the same money rule its sibling
 * documents: a stale id behind a changed search box raises a bill on the
 * account the clerk was looking at a moment ago.
 */
import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";

import { stepActiveOption, useFieldError, FieldLabel } from "./FormModal";
import { remoteSearchPanel } from "./RemoteSearchSelectField";
import type { RemoteSearchStatus, RemoteSearchWords } from "./RemoteSearchSelectField";
import { FieldError, INVALID_INPUT_CLASS } from "./StateFrame";
import { StatusPill } from "./StatusPill";
import type { StatusTone } from "./StatusPill";
import { RefusalStrip } from "./Surfaces";
import { Note } from "./TextBits";

/** One account as the dropdown draws it. `value` posts; nothing else here is
 *  ever an id (B14 rule 31). */
export interface AccountComboboxOption {
  value: string;
  /** The first line — the customer's name, or the host's words for "no name". */
  name: string;
  /** The second line — `AC-2026-00042 · 1408 Elm St · Unit A`. */
  detail: string;
  status: { label: string; tone: StatusTone };
}

export interface AccountComboboxProps {
  id: string;
  /** ≤ 3 words (B14 rule 33). */
  label: string;
  term: string;
  onTermChange: (term: string) => void;
  status: RemoteSearchStatus;
  options: readonly AccountComboboxOption[];
  /** The chosen account's id — `""` until one is picked. */
  value: string;
  /** What the box shows once an account is chosen (the host keeps it, because
   *  the option list moves on as soon as the term does). */
  selectedName: string;
  onChange: (option: AccountComboboxOption | null) => void;
  words: RemoteSearchWords;
  required?: boolean;
  help?: string;
  placeholder?: string;
  error?: string;
}

/**
 * The name with the typed term picked out, as drawn (`Maria **Alv**arez`).
 * Case-insensitive, first match only; a term that is not in the name (it
 * matched the number or the address) leaves the name plain.
 */
export function highlightMatch(name: string, term: string): ReactNode {
  const needle = term.trim();
  if (needle === "") return name;
  const at = name.toLowerCase().indexOf(needle.toLowerCase());
  if (at < 0) return name;
  return (
    <>
      {name.slice(0, at)}
      <span className="text-accent-700" data-match="">
        {name.slice(at, at + needle.length)}
      </span>
      {name.slice(at + needle.length)}
    </>
  );
}

export function AccountCombobox(props: AccountComboboxProps) {
  const contextError = useFieldError(props.id);
  const error = props.error ?? contextError;
  const [active, setActive] = useState(-1);
  const [dismissed, setDismissed] = useState(true);

  const options = props.options;
  const choosing = props.value === "";
  const panel = remoteSearchPanel(props.status, options.length, props.term.trim().length > 0);
  const open = choosing && panel !== "silent" && !dismissed;

  // A highlight means nothing across two different lists — drop it when the
  // matches change (the sibling component's money rule, one level down).
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
  const optionDomId = (index: number): string => `${props.id}-opt-${index}`;

  function pick(option: AccountComboboxOption): void {
    props.onChange(option);
    setActive(-1);
    setDismissed(true);
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setDismissed(false);
      setActive(stepActiveOption(active, event.key === "ArrowDown" ? 1 : -1, options.length));
    } else if (event.key === "Enter" && activeOption !== null) {
      event.preventDefault();
      pick(activeOption);
    } else if (event.key === "Escape" && open) {
      event.stopPropagation();
      setActive(-1);
      setDismissed(true);
    }
  }

  const sentence =
    panel === "too-short"
      ? props.words.tooShort
      : panel === "searching"
        ? props.words.searching
        : panel === "failed"
          ? props.words.failed
          : panel === "no-match"
            ? props.words.noMatch
            : null;

  const described = [
    props.help !== undefined ? `${props.id}-help` : null,
    error !== undefined ? `${props.id}-error` : null,
  ].filter((part): part is string => part !== null);

  return (
    <div className="field" data-account-combobox="">
      <FieldLabel htmlFor={props.id} label={props.label} required={props.required === true} />
      <div className="search-select">
        <input
          id={props.id}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={activeOption !== null ? optionDomId(active) : undefined}
          autoComplete="off"
          className={error !== undefined ? `input ${INVALID_INPUT_CLASS} pr-8` : "input pr-8"}
          value={choosing ? props.term : props.selectedName}
          placeholder={props.placeholder}
          aria-required={props.required === true ? true : undefined}
          aria-invalid={error !== undefined ? true : undefined}
          aria-describedby={described.length > 0 ? described.join(" ") : undefined}
          onChange={(event) => {
            props.onTermChange(event.target.value);
            // TYPING INVALIDATES THE CHOICE — see the file's own note.
            if (!choosing) props.onChange(null);
            setDismissed(false);
          }}
          onFocus={() => setDismissed(false)}
          onBlur={() => setDismissed(true)}
          onKeyDown={handleKeyDown}
        />
        {/* The drawn caret. Decoration only: the input is the control. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-neutral-700"
        >
          ▾
        </span>
        <div className="search-select-list" data-panel-state={panel} hidden={!open}>
          <ul role="listbox" id={listId} aria-label={props.label} className="m-0 list-none p-0">
            {options.map((option, index) => (
              <li
                key={option.value}
                id={optionDomId(index)}
                role="option"
                aria-selected={index === active}
                className={
                  index === active
                    ? "search-select-opt active border-b border-divider bg-accent-100"
                    : "search-select-opt border-b border-divider"
                }
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => pick(option)}
              >
                <span className="flex items-start justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block font-heading font-semibold text-text">
                      {highlightMatch(option.name, props.term)}
                    </span>
                    <span className="block text-sm text-neutral-700">{option.detail}</span>
                  </span>
                  <StatusPill tone={option.status.tone}>{option.status.label}</StatusPill>
                </span>
              </li>
            ))}
          </ul>
          {sentence !== null &&
            (panel === "failed" ? (
              <RefusalStrip role="alert" data-panel-message={panel}>
                {sentence}
              </RefusalStrip>
            ) : (
              <Note className="px-3 py-2" role="status" data-panel-message={panel}>
                {sentence}
              </Note>
            ))}
        </div>
      </div>
      {props.help !== undefined && (
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {error !== undefined && <FieldError id={`${props.id}-error`} message={error} />}
    </div>
  );
}

export default AccountCombobox;
