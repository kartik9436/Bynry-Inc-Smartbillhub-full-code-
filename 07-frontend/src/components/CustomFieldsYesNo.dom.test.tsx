// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-9240 — a Yes/No custom field on a STAFF screen was a single
//          tick box, so a clerk could not record "No": an untouched box saved
//          nothing, the view stayed blank and approval had nothing to copy.
// Rules:   BR-SHL-036 (one control per data type) · B14 rule 44 (how a control
//          is built is ours) · B14 rule 43 (the ONE `CustomFields` component,
//          so every staff screen moves at once)
// ───────────────────────────────────────────────────────
// The worked case from the walk: SEU's *EV Charged on Site* answered **No**.
// Three states, all distinct: nothing chosen (unanswered), Yes, No.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import i18n from "@/i18n";

import { CustomFieldControl, displayValue } from "./CustomFields";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

const EV: CustomFieldRegistryEntry = {
  id: "cf-ev",
  key: "ev_charged_on_site",
  label: "EV Charged on Site",
  help_text: "",
  data_type: "boolean",
  options: [],
  is_required: false,
  display_order: 0,
  placement: { S16: "input", S14: "view" },
};

function control(value: unknown) {
  const onChange = vi.fn();
  const view = render(<CustomFieldControl field={EV} value={value} onChange={onChange} />);
  const box = view.getByLabelText("EV Charged on Site") as HTMLSelectElement;
  return { box, onChange };
}

describe("DEF-SHL-9240 · a Yes/No field can be answered No on a staff screen", () => {
  it("is a Yes / No choice with nothing chosen until the clerk picks", () => {
    const { box } = control(undefined);
    expect(box.tagName).toBe("SELECT");
    expect(box.value).toBe("");
    const labels = Array.from(box.options).map((o) => o.textContent);
    expect(labels).toEqual([
      t("customFields.chooseOne"),
      t("settings.customFields.yes"),
      t("settings.customFields.no"),
    ]);
  });

  it("picking No stores false — an answer, not a blank", () => {
    const { box, onChange } = control(undefined);
    fireEvent.change(box, { target: { value: "false" } });
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("picking Yes stores true, and going back to nothing clears it", () => {
    const yes = control(undefined);
    fireEvent.change(yes.box, { target: { value: "true" } });
    expect(yes.onChange).toHaveBeenCalledWith(true);
    cleanup();
    const back = control(true);
    expect(back.box.value).toBe("true");
    fireEvent.change(back.box, { target: { value: "" } });
    expect(back.onChange).toHaveBeenCalledWith(null);
  });

  it("a stored No shows No, in the control and on the view", () => {
    expect(control(false).box.value).toBe("false");
    expect(displayValue(EV, { ev_charged_on_site: false }, (s) => s, t)).toBe(
      t("settings.customFields.no"),
    );
    expect(displayValue(EV, {}, (s) => s, t)).toBe("");
  });
});
