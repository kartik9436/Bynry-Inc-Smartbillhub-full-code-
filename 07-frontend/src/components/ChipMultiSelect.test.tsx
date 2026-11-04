// ── Trace ──────────────────────────────────────────────
// Change:   `ChipOption` gains OPTIONAL `disabled` + `reason` (2026-09-10), so
//           the plan wizard's step 2 could stop being a wall of checkboxes
//           without losing `BR-RAT-024`'s restored clause — the services this
//           utility has switched OFF are named INSIDE the list, greyed, with
//           where to switch them on.
// Rules:    B14 rule 9 (a multiple-choice field is removable chips + an add
//           control — NEVER a wall of checkboxes) · rule 36 ("compose the kit;
//           where the kit lacks a piece, ADD IT TO THE KIT") · rule 38 (a kit
//           change is never local, so it must move nothing existing) ·
//           BR-SHL-025 (disabled WITH its reason)
// Defect:   DEF-RAT-4824
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THIS FILE DID NOT EXIST AND THE COMPONENT'S OWN TRACE SAID IT DID.**
 * `ChipMultiSelect.tsx` has carried `Tests: src/components/ChipMultiSelect.test
 * .tsx` since it was written for B14 rule 36's breach (e), and there was no such
 * file — hard-won law 1, a comment claiming a guarantee is not the guarantee.
 * The kit component whose entire purpose is rule 9 had nothing asserting it,
 * across the six screens that compose it.
 *
 * ⚠ **AND THE ASSERTIONS READ RENDERED MARKUP, NOT PROPS.** A case asserting
 * that `disabled` was PASSED would have been green on the day there was no such
 * field to pass. What matters is whether a clerk can pick the option and whether
 * they are told why not, and only the markup answers either.
 *
 * ⚠ **THE REASON IS ASSERTED IN THE VISIBLE TEXT, DELIBERATELY.** B14: colour —
 * or its absence — is never the only signal, and an `<option title>` is a
 * mouse-only affordance that reaches no keyboard user. Wiring `reason` to
 * `title` would satisfy a "the reason is present" check and fail the rule; this
 * file goes red on that.
 *
 * **PROVED RED, through vitest.** With the reason moved onto `title` — the
 * obvious wrong fix, and the one `r10` itself draws (B14's own amendment: *"r10
 * puts the action's meaning in `title` alone, which is mouse-only"*) — the
 * markup reads
 *
 *     <option value="fire" disabled="" title="Not switched on">Fire</option>
 *
 * and this file fails, verbatim:
 *
 *     × carries its reason in the VISIBLE TEXT and not on a title
 *       → expected '<div role="group" …' not to contain 'title="Not switched on"'
 *     1 failed, 8 passed
 *
 * ⚠ **EIGHT OF THE NINE PASSED ON THAT**, the *is disabled* case among them —
 * which is the whole argument for asserting the two halves separately.
 */
import "@/i18n";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ChipMultiSelect } from "./ChipMultiSelect";
import type { ChipOption } from "./ChipMultiSelect";

const OPTIONS: ChipOption[] = [
  { value: "electric", label: "Electric" },
  { value: "water", label: "Water" },
  { value: "fire", label: "Fire", disabled: true, reason: "Not switched on" },
];

/**
 * ONE `<option>`, cut at its own closing tag.
 *
 * ⚠ **A FIXED-WIDTH SLICE RUNS INTO THE NEXT OPTION, AND THE FIRST DRAFT OF
 * THIS FILE DID.** `html.slice(at, at + 120)` from `value="water"` reached past
 * `</option>` into `fire`, which IS disabled — so the case asserting that an
 * untouched option renders no `disabled` went red on its neighbour's attribute.
 * That is the *looking at the wrong thing* shape in miniature, and it would have
 * been far worse the other way round: had the widths differed slightly, the case
 * would have PASSED while reading a string it was never pointed at.
 */
