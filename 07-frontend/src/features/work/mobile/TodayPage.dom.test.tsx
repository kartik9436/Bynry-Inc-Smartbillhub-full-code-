// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-041 TC-1..TC-5 — the day in appointment order, the honest
//           marker, the dog and the gate code.  Screen: Work-010
// Rules:    BR-WRK-035 (ordered by appointment time; the pill does not
//           reorder) · BR-WRK-036 (the marker never reads a time it does not
//           have) · B14 rule 31 (no database id is a visible value)
// ───────────────────────────────────────────────────────
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE IN A `MemoryRouter`**, and
// that is not fussiness — it is `DEF-CWP-3925`'s second finding written out.
// The portal's front page mounted bare, so `useParams().tenant` was undefined
// and every address it built came out `//portal/…` — a protocol-relative URL to
// another host, which reads as a perfectly good string to `toContain`. **A
// fixture that cannot tell a working link from a broken one is how a broken
// link hides.** So every render here goes through a `<Route path="/:tenant/
// work/mobile">`, and the link assertion below would catch that exact bug.
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { MobileDay, MobileJobCard } from "./mobileEndpoints";

vi.mock("./mobileEndpoints", async () => {
  const actual = await vi.importActual<typeof import("./mobileEndpoints")>("./mobileEndpoints");
  return { ...actual, loadDay: vi.fn(), syncJob: vi.fn() };
});
vi.mock("./offlineStore", async () => {
  const actual = await vi.importActual<typeof import("./offlineStore")>("./offlineStore");
  return { ...actual, syncMarker: vi.fn() };
});

import { loadDay, syncJob } from "./mobileEndpoints";
import { syncMarker } from "./offlineStore";
import type { SyncMarker } from "./offlineStore";
import { TodayPage } from "./TodayPage";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function card(over: Partial<MobileJobCard> & { order_no: string }): MobileJobCard {
  return {
    id: `id-${over.order_no}`,
    type: "Meter exchange",
    premise: { address_line: "221 Oak Ave" },
    window_start: null,
    window_end: null,
    due_at: null,
    est_minutes: 45,
    priority: null,
    state: "planned",
    dispatch_state: "scheduled",
    access_notes: "",
    hazards: "",
    gate_code: "",
    ...over,
  } as MobileJobCard;
}

/** The story's own fixture: four jobs for D. Ortiz, two of them done. */
const FOUR_JOBS: MobileDay = {
  technician: { name: "D. Ortiz", van: "Unit 12", status: "on_shift" },
  jobs: [
    card({ order_no: "WO-4901", window_start: "2026-03-15T08:30:00Z", dispatch_state: "complete" }),
    card({ order_no: "WO-4902", window_start: "2026-03-15T09:15:00Z", dispatch_state: "complete" }),
    card({
      order_no: "WO-4824",
      due_at: "2026-03-15T12:00:00Z",
      priority: { code: "urgent", name: "Urgent" },
    }),
    card({
      order_no: "WO-4822",
      window_start: "2026-03-15T15:30:00Z",
      priority: { code: "normal", name: "Normal" },
      access_notes: "dog in rear yard",
      gate_code: "4417",
    }),
  ],
  count: 4,
  done: 2,
  empty_reason: null,
};

