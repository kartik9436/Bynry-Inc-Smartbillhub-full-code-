// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-012 (S25 reads list) · US-MET-013 (S29 read detail drawer) ·
//           US-MET-019 (S25 Needs-attention landing)
//           Screens: S25, S29
// Rules:    BR-MET-016 (consumers see lineage HEADS — a corrected read appears once) ·
//           BR-MET-021 (one primary status per read, from the A5 vocabulary) ·
//           BR-MET-053 (lifecycle: committed → BILLED(locked); corrections SUPERSEDE) ·
//           BR-MET-055 (server pagination + the 2-year hot window; no unbounded list) ·
//           BR-MET-056 (the drawer renders STORED data — the math, the thresholds and
//           the chain all come from storage and are never re-derived here) ·
//           BR-MET-059 (the channel model) · BR-MET-060 (Reads lands on Needs attention) ·
//           BR-SHL-011 (URL grammar) · BR-SHL-025 (a control you may not use renders
//           disabled WITH its reason) · BR-SHL-034 (one date formatter)
// ───────────────────────────────────────────────────────
// The pieces S25 and S29 share.
//
// Two laws are enforced by CONSTRUCTION in this file rather than by care:
//
//   1. **A consumption is never rendered without its unit** (CLAUDE.md rule 3).
//      `UsageCell` takes the whole row and reads the SERVER's `usage_display`
//      ("684.000000 kWh"). It has no prop that could be handed a bare number,
//      so a usage column cannot be built here that loses the unit.
//
//   2. **Nothing recomputes metering's arithmetic** (BR-MET-056). `mathLine`
//      assembles the stored OPERANDS into the sentence the rule asks for —
//      `(current − prior) × multiplier = usage` — and takes the result from
//      `usage_display`. It never evaluates the expression. If it did, this file
//      would be a second implementation of consumption that can disagree with
//      the bill.
//
// The flag reason is rendered from the same stored bag (BR-MET-022, "stored
// self-describing (no re-derivation needed for display)") — nothing here
// recomputes a threshold.
//
// ⚠ **BUT IT IS NO LONGER WALKED AND LABELLED, AND THIS PARAGRAPH USED TO SAY
// THE OPPOSITE (`DEF-MET-5204`, 2026-09-14).** It read: *"that is also why
// there is no per-rule sentence template here — a rule added server-side
// tomorrow renders correctly today."* **It did not render correctly.** Walking
// the bag put the engine's own vocabulary on a clerk's screen: `basis`,
// `occupied` and `plan_id` as FIELD LABELS, and the sentence
// `no active account on the unit (BR-MET-036)` as a value, seen on 2 of 2
// readings opened in a browser. B14 rule 31 names `BR-…` by family.
//
// `outcomeSentence` below is `B33`'s answer and it reads every key BY NAME, so
// the guarantee is structural: a key nobody has named cannot reach the DOM,
// and a rule nobody has taught this screen renders its NAME and nothing else.
import { useTranslation } from "react-i18next";

import {
  READ_STATUS_ESTIMATED,
  READ_STATUS_FLAGGED,
  READ_STATUS_OK,
  isNonConsumptionChannel,
} from "@/api/endpoints";
import type { ReadRow, ReadRuleOutcome } from "@/api/endpoints";
import { StatusPill } from "@/components/StatusPill";
import { formatQuantity } from "@/components/UnitCell";
import type { StatusTone } from "@/components/StatusPill";
import type { Translator } from "@/features/tenancy/settingsShared";

import { PeakQuantity } from "./demandShared";
import { Dash } from "./meteringShared";

import "./reads.css";

/** CR-018 Phase 1 §4 — the muted ink, color-mix written long-hand in srgb. */
const MUTED65 = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/**
 * BR-MET-163 (DEF-899) — **a person, rendered as a person.**
 *
 * The compliance panel printed `Uploaded by  01a01d99-d617-7aa9-9f07-…` to a
 * clerk who wanted a NAME, with a human-formatted timestamp in the row
 * directly beneath it, so the panel was half-translated and looked considered.
 * A UUID is a valid string: the field was present, populated, correctly typed
 * and rendered without error, and no gate in this repo can tell a primary key
 * from a name because to the code they are the same type.
 *
 * Three states, and the middle one is the whole point:
 *
 *   · **a name** — what a reader is shown, with the id on `title` as evidence;
 *   · **an id we could not resolve to a person** — said in WORDS, id still on
 *     `title`. The stamp outlives any user row (BR-AUD-003's own posture), so
 *     this is a real state and not an error;
 *   · **no actor at all** — the em dash, unchanged.
 *
 * ⚠ **THE NAME IS SERVED, NOT LOOKED UP HERE.** `GET /users` is
 * System-Admin-only and the reader this defect is about is a Billing Clerk, so
 * a browser-side resolve would 403 for exactly the person who needs the answer.
 * The server resolves it through audit's own `actor_names` seam.
 */
