// ── Trace ──────────────────────────────────────────────
// Change:   DEF-MET-6913 — the premises detail header shows no utility-service
//           chips. Reported by the Product Owner from the live beta
//           (smartbillhub.bynry.com, Ottumwa Water Works, premises `P-00079`,
//           v2.352.0): *"On the premises detail page the header should show the
//           utility service chips; this premises has 4 utility services but they
//           are not visible in the header."*
//           Screens: S15/PRM-02 (premises detail) — and any other entity header
//           that names the services a record carries.
// Rules:    B14 rule 43 (a piece of UI is built as a COMPONENT; standalone code
//           inside a page is not reuse — which is why this is a file in
//           `components/` and not 30 lines inside a 2,908-line page) ·
//           B14 rule 44 (our UI standard wins over the drawing, INCLUDING the
//           frame — the blueprint's PRM-02 header carries no chip row and the
//           product's own entity headers do, so the standard decides) ·
//           B14 rule 33 (on-screen text is capped by what it is FOR — a chip is
//           a LABEL, so ≤ 3 words and no sentence; RATIONALE is ZERO WORDS, so
//           this component never explains itself on screen) ·
//           B14 rule 31 (no database id is ever the visible value of a field —
//           a chip shows the service's NAME, never its code or its row id) ·
//           B14 rule 21 (Tailwind utilities, no stylesheet class — this file is
//           registered in `styles/route-b-migrated.txt`, so the real compiler
//           owns every utility here through `routeBUtilities.test.ts`) ·
//           BR-RAT-024 (the ELEVEN services, in seed order).
// Tests:    07-frontend/src/components/ServiceChips.dom.test.tsx ·
//           07-frontend/src/features/metering/PremisesHeaderChips.dom.test.tsx ·
//           10-scripts/def_met_6913_premises_chips_walkthrough.mjs (the browser
//           walk — hard-won law 6: no gate in this repo reads rendered output,
//           so nothing else can answer the PO's actual question).
// ───────────────────────────────────────────────────────
/**
 * **`▪ WATER  ▪ SEWER  ▪ TRASH  ▪ FIRE`** — the services a record carries, as
 * chips, for an entity HEADER.
 *
 * ⚠ **IT IS NOT A SECOND SERVICE VOCABULARY AND MUST NEVER BECOME ONE**
 * (`DEF-348`, `DEF-763`, and `PremisesDetailPage.ServiceWords` says the same
 * thing about the same catalogue). The name is `rating.service.<code>` — THE
 * service-name catalogue in this product, present for all eleven codes in all
 * eleven languages — and the colour is `serviceBadge(code).token`, the palette
 * `ServiceTags` already paints. **There is no list of codes in this file**, so
 * a twelfth service needs nothing here: an unknown code keeps its own text and
 * takes `serviceBadge`'s neutral token rather than being dropped. That is
 * deliberate — hard-won law 2 is that the front end typed the service list out
 * by hand in two places and an eleventh service *failed silently*.
 *
 * ⚠ **EMPTY AND ABSENT BOTH RENDER NOTHING, AND THAT IS THE HEADER'S ANSWER
 * RATHER THAN THE PRODUCT'S.** `null` (nobody was asked) and `[]` (the clerk
 * answered *none*) are different facts — `DEF-762` / `CR-036` (h) — and the
 * screen that must TELL them apart is the fact list, which still does, in
 * words. A header states what a record IS; a stated absence there would be
 * RATIONALE, which B14 rule 33 puts at zero words on screen. So the caller
 * renders no row, no separator and no empty chip: blank space.
 *
 * ⚠ **THE CHIP'S MEANING IS IN ITS ACCESSIBLE NAME, NOT IN ITS SQUARE.** The
 * colour square is `aria-hidden` and carries a runtime token through `style`
 * rather than an interpolated class — `routeBUtilities.test.ts` documents why a
 * class per service is a trap — and the chip's `aria-label` is the translated
 * service name, so a screen reader announces a word and not a colour.
 */
import type { CSSProperties } from "react";

import { serviceBadge } from "@/features/rating/ratingShared";

type Translator = (key: string, options?: Record<string, unknown>) => string;

/**
 * r10's chip, in utilities: `display:inline-flex; gap:5px; padding:3px 8px;
 * background:var(--color-surface); font-size:11px; letter-spacing:0.04em;
 * font-family:var(--font-heading); font-weight:600`.
 *
 * ⚠ **`gap-[5px]` AND `py-[3px]` ARE r10's OWN ODD VALUES** and are kept rather
 * than rounded to the 4px scale, for the reason `accountDetailHeader.tsx` gives
 * about the identical chip: this is a ported drawing, and rounding it would
 * move the one element the two screens have to agree on.
 */
const SERVICE_CHIP =
  "inline-flex items-center gap-[5px] bg-surface px-2 py-[3px] " +
  "font-heading text-xs font-semibold uppercase tracking-label";

export function ServiceChips(props: {
  /** The service CODES this record carries. `null` and `[]` both render nothing. */
  services: readonly string[] | null | undefined;
  t: Translator;
}) {
  const services = props.services ?? [];
  if (services.length === 0) {
    return null;
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5" data-testid="service-chips">
      {services.map((code) => {
        const badge = serviceBadge(code);
        const name = props.t(`rating.service.${code}`, { defaultValue: code });
        const swatch: CSSProperties = { background: `var(${badge.token})` };
        return (
          <span key={code} className={SERVICE_CHIP} data-service={code} aria-label={name}>
            <span aria-hidden="true" className="inline-block h-2 w-2 shrink-0" style={swatch} />
            <span aria-hidden="true">{name}</span>
          </span>
        );
      })}
    </span>
  );
}

export default ServiceChips;
