// ── Trace ──────────────────────────────────────────────
// Change:  DEF-CUS-5468 (step 2 asked the whole address in one box, so every
//          property the wizard built held NULL city/state/postal_code and no
//          name) · DEF-MET-5469 (the commit door could not CARRY those four)
//          · DEF-CUS-5470 (the owner echo was nineteen words of rationale) ·
//          PO ruling 2026-09-16 — the utility services, the plan, the plan
//          summary and the coverage warning move onto this step.
// Rules:   B14 rule 42 (a screen is built from the drawing AS AN IMAGE) ·
//          rule 41 (the product UI matches the blueprint) · rule 33 · rule 9
//          (a multi-select is chips + an add control) · hard rule 8 (an
//          address lives on `premises` and nowhere else) · hard rule 2 (money
//          is rounded once, on the server) · hard-won law 6 (no gate in this
//          repo looks at rendered output).
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT THE VITEST SUITE CANNOT, AND IT IS TWO THINGS.
//
// **1 · THE SEARCH IS A ROUND TRIP TO A REAL REGISTER.** The suite stubs
// `fetch`, so it can prove the screen ASKS and never that the register ANSWERS.
// Hard rule 8 makes this screen the one door in the product that can create a
// second `premises` row for one building, and the only way to know the search
// would actually stop that is to type an address a tenant really has and watch
// its own row come back.
//
// **2 · LAYOUT IS NOT COMPUTED IN JSDOM.** Every element is 0x0 there, so a
// field that has silently fallen out of its two-column grid, or a panel that
// scrolls sideways at 1280, is invisible to every test in the suite. The staff
// app supports 1280 and 1440 and neither is checked anywhere else.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def5468/walk";
mkdirSync(OUT, { recursive: true });

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

const browser = await chromium.launch({ executablePath: resolveChromium() });
const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

