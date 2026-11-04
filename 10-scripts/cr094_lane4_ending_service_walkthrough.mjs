// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 1 lane 4 — ending service. The five screens the
//          blueprint draws at pages 98–131: the move-out wizard (S20), its
//          standalone door, the close-out act, the transfer wizard (S89) and
//          the disconnect wizard (S90).
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate in this repo reads rendered output) ·
//          law 7 habit 3 (a check's output must distinguish pass from fail TO
//          A READER) · PO 2026-09-10 (clerk screens are verified at 1280 and
//          1440, and nothing narrower) · B14 rule 37 (a figure drawn in a
//          wireframe is an ILLUSTRATION — nothing here asserts a drawn number)
// ───────────────────────────────────────────────────────
//
// ⚠ STEP 1 CLASSIFIES AND FIXES NOTHING, SO THIS WALK IS READ-ONLY.
// It opens each wizard, reads what the step rail and the fields actually say,
// and COMMITS NOTHING. No account is closed, no cut is scheduled, no sale is
// reassigned. Where a step cannot be reached without writing, the script says
// so in its own output rather than leaving the reader to infer it.
//
// WHAT IT MEASURES THAT NO SUITE IN THIS REPO CAN
//
//   1 · **the step rail a wizard actually renders**, against what the blueprint
//       drew. The DOM suites each mount ONE wizard and assert its own labels;
//       nothing compares a rail to a drawing. ⚠ **THIS MEASUREMENT DID NOT WORK
//       UNTIL 2026-09-12 (`DEF-CUS-5096`)** — its selector could not match
//       `WizardFrame`'s rail, so every run printed `(none rendered)` and the
//       step-1 audit's rail tables were read off the `innerText` dumps by eye.
//       A claim in this header is not the measurement; see the note at the
//       selector itself.
//   2 · **whether a date field is a native `input[type=date]`** — UI-RULES 7's
//       `.date-input` does not exist anywhere in 07-frontend, and only the
//       browser can say what the control actually is.
//   3 · **the commit button's rendered `class`** against `buttonClasses`,
//       because B14 rule 6's danger tier is a colour and a prop assertion was
//       green on the day it was broken (B14 amendment 2026-08-25).
//   4 · **the page-head title's computed font-size** (B14 rule 40, 32px).
//   5 · **money on screen at more than 2 decimals** (CLAUDE.md hard rule 2).
//
// HOW TO RUN IT
//
//   06-backend  $ DJANGO_SETTINGS_MODULE=config.settings.local \
//                 DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
//                 python3 manage.py runserver 127.0.0.1:8600 --noreload
//   07-frontend $ npx vite build && PORT=8601 API_PROXY_TARGET=http://127.0.0.1:8600 node server.mjs
//   10-scripts  $ BASE=http://127.0.0.1:8601 node cr094_lane4_ending_service_walkthrough.mjs
import { existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8601";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr094-lane4";
// The blueprint's own fixture account, A-10432 — active, $247.30, one unit.
const MOVE_OUT_ACCOUNT = process.env.MOVE_OUT_ACCOUNT ?? "";
const CLOSE_OUT_ACCOUNT = process.env.CLOSE_OUT_ACCOUNT ?? "";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const c = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium found");
}

const lines = [];
function say(s) { console.log(s); lines.push(s); }

/** Everything the page can tell us about one wizard screen, read as RENDERED
 *  output rather than as source. */
async function readScreen(page) {
  return page.evaluate(() => {
    const text = (el) => (el ? (el.innerText || "").replace(/\s+/g, " ").trim() : null);
    const head = document.querySelector("h1, h2");
    // ⚠ **THIS SELECTOR MATCHED NOTHING, AND THE RAIL IS MEASUREMENT #1 OF THE
    //     FIVE THIS SCRIPT'S OWN HEADER CLAIMS — `DEF-CUS-5096`, 2026-09-12.**
    // It read `[class*='step'], ol li, nav ol li`. `WizardFrame` renders the
    // rail as `<nav data-wizard="rail"><button data-wizard-step="1">` — no
    // `<ol>`, no `<li>`, and every class a Tailwind utility, so not one of the
    // three alternatives could ever match. Measured on a live disconnect
    // wizard: the old selector finds **0** elements and `[data-wizard-step]`
    // finds **5**, with the right text in them.
    //
    // **So every run of this script, including the step-1 run it was written
    // for, printed `step rail ..... (none rendered)` on all five screens** —
    // and step 1's rail tables were read off the `innerText` dumps by eye
    // instead. That is CLAUDE.md law 7's *structurally incapable of failing*:
    // the check could not fire, its output was indistinguishable from a screen
    // with no rail, and it was believed for a whole audit.
    //
    // ⚠ It is fixed by ADDING the real handle rather than replacing the old
    // guesses: `DataTable` and other kit pieces do use `<ol>`/`<li>` rails
    // elsewhere, and narrowing this to one product would make the script
    // blind somewhere new. `data-wizard-step` is `WizardFrame`'s own contract.
    const rail = [
      ...document.querySelectorAll(
        "[data-wizard-step], [data-wizard='rail'] button, [class*='step'], ol li, nav ol li",
      ),
    ]
      .map((el) => (el.innerText || "").replace(/\s+/g, " ").trim())
      .filter((s) => s && s.length < 60);
    const buttons = [...document.querySelectorAll("button, a[role='button']")].map((b) => ({
      label: (b.innerText || "").replace(/\s+/g, " ").trim(),
      disabled: b.disabled === true || b.getAttribute("aria-disabled") === "true",
      cls: b.className,
    }));
    const inputs = [...document.querySelectorAll("input, select, textarea")].map((i) => ({
      tag: i.tagName.toLowerCase(),
      type: i.getAttribute("type"),
      name: i.getAttribute("name") || i.id || null,
      cls: i.className,
      required: i.required === true || i.getAttribute("aria-required") === "true",
    }));
    const body = document.body.innerText || "";
    // Money at more than two decimals on screen — hard rule 2.
    const overPrecise = [...new Set(body.match(/\$?\d[\d,]*\.\d{3,}/g) || [])];
    const headSize = head ? getComputedStyle(head).fontSize : null;
    return {
      title: text(head),
      headSize,
      rail,
      buttons,
      inputs,
      overPrecise,
      bodyLen: body.length,
      body,
    };
  });
}

