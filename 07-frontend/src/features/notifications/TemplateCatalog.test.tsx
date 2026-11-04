// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    CR-007 (SET-09 the template catalog · SET-10 the template detail)
//           Screens: SET-09 · SET-10
// Rules:    BR-NOT-014 (three disconnect slots) · BR-NOT-015 (the rights footer
//           is a PLATFORM DEFAULT a System Admin overrides — the PO ruled on
//           2026-08-17 that the platform WRITES the five sentences) · BR-SHL-025 (a
//           forbidden control renders DISABLED WITH ITS REASON, never hidden) ·
//           BR-BIL-026 (an edit is a NEW version) · CLAUDE.md rule 4
// ───────────────────────────────────────────────────────
// ⚠ **THE FILE OPTS INTO jsdom AS OF 2026-09-07, AND FOR ONE REASON: SET-10 HAS
// TWO MODES NOW.** The Product Owner ruled that editing is a mode — the screen
// opens on the rendered document and the wording form appears when *Edit
// wording* is pressed — so a static render reaches the READING half only.
// `renderEditingDetail` mounts, presses that one control, and returns the same
// kind of markup string, so every assertion below stays an assertion about
// rendered output. Every other case is unchanged and still static.
//
//
// The assertions worth the file, in the order they would break:
//
//   1. **The three disabled controls are all PRESENT and each says something
//      DIFFERENT.** Test send, sample PDF and set default are refused for three
//      unrelated reasons with three different fixes; a screen that hid them, or
//      that showed one generic "not available" for all three, would send a
//      System Admin looking in the wrong place three times.
//   2. **A template with no body says so, in the server's words, with its OQ.**
//      ⚠ AMENDED 2026-08-17. This read *"every disconnect slot is empty
//      (OQ-250)"*, and the id was wrong twice over (OQ-250 is CR-005's
//      counter-pad question; the rights-footer row is OQ-253, itself minted
//      twice — DEF-226). The PO then ruled that the platform writes the five
//      rights sentences, so the disconnect slots are seeded and the fixture
//      moves to a class no ruling has reached: the NACHA autopay
//      authorization, whose wording is a payment scheme's. **The behaviour
//      under test is unchanged** — a row must never render a confident name
//      over a letter that cannot be produced.
//   3. **A read-only role sees the create control disabled with its reason**,
//      not a screen with the button missing (BR-SHL-025 + the PO's Settings
//      ruling of 2026-08-16).
//   4. **The save button says "Save as new version".** BR-BIL-026 makes every
//      edit a new append-only version and the published one keeps going out
//      until somebody publishes; a button labelled "Save" would promise that
//      typing changes what customers receive.
//
// No DOM library is in package.json, so these assert on react-dom/server static
// markup — real render output, no new dependency (the idiom StateFrame.test.tsx
// established).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type {
  TemplateCatalogPage,
  TemplateCatalogRow,
  TemplateDetail,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateCatalogTab } from "./TemplateCatalog";
import { TemplateWorkspace as TemplateDetailPanel } from "./TemplateWorkspace";

const READ_ONLY_REASON =
  "Templates are System Admin only. A Billing Clerk or an Executive can read every " +
  "template, every variant, every version and the preview, and can change none of them.";

const NO_BODY_REASON =
  "A COMPLIANCE DOCUMENT. BR-NOT-004 type 4 is NACHA-required for recurring ACH: its " +
  "wording is prescribed by a scheme this repo does not hold, and it is the last " +
  "document in the product that should be drafted by inference. OQ-206.";

function aRow(overrides: Partial<TemplateCatalogRow> = {}): TemplateCatalogRow {
  return {
    code: "disconnect_notice_10_day",
    name: "Disconnect notice · 10-day warning",
    category: "collections",
    category_source: "cr_007",
    kind: "Print + email",
    variants: 0,
    used_by: "Dunning stage 1 of the regulated ladder — not yet selected (DEF-190)",
    edited: null,
    edited_at: null,
    group: "printable",
    channel: "pdf_print",
    catalog_unavailable: null,
    body_unavailable: NO_BODY_REASON,
    has_published: false,
    ...overrides,
  };
}

