// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-9320 — the app frame (sidebar, top bar, user menu) in the
//          ten non-English catalogues: English left in, verbs for nouns, and a
//          nav word that disagreed with its own page's heading.
// ───────────────────────────────────────────────────────
//
// Photographs the frame on ONE page (Meter Reads, so the nav word and the
// page heading it names sit side by side) in all eleven languages at 1440
// wide, then a second photograph with the user menu open. For each language
// it prints, and fails on:
//   * a blank photograph (no sidebar text);
//   * an English word from the frame's own catalogue text still in the frame
//     (the tenant name and the user's name/role are the utility's data);
//   * a sidebar label that is cut off (scrollWidth > clientWidth) or wraps
//     onto a second line.
//
// Expects the API on a scratch PostgreSQL 16 database prepared with `migrate`
// + `seed_demo` + `load_sample_data --tenant brazosbend`, and the SPA from
// `vite build --mode wolocal` served by `07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5198 OUT=08-qa/shell-i18n-2026-10-03 \
//     node 10-scripts/shell_i18n_frame_walk.mjs
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5198";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/shell-i18n";
const PAGE = process.env.PAGE ?? "reads";
const LANGS = (process.env.LANGS ?? "en,de,es,es-MX,fr-FR,hi,id-ID,it-IT,ja-JP,ko-KR,pt-BR").split(",");
mkdirSync(OUT, { recursive: true });

// Every English word the frame itself prints (shell.* catalogue text). A hit in
// a non-English frame is English left in. Matched as whole words.
const PROBES = [
  "Dashboard", "Plans", "Rates", "Premises", "Assets", "Accounts", "Reads", "Billing", "Payments",
  "Work", "Finance", "Runbooks", "Reports", "Settings", "Search", "Help", "Notifications",
  "Collapse", "My profile", "Change password", "Two-factor", "Sign out",
];
// Words that ARE that language's word and spell the English way — decided, not
// skipped (decision log 2026-10-03, DEF-SHL-9320). Printed, never silent.
const SAME_IN = { de: ["Dashboard"], "fr-FR": ["Notifications"] };

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
await page.goto(`${BASE}/${TENANT}/${PAGE}`, { waitUntil: "networkidle" });
await page.waitForSelector(".sidebar nav .side-label", { timeout: 30000 });

let failures = 0;
for (const lang of LANGS) {
  await page.keyboard.press("Escape");
  await page.evaluate((c) => window.__SMARTBILLHUB_I18N__?.changeLanguage(c), lang);
  await page.waitForTimeout(900);
  const facts = await page.evaluate(() => {
    const labels = [...document.querySelectorAll(".sidebar nav .side-label")].map((el) => {
      const lh = parseFloat(getComputedStyle(el).lineHeight) || 20;
      return {
        text: el.textContent.trim(),
        cut: el.scrollWidth > el.clientWidth + 1,
        wraps: el.getBoundingClientRect().height > lh * 1.5,
      };
    });
    const search = document.querySelector('.topbar input[type="search"], header input')?.getAttribute("placeholder") ?? "";
    const aria = [...document.querySelectorAll(".topbar [aria-label], .sidebar [aria-label], header [aria-label]")]
      .map((el) => el.getAttribute("aria-label"));
    const heading = document.querySelector("main h1, .page-header h1, h1")?.textContent.trim() ?? "";
    const crumbs = document.querySelector("nav.crumbs")?.textContent.trim() ?? "";
    return { labels, search, aria, heading, crumbs };
  });
  const file = `${OUT}/frame-${lang}.png`;
  await page.screenshot({ path: file });
  // user menu open
  await page.click(".sidebar button.foot");
  await page.waitForTimeout(300);
  const menuItems = await page.evaluate(() =>
    [...document.querySelectorAll(".foot-menu [role=menuitem]")].map((e) => {
      const cs = getComputedStyle(e);
      const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.4;
      const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
      return { text: e.textContent.trim(), wraps: e.getBoundingClientRect().height - pad > lh * 1.5 };
    }),
  );
  const menu = menuItems.map((m) => m.text);
  await page.screenshot({ path: `${OUT}/frame-${lang}-user-menu.png` });
  await page.keyboard.press("Escape");
  await page.click(".sidebar button.foot").catch(() => {});
  await page.waitForTimeout(200);
  if ((await page.$(".foot-menu")) !== null) await page.click(".sidebar button.foot");

  const frameText = [...facts.labels.map((l) => l.text), facts.search, ...facts.aria, ...menu, facts.crumbs].join(" | ");
  const hits =
    lang === "en" ? [] : PROBES.filter((w) => new RegExp(`(^|[^\\p{L}])${w}([^\\p{L}]|$)`, "u").test(frameText));
  const kept = hits.filter((w) => (SAME_IN[lang] ?? []).includes(w));
  const english = hits.filter((w) => !kept.includes(w));
  const cut = facts.labels.filter((l) => l.cut).map((l) => l.text);
  const wraps = [...facts.labels, ...menuItems].filter((l) => l.wraps).map((l) => l.text);
  const blank = facts.labels.length === 0 || facts.labels.every((l) => l.text === "");
  const bad = blank || english.length > 0 || cut.length > 0 || wraps.length > 0;
  if (bad) failures += 1;
  console.log(
    `${bad ? "FAIL" : "ok  "} ${lang.padEnd(5)} nav: ${facts.labels.map((l) => l.text).join(" · ")}\n` +
      `      heading: ${facts.heading} | crumbs: ${facts.crumbs} | search: ${facts.search}\n` +
      `      user menu: ${menu.join(" · ")}\n` +
      (kept.length ? `      same word in this language (decided): ${kept.join(", ")}\n` : "") +
      (english.length ? `      ENGLISH LEFT: ${english.join(", ")}\n` : "") +
      (cut.length ? `      CUT OFF: ${cut.join(", ")}\n` : "") +
      (wraps.length ? `      WRAPS: ${wraps.join(", ")}\n` : "") +
      (blank ? "      BLANK\n" : ""),
  );
}
await browser.close();
console.log(failures === 0 ? "all eleven frames clean" : `${failures} language(s) failed`);
process.exit(failures === 0 ? 0 : 1);
