// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-040 (EP-RBS-01) — CR-075 wave E task E4, the `RBS-004`
//          Activity tab. Screens: RBS-004.1 … RBS-004.7.
// Rules:   B14 rule 31 (no database id — and no internal enum code — is ever
//          the visible value of a field) · B14 rule 32 (description budget;
//          no internal code in clerk-facing copy) · B14 rule 35 (a catalogue
//          is written in its own language) · `BR-RBS-002` (a Check holds no
//          port at all) · `BR-RBS-038` (a run pins its version; every edit
//          writes a new one) · `BR-SHL-023` (ONE date-formatting path).
// Defects: DEF-RBS-4308 (the wire and the view model never met) ·
//          DEF-RBS-4285 (`why` and the change summary have no engine field) ·
//          DEF-RBS-4309 (the one-sentence purpose has no field either).
// Tests:   src/features/runbooks/setupModel.test.ts
// Impacts: src/features/runbooks/RunbookSetupPage.tsx
// ───────────────────────────────────────────────────────
/**
 * The mapper `api/runbooksEndpoints.ts` promised and nobody had written.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE ONE RULE THIS FILE APPLIES, EVERYWHERE
 * ══════════════════════════════════════════════════════════════════════════
 * `setupTypes.ts` states it and this file is where it is carried out: **a row
 * whose LABEL is the same for all 26 runbooks is chrome and is translated
 * here; a row whose label VARIES by runbook is data and arrives already in the
 * reader's language.** So *Time zone*, *Most per run* and *Cap raised to 400*
 * are built from catalogue keys in this file, and a step's label, a guard's
 * label and a parameter's label are passed through untouched.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * `E4` — THE ACTIVITY SENTENCE IS COMPOSED HERE, FROM FACTS
 * ══════════════════════════════════════════════════════════════════════════
 * `selectors.runbook_activity` serves `{field, from, to}` and says why in its
 * own docstring: *"`summary` now carries the facts and the screen composes the
 * sentence."* `RBS-004.7` draws four of them — *Cap raised to 400* · *Paused* ·
 * *Schedule set to Mondays* · *Added from templates* — and every one of those
 * is English, so every one of them is a catalogue key here rather than a string
 * from Python.
 *
 * ⚠ **AN UNRECOGNISED FIELD NAMES ITSELF IN WORDS, NEVER IN CODE.** A tenth
 * editable setting added on the server would otherwise print `gate_mode` at a
 * clerk, which is B14 rule 32's *no internal code in clerk-facing copy*. The
 * fallback is *Settings changed* — true of every edit, and visibly less than
 * the sentence it replaces rather than wrong.
 *
 * ⚠ **AND `v4` IS NOT A DATABASE ID.** `08-screen-layouts.md` says so in those
 * words. The activity row's `id` from the wire IS the version number, so there
 * is no uuid on this path to leak.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THREE THINGS THE SHEETS DRAW THAT THE WIRE CANNOT CARRY — EACH ABSENT, NONE
 * INVENTED
 * ══════════════════════════════════════════════════════════════════════════
 *   1. **The purpose sentence** (`DEF-RBS-4309`). `RunbookDefinition` has no
 *      field for *Finds what stops a bill run before it starts*. `purpose` is
 *      OPTIONAL on the view model and an absent one draws NOTHING — the page
 *      head keeps its category chip and loses one line.
 *   2. **Every step's `why` line** (`DEF-RBS-4285`). Same shape, already
 *      optional, already drawing nothing.
 *   3. **A schedule in words.** `cron` is a five-field expression and a raw one
 *      on screen is an internal code (rule 32). The row therefore says what the
 *      TRIGGER is — *Manually* · *On a schedule* · *On an event* — and no
 *      shipped runbook carries a cron today, so nothing is lost meanwhile
 *      (`DEF-RBS-4342`).
 */
import { settingsFieldRows } from "./setupScope";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatDate } from "@/components/DateCell";
import type { PageSize } from "@/components/tableTypes";
import type { PagedRows } from "@/api/paginated";

