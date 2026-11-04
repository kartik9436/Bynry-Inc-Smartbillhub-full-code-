// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-WRK-10601 — the phone's *Unable to read* reached the office as
//           nothing at all (refused at sync). Now stored, it must READ as the
//           technician's answer on the order's Readings, never as *Not taken*.
// ───────────────────────────────────────────────────────
//
// The checklist is the server's RECORDING (`work-order.completed.checklist.json`)
// with the two fields `apps/work/checklist.checklist()` now serves on a reading.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import CHECKLIST from "../__fixtures__/server/work-order.completed.checklist.json";
import type { OrderChecklist } from "../workEndpoints";
import { OrderChecklistTab } from "./OrderChecklist";

afterEach(() => cleanup());

function mountWith(patch: Record<string, unknown>) {
  const [first, ...rest] = CHECKLIST.readings;
  const list = {
    ...CHECKLIST,
    readings: [{ ...first, value: null, value_text: null, ...patch }, ...rest],
  } as unknown as OrderChecklist;
  render(
    <OrderChecklistTab
      orderId="o"
      shape="completed"
      list={list}
      photos={[]}
      onOpenPhoto={() => undefined}
      regional={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}
    />,
  );
  return document.querySelector(`[data-reading-row="${first.seq}"]`) as HTMLElement;
}

describe("DEF-WRK-10601 — Unable to read on the order's Readings", () => {
  it("reads as Unable to read with the technician's reason", () => {
    const row = mountWith({ unable_to_read: true, unable_reason: "Meter buried" });
    expect(row.textContent).toContain("Unable to read · Meter buried");
    expect(row.textContent).not.toContain("Not taken");
  });

  it("reads as Unable to read alone when the phone sent no reason", () => {
    const row = mountWith({ unable_to_read: true, unable_reason: null });
    expect(row.textContent).toContain("Unable to read");
    expect(row.textContent).not.toContain("·");
  });

  // DEF-MET-10609 — the reason is a code from the ONE can't-read list; the
  // office reads its NAME and the technician's note, never the code.
  it("reads the reason's name from the list, never its code", () => {
    const row = mountWith({ unable_to_read: true, unable_reason: "dog", unable_reason_name: "Dog" });
    expect(row.textContent).toContain("Unable to read · Dog");
    expect(row.textContent).not.toContain("dog");
  });

  it("shows the technician's note under the answer", () => {
    const row = mountWith({
      unable_to_read: true,
      unable_reason: "dog",
      unable_reason_name: "Dog",
      unable_note: "Barking at the gate",
    });
    expect(row.querySelector("[data-reading-note]")?.textContent).toBe("Barking at the gate");
  });

  it("a text reading reads as typed", () => {
    const row = mountWith({ kind: "text", value_text: "W-5000-N", unable_to_read: false });
    expect(row.textContent).toContain("W-5000-N");
  });
});
