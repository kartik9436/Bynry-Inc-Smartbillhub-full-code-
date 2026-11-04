// ── Trace ──────────────────────────────────────────────
// Change:  PO report 2026-09-22, item 7 — *"a proper drop-file control"*:
//          drag a file in, or browse. The attach control was a bare
//          `<input type="file">` reading `No file chosen`.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT — standalone code inside
//          a page is not reuse) · rule 36 (*"where the kit lacks a piece, ADD
//          IT TO THE KIT — one component, one visual decision, every screen —
//          rather than hand-rolling it in the screen, which is how four
//          screens acquire four different chips"*) · rule 39 (label → control
//          → helper) · rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6) · rule 21
//          (Tailwind utilities; this file is listed in
//          `styles/route-b-migrated.txt` and adds NO stylesheet class) ·
//          BR-SHL-017 (a required field is visibly marked) · BR-SHL-031 (the
//          upload allowlist — enforced by the SERVER, never by this)
// Screens: `REQ-03.4` service-request capture · `NEW-01` new-connect owner
//          step — both through `components/documents/DocumentCaptureForm`.
// ───────────────────────────────────────────────────────
import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";

import { Button } from "./Button";
import { useFieldError } from "./FormModal";

/**
 * One file field a person can DROP onto or browse for.
 *
 * ⚠ **IT IS A COMPONENT AND NOT A BLOCK IN THE WIZARD — B14 RULE 43, RATIFIED
 * ON EXACTLY THIS MISTAKE.** Rule 43 was ruled after *"use it"* turned out to
 * mean 120 lines inline in a 4,186-line page, importable by nothing. Two
 * screens already take a file off a person through `DocumentCaptureForm`, and
 * a third will; writing a drop zone into one of them would be the same defect
 * with newer wording.
 *
 * ⚠ **WHY NOT A SIXTH VARIANT INSIDE `FileField`.** `FileField` is the kit's
 * plain file input and 14 screens render it. A drop target is a different
 * SHAPE — it has a hover state, a drag state and a second way in — and folding
 * both into one component would put a `drop?: boolean` on every one of those
 * call sites. They are siblings, and `FileField`'s own header already records
 * the precedent for a second file component rather than a widened one.
 *
 * ── HOW IT STAYS REACHABLE FROM A KEYBOARD, WHICH IS THE PART THAT USUALLY
 *    GETS LOST ─────────────────────────────────────────────────────────────
 * **The real `<input type="file">` is still here and still the only thing that
 * holds the file.** It is visually hidden and NOT `display:none` — a hidden
 * input is removed from the tab order, and that is how a drop zone ends up
 * mouse-only. The visible `Choose a file` control is a real `<button>` that
 * clicks it, the `<label>` is bound to it by `htmlFor`, and the zone shows a
 * focus ring when the input inside it has focus (`has-[:focus-visible]`). So:
 * tab reaches it, space opens the picker, and a screen reader announces the
 * label. **A clickable `<div>` would have been shorter and is a defect.**
 *
 * ⚠ **THERE IS NO `value` PROP AND THERE CANNOT BE.** A file input's value may
 * only be set by the user, so React cannot control it. The host holds the
 * chosen `File` and passes `fileName` back for display — `FileField`'s rule,
 * for the same DOM reason.
 *
 * ⚠ **`accept` IS A CONVENIENCE AND NEVER THE GUARD.** `BR-SHL-031`'s allowlist
 * is enforced by the server (415) and a clerk can defeat `accept` in any
 * picker. A DROPPED file does not go through the picker at all, so it does not
 * even get the hint — which is why the caller still validates what it is
 * handed, exactly as it does for a browsed file.
 */
