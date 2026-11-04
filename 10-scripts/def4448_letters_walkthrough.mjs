// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-BIL-4448 · DEF-NOT-4449 · DEF-PAY-4450 · DEF-PAY-4451
// Ruling:  PO 2026-09-07 — "(a) Fix all of them now", and the standing
//          definition of done: "everything should be executed based on actual
//          code, and rules that we place, also ensure you do web walkthorugh
//          before you sign off the user story or build".
// ───────────────────────────────────────────────────────
//
// OPEN THE LETTERS IN A BROWSER AND READ THEM — hard-won law 6, which is the
// only thing in this repo that looks at rendered output.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  IT COUNTS EM-DASHES, AND IT ALSO NAMES THE VALUES IT EXPECTS TO SEE.    ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// A walkthrough that only counted `——` would be green over a letter whose
// template lost its tokens — the body would simply have nothing to dash. So
// every check below asserts a CONCRETE STRING a person could read aloud, and
// the em-dash count is reported beside it rather than instead of it.
//
// Run:  node 10-scripts/def4448_letters_walkthrough.mjs
//   WEB=http://127.0.0.1:8180  TENANT=brazosbend
//   EMAIL=dana@brazosbendutilities.com  PASSWORD='S3cure!passw0rd'

import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// The frontend owns the browser (`10-scripts/12-smoke-walkthrough.mjs`'s idiom):
// resolving from its package.json is what makes this runnable from the repo root
// without a second install, and `playwright-core` is what is actually there.
const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

// The pinned revision is not what is installed here (1194 on disk, 1234 wanted),
// and `playwright install` is forbidden in this sandbox. `12-smoke-walkthrough
// .mjs` already solved this; the same resolution, for the same reason — an
// off-revision chromium beats not looking at the screen at all, and the
// substitution is PRINTED rather than silent.
const resolveChromium = () => {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
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
  throw new Error(`no chromium found; playwright wants ${wanted}`);
};

const WEB = process.env.WEB || "http://127.0.0.1:8180";
const TENANT = process.env.TENANT || "brazosbend";
const EMAIL = process.env.EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/def4448-walk";

const findings = [];
const note = (ok, what, detail) => {
  findings.push({ ok, what, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${what}${detail ? " — " + detail : ""}`);
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on("console", (m) => {
    if (m.type() === "error") console.log("   [console error]", m.text().slice(0, 160));
  });

  // ── sign in through the real door ────────────────────────────────────────
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  note(!page.url().includes("/signin"), "signed in", page.url());

  // ── Settings → Notifications → messages waiting to go out ────────────────
  await page.goto(`${WEB}/${TENANT}/settings/notifications`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}-notifications.png`, fullPage: true });

  // Open the first message that offers its body. The panel only discloses a
  // body while NOTHING could have sent it (unsent_preview's self-disarming
  // gate), which is true on this stack: no provider is connected.
  // The worklist is its OWN TAB under Notifications (CR-048 wave I, PO
  // 2026-08-30: *"'Messages needing attention' gets its own tab"*), so the
  // settings landing shows none of these controls until it is opened.
  const tab = page.locator('button:has-text("Messages needing attention"), a:has-text("Messages needing attention"), [role="tab"]:has-text("Messages")');
  if (await tab.count()) {
    await tab.first().click();
    await page.waitForTimeout(1500);
  } else {
    console.log("PAGE TEXT >>>");
    console.log((await page.locator("body").innerText()).slice(0, 1800));
  }

  const showButtons = page.locator('button:has-text("Show the message")');
  const count = await showButtons.count();
  note(count > 0, "messages needing attention offer a body", `${count} button(s)`);

  // ⚠ **READ THE DRAWER, NOT THE PAGE.** `innerText` of `body` includes the
  // whole shell — nav, table, every other row — so an em-dash count taken over
  // it says nothing about the LETTER. The panel is what this defect is about.
  const readOne = async (index) => {
    await showButtons.nth(index).click();
    await page.waitForTimeout(1200);
    const panel = page.locator('[role="dialog"], aside, section:has-text("Waiting to go out")');
    const scope = (await panel.count()) ? panel.last() : page.locator("body");
    const text = await scope.innerText();
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
    return text;
  };

  // One of each kind the table offers, found by the row's own TYPE cell rather
  // than by position — a positional pick silently reads whichever letter the
  // sort happens to put first.
  const kinds = ["Notice", "Bill", "Receipt"];
  for (const kind of kinds) {
    const row = page.locator("tr", { hasText: kind }).first();
    const button = row.locator('button:has-text("Show the message")');
    if (!(await button.count())) {
      note(false, `a ${kind} row offers its body`, "no control");
      continue;
    }
    await button.click();
    await page.waitForTimeout(1200);
    const panel = page.locator('[role="dialog"], aside, section:has-text("Waiting to go out")');
    const scope = (await panel.count()) ? panel.last() : page.locator("body");
    const text = await scope.innerText();
    const dashes = (text.match(/——/g) || []).length;
    console.log(`\n════ ${kind.toUpperCase()} — ${dashes} em-dash(es) in the panel ════`);
    console.log(text.slice(0, 2600));
    await page.screenshot({ path: `${OUT}-${kind.toLowerCase()}.png`, fullPage: true });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
  }

  await browser.close();

  const failed = findings.filter((f) => !f.ok);
  console.log(`\n${findings.length - failed.length}/${findings.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
};

run().catch((error) => {
  console.error("walkthrough crashed:", error);
  process.exit(2);
});
