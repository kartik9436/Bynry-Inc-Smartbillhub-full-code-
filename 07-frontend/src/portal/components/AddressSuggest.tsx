// ── Trace ──────────────────────────────────────────────
// Change:   CR-200-BRC10 lane B — F1 (one suggestion drop-down), used by F2
//           Start service, F4 Ask us for something; and the apartment choice
//           (F2/F4) after a building with several units.
// Defects:  DEF-CWP-10682 (no suggestions) · DEF-CWP-10680 (apartment ignored)
// Rulings:  PO 2026-10-29 — 1A (after 4 typed characters, at most 5, street +
//           town + ZIP only; picking fills street, town and ZIP and runs the
//           check) · 2A (pick from the building's unit LABELS, plus *Mine isn't
//           listed* → a person will look at it) · Ask us A (same suggestions)
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT, importable — both
//           screens use this one file) · rule 36/44 (the portal kit's input
//           shape and `RadioList`; the drawing has NO suggestion list and NO
//           apartment picker — p31/p32 name the states *ADDRESS NOT
//           RECOGNISED: offers the nearest matches* and *UNIT NEEDED: asks
//           which unit* and draw neither, so both are built from the kit) ·
//           rule 21 (Tailwind; `portal/` is on route-b-migrated.txt) · rule 31
//           (no id: a suggestion is four strings) · rule 33 (label ≤ 3 words)
// Tests:    src/portal/components/AddressSuggest.dom.test.tsx ·
//           src/portal/guest/StartService.dom.test.tsx · QuickService.test.tsx
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";

import { getAddressSuggestions } from "../api/guestClient";
import type { AddressSuggestion } from "../api/guestClient";
import { useAnnounce, useFieldWiring } from "./a11y";
import { RadioList } from "./primitives";

/** PO 1A — nothing is looked up below four typed characters. */
export const SUGGEST_FROM_CHARS = 4;
/** How long typing must pause before a look-up: one request per pause, not
 *  per keystroke, because the guest throttle is sixty a minute per address. */
const PAUSE_MS = 250;

/** `2155 Hemlock Dr, Ann Arbor, MI 48108` — the one way a suggestion reads. */
export function suggestionLine(row: AddressSuggestion): string {
  const tail = [row.state ?? "", row.postal_code ?? ""].filter((part) => part !== "").join(" ");
  return [row.street, row.city, tail].filter((part) => part !== "").join(", ");
}

/**
 * The street box with suggestions under it — a WAI-ARIA 1.2 combobox.
 *
 * ⚠ **IT OWNS ITS INPUT, AND THE INPUT IS `TextInput`'S SHAPE.** A combobox
 * needs `role`, `aria-expanded`, `aria-controls` and `aria-activedescendant` on
 * the box itself, which the kit's `TextInput` does not forward; the classes are
 * copied from it so there is still one input shape in the portal (B14 rule 39),
 * and `useFieldWiring` gives it the same label / helper / error wiring a
 * `FormField` publishes.
 *
 * Keys: ↓/↑ move through the list (and open it), Enter picks the highlighted
 * one, Escape closes it and keeps what was typed. A pick fills the parts
 * (`onPick`) — the box shows the street, the caller fills town and ZIP.
 * The count is spoken when a list arrives, never the whole list.
 *
 * ⚠ **TYPING AFTER A PICK IS A NEW SEARCH.** The pick is the caller's state;
 * nothing is looked up after a pick until the person types again.
 */
