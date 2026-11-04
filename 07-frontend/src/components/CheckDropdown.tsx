// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — the New tax or fee form's Services and
//           Customer classes (images 05 and 06 of
//           `05-prototype/taxes-fees-2026-10-03/images/`).
// Rules:    PO ruling 2026-10-03 (README point 1): *"Services: only the services
//           this utility has switched on, in one dropdown with 'All services'
//           first. Customer classes: one dropdown, 'Every customer class'
//           first."* · B14 rule 36 (where the kit lacks a piece, add it to the
//           kit) · B14 rule 9 (never a WALL of checkboxes — this list is shut
//           until opened, and shows what was chosen as one line)
// ───────────────────────────────────────────────────────
//
// A MULTIPLE CHOICE IN ONE BOX: the chosen values read as one line, and the
// list opens with a tick per option and an "all" row first.
//
// ⚠ **AN EMPTY SELECTION MEANS ALL, AND THAT IS THE SERVER'S MEANING TOO.** A
// tax with `applies_to_services: []` applies to every service; ticking the
// "all" row therefore CLEARS the list rather than ticking every row, so a
// service the utility switches on next year is covered without an edit.
//
// ⚠ **THE FIRST ROW IS TICKED ONLY WHEN NOTHING ELSE IS.** Image 05 draws
// *All services* unticked beside three ticked services, and image 06 draws
// *Every customer class* ticked alone.
//
// ⚠ **`mode="pick"` — A LIST WHERE EMPTY MEANS NOTHING CHOSEN (CR-166-BRC10
// task 4, B14 rule 36, opt-in).** The New discount form's *Specific services*
// and *Named charge codes* are the opposite of the tax lists: an empty list is
// an UNFINISHED form and is refused (`CR-091-BRC01`, PO 2026-09-10 — *"All
// services"* is its own choice there). So that mode draws NO "all" row and the
// closed box reads its `placeholder` when nothing is ticked. Absent, the
// component renders byte-for-byte what the tax form renders today.
//
// ⚠ **`mode="every"` — A LIST THAT STARTS WITH EVERYTHING TICKED (CR-176-BRC10
// task 7, B14 rule 36, opt-in).** Add units' *Services* are the building's
// services, ALL ticked to start, and the clerk unticks what a unit will not take
// (PO 2026-10-09; image 05 of `05-prototype/add-units-redesign-2026-10-09/`
// draws the "all" row ticked WITH every service ticked under it). So here the
// list holds every chosen value — never `[]` for all — the "all" row is ticked
// when every option is, and pressing it ticks every option or, when all are
// ticked, none. The closed box reads `allLabel` with all ticked and
// `placeholder` with none. Absent, nothing above moves.
import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";

import { FieldLabel, fieldErrorToShow, useFieldError } from "./FormModal";
import { FieldError, INVALID_INPUT_CLASS } from "./StateFrame";

export interface CheckDropdownOption {
  value: string;
  label: string;
  /** A small mark drawn before the label — the service's colour square. */
  marker?: ReactNode;
}

export interface CheckDropdownProps {
  id: string;
  label: string;
  /** The "all" row's words — *All services*, *Every customer class*. Unused
   *  in `mode="pick"`. */
  allLabel: string;
  options: readonly CheckDropdownOption[];
  /** [] means ALL — or, in `mode="pick"`, nothing chosen yet. */
  selected: readonly string[];
  /** `all` (default): the first row is "all" and empty means all. `pick`: no
   *  "all" row; empty means nothing chosen, and the box reads `placeholder`. */
  mode?: "all" | "pick" | "every";
  /** What the closed box reads with nothing ticked, in `mode="pick"`. */
  placeholder?: string;
  onChange: (next: string[]) => void;
  help?: string;
  error?: string;
  disabled?: boolean;
  required?: boolean;
}

/** The one line the closed box reads: the chosen labels in list order, or the
 *  "all" words. Exported so the summary panel and Review say the same thing. */
export function checkDropdownSummary(
  options: readonly CheckDropdownOption[],
  selected: readonly string[],
  allLabel: string,
): string {
  if (selected.length === 0) {
    return allLabel;
  }
  const chosen = options.filter((option) => selected.includes(option.value)).map((option) => option.label);
  // A value the list no longer offers (a service switched off since) is still
  // shown, by its code, rather than silently dropped from the line.
  const unknown = selected.filter((value) => !options.some((option) => option.value === value));
  return [...chosen, ...unknown].join(", ");
}

/** Tick or untick one option. Ticking the last remaining one off returns to
 *  ALL, which is what an empty list means. */
export function toggleCheckDropdown(selected: readonly string[], value: string): string[] {
  return selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value];
}

const ROW =
  "flex w-full cursor-pointer items-center gap-3 border-b border-divider px-4 py-3 " +
  "font-heading text-base font-semibold last:border-b-0 hover:bg-neutral-100";

export function CheckDropdown(props: CheckDropdownProps) {
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement | null>(null);
  const listId = useId();
  const contextError = useFieldError(props.id);
  const error = fieldErrorToShow(props.error, contextError);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    function onPointer(event: MouseEvent): void {
      if (wrapper.current !== null && !wrapper.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const pick = props.mode === "pick";
  const every = props.mode === "every";
  const allTicked =
    every && props.options.length > 0 && props.options.every((option) => props.selected.includes(option.value));
  const summary = every
    ? allTicked
      ? props.allLabel
      : checkDropdownSummary(props.options, props.selected, props.placeholder ?? "")
    : checkDropdownSummary(
        props.options,
        props.selected,
        pick ? (props.placeholder ?? "") : props.allLabel,
      );
  const describedBy = [props.help !== undefined ? `${props.id}-help` : null, error !== undefined ? `${props.id}-error` : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="field" ref={wrapper} data-check-dropdown={props.id}>
      <FieldLabel htmlFor={props.id} label={props.label} required={props.required === true} />
      <div className="relative">
        <button
          id={props.id}
          type="button"
          className={`input flex items-center justify-between gap-2 text-left ${error !== undefined ? INVALID_INPUT_CLASS : ""}`}
          aria-haspopup="true"
          aria-expanded={open}
          aria-controls={listId}
          aria-invalid={error !== undefined ? true : undefined}
          aria-describedby={describedBy === "" ? undefined : describedBy}
          disabled={props.disabled === true}
          onClick={() => setOpen((was) => !was)}
        >
          <span className="min-w-0 truncate">{summary}</span>
          <span aria-hidden="true" className="flex-none text-xs">
            ▾
          </span>
        </button>
        {open && (
          <div
            id={listId}
            role="group"
            aria-label={props.label}
            className="absolute left-0 right-0 top-full z-40 border border-text bg-surface shadow-md"
            data-check-dropdown-list=""
          >
            {!pick && (
              <label className={`${ROW} bg-neutral-100`}>
                <input
                  type="checkbox"
                  checked={every ? allTicked : props.selected.length === 0}
                  onChange={() =>
                    props.onChange(
                      every && !allTicked ? props.options.map((option) => option.value) : [],
                    )
                  }
                />
                {props.allLabel}
              </label>
            )}
            {props.options.map((option) => (
              <label key={option.value} className={`${ROW} bg-surface`}>
                <input
                  type="checkbox"
                  checked={props.selected.includes(option.value)}
                  onChange={() => props.onChange(toggleCheckDropdown(props.selected, option.value))}
                />
                {option.marker}
                {option.label}
              </label>
            ))}
          </div>
        )}
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
