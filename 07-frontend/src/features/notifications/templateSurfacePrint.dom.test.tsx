// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-076 — three things the PO asked for on SET-10 after using it:
//          (1) a surface switcher over the preview, DERIVED and not hardcoded
//          (*"you are correct - dont use hard coding"*) · (2) the Wording panel
//          takes 60% of the width · (3) a Print control that prints the REAL
//          rendered document (*"you should print real rendered document"*).
// Screens: SET-10 (the template designer)
// Rules:   BR-SHL-010 (an undeclared capability is not rendered) ·
//          BR-SHL-025 (a control that cannot act is disabled WITH its reason) ·
//          B14 rule 21 (Tailwind utilities, per file) · B14 rule 33 (a refusal
//          is five or six words) · B14 rule 36 (compose the shared kit) ·
//          CLAUDE.md hard-won law 2 (a hand-typed list is how the eleventh
//          service silently never reached the sign-up screen)
// ───────────────────────────────────────────────────────
// ── WHAT THESE CASES ARE WRITTEN AGAINST ──────────────────────────────────
// Three defects, one per item, and each is a thing that PASSES every other
// check in this repo:
//
//  1. **A TAB BAR OF FIVE CONSTANTS.** It is the shape the PO first proposed
//     and then ruled out. On `sms_bill_ready` it offers a printed page, an
//     email and a contract that class has no form for, and on the day a sixth
//     surface exists it goes on offering exactly five. `tsc` passes, every
//     `toContain` passes, and the screen is wrong — the sign-up screen's
//     eleventh service, one screen along.
//  2. **A COMMENT THAT STILL DESCRIBES THE OLD SPLIT.** The ratio moves and the
//     paragraph above it keeps saying *a quarter for the controls*, so the next
//     lane reading the kit is told the opposite of what the file does.
//  3. **PRINTING A RE-RENDER OF THE BODY TEXT.** `<pre>${preview.body}</pre>`
//     in a blank window is the snippet this started from, and what comes out of
//     it is a DIFFERENT document from the one on screen: no inbox lines on an
//     email, no page on a letter, no locked rights footer, no sample-data
//     notice. It is the receipt defect's own shape — a preview showing values
//     the real document does not have — pointed the other way.
//
// ── PROVED RED FIRST (hard-won law 7), AND THROUGH THE HARNESS THAT RUNS THEM
// Run against the pre-change screen, with `./node_modules/.bin/vitest run` —
// the command the suite is actually run with, not a hand-rolled one:
// **9 failed, 3 passed.** Every failure is quoted at the bottom of this file,
// and so is each of the three that passed and why none of them is evidence.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { TemplateDetail, TemplatePreview, TemplateVersionRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateWorkspace as TemplateDetailPanel } from "./TemplateWorkspace";
import { DESIGNER_FRAME } from "./notificationsKit";
import { printableDocument } from "./printPreview";

afterEach(cleanup);

const RIGHTS_FOOTER = "You have the right to dispute this notice";

function aVersion(overrides: Partial<TemplateVersionRow> = {}): TemplateVersionRow {
  return {
    id: "ver-1",
    version: 1,
    status: "published",
    subject: "Your service is scheduled for disconnection",
    body: `Hi {first_name}, your balance is {balance}. ${RIGHTS_FOOTER}.`,
    effective_from: null,
    created_by: null,
    published_by: null,
    published_at: "2026-09-07T00:00:00Z",
    archived_at: null,
    updated_at: "2026-09-07T00:00:00Z",
    pinned_by: 0,
    deletable: true,
    author_label: "platform seed",
    change_note: null,
    change_note_unavailable: "No column records what an edit changed.",
    ...overrides,
  };
}

function aPreview(overrides: Partial<TemplatePreview> = {}): TemplatePreview {
  return {
    body: `Hi Yuki, your balance is $247.87. ${RIGHTS_FOOTER}.`,
    subject: "Your service is scheduled for disconnection",
    channel: "pdf_print",
    sample_data: true,
    sample_data_notice: "Preview only — sample data, nothing is sent.",
    sample_data_detail: "Sample data. Nothing here is a real customer.",
    absences: [],
    problems: [],
    unsampled: [],
    rendered_length: 92,
    ...overrides,
  };
}

/** The 10-day disconnect notice — the PO's own example. It is *"Print +
 *  email"*, so the server derives TWO surfaces for it and this screen could
 *  only ever draw one of them. */
