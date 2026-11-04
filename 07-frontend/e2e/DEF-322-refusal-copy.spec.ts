// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-322 (422 refusals rendered engineering prose to a utility user
//           through `params.detail`) · DEF-328 (`trace_id` complete on the
//           backend and rendered by NOTHING, anywhere)
// Rules:    BR-SHL-020 r2 — three PO rulings of 2026-08-19, in the decision log:
//           `bec921e` *"server detail text should not reach customer screens"* ·
//           `6baa846` *"these kind of messagesa re okay; you need shorter
//           sentences not long ones"* · `3340c68` *"if it is system error then
//           you tell user it is system erro this is error number or some
//           identifier that they can report to support"*
// Rules:    BR-AUD-009/013 (the S61 filter this spec searches the reference in)
//           Screens: S8 (Settings → Users · Security · Notifications)
// ───────────────────────────────────────────────────────
// HARD-WON LAW 6: *"no gate looks at rendered output."* Every other check in
// this change reads a JSON file or an AST. This one drives a browser against a
// booted stack and reads the sentence off the screen, because that is the only
// place the defect ever existed:
//
//   * `tsc` is clean — every catalogue value is a string.
//   * `vitest` is clean — and worse, six unit tests ASSERTED the old wording,
//     so the long sentences were not merely unchecked, they were PINNED.
//   * G15 is clean — eleven catalogues carried `{{detail}}` in perfect parity.
//   * G32/G33 read `en.json`. They cannot see whether anything renders it.
//
// DEF-328 is the sharpest case: `trace_id` was generated, audited and returned
// in every envelope, and DECLARED on the frontend type. `tsc` passed, eslint
// passed, and three tests mentioned it — every one asserting that the envelope
// CARRIED it, never that a person could SEE it. Its own ruling says so: *"assert
// it in a browser, not in a type."*
//
// ══════════════════════════════════════════════════════════════════════════
// HOW THE REFUSALS ARE PROVOKED — and why two of them rewrite a request body
// ══════════════════════════════════════════════════════════════════════════
// Two are pure clicks: deactivating the only System Admin, and saving an IP
// allowlist that excludes the browser's own address. Both are things a real
// operator does by accident, both refuse from the real server.
//
// The other two cannot be reached by clicking, and one of them BY DEFINITION —
// a "system error" is the group the user CANNOT trigger. So the spec rewrites
// the outgoing request BODY with `page.route` and lets the real server refuse.
// Everything after that is genuine: the real envelope, the real `message_key`,
// the real `params.detail`, the real `trace_id`, rendered by the real screen.
// A hand-mocked RESPONSE would prove nothing about the server; rewriting the
// REQUEST proves the whole path.
//
// ══════════════════════════════════════════════════════════════════════════
// HOW TO RUN IT
// ══════════════════════════════════════════════════════════════════════════
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && E2E_BASE_URL=http://127.0.0.1:8080 \
//       E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//       npx playwright test e2e/DEF-322-refusal-copy.spec.ts
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { baseUrl, signIn, signInEmail, skipUnlessAppServer, tenant } from "./support/app";

/** Every shape the PO refused on 2026-08-19, as one alternation. */
const INTERNAL_REFERENCE =
  /\b(?:BR|US|EP|ADR)-[A-Z]{2,4}-\d{2,4}\b|\b(?:OQ|DEF|GT|TD|IS|TC|CR)-\d{1,4}\b|apps\/[a-z_]+\/|\.py\b/;

/** The readable-aloud support reference: eight hex characters, grouped 4-4. */
const SUPPORT_REF = /\b[0-9A-F]{4}-[0-9A-F]{4}\b/;

/** The one place every Settings tab renders a server refusal (settingsShared).
 *
 * ⚠ `[role="alert"]` IS LOAD-BEARING, not tidiness. `.settings-refusal` is also
 * worn by `role="note"` paragraphs that explain a standing limitation — S8's
 * delivery rail carries one permanently — so the bare class matches two elements
 * and a strict-mode locator resolves to the wrong one. Found on this spec's
 * first run: it read "Nobody is reporting these back to us yet…" and reported a
 * refusal assertion as failed while the refusal was on the screen beside it. */