export function ActorName(props: { id: string | null; name: string | null; t: Translator }) {
  const { id, name, t } = props;
  if (id === null) {
    return <Dash />;
  }
  if (name === null || name === "") {
    return (
      <span className={MUTED65} title={id}>
        {t("metering.read.compliance.actorUnresolved")}
      </span>
    );
  }
  return <span title={id}>{name}</span>;
}

// ── Routes and URL state (BR-SHL-011; tenant-relative like every route here) ─

/** S25. SHELL_NAV's own `reads` parent path, so the sidebar item lands here. */
export const READS_ROUTE = "/reads";

/**
 * S28 — Upload reads (DEF-115). A ROUTE rather than a modal, for the same two
 * reasons S16 and S68 are: a half-filled five-step import must survive a
 * refresh and be linkable, and a browser Back must leave the wizard rather than
 * unwinding it a step at a time.
 *
 * The segment is STATIC, so React Router ranks it above nothing else here —
 * `/reads` takes no id parameter (S29 rides on `?read=`), so there is no id
 * this path could be mistaken for.
 */
export const READS_UPLOAD_ROUTE = "/reads/upload";

/**
 * S29 — a FULL PAGE as of 2026-08-26 (CR-038 W5). r10's RDS-04 draws it as a
 * drawer, and the PO overrode that presentation in as many words: *"i want
 * page to be open for consitency - we dont open side panel"*. The id segment
 * sits BELOW the static `/reads/*` siblings in App.tsx (upload · estimate ·
 * routes · cycles), which React Router ranks above it anyway — the DEF-520
 * habit, written down.
 */
export const READ_DETAIL_ROUTE_PATTERN = "/reads/:readId";

export function readDetailPath(readId: string): string {
  return `/reads/${readId}`;
}

/**
 * The RETIRED drawer's URL state, kept only as a REDIRECT: `?read=<id>` links
 * live in tickets (that linkability was the param's whole point), so S25
 * forwards them to the page rather than letting them silently open nothing —
 * the same posture as `LEGACY_SETTINGS_TAB_PATHS`.
 */
export const READ_PARAM = "read";
export const READS_TAB_PARAM = "tab";
/** BR-MET-055's explicit opt-in. A top-level query param, NOT an `f.` filter. */
export const READS_ARCHIVE_PARAM = "archive";

export const READS_TAB_ALL = "all";
/**
 * The cycles tab — the blueprint's entry 15, and it REPLACES TWO DOORLESS
 * SCREENS. `/:tenant/reads/routes` and `/:tenant/reads/cycles` were both routed
 * and built and neither had an inbound link; hard-won law 2's mirror is a live
 * screen behind a dead control, and these were live screens behind no control
 * at all. The two addresses are KEPT and redirect here — there are tickets with
 * those URLs in them.
 */
export const READS_TAB_CYCLES = "cycles";
export const READS_TABS = [READS_TAB_ALL, READS_TAB_CYCLES] as const;
export type ReadsTab = (typeof READS_TABS)[number];

/**
 * **THE LANDING IS `All reads`, ON EVERY OPEN.**
 *
 * ⚠ **THIS WAS `Needs attention` UNTIL 2026-09-12, AND THE RULE THAT SAID SO IS
 * SUPERSEDED.** `BR-MET-060` — *"Reads screen opens on Needs attention
 * (Missing/Flagged/Disputed KPI chips + drill-in); full list one tab away"* —
 * is stamped **SUPERSEDED 2026-09-12** on the PO's own words: *"Need Attention
 * — does not add any value."* `US-MET-019`, the story that built the three
 * counts, is retired with it.
 *
 * An unknown or absent `?tab=` falls back here rather than erroring
 * (BR-SHL-011's spirit), which makes the fallback and the landing rule the same
 * line of code — and it is also what carries the retired tab's own links: a
 * bookmarked `?tab=attention` lands on the readings instead of on a tab that no
 * longer exists.
 */
