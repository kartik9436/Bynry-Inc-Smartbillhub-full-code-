// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 1, lane 3 — STARTING SERVICE.
//          Screens 03 new account · 04 move-in · 05 move-in standalone ·
//          06 service request capture · 07 new connect, of
//          `04-docs/05-modules/03-customers/08-screen-layouts.md`.
// Purpose: STEP 1 CLASSIFIES AND FIXES NOTHING. This script writes no data and
//          submits no wizard. It INVENTORIES what each step actually renders —
//          the rail labels in order, the "Step N of M" caption, the page title,
//          every labelled control in DOM order with its required flag, the
//          footer, and every stated absence — so the conformance document can
//          be written from the running product rather than from the code.
// Rules:   hard-won law 6 (no gate in this repo reads rendered output — the
//          only way to know what a screen says is to open it) · law 7 habit 3
//          (a check's output must distinguish pass from fail TO A READER, so
//          this prints the inventory rather than a count) · PO 2026-09-10
//          (clerk screens are verified at 1280 and 1440, nothing narrower) ·
//          CR-094 §5(a) — do not quote a figure you have not measured.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY AN INVENTORY AND NOT ASSERTIONS.** The blueprint's screen-03 section
// says in its own words *"Every drawing below is the wizard as it should be,
// not as it is"*, so a test asserting the drawing would fail by design and
// prove nothing. What step 1 owes is a MEASUREMENT of the as-built, beside the
// drawing, with the difference named. That is what this prints.
//
// ⚠ **THE STEP COUNTS ARE READ FROM THE RAIL, NOT FROM THE URL.** `?step=9` on
// an eight-step wizard clamps silently (`stepFromParam`), so walking by URL and
// counting URLs would report whatever number you asked for. Every count below
// comes from the rail the browser painted.
//
// HOW TO RUN IT
//
//   06-backend  $ DJANGO_SETTINGS_MODULE=config.settings.local \
//                 DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
//                 python3 manage.py runserver 127.0.0.1:8590 --noreload
//   07-frontend $ PORT=8591 API_PROXY_TARGET=http://127.0.0.1:8590 node server.mjs
//   10-scripts  $ BASE=http://127.0.0.1:8591 node cr094_lane3_starting_service_walkthrough.mjs
//
// It NEVER presses a commit control. The only buttons it touches are the
// stepper's own rail entries and "Continue", and only where a step is already
// reachable without writing anything.
import { existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8591";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ACCOUNT = process.env.ACCOUNT ?? "01a08ad4-2e4d-7764-8f2f-29b8e825d4ac";
const OUT = process.env.OUT ?? "/tmp/cr094-lane3";
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

/** Everything a conformance row needs, read off the painted page. */
const INVENTORY = () => {
  const text = (el) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
  // The rail is the only honest source for the step list — see the header.
  const railNodes = Array.from(document.querySelectorAll(
    "[class*=wizard] li, [class*=stepper] li, ol[class*=step] li, nav[aria-label*='tep'] li, [class*='step-rail'] *[class*=item]",
  ));
  const rail = railNodes.map(text).filter(Boolean);
  const labelled = Array.from(document.querySelectorAll("input, select, textarea")).map((el) => {
    const id = el.id || null;
    let label = null;
    if (id) label = text(document.querySelector(`label[for="${CSS.escape(id)}"]`)) || null;
    if (!label) label = text(el.closest("label")) || null;
    if (!label) label = el.getAttribute("aria-label");
    return {
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute("type"),
      id,
      label,
      required: el.required || el.getAttribute("aria-required") === "true",
      disabled: el.disabled,
      placeholder: el.getAttribute("placeholder"),
    };
  });
  const buttons = Array.from(document.querySelectorAll("button, a[role=button]")).map((b) => ({
    label: text(b),
    disabled: b.disabled === true || b.getAttribute("aria-disabled") === "true",
  })).filter((b) => b.label);
  return {
    url: location.pathname + location.search,
    h1: text(document.querySelector("h1")),
    kicker: text(document.querySelector("[class*=kicker]")),
    caption: (document.body.innerText.match(/Step\s+\d+\s+of\s+\d+[^\n]*/) || [null])[0],
    rail,
    headings: Array.from(document.querySelectorAll("h2, h3")).map(text).filter(Boolean),
    fields: labelled,
    buttons,
    // A stated absence is the product saying what it cannot do. It is NOT a
    // defect (CR-094 §5(b)); it is recorded so the conformance doc can quote it.
    absences: Array.from(document.querySelectorAll(
      "[class*=absence], [class*=refus], [class*=notice], [class*=callout], [class*=warning], [class*=banner]",
    )).map(text).filter((s) => s.length > 12),
    bodyChars: document.body.innerText.length,
  };
};

const browser = await chromium.launch({ executablePath: resolveChromium() });

const FLOWS = [
  { screen: "03", name: "New account wizard", path: `/${TENANT}/accounts/new`, probe: 8 },
  { screen: "04", name: "Move-in wizard", path: `/${TENANT}/accounts/${ACCOUNT}/move-in`, probe: 8 },
  { screen: "05", name: "Move-in · standalone", path: `/${TENANT}/move-ins/new`, probe: 8 },
  { screen: "06", name: "Service request capture", path: `/${TENANT}/requests/new`, probe: 8 },
  { screen: "07", name: "New connect wizard", path: `/${TENANT}/connections/new`, probe: 11 },
];

for (const width of [1440, 1280]) {
  const page = await browser.newPage({ viewport: { width, height: 1600 } });
  page.on("pageerror", (e) => say(`  PAGE ERROR: ${e.message}`));

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  say(`\n############ WIDTH ${width} ############`);

  for (const flow of FLOWS) {
    say(`\n================ ${flow.screen} · ${flow.name} ================`);
    for (let s = 1; s <= flow.probe; s += 1) {
      await page.goto(`${BASE}${flow.path}?step=${s}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(700);
      const inv = await page.evaluate(INVENTORY);
      // ⚠ The clamp: ?step=9 on an 8-step wizard renders step 8. Reporting the
      // URL we asked for would manufacture a ninth step that does not exist.
      say(`\n-- asked ?step=${s} · landed ${inv.url}`);
      say(`   H1        : ${JSON.stringify(inv.h1)}`);
      say(`   kicker    : ${JSON.stringify(inv.kicker)}`);
      say(`   caption   : ${JSON.stringify(inv.caption)}`);
      say(`   rail (${inv.rail.length}): ${JSON.stringify(inv.rail)}`);
      say(`   headings  : ${JSON.stringify(inv.headings)}`);
      say(`   fields (${inv.fields.length}):`);
      for (const f of inv.fields) {
        say(`     · ${f.required ? "REQ " : "    "}${f.disabled ? "DIS " : "    "}${f.tag}${f.type ? `/${f.type}` : ""} #${f.id ?? "-"} ${JSON.stringify(f.label)}${f.placeholder ? ` ph=${JSON.stringify(f.placeholder)}` : ""}`);
      }
      say(`   buttons   : ${JSON.stringify(inv.buttons)}`);
      for (const a of inv.absences) say(`   ABSENCE   : ${JSON.stringify(a)}`);
      if (inv.caption) {
        const m = inv.caption.match(/Step\s+(\d+)\s+of\s+(\d+)/);
        if (m && Number(m[1]) !== s) {
          say(`   ⚠ CLAMPED — asked ${s}, the screen says step ${m[1]} of ${m[2]}. Stop probing.`);
          break;
        }
      }
    }
  }
  await page.close();
}

await browser.close();
writeFileSync(join(OUT, "inventory.txt"), lines.join("\n"));
say(`\nwrote ${join(OUT, "inventory.txt")}`);
