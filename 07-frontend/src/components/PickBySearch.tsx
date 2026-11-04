// ── Trace ──────────────────────────────────────────────
// Change:   CR-176-BRC10 — the Add units redesign (`DEF-MET-10035`), task 6.
// Ruling:   decision log 2026-10-09, *"PO GO — BUILD THE ADD-UNITS REDESIGN"*,
//           rule (4): *"a building is picked by search and confirmed with Use
//           this building, then ✓ Selected / Change building — the pattern
//           ruled for Owner on Add a premise"*.
// Drawing:  05-prototype/add-units-redesign-2026-10-09/images/01–04.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT) · rule 36 (the kit) ·
//           rule 21 (Tailwind; on route-b-migrated.txt) · rule 31 (no
//           database id on screen) · rule 33 (labels, no rationale) · IS-3
//           (search debounced 300 ms, minimum 2 characters)
// ───────────────────────────────────────────────────────
//
// SEARCH, LOOK, THEN SAY "USE THIS" — ONE CONTROL FOR EVERY PICK THAT MUST BE
// CONFIRMED BEFORE IT COUNTS.
//
// Three states, and the drawing draws each:
//   1. **searching** — a box and *Find*; matches drop down under the box;
//   2. **looking** — one match opened as a READ-ONLY card with a *Use this …*
//      button, so a wrong building is seen before anything is added to it;
//   3. **chosen** — the same card with *✓ Selected* and *Change …*.
//
// ⚠ **IT NEVER PICKS FOR THE CLERK.** One match still opens as a card to be
// confirmed — the posture `MasterAccountSearch` takes for owners, because two
// similar addresses are two buildings and adding units to the wrong one is a
// set of rows that bill.
//
// ⚠ **THE CARD'S BODY IS THE CALLER'S.** What a building, an owner or an
// account says about itself differs; the frame — the header line, the
// *Use* / *✓ Selected* / *Change* actions, the search above — is shared, so the
// screens that use it cannot drift apart. Add a premise's Owner uses the same
// shape (decision log 2026-10-09) and can converge onto this component.
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { Button } from "./Button";
import { FieldLabel, fieldErrorToShow, useFieldError } from "./FormModal";
import { createSearchDebouncer } from "./searchDebounce";
import { FieldError, INVALID_INPUT_CLASS } from "./StateFrame";
import { InlineLink } from "./Surfaces";

/** One match: what the list and the card header print. Never an id on screen. */
export interface PickCandidate {
  /** The record's id — posted back, never drawn (B14 rule 31). */
  id: string;
  /** The line a clerk recognises: `101 Silver Creek Rd`. */
  title: string;
  /** The second line: `P-00001 · Silver Creek, TX 78611`. */
  meta?: string;
}

export interface PickBySearchProps {
  id: string;
  label: string;
  required?: boolean;
  placeholder: string;
  findLabel: string;
  /** What the list says when the search found nothing. */
  noMatchLabel: string;
  /** Ask the server. Called with at least two characters, or on *Find*. */
  search: (q: string) => Promise<PickCandidate[]>;
  /** The confirmed pick, or `null`. The caller owns it. */
  chosen: PickCandidate | null;
  onUse: (candidate: PickCandidate) => void;
  onChange: () => void;
  /** Called on any search activity — typing, Find, opening a match — so the
   *  caller can lift a refusal the clerk is already answering. */
  onActivity?: () => void;
  /** The read-only body of the card, for the match being looked at or chosen. */
  renderCard: (candidate: PickCandidate) => ReactNode;
  useLabel: string;
  selectedLabel: string;
  changeLabel: string;
  error?: string;
}

/** The text the box shows once a pick is confirmed: `title · first meta part`. */
export function pickBoxText(candidate: PickCandidate): string {
  const first = (candidate.meta ?? "").split(" · ")[0]?.trim() ?? "";
  return first === "" ? candidate.title : `${candidate.title} · ${first}`;
}