function summarise(tag, s) {
  say(`  title ......... ${JSON.stringify(s.title)}  (font-size ${s.headSize})`);
  const railStr = [...new Set(s.rail)].slice(0, 14).join(" | ");
  say(`  step rail ..... ${railStr || "(none rendered)"}`);
  const dateInputs = s.inputs.filter((i) => i.type === "date");
  const kitDate = s.inputs.filter((i) => (i.cls || "").includes("date-input"));
  say(`  date controls . ${dateInputs.length} native input[type=date] · ${kitDate.length} .date-input`);
  const commit = s.buttons.filter((b) => /✓|Complete|Schedule|Record|Confirm|Close it out/i.test(b.label));
  for (const b of commit) {
    const danger = /danger/i.test(b.cls);
    say(`  commit ........ ${JSON.stringify(b.label)}  disabled=${b.disabled}  danger-class=${danger}`);
  }
  say(`  money >2dp .... ${s.overPrecise.length ? s.overPrecise.join(", ") : "none"}`);
  writeFileSync(join(OUT, `${tag}.txt`), s.body, "utf8");
}

async function shot(page, tag, width) {
  await page.screenshot({ path: join(OUT, `${tag}-${width}.png`), fullPage: true });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  for (const width of [1280, 1440]) {
    const ctx = await browser.newContext({ viewport: { width, height: 1100 } });
    const page = await ctx.newPage();
    const consoleErrors = [];
    page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });

    say(`\n════════ ${width}px ════════`);
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
    await page.fill("#signin-email", EMAIL);
    await page.fill("#signin-password", PASSWORD);
    await page.click('button[type="submit"]');
    // ⚠ `networkidle` alone RACES the sign-in POST and leaves the walk on
    // /signin with every later call 401 — and the reader cannot tell that from
    // a page that simply renders nothing (law 7 habit 2: what would make this
    // check pass wrongly). Waiting for the dashboard URL is what refuses.
    await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });
    say(`signed in → ${page.url()}`);

    const walks = [
      ["08-move-out-step1", `${BASE}/${TENANT}/accounts/${MOVE_OUT_ACCOUNT}/move-out`],
      ["09-move-out-standalone", `${BASE}/${TENANT}/move-outs/new`],
      ["10-close-out", `${BASE}/${TENANT}/accounts/${CLOSE_OUT_ACCOUNT}/close-out`],
      ["11-transfer-step1", `${BASE}/${TENANT}/transfers/new`],
      ["12-disconnect-step1", `${BASE}/${TENANT}/disconnects/new`],
      ["01-register-move-outs", `${BASE}/${TENANT}/accounts?tab=move-outs`],
      ["01-register-transfers", `${BASE}/${TENANT}/accounts?tab=transfers`],
      ["01-register-disconnects", `${BASE}/${TENANT}/accounts?tab=disconnects`],
    ];

    for (const [tag, url] of walks) {
      say(`\n── ${tag} · ${url.replace(BASE, "")}`);
      try {
        await page.goto(url, { waitUntil: "networkidle" });
        await page.waitForTimeout(700);
        const s = await readScreen(page);
        summarise(tag, s);
        await shot(page, tag, width);
      } catch (e) {
        say(`  ✗ could not open: ${e.message}`);
      }
    }

    if (consoleErrors.length) {
      say(`\nconsole errors (${consoleErrors.length}):`);
      for (const e of [...new Set(consoleErrors)].slice(0, 12)) say(`  · ${e}`);
    } else {
      say(`\nconsole errors: none`);
    }
    await ctx.close();
  }
  await browser.close();
  writeFileSync(join(OUT, "walk.log"), lines.join("\n"), "utf8");
  say(`\nwritten to ${OUT}`);
})().catch((e) => { console.error(e); process.exit(1); });
