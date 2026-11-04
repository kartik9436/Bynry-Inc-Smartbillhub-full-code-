// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-016 (EP-WRK-03) TC-1 · TC-3 — the pack prefills, and the
//           review panel's seven sections and their item count.
// Rules:    BR-WRK-011 · BR-WRK-009 · BR-WRK-015 · CLAUDE.md hard rule 2
//           (a quantity is a STRING client-side) · hard rule 3
// ───────────────────────────────────────────────────────
//
// The builder's arithmetic, asserted WITHOUT mounting anything — the same
// posture `commitPlanOf` takes in the New Connect wizard. `Work-017`'s
// *"7 SECTIONS · 26 ITEMS"* is a function of the draft, so it can be a
// function call rather than a screenshot.
import { describe, expect, it } from "vitest";

import {
  applyPack,
  clearPack,
  collectionPayloads,
  emptyBuilderDraft,
  headerPayload,
  draftFromTemplate,
  helpRowAddable,
  helpRowMissing,
  isHttpsAddress,
  isVideoAddress,
  step1Complete,
  taskMinutes,
} from "./templateBuilderModel";
import type { TemplatePack } from "./workEndpoints";

/** A task row with no payment check (FB-013 added the three fields). */
const NO_MONEY = { moneyCheck: false, moneyMinutes: "5", moneyChargeCode: "" } as const;

/** The *Meter exchange* pack as `GET /work/template-packs` answers it — the
 *  seven tasks of `Work-015` and the three readings of `Work-016`. */
const METER_EXCHANGE: TemplatePack = {
  code: "METER_EXCHANGE",
  name: "Meter exchange",
  tasks: 7,
  parts: 3,
  readings: 3,
  safety: 3,
  help: 3,
  est_duration_minutes: 45,
  unresolved_parts: [],
  bundle: {
    details: {
      show_account_summary: true,
      show_asset_card: true,
      show_access_notes: true,
      show_appointment: true,
    },
    safety: [
      { text: "Isolate at the service head before removal", is_mandatory: true },
      { text: "Check for backfeed / on-site generation", is_mandatory: true },
      { text: "Confined space check where pit-set", is_mandatory: true },
    ],
    tasks: [
      { title: "Verify meter ID matches work order", est_minutes: 3, photo_required: false, is_mandatory: true },
      { title: "Record final read on old meter", est_minutes: 2, photo_required: true, is_mandatory: true },
      { title: "Isolate supply & remove old meter", est_minutes: 10, photo_required: false, is_mandatory: true },
      { title: "Fit new meter & pressure test", est_minutes: 15, photo_required: false, is_mandatory: true },
      { title: "Record opening read on new meter", est_minutes: 2, photo_required: true, is_mandatory: true },
      { title: "Apply tamper seal & log seal number", est_minutes: 5, photo_required: false, is_mandatory: true },
      { title: "Restore supply & confirm flow", est_minutes: 8, photo_required: false, is_mandatory: true },
    ],
    materials: [
      { part_id: "p1", part_no: "MTR-E1P", name: "Electric meter", planned_qty: "1.0000", unit_of_measure: "each" },
      { part_id: "p2", part_no: "SEAL-01", name: "Tamper seal", planned_qty: "1.0000", unit_of_measure: "each" },
      { part_id: "p3", part_no: "GSKT-STD", name: "Gasket", planned_qty: "1.0000", unit_of_measure: "each" },
    ],
    readings: [
      { prompt: "Final read on old meter", unit_of_measure: "kWh", min: "0", max: "99999", required: true, photo_required: true, posts_as_meter_read: true },
      { prompt: "Opening read on new meter", unit_of_measure: "kWh", min: "0", max: "999", required: true, photo_required: true, posts_as_meter_read: true },
      { prompt: "New meter serial", unit_of_measure: "serial", min: null, max: null, required: true, photo_required: false, posts_as_meter_read: false },
    ],
    help: [
      { kind: "document", label: "Meter exchange SOP", ref: null },
      { kind: "phone", label: "Supervisor", ref: null },
      { kind: "phone", label: "AMI activation hotline", ref: null },
    ],
  },
};