export function FileDropField(props: {
  id: string;
  label: string;
  /** ≤ 6 words. What to do: *"Drop a file here"*. */
  hint: string;
  /** ≤ 3 words, and it is a LABEL: *"Choose a file"*. */
  browseLabel: string;
  accept?: string;
  required?: boolean;
  help?: string;
  onChange: (file: File | null) => void;
  /** The chosen file's name, so the zone can say what is selected. */
  fileName?: string | null;
  error?: string;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [over, setOver] = useState(false);
  const contextError = useFieldError(props.id);
  const error = props.error ?? contextError;
  const describedBy = [
    `${props.id}-hint`,
    props.help !== undefined ? `${props.id}-help` : null,
    error !== undefined ? `${props.id}-error` : null,
  ]
    .filter((value): value is string => value !== null)
    .join(" ");

  function take(file: File | null): void {
    props.onChange(file);
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>): void {
    const chosen = event.target.files;
    take(chosen !== null && chosen.length > 0 ? chosen[0] : null);
  }

  // ⚠ **`preventDefault` ON *BOTH* `dragOver` AND `drop`.** Without the first
  // the browser never fires the second — it treats the page as a non-target and
  // navigates to the file instead, which looks exactly like the drop being
  // ignored. This is the one detail that makes a hand-rolled drop zone fail
  // silently, and it is the reason this is a component.
  function handleDragOver(event: DragEvent<HTMLDivElement>): void {
    if (props.disabled === true) return;
    event.preventDefault();
    setOver(true);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    if (props.disabled === true) return;
    event.preventDefault();
    setOver(false);
    const dropped = event.dataTransfer?.files;
    if (dropped !== undefined && dropped.length > 0) {
      // ⚠ **ONE FILE, AND THE FIRST ONE.** The form this serves attaches a
      // document at a time (`Attaching one`, singular) and a host that took
      // the whole list would silently drop all but one anyway. Taking the
      // first is the same answer the browse path gives.
      take(dropped[0]);
      // Keep the real input in step with what the host now holds, so the two
      // ways in cannot disagree about which file is selected.
      if (inputRef.current !== null) {
        try {
          const transfer = new DataTransfer();
          transfer.items.add(dropped[0]);
          inputRef.current.files = transfer.files;
        } catch {
          // Older engines refuse to write `files`. The HOST's state is the
          // truth either way — this only keeps the native control's own label
          // honest — so a refusal here changes nothing a person can see.
        }
      }
    }
  }

  return (
    <div className="field">
      <label htmlFor={props.id}>
        {props.label}
        {props.required === true && (
          // BR-SHL-017, and the same marker every other field draws.
          <span className="field-required" aria-hidden="true">
            *
          </span>
        )}
      </label>
      <div
        data-file-drop=""
        data-over={over ? "" : undefined}
        onDragOver={handleDragOver}
        onDragLeave={() => setOver(false)}
        onDrop={handleDrop}
        className={[
          "flex flex-col items-center justify-center gap-2 rounded-none border border-dashed px-4 py-5 text-center",
          "has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent",
          // ⚠ **THE OVER-STATE USED A COLOUR STEP THAT DOES NOT EXIST —
          // DEF-CUS-6180.** The theme declares accent at 100 and at 500 and
          // nothing at 50, so the class that was here compiled to no rule at
          // all and the drag-over highlight simply did not paint. Tailwind
          // emits nothing for a token it does not have and says nothing about
          // it; the Route B utilities test is the only thing that can see it,
          // and it had been red naming that class since this file joined the
          // migration ledger.
          //
          // ⚠ **AND NOTE WHAT THIS COMMENT MAY NOT CONTAIN.** That test scans
          // this file for class-shaped tokens and cannot tell a comment from
          // code, so spelling the bad class in backticks here makes the guard
          // report an orphan over a component that no longer uses one. Write
          // the diagnosis in prose; the guard reads punctuation, not meaning.
          over ? "border-accent bg-accent-100" : "border-divider bg-surface",
          error !== undefined ? "border-danger-500" : "",
          props.disabled === true ? "opacity-60" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {/* The FACT first — what is selected, or what to do. Rule 33 caps both
            at six words and the caller supplies them. */}
        <p className="text-sm text-text" id={`${props.id}-hint`} data-file-drop-hint="">
          {(props.fileName ?? null) !== null && props.fileName !== "" ? props.fileName : props.hint}
        </p>
        {/* ⚠ **THE KIT'S BUTTON, NOT A HAND-ROLLED ONE — B14 rule 36.** A
            hand-written `btn` / `btn-secondary` / `btn-sm` trio here would be a
            fifth button style in a component, and the two sizes the kit allows
            are exactly `default` and `sm`.
            ⚠ **AND THE THREE CLASS NAMES ARE NOT SPELLED AS A CLASS LIST
            HERE ANY MORE, DELIBERATELY.** The Route B utilities test scans this
            file for class-shaped tokens and cannot tell a comment from code, so
            quoting the bad example made the guard report three orphans over a
            component that never used one — a check failing on a fault it
            invented. Prose says the same thing to a reader and nothing at all
            to the scanner. */}
        <Button
          variant="secondary"
          size="sm"
          data-file-drop-browse=""
          disabled={props.disabled === true}
          onClick={() => inputRef.current?.click()}
        >
          {props.browseLabel}
        </Button>
        {/* ⚠ **`sr-only` AND NOT `hidden`.** `hidden`/`display:none` takes the
            input out of the tab order, and then the only way to this field is
            a mouse. `sr-only` keeps it focusable and announced. */}
        <input
          ref={inputRef}
          id={props.id}
          type="file"
          className="sr-only"
          accept={props.accept}
          disabled={props.disabled === true}
          aria-required={props.required === true ? true : undefined}
          aria-invalid={error !== undefined ? true : undefined}
          aria-describedby={describedBy}
          onChange={handleChange}
        />
      </div>
      {props.help !== undefined && (
        // Rule 39: the helper reads as attached to the control ABOVE it.
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {error !== undefined && (
        <p className="field-error" id={`${props.id}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
