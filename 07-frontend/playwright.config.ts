import { defineConfig } from "@playwright/test";

// FI-06 (B13 §2): the Playwright harness for the UI half of the 300-journey
// suite. Journeys automate INCREMENTALLY (B12 r3 §5): the generated wiring
// index knows which stories each journey needs, and a journey activates only
// when its last story is built. See e2e/README.md.
export default defineConfig({
  testDir: "./e2e",
  // DEF-057 / PO ruling 2026-08-11 ("we ahve to prove against human clicking").
  // The list reporter is Playwright's normal output; `support/census.ts` adds
  // the line nobody was printing — how many assertions ACTUALLY executed, split
  // into browser and server-free — and FAILS a run that executed no browser
  // assertion at all. A job whose only outcomes are "passed" and "passed" is
  // not a check; that job was `.github/workflows/qa.yml` until this landed.
  reporter: [["list"], ["./e2e/support/census.ts"]],
  // MEASURED, not guessed. `vite build` emits ONE 3.5 MB JS chunk (it says so on
  // every build: *"chunks are larger than 500 kB"*), and a full page load of the
  // built SPA takes ~13 s in the E2E sandbox — so a journey that navigates three
  // times blows Playwright's 30 s default while everything is working correctly.
  // The default is raised rather than the journeys written to navigate less: a
  // journey should click the way a human clicks. The 3.5 MB chunk is a REAL
  // finding and is reported rather than absorbed here (lane report, 2026-08-11).
  timeout: 90_000,
  expect: { timeout: 10_000 },
  use: {
    // The harness never starts the app — point E2E_BASE_URL at a running
    // frontend (e2e/support/app.ts documents the contract). Default: the
    // local Vite dev server. `08-qa/01-e2e/stack/boot_stack.sh` brings up the
    // whole stack (Postgres + Django + the BUILT frontend on one origin) and
    // prints the URL to use.
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    launchOptions: {
      // An ESCAPE HATCH, not the normal path: `npx playwright install chromium`
      // is how a browser normally arrives, and it is what CI does. Some
      // sandboxes cannot reach cdn.playwright.dev (403 "host not permitted"),
      // and there a pre-provisioned Chromium is the difference between a
      // journey that runs and one that reports itself unrunnable. Set it to an
      // absolute path to a Chromium binary; leave it unset everywhere else.
      //   E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
      executablePath: process.env.E2E_CHROMIUM_EXECUTABLE || undefined,
    },
  },
});
