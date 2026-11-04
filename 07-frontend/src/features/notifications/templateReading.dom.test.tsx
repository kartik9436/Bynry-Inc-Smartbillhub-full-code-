// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-076 addendum — the Product Owner compared the running SET-10 with
//          the design and asked for a different SHAPE: the rendered document
//          with a narrow rail, and the wording form behind *Edit wording*.
// Screens: SET-10 (Settings → Configure → Templates → one template)
// Defects: DEF-NOT-4445 (the preview strip's Default variant badge was drawn
//          over every variant, including the ones it was denying) ·
//          DEF-NOT-4444 (a raw message key in the variant badge)
// Rules:   B14 rule 31 (no database id is ever a visible value) · rule 36 (the
//          shared kit) · BR-SHL-020 / BR-SHL-025 (an absent fact is NAMED and a
//          dead control carries its reason) · BR-NOT-001 (the default variant)
// ───────────────────────────────────────────────────────
//
// THE SCREEN A PERSON LANDS ON.
//
// ⚠ **EVERY CASE HERE IS ABOUT THE DEFAULT VIEW, WHICH IS WHY THE FILE EXISTS
// SEPARATELY.** `templateDesigner.dom.test.tsx` and `templateSurfacePrint.dom
// .test.tsx` both press *Edit wording* in their own helpers, because their
// subject is the composer. Nothing pressed anything before this file, and the
// half of the screen a person actually opens had no suite of its own.
//
// ⚠ **WHAT IT CANNOT ANSWER, SAID PLAINLY (hard-won law 6).** jsdom performs no
// layout, so no case below measures a column, a height or a right edge. Whether
// the document reads as paper at 1440px is a browser question and is answered
// by the walkthrough, not here. What jsdom CAN answer is *which facts are on
// the screen and which are named as absent*, and that is the whole of this file.
//
// RED-PROVED BEFORE TRUSTED GREEN, in `vitest run` (DEF-GOV-3733):
//   · the strip was reverted to `variants.find((v) => v.is_default)` and "the
//     badge names the OPEN variant" failed with the pill drawn over a variant
//     that is not the default — DEF-NOT-4445 reproduced exactly;
//   · `VARIANT_STATE_KEY` was reverted to the interpolated key and "no raw
//     message key reaches the screen" failed on
//     `templates.detail.state.not-live` — DEF-NOT-4444 reproduced exactly;
//   · `HeadMeta`'s author line was replaced with `newest.author_label` and "the
//     author is NAMED as absent, never printed as an id" failed, printing the
//     uuid.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { TemplateDetail, TemplateVariantRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateWorkspace as TemplateDetailPanel } from "./TemplateWorkspace";

afterEach(cleanup);

/** A real account id, because that is what the server sends and what B14 rule
 *  31 forbids drawing. */
const AUTHOR_ID = "8f14e45f-ea28-4c1a-9b3d-000000000042";

function aVariant(overrides: Partial<TemplateVariantRow> = {}): TemplateVariantRow {
  return {
    id: "v-default",
    name: "Standard",
    category: "default",
    language: "default",
    is_default: true,
    active: true,
    published_version: 1,
    version_count: 1,
    ...overrides,
  };
}

