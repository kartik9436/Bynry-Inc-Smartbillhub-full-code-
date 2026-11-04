// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-028 (EP-CWP-06), the PREFERENCES half · Screen: CWP-025
// Rules:    BR-NOT-024 / CR-068 R4 (print is the FLOOR — the grid says ALWAYS
//           and offers NO control, not a disabled one) · BR-CWP-087 (the
//           consent, its date, and a way to withdraw that WRITES) · B14
//           rule 17 (a stated absence, never an empty table) · rule 31 (no
//           database id on screen) · rule 33 (a refusal is five or six words)
// Cases:    TC-3 (post is a chip, not a switch) · TC-4 (email switches) ·
//           TC-5 (going back to paper calls the withdrawal and never a delete)
//           · TC-9 (the two languages the portal offers, each named in its
//           own language, plus the reader's own where it is neither) · an
//           ABSENT consent is not a withdrawn one · the unreadable floor
//           states its absence rather than drawing an empty grid
// Defect:   DEF-CWP-4442 — PO 2026-09-07: *"currently in drop down show only 2
//           elnglish and spanish"*. TC-9 asserted ELEVEN until that day.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { offeredLocales } from "../components/language";
import type { PortalPreferences } from "../api/portalClient";

let answer: () => Promise<PortalPreferences> = async () => {
  throw new Error("no behaviour set");
};
let saves: Array<Record<string, unknown>> = [];
let withdrawals = 0;
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getPreferences: () => answer(),
    savePreferences: async (fields: Record<string, unknown>) => {
      saves.push(fields);
      return { accounts_updated: 4, account_ids: [] };
    },
    withdrawPaperless: async () => {
      withdrawals += 1;
      return { withdrawn: 1 };
    },
  };
});

const { PreferencesView } = await import("./Preferences");

const KINDS = ["invoice", "payment", "notice", "plan", "account", "move"] as const;

const BASE: PortalPreferences = {
  as_of: "2026-09-05",
  channels: ["post", "email", "text", "portal"],
  floor_readable: true,
  rows: KINDS.map((kind) => ({
    kind,
    post: "always" as const,
    email: "off" as const,
    text: "off" as const,
    portal: "always" as const,
  })),
  email_on: false,
  text_on: false,
  applies_to_every_document: true,
  election_varies: false,
  account_count: 4,
  // The server's offer, narrowed from eleven on 2026-09-07 (`DEF-CWP-4442`).
  locales: ["en", "es"],
  locale: "es-MX",
  paperless: {
    agreed_on: "2025-09-21",
    wording_version: "paperless-v1-2026-09",
    withdrawn_on: null,
    taken_on_screen: "CWP-009",
  },
};

function draw(patch: Partial<PortalPreferences> = {}) {
  answer = async () => ({ ...BASE, ...patch });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/my-details/preferences"]}>
      <Routes>
        <Route path="/:tenant/portal/my-details/preferences" element={<PreferencesView />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  saves = [];
  withdrawals = 0;
});
afterEach(cleanup);