function aPage(overrides: Partial<TemplateCatalogPage> = {}): TemplateCatalogPage {
  return {
    count: 1,
    results: [aRow()],
    page: 1,
    per: 50,
    categories: [
      { key: "billing", count: 0 },
      { key: "collections", count: 1 },
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
    create_action_reason:
      "A template CLASS is platform vocabulary. What this button creates is a new " +
      "VARIANT of a listed template. OQ-253.",
    ...overrides,
  };
}

function aDetail(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    code: "dunning",
    name: "Past-due reminder",
    category: "collections",
    category_source: "cr_007",
    kind: "Print",
    used_by: "notices.generate_reminder — dunning stages 1-2 (BR-NOT-008)",
    group: "printable",
    channel: "pdf_print",
    // CR-076 — the surfaces this class is a form for, SERVED. `"Print"` is
    // one channel, so the designer draws no switcher for it.
    preview_surfaces: ["printable"],
    merge_fields: ["account", "balance", "first_name"],
    // The PO's two-column right rail: the token AND the value it resolves to.
    merge_field_rows: [
      {
        token: "account",
        insert: "{account}",
        sample_value: "SAMPLE-ACCOUNT",
        sample_unavailable: null,
        derived_spelling: false,
      },
      {
        token: "balance",
        insert: "{balance}",
        sample_value: "USD 123.45",
        sample_unavailable: null,
        derived_spelling: false,
      },
      {
        token: "first_name",
        insert: "{first_name}",
        sample_value: "Sample",
        sample_unavailable: null,
        derived_spelling: false,
      },
      {
        // BR-TEN-017 — stamped from Settings → Company, never sampled, so the
        // pane shows whether THIS utility has filled its profile in.
        token: "utility_name",
        insert: "{utility_name}",
        sample_value: null,
        sample_unavailable:
          "the utility's own, stamped at render (BR-TEN-017) — never sampled.",
        derived_spelling: false,
      },
    ],
    sample_identity: { customer_name: "Sample Customer", account_no: "SAMPLE-ACCOUNT" },
    derived_spelling: [],
    // CR-011 item 9 — the server always sends this key; only the four
    // contract classes carry a value. These fixtures are not contracts.
    platform_default: null,
    mandatory_content: [],
    custom_field_variables: ["{{account.custom.<key>}}"],
    catalog_unavailable: null,
    body_unavailable: null,
    variants: [
      {
        id: "v-default",
        name: "Past-due reminder",
        category: "default",
        language: "default",
        is_default: true,
        active: true,
        published_version: 1,
        version_count: 1,
      },
    ],
    selected_variant: "v-default",
    versions: [
      {
        id: "ver-1",
        version: 1,
        status: "published",
        subject: null,
        body: "Hi {first_name}, your account {account} has a balance of {balance}.",
        effective_from: null,
        created_by: null,
        published_by: null,
        published_at: "2026-08-16T00:00:00Z",
        archived_at: null,
        updated_at: "2026-08-16T00:00:00Z",
        pinned_by: 3412,
        deletable: false,
        // OQ-255 — the product holds the date and neither the author's display
        // name nor a note about what changed.
        author_label: "platform seed",
        change_note: null,
        // DEF-2479 — a TABLE CELL holds a VALUE. The old fixture carried the
        // paragraph that drew a 645px-tall cell; the id rides the machine field.
        change_note_unavailable: "No change note recorded",
        change_note_br_ref: "OQ-255 · B11 F-3",
      },
    ],
    preview: {
      body: "Hi Sample, your account SAMPLE-ACCOUNT has a balance of USD 123.45.",
      subject: null,
      channel: "pdf_print",
      sample_data: true,
      // CR-048 wave I — short line on screen, whole sentence on hover.
      sample_data_notice: "Preview only — sample data, nothing is sent.",
      sample_data_detail:
        "Rendered from SAMPLE data — no customer, no account and no " +
        "balance on this page is real.",
      absences: [],
      problems: [],
      unsampled: [],
      rendered_length: 66,
    },
    preview_unavailable: null,
    sms_character_counter: 160,
    can_edit: true,
    cannot_edit_reason: null,
    can_test_send: false,
    test_send_label: "System Admin only",
    test_send_reason:
      "No test send in this release, on any channel. There is no dispatcher and no " +
      "provider integration, and the PO declined the resend-invite action with \"no " +
      "email yet\".",
    can_download_pdf: false,
    // DEF-2479 — no module path and no OQ id in the sentence any more.
    download_pdf_label: "No sample PDF",
    download_pdf_reason: "No sample PDF for this class — the preview shows the text body.",
    can_set_default: false,
    // DEF-335 — customer-facing wording, provenance on the machine field.
    // CR-048 wave I — plus the short label the screen actually draws.
    set_default_label: "Default is fixed",
    set_default_reason:
      "You cannot change which variant is the default yet. " +
      "Messages already sent must keep the exact wording they used.",
    set_default_br_ref: "BR-NOT-001 · BR-NOT-006 · BR-BIL-026 · OQ-252",
    // The server's own words since OQ-CUS-12619 (2026-09-23): a message goes
    // in the utility's language, never the customer's.
    language_selection_label: "Utility's language only",
    language_selection_reason:
      "Messages use your utility's language. Other languages are never chosen.",
    language_selection_br_ref: "BR-NOT-006 · OQ-CUS-12619",
    ...overrides,
  };
}

