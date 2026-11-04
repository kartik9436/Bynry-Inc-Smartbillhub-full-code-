// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-020 (EP-CWP-03) · US-CWP-023 · US-CWP-024
//           Screens: CWP-022 and every signed-in screen after it
// Rules:    09-component-inventory.md §1 (a LABEL when the set has one entry) ·
//           BR-CWP-013 (the set is FLAT) · BR-CWP-015 (totalled, never merged)
//           · BR-CWP-099 + PO 2026-09-04 (our accent is the default; a
//           utility's hex OVERRIDES it — one variable) · B14 rule 31
// Cases:    the switcher's two shapes · the six tabs · the initials ·
//           the accent override and its absence · the money formatter
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import pkg from "../../../package.json";

import type { PortalFront } from "../api/guestClient";
import type { PortalAccount } from "../api/portalClient";
import { formatMoney } from "../signin/Enrol";
import { PORTAL_SCREENS } from "../routing/screenIds";
import {
  AccountSwitcher,
  MESSAGES_SCREEN_ID,
  PORTAL_TABS,
  PortalShell,
  initialsOf,
  messagesRoute,
  routedTabs,
  tabIsRouted,
} from "./PortalShell";

function front(hex: string | null = "#EC3013"): PortalFront {
  return {
    tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: hex, brand_accent_hex: null },
    is_live: true,
    // `DEF-CWP-3994` — the tenant's Regional settings ride on the front
    // payload, and the type makes them REQUIRED so a fixture cannot
    // quietly omit them and hide the wire being absent.
    regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
    // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`).
    locales: ["en", "es"],
    cards: [],
    links: { help: false, visit: false },
    services: [],
    strapline: null,
    office_hours_text: null,
    emergency_phone: null,
  };
}

function account(id: string, label: string, over: Partial<PortalAccount> = {}): PortalAccount {
  return {
    id,
    account_no: `ACC-${id}`,
    label,
    permissions: ["see", "download", "pay"],
    source: "holder",
    is_master: false,
    ...over,
  };
}

