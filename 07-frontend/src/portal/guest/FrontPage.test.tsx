// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) · US-CWP-069 TC-5 · US-CWP-070 TC-3/TC-4
//           Screens: CWP-001 · wireframes/CWP-001.png
// Rules:    BR-CWP-093 (nothing empty ever appears) · CR-068 R8 · R9 · R3 ·
//           B14 rule 31 (no id is a visible value) · rule 21 (every class here
//           is owned by routeBUtilities.test.ts through the `portal/` entry)
// Cases:    US-CWP-001 TC-1 · TC-2 · TC-3 · TC-4 — at the first paint
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { queryKeys } from "@/api/queryClient";

import type { ErrandCardKey, ErrandCardOffer, ErrandCardReason, PortalFront } from "../api/guestClient";
import { PORTAL_SCREENS, resolvePortalScreen } from "../routing/screenIds";

import { FrontPage } from "./FrontPage";
import { CARD_ROUTE } from "./FrontPageView";

/**
 * The six cards as the SERVER sends them since 2026-09-05 — all of them, each
 * with whether a visitor may use it. Pass overrides by key; the defaults are
 * Pine Hill's live state (four usable, `check_my_area` off by `CR-068` R9,
 * `help_answers` off until something is published).
 *
 * ⚠ **THE DEFAULT MUST STAY SIX LONG.** The fixture that cannot tell a
 * complete payload from a filtered one is the fixture that would let the old
 * behaviour creep back in unnoticed — `DEF-CWP-3925`'s lesson one shape over.
 */
function cards(over: Partial<Record<ErrandCardKey, ErrandCardReason | null>> = {}): ErrandCardOffer[] {
  const base: Record<ErrandCardKey, ErrandCardReason | null> = {
    pay_bill: null,
    report_problem: null,
    check_my_area: "status_page_not_offered",
    start_service: null,
    what_things_cost: null,
    help_answers: "nothing_published_yet",
  };
  const merged = { ...base, ...over };
  return (Object.keys(base) as ErrandCardKey[]).map((key) => {
    const reason = merged[key];
    return reason === null
      ? { key, available: true as const, reason_code: null }
      : { key, available: false as const, reason_code: reason };
  });
}

function front(over: Partial<PortalFront> = {}): PortalFront {
  return {
    tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: "#EC3013", brand_accent_hex: "#E15B47" },
    is_live: true,
    // `DEF-CWP-3994` — the tenant's Regional settings ride on this payload now,
    // and the type makes them REQUIRED so a fixture cannot quietly omit them.
    regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
    // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`).
    locales: ["en", "es"],
    cards: cards(),
    links: { help: false, visit: false },
    switches: {
      quick_pay_enabled: true,
      self_read_enabled: false,
      plans_enabled: true,
      requests_enabled: true,
      outage_reporting_enabled: true,
    },
    services: [
      { code: "water", name: "Water", color: "#1e6b8f" },
      { code: "sewer", name: "Sewer", color: "#5a5555" },
    ],
    strapline: "Your account, your bills and your meter readings — any time.",
    office_hours_text: "8am to 5pm, Monday to Friday",
    emergency_phone: "(512) 555-0100",
    ...over,
  };
}

