// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-049 task 8 — "Note a template or item change as a change: the
//          audit trail on the wording itself."
// Screens: SET-10 · the version history page (`?view=history`)
// Rules:   BR-NOT-027 part 3 (a change to a template is NOTED AS A CHANGE) ·
//          BR-NOT-028 (PROPOSED — derived, never stored twice) · BR-BIL-026 ·
//          B14 rule 21 (`TemplateDetail.tsx` is on route-b-migrated.txt) ·
//          the PO's ruling of 2026-08-30 — a table cell holds a VALUE and the
//          sentence explaining it goes in a tooltip or the opened detail ·
//          CLAUDE.md hard-won law 2 (built is not wired)
// ───────────────────────────────────────────────────────
// ── WHY THIS FILE MOUNTS THE REAL SCREEN ──────────────────────────────────
// Earlier on this same feature, a panel that was BUILT and never MOUNTED still
// passed 7 of 9 frontend cases; only the cases that render the real screen and
// click went red. So every case here goes through `TemplateDetailPanel` and the
// history page a person actually opens, not through the two exported pieces
// directly.
//
// ── PROVED RED FIRST (hard-won law 7) ─────────────────────────────────────
// Run against the pre-change screen (the "Changed" cell reverted to the empty
// `<td>` it was, the file restored byte-identical afterwards): **7 failed, 0
// passed.** Verbatim, one message per case:
//   · the fields that moved, as a VALUE         → Unable to find an element by:
//       [data-testid="version-changed-2"]
//   · the FIRST version says so rather than blank
//                                               → Unable to find an element by:
//       [data-testid="version-changed-1"]
//   · a backend that does not answer says so    → Unable to find an element by:
//       [data-testid="version-changed-2"]
//   · clicking it loads the change record       → Unable to find an element by:
//       [data-testid="version-changed-2"]
//   · which sent letters carry the old wording  → Unable to find an element by:
//       [data-testid="version-changed-2"]
//   · a version nothing was sent on says so     → Unable to find an element by:
//       [data-testid="version-changed-2"]
//   · clicking again closes it                  → Unable to find an element by:
//       [data-testid="version-changed-2"]
//
// ── WHAT JSDOM CANNOT SEE, STATED RATHER THAN FAKED ───────────────────────
// jsdom performs no layout, so nothing here can prove the "Changed" cell is one
// line tall rather than the 645px paragraph DEF-2479 was about. What it CAN
// answer honestly is that the cell's text is a short value and the sentence is
// on `title` — asserted both ways round, because a check that only looks for
// the value would pass on a cell that also printed the paragraph.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

// ⚠ `ApiClient` COMES FROM `@/api/client`, NOT FROM `@/api/endpoints` (DEF-2464).
// `endpoints.ts` IMPORTS the type for its own signatures and does not re-export
// it, so `import type { ApiClient } from "@/api/endpoints"` compiles under
// `vitest` and under this repo's `tsc` invocation for src/, and FAILS the
// production build's `tsc --noEmit && vite build` with TS2459. Every other test
// in this folder takes it from `@/api/client`; this one had drifted.
import type { ApiClient } from "@/api/client";
import type {
  TemplateChangeRecord,
  TemplateDetail,
  TemplateVersionRow,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateWorkspace as TemplateDetailPanel } from "./TemplateWorkspace";

afterEach(cleanup);

const RIGHTS_FOOTER = "You have the right to dispute this notice";

function aVersion(overrides: Partial<TemplateVersionRow> = {}): TemplateVersionRow {
  return {
    id: "ver-1",
    version: 1,
    status: "archived",
    subject: null,
    body: `Hi {first_name}, your balance is {balance}. ${RIGHTS_FOOTER}.`,
    effective_from: null,
    created_by: null,
    published_by: null,
    published_at: "2026-08-16T00:00:00Z",
    archived_at: "2026-08-30T00:00:00Z",
    updated_at: "2026-08-16T00:00:00Z",
    pinned_by: 3412,
    deletable: false,
    author_label: "platform seed",
    change_note: null,
    change_note_unavailable: "No change note recorded",
    changed_fields: ["body"],
    changed_from_version: null,
    ...overrides,
  };
}

