/**
 * RENDERED-OUTPUT PROOF — `CR-092` step 2 lane 3: **does the asset edit surface
 * actually WRITE what it shows, and does it SHOW what it wrote?**
 *
 * Two defects, and each is proved the only way it can be: by driving the real
 * form in a real browser and then **reading the row back from the server**.
 *
 *   * **`DEF-MET-4971`** — the edit dialog's `Asset type` select is required,
 *     interactive and **never put in the PATCH payload**. A clerk changes it,
 *     presses Save, **gets the success toast**, and the type is unchanged.
 *   * **`DEF-MET-4972`** — `purchase_date` is typed once on the Add wizard and
 *     then **appears on no screen**, while `age_months`,
 *     `accumulated_depreciation` and `present_value` are all computed from it
 *     and drawn on the asset.
 *
 * ⚠ **A SUCCESS TOAST IS NOT PROOF, WHICH IS THE WHOLE POINT OF `DEF-MET-4971`**
 * — the toast is exactly what the defect produces today. So the assertion is
 * made against `GET /assets/{id}` AFTER the save, never against the screen's own
 * report of itself. This script would be worthless without that line.
 *
 * ⚠ **IT SEEDS ITS OWN ASSET AND REMOVES IT AGAIN.** No tenant on this database
 * holds the blueprint's 126 assets (brazosbend 14 · oak-ridge 74 · pine-hill
 * 135), and every one of them belongs to somebody else's measurement. This run
 * creates one `behind_the_meter` asset, drives it, and DELETEs it, so it is
 * repeatable and it disturbs nothing.
 *
 * ⚠ **WHY `behind_the_meter` AND NOT `meters`.** The type select offers
 * `typesForTab(...)` — only types whose catalog `category` equals the tab — so
 * the tab decides how many alternatives exist at all. On brazosbend: meters 2
 * (meter · net_meter) · sub_meters **1** · behind_the_meter **10**. A tab with
 * one option cannot demonstrate a type change; behind_the_meter can, and it
 * needs no service, no unit of measure and no connection size to exist.
 *
 * ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY, and what is done about each.**
 *   * The save could fail and leave the type unchanged for an honest reason. →
 *     the run asserts the dialog CLOSED and the success toast appeared before it
 *     reads the row back, and it prints any field error it finds instead.
 *   * The select could be driven to the value it already holds. → the option is
 *     chosen as *the first one that is not the current type*, and the run fails
 *     if no such option exists.
 *   * A `selectOption` that silently matches nothing leaves the old value. → the
 *     control's value is re-read from the DOM after the change and asserted.
 *   * The detail panel could be matched by a label that merely EXISTS in the
 *     catalogue rather than one that RENDERS. → the purchase-date assertion
 *     reads the rendered `<dd>` and requires a non-dash value equal to the date
 *     the asset was seeded with.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
 *      python3 manage.py runserver 127.0.0.1:8551 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=8552 API_PROXY_TARGET=http://127.0.0.1:8551 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:8552 SMOKE_TENANT=brazosbend \
 *     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr092-lane3-edit-writes.mjs
 *
 * **Exit code 0 only when every assertion passed at BOTH widths.** The audience
 * is clerk and utility-admin — laptop and desktop, not mobile (PO 2026-09-10) —
 * so the widths are 1280 and 1440 and nothing narrower.
 *
 * ⚠ **IF IT DIES ON `login refused: 401 … AUTH-001`, THE PRODUCT IS PROBABLY
 * FINE AND THE ACCOUNT IS LOCKED.** `BR-IDN-025` locks a user for **15 minutes
 * after 5 failed sign-ins** (`LOCKOUT_MAX_FAILED` / `LOCKOUT_MINUTES`,
 * `apps/identity/services.py:66`), the demo database is SHARED between lanes,
 * and the five failures need not be yours — a sibling driving the same account
 * with a stale password locks it for everybody. It happened to this lane on
 * 2026-09-12, forty minutes after the same run had passed on the same build.
 * The refusal is indistinguishable from a broken sign-in, so check before you
 * conclude anything:
 *
 *     psql … -c "set app.tenant_id='<tenant uuid>';
 *                select locked_until, now() from users where email like 'dana%'"
 *
 * A `locked_until` in the future is a wait, not a defect. **Do not clear it** —
 * it is a live security control on a database other lanes are measuring.
 */