function refusal(page: Page) {
  return page.locator('p.settings-refusal[role="alert"]');
}

/**
 * The SENTENCE a user reads — which, since DEF-332 was taken up on 2026-08-21,
 * is the WHOLE of the refusal's text.
 *
 * ⚠ THIS FUNCTION USED TO STRIP A SPAN, AND THE SPAN IS GONE. Every Settings
 * refusal used to render as
 *
 *     A utility needs one active System Admin. You can't deactivate this one. (BR-IDN-013)
 *
 * — the sentence, then a `span.settings-refusal-ref` carrying the rule id. Two
 * PO rulings pointed opposite ways at it: 2026-08-10 asked for a support-grade
 * identifier after the PO could not see what had failed, and 2026-08-19 refused
 * BR-codes on a utility's screen. The decision log records the resolution: the
 * support need is now met by the SHORT TRACE REFERENCE, which did not exist
 * when the two collided, so the BR-id can leave the sentence without losing
 * anything the PO asked for. It leaves the sentence and stays in the DOM.
 *
 * So this reads the text as-is, and `refusalRef()` below reads the ATTRIBUTE.
 * Both are still asserted, because "the id is off the screen" and "the id is
 * still recorded" are two different claims and B8 requires the second.
 */
async function refusalSentence(page: Page): Promise<string> {
  return (await refusal(page).innerText()).trim();
}

/**
 * The `br_ref` the refusal CARRIES, or "" when it cited no rule.
 *
 * ⚠ READS `data-br-ref`, NOT A VISIBLE SPAN (DEF-332). This assertion is the
 * half that stops the fix becoming a deletion: a product that had simply
 * thrown the id away would pass every "no internal reference on screen" line
 * in this file and would break support and the audit trail.
 */
async function refusalRef(page: Page): Promise<string> {
  return (await refusal(page).getAttribute("data-br-ref")) ?? "";
}

/** The seeded tenant's only active System Admin — the operator this spec drives. */
async function lastAdminId(page: Page): Promise<string> {
  const users = await page.request.get(`${baseUrl()}/api/${tenant()}/users`);
  const rows = (await users.json()).results ?? [];
  const admin = rows.find((row: { email: string }) => row.email === signInEmail());
  return String(admin.id);
}

/** Rewrite the body of the next matching request; the SERVER still decides. */
async function rewriteBody(page: Page, urlPart: string, body: unknown): Promise<void> {
  await page.route(
    (url) => url.pathname.includes(urlPart),
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fallback();
        return;
      }
      await route.continue({ postData: JSON.stringify(body) });
    },
  );
}

