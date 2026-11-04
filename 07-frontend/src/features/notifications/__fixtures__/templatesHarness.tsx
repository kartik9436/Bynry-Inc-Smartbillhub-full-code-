/**
 * A capture harness for the Templates redesign (`CR-199-BRC10` R2): the real
 * `TemplateCatalogTab`, the real stylesheets, and an API answered from the
 * fixtures below — so each drawing image in
 * `05-prototype/templates-redesign-2026-10-29/images/` can be screenshotted
 * beside the screen without a booted backend. Not part of the product bundle:
 * only `templates-harness.html` loads it, under `npm run dev`.
 *
 * ⚠ **THE FIXTURES ARE ILLUSTRATIONS (B14 rule 37), AND ONE IS AHEAD OF THE
 * SERVER.** The list's channel counts, per-row languages and status facets are
 * served here so the drawn chips can be looked at; the real catalogue read does
 * not serve them yet (filed as a defect by the screens lane). Everything else
 * is the shape `CR-199-BRC10` §5 / §5b documents.
 *
 * Query: `?entry=<path and query under /springfield/settings/configure/templates>`
 * · `&legal=1` (the template is a legal notice) · `&errors=1` (the render
 * finds an unknown placeholder and a bare link) · `&dark=1`.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ReactDOM from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import "@/i18n";
import "@/styles/global.css";
import "@/features/tenancy/SettingsPage.css";
import "@/styles/tailwind.css";

import type { ApiClient } from "@/api/client";
import type {
  TemplateCatalogPage,
  TemplateCatalogRow,
  TemplateDetail,
  TemplatePreview,
  TemplateVariantOptions,
  TemplateVersionRow,
} from "@/api/endpoints";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { TemplateCatalogTab } from "../TemplateCatalog";

const params = new URLSearchParams(window.location.search);
const legal = params.get("legal") === "1";
const withErrors = params.get("errors") === "1";
if (params.get("dark") === "1") {
  document.documentElement.setAttribute("data-theme", "dark");
}

const EN_ES = (written: boolean) => [
  { code: "en", written: true },
  { code: "es", written },
];

function row(overrides: Partial<TemplateCatalogRow>): TemplateCatalogRow {
  return {
    code: "x",
    name: "X",
    category: "billing",
    category_source: "cr_007",
    kind: "Email",
    variants: 1,
    used_by: "Sent when a bill is issued.",
    used_by_state: "in-use",
    edited: null,
    edited_at: null,
    group: "email",
    channel: "email",
    catalog_unavailable: null,
    body_unavailable: null,
    has_published: true,
    languages: EN_ES(false),
    ...overrides,
  };
}

const ROWS: TemplateCatalogRow[] = [
  row({
    code: "account_message",
    name: "A message from the billing team",
    category: "account_lifecycle",
    used_by: "What a clerk writes to a customer from the account screen.",
    edited: "Oct 12 · Gaurav",
  }),
  row({
    code: "email_bill_ready",
    name: "Bill ready · e-bill email",
    variants: 3,
    edited: "Oct 29 · Gaurav",
    has_draft: true,
    languages: EN_ES(true),
  }),
  row({
    code: "sms_bill_ready",
    name: "Bill ready · SMS",
    kind: "SMS",
    group: "sms",
    channel: "sms",
    languages: EN_ES(true),
  }),
  row({
    code: "disconnect_notice_10_day",
    name: "Disconnect notice · 10 day",
    category: "collections",
    used_by: "The regulated notice before a disconnection.",
    kind: "Print + email",
    group: "printable",
    channel: "pdf_print",
    variants: 2,
    needs_approval: true,
  }),
  row({
    code: "email_past_due",
    name: "Past-due reminder · email",
    category: "collections",
    used_by: "Sent 3 days after the due date.",
    variants: 2,
  }),
  row({
    code: "staff_bulk_summary",
    name: "Bulk action summary",
    used_by: "Told to the staff member who ran a bulk action.",
    kind: "In-app message",
    group: "in_app",
    channel: "in_app",
  }),
];

const PAGE: TemplateCatalogPage = {
  count: ROWS.length,
  results: ROWS,
  page: 1,
  per: 50,
  categories: [
    { key: "billing", count: 3 },
    { key: "collections", count: 2 },
    { key: "account_lifecycle", count: 1 },
  ],
  channels: [
    { key: "email", count: 4 },
    { key: "sms", count: 1 },
    { key: "in_app", count: 1 },
    { key: "pdf_print", count: 1 },
  ],
  channels_total: ROWS.length,
  languages: [
    { key: "en", count: 6 },
    { key: "es", count: 2 },
  ],
  statuses: [
    { key: "published", count: 5 },
    { key: "draft", count: 1 },
    { key: "not_published", count: 0 },
    { key: "needs_approval", count: 1 },
  ],
  columns: [],
  page_sizes: [50, 100, 200],
  can_edit: true,
  cannot_edit_reason: null,
  create_action: "variant",
  create_action_reason: "",
};

const BILL_RICH =
  "Hello {first_name},\n\nYour bill for account **{account_no}** is ready.\n\n" +
  "- Amount due: **{amount_due}**\n- Due date: {due_date}\n\n[[Pay now|{pay_link}]]\n\n" +
  "[View your bill]({bill_link})\n\nQuestions? Call {support_phone}.";
const SMS = "{utility_name}: your bill of {amount_due} is due {due_date}. Pay: {pay_link}";
const LEGAL =
  "{customer_name},\n\nService at {service_address} will be disconnected unless " +
  "**{amount_due}** is paid within 10 days.\n\n[[Pay now|{pay_link}]]\n\n" +
  "Call {support_phone} to set up a payment plan.";

function version(n: number, status: string, body: string, extra: Partial<TemplateVersionRow> = {}) {
  return {
    id: `ver-${n}`,
    version: n,
    status,
    subject: "Your {utility_name} bill is ready",
    body,
    effective_from: null,
    created_by: null,
    published_by: null,
    published_at: status === "draft" ? null : `2026-10-${10 + n}T09:00:00Z`,
    archived_at: status === "archived" ? `2026-10-${11 + n}T09:00:00Z` : null,
    updated_at: `2026-10-${10 + n}T09:00:00Z`,
    pinned_by: 0,
    deletable: true,
    author_label: "platform seed",
    author_name: n === 1 ? null : "Gaurav",
    author_recorded: n !== 1,
    change_note: null,
    change_note_unavailable: "Not recorded",
    changed_fields: n === 1 ? [] : ["body"],
    changed_from_version: n === 1 ? null : n - 1,
    body_format: "rich" as const,
    can_make_live_again: status === "archived",
    make_live_again_needs_approval: legal,
    ...extra,
  } satisfies TemplateVersionRow;
}

const EMAIL_HTML = `<!doctype html><html><body style="margin:0;background:#f4f4f4;font-family:Arial,sans-serif">
<div style="max-width:560px;margin:16px auto;background:#fff;border:1px solid #ddd">
<div style="padding:12px 20px;color:#555;font-size:12px">From Springfield Water Utility · To Pat Rivera<br>
<b style="color:#111;font-size:14px">Your Springfield Water Utility bill is ready</b></div>
<div style="background:#1f4e8c;color:#fff;padding:16px 20px;font-weight:bold">&#128167; Springfield Water Utility</div>
<div style="padding:20px;color:#111;font-size:14px;line-height:1.5"><p>Hello Pat,</p>
<p>Your bill for account <b>AC-004211</b> is ready.</p>
<ul><li>Amount due: <b>$84.20</b></li><li>Due date: Nov 15, 2026</li></ul>
<p><a style="display:inline-block;background:#1f4e8c;color:#fff;padding:10px 18px;text-decoration:none;font-weight:bold">Pay now</a></p>
<p><a style="color:#1f4e8c">View your bill</a></p><p>Questions? Call (217) 555-0142.</p></div>
<div style="border-top:1px solid #eee;padding:14px 20px;color:#666;font-size:11px">Springfield Water Utility · 300 Monroe St, Springfield, IL 62701<br>
You receive this because you have an account with us.</div></div></body></html>`;

function preview(kind: "email" | "sms" | "print"): TemplatePreview {
  const base: TemplatePreview = {
    body:
      kind === "sms"
        ? "Springfield Water Utility: your bill of $84.20 is due Nov 15, 2026. Pay: https://springfield.example/pay/AC-004211"
        : kind === "print"
          ? "NOTICE OF INTENT TO DISCONNECT\n\nPat Rivera\n412 Maple St, Springfield\nAccount AC-004211\n\nService will be disconnected unless $84.20 is paid within 10 days."
          : "Hello Pat,\n\nYour bill for account AC-004211 is ready.",
    subject: kind === "email" ? "Your Springfield Water Utility bill is ready" : null,
    channel: kind,
    sample_data: true,
    sample_data_notice: "Preview only — sample data, nothing is sent.",
    sample_data_detail: "Rendered from sample data.",
    absences: [],
    problems: [],
    unsampled: [],
    rendered_length: kind === "sms" ? 116 : 249,
  };
  if (kind !== "email") return base;
  return {
    ...base,
    html: EMAIL_HTML,
    text: base.body,
    body_format: "rich",
    branding: {
      brand_primary_hex: "#1f4e8c",
      band_hex: "#1f4e8c",
      ink_hex: "#ffffff",
      has_logo: true,
      logo_url: null,
      logo_link_url: "https://springfieldwater.example",
      utility_name: "Springfield Water Utility",
    },
    errors: withErrors
      ? [
          {
            code: "placeholderUnknown",
            message_key: "notifications.templates.placeholderUnknown",
            params: { placeholder: "{bogus}" },
          },
        ]
      : [],
    warnings: withErrors
      ? [
          {
            code: "linkAsText",
            message_key: "notifications.templates.linkAsText",
            params: { placeholder: "{pay_link}" },
          },
        ]
      : [],
  };
}

const TOKENS: [string, string, string, "text" | "link"][] = [
  ["customer_name", "Customer name", "Pat Rivera", "text"],
  ["first_name", "First name", "Pat", "text"],
  ["account_no", "Account number", "AC-004211", "text"],
  ["service_address", "Service address", "412 Maple St, Springfield", "text"],
  ["amount_due", "Amount due", "$84.20", "text"],
  ["due_date", "Due date", "Nov 15, 2026", "text"],
  ["pay_link", "Pay link", "https://springfield.example/pay/AC-004211", "link"],
  ["bill_link", "Bill link", "https://springfield.example/bills/B-118204", "link"],
  ["support_phone", "Support phone", "(217) 555-0142", "text"],
  ["utility_name", "Utility name", "Springfield Water Utility", "text"],
];

function detail(code: string): TemplateDetail {
  const isSms = code.startsWith("sms_");
  const isLegal = code.startsWith("disconnect");
  const body = isSms ? SMS : isLegal ? LEGAL : BILL_RICH;
  const listing = ROWS.find((candidate) => candidate.code === code) ?? ROWS[1];
  return {
    code,
    name: listing.name,
    category: listing.category,
    category_source: "cr_007",
    kind: listing.kind,
    used_by: listing.used_by,
    group: isSms ? "sms" : "email",
    channel: isSms ? "sms" : "email",
    preview_surfaces: isSms ? ["sms"] : isLegal ? ["email", "printable"] : ["email"],
    body_formats: isSms ? ["plain"] : ["plain", "rich"],
    merge_fields: TOKENS.map(([token]) => token),
    merge_field_rows: TOKENS.map(([token, label, sample, kind]) => ({
      token,
      insert: `{${token}}`,
      sample_value: sample,
      sample_unavailable: null,
      derived_spelling: false,
      label,
      kind,
    })),
    sample_identity: { customer_name: "Pat Rivera", account_no: "AC-004211" },
    derived_spelling: [],
    platform_default: null,
    mandatory_content: [],
    custom_field_variables: [],
    catalog_unavailable: null,
    body_unavailable: null,
    variants: [
      {
        id: "v-default",
        name: listing.name,
        category: "default",
        language: "default",
        is_default: true,
        active: true,
        published_version: 3,
        version_count: 4,
      },
      {
        id: "v-es",
        name: "Español",
        category: "default",
        language: "es",
        is_default: false,
        active: true,
        published_version: 2,
        version_count: 2,
      },
    ],
    selected_variant: "v-default",
    versions: isLegal
      ? [version(2, "published", body), version(1, "archived", body)]
      : [
          version(4, "draft", body),
          version(3, "published", body),
          version(2, "archived", body),
          version(1, "archived", body),
        ],
    preview: preview(isSms ? "sms" : "email"),
    preview_unavailable: null,
    sms_character_counter: 160,
    can_edit: true,
    cannot_edit_reason: null,
    can_test_send: true,
    test_send_reason: "Sends the wording on screen to your own address, with sample data.",
    can_download_pdf: false,
    download_pdf_label: "No sample PDF",
    download_pdf_reason: "The preview shows the text body.",
    can_set_default: false,
    set_default_reason: "The fallback variant is fixed in this release.",
    language_selection_reason: "Messages follow the customer's preferred language.",
    set_default_label: "Default is fixed",
    language_selection_label: "Customer's language",
    test_send_label: "Goes to you",
    set_default_br_ref: "OQ-252",
    language_selection_br_ref: "BR-NOT-006",
  };
}

function options(code: string): TemplateVariantOptions {
  return {
    code,
    channel: code.startsWith("sms_") ? "sms" : "email",
    needs_approval: legal || code.startsWith("disconnect"),
    categories: [
      { value: "default", label: "All customers" },
      { value: "residential", label: "Residential" },
      { value: "commercial", label: "Commercial" },
      { value: "low_income", label: "Low-income" },
    ],
    languages: [
      { value: "default", code: "en", is_utility_language: true },
      { value: "es", code: "es", is_utility_language: false },
    ],
    start_from: ["published", "blank", "variant"],
    taken: [],
    can_edit: true,
  };
}

const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
const client = {
  get: async (path: string) => {
    if (path.startsWith("/template-catalog?") || path === "/template-catalog") return ok(PAGE);
    if (path === "/template-languages") {
      return ok({
        default_language: "en",
        languages: [
          { value: "default", language: "en", accounts: 9120, is_default: true, no_preference: 410 },
          { value: "es", language: "es", accounts: 312, is_default: false, no_preference: 0 },
        ],
        total: 9432,
      });
    }
    if (path.startsWith("/template-library"))return ok({ results: [], count: 0, kinds: ["notification", "bill"] });
    const m = /^\/template-catalog\/([^/?]+)(\/variant-options)?/.exec(path);
    if (m !== null) return ok(m[2] !== undefined ? options(m[1]) : detail(m[1]));
    throw new Error(`harness has no answer for GET ${path}`);
  },
  post: async (path: string) => {
    if (path.endsWith("/preview")) return ok(preview(path.includes("sms_") ? "sms" : "email"));
    return ok(version(5, "draft", BILL_RICH));
  },
} as unknown as ApiClient;

const entry = `/springfield/settings/configure/templates${params.get("entry") ?? ""}`;
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <QueryClientProvider client={queryClient}>
    <ToastProvider>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <MemoryRouter initialEntries={[entry]}>
          <main className="mx-auto max-w-[80rem] bg-bg p-6 max-sm:p-4">
            <Routes>
              <Route
                path="/:tenant/settings/:tab/:sub"
                element={<TemplateCatalogTab readOnly={false} client={client} />}
              />
            </Routes>
          </main>
        </MemoryRouter>
      </TenantRegionalProvider>
    </ToastProvider>
  </QueryClientProvider>,
);
