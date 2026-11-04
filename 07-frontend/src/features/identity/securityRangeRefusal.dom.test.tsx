// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-145-BRC08 task F4 — when a value is out of range, show WHICH
//          field was refused and WHY, against that control.
// Rules:   BR-IDN-025 / BR-IDN-026 as amended (PO 2026-09-28, "Im okay with
//          these limit") — the lockout threshold, the lockout length, the hard
//          limit after sign-in and the "keep me signed in" window are ranges
//          the server validates · BR-SHL-017 (the field kit announces an error
//          with the input it belongs to) · BR-SHL-020 (plain language)
// ───────────────────────────────────────────────────────
// ⚠ **WHY THIS IS A DOM TEST AND NOT A STRING ASSERTION.** "The refusal shows
// on the right field" is a statement about WHERE a sentence is, and
// `renderToStaticMarkup(...).toContain("Choose between 5 and 60.")` is true of
// a page-level banner, of the wrong field's error slot, and of the right one —
// all three. The only assertion that can tell them apart reads the input's own
// `aria-describedby` and follows it to the element it names, which is also
// exactly what a screen reader does.
//
// ⚠ **AND THE REQUEST MUST HAVE BEEN ANSWERED BEFORE ANYTHING IS ASSERTED.**
// A `waitFor` that succeeds on its first tick reads the screen from BEFORE the
// save, where there is no error to find and no error to fail on — a lane on
// this project shipped a test that passed with its own fix removed that way.
// `findBy*` is used throughout: it retries until the element EXISTS, so it
// cannot pass before the mutation has rejected and re-rendered.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { SecurityPolicy } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { SecurityTab } from "@/features/identity/SettingsSecurityTab";

afterEach(cleanup);

const TENANT = "brazosbend";

const POLICY: SecurityPolicy = {
  pw_min_length: 8,
  pw_require_mixed: true,
  pw_require_symbol: false,
  pw_expiry_days: null,
  session_timeout_minutes: 60,
  ip_allowlist: [],
  absolute_session_hours: 12,
  keep_signed_in_offered: true,
  keep_signed_in_days: 30,
  lockout_max_failed: 5,
  lockout_minutes: 15,
  field_capture_hours: 168, // PO 2026-10-21 — the field app's capture life, hours
  password_link_valid_days: 7, // CR-188-BRC10 — an emailed sign-in link's life, days
  limits: {
    // The two password rows joined `SETTING_LIMITS` with `DEF-IDN-7501`'s
    // close; the values are the ones the server always enforced.
    pw_min_length: { choices: [8, 10, 12], default: 8 },
    pw_expiry_days: { choices: [null, 90, 180], default: null },
    session_timeout_minutes: { choices: [15, 30, 45, 60], default: 60 },
    absolute_session_hours: { min: 4, max: 12, default: 12 },
    keep_signed_in_offered: { boolean: true, default: true },
    keep_signed_in_days: { min: 1, max: 30, default: 30 },
    lockout_max_failed: { min: 3, max: 10, default: 5 },
    lockout_minutes: { min: 5, max: 60, default: 15 },
    field_capture_hours: { choices: [1, 12, 24, 36, 48, 72, 168, 336, 720], default: 168 },
    password_link_valid_days: { choices: [1, 2, 3, 7, 14], default: 7 },
  },
};

/**
 * A server that serves the policy and then refuses ONE named field, with the
 * range it would have accepted — which is the shape `B7` sends.
 */
function serverRefusing(field: string, min: number, max: number) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: (async (_input: unknown, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "GET") {
        return new Response(JSON.stringify(POLICY), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      // ⚠ THE FLAT G1 ENVELOPE, the shape `core/errors.py`'s `_envelope`
      // writes and `identity/services.py` raises for a range refusal
      // (`VAL-003`, `errors.identity.policy_invalid`). Until 2026-09-28 this
      // fixture wrapped it in `{ error: {...} }`, a shape the server has never
      // sent: `asEnvelope` then found no `message_key`, fell back to the
      // generic "Something went wrong", dropped every field error, and all
      // three cases failed against a server that does not exist.
      return new Response(
        JSON.stringify({
          code: "VAL-003",
          message_key: "errors.identity.policy_invalid",
          params: {},
          field_errors: [
            {
              field,
              code: "VAL-003",
              message_key: "errors.identity.value_out_of_range",
              params: { min, max },
            },
          ],
          br_ref: null,
          trace_id: "t-cr145-f4",
        }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }) as typeof fetch,
  });
}

