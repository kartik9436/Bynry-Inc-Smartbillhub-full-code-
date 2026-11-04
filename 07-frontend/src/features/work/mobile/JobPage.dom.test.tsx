// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-042 TC-1..TC-4 (everything carried, nothing fetched) ·
//           US-WRK-043 TC-1/TC-2 (the phone's half of the safety lock)
//           Screen: Work-011
// Rules:    BR-WRK-037 (two of three ticked is LOCKED) · BR-WRK-038 (help
//           opens offline) · BR-WRK-042 (fetched at sync, never on tap) ·
//           B14 rule 31 · rule 33
// ───────────────────────────────────────────────────────
//
// ⚠ Mounted under the REAL path pattern (`DEF-CWP-3925`) — see TodayPage.test.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { MobileBundle } from "./mobileEndpoints";

vi.mock("./mobileEndpoints", async () => {
  const actual = await vi.importActual<typeof import("./mobileEndpoints")>("./mobileEndpoints");
  return { ...actual, loadJob: vi.fn(), syncJobQueue: vi.fn(), syncJob: vi.fn(), acceptJob: vi.fn() };
});
// `DEF-WRK-9636` / `DEF-WRK-9619` — the acts a technician takes ON this page.
// CR-168-BRC10 §F (FIELD-2): every one goes through `capture` / `capturePhoto`
// (token, fix, outbox, then send) — `capture.test.ts` proves those; here they
// are mocked to their contract and the PAGE's half is asserted.
const declared: Record<string, string> = {};
const listeners = new Set<() => void>();
vi.mock("./offlineStore", async () => {
  const actual = await vi.importActual<typeof import("./offlineStore")>("./offlineStore");
  return {
    ...actual,
    syncMarker: vi.fn(async () => ({ offline: false, lastSyncAt: null, jobsToSend: 0, itemsWaiting: 0 })),
    writeJob: vi.fn(),
    declaredPhotos: vi.fn(async () => ({ ...declared })),
    onStoreChange: vi.fn((fn: () => void) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    }),
  };
});
vi.mock("./location", () => ({ startFix: vi.fn(), bestFix: vi.fn(async () => null), stopFix: vi.fn() }));
vi.mock("./capture", () => ({
  capture: vi.fn(),
  capturePhoto: vi.fn(async (input: { taskId?: string }) => {
    if (input.taskId) declared[input.taskId] = "p1";
    listeners.forEach((fn) => fn());
    return { photoId: "p1", sent: null };
  }),
}));

import { fireEvent } from "@testing-library/react";

import { capture, capturePhoto } from "./capture";
import { JobPage } from "./JobPage";
import { startFix } from "./location";
import { acceptJob, loadJob, syncJob } from "./mobileEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const SAFETY = [
  { id: "s1", seq: 1, text: "Isolate at the service head before removal", is_mandatory: true, ticked_at: null },
  { id: "s2", seq: 2, text: "Check for backfeed / on-site generation", is_mandatory: true, ticked_at: null },
  { id: "s3", seq: 3, text: "Confined space check where pit-set", is_mandatory: true, ticked_at: null },
];