function mount(
  day: MobileDay | null,
  marker: SyncMarker = { offline: false, lastSyncAt: "2026-03-15T08:12:00Z", jobsToSend: 0 },
  fromStore = false,
) {
  vi.mocked(syncJob).mockResolvedValue({} as never);
  vi.mocked(loadDay).mockResolvedValue({ day, fromStore });
  vi.mocked(syncMarker).mockResolvedValue(marker);
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/work/mobile`]}>
      <Routes>
        <Route path="/:tenant/work/mobile" element={<TodayPage />} />
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

describe("Work-010 — Today", () => {
  it("TC-1 · renders the day in the order the server sent, and does not sort", async () => {
    // `BR-WRK-035`. The server orders by appointment time; this asserts the
    // component is a faithful renderer of that order rather than a second
    // opinion about it.
    mount(FOUR_JOBS);
    await waitFor(() => expect(screen.getByText("WO-4901")).toBeTruthy());
    const shown = screen.getAllByText(/^WO-\d+$/).map((node) => node.textContent);
    expect(shown).toEqual(["WO-4901", "WO-4902", "WO-4824", "WO-4822"]);
  });

  it("TC-2 · negative — an Urgent pill does not move its job up the list", async () => {
    // *"an Urgent job across town does not jump the one they are standing
    // outside"*. `WO-4824` carries Urgent and stays third; the pill is a label.
    mount(FOUR_JOBS);
    await waitFor(() => expect(screen.getByText("WO-4824")).toBeTruthy());
    const shown = screen.getAllByText(/^WO-\d+$/).map((node) => node.textContent);
    expect(shown.indexOf("WO-4824")).toBeLessThan(shown.indexOf("WO-4822"));
    expect(screen.getByText("Urgent")).toBeTruthy();
  });

  it("TC-3 · the offline marker shows the last sync time", async () => {
    mount(FOUR_JOBS, { offline: true, lastSyncAt: "2026-03-15T08:12:00Z", jobsToSend: 0 });
    await waitFor(() =>
      expect(screen.getByTestId("offline-marker").textContent).toContain("◍"),
    );
    // The word for *offline* comes from the catalogue, not from this test.
    expect(screen.getByTestId("offline-marker").textContent).toMatch(/\d{2}[:.]\d{2}/);
  });

  it("TC-4 · negative — a phone that has never synced never renders a time", async () => {
    // The tempting default (no stored value → use now) would make a phone that
    // has never reached the server claim it synced this minute. That is the one
    // thing this marker exists to make impossible.
    mount(FOUR_JOBS, { offline: true, lastSyncAt: null, jobsToSend: 0 });
    await waitFor(() => expect(screen.getByTestId("offline-marker")).toBeTruthy());
    // CR-168-BRC10 §F (FIELD-2) — the waiting count now rides on the marker
    // ALWAYS, zero included (*"The phone always shows N waiting to send"*);
    // the half this case owns — no TIME — is unchanged.
    expect(screen.getByTestId("offline-marker").textContent).toBe(
      `${t("work.mobile.marker.never")} · ${t("work.mobile.marker.waiting", { count: 0 })}`,
    );
    expect(screen.getByTestId("offline-marker").textContent).not.toMatch(/\d{2}[:.]\d{2}/);
  });

  it("CR-168 §F · *N waiting to send* is always shown — zero, and a real count", async () => {
    mount(FOUR_JOBS, { offline: true, lastSyncAt: null, jobsToSend: 1, itemsWaiting: 7 });
    await waitFor(() => expect(screen.getByTestId("items-waiting")).toBeTruthy());
    expect(screen.getByTestId("items-waiting").textContent).toContain(t("work.mobile.marker.waiting", { count: 7 }));
    cleanup();
    mount(FOUR_JOBS, { offline: false, lastSyncAt: "2026-03-15T08:12:00Z", jobsToSend: 0, itemsWaiting: 0 });
    await waitFor(() => expect(screen.getByTestId("items-waiting")).toBeTruthy());
    expect(screen.getByTestId("items-waiting").textContent).toContain(t("work.mobile.marker.waiting", { count: 0 }));
  });

  it("TC-5 · the dog and the gate code reach the card", async () => {
    mount(FOUR_JOBS);
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    const text = document.body.textContent ?? "";
    expect(text).toContain("dog in rear yard");
    expect(text).toContain("4417");
  });

  it("builds a real link to the job — the address, not `//work/mobile/…`", async () => {
    // ⚠ `DEF-CWP-3925`'s fixture lesson. Mounted bare, `useParams().tenant` is
    // undefined and this href would be `//work/mobile/jobs/…` — a
    // protocol-relative URL to ANOTHER HOST that reads as a fine string to a
    // `toContain`. Asserting the leading `/{tenant}/` is what catches it.
    mount(FOUR_JOBS);
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    const link = screen.getByText("WO-4822").closest("a");
    expect(link?.getAttribute("href")).toBe(`/${TENANT}/work/mobile/jobs/id-WO-4822`);
    expect(link?.getAttribute("href")?.startsWith("//")).toBe(false);
  });

  it("a login with no technician profile gets a sentence, never an error", async () => {
    // `US-WRK-040` TC-3 — six words, and an EMPTY DAY rather than an error page.
    mount({ ...FOUR_JOBS, technician: null, jobs: [], count: 0, done: 0, empty_reason: "no_technician_profile" });
    await waitFor(() =>
      expect(screen.getByText(t("work.mobile.empty.noProfile"))).toBeTruthy(),
    );
    expect(t("work.mobile.empty.noProfile").split(/\s+/).length).toBeLessThanOrEqual(6);
  });

  it("DEF-WRK-4061 · syncs EVERY job's bundle, because that is what *fetched at sync* means", async () => {
    // ⚠ **THE TEST THAT WOULD HAVE CAUGHT THE WAVE'S WORST DEFECT, WRITTEN
    // AFTER A BROWSER FOUND IT.** `syncJob` had no caller anywhere in the
    // tree, so the offline store never held a bundle and tapping ANY job on
    // the phone showed *Not on this phone yet.* — with `tsc`, eslint, G13 and
    // every unit test green, because `JobPage`'s own tests MOCK the store and
    // therefore prove the screen renders a bundle rather than that one ever
    // arrives (hard-won law 2, in the wave that quotes it).
    //
    // It asserts the CALL and the count, not the rendering: a fifth screen
    // that fetches the day and forgets the bundles goes red here naming the
    // job it skipped.
    mount(FOUR_JOBS);
    await waitFor(() => expect(vi.mocked(syncJob)).toHaveBeenCalledTimes(FOUR_JOBS.jobs.length));
    const asked = vi.mocked(syncJob).mock.calls.map(([id]) => id);
    expect(asked).toEqual(FOUR_JOBS.jobs.map((job) => job.id));
  });

  it("does NOT re-fetch bundles when the day itself came from the store", async () => {
    // The offline case. There is no signal, the fetches would fail one by one,
    // and the bundles are already there from the last sync — which is the whole
    // point of having them.
    mount(FOUR_JOBS, { offline: true, lastSyncAt: "2026-03-15T08:12:00Z", jobsToSend: 0 }, true);
    await waitFor(() => expect(screen.getByText("WO-4901")).toBeTruthy());
    expect(vi.mocked(syncJob)).not.toHaveBeenCalled();
  });

  it("one unreachable bundle does not cost the technician the other three", async () => {
    // A help document whose link would not mint, a network that dropped
    // mid-day: the day must still be usable. Failures are per job.
    vi.mocked(syncJob).mockRejectedValueOnce(new Error("gone"));
    mount(FOUR_JOBS);
    await waitFor(() => expect(vi.mocked(syncJob)).toHaveBeenCalledTimes(FOUR_JOBS.jobs.length));
    expect(screen.getAllByText(/^WO-\d+$/)).toHaveLength(4);
  });

  it("B14 rule 31 — no uuid is ever a visible value", async () => {
    mount(FOUR_JOBS);
    await waitFor(() => expect(screen.getByText("WO-4822")).toBeTruthy());
    const list = screen.getByRole("list");
    expect(within(list).queryByText(/id-WO-/)).toBeNull();
  });
});
describe("DEF-WRK-9688 · DEF-WRK-9693 — the utility's clock, and the unbooked jobs", () => {
  it("draws the booked window in the utility's time, not the phone's", async () => {
    mount({
      ...FOUR_JOBS,
      jobs: [
        card({
          order_no: "WO-0104",
          window_start: "2026-10-04T13:00:00+00:00",
          window_end: "2026-10-04T17:00:00+00:00",
          appointment: { date: "2026-10-04", start: "08:00", end: "12:00", time_zone: "America/Chicago" },
        }),
      ],
      count: 1,
      done: 0,
    });
    await waitFor(() => expect(screen.getByText("WO-0104")).toBeTruthy());
    expect(document.body.textContent).toContain("08:00–12:00");
  });

  it("a job with no visit booked is listed under Unscheduled, after the booked ones", async () => {
    mount({
      ...FOUR_JOBS,
      jobs: [
        card({ order_no: "WO-0001", window_start: "2026-10-04T13:00:00+00:00", unscheduled: false }),
        card({ order_no: "WO-0002", due_at: "2026-10-13T13:00:00+00:00", unscheduled: true }),
      ],
      count: 2,
      done: 0,
    });
    await waitFor(() => expect(screen.getByText("WO-0002")).toBeTruthy());
    const heading = screen.getByTestId("unscheduled-heading");
    expect(heading.textContent).toBe(t("work.mobile.today.unscheduled"));
    const list = heading.nextElementSibling as HTMLElement;
    expect(within(list).getByText("WO-0002")).toBeTruthy();
    expect(within(list).queryByText("WO-0001")).toBeNull();
  });
});
