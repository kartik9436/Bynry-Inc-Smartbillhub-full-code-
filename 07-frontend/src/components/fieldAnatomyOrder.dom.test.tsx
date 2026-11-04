// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-SHL-4921 — the staff form kit rendered label → helper → input
//           in all five help-bearing variants of `FormModal.tsx` and in
//           `CustomFields.tsx`'s multi-select, which is the order B14 rule 39
//           ruled against on the day it was ratified.
// Rules:    B14 rule 39 (PO, verbatim 2026-09-11: *"in the forms for the
//           fields. It starts with the field name. then the input field, and
//           then it should show the helper text below that input field."*) ·
//           B14 rule 7 (a date field is the date input — bounds included;
//           DEF-MET-4974).
// Why here: this is the check DEF-SHL-4921's own remediation column asked for —
//           *"fail when an element carrying field-help precedes its control
//           inside the same field container"* — and it is written as the ONE
//           thing a source check can decide. It reads DOM ORDER, which is
//           source-checkable and needs no browser. It deliberately does NOT
//           assert the 5 / 6 / 20px figures: those need rendered output, jsdom
//           computes no layout, and the instrument that does measure them is
//           `10-scripts/render-checks/cr092-lane3-field-anatomy.mjs`.
//
// ⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN, AND IN THE HARNESS THAT RUNS IT**
//   (hard-won law 7, both halves). This exact file was run under `vitest` in a
//   clean worktree pinned at the pre-fix tip `a0b28104a`: 6 of its 7 cases
//   failed there, one per help-bearing variant, each naming the variant. The
//   same file at this commit passes. A red proof through `python3 <file>` or a
//   hand-run of one case is the shape that has already announced two gates
//   green while the suite reported them crashed.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

import type { CustomFieldRegistryEntry } from "@/api/endpoints";

import { CustomFieldControl } from "./CustomFields";
import {
  DatePickerField,
  PasswordField,
  SearchSelectField,
  SelectField,
  TextField,
} from "./FormModal";

afterEach(cleanup);

const HELP = "This sentence must sit under the control.";
const OPTIONS = [
  { value: "a", label: "Option A" },
  { value: "b", label: "Option B" },
];

/**
 * The whole rule, as one question a source check can answer: inside the field
 * wrapper, does the helper come AFTER the control?
 *
 * `compareDocumentPosition` is used rather than an index into `children`
 * because the control is not always a direct child — `PasswordField` wraps its
 * input with the reveal toggle and `SearchSelectField` wraps its combobox with
 * the listbox, and a check that only looked at direct children would silently
 * skip both. That is the "reporting zero over a scope it excludes" shape.
 */
