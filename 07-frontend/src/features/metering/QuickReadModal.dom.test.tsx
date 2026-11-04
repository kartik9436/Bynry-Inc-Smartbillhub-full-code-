// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   OQ-422 CLOSED 2026-08-27 — PO verbatim: *"(b) Accept and warn"*.
//           Screens: S25 (the "Add reading" action) · S28 (the hand-off)
// Story:    US-MET-012 (S25) · US-MET-007 (S28 steps 1–2, the pipeline reused)
// Rules:    BR-MET-140 (a counter reading on a meter with NO cycle is ACCEPTED
//           and WARNED) · BR-MET-129 (a collected reading is STORED — we may
//           warn, we may not reject) · BR-MET-122 (the neighbouring OFF-cycle
//           case, whose shape this borrows) · B14 (one warning vocabulary;
//           the danger tier is for destructive commits)
// ───────────────────────────────────────────────────────
// **THE POINT OF THIS FILE IS THAT THE WARNING IS ON THE SCREEN.**
//
// The worked case the PO ruled on: a clerk at the counter holds meter **M-5002**
// and a reading of **1,300 kWh** taken today, and the meter belongs to no route
// — or to a route on no cycle. Before 2026-08-27 the modal drew that absence as
// a muted grey line and the reading posted anyway. The PO chose *"(b) Accept and
// warn"*, and their reason was that **somebody should fix the route**.
//
// Every other check in this repo is blind to the difference:
//
//   · `tsc` cannot tell a muted line from a warning — both are a `<p>` with a
//     string in it.
//   · `G31` counts stylesheet classes and passes either way.
//   · `G33` measures REFUSAL copy, and this is deliberately not a refusal.
//   · The backend tests assert the PAYLOAD carries a reason, and a payload is
//     not a screen (hard-won law 2 — built is not wired).
//
// So it runs in jsdom and drives the real control: it types the meter number and
// TABS OUT of the box, exactly as a clerk does, and then asserts on rendered
// output — that the reason shown is the reason the server served, that the
// sentence saying the reading still posts is present, that the action which ends
// the warning is named, and that nothing about it is styled as an error.
//
// ────────────────────────────────────────────────────────────────────────────
// ⚠ AND FROM 2026-09-14 IT CARRIES THE WRONG-REGISTER TRAP — ENTRY 12's MR-25
// AND MR-31, WHICH IS THE RULING THE PO PUT FIRST
// ────────────────────────────────────────────────────────────────────────────
// PO, 2026-09-14, verbatim: *"Put this first. DEF-797 already cost 412 kW billed
// as 14 kWh — $154 against $4,532. Money path, so I'm not classifying it"*.
//
// A reading filed against the wrong register is PERMANENT — `supersede_read`
// takes a value and a reason, and migration `0007`'s trigger freezes the
// channel — so the register has to be impossible to mistake ON THE WAY IN.
//
// **Nothing else in this repo can see the difference.** `tsc` type-checks a
// string, so a box labelled `tou_on` and one labelled *On-peak · kWh* are the
// same to it. The backend tests assert a payload, and a payload is not a screen.
// No gate reads rendered output at all — B14's own status table says so about
// nearly every rule in it. So the cases at the bottom of this file are the only
// instrument there is, and they assert on the LABEL a clerk reads and on the
// CHANNEL the batch carries.
//
// ────────────────────────────────────────────────────────────────────────────
// PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7)
// ────────────────────────────────────────────────────────────────────────────
// Twice, each against the fault it is written for, and each reverted after.
//
//   1. **The warning put back the way it was before the ruling** — the muted
//      `m-0 text-sm` line the PO's *"(b) Accept and warn"* replaced:
//
//          AssertionError: expected 'm-0 text-sm' to contain 'border-l-warning-500'
//
//   2. **One generic sentence for both reasons**, the shortcut that sends a
//      clerk to the wrong screen:
//
//          Error: expect(element).toHaveTextContent()
//          Expected element to have text content:
//            Its route is on no cycle.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { formatMonthYear } from "@/components/DateCell";

import { QuickReadModal } from "./QuickReadModal";
import type { QuickReadContext, QuickReadRegisters } from "./QuickReadModal";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const METER_NO = "M-5002";
const PERIOD = "2026-08-01";
/** Q9 (PO 2026-09-14, *"as drawn"*) — the period reads as a MONTH, never as a
 *  calendar date whose day-of-month means nothing to anybody. */
const PERIOD_SHOWN = formatMonthYear(PERIOD, "UTC");

