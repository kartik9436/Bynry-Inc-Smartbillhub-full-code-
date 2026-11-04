// FI-06 support — app boot for UI journeys (B13 §2; B12 r3 §5).
// The harness NEVER starts the app: point E2E_BASE_URL at a running frontend
// (default: the local Vite dev server). Specs that need the app call
// skipUnlessAppServer(test) first, so a missing server means SKIP, not red —
// CI stays green before the compose stack exists (the same posture as the
// vitest it.todo convention: honest about what could not run).
import type { Page, test as playwrightTest } from "@playwright/test";

export const DEFAULT_BASE_URL = "http://localhost:5173";

export function baseUrl(): string {
  return process.env.E2E_BASE_URL ?? DEFAULT_BASE_URL;
}

// Probed once per worker process — a dead server stays dead for the run.
let serverUp: boolean | null = null;

// The probe's budget. 2_000 was measured to be too short on 2026-08-15: with
// several lanes' Playwright runs sharing four CPUs, the BUILT SPA's index took
// longer than two seconds to answer, the probe threw, `serverUp` cached FALSE
// for the whole worker process — and 73 of 76 tests in a batch-A run SKIPPED
// against a stack that was up and answering 200 the whole time. The run
// reported "3 failed" and exited, and the census did NOT catch it, because
// SOME browser assertions had executed. That is DEF-057's shape one turn
// further on: not a suite that proves nothing, but a suite that silently proves
// 4 % of what it was asked to and reports the 4 % as the whole answer.
//
// A slow answer is not a missing server, so the budget is the one a human would
// wait, and a single failure is retried once before a worker writes the whole
// run off.
const PROBE_TIMEOUT_MS = 30_000;

export async function appServerAvailable(): Promise<boolean> {
  if (serverUp === null) {
    for (let attempt = 0; attempt < 2 && serverUp !== true; attempt++) {
      try {
        const response = await fetch(baseUrl(), {
          signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
        });
        serverUp = response.ok;
      } catch {
        serverUp = false;
      }
    }
  }
  return serverUp === true;
}

// Call once at the top of a describe block (or spec file): every test in it
// skips with an honest reason when no app server answers at the base URL.
export function skipUnlessAppServer(test: typeof playwrightTest): void {
  test.beforeEach(async () => {
    const up = await appServerAvailable();
    test.skip(
      !up,
      `no app server at ${baseUrl()} — run \`npm run dev\` in 07-frontend or set E2E_BASE_URL`,
    );
  });
}

// The tenant the harness drives. Tenancy is PATH-based (PO 2026-08-10), so a
// journey's URLs are `/{tenant}/…`; point E2E_TENANT at whatever slug the
// target environment was seeded with.
export const DEFAULT_TENANT = "brazosbend";

export function tenant(): string {
  return process.env.E2E_TENANT ?? DEFAULT_TENANT;
}

// The first path inside the authenticated shell. "/" is the PUBLIC Pricing
// screen (S1) since the public route group landed with the S1/S3/S110–S114
// packet, so the shell must be entered by an authenticated path — and every
// authenticated path now carries the tenant.
export function shellEntryPath(): string {
  return `/${tenant()}/dashboard`;
}

