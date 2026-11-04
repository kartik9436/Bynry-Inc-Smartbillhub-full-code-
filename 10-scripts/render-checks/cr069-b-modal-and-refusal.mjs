/**
 * RENDERED-OUTPUT CHECK — CR-069 wave B, the modal and the refusal, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*, and for CR-069 the visual authority
 * is the wireframe pack (`04-docs/05-modules/13-integrations/wireframes/`),
 * frames 25.1 · 49.2 · 50.1 · 55.2 for the screens this clicks. A story is not
 * signed off until this has run green against a running product.
 *
 * ⚠ **AND IT READS COMPUTED STYLE, BECAUSE THE RULE-21 TRAP BIT WAVE A.** The
 * app's Tailwind theme clears the default palette, so `text-slate-500` and
 * `text-lg` compile to NOTHING while `tsc`, vitest and the DOM all look fine.
 * Wave A's walkthrough checked `display` and `padding` — both real — and the
 * card colours never rendered (DEF-INT-3580). This one reads the colour of a
 * state word and the border style of the field slot in a real engine.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   createdb sbh_cr069b
 *   DATABASE_URL=…/sbh_cr069b python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/sbh_cr069b python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr069b" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8072 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4272 API_PROXY_TARGET=http://127.0.0.1:8072 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4272 \
 *   SMOKE_DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr069b" \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-b-modal-and-refusal.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — it reads row counts
 * back through `psql` before and after every refused write, and a mid-run
 * reseed looks exactly like a leak.
 *
 * ── WHAT IT ASSERTS (demo script B, clicked) ──────────────────────────────
 *   1  *Connect · Custom SMTP* — FIVE typed fields from the manifest (mail
 *      server, port, username, password, send-from), environment, cadence,
 *      *Save and test*, and the footer sentence (frame 25.1).
 *   2  Filling them in and pressing *Save and test* shows the SERVER'S refusal
 *      in six words or fewer with *Nothing was saved.* beside it (the adapter
 *      arrives with wave E) — and `integration_connection` and
 *      `integration_credential` hold exactly as many rows as before.
 *   3  *Connect · Microsoft 365* — ONE typed field, a *Sign in with Microsoft*
 *      button, and **no password input anywhere in the DOM** (frame 49.2).
 *   4  *Connect · Payment kiosk network* — the key WE issue and the allowlist,
 *      and the words *bearer* and *token* nowhere (frame 50.1, C2).
 *   5  The Card processor card reads *Coming soon · W7* and its Connect is
 *      dashed and `aria-disabled`; pressing it opens nothing (frame 55.2).
 *   6  `POST /integrations/payments_card/connect` from the API with a
 *      real-looking key → 409, the catalogue sentence ≤ 6 words, row counts
 *      unchanged, and the key absent from the audit trail (US-INT-017 TC-1/6).
 *   7  `docker compose config` lists `celery-integrations` on `-Q integrations`
 *      and the default worker stays `-Q celery` (US-INT-016 TC-2).
 *   8  The utilities compiled — a state word's colour is the theme's, the field
 *      slot's border is SOLID and its legend is not monospace — read as
 *      computed style. B14 rule 36: nothing dashed, monospaced or labelled like
 *      a diagram ships to a utility user.
 *   9  No sideways scroll at 1440; no rule id, question id or UUID in clerk copy.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [join(root, dir, "chrome-linux", "chrome"), join(root, dir)]) {
        try {
          execFileSync(candidate, ["--version"], { stdio: "ignore" });
          return candidate;
        } catch {
          // keep looking
        }
      }
    }
    return wanted;
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4272";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const DATABASE_URL = process.env.SMOKE_DATABASE_URL ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-b-modal";
const VIEWPORT = { width: 1440, height: 1000 };
const LOOKS_LIKE_A_KEY = "sk_live_51H8f2kL0pQz9xW3vT6yU1sR4";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** Row counts read back through psql — the database's own answer, not the API's. */
function rowCounts() {
  if (!DATABASE_URL) return null;
  const sql =
    "SELECT (SELECT count(*) FROM integration_connection) || ' ' || (SELECT count(*) FROM integration_credential)";
  const out = execFileSync("psql", [DATABASE_URL, "-tA", "-c", sql], { encoding: "utf8" }).trim();
  const [connections, credentials] = out.split(" ").map(Number);
  return { connections, credentials };
}

