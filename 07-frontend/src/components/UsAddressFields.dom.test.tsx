// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `DEF-CUS-6408` — PO report 2026-09-23: the billing address *"should
//           full address line, unit, city, zip … how address taken in USA
//           ;do'nt make it mandatory"*.
// Proves:   the five parts, in US order; NONE required; the ZIP's FORMAT is
//           checked and its presence is not; the state is a searchable picker
//           that stores a two-letter code; the value handed back is STRUCTURED.
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { UsAddressFields, emptyUsAddress, usZipIsValid } from "./UsAddressFields";
import type { UsAddressValue } from "./UsAddressFields";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

function Harness(props: { onChange?: (next: UsAddressValue) => void; disabled?: boolean }) {
  const [value, setValue] = useState<UsAddressValue>(emptyUsAddress());
  return (
    <UsAddressFields
      idPrefix="billing"
      value={value}
      disabled={props.disabled}
      onChange={(next) => {
        setValue(next);
        props.onChange?.(next);
      }}
    />
  );
}

describe("UsAddressFields — a US address, and none of it required", () => {
  it("draws Street · Apt, suite or unit · City · State · ZIP code, in that order", () => {
    render(<Harness />);
    const ids = Array.from(document.querySelectorAll("input")).map((input) => input.id);
    expect(ids).toEqual([
      "billing_line1",
      "billing_line2",
      "billing_city",
      "billing_state",
      "billing_postal_code",
    ]);
    expect(screen.getByLabelText(t("common.usAddress.line1"))).toBeInTheDocument();
    expect(screen.getByLabelText(t("common.usAddress.line2"))).toBeInTheDocument();
    expect(screen.getByLabelText(t("common.usAddress.zip"))).toBeInTheDocument();
    // US English, which is the whole point of the words.
    expect(t("common.usAddress.line2")).toBe("Apt, suite or unit");
    expect(t("common.usAddress.zip")).toBe("ZIP code");
  });

  it("NOTHING is required — no aria-required and no drawn mark on any of the five", () => {
    render(<Harness />);
    for (const input of Array.from(document.querySelectorAll("input"))) {
      expect(input).not.toHaveAttribute("aria-required");
      expect(input).not.toBeRequired();
    }
    expect(
      document.querySelector("[data-us-address] abbr, [data-us-address] .text-danger-500"),
    ).toBeNull();
  });

  it("hands back a STRUCTURED value, with the state as its two-letter code", () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(t("common.usAddress.line1")), {
      target: { value: "PO Box 4471" },
    });
    fireEvent.change(screen.getByLabelText(t("common.usAddress.line2")), {
      target: { value: "Suite 200" },
    });
    fireEvent.change(screen.getByLabelText(t("common.usAddress.city")), {
      target: { value: "Round Rock" },
    });
    // The picker is SEARCHABLE (B14 rule 8): type, then pick the option.
    fireEvent.change(screen.getByLabelText(t("common.usAddress.state")), {
      target: { value: "Tex" },
    });
    fireEvent.click(document.getElementById("billing_state-opt-TX") as HTMLElement);
    fireEvent.change(screen.getByLabelText(t("common.usAddress.zip")), {
      target: { value: "78664-1234" },
    });
    expect(onChange).toHaveBeenLastCalledWith({
      line1: "PO Box 4471",
      line2: "Suite 200",
      city: "Round Rock",
      state: "TX",
      postal_code: "78664-1234",
    });
  });

  it("the ZIP's FORMAT is checked only when something was typed", () => {
    render(<Harness />);
    const zip = screen.getByLabelText(t("common.usAddress.zip"));
    expect(zip).not.toHaveAttribute("aria-invalid");
    fireEvent.change(zip, { target: { value: "7866" } });
    expect(zip).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(t("common.usAddress.zipFormat"))).toBeInTheDocument();
    fireEvent.change(zip, { target: { value: "78664" } });
    expect(zip).not.toHaveAttribute("aria-invalid");
    fireEvent.change(zip, { target: { value: "" } });
    expect(zip).not.toHaveAttribute("aria-invalid");
  });

  it("usZipIsValid — empty, five digits and ZIP+4 pass; anything else does not", () => {
    expect(usZipIsValid("")).toBe(true);
    expect(usZipIsValid("   ")).toBe(true);
    expect(usZipIsValid("78704")).toBe(true);
    expect(usZipIsValid("78704-1234")).toBe(true);
    expect(usZipIsValid("7870")).toBe(false);
    expect(usZipIsValid("78704-12")).toBe(false);
    expect(usZipIsValid("7870A")).toBe(false);
  });

  it("disabled draws all five and lets none of them take a value", () => {
    render(<Harness disabled />);
    for (const input of Array.from(document.querySelectorAll("input"))) {
      expect(input).toBeDisabled();
    }
  });
});
