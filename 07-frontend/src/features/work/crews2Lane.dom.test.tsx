// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 6, lane CREWS-2 — the three facts lane SRV-4
//           serves (`2.513.0`) that the Crews screens did not yet draw:
//           image 27's member NAMES, image 26's *on Field crew A* beside each
//           login, image 33's PROOF column with attaching and opening a scan;
//           and DEF-WRK-9640 (the All time caption).
// Images:   05-prototype/work-backoffice-2026-10-04/images/26, 27, 33, 34
// Rules:    CR-168 §7 — every body served here is a RECORDING of the real
//           server (`__fixtures__/server/`), never typed here.
// ───────────────────────────────────────────────────────
//
// RED FIRST on `8badcb01c` (the screens as lane CREWS left them): 7 of 7 red —
// quoted in the lane report and CR-168 §22.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { CrewsPage } from "./CrewsPage";
import { TechnicianDetailPage } from "./TechnicianDetailPage";

import TECHNICIANS from "./__fixtures__/server/work.crews.technicians.json";
import CREWS from "./__fixtures__/server/work.crews.crews.json";
import CONTRACTORS from "./__fixtures__/server/work.crews.contractors.json";
import CERT_WATCH from "./__fixtures__/server/work.certification-watch.json";
import TECHNICIAN from "./__fixtures__/server/work.technician.json";
import STAFF from "./__fixtures__/server/work.technicians.json";
import CERT_TYPES from "./__fixtures__/server/work.lookups.certification_types.json";
import PERFORMANCE_ALL from "./__fixtures__/server/work.technician.performance.json";
import PERFORMANCE from "./__fixtures__/server/work.technician.performance.month.json";

import de from "@/i18n/locales/de.json";
import en from "@/i18n/locales/en.json";
import es from "@/i18n/locales/es.json";
import esMX from "@/i18n/locales/es-MX.json";
import fr from "@/i18n/locales/fr-FR.json";
import hi from "@/i18n/locales/hi.json";
import id from "@/i18n/locales/id-ID.json";
import it_ from "@/i18n/locales/it-IT.json";
import ja from "@/i18n/locales/ja-JP.json";
import ko from "@/i18n/locales/ko-KR.json";
import pt from "@/i18n/locales/pt-BR.json";

const TENANT = "brazosbend";

interface Call {
  method: string;
  path: string;
  query?: Record<string, unknown>;
  body?: unknown;
}

function recordedServer(calls: Call[]): ApiClient {
  const ok = (data: unknown): ApiResponse<unknown> => ({ status: 200, data, etag: null, notModified: false });
  const get = async (path: string, opts?: { query?: Record<string, unknown> }) => {
    const query = opts?.query ?? {};
    calls.push({ method: "GET", path, query });
    if (path === "/work/crews") {
      if (query.view === "crews") return ok(CREWS);
      if (query.view === "contractors") return ok(CONTRACTORS);
      return ok(TECHNICIANS);
    }
    if (path === "/work/certification-watch") return ok(CERT_WATCH);
    if (path === "/work/technicians") return ok(STAFF);
    if (path === "/lookups/certification_types") return ok(CERT_TYPES);
    if (path === `/work/technicians/${TECHNICIAN.slug}`) return ok(TECHNICIAN);
    if (path === `/work/technicians/${TECHNICIAN.slug}/performance`) {
      return ok(query.period ? PERFORMANCE : PERFORMANCE_ALL);
    }
    throw new Error(`no recording for GET ${path}`);
  };
  const write = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, body });
    if (path.endsWith("/proof")) {
      const file = (body as FormData).get("file") as File;
      const held = TECHNICIAN.certifications.find((c) => c.proof !== null)!.proof!;
      return { ...ok({ ...held, name: file.name, content_type: file.type, bytes: file.size }), status: 201 };
    }
    return ok(TECHNICIAN);
  };
  return { get, post: write("POST"), put: write("PUT"), patch: write("PATCH"), delete: write("DELETE") } as unknown as ApiClient;
}

