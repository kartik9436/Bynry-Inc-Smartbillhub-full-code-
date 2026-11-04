// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave E — E1 (rebuild the designer output-first) · E2 (the
//          editor and preview follow the KIND) · E4 (the version list with pin
//          counts and LOCKED BLOCKS) · E5 (the channel switcher)
// Screens: SET-10 · the ten designers S91–S106
// Rules:   BR-NOT-015 (the regulatory rights footer) · BR-BIL-026 (an edit is a
//          NEW version) · CLAUDE.md hard rule 4 (a published body is evidence
//          of what a customer was sent, so it is never rewritten or deleted) ·
//          BR-SHL-025 (disabled WITH its reason, never hidden) · B14 rule 21
// ───────────────────────────────────────────────────────
// *"On a regulated notice the page is not a preview of the work — it IS the
// work, and the rights footer, the certified-mail number and the tier banner
// can only be checked by looking at it."*
//
// ── WHAT THE PACKET SAID AND WHAT THE TREE ACTUALLY HELD ──────────────────
// CR-048 records E1 as *"the main gap: no preview at all on a screen that
// authors regulated notices"*, traced against the deployed `v2.79.13`. **That
// is not true of this tree, and saying so is not a quibble** — half of E1 is
// already here and building it again would have been the third copy. `HEAD`
// carries a live debounced `PreviewPane` that posts the candidate body to
// `POST …/preview` and renders the engine's own output with its sample-data
// notice, its absences and its unsampled tokens. What is missing is the
// **SHAPE**: every one of those panels is stacked in one column, so the
// rendered document is below the fold under an editor, a merge-field table and
// a history — the opposite of *"a quarter of the screen for the controls,
// three quarters for what the customer will actually hold"*.
//
// So E1 here is the LAYOUT and the ORDER, not a preview from nothing.
//
// ── WHAT JSDOM CANNOT SEE, STATED RATHER THAN FAKED (wave C's rule) ───────
// jsdom performs no layout, so **nothing in this file measures a quarter or
// three quarters of anything.** Asserting "the preview is 75% wide" would be a
// test that cannot fail. What is asserted instead is what a DOM can answer
// honestly: that the rail and the output are SIBLINGS under one frame, that the
// document is inside the output half rather than under the rail, and that the
// frame declares a two-track grid whose tracks are in the ratio the requirement
// names. Whether 1fr:3fr is right on a 1440px screen is a measurement, and the
// only instrument for it is a browser (hard-won law 6).
//
// ── PROVED RED FIRST (hard-won law 7) ─────────────────────────────────────
// Run against the pre-change screen: **13 failed, 2 passed.** One message per
// failing case, quoted:
//   · the rail and the document are two halves → Unable to find an element by:
//       [data-testid="designer-frame"]
//   · the document sits in the output half     → Unable to find an element by:
//       [data-testid="designer-output"]
//   · a printable renders as a PAGE            → Unable to find an element by:
//       [data-testid="preview-page"]
//   · an SMS renders in a phone bubble         → Unable to find an element by:
//       [data-testid="preview-sms-bubble"]
//   · the SMS counter is beside the words      → Unable to find an element by:
//       [data-testid="sms-meter"]
//   · …and states the segment and the cost     → Unable to find an element by:
//       [data-testid="sms-meter"]
//   · an email shows subject AND preheader     → Unable to find an element by:
//       [data-testid="preview-inbox"]
//   · the rights footer is a LOCKED block in the editor
//                                              → Unable to find an element by:
//       [data-testid="locked-block-0"]
//   · …and in the preview                      → Unable to find an element by:
//       [data-testid="preview-locked-0"]
//   · a pinned version says it cannot be deleted
//                                              → Unable to find an element by:
//       [data-testid="version-pinned-1"]
// ⚠ **THE TWO THAT PASSED ARE GUARDS FOR THE OPPOSITE DIRECTION, AND THEY ARE
// LABELLED AS SUCH RATHER THAN COUNTED AS PROOF.** *"a printable version list
// has no effective-from column"* and *"a version nothing points at does NOT
// claim to be protected"* both pass today because NEITHER column exists — they
// pin the negative half of E2 and E4, so a fix that draws the effective date on
// every kind, or a padlock on every version, goes red. Neither is evidence that
// anything was missing; the thirteen above are.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type {
  TemplateDetail,
  TemplatePreview,
  TemplateVersionRow,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateWorkspace as TemplateDetailPanel } from "./TemplateWorkspace";

