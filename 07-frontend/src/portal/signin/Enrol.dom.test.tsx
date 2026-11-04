// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-018 (EP-CWP-05) — prove it is you: a code, to a contact
//           already on file · US-CWP-019 — choose a password, and see what the
//           login will let you do. Screens: CWP-017 · CWP-018
//
//           ⚠ **`Enrol.tsx`'s OWN TRACE HEADER CITES `US-CWP-016`, `017` AND
//           `018` FOR THESE THREE SCREENS, AND THAT IS ONE LOW THROUGHOUT WAVE
//           E (`DEF-CWP-3862`).** `EP-CWP-05` numbers them `US-CWP-017` (find
//           my account, `CWP-016`), `US-CWP-018` (prove it is you, `CWP-017`)
//           and `US-CWP-019` (choose a password, `CWP-018`) — the wave read a
//           story id off the SCREEN number beside it. The screens are right and
//           nothing is renumbered; the citations are.
//
// Rules:    BR-CWP-033 (the code goes ONLY to a contact already on the account
//           and is shown MASKED — never to an address typed on the previous
//           screen) · BR-CWP-034 (no contact ⇒ dead-end into *ring the office*)
//           · BR-CWP-035 (ten minutes, and an expired code is its OWN answer
//           with a resend, never an error page) · BR-CWP-032 (matched and
//           proven are two states; between them the visitor has been told
//           NOTHING) · BR-CWP-037 (the tenant's own password policy, read and
//           never hardcoded) · BR-CWP-039 (a consequence panel before the
//           commit, naming what the login can and cannot do) · B14 rule 31 ·
//           rule 33 · rule 36
// Cases:    US-CWP-018 TC-1 (the masked number and the ten minutes) · TC-2 (an
//           expired code is a sentence with a resend) · TC-3 (no contact
//           dead-ends) · TC-7 (a resend re-issues) · US-CWP-019 TC-1 · TC-2
//           (the policy is the SERVER's) · TC-3 (mismatched confirmations are
//           refused and neither value is echoed) · TC-5 (the panel names the
//           account, the address, the services and the balance, and says what
//           the login CANNOT do)
//
//           ⚠ **THIS FILE IS THE ONE `Enrol.tsx` HAS NAMED SINCE WAVE E AND
//           NOBODY WROTE** — hard-won law 1: *a comment claiming a guarantee is
//           not the guarantee*. Three screens shipped with a `Tests:` line
//           pointing at `src/portal/signin/Enrol.test.tsx`, which does not
//           exist. Filed as `DEF-CWP-3863`.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type {
  EnrolConsequences,
  FindAccountResult,
  SetPasswordResult,
  VerifyCodeResult,
} from "../api/portalClient";

let found: FindAccountResult = { matched: false };
let verdict: VerifyCodeResult = { result: "ok" };
let panel: EnrolConsequences;
let created: SetPasswordResult = { ok: true };
let finds = 0;
let sent: Array<Record<string, unknown>> = [];

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    findAccount: async (body: Record<string, unknown>) => {
      finds += 1;
      sent.push(body);
      return found;
    },
    verifyCode: async (body: Record<string, unknown>) => {
      sent.push(body);
      return verdict;
    },
    getConsequences: async () => panel,
    setPassword: async (body: Record<string, unknown>) => {
      sent.push(body);
      return created;
    },
  };
});

const { EnrolView } = await import("./Enrol");

const MATCHED: FindAccountResult = {
  matched: true,
  account_ref: "ref-opaque-not-an-id",
  sent_to: "••• ••• 4218",
  channel: "sms",
  expires_in_minutes: 10,
};

