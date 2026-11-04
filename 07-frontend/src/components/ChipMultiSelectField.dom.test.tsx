// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `DEF-SHL-6250` — *"ChipMultiSelect renders its label only as an
//           aria-label, so a chips field inside a modal has no visible name
//           and no required marker"*. Fixed 2026-09-28 for the New Connect
//           redesign, whose `step2-premise.png` draws **Utility services \***
//           over the multi-select.
// Rules:    B14 rule 9 (chips + an add control, never a wall of checkboxes) ·
//           rule 10 (the asterisk rides on the label) · rule 39 (LABEL →
//           INPUT → HELPER) · rule 21 · rule 43 · hard-won law 6
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIRST CASE IS THE ONE THAT PROTECTS THE OTHER NINE CALL SITES.**
// This component is on nine screens and every one of them takes its name from
// a surrounding `Panel`. The fix had to be opt-in or it would have put a
// second, duplicate heading on all nine at once — so the default is asserted
// as hard as the new behaviour.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChipMultiSelect } from "./ChipMultiSelect";

afterEach(cleanup);

const SERVICES = [
  { value: "water", label: "Water" },
  { value: "sewer", label: "Sewer" },
  { value: "broadband", label: "Broadband" },
];

function field(props: Record<string, unknown> = {}) {
  return (
    <ChipMultiSelect
      label="Utility services"
      options={SERVICES}
      selected={["water", "sewer"]}
      onChange={vi.fn()}
      addLabel="Add a service"
      emptyLabel="None chosen"
      removeLabel="Remove"
      testKey="services"
      {...props}
    />
  );
}

describe("ChipMultiSelect — the default is untouched", () => {
  it("draws NO visible label, exactly as the nine existing screens render it", () => {
    // ⚠ NOT `not.toContain("<label")` — the add control is ALREADY wrapped in
    // a `<label>` carrying an `sr-only` span, and an assertion that trips on
    // that would go red on the correct default. What must be absent is the
    // FIELD wrapper, the field's own label and the required marker.
    const { container } = render(field());
    expect(container.querySelector(".field")).toBeNull();
    expect(container.querySelector(".field > label")).toBeNull();
    expect(container.querySelector(".field-required")).toBeNull();
    expect(container.querySelector("[role='group']")).toHaveAttribute(
      "aria-label",
      "Utility services",
    );
    // The only words on screen are the chips and the add control's own.
    expect(screen.queryByText("Utility services")).toBeNull();
  });

  it("is chips plus an add control, and the add control is NOT a search", () => {
    // B14 rule 9, and `searchable` absent is the no-search form the drawing
    // shows — a plain `<select>`, which the shared `.view select` rule gives
    // the product's one chevron (rule 8).
    render(field());
    expect(screen.getByText("Water")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove Water" })).toBeInTheDocument();
    const add = screen.getByRole("combobox", { name: "Add a service" });
    expect(add.tagName).toBe("SELECT");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("the add control offers only what is NOT already chosen", () => {
    render(field());
    expect(screen.getByRole("option", { name: "Broadband" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Water" })).toBeNull();
  });
});

describe("ChipMultiSelect — DEF-SHL-6250, a label and an asterisk of its own", () => {
  it("draws a visible label and marks it required", () => {
    render(field({ showLabel: true, required: true }));
    expect(screen.getByText("Utility services")).toBeInTheDocument();
    // B14 rule 10's marker, the kit's one spelling of it.
    const { container } = render(field({ showLabel: true, required: true }));
    expect(container.querySelector(".field-required")?.textContent).toBe("*");
  });

  it("the visible label NAMES the group — one name, not two", () => {
    const { container } = render(field({ showLabel: true }));
    const group = container.querySelector("[role='group']");
    expect(group).not.toHaveAttribute("aria-label");
    const labelId = group?.getAttribute("aria-labelledby");
    expect(labelId).toBeTruthy();
    expect(document.getElementById(labelId as string)?.textContent).toContain("Utility services");
  });

  it("the label is a DIRECT child of `.field`, or the stylesheet does not reach it", () => {
    // `.field > label` is a CHILD selector — the same descendant trap
    // `DEF-MET-4959` records one control over.
    const { container } = render(field({ showLabel: true }));
    expect(container.querySelector(".field > label")).not.toBeNull();
  });

  it("the helper and the refusal render, and the group points at both", () => {
    const { container } = render(
      field({ showLabel: true, help: "Pick every service here.", error: "Choose at least one." }),
    );
    const group = container.querySelector("[role='group']");
    const described = (group?.getAttribute("aria-describedby") ?? "").split(" ");
    expect(described).toHaveLength(2);
    for (const id of described) {
      expect(document.getElementById(id)).not.toBeNull();
    }
    expect(screen.getByText("Pick every service here.")).toBeInTheDocument();
    expect(screen.getByText("Choose at least one.")).toBeInTheDocument();
  });

  it("no helper and no refusal — nothing is described, so nothing dangles", () => {
    const { container } = render(field({ showLabel: true }));
    expect(container.querySelector("[role='group']")).not.toHaveAttribute("aria-describedby");
  });

  it("two labelled fields on one screen get two different names", () => {
    // `useId` and not `testKey`: `testKey` is optional, and two fields sharing
    // one label id would give both of them the second field's name.
    const { container } = render(
      <>
        {field({ showLabel: true })}
        {field({ showLabel: true, label: "Areas" })}
      </>,
    );
    const ids = [...container.querySelectorAll("[role='group']")].map((one) =>
      one.getAttribute("aria-labelledby"),
    );
    expect(ids[0]).not.toBe(ids[1]);
  });
});
