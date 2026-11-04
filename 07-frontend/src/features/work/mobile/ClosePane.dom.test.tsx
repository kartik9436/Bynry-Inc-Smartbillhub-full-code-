// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-045 TC-1/TC-2/TC-4/TC-5/TC-7 (the close from the phone) ·
//           US-WRK-044 TC-7 (the marker counts JOBS)
//           Screen: Work-012 (`WS-12`)
// Rules:    BR-WRK-041 (the offline label; the close activates nothing) ·
//           BR-WRK-040 (a missing REQUIRED photograph stops the close) ·
//           BR-WRK-042 (a key minted at capture; a second tap queues nothing) ·
//           BR-SHL-025 (the SERVER's refusal, in the server's words)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE STORE IS MOCKED, AND THAT IS A LIMIT WORTH STATING RATHER THAN
// HIDING.** jsdom has no IndexedDB and this repository carries no fake, so
// `offlineStore` degrades to no-ops here and NOTHING below proves that a
// queued item survives a page reload. What it does prove is the part that is
// this screen's own: WHAT gets queued, in what order relative to the network,
// and what the technician is told. The durable-storage half needs a fake
// IndexedDB and is named in the lane report rather than quietly assumed.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

const enqueued: unknown[] = [];
const synced: string[] = [];
let offline = false;
let refusal: { message?: string; message_key?: string } | null = null;

// `DEF-WRK-4127` — when the job was first opened on this phone; the close
// pre-fills it as *Arrived*. Local 09:00 on 15 March.
const OPENED = new Date(2026, 2, 15, 9, 0).toISOString();
vi.mock("./offlineStore", () => ({
  syncMarker: vi.fn(async () => ({ offline, lastSyncAt: null, jobsToSend: 0 })),
  onSiteSince: vi.fn(async () => OPENED),
}));

// DEF-WRK-10644 (FB-013) — the bundle's steps and the job's money read. A
// test that sets neither gets the old shape: no steps, and no money read.
let tasks: { id: string; seq: number; ticked_at: string | null; money_fresh_minutes?: number | null }[] = [];
let money: Record<string, unknown> | null = null;
const moneyReads: string[] = [];
vi.mock("./mobileEndpoints", () => ({
  loadJob: vi.fn(async () => ({ order_no: "WO-4822", tasks })),
  loadJobMoney: vi.fn(async (orderId: string) => {
    moneyReads.push(orderId);
    if (money === null) throw new Error("offline");
    return money;
  }),
}));

// CR-168-BRC10 §F (FIELD-2) — the close goes through `capture`, which stamps
// the token and the fix and sends when there is a signal. Mocked here with the
// same contract: the item is recorded FIRST, then sent unless `send` is false.
let fix: { lat: number; lng: number; accuracy_m: number; fix_at: string } | null = null;
vi.mock("./location", () => ({
  startFix: vi.fn(),
  bestFix: vi.fn(async () => fix),
}));
vi.mock("./capture", () => ({
  capture: vi.fn(async (input: { orderId: string; kind: string; key: string; payload: Record<string, unknown>; send?: boolean }) => {
    const item = { ...input, seq: 20, capturedAt: new Date().toISOString(), location: fix };
    enqueued.push(item);
    if (input.send === false) return { item, sent: null };
    synced.push(input.orderId);
    const result =
      refusal === null
        ? { work_order_id: input.orderId, accepted: 1, duplicate: 0, refused: 0, items: [], synced_at: "" }
        : {
            work_order_id: input.orderId,
            accepted: 0,
            duplicate: 0,
            refused: 1,
            items: [{ key: input.key, kind: "close", seq: 20, result: "refused", detail: refusal }],
            synced_at: "",
          };
    return { item, sent: [result] };
  }),
}));

let blocking: { kind: string; scope: string; id: string; prompt: string }[] = [];
let missingPhotos: { kind: string; scope: string; id: string; prompt: string }[] = [];
vi.mock("./evidenceEndpoints", () => ({
  loadCloseReadiness: vi.fn(async () => ({
    can_close: blocking.length === 0,
    blocking,
    missing_photos: missingPhotos,
    flagged: [],
    readings_captured: 3,
    readings_total: 3,
    required_photos_taken: 2,
    required_photos_total: 2,
  })),
}));