/** One register, which is what the counter case is. */
const ONE_REGISTER: QuickReadRegisters = {
  simple: true,
  channels: ["total"],
  channel_count: 1,
  default_channel: "total",
  absent_reason: null,
  hand_off_to: null,
};

/**
 * ⚠ **THE METER `DEF-797` WAS ABOUT.** A time-of-use meter carries registers
 * whose readings are different numbers about different things, and the register
 * a reading is filed against can never be changed afterwards.
 */
const THREE_REGISTERS: QuickReadRegisters = {
  simple: false,
  channels: ["tou_on", "tou_off", "total"],
  channel_count: 3,
  default_channel: null,
  absent_reason: null,
  hand_off_to: null,
};

/** The server could not read this meter's plan. It does NOT mean one register —
 *  guessing `total` here files one window's dial as a whole month's usage. */
const REGISTERS_UNKNOWN: QuickReadRegisters = {
  simple: false,
  channels: null,
  channel_count: null,
  default_channel: null,
  absent_reason: "plan_unreadable",
  hand_off_to: "upload",
};

afterEach(cleanup);

function ok<T>(data: T): ApiResponse<T> {
  return { ok: true, status: 200, data } as unknown as ApiResponse<T>;
}

/** `GET /reads/quick-context`, with the register set the case is about. */
function context(
  cycle: QuickReadContext["cycle"],
  registers: QuickReadRegisters = ONE_REGISTER,
  meter: Partial<QuickReadContext["meter"]> = {},
): QuickReadContext {
  return {
    meter: {
      id: "a-5002",
      asset_no: METER_NO,
      unit: "kWh",
      multiplier: "1",
      service: "electric",
      ...meter,
    },
    read_at: new Date().toISOString().slice(0, 10),
    registers,
    cycle,
    pipeline: {
      stage: "POST /read-batches",
      validate: "POST /read-batches/{id}/validate",
      commit: "POST /read-batches/{id}/post",
      note: "same_as_file_import",
    },
    // BR-MET-140 joined the payload's own rule list on 2026-08-27.
    rule_refs: ["BR-MET-049", "BR-MET-059", "BR-MET-014", "BR-MET-140"],
  };
}

const NO_ROUTE: QuickReadContext["cycle"] = {
  cycle: null,
  cycle_absent: {
    reason: "no_route",
    severity: "warning",
    accepted: true,
    action: "add_meter_to_route",
    rule_ref: "BR-MET-140",
  },
  route: null,
  period_month: PERIOD,
  read_window: null,
  in_window: null,
};

const ROUTE_HAS_NO_CYCLE: QuickReadContext["cycle"] = {
  cycle: null,
  cycle_absent: {
    reason: "route_has_no_cycle",
    severity: "warning",
    accepted: true,
    action: "assign_route_to_cycle",
    rule_ref: "BR-MET-140",
  },
  route: { id: "r-1", code: "RT-01" },
  period_month: PERIOD,
  read_window: null,
  in_window: null,
};

const ON_A_CYCLE: QuickReadContext["cycle"] = {
  cycle: { id: "c-1", code: "CY-001", name: "Cycle 1" },
  cycle_absent: null,
  route: { id: "r-1", code: "RT-01" },
  period_month: PERIOD,
  read_window: { from: "2026-08-01", to: "2026-08-10" },
  in_window: true,
};

/** Every write the modal makes, in the order it made them — so a case can ask
 *  WHAT WAS STAGED rather than only what was drawn. */
interface Posted {
  staged: { rows: { channel: string; reading: string; meter_id: string; read_date: string }[] }[];
}

function stubClient(
  cycle: QuickReadContext["cycle"],
  registers: QuickReadRegisters = ONE_REGISTER,
  posted?: Posted,
  meter: Partial<QuickReadContext["meter"]> = {},
): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === "/reads/quick-context") return ok(context(cycle, registers, meter) as T);
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      if (path === "/read-batches") {
        posted?.staged.push(body as Posted["staged"][number]);
        return ok({ id: "b-1" } as T);
      }
      if (path === "/read-batches/b-1/validate") return ok({ id: "b-1" } as T);
      if (path === "/read-batches/b-1/post") {
        return ok({ posted_reads: 3, batch_no: "RB-1", counts: { warnings: 0 } } as T);
      }
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

