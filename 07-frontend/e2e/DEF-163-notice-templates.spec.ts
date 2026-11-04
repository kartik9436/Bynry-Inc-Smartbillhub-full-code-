// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-163 (no tenant has ever had a notice template, so every
//          disconnect notice and every dunning letter is REFUSED at render)
// Story:   US-NOT-005 / US-NOT-006 / US-NOT-016 (the S8 template read) ·
//          US-TEN-001 (provisioning, which is where the rows come from)
//          Screens: S8 → Notifications
// Rules:   BR-NOT-001 (a `default` fallback variant is MANDATORY) ·
//          BR-NOT-006 (type × category × language) · BR-BIL-026 (only a
//          PUBLISHED version resolves) · CLAUDE.md hard-won law 6 (diff the
//          running app; no gate looks at rendered output)
// ───────────────────────────────────────────────────────
//
// **THE ONE THING THIS FILE PROVES: A PERSON CAN SEE, IN A BROWSER, WHICH
// LETTERS THEIR UTILITY CAN SEND AND WHY THE REST ARE MISSING.**
//
// The unit tests prove the seeder writes rows and the component test proves the
// panel renders a reason from a fixture. Neither can prove the thing DEF-163
// was actually about: that a tenant provisioned by the real signup path, read
// through the real endpoint, drawn by the real screen, shows a published body
// where one exists and an ANSWERABLE sentence where one does not.
//
// **WHY THE ASSERTIONS ARE ON THE TEXT AND NOT ON A COUNT.** DEF-163's cost was
// not that a number was wrong — it was that a blank cell meant two different
// things and a person could not tell which. So this spec reads what a human
// reads: the word "Version" beside the reminder, and the string "OQ-243" beside
// the disconnect notice. A screen that renders a count and no sentence passes
// every other check in this repository and fails this one.
//
// **WHAT IT DOES NOT CLAIM.** Nothing is sent. Generating a notice writes queue
// rows and there is no dispatcher in this release (BR-NOT-013, PO 2026-08-16),
// so a green run here never means a customer received anything.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

test("DEF-163 · S8 Notifications names the letters this utility has, and the question behind each one it does not @app-server", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/${tenant()}/settings/notifications`);

  const templates = page.getByTestId("template-seed-summary");
  await expect(templates).toBeVisible();

  // ── The half that is FIXED ────────────────────────────────────────────────
  // `dunning` is A13's friendly past-due reminder, planted at provisioning.
  // Before this lane every row on this card answered "no published body", on
  // every tenant on every deployment.
  const dunningRow = page.locator("tr", { hasText: /^dunning/ });
  await expect(dunningRow).toContainText(/Version 1/);
  // …and the same row must NOT be drawn as an absence.
  await expect(page.getByTestId("unpublished-dunning")).toHaveCount(0);
  await expect(page.locator("tr", { hasText: /^receipt/ })).toContainText(/Version 1/);

  // ── The half that is REFUSED, and says so in words a person can act on ────
  // A19 §2 writes three tier bodies and a template variant holds one; the
  // regulatory rights footer is written in no signed document. Both halves are
  // OQ-243, and the card carries the SERVER's sentence rather than a label.
  const disconnect = page.getByTestId("unpublished-disconnect_notice");
  await expect(disconnect).toBeVisible();
  await expect(disconnect).toContainText("OQ-243");
  await expect(disconnect).toContainText(/three tier bodies/i);

  // The payment-plan agreement, and the ten classes with no token catalogue,
  // each name their own question too — so no row on this card is a shrug.
  await expect(page.getByTestId("unpublished-contract_payment_plan")).toContainText("OQ-244");
  await expect(page.getByTestId("unpublished-email_past_due")).toContainText("OQ-206");

  // ── The claim this screen must never make ─────────────────────────────────
  // Having a body is not having a dispatcher. The tab states that on its face
  // and a person reading "Version 1" beside a reminder must not conclude the
  // reminder went anywhere.
  await expect(page.getByText(/Nothing is sent in this release/i).first()).toBeVisible();
});