import { ClosePane, PHONE_OUTCOMES, labourTimeProblem, reasonRequired } from "./ClosePane";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function mount() {
  return render(
    <MemoryRouter initialEntries={["/brazosbend/work/mobile/jobs/o1/close"]}>
      <Routes>
        <Route path="/:tenant/work/mobile/jobs/:orderId/close" element={<ClosePane />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);
beforeEach(() => {
  enqueued.length = 0;
  synced.length = 0;
  offline = false;
  refusal = null;
  blocking = [];
  missingPhotos = [];
  fix = null;
  tasks = [];
  money = null;
  moneyReads.length = 0;
});

describe("Work-012 · the close (CR-070 wave L)", () => {
  it("offers FOUR outcomes — `cancelled` is the dispatcher's and is not here", () => {
    // A picker that offered *Cancelled* would make cancelling look like a
    // decision a technician standing at the job may take. It is not.
    expect([...PHONE_OUTCOMES]).toEqual([
      "passed",
      "partially_done",
      "failed",
      "waiting_on_someone_else",
    ]);
    expect(PHONE_OUTCOMES as readonly string[]).not.toContain("cancelled");
  });

  it("TC-2 · the LABEL says what will happen — offline it says so", async () => {
    offline = true;
    mount();
    // `WS-12`'s offline label, and `BR-WRK-041`. A single *Close job* over a
    // phone with no signal is a promise the app cannot keep, and the technician
    // finds out at 18:00 when the office rings.
    await waitFor(() =>
      expect(screen.getByText(t("work.mobile.close.commitOffline"))).toBeTruthy(),
    );
  });

  it("online it reads plainly, and the two labels are different strings", async () => {
    mount();
    await waitFor(() => expect(screen.getByText(t("work.mobile.close.commit"))).toBeTruthy());
    expect(t("work.mobile.close.commit")).not.toBe(t("work.mobile.close.commitOffline"));
  });

  it("DEF-WRK-10798 · a Partly done close carries the SERVER's token, partially_done", async () => {
    // The server refuses anything outside `WORK_ORDER_OUTCOMES`
    // (`apps/work/connection_models.py`; `metering.work_order.outcome_unknown`).
    // This screen sent `partly_done`, so every Partly done close was refused.
    const SERVER_OUTCOMES = ["passed", "failed", "partially_done", "cancelled", "waiting_on_someone_else", PAID];
    mount();
    await waitFor(() => screen.getByText(t("work.mobile.close.outcomes.partly_done")));
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.partly_done")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() => expect(enqueued.length).toBe(1));
    const item = enqueued[0] as { payload: { outcome: string } };
    expect(item.payload.outcome).toBe("partially_done");
    for (const token of PHONE_OUTCOMES) expect(SERVER_OUTCOMES).toContain(token);
  });

  it("TC-1 · queues the close FIRST and then sends it — one path, two speeds", async () => {
    mount();
    await waitFor(() => screen.getByText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() => expect(enqueued.length).toBe(1));
    const item = enqueued[0] as { kind: string; payload: { outcome: string }; capturedAt: string };
    expect(item.kind).toBe("close");
    expect(item.payload.outcome).toBe("passed");
    // ⚠ THE HANDSET'S OWN TIME travels with it. `accept_field_result` dates
    // every meter read from it (`BR-WRK-003`), so a close that carried no time
    // would put an offline day's readings on the day they arrived.
    expect(item.capturedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    await waitFor(() => expect(synced).toEqual(["o1"]));
  });

  it("TC-2 · OFFLINE it queues and does NOT attempt the network", async () => {
    offline = true;
    mount();
    await waitFor(() => screen.getByText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commitOffline")));
    await waitFor(() => expect(enqueued.length).toBe(1));
    expect(synced).toEqual([]);
  });

  it("TC-5 · the key is minted AT CAPTURE, so a second tap queues the same one", async () => {
    mount();
    await waitFor(() => screen.getByText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() => expect(enqueued.length).toBe(1));
    const key = (enqueued[0] as { key: string }).key;
    // The key is derived from the order and the capture MINUTE, so a double tap
    // on a laggy screen writes the same record rather than a second close.
    // (`enqueue` is a keyed put — this asserts the key's shape, which is the
    // half this component owns.)
    expect(key).toContain("o1");
    expect(key.startsWith("close-")).toBe(true);
  });

  it("TC-7 · *Waiting on someone* needs a reason and refuses without one", async () => {
    expect(reasonRequired("waiting_on_someone_else")).toBe(true);
    expect(reasonRequired("passed")).toBe(false);
    mount();
    await waitFor(() => screen.getByText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(
      screen.getByLabelText(t("work.mobile.close.outcomes.waiting_on_someone_else")),
    );
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() =>
      expect(screen.getByText(t("work.mobile.close.reason_required"))).toBeTruthy(),
    );
    // Nothing queued — the job is not closed and must not look closed.
    expect(enqueued.length).toBe(0);
  });

  it("BR-WRK-040 SUPERSEDED 2026-10-21 — a missing REQUIRED photograph WARNS and the close goes", async () => {
    blocking = [];
    missingPhotos = [
      { kind: "missing_required_photo", scope: "reading", id: "rd-2", prompt: "Opening read" },
      { kind: "missing_required_photo", scope: "task", id: "tk-1", prompt: "Meter seal" },
    ];
    mount();
    await waitFor(() => expect(screen.getByTestId("close-photos-missing")).toBeTruthy());
    expect(screen.getByTestId("close-photos-missing").textContent).toBe(
      t("work.mobile.close.blocked", { count: 2 }),
    );
    expect(screen.queryByTestId("close-blocked")).toBeNull();
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    const button = screen.getByText(t("work.mobile.close.commit")).closest("button");
    expect(button?.hasAttribute("disabled")).toBe(false);
    fireEvent.click(button as HTMLButtonElement);
    await waitFor(() => expect(enqueued.length).toBe(1));
  });

  it("TC-4 · an OLDER server that still sends the photo in `blocking` still stops the close", async () => {
    blocking = [
      { kind: "missing_required_photo", scope: "reading", id: "rd-2", prompt: "Opening read" },
    ];
    mount();
    await waitFor(() => expect(screen.getByTestId("close-blocked")).toBeTruthy());
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    const button = screen.getByText(t("work.mobile.close.commit")).closest("button");
    // ⚠ The ATTRIBUTE, not the substring: the kit emits `disabled:opacity-45` in
    // its class string on every button it draws (the trap `OrderDetailPage.
    // test.tsx` records twice).
    expect(button?.hasAttribute("disabled")).toBe(true);
    fireEvent.click(button as HTMLButtonElement);
    expect(enqueued.length).toBe(0);
  });

  it("a refused close shows the SERVER's sentence, not a wording of ours", async () => {
    refusal = { message: "Finish safety first." };
    mount();
    await waitFor(() => screen.getByText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    // `BR-SHL-025`: the server knows WHICH safety row is outstanding and the
    // phone does not. A generic line here would drift out of step with the rule.
    await waitFor(() => expect(screen.getByTestId("close-refusal").textContent).toBe(
      "Finish safety first.",
    ));
  });

  it("DEF-WRK-9625 · a refusal with a catalogue key is shown in the phone's own words", async () => {
    refusal = { message: "work.order.photos_still_needed", message_key: "work.order.photos_still_needed" };
    mount();
    await waitFor(() => screen.getByText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() => expect(screen.getByTestId("close-refusal").textContent).toBe(
      t("work.order.photos_still_needed"),
    ));
  });

  it("B14 rule 11 — the consequence precedes the commit and says what it is not", async () => {
    mount();
    await waitFor(() => expect(screen.getByText(t("work.mobile.close.consequence"))).toBeTruthy());
    // `WS-12`'s own last line, and `BR-MET-110`: closing does not switch the
    // supply on. Rule 32 gives the section ONE sentence.
    expect(t("work.mobile.close.consequence").split(".").filter((s) => s.trim()).length).toBe(1);
  });

  it("CR-168 §F · BR-WRK-061 — the close carries the job's best fix, and says how precise it is", async () => {
    fix = { lat: 29.5601, lng: -95.8072, accuracy_m: 8, fix_at: "2026-10-04T15:00:00.000Z" };
    mount();
    await waitFor(() => expect(screen.getByTestId("close-fix").textContent).toBe(t("work.mobile.close.fix", { metres: 8 })));
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() => expect(enqueued.length).toBe(1));
    expect((enqueued[0] as { location: unknown }).location).toEqual(fix);
  });

  it("CR-168 §F — no fix yet is a fact, never a refusal: the close still goes", async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId("close-fix").textContent).toBe(t("work.mobile.close.noFix")));
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() => expect(enqueued.length).toBe(1));
  });

  it("DEF-WRK-4127 · Arrived and Finished are pre-filled from the phone's clock and travel on the close", async () => {
    mount();
    const arrived = (await screen.findByLabelText(t("work.mobile.close.arrived"))) as HTMLInputElement;
    await waitFor(() => expect(arrived.value).toBe("2026-03-15T09:00"));
    const finished = screen.getByLabelText(t("work.mobile.close.finished")) as HTMLInputElement;
    expect(finished.value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    // The technician corrects the finish to 10:35 — the PO's worked figure.
    fireEvent.change(finished, { target: { value: "2026-03-15T10:35" } });
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() => expect(enqueued.length).toBe(1));
    const payload = (enqueued[0] as { payload: { arrived_at: string; finished_at: string } }).payload;
    expect(payload.arrived_at).toBe(new Date(2026, 2, 15, 9, 0).toISOString());
    expect(payload.finished_at).toBe(new Date(2026, 2, 15, 10, 35).toISOString());
  });

  it("DEF-WRK-4127 · a finish not after the arrival is refused on the phone and queues nothing", async () => {
    expect(labourTimeProblem("2026-03-15T10:35", "2026-03-15T09:00")).toBe("work.mobile.close.timesOutOfOrder");
    expect(labourTimeProblem("", "2026-03-15T09:00")).toBe("work.mobile.close.timesRequired");
    expect(labourTimeProblem("2026-03-15T09:00", "2026-03-15T10:35", new Date(2026, 2, 16))).toBeNull();
    mount();
    const finished = (await screen.findByLabelText(t("work.mobile.close.finished"))) as HTMLInputElement;
    fireEvent.change(finished, { target: { value: "2026-03-15T08:00" } });
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() =>
      expect(screen.getByTestId("close-refusal").textContent).toBe(t("work.mobile.close.timesOutOfOrder")),
    );
    expect(enqueued.length).toBe(0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-WRK-10644 (FB-013, PO rulings 2026-10-28) — the paid close, on the web
// phone shell exactly as on the phone: offered ONLY when the next step to do
// declares a payment check and a FRESH read (that step's own bar) shows the
// balance cleared; the snapshot travels as `field_data.money_seen`.
// ══════════════════════════════════════════════════════════════════════════

const PAID = "not_done_payment_received";
const MONEY_STEP = { id: "task-cut", seq: 2, ticked_at: null, money_fresh_minutes: 5 };

function aRead(minutesOld: number, owing = "0.0000") {
  const asAt = new Date(Date.now() - minutesOld * 60_000).toISOString();
  return {
    as_at: asAt,
    fresh_minutes: 5,
    withheld: null,
    owing: { amount: owing, display: owing.slice(0, -2), currency: "USD" },
    balance: { amount: owing, display: owing.slice(0, -2), currency: "USD" },
    currency: "USD",
    latest_payment: { amount: "312.4000", display: "312.40", currency: "USD", posted_at: "2026-03-15T09:30:00Z", cleared_at: null },
    charges: [],
    unavailable: [],
  };
}

describe("Work-012 · DEF-WRK-10644 — Not done — payment received (FB-013)", () => {
  it("a fresh cleared read on the next payment-check step offers it, chosen, with the remark, and sends the snapshot", async () => {
    tasks = [{ id: "task-1", seq: 1, ticked_at: "2026-03-15T09:10:00Z" }, MONEY_STEP];
    money = aRead(1);
    mount();
    const paid = (await screen.findByLabelText(t(`work.mobile.close.outcomes.${PAID}`))) as HTMLInputElement;
    expect(paid.checked).toBe(true);
    expect(screen.getByText(t("work.mobile.close.balanceCleared"))).toBeTruthy();
    const remark = screen.getByLabelText(t("work.mobile.close.remark")) as HTMLTextAreaElement;
    expect(remark.value).toBe(t("work.mobile.close.paidRemark"));
    fireEvent.click(screen.getByText(t("work.mobile.close.commit")));
    await waitFor(() => expect(enqueued.length).toBe(1));
    const payload = (enqueued[0] as { payload: { outcome: string; field_data: Record<string, unknown> } }).payload;
    expect(payload.outcome).toBe(PAID);
    expect(payload.field_data.reason).toBe(t("work.mobile.close.paidRemark"));
    const seen = payload.field_data.money_seen as Record<string, unknown>;
    expect(seen.task_id).toBe("task-cut");
    expect(seen.balance).toBe("0.0000");
    expect(seen.currency).toBe("USD");
    expect(seen.as_at).toBe((money as { as_at: string }).as_at);
    expect(typeof seen.checked_at).toBe("string");
    expect(seen.latest_payment).toEqual({ amount: "312.4000", at: "2026-03-15T09:30:00Z" });
  });

  it("a STALE read (older than the step's own bar) does not offer it — R17 is unchanged", async () => {
    tasks = [MONEY_STEP];
    money = aRead(20);
    mount();
    await waitFor(() => expect(moneyReads).toEqual(["o1"]));
    await screen.findByLabelText(t("work.mobile.close.outcomes.passed"));
    expect(screen.queryByLabelText(t(`work.mobile.close.outcomes.${PAID}`))).toBeNull();
    expect(screen.queryByText(t("work.mobile.close.balanceCleared"))).toBeNull();
  });

  it("a balance still owed does not offer it", async () => {
    tasks = [MONEY_STEP];
    money = aRead(1, "312.4000");
    mount();
    await waitFor(() => expect(moneyReads).toEqual(["o1"]));
    await screen.findByLabelText(t("work.mobile.close.outcomes.passed"));
    expect(screen.queryByLabelText(t(`work.mobile.close.outcomes.${PAID}`))).toBeNull();
  });

  it("no step declaring a payment check: it is never offered and the money is never read (R18)", async () => {
    tasks = [{ id: "task-1", seq: 1, ticked_at: null, money_fresh_minutes: null }];
    money = aRead(1);
    mount();
    await screen.findByLabelText(t("work.mobile.close.outcomes.passed"));
    await waitFor(() => expect(screen.getByText(t("work.mobile.close.commit"))).toBeTruthy());
    expect(moneyReads).toEqual([]);
    expect(screen.queryByLabelText(t(`work.mobile.close.outcomes.${PAID}`))).toBeNull();
  });

  it("the payment-check step already done (ticked): not offered — the step was not stopped", async () => {
    tasks = [{ ...MONEY_STEP, ticked_at: "2026-03-15T09:20:00Z" }];
    money = aRead(1);
    mount();
    await screen.findByLabelText(t("work.mobile.close.outcomes.passed"));
    await waitFor(() => expect(screen.getByText(t("work.mobile.close.commit"))).toBeTruthy());
    expect(screen.queryByLabelText(t(`work.mobile.close.outcomes.${PAID}`))).toBeNull();
  });

  it("on the paid close the photo is optional: no 'photographs still needed' line (the phone's FF-34)", async () => {
    tasks = [MONEY_STEP];
    money = aRead(1);
    missingPhotos = [{ kind: "photo", scope: "task", id: "t1", prompt: "Meter face" }];
    mount();
    const paid = (await screen.findByLabelText(t(`work.mobile.close.outcomes.${PAID}`))) as HTMLInputElement;
    expect(paid.checked).toBe(true);
    expect(screen.queryByTestId("close-photos-missing")).toBeNull();
    // Any other outcome still warns.
    fireEvent.click(screen.getByLabelText(t("work.mobile.close.outcomes.passed")));
    expect(screen.getByTestId("close-photos-missing")).toBeTruthy();
  });

  it("no signal (the read fails): not offered", async () => {
    tasks = [MONEY_STEP];
    money = null;
    mount();
    await waitFor(() => expect(moneyReads).toEqual(["o1"]));
    await screen.findByLabelText(t("work.mobile.close.outcomes.passed"));
    expect(screen.queryByLabelText(t(`work.mobile.close.outcomes.${PAID}`))).toBeNull();
  });
});
