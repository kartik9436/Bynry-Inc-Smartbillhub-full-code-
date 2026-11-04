// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Plan:    15-bulk-bill-run-build-plan.md T7 — "Every-link test: click every
//          link on every step; fail on a link that changes nothing"
// Rules:   changes row 42 (PO 2026-09-30: *"you have see on this screen but it
//          dones not go anywhere"*) · hard-won law 2, mirror half
// Story:   US-BIL-039 TC-9
// ───────────────────────────────────────────────────────
/**
 * EVERY LINK AND BUTTON, ON EVERY STEP, MUST DO SOMETHING.
 *
 * For each face of the page the test finds every enabled `<a>` and `<button>`
 * and, on a FRESH mount each time (so one press cannot mask the next):
 *
 *   * an `<a>` must carry a real address under the tenant (`/brazosbend/…`),
 *     never `#`, never empty, never protocol-relative `//…` — the shape that
 *     hid dead links on the portal (`DEF-CWP-3925`);
 *   * a `<button>` is pressed and something must change: the page's markup,
 *     the address, or a request made. A button that changes none of the three
 *     is a dead control, and the test names it.
 *
 * The ONE thing skipped is a control that already IS the current choice
 * (`aria-selected` / `-checked` / `-pressed` / `-current` true) — pressing the
 * current tab, tile or tag is a no-op by design.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CYCLE_ID, RUN_ID } from "./__fixtures__/bulkRunFixtures";
import type { FakeOptions } from "./__fixtures__/fakeClient";
import { TENANT, mountRun, where } from "./__fixtures__/mountRun";

afterEach(cleanup);

interface Face {
  name: string;
  options: FakeOptions;
  search: string;
  ready: () => Promise<void>;
}

const OPEN_RUN = `?run=${RUN_ID}`;

const FACES: Face[] = [
  {
    name: "Scope",
    options: { scope: "overlap" },
    search: "",
    ready: async () => {
      const select = await screen.findByLabelText(/^Cycle/);
      await waitFor(() => expect(select.querySelectorAll("option").length).toBeGreaterThan(1));
      fireEvent.change(select, { target: { value: CYCLE_ID } });
      fireEvent.change(screen.getByLabelText(/^Run name/), { target: { value: "September 2026" } });
      await screen.findByText("Fix 1 thing to start.");
      // Open Previous runs so its links are in the DOM too.
      fireEvent.click(screen.getByRole("button", { name: "Previous runs" }));
    },
  },
  {
    name: "Check",
    options: {},
    search: OPEN_RUN,
    ready: async () => {
      await screen.findByText(/Checked 1,406 accounts at/);
      fireEvent.click(screen.getByRole("button", { name: /^No reading/ }));
    },
  },
  {
    name: "Sign off",
    options: { phase: "calculated" },
    search: OPEN_RUN,
    ready: async () => {
      await screen.findAllByRole("button", { name: "Fix in Check" });
    },
  },
  {
    name: "Send",
    options: { phase: "authorised" },
    search: OPEN_RUN,
    ready: async () => {
      const box = await waitFor(() => {
        const found = document.querySelector("[data-acknowledge]");
        expect(found).not.toBeNull();
        return found as HTMLElement;
      });
      fireEvent.click(box);
    },
  },
  {
    name: "Sent",
    options: { phase: "issued" },
    search: OPEN_RUN,
    ready: async () => {
      await screen.findByText("1,369 bills sent");
      await waitFor(() => expect(document.querySelectorAll('[data-not-in-run-row="blocked"]').length).toBe(2));
      // Select a row so the catch-up action is live.
      fireEvent.click(document.querySelectorAll('[data-not-in-run="sent"] input[type="checkbox"]')[0]);
    },
  },
];

function controls(): HTMLElement[] {
  const page = document.querySelector('[data-screen="bulk-bill-run"]') as HTMLElement;
  return Array.from(page.querySelectorAll<HTMLElement>("a, button")).filter((element) => {
    if (element instanceof HTMLButtonElement && element.disabled) return false;
    for (const current of ["aria-selected", "aria-checked", "aria-pressed", "aria-current"]) {
      if (element.getAttribute(current) === "true") return false;
    }
    // A step already passed on the rail is a real door back; the current one
    // is disabled by the frame and skipped above.
    return true;
  });
}

function label(element: HTMLElement): string {
  return (element.getAttribute("aria-label") ?? element.textContent ?? "").trim() || element.outerHTML.slice(0, 80);
}

async function mounted(face: Face) {
  const fake = mountRun(face.options, face.search);
  await face.ready();
  return fake;
}

// BULK-CHG-42 (every link goes somewhere) · BULK-CHG-32 (Previous runs opens and its links work) · BULK-CHG-27 (plan T7)
describe("T7 — every link and button on every step does something", () => {
  for (const face of FACES) {
    it(`${face.name}: no dead link, no dead button`, async () => {
      await mounted(face);
      const count = controls().length;
      expect(count).toBeGreaterThan(3);
      const dead: string[] = [];
      for (let index = 0; index < count; index += 1) {
        cleanup();
        const fake = await mounted(face);
        const element = controls()[index];
        if (element === undefined) continue;
        if (element instanceof HTMLAnchorElement) {
          const href = element.getAttribute("href") ?? "";
          if (href === "" || href === "#" || href.startsWith("//") || !(href.startsWith(`/${TENANT}/`) || href.startsWith("#"))) {
            dead.push(`link "${label(element)}" → "${href}"`);
          }
          if (href.startsWith("#") && document.getElementById(href.slice(1)) === null) {
            dead.push(`link "${label(element)}" → missing target ${href}`);
          }
          continue;
        }
        const before = { html: document.body.innerHTML, calls: fake.calls.length, at: where.location };
        await act(async () => {
          fireEvent.click(element);
          await new Promise((resolve) => setTimeout(resolve, 30));
        });
        const after = { html: document.body.innerHTML, calls: fake.calls.length, at: where.location };
        if (before.html === after.html && before.calls === after.calls && before.at === after.at) {
          dead.push(`button "${label(element)}"`);
        }
      }
      expect(dead).toEqual([]);
    }, 120_000);
  }
});
