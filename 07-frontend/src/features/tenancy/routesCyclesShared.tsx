// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3 (PO 2026-08-23) — Routes & Cycles: the screens wave.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §2–§4, §7
// Story:   US-MET-006 (EP-MET-02 §Stories)
//          Screens: S8 · SET-05 · SET-05.cycles · SET-06D · SET-07D · SET-06/07
// Rules:   the pre-CR PO ruling (grouping only; start day · frequency · days to
//          complete; eight one-word business names) · D6 (NO reader anywhere) ·
//          D9 (bill day + due days are CYCLE DEFAULTS the run may override) ·
//          D10 (a route serves a service SET) · D11 (walking order PER
//          PREMISES) · D12 (no Balance column) · D13 (a cycle is DERIVED at
//          bill-run time) · BR-MET-078 (no money on this surface)
// B14:     rule 21 (Tailwind utilities, NO stylesheet class) · 18 (80% measure)
// Tests:   routesCyclesShared.test.ts
// ───────────────────────────────────────────────────────
/**
 * The pieces every Routes & Cycles screen shares — the vocabulary, the paths,
 * the walking-order arithmetic and four small Tailwind surfaces.
 *
 * ⚠ **WHY A SHARED FILE AT ALL, WHEN THE LANDING ALREADY HAD ONE.** RC-W3 adds
 * two brand-new screens (SET-06D, SET-07D) and four addressable wizard pages to
 * a surface that was one tab. The frequency word, the "derived, not stored"
 * sentence and the route/cycle URL are each read by four or more of them, and
 * the alternative to one owner is DEF-348's shape — the same pencil drawn three
 * times under two names.
 *
 * ⚠ **B14 RULE 21 — EVERYTHING HERE IS TAILWIND UTILITIES AND ADDS NO CLASS TO
 * ANY STYLESHEET.** The PO asked directly on 2026-08-23: *"Pls confirm UI is
 * build using tailwind for Routes and Cycles?"* G31's declared-class count is a
 * CEILING (546) that may fall and never rise, so a `.rc-facts-rail` here would
 * be a rule broken on the commit that added it.
 *
 * ⚠ **AND IT BORROWS NO OTHER FEATURE'S CLASSES.** Not `met-*` (metering's),
 * not `settings-*`. That is the `ImportAccountsWizard` mistake B17 §7 names by
 * name — a customers screen reaching for metering's stylesheet.
 */
import type { ReactNode } from "react";

import { buttonClasses } from "@/components/Button";
import { Chip, ChipRow, ChipToggle } from "@/components/Chip";
import type { CycleRow, RouteMember, RoutePremisesStop } from "@/api/endpoints";
import type { Translator } from "./settingsShared";

// ── The vocabulary ─────────────────────────────────────────────────────────

/**
 * B17 §2 — **the eight one-word business names, in the design's order**, and
 * they are the SERVER's own strings (`apps/metering/schedule.FREQUENCIES`).
 *
 * The PO asked for one word each: *"give business names to frequence - 1
 * word."* **Fortnightly carries their "biweekly"** because biweekly also means
 * twice-a-week in common use, and a schedule word that means two things is
 * exactly what a controlled vocabulary exists to prevent.
 *
 * ⚠ THIS SUPERSEDES `CYCLE_FREQUENCIES` IN `RoutesCyclesWizards.tsx`, which is
 * CR-006's three (`monthly · bi_monthly · quarterly`) and is now a subset
 * written in the wrong spelling — RC-W1's migration 0019 moved every shipped
 * row onto the words above.
 */
export const CYCLE_FREQUENCY_WORDS = [
  "Daily",
  "Weekly",
  "Fortnightly",
  "Monthly",
  "Bimonthly",
  "Quarterly",
  "Semiannual",
  "Annual",
] as const;

export type CycleFrequencyWord = (typeof CYCLE_FREQUENCY_WORDS)[number];

/**
 * What a SHIPPED row may still hold, and what each becomes — the client half of
 * `schedule.LEGACY_FREQUENCIES`. It exists so a cycle written before RC-W1
 * renders a word rather than a raw i18n key on the one screen a utility uses to
 * find it.
 */
