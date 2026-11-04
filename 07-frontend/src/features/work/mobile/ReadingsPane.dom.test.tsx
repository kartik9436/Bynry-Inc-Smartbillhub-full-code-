// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-047 (out of range flags, never refuses) · US-WRK-049 (the
//           rule column and the file column).  Screen: Work-012
// Rules:    BR-WRK-039 · BR-WRK-040 · hard rule 3 · B14 rule 31
// ───────────────────────────────────────────────────────
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import SHAPES from "../../../../../field-app/tests/sync/support/jobReadingShapes.json";
import { ReadingsPane } from "./ReadingsPane";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    // The KEY is returned, so an assertion below names the string the screen
    // asked for rather than the English it happened to resolve to. A test that
    // matched English would pass on a screen showing the wrong catalogue entry.
    t: (key: string) => key,
  }),
}));

const READINGS = [
  {
    id: "r1",
    seq: 1,
// ⚠ **THIS FIXTURE MIRRORS THE SERVER, NOT THE TYPE — `DEF-WRK-4111`.**
// The job bundle is `apps/work/checklist.checklist()` verbatim (`mobile.bundle`
// returns the pack unchanged), so a reading row carries `unit_of_measure`. This
// file used to say `unit`, which matched `ReadingRow` exactly and matched the
// server not at all: on a real handset `row.unit` was `undefined`, the unit
// column rendered EMPTY, and every save posted no unit and was refused
// `work.reading.unit_required`. A technician could not record one reading, and
// every case below passed throughout.
// **A mock written from the type can only confirm the type to itself.** When
// you add a field here, copy it off the server's payload.

    prompt: "Opening read, new meter",
    unit_of_measure: "kWh",
    value: "1204.0000",
    in_range: false, // BR-WRK-039 — flags, never blocks
    required: true,
    photo_required: true,
    photo_attachment_id: "a1",
    captured_at: "2026-03-15T16:02:00Z",
    posts_as_meter_read: true,
  },
  {
    id: "r2",
    seq: 2,
    prompt: "Voltage at socket",
    unit_of_measure: "V",
    value: null,
    in_range: null, // never checked — NOT the same as out of range
    required: true,
    photo_required: true,
    photo_attachment_id: null, // BR-WRK-040 — blocks
    captured_at: null,
    posts_as_meter_read: false,
  },
  {
    id: "r3",
    seq: 3,
    prompt: "New meter serial",
    unit_of_measure: "serial",
    value: "8841",
    in_range: null,
    required: true,
    photo_required: false, // never asked — must NOT read as "missing"
    photo_attachment_id: null,
    captured_at: "2026-03-15T16:05:00Z",
    posts_as_meter_read: false,
  },
  {
    // DEF-WRK-10602 — a TEXT reading as `checklist.checklist()` serves it:
    // `kind: "text"`, words in `value_text`, no unit, no figure.
    id: "r4",
    seq: 4,
    prompt: "Seal number",
    unit_of_measure: "",
    kind: "text",
    value: null,
    value_text: "S-1180",
    in_range: null,
    required: true,
    photo_required: false,
    photo_attachment_id: null,
    captured_at: "2026-03-15T16:06:00Z",
    posts_as_meter_read: false,
  },
];

vi.mock("./mobileEndpoints", () => ({
  loadJob: async () => ({ readings: READINGS }),
  mergeReadingIntoJob: vi.fn(async () => undefined),
}));

// CR-168-BRC10 §F (FIELD-2) — a reading goes through the outbox (`capture`),
// a photograph through `capturePhoto`; `capture.test.ts` proves those.
let declared: Record<string, string> = {};
vi.mock("./capture", () => ({
  capture: vi.fn(async () => ({ item: {}, sent: null })),
  capturePhoto: vi.fn(async (input: { readingId?: string }) => {
    if (input.readingId) declared = { ...declared, [input.readingId]: "p1" };
    return { photoId: "p1", sent: null };
  }),
}));
vi.mock("./location", () => ({ startFix: vi.fn(), bestFix: vi.fn(async () => null) }));
vi.mock("./offlineStore", () => ({ declaredPhotos: vi.fn(async () => declared) }));

vi.mock("./evidenceEndpoints", () => ({
  loadCloseReadiness: async () => ({
    can_close: false,
    blocking: [
      { kind: "missing_required_photo", scope: "reading", id: "r2", prompt: "Voltage at socket" },
    ],
    flagged: [
      {
        kind: "out_of_range",
        scope: "reading",
        id: "r1",
        prompt: "Opening read, new meter",
        value: "1204.0000",
        unit_of_measure: "kWh",
      },
    ],
    readings_captured: 3,
    readings_total: 4,
    required_photos_taken: 2,
    required_photos_total: 3,
  }),
  putReading: vi.fn(),
  postAttachment: vi.fn(),
}));

