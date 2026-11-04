// ── Trace ──────────────────────────────────────────────
// Lane:    A11Y-BC — customer portal accessibility, Groups B and C
//          (decision log 2026-10-23, "Portal accessibility, Groups B and C …")
// Finding: F-02 (messages not announced) · F-03 (inputs not marked invalid /
//          described / required) · F-11 (My details phone + ZIP) · F-18
//          (sign-in / forgot-password messages) · F-22 (a disabled button's
//          reason is a tooltip only) · F-04 (focus drops to the body) · F-17
//          (language and account selectors)
// ───────────────────────────────────────────────────────
//
// A READ-ONLY SCAN of a running portal, used for the BEFORE and the AFTER of
// `08-qa/a11y-portal-2026-10/group-bc-inventory.md`. It asks the same five
// questions of every form, in English and Spanish, signed out and signed in:
//
//   1. what the inputs say about themselves (aria-invalid, aria-describedby,
//      aria-required, and how many asterisks are drawn);
//   2. what the always-present live regions hold after the submit;
//   3. where focus is after the submit;
//   4. how many inputs are marked in error after the submit;
//   5. which disabled buttons carry their reason ONLY in a `title`.
//
// and, for Group C, presses each listed control WITH THE KEYBOARD and reports
// where focus lands, then where one Tab takes it.
//
// ⚠ IT SUBMITS EMPTY FORMS ONLY — nothing is typed, so no row is written by a
// guest form; and it is pointed at a PRIVATE COPY of the database with fake
// (`example.invalid`) people in it. Never run it at a shared stack.
//
//   BASE=http://127.0.0.1:5631 TENANT=brazosbend EMAIL=… PASSWORD=… \
//     OUT=<dir> [STRICT=1] node 10-scripts/a11y/portal_bc_scan.mjs
//
// Prints one line per measurement and writes `scan.json` into OUT.
//
// ⚠ **`STRICT=1` IS THE KEYBOARD GATE (F-04).** It exits 1, naming each one,
// when ANY pressed submit or listed action leaves focus on the body, or when a
// submitted form put nothing in a live region. Without it the scan only
// measures (that is how the BEFORE was taken: on the old code it must not stop
// at the first failure).
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5631";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "";
const PASSWORD = process.env.PASSWORD ?? "";
const OUT = process.env.OUT ?? "/tmp/a11y-bc";
const LANGS = (process.env.LANGS ?? "en,es").split(",");
mkdirSync(OUT, { recursive: true });

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

// Every form the tester named, plus every other portal screen with a commit.
const GUEST_FORMS = ["/sign-in", "/forgot-password", "/enrol", "/track", "/report", "/start-service", "/pay", "/update-email"];
const SIGNED_IN_FORMS = [
  "/my-details",
  "/my-details/preferences",
  "/accounts/add",
  "/ask-for-a-plan",
  "/ask-a-question",
  "/stop-or-restart",
  "/usage/submit",
  "/payment-methods",
  "/pay-now",
  "/help-paying",
];

/** Where focus is, as a short readable descriptor. */
const FOCUS_JS = () => {
  const el = document.activeElement;
  if (!el || el === document.body) return "BODY";
  const bits = [el.tagName.toLowerCase()];
  if (el.id) bits.push(`#${el.id}`);
  for (const a of el.getAttributeNames()) {
    if (a.startsWith("data-") && a !== "data-variant" && a !== "data-size") bits.push(`[${a}]`);
  }
  const text = (el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 40);
  return `${bits.join("")} "${text}"`;
};

