// ── Trace ──────────────────────────────────────────────
// Change:  CR-087 lane B — the tax wizard (four steps → three), the tax detail
//          (six tabs → three, remittance folded into Overview), and `PRB-05`
//          (the premises count narrows on customer class and service).
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do web
//          walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate looks at rendered output) · hard-won law 2's
//          mirror (a live screen behind a dead control).
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS, AND WHY EACH ONE IS HERE RATHER THAN IN A UNIT TEST.
//
//   1 · the three wizard steps, clicked in order. A unit test renders a step in
//       isolation; only a click proves `Continue` reaches the next one and that
//       the rail's fence (BR-SHL-018) lets it.
//   2 · the premises count on step 1, read BEFORE and AFTER ticking a customer
//       class. That is `PRB-05`'s own done-when — *"ticking Commercial only
//       moves the count … before the clerk leaves the step"* — and it is a
//       statement about a live server answering a live query, which no
//       front-end test can make.
//   3 · the tax detail's three tabs, and its Edit button's `disabled`
//       ATTRIBUTE. `DEF-RAT-4647` was a control greyed out over a working
//       screen for two weeks with every check green; the only thing that could
//       have caught it is somebody looking.
//
// ⚠ IT READS THE `disabled` ATTRIBUTE AND NEVER THE WORD. The shared Button's
// utility string carries `disabled:opacity-45`, so a text search for
// "disabled" passes on an ENABLED button — the exact false pass the unit test
// beside this one records.
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8401";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr087b";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (...parts) => console.log(...parts);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── 1 · the wizard, three steps ─────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/new`, { waitUntil: "networkidle" });
await page.waitForSelector("nav[aria-label] button", { timeout: 30000 });

const rail = await page.$$eval("nav[aria-label] button", (bs) =>
  bs.map((b) => b.textContent.replace(/^\d+/, "").trim()),
);
say("STEP RAIL:", JSON.stringify(rail), `(${rail.length} steps)`);
say("SUB-LINE:", (await page.textContent(".page-header-rollup")).trim());
say("STEP COUNT LINE:", (await page.textContent("[data-kicker]")).trim());

// ⚠ THE COUNT IS READ FROM A `data-` HOOK AND NEVER SCRAPED OUT OF THE PROSE.
// The first draft of this walk matched a sentence with a regex and came back
// with the whole navigation rail — a finding about the WALK, not the product,
// and the same shape `po20260908_walkthrough.mjs` records: a check written
// against an English label stops working in ten of the eleven catalogues and
// never says so.
const readCount = async () => {
  await page.waitForSelector("[data-matched-premises]", { timeout: 20000 }).catch(() => {});
  return page.evaluate(() => {
    const el = document.querySelector("[data-matched-premises]");
    if (!el) {
      const note = [...document.querySelectorAll("[data-note]")].map((n) => n.textContent.trim());
      return { count: null, sentence: note.find((t) => /premis/i.test(t)) ?? "(no count element)" };
    }
    return {
      count: Number(el.getAttribute("data-matched-premises")),
      total: Number(el.getAttribute("data-matched-total")),
      narrowed: el.getAttribute("data-matched-narrowed"),
      sentence: (el.querySelector("p")?.textContent ?? "").trim(),
    };
  });
};
say("COUNT, nothing restricted:", JSON.stringify(await readCount()));

// ⚠ `PRB-05`'s own done-when, on a live server: tick ONE customer class and
// read the number again WITHOUT leaving the step.
// ⚠ THE INPUT IS `sr-only` WITH A DECORATIVE SPAN OVER IT, so a plain click on
// the input is intercepted and times out on a perfectly healthy screen. Check
// the LABEL, which is what a person clicks.
const commercial = await page.$("#class-commercial");
if (commercial) {
  await page.click('label[for="class-commercial"]');
  await page.waitForTimeout(3000);
  say("COUNT, Commercial ticked:", JSON.stringify(await readCount()));
  await page.click('label[for="service-water"]').catch(() => say("  (no water service on this tenant)"));
  await page.waitForTimeout(3000);
  say("COUNT, + Water ticked:", JSON.stringify(await readCount()));
} else {
  say("!! #class-commercial is NOT on step 1 — the move did not land");
}

await page.screenshot({ path: `${OUT}/01-step1.png`, fullPage: true });

// Step 1 → 2. The name and the authority are the only two the client gates on.
await page.fill("#name", "Walkthrough surcharge");
const options = await page.$$eval("#jurisdiction option", (os) =>
  os.map((o) => o.value).filter((v) => v && v !== "__new__"),
);
if (options.length > 0) await page.selectOption("#jurisdiction", options[0]);
await page.click('button:has-text("Continue")');
await page.waitForTimeout(1500);
say("AFTER CONTINUE:", (await page.textContent("[data-kicker]")).trim());
say("STEP 2 HEADING:", (await page.textContent("h2")).trim());
const hasFrom = (await page.$("#effective_from")) !== null;
say("effective_from on step 2:", hasFrom);
const hasDue = (await page.$("#due_date_rule")) !== null;
say("a remittance field on step 2 (must be false):", hasDue);
await page.screenshot({ path: `${OUT}/02-step2.png`, fullPage: true });

await page.click('button:has-text("Continue")');
await page.waitForTimeout(1500);
say("STEP 3:", (await page.textContent("[data-kicker]")).trim(), "—", (await page.textContent("h2")).trim());
const commit = await page.$$eval("button", (bs) =>
  bs.map((b) => b.textContent.trim()).filter((t) => /save|create/i.test(t)),
);
say("COMMIT BUTTONS ON STEP 3:", JSON.stringify(commit));
await page.screenshot({ path: `${OUT}/03-step3.png`, fullPage: true });

// ── 2 · the tax detail ──────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
const firstTax = await page.$('a[href*="/plans-rates/taxes-fees/"]');
if (!firstTax) {
  say("!! no tax rows on the landing tab — cannot walk the detail");
} else {
  await firstTax.click();
  await page.waitForTimeout(3000);
  const tabs = await page.$$eval("nav[aria-label] button, [role=tab]", (bs) =>
    bs.map((b) => b.textContent.trim()).filter(Boolean),
  );
  say("DETAIL TABS:", JSON.stringify(tabs), `(${tabs.length})`);

  const actions = await page.$$eval(".page-header-actions button", (bs) =>
    bs.map((b) => ({ label: b.textContent.trim(), disabled: b.hasAttribute("disabled"), title: b.getAttribute("title") })),
  );
  say("HEADER ACTIONS:", JSON.stringify(actions));

  const blocks = await page.$$eval("[data-definition-block]", (ds) =>
    ds.map((d) => d.getAttribute("data-definition-block")),
  );
  say("OVERVIEW BLOCKS:", JSON.stringify(blocks));

  // ⚠ READ THE BLOCKS, NOT `main`. The first draft of this walk scraped
  // `page.textContent("main")` and reported MISSING over three facts that were
  // plainly on screen — a check looking at the wrong thing, which is law 7's
  // fourth shape and which a screenshot disproved in one glance.
  const blockText = await page.$$eval("[data-definition-block]", (ds) =>
    Object.fromEntries(ds.map((d) => [d.getAttribute("data-definition-block"), d.innerText])),
  );
  for (const [what, block, needle] of [
    ["Taxed / Not taxed (DEF-RAT-4662)", "taxed", /\bTaxed\b/],
    ["the discount treatment (DEF-RAT-4661)", "taxed", /discount/i],
    ["the remittance block", "remittance", /Remitted to/i],
  ]) {
    const text = blockText[block] ?? "";
    say(`  ${needle.test(text) ? "on screen" : "MISSING"} — ${what}`);
  }
  const form = await page.$("[data-tax-remittance-form]");
  say("editable filing form on the page:", form !== null);
  if (form) {
    const boxes = await page.$$eval("[data-tax-remittance-form] input, [data-tax-remittance-form] select", (es) =>
      es.map((e) => e.id).filter(Boolean),
    );
    say("  its fields:", JSON.stringify(boxes));
  }
  await page.screenshot({ path: `${OUT}/04-detail.png`, fullPage: true });
}

await browser.close();
say("screenshots:", OUT);
