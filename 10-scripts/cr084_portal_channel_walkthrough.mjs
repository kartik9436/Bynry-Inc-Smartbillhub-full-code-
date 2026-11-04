// ── Trace ──────────────────────────────────────────────
// Change:  CR-084 — the customer portal becomes a notification channel. PO
//          2026-09-07, pointing at the greyed-out row: *"can you swithc on this
//          now - Customer portal"*.
// Defect:  DEF-NOT-4531 — the template catalogue said 23 of its 38 templates
//          had no wording, over wording it was displaying underneath.
// Screens: S8 (Settings → Notifications → a rule) · SET-09/SET-10 (Settings →
//          Configure → Templates and one template)
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//          running app) · law 7 (a check's output must distinguish pass from
//          fail to a READER, and a declared blind spot needs a NUMBER) ·
//          law 2's mirror (a refusal that rots when the thing it refuses
//          arrives) · B14 rule 32
// ───────────────────────────────────────────────────────
/**
 * cr084_portal_channel_walkthrough — open the two screens the Product Owner
 * opened, and read what they now say.
 *
 *     # a stack on ports of your own (a port answering 200 is not proof YOUR
 *     # server bound it — check the boot lines in the logs)
 *     cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
 *       python3.12 manage.py runserver 127.0.0.1:8341 --noreload
 *     cd 07-frontend && ./node_modules/.bin/vite build \
 *       && PORT=8342 API_PROXY_TARGET=http://127.0.0.1:8341 node server.mjs
 *     OUT=/tmp/cr084 node 10-scripts/cr084_portal_channel_walkthrough.mjs
 *
 * ⚠ **REBUILD `dist/` BEFORE YOU WALK.** `server.mjs` serves whatever was on
 * disk when a request arrives and never says the bundle is stale.
 *
 * WHAT IT ASKS, AND WHY EACH ONE NEEDS A BROWSER
 * ---------------------------------------------
 *  · **The Customer portal row is a TOGGLE and not a sentence.** The DOM suite
 *    can assert a row exists; only a browser can say whether that row carries a
 *    working checkbox or a greyed-out paragraph, and the whole of the Product
 *    Owner's instruction is the difference between those two.
 *  · **Its refusal is GONE, not merely overridden.** A change that added the
 *    toggle and left the old row in `unavailable_channels` would draw the
 *    channel twice — once switchable, once refusing — and every server test
 *    would pass on it.
 *  · **The refusal that IS still true is still drawn.** `mail` on the
 *    disconnect notice is a real vendor gap. A walk that only checked the
 *    portal had gone would pass just as happily over a screen that had lost
 *    every refusal it has.
 *  · **The templates list no longer says its own wording is missing.** The
 *    Product Owner read that sentence off a screen that was showing the
 *    wording. This counts the rows carrying it, so the answer is a NUMBER —
 *    *"0 of 38"* — rather than a pass nobody can check.
 *  · **The one template they opened says something true.** `email_bill_ready`,
 *    by name, with its old sentence quoted in the failure.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8342";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr084-shots";
const VIEWPORT = { width: 1440, height: 1000 };

//: The sentence the Product Owner found, in the two places it lived. Quoted so
//: a failure prints what a person would read rather than a selector.
const DEAD_REFUSAL = "there is no customer portal in this product";
const DEAD_WORDING_CLAIM = "no wording has been written for it";

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
  throw new Error("no chromium found");
}

const findings = [];
const notes = [];
function say(line) {
  notes.push(line);
  console.log(line);
}
function bad(line) {
  findings.push(line);
  console.error("  ✗ " + line);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: VIEWPORT });

  // The payload the SCREEN used, captured off the wire — never a second request
  // with different headers, which is a different question with a similar answer.
  let ruleWire = null;
  let catalogWire = null;
  page.on("response", async (r) => {
    const url = r.url();
    if (r.request().method() !== "GET" || r.status() !== 200) return;
    try {
      if (/\/notification-rules\/bill_ready/.test(url)) ruleWire = (await r.json()).data ?? (await r.json());
      // ⚠ `/template-catalog`, NOT `/notification-templates`. The first draft
      // matched the S8 card's read and reported *"templates served: 0"* — which
      // the walk then correctly called a finding rather than a pass, because a
      // number was printed beside it (law 7). SET-09 is `/template-catalog`.
      else if (/\/template-catalog(\?|$)/.test(url)) catalogWire = await r.json();
    } catch {
      /* not JSON — the SPA fallback */
    }
  });

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  say("signed in");

  // ── 1 · THE ROW THE PRODUCT OWNER POINTED AT ──────────────────────────
  await page.goto(`${BASE}/${TENANT}/settings/notifications/bill_ready`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('[data-testid="channel-test-email"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "01-bill-ready-channels.png"), fullPage: true });

  const portalToggle = page.locator('[data-testid="channel-test-portal"]');
  const portalRefusal = page.locator('[data-testid="channel-unavailable-portal"]');
  const portalRefusalCount = await portalRefusal.count();
  const portalRows = await page.locator('tr:has-text("Customer portal")').count();
  say(`rows mentioning "Customer portal": ${portalRows}`);

  if (portalRefusalCount > 0) {
    const text = (await portalRefusal.first().innerText()).replace(/\s+/g, " ").trim();
    bad(`Customer portal is STILL drawn as a refusal: "${text}"`);
  } else {
    say("Customer portal is no longer in the refused rows");
  }
  if ((await portalToggle.count()) === 0) {
    bad(
      "Customer portal has no channel row on Bill ready — the toggle the Product Owner " +
        'asked for ("can you swithc on this now - Customer portal") is not drawn',
    );
  } else {
    // A row is not a switch. Read the CHECKBOX, and read whether it is on.
    const box = page.locator('input[type="checkbox"]').nth(0);
    const state = await page.evaluate(() => {
      const row = [...document.querySelectorAll("tr")].find((tr) =>
        (tr.textContent ?? "").includes("Customer portal"),
      );
      if (row === undefined) return null;
      const input = row.querySelector('input[type="checkbox"]');
      return input === null
        ? { hasCheckbox: false }
        : { hasCheckbox: true, checked: input.checked, disabled: input.disabled };
    });
    say(`Customer portal row: ${JSON.stringify(state)}`);
    if (state === null || state.hasCheckbox !== true) {
      bad("the Customer portal row carries no checkbox — it is drawn but not switchable");
    } else if (state.disabled === true) {
      bad("the Customer portal checkbox is DISABLED — the switch is drawn and cannot be used");
    }
    void box;
  }
  // ⚠ **THE SWITCH MUST GO BOTH WAYS.** A channel with no template class was
  // locked off by the enable-checkbox's own guard — turn it off and it greys
  // out — which would have made this a one-way switch and the mirror of the
  // defect this change fixes. Only a browser can ask this.
  const portalCell = (
    await page.evaluate(() => {
      const row = [...document.querySelectorAll("tr")].find((tr) =>
        (tr.textContent ?? "").includes("Customer portal"),
      );
      return row === undefined ? null : (row.textContent ?? "").replace(/\s+/g, " ").trim();
    })
  );
  say(`Customer portal row reads: "${portalCell}"`);
  if (portalCell !== null && /no template for this channel yet/i.test(portalCell)) {
    bad(
      'the Customer portal row still says "No template for this channel yet" — the word ' +
        '"yet" promises wording that is not coming on a channel that publishes the document',
    );
  }
  await page.evaluate(() => {
    const row = [...document.querySelectorAll("tr")].find((tr) =>
      (tr.textContent ?? "").includes("Customer portal"),
    );
    const input = row?.querySelector('input[type="checkbox"]');
    if (input !== null && input !== undefined) input.click();
  });
  const afterOff = await page.evaluate(() => {
    const row = [...document.querySelectorAll("tr")].find((tr) =>
      (tr.textContent ?? "").includes("Customer portal"),
    );
    const input = row?.querySelector('input[type="checkbox"]');
    return input === null || input === undefined
      ? null
      : { checked: input.checked, disabled: input.disabled };
  });
  say(`after switching Customer portal off: ${JSON.stringify(afterOff)}`);
  if (afterOff !== null && afterOff.disabled === true) {
    bad(
      "switching Customer portal OFF greys its own checkbox out — the switch is one-way " +
        "and nobody can turn it back on",
    );
  }

  if (portalRows > 1) {
    bad(
      `Customer portal appears on ${portalRows} rows — a toggle AND a leftover refusal is ` +
        "the channel drawn twice, which every server test passes over",
    );
  }

  const bodyText = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  if (bodyText.includes(DEAD_REFUSAL)) {
    bad(`the dead refusal is still on this screen: "${DEAD_REFUSAL}"`);
  } else {
    say(`the dead refusal is gone: "${DEAD_REFUSAL}" appears 0 times`);
  }
  say(
    `served channel_rules: ${JSON.stringify(
      (ruleWire?.channel_rules ?? []).map((r) => [r.channel, r.enabled]),
    )}`,
  );
  say(
    `served unavailable_channels: ${JSON.stringify(
      (ruleWire?.unavailable_channels ?? []).map((r) => r.channel),
    )}`,
  );

  // ── 2 · THE REFUSAL THAT IS STILL TRUE MUST STILL BE DRAWN ────────────
  // Without this, a screen that had lost EVERY refusal would pass part 1.
  await page.goto(`${BASE}/${TENANT}/settings/notifications/disconnect_notice`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('[data-testid="channel-unavailable-mail"]', { timeout: 20000 });
  const mailText = (await page.locator('[data-testid="channel-unavailable-mail"]').innerText())
    .replace(/\s+/g, " ")
    .trim();
  say(`the disconnect notice still refuses "Mail": ${mailText.slice(0, 90)}…`);
  await page.screenshot({ path: join(OUT, "02-disconnect-still-refuses-mail.png"), fullPage: true });

  // ── 3 · THE TEMPLATE LIST STOPS CALLING ITSELF EMPTY ──────────────────
  await page.goto(`${BASE}/${TENANT}/settings/reference-data/templates`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('[data-testid="template-catalog"], table', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "03-template-catalog.png"), fullPage: true });

  const rows = catalogWire?.results ?? catalogWire?.data?.results ?? [];
  const claiming = rows.filter((r) => (r.used_by ?? "").toLowerCase().includes(DEAD_WORDING_CLAIM));
  // ⚠ A NUMBER, NOT A VERDICT (law 7). "0 of 38" and a silent pass read the
  // same way in a log, and only one of them proves the sweep looked at
  // anything.
  say(`templates served: ${rows.length}; rows still claiming no wording: ${claiming.length}`);
  if (rows.length === 0) {
    bad("the catalogue served no rows at all, so nothing here was measured");
  }
  if (claiming.length > 0) {
    bad(
      `${claiming.length} of ${rows.length} templates still say "${DEAD_WORDING_CLAIM}": ` +
        claiming.map((r) => r.code).join(", "),
    );
  }
  const stateless = rows.filter((r) => r.used_by_state === undefined || r.used_by_state === null);
  if (stateless.length > 0) {
    bad(
      `${stateless.length} of ${rows.length} rows carry no derived used_by_state, so the ` +
        "status pill beside them is still being guessed from the prose",
    );
  } else {
    say(`every one of the ${rows.length} rows carries a served used_by_state`);
  }

  // ── 4 · THE ONE TEMPLATE THEY OPENED ──────────────────────────────────
  await page.goto(
    `${BASE}/${TENANT}/settings/reference-data/templates?template=email_bill_ready`,
    { waitUntil: "networkidle" },
  );
  await page.waitForSelector('[data-testid="template-detail-page"]', { timeout: 20000 });
  await page.waitForSelector('[data-testid="head-meta"]', { timeout: 20000 });
  const meta = (await page.locator('[data-testid="head-meta"]').innerText())
    .replace(/\s+/g, " ")
    .trim();
  say(`Bill ready · e-bill email header now reads: "${meta}"`);
  await page.screenshot({ path: join(OUT, "04-bill-ready-email-template.png"), fullPage: true });
  if (meta.toLowerCase().includes(DEAD_WORDING_CLAIM)) {
    bad(
      "the template the Product Owner opened STILL says no wording has been written for " +
        "it, on a page that is displaying the wording",
    );
  }
  // The wording really is on the page — otherwise the sentence above was true
  // and this whole defect was a misreading.
  const hasBody = (await page.locator('[data-testid="preview-page"], [data-testid="preview-bubble"]').count()) > 0;
  if (!hasBody) {
    bad("no rendered wording on this template page — the old sentence may have been right");
  } else {
    say("the wording is rendered on the page, which is what made the old sentence false");
  }

  writeFileSync(
    join(OUT, "walkthrough.txt"),
    [...notes, "", ...(findings.length ? ["FINDINGS:", ...findings] : ["no findings"])].join("\n"),
  );
  await browser.close();

  console.log("");
  if (findings.length > 0) {
    console.error(`${findings.length} finding(s) — see ${OUT}/walkthrough.txt`);
    process.exit(1);
  }
  console.log(`clean — screenshots and the transcript are in ${OUT}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
