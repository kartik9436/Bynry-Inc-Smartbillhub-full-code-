// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-040 (EP-RBS-01) — CR-075 wave E tasks E4 and E5.
// Screens: RBS-004.1 … RBS-004.7.
// Rules:   B14 rule 31 (no database id — nor an internal enum code — is ever
//          the visible value of a field) · B14 rule 32 · `BR-RBS-002` ·
//          `BR-RBS-038` · `BR-RBS-042` clause 1 · `NFR-5` (no hard cap).
// Defects: DEF-RBS-4308 · DEF-RBS-4309 · DEF-RBS-4337 · DEF-RBS-4338 ·
//          DEF-RBS-4339 · DEF-RBS-4342.
// ───────────────────────────────────────────────────────
// EVERY CASE HERE ASSERTS A RULE, NEVER AN IMPRESSION — the plan's own
// definition of done: *"every wave's exit test asserts a rule — a construction
// failure, a 409, a byte-identical report — never an impression."*
//
// ⚠ **THE PAYLOAD BELOW WAS RECORDED FROM A RUNNING SERVER, NOT INVENTED.**
// `POST /runbooks {"template_key": "configuration_check"}` on a freshly seeded
// database on 2026-09-06 answered exactly this shape. `DEF-RBS-4308` is what an
// invented one costs: the client declared `Promise<RunbookSetupView>`, the
// endpoint served something else, `tsc` was satisfied because an unchecked cast
// is not a runtime check, and the screen threw in a browser while every test
// passed over a hand-built view model.
import { describe, expect, it } from "vitest";

import { activitySummary, toSetupView } from "./setupModel";
import type { SetupContext } from "./setupModel";
import { LIMITS_SCHEMA, limitsDraft, limitsToWire } from "./setupLimits";
import type { RunbookDetailBody } from "./setupWire";
import en from "@/i18n/locales/en.json";

/**
 * A translator that behaves like `i18next` does: the catalogue's value when the
 * key is there, **and the KEY ITSELF when it is not**.
 *
 * ⚠ **RETURNING THE KEY ALWAYS WOULD HAVE MADE FOUR OF THESE CASES LIE, AND
 * THE FIRST DRAFT DID EXACTLY THAT.** `triggerValue`, `capabilities`,
 * `roleWords` and `categoryLabel` each detect a MISSING word by comparing the
 * answer with the key — the fallback `libraryLabels.ts` records — so a stub
 * that echoes every key sends all four down the missing branch and the suite
 * asserts the fallback while believing it is asserting the value. It was caught
 * by one case going red (`schedule.runs` came back `absent`), which is the only
 * reason it is written down here instead of shipping.
 *
 * Reading the REAL catalogue also makes each assertion a parity check: a key
 * the mapper names and nobody added shows up as the raw key in the expectation.
 */
const CATALOGUE = en as Record<string, string>;
const echo: SetupContext["t"] = (key, options) => {
  const value = CATALOGUE[key];
  if (value === undefined) return key;
  if (options === undefined) return value;
  return Object.entries(options).reduce(
    (text, [name, replacement]) => text.split(`{{${name}}}`).join(String(replacement)),
    value,
  );
};