function helperFollowsControl(container: HTMLElement): {
  field: boolean;
  help: boolean;
  control: boolean;
  after: boolean;
} {
  const field = container.querySelector(".field");
  const help = field?.querySelector(".field-help") ?? null;
  const control = field?.querySelector("input, select, textarea") ?? null;
  if (field === null || help === null || control === null) {
    return { field: field !== null, help: help !== null, control: control !== null, after: false };
  }
  // DOCUMENT_POSITION_FOLLOWING === 4: `help` comes after `control`.
  const following = (control.compareDocumentPosition(help) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  return { field: true, help: true, control: true, after: following };
}

const VARIANTS: { name: string; node: ReactElement }[] = [
  {
    name: "TextField",
    node: <TextField id="f1" label="Asset #" value="" onChange={() => undefined} help={HELP} />,
  },
  {
    name: "TextField (multiline)",
    node: (
      <TextField
        id="f2"
        label="Detail"
        value=""
        multiline
        onChange={() => undefined}
        help={HELP}
      />
    ),
  },
  {
    name: "PasswordField",
    node: (
      <PasswordField id="f3" label="Password" value="" onChange={() => undefined} help={HELP} />
    ),
  },
  {
    name: "SelectField",
    node: (
      <SelectField
        id="f4"
        label="Asset type"
        value=""
        options={OPTIONS}
        onChange={() => undefined}
        help={HELP}
      />
    ),
  },
  {
    name: "DatePickerField",
    node: (
      <DatePickerField
        id="f5"
        label="Retire date"
        value=""
        dateFormat="MM/DD/YYYY"
        onChange={() => undefined}
        help={HELP}
      />
    ),
  },
  {
    name: "SearchSelectField",
    node: (
      <SearchSelectField
        id="f6"
        label="Replaced by"
        value=""
        options={OPTIONS}
        onChange={() => undefined}
        help={HELP}
      />
    ),
  },
];

describe("B14 rule 39 — a field is label → input → helper (DEF-SHL-4921)", () => {
  it.each(VARIANTS)("$name renders its helper BELOW its control", ({ name, node }) => {
    const { container } = render(node);
    const seen = helperFollowsControl(container);

    // Each of these is asserted separately so a failure says WHICH half broke:
    // a helper that vanished reads exactly like a helper in the wrong place if
    // the only assertion is the ordering one.
    expect(seen.field, `${name}: no .field wrapper rendered`).toBe(true);
    expect(seen.help, `${name}: no .field-help rendered — the help prop is dropped`).toBe(true);
    expect(seen.control, `${name}: no control rendered`).toBe(true);
    expect(
      seen.after,
      `${name}: the helper precedes its control. B14 rule 39, PO verbatim: "It starts with the ` +
        `field name. then the input field, and then it should show the helper text below that ` +
        `input field." Move the {props.help} block BELOW the control in FormModal.tsx.`,
    ).toBe(true);
  });

  it("CustomFields' multi-select puts its helper below the checkbox group", () => {
    const field: CustomFieldRegistryEntry = {
      id: "cf1",
      key: "zones",
      label: "Zones",
      help_text: HELP,
      data_type: "multi_select",
      options: ["North", "South"],
      is_required: false,
      display_order: 1,
      placement: {},
    };
    const { container } = render(
      <CustomFieldControl field={field} value={[]} onChange={() => undefined} />,
    );
    const wrapper = container.querySelector(".field");
    const help = wrapper?.querySelector(".field-help") ?? null;
    // The "control" of a checkbox GROUP is the group, so the helper must follow
    // the LAST box rather than the first.
    const boxes = wrapper?.querySelectorAll('input[type="checkbox"]') ?? [];
    const last = boxes.length > 0 ? boxes[boxes.length - 1] : null;

    expect(wrapper, "no .field wrapper rendered").not.toBeNull();
    expect(help, "no .field-help rendered").not.toBeNull();
    expect(last, "no checkboxes rendered").not.toBeNull();
    expect(
      (last as Element).compareDocumentPosition(help as Element) &
        Node.DOCUMENT_POSITION_FOLLOWING,
      "CustomFields multi-select: the helper precedes the checkbox group (B14 rule 39)",
    ).not.toBe(0);
  });
});

describe("B14 rule 7 — the shared date control can be bounded (DEF-MET-4974)", () => {
  it("passes min and max through to the date input", () => {
    const { container } = render(
      <DatePickerField
        id="d1"
        label="Retire date"
        value=""
        dateFormat="MM/DD/YYYY"
        min="2020-01-01"
        max="2026-09-12"
        onChange={() => undefined}
      />,
    );
    const input = container.querySelector<HTMLInputElement>('input[type="date"]');
    expect(input, "no date input rendered").not.toBeNull();
    expect(input).toHaveAttribute("min", "2020-01-01");
    expect(input).toHaveAttribute("max", "2026-09-12");
  });

  it("omits both attributes when no bound is given, so existing fields do not move", () => {
    const { container } = render(
      <DatePickerField
        id="d2"
        label="Read date"
        value=""
        dateFormat="MM/DD/YYYY"
        onChange={() => undefined}
      />,
    );
    const input = container.querySelector<HTMLInputElement>('input[type="date"]');
    expect(input).not.toHaveAttribute("min");
    expect(input).not.toHaveAttribute("max");
  });
});
