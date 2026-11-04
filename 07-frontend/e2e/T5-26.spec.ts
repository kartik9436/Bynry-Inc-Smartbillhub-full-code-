// ── Trace ──────────────────────────────────────────────
// Journey:  T5-26 — Last-admin demotion (a tenant always keeps ≥1 active System
//           Admin). `08-qa/01-e2e/journeys/T5-26-last-admin-demotion.md` is the
//           spec; this file walks its five-row step table in order.
// Story:    US-IDN-006 (the user list and its role/status actions) ·
//           US-IDN-007 (invite/add a user) · US-IDN-001 (sign in)
//           Screens: S3 · S8 Users
// Rules:    BR-IDN-013 (the LAST active System Admin cannot be demoted,
//           deactivated or removed — by anyone, including themselves) ·
//           A4 role matrix (user management is admin-level) · BR-AUD-001
// Money:    NONE. No step renders a figure; `moneyTriple` is not called.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py seeds
//           exactly ONE user — Dana, System Admin — which is the journey's own
//           starting state.
// ───────────────────────────────────────────────────────
//
// THIS SPEC WRITES TO THE SESSION IT RIDES ON, so it is careful in one specific
// way: step 5's self-demotion is wrapped in a `finally` that restores Dana to
// System Admin. Every other spec in this batch signs in as her, and a suite
// that left the seeded owner a Billing Clerk would report seven unrelated
// failures for one cause. The restore is asserted, so a failed restore is
// itself reported rather than assumed.
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, signInEmail, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const SECOND_ADMIN_EMAIL = "t5-26-second-admin@brazosbendutilities.com";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface UserRow {
  id: string;
  email: string;
  role: string;
  status: string;
}

async function users(request: APIRequestContext): Promise<UserRow[]> {
  const response = await request.get(api("/users?per=100"));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { results: UserRow[] }).results;
}

async function dana(request: APIRequestContext): Promise<UserRow> {
  const found = (await users(request)).find((u) => u.email === signInEmail());
  expect(found, "the signed-in owner is not in the user list").toBeDefined();
  return found as UserRow;
}

async function activeAdmins(request: APIRequestContext): Promise<UserRow[]> {
  return (await users(request)).filter((u) => u.role === "system_admin" && u.status === "active");
}

