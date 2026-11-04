// ── Trace ──────────────────────────────────────────────
// Ruling:  PO 2026-09-28, verbatim: *"the Units "Missing services" block —
//          filter or leave it. - filter"*, raised as *"why this is build -
//          missing services - it would ahve been a filer criteria and I can
//          filter th units based on this"*. Decision log, same date.
// Defect:  DEF-MET-6796 — units holding fewer service points than their
//          address offers. **The shortfall was INVISIBLE**: no screen, gate or
//          test counted it. That is why this chip carries the COUNT and not
//          only the control.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT, not code inside a page) ·
//          rule 33 (a LABEL ≤ 3 words — *Missing services* is two; RATIONALE is
//          ZERO words on screen, so nothing here explains what a gap is) ·
//          rule 12 (the toolbar's vocabulary is chips) · rule 21 (Tailwind
//          utilities; this file is on route-b-migrated.txt) · BR-MET-119 as
//          amended 2026-09-25 · BR-BIL-300 (why a gap is money)
// Tests:   src/features/metering/MissingServicesChip.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A CHIP AND NOT A LINE OF TEXT — THE ONE CONSTRAINT THAT DECIDES IT
// ══════════════════════════════════════════════════════════════════════════
// The PO ratified two separate things: *a filter sits with the four already
// there*, and *its count is visible whether or not the filter is on*. The
// declared filter satisfies the first — it is in the `+ Filter ▾` panel, it
// round-trips through `f.missing_services`, and it leaves a removable chip.
// It cannot satisfy the second, because a panel is CLOSED by default and a
// number nobody opens a panel to read is exactly as invisible as the figure
// `DEF-MET-6796` was filed about.
//
// So the count lives on the toolbar, and it is a `ChipToggle` rather than a
// caption because **B14 says a row of controls holds only things a person can
// PRESS**. One control, two jobs: it states the number and it applies the
// filter. There is still only ONE value — `state.filters.missing_services` —
// so this and the panel cannot drift apart the way the block and the list did.
//
// ⚠ **IT SURVIVES ITS OWN COUNT REACHING ZERO WHILE IT IS ENGAGED, AND THAT IS
// THE LAW-2 MIRROR.** Draw it only when the count is positive and a clerk who
// fixes the last short unit with the filter still on is left looking at an
// empty table with no control to untick — a live filter behind a vanished
// door. So: positive count OR engaged.
import { ChipToggle } from "@/components/Chip";

import type { Translator } from "@/features/tenancy/settingsShared";

export function MissingServicesChip(props: {
  /** The server's `service_gap_count` — how many units are short under
   *  everything else the clerk has set. `null` when this build's server did
   *  not send one: the chip then says nothing rather than drawing a `0` it was
   *  never told (`DEF-138`'s shape). */
  count: number | null;
  /** Is `f.missing_services` applied right now? */
  on: boolean;
  onToggle: () => void;
  t: Translator;
}) {
  const { count, on, t } = props;
  if (!on && (count === null || count === 0)) {
    return null;
  }
  return (
    <ChipToggle selected={on} onClick={props.onToggle}>
      {t("metering.units.gaps.heading")}
      {count === null ? null : (
        <span className="ml-1.5 opacity-75">
          {t("metering.units.gaps.count", { count })}
        </span>
      )}
    </ChipToggle>
  );
}