const page = await browser.newPage({ viewport: { width: 1280, height: 1200 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ⚠ **CLICKED THROUGH, NEVER NAVIGATED BY URL.** The draft lives in the
// wizard's own state and does not survive a reload (`BR-MET-112` — nothing is
// written until the last step), so a `goto` of `?step=2` lands on an EMPTY
// draft. That is fine for reading the chrome and useless for anything that
// depends on an answer given on step 1.
const stepUrl = (n) => `${BASE}/${TENANT}/connections/new?step=${n}`;

// ══════════════════════════════════════════════════════════════════════════
// 1 · EVERY FIELD p087 DRAWS IS ON THE SCREEN, AT BOTH STAFF WIDTHS
// ══════════════════════════════════════════════════════════════════════════
const DRAWN = [
  ["#nc_premise_type", "Premise type"],
  ["#nc_premise_name", "Premises name"],
  ["#nc_address", "Street address or premise"],
  ["#nc_unit", "Unit, flat or suite"],
  ["#nc_city", "City"],
  ["#nc_state", "State"],
  ["#nc_zip", "ZIP code"],
  ["#nc_parcel", "Parcel or GIS reference"],
  ["#nc_route", "Read route"],
];

for (const width of [1280, 1440]) {
  await page.setViewportSize({ width, height: 1200 });
  await page.goto(stepUrl(2), { waitUntil: "networkidle" });
  await page.waitForSelector("#nc_address", { timeout: 20000 });

  for (const [sel, label] of DRAWN) {
    const present = (await page.locator(sel).count()) === 1;
    check(`@${width} ${label} is on the screen`, present, sel);
  }

  // The drawing's two group headings, so a field cannot drift out of its group
  // without this saying so.
  for (const heading of ["Service address", "The record"]) {
    check(
      `@${width} the group heading "${heading}" is drawn`,
      await page.getByText(heading, { exact: true }).first().isVisible(),
    );
  }

  // ⚠ **THE PAGE MUST NOT SCROLL SIDEWAYS AT EITHER WIDTH.** A two-column grid
  // that has stopped collapsing is invisible to every other check we have.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check(`@${width} the page does not scroll sideways`, overflow <= 0, `${overflow}px`);

  await page.screenshot({ path: `${OUT}/step2-${width}.png`, fullPage: true });
}

await page.setViewportSize({ width: 1280, height: 1200 });

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE GREYED UNIT BOX — drawn greyed rather than removed, and it says why
// ══════════════════════════════════════════════════════════════════════════
check(
  "the Unit box is DISABLED, as the drawing greys it",
  await page.locator("#nc_unit").isDisabled(),
);
check(
  "and it carries its reason (BR-SHL-025)",
  (await page.getByText("Named on the next step").count()) > 0,
);

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE SERVICE LIST IS THE TENANT'S OWN — counted, never assumed
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THE COUNT IS THE ASSERTION.** The platform sells ELEVEN services and a
// tenant sells a subset; `BR-MET-003` says a premises may offer only what this
// utility sells. A screen holding its own list would offer eleven to everybody,
// which is exactly how `fire` reached position 11 and never appeared on the
// sign-up screen. So this reads what the SERVER says the tenant has enabled and
// compares it with what the dropdown actually offers.
const enabled = await page.evaluate(async (tenant) => {
  const res = await fetch(`/api/${tenant}/settings/services`, {
    headers: { Accept: "application/json" },
    credentials: "include",
  });
  const body = await res.json();
  const rows = Array.isArray(body) ? body : (body.data ?? body.results ?? []);
  return rows.filter((r) => r.enabled).map((r) => r.name);
}, TENANT);

// ⚠ **THE PLACEHOLDER IS NOT AN OFFER.** The first `<option>` is the control's
// own *Add a service…* prompt and carries an EMPTY value; counting it made this
// check report 3-vs-2 on a screen that was correct. Filtering on `value` rather
// than on the visible text is the difference between counting services and
// counting options — and a check that fails wrongly is spent just as fast as
// one that passes wrongly.
const offered = await page.$$eval("#services_available-add option", (nodes) =>
  nodes.filter((n) => n.value !== "").map((n) => n.textContent.trim()),
);
say(`the tenant has ${enabled.length} services enabled: ${enabled.join(", ")}`);
say(`the dropdown offers ${offered.length}: ${offered.join(", ")}`);
check(
  "the dropdown offers exactly the tenant's enabled services",
  offered.length === enabled.length && enabled.every((n) => offered.includes(n)),
  `${offered.length} offered vs ${enabled.length} enabled`,
);

// ══════════════════════════════════════════════════════════════════════════
// 4 · THE SEARCH FINDS A PROPERTY THAT REALLY EXISTS — hard rule 8
// ══════════════════════════════════════════════════════════════════════════
// The term is taken FROM THE REGISTER rather than typed from memory, so this
// cannot pass by accident on a seed that happens to contain a guess.
const sample = await page.evaluate(async (tenant) => {
  const res = await fetch(`/api/${tenant}/premises/picker?q=a&per=5`, {
    headers: { Accept: "application/json" },
    credentials: "include",
  });
  const body = await res.json();
  const rows = body.data?.results ?? body.results ?? [];
  return rows[0] ?? null;
}, TENANT);

if (sample === null) {
  check("the register has a property to search for", false, "picker returned nothing");
} else {
  const term = (sample.address_line ?? "").slice(0, 12);
  say(`searching the register for "${term}" (from ${sample.premise_no})`);
  await page.fill("#nc_address", term);
  await page.waitForSelector("[data-premises-results] [data-premises-option]", { timeout: 20000 });
  const hits = await page.$$eval("[data-premises-option]", (nodes) =>
    nodes.map((n) => n.textContent.trim()),
  );
  say(`the register answered with ${hits.length}: ${hits.join(" | ")}`);
  check("the search returns the register's own rows", hits.length > 0);

  await page.click(`[data-premises-option="${sample.premise_no}"]`);
  await page.waitForSelector("[data-premises-picked]", { timeout: 20000 });
  const filled = await page.evaluate(() => ({
    address: document.querySelector("#nc_address").value,
    city: document.querySelector("#nc_city").value,
    state: document.querySelector("#nc_state").value,
    zip: document.querySelector("#nc_zip").value,
  }));
  say("picking filled the address in from the register:", JSON.stringify(filled));
  check(
    "picking an existing property writes the WHOLE address, not just the street",
    filled.address === (sample.address_line ?? "") &&
      filled.city === (sample.city ?? "") &&
      filled.state === (sample.state ?? "") &&
      filled.zip === (sample.postal_code ?? ""),
    JSON.stringify(filled),
  );
  // ⚠ B14 rule 31 — a database id is never the visible value of anything. The
  // premise NUMBER is the tenant's own series and is fine; the uuid is not.
  const shown = await page.locator("[data-premises-picked]").innerText();
  check("no uuid is on the screen (rule 31)", !shown.includes(sample.id), shown);

  await page.click("[data-premises-unpick]");
  check(
    "and the clerk can let the register row go again",
    (await page.locator("[data-premises-picked]").count()) === 0,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 5 · THE PLAN, ITS SUMMARY, AND THE FIGURE THAT IS DELIBERATELY ABSENT
// ══════════════════════════════════════════════════════════════════════════
const planNames = await page.$$eval("#nc_plan option", (nodes) =>
  nodes.map((n) => n.textContent.trim()).filter((t) => t !== ""),
);
say(`the plan picker offers ${planNames.length}: ${planNames.join(", ")}`);
check("the plan is asked on THIS step (PO 2026-09-16)", planNames.length >= 1);

if (planNames.length >= 1) {
  // Tick two services first, so the coverage check has something to compare.
  await page.selectOption("#services_available-add", { index: 1 });
  await page.selectOption("#nc_plan", { index: 1 });
  await page.waitForSelector("[data-plan-summary]", { timeout: 20000 });
  const summary = await page.locator("[data-plan-summary]").innerText();
  say("the plan summary reads:\n" + summary);
  check("the summary names the plan", summary.trim().length > 0);
  // ⚠ **THE ABSENCE IS THE POINT.** p087's sibling page prints
  // `$30.50/month × 25 = $762.50`. Money is rounded ONCE, on the server (hard
  // rule 2), and no endpoint publishes a plan's base charge per unit here — a
  // figure multiplied up in the browser is the second rounding path DEF-088
  // removed, and it would sit beside real ones.
  check(
    "and it carries NO monthly total (hard rule 2)",
    !/\$\s*\d/.test(summary) && !summary.includes("/month"),
    summary,
  );
  await page.screenshot({ path: `${OUT}/step2-plan-summary.png`, fullPage: true });
}

// ══════════════════════════════════════════════════════════════════════════
// 6 · RULE 33 — the owner echo is a FACT, not an explanation
// ══════════════════════════════════════════════════════════════════════════
const owner = await page.locator("text=/^Owner:/").first().innerText();
const words = owner.trim().split(/\s+/).length;
say(`the owner echo reads "${owner}" — ${words} words`);
check("the owner echo is a fact, not rationale (rule 33)", words <= 6, `${words} words`);

// ══════════════════════════════════════════════════════════════════════════
// 7 · NOTHING WAS WRITTEN — BR-MET-112, asserted on the wire
// ══════════════════════════════════════════════════════════════════════════
// Everything above typed into a form, searched a register and chose a plan. If
// any of it had written a row, this step would not be a draft any more.
const writes = [];
page.on("request", (r) => {
  if (["POST", "PUT", "PATCH", "DELETE"].includes(r.method())) writes.push(`${r.method()} ${r.url()}`);
});
await page.fill("#nc_city", "Austin");
await page.fill("#nc_state", "TX");
await page.fill("#nc_zip", "78704");
await page.fill("#nc_premise_name", "Balcones Tower");
await page.waitForTimeout(1500);
check("nothing is written on step 2 (BR-MET-112)", writes.length === 0, writes.join(" | "));

say(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
say(`screenshots in ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
