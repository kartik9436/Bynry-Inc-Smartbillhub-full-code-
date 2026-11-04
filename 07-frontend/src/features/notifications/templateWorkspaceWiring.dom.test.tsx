// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 T6/T7 — the workspace is WIRED to the three server
//           lanes' endpoints (§5 variants and history, §5b email)
// Rules:    PO rulings A1 C · A2 A · A3 A · A4 B · 2A · hard-won law 2 (built
//           is not wired: each case presses the control and reads the REQUEST
//           the server would receive, not only what the screen shows)
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type {
  TemplateDetail,
  TemplatePreview,
  TemplateVariantOptions,
  TemplateVersionRow,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateWorkspace, workspaceAxes } from "./TemplateWorkspace";

afterEach(cleanup);

function aVersion(overrides: Partial<TemplateVersionRow> = {}): TemplateVersionRow {
  return {
    id: "ver-2",
    version: 2,
    status: "published",
    subject: "Your bill is ready",
    body: "Hello {first_name}",
    effective_from: null,
    created_by: null,
    published_by: null,
    published_at: "2026-10-12T09:00:00Z",
    archived_at: null,
    updated_at: "2026-10-12T09:00:00Z",
    pinned_by: 0,
    deletable: true,
    author_label: "platform seed",
    change_note: null,
    change_note_unavailable: "Not recorded",
    changed_fields: ["body"],
    changed_from_version: 1,
    body_format: "rich",
    ...overrides,
  };
}

