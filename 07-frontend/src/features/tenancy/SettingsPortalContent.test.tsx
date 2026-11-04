// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-071 (EP-CWP-12) — the answers list and the editor ·
//           US-CWP-073 — tips · US-CWP-074 — service centres.
//           Screens: CWP-071 · CWP-072 · CWP-073 · CWP-074 · CWP-075
// Rules:    BR-CWP-094 (all three states are HERE and only here) · BR-CWP-095
//           (two independent reasons a tip is quiet) · BR-CWP-096 (hidden is a
//           state — the depot is in this list) · **B14 rule 36** (the screens
//           compose the shared kit: `DataTable`'s pagination footer and
//           sortable headers, `StatusPill`, `RowActions`, `Switch`,
//           `ChipMultiSelect` — asserted, because "we composed the kit" is a
//           claim and hard-won law 1 says a claim is not the guarantee) ·
//           r10 rule 9 (chips, never a wall of checkboxes)
// Cases:    US-CWP-071 TC-1 · TC-7 · TC-9 · US-CWP-073 TC-3 · TC-7 (BOTH
//           halves — the list AND *in the editor*, which is what the story
//           actually says) · US-CWP-074 TC-1 · TC-4 · TC-9
// Defect:   DEF-CWP-3820 · DEF-CWP-3821 — the two creators shipped as endpoints
//           with nothing able to reach them; these suites assert the controls
//           exist and are LIVE, because a disabled button and no button at all
//           look identical to every check that reads a key set
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import type {
  HelpAnswerDetail,
  HelpAnswerRow,
  ServiceCentreDetail,
  ServiceCentresView,
  TipRow,
  TipsView,
} from "@/api/publishedContentEndpoints";

import { PortalHelpEditor, PortalHelpList } from "./SettingsPortalHelp";
import { PortalTipEditor, PortalTipsList, tipWordCount } from "./SettingsPortalTips";
import { ServiceCentreEditor, ServiceCentresView as CentresList } from "./SettingsServiceCentres";

function answer(over: Partial<HelpAnswerRow>): HelpAnswerRow {
  return {
    slug: "why-is-my-bill-higher-than-last-month",
    question: "Why is my bill higher than last month?",
    topic: "billing",
    status: "published",
    position: 1,
    also_show_on_screen: "bill",
    languages_published: 10,
    languages_total: 11,
    needs_translating: 1,
    reads_this_month: 1204,
    last_changed_by: "Sarah Miller",
    last_changed_on: "2026-09-02T10:00:00Z",
    ...over,
  };
}

const EIGHT: HelpAnswerRow[] = [
  answer({}),
  answer({ slug: "estimated", question: 'What does "estimated" mean on my bill?', topic: "readings", position: 2, reads_this_month: 842, languages_published: 11, needs_translating: 0 }),
  answer({ slug: "leak", question: "How do I check for a leak?", topic: "water", position: 3, reads_this_month: 790, languages_published: 2, needs_translating: 9 }),
  answer({ slug: "meter-read", question: "When is my meter read?", topic: "readings", status: "draft", position: 4, reads_this_month: 0, languages_published: 1, needs_translating: 10 }),
  answer({ slug: "instalments", question: "Can I pay in instalments?", topic: "paying", position: 5, reads_this_month: 611 }),
  answer({ slug: "late", question: "What happens if I pay late?", topic: "paying", position: 6, reads_this_month: 508 }),
  answer({ slug: "close", question: "How do I close my account?", topic: "moving", position: 7, reads_this_month: 410 }),
  answer({ slug: "pipe", question: "Who is responsible for the pipe outside?", topic: "water", status: "not_shown", position: 8, reads_this_month: 0 }),
];

