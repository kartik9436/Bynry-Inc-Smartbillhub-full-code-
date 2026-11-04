// ── Trace ──────────────────────────────────────────────
// Journey:  T5-25 — IP allowlist self-lockout (the guard refuses the save that
//           locks you out). `08-qa/01-e2e/journeys/T5-25-ip-self-lockout-guard.md`
//           is the spec; this file walks its six-row step table in order.
// Story:    US-IDN-010 (S8 Security — password policy · session timeout · IP
//           allowlist) · US-IDN-001 (sign in)
//           Screens: S3 · S8 Security
// Rules:    BR-IDN-020 (valid IPv4 CIDRs; empty = unrestricted; enforced at
//           sign-in AND per request; the SAVING ADMIN'S current IP must fall
//           inside the new list) · BR-IDN-019 (one tenant-wide record, atomic
//           save, before/after audit) · NFR-12
// Money:    NONE. No step renders a figure; `moneyTriple` is not called.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py — the
//           seeded policy has `ip_allowlist: []` (unrestricted), which is the
//           journey's own starting state.
// ───────────────────────────────────────────────────────
//
// THE HARNESS'S OWN IP IS THE FIXTURE. The journey pins Dana to 203.0.113.7;
// this spec's caller is Playwright on the loopback, so the CIDR that EXCLUDES
// the saving admin is any range that does not contain 127.0.0.1, and the one
// that INCLUDES her is 127.0.0.0/8. Both are documented TEST-NET / loopback
// ranges, so nothing here depends on where the stack happens to run.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

// The journey's own excluding range (TEST-NET-2, RFC 5737).
const EXCLUDES_ME = "198.51.100.0/24";
// Loopback — the harness's own address, so this list INCLUDES the saving admin.
const INCLUDES_ME = "127.0.0.0/8";
const MALFORMED = ["300.1.1.0/24", "198.51.100.0/33", "not-an-address"];

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface Policy {
  ip_allowlist: string[];
  session_timeout_minutes: number;
}