describe("US-WRK-016 — the builder's arithmetic", () => {
  it("TC-1 — the Meter exchange pack prefills steps 2 to 6 and leaves the header alone", () => {
    const filled = applyPack(emptyBuilderDraft(), METER_EXCHANGE);
    expect(filled.safety).toHaveLength(3);
    expect(filled.tasks).toHaveLength(7);
    expect(filled.materials).toHaveLength(3);
    expect(filled.readings).toHaveLength(3);
    expect(filled.help).toHaveLength(3);
    // A pack knows nothing about this utility's services, job types or kits —
    // prefilling a SERVICE would be the pack deciding what is being authored.
    expect(filled.name).toBe("");
    expect(filled.service).toBe("");
    // It is remembered for the SCREEN and stored nowhere: nothing on a
    // template records which pack it came from (`US-WRK-016` §5).
    expect(filled.packCode).toBe("METER_EXCHANGE");
    expect(Object.keys(collectionPayloads(filled))).not.toContain("packCode");
  });

  it("the seven tasks come to 45 minutes, which is what the dispatcher schedules against", () => {
    const filled = applyPack(emptyBuilderDraft(), METER_EXCHANGE);
    expect(taskMinutes(filled.tasks)).toBe(45);
    // `Work-013`'s EST. cell is the SAME figure, computed once. A second field
    // for it would be a second answer to one question.
    expect(headerPayload(filled).est_duration_minutes).toBe(45);
  });

  it("a blank estimate counts as nothing rather than breaking the sum", () => {
    const draft = emptyBuilderDraft();
    draft.tasks = [
      { title: "Look at it", estMinutes: "", photoRequired: false, isMandatory: true, ...NO_MONEY, instruction: "" },
      { title: "Fix it", estMinutes: "12", photoRequired: false, isMandatory: true, ...NO_MONEY, instruction: "" },
    ];
    expect(taskMinutes(draft.tasks)).toBe(12);
    // A template with no estimate at all sends NULL, not a zero that would
    // read as *"this job takes no time"* on the dispatcher.
    draft.tasks = [{ title: "Look at it", estMinutes: "", photoRequired: false, isMandatory: true, ...NO_MONEY, instruction: "" }];
    expect(headerPayload(draft).est_duration_minutes).toBeNull();
  });

  // ⚠ RETIRED 2026-10-04 (CR-168 P3.26): *"TC-3 — the review panel is SEVEN
  // sections and, on the drawn template, 26 items"*. The 26 was a wireframe's
  // illustration built to as a fact (Details counted as 4, Signature as 3; B14
  // rule 37). The Review now draws every row (`TemplateSummary`), asserted in
  // `cr168Templates.dom.test.tsx`.

  it("*Start empty* clears the collections and keeps what the clerk has typed", () => {
    const filled = applyPack(emptyBuilderDraft(), METER_EXCHANGE);
    const named = { ...filled, name: "Backflow test", service: "water" };
    const emptied = clearPack(named);
    expect(emptied.tasks).toEqual([]);
    expect(emptied.readings).toEqual([]);
    expect(emptied.name).toBe("Backflow test");
    expect(emptied.service).toBe("water");
  });

  it("step 1 refuses on a missing name, service or scope and on nothing else", () => {
    expect(step1Complete(emptyBuilderDraft())).toBe(false);
    expect(step1Complete({ ...emptyBuilderDraft(), name: "Backflow test" })).toBe(false);
    // P3.12 (`DEF-WRK-9577`) — asked, never defaulted to premises.
    expect(step1Complete({ ...emptyBuilderDraft(), name: "Site visit", service: "water" })).toBe(false);
    // `US-WRK-015` TC-5 publishes a template with no tasks and no readings —
    // some jobs are a visit and a signature — so nothing below step 1 blocks.
    expect(
      step1Complete({ ...emptyBuilderDraft(), name: "Site visit", service: "water", scope: "per_premise" }),
    ).toBe(true);
  });
});

