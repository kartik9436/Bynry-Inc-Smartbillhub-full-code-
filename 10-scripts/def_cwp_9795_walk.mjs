// DEF-CWP-9795 — the customer portal's "Your account" page, in a real browser,
// for an account exempt by CERTIFICATE (one tax) and one exempt by the old
// BLANKET flag, at 1440 and 390 (and 320, WCAG 2.1 reflow).
//
// World: `10-scripts/def_cwp_9795_seed.py`. Serve a LOCAL bundle against a
// LOCAL API (never the live site), then:
//
//   BASE=http://127.0.0.1:8795 node 10-scripts/def_cwp_9795_walk.mjs
//
// Photographs land in 08-qa/screens/def-cwp-9795-2026-10-06/.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8795";
const T = process.env.TENANT ?? "sixrivers";
const PASSWORD = "Six-Rivers-Walk-2026";
const CHROME = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OUT = new URL("../08-qa/screens/def-cwp-9795-2026-10-06/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const WHO = [
  {
    key: "certificate",
    email: "office@gracefellowship.test",
    expect: ["Tax exempt", "Exempt from", "City of Cedar Ford utility tax", "Dec 31, 2028"],
    never: ["CF-REL-2026-0412"],
  },
  {
    key: "blanket",
    email: "marcus.bell@example.test",
    expect: ["Tax exempt", "Runs out", "Mar 31, 2027"],
    never: ["TX-EX-88213", "Exempt from"],
  },
];

let failures = 0;
const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  for (const who of WHO) {
    for (const width of [1440, 390, 320]) {
      const ctx = await browser.newContext({ viewport: { width, height: 1000 }, baseURL: BASE });
      const page = await ctx.newPage();
      await page.goto(`/${T}/portal/sign-in`);
      await page.fill("#portal-email", who.email);
      await page.fill("#portal-password", PASSWORD);
      await page.locator("main button", { hasText: /^Sign in$/ }).click();
      await page.waitForURL(/\/portal\/home/, { timeout: 30000 });
      await page.goto(`/${T}/portal/account`);
      const panel = page.locator("[data-testid='your-account-tax']");
      let text = "";
      try {
        await panel.waitFor({ timeout: 20000 });
        text = (await panel.innerText()).replace(/\s+/g, " ");
      } catch {
        text = "(no Tax exempt panel)";
      }
      const missing = who.expect.filter((s) => !text.includes(s));
      const leaked = who.never.filter((s) => text.includes(s));
      const scroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      const ok = missing.length === 0 && leaked.length === 0 && !scroll;
      if (!ok) failures += 1;
      console.log(
        `${ok ? "PASS" : "FAIL"} ${who.key} @${width}: "${text}"` +
          (missing.length ? ` missing=${JSON.stringify(missing)}` : "") +
          (leaked.length ? ` leaked=${JSON.stringify(leaked)}` : "") +
          (scroll ? " SIDEWAYS-SCROLL" : ""),
      );
      await page.screenshot({ path: `${OUT}${who.key}-${width}.png`, fullPage: true });
      await panel.screenshot({ path: `${OUT}${who.key}-${width}-panel.png` }).catch(() => {});
      await ctx.close();
    }
  }
} finally {
  await browser.close();
}
console.log(failures ? `${failures} FAILED` : "ALL PASS");
process.exit(failures ? 1 : 0);