function aDetail(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    code: "disconnect_notice_10_day",
    name: "Disconnect notice · 10-day warning",
    category: "collections",
    category_source: "cr_007",
    kind: "Print + email",
    used_by: "Dunning stage 1 of the regulated ladder",
    group: "printable",
    channel: "pdf_print",
    preview_surfaces: ["printable", "email"],
    merge_fields: ["balance", "first_name"],
    merge_field_rows: [],
    sample_identity: { customer_name: "Yuki Nakamura", account_no: "A-11208" },
    derived_spelling: [],
    platform_default: null,
    mandatory_content: [RIGHTS_FOOTER],
    custom_field_variables: [],
    catalog_unavailable: null,
    body_unavailable: null,
    variants: [
      {
        id: "var-1",
        name: "Standard",
        category: "default",
        language: "default",
        is_default: true,
        active: true,
        published_version: 1,
        version_count: 1,
      },
    ],
    selected_variant: "var-1",
    versions: [aVersion()],
    preview: aPreview(),
    preview_unavailable: null,
    sms_character_counter: 160,
    can_edit: true,
    cannot_edit_reason: null,
    can_test_send: false,
    test_send_label: "No delivery channel",
    test_send_reason: "There is no dispatcher on any channel in this release.",
    can_download_pdf: false,
    download_pdf_label: "No sample PDF",
    download_pdf_reason: "The platform's page writer is billing's and it writes bills.",
    can_set_default: false,
    set_default_label: "Default is fixed",
    set_default_reason: "The default variant is the row's KEY, not a flag on it.",
    language_selection_label: "Not chosen automatically",
    language_selection_reason: "Languages come from the tenant's regional settings.",
    set_default_br_ref: "OQ-252",
    language_selection_br_ref: "BR-SHL-041",
    ...overrides,
  };
}

/** ⚠ **IT OPENS THE WORDING FORM BEFORE RETURNING (2026-09-07).** SET-10 opens
 *  on the rendered document now and the composer is a mode behind *Edit
 *  wording* — the Product Owner's ruling on the shape of this screen. Every
 *  case in this file is about the DESIGNER's own halves (the rail, the output
 *  column, the 60/40 split), so the helper presses that control once, here.
 *  The reading view has its own surface tabs and its own Print, and they are
 *  the same components; what these cases pin is the EDIT mode's geometry. */
