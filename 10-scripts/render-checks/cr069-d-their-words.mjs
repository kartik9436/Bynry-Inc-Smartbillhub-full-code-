/**
 * RENDERED-OUTPUT CHECK — CR-069 wave D, *their words for our things*, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. A story is not signed off until this
 * has run green against a running product, on the wireframe pack's frames
 * (45.1 the mapping editor · 81.2 how they say a customer paid), not r10.
 *
 * ⚠ **AND IT READS A COLOUR, ON PURPOSE (DEF-INT-3621).** This product's
 * Tailwind theme declares its own palette (`--color-*: initial`), so a stock
 * `border-red-600` is a class no stylesheet declares: it is in the DOM, every
 * `toContain` assertion passes on it, and it renders NOTHING. Wave A's grid
 * shipped twelve such tokens and its walkthrough read only display and
 * padding, which are structural utilities that do compile. So step 4 below
 * reads `border-top-color` on an unmapped row as computed style and requires
 * the theme's danger red — the one check that goes red when a token is fake.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   createdb sbh_cr069d
 *   DATABASE_URL=…/sbh_cr069d python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/sbh_cr069d python3 06-backend/manage.py seed_demo
 *   # the story's fixture (US-INT-037 §4): the utility's own tender *Bank transfer*
 *   DATABASE_URL=…/sbh_cr069d python3 06-backend/manage.py shell -c "
 *     from apps.tenancy.models import Tenant, PaymentMethod
 *     from core.tenancy import tenant_context
 *     t = Tenant.objects.get(subdomain='brazosbend')
 *     with tenant_context(t.id):
 *         PaymentMethod.objects.update_or_create(tenant=t, code='bank_transfer',
 *             defaults={'name': 'Bank transfer', 'active': True})"
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr069d" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8074 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4274 API_PROXY_TARGET=http://127.0.0.1:8074 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4274 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-d-their-words.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** It WRITES two
 * mapping rows (and clears them first), so a shared database would carry a
 * stranger's mappings afterwards.
 *
 * ── WHAT IT ASSERTS (demo script D, clicked) ──────────────────────────────
 *   1  Settings → Integrations: the kiosk card carries the one link to S143,
 *      and a card whose manifest ships no words carries none (law 2: wired).
 *   2  S143 for the Payment kiosk: **fourteen rows, every one red, unmapped
 *      first**; the sentence reads *14 of 14 not mapped.* (BR-INT-031).
 *   3  No database id, rule number or internal reference reaches the clerk
 *      (B14 rules 31 and 32); the row action is an icon with a name (rule 15).
 *   4  **The theme's red actually painted** — computed border colour.
 *   5  *Map it* on `ACHCHECK` → *Bank transfer* → Save; the same for
 *      `ACHSAVINGS` → **both green, one of ours shared by two of theirs**, and
 *      the sentence reads *12 of 14 not mapped.* (BR-INT-032).
 *   6  Mapping `ACHCHECK` a second way **in the same request is refused** —
 *      one of their words means exactly one of ours (BR-INT-032; TC-2's UNIQUE
 *      is proved on PostgreSQL by tests/test_us_int_037_pg.py).
 *   7  The bank file's mappings: *Bounced payments*, `R02`'s action disabled
 *      with *Waiting for a decision* (OQ-INT-1487 — shown, never chosen).
 *   8  The served grid: the accounting file registers **four** codecs and the
 *      mailbox **none** — the format picker's rule as data (BR-INT-033). The
 *      picker itself is the manifest's `file_format` select, drawn by S141's
 *      field slot when wave B lands it.
 *   9  No sideways scroll at 1440; screenshots of every step.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4274";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-d-their-words";
const VIEWPORT = { width: 1440, height: 1000 };
const KIOSK = "payments_kiosk";
const BANK = "bank_lockbox_file";

/** `--color-danger-500: #e0341a` in src/styles/tailwind.css, as a browser reports it. */
const DANGER_RED = "rgb(224, 52, 26)";

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
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