export function readsTabFromParam(raw: string | null): ReadsTab {
  return (READS_TABS as readonly string[]).includes(raw ?? "")
    ? (raw as ReadsTab)
    : READS_TAB_ALL;
}

// ── Status vocabulary (BR-MET-021 + the BR-MET-052 catalog additions) ──────

/**
 * `ok` is the only clean status; `estimated` is a LAWFUL bill input that
 * travels flagged (BR-MET-029), so it is warning-toned rather than neutral — a
 * customer disputing an estimated bill has to be able to see it was one.
 * Everything else is a validation flag, and the two that are hard errors in the
 * catalog (BR-MET-052) carry the danger tone.
 */
const DANGER_STATUSES = new Set([
  "negative_usage",
  "retired_meter",
  "unknown_meter",
  "duplicate",
  "missing",
  "unit_missing",
]);

export function readStatusTone(status: string): StatusTone {
  if (status === READ_STATUS_OK) {
    return "success";
  }
  if (DANGER_STATUSES.has(status)) {
    return "danger";
  }
  return "warning"; // estimated + every remaining flag
}

/** The pill. Label from the catalog, VERBATIM fallback for a status we do not know. */
export function ReadStatusCell(props: { status: string; t: Translator }) {
  return (
    <StatusPill tone={readStatusTone(props.status)}>
      {props.t(`metering.reads.status.${props.status}`, { defaultValue: props.status })}
    </StatusPill>
  );
}

/**
 * BR-MET-1189 (PO 2026-10-04, DEF-WRK-9642): where a register holds two
 * readings on one date, which one counts. `true` — the highest approved and
 * validated, the one billing uses; `false` — kept as history. `null` — the
 * reading is alone on its date, so there is nothing to mark and nothing draws.
 */
export function CountedReadingPill(props: { counts: boolean | null | undefined; t: Translator }) {
  if (props.counts === true) {
    return <StatusPill tone="success">{props.t("assets.reads.counts")}</StatusPill>;
  }
  if (props.counts === false) {
    return <StatusPill tone="muted">{props.t("assets.reads.not_counted")}</StatusPill>;
  }
  return null;
}

/**
 * CLAUDE.md rule 3, made structural: the only usage renderer takes the ROW and
 * prints the server's `usage_display`. There is no `amount` prop to pass a bare
 * number into, which is why a usage column here cannot lose its unit.
 */
export function UsageCell(props: { row: ReadRow }) {
  const { t } = useTranslation();
  if (props.row.is_peak) {
    // ── BR-MET-051 · BR-MET-143: a PEAK is not energy ───────────────────────
    // ✅ **AMENDED 2026-08-27 (DEF-797).** This cell used to render
    // `current_value` and NOT the served consumption, and the reason it gave
    // was correct at the time: *"BR-MET-019's `(current − prior) × multiplier`
    // runs on every channel, and on a demand register that delta is the
    // difference between two peaks — a number nothing bills."*
    //
    // That is now fixed at the WRITE rather than worked around here: a maximum
    // register commits BR-MET-051's own figure — *"manual demand-register
    // VALUE at cycle read"* — so `consumption` on a demand row IS the peak the
    // customer is billed for, and `unit` is the register's own `kW`. So the
    // cell shows the SERVER's composed figure like every other row, which is
    // BR-MET-056 (rendered from stored values, never re-derived) and removes
    // the one place this screen did arithmetic of its own.
    return (
      <PeakQuantity quantity={props.row.consumption} unit={props.row.unit} t={t} />
    );
  }
  if (props.row.usage_display === null) {
    // An estimate with no consumption, or a read the engine refused to total.
    return <Dash>{t("metering.reads.usageUnknown")}</Dash>;
  }
  return (
    <span className="rd-usage">
      {props.row.usage_display}
      {/* ⚠ **BR-MET-135 / BR-AST-029 — THIS COLUMN IS HEADED "Usage", AND A
          GENERATION OR EXPORT FIGURE IS NOT USAGE.** The rule, verbatim: a
          device's produced quantity is *"distinct from `export` … and never
          summed with consumption"*. Nothing here adds anything up — but a
          612 kWh sitting silently in a column called Usage is the same claim
          made by a label, and a person reading the list totals it in their
          head. So the register NAMES ITSELF beside the number, on every
          non-consumption row.

          Tailwind utilities, no stylesheet class (B14 rule 21). */}
      {isNonConsumptionChannel(props.row.channel) && (
        <span
          className="ml-1 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
          data-cell="non-consumption-channel"
          title={t("metering.reads.notConsumptionWhy")}
        >
          {t(`metering.reads.channel.${props.row.channel}`, {
            defaultValue: props.row.channel,
          })}
        </span>
      )}
      {props.row.status === READ_STATUS_ESTIMATED && (
        <span className="rd-est" title={t("metering.reads.estimatedWhy")}>
          {" "}
          {t("metering.reads.estimatedBadge")}
        </span>
      )}
    </span>
  );
}