const LEGACY_FREQUENCY_WORDS: Readonly<Record<string, CycleFrequencyWord>> = {
  daily: "Daily",
  weekly: "Weekly",
  biweekly: "Fortnightly",
  bi_weekly: "Fortnightly",
  fortnightly: "Fortnightly",
  monthly: "Monthly",
  bimonthly: "Bimonthly",
  bi_monthly: "Bimonthly",
  quarterly: "Quarterly",
  semiannual: "Semiannual",
  semi_annual: "Semiannual",
  annual: "Annual",
  yearly: "Annual",
};

/**
 * The catalogue key for a served frequency, or **null when the word is not one
 * of the eight**.
 *
 * ⚠ NULL, NOT A FALLBACK KEY. A word this vocabulary does not know is a fact
 * about the data, and printing it through `t(key, { defaultValue: raw })` would
 * quietly make an unruled ninth frequency look like a supported one. The caller
 * renders the honest "not one of the eight" state instead.
 */
export function frequencyKey(value: string | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  const text = String(value).trim();
  if (text === "") {
    return null;
  }
  const direct = CYCLE_FREQUENCY_WORDS.find((word) => word.toLowerCase() === text.toLowerCase());
  const word = direct ?? LEGACY_FREQUENCY_WORDS[text.toLowerCase().replace(/-/g, "_")];
  return word === undefined ? null : `settings.cycles.frequency.${word.toLowerCase()}`;
}

/**
 * DEF-224's plurals, and **deliberately not i18next's plural suffixes.**
 *
 * The defect, verbatim: *"no count on this surface has a plural form — '1 routes
 * selected', '1 routes · 1 members', 'will skip 1 premises'"*. i18next solves
 * that with `key_one` / `key_other` / `key_many`, resolved **per language** —
 * which means the KEY SET differs between catalogues by construction, and G15's
 * first assertion is that every catalogue carries EXACTLY `en.json`'s keys. One
 * of those two things has to give.
 *
 * So the branch is taken here and the catalogues stay parallel. It is correct
 * for all eleven languages this product ships (de · en · es · es-MX · fr-FR ·
 * hi · id-ID · it-IT · ja-JP · ko-KR · pt-BR): every one is either one/other or
 * other-only, and none is Slavic. A twelfth language with a `few` category
 * would need this revisited — which is a real cost, recorded rather than
 * discovered.
 */
export function pluralKey(base: string, count: number): string {
  return count === 1 ? `${base}.one` : `${base}.other`;
}

/** The frequency as a word, or the caller's dash when the cycle has none. */
export function frequencyLabel(value: string | null, t: Translator, dash: string): string {
  const key = frequencyKey(value);
  return key === null ? dash : t(key);
}

// ── D11 · the walking order, at PREMISES grain ─────────────────────────────

/**
 * One STOP on the route sheet. **A stop is a PREMISES, not a unit** — PO ruling
 * D11, verbatim: *"Per premises"*.
 *
 * The upgraded prototype's Premises tab numbers 1408 Elm's three units 0142,
 * 0143, 0144 and Cedar Ct's three units all 0145; B17 §3's table records that
 * the first reading is the wrong one and the second is right. A reader walking
 * a three-unit building climbs the steps ONCE.
 */
export interface RouteStop {
  premises_id: string;
  premise_no: string | null;
  units: number;
  unit_ids: string[];
  /** The lowest per-unit `walk_order` the membership carries, or null. Used to
   *  ORDER the stops and never rendered — see `RouteMember.walk_order`. */
  hint: number | null;
}

/**
 * Folds the unit-grain membership into premises stops.
 *
 * ⚠ **THIS IS WHERE THE PER-UNIT COLUMN DIES.** `route_memberships.walk_order`
 * is superseded by D11 and `route_premises_orders` replaces it. The old column
 * is used for ONE thing only — deciding which stop comes first — and its VALUE
 * never reaches the screen, because a 4 beside a premises whose stop number is
 * 2 is worse than no number at all.
 *
 * ⚠ **AND `route_detail` SERVES THE RULED ORDER NOW (RC-W3b), so prefer
 * `stopsFromServedOrder` and keep this as the fallback it has become.** The
 * server projects the per-premises order back onto `membership.walk_order`, so
 * the two agree; this stays because a route that has never been sequenced has
 * no `premises_order` row to read and still has to draw as a walkable list.
 */
