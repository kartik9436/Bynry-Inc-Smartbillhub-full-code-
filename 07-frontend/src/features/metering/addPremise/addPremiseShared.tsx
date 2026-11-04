// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 round B — the pieces every step of Add a premise shares:
//           the section heading, the field pair, the closed-by-default section
//           whose header says its state, and the result box the address check,
//           the same-address prompt and the owner search draw.
// Rules:    B14 rule 21 (Tailwind utilities, no stylesheet class — this folder
//           is on `src/styles/route-b-migrated.txt`) · B14 rule 43 (a piece of
//           UI is a component) · B14 rule 44 (the drawing gives the shape, the
//           kit and its tokens build it) · B14 rule 32 (an optional group is
//           closed by default with its state in the header)
// Drawing:  05-prototype/add-premise-2026-10-09/images/01, 02, 04–08, 13, 14
// ───────────────────────────────────────────────────────
import { useId } from "react";
import type { ReactNode } from "react";

import { Panel } from "@/components/Panel";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/** A section's heading, inside its box — the Discounts redesign's register. */
export const SECTION_HEADING = "m-0 mb-4 font-heading text-h4";

/** Two fields side by side, as the drawing sets every pair. */
export const PAIR = "grid grid-cols-2 gap-x-4 gap-y-5";

/** City · State · ZIP on ONE line (PO 2026-10-09: *"keep in in 1 line ineatsd
 *  of 2"*), the ZIP the narrowest as drawn. */
export const CITY_LINE = "grid grid-cols-[2fr_2fr_1fr] gap-x-4";

/**
 * The frame draws rail, content and footer as one column; this lays them onto
 * two — the rail across both, the step and its footer on the left, *This
 * premise* on the right — by the `data-wizard` hooks the frame already renders.
 * The same device as the Discounts redesign's form (`DISCOUNT_FORM_LAYOUT`),
 * which is the format the PO asked this screen to take (decision log
 * 2026-10-09).
 */
export const ADD_PREMISE_LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_320px] gap-x-5 items-start " +
  "[&_[data-wizard=frame]]:contents " +
  "[&_[data-wizard=rail]]:col-span-2 [&_[data-wizard=rail]]:row-start-1 " +
  "[&_[data-wizard=rail]]:mb-5 [&_[data-wizard=rail]]:border [&_[data-wizard=rail]]:bg-surface " +
  "[&_[data-wizard=content]]:col-start-1 [&_[data-wizard=content]]:row-start-2 " +
  "[&_[data-wizard=content]]:mb-0 " +
  "[&_[data-wizard=actions]]:col-start-1 [&_[data-wizard=actions]]:row-start-3 " +
  "[&_[data-wizard=actions]]:mt-5 [&_[data-wizard=actions]]:border-t " +
  "[&_[data-wizard=actions]]:border-divider [&_[data-wizard=actions]]:pt-4 " +
  "[&_[data-wizard=blocked]]:hidden";

/**
 * **A SECTION THAT IS CLOSED UNTIL OPENED, ITS STATE ON THE HEADER.** Owner ·
 * *Needs an owner* ▾, Area & sub-area · *No area* ▾, Custom fields · *1
 * required* ▾ (images 01, 02). CONTROLLED, because a missing required custom
 * field must OPEN its section from outside (image 08) — the kit's `Disclosure`
 * keeps its own state and cannot be opened by its parent.
 */
export function FoldPanel(props: {
  id: string;
  title: string;
  state: ReactNode;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  const bodyId = useId();
  return (
    <Panel as="section" aria-labelledby={`${props.id}-title`} data-add-premise-fold={props.id} data-open={props.open ? "true" : "false"}>
      <button
        type="button"
        className="flex w-full cursor-pointer items-center justify-between gap-3 border-0 bg-transparent p-0 text-left"
        aria-expanded={props.open}
        aria-controls={bodyId}
        onClick={props.onToggle}
      >
        <h2 id={`${props.id}-title`} className="m-0 font-heading text-h4">
          {props.title}
        </h2>
        <span className="text-base text-neutral-700" data-add-premise-fold-state="">
          {props.state} <span aria-hidden="true">{props.open ? "▴" : "▾"}</span>
        </span>
      </button>
      {props.open && (
        <div id={bodyId} className="mt-4 flex flex-col gap-5">
          {props.children}
        </div>
      )}
    </Panel>
  );
}

export type ResultTone = "plain" | "good" | "warn";

const TONE: Record<ResultTone, string> = {
  plain: "border-neutral-600 bg-neutral-200 text-neutral-800",
  good: "border-success-700 bg-success-100 text-success-700",
  warn: "border-warning-700 bg-warning-100 text-warning-700",
};

/**
 * The boxed answer under the address or the owner search: a bold first line,
 * an optional second, an optional fact table and an optional row of buttons —
 * *City map not connected.* (grey), *Matches the city map.* (green), *No match
 * on the city map.* / *This address already exists.* (amber).
 */
export function ResultBox(props: {
  tone: ResultTone;
  title: ReactNode;
  line?: ReactNode;
  facts?: readonly { id: string; label: string; value: ReactNode }[];
  actions?: ReactNode;
  role?: "status" | "alert";
  "data-result"?: string;
}) {
  return (
    <div
      className={`flex flex-col gap-3 border-l-4 px-4 py-3 ${TONE[props.tone]}`}
      role={props.role ?? "status"}
      data-add-premise-result={props["data-result"] ?? props.tone}
    >
      <p className="m-0 font-semibold">{props.title}</p>
      {props.line !== undefined && <p className="m-0 text-md">{props.line}</p>}
      {props.facts !== undefined && props.facts.length > 0 && (
        <dl className="m-0 border border-divider bg-surface text-text">
          {props.facts.map((fact) => (
            <div key={fact.id} className="grid grid-cols-[160px_minmax(0,1fr)] border-b border-divider px-3 py-2 last:border-b-0" data-result-fact={fact.id}>
              <dt className="text-neutral-700">{fact.label}</dt>
              <dd className="m-0">{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {props.actions !== undefined && <div className="flex flex-wrap gap-2">{props.actions}</div>}
    </div>
  );
}