// ── THE CONTENT PANE, AND WHY THIS HELPER NOW LOOKS AT IT ──────────────────
//
// DEF-129, and it is the sharpest escape route in the register. The tenant
// dashboard — **the first screen after every single sign-in** — did not exist:
// `App.tsx` redirected `/{tenant}` to `dashboard`, no route with that path was
// declared, the request fell through the router's catch-all, and the content
// pane rendered the literal developer string `SMARTBillHub — W0 scaffold`.
//
// **Every journey in this suite walked straight past it**, because `bootApp`
// waited for the SIDEBAR and then returned. The sidebar renders perfectly. So
// the harness proved the FRAME and never once looked at what was inside it —
// the same shape as DEF-057 (a suite that proved 4 % of what it was asked to
// and reported the 4 % as the whole answer), one layer further in.
//
// The fix is one assertion and it is deliberately narrow. It does NOT try to
// know what each screen renders; it asserts the two things that are true of
// EVERY built screen and false of the placeholder:
//
//   1. the content pane holds a heading — a screen has a name (BR-SHL-044 puts
//      an `<h1>` on every one through PageHeader);
//   2. the content pane is not the catch-all.
//
// ⚠ HOW (2) IS DETECTED CHANGED ON 2026-08-16 (DEF-152) AND HAD TO. It used to
// match the TEXT `/W0 scaffold/` — the developer string the catch-all printed.
// That string is gone: the catch-all now renders an honest not-built-yet state
// in the user's own language, through the catalogues, with a `<h1>` of its own.
// A text match would therefore now PASS on every unrouted path in the product,
// which is the guard silently retiring itself the day the thing it guards moves.
//
// So it matches the catch-all's own STRUCTURAL marker, `[data-not-built-yet]`,
// which `components/NotBuiltYet.tsx` puts on its root and nothing else in the
// product carries. It is language-independent by construction — the old text
// match would have sailed past the same defect in German — and it cannot be
// defeated by rewriting the copy.
//
// A REGISTERED not-built destination (e.g. `/reports`, whose library is
// US-REP-001) is a legitimate STATE and is still not a SCREEN, so this helper
// fails on it deliberately. A journey that must pass through one asserts the
// state, not the screen.
//
// Proved RED before trusted green (hard-won law 7), twice: against the pre-fix
// build the old helper passed and its first version failed on the text marker
// (DEF-129); against the post-fix build the TEXT version passes on `/reports`
// and this attribute version fails on it (DEF-152). Both quoted in the lane
// reports.
const CONTENT_PANE = "main.view";
const CATCH_ALL_MARKER = "[data-not-built-yet]";

/**
 * The assertion the sidebar check was standing in for: this route rendered a
 * SCREEN. Exported so a journey can re-assert it after navigating, and so its
 * own guard test can drive it against a pane it knows is blank.
 */
export async function expectScreenInContentPane(page: Page, path: string): Promise<void> {
  const pane = page.locator(CONTENT_PANE);
  // ATTACHED, not visible: an empty `<main>` collapses to zero height and would
  // never become "visible", so a visibility wait here would hang for the whole
  // test budget on precisely the case this guard exists to name.
  await pane.waitFor({ state: "attached" });
  // First wait for the pane to have painted ANYTHING — a heading, a paragraph,
  // a table, an A18 state. Waiting for the heading first would report every
  // fall-through as a bare 15-second timeout, and a timeout is the least
  // informative failure a suite can produce: DEF-129 would have read
  // "locator.waitFor: Timeout" instead of naming the placeholder.
  await pane.locator("h1, h2, p, table, [role=alert], [role=note]").first().waitFor({
    timeout: 15_000,
  });
  const text = (await pane.innerText()).trim();
  if ((await pane.locator(CATCH_ALL_MARKER).count()) > 0) {
    throw new Error(
      `${path} rendered the not-built-yet state, not a screen — the router has no route for ` +
        `this path and it fell through to the catch-all (DEF-129, DEF-152). If the destination ` +
        `is knowingly unbuilt it belongs in UNBUILT_SIDEBAR_DESTINATIONS, and this journey must ` +
        `assert that STATE rather than a screen. Content pane read: ` +
        `${JSON.stringify(text.slice(0, 200))}`,
    );
  }
  if (text === "") {
    throw new Error(`${path} rendered an EMPTY content pane — the shell framed nothing`);
  }
  // THEN the heading. A screen has a name (BR-SHL-044 puts an <h1> on every one
  // through PageHeader), and this also waits out the A18 loading skeleton, so
  // the check is not a race against the first paint.
  await pane.locator("h1, h2").first().waitFor({ timeout: 15_000 });
}

// Boots the shell and waits for the sidebar nav (BR-SHL-001) — the marker
// every UI journey starts from. The label is the en catalog's
// "shell.nav.label"; journeys switching language re-query afterwards.
//
// AND THEN LOOKS INSIDE THE FRAME (DEF-129) — see the block above.
export async function bootApp(page: Page): Promise<void> {
  await page.goto(shellEntryPath());
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor();
  await expectScreenInContentPane(page, shellEntryPath());
}