function bundle(over: Partial<MobileBundle> = {}): MobileBundle {
  const safety = over.safety ?? SAFETY;
  const outstanding = safety.filter((r) => r.is_mandatory && !r.ticked_at);
  return {
    order_id: "o1",
    order_no: "WO-4822",
    safety,
    safety_lock: {
      locked: outstanding.length > 0,
      remaining: outstanding.length,
      first_outstanding: outstanding[0]?.text ?? null,
      ticked: safety.filter((r) => r.ticked_at).length,
      total: safety.length,
      mandatory_total: safety.filter((r) => r.is_mandatory).length,
    },
    tasks: Array.from({ length: 7 }, (_, i) => ({
      id: `t${i + 1}`,
      seq: i + 1,
      title: `Step ${i + 1}`,
      est_minutes: 6,
      photo_required: i === 2,
      photo_attachment_id: null,
      ticked_at: null,
    })),
    tasks_total: 7,
    tasks_ticked: 0,
    tasks_est_minutes: 45,
    readings: [],
    materials: [],
    help: [
      { id: "h1", seq: 1, kind: "document", label: "Meter exchange SOP v4", ref: "doc-1", url: "https://x/sop" },
      { id: "h2", seq: 2, kind: "phone", label: "Supervisor · M. Torres", ref: "(512) 555-0138", url: null },
      { id: "h3", seq: 3, kind: "note", label: "AMI activation hotline · ext 44", ref: null, url: null },
    ],
    details: { access_notes: "dog in rear yard", hazards: "", gate_code: "4417" },
    customer: { name: "Miller, Sarah", phone: "(512) 555-0114", account_no: "A-10688" },
    card: {} as MobileBundle["card"],
    ...over,
  } as MobileBundle;
}