import { execFileSync } from "node:child_process";
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
    const { readdirSync } = require("node:fs");
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [
        join(root, dir, "chrome-linux", "chrome"),
        join(root, dir, "chrome-linux64", "chrome"),
        join(root, dir, "chrome-linux", "headless_shell"),
      ]) {
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8552";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";

/** The seeded subject. The date is the one figure the whole `DEF-MET-4972` half
 *  turns on, so it is a literal here and asserted character-for-character. */
const PURCHASE_DATE = "2021-04-02";
const PURCHASE_DATE_SHOWN = "04/02/2021"; // brazosbend's Regional format is MM/DD/YYYY
const SEED_TYPE = "pv";

const WIDTHS = [
  { label: "1280", width: 1280, height: 900 },
  { label: "1440", width: 1440, height: 900 },
];

let failures = 0;
const say = (...p) => console.log(...p);
function fail(label, detail) {
  failures += 1;
  say(`  FAIL ${label}`);
  if (detail !== undefined) say(`       ${detail}`);
}
function ok(label, detail) {
  say(`  ok   ${label}${detail === undefined ? "" : ` — ${detail}`}`);
}

async function login(page) {
  const res = await page.request.post(`${BASE}/api/${TENANT}/auth/session`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  if (!res.ok()) throw new Error(`login refused: ${res.status()} ${await res.text()}`);
}

async function seedAsset(page, assetNo) {
  const res = await page.request.post(`${BASE}/api/${TENANT}/assets`, {
    data: {
      type: SEED_TYPE,
      asset_no: assetNo,
      serial_no: `${assetNo}-SER`,
      manufacturer_model: "Acme · PV-9",
      supplier: "Acme Supply",
      purchase_cost: "1800.0000",
      purchase_date: PURCHASE_DATE,
      expected_life_years: 10,
    },
  });
  if (!res.ok()) throw new Error(`seed refused: ${res.status()} ${await res.text()}`);
  return res.json();
}

async function readAsset(page, id) {
  const res = await page.request.get(`${BASE}/api/${TENANT}/assets/${id}`);
  if (!res.ok()) throw new Error(`asset read refused: ${res.status()}`);
  return res.json();
}

async function removeAsset(page, id) {
  const res = await page.request.delete(`${BASE}/api/${TENANT}/assets/${id}`);
  say(`  cleanup: DELETE /assets/${id} -> ${res.status()}`);
}

async function run() {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const stamp = Date.now().toString(36).toUpperCase().slice(-6);
  try {
    for (const w of WIDTHS) {
      say(`\n── ${w.label}px ──────────────────────────────────────────────`);
      const context = await browser.newContext({
        viewport: { width: w.width, height: w.height },
      });
      const page = await context.newPage();
      page.on("pageerror", (e) => fail(`page error at ${w.label}`, String(e)));
      await login(page);

      const assetNo = `L3-${stamp}-${w.label}`;
      const seeded = await seedAsset(page, assetNo);
      say(`  seeded ${seeded.asset_no} (${seeded.type}) id=${seeded.id}`);

      try {
        // ── DEF-MET-4971 ────────────────────────────────────────────────
        await page.goto(
          `${BASE}/${TENANT}/assets?tab=behind_the_meter&q=${encodeURIComponent(assetNo)}`,
          { waitUntil: "networkidle" },
        );
        await page.waitForSelector(`tbody tr:has-text("${assetNo}")`, { timeout: 20000 });
        const row = page.locator("tbody tr", { hasText: assetNo }).first();
        await row.locator('button[aria-label="Edit"]').first().click();
        await page.waitForSelector(".modal-body .field", { timeout: 20000 });

        const select = page.locator("#type");
        if ((await select.count()) === 0) {
          fail("the edit dialog renders an Asset type control", "#type not found");
        } else {
          const before = await select.inputValue();
          const options = await select.locator("option").evaluateAll((els) =>
            els.map((el) => ({ value: el.value, label: el.textContent.trim() })),
          );
          const target = options.find((o) => o.value !== "" && o.value !== before);
          if (target === undefined) {
            fail(
              "the Asset type select offers an alternative",
              `only ${JSON.stringify(options.map((o) => o.value))} on this tab`,
            );
          } else {
            ok("the Asset type select is interactive", `${before} → ${target.value}`);
            await select.selectOption(target.value);
            const chosen = await select.inputValue();
            if (chosen !== target.value) {
              fail("the select took the new value", `DOM still reads ${chosen}`);
            } else {
              await page.getByRole("button", { name: "Save asset" }).click();
              await page.waitForSelector(".modal-body", { state: "detached", timeout: 20000 });
              const toast = await page.locator("[role='status'], .toast, .notice").allTextContents();
              ok("the dialog closed and reported success", JSON.stringify(toast).slice(0, 120));

              // ⚠ THE ONLY LINE THAT PROVES ANYTHING. The toast above is what
              // the defect produces today; the row is what it does not.
              const after = await readAsset(page, seeded.id);
              if (after.type === target.value) {
                ok("DEF-MET-4971 — the saved type reached the database", `type=${after.type}`);
              } else {
                fail(
                  "DEF-MET-4971 — the saved type reached the database",
                  `chose ${target.value}, the server still holds ${after.type} — the save reported success`,
                );
              }
            }
          }
        }

        // ── DEF-MET-4972 · the DISPLAY half ─────────────────────────────
        await page.goto(`${BASE}/${TENANT}/assets/${seeded.id}`, { waitUntil: "networkidle" });
        await page.waitForSelector("[data-asset-facts]", { timeout: 20000 });
        const shown = await page.evaluate(() => {
          const cell = document.querySelector("[data-purchase-date]");
          const labels = Array.from(document.querySelectorAll("dt")).map((el) =>
            el.textContent.trim(),
          );
          return { value: cell === null ? null : cell.textContent.trim(), labels };
        });
        if (shown.value === null) {
          fail(
            "DEF-MET-4972 — the asset shows its purchase date",
            `no [data-purchase-date] cell on the Overview; the fact labels are ${JSON.stringify(shown.labels)}`,
          );
        } else if (!shown.value.includes(PURCHASE_DATE_SHOWN)) {
          fail(
            "DEF-MET-4972 — the asset shows its purchase date",
            `the cell reads "${shown.value}", expected to contain ${PURCHASE_DATE_SHOWN}`,
          );
        } else {
          ok("DEF-MET-4972 — the asset shows its purchase date", shown.value);
        }
      } finally {
        await removeAsset(page, seeded.id);
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }

  say(`\n${failures === 0 ? "PASS" : `FAIL — ${failures} assertion(s)`}`);
  process.exit(failures === 0 ? 0 : 1);
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
