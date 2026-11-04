// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave E — E7 (group the template list by event) and E8 (the
//          list toolbar in the toolkit's own shape).
// Screens: SET-09
// Rules:   B14 rule 12 (one search · a removable chip per filter · one
//          `+ Filter` · column picker) · B14 rule 19 (the module's own search
//          prompt) · B14 rule 21 (utilities only; both files are on
//          `route-b-migrated.txt`) · BR-SHL-010 (an undeclared capability is
//          not rendered) · BR-SHL-011 (`f.<name>` URL grammar) · DEF-442 (the
//          filter panel + removable chips) · DEF-1700 (a screen that wants a
//          new dimension DECLARES it; it does not grow a row of controls)
// ───────────────────────────────────────────────────────
// WHAT THESE TWO TASKS ARE ACTUALLY ABOUT, AND WHY THEY SHARE A FILE.
//
// E7's complaint is that SET-09 lists **37 rows because every channel is its
// own row**: *"Bill ready · e-bill email"* and *"Bill ready · SMS"* sit apart
// as though they were unrelated documents. They are one EVENT on two SURFACES,
// and the list already holds everything needed to say so.
//
// E8's complaint is that the same screen draws its OWN toolbar — a labelled
// search box and six category pills — beside four other screens that draw the
// shared one. Both are about the SAME control row, so a change to either moves
// the same markup, and splitting them across two files would let one pass while
// the other silently reverted it.
//
// ── ⚠ WHAT THE SERVER DOES NOT SERVE, STATED RATHER THAN INVENTED ─────────
// **There is no event id on a catalog row.** `TemplateCatalogRow` carries
// `group` (the CHANNEL FAMILY — printable / email / sms / contracts / in_app)
// and `channel` (`pdf_print` / `email` / `sms` / `in_app`), and `catalogs.py`
// says in as many words that `group` *"is not `category`"* and answers *"what
// kind of artifact is this"*. Neither is the event. The event key DOES exist on
// the server — `rule_catalog.EventClass.key`, with `template_classes={E:
// "email_bill_ready", S: "sms_bill_ready"}` — and **that mapping is not on this
// endpoint's payload**, so nothing here can read it without a second request
// into another screen's contract.
//
// So the event is DERIVED, from the one place the relationship is already
// written down in full: the template's own NAME. The seeded names are built
// `<event> · <surface>` — *"Past-due reminder · Email"*, *"Past-due reminder ·
// SMS"*, *"Bill ready · e-bill email"* — which is exactly the shape E7 quotes.
// That is a regrouping of rows that already know their event and their surface,
// with no schema change and no migration, which is what the task asks for.
//
// ── ⚠ AND THE MEASURED FIGURE DISAGREES WITH THE PACKET BY ONE ────────────
// CR-048 E7 says *"Four events have more than one surface today."* Derived from
// the 37 seeded names, **FIVE stems carry more than one row**:
//
//   · Past-due reminder      3  (printable · email · SMS)
//   · Disconnect notice      4  (10-day · 5-day · 48-hour · SMS supplement)
//   · Payment receipt        3  (printable · email · SMS)
//   · Bill ready             2  (e-bill email · SMS)
//   · Payment plan           3  (instalment due · instalment missed · voided)
//
// The first four are one event on several surfaces and are the four the packet
// counts. **The fifth is not**: *"Payment plan · instalment due"*, *"· missed"*
// and *"· voided"* are three DIFFERENT events sharing a family name, and
// `rule_catalog` gives none of them an entry at all. Grouping them together is
// still the right drawing — they are the same document family and a person
// looking for one is looking near the others — but the count is FIVE and the
// packet says four, so it is written down here rather than rounded to match.
//
// ── PROVED RED FIRST (hard-won law 7) ─────────────────────────────────────
// Run against the pre-change screen: **8 failed, 2 passed**. One message per
// failing case, quoted verbatim:
//   · the event is named once per run   → Unable to find an element by:
//       [data-testid="event-heading-Bill ready"]
//   · a surface row says which surface  → Unable to find an element by:
//       [data-testid="surface-sms_bill_ready"]
//   · a lone template keeps its name    → Unable to find an element by:
//       [data-testid="event-heading-Write-off notice"]
//   · the run count is on the heading   → Unable to find an element by:
//       [data-testid="event-count-Past-due reminder"]
//   · rule 19's prompt on the shared box →
//       expect(element).toHaveAttribute("aria-label", "Search template name,
//       code, category or use…")
//   · the category dimension is the shared FilterBar →
//       expected <button type="button" …(5)></button> to be null   (`chip-all`,
//       the first of this screen's six own pills, was still on screen)
//   · the panel OFFERS its options      → Unable to find an accessible element
//       with the role "checkbox" and name "Collections"
//   · the page action is in the title row → Unable to find an element by:
//       [data-testid="templates-title-row"]
//
// ⚠ **THE TWO THAT PASSED BEFORE THE CHANGE ARE GUARDS, AND THEY ARE LABELLED
// AS SUCH RATHER THAN COUNTED AS PROOF.** *"there is ONE search box"* passes
// today only because `searchFields` is UNDECLARED, so `DataTable` draws none
// and this screen's own box is the only one — it goes red the instant the
// capability is declared and the local box is left behind, which is the exact
// regression E8 can produce. *"DROPS the grouping when the sort cannot keep a
// run together"* passes today because there is no grouping to drop; it pins the
// FALLBACK, so a later "improvement" that draws headings under every sort order
// fails. Neither is evidence that E7 or E8 was missing — the eight above are.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { TemplateCatalogPage, TemplateCatalogRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateCatalogTab } from "./TemplateCatalog";

