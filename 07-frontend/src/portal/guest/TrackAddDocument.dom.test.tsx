// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-9049 — after a clerk's *Ask for more*, the applicant had no
//          way to send a second document from the portal (21-walk W14,
//          2026-10-02). Track said *More info needed* and nothing else.
// Screen:  CWP-012 (Track) — *Add a document*, shown only for a request in
//          `more_info` (`can_add_document` on the server's answer)
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import type { TrackView } from "../api/guestClient";

import { TrackAnything } from "./TrackAnything";

const ASKED: TrackView = {
  series: "request",
  reference: "SR-26-0024",
  status: "more_info",
  reported_at: "2026-10-02T04:06:53Z",
  submitted_at: "2026-10-02T04:06:53Z",
  closed_at: null,
  can_add_document: true,
  documents_left: 3,
};

const NOT_ASKED: TrackView = {
  ...ASKED,
  status: "submitted",
  can_add_document: false,
  documents_left: 0,
};

interface Posted {
  path: string;
  body: unknown;
}

function client(first: TrackView, afterUpload: TrackView, posted: Posted[]): ApiClient {
  return {
    get: async () => ({ data: undefined, status: 200 }),
    post: async (path: string, body: unknown) => {
      posted.push({ path, body });
      return { data: path.endsWith("/documents") ? afterUpload : first, status: 200 };
    },
    put: async () => ({ data: undefined, status: 200 }),
    patch: async () => ({ data: undefined, status: 200 }),
    del: async () => ({ data: undefined, status: 200 }),
  } as unknown as ApiClient;
}

async function lookUp(api: ApiClient): Promise<HTMLElement> {
  const { container } = render(
    <MemoryRouter initialEntries={["/pine-hill/portal/track"]}>
      <Routes>
        <Route path="/:tenant/portal/track" element={<TrackAnything client={api} />} />
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.change(container.querySelector("#cwp012-reference") as HTMLInputElement, {
    target: { value: "SR-26-0024" },
  });
  fireEvent.change(container.querySelector("#cwp012-second-fact") as HTMLInputElement, {
    target: { value: "77494" },
  });
  fireEvent.click(container.querySelector("button:not([disabled])") as HTMLButtonElement);
  await waitFor(() => expect(container.querySelector("[data-reference]")).not.toBeNull());
  return container as HTMLElement;
}

afterEach(cleanup);

describe("CWP-012 · Add a document when we asked for more (DEF-CWP-9049)", () => {
  it("offers Add a document for a request waiting on the applicant", async () => {
    const container = await lookUp(client(ASKED, ASKED, []));
    const box = container.querySelector("[data-track-add-document]");
    expect(box).not.toBeNull();
    expect(box?.querySelector('input[type="file"]')).not.toBeNull();
    expect(box?.textContent).toMatch(/Add a document/);
    expect(box?.textContent).toMatch(/3 files at most/);
  });

  it("offers nothing for a request nobody asked about", async () => {
    const container = await lookUp(client(NOT_ASKED, NOT_ASKED, []));
    expect(container.querySelector("[data-track-add-document]")).toBeNull();
    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it("sends the file with the same reference and second fact, and says it was sent", async () => {
    const posted: Posted[] = [];
    const container = await lookUp(client(ASKED, { ...ASKED, documents_left: 2 }, posted));
    const input = container.querySelector(
      '[data-track-add-document] input[type="file"]',
    ) as HTMLInputElement;
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "clearer-id.png", {
      type: "image/png",
    });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() =>
      expect(container.querySelector('[data-sent-file="clearer-id.png"]')).not.toBeNull(),
    );
    const upload = posted.find((one) => one.path === "/portal/public/track/documents");
    expect(upload).toBeDefined();
    const form = upload?.body as FormData;
    expect(form.get("reference")).toBe("SR-26-0024");
    expect(form.get("second_fact")).toBe("77494");
    expect((form.get("file") as File).name).toBe("clearer-id.png");
    expect(container.querySelector("[data-track-add-document]")?.textContent).toMatch(
      /2 files at most/,
    );
  });
});