function mount(data: MobileBundle | null) {
  vi.mocked(loadJob).mockResolvedValue(data);
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/work/mobile/jobs/o1`]}>
      <Routes>
        <Route path="/:tenant/work/mobile/jobs/:orderId" element={<JobPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());
// ⚠ EXPLICIT, because this repo has NO global vitest setup file (`vitest.config.ts`
// says so in its own words), so @testing-library's auto-cleanup never registers.
// Without it every render stacks in one document and the second test onward fails
// with *"found multiple elements"* — which reads like a component bug and is not.
afterEach(cleanup);

describe("Work-011 — the job on the phone", () => {
  it("TC-1 · everything the template put on the job is on the screen", async () => {
    mount(bundle());
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    const text = document.body.textContent ?? "";
    expect(text).toContain("Miller, Sarah");
    expect(text).toContain("(512) 555-0114");
    for (const row of SAFETY) expect(text).toContain(row.text);
    expect(screen.getAllByText(/^Step \d$/)).toHaveLength(7);
    expect(text).toContain("Meter exchange SOP v4");
  });

  it("TC-1 · opening the job makes NO network request — it reads the store", async () => {
    // `BR-WRK-042`. `loadJob` is a store read with no network fallback; this
    // asserts the screen calls THAT and nothing else. A read that fell back to
    // the network on a miss would pass every test with a signal and fail the
    // only case that matters.
    mount(bundle());
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    expect(vi.mocked(loadJob)).toHaveBeenCalledTimes(1);
  });

  it("US-WRK-043 TC-1 · two of three ticked is LOCKED, not two-thirds unlocked", async () => {
    const safety = SAFETY.map((row, i) => (i < 2 ? { ...row, ticked_at: "2026-03-15T15:31:00Z" } : row));
    mount(bundle({ safety }));
    await waitFor(() => expect(screen.getByTestId("task-list")).toBeTruthy());
    expect(screen.getByTestId("task-list").getAttribute("data-locked")).toBe("true");
    // The refusal is short AND the outstanding row is named beside it —
    // `BR-WRK-037` says name the row, B14 rule 33 caps the sentence.
    const body = document.body.textContent ?? "";
    expect(body).toContain(t("work.mobile.tasks.finishSafety"));
    expect(body).toContain("Confined space check where pit-set");
  });

  it("US-WRK-043 TC-2 · ticking the third unlocks the tasks", async () => {
    const safety = SAFETY.map((row) => ({ ...row, ticked_at: "2026-03-15T15:31:00Z" }));
    mount(bundle({ safety }));
    await waitFor(() => expect(screen.getByTestId("task-list")).toBeTruthy());
    expect(screen.getByTestId("task-list").getAttribute("data-locked")).toBe("false");
    expect(document.body.textContent).not.toContain(t("work.mobile.tasks.finishSafety"));
  });

  it("the refusal sentence is five or six words — B14 rule 33", () => {
    expect(t("work.mobile.tasks.finishSafety").split(/\s+/).length).toBeLessThanOrEqual(6);
    expect(t("work.mobile.pane.held").split(/\s+/).length).toBeLessThanOrEqual(6);
  });

  it("a task that needs a photograph says so — and, since MQ-017, says what finishes it", async () => {
    // Amended 2026-10-24 (MQ-017): an open required-photo task now reads
    // *"Take 1 photo to finish this step."*, not the bare *"photo required"*.
    for (const key of Object.keys(declared)) delete declared[key];
    mount(bundle());
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    expect(document.body.textContent).toContain(t("work.mobile.tasks.photoToFinish", { count: 1 }));
  });

  it("TC-4 · a help document with no link is LISTED, never dropped", async () => {
    // *"the job still opens; nothing silently dropped"*. A missing SOP a
    // technician can SEE is missing is a phone call to the supervisor; one that
    // quietly is not on the list is a technician improvising in a basement.
    const data = bundle();
    data.help = data.help.map((row) => (row.kind === "document" ? { ...row, url: null } : row));
    mount(data);
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    expect(document.body.textContent).toContain("Meter exchange SOP v4");
    expect(screen.queryByRole("link", { name: "Meter exchange SOP v4" })).toBeNull();
  });

  it("CR-168 P3.25 · a Link opens from the phone and says it needs a signal", async () => {
    // Before this, anything but a phone or a stored document was PLAIN TEXT,
    // so a video link reached the technician untappable.
    const data = bundle();
    data.help = [
      ...data.help,
      { id: "h4", seq: 4, kind: "link", label: "Fitting a single-phase meter", ref: "https://www.youtube.com/watch?v=Qx4dF2mT9sE", url: null },
    ];
    mount(data);
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    const link = screen.getByRole("link", { name: /Fitting a single-phase meter/u });
    expect(link.getAttribute("href")).toBe("https://www.youtube.com/watch?v=Qx4dF2mT9sE");
    expect(link.textContent).toContain(t("work.mobile.help.needsSignal"));
  });

  it("a job not yet on the phone says so rather than spinning for ever", async () => {
    mount(null);
    await waitFor(() => expect(screen.getByText(t("work.mobile.job.notSynced"))).toBeTruthy());
  });

  it("B14 rule 31 — the order NUMBER is visible and the uuid is not", async () => {
    mount(bundle());
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    expect(document.body.textContent).not.toContain("o1");
  });

  it("all four panes are LINKS — nothing on this screen is held any more", async () => {
    // ⚠ AMENDED TWICE, AND THE SECOND AMENDMENT IS THE POINT AS MUCH AS THE
    // FIRST. Wave J wrote this asserting all FOUR panes were held; wave K
    // released three and corrected it to *"only Close is still held"*; wave L
    // released the fourth. **Releasing a control is only half done until the
    // test that described it as held is corrected too**, or the suite goes on
    // certifying a screen that no longer exists — `DEF-CWP-3925` from the other
    // end, where the portal shipped two working doors out of eight with every
    // check green.
    mount(bundle());
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());

    for (const id of ["readings", "photos", "signature", "close"]) {
      const link = document.querySelector(`[data-pane="${id}"] a`);
      expect(link, `${id} landed in wave K and must be a link, not a held span`).toBeTruthy();
      // Asserted BY ADDRESS, not by label — a link whose href is wrong reads
      // perfectly well and goes nowhere (`DEF-WRK-4051`).
      expect(link?.getAttribute("href")).toContain(`/jobs/o1/${id}`);
      expect(document.querySelector(`[data-held-pane="${id}"]`)).toBeNull();
    }

    // ⚠ AND NOTHING IS HELD — asserted as an ABSENCE, which is the half that
    // rots silently. `HELD_PANES` is empty, so `HeldPanes` renders no list at
    // all; a stale `data-held-pane` here would be a refusal outliving its cause.
    expect(document.querySelector("[data-held-pane]")).toBeNull();
  });
});

describe("the technician's own acts on the job page — CR-168-BRC10 lane FIELD-FIX", () => {
  it("DEF-WRK-9636 · tapping a safety row queues a safety tick and sends it", async () => {
    const data = bundle();
    const after = bundle({ safety: SAFETY.map((r, i) => (i === 0 ? { ...r, ticked_at: "2026-10-04T15:00:00Z" } : r)) });
    vi.mocked(capture).mockResolvedValue({
      item: {} as never,
      sent: [{ work_order_id: "o1", accepted: 1, duplicate: 0, refused: 0, items: [], synced_at: "" }],
    });
    vi.mocked(syncJob).mockResolvedValue(after);
    mount(data);
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    // CR-168 §F, BR-WRK-061 — location acquisition starts when the job opens.
    expect(vi.mocked(startFix)).toHaveBeenCalledWith("o1");

    fireEvent.click(screen.getByRole("checkbox", { name: SAFETY[0].text }));

    await waitFor(() => expect(vi.mocked(capture)).toHaveBeenCalled());
    const item = vi.mocked(capture).mock.calls[0][0];
    expect(item.kind).toBe("safety_tick");
    expect(item.payload).toEqual({ safety_id: "s1" });
    expect(item.orderId).toBe("o1");
    // The lock shown afterwards is the SERVER's, re-read — never recomputed here.
    await waitFor(() => expect(vi.mocked(syncJob)).toHaveBeenCalledWith("o1"));
    await waitFor(() =>
      expect((screen.getByRole("checkbox", { name: SAFETY[0].text }) as HTMLInputElement).checked).toBe(true),
    );
  });

  it("DEF-WRK-9636 · a task is ticked the same way once safety is done", async () => {
    const safety = SAFETY.map((row) => ({ ...row, ticked_at: "2026-03-15T15:31:00Z" }));
    vi.mocked(capture).mockResolvedValue({
      item: {} as never,
      sent: [{ work_order_id: "o1", accepted: 1, duplicate: 0, refused: 0, items: [], synced_at: "" }],
    });
    vi.mocked(syncJob).mockResolvedValue(bundle({ safety }));
    mount(bundle({ safety }));
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());

    fireEvent.click(screen.getByRole("checkbox", { name: "Step 1" }));

    await waitFor(() => expect(vi.mocked(capture)).toHaveBeenCalled());
    const item = vi.mocked(capture).mock.calls[0][0];
    expect(item.kind).toBe("task_tick");
    expect(item.payload).toEqual({ task_id: "t1" });
  });

  it("DEF-WRK-9636 · while safety is outstanding the task boxes cannot be ticked", async () => {
    mount(bundle());
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    expect((screen.getByRole("checkbox", { name: "Step 1" }) as HTMLInputElement).disabled).toBe(true);
  });

  it("DEF-WRK-9619 · a photo-required task has its own camera and the photo is sent FOR that task", async () => {
    const safety = SAFETY.map((row) => ({ ...row, ticked_at: "2026-03-15T15:31:00Z" }));
    mount(bundle({ safety }));
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());

    // Only the task that asks for a photograph carries a camera.
    const cameras = document.querySelectorAll('[data-task-camera] input[type="file"]');
    expect(cameras).toHaveLength(1);
    const file = new File([new Uint8Array([1, 2, 3])], "dial.jpg", { type: "image/jpeg" });
    fireEvent.change(cameras[0], { target: { files: [file] } });

    await waitFor(() => expect(vi.mocked(capturePhoto)).toHaveBeenCalled());
    const input = vi.mocked(capturePhoto).mock.calls[0][0];
    expect(input.orderId).toBe("o1");
    expect(input.taskId).toBe("t3");
    // The row says the photograph is in, and no longer that one is needed.
    await waitFor(() => expect(document.querySelector('[data-task-id="t3"] [data-flag="photo-taken"]')).toBeTruthy());
    expect(document.querySelector('[data-task-id="t3"] [data-flag="missing-photo"]')).toBeNull();
  });

  it("MQ-017 · a task whose photo is REQUIRED cannot be ticked until the photo is taken, and says why", async () => {
    // PO 2026-10-24: *"B. Block on a required photo - but show warning message
    // to field technician"*. The server still accepts a tick and records the
    // gap; the block is here, where the tap happens.
    for (const key of Object.keys(declared)) delete declared[key]; // an earlier test photographed t3
    const safety = SAFETY.map((row) => ({ ...row, ticked_at: "2026-03-15T15:31:00Z" }));
    mount(bundle({ safety }));
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());

    const box = screen.getByRole("checkbox", { name: "Step 3" }) as HTMLInputElement;
    expect(box.disabled).toBe(true);
    const flag = document.querySelector('[data-task-id="t3"] [data-flag="missing-photo"]');
    expect(flag?.textContent).toBe("Take 1 photo to finish this step.");
    // the disabled box is still explained to a screen reader
    expect(box.getAttribute("aria-describedby")).toBe(flag?.id);
    fireEvent.click(box);
    expect(vi.mocked(capture)).not.toHaveBeenCalled();
    // a task with no photo asked for is untouched
    expect((screen.getByRole("checkbox", { name: "Step 1" }) as HTMLInputElement).disabled).toBe(false);

    const file = new File([new Uint8Array([1, 2, 3])], "dial.jpg", { type: "image/jpeg" });
    fireEvent.change(document.querySelector('[data-task-camera="t3"] input[type="file"]')!, { target: { files: [file] } });
    await waitFor(() => expect((screen.getByRole("checkbox", { name: "Step 3" }) as HTMLInputElement).disabled).toBe(false));
    expect(document.querySelector('[data-task-id="t3"] [data-flag="missing-photo"]')).toBeNull();
  });

  it("CR-168 §F · offline, a safety tick waits on the phone and the tasks open — the server still decides", async () => {
    // One safety row, mandatory. With no signal `capture` answers `sent: null`.
    const one = [SAFETY[0]];
    vi.mocked(capture).mockResolvedValue({ item: {} as never, sent: null });
    vi.mocked(syncJob).mockClear();
    const data = bundle({ safety: one, safety_lock: { locked: true, remaining: 1, first_outstanding: one[0].text, ticked: 0, total: 1, mandatory_total: 1 } });
    mount(data);
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    expect((screen.getByRole("checkbox", { name: "Step 1" }) as HTMLInputElement).disabled).toBe(true);

    fireEvent.click(screen.getByRole("checkbox", { name: one[0].text }));

    await waitFor(() =>
      expect((screen.getByRole("checkbox", { name: "Step 1" }) as HTMLInputElement).disabled).toBe(false),
    );
    expect((screen.getByRole("checkbox", { name: one[0].text }) as HTMLInputElement).checked).toBe(true);
    // Nothing was asked of the server — there is no signal to ask with.
    expect(vi.mocked(syncJob)).not.toHaveBeenCalled();
  });

  it("CR-168 §F · BR-WRK-059 — a job not yet taken offers Accept job, and taking it hides the offer", async () => {
    vi.mocked(acceptJob).mockResolvedValue({ technician_acceptance: { state: "accepted", at: "2026-10-04T15:00:00Z", reason: null } });
    mount(bundle({ technician_acceptance: { state: "pending", at: null, reason: null } }));
    await waitFor(() => expect(screen.getByTestId("accept-job")).toBeTruthy());
    fireEvent.click(screen.getByText(t("work.mobile.job.accept")));
    await waitFor(() => expect(vi.mocked(acceptJob)).toHaveBeenCalledWith("o1"));
    await waitFor(() => expect(screen.queryByTestId("accept-job")).toBeNull());
  });
});