function optionAt(html: string, value: string): string {
  const at = html.indexOf(`value="${value}"`);
  expect(at, `the ${value} option is not rendered at all`).toBeGreaterThan(-1);
  const end = html.indexOf("</option>", at);
  expect(end, `the ${value} option is never closed`).toBeGreaterThan(at);
  // The closing tag is INCLUDED so a label can be pinned at both ends
  // (`>Water<`) — a bare `Water` would also match `Water heater`.
  return html.slice(at, end + "</option>".length);
}

function markup(props: Partial<Parameters<typeof ChipMultiSelect>[0]> = {}) {
  return renderToStaticMarkup(
    <ChipMultiSelect
      label="Services in this plan"
      options={OPTIONS}
      selected={["electric"]}
      onChange={() => {}}
      addLabel="Add a service…"
      emptyLabel="No service chosen yet."
      removeLabel="Remove"
      {...props}
    />,
  );
}

describe("B14 rule 9 — chips plus an add control, never a wall of checkboxes", () => {
  it("draws no checkbox at all", () => {
    // The rule names the thing it forbids, so the test does too.
    expect(markup()).not.toContain('type="checkbox"');
  });

  it("a chosen value is a CHIP that carries its own remove", () => {
    const html = markup();
    expect(html).toContain('data-chip="electric"');
    expect(html).toContain('data-chip-remove="electric"');
    // The remove control names WHICH chip, or a screen reader announces three
    // identical buttons.
    expect(html).toContain('aria-label="Remove Electric"');
  });

  it("an unchosen value is an OPTION in the add control, not a chip", () => {
    const html = markup();
    expect(html).toContain('value="water"');
    expect(html).not.toContain('data-chip="water"');
  });

  it("nothing chosen says so in words rather than drawing an empty box", () => {
    const html = markup({ selected: [] });
    expect(html).toContain("No service chosen yet.");
    expect(html).toContain("data-chip-empty");
  });
});

describe("an option that is present and NOT choosable (2026-09-10)", () => {
  it("is disabled, so a plan cannot bind a service the utility cannot bill", () => {
    const html = markup();
    expect(optionAt(html, "fire")).toContain("disabled");
  });

  it("is still NAMED, because hiding it teaches the clerk the product cannot do it", () => {
    // BR-RAT-024's restored clause and the PO's ruling of 2026-09-08. Both
    // halves are asserted as a pair: visible-but-selectable and invisible are
    // each the wrong screen, and either assertion alone permits one of them.
    expect(markup()).toContain("Fire");
  });

  it("carries its reason in the VISIBLE TEXT and not on a title", () => {
    const html = markup();
    expect(optionAt(html, "fire")).toContain("Not switched on");
    // ⚠ The assertion that makes the one above mean something: a `title` would
    // also "contain" the reason, and would reach no keyboard user.
    expect(html).not.toContain('title="Not switched on"');
  });

  it("an option with neither field renders exactly what it rendered before", () => {
    // ⚠ **RULE 38's CAVEAT, ASSERTED.** A kit change is never local: this
    // component is composed by six screens and every one of them passes options
    // with no `disabled` and no `reason`. If those ever start rendering a dash,
    // an empty suffix or a `disabled` attribute, this goes red.
    const option = optionAt(markup(), "water");
    expect(option).toContain(">Water<");
    expect(option).not.toContain("disabled");
    expect(option).not.toContain("—");
  });
});

describe("the whole field can be held, with its reason (BR-SHL-025)", () => {
  it("held: the add control and every chip's remove are refused together", () => {
    const html = markup({ reason: "Read-only role" });
    // Half a hold is worse than none — a clerk who can remove a chip but not
    // add one has been given a destructive-only control.
    const add = html.slice(html.indexOf("<select"), html.indexOf("</select>"));
    expect(add).toContain("disabled");
    expect(html.slice(html.indexOf("data-chip-remove"))).toContain("disabled");
  });
});
