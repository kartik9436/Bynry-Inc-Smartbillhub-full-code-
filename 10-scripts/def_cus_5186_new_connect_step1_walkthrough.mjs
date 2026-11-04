// ── Trace ──────────────────────────────────────────────
// Change:  DEF-CUS-5186 (the drawing is eight steps, the product was nine) ·
//          DEF-CUS-5198 (the ninth rail cell hung outside the rail at both
//          staff widths) · DEF-CUS-5435 (four elements p086/p087 draws on
//          step 1 were on another page or on no page at all).
// Rules:   B14 rule 42 (a screen is built from the drawing AS AN IMAGE) ·
//          rule 41 (the product UI matches the blueprint) · rule 33 (on-screen
//          text is capped by what it is for) · rule 37 (a figure or a state
//          drawn in a wireframe is an ILLUSTRATION) · hard-won law 6 (no gate
//          in this repo looks at rendered output).
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT A UNIT TEST CANNOT, AND IT IS ONE NUMBER.
//
// `DEF-CUS-5198` is an OVERFLOW: nine rail cells whose content measured 1236px
// inside a 992px box at 1280, so 244px of *Review & confirm* hung outside it.
// **`scrollWidth` vs `clientWidth` is a LAYOUT fact and jsdom computes neither**
// — every element is 0×0 there — so the vitest suite that renders this rail
// cannot see the defect at all, in either direction. It has to be measured in a
// browser that does layout, at both widths the staff app supports (1280 and
// 1440, per the UI generator skill's approved table).
//
// ⚠ AND MEASURE IT AT BOTH, NOT AT ONE. The original fault was 244px at 1280
// and 84px at 1440 — a check run only at 1440 would have called an 84px
// overflow "nearly fine", and one run only at 1920 would have reported it fixed
// while it was at its worst.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def5186/walk";
mkdirSync(OUT, { recursive: true });

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

const browser = await chromium.launch({ executablePath: resolveChromium() });
const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