function aDetail(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    code: "disconnect_notice_48_hour",
    name: "Disconnect notice · 48-hour certified",
    category: "collections",
    category_source: "cr_007",
    kind: "Print",
    used_by: "The final tier of the regulated ladder",
    group: "printable",
    channel: "pdf_print",
    // CR-076 — the surfaces this class is a form for, SERVED. `"Print"` is
    // one channel, so the designer draws no switcher for it.
    preview_surfaces: ["printable"],
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
        published_version: 2,
        version_count: 2,
      },
    ],
    selected_variant: "var-1",
    versions: [
      aVersion({
        id: "ver-2",
        version: 2,
        status: "published",
        pinned_by: 0,
        deletable: false,
        changed_fields: ["body"],
        changed_from_version: 1,
      }),
      aVersion(),
    ],
    preview: null,
    preview_unavailable: "No preview in this fixture.",
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

function aChangeRecord(overrides: Partial<TemplateChangeRecord> = {}): TemplateChangeRecord {
  return {
    code: "disconnect_notice_48_hour",
    version: 2,
    version_id: "ver-2",
    previous_version: 1,
    is_first_version: false,
    changed_at: "2026-08-30T10:00:00Z",
    author_label: "platform seed",
    changed_fields: ["body"],
    fields: [
      { field: "body", lines_added: 2, lines_removed: 0, added: false, removed: false },
    ],
    change_note: null,
    change_note_br_ref: "OQ-255 · B11 F-3",
    superseded: {
      version: 1,
      documents: 3412,
      truncated: true,
      sample: [
        {
          message_id: "msg-1",
          channel: "pdf_print",
          status: "sent",
          sent_at: "2026-07-14T09:00:00Z",
          account_id: "acc-1",
          document_id: "doc-1",
          document_kept: true,
          display_name: "disconnect_notice/2026/07/A-11208.txt",
        },
      ],
    },
    ...overrides,
  };
}

/** A client that answers ONLY the change route — everything else throws, so a
 *  case that accidentally depends on another call fails loudly instead of
 *  hanging. */
function stubClient(record: TemplateChangeRecord | Error) {
  const get = vi.fn(async (path: string) => {
    /* ⚠ AMENDED BY CR-199-BRC10: the workspace now also reads
       `…/variant-options`, and this stub answered EVERY get with a change
       record — so the options read got a change record and the screen broke.
       It now does what its own docstring always said: only the change route
       answers, everything else throws. */
    if (!String(path).includes("/changes/")) {
      throw new Error(`unexpected read in this suite: ${String(path)}`);
    }
    if (record instanceof Error) {
      throw record;
    }
    return { status: 200, data: record, etag: null, notModified: false };
  });
  return { client: { get } as unknown as ApiClient, get };
}

function renderHistory(detail: TemplateDetail, client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(["template-catalog", "detail", detail.code, "default"], detail);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/?view=history"]}>
          <TemplateDetailPanel
            code={detail.code}
            client={client}
            readOnly={false}
            readOnlyReason={null}
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
}

describe("CR-049 task 8 — the version history says WHAT changed", () => {
  it("BR-NOT-027 part 3: an edited version names the fields that moved, as a VALUE", () => {
    const { client } = stubClient(aChangeRecord());
    renderHistory(aDetail(), client);

    const cell = screen.getByTestId("version-changed-2");
    expect(cell).toHaveTextContent("Letter");
    // ⚠ THE SENTENCE IS ON `title`, NOT IN THE CELL. Asserted BOTH ways: a
    // check that only looked for "Letter" would pass on a cell that printed the
    // whole explanation beside it, which is the 645px defect (DEF-2479).
    expect(cell).toHaveAttribute("title", expect.stringContaining("v1"));
    expect(cell.textContent).not.toContain("Open it to see");
  });

  it("the FIRST version says so — a blank would read as 'nobody wrote this'", () => {
    const { client } = stubClient(aChangeRecord());
    renderHistory(aDetail(), client);

    const cell = screen.getByTestId("version-changed-1");
    expect(cell).toHaveTextContent("First version");
    // It is NOT a control: there is no earlier wording for anybody to be
    // holding, so there is nothing to open.
    expect(cell.tagName).not.toBe("BUTTON");
  });

  it("a build whose backend does not answer says NOT RECORDED, never 'nothing changed'", () => {
    const { client } = stubClient(aChangeRecord());
    const detail = aDetail();
    // The wire field is optional, and `undefined` means *this backend has not
    // shipped it*. Drawing an empty cell there would be this screen inventing a
    // fact — hard-won law 1, on a legal trail.
    detail.versions[0].changed_fields = undefined;
    detail.versions[0].changed_from_version = undefined;
    renderHistory(detail, client);

    expect(screen.getByTestId("version-changed-2")).toHaveTextContent("Not recorded");
  });
});