afterEach(cleanup);

function aRow(overrides: Partial<TemplateCatalogRow> = {}): TemplateCatalogRow {
  return {
    code: "x",
    name: "X",
    category: "billing",
    category_source: "cr_007",
    kind: "Email",
    variants: 1,
    used_by: "Nothing yet",
    edited: null,
    edited_at: null,
    group: "email",
    channel: "email",
    catalog_unavailable: null,
    body_unavailable: null,
    has_published: true,
    ...overrides,
  };
}

/** The four seeded rows E7 names, plus one that belongs to no event — the
 *  shape the grouping has to get right in BOTH directions. Names and codes are
 *  quoted from `apps/notifications/catalogs.py`. */
const ROWS: TemplateCatalogRow[] = [
  aRow({ code: "email_bill_ready", name: "Bill ready · e-bill email", channel: "email" }),
  aRow({
    code: "sms_bill_ready",
    name: "Bill ready · SMS",
    kind: "SMS",
    group: "sms",
    channel: "sms",
  }),
  aRow({
    code: "dunning",
    name: "Past-due reminder",
    category: "collections",
    // The seeder's own value, and the reason the folded row's first control is
    // a printer: the printable original carries no ` · ` suffix because,
    // before there were two more of it, it did not need one.
    kind: "Print",
    used_by: "Payment reminders — first and second stage.",
    group: "printable",
    channel: "pdf_print",
  }),
  aRow({
    code: "email_past_due",
    name: "Past-due reminder · Email",
    category: "collections",
    used_by: "Not in use yet — no wording has been written for it.",
  }),
  aRow({
    code: "sms_past_due",
    name: "Past-due reminder · SMS",
    category: "collections",
    kind: "SMS",
    used_by: "Not in use yet — no wording has been written for it.",
    group: "sms",
    channel: "sms",
  }),
  aRow({
    code: "writeoff_notice",
    name: "Write-off notice",
    category: "collections",
    group: "printable",
    channel: "pdf_print",
  }),
];

/** The minimum `TemplateDetail` the panel needs to render at all. E5's cases
 *  assert the SWITCHER and nothing else; SET-10's own suites cover the rest. */