describe("what the builder posts", () => {
  it("the ORDER of each list is the payload's order — `seq` is the server's to assign", () => {
    const filled = applyPack(emptyBuilderDraft(), METER_EXCHANGE);
    const reordered = {
      ...filled,
      tasks: [filled.tasks[5], ...filled.tasks.filter((_row, i) => i !== 5)],
    };
    const payload = collectionPayloads(reordered);
    expect(payload.tasks[0].title).toBe("Apply tamper seal & log seal number");
    // A caller never sends a `seq`: the list order IS the sequence, which is
    // what makes replace-in-full the only shape a drag can use.
    expect(Object.keys(payload.tasks[0])).not.toContain("seq");
  });

  it("an unset range is NULL and never a zero, because they are different facts", () => {
    const filled = applyPack(emptyBuilderDraft(), METER_EXCHANGE);
    const payload = collectionPayloads(filled);
    const serial = payload.readings[2];
    expect(serial.min).toBeNull();
    expect(serial.max).toBeNull();
    // hard rule 3 — the unit is a COLUMN and the server refuses a blank one.
    expect(serial.unit_of_measure).toBe("serial");
  });

  it("step 7's three answers travel on `details`, and default to asking", () => {
    const payload = collectionPayloads(emptyBuilderDraft());
    expect(payload.details.signature_required).toBe(true);
    expect(payload.details.refusal_reason_required).toBe(true);
    expect(payload.details.door_hanger_on_no_answer).toBe(true);
  });

  it("an unchosen picker sends NULL, never the empty string", () => {
    const payload = headerPayload({ ...emptyBuilderDraft(), name: "X", service: "water" });
    expect(payload.type_id).toBeNull();
    expect(payload.skill_id).toBeNull();
    expect(payload.safety_kit_id).toBeNull();
    // A crew of nobody is not a crew; the floor is one.
    expect(payload.crew_size).toBe(1);
  });
});

