// ── Trace ──────────────────────────────────────────────
// Change:  the three outstanding items of the 2026-09-08 PO rulings —
//          (10) *"yes please"*, SURFACES moves to the top of the template rail
//               reworded as *"This notice also goes out as: SMS · Printed
//               letter"* with one line saying each is edited separately;
//          (8)  *"(a) Texas, fix the postcode"*, `DEF-MET-4629` — one seeded
//               estate answered the same address question three ways;
//          `CR-077`'s READING starters, the last unbuilt piece of the
//               2026-09-07 ruling *"…Accounts, Reading"*.
// Screens: SET-10 (Settings → Configure → Templates) · S21 (Account) ·
//          S28 (Reads → Upload)
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//          RUNNING app) · law 7 (a check must distinguish pass from fail to a
//          READER, and you must be able to say what would make it pass
//          wrongly) · law 2 (built is not wired, and its mirror: a live screen
//          behind a dead control) · B14 rule 32 (a description budget)
// ───────────────────────────────────────────────────────
/**
 * po20260908_walkthrough — click the three things and say what is on screen.
 *
 *     # a stack on ports of your own (a port answering 200 is not proof YOUR
 *     # server bound it — check the boot lines in the logs)
 *     cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
 *       DATABASE_URL=... python3.12 manage.py runserver 127.0.0.1:8331 --noreload
 *     cd 07-frontend && ./node_modules/.bin/vite build \
 *       && PORT=8332 API_PROXY_TARGET=http://127.0.0.1:8331 node server.mjs
 *     OUT=/tmp/po20260908 node 10-scripts/po20260908_walkthrough.mjs
 *
 * ⚠ **REBUILD `dist/` BEFORE YOU WALK.** `server.mjs` serves whatever was on
 * disk when a request arrives and never says the bundle is stale.
 *
 * ╔══════════════════════════════════════════════════════════════════════╗
 * ║  WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked before trusting    ║
 * ║  any of them green (hard-won law 7, second habit)                     ║
 * ╚══════════════════════════════════════════════════════════════════════╝
 *  · **A · the rail.** *"Surfaces is present"* was already true before the
 *    ruling — it was the FOURTH panel. So this asserts POSITION, by geometry:
 *    the switcher's top edge is above the merge-fields panel's top edge, in
 *    the browser, where a rail is actually laid out. A DOM-order assertion
 *    would pass on a rail that CSS had reordered, and a presence assertion
 *    would pass on the very screen the Product Owner complained about.
 *  · **A · the sentence.** A test asserting "some text is under the tabs"
 *    passes on a tooltip that never renders. This reads the element's
 *    `innerText` — what a person can actually read — and asserts it is not
 *    empty and is not clipped to zero height.
 *  · **B · the addresses.** Asserting "the page contains TX" passes on a page
 *    that ALSO contains `Texas` somewhere else. So this asserts the ABSENCE of
 *    the two old spellings and of the old postcode across the whole rendered
 *    page, and the presence of the new pair in BOTH the header and the mailing
 *    box, located separately.
 *  · **C · the starters.** Downloading a file proves the button is wired; it
 *    does not prove the file works. So each downloaded body is PASTED BACK
 *    into the wizard and staged through the real server, and the mapping the
 *    server answers with is read for unmapped columns. A file that downloads
 *    and cannot be uploaded is exactly the Parts trap this lane was warned
 *    about.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8332";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/po20260908";
const VIEWPORT = { width: Number(process.env.WIDTH ?? 1440), height: Number(process.env.HEIGHT ?? 1000) };

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

/**
 * S28 step 1 → step 2. The reading month is the ONE required tag (the wizard's
 * own `validate`), so this fills it and advances; a walk that opened
 * `/reads/upload` and looked for the starter buttons would time out on a
 * perfectly healthy screen, which is a finding about the walk and not about
 * the product (`DEF-NOT-4462`'s shape).
 */
async function walkToUpload(page) {
  await page.goto(`${BASE}/${TENANT}/reads/upload`, { waitUntil: "networkidle" });
  await page.waitForSelector("#period_month", { timeout: 30000 });
  await page.fill("#period_month", "2026-08-03");
  // ⚠ **THE ENABLED ONE.** The workflow rail draws a DISABLED stage button
  // carrying the same word, and `first()` finds that one — a walk that clicks
  // it times out on a healthy screen and reads exactly like a broken product.
  await page.locator('button:has-text("Transform"):not([disabled])').first().click();
  await page.waitForSelector('[data-testid="reads-starter-flat"]', { timeout: 30000 });
}