export function premisesStops(members: readonly RouteMember[]): RouteStop[] {
  const stops = new Map<string, RouteStop>();
  for (const member of members) {
    const existing = stops.get(member.premises_id);
    if (existing === undefined) {
      stops.set(member.premises_id, {
        premises_id: member.premises_id,
        premise_no: member.premise_no,
        units: 1,
        unit_ids: [member.unit_id],
        hint: member.walk_order,
      });
      continue;
    }
    existing.units += 1;
    existing.unit_ids.push(member.unit_id);
    if (member.walk_order !== null && (existing.hint === null || member.walk_order < existing.hint)) {
      existing.hint = member.walk_order;
    }
  }
  // Ordered stops first, in their stored order; then the unordered ones by
  // premise number, so a route that has never been sequenced still reads as a
  // list somebody could walk rather than as insertion order.
  return [...stops.values()].sort((a, b) => {
    if (a.hint !== null && b.hint !== null && a.hint !== b.hint) {
      return a.hint - b.hint;
    }
    if (a.hint !== null && b.hint === null) {
      return -1;
    }
    if (a.hint === null && b.hint !== null) {
      return 1;
    }
    return (a.premise_no ?? "").localeCompare(b.premise_no ?? "");
  });
}

/** The stop's sequence number as a reader sees it: its POSITION, 1-based. */
export function stopSequenceOf(stops: readonly RouteStop[], stop: RouteStop): number {
  return stops.findIndex((row) => row.premises_id === stop.premises_id) + 1;
}

/**
 * Drag-to-reorder as a pure move. An out-of-range or no-op index returns the
 * SAME array reference's contents unchanged — a reorder that silently drops or
 * duplicates a stop would put a premises on nobody's walk.
 */