const DETAIL_SHAPE = {
  code: "sms_bill_ready",
  name: "Bill ready · SMS",
  category: "billing",
  category_source: "cr_007",
  kind: "SMS",
  used_by: "Nothing yet",
  group: "sms",
  channel: "sms",
  // CR-076 — served, so the panel can draw its preview switcher. ⚠ This object
  // carries no `: TemplateDetail` annotation, so `tsc` did NOT name it when the
  // field was added and the five annotated fixtures were all it listed. The
  // suite went red at runtime instead, on `data.preview_surfaces is not
  // iterable` — which is the cheap version of the same lesson: a fixture that
  // opts out of the type opts out of every check that reads it.
  preview_surfaces: ["sms"],
  merge_fields: [],
  merge_field_rows: [],
  sample_identity: { customer_name: null, account_no: null },
  derived_spelling: [],
  platform_default: null,
  mandatory_content: [],
  custom_field_variables: [],
  catalog_unavailable: null,
  body_unavailable: null,
  variants: [],
  selected_variant: null,
  versions: [],
  preview: null,
  preview_unavailable: null,
  sms_character_counter: 160,
  can_edit: true,
  cannot_edit_reason: null,
  can_test_send: false,
  test_send_reason: "No dispatcher in this release.",
  can_download_pdf: false,
  download_pdf_reason: "No page writer for notices.",
  can_set_default: false,
  set_default_reason: "The default variant is the row's KEY.",
  language_selection_reason: "Languages come from regional settings.",
  set_default_br_ref: "OQ-252",
  language_selection_br_ref: "BR-SHL-041",
};

function aPage(overrides: Partial<TemplateCatalogPage> = {}): TemplateCatalogPage {
  return {
    count: ROWS.length,
    results: ROWS,
    page: 1,
    per: 50,
    categories: [
      { key: "billing", count: 2 },
      { key: "collections", count: 4 },
      { key: "payments", count: 0 },
      { key: "service_field", count: 0 },
      { key: "account_lifecycle", count: 0 },
    ],
    columns: [
      { key: "name", always: true },
      { key: "category", always: false },
      { key: "kind", always: false },
      { key: "variants", always: false },
      { key: "used_by", always: false },
      { key: "edited", always: false },
    ],
    page_sizes: [50, 100, 200, 500, 1000],
    can_edit: true,
    cannot_edit_reason: null,
    create_action: "variant",
    create_action_reason: "A template CLASS is platform vocabulary. OQ-253.",
    ...overrides,
  };
}

/** Seeds the cache under the key the screen will ask for, so the table renders
 *  its rows synchronously. `sort` is the screen's `defaultSort`, which E7 moves
 *  from `category` to `name` — the ONE server-sortable column whose order puts
 *  a run of surfaces together. */