function mountTab(client: ReturnType<typeof serverRefusing>) {
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN. A bare `MemoryRouter` with no
  // `/:tenant/...` route leaves `useParams().tenant` undefined, and every
  // address the tab builds then comes out `//settings/...` — a
  // protocol-relative URL to another host that reads as a perfectly good
  // string to `toContain`.
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/settings/security`]}>
          <Routes>
            <Route
              path="/:tenant/settings/security"
              element={<SecurityTab readOnly={false} client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The sentence a control actually announces — followed through the DOM the
 *  way a screen reader follows it, rather than searched for on the page. */
async function refusalOn(fieldId: string): Promise<string> {
  const input = (await screen.findByDisplayValue(
    (_v, el) => el?.id === fieldId,
  )) as HTMLInputElement;
  const described = input.getAttribute("aria-describedby") ?? "";
  const errorId = described.split(/\s+/).find((id) => id.endsWith("-error")) ?? "";
  expect(errorId).toBe(`${fieldId}-error`);
  return document.getElementById(errorId)?.textContent ?? "";
}

async function typeAndSave(fieldId: string, value: string): Promise<void> {
  const input = (await screen.findByDisplayValue(
    (_v, el) => el?.id === fieldId,
  )) as HTMLInputElement;
  fireEvent.change(input, { target: { value } });
  fireEvent.click(await screen.findByRole("button", { name: /Save security settings/i }));
}

describe("CR-145-BRC08 F4 — an out-of-range value names its own field", () => {
  it("renders the server's range against the lockout-length control, and nowhere else", async () => {
    mountTab(serverRefusing("lockout_minutes", 5, 60));
    await typeAndSave("lockout_minutes", "90");

    // The refusal lands on the control the server named, in the admin's words,
    // carrying the SERVER's numbers — not this file's.
    expect(await screen.findByText("Choose between 5 and 60.")).toBeInTheDocument();
    expect(await refusalOn("lockout_minutes")).toBe("Choose between 5 and 60.");

    // ⚠ AND NOWHERE ELSE — this is the half that separates "on the right field"
    // from "on the page". Its three sibling ranges announce nothing.
    const input = document.getElementById("lockout_minutes") as HTMLInputElement;
    expect(input).toHaveAttribute("aria-invalid", "true");
    for (const sibling of ["lockout_max_failed", "absolute_session_hours", "keep_signed_in_days"]) {
      const el = document.getElementById(sibling) as HTMLInputElement;
      expect(el).not.toHaveAttribute("aria-invalid");
      expect(el.getAttribute("aria-describedby") ?? "").not.toContain("-error");
    }
    // Exactly one control is carrying it — not a banner repeated per field.
    expect(screen.getAllByText("Choose between 5 and 60.")).toHaveLength(1);
  });

  it("follows the field the server names — a different field, a different control", async () => {
    // ⚠ THE SAME REASONING AS `F2`'s SECOND FIXTURE: asserting one field once
    // cannot tell a screen that READS `field` from a screen that always paints
    // the same box. Refusing a different field must move the sentence.
    mountTab(serverRefusing("lockout_max_failed", 3, 10));
    await typeAndSave("lockout_max_failed", "99");

    expect(await refusalOn("lockout_max_failed")).toBe("Choose between 3 and 10.");
    const untouched = document.getElementById("lockout_minutes") as HTMLInputElement;
    expect(untouched).not.toHaveAttribute("aria-invalid");
  });

  it("names the hard limit in hours when that is the field refused", async () => {
    mountTab(serverRefusing("absolute_session_hours", 4, 12));
    await typeAndSave("absolute_session_hours", "48");

    expect(await refusalOn("absolute_session_hours")).toBe("Choose between 4 and 12.");
    // Nothing was saved, so the box still holds what the admin typed and can
    // be corrected in place rather than retyped from scratch.
    expect((document.getElementById("absolute_session_hours") as HTMLInputElement).value).toBe(
      "48",
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-145-BRC08 task F4 (frontend lane SESS-FRONTEND)
// generated: 2026-09-28
// exceptions: the message key `errors.identity.value_out_of_range` is added by
//   this lane in the eleven catalogues and must be the key `B7` sends; a
//   different key on the wire reaches a clerk as SILENCE, not as an error,
//   which is what G18 exists to catch (reported to the backend lane).
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