describe("CR-168 round 4 — scope, instruction text and the Link kind", () => {
  it("P3.12 — the header carries the scope once it is answered, and not before", () => {
    expect(headerPayload({ ...emptyBuilderDraft(), name: "X", service: "water" })).not.toHaveProperty("scope");
    expect(headerPayload({ ...emptyBuilderDraft(), name: "X", service: "water", scope: "per_asset" }).scope).toBe("per_asset");
  });

  it("PO answer 3 — a task's instruction travels, and a blank one is null", () => {
    const draft = emptyBuilderDraft();
    draft.tasks = [
      { title: "Fit the new meter", estMinutes: "25", photoRequired: false, isMandatory: true, ...NO_MONEY, instruction: " Isolate first. " },
      { title: "Record the reading", estMinutes: "5", photoRequired: false, isMandatory: true, ...NO_MONEY, instruction: "  " },
    ];
    const payload = collectionPayloads(draft);
    expect(payload.tasks[0].instruction).toBe("Isolate first.");
    expect(payload.tasks[1].instruction).toBeNull();
  });

  it("P3.25 — a link is sent as `link`, a document and a phone as `ref`", () => {
    const draft = emptyBuilderDraft();
    draft.help = [
      { kind: "link", label: "Fitting a meter", ref: "https://youtu.be/Qx4dF2mT9sE", fileName: "", fileBytes: null },
      { kind: "phone", label: "Supervisor", ref: "(512) 555-0100", fileName: "", fileBytes: null },
    ];
    const payload = collectionPayloads(draft);
    expect(payload.help[0]).toEqual({ kind: "link", label: "Fitting a meter", link: "https://youtu.be/Qx4dF2mT9sE" });
    expect(payload.help[1]).toEqual({ kind: "phone", label: "Supervisor", ref: "(512) 555-0100" });
  });

  it("P3.25 — https only, and the three video hosts are videos", () => {
    expect(isHttpsAddress("https://www.youtube.com/watch?v=Qx4dF2mT9sE")).toBe(true);
    expect(isHttpsAddress("http://www.youtube.com/watch?v=Qx4dF2mT9sE")).toBe(false);
    expect(isHttpsAddress("youtube.com")).toBe(false);
    expect(isVideoAddress("https://www.youtube.com/watch?v=Qx4dF2mT9sE")).toBe(true);
    expect(isVideoAddress("https://youtu.be/Qx4dF2mT9sE")).toBe(true);
    expect(isVideoAddress("https://vimeo.com/1")).toBe(true);
    expect(isVideoAddress("https://example.com/manual")).toBe(false);
    expect(helpRowAddable("link", "Manual", "http://example.com")).toBe(false);
    expect(helpRowAddable("document", "Manual", "")).toBe(true);
    expect(helpRowAddable("phone", "", "555")).toBe(false);
  });

  it("a held document reads back with its file's name and size; a link reads its address", () => {
    const row = {
      id: "t",
      template_no: null,
      name: "X",
      service: null,
      scope: "per_asset",
      sequence: 0,
      job_type: null,
      skill: null,
      safety_kit: null,
      crew_size: 1,
      est_duration_minutes: null,
      is_gate: false,
      no_gate_reason: null,
      is_sample: false,
      active: true,
      version: 0,
      contents: { tasks: 0, parts: 0, readings: 0, safety: 0, help: 2 },
      status: "draft" as const,
      orders_raised: 0,
      bundle: {
        details: null,
        safety: [],
        tasks: [],
        materials: [{ part_id: "p", part_no: "P", name: "Part", planned_qty: "2.0000", unit_of_measure: "each" }],
        readings: [],
        asset_types: [],
        help: [
          { seq: 1, kind: "document", label: "Procedure", ref: "doc-key", url: "/x", link: null, file: { id: "f", name: "procedure.pdf", content_type: "application/pdf", bytes: 421888 } },
          { seq: 2, kind: "link", label: "Video", ref: "https://youtu.be/a", url: null, link: "https://youtu.be/a", file: null },
        ],
      },
    };
    const draft = draftFromTemplate(row);
    expect(draft.scope).toBe("per_asset");
    expect(draft.help[0]).toMatchObject({ fileName: "procedure.pdf", fileBytes: 421888, ref: "doc-key" });
    expect(draft.help[1].ref).toBe("https://youtu.be/a");
    // P1.18 — no four trailing zeros in the box a clerk edits.
    expect(draft.materials[0].plannedQty).toBe("2");
  });

  // FB-013 (DEF-WRK-10641, PO 2026-10-28) — a step's payment check is edited
  // here and SURVIVES a save: the PUT replaces the task rows, and before this
  // the builder never sent the two money columns, so re-saving a template
  // silently erased every check it had.
  it("FB-013 — a step's payment check reloads from the template and is sent back on save", () => {
    const tasks = [
      { seq: 1, title: "Photograph the meter", est_minutes: 2, photo_required: true, is_mandatory: true },
      { seq: 2, title: "Close the valve", est_minutes: 5, photo_required: false, is_mandatory: true,
        money_fresh_minutes: 5, money_charge_code: null },
      { seq: 3, title: "Reconnect", est_minutes: 5, photo_required: false, is_mandatory: true,
        money_fresh_minutes: 15, money_charge_code: "CC-RECON" },
    ];
    const row = {
      id: "t", name: "Disconnection", scope: "per_unit", version: 1, crew_size: 1,
      service: { code: "water" }, job_type: null, skill: null, safety_kit: null,
      bundle: { details: null, safety: [], tasks, materials: [], readings: [], asset_types: [], help: [] },
    } as unknown as Parameters<typeof draftFromTemplate>[0];
    const draft = draftFromTemplate(row);
    expect(draft.tasks.map((t) => [t.moneyCheck, t.moneyMinutes, t.moneyChargeCode])).toEqual([
      [false, "5", ""],
      [true, "5", ""],
      [true, "15", "CC-RECON"],
    ]);
    const sent = collectionPayloads(draft).tasks;
    expect(sent.map((t) => [t.money_fresh_minutes, t.money_charge_code])).toEqual([
      [null, null],
      [5, null],
      [15, "CC-RECON"],
    ]);
  });

  it("FB-013 — ticking Check payment sends the default five minutes; unticking sends none", () => {
    const draft = emptyBuilderDraft();
    draft.tasks = [
      { title: "Close the valve", estMinutes: "5", photoRequired: false, isMandatory: true,
        moneyCheck: true, moneyMinutes: "", moneyChargeCode: " ", instruction: "" },
      { title: "Seal it", estMinutes: "5", photoRequired: false, isMandatory: true,
        moneyCheck: false, moneyMinutes: "9", moneyChargeCode: "CC-X", instruction: "" },
    ];
    const sent = collectionPayloads(draft).tasks;
    expect([sent[0].money_fresh_minutes, sent[0].money_charge_code]).toEqual([5, null]);
    expect([sent[1].money_fresh_minutes, sent[1].money_charge_code]).toEqual([null, null]);
  });
});