export function PickBySearch(props: PickBySearchProps) {
  const [term, setTerm] = useState(props.chosen === null ? "" : pickBoxText(props.chosen));
  const [matches, setMatches] = useState<PickCandidate[] | null>(null);
  const [looking, setLooking] = useState<PickCandidate | null>(null);
  const seq = useRef(0);
  const contextError = useFieldError(props.id);
  const error = fieldErrorToShow(props.error, contextError);

  function ask(q: string, openSingle: boolean): void {
    props.onActivity?.();
    if (q === "") {
      setMatches(null);
      return;
    }
    const mine = ++seq.current;
    void props
      .search(q)
      .then((rows) => {
        if (mine !== seq.current) return;
        if (openSingle && rows.length === 1) {
          setMatches(null);
          setLooking(rows[0]);
          setTerm(pickBoxText(rows[0]));
          return;
        }
        setMatches(rows);
      })
      .catch(() => {
        if (mine === seq.current) setMatches([]);
      });
  }

  // The debouncer is made once; it calls the CURRENT `ask` through a ref, so a
  // re-render never leaves it holding a stale `props.search`.
  const askRef = useRef(ask);
  askRef.current = ask;
  const debounced = useMemo(() => createSearchDebouncer((q) => askRef.current(q, false)), []);
  useEffect(() => () => debounced.clear(), [debounced]);

  // A pick made elsewhere (a `?premises=` link) shows in the box.
  const chosenText = props.chosen === null ? null : pickBoxText(props.chosen);
  useEffect(() => {
    if (chosenText !== null) {
      setTerm(chosenText);
      setMatches(null);
      setLooking(null);
    }
  }, [chosenText]);

  const shown = props.chosen ?? looking;
  const isChosen = props.chosen !== null;

  return (
    <div className="field" data-pick-by-search={props.id}>
      <FieldLabel htmlFor={props.id} label={props.label} required={props.required === true} />
      <div className="relative">
        <div className="flex gap-2">
          <input
            id={props.id}
            type="search"
            autoComplete="off"
            className={`input min-w-0 flex-1 ${error !== undefined ? INVALID_INPUT_CLASS : ""}`}
            value={term}
            placeholder={props.placeholder}
            readOnly={isChosen}
            aria-required={props.required === true ? true : undefined}
            aria-invalid={error !== undefined ? true : undefined}
            aria-describedby={error !== undefined ? `${props.id}-error` : undefined}
            onChange={(event) => {
              const next = event.target.value;
              setTerm(next);
              setLooking(null);
              debounced.type(next.trim());
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                debounced.clear();
                ask(term.trim(), true);
              }
            }}
          />
          <Button
            variant="secondary"
            disabled={isChosen}
            onClick={() => {
              debounced.clear();
              ask(term.trim(), true);
            }}
          >
            {props.findLabel}
          </Button>
        </div>
        {!isChosen && looking === null && matches !== null && (
          <ul
            role="listbox"
            aria-label={props.label}
            className="absolute left-0 right-0 top-full z-40 m-0 list-none border border-text bg-surface p-0 shadow-md"
            data-pick-matches=""
          >
            {matches.length === 0 ? (
              <li className="px-4 py-3 text-neutral-700">{props.noMatchLabel}</li>
            ) : (
              matches.map((candidate) => (
                <li key={candidate.id} role="option" aria-selected={false}>
                  <button
                    type="button"
                    className="flex w-full items-baseline justify-between gap-3 border-b border-divider bg-surface px-4 py-3 text-left last:border-b-0 hover:bg-neutral-100"
                    onClick={() => {
                      setMatches(null);
                      setLooking(candidate);
                      setTerm(pickBoxText(candidate));
                    }}
                  >
                    <span>{candidate.title}</span>
                    {candidate.meta !== undefined && (
                      <span className="text-sm text-neutral-700">{candidate.meta}</span>
                    )}
                  </button>
                </li>
              ))
            )}
          </ul>
        )}
      </div>
      {error !== undefined && <FieldError id={`${props.id}-error`} message={error} />}
      {shown !== null && (
        <div className="mt-4 border border-divider bg-neutral-100 p-4" data-pick-card={isChosen ? "chosen" : "looking"}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="m-0 font-semibold">
              {[shown.title, shown.meta].filter((part) => part !== undefined && part !== "").join(" · ")}
            </p>
            {isChosen ? (
              <span className="flex items-center gap-4">
                <span className="font-semibold text-success-700" data-pick-selected="">
                  {props.selectedLabel}
                </span>
                <InlineLink
                  className="font-semibold"
                  onClick={() => {
                    setTerm("");
                    setLooking(null);
                    setMatches(null);
                    props.onChange();
                  }}
                >
                  {props.changeLabel}
                </InlineLink>
              </span>
            ) : (
              <Button variant="secondary" onClick={() => props.onUse(shown)}>
                {props.useLabel}
              </Button>
            )}
          </div>
          <div className="mt-3">{props.renderCard(shown)}</div>
        </div>
      )}
    </div>
  );
}