async function mapWord(page, word, ourWord) {
  const row = page.locator(`[data-mapping-row="${word}"]`);
  await row.getByRole("button", { name: "Map it" }).click();
  await row.locator("select").selectOption({ label: ourWord });
  await row.getByRole("button", { name: "Save" }).click();
  await page.waitForFunction(
    (w) => document.querySelector(`[data-mapping-row="${w}"]`)?.getAttribute("data-state") === "mapped",
    word,
    { timeout: 10000 },
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  let servedGrid = null;
  page.on("response", async (response) => {
    if (!/\/integrations(?:\?|$)/.test(response.url())) return;
    try {
      servedGrid = JSON.parse(await response.text());
    } catch {
      // not JSON
    }
  });

  console.log(`cr069-d: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // A clean slate: the run writes two rows, so it clears the kiosk's first.
  const api = (path) => `${BASE}/api/${TENANT}${path}`;
  const reset = await page.request.put(api(`/integrations/${KIOSK}/mappings`), {
    data: {
      rows: [
        { entity_type: "tender", external_value: "ACHCHECK", local_value: null },
        { entity_type: "tender", external_value: "ACHSAVINGS", local_value: null },
      ],
    },
  });
  check(reset.status() === 200, `the run starts from unmapped rows (PUT reset → ${reset.status()})`);

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · Settings → Integrations — the card's link
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 1 · Settings → Integrations ──");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForSelector(`[data-provider="${KIOSK}"]`, { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "1-grid-with-mappings-link.png"), fullPage: true });
  check(
    (await page.locator(`[data-mappings-link="${KIOSK}"]`).count()) === 1,
    "the Payment kiosk card carries the Mappings link",
  );
  check(
    (await page.locator(`[data-mappings-link="email_smtp"]`).count()) === 0,
    "the Custom SMTP card, whose manifest ships no words, carries none",
  );

  // 8 · the format picker's rule, as the server serves it
  if (servedGrid !== null) {
    const byKey = Object.fromEntries(servedGrid.providers.map((one) => [one.key, one]));
    check(
      byKey.accounting_file.codecs.length === 4,
      `the accounting file registers four codecs (${byKey.accounting_file.codecs.join(" · ")}) — a picker`,
    );
    check(
      byKey.email_smtp.codecs.length === 0,
      "Custom SMTP registers no choice of codec — no picker (BR-INT-033)",
    );
    check(
      byKey[KIOSK].vocabularies.length === 1 && byKey[KIOSK].vocabularies[0].count === 14,
      "the kiosk's manifest ships fourteen words to map",
    );
  } else {
    check(false, "GET /integrations was never observed");
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · S143 for the Payment kiosk — fourteen red rows
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 2 · S143 · Payment kiosk · How they pay ──");
  await page.click(`[data-mappings-link="${KIOSK}"]`);
  await page.waitForSelector("[data-mapping-row]", { timeout: 20000 });
  check(
    page.url().endsWith(`/settings/integrations/${KIOSK}/mappings`),
    `S143 has a URL of its own (${new URL(page.url()).pathname})`,
  );
  await page.screenshot({ path: join(OUT, "2-fourteen-red-rows.png"), fullPage: true });

  const rows = page.locator("[data-mapping-row]");
  const states = await rows.evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-state")));
  check(states.length === 14, `fourteen rows drawn (${states.length})`);
  check(states.every((s) => s === "unmapped"), "every row reads unmapped — red — before anyone has mapped");
  const status = await page.locator("[data-unmapped]").innerText();
  check(status.includes("14 of 14 not mapped."), `the sentence: "${status.trim().split("\n")[0]}"`);
  check(
    (await page.getByRole("button", { name: "Map it" }).count()) === 14,
    "fourteen icon actions, each named Map it (rule 15)",
  );

  // 3 · nothing internal reaches the clerk
  const text = await page.evaluate(() => document.body.innerText);
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = text.match(pattern);
    check(hit === null, `no ${pattern} in clerk copy${hit ? ` — found ${hit[0]}` : ""}`);
  }

  // 4 · the theme's red actually painted (DEF-INT-3621)
  const painted = await rows.first().evaluate((el) => {
    const s = getComputedStyle(el);
    return { border: s.borderTopColor, display: s.display, padding: s.paddingTop };
  });
  check(
    painted.border === DANGER_RED,
    `an unmapped row's border is the theme's danger red (${painted.border})`,
  );
  check(painted.display === "flex" && painted.padding !== "0px", "the row's layout utilities compiled");

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · two of theirs → one of ours
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 5 · ACHCHECK and ACHSAVINGS both → Bank transfer ──");
  await mapWord(page, "ACHCHECK", "Bank transfer");
  await page.screenshot({ path: join(OUT, "5a-achcheck-mapped.png"), fullPage: true });
  await mapWord(page, "ACHSAVINGS", "Bank transfer");
  await page.screenshot({ path: join(OUT, "5b-both-mapped.png"), fullPage: true });

  const after = await rows.evaluateAll((nodes) =>
    nodes.map((n) => ({
      word: n.getAttribute("data-mapping-row"),
      state: n.getAttribute("data-state"),
      ours: n.querySelector("[data-our-word]")?.textContent ?? "",
    })),
  );
  const mapped = after.filter((r) => r.state === "mapped");
  check(mapped.length === 2, `two rows are mapped (${mapped.length})`);
  check(
    mapped.every((r) => r.ours === "Bank transfer"),
    "both read Bank transfer — one of ours shared by two of theirs (BR-INT-032)",
  );
  check(
    after.slice(0, 12).every((r) => r.state === "unmapped") &&
      after.slice(12).map((r) => r.word).join(",") === "ACHCHECK,ACHSAVINGS",
    "unmapped first, then their word — the twelve red rows lead",
  );
  const status2 = await page.locator("[data-unmapped]").innerText();
  check(status2.includes("12 of 14 not mapped."), `the sentence now: "${status2.trim().split("\n")[0]}"`);
  const greenRow = page.locator('[data-mapping-row="ACHCHECK"]');
  const greenBorder = await greenRow.evaluate((el) => getComputedStyle(el).borderTopColor);
  check(greenBorder !== DANGER_RED, `a mapped row is no longer red (${greenBorder})`);
  check(
    (await greenRow.getByRole("button", { name: "Change" }).count()) === 1,
    "a mapped row's action reads Change",
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · a second meaning for one of their words is refused
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 6 · ACHCHECK a second way — refused ──");
  const refused = await page.request.put(api(`/integrations/${KIOSK}/mappings`), {
    data: {
      rows: [
        { entity_type: "tender", external_value: "ACHCHECK", local_value: "bank_transfer" },
        { entity_type: "tender", external_value: "ACHCHECK", local_value: "cash" },
      ],
    },
  });
  const body = await refused.json().catch(() => ({}));
  check(
    refused.status() === 422 && body.message_key === "integrations.refusal.mapping_twice",
    `refused by name: ${refused.status()} ${body.message_key ?? "(no key)"} — one of their words means exactly one of ours`,
  );
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector('[data-mapping-row="ACHCHECK"][data-state="mapped"]', { timeout: 20000 });
  const still = await page
    .locator('[data-mapping-row="ACHCHECK"] [data-our-word]')
    .textContent();
  check(still === "Bank transfer", `after the refusal ACHCHECK still means ${still}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · the bank file — R02 is shown and never chosen
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 7 · S143 · Bank & lockbox file · Bounced payments ──");
  await page.goto(`${BASE}/${TENANT}/settings/integrations/${BANK}/mappings`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('[data-mapping-row="R02"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "7-bank-bounced-payments.png"), fullPage: true });
  const r02 = page.locator('[data-mapping-row="R02"]').getByRole("button", { name: "Map it" });
  check(await r02.isDisabled(), "R02's action is disabled — the writer will not choose for it");
  check(
    (await r02.getAttribute("title")) === "Waiting for a decision",
    `…and says why in the tooltip: "${await r02.getAttribute("title")}"`,
  );
  const r01 = page.locator('[data-mapping-row="R01"]').getByRole("button", { name: "Map it" });
  check(!(await r01.isDisabled()), "R01's action is live");
  const bankText = await page.evaluate(() => document.body.innerText);
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = bankText.match(pattern);
    check(hit === null, `no ${pattern} on the bank's mappings${hit ? ` — found ${hit[0]}` : ""}`);
  }

  // 9 · no sideways scroll
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${sideways}px)`);

  await browser.close();

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr069 wave D: their words, mapped on one screen — two of theirs, one of ours");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