function renderCatalog(
  page: TemplateCatalogPage,
  { sort = "name", entry = "/" }: { sort?: string; entry?: string } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(["template-catalog", "", "", sort, 1, 50, "asc"], page);
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>
          <TemplateCatalogTab readOnly={false} client={{} as never} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-048 wave I — one row per template, with a control per surface", () => {
  it("names the event ONCE, and never prints the same name twice in one cell", () => {
    renderCatalog(aPage());
    // *"why we are showing two names under template name"* — PO, 2026-08-30.
    // Wave E drew the event as a heading ABOVE the row's own name, so a
    // template that is its own event printed its name twice. There is no
    // heading element left at all: a row's name comes from one place.
    expect(screen.queryByTestId("event-heading-Bill ready")).toBeNull();
    expect(screen.queryByTestId("event-heading-Write-off notice")).toBeNull();
    // "Bill ready" is ONE row now, named for the event.
    expect(screen.getByTestId("template-name-email_bill_ready")).toHaveTextContent(/^Bill ready$/);
    // …and the sibling surface is no longer a row of its own.
    expect(screen.queryByTestId("template-name-sms_bill_ready")).toBeNull();
  });

  it("a template that is its own event keeps its whole name, unchanged", () => {
    renderCatalog(aPage());
    // "Write-off notice" has no ` · `, so there is no event to fold it under
    // and nothing about the row changes. This is the case wave E got wrong.
    expect(screen.getByTestId("template-name-writeoff_notice")).toHaveTextContent(
      /^Write-off notice$/,
    );
  });

  it("every folded surface is still ONE CLICK away, as a control in the Kind column", () => {
    renderCatalog(aPage());
    // *"you can also do that by havng action button for each type that way
    // screen and table remain clean"* — the PO's own design instruction.
    // Past-due reminder is one row with three surface controls.
    expect(screen.getByTestId("template-surface-dunning")).toBeInTheDocument();
    expect(screen.getByTestId("template-surface-email_past_due")).toBeInTheDocument();
    expect(screen.getByTestId("template-surface-sms_past_due")).toBeInTheDocument();
    // …and only one of the three is a ROW.
    expect(screen.queryByTestId("template-name-email_past_due")).toBeNull();
    expect(screen.queryByTestId("template-name-sms_past_due")).toBeNull();
  });

  /* ⚠ AMENDED BY CR-199-BRC10 F1. CR-048 wave I drew the Kind column as
     icons; the redesign (`01-list.png`) draws a **Channels** column of small
     word tags — *Email*, *Text*, *Letter*, *In-app*. What these two cases
     pinned survives: every channel is NAMED (never a silent glyph), a folded
     row keeps one control per channel with an accessible name, and a channel
     this screen has no word for prints its own value rather than a wrong one. */
  it("every channel tag says its WORD, and a folded row's tags are named controls", () => {
    renderCatalog(aPage());
    const surface = screen.getByTestId("template-surface-sms_past_due");
    expect(surface).toHaveTextContent("Text");
    expect(surface).toHaveAttribute("aria-label", "Open Text");
    expect(screen.getByTestId("template-surface-dunning")).toHaveTextContent("Letter");
    // A template that is its own event draws its tag without a button.
    const solo = screen.getByTestId("template-channel-writeoff_notice");
    expect(solo).toHaveTextContent("Letter");
    expect(solo.querySelector("button")).toBeNull();
  });

  it("a row's channel is the template's OWN channel, never parsed out of the kind sentence", () => {
    renderCatalog(
      aPage({
        results: [
          aRow({
            code: "contract_autopay_authorization",
            name: "Autopay authorization (NACHA)",
            kind: "PDF + click-to-accept",
            channel: "pdf_print",
          }),
          aRow({ code: "odd_one", name: "Something else", kind: "Carrier pigeon", channel: "pigeon" }),
        ],
      }),
    );
    // One template, one channel — however many words its kind sentence has.
    expect(screen.getByTestId("template-channel-contract_autopay_authorization")).toHaveTextContent(
      /^Letter$/,
    );
    // A channel this screen has no word for prints ITS OWN value.
    expect(screen.getByTestId("template-channel-odd_one")).toHaveTextContent("pigeon");
  });
  it("⚠ DROPS the folding when the sort cannot keep a run together", () => {
    // A run is only contiguous while the list is sorted by NAME ascending.
    // Sorted by category, "Bill ready · SMS" and "Bill ready · e-bill email"
    // can be pages apart — and folding rows that are not adjacent would hide a
    // template inside a row it does not belong to. So the list falls back to
    // exactly the flat screen it was.
    renderCatalog(aPage(), { sort: "category", entry: "/?sort=category" });
    expect(screen.getByTestId("template-name-sms_bill_ready")).toHaveTextContent(
      "Bill ready · SMS",
    );
    expect(screen.getByTestId("template-name-email_bill_ready")).toHaveTextContent(
      "Bill ready · e-bill email",
    );
  });
});