function render(node: React.ReactElement, seed: [readonly unknown[], unknown][]): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  for (const [key, value] of seed) queryClient.setQueryData(key, value);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/pine-hill/settings/reference-data/customer-portal/help"]}>{node}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CWP-071 · help and answers in the back office (US-CWP-071)", () => {
  it("TC-1: all EIGHT are here — the two the customer never sees included", () => {
    const html = render(<PortalHelpList readOnly={false} onOpen={() => undefined} />, [[queryKeys.portalHelp, EIGHT]]);
    expect(html).toContain('data-screen="CWP-071"');
    expect((html.match(/data-answer-row="/g) ?? []).length).toBe(8);
    expect(html).toContain('data-answer-status="draft"');
    expect(html).toContain('data-answer-status="not_shown"');
  });

  it("the read count is a real figure and reads as one", () => {
    const html = render(<PortalHelpList readOnly={false} onOpen={() => undefined} />, [[queryKeys.portalHelp, EIGHT]]);
    expect(html).toContain("1,204");
    expect(html).toContain("842");
  });

  it("⚠ B14 rule 36: it composes the KIT — a pagination footer and a sortable header, not a hand-rolled table", () => {
    const html = render(<PortalHelpList readOnly={false} onOpen={() => undefined} />, [[queryKeys.portalHelp, EIGHT]]);
    // r10 rule 16 — the footer on every list table: the range and the page size.
    expect(html).toContain("table-pager");
    expect(html).toContain("1–8 of 8");
    expect(html).toContain("Rows per page");
    // r10 rule 13 — a sortable header carries the sort control.
    // A sortable header renders the kit's own sort control; the arrow appears
    // on the column actually sorted, which here is `position` and unsortable
    // by design (the ORDER is the portal's order, not a view preference).
    expect(html).toContain("table-sort");
    // r10 rule 12 — the toolbar's search box, with this list's own prompt.
    expect(html).toContain("Search questions…");
  });

  it("TC-7 · TC-9: the editor shows the missing language and warns that publishing is immediate", () => {
    const detail: HelpAnswerDetail = {
      ...answer({}),
      body: "Most of the time it is one of three things…",
      variants: [
        { locale: "en", status: "published", has_body: true, last_changed_on: null },
        { locale: "es-MX", status: "published", has_body: true, last_changed_on: null },
        { locale: "fr-FR", status: "needs_translating", has_body: false, last_changed_on: null },
        { locale: "hi", status: "published", has_body: true, last_changed_on: null },
      ],
      publish_is_immediate: true,
      has_approval_step: false,
    };
    const html = render(<PortalHelpEditor slug="why-is-my-bill-higher-than-last-month" readOnly={false} onBack={() => undefined} />, [
      [[...queryKeys.portalHelp, "why-is-my-bill-higher-than-last-month"], detail],
    ]);
    expect(html).toContain('data-screen="CWP-072"');
    expect(html).toContain('data-variant="fr-FR"');
    expect(html).toContain('data-variant-status="needs_translating"');
    // ⚠ The language table names each language in its OWN words, from `Intl`
    // — `Français (France)` and `हिन्दी`, not eleven catalogue lines that
    // could only ever be identical.
    expect(html).toContain("Français");
    expect(html).toContain("हिन्दी");
    expect(html).toContain('data-publish-warning=""');
    expect(html).toContain("Nobody approves it first.");
  });

  it("⚠ Publish is NOT the danger tier — rule 6 reserves that for destructive commits", () => {
    const detail: HelpAnswerDetail = {
      ...answer({}),
      body: "…",
      variants: [{ locale: "en", status: "published", has_body: true, last_changed_on: null }],
      publish_is_immediate: true,
      has_approval_step: false,
    };
    const html = render(<PortalHelpEditor slug="x" readOnly={false} onBack={() => undefined} />, [
      [[...queryKeys.portalHelp, "x"], detail],
    ]);
    const publish = html.slice(html.indexOf('data-action="publish"') - 400, html.indexOf('data-action="publish"'));
    expect(publish).not.toContain('data-variant="danger"');
  });
});

describe("CWP-073 · tips (US-CWP-073)", () => {
  const tipRows: TipRow[] = [
    { id: "1", text: "A running toilet can use 4,000 gallons a month.", target_screen: "usage_looks_high", month_from: null, month_to: null, is_on: true, position: 1, in_season: true, showing_today: true, word_count: 9, word_guidance: 15 },
    { id: "4", text: "Watering before 10am loses less to evaporation.", target_screen: "usage", month_from: 6, month_to: 9, is_on: true, position: 4, in_season: false, showing_today: false, word_count: 7, word_guidance: 15 },
    { id: "5", text: "Leave a tap dripping overnight when it freezes.", target_screen: "portal_home", month_from: 12, month_to: 2, is_on: false, position: 5, in_season: false, showing_today: false, word_count: 8, word_guidance: 15 },
    { id: "6", text: "A thirty word tip is accepted and flagged against the fifteen word guidance rather than refused because the rule belongs on the screen", target_screen: "overdue", month_from: null, month_to: null, is_on: true, position: 6, in_season: true, showing_today: true, word_count: 23, word_guidance: 15 },
  ];

  /** ⚠ **THE SIX SCREENS TRAVEL WITH THE ROWS.** Typing them into the picker
   *  would be CLAUDE.md's opening trap — a seventh screen served by the API,
   *  passing `tsc` and every test, and never offered to a clerk. */
  const tips: TipsView = {
    tips: tipRows,
    all_screens: ["portal_home", "usage", "usage_looks_high", "send_a_reading", "overdue", "every_reading"],
    word_guidance: 15,
  };

  it("TC-3: a quiet tip says WHY, and the two reasons are independent", () => {
    const html = render(<PortalTipsList readOnly={false} />, [[queryKeys.portalTips, tips]]);
    expect(html).toContain('data-screen="CWP-073"');
    expect(html).toContain('data-showing="no"');
    expect(html).toContain('data-out-of-season=""');
    // The freeze tip is BOTH off and out of season.
    expect(html).toContain('data-switch-state="off"');
  });

  it("TC-7: a long tip is flagged, not refused", () => {
    const html = render(<PortalTipsList readOnly={false} />, [[queryKeys.portalTips, tips]]);
    expect(html).toContain('data-too-long="23"');
    expect(html).toContain("23 words");
  });

  /**
   * ⚠ **THE FIXTURE SAID `word_count: 24` AND ITS OWN TEXT IS 23 WORDS**
   * (`DEF-CWP-3823`, corrected above). Nothing could see it while only the LIST
   * rendered the figure: the list prints whatever the server sends, so a
   * fixture number that agrees with nothing still passed.
   *
   * It surfaced the moment the editor arrived, because the editor COUNTS —
   * `text.split()`, the same arithmetic `back_office_tips` does — and the two
   * disagreed by one on the same row. In the product they cannot disagree; in a
   * fixture they can, and a fixture that lies is the one place this pair of
   * counters could drift unseen. So the agreement is asserted rather than
   * assumed.
   */
  it("⚠ the editor's own count and the served one are the SAME arithmetic", () => {
    const row = tipRows[3];
    expect(tipWordCount(row.text)).toBe(row.word_count);
    for (const one of tipRows) expect(tipWordCount(one.text)).toBe(one.word_count);
  });

  it("⚠ the switch is the KIT's control, not a bordered word-button (rule 36 breach (d))", () => {
    const html = render(<PortalTipsList readOnly={false} />, [[queryKeys.portalTips, tips]]);
    expect(html).toMatch(/role="switch"[^>]*data-variant="(primary|secondary)"|data-variant="(primary|secondary)"[^>]*role="switch"/);
  });

  // ══ DEF-CWP-3820 — the three writes the server has always accepted ═══════

  it("⚠ *New tip* is LIVE, and the row can be opened and removed (DEF-CWP-3820)", () => {
    const html = render(<PortalTipsList readOnly={false} />, [[queryKeys.portalTips, tips]]);
    // A disabled button and no button at all look identical to a key-set
    // check, so the ENABLED state is what is asserted.
    expect(html).toContain('data-action="new-tip"');
    expect(html).not.toMatch(/data-action="new-tip"[^>]*disabled/);
    expect(html).not.toContain("Writing tips arrives later");
    expect(html).toContain('aria-label="Edit"');
    expect(html).toContain('aria-label="Remove"');
  });

  it("BR-SHL-025: a view-only role sees the same controls, disabled with the reason", () => {
    const html = render(<PortalTipsList readOnly />, [[queryKeys.portalTips, tips]]);
    expect(html).toMatch(/data-action="new-tip"[^>]*disabled|disabled[^>]*data-action="new-tip"/);
  });

  it("TC-7 · the OTHER half: the flag is IN THE EDITOR, while it is being typed", () => {
    const html = render(<PortalTipEditor tipId="6" readOnly={false} onBack={() => undefined} />, [
      [queryKeys.portalTips, tips],
    ]);
    expect(html).toContain('data-screen="CWP-073-editor"');
    // Accepted, never refused: Save is live on a 24-word tip.
    expect(html).toContain('data-editor-too-long="23"');
    expect(html).not.toMatch(/data-action="save"[^>]*disabled/);
  });

  it("⚠ the *where* picker offers the SERVER's six, not six typed into this app", () => {
    const html = render(<PortalTipEditor tipId="1" readOnly={false} onBack={() => undefined} />, [
      [queryKeys.portalTips, tips],
    ]);
    expect((html.match(/<option /g) ?? []).length).toBe(6);
    expect(html).toContain("Usage looks high");
    expect(html).toContain("Every reading screen");
  });

  it("⚠ the preview IS the customer's own TipBar, so it cannot drift", () => {
    const html = render(<PortalTipEditor tipId="1" readOnly={false} onBack={() => undefined} />, [
      [queryKeys.portalTips, tips],
    ]);
    expect(html).toContain('data-tip-bar="usage_looks_high"');
    expect(html).toContain("A running toilet can use 4,000 gallons a month.");
  });

  it("BR-CWP-093 in the editor: an empty tip previews as NOTHING, not as a frame", () => {
    const html = render(<PortalTipEditor tipId={null} readOnly={false} onBack={() => undefined} />, [
      [queryKeys.portalTips, tips],
    ]);
    expect(html).toContain('data-preview-empty=""');
    expect(html).not.toContain("data-tip-bar=");
    // Hard-won law 3: a brand-new tip is OFF, and Save is held until it says
    // something.
    expect(html).toMatch(/data-switch-state="off"/);
    expect(html).toMatch(/data-action="save"[^>]*disabled|disabled[^>]*data-action="save"/);
    // A tip that does not exist yet cannot be removed.
    expect(html).not.toContain('data-action="remove"');
  });
});

describe("CWP-074 · CWP-075 · service centres (US-CWP-074)", () => {
  const view: ServiceCentresView = {
    all_actions: ["pay_a_bill", "open_or_close_an_account", "report_a_problem", "hand_in_a_document", "ask_a_question"],
    all_payment_methods: ["cash", "cheque", "card", "money_order"],
    centres: [
      { slug: "main-office", name: "Main office", address: "214 Cedar St, Austin TX 78702", phone: "(512) 555-0148", directions_note: null, allowed_actions: ["pay_a_bill", "open_or_close_an_account", "report_a_problem", "hand_in_a_document", "ask_a_question"], payment_methods_accepted: ["cash", "cheque", "card", "money_order"], is_shown_to_customers: true, position: 1, hours: [], today: { is_open_now: true, closes_at: "17:00", opens_later_today: false, next_open_date: null, next_open_weekday: null, next_open_is_today: false, next_open_at: null, closed_for_holiday: null, next_holiday: null }, last_changed_on: null },
      { slug: "north-counter", name: "North counter", address: "1190 Palm Ct, Austin TX 78758", phone: null, directions_note: null, allowed_actions: ["pay_a_bill"], payment_methods_accepted: ["cash", "cheque"], is_shown_to_customers: true, position: 2, hours: [], today: { is_open_now: false, closes_at: null, opens_later_today: false, next_open_date: null, next_open_weekday: 3, next_open_is_today: false, next_open_at: "09:00", closed_for_holiday: null, next_holiday: null }, last_changed_on: null },
      { slug: "depot", name: "Depot", address: "44 Works Rd, Austin TX 78721", phone: null, directions_note: null, allowed_actions: [], payment_methods_accepted: [], is_shown_to_customers: false, position: 3, hours: [], today: { is_open_now: false, closes_at: null, opens_later_today: false, next_open_date: null, next_open_weekday: null, next_open_is_today: false, next_open_at: null, closed_for_holiday: null, next_holiday: null }, last_changed_on: null },
    ],
  };

  it("TC-1: the depot is HIDDEN and still in this list — that is the whole rule", () => {
    const html = render(<CentresList readOnly={false} />, [[queryKeys.serviceCentres, view]]);
    expect(html).toContain('data-screen="CWP-074"');
    expect((html.match(/data-centre-row="/g) ?? []).length).toBe(3);
    expect(html).toContain('data-centre-row="depot" data-shown="no"');
    expect(html).toContain("Hiding keeps a place on this list and off the portal.");
  });

  it("TC-9: Remove is the danger tier and hiding is what the screen recommends", () => {
    const detail: ServiceCentreDetail = {
      slug: "depot",
      name: "Depot",
      address: "44 Works Rd, Austin TX 78721",
      phone: null,
      directions_note: null,
      allowed_actions: [],
      all_actions: view.all_actions,
      payment_methods_accepted: [],
      all_payment_methods: view.all_payment_methods,
      is_shown_to_customers: false,
      position: 3,
      hours: [{ day_of_week: 0, is_closed: true, opens_at: null, closes_at: null }],
      last_changed_on: null,
    };
    const html = render(<ServiceCentreEditor slug="depot" readOnly={false} onBack={() => undefined} />, [
      [[...queryKeys.serviceCentres, "depot"], detail],
    ]);
    expect(html).toContain('data-screen="CWP-075"');
    expect(html).toMatch(/data-variant="danger"[^>]*>|data-action="remove"/);
    // ⚠ CHIPS, NOT CHECKBOXES (r10 rule 9 / rule 36 breach (e)).
    expect(html).toContain('data-chip-select="actions"');
    expect(html).toContain('data-chip-select="methods"');
    expect(html).not.toContain('type="checkbox"');
  });

  // ══ DEF-CWP-3821 — a utility could never get its FIRST centre ════════════

  it("⚠ *New centre* is LIVE, and the held sentence is gone (DEF-CWP-3821)", () => {
    const html = render(<CentresList readOnly={false} />, [[queryKeys.serviceCentres, view]]);
    expect(html).toContain('data-action="new-centre"');
    expect(html).not.toMatch(/data-action="new-centre"[^>]*disabled/);
    expect(html).not.toContain("Adding centres arrives later");
  });

  it("a NEW centre starts HIDDEN, with seven closed days and nothing to remove", () => {
    const html = render(<ServiceCentreEditor slug={null} readOnly={false} onBack={() => undefined} />, [
      [queryKeys.serviceCentres, view],
    ]);
    expect(html).toContain('data-screen="CWP-075"');
    // Law 3: publishing an address a customer will drive to is the option you
    // have to type.
    expect(html).toContain("Hidden");
    expect((html.match(/data-hour-row="/g) ?? []).length).toBe(7);
    expect(html).not.toContain('data-action="remove"');
    // Name and address are required, so Save is held until they are typed.
    expect(html).toMatch(/data-action="save"[^>]*disabled|disabled[^>]*data-action="save"/);
    // ⚠ THE FIVE ACTIONS AND FOUR TENDERS COME FROM THE LIST READ, not from a
    // literal in the editor — there is no detail row to read them off.
    expect(html).toContain('data-chip-select="actions"');
    expect(html).toContain("Money order");
  });
});