function mount() {
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN, not bare inside a MemoryRouter.
  // Hard-won law 2's fixture clause: a component mounted with no matching route
  // gets `undefined` from `useParams`, and every address it builds comes out
  // wrong while still reading as a perfectly good string to `toContain`.
  return render(
    <MemoryRouter initialEntries={["/brazos-bend/work/mobile/jobs/o1/readings"]}>
      <Routes>
        <Route
          path="/:tenant/work/mobile/jobs/:orderId/readings"
          element={<ReadingsPane />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

// Without this each `mount()` leaves its predecessor in the document, and
// `getByText` then finds three "kWh" and fails on ambiguity rather than on
// anything about the screen.
afterEach(cleanup);

describe("Work-012 — the readings pane", () => {
  it("shows an out-of-range value in the DANGER tier, and it does not block", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("Opening read, new meter")).toBeTruthy());
    const flag = document.querySelector('[data-flag="out-of-range"]');
    expect(flag, "1,204 against 0–999 must be flagged").toBeTruthy();
    // BR-WRK-039 is RED. The colour is the rule here, not decoration.
    expect(flag?.className).toContain("text-danger-700");
  });

  it("shows a missing REQUIRED photograph in the WARNING tier — a different rule", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("Voltage at socket")).toBeTruthy());
    const flag = document.querySelector('[data-flag="missing-photo"]');
    expect(flag, "a required photograph that was not taken must be flagged").toBeTruthy();
    expect(flag?.className).toContain("text-warning-700");
  });

  it("⚠ renders the two rules DIFFERENTLY — this is the whole of BR-WRK-040", async () => {
    // *Two different rules, two different sentences.* A screen that showed both
    // as one shade of "check this" teaches a technician that neither matters,
    // and the one that does is the one that stops a job closing on a Friday.
    mount();
    await waitFor(() => expect(screen.getByText("Opening read, new meter")).toBeTruthy());
    const outOfRange = document.querySelector('[data-flag="out-of-range"]');
    const missing = document.querySelector('[data-flag="missing-photo"]');
    expect(outOfRange?.className).not.toEqual(missing?.className);
    expect(outOfRange?.textContent).not.toEqual(missing?.textContent);
  });

  it("does NOT flag a reading whose template never asked for a photograph", async () => {
    // `US-WRK-049`'s point: *never asked* and *asked and not taken* are
    // different states, and a single nullable column could not tell them apart.
    mount();
    await waitFor(() => expect(screen.getByText("New meter serial")).toBeTruthy());
    const serialRow = document.querySelector('[data-reading-id="r3"]');
    expect(serialRow?.querySelector('[data-flag="missing-photo"]')).toBeNull();
  });

  it("does NOT flag a reading whose template set no bounds", async () => {
    // `in_range: null` is *not checked*, which is not *out of range*. A red flag
    // beside a number nothing ever questioned teaches people to ignore red.
    mount();
    await waitFor(() => expect(screen.getByText("New meter serial")).toBeTruthy());
    const serialRow = document.querySelector('[data-reading-id="r3"]');
    expect(serialRow?.querySelector('[data-flag="out-of-range"]')).toBeNull();
  });

  it("shows each reading's unit as its own thing — hard rule 3", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("Opening read, new meter")).toBeTruthy());
    // Not "Opening read (kWh)" — a unit hidden inside a prompt is a unit
    // nothing can validate, convert or compare.
    expect(screen.getByText("kWh")).toBeTruthy();
    expect(screen.getByText("V")).toBeTruthy();
  });

  it("states the consequence, because the colours alone do not explain it", async () => {
    mount();
    await waitFor(() => expect(document.querySelector("[data-consequence]")).toBeTruthy());
    expect(document.querySelector("[data-consequence]")?.textContent).toContain(
      "work.mobile.readings.consequence",
    );
  });

  it("takes the close verdict from the SERVER and does not recompute it", async () => {
    // The footer counts come from `close_readiness()`. A screen that derived
    // them would be a second opinion about whether a job may be finished — the
    // exact failure `BR-WRK-037`'s one-evaluator argument already rejected.
    mount();
    await waitFor(() => expect(document.querySelector("[data-consequence]")).toBeTruthy());
    expect(screen.getByText("work.mobile.readings.footer")).toBeTruthy();
  });

  it("CR-168 §F — a reading typed in the field goes into the outbox WITH its unit", async () => {
    const { capture } = await import("./capture");
    mount();
    await waitFor(() => expect(screen.getByText("Opening read, new meter")).toBeTruthy());
    // DEF-WRK-10595: r2's photo is REQUIRED and not taken, so its save is held
    // (cases below); r1 has its photo, so a corrected figure goes straight out.
    vi.mocked(capture).mockClear();
    const input = screen.getByLabelText("Opening read, new meter") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "241" } });
    fireEvent.blur(input);
    await waitFor(() => expect(vi.mocked(capture)).toHaveBeenCalled());
    const call = vi.mocked(capture).mock.calls[0][0];
    expect(call.kind).toBe("reading");
    expect(call.payload).toEqual({ reading_id: "r1", value: "241", unit: READINGS[0].unit_of_measure });
  });

  it("DEF-WRK-10595 (MQ-020) — a reading whose photo is REQUIRED is not saved until the photo exists", async () => {
    // The phone's FF-20 rule on the web technician page: the typed figure is
    // KEPT in the pane, the row says what is missing, and nothing is captured.
    const { capture } = await import("./capture");
    vi.mocked(capture).mockClear();
    declared = {};
    mount();
    await waitFor(() => expect(screen.getByText("Voltage at socket")).toBeTruthy());
    const input = screen.getByLabelText("Voltage at socket") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "241" } });
    fireEvent.blur(input);
    const row = document.querySelector('[data-reading-id="r2"]') as HTMLElement;
    await waitFor(() =>
      expect(row.querySelector('[data-flag="missing-photo"]')?.textContent).toBe(
        "work.mobile.readings.photoToSave",
      ),
    );
    expect(vi.mocked(capture)).not.toHaveBeenCalled();
    expect(input.value).toBe("241");
  });

  it("DEF-WRK-10595 — the held figure is saved, with its unit, once the photo is attached", async () => {
    const { capture, capturePhoto } = await import("./capture");
    vi.mocked(capture).mockClear();
    declared = {};
    mount();
    await waitFor(() => expect(screen.getByText("Voltage at socket")).toBeTruthy());
    const input = screen.getByLabelText("Voltage at socket") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "241" } });
    fireEvent.blur(input);
    expect(vi.mocked(capture)).not.toHaveBeenCalled();
    const row = document.querySelector('[data-reading-id="r2"]') as HTMLElement;
    const camera = row.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(camera, {
      target: { files: [new File([new Uint8Array([1])], "v.jpg", { type: "image/jpeg" })] },
    });
    await waitFor(() => expect(vi.mocked(capturePhoto)).toHaveBeenCalled());
    await waitFor(() => expect(vi.mocked(capture)).toHaveBeenCalled());
    expect(vi.mocked(capture).mock.calls[0][0].payload).toEqual({
      reading_id: "r2",
      value: "241",
      unit: READINGS[1].unit_of_measure,
    });
  });

  it("DEF-WRK-10602 — a text reading shows its words as typed", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("Seal number")).toBeTruthy());
    expect((screen.getByLabelText("Seal number") as HTMLInputElement).value).toBe("S-1180");
  });

  it("DEF-WRK-10602 — a text reading is sent in the PHONE's text shape, which the server is tested to accept", async () => {
    // The shared fixture is the one the backend test POSTs through the sync
    // door and the field app's capture is held to — one shape, three clients.
    const { capture } = await import("./capture");
    vi.mocked(capture).mockClear();
    mount();
    await waitFor(() => expect(screen.getByText("Seal number")).toBeTruthy());
    const input = screen.getByLabelText("Seal number") as HTMLInputElement;
    fireEvent.change(input, { target: { value: ` ${SHAPES.text.value_text} ` } });
    fireEvent.blur(input);
    await waitFor(() => expect(vi.mocked(capture)).toHaveBeenCalled());
    expect(vi.mocked(capture).mock.calls[0][0].payload).toEqual({ ...SHAPES.text, reading_id: "r4" });
  });

  it("DEF-WRK-10595 — a reading never asked for a photo still saves on blur", async () => {
    const { capture } = await import("./capture");
    vi.mocked(capture).mockClear();
    mount();
    await waitFor(() => expect(screen.getByText("New meter serial")).toBeTruthy());
    const input = screen.getByLabelText("New meter serial") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "8842" } });
    fireEvent.blur(input);
    await waitFor(() => expect(vi.mocked(capture)).toHaveBeenCalled());
  });

  it("CR-168 §F — a photograph taken here reads as taken before its bytes have left the phone", async () => {
    const { capturePhoto } = await import("./capture");
    declared = {};
    mount();
    await waitFor(() => expect(screen.getByText("Voltage at socket")).toBeTruthy());
    const row = document.querySelector('[data-reading-id="r2"]') as HTMLElement;
    const camera = row.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(camera, { target: { files: [new File([new Uint8Array([1])], "v.jpg", { type: "image/jpeg" })] } });
    await waitFor(() => expect(vi.mocked(capturePhoto)).toHaveBeenCalled());
    await waitFor(() => expect(row.querySelector('[data-flag="photo-taken"]')).toBeTruthy());
    expect(row.querySelector('[data-flag="missing-photo"]')).toBeNull();
  });
});
