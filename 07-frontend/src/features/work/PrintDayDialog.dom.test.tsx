// @vitest-environment jsdom
// CR-168-BRC10 round 6, lane SRV-5 — P6.3, ruling 3's *"a day's pack prints"*.
// The door is asserted by ADDRESS (hard-won law 2): the day picked, the
// technician by SLUG (B14 rule 31), and the route the server mounts.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { PrintDayDialog, dayPackHref } from "./PrintDayDialog";

const t = (key: string, options?: Record<string, unknown>) => i18n.t(key, options);
const tenantPath = (segment: string) => `/brazosbend${segment}`;

afterEach(cleanup);

describe("PrintDayDialog — a technician's day on paper", () => {
  it("builds the day pack's address for a technician and for a crew", () => {
    expect(dayPackHref(tenantPath, { technician: "r-patel" }, "2026-10-06")).toBe(
      "/api/brazosbend/work/print/day-pack?date=2026-10-06&technician=r-patel",
    );
    expect(dayPackHref(tenantPath, { crew: "crew-b" }, "2026-10-06")).toBe(
      "/api/brazosbend/work/print/day-pack?date=2026-10-06&crew=crew-b",
    );
  });

  it("offers today by default and opens the PDF for the day picked", async () => {
    const opened: string[] = [];
    let closed = false;
    render(
      <PrintDayDialog
        name="R. Patel"
        holder={{ technician: "r-patel" }}
        tenantPath={tenantPath}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        onClose={() => {
          closed = true;
        }}
        open={(href) => opened.push(href)}
      />,
    );
    expect(screen.getByText(t("work.print.dayTitle", { name: "R. Patel" }))).toBeTruthy();
    const input = document.getElementById("date") as HTMLInputElement;
    expect(input.value).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    fireEvent.change(input, { target: { value: "2026-10-07" } });
    fireEvent.click(screen.getByText(t("work.print.submit")));
    await waitFor(() => expect(opened.length).toBe(1));
    expect(opened[0]).toBe("/api/brazosbend/work/print/day-pack?date=2026-10-07&technician=r-patel");
    expect(closed).toBe(true);
  });
});
