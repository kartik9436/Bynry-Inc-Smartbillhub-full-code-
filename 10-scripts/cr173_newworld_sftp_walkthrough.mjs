// ── Trace ──────────────────────────────────────────────
// Change:  CR-173-BRC10 — Send to City folder + New World receipt push, walked
//          as a System Admin in a browser at 1440 (the staff design width).
// ───────────────────────────────────────────────────────
//
// The stack it expects (all LOCAL — never the City's server, never a deployed site):
//   · the API on API_PROXY_TARGET, with `10-scripts/cr173_newworld_walk_seed.py` run;
//   · the SPA built `--mode lane`, served by `07-frontend/server.mjs`;
//   · the fake SFTP server: `python3 06-backend/tests/fake_sftp_server.py --port 2222 --root <dir>`.
//
//   SFTP_PORT=2222 DAY=2026-10-05 OUT=<dir> node 10-scripts/cr173_newworld_sftp_walkthrough.mjs
//
// Photos, in order: 01 empty section · 02 saved, password masked · 03 test OK
// against the fake server · 04 test with a wrong password · 05 the runbook's
// Run dialog · 06 the runbook after a live run · 07 the run history row.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5373";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/nwsftp";
const SFTP_PORT = process.env.SFTP_PORT ?? "2222";
const DAY = process.env.DAY ?? "";
const FAKE = "test-password-not-real";
const RUN_OPEN = process.env.RUN_OPEN ?? "Open the run";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
};

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const bodies = [];
page.on("response", async (r) => {
  if (r.url().includes("/groups/") || r.url().includes("/runbooks/")) {
    try { bodies.push(await r.text()); } catch { /* streamed */ }
  }
});
page.on("pageerror", (e) => console.log("  page error:", e.message));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 30000 });

const section = () => page.locator("[data-field-group=send_file]");
const shoot = async (name, locator) => {
  await (locator ?? page).screenshot({ path: join(OUT, name), ...(locator ? {} : { fullPage: true }) });
};

// 01 · the empty section
await page.goto(`${BASE}/${TENANT}/settings/connectors/erp_newworld/configure`, { waitUntil: "networkidle" });
await section().waitFor({ timeout: 20000 });
await section().scrollIntoViewIfNeeded();
check("the section is titled Send to City folder", (await section().innerText()).includes("Send to City folder"));
await shoot("01-send-to-city-folder-empty.png", section());

// 02 · saved, password masked
await section().locator("#field-sftp_host").fill("127.0.0.1");
await section().locator("#field-sftp_port").fill(SFTP_PORT);
await section().locator("#field-sftp_username").fill("Bynry-test");
await section().locator("#field-sftp_password").fill(FAKE);
await section().locator("#field-sftp_path").fill("/");
await section().getByRole("button", { name: "Save ✓" }).click();
await section().locator("[data-group-saved]").waitFor({ timeout: 15000 });
const masked = await section().locator("[data-password-hint]").innerText();
check("the password shows only as its hint", masked.includes("••••real") && !masked.includes(FAKE), masked);
check("the password box is empty after saving", (await section().locator("#field-sftp_password").inputValue()) === "");
await shoot("02-send-to-city-folder-saved-masked.png", section());

// 03 · test OK against the local fake server
await section().getByRole("button", { name: "Test connection" }).click();
await section().locator("[data-group-test-result]").waitFor({ timeout: 40000 });
const ok = await section().locator("[data-group-test-result]").getAttribute("data-group-test-result");
check("Test connection succeeds against the fake server", ok === "ok");
// The key is stored by the FIRST successful test and shown then; a re-run over
// its own leftovers finds it already in the Server key box instead.
const keyShown = (await section().locator("[data-server-key]").count()) === 1;
const keyStored = (await section().locator("#field-sftp_host_key").inputValue()).startsWith("SHA256:");
check("the server key is shown or already stored", keyShown || keyStored);
await shoot("03-send-to-city-folder-test-ok.png", section());

// 04 · a wrong password
await section().locator("#field-sftp_password").fill("wrong-but-also-fake");
await section().getByRole("button", { name: "Save ✓" }).click();
await section().locator("[data-group-saved]").waitFor({ timeout: 15000 });
await section().getByRole("button", { name: "Test connection" }).click();
await section().locator("[data-group-test-result=refused]").waitFor({ timeout: 40000 });
check("a wrong password reads one sentence", (await section().innerText()).includes("User name or password refused."));
await shoot("04-send-to-city-folder-test-wrong-password.png", section());
// put the right one back for the run
await section().locator("#field-sftp_password").fill(FAKE);
await section().getByRole("button", { name: "Save ✓" }).click();
await section().locator("[data-group-saved]").waitFor({ timeout: 15000 });

// 05 · the runbook's Run dialog
await page.goto(`${BASE}/${TENANT}/runbooks/newworld_receipt_push`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Run ▶" }).first().click();
const dialog = page.getByRole("dialog");
await dialog.waitFor();
await dialog.locator("#run_mode").selectOption("live");
if (DAY) await dialog.locator("#run_day").fill(DAY);
await shoot("05-runbook-run-dialog.png");
await dialog.getByRole("button", { name: "Run ▶" }).click();
await dialog.waitFor({ state: "detached", timeout: 60000 });
await page.waitForTimeout(1500);

// 06 · the runbook's runs
await page.goto(`${BASE}/${TENANT}/runbooks/newworld_receipt_push#runs`, { waitUntil: "networkidle" });
await shoot("06-runbook-after-live-run.png");

// 07 · the connection's run history
await page.goto(`${BASE}/${TENANT}/settings/integrations/erp_newworld`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const text = await page.locator("body").innerText();
check("the two partner rows keep their own address (DEF-INT-10000)", text.includes("/partner/v1/receipts"));
check("the run history lists Send receipt file", text.includes("Send receipt file"));
await shoot("07-connection-after-run.png");
await page.getByText("Recent activity").scrollIntoViewIfNeeded();
await shoot("08-run-history.png", page.locator("section", { has: page.getByText("Recent activity") }).last());
// open the newest send run, where the summary names the file
const openRun = page.locator("section", { has: page.getByText("Recent activity") }).last().getByRole("button", { name: RUN_OPEN }).first();
if ((await openRun.count()) > 0) {
  await openRun.click();
  await page.waitForTimeout(1500);
  const detail = await page.locator("body").innerText();
  check("the run names the file, folder and count", /Receipt_\d{8}\.xml · \d+ receipts · to \//.test(detail));
  await shoot("09-run-detail.png");
}

check("no response carried the password", !bodies.some((b) => b.includes(FAKE)));
await browser.close();
const failed = results.filter((r) => !r.ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
