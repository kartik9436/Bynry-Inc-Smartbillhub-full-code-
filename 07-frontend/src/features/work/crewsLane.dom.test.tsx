// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — P3.49 (three lists), P3.43 (Add
//           crew member), P3.27 (Add a crew), Add a contractor, P3.45 (a
//           technician's Jobs), P3.48 (Certifications as a table, add and
//           renew), ruling 27 (Performance and *This month*).
// Images:   05-prototype/work-backoffice-2026-10-04/images/25–34
// Rules:    CR-168 §7 — every body served here is a RECORDING of the real
//           server (`__fixtures__/server/`, written by
//           `10-scripts/cr168_capture_work_shapes.py`), never typed here.
// ───────────────────────────────────────────────────────
//
// ⚠ **THE WITNESSES ARE READ FROM THE RECORDINGS**, so a re-recording on
// another seed moves them with it. Each case first proves the recorded body
// arrived (a value only it carries is on screen), because a screen that never
// mounted and one that mounted empty look the same to a `queryBy…`.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
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
import SKILLS from "./__fixtures__/server/work.lookups.work_skills.json";
import CERT_TYPES from "./__fixtures__/server/work.lookups.certification_types.json";
import JOBS from "./__fixtures__/server/work.technician.jobs.json";
import JOBS_OPEN from "./__fixtures__/server/work.technician.jobs.open.json";
import JOBS_DONE from "./__fixtures__/server/work.technician.jobs.done.json";
import PERFORMANCE_ALL from "./__fixtures__/server/work.technician.performance.json";
import PERFORMANCE from "./__fixtures__/server/work.technician.performance.month.json";

const TENANT = "brazosbend";

interface Call {
  method: string;
  path: string;
  query?: Record<string, unknown>;
  body?: unknown;
}

function recordedServer(calls: Call[], options: { blocks?: boolean } = {}): ApiClient {
  const watch = options.blocks
    ? { ...CERT_WATCH, policy: "block", blocks: true, windows: CERT_WATCH.windows.map((w) => ({ ...w, entries: w.entries.map((e) => ({ ...e, blocked_template_types: 4 })) })) }
    : CERT_WATCH;
  const ok = (data: unknown): ApiResponse<unknown> => ({ status: 200, data, etag: null, notModified: false });
  const get = async (path: string, opts?: { query?: Record<string, unknown> }) => {
    const query = opts?.query ?? {};
    calls.push({ method: "GET", path, query });
    if (path === "/work/crews") {
      if (query.view === "crews") return ok(CREWS);
      if (query.view === "contractors") return ok(CONTRACTORS);
      if (query.view === "technicians") return ok(TECHNICIANS);
      throw new Error("the Crews page read /work/crews without a view");
    }
    if (path === "/work/certification-watch") return ok(watch);
    if (path === "/work/technicians") return ok(STAFF);
    if (path === "/lookups/work_skills") return ok(SKILLS);
    if (path === "/lookups/certification_types") return ok(CERT_TYPES);
    if (path === `/work/technicians/${TECHNICIAN.slug}`) return ok(TECHNICIAN);
    if (path === `/work/technicians/${TECHNICIAN.slug}/jobs`) {
      if (query["f.state"] === "open") return ok(JOBS_OPEN);
      if (query["f.state"] === "done") return ok(JOBS_DONE);
      return ok(JOBS);
    }
    if (path === `/work/technicians/${TECHNICIAN.slug}/performance`) {
      return ok(query.period ? PERFORMANCE : PERFORMANCE_ALL);
    }
    throw new Error(`no recording for GET ${path}`);
  };
  const write = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, body });
    if (path === "/work/crews") return { ...ok({ ...CREWS.results[0], id: "new-crew", name: (body as { name: string }).name }), status: 201 };
    if (path.startsWith("/work/technicians/")) return ok(TECHNICIAN);
    return { ...ok(CREWS.results[0]), status: 201 };
  };
  return {
    get,
    post: write("POST"),
    put: write("PUT"),
    patch: write("PATCH"),
    delete: write("DELETE"),
    del: write("DELETE"),
  } as unknown as ApiClient;
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