function aDetail(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    code: "print_bill",
    name: "Bill · standard",
    category: "billing",
    category_source: "cr_007",
    kind: "Print + email",
    used_by: "Every bill run on every cycle",
    group: "printable",
    channel: "print",
    preview_surfaces: ["printable"],
    merge_fields: ["account_no", "total_due", "utility_name"],
    merge_field_rows: [
      {
        token: "account_no",
        insert: "{account_no}",
        sample_value: "SAMPLE-ACCOUNT",
        sample_unavailable: null,
        derived_spelling: false,
      },
      {
        token: "total_due",
        insert: "{total_due}",
        sample_value: "$123.45",
        sample_unavailable: null,
        derived_spelling: false,
      },
      {
        token: "utility_name",
        insert: "{utility_name}",
        sample_value: null,
        sample_unavailable: "From Settings → Company",
        derived_spelling: false,
      },
    ],
    sample_identity: { customer_name: "Sample Customer", account_no: "SAMPLE-ACCOUNT" },
    derived_spelling: [],
    platform_default: null,
    mandatory_content: [],
    custom_field_variables: ["{{account.custom.<key>}}"],
    catalog_unavailable: null,
    body_unavailable: null,
    variants: [aVariant()],
    selected_variant: "v-default",
    versions: [
      {
        id: "ver-2",
        version: 2,
        status: "published",
        subject: null,
        body: "Riverbend Water\n\nAmount due {total_due}",
        effective_from: null,
        created_by: AUTHOR_ID,
        published_by: AUTHOR_ID,
        published_at: "2026-07-12T09:00:00Z",
        archived_at: null,
        updated_at: "2026-07-12T09:00:00Z",
        pinned_by: 0,
        deletable: true,
        author_label: AUTHOR_ID,
        change_note: null,
        change_note_unavailable: "Not recorded",
        change_note_br_ref: "OQ-255",
        changed_fields: ["body"],
        changed_from_version: 1,
      },
    ],
    preview: {
      body: "Riverbend Water\n\nAmount due $123.45\nThank you for your custom.",
      subject: null,
      channel: "print",
      sample_data: true,
      sample_data_notice: "Preview only — sample data, nothing is sent.",
      sample_data_detail: "Rendered from SAMPLE data — nothing on this page is real.",
      absences: [],
      problems: [],
      unsampled: [],
      rendered_length: 60,
    },
    preview_unavailable: null,
    sms_character_counter: 160,
    can_edit: true,
    cannot_edit_reason: null,
    can_test_send: true,
    test_send_reason: "The test goes to your own address and nothing leaves the building.",
    can_download_pdf: false,
    download_pdf_label: "No sample PDF",
    download_pdf_reason: "The preview shows the text body; there is no page to hand over yet.",
    can_set_default: false,
    set_default_reason: "You cannot change which variant is the fallback in this release.",
    language_selection_reason: "Nothing selects a variant by language yet.",
    set_default_label: "Default is fixed",
    language_selection_label: "One language",
    test_send_label: "Goes to you",
    set_default_br_ref: "OQ-252",
    language_selection_br_ref: "OQ-254",
    ...overrides,
  };
}

