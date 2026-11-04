// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-027 (EP-CWP-06) · Screen: CWP-020
// Rules:    BR-CWP-033 (the code goes to the ADDED account's contact) ·
//           BR-CWP-039 (a consequence panel BEFORE the commit) · BR-CWP-015
//           (nothing is combined — bills stay separate) · BR-CWP-034 (no
//           contact dead-ends) · B14 rule 31 · rule 33
// Cases:    the two facts · the consequence panel and its third bullet · the
//           masked destination · the dead end · already held · a wrong code
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { MemoryRouter, Route, Routes } from "react-router-dom";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { AddAccountFound } from "../api/portalClient";

let find: () => Promise<AddAccountFound> = async () => ({ matched: false, reason: "not_matched" });
let verify: () => Promise<{ linked: boolean; reason?: string }> = async () => ({ linked: true });
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, findAccountToAdd: () => find(), verifyAccountToAdd: () => verify() };
});

const { AddAccountView } = await import("./AddAccount");

const MATCHED: AddAccountFound = {
  matched: true,
  account_ref: "otp-row",
  sent_to: "••• ••• 0144",
  channel: "sms",
  expires_in_minutes: 10,
};

/** The set already on this login — what the rail draws (`DEF-CWP-3984`). */
const ON_THIS_LOGIN = [
  {
    id: "a1",
    account_no: "ACC-10519-A",
    label: "1408 Elm St · A",
    permissions: ["see", "pay"],
    source: "holder",
    is_master: true,
  },
  {
    id: "a2",
    account_no: "ACC-10519-B",
    label: "1408 Elm St · B",
    permissions: ["see"],
    source: "holder",
    is_master: false,
  },
];

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATH, NOT BARE AND NOT IN A
 * PLAIN `MemoryRouter`.** This fixture was `render(<AddAccountView … />)` with
 * no router at all, which worked only for as long as the screen built no
 * addresses. The moment it gained a back link (`DEF-CWP-4000`) every case
 * failed on `Cannot destructure property 'basename'` — the honest failure.
 *
 * A bare `MemoryRouter` would be WORSE than that error, because it does not
 * fail: `useParams().tenant` comes back undefined, `usePortalPath` builds
 * `//portal/accounts` — a protocol-relative URL to another host — and every
 * `toContain` reads it as a perfectly good string (CLAUDE.md hard-won law 2).
 * The route PATTERN is what makes the tenant real.
 *
 * ⚠ The `accounts` prop stays REQUIRED and its own note below says why: an
 * optional one `tsc` never complains about is a rail that renders nothing
 * while every case here passes.
 */