const crewsAt = (query = "") => `/${TENANT}/work/crews${query}`;
const CREWS_PATTERN = "/:tenant/work/crews";

function headerTexts(): string[] {
  // The sort glyph a sortable header carries is not part of its label.
  return Array.from(document.querySelectorAll("thead th")).map((th) => (th.textContent ?? "").replace(/[▲▼↑↓]/g, "").trim());
}

afterEach(cleanup);

describe("ruling 30 — Crews is THREE lists (images 25, 27, 28)", () => {
  it("opens on Technicians, asks the server for that list alone, and badges all three", async () => {
    const calls: Call[] = [];
    mount(crewsAt(), CREWS_PATTERN, <CrewsPage client={recordedServer(calls)} />);
    await screen.findAllByText(TECHNICIANS.results[0].name);
    const reads = calls.filter((c) => c.path === "/work/crews");
    expect(reads.every((c) => c.query?.view === "technicians")).toBe(true);
    const strip = document.querySelector('[data-segmented="crews-view"]') as HTMLElement;
    expect(strip).not.toBeNull();
    const segments = Array.from(strip.querySelectorAll("[data-segment]")).map((b) => (b.textContent ?? "").replace(/\s+/g, " ").trim());
    expect(segments).toEqual([
      `Technicians${TECHNICIANS.counts.technicians}`,
      `Crews${TECHNICIANS.counts.crews}`,
      `Contractors${TECHNICIANS.counts.contractors}`,
    ]);
  });

  it("Technicians draws image 25's seven columns in order, with each person's crew and job title", async () => {
    mount(crewsAt(), CREWS_PATTERN, <CrewsPage client={recordedServer([])} />);
    await screen.findAllByText(TECHNICIANS.results[0].name);
    expect(headerTexts().slice(0, 7)).toEqual(["Technician", "Crew", "Job title", "Skills", "Certifications", "Shift", "Status"]);
    const first = TECHNICIANS.results[0];
    const row = screen.getByText(first.name).closest("tr") as HTMLElement;
    expect(within(row).getByText(first.crew!.name)).toBeTruthy();
    expect(within(row).getByText(first.role_label!)).toBeTruthy();
    // the name links by SLUG under the real tenant path (B14 rule 31)
    expect(screen.getByText(first.name).closest("a")?.getAttribute("href")).toBe(`/${TENANT}/work/crews/${first.slug}`);
  });

  it("Crews draws image 27's columns, each crew's counted members, and both add buttons", async () => {
    const calls: Call[] = [];
    mount(crewsAt("?view=crews"), CREWS_PATTERN, <CrewsPage client={recordedServer(calls)} />);
    await screen.findAllByText(CREWS.results[0].name);
    expect(calls.some((c) => c.path === "/work/crews" && c.query?.view === "crews")).toBe(true);
    expect(headerTexts().slice(0, 6)).toEqual(["Crew", "Members", "Does", "Skills", "Shift", "Status"]);
    const first = CREWS.results[0];
    const row = screen.getByText(first.name).closest("tr") as HTMLElement;
    // Lane CREWS-2 (round 6) draws the names beside the count (image 27's
    // *D. Ortiz · R. Patel · 2 people*, SRV-4's `member_names`), so the count
    // is no longer a text node of its own; `crews2Lane.dom.test.tsx` owns the
    // whole cell.
    expect(row.querySelector(`[data-crew-members="${first.members}"]`)?.textContent).toContain(`${first.members} people`);
    expect(within(row).getByText(first.role_label!)).toBeTruthy();
    expect(screen.getByRole("button", { name: "+ Add crew member" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "+ Add a crew" })).toBeTruthy();
    expect(document.querySelector("[data-cert-watch]")).toBeNull();
  });

  it("Contractors draws image 28's columns, *By arrangement*, and only *+ Add a contractor*", async () => {
    mount(crewsAt("?view=contractors"), CREWS_PATTERN, <CrewsPage client={recordedServer([])} />);
    await screen.findAllByText(CONTRACTORS.results[0].name);
    expect(headerTexts().slice(0, 4)).toEqual(["Contractor", "Skills", "Hours", "Status"]);
    expect(screen.getByText("By arrangement")).toBeTruthy();
    expect(screen.getByRole("button", { name: "+ Add a contractor" })).toBeTruthy();
    // ruling 36 — a contractor's people wait for the field-app document
    expect(screen.queryByRole("button", { name: "+ Add crew member" })).toBeNull();
  });

  it("choosing a list asks the server for THAT list and writes it to the address", async () => {
    const calls: Call[] = [];
    mount(crewsAt(), CREWS_PATTERN, <CrewsPage client={recordedServer(calls)} />);
    await screen.findAllByText(TECHNICIANS.results[0].name);
    fireEvent.click(document.querySelector('[data-segment="crews"]') as HTMLElement);
    await screen.findAllByText(CREWS.results[0].name);
    expect(calls.some((c) => c.path === "/work/crews" && c.query?.view === "crews")).toBe(true);
  });

  it("the watch WARNS and never says blocked, even where the server still says blocks (PO answer 2, 2026-10-04)", async () => {
    mount(crewsAt(), CREWS_PATTERN, <CrewsPage client={recordedServer([], { blocks: true })} />);
    const watch = await screen.findByText("Certification watch");
    const box = watch.closest("[data-cert-watch]") as HTMLElement;
    const entry = CERT_WATCH.windows[0].entries[0];
    expect(box.textContent).toContain(entry.technician);
    expect(box.textContent ?? "").not.toMatch(/blocked/i);
    expect(document.querySelector("[data-cert-blocked]")).toBeNull();
  });
});

