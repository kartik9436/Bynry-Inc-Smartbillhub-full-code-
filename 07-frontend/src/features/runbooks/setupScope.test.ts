/* ══════════════════════════════════════════════════════════════════════════
 * WHAT **CHANGE SCOPE** COLLECTS AND WHAT IT SENDS — the RULE, not the modal.
 *
 * Story: US-RBS-039 (EP-RBS-05) — CR-075 wave T.
 * Rules: `BR-RBS-042` (a tenant sets input VALUES; a domain per input, resolved
 *        per tenant; one value, several, or *all*, and ***all* is stored as THE
 *        WORD and resolved at run start*) · `NFR-3` · `NFR-5` · B14 rule 9.
 *
 * ⚠ **THE CENTRAL CASE IS `scopeToWire` SENDING THE WORD.** Sending
 * `entry.values` instead is one character shorter, is right in every observable
 * way on the day it is written, and is silently wrong the month a utility adds
 * a service: that service is then outside every runbook set to *all*, with no
 * error, no screen change and nothing anywhere to see. It is the reason the
 * draft carries a MODE beside the values rather than a list that happens to
 * hold everything.
 * ══════════════════════════════════════════════════════════════════════════ */
import { describe, expect, it } from "vitest";

import { BOUNDED_DOMAINS, editableKind, holdReason, scopeDraft, scopeToWire } from "./setupScope";
import type { WireParameterSetting } from "./setupWire";

function input(over: Partial<WireParameterSetting>): WireParameterSetting {
  return {
    name: "services",
    label: "Services",
    type: "enum",
    required: true,
    domain: null,
    multi: false,
    choices: [],
    setting_key: null,
    value: null,
    is_set: false,
    value_labels: {},
    ...over,
  };
}

const SERVICES = input({ domain: "service", multi: true, value: "all" });
const REPORT = input({
  name: "report",
  label: "Report",
  choices: ["blockers_and_warnings", "blockers_only"],
  value: "blockers_and_warnings",
});
const MONEY = input({
  name: "past_due_more_than",
  label: "Past due more than",
  type: "money",
  value: "5.0000",
});
const ACCOUNT = input({ name: "account", label: "Account", type: "ref:object", domain: "account" });
const ROUNDING = input({
  name: "rounding",
  label: "Rounding",
  type: "ref:setting",
  setting_key: "money.rounding",
});
const PERIOD = input({ name: "period", label: "Period", type: "window" });
const TOGGLE = input({ name: "raise_work_items", label: "Raise work items", type: "toggle", value: true });

describe("BR-RBS-042 · which control each input gets, and which get none", () => {
  it("a bounded domain is editable and an unbounded one is HELD", () => {
    expect(editableKind(SERVICES)).toBe("domain");
    // 40,000 accounts at the top of T5 is not a dropdown (`NFR-3`), and the
    // kit has no searching picker — so it is drawn disabled WITH its reason
    // rather than truncated to page 1, which would look perfectly healthy
    // right up to the customer who needs it most.
    expect(editableKind(ACCOUNT)).toBe("held");
    expect(holdReason(ACCOUNT)).toBe("unbounded");
  });

  it("Settings-owned and control-less inputs are held, each with its own reason", () => {
    expect(editableKind(ROUNDING)).toBe("held");
    expect(holdReason(ROUNDING)).toBe("settings");
    expect(editableKind(PERIOD)).toBe("held");
    expect(holdReason(PERIOD)).toBe("noControl");
  });

  it("the bounded list is DECLARED, never inferred from how many rows came back", () => {
    // A domain holding three rows in a demo tenant and 40,000 in a real one is
    // the whole trap: a client that decided by counting page 1 would draw a
    // perfectly good picker until it met a real utility.
    expect(BOUNDED_DOMAINS).toEqual(["service", "period"]);
    expect(BOUNDED_DOMAINS).not.toContain("account");
  });

  it("choices, scalars and toggles each get their own control", () => {
    expect(editableKind(REPORT)).toBe("choice");
    expect(editableKind(MONEY)).toBe("scalar");
    expect(editableKind(TOGGLE)).toBe("switch");
  });
});

describe("BR-RBS-042 clause 1 · *all* is a rule and it leaves as the word", () => {
  it("a stored *all* opens the sheet in ALL mode with no chips", () => {
    const draft = scopeDraft([SERVICES]);
    expect(draft.services.mode).toBe("all");
    expect(draft.services.values).toEqual([]);
  });

  it("ALL mode sends the WORD, never the services that happen to be on screen", () => {
    const draft = scopeDraft([SERVICES]);
    // A person opens the picker, sees Water and Sewer, and saves without
    // changing anything. THE CHIPS ARE NOT THE ANSWER.
    draft.services.values = ["water", "sewer"];
    expect(scopeToWire(draft, [SERVICES])).toEqual({ parameters: { services: "all" } });
  });

  it("choosing SOME sends exactly those, as a list", () => {
    const draft = scopeDraft([SERVICES]);
    draft.services.mode = "some";
    draft.services.values = ["water"];
    expect(scopeToWire(draft, [SERVICES])).toEqual({ parameters: { services: ["water"] } });
  });

  it("a stored list opens in SOME mode with its chips", () => {
    const draft = scopeDraft([input({ domain: "service", multi: true, value: ["water", "sewer"] })]);
    expect(draft.services.mode).toBe("some");
    expect(draft.services.values).toEqual(["water", "sewer"]);
  });
});

describe("what travels and what never does", () => {
  it("a HELD input is never sent, so a round trip cannot rewrite it", () => {
    const parameters = [SERVICES, ACCOUNT, ROUNDING, PERIOD];
    const body = scopeToWire(scopeDraft(parameters), parameters);
    expect(Object.keys(body.parameters ?? {})).toEqual(["services"]);
  });

  it("the WHOLE document travels, because a delta cannot clear a value", () => {
    const parameters = [SERVICES, REPORT, MONEY];
    const body = scopeToWire(scopeDraft(parameters), parameters);
    expect(Object.keys(body.parameters ?? {}).sort()).toEqual([
      "past_due_more_than",
      "report",
      "services",
    ]);
  });

  it("an emptied text box sends null, not an empty string", () => {
    const draft = scopeDraft([MONEY]);
    draft.past_due_more_than.value = "   ";
    expect(scopeToWire(draft, [MONEY])).toEqual({ parameters: { past_due_more_than: null } });
  });

  it("a toggle travels as a boolean and not as the string it was edited as", () => {
    const draft = scopeDraft([TOGGLE]);
    expect(draft.raise_work_items.value).toBe("true");
    expect(scopeToWire(draft, [TOGGLE])).toEqual({ parameters: { raise_work_items: true } });
  });
});