function draw(accounts = ON_THIS_LOGIN) {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/accounts/add"]}>
      <Routes>
        <Route
          path="/:tenant/portal/accounts/add"
          element={<AddAccountView accounts={accounts} />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

function typeTwoFacts(container: HTMLElement) {
  fireEvent.change(container.querySelector("#add-number")!, { target: { value: "ACC-10519-C" } });
  fireEvent.change(container.querySelector("#add-postcode")!, { target: { value: "78702" } });
}

afterEach(cleanup);

describe("CWP-020 · add another account (US-CWP-027)", () => {
  /** ⚠ **ADDING AN ACCOUNT TO A VIEW IS NOT TAKING ONE OVER, AND THE SCREEN
   *  HAD NOT SAID SO.** The captured wireframe gives this form a second panel
   *  for exactly that, and its caption is the reason: *"a change of responsible
   *  party has legal and deposit consequences a form cannot settle"*. Somebody
   *  who has bought a house would otherwise type the number in, fail the code
   *  that goes to the OLD holder's contact, and be told nothing about what to
   *  do instead.
   *
   *  ⚠ **AND THE DOOR IS ASSERTED BY ADDRESS.** The wireframe writes a
   *  telephone number; no payload this screen reads carries a general
   *  enquiries one, so the panel opens the offices list — which publishes each
   *  office's own number — and this case is what fails if that door is ever
   *  pointed somewhere else. */
  it("says that taking an account over is a different thing, and opens the way to do it", async () => {
    const { container } = draw();
    const panel = container.querySelector("[data-testid='add-account-taking-over']");
    expect(panel).not.toBeNull();
    expect(container.querySelector("[data-add-account-taking-over]")?.textContent ?? "").toContain(
      "somebody else's name",
    );
    expect(panel?.querySelector("a")?.getAttribute("href")).toBe("/pine-hill/portal/visit");
  });

  it("asks for the two facts printed on that account's own bill", () => {
    const { container } = draw();
    expect(container.querySelector("#add-number")).toBeTruthy();
    expect(container.querySelector("#add-postcode")).toBeTruthy();
    // ⚠ AND FOR NOTHING ELSE. A surname box here would be a third fact the
    // person adding a tenant's account does not hold.
    expect(container.querySelectorAll("input")).toHaveLength(2);
  });

  it("BR-CWP-039 — the consequence panel is on screen BEFORE the commit", () => {
    const { container } = draw();
    const panel = container.querySelector("[data-add-account-consequences]");
    expect(panel).toBeTruthy();
    // ⚠ THE THIRD BULLET IS THE ONE A LANDLORD NEEDS. The obvious reading of
    // *add this account to my login* is that the two bills become one.
    expect(panel!.textContent).toContain("Nothing is combined");
    expect(panel!.textContent).toContain("not to you");
  });

  it("the Find control is held until both facts are typed (B14 rule 33)", () => {
    const { container } = draw();
    const held = container.querySelector("button[disabled]");
    expect(held?.getAttribute("title")).toBe("Both fields are needed");
  });

  it("BR-CWP-033 — the masked destination is the ADDED account's contact", async () => {
    find = async () => MATCHED;
    const { container } = draw();
    typeTwoFacts(container);
    fireEvent.click(screen.getByText("Find this account"));
    expect(await screen.findByText(/••• ••• 0144/)).toBeTruthy();
    // The sentence says WHOSE contact it is, because a customer who assumes it
    // is theirs will sit waiting for a message that is not coming.
    expect(container.querySelector("[data-add-account-code]")?.textContent).toContain(
      "the contact on the account you are adding",
    );
  });

  it("an unknown pair is refused with one sentence, and no code step opens", async () => {
    find = async () => ({ matched: false, reason: "not_matched" });
    const { container } = draw();
    typeTwoFacts(container);
    fireEvent.click(screen.getByText("Find this account"));
    expect(await screen.findByText("We could not match those two.")).toBeTruthy();
    expect(container.querySelector("[data-add-account-code]")).toBeNull();
  });

  it("an account already on the list says so — it discloses nothing", async () => {
    find = async () => ({ matched: false, reason: "already_held" });
    const { container } = draw();
    typeTwoFacts(container);
    fireEvent.click(screen.getByText("Find this account"));
    expect(await screen.findByText("This account is already on your list.")).toBeTruthy();
    expect(container.querySelector("[data-add-account-code]")).toBeNull();
  });

  it("BR-CWP-034 — no contact on file DEAD-ENDS into ringing the office", async () => {
    // ⚠ It must never fall back to something weaker, and the screen must not
    // offer a code box there is no code for.
    find = async () => ({ matched: true, reason: "no_contact_on_file", account_ref: null });
    const { container } = draw();
    typeTwoFacts(container);
    fireEvent.click(screen.getByText("Find this account"));
    expect(await screen.findByText(/call the office/)).toBeTruthy();
    expect(container.querySelector("[data-add-account-code]")).toBeNull();
  });

  it("a wrong code refuses and does NOT show the added confirmation", async () => {
    find = async () => MATCHED;
    verify = async () => ({ linked: false, reason: "wrong" });
    const { container } = draw();
    typeTwoFacts(container);
    fireEvent.click(screen.getByText("Find this account"));
    await screen.findByText(/••• ••• 0144/);
    fireEvent.change(container.querySelector("#add-code")!, { target: { value: "000000" } });
    fireEvent.click(screen.getByText("Add this account"));
    expect(await screen.findByText("That code is not right.")).toBeTruthy();
    expect(container.querySelector("[data-add-account-done]")).toBeNull();
  });

  it("a right code confirms, and the confirmation repeats that bills stay separate", async () => {
    find = async () => MATCHED;
    verify = async () => ({ linked: true });
    const { container } = draw();
    typeTwoFacts(container);
    fireEvent.click(screen.getByText("Find this account"));
    await screen.findByText(/••• ••• 0144/);
    fireEvent.change(container.querySelector("#add-code")!, { target: { value: "123456" } });
    fireEvent.click(screen.getByText("Add this account"));
    const done = await screen.findByText(/Bills stay separate/);
    expect(done).toBeTruthy();
  });

  it("D9 — the rail lists what is already on this login, with a count in its head", () => {
    // ⚠ `DEF-CWP-3984`. The screen composed no `Panel` at all, so the one fact
    // this form needs — is the number I am about to type already here? — had
    // nowhere to be, and a duplicate was only refused after a round trip.
    const { container } = draw();
    const rail = container.querySelector("[data-testid='add-account-already']");
    expect(rail, "CWP-020 draws no ALREADY ON THIS LOGIN panel").not.toBeNull();
    expect(container.querySelector("[data-already-count]")?.textContent).toBe("2");
    expect(rail?.textContent).toContain("1408 Elm St · A");
    expect(rail?.textContent).toContain("ACC-10519-B");
  });

  it("D9 — the rail survives the step change and the confirmation", async () => {
    // The set does not stop being true when the form advances; the drawing
    // keeps the panel on both states, and a rail that vanished at step two
    // would be the same screen twice with different furniture.
    find = async () => MATCHED;
    verify = async () => ({ linked: true });
    const { container } = draw();
    typeTwoFacts(container);
    fireEvent.click(screen.getByText("Find this account"));
    await screen.findByText(/••• ••• 0144/);
    expect(container.querySelector("[data-testid='add-account-already']")).not.toBeNull();
    fireEvent.change(container.querySelector("#add-code")!, { target: { value: "482913" } });
    fireEvent.click(screen.getByText("Add this account"));
    await screen.findByText("It is on your list. Bills stay separate.");
    expect(container.querySelector("[data-testid='add-account-already']")).not.toBeNull();
  });

  it("B14 rule 31 — no database id reaches the page", async () => {
    find = async () => MATCHED;
    const { container } = draw();
    typeTwoFacts(container);
    fireEvent.click(screen.getByText("Find this account"));
    await screen.findByText(/••• ••• 0144/);
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });
});
