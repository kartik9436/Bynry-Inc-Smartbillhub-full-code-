// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 1, lane 3 — STARTING SERVICE, second pass.
// Purpose: Two things the first pass could not do.
//          (1) **WALK screen 06 (service request capture) by CLICKING**, because
//              `?step=` does NOT move that wizard — it is the one flow of the
//              five whose step is not URL state, so its steps 2–6 are invisible
//              to a URL probe and were never measured.
//          (2) **MEASURE the rules, not the markup** — B14 rule 40 (the
//              page-head title is 32px on every screen, ratified 2026-09-12),
//              rule 7 (a date field is never a bare text input) and rule 32 (a
//              stated absence is a `<details>` CLOSED by default).
// Rules:   B14 rules 7 · 32 · 40 · hard-won law 6 · CR-094 §5(a) — do not quote
//          a figure you have not measured.
// ───────────────────────────────────────────────────────
//
// ⚠ **IT STILL COMMITS NOTHING.** It types into screen 06 and presses Continue,
// which the product itself says writes nothing until the name and address are
// in — and it stops at step 6 without pressing *Submit request*. Nothing else
// is filled and no other wizard is advanced.
//
// ⚠ **`getComputedStyle`, NEVER A CLASS TOKEN (DEF-MET-4984).** A size asserted
// from a class name passes while the browser paints something else. Rule 40's
// own wording is *"the size is set on the element rather than inherited from
// its tag"*, which only a computed style can answer.
//
// HOW TO RUN IT — same stack as cr094_lane3_starting_service_walkthrough.mjs:
//   10-scripts $ BASE=http://127.0.0.1:8591 node cr094_lane3_walk_and_measure.mjs
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

const MEASURE = () => {
  const text = (el) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
  const h1 = document.querySelector("h1");
  const cs = h1 ? getComputedStyle(h1) : null;
  return {
    url: location.pathname + location.search,
    h1: text(h1),
    // Rule 40 — 32px on every ordinary screen, set on the element.
    h1FontSize: cs?.fontSize ?? null,
    h1Weight: cs?.fontWeight ?? null,
    caption: (document.body.innerText.match(/Step\s+\d+\s+of\s+\d+[^\n]*/) || [null])[0],
    headings: Array.from(document.querySelectorAll("h2, h3")).map(text).filter(Boolean),
    // Rule 7 — every date field. A bare text input with a date placeholder is
    // the violation the blueprint calls repo-wide; naming the element decides it.
    dateish: Array.from(document.querySelectorAll("input")).filter((el) => {
      const id = (el.id || "").toLowerCase();
      const ph = (el.getAttribute("placeholder") || "").toLowerCase();
      return el.type === "date" || /date|dob|_at$|_on$/.test(id) || /yyyy|mm\/dd/.test(ph);
    }).map((el) => ({
      id: el.id || null, type: el.type, placeholder: el.getAttribute("placeholder"),
      cls: el.className || null,
    })),
    // Rule 32 — a stated absence is a <details> CLOSED by default.
    details: Array.from(document.querySelectorAll("details")).map((d) => ({
      open: d.open, summary: text(d.querySelector("summary")).slice(0, 90),
    })),
    fields: Array.from(document.querySelectorAll("input, select, textarea")).map((el) => {
      let label = null;
      if (el.id) label = text(document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) || null;
      if (!label) label = text(el.closest("label")) || null;
      return { tag: el.tagName.toLowerCase(), type: el.getAttribute("type"), id: el.id || null, label, required: el.required };
    }).filter((f) => f.id !== null || f.label),
    buttons: Array.from(document.querySelectorAll("button")).map((b) => ({ label: text(b), disabled: b.disabled }))
      .filter((b) => b.label),
  };
};

const browser = await chromium.launch({ executablePath: resolveChromium() });

for (const width of [1440, 1280]) {
  const page = await browser.newPage({ viewport: { width, height: 1600 } });
  page.on("pageerror", (e) => say(`  PAGE ERROR: ${e.message}`));
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  say(`\n############ WIDTH ${width} ############`);

  // ── Rule 40 / 7 / 32, on the entry step of each of the five screens ───────
  const entries = [
    ["03 new account", `/${TENANT}/accounts/new`],
    ["04 move-in", `/${TENANT}/accounts/${ACCOUNT}/move-in`],
    ["05 move-in standalone", `/${TENANT}/move-ins/new`],
    ["06 request capture", `/${TENANT}/requests/new`],
    ["07 new connect", `/${TENANT}/connections/new`],
  ];
  for (const [name, path] of entries) {
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);
    const m = await page.evaluate(MEASURE);
    say(`\n-- ${name} · ${m.url}`);
    say(`   h1            : ${JSON.stringify(m.h1)}`);
    say(`   RULE 40 size  : ${m.h1FontSize} (weight ${m.h1Weight})  ${m.h1FontSize === "32px" ? "== 32px OK" : "!= 32px"}`);
    say(`   RULE 7 dates  : ${JSON.stringify(m.dateish)}`);
    say(`   RULE 32 detail: ${JSON.stringify(m.details)}`);
  }

  // ── Screen 06, walked by CLICKING, because ?step= does not move it ────────
  say(`\n================ 06 · service request capture — WALKED ================`);
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const fill = async (sel, value) => {
    if (await page.locator(sel).count()) { await page.fill(sel, value); return true; }
    return false;
  };
  for (let step = 1; step <= 6; step += 1) {
    const m = await page.evaluate(MEASURE);
    say(`\n-- painted step ${step} · ${m.url}`);
    say(`   h1       : ${JSON.stringify(m.h1)}  (${m.h1FontSize})`);
    say(`   caption  : ${JSON.stringify(m.caption)}`);
    say(`   headings : ${JSON.stringify(m.headings)}`);
    say(`   fields   :`);
    for (const f of m.fields) {
      say(`     · ${f.required ? "REQ " : "    "}${f.tag}${f.type ? `/${f.type}` : ""} #${f.id ?? "-"} ${JSON.stringify(f.label)}`);
    }
    say(`   buttons  : ${JSON.stringify(m.buttons.filter((b) => !/Dana Whitfield/.test(b.label)))}`);
    say(`   RULE 32  : ${JSON.stringify(m.details)}`);
    if (step === 6) break;
    // Minimum to pass each gate. Nothing else is typed.
    await fill("#applicant_name", "Lane3 Probe");
    await fill("#applicant_email", "lane3@example.com");
    await fill("#applicant_phone", "(512) 555-0142");
    await fill("#service_address_line1", "212 Balcones Drive");
    await fill("#service_city", "Austin");
    await fill("#service_postal_code", "78704");
    await fill("#unit_count", "6");
    const moved = await page.evaluate(() => {
      const b = Array.from(document.querySelectorAll("button"))
        .find((x) => /^continue$/i.test((x.textContent || "").trim()) && !x.disabled);
      if (!b) return false;
      b.click();
      return true;
    });
    await page.waitForTimeout(1200);
    if (!moved) { say(`   ⚠ no enabled Continue on step ${step} — the walk stops here.`); break; }
  }
  await page.close();
}

await browser.close();
writeFileSync(join(OUT, "measure.txt"), lines.join("\n"));
say(`\nwrote ${join(OUT, "measure.txt")}`);
