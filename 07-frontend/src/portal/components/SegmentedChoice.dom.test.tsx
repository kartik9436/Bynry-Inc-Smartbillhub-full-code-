// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    CR-068 (the customer portal) · the KIT half
// Screens:  CWP-025 (How we contact you) · CWP-033 (Usage) · CWP-023 (Accounts)
// Defect:   DEF-CWP-3996 — `SegmentedChoice` wrote `props.label` to
//           `aria-label` and DREW NOTHING, so CWP-025 shipped four bare
//           `On`/`Off` buttons floating above a table with nothing saying what
//           they switch. Reported by the PO on the running product and filed
//           as row D4 of `14-layout-audit.md`.
// Defect:   DEF-CWP-3997 — the chosen option rendered `variant="primary"`, a
//           solid brand fill. B14 rule 6 reserves that tier for destructive
//           commits, so a red `Off` block read as an error rather than a state.
// Rules:    B14 rule 6 (danger/brand tier is for destructive commits) ·
//           rule 36 (compose the kit — `SegmentedControl` already exists) ·
//           rule 33 (a label is a name, three words)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **WHY THE FIRST TEST IS WRITTEN THE WAY IT IS, AND WHY THE OBVIOUS ONE IS
// USELESS HERE.** `aria-label` satisfies every accessibility check that looks
// for an accessible NAME — `getByRole("group", { name: "Email as well" })`
// passes on the broken component, and so does every axe rule. A checker
// therefore reports a control that no sighted person can read as correctly
// labelled. The only assertion that can tell the two apart is one about a
// **visible text node**, which is what `getByText` is doing below.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { SegmentedChoice } from "./primitives";

afterEach(cleanup);

const OPTIONS = [
  { key: "on", label: "On" },
  { key: "off", label: "Off" },
];

describe("SegmentedChoice", () => {
  it("draws its label where a person can read it (DEF-CWP-3996)", () => {
    render(
      <SegmentedChoice
        label="Email as well"
        options={OPTIONS}
        current="off"
        onChoose={() => undefined}
        testId="email"
      />,
    );
    // The accessible name is NOT the assertion — the broken component had one.
    // A visible text node is.
    const visible = screen.getByText("Email as well");
    expect(visible).toBeVisible();
    expect(visible.getAttribute("aria-hidden")).toBeNull();
  });

  it("ties that label to the control by id, not by a floating word", () => {
    render(
      <SegmentedChoice
        label="How far back"
        options={[
          { key: "12", label: "12 months" },
          { key: "24", label: "24 months" },
        ]}
        current="12"
        onChoose={() => undefined}
        testId="window"
      />,
    );
    const group = screen.getByRole("radiogroup", { name: "How far back" });
    const labelledBy = group.getAttribute("aria-labelledby");
    expect(labelledBy).not.toBeNull();
    expect(document.getElementById(labelledBy as string)?.textContent).toBe("How far back");
  });

  it("never renders the chosen option in the brand button tier (DEF-CWP-3997, B14 rule 6)", () => {
    render(
      <SegmentedChoice
        label="Email as well"
        options={OPTIONS}
        current="on"
        onChoose={() => undefined}
        testId="email"
      />,
    );
    // Rule 6 reserves `primary`/`danger` for destructive commits. A state is
    // not a commit, and a solid red `Off` block reads as an error.
    expect(document.querySelector('[data-variant="primary"]')).toBeNull();
    expect(document.querySelector('[data-variant="danger"]')).toBeNull();
  });

  it("marks the chosen option in a way a screen reader reports", () => {
    render(
      <SegmentedChoice
        label="Email as well"
        options={OPTIONS}
        current="on"
        onChoose={() => undefined}
        testId="email"
      />,
    );
    const chosen = screen.getByRole("radio", { name: "On" });
    expect(chosen).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Off" })).toHaveAttribute("aria-checked", "false");
  });

  it("still calls back with the option's key", async () => {
    const chose = vi.fn();
    const { default: userEvent } = await import("@testing-library/user-event");
    render(
      <SegmentedChoice
        label="Email as well"
        options={OPTIONS}
        current="on"
        onChoose={chose}
        testId="email"
      />,
    );
    await userEvent.click(screen.getByRole("radio", { name: "Off" }));
    expect(chose).toHaveBeenCalledWith("off");
  });

  it("keeps the `data-segmented` handle the screens' tests select on", () => {
    render(
      <SegmentedChoice
        label="Email as well"
        options={OPTIONS}
        current="on"
        onChoose={() => undefined}
        testId="email"
      />,
    );
    expect(document.querySelector('[data-segmented="email"]')).not.toBeNull();
  });
});