/** Render with the query already resolved, so the markup is the loaded screen
 *  and not a skeleton. No network, no timers.
 *
 *  ⚠ AMENDED 2026-08-18 (DEF-211 · DEF-212), and the amendments are the two
 *  changes those defects made to how this screen is built rather than a
 *  weakening of anything asserted below:
 *    · **A ROUTER.** SET-10 has a URL now — `?template=<code>&variant=<id>` —
 *      so the tab reads `useSearchParams`, and a component that reads the URL
 *      cannot render outside a router. (The old harness needed none because
 *      opening a template was component state, which is precisely the defect.)
 *    · **THE QUERY KEY CARRIES `dir`.** The list rides the shared DataTable,
 *      whose sort cycles asc → desc (B14 rule 13); without the direction in the
 *      key, Z→A would read the A→Z page straight out of the cache.
 */
function renderCatalog(page: TemplateCatalogPage, readOnly = false): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  // ⚠ **`name`, NOT `category` (CR-048 E7).** The key mirrors the screen's
  // `defaultSort`, and E7 moved it: `name` is the one server sort under which a
  // run of one event's surfaces is CONTIGUOUS, which is what makes the grouped
  // heading a true statement about the page. A stale key here does not fail
  // loudly — the query simply misses, the table renders empty, and every
  // `toContain` below reports the CELL it was looking for as missing rather
  // than the cache key that was wrong. That is how these four went red.
  client.setQueryData(["template-catalog", "", "", "name", 1, 50, "asc"], page);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>
          <TemplateCatalogTab readOnly={readOnly} client={{} as never} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** @param view CR-048 wave I — "history" renders the VERSION HISTORY PAGE.
 *  The PO took the panel off the edit tab, so a test that wants a version
 *  row goes to `?view=history`, exactly as a person does. */