function auditCarries(text) {
  if (!DATABASE_URL) return null;
  const sql = `SELECT count(*) FROM audit_log WHERE (COALESCE(after::text,'') || COALESCE(before::text,'')) LIKE '%${text}%'`;
  return Number(execFileSync("psql", [DATABASE_URL, "-tA", "-c", sql], { encoding: "utf8" }).trim());
}

function auditRefusals() {
  if (!DATABASE_URL) return null;
  const sql = "SELECT count(*) FROM audit_log WHERE action = 'integration.connect_refused'";
  return Number(execFileSync("psql", [DATABASE_URL, "-tA", "-c", sql], { encoding: "utf8" }).trim());
}

const en = JSON.parse(readFileSync(join(process.cwd(), "07-frontend/src/i18n/locales/en.json"), "utf8"));

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`cr069-b: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-provider]", { timeout: 20000 });
  const before = rowCounts();
  if (before) console.log(`   rows before: ${JSON.stringify(before)}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · Connect · Custom SMTP — five fields from the manifest (frame 25.1)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 1 · Connect · Custom SMTP ──");
  await page.click('[data-provider="email_smtp"] [data-card-action="connect"]');
  await page.waitForSelector('[data-connect-modal="email_smtp"]');
  await page.screenshot({ path: join(OUT, "01-connect-custom-smtp.png"), fullPage: true });
  const smtpInputs = await page.$$eval('[data-connect-modal="email_smtp"] [data-field-slot] input', (nodes) =>
    nodes.map((n) => n.getAttribute("name")),
  );
  check(
    JSON.stringify(smtpInputs) === JSON.stringify(["host", "port", "username", "password", "send_from"]),
    `five typed fields from the manifest: ${smtpInputs.join(", ")}`,
  );
  check(
    (await page.$eval('[data-connect-modal="email_smtp"] input[name="password"]', (n) => n.type)) === "password",
    "the password field is a password input",
  );
  check((await page.$('[data-segmented="environment"]')) !== null, "an Environment control (Production | Sandbox)");
  check((await page.$('[data-segmented="cadence"]')) !== null, "a How often control (Nightly | Hourly | Manual)");
  const footer = await page.$eval("[data-footer-sentence]", (n) => n.textContent?.trim());
  check(footer === en["integrations.modal.testing_sends_one"], `the footer sentence: "${footer}"`);
  check((await page.$('[data-connect-modal="email_smtp"] button[type="submit"]')) !== null, "a Save and test button");

  // 8 (part) · computed style — the field slot's border compiled, and it is
  // SOLID.
  //
  // ⚠ **THIS CHECK USED TO ASSERT `dashed`, AND IT WAS POINTED AT A DEFECT**
  // (`DEF-INT-3721`, B14 rule 36 breach (a), PO 2026-09-04). The modal drew four
  // production panels as `border-dashed border-info-700` boxes with `font-mono
  // uppercase tracking-wider` legends — a customer-facing form that looked like
  // a sketch of itself — and the ONE check in this repository that looks at
  // real pixels reported it green, in the words *"the field slot's border is
  // dashed in a real engine"*. Nothing dashed, monospaced or labelled like a
  // diagram ships to a utility user, so the assertion is turned around: the
  // computed border must be SOLID, and the font must not be monospace. `G86`
  // refuses the source-text form; this refuses the rendered one.
  const slot = await page.$eval("[data-field-slot]", (el) => {
    const s = getComputedStyle(el);
    const legend = el.querySelector("legend");
    return {
      border: s.borderTopStyle,
      colour: s.borderTopColor,
      legendFont: legend === null ? "" : getComputedStyle(legend).fontFamily,
    };
  });
  check(slot.border === "solid", `the field slot's border is SOLID in a real engine (${slot.border}, ${slot.colour})`);
  check(
    !/mono/i.test(slot.legendFont),
    `the field slot's legend is not typewriter type (${slot.legendFont.slice(0, 40)})`,
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · Save and test → the server's refusal, and nothing saved
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 2 · Save and test on a live card whose adapter has not arrived ──");
  await page.fill('input[name="host"]', "smtp.brazosbend.example");
  await page.fill('input[name="port"]', "587");
  await page.fill('input[name="username"]', "billing@brazosbend.example");
  await page.fill('input[name="password"]', "Ew3!kQ9-lockbox");
  await page.fill('input[name="send_from"]', "billing@brazosbend.example");
  await page.fill("[data-test-recipient]", "alex@brazosbend.example");
  await page.click('[data-connect-modal="email_smtp"] button[type="submit"]');
  await page.waitForSelector("[data-refusal]", { timeout: 10000 });
  await page.screenshot({ path: join(OUT, "02-save-and-test-refused.png"), fullPage: true });
  const refusal = await page.$eval("[data-refusal]", (n) => n.textContent?.trim() ?? "");
  const [sentence] = refusal.split(" · ");
  check(sentence.split(/\s+/).length <= 6, `the refusal is six words or fewer: "${sentence}"`);
  check(refusal.endsWith(en["integrations.modal.nothingSaved"]), `…and says nothing was saved: "${refusal}"`);
  const afterSmtp = rowCounts();
  if (before && afterSmtp) {
    check(
      afterSmtp.connections === before.connections && afterSmtp.credentials === before.credentials,
      `row counts unchanged after the refused connect (${JSON.stringify(afterSmtp)})`,
    );
    check(auditCarries("Ew3!kQ9-lockbox") === 0, "the typed password reached no audit row");
  }
  await page.click('[data-connect-modal="email_smtp"] button[type="button"]:has-text("Cancel")');
  await page.waitForSelector('[data-connect-modal="email_smtp"]', { state: "detached" });

  // ═════════════════════════════════════════════════════════════════════════
  // 3 · Connect · Microsoft 365 — no password input in the DOM (frame 49.2)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 3 · Connect · Microsoft 365 ──");
  await page.click('[data-provider="email_microsoft"] [data-card-action="connect"]');
  await page.waitForSelector('[data-connect-modal="email_microsoft"]');
  await page.screenshot({ path: join(OUT, "03-connect-microsoft-365.png"), fullPage: true });
  const msInputs = await page.$$eval('[data-connect-modal="email_microsoft"] [data-field-slot] input', (nodes) =>
    nodes.map((n) => n.getAttribute("name")),
  );
  check(JSON.stringify(msInputs) === JSON.stringify(["send_from"]), `one typed field: ${msInputs.join(", ")}`);
  check((await page.$('input[type="password"]')) === null, "no password input exists anywhere in the DOM");
  check((await page.$("[data-oauth-start]")) !== null, "a Sign in with Microsoft button");
  const msFooter = await page.$eval("[data-footer-sentence]", (n) => n.textContent?.trim());
  check(msFooter === en["integrations.modal.roundTrip"], `the footer: "${msFooter}" — there is no Save`);
  check((await page.$('[data-connect-modal="email_microsoft"] button[type="submit"]')) === null, "and indeed no submit button");
  await page.click('[data-connect-modal="email_microsoft"] button:has-text("Cancel")');
  await page.waitForSelector('[data-connect-modal="email_microsoft"]', { state: "detached" });

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · Connect · Payment kiosk — a key we issue, nothing about bearer tokens
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 4 · Connect · Payment kiosk network ──");
  await page.click('[data-provider="payments_kiosk"] [data-card-action="connect"]');
  await page.waitForSelector('[data-connect-modal="payments_kiosk"]');
  await page.screenshot({ path: join(OUT, "04-connect-payment-kiosk.png"), fullPage: true });
  const kioskText = (await page.$eval('[data-connect-modal="payments_kiosk"]', (n) => n.textContent ?? "")).toLowerCase();
  check((await page.$("[data-issued-key-panel]")) !== null, "the key WE issue, in its own panel");
  check((await page.$('input[name="allowed_addresses"]')) !== null, "the allowed-addresses field");
  check(!kioskText.includes("bearer") && !kioskText.includes("token"), "nothing about bearer tokens");
  await page.click('[data-connect-modal="payments_kiosk"] button:has-text("Cancel")');
  await page.waitForSelector('[data-connect-modal="payments_kiosk"]', { state: "detached" });

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · The Card processor card — Coming soon · W7, DISABLED, takes no press
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 5 · the Card processor card ──");
  const cardText = await page.$eval('[data-provider="payments_card"]', (n) => n.textContent ?? "");
  check(cardText.includes("Coming soon") && cardText.includes("W7"), "reads Coming soon · W7");
  // ⚠ `dashed` HERE WAS THE SAME DEFECT ONE SCREEN OVER (`DEF-INT-3721`).
  // `BR-INT-001`'s own words are *"Connect disabled at UI AND API"* — the rule
  // never said dashed, only the file's header did, and a hatched rectangle on a
  // card is a wireframe hatching on a customer's screen. It is the kit's
  // `Button`, disabled, and the refusal that matters is still the server's.
  const soon = await page.$eval('[data-provider="payments_card"] [data-coming-soon-connect]', (el) => ({
    aria: el.getAttribute("aria-disabled"),
    disabled: el.hasAttribute("disabled"),
    border: getComputedStyle(el).borderTopStyle,
    variant: el.getAttribute("data-variant"),
  }));
  check(
    soon.aria === "true" && soon.disabled && soon.border !== "dashed" && soon.variant !== null,
    `its Connect is the kit's Button, disabled, not hatched (${soon.variant}, ${soon.border})`,
  );
  // Playwright refuses to click an `aria-disabled` control on its own — which
  // is the point of the control — so the press is dispatched as the DOM event.
  await page.dispatchEvent('[data-provider="payments_card"] [data-coming-soon-connect]', "click");
  await page.waitForTimeout(300);
  check((await page.$("[data-connect-modal]")) === null, "pressing it opens nothing");
  await page.screenshot({ path: join(OUT, "05-card-processor-coming-soon.png") });

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · The API is asked anyway — refused in six words, database unchanged
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 6 · POST /integrations/payments_card/connect with a real-looking key ──");
  const refusalsBefore = auditRefusals();
  const response = await page.request.post(`${BASE}/api/${TENANT}/integrations/payments_card/connect`, {
    data: {
      environment: "production",
      cadence: "manual",
      fields: { merchant_id: "acct_1H8f2kL0", merchant_secret: LOOKS_LIKE_A_KEY, client_id: "sbh-web" },
    },
  });
  const body = await response.json();
  check(response.status() === 409, `refused with 409 (got ${response.status()})`);
  check(body.message_key === "integrations.refusal.not_available", `message key ${body.message_key}`);
  const catalogue = en[body.message_key] ?? "";
  check(catalogue.split(/\s+/).length <= 6, `the catalogue sentence is ≤ 6 words: "${catalogue}"`);
  check(!/BR-|OQ-/.test(catalogue), "and names no rule");
  const afterCard = rowCounts();
  if (before && afterCard) {
    check(
      afterCard.connections === before.connections && afterCard.credentials === before.credentials,
      `row counts unchanged (${JSON.stringify(afterCard)})`,
    );
    check(auditCarries(LOOKS_LIKE_A_KEY) === 0, "the key reached no audit row");
    check(auditRefusals() === refusalsBefore + 1, "one integration.connect_refused audit row was written");
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · docker compose config — the worker on its own queue (US-INT-016)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 7 · docker compose config ──");
  try {
    const config = execFileSync("docker", ["compose", "-f", "docker-compose.yml", "config", "--no-interpolate"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    check(/celery-integrations:/.test(config), "celery-integrations is a service");
    check(/-Q\s*\n?\s*-?\s*integrations/.test(config.replace(/\n\s+-\s+/g, " ")), "on -Q integrations");
  } catch {
    // The compose CLI cannot read the file without an env file; read the YAML instead.
    const raw = readFileSync(join(process.cwd(), "docker-compose.yml"), "utf8");
    const block = raw.slice(raw.indexOf("  celery-integrations:"), raw.indexOf("  celery-beat:"));
    check(block.includes('"-Q", "integrations"'), "celery-integrations consumes -Q integrations (read from the YAML)");
    const defaultWorker = raw.slice(raw.indexOf("  celery:\n"), raw.indexOf("  celery-billing:"));
    check(defaultWorker.includes('"-Q", "celery"'), "the default worker stays on -Q celery");
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 8 · computed style — a state word's colour is the theme's (rule 21)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 8 · the utilities compiled ──");
  const word = await page.$eval('[data-provider="email_smtp"] [data-state]', (el) => getComputedStyle(el).color);
  const bodyColour = await page.$eval("body", (el) => getComputedStyle(el).color);
  check(word !== bodyColour && word !== "rgb(0, 0, 0)", `a state word carries a theme colour (${word}, body ${bodyColour})`);

  // ═════════════════════════════════════════════════════════════════════════
  // 9 · no sideways scroll, nothing internal in clerk copy
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 9 · clerk copy ──");
  const text = await page.evaluate(() => document.body.innerText);
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = text.match(pattern);
    check(hit === null, `no ${pattern} in clerk copy${hit ? ` — found ${hit[0]}` : ""}`);
  }
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${sideways}px)`);

  await browser.close();
  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr069 wave B: the modal opens for every card, and the server refuses what the button cannot");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