// ── The math line (BR-MET-056 "math shown") ────────────────────────────────

/**
 * `(current − prior) × multiplier = usage · N days`, assembled from the five
 * STORED values and never evaluated. The `=` side is the server's own
 * `usage_display`, so the number in the sentence is the number that bills.
 *
 * Returns null when the read carries no register pair — an estimate has a
 * consumption and NO current_value by BR-MET-028, and printing "(— − —) × 1"
 * would be a sentence about nothing. The caller renders the estimate line
 * instead.
 */
export function mathLine(row: ReadRow, t: Translator): string | null {
  if (row.current_value === null || row.prior_value === null || row.usage_display === null) {
    return null;
  }
  return t("metering.read.mathLine", {
    current: row.current_value,
    prior: row.prior_value,
    multiplier: row.multiplier ?? "1",
    usage: row.usage_display,
  });
}

// ── Stored rule outcomes (BR-MET-022 self-describing; never re-derived) ────

export const OUTCOME_OK = "ok";
export const OUTCOME_NOT_EVALUATED = "not_evaluated";

/** The verdicts that explain a flag: everything the engine did not pass. */
export function flaggedOutcomes(row: ReadRow): ReadRuleOutcome[] {
  return row.rule_outcomes.filter(
    (outcome) => outcome.severity !== OUTCOME_OK && outcome.severity !== OUTCOME_NOT_EVALUATED,
  );
}

/**
 * The honest half of a clean read (CLAUDE.md law 1): rules that could NOT run.
 * A read showing "passed every rule" while four rules never executed is the
 * comment-as-guarantee failure in data form.
 */
export function unevaluatedOutcomes(row: ReadRow): ReadRuleOutcome[] {
  return row.rule_outcomes.filter((outcome) => outcome.severity === OUTCOME_NOT_EVALUATED);
}

/**
 * The prototype's "Rule outcomes: 10/10 passed". COUNTING stored verdicts is
 * not re-deriving one — no threshold is compared here, and `evaluated` excludes
 * the rules that never ran so the fraction cannot flatter the read.
 */
export function outcomeTally(row: ReadRow): { passed: number; evaluated: number } {
  const evaluated = row.rule_outcomes.filter(
    (outcome) => outcome.severity !== OUTCOME_NOT_EVALUATED,
  );
  return {
    passed: evaluated.filter((outcome) => outcome.severity === OUTCOME_OK).length,
    evaluated: evaluated.length,
  };
}

/**
 * One stored `detail` value, rendered for reading. Scalars print verbatim —
 * the engine stores full-precision decimal STRINGS and rounding one here would
 * be this screen deciding a precision nobody signed. Arrays are the bound pairs
 * (`flag_bounds: [25, 35]`).
 */