function renderDetail(
  detail: TemplateDetail,
  readOnly = false,
  view?: "history",
): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(["template-catalog", "detail", detail.code, "default"], detail);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[view === "history" ? "/?view=history" : "/"]}>
          <TemplateDetailPanel
            code={detail.code}
            client={{} as never}
            readOnly={readOnly}
            readOnlyReason={detail.cannot_edit_reason}
            variantId={null}
            onSelectVariant={() => undefined}
            onBack={() => undefined}
            /* CR-048 E5 — no siblings in these fixtures, so no switcher is
               drawn. REQUIRED rather than optional: an optional prop nothing
               passes is dead UI (hard-won law 2), and `tsc` naming all three
               call sites is what proves this one is wired. */
            surfaces={[]}
            onOpenSurface={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

/** SET-10 with the WORDING FORM OPEN — the other of its two modes (2026-09-07).
 *
 *  ⚠ **IT PRESSES THE REAL CONTROL.** There is no `editing` prop to set: an
 *  open editor is working state holding unsaved text rather than a place a link
 *  points at, so forcing the mode from outside would be testing a screen no
 *  person can produce. It returns markup, so the cases below stay written the
 *  way every other case in this file is written. */
function renderEditingDetail(detail: TemplateDetail): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(["template-catalog", "detail", detail.code, "default"], detail);
  const { container } = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/"]}>
          <TemplateDetailPanel
            code={detail.code}
            client={{} as never}
            readOnly={false}
            readOnlyReason={detail.cannot_edit_reason}
            variantId={null}
            onSelectVariant={() => undefined}
            onBack={() => undefined}
            surfaces={[]}
            onOpenSurface={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByTestId("edit-wording"));
  return container.innerHTML;
}

/** CR-199-BRC10 F6 — the merge-field rail became the `+ Insert placeholder`
 *  picker (`03`), opened from the wording pane while editing. This presses
 *  the two real controls a person presses to see it. */
function renderPlaceholderPicker(detail: TemplateDetail): string {
  cleanup();
  renderEditingDetail(detail);
  fireEvent.click(screen.getByTestId("insert-placeholder"));
  return document.body.innerHTML;
}