/**
 * The mapping stage-2 answers, read as MACHINE STATUS rather than as words.
 *
 * ⚠ `data-workflow-map-status` is `matched` | `ignored` | `unmapped`; the CELL
 * says *"Matched"* / *"Ignored"* / *"Not mapped"* and is translated, so a check
 * written against the English label is a check that stops working in ten of
 * the eleven catalogues and never says so.
 */
async function stagedMapping(page) {
  await page.waitForSelector('[data-workflow="mapping"] tbody tr', { timeout: 30000 });
  return page.evaluate(() => {
    const rows = [...document.querySelectorAll('[data-workflow="mapping"] tbody tr')];
    const byStatus = {};
    const notMatched = [];
    for (const tr of rows) {
      const status = tr.getAttribute("data-workflow-map-status") ?? "(none)";
      byStatus[status] = (byStatus[status] ?? 0) + 1;
      if (status !== "matched") {
        notMatched.push([(tr.querySelector("td")?.textContent ?? "").trim(), status]);
      }
    }
    const text = (document.querySelector("main") ?? document.body).innerText;
    return {
      total: rows.length,
      byStatus,
      notMatched,
      rowCount: (/(\d+)\s+rows?/i.exec(text) ?? [])[1] ?? null,
    };
  });
}

const findings = [];
function say(line) {
  console.log(line);
}
function bad(line) {
  findings.push(line);
  console.error("  ✗ " + line);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium(), headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT, acceptDownloads: true });
  const page = await context.newPage();
  page.on("response", (r) => {
    if (r.status() >= 500) bad(`${r.status()} ${r.request().method()} ${r.url()}`);
  });

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });
  say("signed in");

  /* ══ A · SET-10 — SURFACES IS THE RAIL'S FIRST PANEL ═══════════════════ */
  say("\n── A · Settings → Configure → Templates → the SMS bill-ready notice ──");
  await page.goto(
    `${BASE}/${TENANT}/settings/reference-data/templates?template=sms_bill_ready`,
    { waitUntil: "networkidle" },
  );
  await page.waitForSelector('[data-testid="template-detail-page"]', { timeout: 30000 });
  await page.waitForSelector('[data-testid="surface-switcher"]', { timeout: 30000 });

  const rail = await page.evaluate(() => {
    const railEl = document.querySelector('[data-testid="reading-rail"]');
    if (railEl === null) return null;
    const panels = [...railEl.children].map((el) => {
      const own = el.getAttribute("data-testid");
      const inner = el.querySelector("[data-testid]");
      const box = el.getBoundingClientRect();
      return {
        id: own ?? inner?.getAttribute("data-testid") ?? el.tagName.toLowerCase(),
        top: Math.round(box.top),
        height: Math.round(box.height),
      };
    });
    const switcher = document.querySelector('[data-testid="surface-switcher"]');
    const merge = document.querySelector('[data-testid="merge-fields"]');
    const sentence = document.querySelector('[data-testid="surface-separate"]');
    const heading = switcher?.querySelector("p");
    const scroller = document.querySelector("main") ?? document.documentElement;
    return {
      panels,
      switcherTop: switcher === null ? null : Math.round(switcher.getBoundingClientRect().top),
      mergeTop: merge === null ? null : Math.round(merge.getBoundingClientRect().top),
      railTop: Math.round(railEl.getBoundingClientRect().top),
      fold: Math.round(scroller.getBoundingClientRect().bottom),
      heading: (heading?.textContent ?? "").trim(),
      tabs: [...(switcher?.querySelectorAll('[role="tab"]') ?? [])].map((el) =>
        (el.textContent ?? "").trim(),
      ),
      sentence: sentence === null ? null : (sentence.innerText ?? "").trim(),
      sentenceHeight: sentence === null ? 0 : Math.round(sentence.getBoundingClientRect().height),
    };
  });

  if (rail === null) {
    bad("there is no reading rail at all");
  } else {
    say(`rail panels, top to bottom: ${rail.panels.map((p) => `${p.id}@${p.top}px`).join(" · ")}`);
    say(`heading: "${rail.heading}"  ·  tabs: ${JSON.stringify(rail.tabs)}`);
    say(`sentence (${rail.sentenceHeight}px tall): "${rail.sentence}"`);
    if (rail.panels[0]?.id !== "surface-switcher") {
      bad(`Surfaces is not the rail's first panel — first is ${rail.panels[0]?.id}`);
    }
    // Geometry, not DOM order: a rail CSS had reordered would pass the check above.
    if (rail.mergeTop !== null && rail.switcherTop !== null && rail.switcherTop >= rail.mergeTop) {
      bad(`Surfaces (${rail.switcherTop}px) is not ABOVE merge fields (${rail.mergeTop}px)`);
    }
    if (rail.switcherTop !== null && rail.switcherTop > rail.fold) {
      bad(`Surfaces starts at ${rail.switcherTop}px, below the ${rail.fold}px fold`);
    }
    if (rail.heading !== "This notice also goes out as") {
      bad(`the heading reads "${rail.heading}", not the ruled wording`);
    }
    if (rail.sentence === null || rail.sentence === "" || rail.sentenceHeight === 0) {
      bad("the line saying each surface is edited separately is not on screen");
    }
  }
  await page.screenshot({ path: join(OUT, "A1-surfaces-at-top.png"), fullPage: false });

  // …and the same place in the EDIT mode, which is the other rail.
  const edit = page.locator('[data-testid="edit-wording"], button:has-text("Edit wording")').first();
  if ((await edit.count()) > 0) {
    await edit.click();
    await page.waitForSelector('[data-testid="designer-rail"]', { timeout: 20000 });
    const first = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="designer-rail"]');
      const child = el?.children[0];
      return child?.getAttribute("data-testid") ?? child?.querySelector("[data-testid]")?.getAttribute("data-testid") ?? null;
    });
    say(`edit-mode rail's first panel: ${first}`);
    if (first !== "surface-switcher") bad(`edit mode still opens with ${first} above Surfaces`);
    await page.screenshot({ path: join(OUT, "A2-surfaces-edit-mode.png"), fullPage: false });
  }

  /* ══ B · S21 — THE TWO ADDRESSES ON ONE ACCOUNT AGREE ══════════════════ */
  say("\n── B · Accounts → one account: the header and the mailing box ──");
  await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
  await page.waitForSelector("table tbody tr a", { timeout: 30000 });
  await page.locator("table tbody tr a").first().click();
  await page.waitForSelector("h1", { timeout: 30000 });
  await page.waitForSelector('text=/Mailing address/i', { timeout: 30000 });

  const address = await page.evaluate(() => {
    const text = (document.querySelector("main") ?? document.body).innerText;
    const heading = [...document.querySelectorAll("h4")].find((el) =>
      /mailing address/i.test(el.textContent ?? ""),
    );
    const box = heading?.nextElementSibling;
    return {
      accountNo: (document.querySelector("h1")?.textContent ?? "").trim(),
      header: (document.querySelector("h1")?.parentElement?.innerText ?? "").trim().split("\n").join(" | "),
      mailing: (box?.textContent ?? "").trim(),
      hasOldState: /\bTexas\b/.test(text),
      hasOldAbbrev: /,\s*NE\b/.test(text),
      hasOldPostcode: /\b68901\b/.test(text),
      newPairs: (text.match(/TX[ ,]+78611/g) ?? []).length,
    };
  });
  say(`account: ${address.accountNo}`);
  say(`header:  ${address.header}`);
  say(`mailing: ${address.mailing}`);
  say(
    `old spellings on this page — "Texas": ${address.hasOldState} · ", NE": ${address.hasOldAbbrev} · "68901": ${address.hasOldPostcode}`,
  );
  if (address.hasOldState) bad('the page still says "Texas" where an address wants the code');
  if (address.hasOldAbbrev) bad('the page still says ", NE"');
  if (address.hasOldPostcode) bad("the page still carries the Nebraska postcode 68901");
  if (!/TX/.test(address.mailing) || !/78611/.test(address.mailing)) {
    bad(`the mailing box does not read TX 78611 — it reads "${address.mailing}"`);
  }
  if (!/78611/.test(address.header)) {
    bad(`the header does not carry the estate's postcode — it reads "${address.header}"`);
  }
  await page.screenshot({ path: join(OUT, "B1-account-addresses.png"), fullPage: false });

  /* ══ C · S28 — THE FOUR READING STARTERS, DOWNLOADED AND UPLOADED ══════ */
  say("\n── C · Reads → Upload: the four starter files ──");
  await walkToUpload(page);

  const labels = await page.evaluate(() =>
    ["flat", "tou", "demand", "net"].map((s) => {
      const el = document.querySelector(`[data-testid="reads-starter-${s}"]`);
      return { shape: s, label: (el?.textContent ?? "").trim(), enabled: el !== null && !el.disabled };
    }),
  );
  say(`starter buttons: ${labels.map((l) => `${l.shape}="${l.label}"(${l.enabled ? "enabled" : "DISABLED"})`).join(" · ")}`);
  for (const l of labels) {
    if (!l.enabled) bad(`the ${l.shape} starter button is not clickable`);
    if (l.label === "") bad(`the ${l.shape} starter button has no label`);
  }
  await page.screenshot({ path: join(OUT, "C1-four-starters.png"), fullPage: false });

  const files = {};
  for (const shape of ["flat", "tou", "demand", "net"]) {
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 20000 }),
      page.click(`[data-testid="reads-starter-${shape}"]`),
    ]);
    const path = join(OUT, `starter-${shape}.csv`);
    await download.saveAs(path);
    const body = (await import("node:fs")).readFileSync(path, "utf8");
    files[shape] = { name: download.suggestedFilename(), body };
    say(`  downloaded ${shape}: ${download.suggestedFilename()} — ${body.trim().split("\n").length - 1} worked row(s)`);
  }

  // …and each one back UP through the real screen. The file is PASTED, which
  // is the same input by another route and is what makes this provable without
  // a file dialog; the server stages it and answers with the mapping IT
  // detected, which is the thing being asked about.
  for (const shape of ["flat", "tou", "demand", "net"]) {
    await walkToUpload(page);
    await page.fill("#reads-text", files[shape].body);
    await page.locator('button:has-text("Stage the batch"):not([disabled])').first().click();
    const staged = await stagedMapping(page);
    say(
      `  ${shape}: ${staged.total} column(s) detected · ` +
        Object.entries(staged.byStatus).map(([k, v]) => `${v} ${k}`).join(", ") +
        (staged.rowCount === null ? "" : ` · ${staged.rowCount} row(s) staged`),
    );
    if (staged.total === 0) bad(`${shape}: the mapping table is EMPTY — nothing was detected`);
    if (staged.notMatched.length > 0) {
      bad(
        `${shape}: ${staged.notMatched.length} column(s) the clerk would have to map by hand — ` +
          JSON.stringify(staged.notMatched),
      );
    }
    await page.screenshot({ path: join(OUT, `C2-${shape}-staged.png`), fullPage: false });
  }

  /* ── C · THE NEGATIVE CONTROL, AND IT IS NOT OPTIONAL ─────────────────────
     The first version of the check above looked for a cell reading *"not
     matched"* and reported `0 unmatched` for every file. The label this table
     actually prints is **"Not mapped"**, so the regex could never match
     anything — a check STRUCTURALLY INCAPABLE OF FAILING, reporting a true
     zero over a scope it silently excluded (hard-won law 7). It reads
     `data-workflow-map-status` now, which is the machine value.

     So the instrument proves itself before its result is believed: the same
     flat file with ONE header renamed to something no alias covers must come
     back with that column NOT matched. If this run reports zero, the check
     above is measuring nothing and every green line before it is worthless. */
  // ⚠ **AN OPTIONAL COLUMN, NOT A REQUIRED ONE.** Renaming `reading` was the
  // first attempt and it proves something else entirely: a missing REQUIRED
  // column is a whole-file refusal (`required_column_not_mapped`), so nothing
  // stages, there is no mapping table, and this walk timed out on a server
  // behaving exactly as BR-MET-032 says it should. `notes` is optional, so the
  // file stages and the unknown column comes back for a clerk to deal with —
  // which is the state this check has to be able to see.
  const sabotaged = files.flat.body.replace(/,notes,/, ",zz_not_a_column,");
  await walkToUpload(page);
  await page.fill("#reads-text", sabotaged);
  await page.locator('button:has-text("Stage the batch"):not([disabled])').first().click();
  const control = await stagedMapping(page);
  say(
    `  negative control (one header renamed): ${control.total} column(s) · ` +
      Object.entries(control.byStatus).map(([k, v]) => `${v} ${k}`).join(", "),
  );
  if (control.notMatched.length === 0) {
    bad(
      "THE UNMAPPED CHECK CANNOT FAIL: a file with an unknown column still reported " +
        "every column matched, so the four green lines above prove nothing",
    );
  }
  await page.screenshot({ path: join(OUT, "C3-negative-control.png"), fullPage: false });

  writeFileSync(join(OUT, "findings.txt"), findings.join("\n") + "\n");
  say(`\n${findings.length} finding(s); shots in ${OUT}`);
  await browser.close();
  process.exit(findings.length === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});