const CTX: SetupContext = { t: echo, timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" };

/** `GET /runbooks/configuration_check`, recorded 2026-09-06; `parameters`
 *  added 2026-09-07 when wave `T` began serving it (`BR-RBS-042`). */
const BODY: RunbookDetailBody = {
  // The four inputs runbook 1 declares, with what this tenant set them to —
  // which is nothing, so each reads its declared default and says so.
  parameters: [
    {
      name: "report",
      label: "Report",
      type: "enum",
      required: true,
      domain: null,
      multi: false,
      choices: ["blockers_and_warnings", "blockers_only"],
      setting_key: null,
      value: "blockers_and_warnings",
      is_set: false,
      value_labels: {},
    },
  ],
  key: "configuration_check",
  name: "Can we bill?",
  kind: "check",
  category: "platform",
  tags: ["Plans & Rates", "Service points"],
  origin: "shipped",
  template_key: "configuration_check",
  subject_type: "tenant",
  unit_of_work: "config graph",
  enabled: true,
  current_version: 1,
  schedule: {
    trigger_kind: "manual",
    cron: null,
    event_kind: null,
    timezone: "UTC",
    next_run: null,
  },
  cap: null,
  gate_mode: "approve_each_run",
  visible_to_roles: null,
  roles: ["system_admin"],
  trusted_version: 1,
  dry_run_only: false,
  template_update: null,
  activity: [
    {
      id: 1,
      version: 1,
      changes: [{ field: "origin", to: "shipped" }],
      actor: { name: "Dana Whitfield" },
      when: "2026-09-06T20:12:45.540838+00:00",
    },
  ],
  definition: {
    key: "configuration_check",
    name: "Can we bill?",
    kind: "check",
    category: "platform",
    subject_type: "tenant",
    unit_of_work: "config graph",
    triggers: ["manual"],
    tags: [],
    parameters: [
      {
        name: "report",
        type: "enum",
        label: "Report",
        required: true,
        default: "blockers_and_warnings",
        choices: ["blockers_and_warnings", "blockers_only"],
        setting_key: null,
      },
      {
        name: "include_held_accounts",
        type: "toggle",
        label: "Include held accounts",
        required: false,
        default: false,
        choices: [],
        setting_key: null,
      },
    ],
    steps: [
      { key: "services_and_units", label: "Services and units", mode: "set", writes: false },
      { key: "tax", label: "Tax", mode: "set", writes: false },
    ],
    guards: [],
    requires: null,
    ports: [],
  },
  guards: [],
  ports: [],
  writes_nothing: true,
  requires: null,
  last_run: null,
  open_items: 0,
};

const NO_RUNS = { page: 1, per: 50 as const, loading: false, data: { rows: [], total: 0 } };

describe("E4 · the mapper — DEF-RBS-4308, the gap nothing went red over", () => {
  it("fills every field RunbookSetup reads, so the screen cannot throw on undefined", () => {
    const view = toSetupView(BODY, NO_RUNS, CTX);
    // The exact read that crashed the live screen: `view.capabilities.length`.
    expect(Array.isArray(view.capabilities)).toBe(true);
    expect(Array.isArray(view.steps)).toBe(true);
    expect(Array.isArray(view.guards)).toBe(true);
    expect(Array.isArray(view.scope)).toBe(true);
    expect(Array.isArray(view.activity)).toBe(true);
    expect(view.limits.mostPerRun).toBeDefined();
    expect(view.runs.rows).toEqual([]);
    expect(view.name).toBe("Can we bill?");
  });

  // `DEF-RBS-4309` — the card sentence has no field on `RunbookDefinition` at
  // all. A mapper that invented one would be a screen inventing a fact.
  it("leaves the purpose ABSENT rather than inventing a sentence", () => {
    expect(toSetupView(BODY, NO_RUNS, CTX).purpose).toBeUndefined();
  });

  // `BR-RBS-002` — a Check is CONSTRUCTED with no writer, so the emptiness is
  // the safety promise and the renderer draws a sentence over it.
  it("maps a Check to NO capabilities, which is the safety promise", () => {
    expect(toSetupView(BODY, NO_RUNS, CTX).capabilities).toEqual([]);
  });

  it("derives *This can* from ports[] and from nothing else", () => {
    const action = { ...BODY, kind: "action" as const, ports: ["notify_email"] };
    const view = toSetupView(action, NO_RUNS, CTX);
    expect(view.capabilities).toHaveLength(1);
    expect(view.capabilities[0].can).toBe(true);
    // No catalogue word for a port yet, so the code is DE-CASED rather than
    // printed raw — `runbooks.port.notify_email` is not on screen either.
    expect(view.capabilities[0].label).toBe("Notify email");
  });

  // `DEF-RBS-4337` — a raw cron is an internal code (B14 rule 32).
  it("says what the TRIGGER is and never prints a cron expression", () => {
    const scheduled = {
      ...BODY,
      schedule: { ...BODY.schedule, trigger_kind: "schedule", cron: "0 7 * * 1" },
    };
    const view = toSetupView(scheduled, NO_RUNS, CTX);
    expect(view.schedule.runs).toEqual({ kind: "text", text: "On a schedule" });
    expect(JSON.stringify(view)).not.toContain("0 7 * * 1");
  });

  // `next_run` is `null` on every runbook in this product and the server says
  // why. *Not set* is a fact; an empty cell and a zero look identical.
  it("draws an absent next run as the stated absence, not as a blank", () => {
    expect(toSetupView(BODY, NO_RUNS, CTX).schedule.next).toEqual({ kind: "absent" });
  });

  // `DEF-RBS-4339` — the engine has no word for an enum choice.
  it("de-cases an enum parameter value instead of printing blockers_and_warnings", () => {
    const view = toSetupView(BODY, NO_RUNS, CTX);
    expect(view.scope[0]).toEqual({
      id: "report",
      label: "Report",
      value: { kind: "text", text: "Blockers and warnings" },
    });
    expect(JSON.stringify(view)).not.toContain("blockers_and_warnings");
  });

  // `BR-RBS-042` clause 1 — ***all* is a rule, not a value***: stored as the
  // WORD and resolved at run start, so the screen says the word from the
  // catalogue rather than a list frozen at configure time.
  //
  // ⚠ **THIS CASE WAS RED FROM 2026-09-07 (`6a56c25bc`, wave T) UNTIL
  // 2026-10-02, AND THE PRODUCT WAS RIGHT THE WHOLE TIME.** Wave T added the
  // SERVED `parameters` (what this tenant set) to `BODY`, and `scopeRows`
  // prefers those over the definition's defaults — so overriding only
  // `definition.parameters` here left `BODY`'s *Report* row in first place and
  // the case read *"Blockers and warnings"*: law 7's *looking at the wrong
  // thing*. It now drives BOTH paths the mapper has for *all*, separately.
  it("draws *all* as the catalogue's word, never expanded into a list", () => {
    const servedAll = {
      ...BODY,
      parameters: [
        {
          name: "services",
          label: "Services",
          type: "enum",
          required: true,
          domain: null,
          multi: true,
          choices: [],
          setting_key: null,
          value: "all",
          is_set: true,
          value_labels: {},
        },
      ],
    };
    expect(toSetupView(servedAll, NO_RUNS, CTX).scope[0].value).toEqual({
      kind: "text",
      text: "All",
    });

    const withAll = {
      ...BODY,
      // No served settings, so the mapper falls back to the definition's
      // declared default — the other path *all* can arrive by.
      parameters: [],
      definition: {
        ...BODY.definition!,
        parameters: [
          {
            name: "services",
            type: "enum",
            label: "Services",
            required: true,
            default: "all",
            choices: [],
            setting_key: null,
          },
        ],
      },
    };
    expect(toSetupView(withAll, NO_RUNS, CTX).scope[0].value).toEqual({
      kind: "text",
      text: "All",
    });
  });

  // `BR-RBS-036` — the SERVER decides the ratchet (`dry_run_only`); this only
  // chooses the words, so the rule lives in one place.
  it("reads the trust ratchet from the server's own flag", () => {
    expect(toSetupView(BODY, NO_RUNS, CTX).limits.fees).toEqual({
      kind: "text",
      text: "Real runs allowed",
    });
    const held = { ...BODY, dry_run_only: true };
    expect(toSetupView(held, NO_RUNS, CTX).limits.fees).toEqual({
      kind: "pill",
      label: "Dry run only",
      tone: "warning",
    });
  });

  // `NFR-3` — the renderer draws the page the SERVER returned and slices
  // nothing. The total is the server's `count`, never `rows.length`.
  it("carries the server's total and page through untouched", () => {
    const view = toSetupView(BODY, { page: 3, per: 200, loading: false, data: { rows: [], total: 51 } }, CTX);
    expect(view.runs).toMatchObject({ page: 3, per: 200, total: 51 });
  });

  it("says *of nothing yet* rather than *of 0* before the first response", () => {
    const view = toSetupView(BODY, { page: 1, per: 50, loading: true, data: undefined }, CTX);
    expect(view.runs.total).toBeNull();
    expect(view.runs.loading).toBe(true);
  });
});

describe("E4 · the Activity sentence, composed from facts", () => {
  it("names the four changes RBS-004.7 draws", () => {
    expect(activitySummary([{ field: "origin", to: "shipped" }], echo)).toBe(
      "Added from templates",
    );
    expect(activitySummary([{ field: "enabled", from: true, to: false }], echo)).toBe("Paused");
    expect(activitySummary([{ field: "cap", from: 100, to: 400 }], echo)).toBe(
      "Cap raised to 400",
    );
    expect(activitySummary([{ field: "cron", from: null, to: "0 7 * * 1" }], echo)).toBe(
      "Schedule changed",
    );
  });

  it("names the source a copy came from — the clone's own first version", () => {
    expect(
      activitySummary(
        [
          { field: "origin", to: "cloned" },
          { field: "cloned_from", to: "Dunning" },
        ],
        echo,
      ),
    ).toBe("Copied from Dunning");
  });

  it("distinguishes raised from lowered, and a first cap from a change", () => {
    expect(activitySummary([{ field: "cap", from: 400, to: 100 }], echo)).toBe(
      "Cap lowered to 100",
    );
    expect(activitySummary([{ field: "cap", from: null, to: 100 }], echo)).toBe(
      "Cap set to 100",
    );
    expect(activitySummary([{ field: "cap", from: 100, to: null }], echo)).toBe("Cap removed");
  });

  // The tab an auditor asks for first: one `PUT` may move two settings and
  // `update_runbook` records both. Dropping the second would make it quietly
  // incomplete, which is worse than a longer line.
  it("joins several facts in one version rather than dropping one", () => {
    const summary = activitySummary(
      [
        { field: "cap", from: 100, to: 400 },
        { field: "gate_mode", from: "approve_each_run", to: "approved_up_front" },
      ],
      echo,
    );
    expect(summary).toBe("Cap raised to 400 · Approval changed");
  });

  // B14 rule 32 — no internal code in clerk-facing copy. A tenth editable
  // setting on the server must print WORDS, never its column name.
  it("falls back to words for a field this screen has never heard of", () => {
    expect(activitySummary([{ field: "retention_days", to: 30 }], echo)).toBe(
      "Settings changed",
    );
  });

  // The bootstrap version is written by the CODE — the backend test asserts
  // `activity[1]["actor"] is None`. A blank would read like a lost name.
  it("names the system when nobody made the change", () => {
    const view = toSetupView(
      { ...BODY, activity: [{ ...BODY.activity[0], actor: null }] },
      NO_RUNS,
      CTX,
    );
    expect(view.activity[0].actor).toBe("the system");
  });

  // `08-screen-layouts.md`: *"A runbook version (`v4`) is a human-facing number
  // under B14 rule 31's own escape clause, not an internal id."* The wire's
  // `id` IS the version number, so there is no uuid on this path at all.
  it("carries no database id onto the Activity row", () => {
    const view = toSetupView(BODY, NO_RUNS, CTX);
    expect(view.activity[0].id).toBe("v1");
    expect(view.activity[0].version).toBe(1);
    expect(/[0-9a-f]{8}-[0-9a-f]{4}/.test(JSON.stringify(view.activity))).toBe(false);
  });

  // `BR-SHL-023` — ONE formatting path. 20:12 UTC is 15:12 in Chicago, so a
  // screen that rendered the instant, or fell through to UTC, prints the wrong
  // day for anybody east of the tenant.
  it("formats the moment in the TENANT's zone and format", () => {
    expect(toSetupView(BODY, NO_RUNS, CTX).activity[0].when).toBe("09/06/2026");
  });
});

describe("E6 · the limits form — the commit that stopped refusing", () => {
  it("opens on the runbook's own current values, never a remembered draft", () => {
    expect(limitsDraft(BODY)).toEqual({ cap: "", gate_mode: "approve_each_run" });
    expect(limitsDraft({ ...BODY, cap: 400 }).cap).toBe("400");
  });

  // A blank cap is *no cap*; `0` would mean *act on nobody*. The two must never
  // collapse — `OQ-RBS-1731` ships 100 as a DEFAULT in wave L4, which is a
  // different fact again.
  it("sends null for a blank cap and never zero", () => {
    expect(limitsToWire({ cap: "", gate_mode: "approve_each_run" }).cap).toBeNull();
    expect(limitsToWire({ cap: "400", gate_mode: "approve_each_run" }).cap).toBe(400);
  });

  it("sends only the two fields this form owns, so a no-op edit writes no version", () => {
    expect(Object.keys(limitsToWire({ cap: "400", gate_mode: "approve_each_run" })).sort()).toEqual([
      "cap",
      "gate_mode",
    ]);
  });

  it("refuses a cap that is not a whole number before any request is made", () => {
    expect(LIMITS_SCHEMA.safeParse({ cap: "4o0", gate_mode: "approve_each_run" }).success).toBe(
      false,
    );
    expect(LIMITS_SCHEMA.safeParse({ cap: "-5", gate_mode: "approve_each_run" }).success).toBe(
      false,
    );
  });

  // `NFR-5` and CLAUDE.md's opening paragraph: nobody may add a maximum that
  // would have to be removed when T4 arrives. This form refuses a NEGATIVE
  // number and nothing else.
  it("puts no upper limit on the cap — NFR-5", () => {
    expect(
      LIMITS_SCHEMA.safeParse({ cap: "40000000", gate_mode: "approve_each_run" }).success,
    ).toBe(true);
  });
});
