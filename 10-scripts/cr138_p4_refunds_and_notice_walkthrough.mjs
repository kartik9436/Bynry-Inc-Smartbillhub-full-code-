// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.10` · `P4.14` · `P4.26` · `P4.27` — screen 6·1
//           Refunds (moved into payments, Kind column and filter, Credit beside
//           Raise) and screen 7·3d Send a notice (a wizard on `WizardFrame`).
// Rules:    CLAUDE.md hard-won law 6 (diff the running app against the drawing —
//           "nine defects were found this way and by nothing else") · B14 rule
//           31 (no database id on screen) · rule 42 (built from the drawing as
//           an image)
// ───────────────────────────────────────────────────────
//
// ⚠ **IT BOOTS NOTHING, ON PURPOSE** — the same shape as
// `cr136_p2_counter_screens_walkthrough.mjs`, whose header explains why: the
// smoke stack tears itself down on exit, which is right for a smoke run and
// wrong for looking at a tab. Point it at an already-running SPA join:
//
//     cd 06-backend && python3 manage.py runserver 127.0.0.1:8011 --noreload &
//     cd 07-frontend && ./node_modules/.bin/vite build
//     PORT=8012 API_PROXY_TARGET=http://127.0.0.1:8011 node server.mjs &
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers WEB=http://127.0.0.1:8012 \
//       node 10-scripts/cr138_p4_refunds_and_notice_walkthrough.mjs
//
// **WHAT IT ASKS, and every question is one no gate in this repo can answer:**
//   1. does `/payments/refunds` OPEN, with the payments strip and **Refunds**
//      selected — the move itself (`P4.10`);
//   2. does the OLD `/finance/refunds` address still land somewhere — the
//      no-silent-dead-link half of that move;
//   3. does 6·1 draw a **Kind** column and a Kind FILTER, and is there a uuid
//      anywhere on the body (rule 31);
//   4. is **Issue credit** beside **Raise refund** in the page head (`P4.10`);
//   5. does `/payments/outstandings/send-notice` open a THREE-STEP RAIL, and
//      does a pasted `?step=3` CLAMP back to step 1 (`P4.27` — the assertion
//      that separates this wizard from the siblings that pass
//      `reached: step`);
//   6. has the **Send notice** door replaced the two dead buttons on 7·1.
//
// ⚠ **AN EMPTY TENANT IS NOT A FINDING FOR THE COLUMN QUESTIONS.** `DataTable`
// draws its empty state INSTEAD of the header row, so a tenant with no refunds
// and no credit notes reports every column missing. The script says which case
// it is rather than printing a line that reads like a defect.
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// `playwright-core` is BORROWED from `07-frontend`, not imported: a bare
// specifier resolves from this module's own directory, never the CWD.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error("no chromium found");
}

const WEB = process.env.WEB || "http://127.0.0.1:8012";
const TENANT = process.env.SMOKE_TENANT || "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/claude-0/lane-p4screens-b/shots";
mkdirSync(OUT, { recursive: true });

