// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-072 (EP-CWP-12) — the help list and one answer ·
//           US-CWP-074 — where you can walk in, and one centre.
//           Screens: CWP-011 · CWP-060 · CWP-013 · CWP-014
// Rules:    BR-CWP-093 (nothing empty ever appears; no count of what is
//           hidden) · BR-CWP-094 (English fallback, and a line saying so) ·
//           BR-CWP-096 (four of five rows say NO; the closure comes from the
//           calendar) · B14 rule 31 (no id is a visible value) · rule 35 (⚠ the
//           day name and the clock are the READER'S, produced by `Intl` — the
//           catalogue holds only the frame)
// Cases:    US-CWP-072 TC-1 · TC-7 · TC-8 · TC-10 · US-CWP-074 TC-2 · TC-4
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";

import type { ErrandCardKey, ErrandCardOffer, PortalCentre, PortalFront, PortalHelpAnswer, PortalHelpList } from "../api/guestClient";
import { centreStatusLine, clockText, weekdayText } from "../components/content";

import { CentrePage, CentresPage } from "./CentresPage";
import { AnswerPage, HelpPage } from "./HelpPage";

/**
 * The server sends all six errand cards with whether each may be used (PO
 * ruling 2026-09-05). These suites are about doors OTHER than the card grid,
 * so they name the usable ones and let this build the payload — one place to
 * edit if the shape moves again.
 */
function offered(...keys: ErrandCardKey[]): ErrandCardOffer[] {
  return CARD_KEYS.map((key) =>
    keys.includes(key)
      ? { key, available: true as const, reason_code: null }
      : { key, available: false as const, reason_code: "switched_off_by_the_utility" as const },
  );
}

const CARD_KEYS: ErrandCardKey[] = [
  "pay_bill",
  "report_problem",
  "check_my_area",
  "start_service",
  "what_things_cost",
  "help_answers",
];


const FRONT: PortalFront = {
  tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: "#EC3013", brand_accent_hex: "#E15B47" },
  is_live: true,
  // `DEF-CWP-3994` — the tenant's Regional settings ride on the front
  // payload, and the type makes them REQUIRED so a fixture cannot
  // quietly omit them and hide the wire being absent.
  regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
  // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`).
  locales: ["en", "es"],
  cards: offered("pay_bill", "report_problem", "start_service", "what_things_cost", "help_answers"),
  links: { help: true, visit: true },
  services: [],
  strapline: null,
  office_hours_text: "8am to 5pm, Monday to Friday",
  emergency_phone: "(512) 555-0100",
};

const SIX: PortalHelpList = {
  answers: [
    { slug: "why-is-my-bill-higher-than-last-month", question: "Why is my bill higher than last month?", topic: "billing" },
    { slug: "what-does-estimated-mean-on-my-bill", question: 'What does "estimated" mean on my bill?', topic: "readings" },
    { slug: "how-do-i-check-for-a-leak", question: "How do I check for a leak?", topic: "water" },
    { slug: "can-i-pay-in-instalments", question: "Can I pay in instalments?", topic: "paying" },
    { slug: "what-happens-if-i-pay-late", question: "What happens if I pay late?", topic: "paying" },
    { slug: "how-do-i-close-my-account", question: "How do I close my account?", topic: "moving" },
  ],
  topics: ["billing", "readings", "water", "paying", "moving"],
  visit_link: true,
};

const NORTH: PortalCentre = {
  slug: "north-counter",
  name: "North counter",
  address: "1190 Palm Ct, Austin TX 78758",
  phone: "(512) 555-0148",
  directions_note: "Inside the community centre, first door on the right.",
  allowed_actions: ["pay_a_bill"],
  cannot_do: ["open_or_close_an_account", "report_a_problem", "hand_in_a_document", "ask_a_question"],
  all_actions: ["pay_a_bill", "open_or_close_an_account", "report_a_problem", "hand_in_a_document", "ask_a_question"],
  payment_methods_accepted: ["cash", "cheque"],
  hours: [
    { day_of_week: 0, is_closed: true, opens_at: null, closes_at: null },
    { day_of_week: 1, is_closed: false, opens_at: "09:00", closes_at: "13:00" },
    { day_of_week: 2, is_closed: true, opens_at: null, closes_at: null },
    { day_of_week: 3, is_closed: false, opens_at: "09:00", closes_at: "13:00" },
    { day_of_week: 4, is_closed: true, opens_at: null, closes_at: null },
    { day_of_week: 5, is_closed: true, opens_at: null, closes_at: null },
    { day_of_week: 6, is_closed: true, opens_at: null, closes_at: null },
  ],
  // A Wednesday: closed today, next opening Thursday at 9:00.
  today: {
    is_open_now: false,
    closes_at: null,
    opens_later_today: false,
    next_open_date: "2026-11-19",
    next_open_weekday: 3,
    next_open_is_today: false,
    next_open_at: "09:00",
    closed_for_holiday: null,
    next_holiday: { date: "2026-11-26", label: "Thanksgiving Day" },
  },
};

