// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1 (`DEF-523`).
// ── Trace ──────────────────────────────────────────────
// Story:   US-CWP-001 — the portal's shared form primitives.
// Screens: CWP-015 (Sign in) · CWP-002 (Set up your login) — every portal
//          screen with a password field, because they all compose `TextInput`.
// Rules:   B14 rule 36 (compose the shared kit) · rule 21 (Tailwind utilities,
//          and `portal/` is on `route-b-migrated.txt` as a directory).
// Defects: DEF-CWP-4377 (the Product Owner, on the live product: "im unable to
//          see the password - this is an issue with all login or change
//          password screen on customer portal").
// ───────────────────────────────────────────────────────
// ⚠ **THE SECOND CASE IS THE ONE THAT MATTERS AND IT IS NOT ABOUT REVEALING.**
// A `<button>` inside a `<form>` defaults to `type="submit"`. A reveal control
// written without `type="button"` therefore SUBMITS THE FORM: a customer who
// presses *Show* to check a typo instead sends the half-typed password and is
// told it is wrong. The control added to prevent a failed sign-in would have
// caused one, on every portal login. It renders identically either way, so
// only a case that puts it inside a real form and watches for a submit can see
// it.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { TextInput } from "./primitives";

// No auto-cleanup in this repo — `vite.config.ts` registers no `setupFiles`.
afterEach(cleanup);

function draw(node: React.ReactNode) {
  return render(<MemoryRouter initialEntries={["/silver-creek-water1/portal/sign-in"]}>{node}</MemoryRouter>);
}

describe("a portal password field can be read back by the person typing it", () => {
  it("starts masked, reveals on Show, and masks again on Hide", async () => {
    const user = userEvent.setup();
    draw(<TextInput id="portal-password" type="password" value="Canyon2026" onChange={() => undefined} />);

    const field = document.getElementById("portal-password") as HTMLInputElement;
    expect(field.type, "a password field must start masked").toBe("password");

    await user.click(screen.getByRole("button", { name: /show/i }));
    expect(field.type, "Show did not reveal the password").toBe("text");
    expect(screen.getByRole("button", { name: /hide/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /hide/i }));
    expect(field.type, "Hide did not mask it again").toBe("password");
  });

  it("does NOT submit the form it sits in — the trap that would break every login", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    draw(
      <form onSubmit={onSubmit}>
        <TextInput id="portal-password" type="password" value="half-typed" onChange={() => undefined} />
      </form>,
    );

    await user.click(screen.getByRole("button", { name: /show/i }));
    expect(
      onSubmit,
      "the reveal submitted the sign-in form — it is missing type=\"button\"",
    ).not.toHaveBeenCalled();
  });

  it("says which field it controls, and its pressed state, to a screen reader", async () => {
    const user = userEvent.setup();
    draw(<TextInput id="enrol-new" type="password" value="x" onChange={() => undefined} />);

    const toggle = screen.getByRole("button", { name: /show/i });
    expect(toggle).toHaveAttribute("aria-controls", "enrol-new");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(screen.getByRole("button", { name: /hide/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("adds nothing to a field that is not a password", () => {
    draw(<TextInput id="portal-email" type="email" value="a@b.c" onChange={() => undefined} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(document.querySelector("[data-password-reveal]")).toBeNull();
  });
});