export function reorderStops(
  stops: readonly RouteStop[],
  from: number,
  to: number,
): RouteStop[] {
  if (
    from === to ||
    from < 0 ||
    to < 0 ||
    from >= stops.length ||
    to >= stops.length
  ) {
    return [...stops];
  }
  const next = [...stops];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

/** The body `PUT /routes/{id}/premises-order` takes: 1-based, dense, in order. */
export function walkOrderPayload(
  stops: readonly RouteStop[],
): { premises_id: string; walk_order: number }[] {
  return stops.map((stop, index) => ({ premises_id: stop.premises_id, walk_order: index + 1 }));
}

/**
 * The stops as the SERVER sequenced them, folded together with the membership.
 *
 * ⚠ **THE SERVER'S ORDER WINS, AND THAT IS THE WHOLE POINT OF READING IT BACK.**
 * Before RC-W3b nothing served `route_premises_orders`, so the screen inferred
 * a walk from the superseded per-unit column and a saved order could not be
 * seen again. Now the ruled list comes back with its own positions and its own
 * unit counts, and this only has to attach the ids each stop covers — which the
 * served rows do not carry and the reorder payload does not need.
 *
 * An EMPTY served order is a route nobody has sequenced, not an empty route:
 * the membership fallback draws it in address order, exactly as before.
 */
export function stopsFromServedOrder(
  served: readonly RoutePremisesStop[],
  members: readonly RouteMember[],
): RouteStop[] {
  if (served.length === 0) {
    return premisesStops(members);
  }
  const unitsBy = new Map<string, string[]>();
  for (const member of members) {
    const list = unitsBy.get(member.premises_id);
    if (list === undefined) {
      unitsBy.set(member.premises_id, [member.unit_id]);
    } else {
      list.push(member.unit_id);
    }
  }
  return [...served]
    .sort((a, b) => a.walk_order - b.walk_order)
    .map((stop) => ({
      premises_id: stop.premises_id,
      premise_no: stop.premise_no,
      units: stop.units,
      unit_ids: unitsBy.get(stop.premises_id) ?? [],
      hint: stop.walk_order,
    }));
}

// ── The proposal (RC-W2's engine, as this surface renders it) ──────────────

/**
 * The catalogue key for a proposed window's status, or **null when the served
 * word is not one of the two**.
 *
 * `Next` and `Scheduled` are the upgraded prototype's own words and the server
 * derives them from POSITION — nothing stores a status. NULL rather than a
 * fallback key, for `frequencyKey`'s reason: a third status would be a fact
 * about the data, and rendering it through a default would make an unruled
 * state look supported.
 */
export function windowStatusKey(status: string | null | undefined): string | null {
  if (status === "Next") {
    return "settings.cycles.window.status.next";
  }
  if (status === "Scheduled") {
    return "settings.cycles.window.status.scheduled";
  }
  return null;
}

/**
 * ⚠ **THE THREE SILENCES, AND WHY THE SCREEN MUST NOT FILL ANY OF THEM.**
 *
 * `period_engine` refuses to derive a cycle's windows in three cases, each of
 * which is an OPEN question the Product Owner has not ruled. It sends a machine
 * `code`; this maps it to a sentence a utility clerk can act on.
 *
 * The codes, and what each one is waiting for:
 *
 *   · `cycle_month_end_anchor_unruled` — the cycle reads on the 29th, 30th or
 *     31st and some months have no such date. Reading on the month's last day,
 *     skipping the month and rolling into the next one produce **different
 *     bills**, and none of the three is chosen.
 *   · `cycle_first_run_disagrees_with_start_day` — the first-run date is not on
 *     the start day, so which of the two sets the rhythm is undecided.
 *   · `cycle_windows_would_overlap` — days-to-complete is longer than the gap
 *     between readings, so the next window would open inside the current one.
 *
 * **What this function must never do is turn one of them into a date.** The
 * sentence names the decision the product is missing and the two things a clerk
 * can do about it today; it carries no date, no code, no rule id and no
 * open-question id (G28: *"keep the honesty, drop the provenance"*).
 *
 * ⚠ **AND THE SERVER'S OWN `detail` IS NOT RENDERED.** It is English prose from
 * a Python module and this product ships eleven languages; a screen that fell
 * back to it would be untranslated for ten of them.
 */
export function scheduleGapKey(code: string | null | undefined): string {
  const known = new Set([
    "cycle_month_end_anchor_unruled",
    "cycle_first_run_disagrees_with_start_day",
    "cycle_windows_would_overlap",
  ]);
  return code != null && known.has(code)
    ? `settings.cycles.gap.${code}`
    : "settings.cycles.gap.unknown";
}

/**
 * ⚠ **OQ-340 — THE STORED START DAY CAN DESCRIBE NOTHING, AND EVERY SCHEDULE
 * SURFACE HAS TO SAY SO.** PO, verbatim, 2026-08-23: *"A: first window 15–17
 * Sep (start day becomes decorative)"*. The engine anchors on the first run
 * whenever the two disagree and **does not rewrite `cycles.start_day`** — that
 * number is the operator's own. The consequence the PO acknowledged in the
 * ruling itself is that the field then lies, so four surfaces (the cycles
 * landing, the detail's Schedule tab, its Facts rail and the wizard's schedule
 * step) render the EFFECTIVE day through this one helper.
 *
 * ⚠ **NOTHING HERE COMPUTES A DAY.** `effective_start_day` is SERVED
 * (`period_engine.effective_start_day`); a client that derived it from
 * `first_run_date` would be a second implementation of a ruled rule, and the
 * one that drifts. This only chooses which served number to show and whether
 * to say the other is decorative.
 */
export interface EffectiveStartDay {
  /** The day windows actually open on — or `null` for a word with no
   *  day-of-month anchor (Daily · Weekly · Fortnightly) and for a cycle with
   *  no first run, which nothing anchors yet. */
  day: number | null;
  /** What is stored, unchanged. */
  stored: number | null;
  /** The stored day is NOT the one used, so a screen must say so. */
  decorative: boolean;
}

export function effectiveStartDay(cycle: {
  start_day: number | null;
  effective_start_day: number | null;
  start_day_differs: boolean;
}): EffectiveStartDay {
  // The served effective day wins; the stored one is the fallback for a cycle
  // the engine has no anchor for, where it is all there is and is not wrong.
  const day = cycle.effective_start_day ?? cycle.start_day;
  return {
    day,
    stored: cycle.start_day,
    decorative:
      cycle.start_day_differs &&
      cycle.start_day !== null &&
      cycle.effective_start_day !== null &&
      cycle.start_day !== cycle.effective_start_day,
  };
}

/**
 * The cycles landing's Start-day cell: the day the cycle uses, and — only when
 * the stored one is decorative — a muted reminder of the number that is not.
 *
 * Both are shown deliberately. Showing only the effective day hides that the
 * operator's own field is being ignored; showing only the stored one is the
 * lie. The full sentence lives on the detail screen, where there is room.
 */
export function StartDayCell(props: {
  cycle: { start_day: number | null; effective_start_day: number | null; start_day_differs: boolean };
  t: Translator;
  dash: string;
}) {
  const { t, dash } = props;
  const effective = effectiveStartDay(props.cycle);
  if (effective.day === null) {
    return <>{dash}</>;
  }
  if (!effective.decorative) {
    return <>{effective.day}</>;
  }
  return (
    <span title={t("settings.cycles.startDay.decorative", {
      effective: effective.day,
      stored: effective.stored,
    })}>
      {effective.day}{" "}
      <span className={RC_MUTED}>{t("settings.cycles.startDay.saved", { stored: effective.stored })}</span>
    </span>
  );
}

/**
 * OQ-341's overlap warning, keyed on its CODE.
 *
 * ⚠ **AND THE SERVER'S OWN `detail` IS NOT RENDERED** — same reason
 * `scheduleGapKey` gives: it is English prose from a Python module and this
 * product ships eleven languages. An unknown code returns `null` and the
 * screen draws nothing, rather than a default sentence that would describe a
 * collision the server did not report (`frequencyKey` argues the posture).
 */
export function scheduleWarningKey(code: string | null | undefined): string | null {
  return code === "cycle_windows_overlap"
    ? "settings.cycles.schedule.warning.cycle_windows_overlap"
    : null;
}

// ── The addressable paths (W3-T5) ──────────────────────────────────────────
//
// ⚠ EVERY ONE OF THESE IS A URL BECAUSE A REFRESH USED TO LOSE THE WIZARD.
// SET-06/07 were `useState` inside the landing tab: three steps in, F5 put the
// user back on the list with nothing kept. B14 rule 3 does not require a URL,
// but BR-SHL-011 does for every other stateful surface in this product.

export const ROUTES_CYCLES_PATH = "/settings/reference-data/routes-cycles";

function under(...segments: string[]): string {
  return [ROUTES_CYCLES_PATH, ...segments.map((s) => encodeURIComponent(s))].join("/");
}

export function routeDetailPath(routeId: string): string {
  return under("routes", routeId);
}

export function cycleDetailPath(cycleId: string): string {
  return under("cycles", cycleId);
}

/** `null` = the creator; an id = the EDITOR, which opens PRE-FILLED (W3-T5). */
export function routeWizardPath(routeId: string | null): string {
  return routeId === null ? under("routes", "new") : `${under("routes", routeId)}/edit`;
}

export function cycleWizardPath(cycleId: string | null): string {
  return cycleId === null ? under("cycles", "new") : `${under("cycles", cycleId)}/edit`;
}

// ── Small Tailwind surfaces (B14 rule 21) ──────────────────────────────────

/** The quiet-text colour, written once. 65% of the text colour is what the
 *  prototype uses for a secondary line. */
export const RC_MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/** B14 rule 18 — a description caps at 80% of the content width, through the
 *  ONE `--desc-measure` token. `max-w-measure` is that token's utility. */
export const RC_DESC = `m-0 max-w-measure text-sm ${RC_MUTED}`;

export interface FactRow {
  label: string;
  value: ReactNode;
}

/**
 * The Facts rail both detail screens carry — label/value pairs down the right.
 *
 * ⚠ **THE ROUTE RAIL HAS NO READER ROW AND THE CYCLE RAIL SAYS "DEFAULTS"**
 * (B17 §3, D6 and D9). The screenshots draw an inline reader edit here and a
 * footnote reading *"Bill and due dates belong to the run, not the cycle"*.
 * Both were superseded by the PO's own rulings the same day the drawing landed.
 * The rail renders the rows its caller passes and invents none.
 */
export function FactsRail(props: { title: string; facts: readonly FactRow[]; footnote?: string }) {
  return (
    <aside
      className="flex w-full shrink-0 flex-col gap-3 border border-divider p-4 lg:w-72"
      aria-label={props.title}
      data-rc="facts-rail"
    >
      <p className="m-0 font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
        {props.title}
      </p>
      <dl className="m-0 flex flex-col gap-2.5">
        {props.facts.map((fact) => (
          <div key={fact.label} className="flex flex-col gap-0.5">
            <dt className={`text-sm ${RC_MUTED}`}>{fact.label}</dt>
            <dd className="m-0 text-base">{fact.value}</dd>
          </div>
        ))}
      </dl>
      {props.footnote !== undefined && <p className={RC_DESC}>{props.footnote}</p>}
    </aside>
  );
}

/**
 * A fact the SERVER does not serve, said out loud.
 *
 * ⚠ **THIS IS NOT AN EMPTY STATE AND MUST NOT READ LIKE ONE.** An empty table
 * claims "there is nothing here"; this claims "nothing here can be asked yet",
 * which is a different sentence about a different thing. Rendering a plausible
 * zero instead is the defect this repo has filed as `notCollected` twice
 * already.
 *
 * ⚠ **AMENDED 2026-08-23 (RC-W3c) — EVERY "NOTHING SERVES THIS" SENTENCE ON
 * THESE TWO SCREENS IS GONE, AND THE REASON MATTERS MORE THAN THE COUNT.** It
 * used to say four tabs in this wave had "a column behind them and no route in
 * front". RC-W3b and RC-W4b mounted all of them: the walk-order writer, Read
 * history, the route's accounts, the exclusion reasons, the uncovered-account
 * list and the run history are REAL, and every one of those sentences was
 * deleted rather than left standing. A stated absence has to be re-checked
 * when somebody else's lane ships — the whole of hard-won law 1, and G38's own
 * reasoning.
 *
 * ⚠ **SO WHAT IT DRAWS NOW IS TWO DIFFERENT THINGS, AND THE NEXT AGENT SHOULD
 * NOT CONFLATE THEM.** Both wear the same dashed frame because both answer
 * B14 rule 17 — *"what is missing, and the action that fills it"* — but:
 *
 *   · **an EMPTY STATE**: a route with no members, a cycle with no routes, a
 *     route nobody has walked, a cycle nobody has billed. The question was
 *     asked and answered, and the answer was nothing.
 *   · **AN UNRULED SILENCE**: `schedule_gap`. The engine could have answered
 *     and REFUSED to, because the rule it would need is not written. That one
 *     must never be softened into "no windows yet" — it is a decision the
 *     product owes, not a state of this tenant's data.
 */
export function StatedAbsence(props: { title: string; body: string; action?: ReactNode }) {
  return (
    <section
      className="flex flex-col items-start gap-2 border border-dashed border-divider p-4"
      role="note"
      data-rc="stated-absence"
    >
      <b className="text-base">{props.title}</b>
      <p className={RC_DESC}>{props.body}</p>
      {props.action}
    </section>
  );
}

/** A removable-chip row (B14 rule 9's shape, read-only here). */
export function ChipList(props: { items: readonly string[]; empty: ReactNode }) {
  if (props.items.length === 0) {
    return <>{props.empty}</>;
  }
  return (
    <span className="inline-flex flex-wrap gap-1">
      {props.items.map((item) => (
        <span key={item} className="border border-divider px-1.5 py-0.5 text-sm">
          {item}
        </span>
      ))}
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// THE PICKER TOOLBAR'S FILTER HALF — MULTI-SELECT, BECAUSE BR-MET-072 IS
// SIGNED AND SAYS "NEVER SINGLE-SELECT".
// ═══════════════════════════════════════════════════════════════════════════
/**
 * The area / assignment filter for a wizard picker, as B14 rule 12's chip row:
 * `[All] [Area: X ×] [Not on any route ×] [+ Filter ▾]`.
 *
 * ⚠ **WHY THIS IS NOT `components/FilterBar`, WHICH IS THE KIT'S OWN FILTER.**
 * `TableRequestState.filters` is `Record<string, string>` — ONE value per
 * dimension — and `FilterBar` renders exactly that. `BR-MET-072` is a
 * **CONFIRMED** rule in the PO's own words (*"all option 1 to many options will
 * be required"*): the area filter is *"MULTI-SELECT with an All option — one to
 * many, never single-select"*, selections OR together, and a backend test
 * (`test_area_filter_is_multi_select_and_ors`) holds the server to it.
 * Declaring `areas` in `TableConfig.filters` would therefore have cut a
 * ratified capability down to match the kit — the precise mistake
 * `UnitsListPage` records in its own `select` column comment, one rule further
 * on. The kit's own note says the same: widening `filters` to many values is an
 * API change, filed as `OQ-306` and not chosen.
 *
 * ⚠ **SO IT IS COMPOSED FROM THE KIT'S CHIPS RATHER THAN HAND-DRAWN.**
 * `ChipRow`, `ChipToggle` and `Chip` are `components/Chip.tsx` — the same three
 * `FilterBar` itself renders — so the chips here and the chips on every list in
 * the product are one visual decision (B14 rule 36: *compose the kit*). What is
 * local is only the SEMANTICS the signed rule requires, and the trigger borrows
 * `buttonClasses("secondary", "sm")` for the same reason.
 *
 * ⚠ **THE GENERAL FIX IS A KIT MULTI-SELECT FILTER, AND IT IS NOT THIS LANE'S
 * TO MAKE.** `OQ-306` CLOSED on 2026-10-02 for the SERVICE dimension only
 * (`isMultiSelectFilter`, `tableTypes.ts`); moving this area filter onto the
 * kit is a separate change nobody has asked for yet. Until then, two screens
 * sharing one implementation here is one pencil, not three.
 */
export function PickerFilterChips(props: {
  /** Every area a premises could carry, as value/label pairs. */
  areaOptions: readonly { value: string; label: string }[];
  /** The areas currently applied. OR-combined (BR-MET-072). */
  areas: readonly string[];
  onAreas: (next: string[]) => void;
  /** The second dimension, present only where the screen has one. */
  unassigned?: { on: boolean; onChange: (next: boolean) => void; label: string; removeLabel: string };
  /** `All` — the resting state, which applies NO filter (BR-MET-072). */
  allLabel: string;
  addLabel: string;
  areaChipLabel: (area: string) => string;
  removeAreaLabel: (area: string) => string;
}) {
  const unassignedOn = props.unassigned?.on === true;
  const none = props.areas.length === 0 && !unassignedOn;
  return (
    <ChipRow>
      {/* Resting = inverted, exactly as `FilterBar` paints its own All chip.
          Clicking it clears BOTH dimensions, which is the only reading of
          "All" that leaves nothing applied. */}
      <ChipToggle
        selected={none}
        onClick={() => {
          props.onAreas([]);
          props.unassigned?.onChange(false);
        }}
      >
        {props.allLabel}
      </ChipToggle>
      {props.areas.map((area) => (
        <Chip
          key={area}
          onRemove={() => props.onAreas(props.areas.filter((one) => one !== area))}
          removeLabel={props.removeAreaLabel(area)}
        >
          {props.areaChipLabel(area)}
        </Chip>
      ))}
      {unassignedOn && props.unassigned !== undefined && (
        <Chip
          onRemove={() => props.unassigned?.onChange(false)}
          removeLabel={props.unassigned.removeLabel}
        >
          {props.unassigned.label}
        </Chip>
      )}
      {/* The add control. A `select` rather than a panel of checkboxes: rule 8
          makes a 5+ list searchable and every browser type-filters a select,
          and an area tree is exactly the list that grows past five. It resets
          to its own prompt after each pick so it never reads as a value. */}
      <select
        className={`${FILTER_TRIGGER_KIT} cursor-pointer`}
        value=""
        aria-label={props.addLabel}
        onChange={(event) => {
          const value = event.target.value;
          if (value === UNASSIGNED_OPTION) {
            props.unassigned?.onChange(true);
          } else if (value !== "" && !props.areas.includes(value)) {
            props.onAreas([...props.areas, value]);
          }
        }}
      >
        <option value="">{props.addLabel}</option>
        {props.unassigned !== undefined && !unassignedOn && (
          <option value={UNASSIGNED_OPTION}>{props.unassigned.label}</option>
        )}
        {props.areaOptions
          .filter((one) => !props.areas.includes(one.value))
          .map((one) => (
            <option key={one.value} value={one.value}>
              {one.label}
            </option>
          ))}
      </select>
    </ChipRow>
  );
}

/** The add control's sentinel for the second dimension — never an area code. */
export const UNASSIGNED_OPTION = "__unassigned";

/**
 * The add control's look, borrowed from the kit — `FilterBar`'s own
 * `PANEL_TRIGGER_KIT`, so the two `+ Filter` triggers in the product cannot
 * drift apart.
 *
 * ⚠ **HOISTED OUT OF THE `className` ON PURPOSE, AND A GATE IS WHY.** Written
 * inline as `` `${buttonClasses("secondary", "sm")} …` ``, the Route B class
 * scanner reads the string literal `"secondary"` as a CLASS TOKEN, finds no
 * stylesheet declaring it and no Tailwind rule compiling it, and fails the file
 * — correctly, by its own rule, over an argument that was never a class. It
 * caught this on the commit that added it. `FilterBar` hoists for the same
 * reason; the constant is the fix and not a `// eslint-disable`-shaped silence.
 */
const FILTER_TRIGGER_KIT = buttonClasses("secondary", "sm");

/* ⚠ **`sortPickerRows` STOOD HERE AND IS DELETED (`DEF-MET-5743`).** It sorted
   a picker's rows in the browser, and its own docstring gave the reason: *"the
   two picker endpoints answer a PLAIN ARRAY of everything that matches … they
   take no `sort`, `page` or `per`"*. **Both pickers take all three now**, so
   that claim was false and the function had no callers left — and a sort over
   one page orders the page rather than the list, which is a table whose first
   row is not the first row. Deleted rather than left standing: hard-won law 1,
   a comment describing a gap that has closed, and law 2's mirror — dead code
   that reads as a supported way to do this. */

/**
 * BR-MET-080 · the landing's coverage sentence, and **D13 decides what it
 * says.**
 *
 * The screenshot's SET-07D coverage tab offers a per-row *"Assign a cycle →"*.
 * The PO ruled: *"Cycles are not directlya ssing to accounts it is derived and
 * determined at the time of bill run"*. So the sentence names what the accounts
 * actually LACK — a route — and the remedy is to route them; there is no
 * account-level cycle assignment anywhere in this product, and
 * `SettingsRoutesCyclesTab.test.tsx` asserts its absence rather than trusting
 * that nobody adds one.
 */
export function coverageSentenceKey(uncovered: number): string {
  return uncovered === 0 ? "settings.cycles.coverage.allCovered" : "settings.cycles.coverage.gap";
}

/** The window a cycle actually has, as a KEY — never a guessed date. */
export function windowSourceKey(source: string | null): string {
  if (source === "derived") {
    return "settings.cycles.window.derived";
  }
  if (source === "stored") {
    return "settings.cycles.window.stored";
  }
  return "settings.cycles.window.none";
}

/** "1–3", the day-of-month shape — never a rendered calendar date.
 *
 *  ⚠ **FROM THE EFFECTIVE START DAY (OQ-340), NOT THE STORED ONE.** This is
 *  the WINDOW fact that sits under *"Derived, not stored"*; deriving it from a
 *  day the engine ignores would make that caption false in the one place it is
 *  printed. */
export function startWindowLabel(cycle: CycleRow, dash: string): string {
  const start = effectiveStartDay(cycle).day;
  if (start === null || cycle.days_to_complete === null) {
    return dash;
  }
  const end = start + cycle.days_to_complete - 1;
  return cycle.days_to_complete === 1 ? `${start}` : `${start}–${end}`;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-029 RC-W3 (B17 §7) — the screens wave
// generated: 2026-08-23 by the RC-W3 frontend lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (routesCyclesShared.test.ts)
// [CR-029 RC-W3c 2026-08-23] AMENDED — `route_premises_orders` HAS an endpoint now (RC-W3b), so `orderRouteAbsent` is deleted and `stopsFromServedOrder` reads the ruled walk back. Two helpers added for RC-W2's proposal: `windowStatusKey` (the two served words, NULL for a third) and `scheduleGapKey` (the three unruled cases as sentences).
// [CR-029 RC-W6b 2026-08-23] AMENDED — OQ-340/341 are RULED, so two helpers land and two change meaning. `effectiveStartDay` + `StartDayCell` are the ONE place a screen decides which start day to show (the first run wins; the stored day can be decorative and is NAMED as such rather than silently swapped), and `startWindowLabel` reads through it — a window derived from a day the engine ignores would make its own *"Derived, not stored"* caption false. `scheduleWarningKey` is OQ-341's warning, keyed on the code like its `scheduleGapKey` sibling. NOTHING here computes a day: `period_engine.effective_start_day` is served and is the one implementation.
// exceptions: E3 `premisesStops` survives only as the FALLBACK for a route nobody has sequenced — it orders by the superseded per-unit `walk_order`, which the server now projects from the ruled per-premises order, and the value is never rendered · E3 `scheduleGapKey` returns a sentence key and NEVER the server's `code` or its English `detail`: OQ-339/340/341 are OPEN, G28 forbids provenance on a customer screen, and `detail` is untranslated in ten of eleven languages
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
