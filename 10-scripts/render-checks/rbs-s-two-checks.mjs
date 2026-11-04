/**
 * RENDERED-OUTPUT CHECK — CR-075 wave S. Runbooks 12 and 16 in a browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ⚠ **THE THINGS THAT MATTER MOST HERE ARE THE ONES THAT SAY *NO*, AND A
 * BACKEND TEST CANNOT TELL YOU WHETHER THEY READ AS DESIGNED ANSWERS OR AS
 * FAILURES.**
 *   · **Runbook 12's moratorium tile must say *Not checked* and NEVER the
 *     card's green `No`.** Nothing in this product holds a forecast
 *     (`OQ-RBS-1757`), and *we looked at the weather and it is fine* and
 *     *nobody looked* send a crew to opposite places.
 *   · **Runbook 12's commit is the DANGER tier, is DISABLED, and approves a
 *     LIST.** `US-RBS-024` `TC-3`: no disconnection is performed by the
 *     product, and there is no port that could.
 *   · **Runbook 16's revenue tile must carry a BASIS and it must read
 *     *priced*.** Nothing it draws was posted, cleared or even issued
 *     (`DEF-RBS-4350`), and the block's fallback is `posting`.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3.12 10-scripts/render-checks/rbs_s_fixture.py --tenant brazosbend
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3.12 10-scripts/render-checks/rbs_s_seed_checks.py --tenant brazosbend
 *   … which prints the two RUN_IDs, in order: disconnect, then preview.
 *
 *   SMOKE_BASE=http://127.0.0.1:4291 SMOKE_DISCONNECT_RUN_ID=… \
 *   SMOKE_PREVIEW_RUN_ID=… PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-s-two-checks.mjs
 */
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// ⚠ **ESM RESOLVES FROM THE FILE, NOT THE WORKING DIRECTORY**, so a bare
// `import … from "playwright"` in `10-scripts/` cannot see
// `07-frontend/node_modules` however you `cd`. `12-smoke-walkthrough.mjs`
// solves it this way and this copies it rather than inventing a second answer.
const requireFrontend = createRequire(
  new URL("../../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  const dir = readdirSync(root).find((one) => /^chromium-\d+$/.test(one));
  if (!dir) throw new Error(`no chromium under ${root} — never run playwright install`);
  return join(root, dir, "chrome-linux", "chrome");
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4291";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const DISCONNECT = process.env.SMOKE_DISCONNECT_RUN_ID ?? "";
const PREVIEW = process.env.SMOKE_PREVIEW_RUN_ID ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-s-two-checks";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\b(?:OQ|DEF|TC|US|EP|GT)-(?:[A-Z]{3}-)?\d{2,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** A stored four- or six-place figure that reached a sentence.
 *
 * ⚠ **IT IS TESTED PER LEAF ELEMENT AND NEVER OVER `body.textContent`, AND THE
 * FIRST DRAFT OF THIS CHECK FAILED WRONGLY BECAUSE OF IT.** `textContent`
 * concatenates sibling cells with NO separator, so a correct `$368.40` beside a
 * correct `09/04/2026` reads as `$368.4009/04/2026` and matches, and a correct
 * `$527.77` beside `11.2%` reads as `$527.7711.2%`. Both screens were right and
 * the check was wrong — hard-won law 7's *what would make this check fail
 * wrongly*, which is the same question asked from the other end. Reading each
 * leaf's own text is what a person sees. */
const OVER_PRECISE_MONEY = /\$\s?\d[\d,]*\.\d{3,}/;

if (DISCONNECT === "" || PREVIEW === "") {
  console.error(
    "⛔ both run ids must be set. This check reads STORED runs — it cannot start one.\n" +
      "   Seed them with rbs_s_fixture.py then rbs_s_seed_checks.py; see the header.",
  );
  process.exit(2);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answer, captured rather than inferred — *did the screen
  // draw it* and *did the server send it* are two questions (`DEF-RBS-4284`).
  let wire = [];
  page.on("response", async (response) => {
    if (!/\/runbooks\//.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });

  console.log("── sign in ───────────────────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  async function open(key, runId, shot) {
    wire = [];
    await page.goto(`${BASE}/${TENANT}/runbooks/${key}/runs/${runId}`, {
      waitUntil: "networkidle",
    });
    // ⚠ `networkidle` IS NOT ENOUGH — the page fetches through `useQuery`, so
    // the first navigation can return with the LOADING SKELETON on screen and a
    // broken WAIT then reads as a broken SCREEN. Wait for the skeleton to GO.
    await page
      .waitForFunction(() => document.querySelector(".skeleton") === null, { timeout: 20000 })
      .catch(() => {});
    await page.screenshot({ path: join(OUT, shot), fullPage: true });
    const report = wire.find((w) => /\/report\b/.test(w.url))?.body ?? "";
    return {
      body: (await page.textContent("body")) ?? "",
      served: report === "" ? null : JSON.parse(report),
    };
  }

  const sideways = () =>
    page.evaluate(
      () =>
        Math.max(
          0,
          document.documentElement.scrollWidth - document.documentElement.clientWidth,
        ),
    );

  // ── RUNBOOK 12 ─────────────────────────────────────────────────────────
  console.log("── runbook 12 · disconnect eligibility ───────────────────");
  const dis = await open("disconnect_eligibility", DISCONNECT, "rbs-s-disconnect.png");
  check(dis.served !== null, "the server served a report for the disconnect run");
  check(/eligible/i.test(dis.body), "the page says how many are eligible");
  check(/removed/i.test(dis.body), "the page says how many were removed");

  // ⚠ THE ONE THAT MATTERS — `OQ-RBS-1757`.
  check(
    /Not checked/.test(dis.body),
    "the moratorium tile reads 'Not checked' (OQ-RBS-1757 — no forecast exists)",
  );
  check(
    !/\bMoratorium\b[\s\S]{0,80}\bNo\b/.test(dis.body),
    "…and never the card's green 'No', which would read as 'we checked the weather'",
  );
  check(
    /No forecast for the service area/.test(dis.body),
    "…and it says WHY, beside the tile rather than in a tooltip",
  );

  const approve = page.locator("button", { hasText: "Approve field list" }).first();
  check((await approve.count()) > 0, "the commit is on screen: 'Approve field list'");
  if ((await approve.count()) > 0) {
    check(await approve.isDisabled(), "…and it is DISABLED (run approval is wave L)");
    // B14 draws a control a user may not use WITH its reason, never hidden.
    const around = (await page.textContent("body")) ?? "";
    check(
      /not built yet/i.test(around),
      "…with its reason on the page (B14: disabled WITH the reason, never hidden)",
    );
    // ⚠ READ FROM COMPUTED STYLE, never from a class name: B14 rule 21's
    // migration clause means an unlisted file's utility renders as NOTHING at
    // all while the class still sits in the DOM.
    const tone = await approve.evaluate((el) => {
      const s = getComputedStyle(el);
      return { bg: s.backgroundColor, color: s.color, border: s.borderColor };
    });
    console.log(`     approve button computed: ${JSON.stringify(tone)}`);
  }
  check(
    !/disconnect(ed|ing)?\s+\d/i.test(dis.body),
    "nothing on the page claims an account was disconnected",
  );
  check((await sideways()) === 0, "the page does not scroll sideways");

  // ── RUNBOOK 16 ─────────────────────────────────────────────────────────
  console.log("── runbook 16 · rate change preview ──────────────────────");
  const prev = await open("rate_change_preview", PREVIEW, "rbs-s-preview.png");
  check(prev.served !== null, "the server served a report for the preview run");

  const tiles =
    prev.served?.find?.((one) => one.block === "kpis")?.payload?.tiles ??
    prev.served?.blocks?.find?.((one) => one.block === "kpis")?.payload?.tiles ??
    [];
  const revenue = tiles.find((one) => one.id === "revenue");
  check(revenue !== undefined, "the server sent a revenue tile");
  check(revenue?.basis === "priced", "…and its basis is 'priced', never 'posting'");
  if (revenue) {
    const shown = Number(revenue.value.amount ?? "0").toFixed(2);
    check(
      prev.body.includes(shown),
      `…and the screen draws the server's own figure (${shown})`,
    );
  }
  check(/Revenue/.test(prev.body), "the revenue tile is on screen");
  check(/How bills move/.test(prev.body), "the distribution is drawn, five rows");
  check(/Biggest movers|Under draft/.test(prev.body), "the movers table is drawn");
  check(/By account type/.test(prev.body), "the by-type breakdown is drawn");
  check((await sideways()) === 0, "the preview does not scroll sideways");

  // ── BOTH PAGES ─────────────────────────────────────────────────────────
  console.log("── both pages ────────────────────────────────────────────");
  for (const [name, runId, key] of [
    ["disconnect", DISCONNECT, "disconnect_eligibility"],
    ["preview", PREVIEW, "rate_change_preview"],
  ]) {
    await page.goto(`${BASE}/${TENANT}/runbooks/${key}/runs/${runId}`, {
      waitUntil: "networkidle",
    });
    await page
      .waitForFunction(() => document.querySelector(".skeleton") === null, { timeout: 20000 })
      .catch(() => {});
    const seen = (await page.textContent("body")) ?? "";
    for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
      const hit = seen.match(pattern);
      check(
        hit === null,
        `${name}: no ${pattern.source.slice(0, 24)}… in clerk copy${hit ? ` (${hit[0]})` : ""}`,
      );
    }
    // LEAF BY LEAF — see `OVER_PRECISE_MONEY`.
    const leaves = await page.evaluate(() =>
      Array.from(document.querySelectorAll("body *"))
        .filter((el) => el.children.length === 0)
        .map((el) => (el.textContent ?? "").trim())
        .filter(Boolean),
    );
    const over = leaves.filter((one) => /\$\s?\d[\d,]*\.\d{3,}/.test(one));
    check(
      over.length === 0,
      `${name}: money shows two decimals in every cell${over.length ? ` (saw ${over[0]})` : ` (${leaves.length} leaves read)`}`,
    );
  }

  await browser.close();
  console.log(`\n── screenshots in ${OUT}`);
  if (failures.length) {
    console.error(`\n⛔ ${failures.length} failed:`);
    for (const one of failures) console.error(`   · ${one}`);
    process.exit(1);
  }
  console.log("\n✓ both screens read as designed answers");
})();