journey("T5-25", "IP allowlist self-lockout — the guard refuses the save that locks you out", () => {
  // NOT serial: each row re-reads the policy, so the run reports which of the
  // journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — S8 Security refuses the save inline and keeps the OLD policy in force", async ({
    page,
  }) => {
    await signIn(page);
    const before = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;

    await page.goto(`/${tenant()}/settings/security`);
    const field = page.locator("#ip_allowlist");
    await expect(field, "S8 Security must render the IP allowlist field").toBeVisible();
    await field.fill(EXCLUDES_ME);
    await page.getByRole("button", { name: /^Save/ }).first().click();

    // IS-7 inline validation: the refusal names the saving admin's own IP.
    await expect(
      page.locator("main"),
      "BR-IDN-020: the refusal must tell the admin their current IP is outside the list",
    ).toContainText(/lock|current IP|outside/i);

    // The atomic save aborted: the policy record is unchanged.
    const after = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;
    expect(after.ip_allowlist, "the policy must be byte-identical after a refused save").toEqual(
      before.ip_allowlist,
    );
  });

  test("step 2 — the same save through the API is refused server-side", async ({ page }) => {
    await signIn(page);
    const before = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;

    const response = await page.request.put(api("/settings/security-policy"), {
      data: { ip_allowlist: [EXCLUDES_ME] },
    });
    expect(
      [409, 422],
      `the API save answered ${response.status()}: ${await response.text()}`,
    ).toContain(response.status());
    const refusal = (await response.json()) as { br_ref: string | null; message_key: string };
    expect(refusal.br_ref).toBe("BR-IDN-020");
    expect(refusal.message_key).toBe("errors.identity.allowlist_self_lockout");

    const after = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;
    expect(after.ip_allowlist).toEqual(before.ip_allowlist);
  });

  test("step 3 — malformed CIDRs are refused per entry, and nothing saves", async ({ page }) => {
    await signIn(page);
    const before = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;

    for (const bad of MALFORMED) {
      const response = await page.request.put(api("/settings/security-policy"), {
        data: { ip_allowlist: [INCLUDES_ME, bad] },
      });
      expect(
        response.status(),
        `"${bad}" was accepted (${response.status()}) — BR-IDN-020 takes valid IPv4 CIDRs only`,
      ).toBeGreaterThanOrEqual(400);
    }

    const after = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;
    expect(after.ip_allowlist, "atomic-save semantics: nothing partial is written").toEqual(
      before.ip_allowlist,
    );
  });

  test("step 4 — contrast: a list containing the admin's own IP saves, once, with its audit row", async ({
    page,
  }) => {
    await signIn(page);
    const response = await page.request.put(api("/settings/security-policy"), {
      data: { ip_allowlist: [EXCLUDES_ME, INCLUDES_ME] },
    });
    expect(
      [200, 201],
      `a list containing the admin's own IP answered ${response.status()}: ${await response.text()}`,
    ).toContain(response.status());

    const saved = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;
    expect(saved.ip_allowlist).toContain(INCLUDES_ME);

    // BR-IDN-019: the atomic save writes ONE before/after audit row.
    const audit = await page.request.get(api("/audit-log?per=20"));
    expect(audit.status()).toBe(200);
    const entries = ((await audit.json()) as { results: { action: string }[] }).results;
    expect(
      entries.some((e) => /security|policy/i.test(e.action)),
      `the save wrote no recognisable audit row — actions seen: ` +
        `${entries.map((e) => e.action).join(", ")}`,
    ).toBe(true);
  });

  test("step 5 — per-request enforcement is live once the list is set", async ({ page }) => {
    await signIn(page);
    // The harness is INSIDE the list (step 4 put loopback in it), so its own
    // requests must still proceed — the half of NFR-12 a test can prove without
    // spoofing a source address.
    const inside = await page.request.get(api("/accounts?per=1"));
    expect(
      inside.status(),
      "an in-list caller with a valid session must proceed (BR-IDN-020 per-request)",
    ).toBe(200);

    // And the policy the enforcement reads is the one that was saved.
    const policy = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;
    expect(policy.ip_allowlist.length, "the allowlist must be in force, not empty").toBeGreaterThan(
      0,
    );
  });

  test("step 6 — RECOVERY: both ranges, then drop the old one from inside the new", async ({
    page,
  }) => {
    await signIn(page);
    // The ratified migration: every save passes the self-lockout check because
    // the saving admin is always inside the surviving list.
    const narrow = await page.request.put(api("/settings/security-policy"), {
      data: { ip_allowlist: [INCLUDES_ME] },
    });
    expect(
      [200, 201],
      `narrowing to the surviving range answered ${narrow.status()}: ${await narrow.text()}`,
    ).toContain(narrow.status());

    // And empty remains the ratified "unrestricted" state — restoring the
    // fixture's own starting point.
    const unrestricted = await page.request.put(api("/settings/security-policy"), {
      data: { ip_allowlist: [] },
    });
    expect(
      [200, 201],
      `restoring the unrestricted state answered ${unrestricted.status()}`,
    ).toContain(unrestricted.status());
    const policy = (await (await page.request.get(api("/settings/security-policy"))).json()) as Policy;
    expect(policy.ip_allowlist).toEqual([]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-25 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the journey's 203.0.113.7 is replaced by the harness's OWN
//   address (loopback) as the "inside" range, because the guard is about the
//   SAVING ADMIN'S request IP and a hard-coded address would test nothing on a
//   box that does not have it · (2) step 5 proves the IN-list half of
//   per-request enforcement only: refusing an OUT-of-list caller needs a second
//   source address the harness cannot produce, and spoofing one through a
//   forwarded header would be testing a header, not the rule · (3) step 6
//   deliberately RESTORES the empty allowlist so the shared fixture database is
//   left as this journey found it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