/**
 * Open the modal, type `M-5002`, TAB OUT of the box — the clerk's own path.
 *
 * ⚠ **THE BLUR IS THE LOOKUP, AND THAT IS WHY THIS TABS RATHER THAN CLICKING.**
 * Entry 12 draws the meter field with the helper *"We look it up."* and no
 * button beside it; the context is fetched when the clerk leaves the box, never
 * per keystroke — a per-character request asks the server about "M", "M-",
 * "M-4" and every one of those is a miss the clerk reads as an error.
 *
 * Deliberately NOT a seeded query cache: the lookup is the moment the product
 * gets to tell the clerk what meter they are about to write a number against.
 * A test that skipped it would prove the branch renders and prove nothing about
 * whether a clerk can reach it.
 */
async function lookUpMeter(
  cycle: QuickReadContext["cycle"],
  registers: QuickReadRegisters = ONE_REGISTER,
  posted?: Posted,
  meter: Partial<QuickReadContext["meter"]> = {},
): Promise<ReturnType<typeof userEvent.setup>> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <QuickReadModal
          onClose={() => {}}
          onPosted={() => {}}
          client={stubClient(cycle, registers, posted, meter)}
          t={t}
          dateFormat="MM/DD/YYYY"
        />
      </ToastProvider>
    </QueryClientProvider>,
  );

  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/meter number/i), METER_NO);
  await user.tab();
  await waitFor(() => expect(screen.getByTestId("quick-read-meter")).toBeInTheDocument());
  return user;
}