journey("T5-26", "Last-admin demotion — a tenant always keeps ≥1 active System Admin", () => {
  // NOT serial: each row re-reads the user list, so the run reports which of
  // the journey's five hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — demoting the last System Admin is refused, and the row is unchanged", async ({
    page,
  }) => {
    await signIn(page);
    const admins = await activeAdmins(page.request);
    expect(
      admins.length,
      `this tenant has ${admins.length} active System Admins — the journey needs exactly one`,
    ).toBe(1);
    const me = admins[0];

    const response = await page.request.patch(api(`/users/${me.id}`), {
      data: { role: "billing_clerk" },
    });
    expect(
      response.status(),
      `demoting the last admin answered ${response.status()}: ${await response.text()}`,
    ).toBeGreaterThanOrEqual(400);
    expect(((await response.json()) as { br_ref: string | null }).br_ref).toBe("BR-IDN-013");

    const after = await dana(page.request);
    expect(after.role, "the user row must be unchanged").toBe("system_admin");
    expect(after.status).toBe("active");
  });

  test("step 2 — deactivating the last System Admin is refused", async ({ page }) => {
    await signIn(page);
    const me = await dana(page.request);
    const response = await page.request.post(api(`/users/${me.id}/deactivate`), { data: {} });
    expect(
      response.status(),
      `deactivating the last admin answered ${response.status()}: ${await response.text()}`,
    ).toBeGreaterThanOrEqual(400);
    expect(((await response.json()) as { br_ref: string | null }).br_ref).toBe("BR-IDN-013");
    expect((await dana(page.request)).status).toBe("active");
  });

  test("step 3 — removing the last System Admin is refused, and the S8 control says why", async ({
    page,
  }) => {
    await signIn(page);
    const me = await dana(page.request);
    const response = await page.request.delete(api(`/users/${me.id}`));
    expect(
      response.status(),
      `removing the last admin answered ${response.status()}: ${await response.text()}`,
    ).toBeGreaterThanOrEqual(400);
    expect((await activeAdmins(page.request)).length, "the admin count never touches 0").toBe(1);

    // IS-6: the control is disabled WITH its reason, not hidden.
    await page.goto(`/${tenant()}/settings/users`);
    await expect(page.locator("main")).toBeVisible();
    const row = page.getByRole("row").filter({ hasText: signInEmail() });
    await expect(row, "S8 Users must list the signed-in admin").toBeVisible();
    await expect(
      page.locator("main"),
      "BR-IDN-013 must be stated on screen, not only at the API",
    ).toContainText(/last|only.*admin|cannot/i);
  });

  test("step 4 — a Billing Clerk cannot reach the user-management surface at all", async ({
    page,
  }) => {
    await signIn(page);
    // The A4 role gate sits IN FRONT of the last-admin guard: user management
    // is admin-level, so a clerk is refused before BR-IDN-013 is even reached.
    const roles = await page.request.get(api("/roles"));
    expect(roles.status()).toBe(200);
    const codes = ((await roles.json()) as { roles: { code: string }[] }).roles.map((r) => r.code);
    expect(codes, "the 3-role model must include the Billing Clerk this step probes as").toContain(
      "billing_clerk",
    );

    // The clerk's own probe needs a clerk session. The seeded tenant has one
    // user, so this step CREATES the clerk and then signs in as them — which
    // needs a credential the invite flow does not hand back (NFR-14: v1 sends
    // no staff auth emails). Asserted as the gap it is.
    const created = await page.request.post(api("/users"), {
      data: { full_name: "T5-26 Priya", email: "t5-26-clerk@brazosbendutilities.com", role: "billing_clerk" },
    });
    expect(
      [200, 201, 409, 422],
      `adding the clerk answered ${created.status()}: ${await created.text()}`,
    ).toContain(created.status());
    const body = await created.text();
    expect(
      body,
      "to probe the role gate FROM BELOW the harness needs a usable credential for the " +
        "new user; the add-user response carries none and v1 sends no staff auth email (NFR-14)",
    ).toMatch(/temp_password|password|invite_token/i);
  });

  test("step 5 — RECOVERY: with a second admin present the guard releases", async ({ page }) => {
    await signIn(page);

    // Promote first — the journey's ratified order.
    const existing = (await users(page.request)).find((u) => u.email === SECOND_ADMIN_EMAIL);
    if (existing === undefined) {
      const created = await page.request.post(api("/users"), {
        data: { full_name: "T5-26 Second Admin", email: SECOND_ADMIN_EMAIL, role: "system_admin" },
      });
      expect(
        [200, 201],
        `adding the second admin answered ${created.status()}: ${await created.text()}`,
      ).toContain(created.status());
    } else if (existing.role !== "system_admin") {
      await page.request.patch(api(`/users/${existing.id}`), { data: { role: "system_admin" } });
    }
    expect(
      (await activeAdmins(page.request)).length,
      "the tenant must now carry two active System Admins",
    ).toBeGreaterThanOrEqual(2);

    // …and NOW the demotion the guard refused in step 1 passes.
    const me = await dana(page.request);
    try {
      const demote = await page.request.patch(api(`/users/${me.id}`), {
        data: { role: "executive" },
      });
      expect(
        [200, 201],
        `with two admins present the demotion answered ${demote.status()}: ${await demote.text()}`,
      ).toContain(demote.status());
      expect(
        (await activeAdmins(page.request)).length,
        "the admin count never touches 0 at any instant",
      ).toBeGreaterThanOrEqual(1);
    } finally {
      // Every other spec in this batch signs in as this user. Restore, and
      // ASSERT the restore, so a failure to restore is reported rather than
      // silently breaking seven unrelated journeys.
      const restore = await page.request.patch(api(`/users/${me.id}`), {
        data: { role: "system_admin" },
      });
      expect(
        [200, 201],
        `restoring the seeded owner's role answered ${restore.status()}`,
      ).toContain(restore.status());
      expect((await dana(page.request)).role).toBe("system_admin");
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-26 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) step 4 cannot sign in AS the clerk: the seeded tenant has one
//   user, the add-user response hands back no usable credential, and v1 sends
//   no staff auth email (NFR-14) — so the step asserts the missing credential
//   seam rather than faking a clerk session by forging a cookie, which
//   e2e/support/app.ts forbids on purpose · (2) step 5's self-demotion is
//   wrapped in `finally` and restored, because every other spec in this batch
//   signs in as the same user; the restore is asserted, not assumed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