const PANEL: EnrolConsequences = {
  account_no: "ACC-10432-A",
  service_address: "1408 Elm St · A",
  services: ["water", "sewer", "trash"],
  balance: "142.1800",
  currency: "USD",
  policy_min_length: 8,
  // ⚠ THE SERVER'S OWN THREE KEYS, copied from `api.enrol_consequences`
  // rather than invented — a fixture that names a key no catalogue holds
  // proves the panel renders and hides that it renders a raw key.
  cannot: ["close_account", "change_owner", "move_out"],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, AND IT WAS NOT UNTIL NOW.** This
 * helper rendered `EnrolView` bare inside a `MemoryRouter` with no
 * `/:tenant/portal` route, so `useParams().tenant` was undefined and every
 * address the screen builds came out `//portal/…` — a protocol-relative URL to
 * another host, which reads as a perfectly good string to `toContain`. It is
 * the same fixture fault that hid `DEF-CWP-3925` on the front page, and it
 * mattered here the moment this screen grew a door.
 */
function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/enrol"]}>
      <Routes>
        <Route path="/:tenant/portal/enrol" element={<EnrolView />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function findMyAccount() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/account number/i), "ACC-10432-A");
  // ⚠ **`zip code`, AND THIS READ `postcode` UNTIL `DEF-CWP-4855`.** The
  // blueprint's conventions block C names the words a North American utility
  // customer knows and *ZIP code* is in the list; the English catalogue said
  // *Postcode*, which is British. The ten other catalogues were already right
  // in their own languages — Postleitzahl, código postal, CAP, CEP, पिन कोड,
  // 郵便番号 — so only `en.json` moved (B14 rule 35).
  await user.type(screen.getByLabelText(/zip code/i), "78702");
  await user.type(screen.getByLabelText(/last name|company/i), "Alvarez");
  await user.click(screen.getByRole("button", { name: /continue/i }));
}

beforeEach(() => {
  found = MATCHED;
  verdict = { result: "ok" };
  panel = PANEL;
  created = { ok: true };
  finds = 0;
  sent = [];
});
afterEach(cleanup);

describe("CWP-016 · find your account (US-CWP-017)", () => {
  /**
   * ⚠ **THE ESCAPE HATCH, AND `s4` SAYS WHY IT IS ON THIS SCREEN:** *"Quick-pay
   * is offered on the same screen. Someone who cannot complete this must not
   * leave without having paid."* The account number is the barrier this whole
   * form is built around, and the rail's only answer was *ring the office* —
   * so a person holding a bill they could not enrol with had no way to settle
   * it and no door out of the screen.
   *
   * The assertion is on the ADDRESS, not on the words: a label styled like a
   * link is what `DEF-CWP-3925` shipped eight of.
   */
  it("offers quick pay to somebody who cannot find their account number", () => {
    draw();
    const door = document.querySelector('[data-where-next="enrol"] a[href="/pine-hill/portal/pay"]');
    expect(door, "no way to pay from the enrolment screen").not.toBeNull();
    // Not a tenant-less address — the fixture fault that hid the last eight.
    expect(door?.getAttribute("href")).not.toMatch(/^\/\//);
  });

  /**
   * ⚠ **`DEF-CWP-4858` — THE COMMIT WAS LIVE OVER THREE EMPTY REQUIRED FIELDS,
   * ON THE ONE GUEST FORM THAT LOCKS AFTER THREE WRONG TRIES.**
   *
   * `BR-CWP-036` gives this form three attempts and then fifteen minutes in
   * the cold, and the rail says so in as many words two inches away. A
   * *Continue →* that can be pressed with every box blank spends one of those
   * three on a submission that cannot possibly match — and the only person who
   * presses it is the one who has not understood the form, which is exactly
   * the person the lock will then punish.
   *
   * Four of the five guest forms already guarded their commit and named the
   * reason; this was the fifth. The assertion is on BOTH halves, because a
   * disabled control with no reason is its own defect (`BR-CWP-056`).
   */
  it("refuses Continue until all three boxes are filled, and says why (DEF-CWP-4858)", async () => {
    draw();
    const commit = screen.getByRole("button", { name: /continue/i });
    expect(commit).toBeDisabled();
    expect(commit).toHaveAttribute("title", "Fill in all three boxes.");

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/account number/i), "ACC-10432-A");
    await user.type(screen.getByLabelText(/zip code/i), "78702");
    // Two of three is still not three.
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();

    await user.type(screen.getByLabelText(/last name|company/i), "Alvarez");
    expect(screen.getByRole("button", { name: /continue/i })).toBeEnabled();

    // ⚠ **AND THE GUARD MUST NOT HAVE COST THE SCREEN ITS COMMIT** — a
    // `ready` that never becomes true is the same defect wearing the fix
    // (hard-won law 7: what would make this check pass wrongly?).
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(finds).toBe(1);
  });

  it("spends no attempt on an empty form (BR-CWP-036)", async () => {
    draw();
    await userEvent.setup().click(screen.getByRole("button", { name: /continue/i }));
    expect(finds, "an empty submission reached the server and spent a try").toBe(0);
  });
});