describe("CR-007 SET-09 · the catalog states every absence rather than showing a blank", () => {
  it("offers CR-007's five categories — through the SHARED filter panel (CR-048 E8)", () => {
    // ⚠ **THIS CASE USED TO ASSERT SIX PILLS OF THIS SCREEN'S OWN**, and the
    // pills are the thing E8 removed: the config ALREADY declared `f.category`,
    // so the pills and the `+ Filter` panel were two controls writing one
    // param — the duplicated dimension DEF-1700 ruled away on Premises, Units
    // and Reads. What must still be true is that all five categories are
    // OFFERED and that the CR's order survives, so that is what is asserted;
    // only the control they are drawn in has changed.
    const html = renderCatalog(aPage());
    for (const label of [
      "Billing",
      "Collections",
      "Payments",
      "Service &amp; field",
      "Account lifecycle",
    ]) {
      expect(html).toContain(label);
    }
    // The toolkit's own `All` chip is the absence of a filter (IS-4), and it
    // is FilterBar's now rather than this screen's.
    expect(html).not.toContain("chip-all");
    expect(html).toContain("+ Filter");
  });

  it("prints the separation of concerns CR-007 asks for — as a CAPTION, not a paragraph", () => {
    // *"Separation of concerns stated on screen: Notifications decide when,
    // Templates define what."* — CR-007, and still true.
    //
    // ⚠ CR-048 wave I — IT IS ONE LINE NOW. The PO read the deployed screen:
    // *"this sentence is too long - Notifications decide WHEN a message goes
    // out. Templates define WHAT it says. Nothing on this screen schedules,
    // triggers or sends anything."* Three sentences of explanation under a
    // screen title is a paragraph; the distinction it draws is the whole
    // reason the Templates/Notifications split exists, so it is KEPT — as the
    // caption it always was. 138 characters became 40.
    const html = renderCatalog(aPage());
    expect(html).toContain("What messages say");
    expect(html).toContain("Not when they go out");
    // The sentences that were doing the explaining are gone from the screen.
    expect(html).not.toContain("Nothing on this screen schedules");
  });

  it("says WHY an unwritten template has no body — as a STATUS on the row, with the words on hover", () => {
    // A confident row over a letter that cannot be produced is the defect
    // DEF-163 was written for, one screen along, and it is still refused.
    //
    // ⚠ CR-048 wave I — WHAT CHANGED IS THE FORM, NOT THE FACT. *"autopay -
    // why you are howing text - this is internal not required"*: the reason
    // used to render as several sentences of the platform's own reasoning
    // about NACHA operating rules, in a scrolling danger box inside the NAME
    // cell — 499 characters on a list row, measured on the running screen.
    // The row now carries a two-word status derived from the same field, and
    // the sentence rides that chip's tooltip.
    const html = renderCatalog(aPage());
    // DEF-163's two absences are still held apart, which was the whole point.
    // This fixture's reason is the "nobody has written it" kind; the
    // PLACEHOLDER kind — the one class that ships a refusal — is covered in
    // `templateCatalogGrouping.dom.test.tsx`, where both appear side by side.
    expect(html).toContain('data-usedby-state="no-wording"');
    expect(html).toContain("Wording not written");
    // The words are still in the document — on the chip, not in the row.
    expect(html).toContain("NACHA");
    // …and no paragraph is rendered inside a table cell any more.
    expect(html).not.toContain("data-refusal");
  });

  it("never renders a blank cell where a template has never been edited", () => {
    // BR-BIL-036's discipline applied to an edit trail: "nobody has touched
    // this" and "we could not read the trail" must not look identical.
    const html = renderCatalog(aPage());
    expect(html).toContain("Never edited");
  });

  it("BR-SHL-025: a read-only role sees the row's write actions DISABLED with its reason", () => {
    /* ⚠ AMENDED BY CR-199-BRC10 F1. This asserted the title row's
       `+ New variant`, which left the list: the drawing (`01-list.png`) puts no
       page action there, and a variant is made from the template it varies —
       the workspace's `+ New variant`, and every row's `…` → *Duplicate as
       variant* (`CR-199-BRC10` §6 L10). What the case exists for is unchanged:
       a role that may not write sees the write controls PRESENT, DISABLED and
       EXPLAINED — never hidden. */
    const html = renderCatalog(
      aPage({ can_edit: false, cannot_edit_reason: READ_ONLY_REASON }),
      true,
    );
    expect(html).toContain("Duplicate as variant");
    expect(html).toMatch(/data-testid="template-edit-[^"]+"[^>]*disabled|disabled[^>]*data-testid="template-edit-/);
    expect(html).toContain("System Admin only");
  });

  it("OQ-253: the row's variant action says VARIANT — never a new template", () => {
    const html = renderCatalog(aPage());
    expect(html).toContain("Duplicate as variant");
    expect(html).not.toContain("+ New template");
  });
});

