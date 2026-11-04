// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-155-BRC09 — the Settings → Security redesign the PO approved on
//          2026-09-29, built from the images in
//          `05-prototype/security-redesign-2026-09-29/` (B14 rule 42).
// Rules:   B14 rule 8 (one dropdown style; zero native selects) ·
//          B14 rule 17 (an empty list says what is missing) ·
//          B14 rule 31 (no database id is the visible value of a field) ·
//          B14 rule 33 · B14 rule 43 · BR-IDN-019/020/025/026 as amended ·
//          BR-AUD-003 / BR-AUD-019 (the actor is a person or a named
//          automation) · hard rule 4 (audit_log is pruned; no row is exempt)
// ───────────────────────────────────────────────────────
// WHAT THIS FILE ASSERTS THAT THE OLDER ONE CANNOT.
//
// `SettingsSecurityTab.test.tsx` renders to a STRING and asks whether words
// are in it. That is the right instrument for "is this sentence on the page"
// and the wrong one for every question this redesign actually turns on:
//
//   · **ORDER.** Three cards in one row, then Save, then the audit card. A
//     `toContain` per card passes with them in any order at all, and "Save is
//     in view" was the single most visible thing wrong with the old screen.
//   · **CONTROL TYPE.** The PO ruled every value a dropdown and the three
//     tick boxes tick boxes. `toContain("Wrong passwords")` is true of a
//     label above a select, above a text box and above nothing.
//   · **WHERE THE OPTIONS CAME FROM.** A test that renders one fixture and
//     finds `15 minutes` passes just as happily against a list typed into the
//     screen — that is `DEF-IDN-7501` in one sentence, and it survived weeks
//     of a green suite. Every option assertion here is made TWICE, against
//     two servers offering different values, and the second fixture requires
//     the first one's values to be ABSENT.
//   · **A READ THAT HAS NOT ANSWERED.** Five rows, fewer than five, none at
//     all, and a failure are four different screens, and three of them are
//     invisible to a synchronous string render.
//
// ⚠ **MOUNTED UNDER `/:tenant/settings/security`, THE PATH `App.tsx` USES.**
// A bare `MemoryRouter` leaves `useParams().tenant` undefined and every
// address the screen builds comes out without a tenant in it — a wrong URL
// that reads as a perfectly good string to `toContain`, which is the fixture
// that hid the customer portal's dead front page (CLAUDE.md hard-won law 2).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { SecurityPolicy, SecurityPolicyChange } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { SecurityTab } from "@/features/identity/SettingsSecurityTab";

afterEach(cleanup);

const TENANT = "brazosbend";