function render(node: React.ReactElement, seed: [readonly unknown[], unknown][], path = "/pine-hill/portal/help"): string {
  return renderWithFront(node, seed, FRONT, path);
}

/** The same, for the cases that turn a published FACT off — the utility with
 *  no phone number and no office hours, which is where `DEF-CWP-4854` lived. */
function renderWithFront(
  node: React.ReactElement,
  seed: [readonly unknown[], unknown][],
  front: PortalFront,
  path = "/pine-hill/portal/help",
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.portalFront, front);
  for (const [key, value] of seed) queryClient.setQueryData(key, value);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/:tenant/portal/help" element={node} />
          <Route path="/:tenant/portal/help/:slug" element={node} />
          <Route path="/:tenant/portal/visit" element={node} />
          <Route path="/:tenant/portal/visit/:slug" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;

// ⚠ THE ANSWER IS ASKED FOR IN THE **BROWSER'S** LANGUAGE, not the app's — the
// app pins `lng: "en"` and a French visitor would otherwise be sent English on
// purpose, which would make the fallback unreachable (see `readerLocale`). So
// the cache key this test seeds has to be the one the component will build,
// and in jsdom that is `navigator.language` (`en-US`), not `"en"`.
const READER = typeof navigator !== "undefined" ? navigator.language : "en";

