// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2 · lane 2 — ONE ASSET. The raise-work-order
//          door, the work list, the register words and the fold.
//          Screens: 08 Overview · 09 Reads · 12 Work & maintenance (S50/AST-02)
// Defects: DEF-MET-4965 (BR-WRK-056's two missing doors) · DEF-MET-4966 (the
//          green test that held one shut) · DEF-MET-4967 (the work-order list
//          fetched and discarded) · DEF-MET-4969 (raw register codes on
//          screen) · DEF-MET-4970 (the read log 2.6 screens below the fold)
// Rules:   BR-WRK-056 (the door is ONE form with four ways in) ·
//          BR-AST-534 (a control the STATE forbids is shown disabled with its
//          reason, never hidden — PO 2026-09-12) · BR-AST-030 · BR-SHL-025 ·
//          B14 rules 31, 33 · hard-won laws 2, 6, 7
// ───────────────────────────────────────────────────────
//
// WHY A WALKTHROUGH AND NOT MORE UNIT CASES.
//
// Every finding this closes is one a green suite passed over for weeks. A
// `renderToStaticMarkup` case proves a component; it cannot tell you that the
// route resolves, that the tenant's own catalogues carry the words, that the
// door opens on a real screen rather than on *"not built yet"*, or where on the
// page a panel actually lands. Three of the checks below are measurements no
// assertion in `AssetDetail.test.tsx` can make.
//
// ⚠ **THE DATA IT NEEDS DOES NOT EXIST ON A SEEDED TENANT, AND THAT IS THE
// FINDING BEHIND HALF THIS LANE.** Measured 2026-09-12 with `app.tenant_id`
// set (RLS `FORCE` is on, so an unscoped count reads 0 and looks like an empty
// database): **0 of 65 work orders across all three tenants carry an
// `asset_id`**, `asset_maintenance` holds **0 rows on every tenant**, and no
// meter's usage payload carried more than ONE register. So the Open work
// panel, the maintenance history and the multi-register strip had never been
// drawn by anything, anywhere. `cr092_lane2_seed.sql` beside this file is what
// this script runs against, and what it seeds is listed in its own header.
//
// ⚠ **AND TWO OF THESE CHECKS WERE WRONG BEFORE THEY WERE RIGHT** — both
// recorded here rather than quietly fixed, because each is hard-won law 7 in
// one of its named shapes:
//   * the fold measurement first used `boundingBox()`, which is VIEWPORT
//     relative — and Playwright scrolls an element into view before clicking
//     one, so it printed the same 765px before and after expanding every
//     register. Not *"the layout did not move"*: *"the ruler moved with it"*.
//     It reads the document coordinate now.
//   * the register count first matched every `[aria-expanded="false"]` on the
//     page and counted the app shell's own controls, reporting *five
//     registers* on a four-register meter. It reads `data-register-list` now.
//
// USAGE
//     BASE=http://127.0.0.1:8488 TENANT=oak-ridge \
//     ASSET=<uuid> RETIRED=<uuid> node 10-scripts/cr092_lane2_asset_detail_walkthrough.mjs
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8488";
const TENANT = process.env.TENANT ?? "oak-ridge";
const EMAIL = process.env.EMAIL ?? "elena@oakridgewater.test";
const PASSWORD = process.env.PASSWORD ?? "0akRidge!passw0rd";
const ASSET = process.env.ASSET ?? "01a08efa-12ed-7dc2-b5a9-08111147a36e"; // W-5001
const RETIRED = process.env.RETIRED ?? "";
const OUT = process.env.OUT ?? "/tmp/claude-0/-home-user-SMARTBillHub/9cbb9b39-00da-5925-a69c-c6f1b1985b49/scratchpad/cr092/work/shots";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found");
}

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });

for (const width of [1280, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  page.on("pageerror", (e) => console.log("  page error:", e.message));
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  console.log(`\n══ ${width}px · signed in as ${EMAIL} ══`);

  // ── 1 · the header door (DEF-MET-4965) ───────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/assets/${ASSET}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  const header = page.locator(".page-header-actions");
  const labels = await header.locator("a,button").allInnerTexts();
  check(`${width} · header offers Raise work order first`, labels[0]?.trim() === "Raise work order", `got ${JSON.stringify(labels)}`);
  const href = await header.locator("a", { hasText: "Raise work order" }).first().getAttribute("href");
  check(`${width} · it points at the door's own address`, href === `/${TENANT}/assets/${ASSET}/work-orders/new`, `href=${href}`);
  await page.screenshot({ path: `${OUT}/w${width}-08-overview.png` });

  // ── 2 · the door actually opens ──────────────────────────────────────────
  await header.locator("a", { hasText: "Raise work order" }).first().click();
  await page.waitForURL((u) => u.pathname.endsWith("/work-orders/new"), { timeout: 15000 });
  await page.waitForTimeout(600);
  const doorTitle = (await page.locator("h1").first().innerText()).trim();
  const notBuilt = await page.locator("text=not built yet").count();
  check(`${width} · the door opens on a real screen`, notBuilt === 0 && doorTitle.length > 0, `h1="${doorTitle}" notBuilt=${notBuilt}`);
  await page.screenshot({ path: `${OUT}/w${width}-27-raise.png` });

  // ── 3 · Reads: the register words and the fold (4969 + 4970) ─────────────
  await page.goto(`${BASE}/${TENANT}/assets/${ASSET}?tab=reads`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const body = await page.locator("body").innerText();
  check(`${width} · no raw register code on screen`, !/\btou_on\b|\btou_mid\b|\btou_off\b/.test(body), body.match(/tou_\w+/g)?.join(",") ?? "");
  check(`${width} · the registers are named in words`, /On-peak/.test(body) && /Off-peak/.test(body) && /Total register/.test(body));
  // ⚠ **DOCUMENT COORDINATES, NOT `boundingBox()`.** `boundingBox()` is
  // viewport-relative and Playwright scrolls an element into view before it
  // clicks one — so a first draft of this check measured 765px before AND
  // after expanding every register, which is not "the layout did not move", it
  // is "the page had scrolled underneath the ruler". A check whose number
  // cannot change is hard-won law 7's *incapable of failing*.
  const docTop = async () =>
    page.evaluate(() => {
      const el = document.querySelector("[data-asset-reads]");
      return el === null ? -1 : Math.round(el.getBoundingClientRect().top + window.scrollY);
    });
  const registerCount = Number(
    (await page.locator("[data-register-list]").getAttribute("data-register-list")) ?? 1,
  );
  const chartsDrawn = await page.locator("[data-register-chart]").count();
  const yNow = await docTop();

  if (registerCount < 2) {
    console.log(`          SKIPPED the fold check: this meter has ${registerCount} register, so there is nothing to collapse`);
  } else {
    // ⚠ **THE STRUCTURAL ASSERTION, WHICH CANNOT BE GAMED BY A THRESHOLD I
    // CHOSE.** However many registers a meter has, exactly ONE full chart
    // panel stands between the top of the page and the read log — that is the
    // fix `DEF-MET-4970` asks for, stated as a shape rather than as a pixel
    // count that drifts with the header's wrapping.
    check(`${width} · ${registerCount} registers, exactly ONE chart panel above the read log`, chartsDrawn === 1, `charts=${chartsDrawn}`);
    const closed = await page.locator('[data-register-list] [aria-expanded="false"]').count();
    check(`${width} · every other register is a collapsed row`, closed === registerCount - 1, `closed=${closed}`);
    for (let i = 0; i < closed; i += 1) {
      await page.locator('[data-register-list] [aria-expanded="false"]').first().click();
      await page.waitForTimeout(150);
    }
    const yOld = await docTop();
    const screens = (y) => (y / 900).toFixed(2);
    console.log(`          read log: BEFORE ${yOld}px (${screens(yOld)} screens, all ${registerCount} panels open — the shape this was filed against) → AFTER ${yNow}px (${screens(yNow)} screens) · viewport 900px`);
    check(`${width} · collapsing is what moved it`, yNow < yOld, `before=${yOld} after=${yNow}`);
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
  }

  const chanHeader = await page.locator('[data-asset-reads] th', { hasText: /^Channel$/ }).count();
  check(`${width} · the reads table carries a Channel column`, chanHeader === 1, `count=${chanHeader}`);
  await page.screenshot({ path: `${OUT}/w${width}-09-reads.png`, fullPage: false });

  // ── 4 · Maintenance: Open work + the second door (4965 + 4967) ───────────
  await page.goto(`${BASE}/${TENANT}/assets/${ASSET}?tab=maintenance`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const mbody = await page.locator("body").innerText();
  check(`${width} · Open work panel draws`, /Open work/.test(mbody));
  check(`${width} · the open orders are listed`, /WO-4908/.test(mbody) && /WO-4907/.test(mbody), mbody.match(/WO-\d+/g)?.join(",") ?? "");
  check(`${width} · a DONE order is not in Open work`, !/WO-4900/.test(mbody.split("Maintenance history")[0]));
  check(`${width} · the maintenance history draws its rows`, /Replaced the register/.test(mbody));
  const panelRaise = await page.locator("section", { hasText: "Open work" }).locator("a", { hasText: "Raise work order" }).count();
  check(`${width} · the panel carries its own raise control`, panelRaise >= 1, `count=${panelRaise}`);

  // ⚠ **DOES THE ORDER NUMBER ACTUALLY LOOK LIKE A LINK, AND DOES IT OPEN?**
  // Figure 18 draws it in the accent; a link the same colour as the text beside
  // it is a door nobody knows is there, and `toContain("href=")` cannot see the
  // difference.
  const linkPaint = await page.evaluate(() => {
    const a = document.querySelector('a[href$="/work/orders/WO-4908"]');
    if (a === null) return null;
    const cell = a.closest("tr")?.querySelectorAll("td")[1];
    return {
      link: getComputedStyle(a).color,
      plain: cell ? getComputedStyle(cell).color : null,
      underline: getComputedStyle(a).textDecorationLine,
    };
  });
  check(`${width} · the order number reads as a link`, linkPaint !== null && (linkPaint.link !== linkPaint.plain || linkPaint.underline.includes("underline")), JSON.stringify(linkPaint));
  if (linkPaint !== null) {
    await page.locator('a[href$="/work/orders/WO-4908"]').first().click();
    await page.waitForTimeout(1200);
    const opened = page.url();
    const dead = await page.locator("text=not built yet").count();
    check(`${width} · and it opens Work's own screen`, opened.endsWith("/work/orders/WO-4908") && dead === 0, `url=${opened} notBuilt=${dead}`);
    await page.goBack({ waitUntil: "networkidle" });
    await page.waitForTimeout(500);
  }
  await page.screenshot({ path: `${OUT}/w${width}-12-maintenance.png`, fullPage: false });

  // ── 5 · BR-AST-534 on a retired asset ────────────────────────────────────
  if (RETIRED) {
    await page.goto(`${BASE}/${TENANT}/assets/${RETIRED}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const btn = page.locator(".page-header-actions button", { hasText: "Raise work order" }).first();
    const shown = await btn.count();
    const disabled = shown ? await btn.isDisabled() : false;
    const title = shown ? await btn.getAttribute("title") : null;
    check(`${width} · retired: the control is SHOWN`, shown === 1, `count=${shown}`);
    check(`${width} · retired: it is DISABLED with its reason`, disabled && title === "This asset is retired.", `disabled=${disabled} title=${title}`);
    const stillLink = await page.locator('.page-header-actions a[href$="/work-orders/new"]').count();
    check(`${width} · retired: no link a middle-click could open`, stillLink === 0, `links=${stillLink}`);
    await page.screenshot({ path: `${OUT}/w${width}-08-retired.png` });
  }
  await page.close();
}

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
if (failed.length) { console.log("FAILED:"); failed.forEach((f) => console.log("  " + f.name)); process.exit(1); }