function shell(accounts: PortalAccount[], hex: string | null = "#EC3013") {
  // ⚠ **RENDERED UNDER THE REAL `:tenant` ROUTE, and the first draft was not.**
  // `usePortalPath` reads the tenant off `useParams`, so a shell rendered on a
  // bare `MemoryRouter` builds every tab as `//portal/...` and `aria-current`
  // lands on nothing — which is exactly what this file caught, and exactly what
  // a `toContain("data-tab")` assertion would have passed over.
  // ⚠ **AND INSIDE A `QueryClientProvider`** — the header's *Sign out*
  // (`DEF-CWP-4359`) clears the cache on its way out, so the frame reads a
  // query client the way every screen inside it already does.
  return renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
      <Routes>
        <Route path="/:tenant/portal/*" element={
      <PortalShell
        front={front(hex)}
        displayName="Maria Alvarez"
        accounts={accounts}
        currentAccountId={accounts[0]?.id ?? null}
        onAccountChange={() => undefined}
      >
        <p>body</p>
      </PortalShell>
        } />
      </Routes>
    </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the account bar — one line under the menu, every signed-in screen", () => {
  // PO ruling 2026-09-08: *"here header bar should ahve menu - and below that we
  // should have a line for account - this should be consitent across registered
  // user login"*. `AccountBar` is drawn by the FRAME, so *consistent across
  // every screen* is a structural fact rather than 50 screens each remembering.
  it("names the account and where it is, on a login with one account", () => {
    const html = shell([account("a1", "1408 Elm St · A")]);
    expect(html).toContain('data-account-bar=""');
    // The utility's own printed reference — the number on the bill, which is
    // what a person reads down the phone. NOT `account.id`, asserted below.
    expect(html).toContain("Account ACC-a1");
    expect(html).toContain("1408 Elm St · A");
  });

  it("draws NO control when there is nothing to choose between", () => {
    // ⚠ The component inventory's rule is *one entry means a label, not a
    // control*, and this is that rule kept — the bar states the account as
    // text and offers no `<select>` at all. NOT a disabled one, which looks
    // broken. The absence is the assertion.
    const html = shell([account("a1", "1408 Elm St · A")]);
    expect(html).not.toContain("<select");
    expect(html).not.toContain('data-account-switcher=');
  });

  it("never draws the database id (B14 rule 31)", () => {
    // The NUMBER is drawn and that is not a breach: `account_no` is the
    // utility's printed reference — it is on the bill and a person reads it
    // down the phone — while `id` is a uuid nobody has ever read out. Rule 31
    // forbids the second, not the first.
    //
    // ⚠ **THE ACCOUNT NUMBER IS GIVEN EXPLICITLY HERE AND THAT MATTERS.** The
    // `account()` helper defaults `account_no` to `ACC-${id}`, which is fine
    // for every other case and useless for this one: with a uuid id the
    // fixture's own number CONTAINS the uuid, so the assertion fails on the
    // fixture rather than on the screen. A test whose subject is *the id must
    // not appear* has to be given data where the two are actually different.
    const html = shell([
      account("11111111-2222-3333-4444-555555555555", "22 Palm Ct", { account_no: "100234" }),
    ]);
    expect(html).toContain("Account 100234");
    expect(html).toContain("22 Palm Ct");
    expect(html).not.toContain("11111111-2222");
  });

  it("says so when the account is billed to the owner", () => {
    const html = shell([account("a1", "1408 Elm St · Common areas", { is_master: true })]);
    expect(html).toContain("Billed to you as owner");
  });

  it("draws nothing at all for a login with no account yet", () => {
    // ⚠ `BR-CWP-093` — an empty labelled row reads as a fault, which is the
    // same reason an unbuilt tab is dropped rather than greyed. A person who
    // has enrolled but not linked an account sees no bar, not an empty one.
    const html = shell([]);
    expect(html).not.toContain('data-account-bar=""');
  });

  it("the account is NOT in the header row any more — it moved, it was not copied", () => {
    // ⚠ Two account controls in one frame would be two answers to one
    // question. The header row keeps the utility, the errands and the way out.
    const html = shell([account("a1", "1408 Elm St · A"), account("a2", "22 Palm Ct")]);
    const header = html.slice(0, html.indexOf('data-account-bar=""'));
    expect(header).not.toContain("data-account-switcher");
    expect(header).toContain('data-link="brand_home"');
  });
});

describe("the account switcher", () => {

  it("is a real <select> of FLAT entries when the set has more — in the bar now", () => {
    const html = shell([
      account("a1", "1408 Elm St · A"),
      account("a2", "1408 Elm St · B"),
      account("a3", "1408 Elm St · Common areas", { is_master: true }),
      account("a4", "22 Palm Ct"),
    ]);
    expect(html).toContain('data-account-switcher="select"');
    expect(html).toContain('data-account-count="4"');
    // BR-CWP-013 — a master account is one more OPTION, never a parent. There
    // is no nesting in the markup and this is what would catch one.
    expect(html).not.toContain("<optgroup");
    expect((html.match(/<option/g) ?? []).length).toBe(4);
    // ⚠ **WHERE it is, not merely that it exists.** The seed has one portal
    // login holding one account, so the multi-account bar CANNOT be walked in
    // a browser on this data — which makes this the only proof that the
    // switcher moved rather than merely still rendering somewhere. Asserted by
    // ORDER in the markup: the bar opens before the select and the header row
    // closes before the bar.
    expect(html.indexOf('data-account-bar=""')).toBeLessThan(html.indexOf("<select"));
    expect(html.indexOf("</header>")).toBeLessThan(html.indexOf('data-account-bar=""'));
  });

  it("shows the address and never the id (B14 rule 31)", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <AccountSwitcher
          accounts={[account("11111111-2222-3333-4444-555555555555", "1408 Elm St · A")]}
          current={null}
          onChange={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(html).toContain("1408 Elm St · A");
    expect(html).not.toContain("11111111-2222");
  });
});