describe("CWP-011 · help and answers (US-CWP-072)", () => {
  it("TC-1: six answers, each its own door, and the topic chips are derived", () => {
    const html = render(<HelpPage />, [[["portal", "help", null], SIX]]);
    expect(html).toContain('data-screen="CWP-011"');
    expect((html.match(/data-answer="/g) ?? []).length).toBe(6);
    for (const row of SIX.answers) expect(html).toContain(`href="help/${row.slug}"`);
    // ⚠ Chips come from what is PUBLISHED — a chip that filtered to nothing
    // would be a container with nothing in it (BR-CWP-093).
    expect((html.match(/data-topic-chip="/g) ?? []).length).toBe(6); // All + five
  });

  it("TC-3 negative: no count of what is hidden appears anywhere", () => {
    // ⚠ READ THE TEXT, NOT THE MARKUP. `overflow-hidden` is a class, not a
    // sentence, and a raw-HTML assertion here fails on the styling rather than
    // on the copy — which is a check that cannot distinguish pass from fail.
    const text = render(<HelpPage />, [[["portal", "help", null], SIX]])
      .replace(/<[^>]*>/g, " ")
      .toLowerCase();
    for (const forbidden of ["hidden", "draft", "not shown", "of 8", "8 answers"]) {
      expect(text).not.toContain(forbidden);
    }
  });

  it("TC-10: the walk-in route is absent from the rail when no centre is shown", () => {
    const withCentres = render(<HelpPage />, [[["portal", "help", null], SIX]]);
    // ⚠ **AN ABSOLUTE PORTAL ADDRESS, AND THIS ASSERTION USED TO READ
    // `href="visit"`** (`CR-085` lane 2). A relative `visit` resolves correctly
    // from `/{tenant}/portal/help` and WRONGLY from every other address this
    // rail now renders at — `/{tenant}/portal/help/{slug}` would send it to
    // `/{tenant}/portal/help/visit`. That is `DEF-CWP-4655` exactly, and the
    // test that could have caught it was asserting the link was PRESENT
    // without ever asking where it went.
    // ⚠ **COUNTED, NOT MATCHED — AND THE FIRST DRAFT OF THIS LINE WAS A CHECK
    // THAT COULD NOT PASS.** `GuestFrame`'s nav draws its own *Visit us* word
    // with the same `data-link="visit"` and the same absolute address whenever
    // the tenant publishes a centre, so `not.toContain('data-link="visit"')`
    // is red on a fixture whose `links.visit` is true however the RAIL
    // behaves. Two marks with `visit_link`, one without: the difference is the
    // rail, which is what this case is about.
    expect((withCentres.match(/data-link="visit"/g) ?? []).length).toBe(2);
    const without = render(<HelpPage />, [[["portal", "help", null], { ...SIX, visit_link: false }]]);
    expect((without.match(/data-link="visit"/g) ?? []).length).toBe(1);
  });

  // ⚠ **R-22, AND IT IS THE DEFECT THIS CASE IS NAMED AFTER (`DEF-CWP-4854`).**
  // A tenant with nothing published served an empty search box, an `All` chip
  // with nothing to filter, and **"Nothing here matches what you typed."** to
  // somebody who had typed nothing. Three states, three SENTENCES (PO
  // 2026-09-11: *"differntiate it using text message"*) — so the two empties
  // must not be the same words, and the furniture that can only ever answer
  // *nothing matches* must not be on the screen at all.
  it("says NOTHING IS PUBLISHED, not NOTHING MATCHES, when the utility has published none (DEF-CWP-4854)", () => {
    const html = render(<HelpPage />, [
      [["portal", "help", null], { answers: [], topics: [], visit_link: false }],
    ]);
    expect(html).toContain('data-screen="CWP-011"');
    expect(html).toContain('data-portal-state="empty"');
    expect(html).toContain("No answers are published here yet.");
    expect(html).not.toContain("Nothing here matches what you typed.");
    // Never an empty search box, and never a chooser with one option.
    expect(html).not.toContain('id="cwp011-search"');
    expect(html).not.toContain("data-topic-chip");
  });

  // ⚠ **THE OTHER HALF OF R-22 ON THIS SCREEN — *nothing matches* — IS NOT
  // TESTABLE HERE AND IS IN `GuestEmptyStates.dom.test.tsx` INSTEAD.** Which
  // sentence renders turns on whether the VISITOR narrowed the list, and the
  // chip and the search box are this component's own state: a static render
  // always asks for `["portal","help",null]` with an empty needle, so the
  // narrowed branch cannot be reached by seeding a cache. A first draft of
  // this case seeded `["portal","help","billing"]` and went red on the failed
  // branch, because the screen had never asked for that key — a check that
  // could not pass, dressed as a check that failed.

  it("STILL STUCK? names a way to reach somebody, and never promises a call it cannot place (DEF-CWP-4854)", () => {
    const withPhone = render(<HelpPage />, [[["portal", "help", null], SIX]]);
    expect(withPhone).toContain('data-stuck-sentence="call"');
    expect(withPhone).toContain('data-stuck-phone=""');
    expect(withPhone).toContain("(512) 555-0100");
    // ⚠ **AND THE HOURS WITH IT** — the drawing's own reason is that a number
    // read without its hours produces a call to a closed office and a second
    // call tomorrow.
    expect(withPhone).toContain('data-stuck-hours=""');
    expect(withPhone).toContain("8am to 5pm, Monday to Friday");

    // A utility that has published neither. The rail used to say *"Call us or
    // come in and someone will go through it with you."* and name nothing at
    // all to call or come in to.
    const bare = renderWithFront(
      <HelpPage />,
      [[["portal", "help", null], SIX]],
      { ...FRONT, emergency_phone: null, office_hours_text: null },
    );
    expect(bare).toContain('data-stuck-sentence="bill"');
    expect(bare).toContain("Call the number printed on your bill.");
    expect(bare).not.toContain("Call us or come in");
  });

  it("no uuid is a visible value on the list (B14 rule 31)", () => {
    const html = render(<HelpPage />, [[["portal", "help", null], SIX]]);
    expect(html).not.toMatch(UUID);
  });

  // ⚠ **THE SEARCH BOX THE DRAWING PUTS AT THE TOP OF THIS SCREEN ON BOTH
  // WIDTHS** (`CR-085`, 2026-09-08). It was simply absent — the screen shipped
  // with topic chips only, and the drawing's own argument for the box is that a
  // reader arrives with WORDS rather than with a category: *"'Billing
  // enquiries' is a filing category; 'Why is my bill higher this month?' is
  // what someone types."*
  it("offers a search box over the answers, labelled for a screen reader (CR-085)", () => {
    const html = render(<HelpPage />, [[["portal", "help", null], SIX]]);
    expect(html).toContain('id="cwp011-search"');
    expect(html).toContain('type="search"');
    // ⚠ A placeholder is NOT a label — it disappears the moment somebody
    // types, which is exactly when a screen-reader user needs to know what the
    // field is. Same reasoning and same markup as the staff lists' box.
    expect(html).toContain('for="cwp011-search"');
    // The catalogue's words, never the key (B14 rule 35 · `DEF-CWP-3952`).
    expect(html).toContain("Search answers…");
    expect(html).not.toContain("portal.help.search");
  });
});

describe("CWP-060 · one answer (US-CWP-072)", () => {
  const answer = (over: Partial<PortalHelpAnswer> = {}): PortalHelpAnswer => ({
    slug: "why-is-my-bill-higher-than-last-month",
    question: "Why is my bill higher than last month?",
    topic: "billing",
    body: "Most of the time it is one of three things…",
    asked_for: "en",
    shown_in: "en",
    is_fallback: false,
    updated_on: "2026-09-02",
    also_written_in: ["en", "es-MX", "hi"],
    related: [{ slug: "how-do-i-check-for-a-leak", question: "How do I check for a leak?", topic: "water" }],
    ...over,
  });

  it("TC-8: a fallback answer carries the line that says which language it is in", () => {
    const html = render(
      <AnswerPage />,
      [[["portal", "help", "answer", "why-is-my-bill-higher-than-last-month", READER], answer({ asked_for: "fr-FR", is_fallback: true })]],
      "/pine-hill/portal/help/why-is-my-bill-higher-than-last-month",
    );
    expect(html).toContain('data-fallback-note=""');
    // ⚠ THE LANGUAGE IS NAMED IN ITS OWN WORDS — `Intl.DisplayNames`, not a
    // catalogue line that could only ever be identical in all eleven.
    expect(html).toContain("English");
  });

  it("an answer in the reader's own language shows no such line", () => {
    const html = render(
      <AnswerPage />,
      [[["portal", "help", "answer", "why-is-my-bill-higher-than-last-month", READER], answer()]],
      "/pine-hill/portal/help/why-is-my-bill-higher-than-last-month",
    );
    expect(html).not.toContain('data-fallback-note=""');
    expect(html).toContain('data-vote="not_helpful"');
    expect(html).toContain('data-vote="helpful"');
  });

  // ⚠ **WHEN IT WAS LAST WRITTEN — SERVED SINCE WAVE D, DRAWN BY NOTHING**
  // (`CR-085`, 2026-09-08). `updated_on` is on the payload, on the type, and in
  // THIS FIXTURE four lines up (`"2026-09-02"`), and the article never printed
  // it. The drawing puts it directly under the title, and the reason is
  // credibility: an answer with no date is one the reader has to guess the age
  // of. The same class as `directions_note` below — a fact with no control in
  // front of it, which no gate in this repo can see.
  it("says when the answer was last written (CR-085)", () => {
    const html = render(
      <AnswerPage />,
      [[["portal", "help", "answer", "why-is-my-bill-higher-than-last-month", READER], answer()]],
      "/pine-hill/portal/help/why-is-my-bill-higher-than-last-month",
    );
    expect(html).toContain('data-updated-on="2026-09-02"');
    // The catalogue's frame, never the key (B14 rule 35).
    expect(html).toContain("Updated");
    expect(html).not.toContain("portal.help.updatedOn");
  });

  it("says nothing when the server sent no date (BR-CWP-093)", () => {
    // ⚠ *Updated —* is worse than silence.
    const html = render(
      <AnswerPage />,
      [[["portal", "help", "answer", "why-is-my-bill-higher-than-last-month", READER], answer({ updated_on: null })]],
      "/pine-hill/portal/help/why-is-my-bill-higher-than-last-month",
    );
    expect(html).not.toContain("data-updated-on");
  });

  it("⚠ no screen promises a translation workflow (OQ-1398's boundary)", () => {
    const html = render(
      <AnswerPage />,
      [[["portal", "help", "answer", "why-is-my-bill-higher-than-last-month", READER], answer({ is_fallback: true, asked_for: "fr-FR" })]],
      "/pine-hill/portal/help/why-is-my-bill-higher-than-last-month",
    );
    for (const promise of ["will be translated", "coming soon", "request a translation", "translation is on its way"]) {
      expect(html.toLowerCase()).not.toContain(promise);
    }
  });
});

describe("CWP-013 · CWP-014 · where you can walk in (US-CWP-074)", () => {
  it("TC-2: the status line is built from the server's FACTS, in the reader's language", () => {
    // ⚠ The wireframe says *Tuesday*; a screen showing Tuesday on a Wednesday
    // has TYPED the day (DEF-CWP-3604). This asserts the weekday the SERVER
    // derived, turned into a name by `Intl`.
    expect(weekdayText(3, "en")).toBe("Thursday");
    expect(weekdayText(3, "fr-FR")).toBe("jeudi");
    expect(clockText("09:00", "en-US")).toBe("9:00am");
    // French drops the leading zero and uses a 24-hour clock; English
    // lowercases the meridiem, which is what r10's own screens print.
    expect(clockText("09:00", "fr-FR")).toBe("9:00");
    expect(clockText("17:00", "en-US")).toBe("5:00pm");
    // ⚠ **AND THE SENTENCE ITSELF, WHICH THIS CASE IS NAMED AFTER AND DID NOT
    // ASSERT UNTIL 2026-09-05 (`DEF-CWP-3940`).** The two lines above check the
    // INGREDIENTS; `centreStatusLine` is what composes them into the thing a
    // person reads, and it was imported here and never called. An unused
    // import is how a missing assertion looks from the outside.
    const t = i18n.getFixedT("en");
    expect(centreStatusLine(NORTH.today, t, "en")).toBe(
      "Closed today · Opens Thursday at 9:00am",
    );
  });

  it("TC-4 negative: four of the five action rows say no", () => {
    const html = render(<CentrePage />, [[["portal", "centres", "north-counter"], NORTH]], "/pine-hill/portal/visit/north-counter");
    expect(html).toContain('data-screen="CWP-014"');
    expect((html.match(/data-can="no"/g) ?? []).length).toBe(4);
    expect((html.match(/data-can="yes"/g) ?? []).length).toBe(1);
  });

  it("the footer holiday is drawn from the calendar's own label and date", () => {
    const html = render(<CentrePage />, [[["portal", "centres", "north-counter"], NORTH]], "/pine-hill/portal/visit/north-counter");
    expect(html).toContain('data-next-holiday="2026-11-26"');
    expect(html).toContain("Thanksgiving Day");
  });

  it("the list draws one card per shown centre and no uuid anywhere", () => {
    const html = render(<CentresPage />, [[["portal", "centres"], [NORTH]]], "/pine-hill/portal/visit");
    expect(html).toContain('data-screen="CWP-013"');
    expect((html.match(/data-centre="/g) ?? []).length).toBe(1);
    expect(html).toContain('data-centre-cannot="north-counter"');
    expect(html).not.toMatch(UUID);
  });

  // ⚠ **A FACT THE SERVER SENDS, THE TYPE DECLARES, AND THIS VERY FIXTURE
  // CARRIED — DRAWN BY NOTHING** (`CR-085`, 2026-09-08). `directions_note` has
  // ridden on `PortalCentre` since wave D and read *"Inside the community
  // centre, first door on the right."* four lines up in this file, and neither
  // centre screen rendered it. That is hard-won law 2 read the other way round:
  // not a control with nothing behind it, but a fact with no control in front
  // of it — and no gate in this repo can see one. The drawing asks for exactly
  // this: *"Parking and step-free access are facts somebody needs before
  // setting out, not afterwards."*
  it("draws the utility's own note about finding the place, on BOTH centre screens (CR-085)", () => {
    const one = render(<CentrePage />, [[["portal", "centres", "north-counter"], NORTH]], "/pine-hill/portal/visit/north-counter");
    expect(one).toContain('data-directions-note="north-counter"');
    expect(one).toContain("Inside the community centre, first door on the right.");

    const list = render(<CentresPage />, [[["portal", "centres"], [NORTH]]], "/pine-hill/portal/visit");
    expect(list).toContain('data-directions-note="north-counter"');
    expect(list).toContain("Inside the community centre, first door on the right.");
  });

  it("says nothing at all when the utility has written no such note (BR-CWP-093)", () => {
    // ⚠ ABSENT, never an empty grey line under the address. An empty line
    // reads as a bug to the one reader who is about to get in a car.
    const bare = { ...NORTH, directions_note: null };
    const one = render(<CentrePage />, [[["portal", "centres", "north-counter"], bare]], "/pine-hill/portal/visit/north-counter");
    expect(one).not.toContain("data-directions-note");
    const list = render(<CentresPage />, [[["portal", "centres"], [bare]]], "/pine-hill/portal/visit");
    expect(list).not.toContain("data-directions-note");
  });
});