describe("CR-007 SET-10 · three refusals, three different sentences", () => {
  it("renders test send, sample PDF and set default all DISABLED, each with its OWN reason", () => {
    /* ⚠ **THE THREE CONTROLS ARE ON TWO MODES NOW, SO THE CASE READS BOTH
       (2026-09-07).** *Send test to me* is in the page head and *Set as
       default* in the preview strip, both reachable the moment the screen
       opens; *Download sample PDF* is the composer's, because it is about the
       document being written. Reading only the mode a control happens to be on
       would let the other two be deleted and stay green, which is precisely
       what BR-SHL-025 is protecting here.

       ⚠ **AND A NON-DEFAULT VARIANT IS SELECTED, DELIBERATELY.** *Set as
       default* is only drawn when the OPEN variant is not the default — that
       is `DEF-NOT-4445`, where the strip's badge was drawn over every variant
       including the ones it was denying. */
    const detail = aDetail({
      variants: [
        ...aDetail().variants,
        {
          id: "v-large",
          name: "Large print",
          category: "default",
          language: "default",
          is_default: false,
          active: true,
          published_version: 1,
          version_count: 1,
        },
      ],
      selected_variant: "v-large",
    });
    const html = renderDetail(detail) + renderEditingDetail(detail);
    // All three controls exist on the page (BR-SHL-025 — never hidden).
    // CR-199-BRC10 F3 — the action bar's word is the drawing's, *Send test*.
    expect(html).toContain("Send test");
    expect(html).toContain("Download sample PDF");
    expect(html).toContain("Set as default");
    // And the three reasons are three DIFFERENT sentences, because the three
    // have three different fixes: a dispatcher, a page renderer, and a ruling.
    // ⚠ CR-048 wave I — THE SENTENCES ARE NO LONGER DRAWN INLINE, so this
    // asserts BOTH halves of the pair the PO asked for: the three or four
    // words a person reads on screen, AND the full sentence still reachable as
    // the control's tooltip. Asserting only the label would let a later lane
    // delete the explanation and stay green, which is the failure this whole
    // change is guarding against (BR-SHL-025: a control that refuses must say
    // why). ⚠ DEF-2479 — `"page writer is billing"` used to be asserted HERE
    // too, requiring a module path's sentence on a utility's screen.
    expect(html).toContain("Default is fixed");
    expect(html).toContain("No sample PDF");
    expect(html).toContain(detail.test_send_label);
    // …and each full sentence rides its control as a title, still three
    // DIFFERENT sentences because the three have three different fixes.
    // On a fragment, not the whole string: static markup escapes `'` to
    // `&#x27;`, so an equality check would fail on an apostrophe rather than on
    // anything this case is about.
    expect(html).toContain(`title="${detail.download_pdf_reason}"`);
    expect(html).toContain("the preview shows the text body");
    expect(html).toContain("no email yet");
    expect(detail.test_send_reason).not.toEqual(detail.download_pdf_reason);
    // The ids never reach the words; they ride the machine field (DEF-335).
    expect(html).toContain('data-br-ref="' + detail.set_default_br_ref + '"');
    expect(html).not.toContain(">OQ-252<");
  });

  it("BR-BIL-026: the save button promises a NEW VERSION, never an overwrite", () => {
    // The save control is the wording form's, so this opens it.
    // CR-199-BRC10 F3 — the drawing's *Save draft*: a draft IS a new version
    // (it is numbered, and the published one keeps going out until Publish),
    // and the status line says so — *Draft v4 · Published v3 goes out now*.
    // No control on the bar says Save, Overwrite or Update.
    const html = renderEditingDetail(aDetail());
    expect(html).toContain("Save draft");
    expect(html).not.toMatch(/>(Save|Overwrite|Update)</);
  });

  it("the preview always announces that it is sample data", () => {
    // A preview that stops saying it is a preview is a preview somebody reads
    // as a real customer's letter.
    const html = renderDetail(aDetail());
    expect(html).toContain("SAMPLE data");
    expect(html).toContain("SAMPLE-ACCOUNT");
  });

  it("CLAUDE.md rule 4: the history shows how many messages use a version AND what that prevents", () => {
    // 3,412 sent receipts is US-NOT-006 TC-5's own figure, and it is why a
    // published version is archived and never deleted.
    //
    // ⚠ **AMENDED BY CR-048 E4.** This case asserted the bare digits `3412`,
    // which is exactly what the cell used to print — a number with nothing
    // beside it saying what it stopped anyone doing. E4's complaint was that
    // *"the rules protecting versions exist and are invisible today"*, so the
    // count is now grouped for reading AND carries its consequence. Both are
    // asserted, because the sentence is the half that was missing and a test
    // that checked only the digits would pass over its removal.
    // CR-048 wave I — the history lives on its own page now.
    const html = renderDetail(aDetail(), false, "history");
    expect(html).toContain("3,412");
    // DEF-NOT-10687: the consequence stays, as a FACT ("never deleted");
    // the WHY that followed it was rationale (B14 rule 33) and is gone.
    expect(html).toContain("never deleted");
    expect(html).not.toContain("it can never be deleted, because");
    expect(html).toContain("Restore");
  });

  it("marks the DEFAULT variant from the server's own flag, never by position", () => {
    const html = renderDetail(aDetail());
    expect(html).toContain("Default");
    // The language note's provenance travels on `data-br-ref`, never in the
    // sentence. It named OQ-254 (*"nothing selects one by it"*) until
    // OQ-CUS-12619 ruled, 2026-09-23, that a message takes the UTILITY's
    // language — flipped, not deleted.
    expect(html).toContain("OQ-CUS-12619");
  });

  it("names the merge fields the class allows, and only those", () => {
    // The palette IS the whitelist: insert-on-click can only ever insert a
    // token the save will accept, because both read this list.
    // CR-199-BRC10 F6 — the palette is the `+ Insert placeholder` picker now.
    const html = renderPlaceholderPicker(aDetail());
    expect(html).toContain("{first_name}");
    expect(html).toContain("{balance}");
    expect(html).not.toContain("{meter_no}");
    // US-NOT-016 — the SHAPE, never this tenant's live field list.
    expect(html).toContain("account.custom.");
  });

  it("the merge-fields panel is TWO COLUMNS — the token AND what it resolves to", () => {
    // PO 2026-08-17, SET-10.corrected: `{{bill.original_total}}` beside
    // `$32.22`. A palette says what you MAY write; this says what will appear.
    //
    // ⚠ **THE PANEL IS A KEY/VALUE LIST RATHER THAN A `<table>` AS OF
    // 2026-09-07, AND THAT IS WHY `"Sample value"` IS GONE FROM THIS CASE.**
    // The design draws the rail's panel as *token · right-aligned value*, which
    // is the shared kit's own `KV_ROW`/`KV_KEY`/`KV_FIGURE` — so the column
    // HEADING went with the table and the two columns did not. What this case
    // exists to pin is unchanged and is asserted more directly below: the token
    // and the value it resolves to are BOTH on the row, and a field with no
    // sample says why instead of showing a blank.
    // CR-199-BRC10 F6 — still the token AND what it resolves to, on one
    // entry of the placeholder picker (`03`: *"{account_no} · e.g. AC-004211"*).
    const html = renderPlaceholderPicker(aDetail());
    const row = /data-testid="merge-field-account"[\s\S]{0,1200}?<\/li>/.exec(html)?.[0] ?? "";
    expect(row, "the account_no row is drawn").not.toBe("");
    expect(row).toContain("{account}");
    expect(row).toContain("SAMPLE-ACCOUNT");
    expect(html).toContain("USD 123.45");
    // And a field with no sample says WHY rather than showing an empty cell.
    expect(html).toContain("BR-TEN-017");
  });

  it("the preview strip names the kind, the sample identity and the default pill", () => {
    // CR-199-BRC10 F7 — the panel is titled *Preview* (`02`), so the strip no
    // longer repeats *Previewing as*; it still names the kind, WHOSE sample
    // data is in the document, and the default marker.
    const html = renderDetail(aDetail());
    expect(html).toContain('data-testid="preview-kind"');
    expect(html).toContain("sample data: Sample Customer");
    expect(html).toContain("Default variant");
  });

  it("'Where it's used' is ONE plain sentence, not a list of ids", () => {
    // ⚠ AMENDED 2026-08-18 (DEF-212, last item). This asserted the payload's
    // raw value, `notices.generate_reminder — dunning stages 1-2
    // (BR-NOT-008)`, which is a Python path and a rule id — the PO asked for
    // ONE PLAIN SENTENCE and the walkthrough recorded that this is what a
    // System Admin actually reads. The behaviour under test is UNCHANGED (the
    // panel still renders one sentence and still cites the rule); what changed
    // is that the leading module path is dropped, so the assertion now pins the
    // sentence rather than the code path. The test would have been wrong to
    // leave: it pinned the defect.
    // CR-199-BRC10 — the sentence is the head's line under the title now
    // (`02`: *"Sent when a bill is issued. · Last edited …"*), not a rail panel.
    const html = renderDetail(aDetail());
    expect(html).toContain('data-testid="head-used-by"');
    expect(html).toContain("Dunning stages 1-2 (BR-NOT-008)");
    expect(html).not.toContain("notices.generate_reminder");
  });

  it("the variant pickers render even at a SINGLE variant", () => {
    // SET-10.corrected showed one tab ("Standard"); CR-199-BRC10 F2 draws the
    // variant as its three choices — Channel · Language · Customers — and they
    // render at one variant too. CR-007's *"each category must have at least
    // one alternative variant"* is a CATALOG-level statement — no variant is
    // invented here to satisfy it.
    const detail = aDetail();
    expect(detail.variants).toHaveLength(1);
    const html = renderDetail(detail);
    expect(html).toContain('data-testid="picker-channel"');
    expect(html).toContain('data-testid="picker-language"');
    expect(html).toContain('data-testid="picker-customers"');
    expect(html).toContain("Past-due reminder");
  });

  it("the history states what it cannot record, rather than leaving a blank column", () => {
    // OQ-255 — the product holds the DATE and neither the author's display
    // name nor a note about what changed. A blank column would read as
    // "nobody edited this", which is a different and false statement.
    // ⚠ DEF-2479 — THIS REQUIRED `OQ-255` TO BE DRAWN IN A TABLE CELL, and the
    // cell it was drawn in measured 645px tall. The FACT is what this case is
    // for and the fact survives; the id moved to the machine field.
    // CR-199-BRC10 F5 — the drawn Saved column (*"Platform default"*): a
    // version nobody is on record for says so in two words, never a blank and
    // never the user id `author_label` holds (B14 rule 31).
    const html = renderDetail(aDetail(), false, "history");
    expect(html).toContain("Platform default");
    expect(html).not.toContain("platform seed");
    expect(html).toContain("OQ-255");   // on data-br-ref, not in the sentence
    expect(html).not.toContain("this module holds a user id");
  });

  it("a class with no merge-field catalogue says so instead of showing an empty palette", () => {
    // "Nobody has defined this class's merge fields" is a DIFFERENT absence
    // from "nobody has written this letter", with a different fix (DEF-163).
    // CR-199-BRC10 F6 — said where the palette is: in the placeholder picker.
    const html = renderPlaceholderPicker(
      aDetail({
        code: "service_outage_notice",
        merge_fields: [],
        catalog_unavailable:
          "CR-007 names 'Planned outage notice' in the SET-09 inventory and no signed " +
          "document writes its merge-variable catalogue or its body. OQ-251.",
      }),
    );
    expect(html).toContain("OQ-251");
    expect(html).toContain("no signed document writes");
  });

  it("BR-SHL-025 on the detail screen too: a read-only role can read and cannot write", () => {
    const html = renderDetail(
      aDetail({ can_edit: false, cannot_edit_reason: READ_ONLY_REASON }),
      true,
    );
    expect(html).toContain("System Admin only");
    // The editor is still drawn — CR-007's *"others read-only + preview"*.
    expect(html).toContain("SAMPLE data");
    expect(html).toContain("disabled");
  });
});

describe("CR-199-BRC10 · the Languages column names a language from its tag (DEF-NOT-10672)", () => {
  it("draws each switched-on language, written or not, in that language's own name", () => {
    // The server serves the BCP-47 tag and whether it is written — never a
    // label, because it keeps no table of language names (B14 rule 35).
    const html = renderCatalog(
      aPage({
        results: [
          aRow({
            body_unavailable: null,
            has_published: true,
            status: "published",
            languages: [
              { code: "en", written: true },
              { code: "es", written: false },
            ],
          }),
        ],
      }),
    );
    expect(html).toContain("template-languages-");
    expect(html).toContain(">English<");
    expect(html).toContain("Español · not written");
    expect(html).not.toContain(">es<");
  });
});
