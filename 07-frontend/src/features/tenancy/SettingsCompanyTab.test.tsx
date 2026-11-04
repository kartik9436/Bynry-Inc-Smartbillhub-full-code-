// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-005 (EP-TEN-05 §Stories)  Screens: S8 (Settings → Company profile)
// Rules:    BR-TEN-017 (issued documents are never re-rendered) · BR-TEN-018 (EIN format-only) ·
//           BR-TEN-019 (logo SVG/PNG ≤ 2 MB; live letterhead preview) · BR-TEN-024 (atomic tab save)
// ───────────────────────────────────────────────────────
// §4 test data is Brazos Bend Utility District No. 1 throughout.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, createApiClient } from "@/api/client";
import { COMPANY_LOGO_FIELD, uploadCompanyLogo } from "@/api/endpoints";
import type { CompanyProfile } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { collectFormErrors } from "@/components/FormModal";
import { ToastProvider } from "@/components/Toast";

import {
  CompanyTab,
  LOGO_MAX_BYTES,
  LOGO_TYPES,
  companyChanges,
  companySchema,
  draftFromProfile,
  formatLogoSize,
  formatLogoType,
  isDirty,
  logoProblem,
  logoProblemKey,
} from "./SettingsCompanyTab";
import { apiErrorText, refusalOf } from "./settingsShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const BRAZOS_BEND: CompanyProfile = {
  legal_name: "Brazos Bend Utility District No. 1",
  dba_name: "Brazos Bend Utilities",
  // CR-060 C7 — the server serves both on every read; `utility` is the seed.
  organisation_type: "utility",
  organisation_types: ["utility", "sub_metering", "hoa"],
  ein: "74-3182640",
  state_utility_id: "TX CCN 13148 / PUCT 10238",
  mailing_address: "9410 FM 1093 Rd, Katy, TX 77494",
  support_phone: "+1 (281) 555-0164",
  support_email: "help@brazosbendutilities.com",
  website: "brazosbendutilities.com",
  logo_file_id: null,
  logo: null,
  // CR-048 wave D — the server always computes the mark; `has_logo` is what a
  // renderer branches on. "BB" from the trading name, white ink because
  // #1B5E9E is dark (see apps/tenancy/brand.py for the 4.58:1 floor).
  has_logo: false,
  logo_ref: null,
  mark: {
    letters: "BB",
    background_hex: "#1B5E9E",
    ink_hex: "#FFFFFF",
    contrast_ratio: 6.68,
  },
  brand_primary_hex: "#1B5E9E",
  brand_accent_hex: "#201E1D",
  remit_to_address: "PO Box 2210, Katy, TX 77492",
  remit_payable_to: "Brazos Bend Utilities",
  service_hours: "Mon–Fri 8–5 CT",
};