// DEF-WRK-10652 (PO 2026-10-29, rulings 3B and 4A) — the customer's
// preparation text and the visit-message switch reload from the template and
// are sent back on EVERY save, so a re-save cannot wipe either.
describe("DEF-WRK-10652 — customer messages on the template", () => {
  const row = (details: Record<string, unknown> | null) =>
    ({
      id: "t", name: "Disconnect visit", scope: "per_unit", version: 1, crew_size: 1,
      service: { code: "water" }, job_type: null, skill: null, safety_kit: null,
      bundle: { details, safety: [], tasks: [], materials: [], readings: [], asset_types: [], help: [] },
    }) as unknown as Parameters<typeof draftFromTemplate>[0];

  it("reloads the prep text and the switch and sends both back on save", () => {
    const draft = draftFromTemplate(
      row({ prep_instructions: "Clear 3 ft around the meter box.", send_customer_visit_messages: false }),
    );
    expect([draft.prepInstructions, draft.sendCustomerVisitMessages]).toEqual([
      "Clear 3 ft around the meter box.",
      false,
    ]);
    const sent = collectionPayloads(draft).details;
    expect([sent.prep_instructions, sent.send_customer_visit_messages]).toEqual([
      "Clear 3 ft around the meter box.",
      false,
    ]);
    // save → reload → save: the same two values again.
    const again = collectionPayloads(draftFromTemplate(row({ ...sent }))).details;
    expect([again.prep_instructions, again.send_customer_visit_messages]).toEqual([
      "Clear 3 ft around the meter box.",
      false,
    ]);
  });

  it("a new template sends visit messages and a blank prep is null (the utility default)", () => {
    const sent = collectionPayloads(emptyBuilderDraft()).details;
    expect([sent.prep_instructions, sent.send_customer_visit_messages]).toEqual([null, true]);
    const old = collectionPayloads(draftFromTemplate(row({ show_appointment: true }))).details;
    expect([old.prep_instructions, old.send_customer_visit_messages]).toEqual([null, true]);
  });
});