function mount(path: string, pattern: string, element: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={pattern} element={element} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const CREWS_PATTERN = "/:tenant/work/crews";
const TECH_PATTERN = "/:tenant/work/crews/:slug";
const techAt = (tab: string) => `/${TENANT}/work/crews/${TECHNICIAN.slug}?tab=${tab}`;

function headerTexts(): string[] {
  return Array.from(document.querySelectorAll("thead th")).map((th) => (th.textContent ?? "").replace(/[▲▼↑↓]/g, "").trim());
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  void i18n.changeLanguage("en");
});

describe("image 27 — a crew's members by name", () => {
  it("draws *D. Ortiz · R. Patel · 2 people* from member_names and the counted members", async () => {
    mount(`/${TENANT}/work/crews?view=crews`, CREWS_PATTERN, <CrewsPage client={recordedServer([])} />);
    await screen.findAllByText(CREWS.results[0].name);
    for (const crew of CREWS.results) {
      expect(crew.member_names.length).toBeGreaterThan(0); // the recording carries names
      const row = screen.getByText(crew.name).closest("tr") as HTMLElement;
      const cell = row.querySelector("[data-crew-member-names]") as HTMLElement;
      expect(cell).not.toBeNull();
      expect(cell.textContent).toBe(`${crew.member_names.join(" · ")} · ${crew.members} people`);
    }
  });
});

describe("image 26 — the crew beside each login on the picker", () => {
  it("a login on a crew reads *on Field crew A*; one on none keeps its status", async () => {
    mount(`/${TENANT}/work/crews`, CREWS_PATTERN, <CrewsPage client={recordedServer([])} />);
    await screen.findAllByText(TECHNICIANS.results[0].name);
    fireEvent.click(screen.getByRole("button", { name: "+ Add crew member" }));
    const dialog = await screen.findByRole("dialog");
    const person = within(dialog).getByLabelText(/Person/);
    fireEvent.focus(person);
    const onCrew = STAFF.results.find((row) => row.crew !== null)!;
    const onNone = STAFF.results.find((row) => row.crew === null && row.status === "invited")!;
    const optionFor = async (name: string) => {
      fireEvent.change(person, { target: { value: name } });
      const label = await within(dialog).findByText(name, { selector: "[role=option] *" });
      return label.closest("[role=option]") as HTMLElement;
    };
    const crewed = await optionFor(onCrew.full_name!);
    expect(crewed.textContent).toContain(`on ${onCrew.crew!.name}`);
    expect(crewed.textContent).not.toContain("Invited");
    const loose = await optionFor(onNone.full_name!);
    expect(loose.textContent).toContain("Invited");
    expect(loose.textContent).not.toContain(" on ");
  });
});

