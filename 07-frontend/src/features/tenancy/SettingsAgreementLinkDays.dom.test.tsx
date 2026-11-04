// @vitest-environment jsdom
//
// CR-190-BRC10 — the agreement link's life is a SETTING (PO: *"7 Days"*):
// shown, edited as a whole number, saved; read-only roles see it and why.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { AgreementLinkDaysField } from "./SettingsAgreementLinkDays";

afterEach(cleanup);

describe("Agreement link days (CR-190-BRC10)", () => {
  it("shows the setting and saves a new whole number", async () => {
    const onSave = vi.fn();
    render(<AgreementLinkDaysField days={7} readOnly={false} readOnlyReason="" saving={false} onSave={onSave} />);
    const box = screen.getByRole("textbox", { name: /Agreement link days/ });
    expect(box).toHaveValue("7");
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    const user = userEvent.setup();
    await user.clear(box);
    await user.type(box, "14");
    await user.click(save);
    expect(onSave).toHaveBeenCalledWith(14);
  });

  it("a read-only role sees the value and no Save", () => {
    render(<AgreementLinkDaysField days={7} readOnly readOnlyReason="Read only" saving={false} onSave={() => undefined} />);
    expect(screen.getByRole("textbox", { name: /Agreement link days/ })).toHaveValue("7");
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.getByText("Read only")).toBeInTheDocument();
  });
});
