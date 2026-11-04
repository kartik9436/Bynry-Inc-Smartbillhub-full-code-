// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Change:   DEF-BIL-10531 — the bill email link's page
// Cases:    the secret is read from the FRAGMENT and never appears in any
//           request URL (it travels in the POST body) · the bill opens and
//           Download hands over the PDF the server sent · an unknown or expired
//           link shows the call-the-office dead end with the utility's number,
//           and so does a link that dies between opening and downloading · the
//           page is mounted under the REAL route pattern (`DEF-CWP-3925`)
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";

import type { BillLink } from "../api/billLinkClient";
import type { PortalFront } from "../api/guestClient";
import { BILL_LINK_ROUTE, BillLinkPage } from "./BillLinkPage";

const SECRET = "s3cret-token-value";

const FRONT: PortalFront = {
  tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: "#EC3013", brand_accent_hex: "#E15B47" },
  is_live: false,
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: null },
  locales: ["en", "es"],
  cards: [],
  links: { help: false, visit: false },
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
};

const OPEN: BillLink = {
  state: "open",
  utility_name: "Pine Hill Water & Power",
  bill_no: "BL-2026-000042",
  bill_date: "2026-10-22",
  due_date: "2026-11-12",
  expires_on: "2026-11-21",
};

const GONE: BillLink = { state: "unavailable", support_phone: "(512) 555-0100" };

function client(link: BillLink) {
  const get = vi.fn(async () => ({ data: FRONT, status: 200 }));
  const post = vi.fn(async () => ({ data: link, status: 200 }));
  return { api: { get, post } as unknown as ApiClient, get, post };
}

function pdfFetch() {
  return vi.fn(async () =>
    new Response("%PDF-1.4 kept", {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="BL-2026-000042.pdf"',
      },
    }),
  );
}

/** The page hands the browser a download: the blob through `createObjectURL`,
 *  the name through the anchor's `download`. Both are captured here. */
function draw(api: ApiClient, fetchImpl: typeof fetch) {
  vi.stubGlobal("fetch", fetchImpl);
  const blobs: Blob[] = [];
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: (blob: Blob) => {
      blobs.push(blob);
      return "blob:bill";
    },
  });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: () => undefined });
  const save = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    save(blobs[blobs.length - 1], this.download);
  });
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queries}>
      <MemoryRouter initialEntries={[`/pine-hill/portal/bill#token=${SECRET}`]}>
        <Routes>
          <Route
            path={`/:tenant/${BILL_LINK_ROUTE}`}
            element={<BillLinkPage client={api} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return save;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("DEF-BIL-10531 · the bill email link's page", () => {
  it("reads the secret from the fragment and POSTs it in the body, never in a URL", async () => {
    const { api, get, post } = client(OPEN);
    const fetchImpl = pdfFetch();
    const save = draw(api, fetchImpl as unknown as typeof fetch);

    expect(await screen.findByText("BL-2026-000042")).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/bill-links/open", { token: SECRET });

    await userEvent.click(screen.getByRole("button", { name: "Download bill" }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/api\/pine-hill\/bill-links\/document$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ token: SECRET });

    // Every address any request was made to — none carries the secret.
    const urls = [
      ...get.mock.calls.map((call) => String((call as unknown[])[0])),
      ...post.mock.calls.map((call) => String((call as unknown[])[0])),
      url,
    ];
    for (const one of urls) expect(one).not.toContain(SECRET);

    const [blob, filename] = save.mock.calls[0] as [Blob, string];
    expect(filename).toBe("BL-2026-000042.pdf");
    expect(await blob.text()).toBe("%PDF-1.4 kept");
  });

  it("shows the dead end with the utility's number for an unknown or expired link", async () => {
    const { api } = client(GONE);
    draw(api, pdfFetch() as unknown as typeof fetch);
    expect(await screen.findByText("This link has expired")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "(512) 555-0100" })).toHaveAttribute("href", "tel:5125550100");
    expect(screen.queryByRole("button", { name: "Download bill" })).toBeNull();
  });

  it("shows the dead end when the link dies between opening and downloading", async () => {
    const { api } = client(OPEN);
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(GONE), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const save = draw(api, fetchImpl as unknown as typeof fetch);
    await userEvent.click(await screen.findByRole("button", { name: "Download bill" }));
    expect(await screen.findByText("This link has expired")).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });
});