function aPreview(overrides: Partial<TemplatePreview> = {}): TemplatePreview {
  return {
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
    preview_surfaces: ["email"],
    body_formats: ["plain", "rich"],
    merge_fields: ["first_name", "pay_link"],
    merge_field_rows: [
      {
        token: "first_name",
        insert: "{first_name}",
        sample_value: "Pat",
        sample_unavailable: null,
        derived_spelling: false,
        label: "First name",
        kind: "text",
      },
      {
        token: "pay_link",
        insert: "{pay_link}",
        sample_value: "https://springfield.example/pay",
        sample_unavailable: null,
        derived_spelling: false,
        label: "Pay link",
        kind: "link",
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
        name: "Bill ready",
        category: "default",
        language: "default",
        is_default: true,
        active: true,
        published_version: 2,
        version_count: 2,
      },
    ],
    selected_variant: "v-default",
    versions: [
      aVersion(),
      aVersion({
        id: "ver-1",
        version: 1,
        status: "archived",
        archived_at: "2026-10-12T09:00:00Z",
        published_at: "2026-10-01T09:00:00Z",
        can_make_live_again: true,
        make_live_again_needs_approval: false,
        changed_from_version: null,
      }),
    ],
    preview: aPreview({
      html: "<html><body><p>Hello Pat</p></body></html>",
      text: "Hello Pat",
      body_format: "rich",
      branding: {
        brand_primary_hex: "#1f4e8c",
        band_hex: "#1f4e8c",
        ink_hex: "#ffffff",
        has_logo: true,
        logo_url: null,
        logo_link_url: "https://springfield.example",
        utility_name: "Springfield Water",
      },
    }),
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

function anOptions(overrides: Partial<TemplateVariantOptions> = {}): TemplateVariantOptions {
  return {
    code: "email_bill_ready",
    channel: "email",
    needs_approval: false,
    categories: [
      { value: "default", label: "All customers" },
      { value: "commercial", label: "Commercial" },
    ],
    languages: [
      { value: "default", code: "en", is_utility_language: true },
      { value: "es", code: "es", is_utility_language: false },
    ],
    start_from: ["blank", "published", "variant"],
    taken: [{ category: "default", language: "default", variant: "v-default" }],
    can_edit: true,
    ...overrides,
  };
}

function aClient(options: TemplateVariantOptions, previewAnswer?: TemplatePreview) {
  const ok = <T,>(data: T) => ({ status: 201, data, etag: null, notModified: false });
  const get = vi.fn(async (path: string) => {
    if (path.endsWith("/variant-options")) return ok(options);
    if (path === "/template-languages") {
      return ok({
        default_language: "en",
        languages: [
          { value: "default", language: "en", accounts: 9120, is_default: true, no_preference: 40 },
          { value: "es", language: "es", accounts: 300, is_default: false, no_preference: 0 },
          { value: "es-MX", language: "es-MX", accounts: 12, is_default: false, no_preference: 0 },
        ],
        total: 9432,
      });
    }
    throw new Error(`unexpected read ${path}`);
  });
  const post = vi.fn(async (path: string, body: Record<string, unknown>) => {
    if (path.endsWith("/new-variant")) {
      return ok({
        variant: { ...aDetail().variants[0], id: "v-new", language: body.language },
        version: null,
        started_from_version: 2,
      });
    }
    if (path.endsWith("/make-live-again")) {
      return ok({
        outcome: "live",
        version: aVersion({ id: "ver-3", version: 3, restored_from_version: 1 }),
        restored_from_version: 1,
        replaced_version: 2,
      });
    }
    if (path.endsWith("/draft")) return ok(aVersion({ id: "ver-3", version: 3, status: "draft" }));
    if (path.endsWith("/publish")) return ok(aVersion({ id: "ver-3", version: 3 }));
    if (path.endsWith("/preview")) return ok(previewAnswer ?? aPreview());
    throw new Error(`unexpected write ${path}`);
  });
  return { client: { get, post } as unknown as ApiClient, get, post };
}

function mount(detail: TemplateDetail, client: ApiClient, entry = "") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(["template-catalog", "detail", detail.code, "v-default"], detail);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/riverbend/settings/configure/templates${entry}`]}>
          <Routes>
            <Route
              path="/:tenant/settings/:tab/:sub"
              element={
                <TemplateWorkspace
                  code={detail.code}
                  client={client}
                  readOnly={false}
                  readOnlyReason={null}
                  variantId="v-default"
                  onSelectVariant={() => undefined}
                  onBack={() => undefined}
                  surfaces={[]}
                  onOpenSurface={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const postsTo = (post: ReturnType<typeof vi.fn>, suffix: string) =>
  post.mock.calls.filter(([path]) => String(path).endsWith(suffix));

describe("CR-199-BRC10 §5 — the pickers are the server's (A3 A, A4 B)", () => {
  it("Customers lists the utility's own classes; Language its switched-on languages", async () => {
    const { client } = aClient(anOptions());
    mount(aDetail(), client);
    const customers = await screen.findByText("Commercial");
    expect(customers.tagName).toBe("OPTION");
    const language = screen
      .getByTestId("picker-language")
      .querySelector("select") as HTMLSelectElement;
    await waitFor(() => expect(language.options).toHaveLength(2));
    // The one with no wording for this customer group says so (`18`).
    expect(language.options[1].textContent).toContain("not written yet");
  });

  it("an unwritten language asks first, then starts from the utility's wording (`18`)", async () => {
    const { client, post } = aClient(anOptions());
    mount(aDetail(), client);
    const language = screen
      .getByTestId("picker-language")
      .querySelector("select") as HTMLSelectElement;
    await waitFor(() => expect(language.options).toHaveLength(2));
    fireEvent.change(language, { target: { value: "es" } });
    const dialog = screen.getByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Start from/ }));
    await waitFor(() => expect(postsTo(post, "/new-variant")).toHaveLength(1));
    expect(postsTo(post, "/new-variant")[0][1]).toEqual({
      language: "es",
      category: "default",
      start_from: "published",
    });
  });

  it("Duplicate as variant posts the variant to copy (`10`)", async () => {
    const { client, post } = aClient(anOptions());
    mount(aDetail(), client);
    fireEvent.click(screen.getByTestId("duplicate-variant"));
    const form = await screen.findByTestId("duplicate-variant-form");
    await waitFor(() => expect(within(form).getAllByRole("combobox")).toHaveLength(4));
    fireEvent.click(screen.getByTestId("duplicate-save"));
    await waitFor(() => expect(postsTo(post, "/new-variant")).toHaveLength(1));
    expect(postsTo(post, "/new-variant")[0][1]).toMatchObject({
      start_from: "variant",
      source_variant: "v-default",
    });
  });
});

describe("CR-199-BRC10 §5c — how many customers read this language (`16`)", () => {
  it("the language line carries the server's count for the open variant's language", async () => {
    const { client } = aClient(anOptions());
    mount(aDetail(), client);
    const chip = await screen.findByTestId("language-readers");
    expect(chip).toHaveTextContent("English · 9,120 customers");
  });
});

describe("CR-199-BRC10 §5 — History makes an earlier version live again (`07`–`09`)", () => {
  it("the row the server allows draws Make live again, and its confirm posts the write", async () => {
    const { client, post } = aClient(anOptions());
    mount(aDetail(), client, "?view=history");
    const action = await screen.findByTestId("make-live-1");
    expect(action).toHaveAttribute("aria-label", "Make live again");
    fireEvent.click(action);
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent("v1 goes out from now. v2 stays in history.");
    fireEvent.click(within(dialog).getByRole("button", { name: "Make live again" }));
    await waitFor(() => expect(postsTo(post, "/make-live-again")).toHaveLength(1));
    expect(postsTo(post, "/make-live-again")[0][1]).toEqual({ version_id: "ver-1" });
  });

  it("the live version draws no Make live again", async () => {
    const { client } = aClient(anOptions());
    mount(aDetail(), client, "?view=history");
    await screen.findByTestId("version-history");
    expect(screen.queryByTestId("make-live-2")).toBeNull();
  });
});

describe("CR-199-BRC10 A1 C — a legal notice is sent for approval (`13`)", () => {
  it("the bar reads Send for approval, and confirming saves a draft and publishes nothing", async () => {
    const { client, post } = aClient(anOptions({ needs_approval: true }));
    mount(aDetail(), client, "?mode=edit");
    await waitFor(() =>
      expect(screen.getByTestId("workspace-publish")).toHaveTextContent("Send for approval"),
    );
    fireEvent.change(screen.getByTestId("editor-body"), { target: { value: "Hello again" } });
    fireEvent.click(screen.getByTestId("workspace-publish"));
    const dialog = screen.getByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Send for approval" }));
    await waitFor(() => expect(postsTo(post, "/draft")).toHaveLength(1));
    expect(postsTo(post, "/publish")).toHaveLength(0);
  });
});

describe("CR-199-BRC10 §5b — rich email (2A)", () => {
  it("Rich / Plain is offered, and Bold writes the closed markup around the selection", async () => {
    const { client } = aClient(anOptions());
    mount(aDetail(), client, "?mode=edit");
    expect(screen.getByRole("radio", { name: "Rich" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Plain text" })).toBeInTheDocument();
    const box = screen.getByTestId("editor-body") as HTMLTextAreaElement;
    box.setSelectionRange(6, 18);
    fireEvent.click(screen.getByTestId("format-bold"));
    expect(box.value).toBe("Hello **{first_name}**");
  });

  it("after Bold the cursor sits after the markup, so the next placeholder goes there (DEF-NOT-10677)", async () => {
    const { client } = aClient(anOptions());
    mount(aDetail(), client, "?mode=edit");
    const box = screen.getByTestId("editor-body") as HTMLTextAreaElement;
    box.setSelectionRange(0, 5);
    fireEvent.click(screen.getByTestId("format-bold"));
    expect(box.value).toBe("**Hello** {first_name}");
    expect(box.selectionStart).toBe(9);
    fireEvent.click(screen.getByTestId("insert-placeholder"));
    fireEvent.click(screen.getByTestId("insert-first_name"));
    expect(box.value).toBe("**Hello**{first_name} {first_name}");
  });

  it("a LINK placeholder goes in as a button (`03`)", async () => {
    const { client } = aClient(anOptions());
    mount(aDetail(), client, "?mode=edit");
    fireEvent.click(screen.getByTestId("insert-placeholder"));
    expect(screen.getByTestId("merge-field-pay_link")).toHaveTextContent("link");
    const box = screen.getByTestId("editor-body") as HTMLTextAreaElement;
    box.setSelectionRange(box.value.length, box.value.length);
    fireEvent.click(screen.getByTestId("insert-pay_link"));
    expect(box.value).toBe("Hello {first_name}[[Pay link|{pay_link}]]");
  });

  it("Save draft sends the format with the words", async () => {
    const { client, post } = aClient(anOptions());
    mount(aDetail(), client, "?mode=edit");
    fireEvent.change(screen.getByTestId("editor-body"), { target: { value: "Hi **there**" } });
    fireEvent.click(screen.getByTestId("editor-save"));
    await waitFor(() => expect(postsTo(post, "/draft")).toHaveLength(1));
    expect(postsTo(post, "/draft")[0][1]).toMatchObject({ body_format: "rich" });
  });

  it("the email is the SERVER's branded render, in a sandboxed frame — never this document", () => {
    const { client } = aClient(anOptions());
    mount(aDetail(), client);
    const frame = screen.getByTestId("preview-email-frame");
    expect(frame.tagName).toBe("IFRAME");
    // DEF-NOT-10688: still no script, no same-origin, no form, no top
    // navigation — and a link opens a NEW tab rather than replacing the preview.
    expect(frame.getAttribute("sandbox")?.split(" ").sort()).toEqual([
      "allow-popups",
      "allow-popups-to-escape-sandbox",
    ]);
    expect(frame.getAttribute("srcdoc")).toMatch(/^<base target="_blank"><html>/);
    expect(frame.getAttribute("srcdoc")).toContain("Hello Pat");
    expect(screen.getByTestId("preview-logo-link")).toHaveTextContent(
      "https://springfield.example",
    );
    expect(screen.getByTestId("preview-branding-settings")).toHaveAttribute(
      "href",
      "/riverbend/settings/company/profile",
    );
  });
});

describe("CR-199-BRC10 A2 A — what the render found in the wording (`17`)", () => {
  it("an unknown placeholder is named in red and blocks the save; a bare link warns", async () => {
    const answer = aPreview({
      errors: [
        {
          code: "placeholderUnknown",
          message_key: "notifications.templates.placeholderUnknown",
          params: { placeholder: "{bogus}" },
        },
      ],
      warnings: [
        {
          code: "linkAsText",
          message_key: "notifications.templates.linkAsText",
          params: { placeholder: "{pay_link}" },
        },
      ],
    });
    const { client } = aClient(anOptions(), answer);
    mount(aDetail(), client, "?mode=edit");
    fireEvent.change(screen.getByTestId("editor-body"), {
      target: { value: "Hello {first_name}, pay at {pay_link} {bogus}" },
    });
    const problems = await screen.findByTestId("wording-problems", {}, { timeout: 2000 });
    expect(problems).toHaveTextContent("{bogus} can't be filled. Pick from the placeholder list.");
    expect(problems).toHaveTextContent("{pay_link} is a link. Make it a button or link.");
    expect(screen.getByTestId("editor-save")).toBeDisabled();
  });
});

describe("DEF-NOT-10676 — the Language picker offers the utility's languages only (PO A4 B)", () => {
  const seeded = ["default", "en-US", "de", "es", "ja-JP"].map((language, index) => ({
    id: `v-${index}`,
    language,
    category: "default",
  }));
  const data = { channel: "email", variants: seeded } as never;
  const options = {
    languages: [
      { value: "default", code: "en-US", is_utility_language: true },
      { value: "es", code: "es", is_utility_language: false },
    ],
    categories: [{ value: "default", label: "All customers" }],
  } as never;
  const t = (key: string) => key;

  it("lists the switched-on set once each, never a seeded language", () => {
    const axes = workspaceAxes(data, "email_bill_ready", [], options, "default", t);
    expect(axes.languages.map((row) => row.value)).toEqual(["default", "es"]);
  });

  it("keeps the language of a variant already open, but never the utility's own twice", () => {
    expect(
      workspaceAxes(data, "email_bill_ready", [], options, "default", t, "de").languages.map((row) => row.value),
    ).toEqual(["default", "es", "de"]);
    expect(
      workspaceAxes(data, "email_bill_ready", [], options, "default", t, "en-US").languages.map((row) => row.value),
    ).toEqual(["default", "es"]);
  });
});

describe("DEF-NOT-10685 — a refused Create draft is said INSIDE the dialog", () => {
  it("draws the refusal in the dialog, keeps it open, and Escape still closes it", async () => {
    const { client, post } = aClient(anOptions());
    post.mockImplementation(async (path: string) => {
      if (path.endsWith("/new-variant")) {
        throw new ApiError(409, {
          code: "BIZ-STATE",
          message_key: "notifications.templates.variant.exists",
        });
      }
      throw new Error(`unexpected write ${path}`);
    });
    mount(aDetail(), client);
    fireEvent.click(screen.getByRole("button", { name: "+ New variant" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Create draft" }));
    await waitFor(() =>
      expect(within(dialog).getByRole("alert")).toHaveTextContent("This variant already exists."),
    );
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("DEF-NOT-10687 — History says what the server says, in short facts", () => {
  it("the platform's seeded v1 (no publish time) reads Published before; pinned is a fact; an email's body is a Message", async () => {
    const { client } = aClient(anOptions());
    const seeded = aDetail({
      versions: [
        aVersion(),
        aVersion({
          id: "ver-1",
          version: 1,
          status: "archived",
          archived_at: "2026-10-12T09:00:00Z",
          published_at: null,
          can_make_live_again: true,
          make_live_again_needs_approval: false,
          changed_from_version: null,
          pinned_by: 99,
          deletable: false,
        }),
      ],
    });
    mount(seeded, client, "?view=history");
    const row = await screen.findByTestId("version-1");
    expect(row).toHaveTextContent("Published before");
    expect(row).not.toHaveTextContent("Archived");
    expect(screen.getByTestId("version-pinned-1")).toHaveTextContent("pinned by 99 sent · never deleted");
    expect(screen.getByTestId("version-pinned-1")).not.toHaveTextContent("because");
    expect(screen.getByTestId("version-changed-2")).toHaveTextContent("Message");
    expect(screen.getByTestId("version-changed-2")).not.toHaveTextContent("Letter");
  });
});

describe("DEF-NOT-10689 — a deactivated variant does not claim to go out", () => {
  it("its archived version reads Archived, with no 'what customers get now'", async () => {
    const { client } = aClient(anOptions());
    const deactivated = aDetail({
      versions: [
        aVersion({
          id: "ver-1",
          version: 1,
          status: "archived",
          archived_at: "2026-10-29T17:13:00Z",
          published_at: "2026-10-01T09:00:00Z",
          changed_from_version: null,
        }),
      ],
    });
    mount(deactivated, client);
    const status = await screen.findByTestId("workspace-status");
    expect(status).toHaveTextContent("Archived · v1");
    expect(status).not.toHaveTextContent("Published v1");
    expect(status).not.toHaveTextContent("This is what customers get now.");
    expect(screen.getByTestId("workspace-status-sentence")).toHaveTextContent("Nothing published yet.");
  });
});
