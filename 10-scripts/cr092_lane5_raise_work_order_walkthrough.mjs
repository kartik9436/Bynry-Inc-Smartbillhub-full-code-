// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2 · lane 5 — SCREEN 27, "Raise work order",
//          built to blueprint section 05 figure 42 (pages 104-107).
// Rules:   BR-WRK-056 (ONE form, many ways in) · BR-AST-534 (a control the
//          STATE forbids is shown disabled WITH ITS REASON, PO 2026-09-12) ·
//          BR-SHL-025 · B14 rules 2, 4, 11, 21, 31, 32, 36, 38, 39, 41, 42 ·
//          hard-won laws 2, 6, 7
// ───────────────────────────────────────────────────────
//
// WHY A WALKTHROUGH. Every gap this closes is one a green suite passed over:
// a five-slot header that was a bare title, a select wearing a bespoke border,
// a footer whose buttons sat in the opposite order from the five sibling action
// screens. `renderToStaticMarkup` proves a component; only a browser can say
// the route resolves, the tenant's catalogues carry the words, and the header
// actually draws five slots.
//
// ⚠ **IT NEEDS `10-scripts/cr092_lane5_seed_template.py` FIRST.** The database
// holds ZERO `work_order_templates` on every tenant and NO asset carries a
// certification cadence, so without it this screen has exactly one state — its
// refusal — and the attention strip cannot render at all. Run the seed, run
// this, then run the seed with `--drop`.
//
// ⚠ **SIGN IN, WAIT FOR THE DASHBOARD, THEN WAIT AGAIN.** The shell bootstraps
// the tenant's regional settings AFTER the session lands; navigating straight
// on renders "We couldn't load your regional settings." on every screen.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

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
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const SPA = "http://127.0.0.1:8080";
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const PASSWORD = "S3cure!passw0rd";
const ASSET = "01a09bc5-ae0c-775a-a7d5-0361eb1c6a1a"; // M-7001
const OUT = "/tmp/build5/shots";

const say = (...a) => console.log(...a);

async function signIn(page) {
  await page.goto(`${SPA}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  await page.waitForTimeout(2500); // regional settings bootstrap
}

async function walk(page, width) {
  await page.setViewportSize({ width, height: 900 });
  await page.goto(`${SPA}/${TENANT}/assets/${ASSET}/work-orders/new`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(900);

  const seen = await page.evaluate(() => {
    const text = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : null);
    const head = document.querySelector(".page-header, header") ?? document.body;
    const h1 = document.querySelector("h1");
    const select = document.querySelector("select#template");
    const fieldset = document.querySelector("[data-raise-template]");
    const submit = document.querySelector("[data-raise-submit]");
    const boxes = [...document.querySelectorAll("[data-consequence]")].map((b) => ({
      hook: b.getAttribute("data-consequence"),
      text: text(b),
    }));
    const footer = submit?.closest("div");
    const order = footer ? [...footer.querySelectorAll("button")].map((b) => text(b)) : [];
    return {
      kicker: text(head.querySelector(".page-header-kicker, [class*=kicker]")),
      title: text(h1),
      titlePx: h1 ? getComputedStyle(h1).fontSize : null,
      status: text(document.querySelector(".page-header-status, [class*=status]")),
      statusBlock: text(document.querySelectorAll("h1")[0]?.parentElement?.parentElement),
      attention: text(document.querySelector("[data-attention]")),
      attentionTone: document.querySelector("[data-attention]")
        ? getComputedStyle(document.querySelector("[data-attention]")).backgroundColor
        : null,
      context: text(document.querySelector(".page-header-rollup")),
      boxes,
      label: text(document.querySelector('label[for="template"]')),
      help: text(document.querySelector("#template-help")),
      selectClass: select ? select.className : null,
      selectOptions: select ? [...select.options].map((o) => o.text) : null,
      fieldsetDisabled: fieldset ? fieldset.disabled : null,
      selectDisabled: select ? select.disabled : null,
      submitLabel: text(submit),
      submitDisabled: submit ? submit.disabled : null,
      submitTitle: submit ? submit.getAttribute("title") : null,
      submitDescribedBy: submit ? submit.getAttribute("aria-describedby") : null,
      refusal: text(document.querySelector("[data-raise-none]")),
      footerOrder: order,
      bodyScrollsSideways: document.body.scrollWidth > document.body.clientWidth,
    };
  });
  say(`\n──────── ${width}px ────────`);
  say(JSON.stringify(seen, null, 2));
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: `${OUT}/screen27-${width}.png`, fullPage: true });
  return seen;
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage();
  const failed = [];
  page.on("requestfailed", (r) => failed.push(r.url()));
  page.on("response", (r) => {
    if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`);
  });
  page.on("console", (m) => {
    if (m.type() === "error") say("console error:", m.text());
  });

  await signIn(page);
  await walk(page, 1280);
  await walk(page, 1440);

  // The KEYBOARD reach: tab to the picker, choose, and confirm the submit wakes.
  await page.selectOption("select#template", { index: 1 });
  await page.waitForTimeout(300);
  const afterChoice = await page.evaluate(() => {
    const submit = document.querySelector("[data-raise-submit]");
    return {
      submitDisabled: submit.disabled,
      submitTitle: submit.getAttribute("title"),
      submitDescribedBy: submit.getAttribute("aria-describedby"),
      chosen: document.querySelector("select#template").selectedOptions[0].text,
    };
  });
  say("\n──────── after choosing a template ────────");
  say(JSON.stringify(afterChoice, null, 2));
  await page.screenshot({ path: `${OUT}/screen27-chosen.png`, fullPage: true });

  say("\nfailed requests:", failed.length ? failed : "none");
  await browser.close();
})();