describe("CR-049 task 8 — clicking it opens the record, and the record names the letters", () => {
  it("hard-won law 2: the control is MOUNTED and a click loads the change record", async () => {
    const { client, get } = stubClient(aChangeRecord());
    renderHistory(aDetail(), client);

    await userEvent.click(screen.getByTestId("version-changed-2"));

    await waitFor(() => expect(screen.getByTestId("change-record")).toBeInTheDocument());
    expect(get).toHaveBeenCalledWith(
      "/template-catalog/disconnect_notice_48_hour/changes/ver-2",
    );
    // WHAT MOVED — a size, never a paraphrase of the words (OQ-255(b)).
    expect(screen.getByTestId("change-field-body")).toHaveTextContent("2");
  });

  it("THE HALF A VERSION LIST CANNOT ANSWER: which sent letters carry the old wording", async () => {
    const { client } = stubClient(aChangeRecord());
    renderHistory(aDetail(), client);

    await userEvent.click(screen.getByTestId("version-changed-2"));
    await waitFor(() => expect(screen.getByTestId("change-record")).toBeInTheDocument());

    // The TOTAL, and the page of it — one query, so "1 of 3,412" is never
    // about two different sets.
    expect(screen.getByTestId("change-record")).toHaveTextContent("3,412");
    const row = screen.getByTestId("change-impact-msg-1");
    expect(row).toHaveTextContent("2026-07-14");
    expect(row).toHaveTextContent("Mail");
    // The KEPT COPY, by id — the route CR-049 task 3 already built. A storage
    // key is never handed to a screen, here or anywhere.
    expect(row.querySelector("[data-document-id]")).toHaveAttribute("data-document-id", "doc-1");
    expect(screen.getByTestId("change-impact-truncated")).toHaveTextContent("3,412");
  });

  it("a version nothing was ever sent on says so, rather than drawing an empty list", async () => {
    const { client } = stubClient(
      aChangeRecord({
        superseded: { version: 1, documents: 0, truncated: false, sample: [] },
      }),
    );
    renderHistory(aDetail(), client);

    await userEvent.click(screen.getByTestId("version-changed-2"));
    await waitFor(() => expect(screen.getByTestId("change-record")).toBeInTheDocument());

    expect(screen.getByTestId("change-impact-none")).toBeInTheDocument();
    expect(screen.queryByTestId("change-impact")).not.toBeInTheDocument();
  });

  it("clicking again closes it — the detail is a look, not a place", async () => {
    const { client } = stubClient(aChangeRecord());
    renderHistory(aDetail(), client);

    await userEvent.click(screen.getByTestId("version-changed-2"));
    await waitFor(() => expect(screen.getByTestId("change-record")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("version-changed-2"));

    expect(screen.queryByTestId("change-record")).not.toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-049 task 8 (sources: 12-governance/11-change-requests.md CR-049 step 5c task 8 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 part 3 · 12-governance/02-decision-log.md 2026-08-30 "A TABLE CELL HOLDS A VALUE AND A CONTROL HOLDS A LABEL")
// generated: 2026-08-30 by the CR-049 task 8 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — every case ran against the pre-change screen and failed on the missing cell; transcripts in the header above. tsc✔ · eslint --max-warnings 0 clean for this file.
// exceptions: (1) NOTHING HERE MEASURES GEOMETRY. jsdom performs no layout; the cell's HEIGHT is the browser harness's question (hard-won law 6).
//         (2) THE AUTHOR'S NOTE IS NOT ASSERTED PRESENT because it is not built — OQ-255(b) is the PO's.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