// ── The real sign-in (S3), for journeys that need a session ────────────────
//
// `bootApp` walks straight into the shell, which is enough for the W0 harness
// proof. A journey that reads a tenant's DATA needs a session cookie, and the
// PO's 2026-08-11 ruling is explicit that it must be earned the way a human
// earns it: *"we ahve to prove against human clicking"*. So this types into the
// S3 form and clicks its button — it never POSTs to `/auth/session` itself,
// because a journey that forged its own cookie would prove the API and skip the
// screen that DEF-041's family of defects live on.
//
// The credentials are the seeded demo fixture's, printed by `manage.py
// seed_demo` under "walkthrough credentials" and published in that file. They
// are overridable so the harness can drive a differently-seeded environment.
export const DEFAULT_E2E_EMAIL = "dana@brazosbendutilities.com";
export const DEFAULT_E2E_PASSWORD = "S3cure!passw0rd";

export function signInEmail(): string {
  return process.env.E2E_EMAIL ?? DEFAULT_E2E_EMAIL;
}

export function signInPassword(): string {
  return process.env.E2E_PASSWORD ?? DEFAULT_E2E_PASSWORD;
}

export function signInPath(): string {
  return `/${tenant()}/signin`;
}

// Signs in and returns once the shell has framed a screen. The field ids are
// S3's own (`SignInPage.tsx`), which is the contract this helper depends on;
// if they move, this fails loudly at the fill rather than timing out later.
export async function signIn(page: Page): Promise<void> {
  await page.goto(signInPath());
  await page.locator("#signin-email").fill(signInEmail());
  await page.locator("#signin-password").fill(signInPassword());
  await page.locator("form button[type=submit]").first().click();
  // BR-IDN-022 can route a first sign-in to a forced password change instead of
  // the dashboard; the seeded owner has `must_change_password: false`, so the
  // shell is the expected landing and anything else is a real failure.
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor();
  // DEF-129 again, and this is the call that actually reproduces what a human
  // does: `signIn` lands on the SAME dashboard `bootApp` opens, so waiting only
  // for the chrome here would leave the identical hole in every journey that
  // earns a session rather than walking in.
  await expectScreenInContentPane(page, shellEntryPath());
}

/** ⚠ **`fullPage: true` IS SILENTLY A VIEWPORT SHOT IN THIS APP** — DEF-316,
 *  recorded here because that defect's own prevention says it must be: *"Any
 *  screenshot-based check of this app must scroll the inner `main.view`
 *  container, not the document — record that in the e2e harness."*
 *
 *  The shell pins every ancestor of the content pane to the viewport and puts
 *  `overflow: auto` on `main.view`, so the DOCUMENT never scrolls. Measured on
 *  Settings → Notifications, 1440×900:
 *
 *      document.documentElement.scrollHeight   900
 *      main.view.clientHeight                  844
 *      main.view.scrollHeight                 8624
 *
 *  Playwright expands the document for `fullPage`, and the document is already
 *  its full 900px — so it captures the top screenful, reports success, and
 *  **9 of every 10 screenfuls of the page are absent from an image that looks
 *  complete.** Every existing screenshot of that screen shows only the top and
 *  looks fine; DEF-314, DEF-315 and DEF-317 all lived below the fold of one.
 *
 *  ⚠ RELEASING `main.view` ALONE DOES NOT WORK, and that is the part worth
 *  knowing: its ancestors are what hold the document at 900px, so the height
 *  has to be released all the way up. Verified both ways — `main.view` only
 *  left the document at 900; the walk below took it to 8680.
 *
 *  This MUTATES the page, so call it immediately before a screenshot and never
 *  before a measurement: `CR-016-ui-conformance.spec.ts` reads computed style
 *  and must see the real layout.
 */
export async function expandInnerScroller(page: Page): Promise<void> {
  await page.evaluate(() => {
    const main = document.querySelector<HTMLElement>("main.view");
    if (main === null) {
      return;
    }
    for (let el: HTMLElement | null = main; el !== null; el = el.parentElement) {
      el.style.setProperty("height", "auto", "important");
      el.style.setProperty("max-height", "none", "important");
      el.style.setProperty("overflow", "visible", "important");
    }
  });
  // The reflow the released heights cause has to settle before the capture.
  await page.waitForTimeout(600);
}