describe("CWP-025 · how we contact you (US-CWP-028)", () => {
  it("draws the six document kinds and the four columns", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());
    expect(container.querySelector('[data-screen="CWP-025"]')).not.toBeNull();
    for (const kind of KINDS) {
      expect(container.querySelector(`[data-preference-row="${kind}"]`)).not.toBeNull();
    }
  });

  it("TC-3 — POST reads ALWAYS on every row and there is NO control for it", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());
    for (const kind of KINDS) {
      const cell = container.querySelector(`[data-cell="${kind}.post"]`);
      expect(cell?.getAttribute("data-state")).toBe("always");
      // ⚠ **NOT A DISABLED SWITCH.** A greyed toggle still reads as *somebody
      // could turn this off*; a chip reading ALWAYS does not.
      expect(cell?.querySelector("button")).toBeNull();
      expect(cell?.querySelector("input")).toBeNull();
    }
  });

  it("says out loud that one choice covers everything, above the table", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-applies-to-all]")).not.toBeNull());
    expect(container.querySelector("[data-applies-to-all]")?.textContent).toMatch(/4/);
    // And what switching a channel off does NOT do.
    expect(screen.getByText(/we mail everything, always/i)).toBeInTheDocument();
  });

  // ── CR-085 group I · the channel a utility has NOT switched on ───────────
  //
  // ⚠ **`channels` WAS SERVED AND READ BY NOTHING.** The drawing names this
  // twice and calls it *"the failure this panel exists to prevent"*: somebody
  // waiting for a text that can never be sent. Pine Hill has all four on, so
  // no walk of the running product could ever have shown it — which is why the
  // wire carries the list and why these two cases set it.
  it("a channel the utility has not switched on is STATED, never offered", async () => {
    const { container } = draw({ channels: ["post", "email", "portal"], text_on: false });
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());

    // No switch for it — an off switch that does nothing is worse than none.
    expect(container.querySelector('[data-segmented="text"]')).toBeNull();
    // And the row says so, by name, where the switch would have been.
    expect(container.querySelector('[data-channel-off="text"]')).not.toBeNull();
    // Email is untouched: one channel off is not both off.
    expect(container.querySelector('[data-segmented="email"]')).not.toBeNull();
  });

  it("a channel the utility HAS switched on keeps its switch", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());
    expect(container.querySelector('[data-segmented="text"]')).not.toBeNull();
    expect(container.querySelector("[data-channel-off]")).toBeNull();
  });

  // ── CR-085 group I · the two languages, screen 59 ────────────────────────
  it("names BOTH languages — the one on the account and the one being read", async () => {
    // The drawing's whole point: *"There are two and they can disagree."* The
    // panel named only the account's, so a customer reading Spanish with an
    // account set to English had no way to see which was which.
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());

    const site = container.querySelector("[data-website-language]");
    expect(site).not.toBeNull();
    // Named in its OWN language, never translated into the reader's (B14
    // rule 35) — the test suite reads English, so English names itself.
    expect(site?.textContent).toContain("English");
  });

  /**
   * `DEF-CWP-4935` — the sentence under that line stated something the product
   * does not do. It read *"Your bills and letters use the language above; this
   * site follows it."*, i.e. the two CANNOT differ.
   *
   * **PO ruling 2026-09-11, verbatim: *"(b) Allow them to differ - currently
   * bills are offered only in english"*.** The website ships in eleven
   * languages and the bill in one, so the two already differ for every
   * customer reading this screen in anything but English — which makes the old
   * wording FALSE as well as unwanted, and a defect rather than a design
   * difference.
   *
   * ⚠ **ASSERTED AS THE WHOLE SENTENCE, NOT AS A SUBSTRING.** A `toContain`
   * on *"this site follows"* passes on both wordings, which is exactly the
   * kind of check that cannot tell a pass from a fail (hard-won law 7).
   */
  it("DEF-CWP-4935 — the panel says what is TRUE about the two languages", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());
    const site = container.querySelector("[data-website-language]");
    const why = site?.nextElementSibling;
    expect(why?.textContent).toBe(
      "We send bills in English today; this site follows the language above.",
    );
  });

  it("TC-4 — email genuinely switches, and the save carries one field", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());
    const user = userEvent.setup();
    const group = container.querySelector('[data-segmented="email"]');
    const on = group?.querySelector('[data-segment="on"]') as HTMLElement;
    await user.click(on);
    await waitFor(() => expect(saves).toHaveLength(1));
    expect(saves[0]).toEqual({ email_on: true });
    // ⚠ **AND NOTHING ABOUT POST IS EVER IN A BODY** — the server refuses it by
    // name, and the screen must not be the thing that sends it.
    expect(JSON.stringify(saves)).not.toMatch(/post/);
  });

  it("says so when this login's accounts disagree, rather than showing one of them", async () => {
    const { container } = draw({ election_varies: true });
    await waitFor(() => expect(container.querySelector("[data-election-varies]")).not.toBeNull());
  });

  it("TC-5 — *Go back to paper* calls the withdrawal, and it is not a danger control", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());
    const button = screen.getByRole("button", { name: /go back to paper/i });
    // r10 rule 6 — danger is for DESTRUCTIVE commits, and this destroys
    // nothing: the consent row keeps its wording version and gains a date.
    expect(button.className).not.toMatch(/danger/);
    await userEvent.setup().click(button);
    await waitFor(() => expect(withdrawals).toBe(1));
  });

  it("shows the date the consent was agreed, and the wording version is never on screen", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-agreed-on]")).not.toBeNull());
    expect(container.querySelector("[data-agreed-on]")?.getAttribute("data-agreed-on")).toBe(
      "2025-09-21",
    );
    expect(container.querySelector("[data-consent-state]")?.getAttribute("data-consent-state")).toBe(
      "agreed",
    );
    // The version is a record, not a thing a customer reads (B14 rule 32).
    expect(container.innerHTML).not.toMatch(/paperless-v1/);
  });

  it("a withdrawn consent says so and offers no second withdrawal", async () => {
    const { container } = draw({
      paperless: { ...BASE.paperless!, withdrawn_on: "2026-08-14" },
    });
    await waitFor(() =>
      expect(container.querySelector('[data-consent-state="withdrawn"]')).not.toBeNull(),
    );
    expect(screen.queryByRole("button", { name: /go back to paper/i })).toBeNull();
  });

  it("an ABSENT consent is not drawn as a withdrawn one (US-CWP-014 TC-2)", async () => {
    const { container } = draw({ paperless: null });
    await waitFor(() => expect(container.querySelector("[data-no-consent]")).not.toBeNull());
    expect(container.querySelector("[data-consent-state]")).toBeNull();
    expect(screen.queryByRole("button", { name: /go back to paper/i })).toBeNull();
  });

  it("TC-9 — the TWO the portal offers, each named in its own language", async () => {
    // ⚠ **THIS ASSERTED ELEVEN UNTIL 2026-09-07** (`DEF-CWP-4442`). PO,
    // verbatim: *"currently in drop down show only 2 elnglish and spanish"*.
    // `BASE.locale` is `es-MX` — a stored value outside the two — so this
    // reader sees three, which is the case below.
    const { container } = draw({ locale: "en" });
    await waitFor(() => expect(container.querySelector("#preferences-locale")).not.toBeNull());
    const options = container.querySelectorAll("#preferences-locale option");
    const labels = Array.from(options).map((option) => option.textContent);
    // Not an English list: `Español` is `Español` on every screen (B14 r35).
    expect(labels).toEqual(["English", "Español"]);
    // B14 rule 31 — the VALUE is the code, the text a person reads is not.
    expect(labels).not.toContain("en");
  });

  it("lists the reader's OWN language when it is neither, rather than going blank", async () => {
    // ⚠ **THE DEFECT THE RULING CARRIED WITH IT, ON THE SCREEN IT WAS FILED
    // AGAINST.** `Preferences.tsx` renders `value={locale}` against options
    // built from the offer; a stored `es-MX` over a two-item list is a BLANK
    // `<select>` — no error, `tsc` green, every `toContain` passing. Nobody's
    // stored choice is reset (decision log 2026-09-07), so it is listed.
    const { container } = draw({ locale: "de" });
    await waitFor(() => expect(container.querySelector("#preferences-locale")).not.toBeNull());
    const labels = Array.from(container.querySelectorAll("#preferences-locale option")).map(
      (option) => option.textContent,
    );
    expect(labels).toEqual(["English", "Español", "Deutsch"]);
    const select = container.querySelector<HTMLSelectElement>("#preferences-locale");
    expect(select?.value).toBe("de");
    // The assertion that fails on the whole point of this fix.
    expect(select?.value).not.toBe("");
  });

  it("the caption counts what is on SCREEN, not what the server offered", async () => {
    // ⚠ **THE HELPER SAID *2 languages available.* UNDER A LIST OF THREE**
    // until the count was moved to the rendered array (`DEF-CWP-4442`). It is
    // the catalogue's own `{{count}}` string — no copy was written for this and
    // `G15`'s untranslated count did not move.
    const { container } = draw({ locale: "de" });
    await waitFor(() => expect(container.querySelector("#preferences-locale")).not.toBeNull());
    expect(container.textContent).toContain("3 languages available.");
    cleanup();
    const plain = draw({ locale: "en" });
    await waitFor(() =>
      expect(plain.container.querySelector("#preferences-locale")).not.toBeNull(),
    );
    expect(plain.container.textContent).toContain("2 languages available.");
  });

  it("shows the guest dropdown's list and this one as ONE list", async () => {
    // ⚠ Two controls for one setting offering different lists is how a
    // product tells one person two things. Both call `offeredLocales` over
    // the server's own offer; this asserts the SHAPE they share rather than
    // trusting two screens to stay in step.
    const { container } = draw({ locale: "es-MX" });
    await waitFor(() => expect(container.querySelector("#preferences-locale")).not.toBeNull());
    expect(
      Array.from(container.querySelectorAll("#preferences-locale option")).map(
        (option) => (option as HTMLOptionElement).value,
      ),
    ).toEqual(offeredLocales(BASE.locales, "es-MX"));
  });

  it("B14 rule 17 — an unreadable floor STATES the absence and draws no grid", async () => {
    const { container } = draw({ floor_readable: false, rows: [] });
    await waitFor(() => expect(container.querySelector("[data-floor-unreadable]")).not.toBeNull());
    // ⚠ An empty table would assert *nothing is sent*, which is the opposite
    // of what is true.
    expect(container.querySelector("[data-preference-grid]")).toBeNull();
  });

  it("hard-won law 2 — this screen is REACHABLE, and it leads back", async () => {
    // ⚠ **A ROUTE NOTHING LINKS TO IS DEAD UI**: it renders nothing a person
    // can get to, every test passes, and the feature does not exist. The
    // door in is on `CWP-024` (asserted in `MyDetails.dom.test.tsx`); this is
    // the way back.
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());
    const back = container.querySelector('a[href="/pine-hill/portal/my-details"]');
    expect(back).not.toBeNull();
  });

  it("B14 rule 31 — nothing on the screen is a database id", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-preference-grid]")).not.toBeNull());
    expect(container.innerHTML).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    );
  });
});
