// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:   DEF-CWP-10550 (F-18) · DEF-CWP-10547 (F-02) · DEF-CWP-10552 (F-04)
// Ruling:   PO/QA 2026-10-23 (decision log "three product answers", point 1):
//           a badly formed email gets a field error BEFORE sending, an empty
//           password gets "Enter your password.", and the one sentence for a
//           wrong email or password is unchanged (BR-CWP-004, BR-CWP-038).
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalFront } from "../api/guestClient";
import { PortalAnnouncer } from "../components/a11y";

const tried: unknown[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    signIn: async (body: unknown) => {
      tried.push(body);
      throw new Error("401");
    },
  };
});

const { FrontDoorView } = await import("./FrontDoor");

const FRONT: PortalFront = {
  tenant: { slug: "pine-hill", name: "Pine Hill", brand_primary_hex: null, brand_accent_hex: null },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: null },
  locales: ["en", "es"],
  cards: [],
  links: { help: true, visit: true },
  switches: undefined,
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
};

function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/sign-in"]}>
      <PortalAnnouncer>
        <Routes>
          <Route path="/:tenant/portal/sign-in" element={<FrontDoorView front={FRONT} />} />
        </Routes>
      </PortalAnnouncer>
    </MemoryRouter>,
  );
}

const press = () => fireEvent.click(screen.getByRole("button", { name: /Sign in/ }));
const fieldError = (id: string) => document.getElementById(`${id}-error`)?.textContent ?? "";
const alertText = () => document.querySelector("[data-portal-alert]")?.textContent ?? "";

afterEach(() => {
  cleanup();
  tried.length = 0;
});

describe("F-18 · sign in checks what was typed before it is sent", () => {
  it("both boxes empty: two field errors, both boxes marked, the summary focused, nothing sent", () => {
    draw();
    press();
    expect(tried).toEqual([]);
    expect(fieldError("portal-email")).toBe("Please enter your email.");
    expect(fieldError("portal-password")).toBe("Enter your password.");
    for (const id of ["portal-email", "portal-password"]) {
      const box = document.getElementById(id)!;
      expect(box).toHaveAttribute("aria-invalid", "true");
      expect(box).toHaveAttribute("aria-required", "true");
      expect(box.getAttribute("aria-describedby")).toContain(`${id}-error`);
    }
    expect(document.activeElement).toBe(document.querySelector("[data-error-summary]"));
    expect(alertText()).toContain("Enter your password.");
    // The account-agnostic sentence is NOT used for an empty form.
    expect(document.querySelector("[data-signin-refused]")).toBeNull();
  });

  it("a malformed email gets the ruled sentence and nothing is sent", () => {
    draw();
    fireEvent.change(document.getElementById("portal-email")!, { target: { value: "maria@" } });
    fireEvent.change(document.getElementById("portal-password")!, { target: { value: "x" } });
    press();
    expect(tried).toEqual([]);
    expect(fieldError("portal-email")).toBe("Enter a full email, like name@example.com.");
    expect(fieldError("portal-password")).toBe("");
  });

  it("a well-formed email and a password are SENT, and a refusal is the one unchanged sentence — announced and focused", async () => {
    draw();
    fireEvent.change(document.getElementById("portal-email")!, { target: { value: "maria@example.invalid" } });
    fireEvent.change(document.getElementById("portal-password")!, { target: { value: "wrong-one" } });
    press();
    await waitFor(() => expect(document.querySelector("[data-signin-refused]")).not.toBeNull());
    expect(tried).toHaveLength(1);
    const refused = document.querySelector("[data-signin-refused]");
    expect(refused?.textContent).toBe("Those details do not match.");
    expect(document.activeElement).toBe(refused);
    expect(alertText()).toBe("Those details do not match.");
  });
});

// The F-18 sentence is six words in English (PO/QA 2026-10-23, "yes the
// shorter one"; decision log "The F-18 email sentence is six words").
const F18_CATALOGUES = import.meta.glob("../../i18n/locales/*.json", { eager: true, import: "default" }) as Record<
  string,
  Record<string, string>
>;
describe("F-18 · the email sentence is the ruled six words", () => {
  it("English and Spanish carry the ruled words, and every catalogue has the key", () => {
    expect(Object.keys(F18_CATALOGUES)).toHaveLength(11);
    for (const [file, cat] of Object.entries(F18_CATALOGUES)) expect(cat["portal.form.emailFormat"], file).toBeTruthy();
    const en = F18_CATALOGUES["../../i18n/locales/en.json"]["portal.form.emailFormat"];
    expect(en).toBe("Enter a full email, like name@example.com.");
    expect(en.split(/\s+/)).toHaveLength(6);
    expect(F18_CATALOGUES["../../i18n/locales/es.json"]["portal.form.emailFormat"].split(/\s+/)).toHaveLength(6);
  });
});