// ══════════════════════════════════════════════════════════════════════════
// BR-MET-140 — what the ruling asks of the screen
// ══════════════════════════════════════════════════════════════════════════
describe("BR-MET-140 — a meter on no cycle is accepted and WARNED", () => {
  it("tells the clerk the reading will still post, which is the half they need first", async () => {
    // BR-MET-129, restated by the ruling: *"we can give the warning, but we
    // cannot reject the reading"*. A warning without this sentence reads as a
    // refusal to a clerk with a customer standing in front of them — which is
    // answer (c), the one the PO was never offered.
    await lookUpMeter(NO_ROUTE);
    const panel = screen.getByTestId("quick-read-cycle-absent");
    expect(panel).toHaveTextContent(
      t("metering.quickRead.cycleAbsentAccepted", { period: PERIOD_SHOWN }),
    );
  });

  it("names the action that ends the warning, so somebody fixes the route", async () => {
    // The PO's own reason for choosing (b) over (a). A warning nobody can act
    // on is the quiet blank it replaced, in amber.
    await lookUpMeter(NO_ROUTE);
    // BR-MET-140 clause 3 — *"each followed by the action that fixes it"*, and
    // it is PER REASON: a clerk told the wrong one looks in the wrong place.
    expect(screen.getByTestId("quick-read-cycle-absent")).toHaveTextContent(
      t("metering.quickRead.cycleAbsentActionNoRoute"),
    );
  });

  it("shows the reason the SERVER served, never one generic sentence for both", async () => {
    // Two shapes, two fixes. `no_route` and `route_has_no_cycle` are different
    // faults, and a clerk told the wrong one looks in the wrong place.
    await lookUpMeter(NO_ROUTE);
    let panel = screen.getByTestId("quick-read-cycle-absent");
    expect(panel).toHaveTextContent(t("metering.quickRead.cycleAbsentNoRoute"));
    expect(panel).not.toHaveTextContent(t("metering.quickRead.cycleAbsentNoCycle"));
    expect(panel).toHaveAttribute("data-reason", "no_route");

    cleanup();

    await lookUpMeter(ROUTE_HAS_NO_CYCLE);
    panel = screen.getByTestId("quick-read-cycle-absent");
    expect(panel).toHaveTextContent(t("metering.quickRead.cycleAbsentNoCycle"));
    expect(panel).not.toHaveTextContent(t("metering.quickRead.cycleAbsentNoRoute"));
    expect(panel).toHaveAttribute("data-reason", "route_has_no_cycle");
  });

  it("is the WARNING tier and never the danger tier", async () => {
    // ⚠ **THE TIER IS THE RULING.** Nothing is wrong with the reading; the
    // configuration fault is ours. B14 reserves the danger tier for
    // destructive commits, and a red panel here would tell a clerk that the
    // number they just read off a meter is bad.
    await lookUpMeter(NO_ROUTE);
    const panel = screen.getByTestId("quick-read-cycle-absent");
    expect(panel.className).toContain("border-l-warning-500");
    expect(panel.innerHTML).toContain("text-warning-700");
    expect(panel.className).not.toContain("danger");
    expect(panel.innerHTML).not.toContain("danger");
    expect(panel).toHaveAttribute("role", "status"); // never role="alert"
  });

  it("never blocks the commit — the post button stays live", async () => {
    // The whole ruling in one assertion. Answer (c) was refusing; it was never
    // offered, and this is what would go red if a later lane "helpfully" gated
    // the post on a resolved cycle.
    await lookUpMeter(NO_ROUTE);
    expect(screen.getByRole("button", { name: t("metering.quickRead.submit") })).toBeEnabled();
  });

  it("no longer cites a CLOSED question anywhere on the screen", async () => {
    // ⚠ G38's law, one case on: a stated absence cites the row that will kill
    // it — and OQ-422 is CLOSED, so `data-tracks="OQ-422"` had to GO rather
    // than be re-worded. What replaces it is the REASON, which is something a
    // person can act on rather than an id out of our register (DEF-332: our
    // ids do not belong on a clerk's screen).
    await lookUpMeter(NO_ROUTE);
    expect(document.body.innerHTML).not.toContain("OQ-422");
    expect(document.body.innerHTML).not.toContain("BR-MET-140");
  });

  it("draws no warning at all when the meter HAS a cycle", async () => {
    // The mirror case, so the panel cannot quietly become furniture.
    await lookUpMeter(ON_A_CYCLE);
    expect(screen.queryByTestId("quick-read-cycle-absent")).toBeNull();
    expect(screen.getByTestId("quick-read-cycle")).toHaveTextContent(
      t("metering.quickRead.cycleLine", { cycle: "CY-001", period: PERIOD_SHOWN }),
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Q7 — THE WRONG-REGISTER TRAP (PO 2026-09-14, *"Put this first"*)
// entry 12 · MR-25 (grow the rows) · MR-31 (the register is a WORD)
// ══════════════════════════════════════════════════════════════════════════
describe("Q7 — the register is impossible to mistake on the way in", () => {
  it("MR-31: a register reads as a WORD, never as the served code", async () => {
    // The blueprint's own finding: *"this screen renders the register as the
    // served code — `tou_on`, not On-peak — because no signed vocabulary maps a
    // channel to a display word on this surface. The reads list DOES translate
    // it, so the same register reads two ways on two screens."*
    //
    // ⚠ It is asserted through the SAME catalogue prefix the reads list uses
    // (`metering.reads.channel.*`), because a second vocabulary is a second copy
    // free to drift (hard-won law 5) — a bare literal here would stay green
    // while the two screens disagreed.
    await lookUpMeter(ON_A_CYCLE, THREE_REGISTERS);

    expect(screen.getByLabelText(/On-peak/)).toBeInTheDocument();
    expect(t("metering.reads.channel.tou_on")).toBe("On-peak");
    // The code itself must not be anywhere a clerk can read it.
    expect(document.body.textContent ?? "").not.toContain("tou_on");
    expect(document.body.textContent ?? "").not.toContain("tou_off");
  });

  it("hard rule 3: every value box carries its UNIT in the label", async () => {
    // *A quantity NEVER travels without its unit.* `DEF-797` is what a bare
    // number box costs — 412 kW filed as 14 kWh, $154 against $4,532 — and on a
    // multi-register meter there are three boxes to get wrong instead of one.
    await lookUpMeter(ON_A_CYCLE, THREE_REGISTERS);

    for (const channel of THREE_REGISTERS.channels ?? []) {
      const label = t("metering.quickRead.registerLabel", {
        register: t(`metering.reads.channel.${channel}`),
        unit: "kWh",
      });
      expect(screen.getByLabelText(label, { exact: false })).toBeInTheDocument();
    }
  });

  it("a served meter with NO unit says so with a dash — it never assumes one", async () => {
    // Hard rule 3's own sentence: *a bare number is refused; a dash is the
    // honest answer.* Q9's ruling leans on this — the unit is *"always present
    // or its absence is stated"*.
    await lookUpMeter(ON_A_CYCLE, THREE_REGISTERS, undefined, { unit: "" });
    expect(screen.getByLabelText(/On-peak · —/)).toBeInTheDocument();
  });

  it("MR-25: a three-register meter asks for THREE numbers and stages three rows", async () => {
    // ⚠ **THIS IS THE CASE THE WHOLE ENTRY EXISTS FOR.** As built, a meter with
    // more than one register rendered NO value fields at all and sent the clerk
    // to a five-stage file wizard for two numbers. The modal has already fetched
    // `channels`, by name, so it grows the boxes instead — same form, same
    // endpoint, same pipeline.
    //
    // It asserts the STAGED ROWS and not only the drawn boxes, because a form
    // that collects three numbers and posts one of them against `total` looks
    // identical on screen and is the permanent error this screen prevents.
    const posted: Posted = { staged: [] };
    const user = await lookUpMeter(ON_A_CYCLE, THREE_REGISTERS, posted);

    await user.type(screen.getByLabelText(/On-peak/), "12480");
    await user.type(screen.getByLabelText(/Off-peak/), "31220");
    await user.type(screen.getByLabelText(/Total register/), "51710");
    await user.click(screen.getByRole("button", { name: t("metering.quickRead.submit") }));

    await waitFor(() => expect(posted.staged).toHaveLength(1));
    expect(posted.staged[0].rows.map((row) => row.channel)).toEqual([
      "tou_on",
      "tou_off",
      "total",
    ]);
    expect(posted.staged[0].rows.map((row) => row.reading)).toEqual(["12480", "31220", "51710"]);
    // One meter, one date — the only thing that varies is the register.
    expect(new Set(posted.staged[0].rows.map((row) => row.meter_id)).size).toBe(1);
    expect(new Set(posted.staged[0].rows.map((row) => row.read_date)).size).toBe(1);
  });

  it("refuses to post until EVERY register has a number", async () => {
    // *All of them post together.* Two of three filed is a hole in a month
    // nobody can correct: the register of a filed reading can never be changed
    // (`supersede_read` takes a value and a reason; `0007`'s trigger freezes the
    // channel).
    const posted: Posted = { staged: [] };
    const user = await lookUpMeter(ON_A_CYCLE, THREE_REGISTERS, posted);

    await user.type(screen.getByLabelText(/On-peak/), "12480");
    await user.click(screen.getByRole("button", { name: t("metering.quickRead.submit") }));

    expect(posted.staged).toHaveLength(0);
    expect(screen.getAllByText(t("metering.quickRead.error.readingRequired")).length).toBe(2);
  });

  it("a ONE-register meter posts against the meter's OWN register, not a hardcoded total", async () => {
    // `default_channel` is the server's answer, and a single-register meter
    // whose plan names something other than `total` gets THAT one. The panel
    // names it in words so the clerk can see which register they write into.
    const posted: Posted = { staged: [] };
    const user = await lookUpMeter(
      ON_A_CYCLE,
      { ...ONE_REGISTER, channels: ["demand"], default_channel: "demand" },
      posted,
    );

    expect(screen.getByTestId("quick-read-meter")).toHaveTextContent(
      t("metering.reads.channel.demand"),
    );
    await user.type(screen.getByLabelText(/Reading/), "412");
    await user.click(screen.getByRole("button", { name: t("metering.quickRead.submit") }));

    await waitFor(() => expect(posted.staged).toHaveLength(1));
    expect(posted.staged[0].rows).toHaveLength(1);
    expect(posted.staged[0].rows[0].channel).toBe("demand");
  });

  it("when the server cannot say what the registers ARE, it refuses instead of guessing", async () => {
    // ⚠ **THE HAND-OFF THAT SURVIVES MR-25, AND IT IS THE ONLY ONE.**
    // `channels: null` means the plan could not be read — NOT that the meter has
    // one register. Defaulting to `total` there files one window's dial as a
    // whole month's usage, permanently. Q6's shape (PO 2026-09-14): the refusal
    // is a STATE, so the commit is DISABLED with its reason rather than removed.
    await lookUpMeter(ON_A_CYCLE, REGISTERS_UNKNOWN);

    expect(screen.getByTestId("quick-read-registers-unknown")).toHaveTextContent(
      t("metering.quickRead.registersUnknown"),
    );
    expect(screen.queryByLabelText(/Reading/)).toBeNull();
    expect(screen.getByRole("button", { name: t("metering.quickRead.submit") })).toBeDisabled();
  });

  it("B14 rule 31: nothing internal reaches this screen", async () => {
    // The meter's uuid and the channel codes are both in hand here and neither
    // is a thing a clerk reads. A catalogue PATH is the other way this breaks —
    // `channelWord`'s fallback is the code precisely so a miss never renders
    // `metering.reads.channel.x` at a clerk.
    await lookUpMeter(ON_A_CYCLE, THREE_REGISTERS);
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("a-5002"); // the asset's own id
    expect(text).not.toContain("metering."); // a catalogue path
    expect(text).not.toContain("tou_");
  });
});