function renderTab(profile: CompanyProfile, readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.companyProfile, profile);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <CompanyTab readOnly={readOnly} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-TEN-005 — Company profile tab (utility details · brand · remittance)", () => {
  it("US-TEN-005 TC-1: the tab renders the stored values and posts ONE atomic change set", () => {
    const html = renderTab(BRAZOS_BEND);
    expect(html).toContain("Brazos Bend Utility District No. 1");
    expect(html).toContain("PO Box 2210, Katy, TX 77492");
    // r10 SET-01.profile: the commit reads "Save changes" (was "Save company profile").
    expect(html).toContain("Save changes");

    // BR-TEN-024: the PUT carries only what changed — an untouched tab sends
    // nothing at all, so a Save cannot silently rewrite a field.
    const original = draftFromProfile(BRAZOS_BEND);
    expect(isDirty(original, original)).toBe(false);
    expect(companyChanges(original, original)).toEqual({});

    const edited = { ...original, legal_name: "Brazos Bend Utility District No. 2" };
    expect(isDirty(edited, original)).toBe(true);
    expect(companyChanges(edited, original)).toEqual({
      legal_name: "Brazos Bend Utility District No. 2",
    });
    // An emptied field goes back as null, not "" — the column is nullable.
    expect(companyChanges({ ...original, website: "" }, original)).toEqual({ website: null });
  });

  it("US-TEN-005 TC-2: the letterhead preview renders live from the CURRENT values", () => {
    const html = renderTab(BRAZOS_BEND);
    expect(html).toContain("settings-letterhead");
    // The trading name and the tenant's colors are in the preview before any
    // save — the brand values ride in as data-bound custom properties.
    expect(html).toContain("Brazos Bend Utilities");
    expect(html).toContain("--settings-brand-primary:#1B5E9E");
  });

  it("US-TEN-005 TC-4 (neg): a malformed EIN is refused inline and blocks the save", () => {
    const schema = companySchema(t);
    const base = draftFromProfile(BRAZOS_BEND);
    expect(collectFormErrors(schema, base).count).toBe(0);

    for (const bad of ["74-31826", "743182640X", "7431826401"]) {
      const result = collectFormErrors(schema, { ...base, ein: bad });
      expect(result.count).toBe(1);
      expect(result.errors.ein).toBe("Enter as NN-NNNNNNN.");
    }
    // BR-TEN-018 is format-only: a well-shaped but unregistered EIN passes here
    // and is never "verified" client-side.
    expect(collectFormErrors(schema, { ...base, ein: "00-0000000" }).count).toBe(0);
    // Blank is allowed — the field is optional until the checklist needs it.
    expect(collectFormErrors(schema, { ...base, ein: "" }).count).toBe(0);
  });

  it("US-TEN-005 TC-5 (neg): the logo guard refuses over-size and wrong-type files before upload", () => {
    // 4.8 MB PNG → the 413 case.
    expect(logoProblem({ size: 4_800_000, type: "image/png" })).toBe("too_large");
    expect(logoProblemKey("too_large")).toBe("settings.company.logo.tooLarge");
    // Anything but PNG or JPG is the 415 case.
    expect(logoProblem({ size: 1000, type: "text/html" })).toBe("unsupported_type");
    expect(logoProblem({ size: 1000, type: "image/gif" })).toBe("unsupported_type");
    expect(logoProblemKey("unsupported_type")).toBe("settings.company.logo.badType");
    // DEF-TEN-10618 (PO 2026-10-27, "Allow PNG, JPG"): an SVG is refused in the
    // browser with its OWN sentence — by type, and by name when the browser
    // sends no type — and nothing is uploaded.
    expect(logoProblem({ size: 180_000, type: "image/svg+xml" })).toBe("svg");
    expect(logoProblem({ size: 180_000, type: "", name: "bbu-logo.svg" })).toBe("svg");
    expect(logoProblem({ size: 180_000, type: "image/png", name: "evil.SVG" })).toBe("svg");
    expect(logoProblemKey("svg")).toBe("settings.company.logo_svg_not_accepted");
    expect(t("settings.company.logo_svg_not_accepted")).toBe("SVG files aren't accepted. Use PNG or JPG.");
    // PNG and JPG pass the client guard.
    expect(logoProblem({ size: 180_000, type: "image/jpeg", name: "logo.jpg" })).toBeNull();
    expect(logoProblem({ size: 180_000, type: "image/png", name: "logo.png" })).toBeNull();
    expect(LOGO_TYPES).toEqual(["image/png", "image/jpeg"]);
    expect(logoProblemKey(null)).toBeNull();
    // The picker offers PNG and JPG only, and the drop line says so.
    const html = renderTab(BRAZOS_BEND);
    expect(html).toContain('accept="image/png,image/jpeg"');
    expect(html).toContain("Logo — PNG or JPG, max 2 MB");
    expect(html).not.toContain("SVG");
    // Exactly at the limit is allowed; one byte over is not.
    expect(logoProblem({ size: LOGO_MAX_BYTES, type: "image/png" })).toBeNull();
    expect(logoProblem({ size: LOGO_MAX_BYTES + 1, type: "image/png" })).toBe("too_large");
  });

  it("BR-TEN-017: the tab states that issued documents keep what was printed, and offers no re-render", () => {
    const html = renderTab(BRAZOS_BEND);
    expect(html).toContain("Bills already issued keep what they were printed with.");
    expect(html.toLowerCase()).not.toContain("re-render");
  });

  it("BR-SHL-025: a view-only role gets a disabled Save with the reason attached", () => {
    const html = renderTab(BRAZOS_BEND, true);
    expect(html).toContain("Your role can view this, but not change it.");
    expect(html).toContain("disabled");
  });

  it("hex colors and the support email are validated in the same shape the server enforces", () => {
    const schema = companySchema(t);
    const base = draftFromProfile(BRAZOS_BEND);
    expect(collectFormErrors(schema, { ...base, brand_primary_hex: "1B5E9E" }).count).toBe(1);
    expect(collectFormErrors(schema, { ...base, brand_primary_hex: "#GGGGGG" }).count).toBe(1);
    expect(collectFormErrors(schema, { ...base, brand_primary_hex: "" }).count).toBe(0);
    expect(collectFormErrors(schema, { ...base, support_email: "help@" }).count).toBe(1);
  });

  it("CR-199-BRC10 S5: the logo link is https only, and the field is on the Brand panel", () => {
    const schema = companySchema(t);
    const base = draftFromProfile(BRAZOS_BEND);
    expect(base.brand_logo_link_url).toBe("");
    const errorsFor = (v: string) =>
      collectFormErrors(schema, { ...base, brand_logo_link_url: v }).count;
    expect(errorsFor("")).toBe(0);
    expect(errorsFor("https://brazosbendutilities.com")).toBe(0);
    expect(errorsFor("https://brazosbendutilities.com/pay?x=1")).toBe(0);
    expect(errorsFor("http://brazosbendutilities.com")).toBe(1);
    expect(errorsFor("javascript:alert(1)")).toBe(1);
    expect(errorsFor('https://x.example/"onmouseover=')).toBe(1);
    expect(errorsFor("https://user@x.example")).toBe(1);
    const html = renderTab({ ...BRAZOS_BEND, brand_logo_link_url: "https://brazosbendutilities.com" });
    expect(html).toContain('id="brand_logo_link_url"');
    expect(html).toContain("Logo link");
    expect(html).toContain('value="https://brazosbendutilities.com"');
    // A save sends only what changed, and an emptied link clears to null.
    const original = draftFromProfile({ ...BRAZOS_BEND, brand_logo_link_url: "https://a.example" });
    expect(companyChanges({ ...original, brand_logo_link_url: "" }, original)).toEqual({
      brand_logo_link_url: null,
    });
  });

  it("US-TEN-005 TC-5: a valid PNG is accepted and posted — the upload is real now", async () => {
    // The endpoint landed, so a file that passes the BR-TEN-019 guard actually
    // goes somewhere. It rides as MULTIPART through the ONE client: the part
    // name is the server's own, and no Content-Type is forced (only the browser
    // can write the boundary).
    let seen: { path: string; body: unknown; contentType: string | undefined } | null = null;
    const client = createApiClient({
      tenant: "brazosbend", // the URL's tenant segment (PO 2026-08-10)
      fetchImpl: async (input, init) => {
        seen = {
          path: String(input),
          body: init?.body,
          contentType: (init?.headers as Record<string, string> | undefined)?.["Content-Type"],
        };
        return new Response(
          JSON.stringify({ logo_file_id: "sha256:9f2c41ab", content_type: "image/png", size_bytes: 180_000 }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        );
      },
    });
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "bbu-logo.png", {
      type: "image/png",
    });
    const stored = await uploadCompanyLogo(file, client);
    expect(stored).toEqual({
      logo_file_id: "sha256:9f2c41ab",
      content_type: "image/png",
      size_bytes: 180_000,
    });
    expect(seen!.path).toBe("/api/brazosbend/settings/company/logo");
    expect(seen!.body).toBeInstanceOf(FormData);
    expect((seen!.body as FormData).get(COMPANY_LOGO_FIELD)).toBe(file);
    expect(seen!.contentType).toBeUndefined();
  });

  it("BR-TEN-019: the server's 413 and 415 render as the file field's own refusal", () => {
    // Both arrive as B12 r1 HTTP-series envelopes (`code: null`, no catalog
    // code) — the screen renders the server's words, with its own numbers.
    const tooLarge = new ApiError(413, {
      code: null,
      message_key: "settings.company.logo_too_large",
      params: { max_bytes: 2_097_152, size: 4_800_000 },
      br_ref: "BR-TEN-019",
    });
    expect(apiErrorText(tooLarge, t)).toBe("That file is over the 2 MB limit.");
    expect(refusalOf(tooLarge, t).brRef).toBe("BR-TEN-019");

    const badType = new ApiError(415, {
      code: null,
      message_key: "settings.company.logo_type_not_allowed",
      params: { allowed: ["image/jpeg", "image/png"], declared: "image/gif" },
      br_ref: "BR-TEN-019",
    });
    expect(apiErrorText(badType, t)).toBe("That file type isn't accepted. Use PNG or JPG.");

    // …and the 422 an SVG sanitizer refusal comes back as.
    const scripted = new ApiError(422, {
      code: "VAL-002",
      message_key: "settings.company.logo_svg_dtd_forbidden",
      br_ref: "BR-TEN-019",
    });
    expect(apiErrorText(scripted, t)).toContain("declares a document type");
  });

  it("BR-TEN-019: the panel states what is ON FILE, and offers no remove control", () => {
    const withLogo: CompanyProfile = {
      ...BRAZOS_BEND,
      logo_file_id: "sha256:9f2c41ab",
      logo: { logo_file_id: "sha256:9f2c41ab", content_type: "image/svg+xml", size_bytes: 184_320 },
      has_logo: true,
      logo_ref: null,
    };
    const html = renderTab(withLogo);
    expect(html).toContain("On file: SVG, 180 KB.");
    // DEF-TEN-10636 — the stored reference is a database id, never shown
    // (B14 rule 31). This line asserted the opposite until 2.605.
    expect(html).not.toContain("sha256:9f2c41ab");
    // There is no DELETE on this resource, so there is no control for one.
    expect(html).not.toContain("Remove logo");
    // ⚠ THIS ASSERTION USED TO BE `expect(html).not.toContain("<img")`, with the
    // comment *"nothing streams the bytes back, so nothing pretends to show the
    // image"*. That was accurate and it was the defect (DEF-192): the screen a
    // utility uses to confirm its branding could not show the branding. CR-048
    // wave D built the read route, and the preview draws the real logo — but
    // only where a tenant is in the URL, which this `node`-environment suite
    // has no window to carry. The drawn <img> and its src are asserted in
    // SettingsCompanyLogo.dom.test.tsx; here the fall-back is what is pinned,
    // and it is a real behaviour: no tenant in scope means no logo URL, so the
    // generated mark is drawn rather than a broken image.
    expect(html).toContain(">BB<");

    const empty = renderTab(BRAZOS_BEND);
    expect(empty).toContain("No logo on file yet.");
  });

  // ── CR-048 wave D / DEF-195 — the generated mark ─────────────────────────
  it("DEF-195: with no logo the letterhead draws TWO LETTERS, not an empty block", () => {
    const html = renderTab(BRAZOS_BEND);
    // The mark itself: the trading name's initials, in the tenant's colour,
    // with the ink the product chose so they can be read on it.
    expect(html).toContain(">BB<");
    expect(html).toContain("background-color:#1B5E9E");
    expect(html).toContain("color:#FFFFFF");
    // …and the preview SAYS which of the two things it is showing, which is
    // what the old identical-either-way square could never do.
    expect(html).toContain("No logo on file, so bills and notices show these two letters");
    expect(html).toContain("We never change your color.");
  });

  it("DEF-195: the letters come from the TRADING name, falling back to the legal name", () => {
    const traded = renderTab({ ...BRAZOS_BEND, dba_name: "Hilltop Power" });
    expect(traded).toContain(">HP<");

    const legalOnly = renderTab({ ...BRAZOS_BEND, dba_name: "" });
    expect(legalOnly).toContain(">BB<"); // "Brazos Bend Utility District No. 1"
  });

  it("OQ-800(a): a pale brand colour gets BLACK letters — their colour, our ink", () => {
    // The exact colour the open question names: #F5E9A0 with white text is
    // about 1.3:1 and unreadable. Nothing here changes the tenant's colour.
    const pale = renderTab({ ...BRAZOS_BEND, brand_primary_hex: "#F5E9A0" });
    expect(pale).toContain("background-color:#F5E9A0");
    expect(pale).toContain("color:#000000");
    expect(pale).not.toContain("color:#FFFFFF");
  });

  it("no brand colour is not a licence to invent one — the mark falls back to TOKENS", () => {
    const colourless = renderTab({ ...BRAZOS_BEND, brand_primary_hex: "" });
    expect(colourless).toContain("var(--color-neutral-300)");
    expect(colourless).toContain("var(--color-text)");
    expect(colourless).toContain(">BB<");
  });

  it("the size line is display-only formatting, and says nothing it does not know", () => {
    expect(formatLogoSize(512)).toBe("512 B");
    expect(formatLogoSize(184_320)).toBe("180 KB");
    expect(formatLogoSize(2_097_152)).toBe("2.0 MB");
    // The server can serve a null size; "0 KB" would be a claim, so say nothing.
    expect(formatLogoSize(null)).toBeNull();
  });

  it("DEF-TEN-10636: the type line is the word a person uses, never the MIME string", () => {
    expect(formatLogoType("image/png")).toBe("PNG");
    expect(formatLogoType("image/jpeg")).toBe("JPG");
    expect(formatLogoType("image/svg+xml")).toBe("SVG");
    expect(formatLogoType("image/webp")).toBe("WEBP");
  });

  it.todo(
    "US-TEN-005 TC-3: a bill issued yesterday still shows the OLD remit-to — server document rendering (BR-TEN-017), not a screen behaviour",
  );
  it.todo(
    "US-TEN-005 TC-6 (neg): the unsaved-changes prompt on tab navigation — router-blocker scope, browser test",
  );
  it.todo("US-TEN-005 TC-7 (isolation): cross-tenant EIN/logo invisibility — server/RLS scope (G5)");
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-005@0733260 (story+rules snapshot hash — EP-TEN-05)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-09 by story-coder (frontend integration lane: the logo upload is real) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