function renderDetail(detail: TemplateDetail) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(["template-catalog", "detail", detail.code, "default"], detail);
  const result = render(
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
  return result;
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE SURFACE SWITCHER, AND WHERE ITS TABS COME FROM
// ══════════════════════════════════════════════════════════════════════════
describe("CR-076 item 1 — the preview surface switcher is DERIVED", () => {
  it("a notice that is posted AND emailed offers exactly those two", () => {
    renderDetail(aDetail());
    const tabs = screen.getByTestId("wireframe-surface-tabs");
    expect(tabs).toBeInTheDocument();
    expect(screen.getByTestId("wireframe-surface-printable")).toBeInTheDocument();
    expect(screen.getByTestId("wireframe-surface-email")).toBeInTheDocument();
    // ⚠ THE HALF A HARDCODED LIST FAILS. Three surfaces this class has no form
    // for must not be offered, and an empty SMS tab is the whole complaint.
    expect(screen.queryByTestId("wireframe-surface-sms")).toBeNull();
    expect(screen.queryByTestId("wireframe-surface-in_app")).toBeNull();
    expect(screen.queryByTestId("wireframe-surface-contract")).toBeNull();
  });

  it("the tabs are IN the one strip above the paper, not a row of their own", () => {
    // ⚠ AMENDED FOR `DEF-NOT-4456`. This used to assert the tabs were a ROW
    // ABOVE the pane, which they were — one of THREE rows between the variant
    // tabs and the document, which is why the paper's top edge measured 902px
    // in a 900px window. The design draws ONE line, so the picker lives inside
    // the strip and the assertion moves with it.
    renderDetail(aDetail());
    const tabs = screen.getByTestId("wireframe-surface-tabs");
    const strip = screen.getByTestId("preview-strip");
    const paper = screen.getByTestId("preview-page");
    expect(screen.getByTestId("preview-pane")).toContainElement(tabs);
    expect(strip).toContainElement(tabs);
    // DOCUMENT_POSITION_FOLLOWING — the paper comes after the strip, which is
    // "below" in a column. jsdom performs no layout, so ORDER is the honest
    // form of that question; the walkthrough measures the pixels.
    expect(strip.compareDocumentPosition(paper) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("a text message gets NO switcher at all — one tab is a dead control", () => {
    renderDetail(
      aDetail({
        code: "sms_bill_ready",
        name: "Bill ready · SMS",
        kind: "SMS",
        group: "sms",
        channel: "sms",
        preview_surfaces: ["sms"],
        preview: aPreview({ channel: "sms", body: "Your bill is ready.", rendered_length: 19 }),
      }),
    );
    // BR-SHL-010, and the same rule `SurfaceSwitcher` already keeps one control
    // along: a strip with a single tab offers a person nothing to press.
    expect(screen.queryByTestId("wireframe-surface-tabs")).toBeNull();
    expect(screen.getByTestId("preview-sms-bubble")).toBeInTheDocument();
  });

  it("an EMPTY served list falls back to the old screen, not to a blank pane", () => {
    // The server serves `[]` for a `kind` whose channels nobody has stated,
    // rather than guessing. The screen's answer is the drawing it had before
    // this field existed — never five tabs, and never nothing rendered.
    renderDetail(aDetail({ preview_surfaces: [] }));
    expect(screen.queryByTestId("wireframe-surface-tabs")).toBeNull();
    expect(screen.getByTestId("preview-page")).toBeInTheDocument();
  });

  it("pressing Email frames the SAME document as an inbox message", () => {
    // ⚠ AMENDED FOR `DEF-NOT-4465`. It used to assert `preview-page` was GONE
    // after switching to Email, and that was the defect written down as an
    // expectation: an email rendered as one paragraph carrying the raw string
    // while a printed notice got real typography, so "what does the customer
    // receive" looked different depending on which template a clerk opened.
    // The Product Owner's verdict was *"it is not PDF preview it is text only
    // preview"*. Same paper, different FRAME.
    renderDetail(aDetail());
    // It opens on the surface the template's own group names, so nothing moves
    // until somebody asks it to.
    expect(screen.getByTestId("preview-page")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("wireframe-surface-email"));
    const inbox = screen.getByTestId("preview-inbox");
    expect(inbox).toBeInTheDocument();
    expect(inbox).toContainElement(screen.getByTestId("preview-page"));
    expect(screen.getByTestId("wireframe-surface-email")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("wireframe-surface-printable")).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("switching the PREVIEW never touches the wording — there is one body", () => {
    renderDetail(aDetail());
    const before = (screen.getByTestId("editor-body") as HTMLTextAreaElement).value;
    fireEvent.click(screen.getByTestId("wireframe-surface-email"));
    expect((screen.getByTestId("editor-body") as HTMLTextAreaElement).value).toEqual(before);
    // ⚠ A SUBJECT BOX IS NOT SUMMONED BY LOOKING AT THE EMAIL FORM. This class
    // is filed `printable`; the composer follows the class, and a field the
    // save would refuse must not appear because a preview tab was pressed.
    expect(screen.queryByTestId("editor-subject")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE SPLIT
// ══════════════════════════════════════════════════════════════════════════
describe("CR-076 item 2, amended — the DOCUMENT takes 60% of the width", () => {
  it("the frame declares two parts wording to three parts document, NAMING its panes", () => {
    // ⚠ AMENDED BY CR-199-BRC10 F6/F7. The redesign's drawing (`02`) puts the
    // WORDING first and the document beside it, and that arrangement is the
    // drawing's to decide; the 60% the document takes is still the PO's own
    // ruling (*"60 is for A big paper showing real document"*), so the ratio
    // is mirrored with the order: `[2fr_3fr]`, wording then document. This
    // case still NAMES its panes — `DEF-NOT-4457`'s point stands: a ratio check
    // that does not say which pane is which passes on its own mirror image.
    renderDetail(aDetail());
    const frame = screen.getByTestId("designer-frame");
    // Unprefixed: desktop-first, `max-lg:` for the stack (`G107`).
    expect(frame.className).toContain("grid-cols-[2fr_3fr]");
    expect(frame.className).toContain("max-lg:grid-cols-1");
    expect(frame.className).not.toContain("lg:grid-cols-[2fr_3fr]");
    expect(frame.className).not.toContain("minmax(0,1fr)_minmax(0,3fr)");
    // The WORDING is the first (two-fifths) track and the DOCUMENT the second
    // (three-fifths) one.
    expect(frame.firstElementChild).toBe(screen.getByTestId("wording-pane"));
    expect(frame.lastElementChild).toBe(screen.getByTestId("preview-pane"));
  });

  it("the kit constant and the frame cannot drift apart", () => {
    renderDetail(aDetail());
    expect(screen.getByTestId("designer-frame").className).toEqual(DESIGNER_FRAME);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 3 · PRINT — THE REAL RENDERED DOCUMENT
// ══════════════════════════════════════════════════════════════════════════
describe("CR-076 item 3 — Print puts the rendered document on paper", () => {
  it("the control renders, and it is the shared kit's button", () => {
    renderDetail(aDetail());
    const button = screen.getByTestId("print-preview");
    expect(button).toBeInTheDocument();
    expect(button.tagName).toEqual("BUTTON");
    // B14 rule 36 — the kit's own class vocabulary, never a hand-rolled button.
    expect(button.className).toContain("btn");
  });

  it("with nothing rendered it is DISABLED WITH ITS REASON, not hidden", () => {
    renderDetail(aDetail({ preview: null, preview_unavailable: null }));
    const button = screen.getByTestId("print-preview");
    expect(button).toBeDisabled();
    const reason = button.getAttribute("title") ?? "";
    expect(reason).not.toEqual("");
    // B14 rule 33 — a refusal is five or six words.
    expect(reason.split(/\s+/).filter(Boolean).length).toBeLessThanOrEqual(6);
  });

  it("what goes on paper is THE NODE ON SCREEN, not a re-render of the body", () => {
    renderDetail(aDetail());
    fireEvent.click(screen.getByTestId("wireframe-surface-email"));
    const pane = screen.getByTestId("preview-printable");
    const sheet = document.implementation.createHTMLDocument("");
    printableDocument({ into: sheet, node: pane, title: "Disconnect notice", styleSource: document });

    // The EMAIL drawing travels — the inbox lines, the subject, the derived
    // preheader. A `<pre>` of `preview.body` would carry none of it, and that
    // is precisely the difference between printing the document and printing
    // the text it happens to contain.
    expect(sheet.querySelector('[data-testid="preview-inbox"]')).not.toBeNull();
    expect(sheet.querySelector('[data-testid="preview-subject"]')).not.toBeNull();
    // …so does the thing a preview must never stop saying about itself. It
    // reads *"Nothing here is sent"* since `DEF-NOT-4456`: the strip above the
    // paper already says *"Previewing as …"*, and saying *preview* twice in one
    // screen is what the Product Owner counted. The CLAIM travels; only its
    // wording moved, and it is the CONSEQUENCE that a printed page needs.
    expect(sheet.body.textContent).toContain("Nothing here is sent");
    // ⚠ AND IT IS NOT THE STRIP THAT TRAVELS. The strip holds live controls —
    // the surface picker, Print — and it stays OUTSIDE the scroll box so the
    // caption line stays put while the letter scrolls, which also keeps the
    // chrome off the paper.
    expect(sheet.querySelector('[data-testid="preview-strip"]')).toBeNull();
    // …and the locked rights footer, which is the whole reason a person looks
    // at a regulated notice on paper (BR-NOT-015).
    expect(sheet.body.textContent).toContain(RIGHTS_FOOTER);
    expect(sheet.title).toEqual("Disconnect notice");
  });

  it("a ROOT-RELATIVE stylesheet is made absolute, or it never loads at all", () => {
    // ⚠ **DEF-NOT-4414, AND IT WAS FOUND IN A BROWSER AND BY NOTHING ELSE.**
    // The built page links its CSS as `/assets/index-<hash>.css`. The print
    // window opens at `about:blank`, which has no base to resolve that against,
    // so the sheet is never requested and what comes out is the right DOM with
    // no styles on it — the whole notice as one wall of serif text, no page, no
    // inbox chrome, no preserved line breaks.
    //
    // jsdom loads no stylesheets, so the case ABOVE — the node travelled —
    // passed over exactly that printout and always would. This one asks the
    // only question a DOM can answer about it: is the href still resolvable
    // once it leaves this document.
    const link = document.createElement("link");
    link.setAttribute("rel", "stylesheet");
    link.setAttribute("href", "/assets/index-abc123.css");
    document.head.appendChild(link);
    try {
      renderDetail(aDetail());
      const sheet = document.implementation.createHTMLDocument("");
      printableDocument({
        into: sheet,
        node: screen.getByTestId("preview-printable"),
        title: "Disconnect notice",
        styleSource: document,
      });
      const copied = sheet.querySelector('link[href$="/assets/index-abc123.css"]');
      expect(copied).not.toBeNull();
      expect(copied?.getAttribute("href")).toEqual(
        new URL("/assets/index-abc123.css", document.baseURI).href,
      );
      expect(copied?.getAttribute("href")?.startsWith("/")).toBe(false);
    } finally {
      link.remove();
    }
  });

  it("it carries the page's own styles, or it is not the same document", () => {
    const style = document.createElement("style");
    style.textContent = ".paper { padding: 4rem }";
    document.head.appendChild(style);
    try {
      renderDetail(aDetail());
      const sheet = document.implementation.createHTMLDocument("");
      printableDocument({
        into: sheet,
        node: screen.getByTestId("preview-printable"),
        title: "Disconnect notice",
        styleSource: document,
      });
      expect(sheet.head.textContent).toContain(".paper { padding: 4rem }");
    } finally {
      style.remove();
    }
  });
});

// ── The RED proof, quoted (hard-won law 7) ────────────────────────────────
// `./node_modules/.bin/vitest run src/features/notifications/templateSurfacePrint`
// against the pre-change screen.
//
// ⚠ **THE FIRST RUN PROVED NOTHING AND IS RECORDED ANYWAY.** It reported
// `1 failed (1) · no tests` on `Failed to resolve import "./printPreview"` —
// the module did not exist yet, so the SUITE never collected and not one case
// ran. A file that cannot be collected is red for a reason that says nothing
// about the screen, and counting it would have been a red proof of the wrong
// thing. `printPreview.ts` was written first; the run below is the real one.
//
// One message per failing case, from that run:
//   · a notice posted AND emailed offers those two → Unable to find an element
//       by: [data-testid="wireframe-surface-tabs"]
//   · the tabs sit above the preview             → same
//   · pressing Email redraws as an inbox         → Unable to find an element
//       by: [data-testid="wireframe-surface-email"]
//   · switching never touches the wording        → same
//   · the frame declares 3fr to 2fr              → expected
//       "grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)]
//        lg:items-start" to contain "lg:grid-cols-[3fr_2fr]"
//   · the kit constant cannot drift              → passed, and is labelled
//       below rather than counted
//   · Print renders and is the kit's button      → Unable to find an element
//       by: [data-testid="print-preview"]
//   · Print is disabled with its reason          → same
//   · what goes on paper is the node on screen   → Unable to find an element
//       by: [data-testid="wireframe-surface-email"]
//   · it carries the page's own styles           → Unable to find an element
//       by: [data-testid="preview-printable"]
// ⚠ **THREE CASES THAT DID NOT FAIL, LABELLED RATHER THAN COUNTED AS PROOF.**
// *"a text message gets NO switcher"* and *"an EMPTY served list falls back to
// the old screen"* both pass on the pre-change screen, because a screen with no
// switcher at all satisfies "no switcher is drawn" trivially. They are the
// NEGATIVE half — they go red the moment somebody offers five constant tabs, or
// draws a strip of one — and that is the failure they exist for. The third,
// *"the kit constant and the frame cannot drift apart"*, compares the rendered
// class string with the constant it comes from and is true of ANY value of it;
// it catches a later lane writing the ratio into the markup by hand, not this
// change. The nine above are the evidence that anything was missing.
//
// ⚠ **AND A TENTH CASE ARRIVED AFTER ALL OF THEM, WITH ITS OWN RED PROOF ON A
// BUG THAT HAD ALREADY SHIPPED.** *"a ROOT-RELATIVE stylesheet is made absolute"*
// was written for `DEF-NOT-4414`, found in Chromium after the first nine were
// green and pushed. Proved red against the shipped code by putting the relative
// href back: `expected '/assets/index-abc123.css' to deeply equal
// 'http://localhost:3000/assets/index-abc123.css'`. **It is the one case here
// written against a defect this lane had already published**, which is why it
// is listed apart rather than folded into the nine.