export function AddressSuggestInput(props: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onPick: (row: AddressSuggestion) => void;
  client?: ApiClient;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  describedBy?: string;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const listId = `${useId()}-suggestions`;
  const say = useAnnounce();
  const wired = useFieldWiring(props.id, props);
  const [typed, setTyped] = useState(props.value);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  // After a pick nothing is looked up until the person types again.
  const [quiet, setQuiet] = useState(false);

  // One look-up per pause in typing.
  useEffect(() => {
    const handle = window.setTimeout(() => setTyped(props.value), PAUSE_MS);
    return () => window.clearTimeout(handle);
  }, [props.value]);

  const query = typed.trim();
  const wanted = query.length >= SUGGEST_FROM_CHARS && !quiet;
  const lookup = useQuery({
    queryKey: ["portal", "address-suggestions", query],
    queryFn: () => getAddressSuggestions(query, client),
    enabled: wanted,
    staleTime: 60_000,
  });
  const rows = wanted ? (lookup.data ?? []) : [];
  const shown = open && rows.length > 0;

  useEffect(() => {
    if (!wanted || lookup.data === undefined) return;
    setOpen(true);
    setActive(-1);
    if (lookup.data.length > 0) {
      say.polite(t("portal.address.suggestionsFound", { count: lookup.data.length }));
    }
    // `say` and `t` are stable for this purpose; a new LIST is the signal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lookup.data, wanted]);

  const pick = (row: AddressSuggestion) => {
    setQuiet(true);
    setOpen(false);
    setActive(-1);
    props.onPick(row);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" && rows.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActive((was) => (was + 1) % rows.length);
    } else if (event.key === "ArrowUp" && rows.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActive((was) => (was <= 0 ? rows.length - 1 : was - 1));
    } else if (event.key === "Enter" && shown && active >= 0) {
      event.preventDefault();
      const row = rows[active];
      if (row !== undefined) pick(row);
    } else if (event.key === "Escape" && shown) {
      event.preventDefault();
      setOpen(false);
      setActive(-1);
    }
  };

  return (
    <div className="relative" data-address-suggest={props.id}>
      <input
        id={props.id}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={shown}
        aria-controls={listId}
        aria-activedescendant={shown && active >= 0 ? `${listId}-${active}` : undefined}
        value={props.value}
        placeholder={props.placeholder}
        autoComplete={props.autoComplete ?? "off"}
        {...wired}
        className="w-full min-h-9 border border-field-border bg-[white] px-2.5 py-1.5 text-body text-neutral-900"
        onChange={(event) => {
          setQuiet(false);
          setOpen(true);
          props.onChange(event.target.value);
        }}
        onKeyDown={onKeyDown}
        onBlur={() => setOpen(false)}
      />
      <ul
        id={listId}
        role="listbox"
        aria-label={t("portal.address.suggestions")}
        hidden={!shown}
        className="absolute inset-x-0 top-full z-10 m-0 list-none border border-t-0 border-field-border bg-[white] p-0"
        data-suggestions=""
      >
        {shown
          ? rows.map((row, index) => (
              <li
                key={suggestionLine(row)}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                data-suggestion={index}
                className={`min-h-11 cursor-pointer px-2.5 py-2.5 text-body text-neutral-900 ${
                  index === active ? "bg-neutral-100 font-semibold underline" : ""
                }`}
                // `mousedown`, not `click`: the box's blur would close the
                // list before a click arrived.
                onMouseDown={(event) => {
                  event.preventDefault();
                  pick(row);
                }}
              >
                {suggestionLine(row)}
              </li>
            ))
          : null}
      </ul>
    </div>
  );
}

/** The value *Mine isn't listed* carries — never a label (labels are text a
 *  utility typed; this cannot be one of them). */
export const NOT_LISTED = "\u0000not-listed";

/**
 * *Which apartment?* — the building's unit LABELS (no occupancy, `BR-CWP-021`)
 * plus *Mine isn't listed*. `value` is a label, `NOT_LISTED`, or null.
 */
export function ApartmentChoice(props: {
  labels: readonly string[];
  value: string | null;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <fieldset className="m-0 flex flex-col gap-1 border-0 p-0" data-apartment-choice="">
      <legend className="mb-1.25 p-0 text-base font-semibold text-neutral-800">
        {t("portal.address.whichApartment")}
      </legend>
      <RadioList
        name={t("portal.address.whichApartment")}
        value={props.value}
        options={[
          ...props.labels.map((label) => ({ value: label, label })),
          { value: NOT_LISTED, label: t("portal.address.notListed") },
        ]}
        onChange={props.onChange}
      />
    </fieldset>
  );
}