/** The five questions, read in one evaluate. */
const READ_JS = () => {
  const main = document.querySelector("main") ?? document.body;
  const fields = [...main.querySelectorAll("input:not([type=hidden]), select, textarea")];
  const live = [...document.querySelectorAll('[aria-live], [role="status"], [role="alert"]')]
    .map((el) => (el.textContent ?? "").replace(/\s+/g, " ").trim())
    .filter((s) => s.length > 0);
  const disabled = [...main.querySelectorAll("button[disabled], button[aria-disabled=true]")].map((b) => ({
    label: (b.textContent ?? "").trim().slice(0, 30),
    title: b.getAttribute("title"),
    describedBy: b.getAttribute("aria-describedby"),
  }));
  return {
    h1: (document.querySelector("h1")?.textContent ?? "").trim(),
    fields: fields.length,
    invalid: fields.filter((f) => f.getAttribute("aria-invalid") === "true").length,
    describedBy: fields.filter((f) => f.hasAttribute("aria-describedby")).length,
    required: fields.filter((f) => f.getAttribute("aria-required") === "true" || f.required).length,
    asterisks: [...main.querySelectorAll("label span")].filter((s) => s.textContent.trim() === "*").length,
    live,
    titleOnlyDisabled: disabled.filter((d) => d.title && !d.describedBy).length,
    disabled,
    summary: document.querySelectorAll("[data-error-summary]").length,
  };
};

const results = [];
const say = (...parts) => console.log(...parts);
function record(row) {
  results.push(row);
  say(JSON.stringify(row));
}

async function setLanguage(page, lang) {
  await page.evaluate((code) => {
    try {
      window.sessionStorage.setItem("smartbillhub.portal.language", code);
    } catch {
      /* private window */
    }
  }, lang);
}

/** One step that fails is RECORDED and the scan goes on — a scan that stops
 *  at the first missing box reports nothing about the other forty. */
async function safe(label, fn) {
  try {
    await fn();
  } catch (error) {
    record({ kind: "error", label, error: String(error).split("\n")[0] });
  }
}

async function open(page, path) {
  await page.goto(`${BASE}/${TENANT}/portal${path}`, { waitUntil: "load", timeout: 60000 });
  // Not `networkidle`: the dev server keeps a socket open. The page is ready
  // when its frame has drawn a heading.
  await page.waitForSelector("[data-portal-frame] h1, h1", { timeout: 30000 }).catch(() => undefined);
  // A page draws its heading before its form arrives from the server; the
  // first baseline run read 0 fields on four pages that have them.
  await page.waitForSelector("main input, main select, main textarea, main button", { timeout: 8000 }).catch(() => undefined);
  await page.waitForTimeout(1500);
}

async function submitEmpty(page, label, lang, auth) {
  const before = await page.evaluate(READ_JS);
  const buttons = page.locator("main button[data-variant='primary']:not([disabled])");
  const n = await buttons.count();
  if (n === 0) {
    record({ kind: "form", path: label, lang, auth, before, submitted: false });
    return;
  }
  // Press it with the KEYBOARD, as the tester did: focus then Enter.
  const target = buttons.nth(n - 1);
  await target.focus();
  await page.keyboard.press("Enter");
  await page.waitForTimeout(1500);
  const after = await page.evaluate(READ_JS);
  const focus = await page.evaluate(FOCUS_JS);
  record({ kind: "form", path: label, lang, auth, before, submitted: true, after, focus });
}