function render(data: PortalFront): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.portalFront, data);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      {/* ⚠ MOUNTED UNDER THE REAL PATH PATTERN, not bare inside the router.
          `usePortalPath` builds every link from `useParams().tenant`, so a
          bare mount binds no param and every href comes out `//portal/…` —
          which reads as a link and is a protocol-relative address to another
          host. The fixture that cannot tell those apart is the fixture that
          let `DEF-CWP-3925` through. */}
      <MemoryRouter initialEntries={["/pine-hill/portal"]}>
        <Routes>
          <Route path="/:tenant/portal" element={<FrontPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;

describe("CWP-001 · the public front page (US-CWP-001)", () => {
  it("TC-1: draws the cards the server offered, in the utility's own colours, with no password field", () => {
    const html = render(front());
    // ⚠ **ALL SIX ARE DRAWN NOW, INCLUDING THE TWO THAT CANNOT BE USED** — PO
    // ruling 2026-09-05, *"Yoi ahev these cards - may be disable them, but for
    // completess have them on screen"*. This asserted four and was silent
    // about the other two, which is how a page could lose a card and nobody
    // be told (`DEF-CWP-3953`).
    for (const key of ["pay_bill", "report_problem", "check_my_area", "start_service", "what_things_cost", "help_answers"]) {
      expect(html, `${key} is missing from the grid`).toContain(`data-errand="${key}"`);
    }
    expect((html.match(/data-errand=/g) ?? []).length).toBe(6);
    expect(html).toContain("Pay a bill");
    expect(html).toContain("What do you need?");
    expect(html).toContain("--color-accent:#EC3013");
    expect(html).toContain("Your account, your bills and your meter readings — any time.");
    expect(html).toContain('data-service-chip="water"');
    expect(html).not.toContain('type="password"');
    // The sign-in bar names a screen that shipped in wave E, so it is a LINK.
    expect(html).toContain("Sign in");
    expect(html).toContain('href="/pine-hill/portal/sign-in"');
  });

  /**
   * ⚠ **THE HEX IN THE FIXTURE ABOVE IS `#EC3013`, AND SO IS THE THEME'S OWN
   * `--color-accent` — THE SAME COLOUR TO THE BYTE.** That coincidence is why
   * `DEF-CWP-3736` survived every check this repo has: a button painted with
   * the product's constant and a button painted with the tenant's hex are
   * identical pixels on every fixture, and the old assertion only asked
   * whether SOME property was present. This case uses a colour that is not
   * ours, and asks the two questions that actually decide it: is the property
   * the one the kit reads, and is the one nobody reads gone?
   */
  it("TC-1b: the property set is the one the KIT reads, and the tenant's hex is not the theme's", () => {
    const html = render(front({
      tenant: {
        slug: "pine-hill",
        name: "Pine Hill Water & Power",
        brand_primary_hex: "#0F7B6C",
        brand_accent_hex: "#B45309",
      },
    }));
    // `buttonKit` writes `bg-accent` / `hover:bg-accent-600` / `active:bg-accent-700`,
    // which Tailwind emits as these three properties and no others.
    expect(html).toContain("--color-accent:#0F7B6C");
    expect(html).toContain("--color-accent-600:color-mix(in srgb, #0F7B6C 88%, black)");
    expect(html).toContain("--color-accent-700:color-mix(in srgb, #0F7B6C 72%, black)");
    // The two properties nothing consumed are GONE, not renamed beside them.
    expect(html).not.toContain("--brand");
    expect(html).not.toContain("--accent:");
    // `brand_accent_hex` is served and deliberately unapplied — DEF-CWP-3737.
    expect(html).not.toContain("#B45309");
  });

  /**
   * PO ruling 2026-09-04, verbatim: *"default will be our style guide and then
   * we will allow utility users to change it"*. So the answer for a utility
   * with no colour is **`#ec3013`, r10's own accent** — never grey, and never
   * an invented fallback. The mechanism is that nothing is written at all and
   * the `:root` declaration stands, so what this case actually has to prove is
   * that the frame writes NO `--color-accent` of any kind: an empty string
   * would override the style guide with garbage and put the unbranded tenants
   * straight back into greyscale, which is half the defect being fixed.
   * The colour that results is measured in a real engine, not here —
   * `10-scripts/cwp_portal_colour_walkthrough.mjs`.
   */
  it("TC-1c: a utility with no colour writes NOTHING, so the style guide's own accent stands", () => {
    for (const hex of [null, ""] as const) {
      const html = render(front({
        tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: hex, brand_accent_hex: hex },
      }));
      // Not "no tenant hex" — no property at all, which is what lets :root win.
      expect(html).not.toContain("--color-accent:");
      // The failure this is really guarding: an empty override.
      expect(html).not.toContain('style=""');
    }
  });

  /**
   * ⚠ **TC-2 IS THE CASE THIS RULING REVERSED, AND IT IS AMENDED IN THE COMMIT
   * THAT CARRIES THE CODE.** It read *absent, not greyed* from the story's
   * first draft until 2026-09-05, when the PO compared the blueprint's six
   * cards with four on a live tenant and ruled the opposite: *"Yoi ahev these
   * cards - may be disable them, but for completess have them on screen"*.
   *
   * The half that did NOT move is the one that matters for money: the card
   * being visible is not the door being open. `BR-CWP-002` refuses
   * `POST /public/bills/lookup` at the edge whether the card is hidden,
   * greyed or missing, and `US-CWP-001` TC-2 asserts that on the server.
   */
  it("TC-2: a card the utility switched off is DRAWN, DISABLED, and says so — and links nowhere", () => {
    const html = render(front({ cards: cards({ pay_bill: "switched_off_by_the_utility" }) }));
    expect(html).toContain('data-errand="pay_bill"');
    expect(html).toContain('data-unavailable="switched_off_by_the_utility"');
    expect(html).toContain("Not offered online at the moment.");
    // The card is on screen; the DOOR is not. No link to /pay anywhere.
    expect(html).not.toContain('href="/pine-hill/portal/pay"');
    expect(html).not.toContain('data-link="pay_bill"');
    expect(html).toContain('data-errand="report_problem"');
  });

  /**
   * The three reasons must not READ ALIKE, which is the whole of
   * `DEF-CWP-3953`: one is undone by the utility in its own settings, one by
   * publishing a single answer today, and one by nobody here at all. A grid
   * where all three said the same words would put the product back exactly
   * where the PO found it, with two extra grey boxes.
   */
  it("the three reasons are three different sentences, on one page, at once", () => {
    const html = render(front({ cards: cards({ pay_bill: "switched_off_by_the_utility" }) }));
    expect(html).toContain("Not offered online at the moment."); // the utility's own switch
    expect(html).toContain("No status page here yet."); // R9, and nobody here can move it
    expect(html).toContain("Nothing published here yet."); // one answer away
    const sentences = new Set([
      "Not offered online at the moment.",
      "No status page here yet.",
      "Nothing published here yet.",
    ]);
    expect(sentences.size).toBe(3);
    // Each is a FACT in six words or fewer (B14 rule 33), and not one of them
    // says WHY the product works this way — rationale is zero words on screen.
    for (const one of sentences) {
      expect(one.replace(/[.]$/, "").split(/\s+/).length, one).toBeLessThanOrEqual(6);
    }
  });

  /**
   * ⚠ **A REASON CODE MUST NEVER PRINT ITSELF.** `t()` answers a missing key
   * WITH THE KEY, and these four keys are not in the eleven catalogues yet —
   * they were handed to the lane that owns those files. Without the English
   * fallbacks this page would show `portal.card.unavailable.switchedOff` to a
   * customer: B14 rule 31, and the exact defect G27 exists for after a
   * Settings panel rendered its own source code. G27 cannot see these calls
   * (its regex needs a literal inside `t(`), so this case is the guard.
   */
  it("B14 rule 31: no reason key and no reason CODE ever reaches the glass", () => {
    const html = render(front({ cards: cards({ pay_bill: "switched_off_by_the_utility" }) }));
    expect(html).not.toContain("portal.card.unavailable");
    expect(html).not.toContain("portal.held.");
    // The codes ride on data- attributes for the tests; they are never TEXT.
    const visible = html.replace(/<[^>]*>/g, " ");
    for (const code of ["switched_off_by_the_utility", "status_page_not_offered", "nothing_published_yet"]) {
      expect(visible, `${code} leaked into visible text`).not.toContain(code);
    }
  });

  /**
   * A reason this build has never heard of must fall back to a neutral
   * sentence rather than to its own key — the day the server grows a fourth
   * condition, an older browser tab must not print it.
   */
  it("an unknown reason falls back to a sentence, never to the code", () => {
    const rogue = [
      { key: "pay_bill", available: false, reason_code: "some_future_condition" },
    ] as unknown as ErrandCardOffer[];
    const html = render(front({ cards: rogue }));
    expect(html).toContain("Not available just now.");
    expect(html.replace(/<[^>]*>/g, " ")).not.toContain("some_future_condition");
  });

  it("TC-3: the portal is off → a holding page, no cards, no nav, the utility's name", () => {
    const html = render(front({ is_live: false, cards: [], services: [], strapline: null, switches: undefined }));
    expect(html).toContain('data-holding="true"');
    expect(html).toContain("Pine Hill Water &amp; Power"); // React escapes the ampersand in text
    expect(html).not.toContain("data-errand=");
    expect(html).not.toContain("<nav");
    expect(html).toContain('data-live="false"');
  });

  /**
   * ⚠ **THE CARD AND THE NAV WORD PART COMPANY HERE, AND THAT IS THE DESIGN.**
   * One condition — nothing published — and two different answers, because a
   * grid of six is a CATALOGUE of what this product does and a nav word is a
   * DESTINATION. A greyed word in a top bar that goes nowhere is hard-won law
   * 2's dead control, which is why `Help` and `Visit us` still come and go.
   */
  it("TC-4: nothing published → the Help CARD is drawn and disabled, the Help WORD is absent", () => {
    const html = render(front());
    expect(html).toContain('data-errand="help_answers"');
    expect(html).toContain('data-unavailable="nothing_published_yet"');
    expect(html).toContain("Nothing published here yet.");
    // The card never links, even though its route exists — availability, not
    // the route table, is what decides whether a door opens.
    expect(html).not.toContain('href="/pine-hill/portal/help"');
    expect(html).not.toContain('data-link="help"');
    expect(html).not.toContain('data-link="visit"');
    expect(html).not.toContain("No answers");
  });

  /**
   * ⚠ **THIS CASE USED TO SAY *Check my area is never drawn* AND NOW SAYS THE
   * OPPOSITE.** The server sends it (2026-09-05), disabled, so the front page
   * can finally explain an absence it could never explain before. What has NOT
   * changed is the ruling: `CR-068` R9 parks the public status page until
   * somebody owns keeping it current out of hours.
   *
   * **THIS IS THE CASE THAT FIRES WHEN THAT HOLD EXPIRES.** `CWP-005` is the
   * status page's allocated id and `08-screen-layouts.md` marks it *DEFERRED,
   * do not build*. The day a lane registers it in `PORTAL_SCREENS`, this goes
   * RED and names the card — instead of leaving a grey box with *"No status
   * page here yet"* sitting over a screen that shipped, which is exactly what
   * `DEF-CWP-3925` cost on five other controls of this very page.
   */
  it("R9 · HOLD EXPIRY: Check my area is drawn, disabled, and has no screen to open", () => {
    const html = render(front());
    expect(html).toContain('data-errand="check_my_area"');
    expect(html).toContain('data-unavailable="status_page_not_offered"');
    expect(html).toContain("No status page here yet.");
    expect(CARD_ROUTE.check_my_area).toBeUndefined();

    const built = PORTAL_SCREENS.find((screen) => screen.id === "CWP-005");
    expect(
      built,
      "CWP-005 — the Check my area status page — is now a routed portal screen, so " +
        "CR-068 R9's hold has expired: give the check_my_area card a CARD_ROUTE entry, " +
        "make the server offer it, and delete the status_page_not_offered reason.",
    ).toBeUndefined();
  });

  /**
   * The mirror of the hold, and the half `DEF-CWP-3925` proves nobody writes:
   * when the server DOES say a card is usable, the screen must open it. A card
   * left disabled over a live destination is the dead control with the arrow
   * reversed, and it is what happened to five `Start →` controls on this page.
   */
  it("HOLD EXPIRY: a card the server calls available opens its screen, not a held button", () => {
    const html = render(front({ cards: cards({ help_answers: null }) }));
    expect(html).toContain('href="/pine-hill/portal/help"');
    expect(html).not.toContain('data-unavailable="nothing_published_yet"');
    // Every routed card that the server offers must be a LINK, not a hold.
    for (const [key, to] of Object.entries(CARD_ROUTE)) {
      expect(html, `${key} is offered and routed but draws no link`).toContain(
        `href="/pine-hill/portal${to}"`,
      );
    }
  });

  /**
   * ⚠ **THE CASE `DEF-CWP-3925` DID NOT HAVE, AND THE REASON IT RAN FOR A
   * WEEK.** `CR-068` R3 holds a `Start →` **until its screen lands**, and four
   * of them landed in waves C, D, E and P without this page hearing about it —
   * each wave tested its own screen at its own address, and no test anywhere
   * asked whether the front page had started pointing at them. So a visitor
   * was told *Opens with the next release* over four live screens.
   *
   * This case reads the ROUTE TABLE rather than the rendering, so it holds for
   * every card at once: a card that claims a destination must claim one this
   * product actually serves, and the id it resolves to is named here so a
   * renamed route goes red rather than quiet.
   */
  it("R3: every card that navigates names a route this product serves — and the right screen", () => {
    const expected: Partial<Record<ErrandCardKey, string>> = {
      pay_bill: "CWP-002",
      report_problem: "CWP-006",
      start_service: "CWP-008",
      help_answers: "CWP-011",
    };
    for (const [key, to] of Object.entries(CARD_ROUTE)) {
      const screen = resolvePortalScreen(to as string);
      expect(screen, `${key} → ${to} is not a portal route`).not.toBeNull();
      expect(screen?.id, `${key} opens the wrong screen`).toBe(expected[key as ErrandCardKey]);
    }
    // Both directions: a card named above and missing from the table is the
    // defect itself, so the two sets must be the same size.
    expect(Object.keys(CARD_ROUTE).sort()).toEqual(Object.keys(expected).sort());
  });

  /**
   * The other half of R3, and the half that is still TRUE: *What things cost*
   * has no screen anywhere in `CR-068` §9, no story, and an endpoint that was
   * deliberately not built (`DEF-CWP-3704`). So it is held, and this case is
   * what makes the difference between the two kinds of card visible — a held
   * control beside a live one, on one page, asserted together.
   */
  it("R3: a card whose screen this product does not draw is still held, with its reason", () => {
    const html = render(front());
    expect(html).toContain('href="/pine-hill/portal/pay"');
    expect(html).toContain('data-held="true"');
    expect(html).toContain("Opens with the next release.");
    expect(CARD_ROUTE.what_things_cost).toBeUndefined();
    // ⚠ **AND R3's HOLD IS NOT THE SAME STATE AS THE SERVER'S.** *What things
    // cost* is OFFERED — prices are public — and merely has no screen yet, so
    // the card is live-looking and its button says *Opens with the next
    // release*. The two beside it are not offered at all and say something
    // about this tenant or about a ruling. Collapsing them would put a
    // release note under a card the utility switched off this morning.
    expect(html).not.toContain('data-errand="what_things_cost" data-unavailable');
    const cost = html.slice(html.indexOf('data-errand="what_things_cost"'));
    expect(cost.slice(0, 400)).not.toContain("data-unavailable");
  });

  /**
   * ⚠ **`s4` NAMES THIS PAGE AS THE PLACE ENROLMENT IS FOUND:** *"The landing
   * page — one of the three doors it carries beneath the sign-in form."* It
   * carried one door, `Sign in`, so a paper-bill customer with no login had to
   * guess that the sign-in screen carries the way on, and somebody who had
   * forgotten a password had to guess the same thing.
   *
   * The assertion is on the ADDRESS and on the screen it opens, which is
   * `DEF-CWP-3925`'s own lesson: a word that looks like a door is not one.
   */
  it("the front page carries the two doors beneath the sign-in bar", () => {
    const html = render(front());
    for (const [href, id] of Object.entries({
      "/pine-hill/portal/enrol": "CWP-016",
      "/pine-hill/portal/forgot-password": "CWP-019",
    })) {
      expect(html, `${href} is not a door on the front page`).toContain(`href="${href}"`);
      expect(resolvePortalScreen(href.replace("/pine-hill/portal", ""))?.id).toBe(id);
    }
    // Neither is a bare label, and neither has lost its tenant.
    expect(html).toContain('data-door="enrol"');
    expect(html).toContain('data-door="forgot_password"');
    expect(html).not.toContain('href="//portal');
  });

  /**
   * ⚠ **ONE FILLED CONTROL, AND IT IS THE ONE THE PAGE IS FOR.** `s1`: *"One
   * filled button, and it is not 'Sign in' — most visits are a payment, and
   * most of those people have no account and do not want one."* Every control
   * on this page was `secondary` before, so the busiest page in the portal
   * offered a stranger no primary action at all.
   */
  it("exactly one primary control, and it is Pay a bill", () => {
    const html = render(front());
    const primaries = [...html.matchAll(/data-variant="primary"/g)];
    expect(primaries).toHaveLength(1);
    // It is inside the pay_bill card, and not inside the sign-in bar.
    const card = html.slice(html.indexOf('data-errand="pay_bill"'));
    expect(card.slice(0, card.indexOf("</article>"))).toContain('data-variant="primary"');
    const signIn = html.slice(html.indexOf('href="/pine-hill/portal/sign-in"'));
    expect(signIn.slice(0, 200)).not.toContain('data-variant="primary"');
  });

  /**
   * The mirror: a utility with quick pay switched off sends `pay_bill`
   * UNAVAILABLE, so the page must have NO filled control rather than promote
   * whatever is drawn first.
   */
  it("quick pay switched off → no primary control anywhere on the page", () => {
    const html = render(front({ cards: cards({ pay_bill: "switched_off_by_the_utility" }) }));
    expect(html).not.toContain('data-variant="primary"');
  });

  it("B14 rule 31 · BR-CWP-021: no uuid, no rule id and no person in what a visitor sees", () => {
    const html = render(front());
    expect(html).not.toMatch(UUID);
    expect(html).not.toMatch(/\b(BR|OQ|DEF)-[A-Z]{0,3}-?\d{3,5}\b/);
    expect(html).not.toContain("Sarah");
  });
});
