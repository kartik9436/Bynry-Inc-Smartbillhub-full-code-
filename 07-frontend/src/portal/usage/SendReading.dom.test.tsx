// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-042 (EP-CWP-08) — Screen: CWP-035 (blueprint `P21`)
// Defect:   DEF-CWP-10175
// Rules:    BR-CWP-067 / BR-CWP-074 (the screen judges nothing; it reports
//           *Received* or *Received – we will check it*) · US-CWP-042 TC-7 ·
//           B14 rules 31, 35 · 22-product-maintenance-process.md §6 questions
//           3 (labels attached), 7 (announced, not only shown)
// Tests:    this file
// Impacts:  src/portal/usage/SendReading.tsx
// ───────────────────────────────────────────────────────
/**
 * `CWP-035` mounted under the REAL portal route pattern (`/:tenant/portal/…`),
 * so every address the screen builds is the one a browser would follow — a bare
 * `MemoryRouter` makes `useParams().tenant` undefined and every link reads
 * `//portal/…`, which still passes a `toContain` (hard-won law 2's fixture
 * clause).
 */
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import { ApiError } from "@/api/client";

import type { PortalSelfReadFrame, PortalSelfReadResult } from "../api/portalClient";

let readFrame: () => Promise<PortalSelfReadFrame> = async () => {
  throw new Error("no behaviour set");
};
let send: (body: Record<string, string>) => Promise<PortalSelfReadResult> = async () => {
  throw new Error("no behaviour set");
};
const sent: Record<string, string>[] = [];

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getSelfReadFrame: () => readFrame(),
    sendReading: (_accountId: string, body: Record<string, string>) => {
      sent.push(body);
      return send(body);
    },
  };
});

const { SendReadingView, SEND_A_READING_PATH } = await import("./SendReading");
const { PORTAL_ROUTES } = await import("../routing/portalRoutes");
const { PORTAL_SCREENS } = await import("../routing/screenIds");

/** `US-CWP-042` §4 — Water · serial 88-40219, last read 153,040 on 31 Aug. */
const FRAME: PortalSelfReadFrame = {
  today: "2026-09-02",
  window: null,
  meters: [
    {
      meter: "M-88402",
      serial: "88-40219",
      service: "water",
      service_name: "Water",
      where: "Front boundary box",
      registers: [
        {
          register: "total",
          unit: "gal",
          last_reading: "153040.000000",
          last_read_on: "2026-08-31",
          expected_now: "153300",
        },
      ],
    },
  ],
};

const CLEAN: PortalSelfReadResult = {
  received: true,
  flagged: false,
  checks: [],
  used: "260.000000",
  unit: "gal",
  times_usual: null,
  read_on: "2026-09-02",
  reading: "153300",
};

function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/usage/submit"]}>
      <Routes>
        <Route path="/:tenant/portal/usage/submit" element={<SendReadingView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  sent.length = 0;
});