describe("CWP-017 · prove it is you (US-CWP-018)", () => {
  it("TC-1 — names the MASKED contact the server sent, and the ten minutes", async () => {
    const { container } = draw();
    await findMyAccount();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-017"]')).not.toBeNull(),
    );
    // ⚠ RENDERED AS IT ARRIVED. Masking here as well would be a second
    // implementation of BR-CWP-033 and the two would drift.
    expect(container.querySelector("[data-enrol-sentto]")?.textContent).toBe("••• ••• 4218");
    expect(container.innerHTML).toMatch(/ten minutes|10 minutes/i);
  });

  it("BR-CWP-033 — nothing the visitor typed is ever offered as a destination", async () => {
    const { container } = draw();
    await findMyAccount();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-017"]')).not.toBeNull(),
    );
    // The screen has no field for *send it somewhere else*, and the body it
    // posted named no address at all.
    expect(container.querySelector('input[type="email"]')).toBeNull();
    expect(JSON.stringify(sent)).not.toMatch(/@/);
  });

  it("D11 — the six-digit code is a DialInput, not the same box as a surname", async () => {
    // ⚠ **`DEF-CWP-3986`.** The drawing has asked for this since the wave was
    // written — *"`DialInput`-style *Six-digit code** (narrow, ≈ 240px, spaced
    // digits)"* — and the screen rendered a plain `TextInput`, which is the
    // identical control to *Last name, or company name* one step earlier.
    //
    // ⚠ **THE CLASS ASSERTIONS ARE THE POINT AND THEY ARE RULED STEP NAMES.**
    // `09-component-inventory.md` spells this `font-mono text-[22px]
    // tracking-[0.35em]`; eslint refuses both arbitrary forms, so the built
    // spelling is `text-metric-sm` (22px) and `tracking-dial` (0.35em) and the
    // pixels are unchanged. Asserting the NAMES here is what catches a later
    // lane "tidying" them back into brackets, which would render nothing.
    const { container } = draw();
    await findMyAccount();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-017"]')).not.toBeNull(),
    );
    const dial = container.querySelector("[data-dial-input]");
    expect(dial).not.toBeNull();
    expect(dial?.getAttribute("id")).toBe("enrol-code");
    expect(dial?.getAttribute("maxlength")).toBe("6");
    expect(dial?.getAttribute("inputmode")).toBe("numeric");
    for (const step of ["font-mono", "text-metric-sm", "tracking-dial", "h-14"]) {
      expect(dial?.className).toContain(step);
    }
  });

  it("BR-CWP-032 — the code step shows NOTHING about the account", async () => {
    const { container } = draw();
    await findMyAccount();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-017"]')).not.toBeNull(),
    );
    // Matched is not proven: no name, no balance, no address until the code
    // comes back.
    for (const leak of ["Alvarez", "142.18", "1408 Elm", "ACC-10432"]) {
      expect(container.innerHTML).not.toMatch(new RegExp(leak, "i"));
    }
  });

  it("TC-2 — an expired code is its OWN sentence, with the resend still there", async () => {
    const { container } = draw();
    await findMyAccount();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-017"]')).not.toBeNull(),
    );
    verdict = { result: "expired" };
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/six-digit|code/i), "418902");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(container.querySelector("[data-enrol-refused]")).not.toBeNull());
    // ⚠ NOT AN ERROR PAGE AND NOT A RESTART — the flow stays on CWP-017 and
    // the resend is beside the message (`BR-CWP-035`).
    expect(container.querySelector('[data-screen="CWP-017"]')).not.toBeNull();
    expect(screen.getByRole("button", { name: /again/i })).toBeInTheDocument();
  });

  it("TC-7 — *Send it again* re-issues, which is what invalidates the first code", async () => {
    draw();
    await findMyAccount();
    await waitFor(() => expect(finds).toBe(1));
    await userEvent.setup().click(screen.getByRole("button", { name: /again/i }));
    await waitFor(() => expect(finds).toBe(2));
  });

  it("TC-3 — no contact on file dead-ends, and no code step is drawn", async () => {
    found = { matched: false, reason: "no_contact_on_file" };
    const { container } = draw();
    await findMyAccount();
    await waitFor(() => expect(container.querySelector("[data-enrol-refused]")).not.toBeNull());
    // ⚠ IT MUST NOT FALL BACK TO SOMETHING WEAKER (`BR-CWP-034`): there is no
    // code box at all, and the visitor is still on CWP-016.
    expect(container.querySelector('[data-screen="CWP-017"]')).toBeNull();
    expect(container.querySelector('[data-screen="CWP-016"]')).not.toBeNull();
  });

  it("states the three tries BEFORE they are spent (BR-CWP-036)", () => {
    const { container } = draw();
    expect(container.querySelector("[data-enrol-tries]")?.textContent).toBeTruthy();
  });
});