describe("image 33 — a certificate's PROOF", () => {
  it("draws the PROOF column: the scan's name where one is held, a dash where none", async () => {
    const opened: string[] = [];
    vi.spyOn(window, "open").mockImplementation((url?: string | URL) => {
      opened.push(String(url));
      return null;
    });
    // The content route is built from the tenant of the URL the BROWSER is on
    // (`api/client.currentTenant`), exactly as in the product.
    window.history.pushState({}, "", techAt("certifications"));
    mount(techAt("certifications"), TECH_PATTERN, <TechnicianDetailPage client={recordedServer([])} />);
    const held = TECHNICIAN.certifications.find((c) => c.proof !== null)!;
    const bare = TECHNICIAN.certifications.find((c) => c.proof === null)!;
    await screen.findAllByText(held.name!);
    expect(headerTexts().slice(0, 4)).toEqual(["Certification", "Expires", "Status", "Proof"]);
    const heldRow = screen.getByText(held.name!).closest("tr") as HTMLElement;
    const link = within(heldRow).getByRole("button", { name: held.proof!.name });
    const bareRow = screen.getByText(bare.name!).closest("tr") as HTMLElement;
    expect(bareRow.querySelector("[data-certification-proof]")?.textContent).toBe("—");
    fireEvent.click(link);
    expect(opened).toHaveLength(1);
    expect(opened[0]).toContain(`/${TENANT}${held.proof!.url}`);
  });

  it("Edit attaches a scan: the dates are replaced, then the file is posted to the certificate", async () => {
    const calls: Call[] = [];
    mount(techAt("certifications"), TECH_PATTERN, <TechnicianDetailPage client={recordedServer(calls)} />);
    const bare = TECHNICIAN.certifications.find((c) => c.proof === null)!;
    await screen.findAllByText(bare.name!);
    const row = screen.getByText(bare.name!).closest("tr") as HTMLElement;
    // Image 33 draws the row's action as ✎ Edit, not Renew.
    expect(within(row).queryByRole("button", { name: "Renew" })).toBeNull();
    fireEvent.click(within(row).getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("PDF or photo, up to 10 MB.")).toBeTruthy();
    const scan = new File(["%PDF-1.4"], "traffic-card.pdf", { type: "application/pdf" });
    fireEvent.change(within(dialog).getByLabelText("Proof"), { target: { files: [scan] } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Renew/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const writes = calls.filter((c) => c.method !== "GET");
    expect(writes.map((c) => c.method)).toEqual(["PUT", "POST"]);
    expect(writes[1].path).toBe(`/work/technicians/${TECHNICIAN.slug}/certifications/${bare.certification_type_id}/proof`);
    expect(((writes[1].body as FormData).get("file") as File).name).toBe("traffic-card.pdf");
  });

  it("refuses a file that is not a PDF or photo, or is over 10 MB, before anything is sent", async () => {
    const calls: Call[] = [];
    mount(techAt("certifications"), TECH_PATTERN, <TechnicianDetailPage client={recordedServer(calls)} />);
    const held = TECHNICIAN.certifications.find((c) => c.proof !== null)!;
    await screen.findAllByText(held.name!);
    const row = screen.getByText(held.name!).closest("tr") as HTMLElement;
    // Image 33 draws the row's action as ✎ Edit, not Renew.
    expect(within(row).queryByRole("button", { name: "Renew" })).toBeNull();
    fireEvent.click(within(row).getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    // a renewal names the scan already on file
    expect(within(dialog).getByText(`On file: ${held.proof!.name}. Choose one to replace it.`)).toBeTruthy();
    const input = within(dialog).getByLabelText("Proof");
    fireEvent.change(input, { target: { files: [new File(["x"], "notes.txt", { type: "text/plain" })] } });
    expect(within(dialog).getByText("Choose a PDF or a photo.")).toBeTruthy();
    const big = new File(["x"], "huge.jpg", { type: "image/jpeg" });
    Object.defineProperty(big, "size", { value: 10 * 1024 * 1024 + 1 });
    fireEvent.change(input, { target: { files: [big] } });
    expect(within(dialog).getByText("The file is over 10 MB.")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: /Renew/ }));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
  });
});

describe("DEF-WRK-9640 — the All time caption", () => {
  it("All time reads *To date*, never *In All time*; a month keeps *In <month>*", async () => {
    mount(techAt("performance"), TECH_PATTERN, <TechnicianDetailPage client={recordedServer([])} />);
    await screen.findByText("Jobs closed");
    const tiles = () => document.querySelector("[data-technician-tiles]") as HTMLElement;
    await waitFor(() => expect(tiles().textContent).toMatch(/In \w/));
    fireEvent.change(screen.getByLabelText("Period"), { target: { value: "" } });
    await waitFor(() => expect(tiles().textContent).toContain("To date"));
    expect(tiles().textContent).not.toContain("In All time");
    expect(tiles().textContent).not.toContain("All time");
  });

  it("in every catalogue, All time has its own caption that is not the period word in a preposition", () => {
    const catalogues: Record<string, Record<string, string>> = {
      en, de, es, "es-MX": esMX, "fr-FR": fr, hi, "id-ID": id, "it-IT": it_, "ja-JP": ja, "ko-KR": ko, "pt-BR": pt,
    };
    for (const [lang, catalogue] of Object.entries(catalogues)) {
      const caption = catalogue["work.technician.performance.closedAllTime"];
      expect(caption, lang).toBeTruthy();
      const wrapped = catalogue["work.technician.performance.closedIn"].replace(
        "{{period}}",
        catalogue["work.technician.performance.allTime"],
      );
      expect(caption, lang).not.toBe(wrapped);
      expect(caption, lang).not.toContain("{{");
    }
  });
});
