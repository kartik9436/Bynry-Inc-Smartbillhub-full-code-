// @vitest-environment jsdom
/**
 * BR-MET-1189 (PO 2026-10-04, DEF-WRK-9642) — the meter's reading list marks
 * which of two same-day readings counts. E-5000: the office's 3,400 kWh is
 * *Kept as history*, the technician's 3,412 kWh *Counts for billing*, and a
 * reading alone on its date draws nothing at all.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import i18n from "i18next";
import { afterEach, describe, expect, it } from "vitest";

import { CountedReadingPill } from "./readsShared";

const t = i18n.t.bind(i18n);

afterEach(cleanup);

describe("CountedReadingPill", () => {
  it("names the reading that counts", () => {
    render(<CountedReadingPill counts={true} t={t} />);
    expect(screen.getByText("Counts for billing")).toBeInTheDocument();
  });

  it("names the sibling kept as history", () => {
    render(<CountedReadingPill counts={false} t={t} />);
    expect(screen.getByText("Kept as history")).toBeInTheDocument();
  });

  it("draws nothing for a reading alone on its date", () => {
    const { container } = render(<CountedReadingPill counts={null} t={t} />);
    expect(container).toBeEmptyDOMElement();
  });
});
