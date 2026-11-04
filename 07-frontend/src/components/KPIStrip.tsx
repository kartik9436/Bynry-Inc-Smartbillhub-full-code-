// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories — display kit)  Screens: S7, S36 (KPI strips)
// Rules:    BR-REP-001 (basis label on every money KPI) · BR-SHL-023 (one formatting path) · BR-SHL-012 (shared loading state)
// ───────────────────────────────────────────────────────
// FE-09 KPIStrip (B13 §1): the screen-top KPI tile row (prototype .kpi-grid,
// layout only — runtime never ported). Each tile is label · value · optional
// detail line. A MONEY tile declares `money` instead of `value`: its amount
// renders through the ONE MoneyCell and its BR-REP-001 date basis is a
// REQUIRED field, rendered in the tile header — the type makes an unlabeled
// money KPI impossible to declare. Which basis each KPI reads (posting vs
// clearing) is the consuming screen's law (A14 §basis table), not this
// component's. Loading composes the shared KPI skeleton (BR-SHL-012 — never
// reimplemented here).
//
// ══════════════════════════════════════════════════════════════════════════
// AMENDED 2026-09-28 — A TILE MAY NOW BE PRESSED, AND STILL ONLY IF IT SAYS SO
// ══════════════════════════════════════════════════════════════════════════
// PO ruling 2026-09-28 gave the Accounts register four status tiles that each
// *"set the list's filter when pressed"*. `press` is OPT-IN per tile: a tile
// without it renders exactly the `<div>` it always did, so none of the ~30
// screens mounting this strip moves a pixel.
//
// ⚠ **THIS DOES NOT MAKE `components/AgeingCards.tsx` REDUNDANT, AND ITS OWN
// HEADING — *"WHY THIS IS NOT A KPIStrip"* — IS AMENDED IN THE SAME COMMIT
// RATHER THAN LEFT STANDING** (hard-won law 1: the comment changes with the
// fact). The payments debtor screen draws TWO rows of figures and the split
// between them is WEIGHT, not pressability: heavy tiles above answering *how
// bad is it*, lighter tone-ruled cards below that narrow the list. Accounts
// draws ONE row, and the PO's four both state a count and narrow — so the tile
// presses. A second component for a pressable tile would be B14 rule 43's own
// failure (*"a piece of UI is a COMPONENT … a second host cannot reuse what is
// not addressable"*), which is why the capability went into the strip the
// screen already mounts.
//
// ⚠ **THIS IS THE HOME `features/customers/newConnectListViews.BuildTiles`
// ASKED FOR BY NAME, HOURS EARLIER ON THIS BRANCH, AND THAT COMPONENT IS NOW
// OWED A FOLD-IN (`DEF-CUS-7701`).** Its docstring reads: *"`KPIStrip` renders
// every tile as a `<div>` and has no `selected` / `onSelect` pair … **the right
// home for this is those two props on `KPIStrip` itself**, which is the
// components lane's file — REPORTED, and this component folds into it the day
// they land."* They have landed. **The pressed ring here is deliberately that
// component's own ring, to the utility**, so the fold-in is a behaviour change
// and not a visual one. It is filed rather than done here because
// `newConnectListViews.tsx` is a live lane's file mid-change-request, and
// because hard-won law 2's mirror is exactly this shape: landing the thing a
// control was waiting for and releasing the control are two acts, and only the
// first one feels like the work.
//
// ⚠ **`aria-pressed`, NEVER `aria-selected`** — same reasoning as
// `AgeingCards`: these are toggle buttons, not tabs, and a screen reader
// announcing *"tab"* tells a clerk the list will be REPLACED rather than
// narrowed.
//
// ⚠ **THE PRESSED OUTLINE IS A WHOLE CLASS STRING, NEVER AN INTERPOLATION.**
// Tailwind's scanner cannot see a class it has to compute, and a class the
// compiler never emitted renders as nothing while every `toContain` assertion
// still passes (`DEF-SHL-5088`). This file is on `src/styles/route-b-migrated.txt`
// from this commit, so `routeBUtilities.test.ts` asks the compiler.
import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { MoneyCell } from "./MoneyCell";
import type { MoneyBasis } from "./MoneyCell";
import { LoadingSkeleton } from "./StateFrame";

import "./KPIStrip.css";

export interface KpiMoney {
  amount: string; // decimal string from the API — never a number
  currency: string;
  basis: MoneyBasis; // BR-REP-001: REQUIRED — no unlabeled money number anywhere
  locale?: string; // tenant Regional number format (IS-8)
}