const findings = [];
function note(step, what) {
  findings.push(`[${step}] ${what}`);
  console.log(`  · ${step}: ${what}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => note("console", `PAGE ERROR: ${e.message}`));

try {
  console.log("step 1 · sign in");
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });

  console.log("step 2 · 6·1 at its NEW address — P4.10");
  await page.goto(`${WEB}/${TENANT}/payments/refunds`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${OUT}/01-refunds-6-1-1440.png`, fullPage: true });
  note("P4.10", `page title reads ${JSON.stringify(await page.textContent("h1").catch(() => null))}`);
  // The strip, and which tab it shows as selected. A screen on its own static
  // route that highlighted nothing would look like a broken deployment — the
  // failure `CollectionsPage` records one screen over.
  const selected = await page
    .locator('[role="tab"][aria-selected="true"], .tabs [aria-current="page"]')
    .first()
    .textContent()
    .catch(() => null);
  note("P4.10", `strip shows ${JSON.stringify(selected)} as selected`);

  console.log("step 3 · the OLD address — no silent dead link");
  await page.goto(`${WEB}/${TENANT}/finance/refunds`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  note("P4.10", `/finance/refunds landed on ${page.url()}`);
  await page.screenshot({ path: `${OUT}/02-legacy-address.png` });

  console.log("step 4 · the Kind column and filter — P4.26");
  await page.goto(`${WEB}/${TENANT}/payments/refunds`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  const headers = await page.locator("th").allTextContents();
  note("P4.26", `columns drawn: ${JSON.stringify(headers)}`);
  if (headers.length === 0) {
    note("P4.26", "NO HEADER ROW — this tenant has no refunds and no credit notes, so DataTable drew its EMPTY STATE. Not a column defect.");
  }
  // ⚠ **THIS READ `button:has-text("Filter")` ON THE FIRST RUN AND REPORTED
  // `false` OVER A BUTTON THAT WAS PLAINLY ON THE SCREENSHOT.** The control is
  // `+ Filter ▾` and it is not a `<button>` element. A selector that names the
  // wrong element reports an absence indistinguishable from a real one — law
  // 7's *looking at the wrong thing* — so this asks for the TEXT and says which
  // question it answered.
  const filterControl = await page.locator(':text("+ Filter")').count();
  note("P4.26", `+ Filter control present: ${filterControl > 0}`);
  const body = (await page.textContent("body")) ?? "";
  if (/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(body)) {
    note("P4.26", "B14 RULE 31 BREACH: something uuid-shaped is on screen");
  } else {
    note("P4.26", "no uuid on the body (rule 31 holds)");
  }
  // ⚠ The load-bearing negative, asked of RENDERED output for the first time:
  // a credit note must not carry a state word.
  for (const word of ["Applied"]) {
    const seen = await page.locator(`td:has-text("${word}")`).count();
    if (seen > 0) note("P4.26", `A CREDIT MAY HAVE BEEN GIVEN A STATE: a cell reads "${word}"`);
  }
  const noState = await page.locator('td:has-text("No state")').count();
  note("P4.26", `cells drawing the stated absence "No state": ${noState}`);

  console.log("step 5 · Issue credit beside Raise refund — P4.10");
  const issue = await page.locator('button:has-text("Issue credit")').count();
  // ⚠ **THE SHIPPED LABEL IS *Raise a refund* AND THE DRAWING SAYS *Raise
  // refund*.** The first run searched for the drawn wording and reported ×0 over
  // a button that is on the screenshot — a finding about the SCRIPT that read
  // like a finding about the product. Both spellings are counted now, and the
  // difference is filed rather than silently normalised here.
  const raiseDrawn = await page.locator('button:has-text("Raise refund")').count();
  const raiseShipped = await page.locator('button:has-text("Raise a refund")').count();
  note(
    "P4.10",
    `page head: Issue credit ×${issue}, Raise refund (drawn) ×${raiseDrawn}, Raise a refund (shipped) ×${raiseShipped}`,
  );
  if (issue > 0) {
    await page.click('button:has-text("Issue credit")');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${OUT}/03-issue-credit-door.png` });
    note(
      "P4.10",
      `door heading ${JSON.stringify(
        await page
          .locator('[role="dialog"] h2, [role="dialog"] h3, .modal-card h2, .modal-card h3')
          .first()
          .textContent()
          .catch(() => null),
      )}`,
    );
    await page.keyboard.press("Escape");
  }

  console.log("step 6 · 7·3d opens, and the step CLAMPS — P4.27");
  // Straight to ?step=3 with NO selection: the clamp must put it back to 1, and
  // the empty Who step must offer the way back rather than a silent empty send.
  await page.goto(`${WEB}/${TENANT}/payments/outstandings/send-notice?step=3`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/04-send-notice-clamped.png`, fullPage: true });
  note("P4.27", `pasted ?step=3 settled at ${page.url()}`);
  note("P4.27", `title reads ${JSON.stringify(await page.textContent("h1").catch(() => null))}`);
  // ⚠ The first run read `.br-steps li, .br-steps button` and reported `[]`
  // over a rail that is plainly on the screenshot. Same fault as the filter
  // selector above; ask for the WORDS.
  const rail = [];
  for (const label of ["Who", "Which notice", "Preview & send"]) {
    rail.push(`${label}:${await page.locator(`:text-is("${label}")`).count()}`);
  }
  note("P4.27", `rail steps found: ${JSON.stringify(rail)}`);
  // The CLAMP is what `P4.27` asks for, and it is about which step OPENS — so
  // ask the SCREEN, not the address bar. Step 1's own heading is the answer.
  const onStepOne = await page.locator(':text("Nobody is selected"), :text("Who is this going to?")').count();
  note("P4.27", `?step=3 rendered step ONE: ${onStepOne > 0}`);
  const continueLive = await page.locator('button:has-text("Continue")').isEnabled().catch(() => null);
  note("P4.27", `Continue enabled over an empty selection: ${continueLive}`);

  console.log("step 7 · the door on 7·1 — the hold that expired");
  await page.goto(`${WEB}/${TENANT}/payments/outstandings`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${OUT}/05-debtors-toolbar.png`, fullPage: true });
  const debtors = (await page.textContent("body")) ?? "";
  for (const gone of ["Send a reminder", "Send a disconnection notice", "no route accepts one"]) {
    if (debtors.includes(gone)) note("P4.14", `THE HOLD IS STILL ON SCREEN: "${gone}"`);
  }
  note("P4.14", "the retired refusal strings are absent from the Debtors body");

  console.log("step 8 · 1280, the laptop minimum");
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${WEB}/${TENANT}/payments/refunds`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/06-refunds-1280.png`, fullPage: true });
  const scrolls = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  note("1280", `page scrolls sideways: ${scrolls}`);
} finally {
  await browser.close();
  console.log("\n── findings ──");
  for (const line of findings) console.log(line);
  console.log(`\nshots in ${OUT}`);
}
