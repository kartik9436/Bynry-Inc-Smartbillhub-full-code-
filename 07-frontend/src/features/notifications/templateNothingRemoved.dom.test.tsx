// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 T6/T7 — the templates redesign removes NOTHING
// Rules:    PO defect #4 (*"earlier actions removed"*) · `CR-199-BRC10` §6
//           (the forty-row inventory) · hard-won law 2 (mount a routed screen
//           under its REAL path pattern) · BR-SHL-025
// ───────────────────────────────────────────────────────
// THE INVENTORY, AS A TEST.
//
// `CR-199-BRC10` §6 lists every action the live Templates screens offered on
// 2026-10-29, before the redesign touched them, and says where each one lives
// now. Each `it` below is one row (or one tight group of rows) of that table,
// named by its row id, and asserts the CONTROL — not a word on the page — so a
// later change that drops one goes red here naming the row it dropped.
//
// ⚠ **MOUNTED UNDER THE REAL ROUTE.** The Templates tab is
// `/:tenant/settings/:tab/:sub` (`App.tsx`); a bare `MemoryRouter` would leave
// `useParams()` empty and every address the screen builds wrong without any
// assertion noticing (hard-won law 2's fixture clause).
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type {
  TemplateCatalogPage,
  TemplateCatalogRow,
  TemplateDetail,
  TemplateVersionRow,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateCatalogTab } from "./TemplateCatalog";

afterEach(cleanup);

const ROUTE = "/:tenant/settings/:tab/:sub";
const BASE = "/riverbend/settings/configure/templates";