describe("FB-023 F4 — the fifth tick, Balance & payments", () => {
  const row = (details: Record<string, unknown> | null) =>
    ({
      id: "t", name: "Disconnect visit", scope: "per_unit", version: 1, crew_size: 1,
      service: { code: "water" }, job_type: null, skill: null, safety_kit: null,
      bundle: { details, safety: [], tasks: [], materials: [], readings: [], asset_types: [], help: [] },
    }) as unknown as Parameters<typeof draftFromTemplate>[0];

  it("a new template shows it; an untick reloads and is sent back", () => {
    expect(collectionPayloads(emptyBuilderDraft()).details.show_balance_payments).toBe(true);
    const draft = draftFromTemplate(row({ show_balance_payments: false }));
    expect(draft.showBalancePayments).toBe(false);
    expect(collectionPayloads(draft).details.show_balance_payments).toBe(false);
  });

  it("a template saved before the tick existed reads it as shown", () => {
    expect(draftFromTemplate(row({ show_appointment: true })).showBalancePayments).toBe(true);
  });
});

describe("FB-028 — the Reconnect limit on the template (PO 2026-10-31)", () => {
  const withTasks = (details: Record<string, unknown> | null, moneyCheck: boolean) =>
    ({
      id: "t", name: "Reconnect visit", scope: "per_unit", version: 1, crew_size: 1,
      service: { code: "water" }, job_type: null, skill: null, safety_kit: null,
      bundle: {
        details,
        safety: [],
        tasks: [
          { seq: 1, title: "Restore the service", est_minutes: 5, photo_required: false, is_mandatory: true,
            money_fresh_minutes: moneyCheck ? 5 : null, money_charge_code: null },
        ],
        materials: [], readings: [], asset_types: [], help: [],
      },
    }) as unknown as Parameters<typeof draftFromTemplate>[0];

  it("reloads the stored 4-place amount at 2 places and sends what is typed", () => {
    const draft = draftFromTemplate(withTasks({ reconnect_limit: "25.0000" }, true));
    expect(draft.reconnectLimit).toBe("25.00");
    expect(collectionPayloads({ ...draft, reconnectLimit: "40" }).details.reconnect_limit).toBe("40");
  });

  it("defaults to 25.00 when a step checks payment, and sends nothing without one", () => {
    const fresh = draftFromTemplate(withTasks(null, true));
    expect(fresh.reconnectLimit).toBe("25.00");
    expect(collectionPayloads({ ...fresh, reconnectLimit: "" }).details.reconnect_limit).toBe("25.00");
    const none = draftFromTemplate(withTasks({ reconnect_limit: "25.0000" }, false));
    expect(collectionPayloads(none).details.reconnect_limit).toBeNull();
  });
});

// FB-031 (DEF-FLD-10805) — the "Meter exchange" pack's empty rows are marked on
// the builder before the server refuses to publish them.
describe("FB-031 — a help row with nothing for the technician", () => {
  it("a document with no uploaded file reads No file — a typed label included", () => {
    expect(helpRowMissing({ kind: "document", ref: "", fileName: "" })).toBe("noFile");
    expect(helpRowMissing({ kind: "document", ref: "SOP-W-12", fileName: "" })).toBe("noFile");
    expect(helpRowMissing({ kind: "document", ref: "doc-key", fileName: "sop.pdf" })).toBeNull();
  });

  it("a phone row with no number reads No number", () => {
    expect(helpRowMissing({ kind: "phone", ref: "", fileName: "" })).toBe("noNumber");
    expect(helpRowMissing({ kind: "phone", ref: "ext.", fileName: "" })).toBe("noNumber");
    expect(helpRowMissing({ kind: "phone", ref: "(512) 555-0142", fileName: "" })).toBeNull();
    expect(helpRowMissing({ kind: "link", ref: "https://youtu.be/x", fileName: "" })).toBeNull();
  });

  it("the two marks are catalogued words, three or fewer (B14 rule 33)", () => {
    // `import.meta.glob` as text, not `node:fs` (the front end's tsconfig has no node types).
    const text = import.meta.glob("../../i18n/locales/en.json", { query: "?raw", eager: true, import: "default" }) as Record<string, string>;
    const en = JSON.parse(Object.values(text)[0]!) as Record<string, string>;
    expect(en["work.builder.help.noFile"]).toBe("No file");
    expect(en["work.builder.help.noNumber"]).toBe("No number");
  });
});