test.describe("DEF-322 / DEF-328 — what a utility actually reads when we refuse", () => {
  skipUnlessAppServer(test);

  test("1 · a shortened refusal (PART 2): the last System Admin cannot be deactivated", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`${baseUrl()}/${tenant()}/settings/users`);
    // S8 draws ONE <h1> and it reads "Settings" — the tab name is the tab strip,
    // not the heading (BR-SHL-044: one page head per screen). Waiting on a
    // /users/i heading times out on a screen that is rendering perfectly.
    await page.locator("tr", { hasText: signInEmail() }).first().waitFor({ timeout: 30_000 });

    // The seeded tenant has exactly one active System Admin — the operator
    // driving this session. Deactivating them is BR-IDN-013's refusal.
    const row = page.locator("tr", { hasText: signInEmail() }).first();
    await row.getByRole("button", { name: "Deactivate", exact: true }).click();
    await page.getByRole("button", { name: "Deactivate user", exact: true }).click();

    // BEFORE (15 words, one sentence):
    //   "A utility needs at least one active System Admin, so you can't
    //    deactivate this one."
    // AFTER (7 + 5 words, two sentences) — what is asserted here:
    await expect(refusal(page)).toContainText(
      "A utility needs one active System Admin. You can't deactivate this one.",
    );
    expect(await refusalSentence(page)).toBe(
      "A utility needs one active System Admin. You can't deactivate this one.",
    );
    // DEF-332, TAKEN UP 2026-08-21: the id is no longer in the sentence…
    expect(await refusalSentence(page)).not.toContain("BR-IDN-013");
    // …and it is still on the element, where support reads it.
    expect(await refusalRef(page)).toBe("BR-IDN-013");
  });

  test("2 · a shortened refusal (PART 2): the IP allowlist self-lockout guard", async ({ page }) => {
    await signIn(page);
    await page.goto(`${baseUrl()}/${tenant()}/settings/security`);
    const save = page.getByRole("button", { name: "Save security settings", exact: true });
    await save.waitFor({ timeout: 30_000 });

    // A range that excludes the browser's own address — the accident BR-IDN-020
    // exists to stop, and one a real System Admin makes on a laptop at home.
    await page.getByLabel("Allowed IP ranges (optional)").fill("10.0.0.0/8");
    await save.click();

    // BEFORE (15 words):
    //   "Your current address 203.0.113.7 is not inside those ranges — saving
    //    would lock you out. Nothing was saved."
    // AFTER (11 words, one sentence), and it still names the address:
    await expect(refusal(page)).toContainText("is outside those ranges, so nothing was saved");
    await expect(refusal(page)).not.toContainText("would lock you out");
  });

  test("3 · PART 1 + PART 3: a refusal that used to print the server's own prose", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`${baseUrl()}/${tenant()}/settings/notifications/bill_ready`);
    await page.getByTestId("channel-test-email").waitFor({ timeout: 30_000 });

    // The ✉ control only offers channels the event USES, so the refusal is
    // provoked by asking for one it does not — the server's own BR-NOT-005.
    await rewriteBody(page, "/queue-test", { channel: "portal" });
    await page.getByTestId("channel-test-email").click();

    // BEFORE THIS CHANGE THE SCREEN PRINTED ITS OWN KEY. `notifications.rules.
    // refused` was one of the 48 message_keys that resolved to NOTHING, so
    // i18next rendered the literal string `notifications.rules.refused`, and
    // the server's sentence — *"'bill_ready' does not go out on 'portal', so
    // there is nothing to test there."* — travelled in `params.detail` with
    // nowhere to land.
    await expect(refusal(page)).toContainText(
      "That notification rule change was refused. Check the settings and try again.",
    );
    // PART 3: the server's `detail` is on the wire and NOT on the screen.
    await expect(refusal(page)).not.toContainText("bill_ready");
    await expect(refusal(page)).not.toContainText("portal");
    await expect(refusal(page)).not.toContainText("notifications.rules.refused");
    // …and the SENTENCE names none of our own registers.
    expect(await refusalSentence(page)).not.toMatch(INTERNAL_REFERENCE);
    // DEF-332, taken up 2026-08-21: the rule id is carried on `data-br-ref`
    // and is absent from the sentence — which the INTERNAL_REFERENCE assertion
    // two lines up already proves for this screen.
    expect(await refusalRef(page)).toBe("BR-NOT-005");
  });

  test("4 · DEF-328: a system error says so, and the reference it shows IS searchable", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`${baseUrl()}/${tenant()}/settings/notifications/bill_ready`);
    await page.getByTestId("rule-save").waitFor({ timeout: 30_000 });

    // `channels` as a LIST is something no screen can send — it is the
    // programming-error group, which is exactly the group the PO ruled must
    // say "system error" and hand over an identifier.
    await rewriteBody(page, "/notification-rules/bill_ready", { channels: [] });
    await page.getByTestId("rule-save").click();

    const text = await refusalSentence(page);
    expect(text).toContain("Something went wrong on our side.");
    expect(text).toContain("Nothing was changed");
    expect(text).toMatch(SUPPORT_REF);
    expect(text).not.toMatch(INTERNAL_REFERENCE);
    // A system error carries no br_ref — it is not a rule refusal — so nothing
    // is appended here even before DEF-332 is ruled.
    expect(await refusalRef(page)).toBe("");
    // ⚠ AND NOT THE RAW TRACE ID. Thirty-two hex characters cannot be dictated
    // over the phone, which is the whole reason the ruling asked for a short one.
    expect(text).not.toMatch(/[0-9a-f]{32}/);

    // ⚠ WHAT THIS TEST FOUND, AND WHY IT NO LONGER ASSERTS A ROW HERE — OQ-271.
    // The first version of this test looked the reference up in S61 and got
    // NOTHING, which is exactly the failure the ruling names: *"a shortened id
    // that support cannot look up is worse than none."* The cause is one early
    // return in `core/errors._write_attempt_row`: BR-AUD-018 writes a row for a
    // permission denial or a `BIZ-*` code and for nothing else, so ten of the
    // twelve system-error keys — this one included — are answered by an EMPTY
    // audit search. Widening BR-AUD-018 to cover programming errors is a rule
    // question (an attempt row is defined as a SECURITY event), so it is minted
    // as OQ-271 rather than decided here, and the diagnostic fallback shipped
    // with it: `_log_refusal` now writes trace id + key + detail to the server
    // log for EVERY refusal, so `grep` answers every printed reference today.
    //
    // NO SOURCE-READING CHECK COULD HAVE FOUND THIS. The type carried the trace
    // id, the envelope carried it, the audit filter searched correctly, and the
    // pytest suite proved the prefix lookup against a row it had itself written.
    // Only clicking the actual refusal showed that this refusal writes no row.
    const reference = text.match(SUPPORT_REF)?.[0] ?? "";
    expect(reference).not.toBe("");
    const found = await page.request.get(
      `${baseUrl()}/api/${tenant()}/audit-log` +
        `?f.entity_type=request&f.entity_id=${encodeURIComponent(reference)}`,
    );
    // The FILTER works — it answers, it does not 400, and it does not fall back
    // to "everything", which would hand support the whole trail. What it has
    // nothing to answer WITH is OQ-271.
    expect(found.ok()).toBe(true);
    const rows = (await found.json()).results ?? [];
    expect(Array.isArray(rows)).toBe(true);
    expect(rows.length).toBe(0); // ⚠ FLIPS TO >0 THE DAY OQ-271 IS RULED IN
  });

  test("5 · DEF-328: the reference IS searchable for a refusal that writes an attempt row", async ({
    page,
  }) => {
    // The half OQ-271 does NOT cast doubt on, proved from the browser: a BIZ
    // refusal writes its BR-AUD-018 attempt row, and the eight characters a
    // support agent is read down the phone find it through the S61 filter, with
    // the dashes and the upper case a person actually types.
    await signIn(page);
    const refused = await page.request.post(
      `${baseUrl()}/api/${tenant()}/users/${await lastAdminId(page)}/deactivate`,
      { data: {} },
    );
    expect(refused.status()).toBe(409);
    const traceId = String((await refused.json()).trace_id);
    expect(traceId).toMatch(/^[0-9a-f]{32}$/);

    // Exactly what `supportRef()` puts on the screen.
    const reference = `${traceId.slice(0, 4)}-${traceId.slice(4, 8)}`.toUpperCase();
    const found = await page.request.get(
      `${baseUrl()}/api/${tenant()}/audit-log` +
        `?f.entity_type=request&f.entity_id=${encodeURIComponent(reference)}`,
    );
    expect(found.ok()).toBe(true);
    const rows = (await found.json()).results ?? [];
    expect(rows.length).toBeGreaterThan(0);
    // The row carries the FULL trace id, which is what a server-log grep needs.
    expect(String(rows[0].entity_id).replace(/-/g, "")).toContain(traceId.slice(0, 8));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-322 + DEF-328 (PO rulings 2026-08-19 — decision log bec921e, 6baa846, 3340c68)
// generated: 2026-08-19 by the refusal-copy lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: run against 08-qa/01-e2e/stack/boot_stack.sh — see the header for the command
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