describe("CR-048 wave I — the Used-by column is a status, and the sentence is not lost", () => {
  it("shows a short status instead of the server's sentence", () => {
    renderCatalog(
      aPage({
        results: [
          aRow({
            code: "writeoff_notice",
            name: "Write-off notice",
            used_by: "Not in use yet — approving a write-off does not send a letter.",
          }),
        ],
      }),
    );
    const cell = screen.getByTestId("template-usedby-writeoff_notice");
    expect(cell).toHaveTextContent("Not in use yet");
    expect(cell.textContent).not.toContain("approving a write-off");
    // The WHOLE sentence is still one hover away — deleting this assertion is
    // deleting the fact, not tidying the test.
    expect(cell.querySelector(".pill")).toHaveAttribute(
      "title",
      "Not in use yet — approving a write-off does not send a letter.",
    );
  });

  it("holds DEF-163's two absences apart — an unwritten letter and a placeholder are different states", () => {
    renderCatalog(
      aPage({
        results: [
          aRow({
            code: "contract_autopay_authorization",
            name: "Autopay authorization (NACHA)",
            used_by: "Not in use yet — no wording has been written for it.",
            body_unavailable:
              "PLACEHOLDER, NOT WORDING, under the PO ruling of 2026-08-18: the wording of an " +
              "authorization for recurring ACH debits is prescribed by the NACHA Operating Rules.",
          }),
          aRow({
            code: "email_deposit",
            name: "Deposit agreement",
            used_by: "Not in use yet — no wording has been written for it.",
            body_unavailable: "Nobody has written this letter yet.",
          }),
          aRow({ code: "dunning", name: "Past-due reminder", used_by: "Payment reminders." }),
        ],
      }),
    );
    expect(
      screen.getByTestId("template-usedby-contract_autopay_authorization"),
    ).toHaveAttribute("data-usedby-state", "placeholder");
    expect(screen.getByTestId("template-usedby-email_deposit")).toHaveAttribute(
      "data-usedby-state",
      "no-wording",
    );
    expect(screen.getByTestId("template-usedby-dunning")).toHaveAttribute(
      "data-usedby-state",
      "in-use",
    );
  });

  it("no row of the list carries a paragraph any more — the autopay explanation is off the row", () => {
    const { container } = renderCatalog(
      aPage({
        results: [
          aRow({
            code: "contract_autopay_authorization",
            name: "Autopay authorization (NACHA)",
            body_unavailable:
              "PLACEHOLDER, NOT WORDING, under the PO ruling of 2026-08-18 (CR-011 item 9): the " +
              "wording of an authorization for recurring ACH debits is prescribed by the NACHA " +
              "Operating Rules, a scheme this repository does not hold.",
          }),
        ],
      }),
    );
    // *"autopay - why you are howing text - this is internal not required"*.
    expect(container.querySelector("tbody [data-refusal]")).toBeNull();
    expect(container.querySelector("tbody")?.textContent).not.toContain("NACHA Operating Rules");
    // The state it carried survives as the chip.
    expect(
      screen.getByTestId("template-usedby-contract_autopay_authorization"),
    ).toHaveAttribute("data-usedby-state", "placeholder");
  });

  it("a folded row whose surfaces disagree says so, with the breakdown on hover", () => {
    renderCatalog(aPage());
    // Past-due reminder folds a printable original that IS in use with two
    // surfaces that are not — one chip cannot be true for all three, so it
    // says Mixed rather than picking whichever sorted first.
    const cell = screen.getByTestId("template-usedby-dunning");
    expect(cell).toHaveAttribute("data-usedby-state", "mixed");
    const title = cell.querySelector(".pill")?.getAttribute("title") ?? "";
    // `DEF-NOT-5392` (FIX-7, 2026-10-05): the seeded and catalogued name is
    // *"Past-due reminder · Email"* since DEF-NOT-4416, so the surface reads "Email".
    expect(title).toContain("Email:");
    expect(title).toContain("SMS:");
    expect(title).toContain("Payment reminders");
  });
});