function aRow(overrides: Partial<TemplateCatalogRow> = {}): TemplateCatalogRow {
  return {
    code: "email_bill_ready",
    name: "Bill ready · e-bill email",
    category: "billing",
    category_source: "cr_007",
    kind: "Email",
    variants: 1,
    used_by: "Sent when a bill is ready.",
    used_by_state: "in-use",
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

const ROWS: TemplateCatalogRow[] = [
  aRow(),
  aRow({
    code: "sms_bill_ready",
    name: "Bill ready · SMS",
    kind: "SMS",
    group: "sms",
    channel: "sms",
  }),
  aRow({
    code: "writeoff_notice",
    name: "Write-off notice",
    kind: "Print",
    group: "printable",
    channel: "pdf_print",
  }),
];

function aPage(overrides: Partial<TemplateCatalogPage> = {}): TemplateCatalogPage {
  return {
    count: ROWS.length,
    results: ROWS,
    page: 1,
    per: 50,
    categories: [{ key: "billing", count: 3 }],
    columns: [],
    page_sizes: [50, 100],
    can_edit: true,
    cannot_edit_reason: null,
    create_action: "variant",
    create_action_reason: "A variant of a listed template.",
    ...overrides,
  };
}

function aVersion(overrides: Partial<TemplateVersionRow> = {}): TemplateVersionRow {
  return {
    id: "ver-1",
    version: 1,
    status: "published",
    subject: "Your bill is ready",
    body: "Hello {first_name}",
    effective_from: null,
    created_by: null,
    published_by: null,
    published_at: "2026-10-01T09:00:00Z",
    archived_at: null,
    updated_at: "2026-10-01T09:00:00Z",
    pinned_by: 0,
    deletable: true,
    author_label: "platform seed",
    change_note: null,
    change_note_unavailable: "Not recorded",
    changed_fields: ["body"],
    changed_from_version: null,
    ...overrides,
  };
}

function aDetail(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    code: "email_bill_ready",
    name: "Bill ready · e-bill email",
    category: "billing",
    category_source: "cr_007",
    kind: "Email",
    used_by: "Sent when a bill is ready.",
    group: "email",
    channel: "email",
    preview_surfaces: ["email", "printable"],
    merge_fields: ["first_name"],
    merge_field_rows: [
      {
        token: "first_name",
        insert: "{first_name}",
        sample_value: "Pat",
        sample_unavailable: null,
        derived_spelling: false,
      },
    ],
    sample_identity: { customer_name: "Sample Customer", account_no: "SAMPLE-1" },
    derived_spelling: [],
    platform_default: null,
    mandatory_content: [],
    custom_field_variables: [],
    catalog_unavailable: null,
    body_unavailable: null,
    variants: [
      {
        id: "v-default",
        name: "Bill ready · e-bill email",
        category: "default",
        language: "default",
        is_default: true,
        active: true,
        published_version: 1,
        version_count: 3,
      },
      {
        id: "v-commercial",
        name: "Commercial",
        category: "commercial",
        language: "default",
        is_default: false,
        active: true,
        published_version: 1,
        version_count: 1,
      },
    ],
    selected_variant: "v-commercial",
    versions: [
      aVersion({
        id: "ver-3",
        version: 3,
        status: "draft",
        published_at: null,
        changed_from_version: 2,
      }),
      aVersion({ id: "ver-2", version: 2, status: "published", changed_from_version: 1 }),
      aVersion({
        id: "ver-1",
        version: 1,
        status: "archived",
        archived_at: "2026-10-02T00:00:00Z",
      }),
    ],
    preview: {
      body: "Hello Pat",
      subject: "Your bill is ready",
      channel: "email",
      sample_data: true,
      sample_data_notice: "Preview only — sample data, nothing is sent.",
      sample_data_detail: "Rendered from SAMPLE data.",
      absences: [],
      problems: [],
      unsampled: [],
      rendered_length: 9,
    },
    preview_unavailable: null,
    sms_character_counter: 160,
    can_edit: true,
    cannot_edit_reason: null,
    can_test_send: true,
    test_send_reason: "The test goes to your own address.",
    can_download_pdf: false,
    download_pdf_label: "No sample PDF",
    download_pdf_reason: "The preview shows the text body.",
    can_set_default: false,
    set_default_reason: "The fallback variant is fixed in this release.",
    language_selection_reason: "Messages follow the customer's language.",
    set_default_label: "Default is fixed",
    language_selection_label: "Customer's language",
    test_send_label: "Goes to you",
    set_default_br_ref: "OQ-252",
    language_selection_br_ref: "BR-NOT-006",
    ...overrides,
  };
}

function mount(entry: string, detail: TemplateDetail = aDetail(), variant = "v-commercial") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(["template-catalog", "", "", "name", 1, 50, "asc"], aPage());
  client.setQueryData(["template-library", "bill"], {
    results: [],
    count: 0,
    kinds: ["notification"],
  });
  client.setQueryData(["template-catalog", "detail", detail.code, variant], detail);
  client.setQueryData(["template-catalog", "detail", detail.code, "default"], detail);
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`${BASE}${entry}`]}>
          <Routes>
            <Route
              path={ROUTE}
              element={<TemplateCatalogTab readOnly={false} client={{} as never} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const OPEN = `?template=email_bill_ready&variant=v-commercial`;

describe("CR-199-BRC10 §6 — the LIST keeps every action it had", () => {
  it("L1 · L2 · L3 · L4 · L5 — search, category and kind filters, sorts, the table frame", () => {
    mount("");
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
    expect(screen.getByText("+ Filter")).toBeInTheDocument();
    for (const header of ["Template", "Channels", "Category", "Variants", "Last edited"]) {
      expect(screen.getAllByText(header).length).toBeGreaterThan(0);
    }
  });

  it("L6 · L7 · L8 — every row opens by its name, 👁 View and ✎ Edit wording", () => {
    mount("");
    expect(screen.getByTestId("template-name-email_bill_ready")).toBeInTheDocument();
    expect(screen.getByTestId("template-open-email_bill_ready")).toBeEnabled();
    expect(screen.getByTestId("template-edit-email_bill_ready")).toBeEnabled();
  });

  it("L9 — a folded row's channels are each one click away", () => {
    mount("");
    expect(screen.getByTestId("template-surface-email_bill_ready")).toBeInTheDocument();
    expect(screen.getByTestId("template-surface-sms_bill_ready")).toBeInTheDocument();
  });

  it("L10 — Duplicate as variant is on every row", () => {
    mount("");
    expect(screen.getByTestId("template-duplicate-email_bill_ready")).toBeInTheDocument();
    expect(screen.getByTestId("template-duplicate-writeoff_notice")).toBeInTheDocument();
  });

  it("L13 — the in-use status and its sentence", () => {
    mount("");
    expect(screen.getByTestId("template-usedby-email_bill_ready")).toBeInTheDocument();
    expect(screen.getByTestId("template-status-email_bill_ready")).toHaveTextContent("Published");
  });

  it("L8 → workspace: ✎ opens the template ALREADY EDITING", () => {
    mount("");
    fireEvent.click(screen.getByTestId("template-edit-email_bill_ready"));
    expect(screen.getByTestId("workspace-mode")).toHaveTextContent("Editing");
    expect(screen.getByTestId("editor-body")).not.toHaveAttribute("readonly");
  });

  it("L10 → workspace: `…` → Duplicate opens the drawn form", () => {
    mount("");
    fireEvent.click(screen.getByTestId("template-duplicate-email_bill_ready"));
    expect(screen.getByTestId("duplicate-variant-form")).toBeInTheDocument();
  });
});

describe("CR-199-BRC10 §6 — the WORKSPACE keeps every action it had", () => {
  it("W1 · W2 · W3 — back, and the Channel / Language / Customers pickers", () => {
    mount(OPEN);
    expect(screen.getByTestId("template-back")).toBeInTheDocument();
    expect(screen.getByTestId("picker-channel")).toBeInTheDocument();
    expect(screen.getByTestId("picker-language")).toBeInTheDocument();
    expect(screen.getByTestId("picker-customers")).toBeInTheDocument();
  });

  it("W4 · W5 · W6 · W13 · W15 · W22 — the ONE action bar, in the drawn order", () => {
    mount(OPEN);
    const bar = screen.getByTestId("workspace-action-bar");
    const order = [...bar.querySelectorAll("button")].map((button) => button.textContent);
    expect(order).toEqual([
      "View",
      "Edit wording",
      "Duplicate as variant",
      "+ New variant",
      "History",
      "Send test",
      "Save draft",
      "Publish",
    ]);
    expect(screen.getByTestId("test-send-reason")).toHaveTextContent("Goes to you");
  });

  it("W7 · W8 · W9 · W10 · W23 — preview tabs, Print, Set as default, the caption, Download sample PDF", () => {
    mount(OPEN);
    expect(screen.getByTestId("wireframe-surface-tabs")).toBeInTheDocument();
    expect(screen.getByTestId("print-preview")).toBeInTheDocument();
    expect(screen.getByTestId("set-default")).toBeDisabled();
    expect(screen.getByTestId("preview-notice")).toBeInTheDocument();
    expect(screen.getByTestId("download-pdf")).toBeDisabled();
    expect(screen.getByTestId("preview-expand")).toBeEnabled();
  });

  it("W11 · W21 · W24 — editing: the placeholder picker, the subject and the body", () => {
    mount(OPEN);
    fireEvent.click(screen.getByTestId("edit-wording"));
    expect(screen.getByTestId("editor-subject")).not.toHaveAttribute("readonly");
    fireEvent.click(screen.getByTestId("insert-placeholder"));
    expect(screen.getByTestId("placeholder-picker")).toBeInTheDocument();
    expect(screen.getByTestId("insert-first_name")).toBeInTheDocument();
    expect(screen.getByTestId("editor-save")).toBeEnabled();
    expect(screen.getByTestId("workspace-publish")).toBeEnabled();
  });

  it("W12 — where it is used, in the head", () => {
    mount(OPEN);
    expect(screen.getByTestId("head-used-by")).toHaveTextContent("Sent when a bill is ready.");
  });

  it("W14 · W15 · W16 · W17 · W18 — History: open in editor, publish, restore, the change record", () => {
    mount(OPEN);
    fireEvent.click(screen.getByTestId("history-link"));
    const history = screen.getByTestId("version-history");
    expect(within(history).getByTestId("preview-version-3")).toBeInTheDocument();
    expect(within(history).getByTestId("open-version-3")).toBeInTheDocument();
    expect(within(history).getByTestId("publish-3")).toBeInTheDocument();
    expect(within(history).getByTestId("restore-1")).toBeInTheDocument();
    expect(within(history).getByTestId("restore-2")).toBeInTheDocument();
    expect(within(history).getByTestId("version-changed-3")).toBeInTheDocument();
  });

  it("W19 — the variant's Deactivate and the way back", () => {
    mount(OPEN);
    expect(screen.getByTestId("deactivate-variant")).toBeInTheDocument();
    expect(screen.getByTestId("reactivate-variant")).toBeDisabled();
  });

  it("W20 — a contract with no variant still offers Create from our default", () => {
    const contract = aDetail({
      code: "contract_service_agreement",
      group: "contracts",
      channel: "pdf_print",
      preview_surfaces: ["contract"],
      variants: [],
      selected_variant: null,
      versions: [],
      preview: null,
      platform_default: {
        body: "SERVICE AGREEMENT",
        subject: null,
        source: "CR-011 item 9",
        notice: "A starting point, not legal advice.",
        label: "Platform default wording",
        is_placeholder: false,
        placeholder_marker: null,
        requires_from_utility: [],
        requires_effective_date: true,
      },
    });
    mount("?template=contract_service_agreement", contract, "default");
    expect(screen.getByTestId("platform-default-offer")).toBeInTheDocument();
    expect(screen.getByTestId("create-from-default")).toBeInTheDocument();
  });

  it("+ New variant opens the drawn form (`06`)", () => {
    mount(OPEN);
    fireEvent.click(screen.getByTestId("new-variant"));
    expect(screen.getByTestId("new-variant-form")).toBeInTheDocument();
  });

  it("Publish asks first (`11`), and names the version", () => {
    mount(OPEN);
    fireEvent.click(screen.getByTestId("edit-wording"));
    fireEvent.click(screen.getByTestId("workspace-publish"));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Publish v3?");
  });
});
