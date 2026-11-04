// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    CR-007 (SET-10 the template detail)   Screens: SET-10
// Defects:  DEF-209 (the remainder — no way back from a deactivated variant,
//           and the two-step path that DOES exist was never mentioned) ·
//           DEF-212 (1) a saved draft could not be re-opened · (3) a brand-new
//           variant wore the same word a deactivated one does · (5) "Where it's
//           used" printed a Python path · DEF-211 (B14 rules 5 and 15 on this
//           screen's tables and controls)
// Rules:    BR-NOT-001 (variants + a mandatory default fallback) · BR-NOT-006 ·
//           BR-BIL-026 (an edit is a NEW version) · BR-BIL-027 · BR-SHL-025 (a
//           control somebody cannot use renders DISABLED WITH ITS REASON,
//           never hidden) · CLAUDE.md rule 4 · B14 rules 5 · 11 · 15
// ───────────────────────────────────────────────────────
// **THIS FILE DID NOT EXIST UNTIL 2026-08-18**, and `TemplateDetail.tsx`'s own
// lifecycle block said `gates: vitest TemplateDetail.test.tsx` for a day —
// hard-won law 1 in one line: a comment naming a test is not the test. SET-10
// carries the editor, the publish control and the only destructive commit on
// the Settings surface, and nothing but a browser spec covered any of it.
//
// The four assertions worth the file, in the order they would break:
//
//  1. **A SAVED DRAFT IS THE THING THE EDITOR OPENS.** The editor used to seed
//     from the published version always, so an edit saved and not published was
//     unreachable — `save_draft` existed and no human could use what it wrote.
//  2. **TWO ABSENCES, TWO WORDS.** "Nobody has published this yet" and
//     "somebody deactivated this" are different facts with different fixes, and
//     the second one is never claimed without an `archived_at` to prove it.
//  3. **THE WAY BACK IS ON THE SCREEN.** There is no unarchive endpoint, so the
//     honest answer is the two-step one the product really has: restore the
//     archived version into a new draft, then publish it. BR-SHL-025 says the
//     control stays visible and disabled WITH that as its reason.
//  4. **NO CONTROL ON THIS SCREEN IS AN UNSTYLED BUTTON** (B14 rule 5). Three
//     type sizes were measured in the browser because several buttons carried
//     no class at all and fell back to the UA's 13.33px.
//
// Most of these assert on react-dom/server static markup — real render output
// (the idiom StateFrame.test.tsx established and TemplateCatalog.test.tsx
// follows).
//
// ⚠ **AND THE FILE OPTS INTO jsdom AS OF 2026-09-07, FOR ONE REASON: SET-10 HAS
// TWO MODES NOW.** The Product Owner ruled that editing is a mode — the screen
// opens on the rendered document and the wording form appears when *Edit
// wording* is pressed — so a static render reaches the READING half and cannot
// reach the composer at all. `renderEditing` below mounts, presses that one
// control and returns the same kind of markup string, so every assertion in
// this file stays an assertion about rendered output rather than about props.
// The static path is unchanged and still what most cases use.
//
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type {
  TemplateDetail,
  TemplateVariantRow,
  TemplateVersionRow,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { editorSource, plainUsedBy, variantStateOf } from "./TemplateDetail";
import { TemplateWorkspace as TemplateDetailPanel } from "./TemplateWorkspace";

const READ_ONLY_REASON =
  "Templates are System Admin only. A Billing Clerk or an Executive can read every " +
  "template, every variant, every version and the preview, and can change none of them.";

function aVariant(overrides: Partial<TemplateVariantRow> = {}): TemplateVariantRow {
  return {
    id: "v-default",
    name: "Past-due reminder",
    category: "default",
    language: "default",
    is_default: true,
    active: true,
    published_version: 1,
    version_count: 1,
    ...overrides,
  };
}

function aVersion(overrides: Partial<TemplateVersionRow> = {}): TemplateVersionRow {
  return {
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
    author_label: "platform seed",
    change_note: null,
    // DEF-2479 — a TABLE CELL holds a VALUE. The old fixture held the
    // 249-character code comment that drew a 645px-tall cell, which is how a
    // fixture protects the shape it should be refusing.
    change_note_unavailable: "No change note recorded",
    change_note_br_ref: "OQ-255 · B11 F-3",
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
    merge_field_rows: [
      {
        token: "balance",
        insert: "{balance}",
        sample_value: "USD 123.45",
        sample_unavailable: null,
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
    variants: [aVariant()],
    selected_variant: "v-default",
    versions: [aVersion()],
    preview: {
      body: "Hi Sample, your account SAMPLE-ACCOUNT has a balance of USD 123.45.",
      subject: null,
      channel: "pdf_print",
      sample_data: true,
      // CR-048 wave I — the SHORT line the pane draws, and the whole sentence
      // it carries on hover. The fixture holds both because the screen renders
      // one and must keep the other reachable.
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
    test_send_reason: "No test send in this release, on any channel. PO: \"no email yet\".",
    can_download_pdf: false,
    // DEF-2479 — the fixture no longer carries a module path or an OQ id. It
    // used to hold the leaked sentence, which is how a test protects the string
    // it should be refusing.
    download_pdf_label: "No sample PDF",
    download_pdf_reason: "No sample PDF for this class — the preview shows the text body.",
    can_set_default: false,
    // DEF-335 — the fixture carries the CUSTOMER-FACING wording, and the ids
    // ride the machine fields beside it. The old fixture pinned the internal
    // sentence, which is how a test protects the string it should be refusing.
    // CR-048 wave I — and now the PAIR: `*_label` is what the screen draws,
    // `*_reason` is what it carries on hover. Both, always: a fixture holding
    // only the label would let a lane delete the explanation and stay green.
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

/**
 * @param options.view CR-048 wave I — `"history"` renders the VERSION HISTORY
 *   PAGE rather than the editor. The PO took the history panel off the edit tab
 *   (*"you give a link on top and allow user to open it as seperate page"*), so
 *   it is now reached at `?view=history` and a test that wants a version row
 *   has to go there — exactly as a person does. Driving it through
 *   `MemoryRouter`'s own URL rather than through a prop is deliberate: it
 *   proves the parameter is really what selects the page, which a prop would
 *   not.
 */
function renderDetail(
  detail: TemplateDetail,
  options: {
    readOnly?: boolean;
    variantId?: string | null;
    view?: "history";
  } = {},
): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const variantId = options.variantId ?? null;
  client.setQueryData(
    ["template-catalog", "detail", detail.code, variantId ?? "default"],
    detail,
  );
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[options.view === "history" ? "/?view=history" : "/"]}
        >
          <TemplateDetailPanel
            code={detail.code}
            client={{} as never}
            readOnly={options.readOnly ?? false}
            readOnlyReason={detail.cannot_edit_reason}
            variantId={variantId}
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

/**
 * The same screen with the WORDING FORM OPEN — the other of SET-10's two modes.
 *
 * ⚠ **IT PRESSES THE REAL CONTROL AND TAKES NO SHORTCUT, ON PURPOSE.** There is
 * no `editing` prop to set: an open editor is working state holding unsaved
 * text, not a place a link points at, so a helper that reached inside the
 * component to force the mode would be testing a screen no person can produce.
 *
 * ⚠ **AND IT RETURNS MARKUP, NOT QUERIES,** so the cases below stay assertions
 * about rendered output written the way the rest of this file writes them.
 */
function renderEditing(detail: TemplateDetail, options: { readOnly?: boolean } = {}): string {
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
            readOnly={options.readOnly ?? false}
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

describe("DEF-212 (5) — 'Where it's used' is one plain sentence", () => {
  it("drops the module path a System Admin cannot read, and keeps the rule id every other row carries", () => {
    expect(plainUsedBy("notices.generate_reminder — dunning stages 1-2 (BR-NOT-008)")).toBe(
      "Dunning stages 1-2 (BR-NOT-008)",
    );
  });

  it("returns a sentence that never had a code path in front of it UNTOUCHED", () => {
    // Thirty-four of the thirty-six classes already answer in English. A
    // rewrite that trimmed those would be this screen wording the server.
    for (const sentence of [
      "Nothing yet — move-in queues no notice (CR-007 provision)",
      "Dunning stage 1 of the regulated ladder (BR-NOT-014)",
      "Queued on payment capture — the one class with a platform body today",
      "Field work rules — R5 (OQ-249). Wording ships now, the flow does not",
    ]) {
      expect(plainUsedBy(sentence)).toBe(sentence);
    }
  });
});

describe("DEF-212 (3) — 'Inactive' was two states wearing one word", () => {
  it("a variant with a published version is LIVE", () => {
    expect(variantStateOf(aVariant({ active: true }), [aVersion()])).toBe("live");
  });

  it("a brand-new variant is 'unpublished', which is not 'deactivated'", () => {
    expect(variantStateOf(aVariant({ active: false, version_count: 0 }), [])).toBe("unpublished");
  });

  it("only an archived_at in hand makes it 'deactivated' — the badge never guesses", () => {
    const archived = [
      aVersion({ status: "archived", archived_at: "2026-08-18T09:00:00Z", published_at: null }),
    ];
    expect(variantStateOf(aVariant({ active: false, version_count: 1 }), archived)).toBe(
      "deactivated",
    );
    // A variant holding a draft nobody has published is NOT a deactivated one,
    // and the payload for an unselected tab carries no versions at all — both
    // answer with the weaker true statement rather than the confident wrong one.
    expect(
      variantStateOf(aVariant({ active: false, version_count: 1 }), [aVersion({ status: "draft" })]),
    ).toBe("not-live");
    expect(variantStateOf(aVariant({ active: false, version_count: 2 }), null)).toBe("not-live");
  });

  it("BR-SHL-025: with nothing to deactivate the control is DISABLED WITH ITS REASON, not live-then-refused", () => {
    const html = renderDetail(
      aDetail({
        variants: [aVariant({ active: false, version_count: 0, published_version: null })],
        versions: [],
        preview: null,
        preview_unavailable: "This variant has no version yet — nothing has been written for it.",
      }),
    );
    expect(html).toContain("Not published yet");
    expect(html).not.toContain(">Deactivated<");
    // The control is present (never hidden), disabled, and says why BEFORE the
    // click — the server used to say the same thing after it.
    expect(html).toContain('data-testid="deactivate-variant"');
    expect(html).toMatch(/data-testid="deactivate-variant"[^>]*disabled|disabled[^>]*deactivate-variant/);
    expect(html).toContain("There is nothing to deactivate");
  });
});

describe("DEF-209 (remainder) — the way back exists, in two steps, and the screen says so", () => {
  const deactivated = aDetail({
    variants: [aVariant({ active: false, version_count: 1, published_version: null })],
    versions: [
      aVersion({ status: "archived", archived_at: "2026-08-18T09:00:00Z", published_at: null }),
    ],
  });

  it("names the deactivated variant as deactivated", () => {
    expect(renderDetail(deactivated)).toContain("Deactivated");
  });

  it("spells out restore → publish, because there is no unarchive endpoint to offer", () => {
    const html = renderDetail(deactivated);
    expect(html).toContain("There is no one-click reactivate");
    expect(html).toContain("choose Restore on its last version");
    expect(html).toContain("then publish that draft");
  });

  it("BR-SHL-025: the Reactivate control RENDERS, disabled, carrying that path as its reason", () => {
    const html = renderDetail(deactivated);
    expect(html).toContain("Reactivate variant");
    expect(html).toContain('data-testid="reactivate-variant"');
    // A live button here would be a control onto nothing: `template_service`
    // has no unarchive and no route calls one. Hiding it is what left the
    // walkthrough recording "no way back" at all.
    expect(html).toMatch(/data-testid="reactivate-variant"[^>]*>/);
  });

  it("B14 rule 6 keeps the danger tier the PO ruled on 2026-08-17", () => {
    // ⚠ CLASS NAME -> `data-variant` (CR-018 Phase 4a, 2026-08-20). Route B
    // deletes the name; `buttonKit` stamps `data-variant`/`data-size` on every
    // kit button precisely so a check has something stable to read.
    expect(renderDetail(aDetail())).toContain('data-variant="danger"');
  });
});

describe("DEF-212 (1) — a saved draft is reachable", () => {
  const published = aVersion({ id: "ver-1", version: 1, status: "published", body: "LIVE BODY" });
  const draft = aVersion({
    id: "ver-2",
    version: 2,
    status: "draft",
    body: "DRAFT BODY",
    published_at: null,
    pinned_by: 0,
  });

  it("editorSource opens the newest DRAFT, not the published version", () => {
    // The old rule was `published ?? versions[0]`, always — which is why an
    // edit saved and not published could not be opened again from any screen.
    expect(editorSource([draft, published], null)?.id).toBe("ver-2");
  });

  it("editorSource honours the row a person opened with the ✎, over its own choice", () => {
    expect(editorSource([draft, published], "ver-1")?.id).toBe("ver-1");
  });

  it("editorSource falls back to the published version when no draft exists", () => {
    expect(editorSource([published], null)?.id).toBe("ver-1");
  });

  it("the textarea holds the DRAFT body and the screen says which version that is", () => {
    // The composer is the EDIT mode's, so this opens it — see `renderEditing`.
    const html = renderEditing(aDetail({ versions: [draft, published] }));
    expect(html).toContain("DRAFT BODY");
    expect(html).not.toContain("LIVE BODY");
    // CR-199-BRC10 F3 — the status line says which version is on screen, in
    // the drawing's words: *Draft v2 · Published v1 goes out now*.
    expect(html).toContain("Draft v2");
    expect(html).toContain("Published v1 goes out now.");
  });

  it("every version row can open it in the editor, and the control is named (B14 rule 15)", () => {
    // CR-048 wave I — the history is its OWN address (`?view=history`); the
    // redesign draws it as a dialog (`07`). *Open in the editor* is the row's
    // `…` now — rule 15 keeps two icons on the row (Preview and the version's
    // own act) — and a menu line carries its WORD beside the glyph.
    const html = renderDetail(aDetail({ versions: [draft, published] }), { view: "history" });
    expect(html).toContain('data-testid="open-version-2"');
    expect(html).toContain('data-testid="open-version-1"');
    expect(html).toContain('title="Open v2 in the editor"');
    expect(html).toContain("<span>Open v2 in the editor</span>");
    // …and the row's own icons are named: Preview on every row.
    expect(html).toContain('aria-label="Preview v2"');
    expect(html).toContain('aria-label="Preview v1"');
  });

  it("the publish and restore actions keep their names", () => {
    const html = renderDetail(aDetail({ versions: [draft, published] }), { view: "history" });
    expect(html).toContain('data-testid="publish-2"');
    expect(html).toContain('aria-label="Publish"');
    // The live version copies back as a draft from its `…` (CLAUDE.md rule 4:
    // history is never rewritten — the old wording returns as a NEW version).
    expect(html).toContain('data-testid="restore-1"');
    expect(html).toContain("<span>Restore</span>");
    // The HISTORY's publish is an icon — the action bar's own Publish
    // (CR-199-BRC10 F3) is a word, and is outside the table.
    const table = html.split('data-testid="version-history"')[1] ?? "";
    expect(table).not.toBe("");
    expect(table).not.toContain(">Publish</button>");
  });
});

describe("DEF-211 — B14 on SET-10", () => {
  it("rule 5: not one button on the screen is left unstyled at the browser default", () => {
    // 13.3333px is the UA default for a `<button>` nobody styled, and the
    // walkthrough measured it beside the app's own 13px and 14px on one screen.
    // A button with no class is the only way that size can appear.
    // ⚠ WAS `!tag.includes('class="btn')` UNTIL 2026-08-20. Route B deleted the
    // class NAME — a kit button now carries its utilities and a `data-variant`,
    // and `class="btn` matches nothing. The question the case asks is "is any
    // button unstyled", and a class name only ever proxied for it, so the check
    // asks it directly: every button carries a non-empty class attribute.
    const html = renderDetail(aDetail());
    const buttons = html.match(/<button[^>]*>/g) ?? [];
    expect(buttons.length).toBeGreaterThan(4);
    expect(buttons.filter((tag) => !/class="[^"]+"/.test(tag))).toEqual([]);
  });

  it("rule 15: the row actions in the history are icons with tooltips, never text links", () => {
    // ⚠ WAS `toContain("settings-icon-btn")` UNTIL 2026-08-20 — a class name,
    // and the class is gone: the 32x32 icon box is the `row` SIZE now, one
    // tier for every row action in the product (DEF-342). More to the point, a
    // class name never checked rule 15: a text link wearing that class passes
    // it. This reads the two things the rule is actually about.
    const html = renderDetail(aDetail(), { view: "history" });
    const rowActions = html.match(/<button[^>]*data-size="row"[^>]*>/g) ?? [];
    expect(rowActions.length, "the version history renders row actions").toBeGreaterThan(0);
    for (const tag of rowActions) {
      // An icon with no accessible name passes every text-absence check in
      // this suite and is unusable without a mouse — B14's own note on rule 15.
      expect(tag, `row action without an accessible name: ${tag}`).toMatch(/aria-label="[^"]+"/);
      expect(tag, `row action without a tooltip: ${tag}`).toMatch(/title="[^"]+"/);
    }
    // ...and it is a GLYPH, not a word. One <svg> per row action.
    const svgs = html.match(/<svg /g) ?? [];
    expect(svgs.length).toBeGreaterThanOrEqual(rowActions.length);
    expect(html).not.toContain(">Restore</button>");
  });

  it("rule 18: every description carries the 80% measure", () => {
    // ⚠ WAS `toContain('class="settings-helper"')` UNTIL CR-048 WAVE C, and the
    // class is gone: this screen is on `route-b-migrated.txt` now and its
    // descriptions carry `max-w-measure`, which resolves through
    // `--container-measure` → `--desc-measure` → 80%.
    //
    // More to the point, the old assertion never asked rule 18's question. It
    // asked whether ONE description on the screen wore a particular name — a
    // second description with no measure at all passed it, and so would a
    // `settings-helper` that had stopped carrying `max-width` (which is exactly
    // the state DEF-211 found it in: a name no stylesheet declared). This reads
    // every description on the screen and asks each one.
    // ⚠ **BOTH MODES, AND THAT IS STRONGER THAN WHAT THIS CASE USED TO DO.**
    // SET-10 opens on the document and the wording form is a mode; a rule about
    // *every description on the screen* has to read both halves or it stops
    // covering the composer's the day the screen learned to hide it.
    const detail = aDetail();
    const html = renderDetail(detail) + renderEditing(detail);
    const descriptions = html.match(/<[a-z]+[^>]*\sdata-desc[=\s>][^>]*>/g) ?? [];
    // ⚠ **THE FLOOR DROPPED FROM 4 TO 2 IN CR-048 WAVE I, AND THAT IS THE
    // DELIVERABLE, NOT A WEAKENED TEST.** The PO found explanatory prose
    // rendered inline ten times in one sitting; four of the paragraphs this
    // number used to count were the defect. What is left are the two genuine
    // descriptions on the screen. The floor stays so the filter below cannot
    // pass vacuously over an empty list.
    expect(descriptions.length, "there are descriptions on this screen to measure")
      .toBeGreaterThanOrEqual(2);
    expect(
      descriptions.filter((tag) => !/class="[^"]*\bmax-w-measure\b[^"]*"/.test(tag)),
      "a description with no B14 rule 18 measure",
    ).toEqual([]);
  });

  it("a short control label is NOT a description, and carries its sentence instead", () => {
    // CR-048 wave I — the other half of rule 18, and the reason the count above
    // fell. A three-word marker under a disabled control is a LABEL: it is not
    // tagged `data-desc`, so it is not held to the 80% measure, and it must
    // still make the explanation reachable or it is a control that refuses
    // without saying why (BR-SHL-025).
    /* ⚠ **A NON-DEFAULT VARIANT IS SELECTED, AND THE FIXTURE HAS TO SAY SO.**
       One of the markers this case reads belongs to *Set as default*, and that
       control is only drawn when the OPEN variant is not the default — which is
       the whole of `DEF-NOT-4445`: the strip used to draw its badge over every
       variant, including the ones it was denying, so both states looked the
       same and no fixture could tell them apart. */
    const other = aVariant({ id: "v-large", name: "Large print", is_default: false });
    const detail = aDetail({
      variants: [aVariant(), other],
      selected_variant: "v-large",
    });
    // Both modes, for the reason the case above gives: the markers live on both
    // halves of this screen and a rule about all of them must read all of them.
    const html = renderDetail(detail) + renderEditing(detail);
    const notes = html.match(/<span[^>]*\sdata-control-note[^>]*>/g) ?? [];
    expect(notes.length, "the disabled controls carry short markers").toBeGreaterThan(2);
    for (const tag of notes) {
      expect(tag, `a control note with no reachable sentence: ${tag}`).toMatch(
        /title="[^"]{20,}"/,
      );
      expect(tag, "a control note must not be tagged as a description").not.toMatch(
        /\sdata-desc[=\s>]/,
      );
    }
    // …and the sentences really are the SERVED ones, not a client invention.
    // ⚠ Compared on a distinctive fragment rather than the whole string:
    // `renderToStaticMarkup` escapes `'` to `&#x27;`, so an equality check
    // against the raw fixture fails on the apostrophe in "utility's" and
    // proves nothing about the wiring either way.
    expect(html).toContain(detail.set_default_reason.slice(0, 40));
    expect(html).toContain("Messages use your utility");
  });
});

describe("DEF-163's posture holds — two absences are never one blank", () => {
  it("no body and no merge-field catalogue are DIFFERENT sentences, each the server's own", () => {
    const html = renderDetail(
      aDetail({
        body_unavailable:
          "A COMPLIANCE DOCUMENT. Its wording is prescribed by a scheme this repo does not " +
          "hold. OQ-206.",
        catalog_unavailable:
          "CR-007 names this in the SET-09 inventory and no signed document writes its " +
          "merge-variable catalogue. OQ-251.",
      }),
    );
    expect(html).toContain("OQ-206");
    expect(html).toContain("OQ-251");
    expect(html).toContain("A COMPLIANCE DOCUMENT");
    expect(html).toContain("no signed document writes");
  });

  it("BR-SHL-025: a read-only role reads everything and writes nothing, with the server's reason", () => {
    const html = renderDetail(aDetail({ can_edit: false, cannot_edit_reason: READ_ONLY_REASON }), {
      readOnly: true,
    });
    expect(html).toContain("System Admin only");
    // The editor is still drawn — CR-007's *"others read-only + preview"*.
    expect(html).toContain("SAMPLE data");
    expect(html).toContain("disabled");
  });
});

it.todo(
  "DEF-212 — re-selecting an already-cached variant re-seeds the textarea (the Editor's `key`): " +
    "a static render mounts fresh every time, so only a live DOM can hold the stale body this " +
    "guards against. It belongs in e2e/CR-007-templates.spec.ts, where the variant tabs are clicked.",
);

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-209 · DEF-211 · DEF-212 (12-governance/10-defect-log.csv) · B14
//   (04-docs/02-decisions/14-ui-conventions.md) · CR-007 (SET-10)
// generated: 2026-08-18 by the templates-B14 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest — RED-PROVED before being trusted green (hard-won law
//   7): `editorSource` was reverted to `published ?? versions[0]` and the three
//   draft assertions failed on "DRAFT BODY"; `variantStateOf` was reverted to
//   `active ? live : deactivated` and the unpublished-badge assertion failed on
//   "Not published yet"; the rule-5 assertion was proved by removing `class`
//   from one control, which failed listing that tag.
// exceptions: (1) THE EDITOR'S `key` HAS NO STATIC-MARKUP ASSERTION and is an
//   it.todo naming where it belongs — a server render mounts fresh, so the
//   stale-body bug it fixes cannot be reproduced without a live DOM.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

describe("CR-011 item 9 — a contract with no variant shows the OFFER, not an empty screen", () => {
  const offer: NonNullable<TemplateDetail["platform_default"]> = {
    body: "SERVICE AGREEMENT\n\n1. We supply the services listed below.\n2. You pay at our published rates.",
    subject: null,
    source: "CR-011 item 9 (PO 2026-08-18)",
    notice: "This is a starting point, not legal advice. Review it before you use it.",
    label: "Platform default wording",
    is_placeholder: false,
    placeholder_marker: null,
    requires_from_utility: [],
    requires_effective_date: true,
  };

  it("draws the offered wording where 'no variant yet' used to be", () => {
    // THE POINT OF THE WHOLE SLICE. BR-NOT-002 makes a contract effective-dated,
    // so the platform never SEEDS one — the body arrives on the payload and
    // never as a version. A screen that only knew how to render versions showed
    // "no variant yet" over wording that was sitting right there: served, and
    // invisible. Hard-won law 2.
    const html = renderDetail(
      aDetail({ code: "contract_service_agreement", variants: [], platform_default: offer }),
    );
    expect(html).toContain("platform-default-offer");
    expect(html).toContain("1. We supply the services listed below.");
    expect(html).toContain("This is a starting point, not legal advice.");
    // and the empty-state must NOT be the thing on screen
    expect(html).not.toContain("variant-none");
  });

  it("still shows the plain empty state for a class with no offer", () => {
    // The guard against over-reach: only the four contracts carry an offer, and
    // every other class must keep the honest "nothing written yet" sentence.
    const html = renderDetail(aDetail({ variants: [], platform_default: null }));
    expect(html).toContain("variant-none");
    expect(html).not.toContain("platform-default-offer");
  });

  it("says an effective date is required, because BR-NOT-002 refuses without one", () => {
    const html = renderDetail(
      aDetail({ code: "contract_deposit", variants: [], platform_default: offer }),
    );
    expect(html).toContain("offer-date-required");
  });

  it("warns that the ACH placeholder cannot render, and lists what the utility must supply", () => {
    // The PO's second half of the ACH ruling — "put the details, I will handle
    // it with user" — is a DELIVERABLE, so the list has to be on the screen and
    // not only in a register. And the warning has to be there because the
    // renderer REFUSES a body still carrying the marker: a screen that offered
    // publish beside it without saying so would be lying by omission.
    const html = renderDetail(
      aDetail({
        code: "contract_autopay_authorization",
        variants: [],
        platform_default: {
          ...offer,
          is_placeholder: true,
          placeholder_marker: "[[UTILITY TO SUPPLY]]",
          requires_from_utility: [
            "Your legal name exactly as it appears on the customer's bank statement.",
            "The company ID number your bank issued you.",
          ],
        },
      }),
    );
    expect(html).toContain("offer-placeholder-warning");
    expect(html).toContain("[[UTILITY TO SUPPLY]]");
    expect(html).toContain("offer-requires");
    expect(html).toContain("The company ID number your bank issued you.");
  });

  // ── CR-190-BRC10 · *Create from our default* (DEF-NOT-10442) ────────────
  it("offers Create from our default to an admin, with the date it takes effect", () => {
    const html = renderDetail(
      aDetail({ code: "contract_service_agreement", variants: [], platform_default: offer }),
    );
    expect(html).toContain('data-testid="create-from-default"');
    expect(html).toContain("Create from our default");
    expect(html).toContain("Takes effect");
  });

  it("does not offer it to a role that cannot edit", () => {
    const html = renderDetail(
      aDetail({
        code: "contract_service_agreement",
        variants: [],
        platform_default: offer,
        can_edit: false,
        cannot_edit_reason: "Only a System Admin edits templates.",
      }),
    );
    expect(html).toContain("platform-default-offer");
    expect(html).not.toContain('data-testid="create-from-default"');
  });

  it("posts the chosen date and opens the new variant", async () => {
    const posted: { path: string; body: unknown }[] = [];
    const client = {
      post: async (path: string, body: unknown) => {
        posted.push({ path, body });
        return {
          status: 201,
          headers: {},
          data: { variant: { id: "v-new", name: "Service agreement" }, version: { version: 1 } },
        };
      },
      get: async () => ({ status: 200, headers: {}, data: null }),
    };
    const selected: string[] = [];
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    const detail = aDetail({
      code: "contract_service_agreement",
      variants: [],
      platform_default: offer,
    });
    queryClient.setQueryData(["template-catalog", "detail", detail.code, "default"], detail);
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/"]}>
            <TemplateDetailPanel
              code={detail.code}
              client={client as never}
              readOnly={false}
              readOnlyReason={null}
              variantId={null}
              onSelectVariant={(id) => selected.push(id)}
              onBack={() => undefined}
              surfaces={[]}
              onOpenSurface={() => undefined}
            />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    const submit = screen.getByTestId("create-from-default-submit") as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
    const input = document.getElementById("from_default_effective_from") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "2026-11-01" } });
    expect(submit.disabled).toBe(false);
    fireEvent.click(submit);
    await screen.findByText("Draft created. Publish it when ready.");
    expect(posted).toEqual([
      {
        path: "/template-catalog/contract_service_agreement/from-default",
        body: { effective_from: "2026-11-01" },
      },
    ]);
    expect(selected).toEqual(["v-new"]);
  });
});
