// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-016 (returned mail: mark returned → bad-address flag →
//           needs-attention → paper suppressed)   Screens: S30 · S35 · S32
// Rules:    BR-PAY-018 (single/bulk; balances unaffected; audited) ·
//           BR-BIL-016 (an email that did not arrive is a provider bounce) ·
//           BR-TEN-043 (the business date is typed, never a clock) ·
//           BR-SHL-025 (a control this deployment cannot honour renders
//           DISABLED WITH its reason)
// ───────────────────────────────────────────────────────
// The Tuesday chore, in a real browser, against a real Django and a real
// Postgres.
//
// WHAT WAS ACTUALLY WRONG, and what this therefore asserts. The engine
// (`apps/payments/returned_mail.py`), the flag, the needs-attention queue, the
// audit row and `POST /deliveries/returned` all existed and a clerk had NOWHERE
// TO TYPE AN ENVELOPE. So "the page rendered" proves nothing here — what has to
// be true is that a control EXISTS, is REACHABLE by clicking, and that the
// server's own answer comes back onto the screen.
//
// Four assertions, in the order a clerk meets them:
//
//   1. the bill's delivery row carries the action, and the "Came back" column;
//   2. clicking it opens a form that ASKS FOR THE DATE (no clock anywhere);
//   3. submitting records it, and the panel repeats the server's own
//      `balances_affected: false` in a clerk's words;
//   4. the same envelope cannot be marked a second time — the control comes
//      back DISABLED with its reason, which is the browser half of CLAUDE.md
//      rule 6.
import { expect, test } from "@playwright/test";

import { bootApp, signIn } from "./support/app";

/** J18's own Tuesday. Typed into the form — never read off a clock. */
const TUESDAY = "2026-09-08";

test("US-PAY-016 · a returned envelope is recorded from the bill's delivery row, and cannot be recorded twice @app-server", async ({
  page,
}) => {
  await signIn(page);
  await bootApp(page);

  // Get to a bill the way a clerk does: the Bills list, then the row.
  await page.goto("/brazosbend/billing/bills");
  await expect(page.locator("[data-not-built-yet]")).toHaveCount(0);
  const firstBill = page.locator("table tbody tr a").first();
  await expect(firstBill).toBeVisible();
  await firstBill.click();

  // 1 · The delivery panel names the queue row AND says whether it came back.
  const cameBack = page.getByRole("columnheader", { name: /came back/i });
  await expect(cameBack).toBeVisible();

  // 2 · The action is on the PAPER rows and it is LIVE on the ones still to
  // mark. This is the control that did not exist this morning. The enabled ones
  // are counted first, because step 5 asserts that this click consumed exactly
  // one of them — a screen that left the button live would invite the same
  // envelope to be marked all afternoon.
  const live = page.locator("button:not([disabled])", { hasText: "Mark returned" });
  const liveBefore = await live.count();
  expect(liveBefore).toBeGreaterThan(0);
  await live.first().click();

  // 3 · The form asks for the DATE (BR-TEN-043) and states the invariance
  // BEFORE the clerk commits — a clerk flagging an address should be able to
  // read that nothing about what the customer owes is changing.
  const date = page.locator("#returned_on");
  await expect(date).toBeVisible();
  await expect(page.getByText(/nothing the customer owes changes/i)).toBeVisible();
  await date.fill(TUESDAY);
  await page.getByRole("button", { name: /^mark returned$/i }).last().click();

  // 4 · The server answered and the screen says what was recorded — including
  // the date the CLERK typed, not today's.
  await expect(page.getByText(/what was recorded/i)).toBeVisible();
  await expect(page.getByText(new RegExp(TUESDAY))).toBeVisible();
  await expect(page.getByText(/nothing the customer owes changes/i)).toBeVisible();

  // 5 · The row now shows the date it came back, and its action is REFUSED with
  // its reason. Marking the same envelope twice is the obvious accident on a
  // stack of fourteen; the database refuses it (UNIQUE on the message id) and
  // so does the screen.
  await expect(page.getByText("09/08/2026").first()).toBeVisible();
  await expect(live).toHaveCount(liveBefore - 1);
  const refused = page.locator("button[disabled]", { hasText: "Mark returned" }).first();
  await expect(refused).toHaveAttribute("title", /already marked returned/i);
});

test("US-PAY-016 · S35 · the chip carries the bulk mark, and the stack lists ONLY the post still to work @app-server", async ({
  page,
}) => {
  await signIn(page);
  await bootApp(page);

  await page.goto("/brazosbend/payments");
  await expect(page.locator("[data-not-built-yet]")).toHaveCount(0);

  // The chip that has counted this queue for days — reading 1 because the case
  // above flagged that account — and beside it the action that clears it. That
  // pairing is the whole story: a count with nothing to click reports a chore
  // nobody can do.
  await expect(page.getByText(/customers whose post came back/i)).toBeVisible();
  const open = page.getByRole("button", { name: /mark returned mail/i });
  await expect(open).toBeVisible();
  await open.click();

  // The modal asks for the date and opens with NOTHING selected — a bulk screen
  // that opened pre-selected would flag the whole queue on one click.
  await expect(page.locator("#returned_on")).toBeVisible();
  await expect(page.getByRole("button", { name: /mark 0 returned/i })).toBeVisible();
  await expect(page.getByText(/nothing the customer owes changes/i)).toBeVisible();

  // ⚠ THE FILTER, PROVED IN THE BROWSER. The fixture holds TWO paper envelopes
  // for this bill and the case above marked the first. The stack a clerk works
  // from is `f.returned=false`, so it must list exactly ONE row now — the one
  // still to mark. A list that showed both would be the whole outbound queue
  // wearing the filter's name, which is what BR-SHL-011's ignore-an-undeclared-
  // filter rule produces when the server does not declare it.
  const rows = page.locator(".pay-returned-stack tbody tr");
  await expect(rows).toHaveCount(1);
  await expect(page.getByText(/1 selected|0 selected/)).toBeVisible();
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-016@EP-PAY-04 · 08-qa/01-e2e/journeys/J18-returned-mail-tuesday.md
// generated: 2026-08-16 by story-coder (returned-mail surface lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: run against the booted stack (08-qa/01-e2e/stack/boot_stack.sh on this lane's OWN database, DEF-054) — transcript in the lane report
// exceptions: (1) DATA PRECONDITION, stated rather than assumed: this spec needs a bill with at least TWO paper queue rows NOT yet marked returned. The boot-stack fixture seeds one issued bill with one paper row, so the second envelope is added before the run (a `copy_no=1` row on the same bill) and the marks are cleared between runs — the spec is not idempotent against its own writes and says so instead of quietly passing on stale state. The FOURTEEN-piece pass is asserted server-side in 06-backend/tests/test_us_pay_016_surface.py, where fourteen accounts can be built. (2) No case asserts a suppressed letter: BR-PAY-018's paper hold is the dispatcher's and is out of this release by PO ruling
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