afterEach(cleanup);

/** BR-NOT-015's rights footer, as `mandatory_content` actually serves it — a
 *  phrase the renderer refuses a body without. Quoted in shape from
 *  `catalogs.py`'s disconnect classes. */
const RIGHTS_FOOTER = "You have the right to dispute this notice";

function aVersion(overrides: Partial<TemplateVersionRow> = {}): TemplateVersionRow {
  return {
    id: "ver-1",
    version: 1,
    status: "published",
    subject: null,
    body: `Hi {first_name}, your balance is {balance}. ${RIGHTS_FOOTER}.`,
    effective_from: null,
    created_by: null,
    published_by: null,
    published_at: "2026-08-16T00:00:00Z",
    archived_at: null,
    updated_at: "2026-08-16T00:00:00Z",
    pinned_by: 3412,
    deletable: false,
    author_label: "platform seed",
    change_note: null,
    change_note_unavailable: "No column records what an edit changed (OQ-255).",
    ...overrides,
  };
}

function aPreview(overrides: Partial<TemplatePreview> = {}): TemplatePreview {
  return {
    body: `Hi Yuki, your balance is $247.87. ${RIGHTS_FOOTER}.`,
    subject: null,
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

function aDetail(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    code: "disconnect_notice_10_day",
    name: "Disconnect notice · 10-day warning",
    category: "collections",
    category_source: "cr_007",
    kind: "Print",
    used_by: "Dunning stage 1 of the regulated ladder",
    group: "printable",
    channel: "pdf_print",
    // CR-076 — the surfaces this class is a form for, SERVED. `"Print"` is
    // one channel, so the designer draws no switcher for it.
    preview_surfaces: ["printable"],
    merge_fields: ["balance", "first_name"],
    merge_field_rows: [
      {
        token: "balance",
        insert: "{balance}",
        sample_value: "$247.87",
        sample_unavailable: null,
        derived_spelling: false,
      },
    ],
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

/** @param view CR-048 wave I — "history" renders the VERSION HISTORY PAGE,
 *  which is where version rows live now that the PO took the panel off the
 *  edit tab.
 *
 *  ⚠ **IT OPENS THE EDITOR BEFORE RETURNING, AND THAT IS THE 2026-09-07 CHANGE
 *  THESE CASES ARE ABOUT.** The Product Owner ruled that editing is a MODE:
 *  SET-10 now opens on the rendered document with a rail beside it, and the
 *  wording form appears when *Edit wording* is pressed. Every case in this file
 *  is about the DESIGNER — the rail, the composer, the SMS meter, the locked
 *  blocks — so the helper presses that control, once, in one place.
 *
 *  It is a real click and not a prop: there IS no prop, deliberately (an open
 *  editor is working state holding unsaved text, not a place a link points at),
 *  and a helper that reached inside the component to set the mode would be
 *  testing a screen no person can produce. */
function renderDetail(detail: TemplateDetail, readOnly = false, view?: "history") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(["template-catalog", "detail", detail.code, "default"], detail);
  const result = render(
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
  // The history PAGE replaces the whole screen, so there is no editor control
  // on it to press.
  if (view !== "history") {
    fireEvent.click(screen.getByTestId("edit-wording"));
  }
  return result;
}

/* ⚠ AMENDED BY CR-199-BRC10 F6/F7. The two halves are the drawing's
   **Wording** and **Preview** panels now (`02`) — wording first, the document
   beside it — and the document keeps the three fifths CR-076 item 2 ruled
   (see `DESIGNER_FRAME`'s note). The rail of merge fields and history the old
   halves were named after is gone into the bar and the picker. */
describe("CR-048 E1 — the designer is two halves of one frame", () => {
  it("the wording and the document are two halves of ONE frame, not a stack", () => {
    renderDetail(aDetail());
    const frame = screen.getByTestId("designer-frame");
    expect(screen.getByTestId("wording-pane").parentElement).toBe(frame);
    expect(screen.getByTestId("preview-pane").parentElement).toBe(frame);
    // …in the drawn order: the wording first, the document beside it.
    expect(frame.firstElementChild).toBe(screen.getByTestId("wording-pane"));
  });

  it("the rendered document is INSIDE the preview half, and the words inside the wording half", () => {
    renderDetail(aDetail());
    expect(screen.getByTestId("preview-pane")).toContainElement(screen.getByTestId("preview-printable"));
    expect(screen.getByTestId("wording-pane")).toContainElement(screen.getByTestId("editor-body"));
  });

  it("the frame gives the document three fifths, and stacks below lg", () => {
    renderDetail(aDetail());
    expect(screen.getByTestId("designer-frame").className).toContain("grid-cols-[2fr_3fr]");
    expect(screen.getByTestId("designer-frame").className).toContain("max-lg:grid-cols-1");
  });
});

describe("CR-048 E2 — the editor and the preview follow the KIND", () => {
  it("a PRINTABLE renders as a page, not as a <pre> on the page background", () => {
    renderDetail(aDetail());
    const page = screen.getByTestId("preview-page");
    expect(page).toHaveTextContent("your balance is $247.87");
  });

  it("an SMS renders in a phone-sized bubble", () => {
    renderDetail(
      aDetail({
        group: "sms",
        channel: "sms",
        preview_surfaces: ["sms"],
        preview: aPreview({ channel: "sms", body: "Your bill is ready.", rendered_length: 19 }),
      }),
    );
    expect(screen.getByTestId("preview-sms-bubble")).toHaveTextContent("Your bill is ready.");
    // …and NOT as a page. One kind, one drawing.
    expect(screen.queryByTestId("preview-page")).toBeNull();
  });

  it("the SMS counter sits BESIDE THE WORDS and states the segments", () => {
    renderDetail(
      aDetail({
        group: "sms",
        channel: "sms",
        preview_surfaces: ["sms"],
        preview: aPreview({ channel: "sms", rendered_length: 150 }),
      }),
    );
    const meter = screen.getByTestId("sms-meter");
    // The requirement's own words: *"the counter and the '4 characters left'
    // warning belong beside the words being typed, not in a validation message
    // after saving."* So the meter is inside the composer, next to the
    // textarea — not down beside the save button where the old counter was.
    // CR-199-BRC10 F6 — inside the Wording pane, under the box (`05`).
    expect(screen.getByTestId("wording-pane")).toContainElement(meter);
    expect(meter).toHaveTextContent("150");
    expect(meter).toHaveTextContent("1"); // one segment at 150 of 160
    expect(meter).toHaveTextContent("10"); // …and ten characters left
  });

  it("⚠ past 160 the meter says TWO segments and what the second one COSTS", () => {
    renderDetail(
      aDetail({
        group: "sms",
        channel: "sms",
        preview_surfaces: ["sms"],
        preview: aPreview({ channel: "sms", rendered_length: 164 }),
      }),
    );
    const meter = screen.getByTestId("sms-meter");
    expect(meter).toHaveTextContent("2");
    // *"Passing 160 characters splits the message into two segments and doubles
    // the per-message cost — on a 2,000-account run that is real money."* The
    // cost is the point of the counter, so it is said in words and not implied
    // by a number turning amber.
    expect(screen.getByTestId("sms-cost-warning")).toBeInTheDocument();
  });

  it("an EMAIL gives the subject its inbox line and the body ONE printing", () => {
    // ⚠ AMENDED FOR `DEF-NOT-4464`. This case used to require the DERIVED
    // PREHEADER — the body's own first line, drawn under the subject and
    // captioned *"first line of the body — this product has no preheader
    // field"* — two lines above the body, which then printed that same
    // sentence again. So the screen showed a clerk the same words twice with
    // our database schema explained in between (B14 rule 32). The Product
    // Owner's words: *"why all this content - there is so much repeat"*.
    // The reasoning behind the derived line was sound and is not reversed: this
    // product still has no preheader column and none is invented here. What
    // changed is that the fallback is no longer DRAWN, because the thing it
    // falls back to is on screen four pixels below it.
    renderDetail(
      aDetail({
        group: "email",
        channel: "email",
        preview_surfaces: ["email"],
        preview: aPreview({
          channel: "email",
          subject: "Your bill is ready",
          body: "Hi Yuki — your September bill is ready to view.",
        }),
      }),
    );
    const inbox = screen.getByTestId("preview-inbox");
    expect(inbox).toHaveTextContent("Your bill is ready");
    expect(screen.queryByTestId("preview-preheader")).toBeNull();
    expect(screen.queryByTestId("preheader-derived")).toBeNull();
    // ⚠ **THE COUNT IS THE ASSERTION, NOT THE PRESENCE.** Both elements were
    // individually correct before; what was wrong was that there were two of
    // them. `preview-preheader` being absent proves nothing on its own — a
    // later change could reintroduce the repeat under another name.
    const printings = (inbox.textContent ?? "").split("Hi Yuki").length - 1;
    expect(printings).toEqual(1);
    // …and it is set as a DOCUMENT, the same renderer a printed notice uses
    // (`DEF-NOT-4465`), not one paragraph carrying the raw string.
    expect(inbox).toContainElement(screen.getByTestId("preview-page"));
  });

  it("an IN-APP notice gets NO letterhead — this one is the product speaking", () => {
    renderDetail(
      aDetail({
        group: "in_app",
        channel: "in_app",
        preview_surfaces: ["in_app"],
        preview: aPreview({ channel: "in_app", body: "Bill run finished: 1,204 bills." }),
      }),
    );
    expect(screen.getByTestId("preview-bell-panel")).toBeInTheDocument();
    // *"No letterhead on this class: every other template is a letter FROM the
    // utility; this one is the product speaking to the operator."*
    expect(screen.queryByTestId("preview-letterhead")).toBeNull();
    expect(screen.queryByTestId("preview-page")).toBeNull();
  });

  it("a CONTRACT gets the effective-from row, and no other kind does", () => {
    renderDetail(
      aDetail({
        group: "contracts",
        channel: "pdf_print",
        versions: [aVersion({ effective_from: "2026-09-01" })],
      }),
      false,
      "history",
    );
    expect(screen.getByTestId("version-effective-1")).toHaveTextContent("2026-09-01");
  });

  it("…and a printable version list has no effective-from column at all", () => {
    renderDetail(aDetail({ versions: [aVersion({ effective_from: null })] }));
    expect(screen.queryByTestId("version-effective-1")).toBeNull();
  });
});

describe("CR-048 E4 — locked blocks, and a version a sent document points at", () => {
  it("the rights footer is a LOCKED BLOCK in the editor, not a rule enforced at save", () => {
    renderDetail(aDetail());
    // *"The regulatory rights footer must be VISIBLE as a locked block in the
    // editor and in the preview, not enforced only on save."* Before E4 it was
    // one sentence in the merge-field panel — "This template may never be saved
    // without: …" — which is a rule stated, not a block shown.
    expect(screen.getByTestId("locked-block-0")).toHaveTextContent(RIGHTS_FOOTER);
  });

  it("…and it is a locked block in the PREVIEW too", () => {
    renderDetail(aDetail());
    expect(screen.getByTestId("preview-pane")).toContainElement(
      screen.getByTestId("preview-locked-0"),
    );
  });

  it("a version 3,412 sent messages point at SAYS it can never be deleted", () => {
    renderDetail(aDetail(), false, "history");
    // CLAUDE.md hard rule 4 — a published body is evidence of what a customer
    // was sent. The rule exists in the database and was invisible on screen:
    // the column showed a bare `3412` with nothing saying what it prevented.
    const pinned = screen.getByTestId("version-pinned-1");
    expect(pinned).toHaveTextContent("3,412");
  });

  it("a version nothing points at does NOT claim to be protected", () => {
    renderDetail(aDetail({ versions: [aVersion({ pinned_by: 0, deletable: true })] }));
    // The protection is a fact about THIS version, not a decoration on the
    // column. A draft nobody has sent is deletable and must not say otherwise.
    expect(screen.queryByTestId("version-pinned-1")).toBeNull();
  });
});