/** What a tile does when a clerk presses it, and whether it is pressed now. */
export interface KpiPress {
  /** Called on every press. The CALLER decides whether that applies its filter
   *  or clears it — this component owns no list state and must not, or two
   *  controls end up holding one answer (the defect `AgeingCards` was drawn to
   *  remove: a strip that looked like a filter beside a `<select>` that was). */
  onPress: () => void;
  /** True while the list is narrowed to this tile. Drives `aria-pressed`. */
  pressed: boolean;
}

export type KpiTile =
  | { id: string; label: string; money: KpiMoney; detail?: ReactNode; press?: KpiPress }
  | { id: string; label: string; value: ReactNode; detail?: ReactNode; press?: KpiPress };

export interface KPIStripProps {
  kpis: readonly KpiTile[];
  loading?: boolean;
  /** The group's accessible name, for a strip whose tiles press. Four unnamed
   *  buttons in a row are unusable without a mouse. Omitted on a read-only
   *  strip, which is not a group of controls and must not announce itself as
   *  one. */
  label?: string;
  /**
   * `DEF-WRK-9680` — what the tiles HOLD. Absent (`"money"`) keeps the 240px
   * track `DEF-LED-6498` set so a T5 receivable keeps its cents. `"count"` is
   * for a strip of whole numbers — Work › Orders' five — which need far less
   * room, and takes the 224px step so five fit one row at 1440 (image 01).
   * It narrows the MINIMUM only: a narrow screen still wraps.
   */
  tiles?: "money" | "count";
}

export function KPIStrip(props: KPIStripProps) {
  const { t } = useTranslation();
  if (props.loading === true) {
    // BR-SHL-012 / A18 §3: KPI-sized skeleton blocks while fetching.
    return <LoadingSkeleton variant="kpi" />;
  }
  const anyPresses = props.kpis.some((kpi) => kpi.press !== undefined);
  return (
    <div
      className="kpi-grid"
      style={props.tiles === "count" ? ({ "--kpi-tile-min": "14rem" } as CSSProperties) : undefined}
      data-kpi-tiles={props.tiles ?? "money"}
      // A read-only strip is not a group of controls, so it announces nothing.
      role={anyPresses ? "group" : undefined}
      aria-label={anyPresses ? props.label : undefined}
    >
      {props.kpis.map((kpi) => {
        const body = (
          <>
            <span className="k">
              {kpi.label}
              {"money" in kpi && (
                // BR-REP-001: the KPI header labels its date basis.
                <span className="kpi-basis">{t(`cells.basis.${kpi.money.basis}`)}</span>
              )}
            </span>
            <span className="v">
              {"money" in kpi ? (
                <MoneyCell
                  amount={kpi.money.amount}
                  currency={kpi.money.currency}
                  locale={kpi.money.locale}
                />
              ) : (
                kpi.value
              )}
            </span>
            {kpi.detail !== undefined && <span className="d">{kpi.detail}</span>}
          </>
        );
        const press = kpi.press;
        if (press === undefined) {
          return (
            <div key={kpi.id} className="kpi">
              {body}
            </div>
          );
        }
        return (
          <button
            key={kpi.id}
            type="button"
            // ⚠ **THE RING IS `newConnectListViews.BuildTiles`' RING, TO THE
            // UTILITY** — `outline-accent` at `-outline-offset-2`, which that
            // file took from its own drawing hours before this landed. One
            // visual decision for the kit (B14 rule 36/44), so folding that
            // component into this one moves no pixel. `text-left` because a
            // `<button>` centres its content and a tile is a column of
            // left-aligned facts.
            className={
              press.pressed
                ? "kpi cursor-pointer text-left outline outline-2 -outline-offset-2 outline-accent"
                : "kpi cursor-pointer text-left"
            }
            aria-pressed={press.pressed}
            data-kpi={kpi.id}
            onClick={press.onPress}
          >
            {body}
          </button>
        );
      })}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-09-28 by LANE CUS-TILES
//   (PO ruling of that date — the Accounts register's four status tiles each
//   SET the list's filter when pressed, so a tile may opt in to `press` and the
//   strip announces itself as a group when one does. Additive: every existing
//   caller renders the same `<div class="kpi">` it always did. B14 rule 43 —
//   the capability goes into the kit piece the screen already mounts rather
//   than into a second strip; rule 21 — Tailwind utilities and no stylesheet
//   class, so this file joins `src/styles/route-b-migrated.txt` in the same
//   commit and `routeBUtilities.test.ts` now owns its classes)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
