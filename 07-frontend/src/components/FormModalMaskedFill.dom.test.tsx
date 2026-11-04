// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-10044 — New Connect step 1 (SR-26-0027): the browser filled
//          the clerk's OWN saved login into the form. Phone showed the clerk's
//          email and Driver's license showed the saved password, because a
//          masked box was `type="password"` with `autocomplete="off"` — which
//          browsers ignore on a password input, taking the text box before it
//          as the username.
// Rules:   B14 rule 38 (the kit owns how a field is built — fixed once here,
//          so every masked field is safe) · hard-won law 7
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): jsdom has no password
// manager, so no test can watch a browser fill. What a test CAN pin is the
// attribute every browser reads before it fills — `new-password` on the masked
// box — on BOTH masked renders (plain and Show/Hide), plus the third-party
// managers' own opt-out flags. Asserting only one render would leave the other
// free to drift back to `off`.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TextField } from "./FormModal";

afterEach(cleanup);

function box(id: string): HTMLInputElement {
  return document.getElementById(id) as HTMLInputElement;
}

describe("DEF-CUS-10044 · a masked box is never a saved login", () => {
  it("a masked box asks new-password, never off", () => {
    render(<TextField id="ssn" label="SSN" value="" onChange={() => undefined} masked />);
    expect(box("ssn")).toHaveAttribute("type", "password");
    expect(box("ssn")).toHaveAttribute("autocomplete", "new-password");
    expect(box("ssn")).toHaveAttribute("data-lpignore", "true");
    expect(box("ssn")).toHaveAttribute("data-1p-ignore", "true");
  });

  it("a masked box with Show/Hide asks new-password too", () => {
    render(
      <TextField id="dl" label="Licence" value="" onChange={() => undefined} masked revealable />,
    );
    expect(box("dl")).toHaveAttribute("autocomplete", "new-password");
    expect(box("dl")).toHaveAttribute("data-lpignore", "true");
    expect(box("dl")).toHaveAttribute("data-1p-ignore", "true");
  });

  it("a contact box names its purpose, so it is never read as the username", () => {
    render(
      <>
        <TextField id="phone" label="Phone" value="" onChange={() => undefined} autoComplete="tel" />
        <TextField id="mail" label="Email" value="" onChange={() => undefined} autoComplete="email" />
      </>,
    );
    expect(box("phone")).toHaveAttribute("autocomplete", "tel");
    expect(box("phone")).toHaveAttribute("type", "text");
    expect(box("mail")).toHaveAttribute("autocomplete", "email");
  });

  it("an ordinary box is unchanged: no autocomplete attribute at all", () => {
    render(<TextField id="plain" label="Plain" value="" onChange={() => undefined} />);
    expect(box("plain")).not.toHaveAttribute("autocomplete");
    expect(box("plain")).not.toHaveAttribute("data-lpignore");
  });
});
