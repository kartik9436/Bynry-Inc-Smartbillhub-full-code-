// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   DEF-MET-10633 — FB-003, the office half (PO ruling 2026-10-27:
//           "The office sees the position and its time; a late one reads
//           added at 18:35 beside the saved time").
// Rules:    BR-MET-1202 · B14 rules 31 (no photo id on screen), 33 (labels
//           ≤ 3 words, facts ≤ 6), 43 (a component, not inline code)
// ───────────────────────────────────────────────────────
// RED FIRST: before this lane the server served no `field_capture` and the
// reading's page drew no position at all — not the one taken at save, not a
// late one, not a photo's.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { FieldCapture } from "@/api/endpoints";

import { FieldPositionPanel } from "./FieldPositionPanel";

afterEach(cleanup);

const PHOTO_ID = "0199aa00-1111-7222-8333-444455556666";

function mount(capture: FieldCapture | null | undefined) {
  return render(<FieldPositionPanel capture={capture} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
}

describe("FieldPositionPanel — where the reader stood", () => {
  it("a late position reads 'added at' its own time beside the saved time (the PO's worked case)", () => {
    mount({
      // Saved 18:32:48 Chicago with no fix; a ±10 m fix at 18:35.
      captured_at: "2026-10-26T23:32:48+00:00",
      position: { lat: "29.785300", lng: "-95.824600", accuracy_m: "10.00", at: "2026-10-26T23:35:00+00:00", added: true },
      photos: [],
    });
    const panel = screen.getByTestId("field-position");
    expect(within(panel).getByTestId("field-position-point")).toHaveTextContent("29.785300, -95.824600 ±10 m");
    expect(within(panel).getByTestId("field-position-added")).toHaveTextContent("added at 18:35");
    expect(within(panel).getByTestId("field-position-saved")).toHaveTextContent("10/26/2026 18:32");
  });

  it("a position taken at save shows no 'added at'", () => {
    mount({
      captured_at: "2026-10-26T23:32:48+00:00",
      position: { lat: "29.785100", lng: "-95.824500", accuracy_m: "4.00", at: "2026-10-26T23:32:48+00:00", added: false },
      photos: [],
    });
    expect(screen.getByTestId("field-position-point")).toHaveTextContent("29.785100, -95.824500 ±4 m");
    expect(screen.queryByTestId("field-position-added")).toBeNull();
  });

  it("saved without one and none came: says so", () => {
    mount({ captured_at: "2026-10-26T23:32:48+00:00", position: null, photos: [] });
    expect(screen.getByTestId("field-position-point")).toHaveTextContent("No position");
  });

  it("each photo shows its own position, never its id", () => {
    mount({
      captured_at: "2026-10-26T23:32:48+00:00",
      position: null,
      photos: [
        { photo_id: PHOTO_ID, position: { lat: "29.785111", lng: "-95.824511", accuracy_m: "7.00", at: "2026-10-26T23:32:40+00:00", added: false } },
        { photo_id: "p-2", position: { lat: "29.785300", lng: "-95.824600", accuracy_m: "10.00", at: "2026-10-26T23:35:00+00:00", added: true } },
      ],
    });
    const rows = screen.getAllByTestId("field-position-photo");
    expect(rows[0].previousElementSibling).toHaveTextContent("Photo 1");
    expect(rows[0]).toHaveTextContent("29.785111, -95.824511 ±7 m");
    expect(rows[1]).toHaveTextContent("added at 18:35");
    expect(document.body.textContent).not.toContain(PHOTO_ID);
  });

  it("FB-019: a photo added after the reading was saved is listed with it, marked 'Added after saving'", () => {
    // The worked case: saved with 1 photo, 2 added after.
    mount({
      captured_at: "2026-10-28T14:14:00+00:00",
      position: null,
      photos: [
        { photo_id: "p-1", position: null, added_after_save: false },
        { photo_id: "p-2", position: null, added_after_save: true },
        { photo_id: "p-3", position: null, added_after_save: true },
      ],
    });
    const rows = screen.getAllByTestId("field-position-photo");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).queryByTestId("field-position-photo-after")).toBeNull();
    expect(within(rows[1]).getByTestId("field-position-photo-after")).toHaveTextContent(/^Added after saving$/);
    expect(within(rows[2]).getByTestId("field-position-photo-after")).toHaveTextContent(/^Added after saving$/);
    expect(rows[2].previousElementSibling).toHaveTextContent("Photo 3");
  });

  it("a read that did not come from the field draws nothing", () => {
    const { container } = mount(null);
    expect(container).toBeEmptyDOMElement();
    cleanup();
    expect(mount(undefined).container).toBeEmptyDOMElement();
  });
});
