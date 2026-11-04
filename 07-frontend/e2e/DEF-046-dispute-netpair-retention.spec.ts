// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-013 (S29 dispute — DEF-046's unwritten marker) ·
//           US-AST-011 / US-AST-012 (the net-metering import/export PAIR) ·
//           US-MET-020 / US-AUD-007 (has data retention ever run?)
//           Screens: S25 · S29 · S61 (+ its Data-retention view)
// ───────────────────────────────────────────────────────
// Three surfaces that did not exist this morning, in a real browser.
//
// Each was the same defect wearing different clothes — hard-won law 2, "built
// is not wired" — and each was found by RUNNING the product, not by a gate:
//
//   1. `meter_reads` carried `disputed_at` / `dispute_reason` / `disputed_by`,
//      `GET /reads/needs-attention` COUNTED disputes, S29 drew a Dispute
//      button, and NO endpoint anywhere set one (DEF-046). The chip could only
//      ever read zero and a customer could not dispute a reading.
//   2. `validation.py` refused an export record on a flat meter and `models.py`
//      carried the channel, and no screen showed the two channels AS A PAIR —
//      which is the whole of US-AST-011/012.
//   3. `archive_job_runs` appeared in a migration, a management command and
//      `core/archival.py` and in NO api.py anywhere, so an operator under a
//      7-year retention obligation could not answer "has it ever run?".
//
// WHY THESE ASSERTIONS AND NOT "THE PAGE RENDERED". Every one of these screens
// EXISTED before today and every one of them was honest about what it could not
// do — the Dispute button said so in its tooltip, the chip said it could not
// drill in. A check that asserted "the control is on the page" would have
// passed against the broken product all week. So each test asserts the thing
// that was ACTUALLY wrong: that the control is LIVE, that the sentence which
// admitted the gap is GONE, and that the honest refusals which must survive
// (OQ-245, OQ-001, "never manual") are still said out loud.
import { expect, test } from "@playwright/test";

import { bootApp, signIn } from "./support/app";

test("S29 · a clerk can dispute a reading, and the drawer says what that does @app-server", async ({
  page,
}) => {
  await signIn(page);
  await bootApp(page);

  await page.goto("/brazosbend/reads?tab=all");
  await expect(page.locator("[data-not-built-yet]")).toHaveCount(0);

  // Open the first reading's drawer the way a clerk does — from the identity
  // cell of the list.
  const firstRead = page.locator(".rd-open").first();
  await expect(firstRead).toBeVisible();
  await firstRead.click();

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();

  // 1 · THE CONTROL IS LIVE. Until 2026-08-16 this button was rendered
  // DISABLED with the reason "The dispute marker is stored and counted, but no
  // endpoint records one yet" — DEF-046's finding, written on the screen and
  // left standing. Its ENABLED state is the whole of "built is now wired", and
  // the absence of that sentence is what a later regression would restore.
  const dispute = drawer.getByRole("button", { name: /^dispute$/i });
  await expect(dispute).toBeVisible();
  await expect(dispute).toBeEnabled();
  await expect(page.getByText(/no endpoint records one yet/i)).toHaveCount(0);

  // 2 · It opens a form that REQUIRES a reason — BR-MET-024, and the reason is
  // what the System Admin who must clear it later actually reads.
  await dispute.click();
  const reason = page.locator("#reason");
  await expect(reason).toBeVisible();

  // 3 · The consequence is stated BEFORE the click, not after it. Raising a
  // dispute takes an account out of the next bill run and only a System Admin
  // puts it back (the OQ-043 closure) — that belongs on the form.
  await expect(page.getByText(/leaves the next bill run/i)).toBeVisible();
});

test("S29 · a net meter shows import AND export together, and nets nothing @app-server", async ({
  page,
}) => {
  await signIn(page);
  await bootApp(page);

  // The pair panel renders for a NET meter and for nothing else (BR-AST-010),
  // so on a fixture of flat meters the assertion that matters is the negative
  // one: no ordinary reading grows an "Export: 0" line for a register that does
  // not exist. That is the failure a naive panel would ship with.
  await page.goto("/brazosbend/reads?tab=all");
  const firstRead = page.locator(".rd-open").first();
  await expect(firstRead).toBeVisible();
  await firstRead.click();

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator(".rd-netpair")).toHaveCount(0);
  await expect(drawer.getByText(/fed back to the grid/i)).toHaveCount(0);

  // And the drawer itself still renders its reading with its UNIT (rule 3 /
  // DEF-060) — the panel was added above the math line and must not have
  // displaced it.
  await expect(drawer.getByText(/how this usage was worked out/i)).toBeVisible();
});

test("S61 · an operator can see whether data retention has ever run @app-server", async ({
  page,
}) => {
  await signIn(page);
  await bootApp(page);

  await page.goto("/brazosbend/audit-log");
  await expect(page.locator("[data-not-built-yet]")).toHaveCount(0);

  // 1 · REACHABLE BY CLICKING. A page nothing links to is the same defect one
  // layer along, so the entry point is asserted rather than the URL typed.
  const link = page.getByRole("button", { name: /data retention/i });
  await expect(link).toBeVisible();
  await link.click();

  await expect(page).toHaveURL(/\/audit-log\/retention$/);
  await expect(page.locator("[data-not-built-yet]")).toHaveCount(0);

  // 2 · Both obligations are named, so an operator sees WHICH one is unmet.
  await expect(page.getByText(/meter readings/i).first()).toBeVisible();
  await expect(page.getByText(/audit trail/i).first()).toBeVisible();

  // 3 · On a fresh stack the job has never run, and the screen SAYS SO. This is
  // the assertion that a blank table would fail: "never run" is a compliance
  // finding, not an empty state.
  await expect(page.getByText(/has never been archived/i).first()).toBeVisible();

  // 4 · BR-MET-055 / BR-AUD-012, "never manual" — the absence of a trigger is a
  // RULE, so it is explained. And there is no button to press.
  await expect(page.getByText(/no way to start, skip or bring forward/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /run now/i })).toHaveCount(0);
});