describe("the shell", () => {
  it("declares six tabs and draws every one the portal actually serves", () => {
    const html = shell([account("a1", "1408 Elm St · A")]);
    expect(PORTAL_TABS).toHaveLength(6);
    for (const tab of routedTabs()) expect(html).toContain(`data-tab="${tab.key}"`);
  });

  it("points every drawn tab at an address a route serves (DEF-CWP-3902)", () => {
    // ⚠ **THE VERSION OF THIS FILE THAT SHIPPED ASSERTED THE OPPOSITE OF WHAT
    // IT MEANT.** `toContain('data-tab="details"')` asks whether the tab is in
    // the markup; it can never ask whether pressing it goes anywhere. Two of
    // the six pointed at addresses `screenIds.ts` does not register —
    // `/details` (the screen is at `/my-details`) and `/requests` (wave 3) —
    // so `useRoutes` matched nothing and drew a blank page under a live
    // header, with this test green.
    for (const tab of routedTabs()) {
      expect(PORTAL_SCREENS.some((screen) => screen.path === tab.to)).toBe(true);
    }
  });

  it("names the tabs whose screens are not built yet — and there are none left", () => {
    // ⚠ **THIS ASSERTION IS A TRIPWIRE, NOT A DESCRIPTION, AND IT FIRED
    // EXACTLY AS IT WAS WRITTEN TO (2026-09-04).** It read `["requests"]`
    // until `US-CWP-060` registered `/requests`, and it went RED on the commit
    // that did — telling that lane in one line that the sixth tab was now
    // live. A `toBeGreaterThan(0)` here would have let the tab return
    // unnoticed, or never return at all.
    //
    // ⚠ **IT IS KEPT AT `[]` RATHER THAN DELETED, AND THAT IS THE POINT OF THE
    // SHAPE.** The list is the ledger of tabs that lead nowhere; an empty
    // ledger is a claim worth asserting, and the next tab added ahead of its
    // screen fails here rather than shipping as a blank page under a live
    // header (`DEF-CWP-3902`).
    expect(PORTAL_TABS.filter((tab) => !tabIsRouted(tab)).map((tab) => tab.key)).toEqual([]);
    expect(shell([account("a1", "x")])).toContain('data-tab="requests"');
  });

  /**
   * ⚠ **THIS CASE USED TO ASSERT THE BELL WAS PRESENT AND NOW ASSERTS THE
   * OPPOSITE, AND THAT IS THE FIX (`DEF-CWP-3982`, audit row D7).** *Messages*
   * was a `<span>` beside `Help`, which is a link: plain text with no
   * destination, no count and no sentence, on every signed-in screen. Hard-won
   * law 2's mirror — a control that looks live and is not — and the old case
   * asserting `data-shell-bell=""` was green over it, because a `toContain`
   * asks whether a mark EXISTS and never whether it goes anywhere.
   *
   * ⚠ **IT IS ABSENT RATHER THAN GREYED, on this file's own precedent:**
   * `routedTabs` already drops an unbuilt tab rather than disabling it
   * (`BR-CWP-093`), and two doors in one header must not answer the same
   * question two different ways.
   */
  it("does not draw Messages while CWP-053 is unbuilt (DEF-CWP-3982)", () => {
    const html = shell([account("a1", "1408 Elm St · A")]);
    if (messagesRoute() === null) {
      expect(html).not.toContain("data-shell-bell");
      expect(html).not.toContain("Messages");
    }
  });

  /**
   * ⚠ **THE CASE THAT FIRES WHEN THE HOLD EXPIRES** — written in the same
   * commit as the hold, which is what `DEF-CWP-3925` cost a week for want of.
   * It asserts the destination **by address and by screen id**, so the day
   * `CWP-053` is registered this file says so out loud.
   *
   * The control releases ITSELF — `messagesRoute()` reads the register — so
   * the first half below is already handled and cannot rot. What still needs a
   * person is the UNREAD COUNT (`DEF-CWP-3901`): it is `read_at IS NULL` on the
   * portal's own per-recipient row, which `US-CWP-067` builds, and no prop can
   * be added for it before then (the last one was dead UI nothing passed).
   * That is what the failure message names.
   */
  it("HOLD EXPIRY: when CWP-053 lands, Messages must open it AND carry its count", () => {
    const to = messagesRoute();
    const built = PORTAL_SCREENS.find((screen) => screen.id === MESSAGES_SCREEN_ID);
    if (to === null) {
      // Still held. The two facts that make the hold true, asserted so a lane
      // cannot half-land the screen: no row, and therefore no door.
      expect(built).toBeUndefined();
      return;
    }
    const html = shell([account("a1", "1408 Elm St · A")]);
    expect(html).toContain(`href="/pine-hill/portal${to}"`);
    expect(html).toContain('data-shell-bell=""');
    expect(
      html.includes("data-shell-bell-count"),
      `CWP-053 is now a routed portal screen at ${to}, so the Messages hold has expired. ` +
        "The word already links itself. What is still missing is the unread count " +
        "(DEF-CWP-3901): read it from the portal's own per-recipient message row, which " +
        "US-CWP-067 builds, and render it as data-shell-bell-count.",
    ).toBe(true);
  });

  it("marks exactly one tab aria-current", () => {
    const html = shell([account("a1", "1408 Elm St · A")]);
    expect((html.match(/aria-current="page"/g) ?? []).length).toBe(1);
  });

  it("overrides the product's accent ONLY when the utility has a hex", () => {
    // The PO's ruling of 2026-09-04, both directions in one pair of cases: a
    // utility WITH a colour gets theirs; one WITHOUT gets r10's, because
    // nothing overrode `:root`. An empty string must write nothing — writing
    // `--color-accent: ""` would override the style guide with garbage and
    // return exactly the unbranded tenants to greyscale.
    expect(shell([account("a1", "x")], "#0F7B6C")).toContain("--color-accent:#0F7B6C");
    expect(shell([account("a1", "x")], null)).not.toContain("--color-accent:");
    expect(shell([account("a1", "x")], "")).not.toContain("--color-accent:");
  });
});