function renderReading(detail: TemplateDetail, variantId: string | null = null) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(
    ["template-catalog", "detail", detail.code, variantId ?? "default"],
    detail,
  );
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/"]}>
          <TemplateDetailPanel
            code={detail.code}
            client={{} as never}
            readOnly={false}
            readOnlyReason={detail.cannot_edit_reason}
            variantId={variantId}
            onSelectVariant={() => undefined}
            onBack={() => undefined}
            surfaces={[]}
            onOpenSurface={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/* ⚠ AMENDED BY CR-199-BRC10 F6/F7. CR-076's reading view — the document with
   a narrow rail of merge fields, *Where it's used* and a history summary, and
   NO wording on screen until *Edit wording* — is redrawn by the redesign
   (`02-workspace-email-view.png`): the screen opens VIEWING, which shows the
   wording and the preview SIDE BY SIDE, the wording greyed and read-only. The
   rail's three panels each went somewhere the drawing puts them (`CR-199-BRC10`
   §6 W11–W13): the merge fields into `+ Insert placeholder`, *Where it's used*
   into the head line, the history behind *History*. These cases assert that
   shape, and that nothing the rail held was lost. */
describe("the screen opens VIEWING: the wording beside the document, not editable", () => {
  it("draws the document and the wording side by side, and the wording cannot be typed into", () => {
    renderReading(aDetail());
    const frame = screen.getByTestId("designer-frame");
    expect(frame).toContainElement(screen.getByTestId("preview-page"));
    expect(frame).toContainElement(screen.getByTestId("wording-pane"));
    expect(screen.getByTestId("editor-body")).toHaveAttribute("readonly");
    expect(screen.getByTestId("workspace-mode")).toHaveTextContent("Viewing");
  });

  it("the document is NOT inside the wording pane — two halves, not a stack", () => {
    renderReading(aDetail());
    const wording = screen.getByTestId("wording-pane");
    expect(wording).not.toContainElement(screen.getByTestId("preview-page"));
    expect(screen.getByTestId("preview-pane")).toContainElement(screen.getByTestId("preview-page"));
    // What the rail held is still on the screen: where it is used (the head),
    // and the history (one press away).
    expect(screen.getByTestId("head-used-by")).toHaveTextContent("Every bill run");
    expect(screen.getByTestId("history-link")).toBeEnabled();
  });

  it("a merge field shows the value it will resolve to, and an absence says why", () => {
    renderReading(aDetail());
    fireEvent.click(screen.getByTestId("edit-wording"));
    fireEvent.click(screen.getByTestId("insert-placeholder"));
    expect(screen.getByTestId("merge-field-total_due")).toHaveTextContent("$123.45");
    // The five BR-TEN-017 identity tokens are stamped from Settings → Company
    // at render; a made-up value here would hide an unfilled profile.
    expect(screen.getByTestId("merge-absent-utility_name")).toHaveTextContent("Settings");
  });

  it("nothing in the rail is clickable when there is nothing to insert into", () => {
    // Insert-on-click writes into a textarea, and in this mode there is none. A
    // row that LOOKED clickable and did nothing is the dead control this repo
    // has a hard-won law about.
    renderReading(aDetail());
    expect(screen.queryByTestId("insert-total_due")).toBeNull();
  });
});

describe("the page head says what the design's head says", () => {
  it("carries the template's own group, its name and its surfaces", () => {
    renderReading(aDetail());
    // ⚠ **LEVEL 2, AND THE LEVEL IS THE ASSERTION.** This header is drawn inside
    // the Settings page, which has already written "Settings" as the document's
    // `h1`; two `h1`s is two page titles in one outline. `PageHeader.titleAs`
    // is what makes that expressible, and pinning the level here is what stops
    // a later lane "restoring" the h1 and putting the defect back.
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Bill · standard");
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(screen.getByTestId("head-kind")).toHaveTextContent("Print + email");
    expect(screen.getByTestId("head-used-by")).toHaveTextContent("Every bill run");
  });

  it("says when the wording last moved, from the version the server sent", () => {
    renderReading(aDetail());
    expect(screen.getByTestId("head-edited")).toHaveTextContent("2026-07-12");
  });

  it("the AUTHOR is named as absent, never printed as an id (B14 rule 31)", () => {
    // The design's *"Alex Reed"* has no field behind it: `author_label` is a
    // UUIDField and its own docstring says *"the id, or the platform, never a
    // name"* (OQ-255). Naming the absence is BR-SHL-020; printing the uuid
    // would be rule 31 in the PO's own words.
    renderReading(aDetail());
    expect(screen.getByTestId("head-author-absent")).toBeInTheDocument();
    expect(document.body.textContent ?? "").not.toContain(AUTHOR_ID);
  });

  it("offers the three actions the design puts on the right", () => {
    renderReading(aDetail());
    expect(screen.getByTestId("edit-wording")).toBeEnabled();
    // ⚠ IT IS IN THE HEAD AND REACHABLE WITHOUT OPENING THE EDITOR, which is
    // the change: it acts on the TEMPLATE, not on the words in a textarea.
    expect(screen.getByTestId("test-send")).toBeEnabled();
    expect(screen.getByTestId("duplicate-variant")).toBeEnabled();
  });
});

describe("the preview strip, and the badge that used to be always true", () => {
  it("names the surface and whose sample data is in the document", () => {
    renderReading(aDetail());
    const strip = screen.getByTestId("preview-strip");
    expect(strip).toHaveTextContent("Sample Customer");
    expect(strip).toHaveTextContent("SAMPLE-ACCOUNT");
  });

  it("DEF-NOT-4445: the badge names the OPEN variant, not the template's default", () => {
    const detail = aDetail({
      variants: [aVariant(), aVariant({ id: "v-large", name: "Large print", is_default: false })],
      selected_variant: "v-large",
    });
    renderReading(detail, "v-large");
    // The template HAS a default variant — BR-NOT-001 makes that mandatory —
    // and the open one is not it, so the strip must offer the action instead of
    // the pill. The old condition drew the pill here.
    expect(screen.queryByTestId("preview-default-pill")).toBeNull();
    const action = screen.getByTestId("set-default");
    // BR-SHL-025: rendered, DISABLED, carrying the server's own reason.
    expect(action).toBeDisabled();
    expect(action.getAttribute("title")).toContain("cannot change which variant");
    // DEF-335 — the rule id rides the machine field and is never in the words.
    expect(screen.getByTestId("set-default-reason").getAttribute("data-br-ref")).toBe("OQ-252");
    expect(screen.getByTestId("set-default-reason").textContent).not.toContain("OQ-252");
  });

  it("…and it IS the pill when the open variant really is the default", () => {
    renderReading(aDetail(), "v-default");
    expect(screen.getByTestId("preview-default-pill")).toBeInTheDocument();
    expect(screen.queryByTestId("set-default")).toBeNull();
  });
});

describe("DEF-NOT-4444 — no raw message key reaches the screen", () => {
  it("a variant with wording nobody published says so in words", () => {
    // `variantStateOf` calls this state `not-live`; all eleven catalogues spell
    // the key `notLive`. With the key built by interpolation the badge rendered
    // the literal `templates.detail.state.not-live`.
    renderReading(
      aDetail({
        variants: [aVariant({ active: false, published_version: null, version_count: 2 })],
      }),
    );
    const badge = screen.getByTestId("workspace-variant-state");
    expect(badge).toHaveTextContent("Not live");
    expect(document.body.textContent ?? "").not.toContain("templates.detail.state");
  });
});

/* ⚠ AMENDED BY CR-199-BRC10 F5 — the rail's history summary is the drawn
   History dialog (`07`), one press of the bar's *History*. */
describe("the history a person opens from the bar", () => {
  it("gives each entry the date and what moved, and names the author's absence", () => {
    renderReading(aDetail());
    fireEvent.click(screen.getByTestId("history-link"));
    expect(screen.getByTestId("version-trail-2")).toHaveTextContent("2026-07-12");
    // WHICH wording moved is recorded (CR-049 task 8); WHO is not, and the
    // Saved cell says so in two words rather than printing an id (rule 31).
    expect(screen.getByTestId("version-2")).toHaveTextContent("Letter");
    expect(screen.getByTestId("version-trail-2")).toHaveTextContent("Platform default");
    expect(document.body.textContent ?? "").not.toContain(AUTHOR_ID);
  });

  it("an empty history is a fact and says so", () => {
    renderReading(aDetail({ versions: [] }));
    fireEvent.click(screen.getByTestId("history-link"));
    expect(screen.getByTestId("version-empty")).toBeInTheDocument();
    expect(screen.getByTestId("head-never-edited")).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-076 addendum (the PO's two SET-10 screenshots, transcribed into the
//         lane brief) · B14 rules 21 · 31 · 32 · 36
// generated: 2026-09-07 by the SET-10 designer lane
// gates: vitest — three RED proofs, each named in the header with the case it
//         failed · the browser walkthrough is what answers the layout half
// exceptions: no case measures geometry — jsdom performs no layout, and saying
//         so is the point (hard-won law 6)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