import { categoryLabel } from "./library/libraryLabels";
import type { RunRow } from "./home/homeEndpoints";
import { statusKey, statusTone } from "./home/runbooksHomeModel";
import type {
  RunbookDetailBody,
  WireActivity,
  WireDefinition,
  WireGuard,
  WireParameter,
  WireParameterSetting,
} from "./setupWire";
import type {
  RunbookSetupView,
  SetupActivityEntry,
  SetupCapability,
  SetupRow,
  SetupRun,
  SetupStep,
  SetupTone,
  SetupValue,
} from "./setupTypes";

/** The one translate signature this file needs. Narrower than `i18next`'s `TFunction`
 *  on purpose: a mapper that could reach the whole i18n surface would be a place
 *  screen behaviour could grow. */
export type Translate = (key: string, options?: Record<string, unknown>) => string;

/** Everything the mapper needs that is not the payload: the reader's language
 *  and the TENANT's date settings (`BR-SHL-023` — one formatting path, so a
 *  screen and an envelope cannot disagree about a date). */
export interface SetupContext {
  t: Translate;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

/** The Runs tab's own request state — the page the SERVER returned, never a
 *  slice taken here (`NFR-3`). */
export interface RunsPageState {
  page: number;
  per: PageSize;
  loading: boolean;
  data: PagedRows<RunRow> | undefined;
}

// ══════════════════════════════════════════════════════════════════════════
// THE MAPPER
// ══════════════════════════════════════════════════════════════════════════

export function toSetupView(
  body: RunbookDetailBody,
  runs: RunsPageState,
  ctx: SetupContext,
): RunbookSetupView {
  const definition: WireDefinition | null = body.definition;
  return {
    key: body.key,
    name: body.name,
    kind: body.kind,
    category: categoryLabel(ctx.t, body.category),
    // ⚠ ABSENT, NOT EMPTY-STRING. `DEF-RBS-4309`: there is no field to read.
    purpose: undefined,
    // `enabled` is the runbook's own switch; `paused` is the screen's word for
    // its opposite, and the header's button reads from this one fact.
    paused: body.enabled === false,

    schedule: {
      runs: triggerValue(body, ctx),
      timeZone: text(body.schedule.timezone),
      // `next_run` is `null` on every runbook in this product and the server
      // says why. `absent` draws the screen's own *Not set*, which is a fact.
      next: instant(body.schedule.next_run, ctx),
    },
    lastRun: lastRunRows(body, ctx),
    capabilities: capabilities(body, ctx),

    steps: steps(definition),
    // ⚠ NO SETTINGS-OWNED NOTE UNTIL A PARAMETER DECLARES ONE. `Parameter.
    // setting_key` is the only thing that says *this value lives in Settings*
    // (`RBR-03`, `RB-021` — policy is read, never duplicated), and the wire
    // carries no address to send a clerk to. Drawing the note with nowhere to
    // go would be hard-won law 2's mirror: a live control onto no screen.
    settingsOwned: null,

    scope: scopeRows(
      (body.parameters ?? []).filter((one) => one.type !== "ref:setting"),
      definition,
      ctx,
    ),
    settingsFields: settingsFieldRows(body.parameters ?? []),
    // `resolve(params)`'s live count is wave `L`'s; a FACT line with no fact is
    // worse than no line, so the note is not drawn at all.
    scopeMatches: null,

    guards: guards(body.guards),

    limits: {
      mostPerRun: body.cap === null ? absent() : text(body.cap.toLocaleString()),
      approval: text(ctx.t(gateKey(body.gate_mode))),
      // `BR-RBS-036` — the trust ratchet as the sentence `RBS-004.5` needs. The
      // SERVER decides it (`dry_run_only`); this line only chooses the words,
      // so the rule lives in one place.
      fees: body.dry_run_only
        ? { kind: "pill", label: ctx.t("runbooks.setup.limits.dryRunOnly"), tone: "warning" }
        : text(ctx.t("runbooks.setup.limits.liveAllowed")),
      whoCanApprove: body.roles.length === 0 ? absent() : text(roleWords(body.roles, ctx)),
    },

    runs: {
      rows: (runs.data?.rows ?? []).map((row) => runRow(row, ctx)),
      total: runs.data?.total ?? null,
      page: runs.page,
      per: runs.per,
      loading: runs.loading,
    },

    activity: body.activity.map((entry) => activityRow(entry, ctx)),
  };
}

// ══════════════════════════════════════════════════════════════════════════
// `E4` — ONE ACTIVITY ROW
// ══════════════════════════════════════════════════════════════════════════

/**
 * *v4 · Cap raised to 400 · Dana W. · 2 Sep* — the whole row, from facts.
 *
 * ⚠ **THE ACTOR CAN BE NOBODY, AND THAT IS A FACT RATHER THAN A GAP.**
 * `ensure_version` writes v1 with no `changed_by` — the bootstrap version is
 * written by the CODE when a template is added, and the backend test asserts
 * `activity[1]["actor"] is None`. So the row says *the system*, in the reader's
 * language, instead of leaving a blank that reads like a lost name.
 */
export function activityRow(entry: WireActivity, ctx: SetupContext): SetupActivityEntry {
  return {
    // A React key. The wire's `id` IS the version number (never a uuid), and
    // the string form keeps it out of any numeric formatting path.
    id: `v${entry.version}`,
    version: entry.version,
    summary: activitySummary(entry.changes, ctx.t),
    actor: entry.actor?.name ?? ctx.t("runbooks.setup.activity.bySystem"),
    when: entry.when === null ? "" : formatDate(entry.when, ctx.timeZone, ctx.dateFormat),
  };
}

/**
 * The sentence `RBS-004.7` draws, composed from `{field, from, to}`.
 *
 * The four the sheet names, in the order the engine can produce them:
 *   * `{field: "origin", to: "shipped"}` → **Added from templates**
 *   * `{field: "origin", to: "cloned"}` + `{field: "cloned_from", to: "Dunning"}`
 *     → **Copied from Dunning**
 *   * `{field: "template", to: …}` → **Template update taken**
 *   * `{field: "enabled", to: false}` → **Paused**
 *   * `{field: "cap", from: 100, to: 400}` → **Cap raised to 400**
 *
 * ⚠ **SEVERAL FACTS IN ONE VERSION ARE JOINED, NEVER TRUNCATED.** One `PUT`
 * may move the cap and the schedule together and `update_runbook` records both
 * in one summary. Dropping the second would make the Activity tab — the tab an
 * auditor asks for first — quietly incomplete, which is worse than a longer
 * line. They join with the same separator the sheets use between facts.
 */
export function activitySummary(
  changes: readonly { field: string; from?: unknown; to?: unknown }[],
  t: Translate,
): string {
  const origin = changes.find((change) => change.field === "origin");
  if (origin !== undefined) {
    if (origin.to === "cloned") {
      const source = changes.find((change) => change.field === "cloned_from");
      return typeof source?.to === "string" && source.to !== ""
        ? t("runbooks.setup.activity.clonedFrom", { name: source.to })
        : t("runbooks.setup.activity.cloned");
    }
    return t("runbooks.setup.activity.added");
  }
  if (changes.some((change) => change.field === "template")) {
    return t("runbooks.setup.activity.templateTaken");
  }
  const phrases = changes.map((change) => phrase(change, t)).filter((one) => one !== "");
  return phrases.length === 0 ? t("runbooks.setup.activity.settingsChanged") : phrases.join(" · ");
}

function phrase(change: { field: string; from?: unknown; to?: unknown }, t: Translate): string {
  switch (change.field) {
    case "enabled":
      return change.to === false
        ? t("runbooks.setup.activity.paused")
        : t("runbooks.setup.activity.resumed");
    case "cap": {
      if (typeof change.to !== "number") return t("runbooks.setup.activity.capCleared");
      const total = change.to.toLocaleString();
      if (typeof change.from !== "number") {
        return t("runbooks.setup.activity.capSet", { total });
      }
      return change.to > change.from
        ? t("runbooks.setup.activity.capRaised", { total })
        : t("runbooks.setup.activity.capLowered", { total });
    }
    case "trigger_kind":
    case "cron":
    case "event_kind":
      // ⚠ **THE CRON IS NOT PRINTED.** `0 7 * * 1` is an internal code and B14
      // rule 32 bans one in clerk-facing copy; *Schedule set to Mondays* needs
      // a cron-to-words formatter this product does not have (`DEF-RBS-4342`).
      // *Schedule changed* is true, is six words short of the sheet's line, and
      // is the honest half.
      return t("runbooks.setup.activity.scheduleChanged");
    case "timezone":
      return typeof change.to === "string" && change.to !== ""
        ? t("runbooks.setup.activity.timeZoneSet", { zone: change.to })
        : t("runbooks.setup.activity.scheduleChanged");
    case "gate_mode":
      return t("runbooks.setup.activity.approvalChanged");
    case "visible_to_roles":
      return t("runbooks.setup.activity.visibilityChanged");
    case "parameters":
      // ⚠ **THE VALUES ARE NOT PRINTED, AND THAT IS RULE 32 RATHER THAN
      // LAZINESS.** *Services set to Water · Sewer* would need every domain's
      // labels on the Activity tab, for values that may since have been
      // deleted; *Scope changed* is true, is three words, and the Scope tab two
      // inches away says what it is now.
      return t("runbooks.setup.activity.scopeChanged");
    default:
      // A tenth editable setting on the server prints WORDS, never its column
      // name. Less than the sheet's sentence, and never an internal code.
      return t("runbooks.setup.activity.settingsChanged");
  }
}

// ══════════════════════════════════════════════════════════════════════════
// the other six tabs
// ══════════════════════════════════════════════════════════════════════════

function steps(definition: WireDefinition | null): SetupStep[] {
  return (definition?.steps ?? []).map((step) => ({
    id: step.key,
    label: step.label,
    // ⚠ `why` IS NEVER SET. `DEF-RBS-4285`: `Step` has no field for it and a
    // placeholder here would be the screen inventing the rule that decided the
    // step — the one thing `BR-RBS-010` says must be real.
    writes: step.writes,
  }));
}

function guards(rows: readonly WireGuard[]): { id: string; label: string }[] {
  return rows.map((guard) => ({ id: guard.key, label: guard.label }));
}

/**
 * `RBS-004.3` region 2 — the runbook's own inputs (`BR-RBS-042`).
 *
 * ⚠ **THE LABELS ARE THE DEFINITION'S OWN AND ARE NOT TRANSLATED HERE.**
 * *Accounts included · Services · Cycles · Account types* is runbook 8's list
 * and nobody else's; a map in the front end would put runbook 8's parameter
 * names into a file that runbook 20 also renders and would break `RB-020`.
 *
 * ⚠ **IT READS `body.parameters`, WHICH IS WHAT THIS TENANT SET — AND UNTIL
 * WAVE `T` IT READ THE DECLARED DEFAULT AND CALLED IT THE SCOPE
 * (`DEF-RBS-4338`).** `runbooks` stored `cap`, `cron` and `gate_mode` and no
 * parameter value at all, so the default and the value were the same string for
 * everybody and the row was ACCIDENTALLY right. It would have been wrong the
 * first time an admin changed one, with `tsc` and every test green, because
 * every test asserted the definition document rather than a tenant's choice.
 *
 * ⚠ **THE PINNED DEFINITION IS STILL THE FALLBACK** and it is not dead code: a
 * runbook whose module the registry no longer holds serves `parameters: []`,
 * and the Scope tab then draws the version's own declaration rather than
 * nothing at all.
 */
function scopeRows(
  settings: readonly WireParameterSetting[],
  definition: WireDefinition | null,
  ctx: SetupContext,
): SetupRow[] {
  if (settings.length > 0) {
    return settings.map((parameter) => ({
      id: parameter.name,
      label: parameter.label,
      value: settingValue(parameter, ctx),
    }));
  }
  return (definition?.parameters ?? []).map((parameter) => ({
    id: parameter.name,
    label: parameter.label,
    value: parameterValue(parameter, ctx),
  }));
}

/**
 * One input's value as a clerk reads it.
 *
 * ⚠ **A DOMAIN VALUE IS DRAWN BY ITS LABEL AND NEVER BY WHAT IS STORED** (B14
 * rule 31). A saved `ref:object` value is an account id: printing it would put
 * a uuid on the screen, which is the exact miss that cost the account header a
 * whole line (`DEF-CUS-3653`). `value_labels` carries the words for the values
 * this tenant chose, resolved on the server for the CHOICE rather than for the
 * domain.
 */
export function settingValue(parameter: WireParameterSetting, ctx: SetupContext): SetupValue {
  const words = parameter.value_labels ?? {};
  const label = (one: unknown) => words[String(one)] ?? humanise(String(one));
  // `BR-RBS-042` clause 1 — ***all* is a rule, not a value**: it is STORED as
  // the word and resolved at run start, so it is CHROME and comes from the
  // catalogue in eleven languages rather than from the data.
  if (parameter.value === "all") return text(ctx.t("runbooks.setup.scope.all"));
  if (parameter.value === null || parameter.value === undefined) return absent();
  if (Array.isArray(parameter.value)) {
    return parameter.value.length === 0
      ? absent()
      : text(parameter.value.map(label).join(" · "));
  }
  if (typeof parameter.value === "boolean") {
    return text(
      parameter.value ? ctx.t("runbooks.setup.thisCan.yes") : ctx.t("runbooks.setup.thisCan.no"),
    );
  }
  return text(label(parameter.value));
}

function parameterValue(parameter: WireParameter, ctx: SetupContext): SetupValue {
  // `BR-RBS-042` clause 1 — ***all* is a rule, not a value**: it is STORED as
  // the word and resolved at run start, so it is CHROME and comes from the
  // catalogue in eleven languages rather than from the definition.
  if (parameter.default === "all") return text(ctx.t("runbooks.setup.scope.all"));
  if (parameter.default === null || parameter.default === undefined) return absent();
  if (Array.isArray(parameter.default)) {
    return parameter.default.length === 0
      ? absent()
      : text(parameter.default.map((one) => humanise(String(one))).join(" · "));
  }
  // A toggle's `true`/`false` are not the runbook's words, they are the
  // language's — so *Yes* and *No* come from the catalogue like every other
  // piece of chrome.
  if (typeof parameter.default === "boolean") {
    return text(
      parameter.default ? ctx.t("runbooks.setup.thisCan.yes") : ctx.t("runbooks.setup.thisCan.no"),
    );
  }
  return text(humanise(String(parameter.default)));
}

/**
 * `blockers_and_warnings` → **Blockers and warnings** (`DEF-RBS-4339`).
 *
 * ⚠ **THE ENGINE SERVES A CODE HERE AND HAS NO WORD FOR IT ANYWHERE.**
 * `contract.py`'s `Parameter` declares `choices` as bare strings, so the value
 * arrives as `blockers_and_warnings` while the sheet draws *Past due over
 * $5.00*. Three answers were possible and two are worse: printing the code is
 * B14 rule 32's *no internal code in clerk-facing copy*, and drawing *Not set*
 * over a parameter that HAS a value is simply false.
 *
 * **So it is de-cased, and the reason it is defensible is consistency rather
 * than convenience.** `Parameter.label`, `Step.label` and `Guard.label` are
 * already English strings written in Python and passed through this mapper
 * untouched — `setupTypes.ts` rules that a label which varies by runbook is
 * DATA and arrives in the reader's language, and today the definition does not
 * localise any of them. A de-cased value is exactly the same class of string as
 * the label beside it, which is not true of a raw `snake_case` code.
 *
 * A per-runbook lookup table here is the one thing that is NOT allowed: it
 * would break `RB-020` (*adding runbook 23 needs one Python module and no
 * frontend code*), which is why the durable fix in `DEF-RBS-4339` is on the
 * definition — `choices` becoming `{value, label}` pairs.
 */
function humanise(code: string): string {
  if (!/^[a-z0-9]+(?:_[a-z0-9]+)+$/.test(code)) return code;
  const words = code.split("_").join(" ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * *This can* — `RBS-004.1` region 9, derived from `ports[]` and nothing else.
 *
 * ⚠ **A CHECK'S EMPTY LIST IS THE SAFETY PROMISE** (`BR-RBS-002`): the
 * capability is ABSENT rather than merely unused, and the renderer draws that
 * sentence. So a Check maps to `[]` here on purpose.
 *
 * ⚠ **THE PORT → CAPABILITY MAP IS NOT INVENTED HERE.** `setupTypes.ts` records
 * why: the map is written down nowhere in the pack, and one of the sheet's
 * three rows — *Change bills* — corresponds to no port at all. So each port the
 * runbook actually holds becomes one row, named from the catalogue by its own
 * code, and an unknown port falls back to its code rather than to a blank key
 * path — visibly a gap rather than a broken string, which is what a fallback is
 * for (`libraryLabels.ts` makes the same trade for a seventeenth category).
 */
function capabilities(body: RunbookDetailBody, ctx: SetupContext): SetupCapability[] {
  return body.ports.map((port) => {
    const key = `runbooks.port.${port}`;
    const word = ctx.t(key);
    return { id: port, label: word === key ? humanise(port) : word, can: true };
  });
}

function lastRunRows(
  body: RunbookDetailBody,
  ctx: SetupContext,
): RunbookSetupView["lastRun"] {
  const run = body.last_run;
  if (run === null) return null;
  return {
    when: instant(run.started_at ?? run.finished_at, ctx),
    state: {
      kind: "pill",
      label: ctx.t(statusKey(run.status)),
      tone: tone(statusTone(run.status)),
    },
    // *Planned* is the count of records a run planned to act on. `counts` is the
    // runbook author's OWN vocabulary (`DEF-RBS-4327`) and drawing its keys would
    // print an untranslated internal word — so this row reads the ONE figure the
    // engine always writes and says *Not set* when there is none.
    planned: typeof run.counts.planned === "number" ? text(String(run.counts.planned)) : absent(),
  };
}

function runRow(row: RunRow, ctx: SetupContext): SetupRun {
  return {
    id: row.id,
    when:
      row.started_at === null
        ? ctx.t("runbooks.mine.neverRun")
        : formatDate(row.started_at, ctx.timeZone, ctx.dateFormat, true),
    outcome: { label: ctx.t(statusKey(row.status)), tone: tone(statusTone(row.status)) },
    // `—`, never `0`: a run that is still waiting has not acted on nobody, it
    // has not acted YET, and the renderer draws the dash from a `null`.
    acted: typeof row.counts.acted === "number" ? row.counts.acted : null,
  };
}

// ── small shapes ─────────────────────────────────────────────────────────────

function text(value: string | null | undefined): SetupValue {
  return value === null || value === undefined || value === "" ? absent() : { kind: "text", text: value };
}

function absent(): SetupValue {
  return { kind: "absent" };
}

function instant(value: string | null, ctx: SetupContext): SetupValue {
  return value === null ? absent() : text(formatDate(value, ctx.timeZone, ctx.dateFormat, true));
}

/** `RBS-004.1` *Runs* — the TRIGGER in words. See the header's point 3. */
function triggerValue(body: RunbookDetailBody, ctx: SetupContext): SetupValue {
  const key = `runbooks.setup.trigger.${body.schedule.trigger_kind}`;
  const word = ctx.t(key);
  return word === key ? absent() : text(word);
}

/** `RBS-004.5` *Approval* — `gate_mode` is an enum code and never drawn raw. */
function gateKey(mode: string): string {
  return `runbooks.setup.gate.${mode}`;
}

/** `RB-050` — *who can approve*, as words rather than as role codes. */
function roleWords(roles: readonly string[], ctx: SetupContext): string {
  return roles
    .map((role) => {
      const key = `runbooks.role.${role}`;
      const word = ctx.t(key);
      return word === key ? humanise(role) : word;
    })
    .join(", ");
}

/** `runbooksHomeModel`'s six tones narrowed to the four these seven tabs draw.
 *  `setupTypes.ts` names four on purpose — *"so a view model cannot ask for one
 *  the sheets never draw"* — and `info` and `muted` are the two it leaves out. */
function tone(value: string): SetupTone {
  if (value === "success" || value === "warning" || value === "danger") return value;
  return "neutral";
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-040 (EP-RBS-01; CR-075 wave E task E4) · wireframes/RBS-004.1–.7 · B14 rules 31, 32, 35
// generated: 2026-09-06 by the CR-075 wave E · E4/E5/E6 build lane
// checklist: A✔ B=n/a C✔ D✔(GET /runbooks/{key}, GET /runbooks/runs) E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest setupModel.test.ts · G15 (catalogue parity)
// exceptions: the purpose sentence (DEF-RBS-4309), every step's `why`
//         (DEF-RBS-4285), a schedule in words (DEF-RBS-4342) and per-tenant
//         parameter VALUES (DEF-RBS-4338) are each ABSENT rather than invented
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
