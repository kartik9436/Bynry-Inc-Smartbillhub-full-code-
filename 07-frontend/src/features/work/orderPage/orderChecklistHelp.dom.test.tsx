// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-WRK-9637 — a job's Checklist printed a held help document's
//           storage key (B14 rule 31). Lane TEMPLATES, CR-168-BRC10 round 4.
// ───────────────────────────────────────────────────────
//
// The checklist is the server's RECORDING; the one row added to it is the shape
// `GET /work-orders/{id}/checklist` answered on PostgreSQL for WO-0042 (a help
// document uploaded through the builder: `ref` is the stored document's id).
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import CHECKLIST from "../__fixtures__/server/work-order.open.checklist.json";
import type { OrderChecklist } from "../workEndpoints";
import { OrderChecklistTab } from "./OrderChecklist";

afterEach(() => cleanup());

const HELD = {
  id: "01a10716-e914-79fd-b58a-4fa2be7abf4c",
  seq: 4,
  kind: "document",
  label: "Meter exchange procedure (held)",
  ref: "01a10716-6e32-7e54-8405-97fd8a3e45c4",
};

function mountWith(help: unknown[]) {
  const list = { ...CHECKLIST, help } as unknown as OrderChecklist;
  render(
    <OrderChecklistTab
      orderId="o"
      shape="open"
      list={list}
      photos={[]}
      onOpenPhoto={() => undefined}
      regional={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}
    />,
  );
}

describe("DEF-WRK-9637 — no storage key is drawn as a help row's place", () => {
  it("a held document reads by its name alone; a typed place and a link still show", () => {
    mountWith([...CHECKLIST.help, HELD]);
    expect(screen.getByText("Meter exchange procedure (held)")).toBeTruthy();
    expect(document.body.textContent).not.toContain(HELD.ref);
    // The recorded typed place (a shelf code) is a place, not a key, and stays.
    expect(document.body.textContent).toContain("STD-WA-012");
    const link = screen.getByRole("link", { name: /youtube\.com/u });
    expect(link.getAttribute("href")).toBe("https://www.youtube.com/watch?v=dQw4w9WgXcQ");
  });
});