describe("CWP-018 · choose a password (US-CWP-019)", () => {
  async function reachStepThree() {
    await findMyAccount();
    await waitFor(() => expect(screen.queryByLabelText(/six-digit|code/i)).not.toBeNull());
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/six-digit|code/i), "418902");
    await user.click(screen.getByRole("button", { name: /verify/i }));
  }

  it("TC-5 — the panel names the account, the address, the services and the balance", async () => {
    const { container } = draw();
    await reachStepThree();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-018"]')).not.toBeNull(),
    );
    expect(screen.getByText("ACC-10432-A")).toBeInTheDocument();
    expect(screen.getByText("1408 Elm St · A")).toBeInTheDocument();
    // ⚠ FOUR DECIMALS ON THE WIRE, TWO ON THE SCREEN (hard rule 2).
    expect(container.querySelector("[data-enrol-balance]")?.textContent).toBe("$142.18");
    // ⚠ AND WHAT THE LOGIN CANNOT DO IS ON THE SCREEN, not implied by its
    // absence (`BR-CWP-039`).
    expect(container.innerHTML).toMatch(/cannot|not be able/i);
  });

  it("TC-2 — the minimum length is the SERVER's, not a number in this file", async () => {
    panel = { ...PANEL, policy_min_length: 12 };
    const { container } = draw();
    await reachStepThree();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-018"]')).not.toBeNull(),
    );
    expect(container.innerHTML).toMatch(/12/);
    expect(container.innerHTML).not.toMatch(/\b8 characters\b/);
  });

  it("TC-3 — the commit is held until both boxes match, and neither is echoed back", async () => {
    const { container } = draw();
    await reachStepThree();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-018"]')).not.toBeNull(),
    );
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/new password/i), "Elm-Street-1408");
    await user.type(screen.getByLabelText(/again/i), "Elm-Street-1409");
    const commit = screen.getByRole("button", { name: /create my login/i });
    expect(commit).toBeDisabled();
    // ⚠ AND NEITHER VALUE IS READABLE: both boxes are `type="password"`, so a
    // mismatch is not resolved by somebody reading one off the screen.
    expect(container.querySelector("#enrol-new")?.getAttribute("type")).toBe("password");
    expect(container.querySelector("#enrol-again")?.getAttribute("type")).toBe("password");
    // Nothing is refused yet either — the guard is the control, not a message.
    expect(container.querySelector("[data-enrol-refused]")).toBeNull();
  });

  it("TC-1 — matching passwords make the commit live, and it posts once", async () => {
    const { container } = draw();
    await reachStepThree();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-018"]')).not.toBeNull(),
    );
    const user = userEvent.setup();
    await user.type(container.querySelector("#enrol-email") as HTMLElement, "m.alvarez@example.com");
    await user.type(screen.getByLabelText(/new password/i), "Elm-Street-1408");
    await user.type(screen.getByLabelText(/again/i), "Elm-Street-1408");
    await user.click(screen.getByRole("button", { name: /create my login/i }));
    await waitFor(() =>
      expect(sent.filter((body) => "password" in body)).toHaveLength(1),
    );
  });

  it("a refused password shows the SERVER's reasons and stays on the screen", async () => {
    created = { ok: false, failures: ["too_short"], min_length: 12 };
    const { container } = draw();
    await reachStepThree();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-018"]')).not.toBeNull(),
    );
    const user = userEvent.setup();
    await user.type(container.querySelector("#enrol-email") as HTMLElement, "m.alvarez@example.com");
    await user.type(screen.getByLabelText(/new password/i), "short1A");
    await user.type(screen.getByLabelText(/again/i), "short1A");
    await user.click(screen.getByRole("button", { name: /create my login/i }));
    await waitFor(() => expect(container.querySelector("[data-enrol-refused]")).not.toBeNull());
    expect(container.querySelector('[data-screen="CWP-018"]')).not.toBeNull();
  });

  it("B14 rule 31 — the account REFERENCE never reaches the screen as a visible value", async () => {
    const { container } = draw();
    await reachStepThree();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-018"]')).not.toBeNull(),
    );
    // The opaque ref travels in bodies and is drawn nowhere; the number a
    // person reads is `ACC-10432-A`, which is printed on their bill.
    expect(container.innerHTML).not.toMatch(/ref-opaque/);
    expect(container.innerHTML).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    );
  });
});
