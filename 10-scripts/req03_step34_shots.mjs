#!/usr/bin/env node
/**
 * REQ-03 tasks 8–10 — SHOOT THE BUILT COMPONENTS IN A REAL BROWSER.
 *
 * ⚠ **WHAT THIS PROVES AND WHAT IT DOES NOT — READ THIS BEFORE QUOTING A
 * SHOT.** Hard-won law 6 asks for the running app beside the drawing, and the
 * full stack cannot be booted in this container: `/var/run/docker.sock` does
 * not exist, so there is no API, no tenant and no sign-in, and a shot of
 * `/requests/new` would be a spinner.
 *
 * **So this mounts the REAL components through the REAL Vite + Tailwind
 * pipeline, on fixture rows, and photographs them in the repo's own Chromium
 * at 1440, 1280 and 420.** It proves the drawn SHAPE — the columns and their
 * order, the chooser and the date inside the row, `+ Service` and `+ Fee`
 * under their tables, the `Total`, the `STATUS` values, and the communication
 * card's rows, its withheld row and its stated absence.
 *
 * **IT DOES NOT PROVE THE PAGE AROUND THEM**: not the frame, not the stepper,
 * not the panel order, not the Review's two columns, and not the flow between
 * steps. Those are covered by the DOM suites and by nothing visual. Law 7's
 * fifth shape — print what you skipped beside what you checked.
 *
 * ⚠ **THE DEV SERVER, NOT `vite build`.** Vite's default build input is
 * `index.html` alone, so a second page at the project root is simply not in
 * the bundle and the shot would be of a 404. The dev server transforms any
 * html at the root, which is what this needs and is why no shared config file
 * is touched. **`--mode compose` matters for the real app** (a bare build
 * bakes the public API host in and sign-in then fails on correct credentials);
 * this harness makes no API call at all.
 *
 * ⚠ **NEVER `playwright install`** — the browser is at the path below.
 *
 *     node 10-scripts/req03_step34_shots.mjs
 */
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ⚠ **BORROWED FROM `07-frontend`, THE WAY THE OTHER 34 WALKTHROUGHS DO IT.**
// `10-scripts/` has no `node_modules` of its own, so a bare `import
// "playwright"` here resolves from the SCRIPT's folder and fails.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FRONTEND = path.join(ROOT, "07-frontend");
const OUT = path.join(ROOT, "05-prototype", "new-request-four-steps-2026-09-29", "as-built");
const EXE = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const PORT = Number(process.env.REQ03_PORT ?? 5199);

const ENTRY = path.join(FRONTEND, "req03-harness.html");
writeFileSync(
  ENTRY,
  `<!doctype html><html lang="en"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>REQ-03 steps 3 and 4 — as built</title></head>
<body><div id="root"></div>
<script type="module" src="/src/features/customers/__req03Harness.tsx"></script>
</body></html>\n`,
);

const server = spawn(
  "npx",
  ["vite", "--host", "127.0.0.1", "--port", String(PORT), "--strictPort"],
  { cwd: FRONTEND, stdio: ["ignore", "pipe", "pipe"] },
);
server.stdout.on("data", (chunk) => process.stdout.write(`  [vite] ${chunk}`));
server.stderr.on("data", (chunk) => process.stderr.write(`  [vite] ${chunk}`));

async function waitForServer(deadlineMs = 180_000) {
  const until = Date.now() + deadlineMs;
  while (Date.now() < until) {
    try {
      const response = await fetch(`http://127.0.0.1:${PORT}/req03-harness.html`);
      if (response.ok) return;
    } catch {
      /* not up yet — the loop is the wait */
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`the dev server never answered on ${PORT}`);
}

let failed = null;
try {
  await waitForServer();
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  try {
    for (const width of [1440, 1280, 420]) {
      const page = await browser.newPage({ viewport: { width, height: 1400 } });
      // ⚠ **`domcontentloaded`, NOT `networkidle`.** Vite's dev server holds an
      // HMR socket open for the life of the page, so the network is never idle
      // and the wait is one that can only ever time out — law 7's *incapable of
      // passing*. The real readiness signal is the selector below.
      await page.goto(`http://127.0.0.1:${PORT}/req03-harness.html`, {
        waitUntil: "domcontentloaded",
        timeout: 120_000,
      });
      await page.waitForSelector("[data-shot='services'] table", { timeout: 60_000 });
      // ⚠ **THE SHOT IS OF THE WHOLE PAGE**, so a column pushed off the side
      // shows rather than being cropped away by the viewport.
      const file = path.join(OUT, `req03-step34-${width}.png`);
      await page.screenshot({ path: file, fullPage: true });
      console.log(`  ${width} → ${file}`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
} catch (error) {
  failed = error;
} finally {
  server.kill("SIGTERM");
  rmSync(ENTRY, { force: true });
}
if (failed !== null) {
  console.error(failed);
  process.exit(1);
}
console.log("done. These shoot the COMPONENTS, not the page around them.");