describe("CWP-035 — Send us your reading", () => {
  it("is routed at the drawing's own address and registered as CWP-035", () => {
    expect(SEND_A_READING_PATH).toBe("/usage/submit");
    expect(PORTAL_ROUTES.map((route) => route.path)).toContain("/usage/submit");
    expect(PORTAL_SCREENS.find((row) => row.id === "CWP-035")?.path).toBe("/usage/submit");
  });

  it("names the meter by service and SERIAL, with its last reading in the rail", async () => {
    readFrame = async () => FRAME;
    const { container } = draw();
    await screen.findByRole("heading", { level: 1, name: "Send us your reading" });
    const select = screen.getByLabelText("Which meter") as HTMLSelectElement;
    expect(select.selectedOptions[0]?.textContent).toBe("Water · 88-40219");
    // B14 rule 31 — the meter number is the option's VALUE, never its words.
    expect(container.textContent).not.toContain("M-88402");
    const rail = container.querySelector("[data-last-reading]");
    expect(rail?.textContent).toContain("153,040");
    expect(rail?.textContent).toContain("about 153,300");
    // The photo is held: its sentence, and no file input anywhere.
    expect(container.querySelector("[data-photo-picker='held']")?.textContent).toContain(
      "Photos cannot be sent yet",
    );
    expect(container.querySelector("input[type='file']")).toBeNull();
  });

  it("question 3 — every box has its label attached; the date opens on today", async () => {
    readFrame = async () => FRAME;
    draw();
    const date = (await screen.findByLabelText(/Date you read it/)) as HTMLInputElement;
    expect(date.value).toBe("2026-09-02");
    const dial = screen.getByLabelText(/The number on the dial/) as HTMLInputElement;
    expect(dial.getAttribute("aria-required")).toBe("true");
    expect(dial.getAttribute("aria-describedby")).toBe("sr-value-error");
  });

  it("cannot be sent until the number is typed, and says why", async () => {
    readFrame = async () => FRAME;
    draw();
    const button = await screen.findByRole("button", { name: "Send it" });
    expect(button).toBeDisabled();
    expect(button.getAttribute("title")).toBe("Type the number first");
  });

  it("a clean reading — sent with the meter number, answered Received, and ANNOUNCED", async () => {
    readFrame = async () => FRAME;
    send = async () => CLEAN;
    draw();
    fireEvent.change(await screen.findByLabelText(/The number on the dial/), {
      target: { value: "153300" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send it" }));
    // F-02 (`DEF-CWP-10547`): the answer is announced through the frame's
    // always-present region and focused; the block itself is `data-received`.
    const status = await waitFor(() => {
      const found = document.querySelector<HTMLElement>("[data-received]");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(status.textContent).toContain("Received");
    expect(status.textContent).not.toContain("we will check it");
    expect(sent).toEqual([
      { meter: "M-88402", register: "total", value: "153300", read_on: "2026-09-02" },
    ]);
    expect(
      document.querySelector("a[data-see-readings]")?.getAttribute("href"),
    ).toBe("/pine-hill/portal/readings");
  });

  it("BR-CWP-074 — a reading the check objects to is RECEIVED, and says it will be looked at", async () => {
    readFrame = async () => FRAME;
    send = async () => ({ ...CLEAN, flagged: true, checks: ["high"], times_usual: 19 });
    draw();
    fireEvent.change(await screen.findByLabelText(/The number on the dial/), {
      target: { value: "158940" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send it" }));
    // F-02 (`DEF-CWP-10547`): the answer is announced through the frame's
    // always-present region and focused; the block itself is `data-received`.
    const status = await waitFor(() => {
      const found = document.querySelector<HTMLElement>("[data-received]");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(status.textContent).toContain("Received – we will check it");
    expect(status.textContent).toContain("That is about 19 times your usual.");
  });

  it("a refused date is tied to the date box — invalid, described, and read aloud", async () => {
    readFrame = async () => FRAME;
    send = async () => {
      throw new ApiError(422, {
        code: "VAL-002",
        message_key: "portal.selfRead.refuse.future",
        params: {},
        field_errors: [
          { field: "read_on", code: "VAL-002", message_key: "portal.selfRead.refuse.future" },
        ],
      });
    };
    const { container } = draw();
    fireEvent.change(await screen.findByLabelText(/The number on the dial/), {
      target: { value: "153300" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send it" }));
    await waitFor(() =>
      expect(container.querySelector("#sr-date-error")?.textContent).toBe(
        "That date is in the future.",
      ),
    );
    const date = screen.getByLabelText(/Date you read it/);
    expect(date.getAttribute("aria-invalid")).toBe("true");
    expect(date.getAttribute("aria-describedby")).toBe("sr-date-error");
    expect(container.querySelector("#sr-date-error")?.getAttribute("aria-live")).toBe("polite");
  });

  it("TC-7 — switched off, the screen draws no form, only the refusal and a way back", async () => {
    readFrame = async () => {
      throw new ApiError(409, {
        code: "BIZ-STATE",
        message_key: "portal.selfRead.notOffered",
        params: {},
      });
    };
    const { container } = draw();
    await screen.findByText("Readings are not taken online here.");
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector("[data-way-out]")?.getAttribute("href")).toBe(
      "/pine-hill/portal/readings",
    );
  });
});
