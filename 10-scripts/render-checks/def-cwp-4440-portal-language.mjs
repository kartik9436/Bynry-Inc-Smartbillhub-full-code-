/**
 * RENDERED-OUTPUT CHECK — `DEF-CWP-4440`, the portal's language, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS AND WHY NO UNIT TEST REPLACES IT.** Hard-won law 6: no
 * gate in this repository looks at rendered output. The Product Owner's
 * standing definition of done is *"everything should be executed based on
 * actual code … also ensure you do web walkthorugh before you sign off"*, and
 * this defect is one only a browser settles, because the failure was **English
 * words on a screen that should not have been in English** — a state in which
 * every string resolves, every test passes and nothing is red anywhere.
 *
 * ⚠ **THE ASSERTIONS ARE TRANSLATED WORDS, NOT KEYS.** Asserting that a key
 * resolved proves i18next is wired to itself. What the PO reported is that the
 * SPANISH did not appear, so this reads the actual glass and compares it to the
 * catalogue's own Spanish and German — and it reads the SAME element twice,
 * before and after, because one reading cannot tell a served language from a
 * hardcoded string.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwp4440 --export --stale-ok)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3.12 06-backend/manage.py seed_portal_demo
 *   … runserver on $API_PORT, `vite build` + `node server.mjs` on $WEB_PORT …
 *   SMOKE_BASE=http://127.0.0.1:4440 SMOKE_TENANT=pine-hill \
 *     SMOKE_PORTAL_EMAIL=… SMOKE_PORTAL_PASSWORD=… \
 *     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/def-cwp-4440-portal-language.mjs
 *
 * ── WHAT IT CLICKS ────────────────────────────────────────────────────────
 *   1  Tenant language set to `es-MX`. A GUEST opens the portal front page and
 *      it is in Spanish — asserted on the words, not on a key.
 *   2  The top menu carries a real `<select>` that PAINTS (computed style —
 *      this theme clears Tailwind's stock palette, so a wrong class renders as
 *      nothing while `tsc` and every `toContain` pass), and its options are
 *      named in their own languages rather than as locale codes.
 *   2b **AND IT DID NOT CLIP THE ROW IT WAS PUT IN** — geometry, not text.
 *      The control worked perfectly and broke the header (`DEF-CWP-4468`),
 *      and no content assertion could see it: the words were in the DOM and
 *      simply cut in half on screen.
 *   3  Pick *Deutsch*. The SAME heading turns German, with no reload.
 *   4  Walk to another portal screen and back: still German — the choice
 *      survives navigation, which is the half `sessionStorage` is there for.
 *   5  **A SCREEN, on a FRESH LOAD, in a brand-new context** — the card, not
 *      the frame. This step is the only guard anywhere for the regression
 *      that shipped past nine unit tests on 2026-09-07: the applier was an
 *      earlier SIBLING of the routes, so `changeLanguage` fired before the
 *      screens attached their listeners and a first load drew a Spanish frame
 *      around an English card (*Inicio · Ayuda* over *Welcome back ·
 *      Password · Sign in*) with `i18n.language` reading `es-MX` throughout.
 *      Steps 1 and 3 cannot see it — they read the front page's `main`, which
 *      carries the utility's own strapline and service names, tenant-authored
 *      text that is identical in every language.
 *   6  Sign in as a customer whose account says `de` while the tenant says
 *      `es-MX`: the signed-in screens are GERMAN. That is the PO's *"Signed
 *      customer should get their own references"*, and it is the assertion
 *      that fails if the tenant default is allowed to win.
 *   7  Change that account to `it-IT` and sign in again: Italian. One reading
 *      proves a key exists; two different readings prove it is served.
 *   8  The customer's own language appears on the SESSION payload and nowhere
 *      in the anonymous guest payload (`BR-CWP-021`), asked on the wire.
 *
 * ⚠ **NOTHING HERE IS FOUND BY ITS LABEL.** Every control is located
 * structurally — the submit button is `[data-screen="CWP-015"] button`, not a
 * name regex — because its label is the setting under test. The first run of
 * this script timed out looking for *Sign in* on a page that said *Entrar*.
 *
 * ── RUN 2026-09-07 · 2.218.6 · PASS, 18 of 18 ────────────────────────────
 * Pine Hill Water & Power, Chromium, 1440×1000, a cloned seeded database.
 * The tenant set to `es-MX`: a guest's front page came up Spanish, and the top
 * menu's control measured `rgb(45, 43, 43)` with a 1px border at 15px — the
 * same ink as the nav words beside it. Its eleven options read *English ·
 * Español · Español de México · Deutsch · हिन्दी · Français (France) ·
 * Indonesia (Indonesia) · Italiano (Italia) · 日本語 (日本) · 한국어(대한민국) ·
 * Português (Brasil)* — every one in its own language and not one a locale
 * code. Picking *Deutsch* turned the page German and it was still German after
 * two navigations. A COLD load of the sign-in screen drew *O BIEN · Crea tu
 * acceso → · Pagar con número de recibo → · Solicitar servicio →*. With the
 * account set to `de` against the tenant's `es-MX`, the signed-in tabs read
 * **Übersicht · Rechnungen · Verbrauch · Zahlungen · Anliegen · Meine Daten**;
 * moved to `it-IT` the same tabs read **Home · Bollette · Consumi · Pagamenti
 * · Richieste · I miei dati**. `GET portal/session` carried `it-IT`, `GET
 * portal/public/front` carried `es-MX`, and `it-IT` appeared nowhere in the
 * anonymous body.
 *
 * ── RUN 2026-09-07 · 2.219.1 · PASS, 30 of 30 (`DEF-CWP-4442`) ───────────
 * The same stack, `pine-hill` on a fresh clone, after the offer was narrowed
 * from eleven to two. **Steps 2, 2c, 9 and 9b are new or rewritten; 1, 3, 4,
 * 5, 6, 7 and 8 are the run above, re-proved unchanged, which is the point:
 * narrowing what the portal OFFERS moved nothing about what it DRAWS.**
 *
 *   * A guest on a tenant set to `en` sees **exactly two — English · Español**.
 *   * A guest on a tenant set to `es-MX` sees **three — English · Español ·
 *     Español de México** — the reader's own language listed rather than
 *     dropped, on a case nobody ruled on and for which no rule was written.
 *   * A signed-in customer whose account says `de` sees **three, with
 *     Deutsch**, the control reads `de` and **is not blank**, and the screens
 *     around it are still **Übersicht · Rechnungen · Verbrauch · Zahlungen ·
 *     Anliegen · Meine Daten**.
 *   * That customer picks *Español* and, on reload, sees **two and Spanish
 *     selected** — German gone, one click, one way.
 *   * And the caption under their control reads **`3 Sprachen verfügbar.`**,
 *     which is the 30th check and the one this file gained because the FIRST
 *     run's screenshot showed it reading **`2`** under a list of three. Every
 *     option assertion passed over that; only the picture said otherwise.
 *   * `it-IT` on the account still draws **Home · Bollette · Consumi ·
 *     Pagamenti · Richieste · I miei dati**, and `GET portal/session` carries
 *     it while the anonymous front payload does not.
 *
 * ⚠ **AND ONE EXPECTATION MEASURED FALSE, RECORDED RATHER THAN QUIETLY
 * DROPPED.** It looked as though narrowing would also close `DEF-CWP-4468`,
 * the two-row header — the widest option was *Indonesia (Indonesia)*. The
 * control did shrink, **186px over three options → 105px over two**, and the
 * header is **still 1100×95 with the nav at 848×79: two rows** at 1440px in
 * English. That defect's own row already said why — the nav was at **853 of
 * about 860 available pixels BEFORE this control existed** — so it stays open
 * and step 2b asserts only what is true, that nothing is clipped.
 *
 * ⚠ **STEP 2b WAS ADDED AFTER THAT RUN AND IS RECORDED SEPARATELY RATHER THAN
 * FOLDED INTO IT.** The 18 above were measured before it existed; claiming 19
 * would be a number nothing produced. It was proved on the same production
 * bundle, red and green, and then run inside THIS script (against a stubbed
 * front payload, since the seeded template had drifted too far to provision
 * the tenant again): with the header's fixed `h-14` restored it printed
 * *⛔ … — CLIPPED: Inicio · Ayuda · Visítanos · Pagar un recibo · Reportar un
 * problema · Pídanos algo · Consultar · … · Iniciar sesión* over a 56px row,
 * and with the shipped `min-h-[3.5rem]` it prints *✓ no nav item escapes the
 * 83px header row*.
 *
 * ── AND IT WAS PROVED RED FIRST, WHICH IS THE HALF THAT MATTERS ───────────
 * With `useTranslation()` deleted from `PortalApp` and the bundle rebuilt,
 * **step 5 failed 2 of 2** and printed the evidence in one line: *i18n says
 * "es-MX"; the card's last lines read ["OR","Set up your login →","Pay with a
 * bill number →","Start service →"]*. **Steps 6, 7 and 8 stayed GREEN over
 * that same broken build**, and so did all nine cases in
 * `PortalLanguage.dom.test.tsx` — which is the measured basis for this file
 * claiming to be the only guard for that regression, rather than an assumed
 * one.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  // The path on disk wins over `executablePath()` — see the sign-out check's
  // own note: the library returns a build number this machine does not have
  // and does not throw, so the launch fails with a file-not-found nobody can
  // act on.
  try {
    const found = execFileSync("bash", [
      "-lc",
      "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
    ])
      .toString()
      .trim();
    if (found) return found;
  } catch {
    /* fall through */
  }
  return chromium.executablePath();
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4440";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const EMAIL = process.env.SMOKE_PORTAL_EMAIL ?? "m.alvarez@example.com";
const PASSWORD = process.env.SMOKE_PORTAL_PASSWORD ?? "Elm-Street-1408!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/def-cwp-4440";
const PORTAL = `${BASE}/${TENANT}/portal`;
/** A shell command that writes one language column, supplied by the runner. */
const SET_TENANT_LANG = process.env.SMOKE_SET_TENANT_LANG;
const SET_ACCOUNT_LANG = process.env.SMOKE_SET_ACCOUNT_LANG;

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}
function setLang(which, code) {
  const cmd = which === "tenant" ? SET_TENANT_LANG : SET_ACCOUNT_LANG;
  if (!cmd) throw new Error(`SMOKE_SET_${which.toUpperCase()}_LANG is not set`);
  execFileSync("bash", ["-lc", cmd.replace("{code}", code)], { stdio: "inherit" });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`def-cwp-4440: ${BASE} tenant=${TENANT}`);

  // ── 1 · a GUEST gets the utility's language ───────────────────────────
  console.log("\n── 1 · the utility set Spanish; a guest opens the portal ──");
  setLang("tenant", "es-MX");
  await page.goto(PORTAL, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-portal-frame="guest"]', { timeout: 20000 });
  const spanish = (await page.locator("main").innerText()).trim();
  console.log(`   front page reads: ${JSON.stringify(spanish.split("\n")[0])}`);
  check(/[áéíóúñ¿¡]/i.test(spanish) || /Bienvenid|factura|servicio|Pagar/i.test(spanish),
    "the guest front page is in SPANISH");
  await page.screenshot({ path: join(OUT, "1-guest-spanish.png"), fullPage: true });

  // ── 2 · the control the PO asked for ──────────────────────────────────
  console.log("\n── 2 · the language dropdown in the top menu ──");
  const picker = page.locator('[data-guest-language="select"]');
  check((await picker.count()) === 1, "the top menu carries exactly one language control");
  check((await picker.evaluate((el) => el.tagName)) === "SELECT", "it is a real <select> (B14 rule 8)");
  check(
    (await picker.evaluate((el) => el.closest("nav") !== null)),
    "it is in the nav — *on top menu*, which is where it was asked for",
  );
  const painted = await picker.evaluate((el) => {
    const s = getComputedStyle(el);
    return { color: s.color, fontSize: s.fontSize, border: s.borderTopWidth, bg: s.backgroundColor };
  });
  // Computed style, never a class string: this theme clears Tailwind's stock
  // palette, so a wrong class renders as nothing and every assertion passes.
  check(painted.color !== "" && painted.color !== "rgba(0, 0, 0, 0)",
    `it paints (colour ${painted.color}, border ${painted.border}, ${painted.fontSize})`);
  const options = await picker.locator("option").allInnerTexts();
  console.log(`   options: ${options.join(" · ")}`);
  // ⚠ **THIS ASSERTED ELEVEN UNTIL 2026-09-07** (`DEF-CWP-4442`). PO,
  // verbatim: *"currently in drop down show only 2 elnglish and spanish"*.
  //
  // ⚠ **AND IT IS THREE HERE RATHER THAN TWO, WHICH IS THE RULING WORKING
  // RATHER THAN FAILING.** This tenant is set to `es-MX` — a lawful setting
  // OUTSIDE the two — so the guest is READING Mexican Spanish, and a picker
  // listing two options over a third the reader is on renders BLANK. So it
  // lists the offer plus the reader's own, which is `BR-CWP-106` applied to a
  // case the Product Owner was never asked about: the same clause covers a
  // language that came from a tenant and one that came from an account.
  // Step 2c below is the plain two, on a tenant inside the offer.
  check(options.length === 3, `it offers the TWO plus this reader's own (${options.length})`);
  check(!options.some((o) => /^[a-z]{2}(-[A-Za-z]+)?$/.test(o.trim())),
    "no option is a locale code on screen (B14 rule 31)");
  check(options.some((o) => /^English$/.test(o.trim())) && options.some((o) => /^Espa\u00f1ol$/.test(o.trim())),
    "the two are English and Espa\u00f1ol, each in its own language (B14 rule 35)");
  // ⚠ **THE NINE THAT LEFT, NAMED — an ABSENCE is what this fix is, and an
  // absence is invisible to every check that only looks for what should be
  // there.** These were on this dropdown yesterday.
  check(!options.some((o) => /Deutsch|\u65e5\u672c\u8a9e|\ud55c\uad6d\uc5b4|Fran\u00e7ais|Portugu\u00eas|Italiano|Indonesia|\u0939\u093f\u0928\u094d\u0926\u0940/.test(o)),
    "and NONE of the nine the Product Owner removed is still offered");

  // ── 2c · the plain case: a tenant inside the offer sees exactly two ────
  console.log("\n── 2c · a tenant set to English: the dropdown is exactly two ──");
  setLang("tenant", "en");
  await page.goto(PORTAL, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-portal-frame="guest"]', { timeout: 20000 });
  const twoOnly = await page.locator('[data-guest-language="select"] option').allInnerTexts();
  console.log(`   options: ${twoOnly.join(" \u00b7 ")}`);
  check(twoOnly.length === 2 && /^English$/.test(twoOnly[0].trim()),
    `exactly two, English first (${twoOnly.length}: ${twoOnly.join(", ")})`);
  const english = (await page.locator("main").innerText()).trim();
  console.log(`   front page reads: ${JSON.stringify(english.split("\n")[0])}`);

  // ── 2b · AND IT DOES NOT CLIP THE ROW IT WAS PUT IN ───────────────────
  //
  // ⚠ **THE CONTROL WORKED PERFECTLY AND BROKE THE HEADER, AND ONLY A
  // SCREENSHOT SAID SO (`DEF-CWP-4468`).** The guest nav was already at
  // **853 of about 860 available pixels** in Spanish, inside a FIXED 56px
  // row, with *Pagar un recibo* and *Reportar un problema* wrapping to two
  // lines to fit. Adding this `<select>` took the nav to **886×70** and cut
  // both of those words in half on screen — in the customer's own language,
  // on the front page. **Every content assertion passed**: the words were in
  // the DOM exactly as expected; they were simply not visible.
  //
  // So this measures GEOMETRY rather than text: no nav item may escape the
  // header row it sits in. It is a cheap check and it is the only one in this
  // repository that can see a clipped control.
  console.log("\n── 2b · the control did not clip the row it was put in ──");
  const box = await page.evaluate(() => {
    const header = document.querySelector("header");
    const row = header.firstElementChild.getBoundingClientRect();
    const items = [...header.querySelector("nav").children].map((el) => {
      const r = el.getBoundingClientRect();
      return { text: (el.innerText || "").trim().slice(0, 24), top: Math.round(r.top), bottom: Math.round(r.bottom) };
    });
    const nav = header.querySelector("nav").getBoundingClientRect();
    return {
      top: Math.round(row.top), bottom: Math.round(row.bottom), height: Math.round(row.height),
      navWidth: Math.round(nav.width), navHeight: Math.round(nav.height),
      rowWidth: Math.round(row.width),
      items,
    };
  });
  const escaped = box.items.filter((i) => i.top < box.top || i.bottom > box.bottom);
  check(escaped.length === 0,
    `no nav item escapes the ${box.height}px header row` +
      (escaped.length ? ` — CLIPPED: ${escaped.map((i) => i.text).join(" · ")}` : ""));
  // ⚠ **`DEF-CWP-4468` IS STILL OPEN AND NARROWING THE OPTIONS DID NOT CLOSE
  // IT — MEASURED 2026-09-07, NOT ASSUMED.** It was reasonable to expect that
  // it would: the widest option was *Indonesia (Indonesia)* and the control
  // did shrink, from 186px over three options to **105px over two**. The
  // header is still **1100×95 with the nav at 848×79 — two rows** at 1440px
  // in English. The reason is in that defect's own row and this measurement
  // confirms it: the nav was at **853 of about 860 available pixels BEFORE
  // this control existed**, so it was going to break on whatever was added
  // next, and taking 80px off a control that is 105px wide does not give the
  // row back. Closing it is a COPY decision — shorten a nav word, or move an
  // errand out of the nav now all six are cards on the front page.
  //
  // So this prints the numbers and asserts only what is TRUE: nothing is
  // clipped. An assertion of one row would be a check that fails on a defect
  // this change never claimed to fix.
  console.log(`   header ${box.rowWidth}\u00d7${box.height}, nav ${box.navWidth}\u00d7${box.navHeight}` +
    ` — ${box.navHeight > 45 ? "TWO rows (DEF-CWP-4468, still open)" : "ONE row"}`);

  // ── 3 · picking one CHANGES THE PAGE ──────────────────────────────────
  //
  // ⚠ **THE PICK WAS *Deutsch* UNTIL 2026-09-07 AND HAD TO MOVE — NOT BECAUSE
  // THE BEHAVIOUR CHANGED BUT BECAUSE GERMAN IS NO LONGER OFFERED TO A READER
  // ON ENGLISH** (`DEF-CWP-4442`). Driving a `<select>` to a value with no
  // `<option>` behind it sets the control to "" and asserts nothing, which is
  // a walkthrough that tests the browser.
  console.log("\n── 3 · a guest picks Español ──");
  await page.locator('[data-guest-language="select"]').selectOption("es");
  await page.waitForTimeout(400);
  const picked = (await page.locator("main").innerText()).trim();
  console.log(`   front page now reads: ${JSON.stringify(picked.split("\n")[0])}`);
  check(picked !== english, "the same page is now different words — the control is not decorative");
  check(/[áéíóúñ¿¡]/i.test(picked) || /Bienvenid|factura|servicio|Pagar/i.test(picked),
    "and those words are SPANISH");
  await page.screenshot({ path: join(OUT, "2-guest-picked-spanish.png"), fullPage: true });

  // ── 4 · it survives a navigation ──────────────────────────────────────
  console.log("\n── 4 · walk away and come back ──");
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  await page.goto(PORTAL, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-portal-frame="guest"]', { timeout: 20000 });
  const stillPicked = (await page.locator("main").innerText()).trim();
  check(stillPicked === picked, "still Spanish after two navigations — the choice is kept for the tab");
  check(
    (await page.locator('[data-guest-language="select"]').inputValue()) === "es",
    "and the control still shows Español rather than resetting",
  );

  // ── 5 · A SCREEN, ON A FRESH LOAD, NOT JUST THE FRAME ─────────────────
  //
  // ⚠ **THIS STEP IS THE ONLY GUARD IN THE REPOSITORY FOR THE REGRESSION THAT
  // SHIPPED PAST NINE UNIT TESTS ON 2026-09-07, AND IT IS WHY THIS FILE
  // EXISTS.** The applier was mounted as an earlier SIBLING of the routes, so
  // `changeLanguage` fired before the screens attached their own
  // `languageChanged` listeners — and a fresh load drew a Spanish FRAME around
  // an English CARD: *Inicio · Ayuda* over *Welcome back · Password · Sign
  // in*, with `i18n.language` reading `es-MX` the whole time. Every unit test
  // passed, because they all ask the instance what language it is in and it
  // was telling the truth.
  //
  // So this reads the CARD, in a brand-new context, on a FIRST load. Steps 1
  // and 3 above cannot see it: they read `main` on the front page, which
  // carries the utility's own strapline and service names — tenant-authored
  // text that is the same in every language — so they pass over a card that
  // never switched.
  console.log("\n── 5 · a SCREEN on a fresh load, not just the frame ──");
  setLang("tenant", "es-MX");
  const cold = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const coldPage = await cold.newPage();
  await coldPage.goto(`${PORTAL}/sign-in`, { waitUntil: "domcontentloaded" });
  await coldPage.waitForSelector('[data-screen="CWP-015"]', { timeout: 20000 });
  await coldPage.waitForTimeout(2000);
  const cardWords = (await coldPage.locator("main").innerText()).trim();
  const appliedLang = await coldPage.evaluate(() => window.__SMARTBILLHUB_I18N__?.language);
  console.log(`   i18n says "${appliedLang}"; the card's last lines read: ` +
    JSON.stringify(cardWords.split("\n").filter(Boolean).slice(-4)));
  check(appliedLang === "es-MX", `the instance is in Spanish (${appliedLang})`);
  // ⚠ THE ENGLISH WORDS ARE NAMED, because their ABSENCE is the whole check —
  // these are exactly what the card drew while the frame was Spanish.
  check(!/\bSign in\b|\bWelcome back\b|\bPassword\b|\bOR\b/.test(cardWords),
    "and the CARD is not still in English — the words the regression left behind are gone");
  check(/Entrar|Contraseña|O BIEN|Crea tu acceso|verte de nuevo/i.test(cardWords),
    "the card is drawn in Spanish on a FIRST load, with no navigation to fix it");
  await coldPage.screenshot({ path: join(OUT, "5-cold-load-screen.png"), fullPage: true });
  await cold.close();

  // ── 6 · a SIGNED-IN customer gets THEIR OWN language ──────────────────
  console.log("\n── 6 · the account says German, the utility says Spanish ──");
  setLang("account", "de");
  const fresh = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const inPage = await fresh.newPage();
  await inPage.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await inPage.waitForSelector('[data-screen="CWP-015"]', { timeout: 20000 });
  await inPage.fill("#portal-email", EMAIL);
  await inPage.fill("#portal-password", PASSWORD);
  // ⚠ **THE SUBMIT CONTROL IS FOUND STRUCTURALLY, NEVER BY ITS LABEL.** Its
  // label is `portal.signIn.commit`, which is *Sign in* · *Entrar* ·
  // *Anmelden* depending on the very setting under test — a `getByRole` name
  // regex here is a walkthrough that only works in the language it was written
  // in, and it timed out on *Entrar* the first time this ran.
  await inPage.locator('[data-screen="CWP-015"] button').last().click();
  await inPage.waitForURL(/\/portal\/home/, { timeout: 20000 });
  await inPage.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
  const signedIn = (await inPage.locator("body").innerText()).trim();
  console.log(`   signed-in tabs read: ${JSON.stringify((await inPage.locator("nav").first().innerText()).replace(/\n/g, " · "))}`);
  check(/[äöüß]/i.test(signedIn) || /Rechnung|Zahlung|Verbrauch|Startseite/i.test(signedIn),
    "the signed-in portal is GERMAN — the account beat the utility's Spanish");
  await inPage.screenshot({ path: join(OUT, "3-signed-in-german.png"), fullPage: true });

  // ── 7 · change the account and it follows ─────────────────────────────
  console.log("\n── 7 · change that account to Italian ──");
  setLang("account", "it-IT");
  const second = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const itPage = await second.newPage();
  await itPage.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await itPage.fill("#portal-email", EMAIL);
  await itPage.fill("#portal-password", PASSWORD);
  await itPage.locator('[data-screen="CWP-015"] button').last().click();
  await itPage.waitForURL(/\/portal\/home/, { timeout: 20000 });
  await itPage.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
  const italian = (await itPage.locator("nav").first().innerText()).replace(/\n/g, " · ");
  console.log(`   signed-in tabs now read: ${JSON.stringify(italian)}`);
  check(/Bollett|Pagament|Consum|Home|Richiest/i.test(italian),
    "the same screens are now ITALIAN — the value is served, not hardcoded");
  await itPage.screenshot({ path: join(OUT, "4-signed-in-italian.png"), fullPage: true });

  // ── 8 · and it is on the SIGNED-IN door only (BR-CWP-021) ─────────────
  console.log("\n── 8 · which payload carries it ──");
  const wire = await itPage.evaluate(async (tenant) => {
    const session = await fetch(`/api/${tenant}/portal/session`, { credentials: "include" });
    const front = await fetch(`/api/${tenant}/portal/public/front`);
    return { session: await session.json(), front: await front.json() };
  }, TENANT);
  check(wire.session.language === "it-IT", `the session payload carries the customer's own language (${wire.session.language})`);
  check(wire.front.regional.language === "es-MX", `the front payload carries the UTILITY's (${wire.front.regional.language})`);
  check(!JSON.stringify(wire.front).includes("it-IT"),
    "the customer's own language appears NOWHERE in the anonymous guest payload");

  // ── 9 · THE OTHER PICKER — a signed-in customer on a language the portal
  //        no longer offers (DEF-CWP-4442) ─────────────────────────────────
  //
  // ⚠ **THE TWO CONTROLS MUST AGREE, AND ONLY A BROWSER CAN SAY THEY DO.**
  // Steps 1–4 read the GUEST dropdown; this reads `CWP-024`'s, the one that
  // WRITES `accounts.preferred_language`. Two controls for one setting
  // offering different lists is how a product tells one person two things.
  //
  // ⚠ **AND IT IS THE BLANK-SELECT CASE ON THE SCREEN THE DEFECT WAS FILED
  // AGAINST.** This account says German, German is not offered, and a
  // `<select>` whose value is not among its options renders EMPTY — with no
  // error, `tsc` green, and every unit assertion passing, because the failure
  // is an absence. So this reads the control's VALUE off the glass, not only
  // its options.
  console.log("\n── 9 · the signed-in customer's own picker, on German ──");
  setLang("account", "de");
  const third = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const dePage = await third.newPage();
  await dePage.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await dePage.fill("#portal-email", EMAIL);
  await dePage.fill("#portal-password", PASSWORD);
  await dePage.locator('[data-screen="CWP-015"] button').last().click();
  await dePage.waitForURL(/\/portal\/home/, { timeout: 20000 });
  await dePage.goto(`${PORTAL}/my-details/preferences`, { waitUntil: "networkidle" });
  await dePage.waitForSelector("#preferences-locale", { timeout: 20000 });
  await dePage.waitForTimeout(600);
  const own = await dePage.locator("#preferences-locale option").allInnerTexts();
  const ownValue = await dePage.locator("#preferences-locale").inputValue();
  console.log(`   options: ${own.join(" \u00b7 ")} — selected ${JSON.stringify(ownValue)}`);
  check(own.length === 3, `it lists the two plus this customer's own German (${own.length})`);
  check(own.some((o) => /^Deutsch$/.test(o.trim())),
    "German is listed, named in its own language rather than silently dropped");
  // ⚠ THE ASSERTION THAT FAILS ON A BLANK CONTROL. `""` is what a `<select>`
  // reports when its value matches no option, and it reads like a customer
  // who simply has not chosen — which is the opposite of true here.
  check(ownValue === "de", `and the control is NOT blank — it shows German (${JSON.stringify(ownValue)})`);
  // ⚠ **THE CAPTION UNDER THE CONTROL, AND A SCREENSHOT IS THE ONLY REASON
  // THIS ASSERTION EXISTS.** The first run of this step passed every check
  // above and the picture showed *2 Sprachen verf\u00fcgbar.* printed under a
  // list of THREE — the helper was counting the server's OFFER while the
  // control drew the offer PLUS this reader's own. Every option assertion was
  // true; the sentence beside them was not. Nothing but a human looking at a
  // rendered page could have seen it (hard-won law 6).
  const caption = (await dePage.locator('[data-screen="CWP-025"], main').first().innerText()).trim();
  check(/\b3\b/.test(caption.split("\n").find((l) => /verf\u00fcgbar|available|disponible/i.test(l)) ?? ""),
    `the caption counts the list it sits under (${JSON.stringify(
      caption.split("\n").find((l) => /verf\u00fcgbar|available|disponible/i.test(l)) ?? "not found")})`);
  const frameWords = (await dePage.locator("body").innerText()).trim();
  check(/[\u00e4\u00f6\u00fc\u00df]/i.test(frameWords) || /Rechnung|Zahlung|Verbrauch|Startseite|Sprache/i.test(frameWords),
    "and they are still READING German — narrowing the offer did not move the resolution");
  await dePage.screenshot({ path: join(OUT, "9-signed-in-german-picker.png"), fullPage: true });

  // ── 9b · choosing away is ONE CLICK AND ONE WAY ───────────────────────
  console.log("\n── 9b · they choose Español, and German stops being offered ──");
  await dePage.selectOption("#preferences-locale", "es");
  await dePage.waitForTimeout(1500);
  await dePage.reload({ waitUntil: "networkidle" });
  await dePage.waitForSelector("#preferences-locale", { timeout: 20000 });
  await dePage.waitForTimeout(600);
  const after = await dePage.locator("#preferences-locale option").allInnerTexts();
  const afterValue = await dePage.locator("#preferences-locale").inputValue();
  console.log(`   options: ${after.join(" \u00b7 ")} — selected ${JSON.stringify(afterValue)}`);
  check(after.length === 2 && afterValue === "es",
    `two options and Spanish selected (${after.length}: ${after.join(", ")} / ${afterValue})`);
  check(!after.some((o) => /^Deutsch$/.test(o.trim())),
    "German is gone — the third option is derived from what they HOLD, not remembered");
  await dePage.screenshot({ path: join(OUT, "9b-moved-to-spanish.png"), fullPage: true });

  console.log(`\n${failures.length === 0 ? "PASS" : `FAIL — ${failures.length}`}: screenshots in ${OUT}`);
  await browser.close();
  process.exit(failures.length === 0 ? 0 : 1);
})().catch((err) => {
  console.error(err);
  process.exit(2);
});