describe("CR-048 E8 — the toolbar is the toolkit's, not this screen's own", () => {
  it("there is ONE search box on the screen, and it is DataTable's", () => {
    renderCatalog(aPage());
    // B14 rule 12 asks for one search. The screen used to render its own
    // labelled `input[type=search]` in the filter slot *beside* DataTable's,
    // which `searchFields` being undeclared kept hidden — so the moment the
    // capability is declared, two boxes appear unless the local one goes.
    expect(document.querySelectorAll("input[type='search']")).toHaveLength(1);
  });

  it("B14 rule 19 — the one box carries the MODULE's prompt, not 'Search this list'", () => {
    renderCatalog(aPage());
    const box = document.querySelector("input[type='search']");
    expect(box).toHaveAttribute(
      "placeholder",
      "Search template name, code, category or use…",
    );
    // The accessible name is the SAME sentence — a screen reader reading a
    // different prompt from the sighted one is the split rule 19 closes.
    expect(box).toHaveAttribute(
      "aria-label",
      "Search template name, code, category or use…",
    );
  });

  it("the category dimension is the shared FilterBar, not six pills of this screen's own", () => {
    renderCatalog(aPage());
    // DEF-442 · DEF-1700: a screen that wants a dimension DECLARES it and the
    // `+ Filter` panel offers it. The six hand-rolled `chip-<key>` buttons are
    // exactly the duplicated dimension row DEF-1700 ruled away.
    expect(screen.queryByTestId("chip-all")).toBeNull();
    expect(screen.queryByTestId("chip-collections")).toBeNull();
    // The `+ Filter` control is FilterBar's `<summary>`, not a `<button>` — a
    // `<details>` disclosure loses its behaviour if the trigger is anything
    // else, which that file records as the one case `buttonKit` sanctions a
    // raw class string for. So it is matched by its text, not by a role it
    // deliberately does not have.
    expect(screen.getByText("+ Filter").tagName).toBe("SUMMARY");
    // …and the shared `All` chip IS present — the six that went are this
    // screen's own `chip-<key>` pills, not the toolkit's one.
    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
  });

  it("the declared filter OFFERS its options — an empty `options` renders no panel at all", () => {
    renderCatalog(aPage());
    // `offerableFilters` drops a group with no options (DEF-782), and the
    // config declared `options: []` — so the panel was empty and the dimension
    // unreachable even once FilterBar was mounted. The options come from the
    // server's own `categories`.
    expect(screen.getByRole("checkbox", { name: "Collections" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Billing" })).toBeInTheDocument();
  });

  it("no page action sits on a row of its own above the toolbar — the variant actions are on the rows", () => {
    /* ⚠ AMENDED BY CR-199-BRC10 F1. CR-048 E8 moved `+ New variant` into the
       title row; the redesign (`01-list.png`) draws no page action on the list
       at all, because a variant is made FROM the template it varies — every
       row's `…` holds *Duplicate as variant* and the workspace has
       `+ New variant` (`CR-199-BRC10` §6 L10). What E8 guarded still holds:
       there is no control band between the heading and the toolbar. */
    renderCatalog(aPage());
    expect(screen.queryByTestId("template-new")).toBeNull();
    expect(screen.queryByTestId("template-toolbar")).toBeNull();
    expect(screen.getByTestId("templates-title-row")).toBeInTheDocument();
    expect(screen.getByTestId("template-duplicate-email_bill_ready")).toBeInTheDocument();
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 E5 — THE CHANNEL SWITCHER
 * ══════════════════════════════════════════════════════════════════════════
 * *"One notice, four surfaces; switching changes both the rail and the page.
 * Needs E7."*
 *
 * It needs E7 because the relationship it switches along IS E7's: the sibling
 * surfaces of a template are the other rows of its event, and `siblingSurfaces`
 * is that same derivation read from one row outward instead of down a page.
 *
 * ⚠ **THE DETAIL PAYLOAD CARRIES NO SIBLING LIST**, so the switcher cannot be
 * built inside SET-10 from what SET-10 fetches. `GET /template-catalog/{code}`
 * answers about ONE class — its variants, its versions, its merge fields — and
 * nothing on it names another class. What holds the relationship is the CATALOG
 * PAGE the list already has in hand, so the list passes its rows down. That is
 * also why there is no switcher on a detail screen reached by a pasted
 * `?template=` link whose row is not on the loaded page: an empty list draws no
 * furniture (BR-SHL-010) rather than a switcher built from whichever rows
 * happened to be cached.
 *
 * ⚠ **AND "SWITCHING CHANGES BOTH THE RAIL AND THE PAGE" IS FREE HERE**, which
 * is worth saying because it looks unimplemented. A surface is a different
 * TEMPLATE CLASS, not a mode of one — `sms_bill_ready` and `email_bill_ready`
 * are two rows with two bodies, two version lists and two merge-field
 * whitelists. So the switcher navigates `?template=`, the detail refetches, and
 * `designerKind` redraws both halves off the new payload's `group`. Nothing
 * needs to be told to change.
 *
 * ── PROVED RED FIRST (hard-won law 7) ─────────────────────────────────────
 * 1 failed, 1 passed:
 *   · offers the event's other surfaces → Unable to find an element by:
 *       [data-testid="surface-switch-email_bill_ready"]
 * The passing one is the absence guard — no switcher on a template that is its
 * own event — which passes today because there is no switcher anywhere; it
 * pins the BR-SHL-010 half so a later change cannot draw a one-tab switcher on
 * the 32 templates that have no siblings.
 */
describe("CR-048 E5 — one notice, its other surfaces", () => {
  function openTemplate(code: string, page = aPage()) {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    client.setQueryData(["template-catalog", "", "", "name", 1, 50, "asc"], page);
    // The detail query the panel will ask for. Only the fields the switcher
    // reads matter here; the rest of SET-10 has its own suite.
    client.setQueryData(["template-catalog", "detail", code, "default"], {
      ...DETAIL_SHAPE,
      code,
      name: page.results.find((row) => row.code === code)?.name ?? code,
    });
    return render(
      <QueryClientProvider client={client}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/?template=${code}`]}>
            <TemplateCatalogTab readOnly={false} client={{} as never} />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  /* ⚠ AMENDED BY CR-199-BRC10 F2. The surface switcher — a strip of buttons at
     the top of the rail — is the drawing's **Channel** picker now (`02`, `05`):
     the first of the three pickers under the title. What these cases pinned is
     unchanged and is asserted against the new control: the other channels are
     offered, the open one is marked, a template that is its own event has
     nothing to switch to, and the consequence of switching is said beside the
     control (PO ruling 2026-09-08). */
  it("offers the event's OTHER channels, and marks the one that is open", () => {
    openTemplate("sms_bill_ready");
    const picker = screen.getByTestId("picker-channel");
    const select = picker.querySelector("select") as HTMLSelectElement;
    const codes = [...select.options].map((option) => option.value);
    expect(codes).toEqual(expect.arrayContaining(["sms_bill_ready", "email_bill_ready"]));
    expect(select.value).toBe("sms_bill_ready");
    expect(select).not.toBeDisabled();
  });

  it("a template that is its own event has NO other channel to switch to", () => {
    // BR-SHL-010: a picker with one choice cannot do anything, so it is drawn
    // disabled with that one choice rather than offering nothing.
    openTemplate("writeoff_notice");
    const select = screen.getByTestId("picker-channel").querySelector("select") as HTMLSelectElement;
    expect(select.options).toHaveLength(1);
    expect(select).toBeDisabled();
  });

  it("is the FIRST of the pickers, under the title", () => {
    openTemplate("sms_bill_ready");
    const pickers = screen.getByTestId("workspace-pickers");
    const first = pickers.querySelector("[data-testid^='picker-']");
    expect(first).toHaveAttribute("data-testid", "picker-channel");
  });

  it("draws no rationale under the Channel picker (DEF-NOT-10673, B14 rule 33)", () => {
    // The 2026-09-08 "Each is edited and published separately…" line was a
    // WHY; image 02 draws the picker with nothing under it.
    openTemplate("sms_bill_ready");
    expect(screen.getByTestId("picker-channel")).toHaveTextContent("Channel");
    expect(screen.getByTestId("picker-channel")).not.toHaveTextContent("published separately");
  });
});