const page = await browser.newPage({ viewport: { width: 1280, height: 1100 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const stepUrl = (n) => `${BASE}/${TENANT}/connections/new?step=${n}`;

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE RAIL FITS — `DEF-CUS-5198`, measured rather than assumed
// ══════════════════════════════════════════════════════════════════════════
const RAIL = "[data-wizard-step]";
async function measureRail(width) {
  await page.setViewportSize({ width, height: 1100 });
  await page.goto(stepUrl(1), { waitUntil: "networkidle" });
  await page.waitForSelector(RAIL, { timeout: 20000 });
  return page.evaluate((sel) => {
    const cell = document.querySelector(sel);
    const rail = cell.parentElement;
    const cells = [...rail.querySelectorAll("[data-wizard-step]")];
    const last = cells[cells.length - 1];
    return {
      cells: cells.length,
      scrollWidth: rail.scrollWidth,
      clientWidth: rail.clientWidth,
      overflow: rail.scrollWidth - rail.clientWidth,
      // The part of the LAST cell that sits outside the rail's own box — the
      // number DEF-CUS-5198 was filed with, and the one a person actually sees.
      lastCellOutside: Math.max(
        0,
        Math.round(last.getBoundingClientRect().right - rail.getBoundingClientRect().right),
      ),
      lastCellText: last.innerText.replace(/\s+/g, " ").trim(),
    };
  }, RAIL);
}

for (const width of [1280, 1440]) {
  const m = await measureRail(width);
  say(
    `rail @${width}: ${m.cells} cells · scrollWidth ${m.scrollWidth} · clientWidth ${m.clientWidth} ` +
      `· overflow ${m.overflow}px · last cell "${m.lastCellText}" hangs ${m.lastCellOutside}px outside`,
  );
  check(`@${width} the rail carries EIGHT cells`, m.cells === 8, `${m.cells}`);
  check(`@${width} the rail does not scroll sideways`, m.overflow <= 0, `${m.overflow}px`);
  check(`@${width} no cell hangs outside the rail`, m.lastCellOutside === 0, `${m.lastCellOutside}px`);
  await page.screenshot({ path: `${OUT}/rail-${width}.png`, fullPage: false });
}

// ══════════════════════════════════════════════════════════════════════════
// 2 · EVERY ELEMENT p086/p087 DRAWS ON STEP 1 IS ON STEP 1 — `DEF-CUS-5435`
// ══════════════════════════════════════════════════════════════════════════
await page.setViewportSize({ width: 1440, height: 1400 });
await page.goto(stepUrl(1), { waitUntil: "networkidle" });
const seen = await page.evaluate(() => ({
  h1: document.querySelector("h1")?.innerText.trim() ?? "",
  stepLine: [...document.querySelectorAll("p")]
    .map((n) => n.innerText.trim())
    .find((t) => /^Step 1 of/.test(t)) ?? "",
  ids: [...document.querySelectorAll("input,select")].map((n) => n.id).filter(Boolean),
  names: [...document.querySelectorAll("input")].map((n) => n.name).filter(Boolean),
  noHome: document.querySelector("[data-no-home]")?.innerText.trim() ?? "",
  badge: document.querySelector("[data-badge]")?.innerText.trim() ?? "",
  weSchedule: (() => {
    const box = document.querySelector('[data-mode="we_schedule"] button');
    return box === null ? null : { text: box.innerText.trim(), disabled: box.disabled };
  })(),
  prefixPlaceholder: document.querySelector("#nc_prefix")?.placeholder ?? "",
  extPlaceholder: document.querySelector("#nc_external_ref")?.placeholder ?? "",
}));
say("step 1 sees:", JSON.stringify(seen, null, 1));

check("the drawn H1", seen.h1 === "Who is asking, and what for?", seen.h1);
check("the drawn step line", seen.stepLine === "Step 1 of 8 · Owner & scope", seen.stepLine);
for (const id of ["nc_owner_kind", "nc_owner_name", "nc_owner_subcategory", "nc_owner_email",
                  "nc_owner_phone", "nc_prefix", "nc_external_ref"]) {
  check(`${id} is on step 1`, seen.ids.includes(id));
}
check("the scope control is on step 1", seen.names.includes("nc_scope"));
check("the mode control is on step 1", seen.names.includes("nc_mode"));
check("the drawn `if known` placeholder", seen.extPlaceholder === "if known", seen.extPlaceholder);
check("the drawn `BAL` prefix placeholder", seen.prefixPlaceholder === "BAL", seen.prefixPlaceholder);
check("the badge", seen.badge === "Becomes a customer", seen.badge);
// ⚠ B14 RULE 33 — the drawn sentence is 13 words in one; two sentences of 6
// and 5 carry both halves and neither breaches the cap.
check(
  "the drawn no-home strip, in two sentences",
  seen.noHome === "This build has no home yet. The premise arrives next step.",
  seen.noHome,
);
// ⚠ B14 RULE 37 — p087 draws this card SELECTED. A drawn state is an
// ILLUSTRATION; the backend raises NotImplementedError("OQ-249") for it.
check(
  "`We schedule it` is present and DISABLED, whatever the drawing shows",
  seen.weSchedule !== null && seen.weSchedule.disabled === true,
  JSON.stringify(seen.weSchedule),
);
await page.screenshot({ path: `${OUT}/step1-1440.png`, fullPage: true });

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE TWO THAT MOVED ARE GONE FROM THE PAGE THEY LEFT
// ══════════════════════════════════════════════════════════════════════════
await page.goto(stepUrl(3), { waitUntil: "networkidle" });
const unitsIds = await page.$$eval("input", (ns) => ns.map((n) => n.id));
check("the prefix has LEFT the units step", !unitsIds.includes("nc_prefix"), unitsIds.join(","));
check("the units step keeps From and To", unitsIds.includes("nc_from") && unitsIds.includes("nc_to"));

await page.goto(stepUrl(5), { waitUntil: "networkidle" });
const planIds = await page.$$eval("input", (ns) => ns.map((n) => n.id));
check("the target activation date is on Plans & work orders", planIds.includes("nc_target"));

// ══════════════════════════════════════════════════════════════════════════
// 4 · NOTHING IS WRITTEN — `BR-MET-112`, on the wire, at the real widths
// ══════════════════════════════════════════════════════════════════════════
const writes = [];
page.on("request", (req) => {
  if (req.method() !== "GET" && req.url().includes("/api/")) writes.push(`${req.method()} ${req.url()}`);
});
for (const n of [1, 2, 3, 4, 5, 6, 7]) {
  await page.goto(stepUrl(n), { waitUntil: "networkidle" });
}
check("steps 1-7 issue no write of any kind", writes.length === 0, writes.join(" · "));

say(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