export function detailValueText(value: unknown, t: Translator): string {
  if (Array.isArray(value)) {
    return value.map((entry) => detailValueText(entry, t)).join(" – ");
  }
  if (typeof value === "boolean") {
    return value ? t("metering.yes") : t("metering.no");
  }
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

/**
 * ⚠ **B33 — ONE PROSE LINE PER RULE, COMPOSED FROM NAMED KEYS (2026-09-14).**
 *
 * The drawing (blueprint entry 03, ⑦ `FLAGS`) puts ONE sentence under the bold
 * rule name — *"154% of a 5.2 kWh average · threshold 150% · 3 readings in the
 * average"* — and no severity badge. What shipped instead was the whole stored
 * bag as a `<dl>` with the RAW KEY as each label, and that is `DEF-MET-5204`:
 * every vacant-unit flag rendered `basis · no active account on the unit
 * (BR-MET-036)` to a clerk, on 2 of 2 readings opened in a browser. B14 rule 31
 * puts no rule number on screen; rule 32 keeps internal codes out of
 * clerk-facing copy entirely.
 *
 * ⚠ **THE FILE HEADER USED TO ARGUE AGAINST DOING THIS, and it was wrong** —
 * *"there is no per-rule sentence template here, so a rule added server-side
 * tomorrow renders correctly today"*. It did not render correctly: it rendered
 * the engine's own vocabulary at a clerk. FIVE stored bags carry a `basis`
 * sentence ending in an id (`BR-MET-036`, `OQ-009`, `CR-054`, `BR-MET-122`,
 * `BR-MET-049`) and four of them sit on a severity that renders. The header is
 * amended above.
 *
 * **THE GUARANTEE IS BY CONSTRUCTION, NOT BY CARE:** every arm below reads keys
 * BY NAME. Nothing iterates the bag, so a key nobody named here — `basis`,
 * `plan_id`, `rule_ref`, `occupied`, `resolutions`, `existing_read_id` — cannot
 * reach the DOM however the engine grows. A rule with no arm renders its NAME
 * and nothing else: honest and silent, rather than raw.
 */
const DECIMAL_TEXT = /^-?\d+(?:\.\d+)?$/;

function detailString(bag: Record<string, unknown>, key: string): string | null {
  const value = bag[key];
  return typeof value === "string" && value.trim() !== "" ? value.trim() : null;
}

/**
 * A stored figure, rounded for DISPLAY and never re-derived. The engine keeps
 * decimals as strings at BR-MET-019's 6dp scale; `formatQuantity` rounds to two
 * places and strips the zeros `NUMERIC(18,6)` puts on the wire — the same
 * treatment `D6` asks for where one screen spelled a quantity two ways. The
 * arithmetic is untouched (B4/B5 are ❄️ FROZEN).
 */
function detailNumber(bag: Record<string, unknown>, key: string): string | null {
  const value = bag[key];
  if (typeof value === "number") {
    return String(value);
  }
  return typeof value === "string" && DECIMAL_TEXT.test(value.trim())
    ? formatQuantity(value.trim())
    : null;
}

/** A bounds pair (`flag_bounds: [25, 35]`), formatted, or null if it is not one. */
function detailPair(bag: Record<string, unknown>, key: string): [string, string] | null {
  const value = bag[key];
  if (!Array.isArray(value) || value.length !== 2) {
    return null;
  }
  const low = detailNumber({ v: value[0] }, "v");
  const high = detailNumber({ v: value[1] }, "v");
  return low === null || high === null ? null : [low, high];
}

/** Join the clauses the drawing separates with a middle dot, DROPPING absences
 *  rather than printing "— · — · —". A rule whose every clause is missing gets
 *  no line at all. */
function clauses(parts: (string | null)[]): string | null {
  const kept = parts.filter((part): part is string => part !== null && part !== "");
  return kept.length === 0 ? null : kept.join(" · ");
}

/**
 * `B33`'s prose line for ONE stored verdict, or `null` when this rule has
 * nothing a clerk can read. Each clause is a separate FACT capped at six words
 * by B14 rule 33, which is why they are joined rather than written as one
 * sentence.
 */
export function outcomeSentence(outcome: ReadRuleOutcome, t: Translator): string | null {
  const bag = outcome.detail;
  const unit = detailString(bag, "unit");
  // CLAUDE.md hard rule 3 — a quantity never travels without its unit, so a
  // figure whose bag carries no unit is DROPPED rather than printed bare.
  const quantity = (key: string): string | null => {
    const figure = detailNumber(bag, key);
    return figure === null || unit === null ? null : `${figure} ${unit}`;
  };

  switch (outcome.rule) {
    case "high":
    case "low": {
      const ratio = detailNumber(bag, "ratio_pct");
      const average = quantity("trailing_average");
      const threshold = detailNumber(bag, "threshold_pct");
      const reads = detailNumber(bag, "trailing_reads");
      return clauses([
        ratio !== null && average !== null
          ? t("metering.read.flag.ratio", { ratio, average })
          : null,
        threshold !== null ? t("metering.read.flag.threshold", { threshold }) : null,
        reads !== null ? t("metering.read.flag.trailing", { reads }) : null,
      ]);
    }
    case "zero":
      return t("metering.read.flag.zero");
    case "days_threshold": {
      const days = detailNumber(bag, "days");
      const hard = bag.hard === true ? detailPair(bag, "hard_bounds") : null;
      const bounds = hard ?? detailPair(bag, "flag_bounds");
      return clauses([
        days !== null ? t("metering.read.flag.days", { days }) : null,
        bounds !== null
          ? t("metering.read.flag.bounds", { low: bounds[0], high: bounds[1] })
          : null,
      ]);
    }
    case "out_of_window": {
      const start = detailString(bag, "window_start");
      const end = detailString(bag, "window_end");
      return start !== null && end !== null
        ? t("metering.read.flag.window", { start, end })
        : null;
    }
    case "vacant_unit":
      // ⚠ **THE RULE ID LEAVES THE SCREEN HERE (`DEF-MET-5204`, `D3`).** The
      // stored bag says `basis: "no active account on the unit (BR-MET-036)"`
      // and nothing reads it. The FACT is stated in the catalogue in the
      // clerk's words and the provenance stays in the code, which is B14 rule
      // 31's own instruction: *"the provenance is not deleted, it MOVES to the
      // code comment beside the string."* Every read ALREADY COMMITTED carries
      // the old string and every one of them now renders this sentence — which
      // a copy edit on the server could never have done.
      return t("metering.read.flag.vacant");
    case "rollover": {
      const wrapped = quantity("wrapped_delta") ?? quantity("consumption");
      const digits = detailNumber(bag, "register_digits");
      return clauses([
        wrapped !== null ? t("metering.read.flag.rollover", { wrapped }) : null,
        digits !== null ? t("metering.read.flag.digits", { digits }) : null,
      ]);
    }
    case "negative_usage": {
      const drop = detailNumber(bag, "drop");
      return drop === null ? null : t("metering.read.flag.negative", { drop });
    }
    case "mismatch": {
      const gap = detailNumber(bag, "gap_pct");
      const tolerance = detailNumber(bag, "tolerance_pct");
      return clauses([
        gap !== null ? t("metering.read.flag.mismatch", { gap }) : null,
        tolerance !== null ? t("metering.read.flag.tolerance", { tolerance }) : null,
      ]);
    }
    case "tou_sum_sanity": {
      const total = quantity("total");
      const summed = quantity("window_sum");
      return total !== null && summed !== null
        ? t("metering.read.flag.touSum", { summed, total })
        : null;
    }
    case "duplicate": {
      const row = detailNumber(bag, "first_row_no");
      return row === null
        ? t("metering.read.flag.duplicate")
        : t("metering.read.flag.duplicateRow", { row });
    }
    case "cycle_membership": {
      // BR-MET-122 names BOTH cycles, and it names them by their CODES.
      const meterCycle = detailString(bag, "meter_cycle");
      const fileCycle = detailString(bag, "file_cycle");
      return fileCycle === null
        ? null
        : meterCycle === null
          ? t("metering.read.flag.cycleNone", { file: fileCycle })
          : t("metering.read.flag.cycleOther", { cycle: meterCycle, file: fileCycle });
    }
    case "row_key": {
      const was = detailString(bag, "keyed_meter");
      const now = detailString(bag, "meter");
      return was === null || now === null
        ? null
        : t("metering.read.flag.rowKey", { was, now });
    }
    case "service_coherence": {
      const stated = detailString(bag, "stated_service");
      const meterService = detailString(bag, "meter_service");
      return stated === null || meterService === null
        ? null
        : t("metering.read.flag.service", {
            stated,
            service: t(`rating.service.${meterService}`, { defaultValue: meterService }),
          });
    }
    case "unit_mismatch": {
      const read = detailString(bag, "read_uom");
      const priced = detailString(bag, "pricing_uom");
      return read === null || priced === null
        ? null
        : t("metering.read.flag.unitMismatch", { read, priced });
    }
    case "retired_meter": {
      const retired = detailString(bag, "retired_on");
      return retired === null ? null : t("metering.read.flag.retired", { on: retired });
    }
    case "unknown_meter":
      return t("metering.read.flag.unknownMeter");
    case "unit_missing":
      return t("metering.read.flag.unitMissing");
    case "generation_channel":
      return t("metering.read.flag.generation");
    case "export_not_net":
      return t("metering.read.flag.exportNotNet");
    default:
      // A rule this screen has never been taught renders its NAME alone. That
      // is hard-won law 1's shape: saying nothing is honest, and printing the
      // engine's own bag is the thing this function exists to stop.
      return null;
  }
}

/** A stored `reason` value (why a rule could not run) in plain language. */
export function reasonText(reason: unknown, t: Translator): string {
  return typeof reason === "string"
    ? t(`metering.read.reason.${reason}`, { defaultValue: reason })
    : detailValueText(reason, t);
}

// ── Where the retired tiles' content went (BR-MET-060 SUPERSEDED) ─────────
//
// `US-MET-019`'s three tiles are withdrawn with the tab that held them, and two
// of the three counts SURVIVE THE MOVE as a filter click on this same list:
// **Flagged** is the `status` filter and **Disputed** is the `disputed` filter,
// each counting with the very predicate its tile used, so nothing a clerk could
// reach is lost. **Missing does not survive and never had a filter** — the
// server cannot slice the reads list that way — and it moves to the cycle
// detail, which is the only place the number means anything: a cycle has a
// window and an expected set, and *"short by five"* is a sentence about a cycle.
//
// ⚠ **ONE THING IS GENUINELY LOST AND IT IS RECORDED RATHER THAN REBUILT:**
// there is no longer one place saying *"nothing needs attention"* across the
// whole tenant. Per cycle, yes; across the tenant, no. That is a cost of the
// ruling, not a gap for the next lane to fill somewhere else.
//
// The two constants stay because the FILTERS stay — they are what the `+ Filter`
// panel writes, and they are the drill-in targets any other screen uses.

/**
 * A slice of the SAME list query with its filter pre-applied — the count and
 * the slice cannot disagree because they are one question asked twice.
 * `flagged` is the server's own composite status (BR-MET-021/052).
 */
export const CHIP_FLAGGED_FILTER = { status: READ_STATUS_FLAGGED } as const;

/**
 * The Disputed chip's drill-in — LIVE as of 2026-08-16 (US-MET-019 TC-4).
 *
 * It could not exist before, and the reason is worth keeping: `GET /reads`
 * declared six filters (route · status · cycle · service · source · channel),
 * none of which selected a dispute marker, and BE-05 **IGNORES** an undeclared
 * `f.` param — so a "Disputed" button would have returned the WHOLE list while
 * looking like a filtered slice. The server declares `disputed` now (metering
 * `selectors.READ_FILTERS`) and it uses the SAME predicate the chip counts —
 * set and not cleared — so the count and the slice cannot disagree.
 */
export const CHIP_DISPUTED_FILTER = { disputed: "true" } as const;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-012@34f14b6 (story+rules snapshot hash — EP-MET-04 list story; co-stories US-MET-013 · US-MET-019 @34f14b6)
// generated: 2026-08-11 by story-coder v1 (W2 reads frontend lane — S25/S29) · AMENDED 2026-08-27 (BR-MET-163 — `ActorName` lands here rather than on either page, because S29 and S28 both render an uploader and two copies is how a vocabulary drifts)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see ReadsListPage.tsx's trailer — one lane, one gate run
// exceptions: [US-MET-013 dispute lane 2026-08-16] `DISPUTED_DRILL_UNAVAILABLE` is GONE and `CHIP_DISPUTED_FILTER` replaces it: the server declares a `disputed` filter now and counts with the same predicate, so the chip and its slice cannot disagree. `MISSING_DRILL_UNAVAILABLE` is GONE as of 2026-09-14: it was the Missing TILE's caption key and `BR-MET-060` is SUPERSEDED, so the tile it captioned no longer exists. The reason it existed is unchanged and now lives on the cycle detail, where a window and an expected set make the number mean something · E4 the flag reason renders as LABELLED STORED KEY/VALUES rather than a per-rule sentence: BR-MET-022 stores each outcome "self-describing (no re-derivation needed for display)", and a sentence template per rule would have to be extended every time the engine gains a rule — this renders the ones it has now and the ones it gains later, identically · E4 decimal details print VERBATIM at the precision the engine stored (ratio_pct arrives as "312.0000000000"): rounding for display is a decision no signed document makes for these figures, and the server already composes `usage_display` when it wants a rendered number — reported as the place a served display string would help
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