/** The seed, with the server publishing all eight limits (CR-145 + DEF-IDN-7501). */
const POLICY: SecurityPolicy = {
  pw_min_length: 8,
  pw_require_mixed: true,
  pw_require_symbol: false,
  pw_expiry_days: 90,
  session_timeout_minutes: 30,
  ip_allowlist: ["203.0.113.0/24"],
  absolute_session_hours: 12,
  keep_signed_in_offered: true,
  keep_signed_in_days: 30,
  lockout_max_failed: 5,
  lockout_minutes: 15,
  field_capture_hours: 168, // PO 2026-10-21 — the field app's capture life, hours
  password_link_valid_days: 7, // CR-188-BRC10 — an emailed sign-in link's life, days
  limits: {
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

/** Five rows, exactly the shape `approved-auditcard-1440.png` draws. The
 *  second is the migration's own row — `BR-AUD-019`'s named automation. */
const FIVE_ROWS: SecurityPolicyChange[] = [
  {
    id: "01a062a7-9f7d-73e6-96e4-700cba033c73",
    changed_at: "2026-09-28T23:14:00Z",
    actor: { id: "u-1", name: "Vijay Bikkad" },
    field: "lockout_minutes",
    before: 30,
    after: 15,
  },
  {
    id: "01a062a7-9f7d-73e6-96e4-700cba033c74",
    changed_at: "2026-09-28T09:02:00Z",
    actor: { kind: "migration", name: "Product upgrade", version: null },
    field: "session_timeout_minutes",
    before: 480,
    after: 60,
  },
  {
    id: "01a062a7-9f7d-73e6-96e4-700cba033c75",
    changed_at: "2026-09-24T16:40:00Z",
    actor: { id: "u-2", name: "Dana Whitfield" },
    field: "ip_allowlist",
    before: [],
    after: ["203.0.113.0/24"],
  },
  {
    id: "01a062a7-9f7d-73e6-96e4-700cba033c76",
    changed_at: "2026-09-19T11:27:00Z",
    actor: { id: "u-1", name: "Vijay Bikkad" },
    field: "pw_expiry_days",
    before: null,
    after: 90,
  },
  {
    id: "01a062a7-9f7d-73e6-96e4-700cba033c77",
    changed_at: "2026-09-12T08:15:00Z",
    actor: { id: "u-2", name: "Dana Whitfield" },
    field: "keep_signed_in_offered",
    before: false,
    after: true,
  },
];

type AuditAnswer = { rows: SecurityPolicyChange[] } | "fail";

function server(policy: SecurityPolicy, audit: AuditAnswer) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: (async (input: unknown) => {
      const url = String(input);
      if (url.includes("/security-policy/field-app-pins")) {
        // OQ-FLD-12797 — the certificate card under the audit card.
        return new Response(
          JSON.stringify({
            pins: [
              {
                spki_sha256: "C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=",
                label: "ISRG Root X1",
                not_after: "2035-06-04",
                active: true,
                status: "valid",
                days_left: 3145,
              },
            ],
            source: "default",
            warning_days: 60,
            min_valid: 2,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/security-policy/audit")) {
        if (audit === "fail") {
          // What a server that has not built this read yet actually answers.
          return new Response(JSON.stringify({ code: "SYS-404" }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify(audit), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(policy), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch,
  });
}

function mount(policy: SecurityPolicy, audit: AuditAnswer): void {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/settings/security`]}>
          <Routes>
            <Route
              path="/:tenant/settings/security"
              element={
                <SecurityTab
                  readOnly={false}
                  client={server(policy, audit)}
                  timeZone="UTC"
                  dateFormat="DD-MMM-YY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Every element in the order the DOM holds it — the only way to assert an
 *  arrangement. `compareDocumentPosition` is what a reader's eye does. */
function domOrder(...nodes: (Element | null)[]): boolean {
  for (let i = 1; i < nodes.length; i += 1) {
    const before = nodes[i - 1];
    const after = nodes[i];
    if (before === null || after === null) {
      return false;
    }
    const mask = before.compareDocumentPosition(after);
    if ((mask & Node.DOCUMENT_POSITION_FOLLOWING) === 0) {
      return false;
    }
  }
  return true;
}

describe("CR-155-BRC09 — Settings → Security, as approved on 2026-09-29", () => {
  it("draws three cards in the drawn order, then Save, then the audit card", async () => {
    mount(POLICY, { rows: FIVE_ROWS });

    const headings = (await screen.findAllByRole("heading", { level: 3 })).map(
      (h) => h.textContent,
    );
    // Four headings for the arrangement the PO approved — the five-card grid
    // is gone, and so is the card whose whole content was a button. The
    // field app's certificate keys (OQ-FLD-12797) were a fifth from
    // 2026-10-24 and are HIDDEN while pinning is dormant (CR-195-BRC10, PO
    // 2026-10-28 "start A1"): the server's `field_app_pinning_enabled` is
    // false or absent here — the next test turns it on.
    expect(headings).toEqual(["Passwords", "Sessions", "Signing in", "Audit log"]);
    expect(screen.queryByText("Field app certificates")).toBeNull();

    // ⚠ SAVE BEFORE THE AUDIT CARD. It shipped BELOW THE FOLD under a
    // three-then-two grid, which is the single most visible thing this
    // redesign fixes, and a heading list cannot see it.
    const save = await screen.findByRole("button", { name: /Save security settings/i });
    const auditCard = document.querySelector("[data-security-audit-card]");
    const passwords = screen.getByRole("heading", { level: 3, name: "Passwords" });
    expect(domOrder(passwords, save, auditCard)).toBe(true);
  });

  it("shows the field app certificates card last when the server says pinning is enabled (CR-195-BRC10)", async () => {
    mount({ ...POLICY, field_app_pinning_enabled: true }, { rows: FIVE_ROWS });
    expect(await screen.findByRole("heading", { level: 3, name: "Field app certificates" })).toBeTruthy();
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings).toEqual([
      "Passwords",
      "Sessions",
      "Signing in",
      "Audit log",
      "Field app certificates",
    ]);
  });

  it("hides the card when the server says pinning is off, explicitly (CR-195-BRC10)", async () => {
    mount({ ...POLICY, field_app_pinning_enabled: false }, { rows: [] });
    await screen.findByRole("heading", { level: 3, name: "Audit log" });
    expect(screen.queryByRole("heading", { level: 3, name: "Field app certificates" })).toBeNull();
  });

  it("puts each control in the card the PO grouped it into", async () => {
    mount(POLICY, { rows: [] });
    await screen.findByRole("heading", { level: 3, name: "Audit log" });

    const cardOf = (title: string): HTMLElement =>
      screen.getByRole("heading", { level: 3, name: title }).closest("section") as HTMLElement;

    // Four, four, three — the counts the PO approved — and Sessions is FIVE
    // since 2026-10-21: the PO put the field app's capture life in Settings
    // (*"this should come from settings"*), and it is a sign-in length.
    expect(within(cardOf("Passwords")).getAllByLabelText(/.+/)).toHaveLength(4);
    // SIX since 2026-10-22 (`CR-188-BRC10`, PO *"don't do any hardcoding"*):
    // how long an emailed sign-in link lasts is a setting, and it is a
    // sign-in length too.
    expect(within(cardOf("Sessions")).getAllByLabelText(/.+/)).toHaveLength(6);
    expect(cardOf("Sessions").querySelector("#password_link_valid_days")).not.toBeNull();
    expect(cardOf("Sessions").querySelector("#field_capture_hours")).not.toBeNull();
    expect(within(cardOf("Signing in")).getAllByLabelText(/.+/)).toHaveLength(3);

    // And each one is in the card that answers its question. `Stay signed in`
    // left its own card because it answers HOW LONG A SESSION LASTS; the
    // lockout pair joined the address list because both answer WHO GETS IN.
    for (const id of ["pw_min_length", "pw_require_mixed", "pw_require_symbol", "pw_expiry_days"]) {
      expect(cardOf("Passwords").querySelector(`#${id}`)).not.toBeNull();
    }
    for (const id of [
      "session_timeout_minutes",
      "absolute_session_hours",
      "keep_signed_in_offered",
      "keep_signed_in_days",
    ]) {
      expect(cardOf("Sessions").querySelector(`#${id}`)).not.toBeNull();
    }
    for (const id of ["lockout_max_failed", "lockout_minutes", "ip_allowlist"]) {
      expect(cardOf("Signing in").querySelector(`#${id}`)).not.toBeNull();
    }
  });

  it("keeps the three tick boxes tick boxes (PO: “(a) Keep them as checkboxes”)", async () => {
    mount(POLICY, { rows: [] });
    await screen.findByRole("heading", { level: 3, name: "Audit log" });

    for (const id of ["pw_require_mixed", "pw_require_symbol", "keep_signed_in_offered"]) {
      const box = document.getElementById(id) as HTMLInputElement;
      expect(box.tagName).toBe("INPUT");
      expect(box.type).toBe("checkbox");
    }
    // A yes/no is a tick box everywhere in this product; making these three
    // dropdowns would break the screen's agreement with every other screen.
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("builds every dropdown from the SERVED limits — proved by a second server", async () => {
    // ⚠ **THIS IS THE CASE A HARD-CODED LIST MUST FAIL.** Asserting the seeded
    // values alone passes against literals typed into the screen, because the
    // literals held exactly those values — the shape of `DEF-IDN-7501`, which
    // survived weeks of a green suite. So the second fixture serves numbers
    // this file's first fixture never had, and requires the first set GONE.
    mount(POLICY, { rows: [] });
    await screen.findByRole("heading", { level: 3, name: "Audit log" });
    const seeded = (id: string): string[] =>
      Array.from((document.getElementById(id) as HTMLSelectElement).options).map(
        (o) => o.textContent ?? "",
      );
    expect(seeded("pw_min_length")).toEqual(["8 characters", "10 characters", "12 characters"]);
    expect(seeded("pw_expiry_days")).toEqual(["Never", "Every 90 days", "Every 180 days"]);
    expect(seeded("session_timeout_minutes")).toEqual([
      "15 minutes",
      "30 minutes",
      "45 minutes",
      "1 hour",
    ]);

    cleanup();

    // A different utility's server. Nothing below is written anywhere in
    // `07-frontend/src`.
    mount(
      {
        ...POLICY,
        pw_min_length: 14,
        pw_expiry_days: 365,
        session_timeout_minutes: 20,
        limits: {
          ...POLICY.limits,
          pw_min_length: { choices: [14, 16], default: 14 },
          pw_expiry_days: { choices: [365], default: 365 },
          session_timeout_minutes: { choices: [20, 120], default: 20 },
        },
      },
      { rows: [] },
    );
    await screen.findByRole("heading", { level: 3, name: "Audit log" });
    expect(seeded("pw_min_length")).toEqual(["14 characters", "16 characters"]);
    expect(seeded("pw_expiry_days")).toEqual(["Every 365 days"]);
    expect(seeded("session_timeout_minutes")).toEqual(["20 minutes", "2 hours"]);
  });

  it("follows the server when a RANGE becomes a CHOICE LIST, with no edit here", async () => {
    // ⚠ **THE SERVER LANE'S FOUR LISTS, ASSERTED BEFORE THEY LAND.** The PO
    // ruled every value a dropdown; four settings still arrive as `min`/`max`
    // and are drawn as typed numbers meanwhile, because typing their lists
    // into the screen is the defect above. This case is the promise that the
    // day `SETTING_LIMITS` publishes them the screen simply follows — a hold
    // with a test that fires when the hold expires (hard-won law 2).
    mount(POLICY, { rows: [] });
    await screen.findByRole("heading", { level: 3, name: "Audit log" });
    // Today: a text box, and the server's own range stated beside it.
    expect((document.getElementById("lockout_minutes") as HTMLElement).tagName).toBe("INPUT");
    expect(screen.getByText(/Between 5 and 60 minutes\./)).toBeInTheDocument();

    cleanup();

    mount(
      {
        ...POLICY,
        limits: {
          ...POLICY.limits,
          lockout_minutes: { choices: [5, 10, 15, 30, 45, 60], default: 15 },
        },
      },
      { rows: [] },
    );
    await screen.findByRole("heading", { level: 3, name: "Audit log" });
    const control = document.getElementById("lockout_minutes") as HTMLSelectElement;
    expect(control.tagName).toBe("SELECT");
    expect(Array.from(control.options).map((o) => o.textContent)).toEqual([
      "5 minutes",
      "10 minutes",
      "15 minutes",
      "30 minutes",
      "45 minutes",
      "1 hour",
    ]);
    // And the range help line goes with the range — a dropdown IS its range,
    // which is the drawing's own reason for deleting every one of them.
    expect(screen.queryByText(/Between 5 and 60 minutes\./)).not.toBeInTheDocument();
  });

  it("renders the audit card's five rows, each value the way its control renders it", async () => {
    mount(POLICY, { rows: FIVE_ROWS });
    const card = (await screen.findByRole("heading", { level: 3, name: "Audit log" })).closest(
      "section",
    ) as HTMLElement;
    const bodyRows = card.querySelectorAll("[data-security-audit-row]");
    expect(bodyRows).toHaveLength(5);

    expect(within(card).getByText("When")).toBeInTheDocument();
    expect(within(card).getByText("Who")).toBeInTheDocument();
    expect(within(card).getByText("Setting")).toBeInTheDocument();
    expect(within(card).getByText("Change")).toBeInTheDocument();

    // WHO is a person's NAME, and a named automation says what it is —
    // never a user id (B14 rule 31, BR-AUD-019).
    expect(within(card).getAllByText("Vijay Bikkad")).toHaveLength(2);
    expect(within(card).getByText("Product upgrade")).toBeInTheDocument();

    // SETTING is the same words the controls above use — read through the
    // same catalogue keys, so the two cannot say different things.
    expect(within(card).getByText("Lockout length")).toBeInTheDocument();
    expect(within(card).getByText("Sign out when idle")).toBeInTheDocument();
    expect(within(card).getByText("Allowed addresses")).toBeInTheDocument();

    // CHANGE: old struck through, new bold, both through the ONE formatter.
    // `480` reads as the control reads it, never as a raw integer.
    const timeoutRow = bodyRows[1] as HTMLElement;
    expect(timeoutRow.querySelector("s")?.textContent).toBe("8 hours");
    expect(timeoutRow.querySelector("strong")?.textContent).toBe("1 hour");
    // An allowlist that was empty says so in a word rather than as a blank.
    expect((bodyRows[2] as HTMLElement).querySelector("s")?.textContent).toBe("Empty");
    expect((bodyRows[2] as HTMLElement).querySelector("strong")?.textContent).toBe(
      "203.0.113.0/24",
    );
    // A boolean, and `Never`.
    expect((bodyRows[4] as HTMLElement).querySelector("s")?.textContent).toBe("Off");
    expect((bodyRows[4] as HTMLElement).querySelector("strong")?.textContent).toBe("On");
    expect((bodyRows[3] as HTMLElement).querySelector("s")?.textContent).toBe("Never");
  });

  it("renders FEWER than five honestly, and an empty state when there are none", async () => {
    // ⚠ **NOT A CORNER CASE.** `audit_log` is pruned on a retention schedule
    // and no row type is exempt (hard rule 4, PO 2026-09-23). A utility that
    // has not touched this tab since the last prune has nothing here. Five is
    // a ceiling, never a promise, and the card must not pad or invent.
    mount(POLICY, { rows: FIVE_ROWS.slice(0, 2) });
    let card = (await screen.findByRole("heading", { level: 3, name: "Audit log" })).closest(
      "section",
    ) as HTMLElement;
    expect(card.querySelectorAll("[data-security-audit-row]")).toHaveLength(2);
    expect(card.querySelector("[data-security-audit-empty]")).toBeNull();

    cleanup();

    mount(POLICY, { rows: [] });
    card = (await screen.findByRole("heading", { level: 3, name: "Audit log" })).closest(
      "section",
    ) as HTMLElement;
    expect(card.querySelectorAll("[data-security-audit-row]")).toHaveLength(0);
    // B14 rule 17 — what is missing, in five words. And no table at all: an
    // empty table with four headers reads as a rendering fault.
    expect(within(card).getByText("No changes recorded yet.")).toBeInTheDocument();
    expect(card.querySelector("table")).toBeNull();
  });

  it("says it could not load rather than drawing an empty log", async () => {
    // ⚠ **THE DIFFERENCE BETWEEN THE TWO SENTENCES IS THE WHOLE CASE.**
    // "Nothing has changed" and "we could not find out" are different facts
    // and only one of them is true when the read fails — and today the read
    // fails for everybody, because `GET /settings/security-policy/audit` is
    // the SERVER lane's and is not on the branch. A card that drew zero rows
    // here would tell every clerk in the product that their utility's
    // security settings have never been touched.
    mount(POLICY, "fail");
    const card = (await screen.findByRole("heading", { level: 3, name: "Audit log" })).closest(
      "section",
    ) as HTMLElement;
    expect(await within(card).findByText("We couldn’t load recent changes.")).toBeInTheDocument();
    expect(card.querySelector("[data-security-audit-empty]")).toBeNull();
    expect(card.querySelectorAll("[data-security-audit-row]")).toHaveLength(0);
    // The eight controls above are untouched — one failed read does not take
    // a working form down with it.
    expect(document.getElementById("pw_min_length")).not.toBeNull();
  });

  it("puts no database id and no internal code on the screen (B14 rule 31)", async () => {
    mount(POLICY, { rows: FIVE_ROWS });
    await screen.findByRole("heading", { level: 3, name: "Audit log" });
    const text = document.body.textContent ?? "";

    // Not one of the five row ids, though every row carries one as its key.
    for (const row of FIVE_ROWS) {
      expect(text).not.toContain(row.id);
    }
    // Nor a `security_policies` column name, which is what a SETTING column
    // built from `row.field` instead of the catalogue would print.
    for (const column of [
      "lockout_minutes",
      "session_timeout_minutes",
      "ip_allowlist",
      "pw_expiry_days",
      "keep_signed_in_offered",
    ]) {
      expect(text).not.toContain(column);
    }
    // Nor a raw wire value where a rendered one belongs.
    expect(text).not.toContain("480");
    expect(text).not.toContain("true");
  });

  it("drops a row for a setting this screen cannot name, rather than printing the column", async () => {
    // The mirror of the case above, and the reason the card filters at all:
    // the day the server grows a setting before the screen does, a row naming
    // it must not reach a clerk as `keep_signed_in_grace_days`.
    mount(POLICY, {
      rows: [
        ...FIVE_ROWS.slice(0, 2),
        {
          id: "01a062a7-9f7d-73e6-96e4-700cba033c99",
          changed_at: "2026-09-27T10:00:00Z",
          actor: { id: "u-1", name: "Vijay Bikkad" },
          field: "keep_signed_in_grace_days",
          before: 1,
          after: 3,
        },
      ],
    });
    const card = (await screen.findByRole("heading", { level: 3, name: "Audit log" })).closest(
      "section",
    ) as HTMLElement;
    expect(card.querySelectorAll("[data-security-audit-row]")).toHaveLength(2);
    expect(document.body.textContent ?? "").not.toContain("keep_signed_in_grace_days");
  });

  it("drops the removed copy and keeps the one help line the drawing keeps", async () => {
    mount(POLICY, { rows: [] });
    await screen.findByRole("heading", { level: 3, name: "Audit log" });
    const text = document.body.textContent ?? "";

    // The SECURITY kicker, under a tab already reading Security.
    expect(screen.queryByText("SECURITY")).not.toBeInTheDocument();
    // Rationale, at zero words on screen (B14 rule 33).
    expect(text).not.toContain("if your own address is not inside the ranges you enter");
    expect(text).not.toContain("actor, timestamp and before/after");
    // `(optional)` left the label — we mark what is required.
    expect(text).not.toContain("(optional)");
    // The platform facts moved from Access into Passwords, where they belong.
    const passwords = screen
      .getByRole("heading", { level: 3, name: "Passwords" })
      .closest("section") as HTMLElement;
    expect(within(passwords).getByText(/The last 5 passwords are blocked\./)).toBeInTheDocument();
    expect(within(passwords).getByText(/A temporary password lasts 7 days\./)).toBeInTheDocument();
    // The one help line kept: a fact a clerk cannot read off the control.
    expect(screen.getByText(/Applies to the next sign-in\./)).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-155-BRC09 (SEC-REDESIGN lane) · US-IDN-010@493ea2f
// generated: 2026-09-29, written against the approved images and proved RED
//   first — each case was run against a deliberately broken screen and the
//   failure it named is recorded in the CR.
// exceptions: the audit read is the SERVER lane's and is not on the branch,
//   so every row above is a fixture. The card's FAILURE case is the one that
//   matches the product today, and it is asserted for that reason.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