describe("initials", () => {
  it("is the reader's own name and never an id", () => {
    expect(initialsOf("Maria Alvarez")).toBe("MA");
    expect(initialsOf("Kestrel")).toBe("K");
    expect(initialsOf(null)).toBe("?");
  });
});

describe("money on screen", () => {
  it("shows four stored decimals as two, and never through a float", () => {
    // Hard rule 2 in a browser: `Number("142.1800")` is a double, and the day a
    // figure is summed on screen that is a rounding error a customer can see.
    expect(formatMoney("142.1800", "USD")).toBe("$142.18");
    expect(formatMoney("0.0000", null)).toBe("$0.00");
    expect(formatMoney("872.8200", "USD")).toBe("$872.82");
    expect(formatMoney("1234567.8900", "USD")).toBe("$1,234,567.89");
    expect(formatMoney("-25.8800", "USD")).toBe("-$25.88");
  });
});

/** `DEF-CWP-9162` — the signed-in frame carries the build too, one source. */
describe("PortalShell · the build version on every signed-in page (DEF-CWP-9162)", () => {
  it("draws the same version the staff frame reads, in a footer", () => {
    const version = (pkg as { version: string }).version;
    const html = shell([]);
    expect(html).toContain(`data-version="${version}"`);
    expect(html).toContain(`Version ${version}`);
    expect(html.indexOf("<footer")).toBeGreaterThan(html.indexOf("<main"));
  });
});