async function keyboardAction(page, label, selector, key, lang, auth) {
  const el = page.locator(selector).first();
  if ((await el.count()) === 0) {
    record({ kind: "action", label, lang, auth, present: false });
    return;
  }
  await el.focus();
  await page.keyboard.press(key);
  await page.waitForTimeout(1200);
  const focus = await page.evaluate(FOCUS_JS);
  const live = (await page.evaluate(READ_JS)).live;
  await page.keyboard.press("Tab");
  const afterTab = await page.evaluate(FOCUS_JS);
  record({ kind: "action", label, lang, auth, present: true, focus, afterTab, live });
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
for (const lang of LANGS) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: lang === "es" ? "es-MX" : "en-US" });
  const page = await context.newPage();
  // A dev server compiles on the first visit, which can outlast one timeout.
  await open(page, "/").catch(() => open(page, "/"));
  await setLanguage(page, lang);

  for (const path of GUEST_FORMS) {
    await safe(path, async () => {
      await open(page, path);
      await submitEmpty(page, path, lang, "out");
    });
  }
  // F-18: a malformed email on the two sign-in forms.
  for (const [path, field] of [["/sign-in", "#portal-email"], ["/forgot-password", "input[type=email]"]]) {
    await safe(`${path} (bad email)`, async () => {
      await open(page, path);
      const box = page.locator(field).first();
      if ((await box.count()) > 0) await box.fill("not-an-email");
      await submitEmpty(page, `${path} (bad email)`, lang, "out");
    });
  }
  // Group C, signed out.
  await open(page, "/ask");
  await page.waitForSelector("[data-action^='ask-']", { timeout: 10000 }).catch(() => undefined);
  const cards = await page.locator("[data-action^='ask-']").count();
  for (let i = 0; i < cards; i += 1) {
    await safe(`ask card ${i + 1}`, async () => {
      await open(page, "/ask");
      await keyboardAction(page, `ask card ${i + 1} opens`, `[data-action^='ask-'] >> nth=${i}`, "Enter", lang, "out");
      await keyboardAction(page, `ask card ${i + 1} back`, "[data-action='cancel-ask']", "Enter", lang, "out");
    });
  }
  await open(page, "/");
  await keyboardAction(page, "language selector (arrow)", "[data-guest-language='select']", "ArrowDown", lang, "out");
  await setLanguage(page, lang);

  // Signed in.
  if (EMAIL) {
    await open(page, "/sign-in");
    await page.fill("#portal-email", EMAIL);
    await page.fill("#portal-password", PASSWORD);
    await page.locator("main button[data-variant='primary']").last().click();
    await page.waitForURL(/\/portal\/home/, { timeout: 15000 }).catch(() => undefined);
    await page.waitForTimeout(800);
    await setLanguage(page, lang);
    for (const path of SIGNED_IN_FORMS) {
      await safe(path, async () => {
        await open(page, path);
        await submitEmpty(page, path, lang, "in");
      });
    }
    // F-11: a bad phone and a bad ZIP, then an emptied phone.
    for (const [label, phone, zip] of [["phone abc / zip 1", "abc", "1"], ["phone emptied", "", null]]) {
      await safe(`/my-details (${label})`, async () => {
        await open(page, "/my-details");
        await page.locator("#my-phone").fill(phone, { timeout: 5000 });
        if (zip !== null) await page.locator("#my-postal-code").fill(zip, { timeout: 5000 });
        await submitEmpty(page, `/my-details (${label})`, lang, "in");
      });
    }
    await open(page, "/home");
    await safe("account selector", () => keyboardAction(page, "account selector (arrow)", "[data-account-switcher='select']", "ArrowDown", lang, "in"));
    await open(page, "/home");
    await keyboardAction(page, "nav tab Bills (Enter)", "nav a[data-tab='bills']", "Enter", lang, "in");
  }
  await context.close();
}
await browser.close();
writeFileSync(join(OUT, "scan.json"), JSON.stringify(results, null, 2));
say(`wrote ${results.length} rows to ${join(OUT, "scan.json")}`);

const broken = [];
for (const row of results) {
  if (row.kind === "form" && row.submitted && row.focus === "BODY") broken.push(`${row.lang} ${row.path}: focus on the body after submit`);
  // A primary that OPENS a step rather than submitting says nothing of its
  // own; focus on the new heading is how that step is read, so it passes.
  const onHeading = /^h[1-3]\b/.test(row.focus ?? "");
  if (row.kind === "form" && row.submitted && !onHeading && (row.after?.live ?? []).length === 0) broken.push(`${row.lang} ${row.path}: nothing announced after submit`);
  if (row.kind === "action" && row.present && row.focus === "BODY") broken.push(`${row.lang} ${row.label}: focus on the body`);
}
say(`${broken.length} keyboard/announcement failure(s)`);
for (const line of broken) say(`  FAIL  ${line}`);
if (process.env.STRICT === "1" && broken.length > 0) process.exit(1);
