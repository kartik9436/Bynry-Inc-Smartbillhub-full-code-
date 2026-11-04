// ── Trace ──────────────────────────────────────────────
// Lane A11Y-BC — the two walks the broad scan (`portal_bc_scan.mjs`) cannot do
// reliably: the six Ask cards by keyboard (open → heading, Back → the card),
// and My details' F-11 cases typed into the boxes (phone `abc`, ZIP `1`, the
// phone emptied). Exits 1 on any failure. PRIVATE COPY of the database only:
// the emptied-phone case really removes the number.
//
//   BASE=… TENANT=… EMAIL=… PASSWORD=… node 10-scripts/a11y/portal_bc_walk_f11_ask.mjs
// ───────────────────────────────────────────────────────
import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");
const BASE = process.env.BASE ?? "http://127.0.0.1:5631";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "";
const PASSWORD = process.env.PASSWORD ?? "";

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const failures = [];
function check(ok, label, detail) {
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${label}${detail === undefined ? "" : ` — ${detail}`}`);
  if (!ok) failures.push(label);
}
const focusOf = (page) =>
  page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body) return "BODY";
    return `${el.tagName.toLowerCase()}${el.getAttribute("data-action") ? `[${el.getAttribute("data-action")}]` : ""} "${(el.textContent ?? "").trim().slice(0, 40)}"`;
  });
const heard = (page) =>
  page.evaluate(() =>
    [...document.querySelectorAll("[data-portal-status], [data-portal-alert]")].map((r) => r.textContent).join(" | "),
  );

async function open(page, path) {
  await page.goto(`${BASE}/${TENANT}/portal${path}`, { waitUntil: "load", timeout: 90000 });
  await page.waitForSelector("h1", { timeout: 30000 });
  await page.waitForTimeout(1500);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
for (const lang of ["en", "es"]) {
  const page = await browser.newPage({ locale: lang === "es" ? "es-MX" : "en-US" });
  await page.goto(`${BASE}/${TENANT}/portal/`, { waitUntil: "load", timeout: 90000 });
  await page.evaluate((code) => window.sessionStorage.setItem("smartbillhub.portal.language", code), lang);

  // ── the six Ask cards ───────────────────────────────
  await open(page, "/ask");
  await page.waitForSelector("[data-action^='ask-']", { timeout: 20000 });
  const codes = await page.$$eval("[data-action^='ask-']", (els) => els.map((e) => e.getAttribute("data-action")));
  check(codes.length === 6, `${lang} six Ask cards drawn`, String(codes.length));
  for (const code of codes) {
    await page.focus(`[data-action="${code}"]`);
    await page.keyboard.press("Enter");
    await page.waitForTimeout(900);
    const opened = await focusOf(page);
    check(opened.startsWith("h1"), `${lang} ${code} opens: focus on the form heading`, opened);
    await page.focus('[data-action="cancel-ask"]');
    await page.keyboard.press("Enter");
    await page.waitForTimeout(900);
    const back = await focusOf(page);
    check(back.includes(`[${code}]`), `${lang} ${code} Back: focus returns to the card`, back);
  }

  // ── My details, F-11 ─────────────────────────────────
  if (EMAIL) {
    await open(page, "/sign-in");
    await page.fill("#portal-email", EMAIL);
    await page.fill("#portal-password", PASSWORD);
    await page.focus("main button[data-variant='primary']");
    await page.keyboard.press("Enter");
    await page.waitForURL(/\/portal\/home/, { timeout: 30000 });
    // The home page fetches before it draws its heading; give route focus
    // the eight seconds it waits for one.
    await page.waitForFunction(() => document.activeElement && document.activeElement !== document.body, null, { timeout: 9000 }).catch(() => undefined);
    const landed = await focusOf(page);
    check(landed !== "BODY", `${lang} sign-in success: focus not on the body`, landed);

    await open(page, "/my-details");
    await page.fill("#my-phone", "abc");
    await page.fill("#my-postal-code", "1");
    await page.focus("main button[data-variant='primary']");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(1200);
    const marks = await page.evaluate(() => ({
      phone: document.getElementById("my-phone")?.getAttribute("aria-invalid"),
      zip: document.getElementById("my-postal-code")?.getAttribute("aria-invalid"),
      phoneMsg: document.getElementById("my-phone-error")?.textContent,
      zipMsg: document.getElementById("my-postal-code-error")?.textContent,
    }));
    check(marks.phone === "true" && marks.zip === "true", `${lang} abc / 1: both boxes invalid`, JSON.stringify(marks));
    check((await focusOf(page)).startsWith("div"), `${lang} abc / 1: focus on the summary`, await focusOf(page));

    await open(page, "/my-details");
    await page.fill("#my-phone", "");
    await page.focus("main button[data-variant='primary']");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2500);
    const said = await heard(page);
    const removed = lang === "es" ? "Teléfono eliminado." : "Phone removed.";
    const stops = lang === "es" ? "Sin teléfono no hay recordatorios por SMS." : "Text reminders stop without a phone.";
    check(said.includes(removed), `${lang} phone emptied: '${removed}' heard`, said.slice(0, 160));
    check(said.includes(stops), `${lang} phone emptied: reminders sentence heard`, said.slice(0, 160));
    check(!said.includes(" 0 "), `${lang} never 'Saved on 0 accounts'`);
    check((await focusOf(page)) !== "BODY", `${lang} phone emptied: focus on the result`, await focusOf(page));
    // Put a number back for the next language's run.
    await open(page, "/my-details");
    await page.fill("#my-phone", "(281) 555-0100");
    await page.focus("main button[data-variant='primary']");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2000);
  }
  await page.close();
}
await browser.close();
console.log(failures.length === 0 ? "WALK PASS" : `WALK FAIL (${failures.length})`);
process.exit(failures.length === 0 ? 0 : 1);