describe("DEF-WRK-9672 — a crew's day pack is offered on its row, as the technician page offers theirs", () => {
  it("Print day… on a crew opens the dialog and prints that crew's day by its slug", async () => {
    const opened: string[] = [];
    const spy = vi.spyOn(window, "open").mockImplementation((url?: string | URL) => {
      opened.push(String(url));
      return null;
    });
    mount(crewsAt("?view=crews"), CREWS_PATTERN, <CrewsPage client={recordedServer([])} />);
    const first = CREWS.results[0];
    await screen.findAllByText(first.name);
    const row = screen.getByText(first.name).closest("tr") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Print day…" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(`Day pack · ${first.name}`)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Print" }));
    await waitFor(() => expect(opened).toHaveLength(1));
    expect(opened[0]).toContain(`/${TENANT}/work/print/day-pack?date=`);
    expect(opened[0]).toContain(`&crew=${first.slug}`);
    spy.mockRestore();
  });
});

describe("ruling 26 — Add crew member (image 26)", () => {
  it("offers the utility's logins with their role and status, and puts the person on the chosen crew", async () => {
    const calls: Call[] = [];
    mount(crewsAt(), CREWS_PATTERN, <CrewsPage client={recordedServer(calls)} />);
    await screen.findAllByText(TECHNICIANS.results[0].name);
    fireEvent.click(screen.getByRole("button", { name: "+ Add crew member" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Add crew member" })).toBeTruthy();
    const candidate = STAFF.results.find((row) => !row.has_profile && row.status !== "deactivated") ?? STAFF.results[0];
    const name = candidate.full_name ?? candidate.email;
    const person = within(dialog).getByLabelText(/Person/);
    fireEvent.focus(person);
    fireEvent.change(person, { target: { value: name } });
    fireEvent.click(await within(dialog).findByText(name, { selector: "[role=option] *, [role=option]" }));
    const crew = CREWS.results[1];
    fireEvent.change(within(dialog).getByLabelText("Crew"), { target: { value: crew.id } });
    fireEvent.change(within(dialog).getByLabelText("Job title"), { target: { value: "Field technician" } });
    fireEvent.change(within(dialog).getByLabelText("Van"), { target: { value: "Unit 14" } });
    expect(within(dialog).getByText(`Adding ${name}`)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: /Add crew member/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.path).toBe(`/work/crews/${crew.id}/members`);
    expect(post.body).toMatchObject({ user_id: candidate.user_id, role_label: "Field technician", van: "Unit 14" });
  });
});

describe("ruling 31 — Add a crew (image 29) and Add a contractor (image 30)", () => {
  it("Add a crew writes the crew, then its skills, then moves each member onto it", async () => {
    const calls: Call[] = [];
    mount(crewsAt("?view=crews"), CREWS_PATTERN, <CrewsPage client={recordedServer(calls)} />);
    await screen.findAllByText(CREWS.results[0].name);
    fireEvent.click(screen.getByRole("button", { name: "+ Add a crew" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Name/), { target: { value: "Field crew C" } });
    fireEvent.change(within(dialog).getByLabelText("Does"), { target: { value: "Leak crew" } });
    const mover = TECHNICIANS.results.find((row) => row.crew !== null)!;
    fireEvent.change(await within(dialog).findByLabelText("Add a member…"), { target: { value: mover.id } });
    const skill = SKILLS.results[0];
    fireEvent.change(within(dialog).getByLabelText("Add a skill…"), { target: { value: skill.id } });
    expect(within(dialog).getByText(`${mover.name} leaves ${mover.crew!.name}.`, { exact: false })).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: /Add crew/ }));
    await waitFor(() => expect(calls.filter((c) => c.method !== "GET").length).toBe(3));
    const writes = calls.filter((c) => c.method !== "GET");
    expect(writes[0]).toMatchObject({ method: "POST", path: "/work/crews", body: { kind: "crew", name: "Field crew C", role_label: "Leak crew" } });
    expect(writes[1]).toMatchObject({ method: "PUT", path: "/work/crews/new-crew/skills", body: { skills: [{ skill_id: skill.id }] } });
    expect(writes[2]).toMatchObject({ method: "PATCH", path: `/work/technicians/${mover.slug}`, body: { crew_id: "new-crew" } });
  });

  it("Add a contractor sends kind contractor, its phone and email, and no hours when by arrangement", async () => {
    const calls: Call[] = [];
    mount(crewsAt("?view=contractors"), CREWS_PATTERN, <CrewsPage client={recordedServer(calls)} />);
    await screen.findAllByText(CONTRACTORS.results[0].name);
    fireEvent.click(screen.getByRole("button", { name: "+ Add a contractor" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Name/), { target: { value: "Hill Country Excavation" } });
    fireEvent.change(within(dialog).getByLabelText("Phone"), { target: { value: "(512) 555-0147" } });
    fireEvent.change(within(dialog).getByLabelText("Email"), { target: { value: "dispatch@hcexcavation.example" } });
    expect(within(dialog).getByText("Adding Hill Country Excavation")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: /Add contractor/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")).toMatchObject({
      path: "/work/crews",
      body: { kind: "contractor", name: "Hill Country Excavation", phone: "(512) 555-0147", email: "dispatch@hcexcavation.example", shift_start: null, shift_end: null },
    });
  });
});

const techAt = (tab?: string) => `/${TENANT}/work/crews/${TECHNICIAN.slug}${tab ? `?tab=${tab}` : ""}`;
const TECH_PATTERN = "/:tenant/work/crews/:slug";

describe("ruling 27/28 — one technician's four tabs (images 31–34)", () => {
  it("draws Overview · Jobs · Certifications · Performance, in that order", async () => {
    mount(techAt(), TECH_PATTERN, <TechnicianDetailPage client={recordedServer([])} />);
    await screen.findAllByText(TECHNICIAN.name);
    const tabs = Array.from(document.querySelectorAll("[role=tab]")).map((tab) => (tab.textContent ?? "").trim());
    // CR-193-BRC10 (MQ-040 step 1) appends *Timesheets* after the drawn four.
    expect(tabs).toEqual(["Overview", "Jobs", "Certifications", "Performance", "Timesheets"]);
  });

  it("Overview's *This month* carries the server's figures (image 31)", async () => {
    mount(techAt(), TECH_PATTERN, <TechnicianDetailPage client={recordedServer([])} />);
    const panel = (await screen.findByText("This month")).closest("section") as HTMLElement;
    const month = TECHNICIAN.this_month;
    expect(panel.textContent).toContain(`Jobs closed ${month.closed}`);
    expect(panel.textContent).toContain(`On time ${month.on_time} of ${month.on_time_of}`);
    expect(panel.textContent).toContain("First-visit completion");
  });

  it("Jobs lists every recorded job and Open / Done ask the server for that state (image 32)", async () => {
    const calls: Call[] = [];
    mount(techAt("jobs"), TECH_PATTERN, <TechnicianDetailPage client={recordedServer(calls)} />);
    const first = JOBS.results[0];
    await screen.findAllByText(first.order_no!);
    // The drawn *CLOSED* column is always there: the server has sent
    // `completed_at` on every row since lane SRV-4, which expired the hold this
    // case was written to fire on (it read `served ? 7 : 6` until then).
    expect(JOBS.results.every((row) => "completed_at" in row)).toBe(true);
    expect(headerTexts().slice(0, 7)).toEqual(["Order", "Type", "Address", "Status", "Due", "Closed", "Outcome"]);
    // an order number opens that order's own page, by its address
    expect(screen.getAllByText(first.order_no!)[0].closest("a")?.getAttribute("href")).toBe(
      `/${TENANT}/work/orders/${first.id}`,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Done" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/jobs") && c.query?.["f.state"] === "done")).toBe(true),
    );
  });

  it("Certifications is a table with add and renew; a run-out one WARNS (image 33, PO answer 2)", async () => {
    const calls: Call[] = [];
    mount(techAt("certifications"), TECH_PATTERN, <TechnicianDetailPage client={recordedServer(calls)} />);
    const cert = TECHNICIAN.certifications[0];
    await screen.findAllByText(cert.name!);
    expect(headerTexts().slice(0, 3)).toEqual(["Certification", "Expires", "Status"]);
    expect(screen.getByRole("button", { name: "+ Add certification" })).toBeTruthy();
    // Image 33 draws the row action as ✎ Edit (DEF-WRK-9664).
    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Expires/), { target: { value: "2030-01-31" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Renew/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    const put = calls.find((c) => c.method === "PUT")!;
    expect(put.path).toBe(`/work/technicians/${TECHNICIAN.slug}/certifications`);
    const sent = (put.body as { certifications: { certification_type_id: string; expires_on: string }[] }).certifications;
    expect(sent).toHaveLength(TECHNICIAN.certifications.length);
    expect(sent.find((c) => c.certification_type_id === cert.certification_type_id)?.expires_on).toBe("2030-01-31");
  });

  it("Performance draws the four tiles and the by-job-type rows from the server (image 34)", async () => {
    mount(techAt("performance"), TECH_PATTERN, <TechnicianDetailPage client={recordedServer([])} />);
    await screen.findByText("Jobs closed");
    const tiles = document.querySelector("[data-technician-tiles]") as HTMLElement;
    expect(tiles.textContent).toContain(String(PERFORMANCE.tiles.closed));
    for (const label of ["Jobs closed", "On time", "First-visit completion", "Avg vs estimate"]) {
      expect(within(tiles).getAllByText(label).length).toBeGreaterThan(0);
    }
    for (const row of PERFORMANCE.results) {
      if (row.job_type) expect(screen.getAllByText(row.job_type).length).toBeGreaterThan(0);
    }
  });
});
